# V4_PLAN.md — Balkan Car Rentals, Fleet Console **v4.0**

> **Status:** Delivery plan (no code changed). Authoritative current-state spec is
> [`CLAUDE.md`](CLAUDE.md); this plan guarantees feature parity with **v3.0**
> (Streamlit + SQLite, ~2,400 LOC) and adds nothing the business hasn't already
> shipped.
>
> **Decided stack (do not re-litigate):** FastAPI backend that **ports** the
> existing clean `services/` + `data/repositories/` layers · Next.js (React +
> TypeScript) + Tailwind frontend (single minimalistic sans-serif font, fully
> responsive/reflow-friendly) · PostgreSQL · proper auth/session/RBAC
> (argon2id, httpOnly cookies + CSRF). Author priorities: **reliability,
> security, responsiveness, speed**, minimalistic single-font UI.

---

## 1. Goals & non-goals

### Goals
| # | Goal | What it concretely means |
|---|------|--------------------------|
| G1 | **Reliability** | Real DB transactions, Postgres ACID, integration tests on every endpoint, no silent-failure paths. Eliminate the v3 cookie-priming reruns and "browser refresh logs you out" class of bugs. |
| G2 | **Security** | argon2id hashing (replaces bcrypt), httpOnly+Secure+SameSite session cookies, CSRF tokens for state-changing requests, server-side RBAC on every route (never trust the client), rate limiting on auth, secrets out of the DB and into env/secret store. |
| G3 | **Responsiveness** | A single layout that reflows from phone to desktop with no pinch-zoom and no horizontal scroll; collapsible sidebar; tables that become cards on narrow viewports. |
| G4 | **Performance** | Sub-200 ms API reads on the indexed queries that already exist; lazy photo loading; HTTP caching/ETags; Next.js server components + streaming; connection pooling. |
| G5 | **Maintainability & types** | End-to-end type safety: Pydantic v2 on the server, generated TypeScript client on the frontend, mypy + tsc in CI. |
| G6 | **Feature parity** | Every v3 capability in the parity matrix (§3) reproduced. |

### Non-goals (explicitly out of scope for v4)
- **Rewriting the domain logic from scratch.** The `services/` (availability math,
  return-state classification, revenue/P&L rollups, licensing cap, auth rules) and
  the SQL in `data/repositories/` are correct and battle-tested — they are
  **ported**, not reinvented. (See §5.2 for the surgical changes required.)
- No new business features (no new payment gateway, no telematics, no multi-tenant).
- No change to the **domain contracts**: money stays **INTEGER cents**, the
  ID formats stay (`C001…`, `RENT-YYYYMM-NNN`), the four roles and their levels
  stay, the six languages stay, the 12 rental-terms rules stay.
- No native mobile app (responsive web only).
- Not porting v3 **bugs**: e.g. `create_rental` currently clamps `invoice_lang`
  to `("tr","en")` even though the UI offers six — v4 fixes this to honor all six
  (see §3 note and §11 R7).

---

## 2. Target architecture

```
                          ┌──────────────────────────────────────────┐
   Browser (phone→desktop)│  Next.js 14 App Router (React 18 + TS)     │
        │  HTTPS           │  • Server Components + Server Actions      │
        ▼                  │  • Tailwind + shadcn/ui, ONE sans font     │
 ┌───────────────┐         │  • next-intl (tr/en/de/it/es/sq)           │
 │  Next.js node │◀────────│  • httpOnly session cookie forwarded       │
 │  (SSR/edge)   │         └──────────────────────────────────────────┘
 └───────┬───────┘                         │  fetch /api/* (JSON), cookie + CSRF header
         │  same-origin /api proxy (rewrites)
         ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │  FastAPI (Python 3.12, uvicorn/gunicorn)                               │
 │  ┌──────────────┐  ┌────────────────────┐  ┌───────────────────────┐  │
 │  │ routers/     │→ │ services/  (PORTED) │→ │ repositories/ (PORTED)│  │
 │  │ (HTTP/auth/  │  │ availability, P&L,  │  │ all SQL, return dicts │  │
 │  │  RBAC dep)   │  │ licensing, audit,   │  │ → SQLAlchemy Core 2.0 │  │
 │  │ Pydantic v2  │  │ email — Streamlit-  │  │ over Postgres         │  │
 │  └──────────────┘  │ free already        │  └───────────┬───────────┘  │
 │   OpenAPI 3.1      └────────────────────┘                │              │
 └───────────────────────────────────────────────────────────┼──────────┘
                                                              ▼
                                              ┌──────────────────────────┐
                                              │  PostgreSQL 16            │
                                              │  + Alembic migrations     │
                                              │  + object storage (S3/    │
                                              │    MinIO) for photos/logo │
                                              └──────────────────────────┘
```

**Where the ported domain logic lives.** The v3 layering is already strictly
one-way and Streamlit-free below the `views/`/`ui/` line:

```
v3:  app.py → views/ , ui/ → services/ → data/repositories/ → core/db.py → SQLite
v4:  Next.js → FastAPI routers/ → services/ → repositories/ → db (SQLAlchemy) → Postgres
                    └ replaces views/+ui/ (presentation only)
```

