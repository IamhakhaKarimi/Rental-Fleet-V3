# CLAUDE.md

Guidance for Claude Code when working in this repo. Full developer docs:
[`DOCUMENTATION.md`](DOCUMENTATION.md) · per-page walkthrough:
[`WALKTHROUGH.md`](WALKTHROUGH.md) · end-user setup: [`README_SETUP.md`](README_SETUP.md).

## What this is
**Balkan Car Rentals — Fleet Console v3.0**: a single-page **Streamlit** app for a
car-rental business (fleet, rentals, customers, occupancy timeline, finance).
Six UI languages (TR/EN/DE/IT/ES/SQ), role-gated, self-bootstrapping (builds +
seeds its own SQLite DB on first run). ~2,400 LOC Python.

## Run / build / test
```bash
# Install (pinned) deps
python -m pip install -r requirements.txt

# Run the app (always via "python -m streamlit", never bare "streamlit")
python -m streamlit run app.py            # Windows: or double-click start_balkan_fleet.bat

# Re-seed vehicles by hand (idempotent, INSERT OR IGNORE)
python -m data.seed.import_csv

# Syntax-check everything
python -m py_compile app.py config/*.py core/*.py data/repositories/*.py \
  data/seed/*.py views/*.py services/*.py ui/*.py
```
- **No test suite exists.** Validate data/service-layer changes with a short bare
  script: `core/`, `data/`, `services/` modules do **not** import Streamlit, so
  they run under plain `python`. Anything importing `ui/` or `views/` pulls in
  Streamlit and must run under `streamlit run` (a bare import only warns "missing
  ScriptRunContext" and `t()` falls back to `DEFAULT_LANG="tr"`).
- Default login after a fresh DB: **`admin` / `admin`** (super-admin).
- Full reset: stop the app, delete `fleet.db` + `fleet.db-wal` + `fleet.db-shm`.

## Architecture (strict one-way layering)
```
app.py → views/ , ui/ → services/ → data/repositories/ → core/db.py → fleet.db
                     ↘ config/ (settings · roles · i18n) used by all layers
```
Rules that matter when editing:
- **All SQL lives in `data/repositories/`.** Repositories return **plain dicts**,
  never ORM objects. Don't write SQL in `services/`, `views/`, or `ui/`.
- **`services/`** holds business logic (auth/hashing, availability math, revenue
  & P&L rollups, audit). No Streamlit widgets here.
- **`views/render_<name>(user)`** is the unit a router entry in `app.py` calls.
- The `user` object everywhere is `{"username","full_name","role"}`.

## Conventions (follow these)
- **Money is INTEGER cents end-to-end.** Convert to a string only at display via
  `ui.components.format_eur`. Form inputs are euros → multiply by 100 before the
  repository. Never store floats.
- **Dates/times are ISO-8601 text** (`YYYY-MM-DDTHH:MM:SS`); cost periods are
  `YYYY-MM-DD`.
- **i18n: every user-facing string goes through `t("key")`** and must exist in
  **all six** languages (identical key-sets, currently **334 keys × 6**). TR and EN
  stay **inline** in `config/i18n.py` under `TRANSLATIONS`; DE/IT/ES/SQ live in
  auto-generated `config/lang_<code>.py` modules, each exposing two plain dicts
  `UI` (every UI string) + `TERMS` (rental-terms title + 12 rules). `config/i18n.py`
  imports each `UI` into `TRANSLATIONS`; `config/terms.py` imports each `TERMS` into
  `RENTAL_TERMS`. The canonical registry `LANGUAGES = {code: "flag + endonym"}` and
  `STAFF_ONLY_LANGS = {"sq"}` live in `config/settings.py` (Streamlit-free, so
  services validate a lang without importing Streamlit). To add a language: extend
  `LANGUAGES` + add a `config/lang_<code>.py` (UI+TERMS). Status/role labels are
  themselves translation keys. `DEFAULT_LANG="tr"`.
- **Permissions: gate every privileged action with `can(user, "<perm>")`** from
  `config/roles.py`. Permissions map to a minimum role *level*
  (`visitor 0 < employer 1 < admin 2 < super_admin 3`). The role id is
  **`employer`** but its label is **Employee / Çalışan**.
- **Status vocabularies are duplicated** in `core/schema.sql` CHECK constraints
  **and** `config/settings.py` — change both together.
- **Audit every mutation:** after a successful create/update/delete, call
  `audit_service.record(user, action, entity, entity_id, detail)`.
- **f-strings:** the runtime here is 3.12 but the project targets **Python 3.11+** —
  avoid nesting an f-string inside another f-string with the *same* quote char
  (PEP 701 only relaxed that in 3.12).
- **DB engine:** one shared engine from `core.db.get_engine()`; `.connect()` for
  reads, `.begin()` for write transactions. SQLite pragmas (FK on, WAL) are set on
  connect.

## Data model (11 physical tables — 8 "core" + `sessions` + `vehicle_photos` + `licenses`)
`vehicles` (soft-delete via `status='DELETED'`; legacy base64 `photo` col, now
write-only — see photos gotcha), `customers`, `rentals` (`Active`/`Closed`;
snapshots the booking staff via `created_by`/`_name`/`_role`; per-rental
`invoice_lang`), `charges` (income ledger, 5 types: rental/overdue_penalty/damage/
deposit/refund), `vehicle_costs` (expense ledger, 7 types: insurance/maintenance/
depreciation/fuel/financing/registration/other), `users` (+ `lang`, `email`),
`sessions` (stores only the SHA-256 of the remember-me cookie token), `audit_log`,
`app_settings` (key/value, e.g. `business_name`, `business_logo` base64 PNG,
`licensed_until_year`, SMTP keys), `vehicle_photos` (multiple base64 JPEGs per
vehicle; see photos gotcha), `licenses` (license-record ledger:
`license_id`, `licensee`, `year`, `years`, `amount` [cents], `purchase_date`,
`notes`, `created_at` — repo `data/repositories/licenses.py`). IDs:
vehicles `C001…`, rentals `RENT-YYYYMM-NNN`, customers/photos/licenses autoincrement.
`licenses` ships in `core/schema.sql` (re-run idempotently), so existing DBs get it
on next start.
`core/db.init_db` runs four migrations in order on every start —
`_migrate_users` (rebuild if `full_name` missing), `_migrate_rentals`
(add snapshot cols), `_migrate_add_columns` (additive: `vehicles.photo`,
`users.lang`, `users.email`, `rentals.invoice_lang`), `_migrate_photos`
(move legacy `vehicles.photo` into `vehicle_photos`) — so existing DBs get the
new columns via `ALTER` and fresh DBs get them straight from `schema.sql`.

## Where things live
| Want to change… | Edit |
|---|---|
| Brand / currency / booking defaults / status lists | `config/settings.py` |
| Roles & permissions | `config/roles.py` |
| Any visible text (TR/EN) | `config/i18n.py` |
| A non-TR/EN language (DE/IT/ES/SQ) | `config/lang_<code>.py` (UI+TERMS) |
| Add a UI language / staff-only gating | `config/settings.py` (`LANGUAGES`, `STAFF_ONLY_LANGS`) |
| Schema (DDL) | `core/schema.sql` (+ a migration in `core/db.py` for existing DBs) |
| A SQL query | the matching `data/repositories/*.py` |
| Company logo (store/encode) | `data/repositories/app_settings.py` (`get/set/clear_logo`) + `ui/photos.py` (`encode_logo`) |
| License records (CRUD) | `data/repositories/licenses.py` + `views/settings._license_tab` |
| Availability / return-time math | `services/scheduling_service.py` |
| Revenue, costs, P&L | `services/finance_service.py` + `data/repositories/vehicle_costs.py` |
| Auth / sessions / accounts | `services/auth_service.py` + `data/repositories/users.py` |
| A page's layout | `views/<name>.py` |
| Shared widgets / theme / nav / invoice / timeline | `ui/` |

## Gotchas / non-obvious behavior
- **Section modules live in `views/`, NOT `pages/`.** Streamlit treats a folder
  literally named `pages/` next to the entrypoint as a *native multipage app* and
  builds a sidebar that runs each file standalone — they only define
  `render_<name>(user)`, so they'd render blank. Keep them in `views/`. The config
  also sets `[client] showSidebarNavigation = false` as defense-in-depth.
- **The top nav is native `st.button`s** (`ui/nav.py`), not `streamlit-option-menu`
  (whose iframe collapses to 0px height on Streamlit 1.58, hiding the whole nav).
  Buttons show **emoji + label** and stack vertically on mobile (responsive CSS in
  `ui/theme.py`), so section names stay legible on a phone. Don't reintroduce
  option-menu.
- **Mobile responsiveness** lives in a `@media (max-width: 640px)` block in
  `ui/theme.py`: it stacks every `st.columns` row and clamps components to the
  viewport so the page fits a phone without pinch-zoom.
- **Language is per-user**, chosen in Settings → Language and stored on
  `users.lang`; `auth_view._apply_user_lang` adopts it on login/restore. There is
  no language toggle in the top bar. The Language tab reads the `LANGUAGES`
  registry and **filters `STAFF_ONLY_LANGS` by role level**: Albanian (`sq`) is
  offered only to parent/staff roles (level ≥ 1 — employer/admin/super_admin);
  visitors see the other five. `auth_service.set_user_lang` validates against
  `LANGUAGES`. Note the customer-facing **invoice** offers **all six** languages
  regardless of UI role gating (a customer document is independent) —
  `build_invoice_html` validates `lang` against `LANGUAGES`.
- **Vehicle photos**: multiple per vehicle in the `vehicle_photos` table (base64
  JPEG, all cropped to one uniform stored size `PHOTO_SIZE=(640,480)` (4:3) via
  Pillow `ImageOps.fit` in `ui/photos.py` so cards line up; Pillow-missing/
  unreadable falls back to raw bytes; no photo → 🚘 avatar). Thumbnails render at
  fixed display heights (dashboard 140, Fleet-edit 120, gallery 90) via
  `object-fit:cover`. Listings (`list_vehicles`) carry **no** photo data —
  thumbnails load the *primary* photo lazily and are cached with `@st.cache_data`
  keyed on `photos_version()` (= `MAX(photo_id)`); call `photos.invalidate_cache()`
  after every add/delete (it already covers cache key reuse). The full gallery
  loads only when the Fleet-edit photo toggle is expanded. **Only** Dashboard
  "Available now" cards and the Fleet-edit tab render photos — the Fleet browse
  table and Dashboard fleet table show **no** thumbnails. Legacy single photos on
  `vehicles.photo` are migrated into the table by `_migrate_photos`; that column is
  now write-only (`add_vehicle`/`update_vehicle` still set it, but nothing reads it
  for display — it only feeds the one-time migration). All 6 photo i18n keys exist
  in both `tr`/`en`. Caveats: `hard_delete` of a vehicle leaves its
  `vehicle_photos` rows behind, and `clear_photos()` in the repo is unused dead
  code (no caller in `views/`/`ui/`).
- **`app.py` does a few bounded priming `st.rerun()`s** (`_cookie_tries < 4`) on a
  fresh load so the remember-me cookie — which only arrives on a later browser
  round-trip — can restore the session before the login form shows. Without this a
  **browser refresh logs the user out**. Login also `time.sleep`s briefly after
  `cookie_mgr.set(...)` so the write reaches the browser before the rerun.
- **`CookieManager` must be created exactly once per run** (in `app.py`) — creating
  it twice raises duplicate-component errors.
- **`STATUS_TOKEN["Overdue"]` is a derived state, not a stored status** — a rental
  is overdue when `end_dt < now`; it's used only for colouring.
- **Notification bell** (`ui/notifications.render_bell`) renders in the top nav for
  staff (`can(user,'create_reservation')`); its badge counts overdue + due-soon via
  `scheduling_service.return_state` (`DUE_SOON_HOURS=24`), and the dialog lists
  copyable phone + WhatsApp/call links. `return_state` has 3 consumers — the bell,
  timeline colouring (`ui/timeline.py`), and the reservations list
  (`views/reservations.py`) — the dashboard reminder block was folded into this bell.
- **Seeding only runs on an empty `vehicles` table**; CSV import is
  `INSERT OR IGNORE` keyed on `vehicle_id`, so it never overwrites in-app edits.
  The seed CSV's rate header is `Base Daily Rate (€)`; the importer also accepts
  the legacy `($)` header.
- **Booking panel is reused** on dashboard + reservations with different
  `key_prefix` to avoid widget-key clashes; the rental popup (`open_rental_dialog`,
  `ui/booking.py` → `_rental_form_body`) puts the customer personal-info fields
  (name / phone / ID) **first**, with the date & selection fields (start date, time,
  days, return, rate, deposit, invoice language) **below** them as a final
  confirmation step (the date was already chosen when picking the car). Its
  per-rental invoice-language select offers **all six** languages, and it re-checks
  `is_vehicle_free` on save before `create_rental(..., invoice_lang=…)`. After a
  rental is created it stashes the `deal_id` in
  `session_state[f"{key_prefix}_last_deal"]` and renders a print-ready invoice
  (`ui/invoice.py`) until dismissed. `render_invoice` is also reached from
  customer history (`views/customers.py`). `build_invoice_html(deal, charges,
  business_name, lang='tr')` takes a 4th `lang` param (validated against
  `LANGUAGES`, all six offered); the printable sheet is sub-A4 (max-width 640px)
  with `@page size:A4` print rules and rental terms from `config/terms.py`
  (`RENTAL_TERMS[lang]` = title + 12 rules per language). The invoice **subtracts the
  deposit**: it shows Subtotal, a `− Deposit` deduction row, and a Grand Total =
  subtotal − deposit (the remaining balance due).
- **Customers page is a card view** (`views/customers.py`): a searchable 3-up grid
  of compact cards (name, phone, rental count, last-rental date, registered-by); a
  page-level "Open Full Table" button (`open_full_table`) pops the full table in a
  dialog, and each card's "Open" button (`card_open`) pops a per-customer dialog
  (edit form Employee+, rental history, reassign Admin+). Rental history has a
  "Print Invoice" column of one small flag button per available language (Albanian
  flag staff-only). **Gotcha — only one `st.dialog` may be open at a time (no
  nesting):** the flag buttons don't nest a dialog; they stash a one-shot
  `(deal_id, lang)` in `session_state["cust_invoice"]` and `st.rerun()` (closing the
  customer dialog), and a dispatch at the top of `render_customers()` re-opens it as
  a standalone invoice dialog. Reassign "Registered By" identifies the rental by the
  **customer full name** (selectbox labelled with the name; each option leads with
  the full name + car/period), not the raw deal id.
- **First paint needs the network** (Google Fonts, vis-timeline, cookie/menu
  components load from CDNs).
- **Popups use `st.dialog`** opened via `st.dialog(title, width=...)(body_fn)(args)`
  so the title is dynamic (i18n) and the dialog is openable from any button's
  if-block (rental popup in `ui/booking.py`, reminders in `ui/notifications.py`,
  license invoice in `views/settings.py`). Pressing Esc/✕ closes it; Save calls
  `st.rerun()`.
- **Annual licensing** (`services/licensing_service.py`, **fully wired**):
  `licensed_year()` reads `app_settings.licensed_until_year`, floored to the
  current year (it can only *extend* forward, never restrict below now).
  `max_date()` = 31 Dec of that year. The three **booking/cost** date pickers cap
  at `lic.max_date()` (`ui/booking.py:57`, `ui/booking.py:136`, `views/finance.py:161`)
  so staff can't record into an unlicensed year. The license-invoice purchase-date
  picker is intentionally **not** capped — it's invoice metadata, not a booking
  date. The super-admin License tab (`views/settings._license_tab`, gated by
  `can(user,'edit_business_settings')` = level 3) is now a **full CRUD** over the
  `licenses` table: it lists records with per-row Edit / Delete / Print-invoice
  (each an `st.dialog`) plus an Add form. Adding/editing a record for a later year
  calls `licensing_service.extend_licensed_year()` to push the date-picker cap
  forward; the "unlock next year" button (`set_licensed_year()`) and the SMTP
  section remain in the tab. Print uses `ui/license_invoice.py`.
- **Email/password-recovery** (`services/email_service.py`, **fully wired** across
  all four UI touchpoints — login forgot-password (`ui/auth_view.py`), profile email
  + child reset + child email (`views/settings.py`), and the SMTP form
  (`views/settings._smtp_section`, reached **inside** the super-admin License tab,
  not a standalone tab)). SMTP config lives in `app_settings`; `is_configured()`
  needs both `smtp_host` and `smtp_from`. `send_mail` uses STARTTLS and never raises.
  When SMTP is unset, recovery mail isn't sent — the new 10-char password is shown
  on-screen (`st.warning recover_fallback`) and audited. `auth.self_recover` is
  restricted to admin/super_admin (employees/visitors get `recover_admin_only` and
  must ask an admin) and delivers to the **account's own** email;
  `auth.admin_recover_child` delivers the new password to the **acting admin's**
  email. `users.email` holds per-user addresses. `FALLBACK_EMAIL` in code is
  `hakamaneshkarimi@gmail.com` (distinct from the owner login `admin@ghoncha.com`).
  Note: the `email_service` module docstring still says "nothing is actually
  transmitted" — that's stale; it does send when SMTP is configured.
- **Activity-log masking**: `views/settings._activity_tab` (gated by
  `can(user,'manage_users')` = admin level 2+; employers/visitors never see it)
  renders `audit_service.recent(500)`. It masks actors whose role is **strictly**
  above the viewer's `ROLE_LEVEL` as "system admin" (equal-rank actors show by
  username), and offers a **"Filter by" toggle** (`st.radio`, key `filter_by`) that
  switches between filtering by **Action** (multi-select action types) and by
  **User** (masked names respected).
