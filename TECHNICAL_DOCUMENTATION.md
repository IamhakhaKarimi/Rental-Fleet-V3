# Balkan Car Rentals — Fleet Console v3.0 · Technical Documentation

> Authoritative companion to `CLAUDE.md`. Cross-reference: `DOCUMENTATION.md`
> (developer docs), `WALKTHROUGH.md` (per-page walkthrough), `README_SETUP.md`
> (end-user setup). Everything below was verified against the source tree.

---

## 1. Overview & purpose

**Balkan Car Rentals — Fleet Console** is a single-page **Streamlit** web
application for running a small car-rental business end-to-end:

- **Fleet** — a catalogue of vehicles with status, rate, mileage, photos.
- **Reservations** — booking, availability math, active-rental cards, returns.
- **Customers** — directory, rental history, per-rental invoices.
- **Occupancy timeline** — a visual Gantt-style view of who has which car when.
- **Finance** — income/cost ledgers rolled up into revenue, cost and P&L views.
- **Settings** — business identity, users/roles, language, licensing, audit log.

Distinguishing characteristics:

- **Six UI languages** — Turkish (default), English, German, Italian, Spanish,
  Albanian (`tr / en / de / it / es / sq`). Albanian is staff-only.
- **Role-gated** — four roles: `visitor < employer < admin < super_admin`.
- **Self-bootstrapping** — on first run it builds its own SQLite schema, seeds the
  fleet from a CSV, and creates a default super-admin (`admin` / `admin`).
- **~8,000 LOC Python** across config / core / data / services / views / ui.
- **Money is integer cents** end-to-end; **dates are ISO-8601 text**.

The codebase version is `APP_VERSION = "3.0"` (`config/settings.py`). The schema
header still reads "v2.0" but is current.

---

## 2. Technology stack & dependencies

All dependencies are **pinned** in `requirements.txt` so behaviour is identical
across machines:

| Package | Version | Role |
|---|---|---|
| `streamlit` | `1.58.0` | UI framework / runtime; the whole app is a Streamlit script |
| `SQLAlchemy` | `2.0.51` | DB engine + Core SQL execution over SQLite (future Postgres swap = connection-string change) |
| `pandas` | `3.0.2` | DataFrames for tables, charts, and CSV seed import |
| `bcrypt` | `5.0.0` | Password hashing (per-password salt) |
| `extra-streamlit-components` | `0.1.81` | `CookieManager` for the remember-me cookie |
| `fpdf2` | `2.8.7` | Pure-Python PDF generation for the downloadable invoices (`ui/pdf.py`) |

**Removed on purpose:** `streamlit-option-menu` — on Streamlit 1.58 its component
iframe collapses to 0px height and hides the whole nav, so navigation is built
from native `st.button` widgets instead (`ui/nav.py`).

**Runtime notes.** Targets **Python 3.11+** (the dev machine runs 3.12).
**Pillow (PIL)** is used opportunistically for photo/logo resizing; if it is
missing the code falls back to storing the original bytes. First paint requires
the network (Google Fonts, the vis-timeline CDN, the cookie/menu components).

---

## 3. Architecture & layering rules

The app enforces a **strict one-way dependency graph**:

```
app.py ─▶ views/ , ui/ ─▶ services/ ─▶ data/repositories/ ─▶ core/db.py ─▶ fleet.db
                       ╲
                        ╲──▶ config/ (settings · roles · i18n · terms)  ← used by ALL layers
```

| Layer | May do | Must NOT do |
|---|---|---|
| `app.py` | bootstrap DB, auth gate, nav, route | hold business logic |
| `views/` | render a page; call services + repos; gate with `can()`; audit | write raw SQL |
| `ui/` | shared widgets, theme, invoice/timeline rendering | write raw SQL |
| `services/` | business logic: auth/hashing, availability, finance rollups, audit, licensing, email | use Streamlit widgets; talk to SQLite directly outside its own SQL helpers |
| `data/repositories/` | **all SQL**; return **plain dicts** | hold business rules; import Streamlit |
| `core/db.py` | engine, schema, migrations, pragmas | know about pages |
| `config/` | constants, roles, i18n, terms | import upward layers |

Concrete rules (from `CLAUDE.md`, confirmed in code):

- **All SQL lives in `data/repositories/`** (and the few read-only helpers in
  `services/scheduling_service.py` + `services/finance_service.py`, which are
  query rollups). Repositories return **plain dicts**, never ORM objects.
- **`services/` hold business logic** — no Streamlit widgets.
- **`views/render_<name>(user)`** is the unit a router entry in `app.py` calls.
- The `user` object everywhere is `{"username","full_name","role","lang","email"}`
  (the public shape produced by `auth_service._public`).
- **Streamlit-free lower layers** — `core/`, `data/`, `services/`, and
  `config/settings.py` / `config/roles.py` do **not** import Streamlit, so they
  run under plain `python`. `config/i18n.py`, `ui/`, and `views/` import Streamlit.

