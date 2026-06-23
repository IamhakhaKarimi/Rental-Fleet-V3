"""Rentals repository — create, list, cancel, and overdue detection."""
from datetime import datetime
from sqlalchemy import text
from config.settings import LANGUAGES, DEFAULT_LANG
from core.db import get_engine
from data.repositories.customers import get_or_create_customer


def next_deal_id() -> str:
    prefix = f"RENT-{datetime.now().strftime('%Y%m')}-"
    with get_engine().connect() as conn:
        rows = conn.execute(
            text("SELECT deal_id FROM rentals WHERE deal_id LIKE :p"), {"p": prefix + "%"}
        ).scalars().all()
    max_n = max((int(d.rsplit("-", 1)[-1]) for d in rows if d.rsplit("-", 1)[-1].isdigit()), default=0)
    return f"{prefix}{max_n + 1:03d}"


def list_active_rentals_with_vehicle() -> list[dict]:
    sql = """SELECT r.deal_id, r.vehicle_id, r.start_dt, r.end_dt, r.status,
                    r.rental_days, r.daily_rate, r.total_amount, r.deposit,
                    v.make_model, c.full_name AS client_name, c.phone, c.id_passport
             FROM rentals r
             JOIN vehicles  v ON v.vehicle_id  = r.vehicle_id
             JOIN customers c ON c.customer_id = r.customer_id
             WHERE r.status = 'Active'
             ORDER BY r.end_dt"""
    with get_engine().connect() as conn:
        return [dict(x) for x in conn.execute(text(sql)).mappings().all()]


def list_all_rentals() -> list[dict]:
    sql = """SELECT r.deal_id, r.vehicle_id, r.start_dt, r.end_dt, r.status,
                    r.rental_days, r.daily_rate, r.total_amount, r.deposit,
                    v.make_model, c.full_name AS client_name, c.phone
             FROM rentals r
             JOIN vehicles  v ON v.vehicle_id  = r.vehicle_id
             JOIN customers c ON c.customer_id = r.customer_id
             ORDER BY r.start_dt DESC"""
    with get_engine().connect() as conn:
        return [dict(x) for x in conn.execute(text(sql)).mappings().all()]


def get_rental_full(deal_id: str) -> dict | None:
    """Everything needed to print an invoice for one rental."""
    sql = """SELECT r.deal_id, r.vehicle_id, r.start_dt, r.end_dt, r.status,
                    r.rental_days, r.daily_rate, r.total_amount, r.deposit,
                    r.contract_signed, r.return_notes, r.created_at,
                    r.created_by, r.created_by_name, r.created_by_role, r.invoice_lang,
                    v.make_model, v.license_plate, v.color, v.year,
                    c.full_name AS client_name, c.phone, c.id_passport
             FROM rentals r
             JOIN vehicles  v ON v.vehicle_id  = r.vehicle_id
             JOIN customers c ON c.customer_id = r.customer_id
             WHERE r.deal_id = :d"""
    with get_engine().connect() as conn:
        row = conn.execute(text(sql), {"d": deal_id}).mappings().first()
    return dict(row) if row else None


def list_charges_for_deal(deal_id: str) -> list[dict]:
    sql = """SELECT type, amount, occurred_at FROM charges
             WHERE deal_id = :d ORDER BY occurred_at, charge_id"""
    with get_engine().connect() as conn:
        return [dict(r) for r in conn.execute(text(sql), {"d": deal_id}).mappings().all()]


def list_rentals_for_customer(customer_id: int) -> list[dict]:
    sql = """SELECT r.deal_id, r.vehicle_id, r.start_dt, r.end_dt,
                    r.rental_days, r.daily_rate, r.total_amount, r.status,
                    r.created_by_name, r.created_by_role,
                    v.make_model
             FROM rentals r JOIN vehicles v ON v.vehicle_id=r.vehicle_id
             WHERE r.customer_id=:cid ORDER BY r.start_dt DESC"""
    with get_engine().connect() as conn:
        return [dict(x) for x in conn.execute(text(sql), {"cid": customer_id}).mappings().all()]


def vehicle_has_active_rental(vehicle_id: str) -> bool:
    """True if the vehicle currently has an Active rental (reserved / out)."""
    with get_engine().connect() as conn:
        row = conn.execute(text(
            "SELECT 1 FROM rentals WHERE vehicle_id=:v AND status='Active' LIMIT 1"
        ), {"v": vehicle_id}).first()
    return row is not None


