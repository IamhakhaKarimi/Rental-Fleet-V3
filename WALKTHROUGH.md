# Balkan Car Rentals — Fleet Console v3.0 — App Walkthrough (phase by phase)

A step-by-step tour of the running application, in the order a user moves through
it: from launch and the landing/login screen, through reservations, fleet CRUD,
customers, the comprehensive finance evaluation, and settings — plus the new
print-ready invoice. Each phase notes **what the user does**, **what the system
does**, and the **code** behind it.

For architecture and module-level detail see [`DOCUMENTATION.md`](DOCUMENTATION.md);
for agent/editing conventions see [`CLAUDE.md`](CLAUDE.md).

> **Legend** — 👤 user action · ⚙️ system behaviour · 📄 code.

---

## Phase 0 — Launch & bootstrap

👤 Double-click `start_balkan_fleet.bat` (Windows) or run
`python -m streamlit run app.py`. The browser opens the app.

⚙️ On the very first launch the app builds itself:
1. `init_db()` runs `core/schema.sql` (creates all **11 physical tables** — the 9
   core data tables, including the new **`licenses`** record table, plus `sessions`
   and `vehicle_photos`; re-run idempotently so existing DBs gain `licenses` too),
   then runs
   four migrations in order (`_migrate_users`, `_migrate_rentals`,
   `_migrate_add_columns`, `_migrate_photos`) so existing DBs gain the newer columns
   and legacy single photos move into `vehicle_photos`.
2. If the `vehicles` table is empty, it seeds 13 cars from `fleet_master.csv`.
3. It creates the default super-admin **`admin` / `admin`** if no users exist.
4. The theme/fonts are injected and the language defaults to **Turkish**.

📄 [`app.py`](app.py) → `_bootstrap()` → [`core/db.py`](core/db.py) `init_db()` →
[`data/seed/import_csv.py`](data/seed/import_csv.py) +
[`services/auth_service.py`](services/auth_service.py) `ensure_default_admin()`.

> The bootstrap is cached (`@st.cache_resource`) so it runs once per server
> process, not on every interaction.

---

## Phase 1 — Landing page (sign-in)

👤 The landing screen is the **login card**: business name + tagline, username,
password, and a **Remember me (30 days)** checkbox. There is also a **Forgot
password?** expander. Sign in with `admin`/`admin` on first use, then change the
password later in Settings.

⚙️ On submit, `authenticate()` verifies the password with **bcrypt**. With
"Remember me" a 256-bit token is stored in the `bcr_session` cookie and only its
**SHA-256 hash** is saved server-side; the session lasts 30 days (vs. 12 hours
without). On a later visit, a valid cookie restores the session automatically and
the login card is skipped.

⚙️ **Forgot password** (`ui/auth_view.py` → `auth.self_recover`) is restricted to
**Admin/Super-Admin accounts**: it generates a random 10-char password, bcrypt-hashes
and saves it, then mails it to that account's **own** email (or, if SMTP is not
configured, shows the new password on-screen). Employees/visitors are told to ask
an admin. The language of the card follows the user's saved preference once known.

⚙️ Until authenticated, the rest of the app is blocked (`st.stop()`), so no page
is reachable without a session.

📄 [`ui/auth_view.py`](ui/auth_view.py) `ensure_authenticated()` / `_render_login()`;
sessions + recovery in [`services/auth_service.py`](services/auth_service.py);
cookie round-trip handled by the priming `st.rerun()` in [`app.py`](app.py).

**After login** a sticky **top navigation bar** appears on every page: business
name, who you're signed in as + your role, a **Log out** button, the section menu,
and — for staff who can create reservations — a **🔔 notification bell** (see
Phase 3d). There is **no** language switch in the top bar; language is per-user and
chosen in **Settings → Language**. The **Finance** item is hidden unless your role
can view it. 📄 [`ui/nav.py`](ui/nav.py).

---

## Phase 2 — Home (dashboard)

The default landing section after login. The nav label is **Home** (`nav_dashboard`
= Ana Sayfa / Home / Startseite / Inicio / Kreu).

