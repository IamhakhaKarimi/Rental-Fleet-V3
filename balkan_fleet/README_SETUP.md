# Balkan Car Rentals — Fleet Console v3.0
### Complete setup guide — no coding required

The app builds and fills its own database on first run from `fleet_master.csv`.
You never import anything by hand.

---

## 1. Install Python (one time)
Download **Python 3.11+** from https://www.python.org/downloads/ and, on the first
install screen, tick **“Add Python to PATH”**. (This one checkbox prevents the most
common error.)

## 2. Get a clean folder
Download **`balkan_fleet_v2.zip`**, and **delete any old `balkan_fleet` folder first**,
then unzip this one fresh. (Unzipping over an old copy leaves stale files — the usual
reason a menu looks empty.) To confirm you're on this build, the top bar shows
**“Fleet Console · v3.0”**.

## 3. Start the app
**Windows (easiest):** double-click **`start_balkan_fleet.bat`**. It installs the
exact libraries it needs the first time, then opens the app in your browser.

**Any system (manual):** open a terminal in the folder and run
```
python -m pip install -r requirements.txt
python -m streamlit run app.py
```
(macOS: use `python3`.) We call `python -m streamlit` on purpose — it avoids the
“streamlit is not recognized” PATH error.

## 4. Sign in
Default administrator: **`admin` / `admin`**. Change it immediately in
**Settings → Password**. Tick **Remember me** to stay signed in for 30 days.

---

## What the app does

**Top bar** — sticky navigation, one click from anywhere, with the **🇹🇷/🇬🇧 language
switch built in**. Sections you can't use are hidden.

**Overview** — fleet occupancy timeline (zoom with the +/− buttons, “NOW” line
labelled), live KPIs, availability calculator, and a quick rental form whose euro
total updates live. Searchable fleet table.

**Reservations** — create rentals; every active rental is a card with overdue
detection (red “OVERDUE” badge + hours late). Each card has:
- **Cancel** — closes the rental and frees the car.
- **Manage / Return** — log an overdue penalty and/or damage charge, add return
  notes, mark the contract signed, then close the rental and free the car. These
  charges flow straight into Finance.

**Fleet (full CRUD)** — four tabs: browse, **Add** a vehicle (code auto-assigned),
**Edit** any field, and **Delete/Archive** (Admin archives, Super Admin permanently
deletes, and archived cars can be restored).

**Customers** — directory of everyone ever rented to, with rental counts, last
rental, and a per-customer history drill-down.

**Finance** (Admin + Super Admin only) — total / rental / penalty / damage revenue
KPIs, a monthly revenue bar chart, and a per-vehicle breakdown.

**Settings** — tabs by role:
- **Business** (Super Admin) — set the business name shown across the app.
- **Users** (Admin+) — create users with a role drop-down, change roles, and
  activate/deactivate accounts. Super Admin creates Admins/Super Admins; Admin
  creates Employees/Visitors.
- **Password** (everyone) — change your own.

## Roles
| | Overview / Reservations / Fleet (view) | Create/cancel/return rentals | Add/Edit fleet | See Finance | Archive car | Delete car | Manage users | Set business name |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **Super Admin** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (any role) | ✓ |
| **Admin** | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ (Employee/Visitor) | — |
| **Employee** | ✓ | ✓ | — | — | — | — | — | — |
| **Visitor** | ✓ | — | — | — | — | — | — | — |

## Notes
- **Reset everything** (incl. users) to the original 13 cars + default admin: stop
  the app, delete `fleet.db` (and `fleet.db-wal`/`fleet.db-shm`), start again.
- **Internet** is needed the first time each screen loads (fonts, calendar, menu,
  cookie components load from the web).
- **Money** is euro, stored as exact integer cents (no rounding drift).
- Passwords use **bcrypt**; “remember me” stores only a hashed session token.