The presentation layer (`views/`, `ui/`, Streamlit, cookie-manager, vis-timeline)
is **discarded and rebuilt** in Next.js. Everything below `services/` is **lifted
as-is** with two mechanical edits: (a) swap the engine factory to Postgres, (b)
replace SQLite-only SQL idioms (`datetime('now')`, `strftime`, `MAX/MIN(a,b)` as
scalar functions, `INSERT OR IGNORE`) with Postgres equivalents (§4, §5.2).

**Auth flow.**
1. `POST /api/auth/login {username,password,remember}` → FastAPI verifies argon2id
   hash → mints an opaque 256-bit session token, stores **only its SHA-256** in
   `sessions` (keeps v3's design), sets two cookies: `sid` (httpOnly, Secure,
   SameSite=Lax, 30 d if remember else session) and `csrftoken` (readable by JS).
2. Every request carries `sid` automatically; state-changing requests must echo
   `csrftoken` in an `X-CSRF-Token` header (double-submit). A FastAPI dependency
   `current_user` validates the session and loads `{username,full_name,role,lang,email}`.
3. RBAC dependency `require(perm)` checks `role_level >= PERMISSION_MIN_LEVEL[perm]`
   — the **exact** v3 table, ported verbatim (§7).
4. `POST /api/auth/logout` deletes the session row and clears cookies.

No client-side trust: the frontend hides controls the user can't use, but the
**server independently enforces** every permission.

---

## 3. Feature-parity matrix (every v3 feature → v4 owner)

Legend for owner: **API** = FastAPI router + ported service/repo · **FE** = Next.js
page/component · **DB** = schema/migration.

