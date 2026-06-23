"""
Return reminders — a notification bell with a numbered badge.

The bell sits in the top bar for staff (Employee and above). Its badge counts
rentals that are overdue (🔴 alarm) or due back within 24 h (🟠 alert). Clicking
it opens a minimalist popup listing each one with the customer's phone (copyable)
and one-tap WhatsApp message/call links so staff can chase the return.
"""

import re
import urllib.parse

import streamlit as st

from config.i18n import t
from services.scheduling_service import return_state, DUE_SOON_HOURS
from data.repositories import rentals as rrepo


def _digits(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def _wa_link(phone: str, message: str = "") -> str:
    d = _digits(phone)
    if not d:
        return ""
    url = f"https://wa.me/{d}"
    if message:
        url += "?text=" + urllib.parse.quote(message)
    return url


def _classify(active_rentals):
    overdue, soon = [], []
    for r in active_rentals:
        state, hrs = return_state(r["end_dt"])
        if state == "overdue":
            overdue.append((r, hrs))
        elif state == "due_soon":
            soon.append((r, hrs))
    overdue.sort(key=lambda x: -x[1])
    soon.sort(key=lambda x: x[1])
    return overdue, soon


def _notifications_body(active_rentals):
    overdue, soon = _classify(active_rentals)
    if not overdue and not soon:
        st.success(t("no_reminders"))
        return

    def _row(r, hrs, kind):
        icon = "🔴" if kind == "overdue" else "🟠"
        when = (t("notif_overdue_by") if kind == "overdue" else t("notif_due_in")).format(h=hrs)
        end = (r["end_dt"] or "")[:16].replace("T", " ")
        msg = t("wa_reminder").format(name=r["client_name"], car=r["make_model"], due=end)
        with st.container(border=True):
            st.markdown(f'{icon} **{r["client_name"]}** — {r["vehicle_id"]} · {r["make_model"]}')
            st.caption(f'{t("col_period")}: → {end} · {when}')
            st.caption(t("phone_copy_hint"))
            st.code(r.get("phone") or "—", language=None)   # built-in copy button
            wa = _wa_link(r.get("phone"), msg)
            if wa:
                cwa, ccall = st.columns(2)
                cwa.link_button(f'💬 {t("whatsapp_msg")}', wa, use_container_width=True)
                ccall.link_button(f'📞 {t("whatsapp_call")}', _wa_link(r.get("phone")),
                                  use_container_width=True)

    if overdue:
        st.markdown(f'#### 🔴 {t("notif_overdue_title")} ({len(overdue)})')
        for r, h in overdue:
            _row(r, h, "overdue")
    if soon:
        st.markdown(f'#### 🟠 {t("notif_due_soon_title").format(n=DUE_SOON_HOURS)} ({len(soon)})')
        for r, h in soon:
            _row(r, h, "due_soon")


def render_bell(user):
    """Top-bar notification bell + badge; opens the reminders popup on click."""
    active = rrepo.list_active_rentals_with_vehicle()
    overdue, soon = _classify(active)
    n = len(overdue) + len(soon)
    # Material line icon (matches the nav rail); append the count when there is one.
    label = f":material/notifications: {n}" if n else ":material/notifications:"
    btn_type = "primary" if overdue else "secondary"
    if st.button(label, key="notif_bell", help=t("notifications_title"),
                 type=btn_type, use_container_width=True):
        st.dialog(t("notifications_title"), width="large")(_notifications_body)(active)