---

## 4. Directory / file map

| Path | Responsibility |
|---|---|
| `app.py` | Entrypoint: `st.set_page_config`, `@st.cache_resource` bootstrap → `init_db()`, cookie priming reruns, auth gate, sidebar nav, page router |
| `config/settings.py` | Paths (`DB_PATH`, `SEED_CSV`), brand (`APP_NAME/TAGLINE/VERSION/ICON`), `LANGUAGES`, `STAFF_ONLY_LANGS`, currency, `VEHICLE_STATUSES`/`RENTAL_STATUSES`, `STATUS_TOKEN`, booking defaults |
| `config/roles.py` | `ROLES`, `ROLE_LEVEL`, `ROLE_LABEL_KEY`, `PERMISSION_MIN_LEVEL`, `can()`, `role_level()`, `assignable_roles()` |
| `config/i18n.py` | `TRANSLATIONS` (TR/EN inline + merged DE/IT/ES/SQ), `init_lang()`, `t()`, `t_lang()`, `set_lang()`, `DEFAULT_LANG` |
| `config/lang_de.py` / `lang_it.py` / `lang_es.py` / `lang_sq.py` | Auto-generated language modules, each exposing `UI` (all UI keys) + `TERMS` (rental-terms title + 12 rules) |
| `config/terms.py` | `RENTAL_TERMS` (TR/EN inline + merged DE/IT/ES/SQ), `rental_terms(lang)` |
| `core/db.py` | `get_engine()` (shared engine + SQLite pragmas), `init_db()`, the four migrations, first-run seed call, `ensure_default_admin`, session purge |
| `core/schema.sql` | DDL for all 11 tables + indexes (idempotent `CREATE ... IF NOT EXISTS`) |
| `data/repositories/vehicles.py` | Vehicle CRUD, `_next_id()` (`C001…`), `list_vehicles` (no photo data), `fleet_counts`, status setters, soft/hard delete, restore |
| `data/repositories/customers.py` | `get_or_create_customer`, `update_customer`, `list_customers` (with rental count + "registered-by" snapshot subqueries) |
| `data/repositories/rentals.py` | `next_deal_id` (`RENT-YYYYMM-NNN`), create/list/cancel/reactivate rentals, `settle_and_close`, `get_rental_full`, `vehicle_has_active_rental`, `update_creator` |
| `data/repositories/charges` | (no separate file — charges are written/read via `rentals.py` + `finance_service.py`) |
| `data/repositories/vehicle_costs.py` | Expense ledger: `COST_TYPES`, `add_cost`, `list_costs`, `delete_cost`, rollups by type/month/year/vehicle |
| `data/repositories/users.py` | User + session SQL; never hashes (gets pre-hashed passwords) |
| `data/repositories/app_settings.py` | Key/value settings: `get/set_setting`, business name, logo (`get/set/clear_logo`) |
| `data/repositories/vehicle_photos.py` | Multi-photo per vehicle: `primary_photo`, `list_photos`, `add_photos`, `delete_photo`, `photos_version`, `photo_count`, `clear_photos` (unused) |
| `data/repositories/licenses.py` | License-record ledger CRUD (`list/get/add/update/delete_license`) |
| `data/repositories/audit.py` | Append-only `record()` (best-effort, swallows errors) + `list_recent()` |
| `data/repositories/admin_ops.py` | Destructive resets (super-admin): `reset_finance()`, `reset_fleet()` |
| `data/seed/import_csv.py` | One-time/idempotent `seed_vehicles_from_csv` (INSERT OR IGNORE keyed on `vehicle_id`) |
| `services/auth_service.py` | Hashing, login, sessions, account management, language pref, last-super-admin guard, password recovery |
| `services/scheduling_service.py` | `compute_return`, `return_state` (overdue/due-soon/ok), `is_vehicle_free`, `available_vehicles` |
| `services/finance_service.py` | Revenue/cost/P&L rollups; `_merge` of income + cost; `profit_by_vehicle` |
| `services/audit_service.py` | Thin convenience layer over the audit repo |
| `services/email_service.py` | SMTP config + `send_mail` (STARTTLS, never raises), `resolve_recipient`, `FALLBACK_EMAIL` |
| `services/licensing_service.py` | `licensed_year`, `set/extend_licensed_year`, `max_date`, `current_year` |
| `views/dashboard.py` | Home page (staff KPIs/timeline/cards/booking/table) + visitor browse hero |
| `views/reservations.py` | Active-rental cards (overdue colouring), booking, return workflow, timeline |
| `views/fleet.py` | Single action-rich vehicle-card grid: add/edit/delete dialogs, status quick-buttons, photo manager, archived restore |
| `views/customers.py` | Card grid for active renters + full table for finished; per-customer dialog, invoice flags, reassign |
| `views/finance.py` | Five tabs: Overview / Monthly / Yearly / By Vehicle / Costs |
| `views/settings.py` | Tabs: Business, Users, License (+ SMTP + danger zone), Language, Profile/Password, Activity |
| `ui/theme.py` | `TOKENS` colour palette, font import, `inject_theme()`, sidebar/KPI/badge CSS, mobile responsiveness |
| `ui/nav.py` | The minimalistic 236px sidebar (`NAV_ITEMS`, `top_nav`, role-gating, footer bell/settings/account/logout) |
| `ui/components.py` | `format_eur`, `page_header`, `section_header`, `status_badge`, `kpi_tile` |
| `ui/booking.py` | Availability search + rental-registration popup (`render_booking_panel`, `open_rental_dialog`, `_rental_form_body`) |
| `ui/invoice.py` | `build_invoice_html`, `render_invoice` (HTML preview + PDF download) |
| `ui/license_invoice.py` | `build_license_invoice_html`, `render_license_invoice` |
| `ui/pdf.py` | `build_invoice_pdf`, `build_license_invoice_pdf` (fpdf2, Unicode font autodetect) |
| `ui/timeline.py` | `render_timeline` (vis-timeline via CDN, custom "NOW" line, zoom buttons) |
| `ui/notifications.py` | `render_bell` + reminders dialog (overdue/due-soon, WhatsApp/call links) |
| `ui/photos.py` | Photo/logo encoding (Pillow), `render_photo`, cached lazy thumbnail, `invalidate_cache` |
| `ui/auth_view.py` | Login form, session restore, language picker, forgot-password, `logout` |

