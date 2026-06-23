"""Customers repository."""
from sqlalchemy import text
from core.db import get_engine


def get_or_create_customer(full_name: str, phone: str, id_passport: str) -> int:
    full_name = (full_name or "").strip()
    phone = (phone or "").strip()
    id_passport = (id_passport or "").strip()
    with get_engine().begin() as conn:
        existing = conn.execute(
            text("SELECT customer_id FROM customers WHERE full_name=:n AND phone=:p"),
            {"n": full_name, "p": phone}
        ).scalar()
        if existing is not None:
            return int(existing)
        result = conn.execute(
            text("INSERT INTO customers (full_name,phone,id_passport) VALUES (:n,:p,:i)"),
            {"n": full_name, "p": phone, "i": id_passport}
        )
        return int(result.lastrowid)


def update_customer(customer_id: int, full_name: str, phone: str, id_passport: str):
    with get_engine().begin() as conn:
        conn.execute(text("""
            UPDATE customers SET full_name=:n, phone=:p, id_passport=:i
            WHERE customer_id=:cid
        """), {"n": (full_name or "").strip(), "p": (phone or "").strip(),
               "i": (id_passport or "").strip(), "cid": customer_id})


def list_customers() -> list[dict]:
    # The two correlated subqueries snapshot WHO booked this customer's most
    # recent rental (name + role) for the "Registered by" column.
    sql = """SELECT c.customer_id, c.full_name, c.phone, c.id_passport,
                    COUNT(r.deal_id) AS rental_count,
                    SUM(CASE WHEN r.status = 'Active' THEN 1 ELSE 0 END) AS active_count,
                    MAX(r.start_dt) AS last_rental,
                    (SELECT r2.created_by_name FROM rentals r2
                       WHERE r2.customer_id = c.customer_id
                       ORDER BY r2.start_dt DESC, r2.deal_id DESC LIMIT 1) AS last_by_name,
                    (SELECT r2.created_by_role FROM rentals r2
                       WHERE r2.customer_id = c.customer_id
                       ORDER BY r2.start_dt DESC, r2.deal_id DESC LIMIT 1) AS last_by_role
             FROM customers c
             LEFT JOIN rentals r ON r.customer_id = c.customer_id
             GROUP BY c.customer_id
             ORDER BY c.full_name"""
    with get_engine().connect() as conn:
        return [dict(x) for x in conn.execute(text(sql)).mappings().all()]