| v3 feature | v4 component(s) | Notes / parity guarantees |
|---|---|---|
| **Fleet list / browse** | `GET /api/vehicles` · FE `/fleet` | List excludes photo blobs (light), as v3. Filter out `DELETED` by default. |
| **Fleet add** | `POST /api/vehicles` (`edit_fleet`) · FE add dialog | Generates next `C00n` id server-side; audit. |
| **Fleet edit** | `PATCH /api/vehicles/{id}` (`edit_fleet`) | Status select limited to `Available`/`Maintenance`; **locked when an active rental exists** (`vehicle_has_active_rental`), with `status_locked_rented` notice. |
| **Status quick-actions** (To-Garage / To-Maintenance / Make-Available) | `POST /api/vehicles/{id}/status` | Immediate, no dialog; same lock rule. |
| **Soft delete (archive)** | `DELETE /api/vehicles/{id}` (`soft_delete_vehicle`) | Sets `status='DELETED'`. |
| **Restore archived** | `POST /api/vehicles/{id}/restore` | Keeps v3 restore list. |
| **Hard delete** | `DELETE /api/vehicles/{id}?hard=true` (`hard_delete_vehicle`, lvl 3) | v4 **fixes** the v3 caveat: also delete orphaned `vehicle_photos`. |
| **Vehicle photos (multi)** | `GET/POST/DELETE /api/vehicles/{id}/photos` · FE gallery | Stored in object storage (§4); 4:3 `fit` to 640×480 server-side (Pillow). Primary thumbnail lazy-loaded; cache keyed on photo version (ETag). |
| **Rentals: create (booking panel)** | `POST /api/rentals` (`create_reservation`) | Re-checks `is_vehicle_free` in the same transaction; customer fields first, then dates/rate/deposit/invoice-lang; **invoice_lang accepts all six** (v3 bug fixed). |
| **Rentals: active list** | `GET /api/rentals?status=Active` | Joined with vehicle + customer, ordered by `end_dt`. |
| **Rentals: settle & close (return)** | `POST /api/rentals/{id}/close` | Records overdue/damage charges, accrues `maintenance_charge`, frees car — one transaction (port `settle_and_close`). |
| **Rentals: cancel / reactivate** | `POST /api/rentals/{id}/cancel` · `/reactivate` (`cancel_reservation`) | Reactivate refuses if car held by another active rental. |
| **Reassign "registered by"** | `PATCH /api/rentals/{id}/creator` (`assign…`, admin+) | Identified by customer full name in the FE selectbox. |
| **Invoice languages (per rental)** | field on rental + invoice endpoint | All six offered; validated against `LANGUAGES`. |
| **Customers: card grid + search** | `GET /api/customers` · FE `/customers` | 3-up responsive cards; reflow to 1-up on phone. |
| **Customers: full table** | `GET /api/customers?view=table` | Dialog/route. |
| **Customers: per-customer dialog** | `GET /api/customers/{id}` (+ rentals) | Edit (Employee+), rental history, reassign (Admin+). |
| **Customer edit** | `PATCH /api/customers/{id}` | Audit. |
| **Occupancy timeline / calendar** | `GET /api/timeline?from&to` · FE timeline | Replace vis-timeline CDN with a bundled React Gantt (e.g. `frappe-gantt-react` or a custom flex/SVG timeline) — no first-paint CDN dependency. Colour via ported `return_state`. |
| **Notification bell (overdue/due-soon)** | `GET /api/notifications` · FE bell | Badge = overdue + due-soon (`DUE_SOON_HOURS=24`); dialog lists phone + `tel:`/WhatsApp links. Staff only (`create_reservation`). |
| **Finance: revenue summary / by vehicle / month / year** | `GET /api/finance/revenue*` (`view_finance`, admin+) | Port `finance_service` verbatim; charge revenue types = rental/overdue_penalty/damage. |
| **Charges ledger** | included in rental close / create | 5 types preserved. |
| **Vehicle costs (expense ledger)** | `GET/POST /api/costs` · FE finance | 7 cost types; date picker capped at licensing `max_date()`. |
| **P&L (summary / by month / year / by vehicle)** | `GET /api/finance/pnl*` | Port `_merge`, `pnl_*`, `profit_by_vehicle`. |
| **Users: list / create** | `GET/POST /api/users` (`manage_users`) | `assignable_roles` enforced. |
| **Users: role change / activate / deactivate** | `PATCH /api/users/{u}` | **Last-active-super-admin guard** (`is_last_active_super_admin`) ported. |
| **Username change / admin reset** | dedicated endpoints | `_can_manage` scope rule ported. |
| **Sessions / remember-me** | cookie + `sessions` table | 30 d vs 12 h; only SHA-256 of token stored. argon2 only affects *password* hashing, token model unchanged. |
| **Audit log** | `audit_service.record` after every mutation · `GET /api/audit` | **Activity masking**: actors strictly above viewer's level shown as "system admin"; filter-by Action or User. Admin+ only. |
| **app_settings (business name)** | `GET/PUT /api/settings/business` | Name edit super-admin only. |
| **Business logo** | object storage + `GET/PUT /api/settings/logo` (admin+) | Aspect-preserving fit 280×100 (not cropped). Rendered on both invoices. |
| **Licenses CRUD** | `GET/POST/PATCH/DELETE /api/licenses` (lvl 3) | Full CRUD ledger; add/edit later year calls `extend_licensed_year`. |
| **Licensing date cap** | `GET /api/licensing` → `max_date()` | All booking/cost date pickers capped at 31 Dec of licensed year; license purchase-date **not** capped. |
| **"Unlock next year"** | `POST /api/licensing/unlock` | `set_licensed_year`. |
| **Email / SMTP password recovery** | `POST /api/auth/recover`, `/users/{u}/recover` + `PUT /api/settings/smtp` | Port `email_service` (STARTTLS, never raises). `self_recover` admin+ only → own email; `admin_recover_child` → acting admin's email; SMTP-unset → return generated password in response **only to authorised admin** + audit. Move SMTP creds + `FALLBACK_EMAIL` to env (§7). |
| **6-language i18n (UI)** | next-intl `messages/<code>.json` × 6 | Identical key-sets (currently 334). `sq` staff-only (level ≥ 1); validated server-side too. |
| **Per-user language** | `users.lang` + `PUT /api/users/{u}/lang` | Adopted on login; validated against `LANGUAGES`. |
| **Printable rental invoice** | `GET /api/rentals/{id}/invoice?lang=` → HTML, optional `?format=pdf` | Server-rendered HTML (sub-A4, max-width 640px, `@page A4`), **subtracts deposit** (Subtotal − Deposit = Grand Total), logo in `.brand`, 12 terms from `RENTAL_TERMS[lang]`. PDF via WeasyPrint. |
| **Printable license invoice** | `GET /api/licenses/{id}/invoice` | Same renderer family; logo injected; purchase-date metadata. |
| **Rental terms (title + 12 rules × 6 langs)** | server data module ported from `config/terms.py` | Used by invoice renderer. |
| **Home/Dashboard** | FE `/` | Title `👤 <full_name> — <role label>`; "Available now" cards (with photos), fleet table (no thumbnails). |
| **Reservations page order** | FE `/reservations` | active cards → quick booking → timeline (bottom); never early-returns. |
| **Profile (self edit)** | `PATCH /api/users/me` | Every role: own full name, email, password. |
| **First-run bootstrap** | Alembic + seed script | `ensure_default_admin()` (`admin`/`admin`, super_admin) + CSV seed on empty fleet, run as an idempotent startup/migration task (§4). |
| **Currency display** | FE `formatEur` util | INTEGER cents → string only at display; mirrors `ui.components.format_eur`. |

---

## 4. Data layer & migration

### 4.1 PostgreSQL schema design
Keep the v3 contracts; upgrade types where Postgres does better.

