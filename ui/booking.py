"""
Booking panel + rental registration popup.

The availability search (dates -> list of free cars) stays inline. The actual
"Quick Rental Registration" form now lives in a centered **popup** (st.dialog)
opened by a primary button under the car list — and by a "Rent" button on each
available-vehicle card on the Overview page. The popup shows the start/return
dates dynamically and lets the operator pick the invoice language.

Creating a reservation is gated by the 'create_reservation' permission (Employee
role / id 'employer' and above).
"""

from datetime import datetime, time

import streamlit as st

from config.i18n import t
from config.roles import can
from config.settings import DEFAULT_PICKUP_HOUR, DEFAULT_RENTAL_DAYS, CURRENCY_SYMBOL, LANGUAGES
from ui.components import section_header, format_eur
from ui.invoice import render_invoice
from services.scheduling_service import compute_return, available_vehicles, is_vehicle_free
from services import audit_service
from services import licensing_service as lic
from data.repositories import rentals as rentals_repo

_DLG_KEYS = ("sd", "stt", "nd", "rtt", "cn", "cp", "ci", "rate", "dep", "ilang")


def _render_invoice_result(key_prefix: str):
    """After a rental is created, show its print-ready invoice until dismissed."""
    deal_id = st.session_state.get(f"{key_prefix}_last_deal")
    if not deal_id:
        return
    st.success(f'{t("register_ok")} · {deal_id}')
    with st.expander(t("show_invoice"), expanded=True):
        render_invoice(deal_id, key_prefix=key_prefix)
        if st.button(t("close_btn"), key=f"{key_prefix}_close_inv"):
            st.session_state.pop(f"{key_prefix}_last_deal", None)
            st.rerun()
    st.divider()


def _rental_form_body(user, key_prefix: str):
    """The popup contents: dynamic dates + customer + invoice language + save."""
    veh = st.session_state.get(f"{key_prefix}_dlg_vehicle")
    if not veh:
        return
    def_start, def_days = st.session_state.get(f"{key_prefix}_dlg_def") or (None, None)

    st.markdown(
        f'🚗 **{veh["vehicle_id"]} · {veh["make_model"]}** · '
        f'{veh.get("license_plate") or "—"} · {format_eur(veh["base_daily_rate"])}/{t("per_day")}'
    )

    # Personal information first — the operator already chose the date when picking
    # the car, so the date/selection fields sit BELOW as a final confirmation step.
    f1, f2 = st.columns(2)
    name = f1.text_input(t("client_name"), key=f"{key_prefix}_dlg_cn")
    phone = f2.text_input(t("client_phone"), key=f"{key_prefix}_dlg_cp")
    cidno = st.text_input(t("client_id"), key=f"{key_prefix}_dlg_ci")

    sd = st.date_input(t("start_date"), value=def_start or datetime.today().date(),
                       max_value=lic.max_date(), key=f"{key_prefix}_dlg_sd")
    d1, d2 = st.columns(2)
    stime = d1.time_input(t("start_time"), time(DEFAULT_PICKUP_HOUR, 0), key=f"{key_prefix}_dlg_stt")
    days = d2.number_input(t("days"), min_value=1, max_value=180,
                           value=int(def_days or DEFAULT_RENTAL_DAYS), step=1, key=f"{key_prefix}_dlg_nd")
    rtime = st.time_input(t("return_time"), stime, key=f"{key_prefix}_dlg_rtt")

    req_start = datetime.combine(sd, stime)
    req_end = compute_return(sd, stime, days, rtime)
    st.markdown(
        f'<div class="return-box"><div class="lbl">{t("calculated_return")}</div>'
        f'<div class="val">{req_start.strftime("%d.%m.%Y %H:%M")} &rarr; '
        f'{req_end.strftime("%d.%m.%Y %H:%M")}</div></div>',
        unsafe_allow_html=True,
    )

    r1, r2 = st.columns(2)
    default_rate = int(round(veh["base_daily_rate"] / 100))
    rate = r1.number_input(f'{t("negotiated_rate")} ({CURRENCY_SYMBOL})', min_value=0,
                           value=default_rate, step=5, key=f"{key_prefix}_dlg_rate")
    deposit = r2.number_input(f'{t("deposit")} ({CURRENCY_SYMBOL})', min_value=0, value=0,
                              step=10, key=f"{key_prefix}_dlg_dep")
    inv_lang = st.selectbox(t("invoice_language"), list(LANGUAGES),
                            format_func=lambda l: LANGUAGES[l],
                            key=f"{key_prefix}_dlg_ilang")

    rate_cents = int(rate) * 100
    total_cents = rate_cents * int(days)
    st.metric(t("live_total"), format_eur(total_cents),
              delta=f'{int(days)} × {format_eur(rate_cents)}', delta_color="off")

    if st.button(t("register_btn"), type="primary", use_container_width=True,
                 key=f"{key_prefix}_dlg_save"):
        if not name.strip() or not phone.strip():
            st.warning(t("register_need_fields"))
        elif not is_vehicle_free(veh["vehicle_id"], req_start, req_end):
            st.error(t("not_available_window"))
        else:
            deal_id = rentals_repo.create_rental(
                vehicle_id=veh["vehicle_id"], make_model=veh["make_model"],
                client_name=name, phone=phone, id_passport=cidno,
                start_dt=req_start, end_dt=req_end, days=int(days),
                daily_rate_cents=rate_cents, deposit_cents=int(deposit) * 100,
                created_by=user.get("username", ""),
                created_by_name=user.get("full_name") or user.get("username", ""),
                created_by_role=user.get("role", ""),
                invoice_lang=inv_lang,
            )
            audit_service.record(user, "create_rental", "rental", deal_id,
                                 f'{veh["vehicle_id"]} · {name.strip()}')
            st.session_state[f"{key_prefix}_last_deal"] = deal_id
            st.session_state.pop(f"{key_prefix}_dlg_vehicle", None)
            st.rerun()


