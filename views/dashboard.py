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
from data.repositories import app_settings as app_cfg
import html as _html


def _available_cards(fleet: list[dict], user):
    """Grid of available vehicles, each a card with a photo (or :material/directions_car: placeholder)
    and a Rent button that opens the registration popup."""
    avail = [v for v in fleet if v["status"] == "Available"]
    st.subheader(f":material/directions_car: {t('available_now')} ({len(avail)})")
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
                st.caption(f':material/directions_car: {v["vehicle_id"]} · {v["license_plate"] or "—"}')
                st.caption(f'**{format_eur(v["base_daily_rate"])}** / {t("per_day")}')
                if may_rent and st.button(f':material/add: {t("rent_card_btn")}', key=f'rentcard_{v["vehicle_id"]}',
                                          type="primary", use_container_width=True):
                    open_rental_dialog(user, "dash", v)


def _visitor_home(user, fleet):
    """Customer-facing browse page shown to visitors (inspired by car-rental
    landing pages): a hero banner + a grid of available cars with photo, specs and
    price. Visitors can't book, so each card ends with a 'contact to book' prompt
    rather than the staff Rent action."""
    business = _html.escape(app_cfg.get_business_name())
    st.markdown(
        f'<div class="visitor-hero">'
        f'<div class="vh-brand">{business}</div>'
        f'<div class="vh-title">{_html.escape(t("visitor_hero"))}</div>'
        f'<div class="vh-sub">{_html.escape(t("visitor_hero_sub"))}</div></div>',
        unsafe_allow_html=True,
    )
    avail = [v for v in fleet if v["status"] == "Available"]
    st.subheader(f':material/directions_car: {t("available_now")} ({len(avail)})')
    if not avail:
        st.info(t("no_available_now"))
        return
    per_row = 3
    for i in range(0, len(avail), per_row):
        cols = st.columns(per_row)
        for v, c in zip(avail[i:i + per_row], cols):
            with c, st.container(border=True):
                render_vehicle_thumb(v["vehicle_id"], height=150)
                st.markdown(f'**{v["make_model"]}**' + (f' · {v["year"]}' if v.get("year") else ''))
                st.caption(f':material/pin: {v["license_plate"] or "—"} · :material/speed: {v.get("mileage", 0):,} km')
                st.markdown(
                    '<span style="font-family:var(--font-display);font-weight:700;'
                    f'font-size:1.15rem;color:var(--accent)">{format_eur(v["base_daily_rate"])}</span>'
                    f'<span style="color:var(--muted)"> /{t("per_day")}</span>',
                    unsafe_allow_html=True)
    st.divider()
    st.info(f':material/call: {t("contact_to_book")}')


def render_dashboard(user):
    fleet = vrepo.list_vehicles()

    # Visitors get a clean, customer-facing browse page — no staff KPIs, timeline,
    # booking panel or fleet table.
    if not can(user, "create_reservation"):
        _visitor_home(user, fleet)
        return

    st.title(f":material/person: {user['full_name']} — {t(ROLE_LABEL_KEY.get(user['role'],'role_visitor'))}")
    st.caption(t("dashboard_help"))

    active = rrepo.list_active_rentals_with_vehicle()

    # (Overdue / due-soon reminders now live in the top-bar notification bell.)

    # ── timeline ───────────────────────────────────────────────────────────
    st.subheader(f":material/calendar_month: {t('timeline_title')}")
    if not active:
        st.info(t("timeline_empty"))
    render_timeline(fleet, active)

    # ── KPIs ───────────────────────────────────────────────────────────────
    counts = vrepo.fleet_counts()
    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi_tile("kpi_total",     counts["total"], icon="directions_car")
    with c2: kpi_tile("kpi_available", counts["available"], accent=True, icon="check_circle")
    with c3: kpi_tile("kpi_rented",    counts["rented"], icon="vpn_key")
    with c4: kpi_tile("kpi_garage",    counts["garage"], icon="build")

    st.divider()

    # ── available-vehicle cards (with photos + Rent popup) ─────────────────
    _available_cards(fleet, user)

    st.divider()

    # ── booking panel ──────────────────────────────────────────────────────
    render_booking_panel(user, key_prefix="dash")

    st.divider()

    # ── searchable fleet table ─────────────────────────────────────────────
    st.subheader(f":material/directions_car: {t('fleet_title')}")
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