| Concern | v3 (SQLite) | v4 (Postgres) |
|---|---|---|
| Money | `INTEGER` cents | `BIGINT` cents (still integer, never float) |
| Date-times (`start_dt`, `end_dt`, `created_at`, `occurred_at`) | ISO-8601 **text** | `timestamptz` (store UTC; convert at edges). Keep a thin `to_iso()` helper so the ported services that `datetime.fromisoformat(...)` still work. |
| Cost `period_date`, license `purchase_date` | `YYYY-MM-DD` text | `date` |
| Status vocab | CHECK constraints | Native `CHECK` **or** Postgres `ENUM`; prefer CHECK to keep parity with `config/settings.py` lists (still change both together). |
| Booleans (`is_active`, `contract_signed`) | INTEGER / 'Yes'/'No' text | `boolean` (migrate 'Yes'/'No' → true/false; 1/0 → bool) |
| Auto-increment ids | `AUTOINCREMENT` | `GENERATED ALWAYS AS IDENTITY` |
| `vehicle_id` / `deal_id` | TEXT PK | `TEXT` PK unchanged (`C001…`, `RENT-YYYYMM-NNN`) |
| Photos / logo | base64 in TEXT columns | **object storage** (S3/MinIO); DB keeps a key/URL + metadata. `bytea` is the fallback if no bucket. |

Indexes from `core/schema.sql` are reproduced 1:1 (rentals interval, charges, costs,
photos, sessions-expires) as Alembic-managed indexes.

**ID generation** stays server-side and concurrency-safe:
- `vehicle_id` (`C00n`): compute next from `MAX(substring)` **inside the insert
  transaction** with `SELECT … FOR UPDATE` advisory lock, or a dedicated sequence
  feeding a formatter. (v3 relied on single-writer SQLite; Postgres needs the lock.)
- `deal_id` (`RENT-YYYYMM-NNN`): same — port `next_deal_id`, but wrap in an advisory
  lock keyed on the `YYYYMM` prefix so two concurrent bookings can't collide.

### 4.2 Money & dates discipline (unchanged contract)
- API request/response money fields are **integer cents** (Pydantic `int`); the FE
  multiplies euro inputs by 100 and formats with a single `formatEur(cents)` util.
- API emits ISO-8601 strings for datetimes (so the ported services and the invoice
  renderer keep working); internally stored as `timestamptz`.

### 4.3 SQLite → Postgres data migration (concrete)
1. **Freeze** v3: stop the Streamlit app, checkpoint WAL (`PRAGMA wal_checkpoint`),
   take a copy of `fleet.db`.
2. **Stand up** the v4 Postgres schema via `alembic upgrade head` (empty DB).
3. **One-shot ETL script** (`scripts/migrate_sqlite_to_pg.py`, run once):
   - Open the SQLite copy read-only and the Postgres engine.
   - For each table in FK order (`vehicles` → `customers` → `rentals` →
     `charges`/`vehicle_costs` → `users` → `sessions` → `audit_log` →
     `app_settings` → `vehicle_photos` → `licenses`), stream rows and transform:
     - ISO text → `timestamptz`/`date`;
     - `'Yes'/'No'` → bool, `1/0` → bool;
     - base64 photo/logo strings → decode → upload to object storage → store the key
       (DROP the base64 once uploaded);
     - leave cents as integers, ids as text.
   - Wrap per-table loads in transactions; verify row counts match after each.
4. **Reconcile**: assertion pass — count per table, `SUM(amount)` per ledger,
   number of active rentals, number of users by role — must equal the SQLite source.
5. **Reset identity sequences** to `MAX(id)+1` for every IDENTITY column.
6. **Smoke test** read endpoints against migrated data before cutover (§11).

`sessions` rows can optionally be dropped (forces a clean re-login post-cutover —
acceptable and arguably preferable for the argon2/cookie change).

### 4.4 First-run bootstrap (parity with v3 self-seeding)
- Alembic migrations replace `_run_schema` + the four `_migrate_*` functions.
- A startup task runs `ensure_default_admin()` (creates `admin`/`admin` super-admin
  if zero users) and seeds vehicles from `fleet_master.csv` **only if the vehicles
  table is empty** (`INSERT … ON CONFLICT (vehicle_id) DO NOTHING` replaces
  `INSERT OR IGNORE`). Accept both `Base Daily Rate (€)` and legacy `($)` headers.

---

## 5. Backend plan (FastAPI)

### 5.1 Structure
```
backend/
  app/
    main.py                 # FastAPI app, CORS, middleware, lifespan (engine, bootstrap)
    deps.py                 # current_user, require(perm), db session, csrf check
    settings.py             # pydantic-settings: DB url, secrets, SMTP, bucket
    routers/
      auth.py vehicles.py rentals.py customers.py finance.py costs.py
      users.py audit.py settings.py licenses.py photos.py i18n.py timeline.py
    schemas/                # Pydantic v2 request/response models per domain
    services/               # PORTED from v3 services/ (Streamlit-free already)
      auth_service.py scheduling_service.py finance_service.py
      licensing_service.py audit_service.py email_service.py
    repositories/           # PORTED from v3 data/repositories/ (all SQL here)
    core/
      db.py                 # SQLAlchemy 2.0 engine/session factory (Postgres)
      security.py           # argon2id, token mint/hash, csrf
      ratelimit.py
    invoices/               # rental_invoice.py, license_invoice.py (HTML/PDF)
    i18n/                    # ported TRANSLATIONS + RENTAL_TERMS (server side)
  alembic/                  # migrations
  tests/
  pyproject.toml            # uv/poetry; ruff, mypy
```