👤 The page **title greets you** — `👤 <your full name> — <your role>` (it no longer
says "Overview"). You then see, top to bottom:
1. **Fleet occupancy timeline** — one row per vehicle, each rental a coloured bar
   on a time axis; a labelled **NOW** line marks the present, overdue bars are red.
   Zoom with the **+ / −** buttons; the mouse wheel pans.
2. **Four KPI tiles** — Total / Available / Rented / In-Garage-or-Maintenance.
3. **"Available now" cards** — one card per free car, each showing a **photo
   thumbnail** (140px tall, or a 🚘 avatar when no photo) and a **Rent** button that
   opens the quick-register popup (see Phase 3b).
4. **Booking panel** (availability + quick rental — see Phase 3).
5. **Searchable fleet table** — type to filter by any column. *(The fleet table
   shows no thumbnails — only the "Available now" cards render photos here.)*

⚙️ The greeting title resolves your role through `ROLE_LABEL_KEY` so "Employee",
"Admin", etc. show in your language. Counts come from a single grouped SQL query;
the timeline is a vis-timeline component built from the active rentals. Card
thumbnails load each vehicle's **primary** photo lazily and are cached
(`@st.cache_data`, keyed on the highest `photo_id`), so the listing query itself
carries no photo bytes.

📄 [`views/dashboard.py`](views/dashboard.py) `render_dashboard()`,
[`ui/timeline.py`](ui/timeline.py),
[`ui/photos.py`](ui/photos.py) `render_vehicle_thumb()`, `vehicles.fleet_counts()`.

---

## Phase 3 — Reservations (create, manage, return) + invoice

👤 The Reservations page has three stacked parts, **reordered** to minimise overlap
with Home: the **active-rental cards** (top), the **booking panel** (quick rental
registration, middle), and the **timeline/calendar** (bottom). The page renders all
three even when there are **no active rentals** — booking and the calendar still
show, so you can always make a new reservation.

### 3a. Check availability & calculate the return
👤 Pick a **start date/time**, a **number of days**, and a **return time**.
⚙️ The app shows the exact **calculated return** moment and lists **only the cars
free for that window** (an indexed interval-overlap query, excluding cars that are
deleted, rented, in garage, or in maintenance). The **start-date picker is capped**
at the licensed year-end (`lic.max_date()`), so staff can't book into an unlicensed
year.
📄 [`ui/booking.py`](ui/booking.py),
[`services/scheduling_service.py`](services/scheduling_service.py),
[`services/licensing_service.py`](services/licensing_service.py).

### 3b. Register the rental
👤 Click **Rent** on an "Available now" card (dashboard) or pick a free car in the
booking panel — either opens a **quick-register popup** (`st.dialog`). Enter the
customer's **name / phone / ID**, adjust the **negotiated daily rate** (defaults to
list price) and any **deposit**, and choose the **invoice language** (any of the six —
TR / EN / DE / IT / ES / SQ). The **total updates live** as you change the rate. Click
**Save Rental**.
⚙️ On save the app **re-checks availability** (`is_vehicle_free`) so a car booked by
someone else in the meantime can't be double-booked, then in one transaction:
finds-or-creates the customer, inserts the rental (storing the chosen
`invoice_lang` and a snapshot of who booked it), posts a `rental` charge (and a
`deposit` charge if any), and flips the car to **Rented**. The action is **audited**.
The popup's start-date picker is also capped at `lic.max_date()`.
📄 [`ui/booking.py`](ui/booking.py) `open_rental_dialog()`,
`rentals.create_rental()`, `customers.get_or_create_customer()`,
`audit_service.record(...)`.

