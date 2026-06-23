"""Reservations: timeline, booking, active-rental cards with overdue detection."""
import streamlit as st
from config.i18n import t
from config.roles import can
from config.settings import CURRENCY_SYMBOL
from ui.components import format_eur
from ui.timeline import render_timeline
from ui.booking import render_booking_panel
from services import audit_service
from services.scheduling_service import return_state
from data.repositories import vehicles as vrepo
from data.repositories import rentals as rrepo


def render_reservations(user):
    st.title(f":material/list: {t('reservations_title')}")
    st.caption(t("reservations_help"))

    fleet  = vrepo.list_vehicles()
    active = rrepo.list_active_rentals_with_vehicle()

    # (Reminders now live in the top-bar notification bell.)

    # ── active rental cards ────────────────────────────────────────────────
    st.subheader(f":material/folder_open: {t('active_reservations')} ({len(active)})")
    if not active:
        st.info(t("no_active_reservations"))

    for r in active:
        state, hrs = return_state(r["end_dt"])
        is_overdue = state == "overdue"
        is_soon = state == "due_soon"
        # Overdue = alert red; due-soon + active stay greyscale (darker = nearer due).
        border_color = "#DC2626" if is_overdue else ("#3F3F46" if is_soon else "#6B7280")

        with st.container(border=True):
            # coloured header stripe via markdown
            if is_overdue:
                badge = (f'<span style="background:#DC2626;color:#fff;padding:2px 8px;'
                         f'border-radius:6px;font-size:12px;font-weight:700">'
                         f'<span class="msym" style="font-size:13px;vertical-align:-2px">warning</span> {t("overdue_badge")} · {t("overdue_detail").format(h=hrs)}</span>')
            elif is_soon:
                badge = (f'<span style="background:#3F3F46;color:#fff;padding:2px 8px;'
                         f'border-radius:6px;font-size:12px;font-weight:700">'
                         f'<span class="msym" style="font-size:13px;vertical-align:-2px">schedule</span> {t("due_soon_badge")} · {t("due_soon_detail").format(h=hrs)}</span>')
            else:
                badge = ""
            st.markdown(
                f'<div style="border-left:4px solid {border_color};padding-left:10px">'
                f'<b>{r["deal_id"]}</b>  {badge}</div>', unsafe_allow_html=True
            )

            ca, cb, cc, cd = st.columns([2.2, 2, 2.4, 1.2])
            ca.markdown(f'**{r["client_name"]}**  \n:material/call: {r["phone"]}  \n:material/badge: {r.get("id_passport","—")}')
            cb.markdown(f':material/directions_car: **{r["vehicle_id"]}** {r["make_model"]}')

            s = r["start_dt"][:16].replace("T", " ")
            e = r["end_dt"][:16].replace("T", " ")
            cc.markdown(f'**{t("col_period")}:** {s} → {e}')
            cc.caption(
                f'{t("col_days")}: {r["rental_days"]} · '
                f'{t("col_total")}: {format_eur(r["total_amount"])} · '
                f'{t("col_deposit")}: {format_eur(r["deposit"])}'
            )

            if can(user, "cancel_reservation"):
                if cd.button(f':material/block: {t("cancel_btn")}', key=f'cnc_{r["deal_id"]}',
                             use_container_width=True):
                    rrepo.cancel_rental(r["deal_id"])
                    audit_service.record(user, "cancel_rental", "rental", r["deal_id"],
                                         r["vehicle_id"])
                    st.success(t("cancel_done"))
                    st.rerun()

                # Return / settlement workflow
                with st.expander(f':material/build: {t("manage_rental")}'):
                    with st.form(f'return_form_{r["deal_id"]}'):
                        rc1, rc2 = st.columns(2)
                        late_eur = rc1.number_input(
                            f'{t("late_fee")} ({CURRENCY_SYMBOL})', min_value=0,
                            value=0, step=5, key=f'late_{r["deal_id"]}')
                        dmg_eur = rc2.number_input(
                            f'{t("damage_charge")} ({CURRENCY_SYMBOL})', min_value=0,
                            value=0, step=10, key=f'dmg_{r["deal_id"]}')
                        notes = st.text_area(t("return_notes"), key=f'rn_{r["deal_id"]}')
                        signed = st.checkbox(t("contract_signed"), value=True,
                                             key=f'cs_{r["deal_id"]}')
                        if st.form_submit_button(f':material/check_circle: {t("return_btn")}', type="primary"):
                            rrepo.settle_and_close(
                                r["deal_id"], r["vehicle_id"],
                                int(late_eur) * 100, int(dmg_eur) * 100,
                                notes, signed)
                            audit_service.record(
                                user, "return_rental", "rental", r["deal_id"],
                                f'late={int(late_eur)}€ damage={int(dmg_eur)}€')
                            st.success(t("return_done"))
                            st.rerun()

    st.divider()

    # ── booking panel (create new rental) ──────────────────────────────────
    st.subheader(f":material/add: {t('quick_register')}")
    render_booking_panel(user, key_prefix="res")
    st.divider()

    # ── timeline ───────────────────────────────────────────────────────────
    render_timeline(fleet, active)