### 5.2 Reuse of services / repositories (the surgical port)
The v3 `services/` and `data/repositories/` **do not import Streamlit** and already
return plain dicts — they move almost verbatim. Required edits, all mechanical:

| v3 idiom | v4 replacement |
|---|---|
| `create_engine(f"sqlite:///{DB_PATH}")` + SQLite pragmas | SQLAlchemy 2.0 engine on `postgresql+psycopg://`, pooled (QueuePool); pragmas dropped. |
| `datetime('now')` in SQL | `now()` (Postgres) |
| `strftime('%Y-%m', occurred_at)` / `'%Y'` | `to_char(occurred_at,'YYYY-MM')` / `'YYYY'` |
| `MAX(a,b)` / `MIN(a,b)` as 2-arg scalars (interval overlap) | `GREATEST(a,b)` / `LEAST(a,b)` |
| `INSERT OR IGNORE` | `INSERT … ON CONFLICT … DO NOTHING` |
| `PRAGMA table_info`, the four `_migrate_*` | Alembic migrations (delete the runtime migrators) |
| bcrypt hashing in `auth_service` | argon2id via `argon2-cffi` (keep `verify_password` able to read legacy bcrypt during a transition window, then re-hash on next login) |
| `invoice_lang in ("tr","en")` clamp in `create_rental` | validate against `LANGUAGES` (all six) — **bug fix** |
| `next_deal_id` / `C00n` under single-writer | add advisory lock (§4.1) |

`scheduling_service` (availability/overlap), `finance_service` (rollups),
`licensing_service`, `audit_service` keep their public function names so routers and
tests read like the originals.

### 5.3 Pydantic v2 models, validation, OpenAPI
- One module per domain in `schemas/` (e.g. `VehicleIn/VehicleOut`, `RentalIn`,
  `RentalOut`, `ChargeOut`, `PnLRow`, `UserOut`, `LicenseIn`). Money fields are `int`
  (cents) with `ge=0` where applicable; `invoice_lang`/`lang` use a
  `Literal["tr","en","de","it","es","sq"]`; statuses use enums mirroring
  `config/settings.py`.
- Validation at the boundary: euro→cents conversion happens in the FE; the API
  rejects floats for money. Date strings validated as ISO.
- **OpenAPI 3.1** auto-generated by FastAPI → consumed by `openapi-typescript` to
  generate the frontend client (single source of truth; no hand-written types).

### 5.4 Error handling
- Domain functions keep their `(ok, code)` / `(ok, code, info)` return shape; routers
  translate `code` (e.g. `password_too_short`, `role_not_allowed`, `user_exists`)
  into HTTP status + a stable `error_code` JSON field the FE maps to an i18n string.
- Global exception handler → RFC 7807-style problem JSON; never leak stack traces.
- All write endpoints are transactional; on failure nothing is audited and the row
  isn't created (no v3-style half-applied state).

---

## 6. Frontend plan (Next.js)

### 6.1 App Router structure
```
frontend/app/
  [locale]/                        # next-intl locale segment (tr|en|de|it|es|sq)
    (auth)/login/page.tsx
    (app)/
      layout.tsx                   # AppShell: collapsible sidebar + topbar + bell
      page.tsx                     # Home / Dashboard
      reservations/page.tsx
      fleet/page.tsx
      customers/page.tsx
      finance/page.tsx
      settings/
        profile/ business/ users/ language/ activity/ license/  (tabs as routes)
  api-proxy rewrites → FastAPI     # same-origin, cookie passthrough
components/   ui/ (shadcn) + domain components (VehicleCard, BookingDialog, Timeline…)
lib/         api client (generated), formatEur, dates, rbac (client-side hints)
messages/    tr.json en.json de.json it.json es.json sq.json
```
- **Server Components by default** for data fetching (fast first paint, no client JS
  for read-only pages); **Client Components** only where interactive (dialogs, forms,
  timeline, bell). Mutations via **Server Actions** or the typed client → FastAPI.

### 6.2 Component library & the single-font, minimalistic look
- **shadcn/ui** (Radix primitives + Tailwind) — copy-in components, no runtime dep
  bloat, fully themeable. Use Dialog (replaces `st.dialog`), Table, Tabs, Select,
  Card, Button, Badge, Toast.