### 3c. Print the invoice  🧾
⚙️ Immediately after saving, a **print-ready invoice** opens for the new rental:
business header (with the **company logo** when one is set in Settings → Business),
**Bill To** (customer), vehicle + rental period, a line-item table
(rental days × rate), a subtotal, a **− Deposit** deduction row, the grand total
(subtotal − deposit = balance due), and a two-column list of
**rental terms** in the chosen language (`config/terms.py` — title + 12 rules per
language). The invoice is a compact, sub-A4 HTML sheet with **A4 print rules**
(`@page size:A4`), and a radio lets you flip it between **all six languages**
(TR / EN / DE / IT / ES / SQ) before printing — a customer document is independent
of UI-language role gating, so Albanian is always offered here. `build_invoice_html`
validates the requested `lang` against `LANGUAGES`.
👤 Click **🖨️ Print Invoice** to open the browser print dialog, or **⬇️ Download
Invoice (HTML)** to save a standalone file the client can keep/print. Click
**Close** to dismiss it.
📄 [`ui/invoice.py`](ui/invoice.py) `render_invoice()` (passes `app_cfg.get_logo()`) /
`build_invoice_html(deal, charges, business_name, lang, logo)`; data from
`rentals.get_rental_full()` + `rentals.list_charges_for_deal()`. The same invoice is
also reachable from a customer's rental history (Phase 5).

### 3d. The notification bell  🔔
👤 For staff who can create reservations, a **bell** sits in the top nav with a
badge counting rentals that are **overdue** or **due soon** (within 24h). Click it
to open a dialog listing those rentals with a **copyable phone number** and
**WhatsApp message / call** link-buttons for chasing the customer.
⚙️ State comes from `scheduling_service.return_state` (also used by the timeline
colouring and the reservations list). The old dashboard reminder block was folded
into this top-bar bell.
📄 [`ui/notifications.py`](ui/notifications.py) `render_bell()`, mounted in
[`ui/nav.py`](ui/nav.py).

### 3e. Manage / return an active rental
👤 Each active rental is a **card** showing customer, vehicle, period, totals.
Overdue rentals get a red **OVERDUE** badge with hours-late. Two actions
(permission-gated):
- **Cancel** — closes the rental and frees the car.
- **Manage / Return** — log an **overdue penalty** and/or **damage charge**, add
  return notes, mark the contract signed, then **Process Return & Close**.
⚙️ On return, the charges post to the ledger (damage also accrues on the vehicle's
maintenance total), the rental closes, the car becomes **Available**, and the
event is audited. These charges flow straight into Finance.
📄 [`views/reservations.py`](views/reservations.py),
`rentals.cancel_rental()` / `rentals.settle_and_close()`.

> Overdue is **derived**, never stored: a rental is overdue when its `end_dt` is in
> the past.

---

## Phase 4 — Fleet (one action table)

The CRUD **tabs are gone**. Fleet is now a **single searchable action table** —
one row per vehicle (code, model, year, plate, status, rate) with a per-row
**Actions** column. A **search box** filters across every field.

👤 What you can do depends on your role:

- **Non-privileged roles** see the table **read-only** (code, model, year, plate,
  colour, mileage, status, rate, notes; no thumbnails, no buttons).
- **➕ Add Vehicle** *(needs Admin — `edit_fleet`)* — a button above the table opens
  an **Add popup** (`st.dialog`): make/model, year, plate, colour, mileage, rate,
  status, notes, and **upload one or more photos** (multi-file). ⚙️ The **vehicle
  code is auto-assigned** (`C001`, `C002`, …); each uploaded image is cropped to a
  uniform **640×480 (4:3)** JPEG and stored in `vehicle_photos`.
- **✏️ Edit** *(Admin)* — the row's edit icon opens an **Edit popup** showing a
  **120px thumbnail** and a **photo manager** behind a `st.toggle`: expanding it
  lazily loads the full gallery (4 per row, ~90px each) to **delete** individual
  photos or **add more**.
- **🗑️ Delete / Archive** *(needs `soft_delete_vehicle`)* — the row's delete icon
  opens a **Delete popup**: tick the confirm box, then **Archive** (status →
  `DELETED`, reversible; the car drops out of listings but keeps its history) or,
  for **Super Admin only** (`hard_delete_vehicle`), **Delete permanently**.