`__init__.py` files in every package are empty markers.

---

## 5. Data model

SQLite database `fleet.db` (next to `app.py`). **Money is INTEGER cents; dates are
ISO-8601 text.** WAL mode means `fleet.db-wal` / `fleet.db-shm` sidecar files
exist while running. DDL lives in `core/schema.sql` (11 physical tables: 8 "core"
+ `sessions` + `vehicle_photos` + `licenses`). All `CREATE` statements are
`IF NOT EXISTS`, so re-running the schema is safe.

### 5.1 `vehicles`
| Column | Type | Notes |
|---|---|---|
| `vehicle_id` | TEXT PK | ID scheme `C001…` (`vehicles._next_id`, zero-padded to 3) |
| `make_model` | TEXT NOT NULL | |
| `year` | INTEGER | |
| `license_plate`, `color` | TEXT | |
| `mileage` | INTEGER DEFAULT 0 | |
| `status` | TEXT NOT NULL DEFAULT 'Available' | CHECK in `('Available','Rented','In Garage','Maintenance','DELETED')` |
| `base_daily_rate` | INTEGER cents, ≥0 | |
| `maintenance_charge` | INTEGER cents | accrues damage charges on return |
| `acquisition_cost`, `acquisition_date` | INTEGER / TEXT | |
| `notes` | TEXT | |
| `photo` | TEXT | legacy base64 — **write-only** now (see gotchas) |
| `created_at`, `updated_at` | TEXT | |

**Soft delete:** `status = 'DELETED'` (via `soft_delete`). Hard delete via
`hard_delete` (super-admin) leaves orphan `vehicle_photos` rows behind.

### 5.2 `customers`
`customer_id` INTEGER PK AUTOINCREMENT, `full_name` NOT NULL, `phone`,
`id_passport`, `created_at`. `get_or_create_customer` de-duplicates on
`(full_name, phone)`.

### 5.3 `rentals`
| Column | Type | Notes |
|---|---|---|
| `deal_id` | TEXT PK | `RENT-YYYYMM-NNN` (`rentals.next_deal_id`) |
| `customer_id` | INTEGER FK → customers | |
| `vehicle_id` | TEXT FK → vehicles | |
| `start_dt`, `end_dt` | TEXT (ISO-8601 `YYYY-MM-DDTHH:MM:SS`) | |
| `rental_days` | INTEGER ≥0 | |
| `daily_rate`, `total_amount`, `deposit` | INTEGER cents | |
| `status` | TEXT DEFAULT 'Active' | CHECK in `('Active','Closed')` |
| `contract_signed` | TEXT DEFAULT 'No' | "Yes"/"No" |
| `return_notes` | TEXT | |
| `created_by` / `created_by_name` / `created_by_role` | TEXT | **snapshot** of the booking staff |
| `invoice_lang` | TEXT DEFAULT 'tr' | per-rental invoice language |
| `created_at` | TEXT | |

> Caveat: `create_rental` clamps the stored `invoice_lang` to `('tr','en')` even
> though the booking popup offers all six languages; the invoice renderer can
> still display any of the six on demand.

### 5.4 `charges` (income ledger)
`charge_id` PK, `deal_id` FK, `vehicle_id` FK, `type` CHECK in
`('rental','overdue_penalty','damage','deposit','refund')`, `amount` (cents),
`occurred_at`. **Revenue = rental + overdue_penalty + damage**; deposit/refund are
excluded from revenue.

