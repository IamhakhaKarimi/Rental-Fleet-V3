"""Throwaway validation for the invoice_lang clamp fix. Uses a temp SQLite DB so
the real fleet.db is never touched. Run from the app root; deleted after use."""
import sys
import shutil
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

# Redirect the DB to a throwaway temp file BEFORE the engine is ever built.
import core.db as db
_tmpdir = tempfile.mkdtemp(prefix="bf_ilang_")
db.DB_PATH = Path(_tmpdir) / "test_fleet.db"
db._engine = None

db.init_db()  # schema + seed vehicles + default admin — all in the temp DB

from sqlalchemy import text
from config.settings import LANGUAGES, DEFAULT_LANG
from data.repositories.rentals import create_rental

with db.get_engine().connect() as c:
    vid = c.execute(text("SELECT vehicle_id FROM vehicles LIMIT 1")).scalar_one()

start = datetime(2026, 7, 1, 10, 0, 0)
end = start + timedelta(days=2)
cases = ["tr", "en", "de", "it", "es", "sq", "xx", ""]

print(f"vehicle={vid}  LANGUAGES={list(LANGUAGES)}  DEFAULT_LANG={DEFAULT_LANG!r}\n")
print(f"{'input':>7} | {'stored':>6} | {'expected':>8} | result")
print("-" * 42)
all_ok = True
for lang in cases:
    deal = create_rental(
        vehicle_id=vid, make_model="Test Car",
        client_name=f"Cust-{lang or 'blank'}", phone="123", id_passport="X",
        start_dt=start, end_dt=end, days=2,
        daily_rate_cents=3000, deposit_cents=0, invoice_lang=lang,
    )
    with db.get_engine().connect() as c:
        stored = c.execute(
            text("SELECT invoice_lang FROM rentals WHERE deal_id=:d"), {"d": deal}
        ).scalar_one()
    expected = lang if lang in LANGUAGES else DEFAULT_LANG
    ok = stored == expected
    all_ok = all_ok and ok
    print(f"{lang!r:>7} | {stored:>6} | {expected:>8} | {'PASS' if ok else 'FAIL'}")

print("\n" + ("ALL PASS ✅" if all_ok else "SOME FAILED ❌"))

db.get_engine().dispose()
shutil.rmtree(_tmpdir, ignore_errors=True)
sys.exit(0 if all_ok else 1)