👤 **Dynamic Status column** *(editors only)* — alongside the status label, small
buttons let you change a car's state **immediately** (no popup): **🅿️ To Garage**,
**🔧 To Maintenance**, and — for a car already in Garage/Maintenance — **✅ Make
Available**. ⚙️ Each calls `vrepo.set_status` and audits the change on the spot.
Manual status is limited to **Available** and **Maintenance**, and these controls
(plus the Edit dialog's status selectbox) are **locked while the car has an active
rental** (`rentals.vehicle_has_active_rental`); the Edit dialog then shows a lock
notice (`status_locked_rented`).

👤 **Archived vehicles** — a bottom **expander** lists archived cars, each with a
**Restore** button to bring it back to **Available**.

⚙️ Every add/edit/archive/delete/restore and every status change is written to the
**audit log**. Each photo add/delete also clears the thumbnail cache so the Home
cards refresh.
📄 [`views/fleet.py`](views/fleet.py) (`_action_table`, `_set_status`,
`_add_dialog`, `_edit_dialog`, `_delete_dialog`, `_archived_section`),
[`ui/photos.py`](ui/photos.py),
[`data/repositories/vehicles.py`](data/repositories/vehicles.py) `set_status()`,
[`data/repositories/vehicle_photos.py`](data/repositories/vehicle_photos.py).

> Legacy single photos stored on the old `vehicles.photo` column are migrated into
> `vehicle_photos` once on startup; new uploads only ever write the
> `vehicle_photos` table.

---

## Phase 5 — Customers *(redesigned)*

👤 A **minimalist card view**: one compact **card per customer** in a **3-up grid**,
each showing name, phone, **rental count**, **last-rental date**, and who registered
them. A **search** box filters by name or phone. A page-level **Open Full Table**
button (`open_full_table`) pops the complete customers table in a dialog for when you
want the dense list.

👤 Each card has an **Open** button (`card_open`) that pops a **per-customer dialog**
containing everything for that one person:
- **✏️ Edit details** *(Employee+)* — change name / phone / ID; saved + audited.
- **Rental history** table — with a **Print Invoice** column whose cells are one
  small **flag button per available language** (Albanian flag only for staff).
- **👤 Reassign "registered by"** *(Admin+)* — point a past deal at a different staff
  member (updates the booking-staff snapshot); audited. The deal is identified by the
  **customer's full name**: the selectbox is labelled with the customer name and each
  option leads with the full name plus car/period to disambiguate (no raw contract/deal
  id is shown).

👤 **Print an invoice from history** — click a **flag** in the Print-Invoice column and
the same print-ready invoice as Phase 3c opens **in that language** in its own pop-up
dialog (decluttered, one document at a time).

⚙️ Customers are created automatically during booking (deduped on name + phone).

> **Gotcha — single-dialog dance.** Streamlit allows only **one `st.dialog` open at a
> time** (no nesting), so the per-customer dialog cannot itself open the invoice dialog.
> Each flag button instead stashes a one-shot `(deal_id, lang)` in
> `session_state["cust_invoice"]` and calls `st.rerun()` — which **closes the customer
> dialog** — and a **dispatch at the top of `render_customers()`** re-opens it as a
> standalone invoice dialog.

📄 [`views/customers.py`](views/customers.py),
[`data/repositories/customers.py`](data/repositories/customers.py),
`rentals.update_creator()`, [`ui/invoice.py`](ui/invoice.py). New i18n keys:
`card_open`, `open_full_table` (added in all six languages).

---

## Phase 6 — Finance: monthly & yearly income / cost / profit  💰 *(rebuilt)*

*Visible to Admin and Super Admin only.* The page now evaluates **income vs cost
vs net profit**, not just revenue.

👤 At the top, four **headline KPIs**: **Total Revenue**, **Total Cost**, **Net
Profit**, **Profit Margin**. Below them, five tabs:

1. **📊 Overview** — revenue mix (rental / overdue penalties / damage) and a
   **cost-by-type** breakdown.
2. **📅 Monthly** — a grouped **income vs cost** bar chart per calendar month, plus
   a table with **income, cost, and net** for each month.
3. **🗓️ Yearly** — the same evaluation rolled up **per year** (for year-over-year
   comparison).
4. **🚗 By Vehicle** — **per-car profitability**: income − cost = net, sorted by
   most profitable.
5. **🧾 Costs** — **record operating costs** (insurance, maintenance,
   depreciation, fuel, financing, registration, other) against a vehicle with an
   amount, date, and note; review and delete **recent cost entries**.

⚙️ Income is summed from the `charges` ledger (rental + overdue + damage; deposits
and refunds excluded). Costs come from the new `vehicle_costs` ledger. The service
joins the two by month, by year, and by vehicle to produce the income/cost/net
figures and the profit margin. Adding/removing a cost is audited.

📄 [`views/finance.py`](views/finance.py),
[`services/finance_service.py`](services/finance_service.py) (`pnl_summary`,
`pnl_by_month`, `pnl_by_year`, `profit_by_vehicle`),
[`data/repositories/vehicle_costs.py`](data/repositories/vehicle_costs.py).

> **Workflow tip:** revenue accrues automatically from rentals/returns; costs are
> entered by hand in the **Costs** tab. Once both exist, Monthly/Yearly/By-Vehicle
> show a true profit picture. With no data yet, the page opens straight on the cost
> form so you can capture the first numbers.

---

## Phase 7 — Settings (by role)

👤 Tabs appear according to your permissions, in this order:

- **🏢 Business** *(Admin+)* — two parts. The **business name** form (shown in the
  top bar and on the sign-in screen) stays **Super Admin only**. Below it, the
  **company logo** is editable by **Admin+**: upload a PNG/JPEG (`upload_logo`),
  preview it, or **Remove** it. ⚙️ The logo is encoded by `ui.photos.encode_logo`
  **aspect-preserving, fit within 280×100** (it is *not* cropped like car photos),
  stored as a base64 **PNG** in `app_settings` (`set_logo`/`get_logo`/`clear_logo`),
  and **rendered on both invoices** (rental + software-license) in the header
  `.brand` block whenever one is set.
- **👥 Users** *(Admin+)* — create users (Super Admin grants any role; Admin grants
  Employee/Visitor), change roles, activate/deactivate accounts, set a user's
  **email**, and **reset a child user's password** (the new password is mailed to
  *your* email, or shown on-screen if SMTP is unset). You can't change your own role
  or deactivate yourself. ⚙️ **Last-super-admin guard** — for the **final active
  super-admin** (`auth.is_last_active_super_admin`), the role-change and
  activate/deactivate controls are **disabled** (with a `last_super_admin` note), so
  the system can never be left without a super-admin.