### 5.5 `vehicle_costs` (expense ledger)
`cost_id` PK, `vehicle_id` FK, `type` CHECK in `('insurance','maintenance',
'depreciation','fuel','financing','registration','other')` (7 types), `amount`
(cents), `period_date` (`YYYY-MM-DD`), `note`. Mirror list lives in
`vehicle_costs.COST_TYPES`.

### 5.6 `users`
`user_id` PK AUTOINCREMENT, `username` UNIQUE, `password_hash` (bcrypt), `full_name`,
`role` CHECK in `('super_admin','admin','employer','visitor')`, `is_active`
(0/1), `lang` DEFAULT 'tr', `email`, `created_at`.

### 5.7 `sessions`
`token_hash` PK (**SHA-256 of the random remember-me token** — the raw token only
lives in the browser cookie), `username`, `expires_at`, `created_at`.

### 5.8 `audit_log`
`id` PK, `username`, `action`, `entity`, `entity_id`, `detail`, `ts`. Append-only.

### 5.9 `app_settings`
`key` PK, `value`, `updated_at`. Holds `business_name`, `company_logo` (base64 PNG),
`licensed_until_year`, and SMTP keys (`smtp_host/port/user/pass/from`).

### 5.10 `vehicle_photos`
`photo_id` PK AUTOINCREMENT, `vehicle_id` FK, `photo` (base64 JPEG, uniform size),
`position`, `created_at`. Kept out of `vehicles` so listings stay light.

### 5.11 `licenses`
`license_id` PK AUTOINCREMENT, `licensee`, `year`, `years` DEFAULT 1, `amount`
(cents), `purchase_date` DEFAULT `date('now')`, `notes`, `created_at`. Ships in
`schema.sql`, so existing DBs get it idempotently on next start.

### 5.12 Indexes
`idx_rentals_vehicle/status/customer/interval`, `idx_charges_deal/vehicle`,
`idx_costs_vehicle`, `idx_vphotos_vehicle`, `idx_sessions_expires`. The
`idx_rentals_interval (vehicle_id, start_dt, end_dt)` index powers the
availability overlap query.

### 5.13 Startup migrations — `core/db.init_db()`

`init_db()` runs the schema, then **four migrations in order**, then seeds (if the
fleet is empty), ensures a default admin, and purges expired sessions:

1. **`_migrate_users`** — if the legacy `users` table lacks `full_name`, drop and
   recreate it from `schema.sql` (safe because no real accounts existed yet).
2. **`_migrate_rentals`** — additively `ALTER TABLE` to add the snapshot columns
   `created_by`, `created_by_name`, `created_by_role` to older DBs.
3. **`_migrate_add_columns`** — additive columns: `vehicles.photo`, `users.lang`,
   `users.email`, `rentals.invoice_lang`.
4. **`_migrate_photos`** — move any legacy single `vehicles.photo` into the
   `vehicle_photos` table (once; skips vehicles already in the table).

Fresh DBs get everything straight from `schema.sql`; existing DBs get the new
columns via `ALTER`.

---

## 6. Core subsystems

### 6.1 Authentication & sessions — `services/auth_service.py`, `ui/auth_view.py`

- **Hashing:** `bcrypt.hashpw` / `checkpw` (per-password salt). `MIN_PASSWORD_LEN = 6`.
- **First-run seed:** `ensure_default_admin()` inserts `admin` / `admin` as
  `super_admin` when there are zero users.
- **Login:** `authenticate(username, password)` returns the public user dict
  (`_public`) or `None` for inactive/wrong creds.
- **Remember-me:** `create_session(username, remember)` makes a 256-bit
  `secrets.token_urlsafe(32)` token; only its **SHA-256** is stored in `sessions`.
  Remember-me ON ⇒ valid `REMEMBER_DAYS = 30`; OFF ⇒ `SESSION_HOURS = 12`. So even
  a DB leak can't replay cookies. `validate_session` checks the hash + expiry +
  active flag; `destroy_session` deletes the row.
- **Cookie:** `ui/auth_view.COOKIE_NAME = "bcr_session"`. The `CookieManager` is
  created **once** in `app.py`. On login the cookie is set and `time.sleep(0.4)`
  lets the write reach the browser before the rerun. Logout invalidates the
  server session first, deletes the cookie, clears `session_state`.
- **Account management:** `create_user`, `change_password`, `set_user_role`,
  `set_user_active`, `change_username` (drops old sessions), `set_user_email`,
  `set_user_full_name`. All role changes are bounded by `assignable_roles`.
- **Last-super-admin guard:** `is_last_active_super_admin(username)` returns True
  iff that user is the only active super-admin; the Users tab disables role-change
  and deactivate for that account.
