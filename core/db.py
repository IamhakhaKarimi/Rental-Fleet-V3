"""
Database access foundation.

- Uses SQLAlchemy over SQLite so a future move to PostgreSQL is mostly a
  connection-string change (the rest of the app talks to repositories, never
  to SQLite directly).
- Turns ON foreign keys and write-ahead logging (WAL) for integrity and
  better read/write concurrency.
- init_db() creates the schema (idempotent) and, on a brand-new database,
  seeds the vehicles table from fleet_master.csv automatically. So the app
  works on first launch with no manual import step.
"""

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine

from config.settings import DB_PATH

import os

_SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "schema.sql")

_engine: Engine | None = None


def get_engine() -> Engine:
    """Return a single shared engine for the whole app."""
    global _engine
    if _engine is None:
        _engine = create_engine(f"sqlite:///{DB_PATH}", future=True)

        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragmas(dbapi_conn, _):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys = ON")      # referential integrity
            cur.execute("PRAGMA journal_mode = WAL")     # concurrent reads during writes
            cur.execute("PRAGMA synchronous = NORMAL")   # safe under WAL, far faster writes
            cur.execute("PRAGMA busy_timeout = 5000")    # wait up to 5s for a lock instead of erroring
            cur.execute("PRAGMA temp_store = MEMORY")    # keep temp b-trees in RAM
            cur.execute("PRAGMA cache_size = -16000")    # ~16 MB page cache per connection
            cur.execute("PRAGMA mmap_size = 134217728")  # 128 MB memory-mapped I/O
            cur.close()

    return _engine


def _run_schema():
    """Create all tables/indexes. Safe to run repeatedly."""
    import sqlite3
    with open(_SCHEMA_FILE, "r", encoding="utf-8") as f:
        sql = f.read()
    # executescript handles comments and multiple statements natively.
    con = sqlite3.connect(str(DB_PATH))
    try:
        con.executescript(sql)
        con.commit()
    finally:
        con.close()


def _is_fleet_empty() -> bool:
    with get_engine().connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM vehicles")).scalar_one()
    return count == 0


def init_db():
    """Create schema, migrate the users table if needed, and seed on first run."""
    _run_schema()
    _migrate_users()
    _migrate_rentals()
    _migrate_add_columns()
    _migrate_photos()
    if _is_fleet_empty():
        # Imported lazily to avoid a circular import at module load time.
        from data.seed.import_csv import seed_vehicles_from_csv
        seed_vehicles_from_csv(get_engine())
    # Make sure at least one super-admin exists so the app can be logged into.
    from services.auth_service import ensure_default_admin
    ensure_default_admin()
    # Hygiene/security: drop expired remember-me sessions so the table can't grow
    # unbounded and stale tokens can't linger. Cheap (indexed) and idempotent.
    from data.repositories.users import purge_expired_sessions
    purge_expired_sessions()


def _migrate_users():
    """
    Phase-1 databases had an older users table (no roles we now use). Because no
    real accounts existed yet, it is safe to rebuild it with the new schema.
    Detection: if the 'full_name' column is missing, recreate the table.
    """
    with get_engine().connect() as conn:
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(users)")).all()]
    if cols and "full_name" not in cols:
        import sqlite3
        con = sqlite3.connect(str(DB_PATH))
        try:
            con.execute("DROP TABLE IF EXISTS users")
            con.commit()
        finally:
            con.close()
        _run_schema()  # recreate with the new definition


def _migrate_rentals():
    """
    Add the 'created_by' snapshot columns (who booked the rental) to older
    databases. Uses additive ALTER TABLE so existing rentals are preserved; new
    columns default to '' for rows created before this feature.
    """
    with get_engine().connect() as conn:
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(rentals)")).all()]
    if not cols:
        return  # table doesn't exist yet (fresh DB) — schema.sql already has them
    needed = {
        "created_by": "TEXT NOT NULL DEFAULT ''",
        "created_by_name": "TEXT NOT NULL DEFAULT ''",
        "created_by_role": "TEXT NOT NULL DEFAULT ''",
    }
    missing = {c: d for c, d in needed.items() if c not in cols}
    if missing:
        with get_engine().begin() as conn:
            for col, ddl in missing.items():
                conn.execute(text(f"ALTER TABLE rentals ADD COLUMN {col} {ddl}"))


def _migrate_add_columns():
    """
    Additive column migrations for older databases (preserves all data):
      - vehicles.photo : optional base64 car photo
      - users.lang     : the user's preferred UI language
    """
    plan = {
        "vehicles": {"photo": "TEXT NOT NULL DEFAULT ''"},
        "users": {"lang": "TEXT NOT NULL DEFAULT 'tr'", "email": "TEXT NOT NULL DEFAULT ''"},
        "rentals": {"invoice_lang": "TEXT NOT NULL DEFAULT 'tr'"},
    }
    for table, cols in plan.items():
        with get_engine().connect() as conn:
            existing = [r[1] for r in conn.execute(text(f"PRAGMA table_info({table})")).all()]
        if not existing:
            continue
        missing = {c: d for c, d in cols.items() if c not in existing}
        if missing:
            with get_engine().begin() as conn:
                for col, ddl in missing.items():
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))


def _migrate_photos():
    """Move any single legacy vehicles.photo into the vehicle_photos table (once)."""
    with get_engine().connect() as conn:
        vcols = [r[1] for r in conn.execute(text("PRAGMA table_info(vehicles)")).all()]
        if "photo" not in vcols:
            return
        legacy = conn.execute(text(
            "SELECT vehicle_id, photo FROM vehicles WHERE photo IS NOT NULL AND photo != ''"
        )).mappings().all()
        already = {r[0] for r in conn.execute(
            text("SELECT DISTINCT vehicle_id FROM vehicle_photos")).all()}
    rows = [r for r in legacy if r["vehicle_id"] not in already]
    if rows:
        with get_engine().begin() as conn:
            for r in rows:
                conn.execute(text(
                    "INSERT INTO vehicle_photos (vehicle_id, photo, position) "
                    "VALUES (:v, :p, 0)"), {"v": r["vehicle_id"], "p": r["photo"]})