- **🔑 License** *(Super Admin only)* — full **license-record CRUD** plus the annual
  unlock and SMTP. A table lists each license record (year/period, licensee, amount,
  purchase date, notes) with per-row **✏️ Edit** (dialog), **🗑️ Delete** (dialog),
  and **🖨️ Print invoice** (dialog) actions; an **Add license** form below it
  records a new one. ⚙️ Records live in the new **`licenses`** table
  (`data/repositories/licenses.py`); adding or editing a record for a **later year**
  calls `licensing_service.extend_licensed_year()`, which pushes out the date-picker
  cap. The original **unlock-next-year** button still extends
  `app_settings.licensed_until_year` (extend-only, audited) and generates a
  **print-ready software-license invoice**, and the **SMTP** form
  (host/port/from/credentials, used by password recovery and reset-password mail)
  remains at the bottom. *(All booking and cost date pickers cap at 31 Dec of the
  licensed year; a license invoice's own purchase-date is intentionally uncapped, as
  it is invoice metadata.)*
- **🌐 Language** *(everyone)* — choose from **six UI languages**: 🇹🇷 Türkçe, 🇬🇧
  English, 🇩🇪 Deutsch, 🇮🇹 Italiano, 🇪🇸 Español and 🇦🇱 Shqip (Albanian). The tab is
  driven by the `LANGUAGES` registry in `config/settings.py` and filters
  `STAFF_ONLY_LANGS = {"sq"}` by role level — **Albanian is shown only to staff
  "parent" roles** (Employee/Admin/Super-Admin, role level ≥ 1); visitors see the
  other five. The choice is saved per-user on `users.lang` (validated against
  `LANGUAGES` by `auth_service.set_user_lang`) and applied on every login/restore.