- **One sans-serif font** self-hosted via `next/font` (e.g. Inter or Geist Sans) —
  **no Google Fonts CDN** (removes v3's "first paint needs the network"). Single
  family, weight scale only; no decorative faces.
- Tailwind design tokens: a small neutral palette + the v3 status colours mapped to
  semantic tokens (`ok/info/warn/danger/archived`) so timeline/badges match.

### 6.3 The responsive sidebar done right
- Persistent **collapsible** left sidebar on ≥`lg`: icon-only when collapsed, icon +
  label when expanded; state persisted (cookie/localStorage). The **content area
  reflows** (grid `min-content / 1fr`) — collapsing the sidebar widens content, it
  does not overlap.
- On `< md`: sidebar becomes a slide-over **Sheet** triggered by a hamburger; the
  nav items (emoji + label, mirroring v3's `ui/nav.py`) stack vertically and stay
  legible — no 0-px-iframe failure mode (that whole class of bug disappears with
  native React).
- Tables degrade to stacked cards under `sm` (mirrors v3's `@media (max-width:640px)`
  intent) so there is no horizontal scroll or pinch-zoom anywhere.

### 6.4 i18n (next-intl, all six languages)
- `next-intl` with `messages/<code>.json`. **Port the 334 v3 keys** out of
  `config/i18n.py` + `lang_*.py` into the six JSON files via a one-off script
  (keep the key names identical). A CI check asserts all six files have **identical
  key-sets** (parity guard, replacing the v3 invariant).
- Locale chosen per user (`users.lang`), applied on login; URL carries `[locale]`.
  Albanian (`sq`) hidden from the language picker for `visitor` (level 0); enforced
  server-side too.
- Rental-terms (`RENTAL_TERMS`) live **server-side** with the invoice renderer (not
  in the FE bundle) since invoices are server-rendered.

### 6.5 Printable invoices (server-rendered)
- Invoices are produced by FastAPI (`/api/rentals/{id}/invoice?lang=&format=html|pdf`)
  so the document is independent of the SPA and identical to print/PDF:
  - **HTML**: ported from `ui/invoice.build_invoice_html` — sub-A4 (max-width 640px),
    `@page size:A4`, logo in `.brand`, **deposit subtracted** (Subtotal / −Deposit /
    Grand Total), 12 terms in the chosen language.
  - **PDF**: render the same HTML with **WeasyPrint** (clean CSS paged media).
- The FE opens the invoice in a print-friendly route/new tab; a "Print" button calls
  `window.print()` for HTML, or downloads the PDF. License invoice: same family
  (`/api/licenses/{id}/invoice`).

---

## 7. AuthN / AuthZ & security hardening

| Control | Implementation |
|---|---|
| Password hashing | **argon2id** via `argon2-cffi` (tuned time/memory cost). Verify-and-rehash path accepts legacy bcrypt during transition, re-hashes on next successful login. |
| Min password length | keep `MIN_PASSWORD_LEN=6` (or raise to 8 — product call). |
| Session cookie | `sid`: httpOnly, Secure, `SameSite=Lax`, path `/`; 30 d (remember) vs session (12 h server-side TTL). Only **SHA-256 of token** in DB (port v3 design). |
| CSRF | Double-submit: `csrftoken` cookie (JS-readable) echoed in `X-CSRF-Token`; required on all non-GET. Dependency rejects mismatch. |
| RBAC | `require(perm)` FastAPI dependency using the **verbatim** `PERMISSION_MIN_LEVEL` table and `role_level`; `assignable_roles`, `_can_manage`, and the **last-active-super-admin guard** ported. Enforced server-side on every route — UI hiding is cosmetic only. |
| Rate limiting | `slowapi` (or Redis token bucket) on `/api/auth/login` and `/api/auth/recover` (per-IP + per-username); exponential backoff on repeated failures. |
| Audit | `audit_service.record(user, action, entity, entity_id, detail)` after every successful mutation (ported); `GET /api/audit` applies the role-based masking + filter-by-Action/User. |
| Input validation | Pydantic v2 at the boundary; parametrised SQL only (already true — all SQL is bound). Status/lang via enums/Literals. |
| Secrets | **Out of the DB**: `DATABASE_URL`, `SESSION_SECRET`, SMTP creds, `FALLBACK_EMAIL`, bucket creds via env / secret manager (pydantic-settings). SMTP password no longer stored plaintext in `app_settings` (v3 did). |
| Transport | HTTPS only; HSTS; secure headers (`secure`/`starlette` middleware): CSP, X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy. |
| Recovery hardening | `self_recover` admin+ only (delivers to own email); `admin_recover_child` → acting admin's email; SMTP-unset fallback returns generated password **only in the authorised admin's response** + audits it. Generic "if the account exists, mail was sent" message to avoid user enumeration. |
| Email | `email_service` ported (STARTTLS, never raises); creds from env. |

---

## 8. Testing strategy

| Layer | Tooling | Coverage targets |
|---|---|---|
| **Domain unit** | `pytest` | Pure functions: `compute_return`, `return_state` (overdue/due-soon/ok boundaries at `DUE_SOON_HOURS`), `_merge`/`pnl_*`, `profit_by_vehicle`, `licensed_year`/`max_date`/`extend_licensed_year`, `next_deal_id` formatting, `assignable_roles`, `is_last_active_super_admin`, `format_eur`. No DB. |
| **Repository / integration** | `pytest` + **testcontainers-postgres** (ephemeral PG) | Every repo against a real Postgres: interval-overlap `available_vehicles`/`is_vehicle_free`, `create_rental` transaction (charges + status flip), `settle_and_close`, soft/hard delete + photo cleanup, ID concurrency under advisory lock. |
| **API** | `pytest` + **httpx** `AsyncClient` (ASGI transport) | Auth (login/logout/CSRF/rate-limit), RBAC matrix (each of 4 roles × each endpoint → 200/403), validation rejects (floats for money, bad lang, bad status), invoice endpoint returns deposit-subtracted totals. |
| **Type safety** | **mypy** (strict on services/repos) + **tsc** (`noImplicitAny`) | Generated TS client keeps FE/BE types in lockstep. |
| **E2E** | **Playwright** (Chromium + mobile viewport) | Critical journeys: login → book a car → print invoice (all six langs) → close rental → see revenue; responsive checks at 375 px and 1440 px (sidebar collapse, table→card reflow, no horizontal scroll). |
| **Lint/format** | **ruff** (py), **eslint + prettier** (ts) | Enforced in CI. |
| **i18n guard** | custom test | All six `messages/*.json` have identical key-sets (replaces "334 keys × 6" invariant). |
| **CI** | GitHub Actions | jobs: lint → mypy/tsc → unit → integration (PG service) → API → build → Playwright (on PR). Block merge on red. |

(Note: v3 has **no test suite** — establishing this is a net new deliverable and a
core reliability goal.)

---

## 9. Deployment & infrastructure

| Concern | Choice |
|---|---|
| Containerization | Three images via multi-stage Dockerfiles: `api` (uvicorn+gunicorn workers), `web` (Next.js standalone output), and reuse official `postgres:16`. `docker-compose.yml` for local/staging (api + web + db + MinIO). |
| Postgres hosting | Managed (Supabase / Neon / RDS / Fly Postgres) in prod; container in dev. Daily automated snapshots + PITR (WAL archiving). |
| Object storage | S3 (prod) / MinIO (dev) for photos + logo; signed URLs for reads, server-side upload for writes. |
| Migrations | **Alembic**; `alembic upgrade head` runs as a pre-start job (not in app code). Migrations reviewed in PRs. |
| Config | `pydantic-settings`, 12-factor env; `.env.example` documents every var; no secrets in the repo. |
| Reverse proxy | Caddy/Nginx terminating TLS; `web` proxies `/api/*` to `api` (same-origin → simple cookie/CSRF story). |
| Observability | Structured JSON logging (`structlog`); request-id middleware; `/healthz` + `/readyz`; metrics via Prometheus (`prometheus-fastapi-instrumentator`); error tracking (Sentry, FE + BE). |
| Backups | DB snapshots (daily + PITR), object-storage versioning, retention policy; documented restore runbook. |
| Scaling/perf | gunicorn worker count tuned to cores; SQLAlchemy pool sized to DB max-connections; HTTP caching/ETag on photo + listing reads; Next.js static where possible. |

---

## 10. Phased roadmap

> Effort is rough engineering time for one experienced full-stack dev; parallelizable
> where noted. Phase names are the canonical milestones.

| Phase | Name | Key deliverables | Effort |
|---|---|---|---|
| **Phase 0** | **Scaffolding** | Monorepo (`backend/`, `frontend/`, `infra/`); FastAPI + Next.js hello-world wired same-origin; Docker Compose (api+web+pg+minio); CI skeleton (lint/type/test jobs); pydantic-settings + `.env.example`; shadcn/ui + single self-hosted font + Tailwind tokens. | ~1 wk |
| **Phase 1** | **Domain port + DB** | Postgres schema in Alembic (parity with `schema.sql` + indexes); port `services/` + `data/repositories/` with the §5.2 edits; SQLAlchemy 2.0 engine; object-storage adapter for photos/logo; one-shot SQLite→PG ETL script; domain + repository tests green (testcontainers). | ~2 wks |
| **Phase 2** | **API** | All routers (§5.1) + Pydantic schemas; auth (argon2id, cookies, CSRF, rate-limit); RBAC dependency; audit wiring; OpenAPI → generated TS client; API/RBAC test suite green. | ~2–3 wks |
| **Phase 3** | **Frontend core** | AppShell (responsive collapsible sidebar + topbar + bell); auth/login; Home, Reservations, Fleet, Customers pages (read + core mutations: book, close, cancel, vehicle CRUD, customer edit); photo gallery; timeline component (bundled, no CDN). | ~3 wks |
| **Phase 4** | **Finance, invoices & i18n** | Finance page (revenue/cost/P&L charts + tables); costs CRUD; Settings tabs (profile, business+logo, users, language, activity, license CRUD + SMTP); next-intl with all six languages ported (+ key-set guard); server-rendered rental & license invoices (HTML + WeasyPrint PDF, deposit-subtracted, logo). | ~3 wks |
| **Phase 5** | **Hardening & QA** | Security headers/CSP/HSTS; rate-limit + recovery-flow hardening; Playwright e2e (desktop + mobile, six-language invoice check); perf pass (ETags, pooling, query review); accessibility pass; observability (logs/metrics/Sentry/health). | ~2 wks |
| **Phase 6** | **Cutover & data migration** | Run ETL on a copy → reconcile counts/sums → staging UAT → schedule cutover window → freeze v3 → final migrate → smoke test → DNS/switch → monitor; keep v3 + SQLite copy for rollback. | ~1 wk |

**Total:** ~14–15 weeks single-dev (compressible with a second dev splitting
backend/frontend across Phases 2–4).

---

## 11. Risks & mitigations; rollback / cutover

| # | Risk | Mitigation |
|---|---|---|
| R1 | SQLite→PG SQL idiom drift (`strftime`, `MAX/MIN`, `datetime('now')`) silently changes results | Centralise in §5.2 table; repository integration tests assert identical outputs vs known fixtures before cutover. |
| R2 | ID collisions under Postgres concurrency (`C00n`, `RENT-…`) | Advisory locks / sequences (§4.1); concurrency test in CI. |
| R3 | Base64→object-storage migration loses/corrupts photos | ETL verifies decode + re-fetch round-trip per asset; keep base64 source in the SQLite copy until verified. |
| R4 | Timestamp/timezone mismatch breaks overdue/due-soon math | Store `timestamptz` UTC, emit ISO; reuse ported `return_state` and unit-test boundary cases; document that v3 used naive local time (decide and freeze the tz policy). |
| R5 | i18n key drift across six languages | CI key-set parity test; port keys mechanically, never by hand. |
| R6 | Security regressions (CSRF, cookie flags, RBAC gaps) | RBAC matrix test (4 roles × every endpoint); security headers test; pen-test pass in Phase 5. |
| R7 | Carrying v3 bugs forward (invoice-lang clamp; orphaned photos on hard delete; SMTP password plaintext) | Explicitly fixed in v4 (§3, §5.2, §7) and covered by tests. |
| R8 | Scope creep into new features | Non-goals (§1) are the contract; parity matrix (§3) is the acceptance checklist. |
| R9 | Cutover data loss / downtime | Rehearse ETL on a copy; short freeze window; keep v3 running read-only as fallback. |

**Rollback / cutover strategy**
1. **Rehearse** the full ETL on a *copy* of `fleet.db` into a staging Postgres; run
   reconciliation (row counts + ledger sums + role counts) and staging UAT.
2. **Cutover window** (low-traffic): announce → freeze v3 (read-only / app down) →
   WAL-checkpoint and snapshot `fleet.db` → run final ETL → reconcile → smoke-test
   key read/write journeys on v4 → flip the reverse proxy / DNS to v4.
3. **Rollback trigger**: if reconciliation fails or smoke tests fail, abort — revert
   proxy to v3 (data never left SQLite; the v3 app and the original `fleet.db` copy
   are untouched). No destructive step on the source until v4 is confirmed.
4. **Post-cutover**: monitor errors/latency for 48 h; retain the SQLite snapshot and
   v3 image for a defined window (e.g. 30 days) before decommission.

---

## 12. Definition of done

A V4 milestone is **done** when **all** hold:

- [ ] Every row in the **feature-parity matrix (§3)** is implemented and verified;
      no v3 capability is missing.
- [ ] Money is **integer cents** end-to-end (DB `BIGINT`, API `int`, FE
      `formatEur` at display only); no float touches money in any layer.
- [ ] IDs match v3 formats (`C00n`, `RENT-YYYYMM-NNN`) and are collision-safe under
      concurrency (test proves it).
- [ ] All four roles + the exact `PERMISSION_MIN_LEVEL` table enforced **server-side**;
      RBAC matrix test (4 roles × endpoints) green; last-super-admin guard works.
- [ ] argon2id hashing; httpOnly+Secure session cookie storing only the token hash;
      CSRF enforced on writes; auth/recovery rate-limited; secrets in env not DB;
      security-headers + RBAC tests green.
- [ ] All six languages ship with **identical key-sets** (CI parity test); per-user
      language works; `sq` staff-gated; invoices render in all six.
- [ ] Rental & license invoices render server-side (HTML + PDF), **deposit
      subtracted**, logo shown, 12 terms in the chosen language.
- [ ] Responsive: usable with no horizontal scroll/pinch-zoom at 375 px and 1440 px;
      sidebar collapses and content reflows; tables become cards on phone
      (Playwright mobile checks green).
- [ ] Test suite green in CI: domain unit, repository integration (real Postgres),
      API, e2e; mypy (strict) + tsc clean; ruff/eslint clean.
- [ ] SQLite→Postgres ETL rehearsed; reconciliation (row counts, ledger sums, user
      roles) matches source exactly; photos/logo verified in object storage.
- [ ] Deploy: Dockerised api+web; Alembic migrations run as pre-start; backups + PITR
      configured; `/healthz`+`/readyz`, structured logs, metrics, Sentry live.
- [ ] Documented rollback path validated on staging; v3 retained as fallback for the
      defined window.
- [ ] **No known v3 bug carried forward** (invoice-lang clamp, orphaned vehicle
      photos on hard delete, plaintext SMTP password) — each fixed and tested.
```
