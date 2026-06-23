"""Customers — minimalist card view; details & invoices open in pop-up dialogs.

The page shows one compact card per customer. "Open" pops a per-customer dialog
holding that customer's rental history (each history row carries per-language
print-invoice buttons), an edit form, and the reassign-registered-by control.
A page-level button pops the full customers table.

Streamlit allows only ONE dialog open at a time, so the print-invoice buttons do
not nest a dialog inside the customer dialog: they stash a one-shot request in
session_state and st.rerun() (which closes the customer dialog); the dispatch at
the top of render_customers() then re-opens it as a standalone invoice dialog.
"""
import pandas as pd
import streamlit as st
from config.i18n import t
from config.roles import can, role_level, ROLE_LABEL_KEY
from config.settings import LANGUAGES, STAFF_ONLY_LANGS
from ui.components import format_eur
from ui.invoice import render_invoice
from services import audit_service
from services import auth_service as auth
from data.repositories.customers import list_customers, update_customer
from data.repositories.rentals import list_rentals_for_customer, update_creator


def _who(name, role) -> str:
    """Format 'Full Name (Role)' for whoever booked the reservation."""
    name = (name or "").strip()
    if not name:
        return "—"
    role_label = t(ROLE_LABEL_KEY.get(role, "")) if role else ""
    return f"{name} ({role_label})" if role_label else name


def _print_langs(user) -> list[str]:
    """Invoice languages offered to this user (Albanian only for staff roles)."""
    lvl = role_level(user)
    return [c for c in LANGUAGES if c not in STAFF_ONLY_LANGS or lvl >= 1]


# ─────────────────────────────── page ──────────────────────────────────────
def render_customers(user):
    st.title(f"👥 {t('customers_title')}")
    st.caption(t("customers_help"))

    # One-shot dialog dispatch: an invoice request stashed from inside the
    # customer dialog re-opens here as its own dialog (avoids nested dialogs).
    pend = st.session_state.pop("cust_invoice", None)
    if pend:
        _invoice_dialog(*pend)

    customers = list_customers()
    if not customers:
        st.info(t("no_customers"))
        return

    q = st.text_input(t("customer_search"), placeholder=t("customer_search"), key="cust_q")
    if q:
        ql = q.lower()
        customers = [c for c in customers
                     if ql in c["full_name"].lower() or ql in (c["phone"] or "")]
        if not customers:
            st.info(t("no_customers"))
            return

    # Split: customers with a rental ACTIVE right now get the card view; everyone
    # else (finished contracts / no live rental) drops to the full table below.
    active = [c for c in customers if (c.get("active_count") or 0) > 0]
    finished = [c for c in customers if (c.get("active_count") or 0) == 0]

    # ── Active renters — compact card grid ──────────────────────────────────
    st.subheader(f'🟢 {t("active_renters")} · {len(active)}')
    if not active:
        st.caption(t("no_active_renters"))
    else:
        _customer_cards(user, active)

    st.divider()

    # ── Everyone else (finished contracts) — the full customers table ───────
    st.subheader(f'📋 {t("all_customers")} · {len(finished)}')
    if not finished:
        st.caption("—")
        return
    _customers_table(finished)
    # Keep per-customer actions (history / reprint invoice / edit) reachable for
    # finished clients without cluttering the table: pick one and open its dialog.
    labels = {c["customer_id"]: f'{c["full_name"]} · {c["phone"] or "—"}' for c in finished}
    oc = st.columns([3, 1])
    pick = oc[0].selectbox(t("open_customer"), [c["customer_id"] for c in finished],
                           format_func=lambda i: labels[i], key="fin_pick",
                           label_visibility="collapsed")
    if oc[1].button(f'📂 {t("open_customer")}', key="fin_open", use_container_width=True):
        _customer_dialog(user, next(c for c in finished if c["customer_id"] == pick))


# ─────────────────────────────── sections ──────────────────────────────────
def _customer_cards(user, customers):
    """Minimalist card grid (used for the currently-renting customers)."""
    per_row = 3
    for i in range(0, len(customers), per_row):
        cols = st.columns(per_row)
        for c, col in zip(customers[i:i + per_row], cols):
            with col, st.container(border=True):
                st.markdown(f'**{c["full_name"]}**')
                st.caption(f'📞 {c["phone"] or "—"}')
                st.caption(f'🚗 {c["rental_count"]} · '
                           f'{t("col_last_rental")}: {(c["last_rental"] or "—")[:10]}')
                st.caption(f'{t("col_registered_by")}: '
                           f'{_who(c.get("last_by_name"), c.get("last_by_role"))}')
                if st.button(f'📂 {t("card_open")}', key=f'open_{c["customer_id"]}',
                             use_container_width=True):
                    _customer_dialog(user, c)


