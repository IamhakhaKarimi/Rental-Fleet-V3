"""
Login gate and session restore.

Flow:
  - On each run we read the browser cookie. If it holds a valid (unexpired)
    session token, the user is restored automatically — this is what makes a
    page refresh keep you signed in, and what makes "remember me" work.
  - If there is no valid session, the login form is shown and the rest of the
    app is blocked with st.stop().

The CookieManager is created once in app.py and passed in here, because creating
it more than once per run causes duplicate-component errors.
"""

import time

import streamlit as st

from config.i18n import t, DEFAULT_LANG
from config.settings import APP_NAME, APP_TAGLINE
from services import auth_service as auth
from data.repositories import app_settings as app_settings_repo

COOKIE_NAME = "bcr_session"


def _apply_user_lang(u: dict):
    """Adopt the signed-in user's saved language for this session."""
    st.session_state.lang = u.get("lang") or DEFAULT_LANG


def ensure_authenticated(cookie_mgr, cookies: dict) -> dict:
    """Return the logged-in user, or render the login form and stop."""
    user = st.session_state.get("user")
    if user:
        return user

    token = (cookies or {}).get(COOKIE_NAME)
    if token:
        restored = auth.validate_session(token)
        if restored:
            st.session_state.user = restored
            _apply_user_lang(restored)
            return restored

    _render_login(cookie_mgr)
    st.stop()


def _render_login(cookie_mgr):
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.1, 1])
    with mid:
        with st.container(border=True):
            st.markdown(
                f'<div class="bcr-brand" style="text-align:center;">{app_settings_repo.get_business_name()}'
                f'<small>{APP_TAGLINE}</small></div>',
                unsafe_allow_html=True,
            )
            st.markdown(f"#### 🔒 {t('login_title')}")
            with st.form("login_form", clear_on_submit=False):
                username = st.text_input(t("login_username"))
                password = st.text_input(t("login_password"), type="password")
                remember = st.checkbox(t("login_remember"))
                submitted = st.form_submit_button(t("login_btn"), type="primary", use_container_width=True)

            if submitted:
                u = auth.authenticate(username, password)
                if not u:
                    st.error(t("login_failed"))
                else:
                    token, expires_at = auth.create_session(u["username"], remember)
                    st.session_state.user = u
                    _apply_user_lang(u)
                    st.session_state.pop("_cookie_tries", None)
                    cookie_mgr.set(COOKIE_NAME, token, expires_at=expires_at, key="set_login_cookie")
                    # Let the cookie component flush the write to the browser before
                    # the rerun aborts the script — otherwise the cookie is never
                    # stored and a refresh logs the user straight back out.
                    time.sleep(0.4)
                    st.rerun()

            st.caption(t("default_admin_warning"))

            # Self-service recovery for Admin / Super-Admin (others: ask an admin)
            with st.expander(f'🔑 {t("forgot_password")}'):
                st.caption(t("recover_help"))
                ru = st.text_input(t("login_username"), key="recover_user")
                if st.button(t("recover_btn"), key="recover_go", type="primary"):
                    ok, msg, info = auth.self_recover(ru)
                    if ok and info.get("sent"):
                        st.success(t("recover_sent").format(to=info["recipient"]))
                    elif ok:
                        st.warning(t("recover_fallback").format(
                            pw=info["new_password"], to=info["recipient"]))
                    else:
                        st.error(t(msg))


def logout(cookie_mgr, cookies: dict):
    token = (cookies or {}).get(COOKIE_NAME)
    auth.destroy_session(token)   # invalidate server-side first (defence in depth)
    try:
        cookie_mgr.delete(COOKIE_NAME, key="del_login_cookie")
    except Exception:
        pass
    for k in ("user", "_primed", "_cookie_tries", "current_page"):
        st.session_state.pop(k, None)
    time.sleep(0.3)   # let the cookie deletion reach the browser
    st.rerun()
