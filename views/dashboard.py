"""Dashboard: timeline + KPIs + available-vehicle cards + booking + fleet table."""
import pandas as pd
import streamlit as st
from config.i18n import t
from config.roles import can, ROLE_LABEL_KEY
from ui.components import format_eur, kpi_tile
from ui.timeline import render_timeline
from ui.booking import render_booking_panel, open_rental_dialog
from ui.photos import render_vehicle_thumb
from data.repositories import vehicles as vrepo
from data.repositories import rentals as rrepo


def _available_cards(fleet: list[dict], user):
    """Grid of available vehicles, each a card with a photo (or 🚘 placeholder)
    and a Rent button that opens the registration popup."""
    avail = [v for v in fleet if v["status"] == "Available"]
    st.subheader(f"🚗 {t('available_now')} ({len(avail)})")
    if not avail:
        st.info(t("no_available_now"))
        return
    may_rent = can(user, "create_reservation")
    per_row = 3
    for i in range(0, len(avail), per_row):
        cols = st.columns(per_row)
        for v, c in zip(avail[i:i + per_row], cols):
            with c, st.container(border=True):
                render_vehicle_thumb(v["vehicle_id"], height=140)
                st.markdown(f'**{v["make_model"]}**' + (f' · {v["year"]}' if v.get("year") else ''))
                st.caption(f'🚗 {v["vehicle_id"]} · {v["license_plate"] or "—"}')
                st.caption(f'**{format_eur(v["base_daily_rate"])}** / {t("per_day")}')
                if may_rent and st.button(f'➕ {t("rent_card_btn")}', key=f'rentcard_{v["vehicle_id"]}',
                                          type="primary", use_container_width=True):
                    open_rental_dialog(user, "dash", v)


def render_dashboard(user):
    st.title(f"👤 {user['full_name']} — {t(ROLE_LABEL_KEY.get(user['role'],'role_visitor'))}")
    st.caption(t("dashboard_help"))

    fleet  = vrepo.list_vehicles()
    active = rrepo.list_active_rentals_with_vehicle()

    # (Overdue / due-soon reminders now live in the top-bar notification bell.)

    # ── timeline ───────────────────────────────────────────────────────────
    st.subheader(f"📅 {t('timeline_title')}")
    if not active:
        st.info(t("timeline_empty"))
    render_timeline(fleet, active)

    # ── KPIs ───────────────────────────────────────────────────────────────
    counts = vrepo.fleet_counts()
    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi_tile("kpi_total",     counts["total"])
    with c2: kpi_tile("kpi_available", counts["available"], accent=True)
    with c3: kpi_tile("kpi_rented",    counts["rented"])
    with c4: kpi_tile("kpi_garage",    counts["garage"])

    st.divider()

    # ── available-vehicle cards (with photos + Rent popup) ─────────────────
    _available_cards(fleet, user)

    st.divider()

    # ── booking panel ──────────────────────────────────────────────────────
    render_booking_panel(user, key_prefix="dash")

    st.divider()

    # ── searchable fleet table ─────────────────────────────────────────────
    st.subheader(f"🚗 {t('fleet_title')}")
    q = st.text_input(t("search"), key="dash_search", placeholder=t("search"))
    rows = [{
        t("col_id"):     v["vehicle_id"],
        t("col_model"):  v["make_model"],
        t("col_year"):   v["year"],
        t("col_plate"):  v["license_plate"] or "—",
        t("col_color"):  v["color"] or "—",
        t("col_status"): t(v["status"]),
        t("col_rate"):   format_eur(v["base_daily_rate"]),
    } for v in fleet]
    df = pd.DataFrame(rows)
    if q:
        qlo = q.lower()
        df = df[df.apply(lambda r: qlo in " ".join(str(x).lower() for x in r), axis=1)]
    st.caption(f"{len(df)} {t('col_count')}")
    st.dataframe(df, use_container_width=True, hide_index=True)