def create_rental(*, vehicle_id, make_model, client_name, phone, id_passport,
                  start_dt, end_dt, days, daily_rate_cents, deposit_cents,
                  created_by="", created_by_name="", created_by_role="",
                  invoice_lang="tr") -> str:
    customer_id = get_or_create_customer(client_name, phone, id_passport)
    deal_id = next_deal_id()
    total = daily_rate_cents * int(days)
    with get_engine().begin() as conn:
        conn.execute(text("""
            INSERT INTO rentals
              (deal_id,customer_id,vehicle_id,start_dt,end_dt,rental_days,
               daily_rate,total_amount,deposit,status,contract_signed,
               created_by,created_by_name,created_by_role,invoice_lang)
            VALUES
              (:did,:cid,:vid,:s,:e,:d,:rate,:total,:dep,'Active','No',
               :cby,:cbn,:cbr,:ilang)
        """), {"did": deal_id, "cid": customer_id, "vid": vehicle_id,
               "s": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
               "e": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
               "d": int(days), "rate": daily_rate_cents, "total": total, "dep": deposit_cents,
               "cby": created_by or "", "cbn": created_by_name or "", "cbr": created_by_role or "",
               "ilang": invoice_lang if invoice_lang in LANGUAGES else DEFAULT_LANG})
        conn.execute(text(
            "INSERT INTO charges (deal_id,vehicle_id,type,amount) VALUES (:did,:vid,'rental',:a)"
        ), {"did": deal_id, "vid": vehicle_id, "a": total})
        if deposit_cents > 0:
            conn.execute(text(
                "INSERT INTO charges (deal_id,vehicle_id,type,amount) VALUES (:did,:vid,'deposit',:a)"
            ), {"did": deal_id, "vid": vehicle_id, "a": deposit_cents})
        conn.execute(text(
            "UPDATE vehicles SET status='Rented',updated_at=datetime('now') WHERE vehicle_id=:v"
        ), {"v": vehicle_id})
    return deal_id


def update_creator(deal_id: str, username: str, full_name: str, role: str):
    """Reassign which staff member a rental is recorded as 'registered by'."""
    with get_engine().begin() as conn:
        conn.execute(text("""
            UPDATE rentals SET created_by=:u, created_by_name=:n, created_by_role=:r
            WHERE deal_id=:d
        """), {"u": username or "", "n": full_name or "", "r": role or "", "d": deal_id})


def cancel_rental(deal_id: str):
    with get_engine().begin() as conn:
        vid = conn.execute(text("SELECT vehicle_id FROM rentals WHERE deal_id=:d"),
                           {"d": deal_id}).scalar()
        conn.execute(text("UPDATE rentals SET status='Closed' WHERE deal_id=:d"), {"d": deal_id})
        if vid:
            conn.execute(text(
                "UPDATE vehicles SET status='Available',updated_at=datetime('now') WHERE vehicle_id=:v"
            ), {"v": vid})


def reactivate_rental(deal_id: str) -> bool:
    """Undo a cancellation: set the rental back to 'Active' and re-reserve its
    vehicle. Returns False (no-op) if the rental is missing or its car is already
    held by a different active rental."""
    with get_engine().begin() as conn:
        row = conn.execute(text(
            "SELECT vehicle_id, status FROM rentals WHERE deal_id=:d"), {"d": deal_id}
        ).mappings().first()
        if not row:
            return False
        vid = row["vehicle_id"]
        clash = conn.execute(text(
            "SELECT 1 FROM rentals WHERE vehicle_id=:v AND status='Active' "
            "AND deal_id<>:d LIMIT 1"), {"v": vid, "d": deal_id}).first()
        if clash:
            return False
        conn.execute(text("UPDATE rentals SET status='Active' WHERE deal_id=:d"), {"d": deal_id})
        conn.execute(text(
            "UPDATE vehicles SET status='Rented', updated_at=datetime('now') WHERE vehicle_id=:v"
        ), {"v": vid})
    return True


def settle_and_close(deal_id: str, vehicle_id: str, late_cents: int,
                     damage_cents: int, return_notes: str, contract_signed: bool):
    """Return a vehicle: record any overdue/damage charges, close the rental, and
    free the car — all atomically. Charges feed the Finance ledger; damage also
    accrues on the vehicle's maintenance_charge."""
    with get_engine().begin() as conn:
        if late_cents > 0:
            conn.execute(text(
                "INSERT INTO charges (deal_id,vehicle_id,type,amount) "
                "VALUES (:d,:v,'overdue_penalty',:a)"
            ), {"d": deal_id, "v": vehicle_id, "a": int(late_cents)})
        if damage_cents > 0:
            conn.execute(text(
                "INSERT INTO charges (deal_id,vehicle_id,type,amount) "
                "VALUES (:d,:v,'damage',:a)"
            ), {"d": deal_id, "v": vehicle_id, "a": int(damage_cents)})
            conn.execute(text(
                "UPDATE vehicles SET maintenance_charge = maintenance_charge + :a "
                "WHERE vehicle_id=:v"
            ), {"a": int(damage_cents), "v": vehicle_id})
        conn.execute(text(
            "UPDATE rentals SET status='Closed', return_notes=:n, contract_signed=:c "
            "WHERE deal_id=:d"
        ), {"n": return_notes or "", "c": "Yes" if contract_signed else "No", "d": deal_id})
        conn.execute(text(
            "UPDATE vehicles SET status='Available', updated_at=datetime('now') "
            "WHERE vehicle_id=:v"
        ), {"v": vehicle_id})
