"""
Balkan Car Rentals — Fleet Console v2.0
Entrypoint: bootstrap DB, auth gate, top nav, route to page.

NOTE: the per-section render modules live in ``views/`` — deliberately NOT
``pages/``. Streamlit treats a directory literally named ``pages`` next to the
entrypoint as a *native multipage app* and auto-builds a sidebar that runs each
file as its own standalone script. Those files only define ``render_<name>(user)``
(no module-level UI), so they render blank. This app navigates via the custom
horizontal top bar (``ui/nav.py``) + the router below, so we keep the section
modules out of the reserved ``pages/`` name to suppress that native menu.
"""
import time

import streamlit as st
import extra_streamlit_components as stx

from config.settings import APP_NAME, APP_TAGLINE, PAGE_ICON, APP_VERSION
from config.i18n import init_lang, t
from ui.theme import inject_theme
from core.db import init_db
from ui import auth_view
from ui.nav import top_nav
from views.dashboard    import render_dashboard
from views.reservations import render_reservations
from views.fleet        import render_fleet
from views.customers    import render_customers
from views.finance      import render_finance
from views.settings     import render_settings

st.set_page_config(
    page_title=f"{APP_NAME} · {APP_TAGLINE} v{APP_VERSION}",
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_resource
def _bootstrap():
    init_db()
    return True


_bootstrap()
init_lang()
inject_theme()

# Cookie manager — must be created once per run, before any st.rerun()
cookie_mgr = stx.CookieManager(key="bcr_cm")
cookies = cookie_mgr.get_all() or {}

# Priming reruns: the cookie component only delivers cookies on a later browser
# round-trip. On a fresh load / refresh, give it a few quick reruns to surface the
# remember-me cookie before falling through to the login form — without this, a
# browser refresh signs the user out. Bounded so a genuinely logged-out visitor
# still reaches the login form quickly. The counter resets on every page reload
# (fresh session_state), so it never gets "stuck".
if "user" not in st.session_state:
    _tries = st.session_state.get("_cookie_tries", 0)
    if not cookies and _tries < 4:
        st.session_state._cookie_tries = _tries + 1
        time.sleep(0.15)
        st.rerun()

# Auth gate
user = auth_view.ensure_authenticated(cookie_mgr, cookies)

# Top nav (returns the selected page key)
page = top_nav(user, cookie_mgr, cookies)

# Router
{
    "dashboard":    render_dashboard,
    "reservations": render_reservations,
    "fleet":        render_fleet,
    "customers":    render_customers,
    "finance":      render_finance,
    "settings":     render_settings,
}.get(page, render_dashboard)(user)