def _customers_table(customers):
    """Full customers table (used for finished-contract customers)."""
    rows = [{
        t("col_id"):            c["customer_id"],
        t("client_name"):       c["full_name"],
        t("col_phone"):         c["phone"] or "—",
        t("col_idno"):          c["id_passport"] or "—",
        t("col_rentals"):       c["rental_count"],
        t("col_last_rental"):   (c["last_rental"] or "—")[:10],
        t("col_registered_by"): _who(c.get("last_by_name"), c.get("last_by_role")),
    } for c in customers]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ─────────────────────────────── dialogs ───────────────────────────────────


def _customer_dialog(user, cust):
    cid = cust["customer_id"]

    def body():
        st.caption(f'📞 {cust["phone"] or "—"} · 🆔 {cust["id_passport"] or "—"}')

        # edit customer details (Employee and above)
        if can(user, "create_reservation"):
            with st.expander(f'✏️ {t("edit_customer")}'):
                with st.form(f"editcust_{cid}"):
                    e1, e2 = st.columns(2)
                    cn = e1.text_input(t("client_name"), value=cust["full_name"])
                    cp = e2.text_input(t("col_phone"), value=cust["phone"] or "")
                    ci = st.text_input(t("col_idno"), value=cust["id_passport"] or "")
                    if st.form_submit_button(t("save_btn"), type="primary"):
                        if not cn.strip():
                            st.error(t("fields_required"))
                        else:
                            update_customer(cid, cn, cp, ci)
                            audit_service.record(user, "edit_customer", "customer",
                                                 cid, cn.strip())
                            st.toast(t("customer_saved"), icon="✅")
                            st.rerun()

        st.markdown(f'#### {t("customer_history")}')
        history = list_rentals_for_customer(cid)
        if not history:
            st.info(t("no_active_reservations"))
            return
        _history_table(user, history)

        # reassign "registered by" (Admin and above)
        if can(user, "manage_users"):
            _reassign(user, cust, history)

    st.dialog(f'👤 {cust["full_name"]}', width="large")(body)()


def _invoice_dialog(deal_id, lang):
    def body():
        render_invoice(deal_id, key_prefix=f"custinv_{deal_id}", lang=lang)
    st.dialog(f'🧾 {t("print_invoice")}', width="large")(body)()


# ─────────────────────────── rental-history table ──────────────────────────
def _history_table(user, history):
    """Render the rental history as rows ending in a Print-Invoice column whose
    cells are one small flag button per available language."""
    langs = _print_langs(user)
    widths = [3, 4, 4, 2, 2, max(3, len(langs))]
    head = st.columns(widths)
    for col, key in zip(head, ["col_deal", "col_car", "col_period",
                               "col_total", "col_status", "print_invoice"]):
        col.markdown(f'**{t(key)}**')
    for r in history:
        row = st.columns(widths)
        row[0].write(r["deal_id"])
        row[1].write(f'{r["vehicle_id"]} {r["make_model"]}')
        row[2].write(f'{r["start_dt"][:10]} → {r["end_dt"][:10]}')
        row[3].write(format_eur(r["total_amount"]))
        row[4].write(t(r["status"]))
        with row[5]:
            bcols = st.columns(len(langs))
            for code, bc in zip(langs, bcols):
                flag = LANGUAGES[code].split(" ", 1)[0]
                if bc.button(flag, key=f'inv_{r["deal_id"]}_{code}',
                             help=f'{t("print_invoice")} · {LANGUAGES[code]}'):
                    st.session_state.cust_invoice = (r["deal_id"], code)
                    st.rerun()


# ─────────────────────────── reassign registered-by ────────────────────────
def _reassign(user, cust, history):
    cid = cust["customer_id"]
    with st.expander(f'🔁 {t("reassign_registered_by")}'):
        # The rental is identified by the Customer Full Name (+ car/period to
        # disambiguate when a customer has several rentals) instead of the raw
        # contract/deal id.
        def _label(r):
            return (f'{cust["full_name"]} · {r["vehicle_id"]} {r["make_model"]} · '
                    f'{r["start_dt"][:10]}')
        rb = st.selectbox(t("client_name"), history, format_func=_label,
                          key=f"rb_deal_{cid}")
        staff = auth.all_users()
        rb_user = st.selectbox(
            t("col_registered_by"), staff,
            format_func=lambda u: f'{u["username"]} '
                                  f'({t(ROLE_LABEL_KEY.get(u["role"], "role_visitor"))})',
            key=f"rb_user_{cid}")
        if st.button(t("apply_btn"), type="primary", key=f"rb_apply_{cid}"):
            update_creator(rb["deal_id"], rb_user["username"],
                           rb_user["full_name"] or rb_user["username"], rb_user["role"])
            audit_service.record(user, "reassign_registered_by", "rental",
                                 rb["deal_id"], rb_user["username"])
            st.toast(t("registered_by_updated"), icon="✅")
            st.rerun()