- **Password recovery:** `self_recover` (login forgot-password; admin/super-admin
  only — others get `recover_admin_only`) delivers to the account's own email;
  `admin_recover_child` resets a child user and delivers to the **acting admin's**
  email. `_gen_password` makes a 10-char alphanumeric password.

### 6.2 Roles & permissions — `config/roles.py`

- **Roles & levels:** `ROLE_LEVEL = {visitor:0, employer:1, admin:2, super_admin:3}`.
  The role id is **`employer`** but its label key is `role_employer` =
  "Employee / Çalışan".
- **`can(user, perm)`** = `role_level(user) >= PERMISSION_MIN_LEVEL[perm]`
  (unknown perms default to level 99 = deny).
- **Permission → minimum level:**

  | Permission | Min level |
  |---|---|
  | `view_dashboard`, `view_reservations`, `view_fleet` | 0 (everyone) |
  | `view_management`, `create_reservation`, `cancel_reservation` | 1 (employer+) |
  | `edit_fleet`, `soft_delete_vehicle`, `view_finance`, `manage_users` | 2 (admin+) |
  | `assign_admin_roles`, `hard_delete_vehicle`, `edit_business_settings` | 3 (super-admin) |

- **`ROLE_LABEL_KEY`** maps each role id to a translation key; labels are
  themselves i18n keys (`role_super_admin`, etc.).
- **`assignable_roles(actor)`** — super-admin grants any role; admin grants only
  `employer`/`visitor`; lower roles grant none.
- Gating is applied both in the nav (hides pages) and again in `app.py`'s router
  (defense-in-depth) — a forced page key still falls back to `dashboard`.

### 6.3 Internationalization — `config/i18n.py`, `config/lang_*.py`, `config/terms.py`

- **`t("key")`** resolves against the session language, falling back to English,
  then to the raw key. **Every user-facing string goes through `t()`** (or
  `t_lang(key, lang)` for explicit-language rendering, used by invoices).
