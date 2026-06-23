"""
Destructive maintenance operations (super-admin only).

SQL lives here per the repository layering rule. Each reset runs in one
transaction and deletes child rows before parents so the foreign keys
(PRAGMA foreign_keys=ON) never block. Every statement names its table as a
fixed string literal — no f-string/identifier interpolation — so there is no
dynamic-SQL surface at all. Returns the per-table counts removed.
"""
from sqlalchemy import text
from core.db import get_engine


def reset_finance() -> dict:
    """Wipe BOTH financial ledgers — income (`charges`) and expenses
    (`vehicle_costs`). Vehicles, rentals, customers, users and settings are kept,
    so the Finance page simply returns to zero. Returns {table: rows_deleted}."""
    with get_engine().begin() as conn:
        counts = {
            "charges": conn.execute(text("SELECT COUNT(*) FROM charges")).scalar_one(),
            "vehicle_costs": conn.execute(text("SELECT COUNT(*) FROM vehicle_costs")).scalar_one(),
        }
        conn.execute(text("DELETE FROM charges"))
        conn.execute(text("DELETE FROM vehicle_costs"))
    return counts


def reset_fleet() -> dict:
    """Wipe the fleet and everything that references a vehicle: vehicle_photos,
    charges, vehicle_costs, rentals, then vehicles (child-first for FK safety).
    Customers, users, settings and licenses are kept. With the vehicles table
    empty, the default catalogue re-seeds automatically on the next app start.
    Returns {table: rows_deleted}."""
    with get_engine().begin() as conn:
        counts = {
            "vehicle_photos": conn.execute(text("SELECT COUNT(*) FROM vehicle_photos")).scalar_one(),
            "charges": conn.execute(text("SELECT COUNT(*) FROM charges")).scalar_one(),
            "vehicle_costs": conn.execute(text("SELECT COUNT(*) FROM vehicle_costs")).scalar_one(),
            "rentals": conn.execute(text("SELECT COUNT(*) FROM rentals")).scalar_one(),
            "vehicles": conn.execute(text("SELECT COUNT(*) FROM vehicles")).scalar_one(),
        }
        conn.execute(text("DELETE FROM vehicle_photos"))
        conn.execute(text("DELETE FROM charges"))
        conn.execute(text("DELETE FROM vehicle_costs"))
        conn.execute(text("DELETE FROM rentals"))
        conn.execute(text("DELETE FROM vehicles"))
    return counts
