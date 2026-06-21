"""
Top navigation bar — language switcher included.

The language is chosen per-user in Settings → Language (and remembered across
logins), so the top bar no longer carries a language toggle. The sidebar is kept
collapsed to maximise the content area.

The section menu is built from native **emoji + label** Streamlit buttons (one per
visible section). This is deliberate:
  - `streamlit-option-menu` renders inside an iframe that collapses to 0px height
    on Streamlit 1.58, hiding the whole nav — native buttons can't fail that way.
  - The label is always shown (icons alone are ambiguous, and mobile has no hover
    tooltip). On a phone the columns stack vertically (see the responsive CSS in
    ui/theme.py), so each section name reads clearly on its own row.
"""
import streamlit as st
from config.i18n import t, init_lang
from config.roles import can, ROLE_LABEL_KEY
from config.settings import APP_TAGLINE, APP_VERSION
from data.repositories import app_settings as app_cfg
from ui import auth_view
from ui.notifications import render_bell

# (page key, translation key, emoji icon shown on the nav button — matches the
# emoji each page uses in its own title)
NAV_ITEMS = [
    ("dashboard",    "nav_dashboard",    "🏠"),
    ("reservations", "nav_reservations", "📋"),
    ("fleet",        "nav_fleet",        "🚘"),
    ("customers",    "nav_customers",    "👥"),
    ("finance",      "nav_finance",      "💰"),
    ("settings",     "nav_settings",     "⚙️"),
]

_STICKY = """
<style>
/* sticky top bar */
section[data-testid="stMain"] > div > div.stMainBlockContainer > div:first-child {
    position: sticky; top: 0; z-index: 999;
    background: #fff; padding-bottom: 6px;
    box-shadow: 0 4px 12px -8px rgba(15,23,42,.18);
}
/* hide sidebar toggle */
button[data-testid="baseButton-headerNoPadding"] { display:none !important; }
</style>
"""


def top_nav(user, cookie_mgr, cookies) -> str:
    st.markdown(_STICKY, unsafe_allow_html=True)

    # ── utility row ────────────────────────────────────────────────────────
    brand_col, spacer, user_col, bell_col, logout_col = st.columns([3, 1, 2.2, 0.9, 1.4])
    with brand_col:
        st.markdown(
            f'<div style="font-family:\'Space Grotesk\',sans-serif;font-weight:700;'
            f'font-size:20px;color:#0F172A;line-height:1.1;padding-top:6px">'
            f'{app_cfg.get_business_name()}'
            f'<span style="font-size:11px;font-weight:400;color:#64748B;margin-left:8px">'
            f'{APP_TAGLINE} · v{APP_VERSION}</span></div>',
            unsafe_allow_html=True,
        )
    with user_col:
        role_label = t(ROLE_LABEL_KEY.get(user["role"], "role_visitor"))
        st.caption(
            f'{t("signed_in_as")} **{user["full_name"] or user["username"]}**'
            f'&nbsp;·&nbsp;{role_label}',
            unsafe_allow_html=True,
        )
    with bell_col:
        if can(user, "create_reservation"):
            render_bell(user)
    with logout_col:
        if st.button(f'🚪 {t("logout")}', key="logout_btn", use_container_width=True):
            auth_view.logout(cookie_mgr, cookies)

    # ── section menu (compact icon buttons; name in tooltip) ───────────────
    items = [(k, lk, emoji) for k, lk, emoji in NAV_ITEMS
             if not (k == "finance" and not can(user, "view_finance"))]
    keys = [k for k, _, _ in items]

    # keep the selected page valid (e.g. Finance hidden for low roles)
    if st.session_state.get("current_page") not in keys:
        st.session_state.current_page = "dashboard"

    # Equal-width segments on desktop; these stack into full-width rows on mobile
    # (responsive CSS in ui/theme.py), so the section name is always legible.
    cols = st.columns(len(items))
    for (key, label_key, emoji), col in zip(items, cols):
        is_active = st.session_state.current_page == key
        if col.button(f"{emoji} {t(label_key)}", key=f"nav_{key}",
                      type="primary" if is_active else "secondary",
                      use_container_width=True):
            if not is_active:
                st.session_state.current_page = key
                st.rerun()

    st.divider()
    return st.session_state.current_page