- **Key set:** identical across all six languages — **354 keys × 6** (verified at
  runtime; `CLAUDE.md`'s "334" is stale).
- **Storage:** TR and EN live **inline** in `TRANSLATIONS` in `config/i18n.py`.
  DE/IT/ES/SQ live in auto-generated `config/lang_<code>.py` modules, each exposing
  two plain dicts: `UI` (every UI string) + `TERMS` (rental-terms title + 12 rules).
  `config/i18n.py` imports each `UI` into `TRANSLATIONS`; `config/terms.py` imports
  each `TERMS` into `RENTAL_TERMS`.
- **Registry:** `LANGUAGES = {code: "flag + endonym"}` and
  `STAFF_ONLY_LANGS = {"sq"}` live in the Streamlit-free `config/settings.py`, so
  services can validate a language without importing Streamlit.
- **Per-user language:** stored on `users.lang`, chosen in Settings → Language,
  adopted on login/restore by `auth_view._apply_user_lang`. There is **no** top-bar
  language toggle. The Language tab filters `STAFF_ONLY_LANGS` by role: Albanian is
  offered only at level ≥ 1.
- **Invoices are language-independent of the UI** — the customer document offers
  **all six** languages regardless of role gating
  (`build_invoice_html` validates `lang` against `LANGUAGES`).

### 6.4 Money handling

- **INTEGER cents everywhere** in the DB and through services/repositories.
- **Form inputs are euros** → multiply by 100 before the repository
  (e.g. `int(rate) * 100` in booking and fleet forms).
- **Display only** via `ui.components.format_eur(cents)` → `€30` (drops decimals
  for whole amounts) or `€30.50`; handles negatives. `ui/pdf.py._eur` mirrors it.
- The CSV importer's `_to_cents` strips `€`/`$`/commas and rounds to cents.
- Never store floats.

### 6.5 Scheduling / availability — `services/scheduling_service.py`

- **`compute_return(start_date, start_time, days, return_time)`** → the exact
  return `datetime` (start date + N days, at the chosen return time).
- **`return_state(end_dt_str, now)`** → `(state, hours)` where state ∈
  `{"overdue","due_soon","ok"}`; `DUE_SOON_HOURS = 24` is the alert window. This is
  a derived view — the stored vehicle status stays `Rented`. Three consumers: the
  notification bell, timeline colouring, and reservation cards.
- **`is_vehicle_free(vehicle_id, start, end)`** — interval-overlap test
  (`MAX(start_a, start_b) < MIN(end_a, end_b)`) against Active rentals; used both
  in availability listing and re-checked at save time.
- **`available_vehicles(start, end)`** — excludes DELETED/In Garage/Maintenance/
  Rented vehicles and any with an overlapping Active rental, using the
  `idx_rentals_interval` index.

### 6.6 Finance — `services/finance_service.py`, `data/repositories/vehicle_costs.py`

- **Revenue** is drawn from `charges` (only `rental + overdue_penalty + damage`):
  `revenue_summary`, `revenue_by_vehicle`, `revenue_by_month`, `revenue_by_year`.
- **Costs** come from `vehicle_costs`: `cost_total`, `cost_by_type/month/year/vehicle`.
- **P&L** joins the two: `pnl_summary` (income, cost, net, margin %),
  `pnl_by_month`, `pnl_by_year` (via `_merge` on the period key), and
  `profit_by_vehicle` (per-car income − cost, sorted by net descending).
- All computed in cents; euros only at display in `views/finance.py`.

### 6.7 Audit logging — `services/audit_service.py`, `data/repositories/audit.py`

- **Audit every mutation:** after a successful create/update/delete, call
  `audit_service.record(user, action, entity, entity_id, detail)`. The repo's
  `record` is **best-effort** — wrapped in try/except so a logging failure never
  aborts the real work.
- `recent(limit)` feeds the Settings → Activity tab, which masks higher-ranked
  actors as "system admin" and offers filter-by-action / filter-by-user.

### 6.8 Vehicle photos — `data/repositories/vehicle_photos.py`, `ui/photos.py`

- Multiple photos per vehicle, stored as base64 JPEG, all cropped to one uniform
  `PHOTO_SIZE = (640, 480)` (4:3) via Pillow `ImageOps.fit` so cards line up.
  Missing/unreadable Pillow → raw bytes; no photo → 🚘 avatar.
- **Listings carry no photo data** (`list_vehicles` omits it). Thumbnails load the
  **primary** photo lazily and are cached with `@st.cache_data`, keyed on
  `photos_version()` = `MAX(photo_id)`. Call `photos.invalidate_cache()` after every
  add/delete. Only Dashboard "Available now" cards and the Fleet-edit tab render
  photos.
- Display heights are fixed (dashboard 140/150, fleet card 150, edit 120, gallery
  90) via `object-fit:cover`.
- Caveats: `hard_delete` leaves orphan photo rows; `clear_photos()` is dead code.

### 6.9 Annual licensing — `services/licensing_service.py`

- `licensed_year()` reads `app_settings.licensed_until_year`, floored to the
  current year (can only **extend** forward).
- `max_date()` = 31 Dec of the licensed year; the three booking/cost date pickers
  cap at it (`ui/booking.py` ×2, `views/finance.py` cost date). The license-invoice
  purchase-date picker is intentionally **not** capped (it's metadata).
- The super-admin License tab is a full CRUD over `licenses`; adding/editing a
  later-year record calls `extend_licensed_year` to push the cap forward. There is
  also a "set licensed year" dropdown (`set_licensed_year`).

### 6.10 Email / password recovery — `services/email_service.py`

- SMTP config lives in `app_settings` (`smtp_host/port/user/pass/from`).
  `is_configured()` needs both `smtp_host` and `smtp_from`.
- `send_mail` uses STARTTLS and **never raises** (returns `(sent, info)`).
- When SMTP is unset, recovery mail isn't sent — the new 10-char password is shown
  on-screen (`recover_fallback`) and audited.
- `FALLBACK_EMAIL = "hakamaneshkarimi@gmail.com"` (distinct from the owner login
  `admin@ghoncha.com`). `resolve_recipient` falls back to it.
- Wired across four touchpoints: login forgot-password, profile email + child
  reset + child email (Users tab), and the SMTP form inside the License tab.
- Note: the module docstring's "nothing is actually transmitted" line is **stale**
  — it does send when SMTP is configured.

### 6.11 Theme & navigation UI — `ui/theme.py`, `ui/nav.py`

- **Single typeface:** Inter for everything (`--font-display` and `--font-body`
  both resolve to Inter), loaded from Google Fonts.
- **Colour tokens** (`TOKENS`, "Onyx" palette): near-white canvas `#FAFAF9`,
  surface `#F4F3F1`, ink `#1A1C1E`, deep-emerald accent `#0B7A55`, plus semantic
  status hues (`ok` green, `info` blue, `warn` amber, `danger` red, `archived`
  grey). Exposed as CSS variables; `STATUS_TOKEN` maps statuses to token names.
- **Sidebar nav** (`ui/nav.py`): a minimalistic **236px** light sidebar of
  full-bleed icon + label rows (Material Symbols via `:material/<name>:`). A brand
  header on top, the main sections in the middle, and the reminders bell · settings
  · account · logout pinned to the bottom. Active section = soft-emerald band.
  Collapsing the native toggle drops the width to 0 so the page reflows to full
  width. Built from native `st.button` (not option-menu).
- **KPI tiles** (`ui.components.kpi_tile`): uppercase label + optional icon chip on
  top, a large **tabular-figure** value below (`tnum`/`lnum` for aligned digits).
- **Status badges** use AA-contrast text shades; **mobile responsiveness** lives in
  a `@media (max-width: 640px)` block that stacks every `st.columns` row, clamps
  components to the viewport, and reveals per-field mobile labels.

---

## 7. Page-by-page walkthrough (`views/`)

### 7.1 Home / Dashboard — `views/dashboard.py`
- **Visitors** (no `create_reservation`) get a clean customer-facing **browse**
  page: a hero banner + a 3-up grid of available cars (photo, specs, price) ending
  in a "contact to book" prompt. No KPIs/timeline/booking/table.
- **Staff** see: page title `👤 <full_name> — <role label>`; the occupancy
  **timeline**; four KPI tiles (total / available / rented / garage from
  `fleet_counts`); the **"Available Now"** photo cards with a Rent popup
  (`open_rental_dialog`); the **booking panel** (`key_prefix="dash"`); and a
  searchable fleet table (no thumbnails). The dashboard reminder block was folded
  into the bell.

### 7.2 Reservations — `views/reservations.py`
Render order: **active rental cards (top) → quick rental registration → timeline
(bottom)** to reduce overlap with Home. Each active card shows an overdue/due-soon
badge (via `return_state`, coloured border), customer/vehicle/period, a Cancel
button, and a **Return / settlement** expander (overdue penalty + damage in euros,
notes, contract-signed) that calls `settle_and_close`. It no longer early-returns
when there are no active rentals — booking + calendar still render.

### 7.3 Fleet — `views/fleet.py`
One action-rich **card grid** (Add/Edit/Delete **tabs removed**). Everyone sees the
cards; `edit_fleet` adds an "➕ Add Vehicle" popup + Edit dialog + status
quick-buttons; `soft_delete_vehicle` adds the Delete/Archive dialog (with optional
hard-delete for super-admins). Manual statuses are **only** `Available` and
`Maintenance` (`_EDITABLE_STATUSES`); status controls are **locked** while a vehicle
has an active rental (`vehicle_has_active_rental`), with an i18n lock notice. The
edit dialog has a lazy multi-photo manager; the archived-vehicle restore list lives
in an expander.

### 7.4 Customers — `views/customers.py`
Split view: **active renters** (customers with a live rental) get a compact 3-up
**card grid**; **finished** customers drop to the full **table** with an
"Open Customer" selectbox. Each card/row's dialog holds the edit form (Employee+),
rental history, and reassign-registered-by (Admin+). The history table ends in a
**Print-Invoice** column of one flag button per available language (Albanian flag
staff-only). Because only **one `st.dialog`** may be open at a time, the flag
buttons stash `(deal_id, lang)` in `session_state["cust_invoice"]` and `st.rerun()`;
a dispatch at the top of `render_customers()` re-opens it as a standalone invoice
dialog. Reassign identifies the rental by **customer full name** + car/period.

### 7.5 Finance — `views/finance.py`
Admin+ only. Headline KPIs (revenue, cost, net, margin), then five tabs:
**Overview** (revenue split + cost-by-type), **Monthly** & **Yearly** (income vs
cost bar chart + table + totals), **By Vehicle** (per-car profitability), **Costs**
(add an operating cost — type, amount, date capped at `lic.max_date()`, note — and a
recent-costs list with delete). When there's no activity yet, only the Costs tab
shows so the first numbers can be captured.

### 7.6 Settings — `views/settings.py`
Tabs gated by role:
- **Business** (admin+ for logo; name super-admin only) — business name +
  company-logo upload (`encode_logo`, aspect-preserving fit, not cropped).
- **Users** (admin+) — create users, list with role-change / activate-deactivate
  (last-super-admin locked), and a per-user "Manage Account" expander (rename,
  email, reset password).
- **License** (super-admin) — licensed-year status + dropdown, full license-record
  CRUD with per-row Edit/Delete/Print-invoice dialogs + an Add form, the **SMTP**
  section, and a **Danger Zone** (reset Finance / reset Fleet data, each guarded by
  typing `RESET`).
- **Language** (everyone) — radio of role-filtered languages, saved to `users.lang`.
- **Profile** (everyone) — own full name, email, and password.
- **Activity** (admin+) — a "Return Activity" undo section (restore archived
  vehicles / reactivate cancelled rentals) plus a masked, filterable audit log of
  the last 500 events.

---

## 8. Run / build / reset / seed

```bash
# Install pinned deps
python -m pip install -r requirements.txt

# Run (ALWAYS via "python -m streamlit", never bare "streamlit")
python -m streamlit run app.py
#   Windows: or double-click start_balkan_fleet.bat

# Re-seed vehicles by hand (idempotent INSERT OR IGNORE)
python -m data.seed.import_csv

# Syntax-check everything
python -m py_compile app.py config/*.py core/*.py data/repositories/*.py \
  data/seed/*.py views/*.py services/*.py ui/*.py
```

- **No test suite exists.** Validate data/service changes with a short bare script:
  `core/`, `data/`, `services/` import no Streamlit and run under plain `python`.
  Anything importing `ui/`/`views/` needs `streamlit run` (a bare import only warns
  "missing ScriptRunContext" and `t()` falls back to `DEFAULT_LANG="tr"`).
- **Default login after a fresh DB:** `admin` / `admin` (super-admin) — change it
  immediately.
- **Full reset:** stop the app, delete `fleet.db` + `fleet.db-wal` + `fleet.db-shm`.
  (Or, without nuking the file, use the super-admin Danger Zone resets.)
- **First run** auto-creates schema, seeds from `fleet_master.csv` (only when the
  `vehicles` table is empty), and creates the default admin.

---

## 9. Conventions

- **i18n:** every user-facing string goes through `t("key")` and must exist in all
  six languages (identical key-sets, currently **354 × 6**).
- **Permissions:** gate every privileged action with `can(user, "<perm>")`.
- **Audit:** call `audit_service.record(...)` after every successful mutation.
- **Money:** integer cents end-to-end; euros only at display via `format_eur`.
- **Dates:** ISO-8601 text (`YYYY-MM-DDTHH:MM:SS`); cost periods `YYYY-MM-DD`.
- **Status vocabularies are duplicated** in `core/schema.sql` CHECK constraints
  **and** `config/settings.py` (`VEHICLE_STATUSES`/`RENTAL_STATUSES`) — change both
  together. The `vehicle_costs` type list is duplicated in the schema CHECK and
  `vehicle_costs.COST_TYPES`; the charge type list likewise.
- **DB engine:** one shared engine from `core.db.get_engine()`; `.connect()` for
  reads, `.begin()` for write transactions. SQLite pragmas set on connect: FK on,
  WAL, `synchronous=NORMAL`, `busy_timeout=5000`, in-memory temp store, page cache,
  128 MB mmap.
- **f-strings:** runtime is 3.12 but the project targets **3.11+** — avoid nesting
  an f-string inside another with the *same* quote char (PEP 701 only relaxed that
  in 3.12).
- **Popups:** `st.dialog(title, width=...)(body_fn)(args)` so titles can be dynamic
  (i18n) and openable from any button's if-block. Only one dialog may be open at a
  time.

---

## 10. Known gotchas & non-obvious behavior

- **Section modules live in `views/`, NOT `pages/`.** Streamlit treats a folder
  literally named `pages/` as a native multipage app and would render those
  `render_<name>(user)`-only files blank. `[client] showSidebarNavigation = false`
  is set as defense-in-depth.
- **Native `st.button` nav, not `streamlit-option-menu`** (whose iframe collapses
  to 0px on Streamlit 1.58). Don't reintroduce option-menu.
- **`CookieManager` must be created exactly once per run** (in `app.py`) — twice
  raises duplicate-component errors.
- **Cookie priming reruns:** `app.py` does up to 4 bounded `st.rerun()`s
  (`_cookie_tries < 4`) on a fresh load so the remember-me cookie (which arrives on
  a later browser round-trip) can restore the session before the login form shows.
  Login also `time.sleep`s briefly after `cookie_mgr.set` so the write lands.
- **`STATUS_TOKEN["Overdue"]` is derived, not stored** — a rental is overdue when
  `end_dt < now`; used only for colouring.
- **Notification bell** renders in the sidebar footer for staff
  (`can(user,'create_reservation')`); its badge counts overdue + due-soon via
  `return_state`. The dialog lists copyable phone + WhatsApp/call links.
- **Seeding only runs on an empty `vehicles` table**; the CSV import is
  `INSERT OR IGNORE` keyed on `vehicle_id`, so it never overwrites in-app edits.
  Rate header `Base Daily Rate (€)` (legacy `($)` also accepted).
- **Booking panel is reused** on Dashboard + Reservations with different
  `key_prefix`. The rental popup puts customer personal-info first, dates/selection
  below as a final confirmation; it re-checks `is_vehicle_free` before
  `create_rental` and then renders a print-ready invoice until dismissed.
- **Photos legacy column** `vehicles.photo` is now **write-only** (set by
  add/update but read by nothing — only feeds the one-time `_migrate_photos`).
  Thumbnails are cached keyed on `photos_version()`; invalidate after every change.
  `hard_delete` orphans photo rows; `clear_photos()` is unused.
- **Only one `st.dialog` at a time** — the customers invoice flow stashes a one-shot
  request and reruns instead of nesting dialogs.
- **First paint needs the network** — Google Fonts, vis-timeline, and the
  cookie/menu components load from CDNs.
- **Email module docstring is stale** — it does transmit when SMTP is configured.
- **Invoice deposit deduction:** the invoice shows Subtotal, a `− Deposit` row, and
  a Grand Total = subtotal − deposit (the remaining balance due). Both the HTML
  (`ui/invoice.py`) and PDF (`ui/pdf.py`) render this, with the company logo in the
  header when set.
- **Not in a git repo** — there is no version control here; edits are deliberate.
```