- **Home page** (`views/dashboard.py`, nav key `nav_dashboard` now reads "Home" /
  "Ana Sayfa" / "Startseite" / "Inicio" / "Kreu"): no longer titled "Overview" —
  the page title now shows the logged-in user as `👤 <full_name> — <role label>`
  (role label via `ROLE_LABEL_KEY`).
- **Profile tab** (`views/settings`, key `tab_profile` = "Profile", was the
  "Password" tab): visible to **every** role. Lets a user edit their **own** Full
  Name (`auth.set_user_full_name` → `users.update_full_name`), Email, and Password.
- **Company logo** (`views/settings` Business tab, now visible to **admin+**, was
  super-admin only): editing the business **name** stays super-admin, but the
  **logo** upload is admin+. Stored as a base64 PNG in `app_settings`
  (`app_settings.get/set/clear_logo`), encoded by `ui.photos.encode_logo`
  (**aspect-preserving, fit within 280×100 — NOT cropped** like car photos). The
  logo renders on **both** invoices: `ui/invoice.build_invoice_html` takes a `logo`
  param (`render_invoice` passes `app_cfg.get_logo()`) and `ui/license_invoice.py`
  fetches `app_cfg.get_logo()` — injected into the `.brand` header only when set.
- **Fleet is one action table** (`views/fleet.py`, Add/Edit/Delete **tabs
  removed**): an "➕ Add Vehicle" popup; an **Actions** column whose Edit /
  Delete-Archive buttons open `st.dialog` popups (gated by `edit_fleet` /
  `soft_delete_vehicle` / `hard_delete_vehicle`); and a **dynamic Status** column
  whose To-Garage / To-Maintenance / Make-Available buttons call `vrepo.set_status`
  **immediately** (not dialogs). Manual status options are **only** `Available` and
  `Maintenance` (`_EDITABLE_STATUSES = ["Available","Maintenance"]` — `Rented` was
  removed); both the edit-dialog selectbox and the status-column quick buttons are
  **disabled/locked when the vehicle has an active rental**
  (`rentals.vehicle_has_active_rental`), and the edit dialog shows a lock notice
  (i18n key `status_locked_rented`). Non-privileged roles see it read-only. The
  archived-vehicle restore list (expander/dialog) is kept.
- **Reservations render order** (`views/reservations.py`) is now: active rental
  cards (TOP) → quick rental registration → timeline/calendar (BOTTOM), to reduce
  overlap with Home. It **no longer early-returns** when there are no active
  rentals — booking + calendar still render.
- **Last-super-admin lockout guard**: `auth.is_last_active_super_admin(username)`.
  The Users tab disables the role-change and deactivate controls for the final
  active super-admin so it can't be demoted or deactivated (super-admins can
  otherwise manage each other via `assignable_roles`).
- **Not in a git repo** — there's no version control here; be deliberate about
  edits.