def open_rental_dialog(user, key_prefix: str, vehicle: dict,
                       default_start=None, default_days=None):
    """Open the rental popup for `vehicle`. Call this from a button's if-block."""
    st.session_state[f"{key_prefix}_dlg_vehicle"] = vehicle
    st.session_state[f"{key_prefix}_dlg_def"] = (default_start, default_days)
    # clear any prior popup field state so it opens fresh
    for suf in _DLG_KEYS:
        st.session_state.pop(f"{key_prefix}_dlg_{suf}", None)
    # dynamic title via the dialog decorator applied at call time
    st.dialog(t("quick_register"), width="large")(_rental_form_body)(user, key_prefix)


def render_booking_panel(user, key_prefix: str = "bk"):
    _render_invoice_result(key_prefix)
    left, right = st.columns([1, 1.4], gap="large")

    with left:
        section_header("availability_title", "availability_help")
        start_date = st.date_input(t("start_date"), datetime.today().date(),
                                   max_value=lic.max_date(), key=f"{key_prefix}_sd")
        c1, c2 = st.columns(2)
        start_time = c1.time_input(t("start_time"), time(DEFAULT_PICKUP_HOUR, 0), key=f"{key_prefix}_st")
        num_days = c2.number_input(t("days"), min_value=1, max_value=180,
                                   value=DEFAULT_RENTAL_DAYS, step=1, key=f"{key_prefix}_nd")
        return_time = st.time_input(t("return_time"), start_time, key=f"{key_prefix}_rt")

        req_start = datetime.combine(start_date, start_time)
        req_end = compute_return(start_date, start_time, num_days, return_time)
        st.markdown(
            f'<div class="return-box"><div class="lbl">{t("calculated_return")}</div>'
            f'<div class="val">{req_end.strftime("%d.%m.%Y")} · {req_end.strftime("%H:%M")}</div></div>',
            unsafe_allow_html=True,
        )

    with right:
        section_header("available_cars", "")
        cars = available_vehicles(req_start, req_end)
        if not cars:
            st.info(t("no_cars"))
            return

        def _label(c):
            return f'{c["vehicle_id"]} · {c["make_model"]} · {format_eur(c["base_daily_rate"])} · {c["license_plate"] or "—"}'

        picked = st.selectbox(t("select_car"), options=cars, format_func=_label, key=f"{key_prefix}_car")

        if not can(user, "create_reservation"):
            st.info(t("no_create_perm"))
            return

        if st.button(f'➕ {t("open_rental_btn")}', type="primary",
                     use_container_width=True, key=f"{key_prefix}_open"):
            open_rental_dialog(user, key_prefix, picked,
                               default_start=start_date, default_days=num_days)