- **👤 Profile** *(everyone)* — edit your **own** account: change your **Full Name**
  (`auth.set_user_full_name` → `users.update_full_name`), set your **own email**
  (used as the recovery destination for Admin/Super-Admin "forgot password"), and
  **change your password**. *(This was previously the "Password" tab; it is now the
  Profile tab, `tab_profile`, and available to every role.)*
- **🕑 Activity** *(Admin+)* — the **audit log** (latest 500 entries): who did what
  and when (rentals, fleet, cost entries, user-management, settings, photo/license
  changes). It has a **"Filter by" toggle** (`st.radio`) that switches between
  filtering by **Action** (multi-select action types) and by **User** (masked names
  respected), and **masks higher-ranked actors** as "system admin" (an actor whose role level is
  strictly above yours is hidden by name, so an admin can't read super-admin names).

📄 [`views/settings.py`](views/settings.py),
[`services/auth_service.py`](services/auth_service.py)
(`set_user_full_name`, `is_last_active_super_admin`),
[`services/audit_service.py`](services/audit_service.py),
[`services/licensing_service.py`](services/licensing_service.py)
(`extend_licensed_year`),
[`services/email_service.py`](services/email_service.py),
[`data/repositories/licenses.py`](data/repositories/licenses.py),
[`data/repositories/app_settings.py`](data/repositories/app_settings.py)
(`get_logo`/`set_logo`/`clear_logo`),
[`ui/photos.py`](ui/photos.py) `encode_logo()`,
[`ui/license_invoice.py`](ui/license_invoice.py).

> **Email recovery fallback:** when SMTP is unconfigured (`is_configured()` false),
> recovery and child-reset show the new plaintext password on-screen instead of
> emailing it; the action is still audited. The hard-coded fallback recipient in
> code is `hakamaneshkarimi@gmail.com` (distinct from the `admin` owner login).

---

## Roles at a glance

| Action | Visitor | Employee | Admin | Super Admin |
|---|:--:|:--:|:--:|:--:|
| View Home / Reservations / Fleet / Customers | ✓ | ✓ | ✓ | ✓ |
| Create / cancel / return rentals (+ invoice) | — | ✓ | ✓ | ✓ |
| Add / edit fleet | — | — | ✓ | ✓ |
| Archive vehicle | — | — | ✓ | ✓ |
| Permanently delete vehicle | — | — | — | ✓ |
| View Finance + enter costs | — | — | ✓ | ✓ |
| Manage users (+ email, child-reset) + view Activity log | — | — | ✓ | ✓ |
| Self password-recovery ("forgot password") | — | — | ✓ | ✓ |
| Upload / remove company logo | — | — | ✓ | ✓ |
| Assign Admin/Super-Admin roles | — | — | — | ✓ |
| Set business name · License records + SMTP | — | — | — | ✓ |

*(Internal role id for "Employee" is `employer`; permission levels:
visitor 0 < employer 1 < admin 2 < super_admin 3.)*

---

## End-to-end happy path (one sentence per step)

1. Launch → DB self-builds and seeds. 2. Sign in (`admin`/`admin`). 3. Home
shows the live timeline + KPIs. 4. Reservations → pick dates → see free cars →
register a rental → **print the invoice**. 5. The car turns Rented and shows on the
timeline. 6. On return, log any late/damage charges and close it. 7. Fleet → add /
edit / archive cars (or flip status) from the action table. 8. Customers → review
who rented what. 9. Finance → enter monthly costs, then read **monthly & yearly
income vs cost vs net** and **per-vehicle profitability**. 10. Settings → manage
users, upload the company logo, record licenses, and audit all activity.
