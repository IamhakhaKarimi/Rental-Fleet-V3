"""Settings: Business, Users, License, Profile/Password, Activity — gated by role."""
from datetime import date

import pandas as pd
import streamlit as st

from config.i18n import t
from config.roles import can, assignable_roles, ROLE_LABEL_KEY, ROLE_LEVEL
from config.settings import CURRENCY_SYMBOL, LANGUAGES, STAFF_ONLY_LANGS
from services import auth_service as auth
from services import audit_service
from services import licensing_service as lic
from services import email_service
from data.repositories import app_settings as cfg
from data.repositories import licenses as lrepo
from data.repositories import vehicles as vrepo
from data.repositories import rentals as rrepo
from data.repositories import admin_ops
from ui import photos
from ui.components import format_eur
from ui.license_invoice import render_license_invoice


def render_settings(user):
    st.title(f"⚙️ {t('settings_title')}")
    st.caption(t("settings_help"))

    specs = []
    if can(user, "manage_users"):                    # admin+ (logo); name is super-admin-only inside
        specs.append(("business", f"🏢 {t('tab_business')}"))
    if can(user, "manage_users"):
        specs.append(("users", f"👥 {t('tab_users')}"))
    if can(user, "edit_business_settings"):          # super-admin only
        specs.append(("license", f"🔑 {t('tab_license')}"))
    specs.append(("language", f"🌐 {t('tab_language')}"))
    specs.append(("password", f"👤 {t('tab_profile')}"))
    if can(user, "manage_users"):
        specs.append(("activity", f"🕑 {t('tab_activity')}"))

    tabs = st.tabs([label for _, label in specs])
    for (kind, _), tab in zip(specs, tabs):
        with tab:
            {"business": _business_tab, "users": _users_tab, "license": _license_tab,
             "language": _language_tab, "password": _password_tab,
             "activity": _activity_tab}[kind](user)


# ━━━━━━━━━━━━━━ Language (everyone)
def _language_tab(user):
    st.subheader(f"🌐 {t('tab_language')}")
    st.caption(t("language_help"))
    # Albanian (and any other STAFF_ONLY_LANGS) is offered only to staff roles
    # (employer/admin/super_admin → level >= 1); visitors see the public set.
    lvl = ROLE_LEVEL.get(user.get("role"), 0)
    opts = [c for c in LANGUAGES if c not in STAFF_ONLY_LANGS or lvl >= 1]
    cur = st.session_state.get("lang", "tr")
    choice = st.radio(t("language"), opts, index=opts.index(cur) if cur in opts else 0,
                      format_func=lambda l: LANGUAGES[l],
                      horizontal=True, key="lang_choice")
    if st.button(t("save_btn"), type="primary", key="lang_save"):
        auth.set_user_lang(user["username"], choice)
        st.session_state.lang = choice
        if isinstance(st.session_state.get("user"), dict):
            st.session_state.user["lang"] = choice
        audit_service.record(user, "set_lang", "user", user["username"], choice)
        st.success(t("lang_saved"))
        st.rerun()


# ━━━━━━━━━━━━━━ Business (admin+ for logo; name super-admin only)
def _business_tab(user):
    st.subheader(f"🏢 {t('business_settings')}")
    if can(user, "edit_business_settings"):
        with st.form("business_form"):
            bname = st.text_input(t("business_name"), value=cfg.get_business_name(),
                                  help=t("business_name_help"))
            if st.form_submit_button(t("save_btn"), type="primary"):
                cfg.set_business_name(bname)
                audit_service.record(user, "set_business_name", "settings", "business_name", bname)
                st.success(t("business_saved"))
                st.rerun()
        st.divider()

    st.subheader(f"🖼️ {t('company_logo')}")
    st.caption(t("logo_help"))
    cur_logo = cfg.get_logo()
    if cur_logo:
        st.markdown(
            f'<img src="data:image/png;base64,{cur_logo}" '
            'style="max-height:120px;max-width:100%;" />',
            unsafe_allow_html=True,
        )
    with st.form("logo_form"):
        up = st.file_uploader(t("upload_logo"), type=photos.PHOTO_TYPES, key="logo_upload")
        if st.form_submit_button(t("save_btn"), type="primary"):
            if up is not None:
                cfg.set_logo(photos.encode_logo(up))
                audit_service.record(user, "set_logo", "settings", "logo")
                st.success(t("logo_saved"))
                st.rerun()
    if cur_logo and st.button(t("remove_logo"), key="logo_remove"):
        cfg.clear_logo()
        audit_service.record(user, "clear_logo", "settings", "logo")
        st.success(t("logo_removed"))
        st.rerun()


# ━━━━━━━━━━━━━━ Users (admin+)
def _users_tab(user):
    st.subheader(f"➕ {t('create_user')}")
    roles_allowed = assignable_roles(user)
    with st.form("create_user_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        new_user = c1.text_input(t("login_username") + " *")
        new_full = c2.text_input(t("full_name"))
        c3, c4 = st.columns(2)
        new_pw = c3.text_input(t("new_password") + " *", type="password")
        new_role = c4.selectbox(t("role"), roles_allowed, format_func=lambda r: t(ROLE_LABEL_KEY[r]))
        new_email = st.text_input(t("email_label"))
        if st.form_submit_button(t("add_user_btn"), type="primary", use_container_width=True):
            ok, msg = auth.create_user(user, new_user, new_pw, new_full, new_role, new_email)
            if ok:
                audit_service.record(user, "create_user", "user", new_user.strip(), new_role)
                st.success(t("user_created"))
                st.rerun()
            else:
                st.error(t(msg))

    st.divider()
    st.subheader(f"📋 {t('users_list')}")
    for u in auth.all_users():
        uname, urole = u["username"], u["role"]
        is_me = uname == user["username"]
        locked = auth.is_last_active_super_admin(uname)
        with st.container(border=True):
            ua, ub, uc, ud = st.columns([2, 1.8, 1.4, 1.4])
            ua.markdown(f'**{uname}**  \n{u["full_name"] or "—"}  \n✉️ {u.get("email") or "—"}')
            ub.caption(t(ROLE_LABEL_KEY.get(urole, "role_visitor")))
            ub.caption("✅ " + t("active") if u["is_active"] else "🔴 " + t("deactivate"))

            if not is_me and urole in assignable_roles(user):
                new_r = uc.selectbox(t("role"), options=assignable_roles(user),
                                     index=assignable_roles(user).index(urole),
                                     format_func=lambda r: t(ROLE_LABEL_KEY[r]),
                                     key=f"role_{uname}", label_visibility="collapsed",
                                     disabled=locked)
                if uc.button(t("change_role"), key=f"ch_role_{uname}",
                             use_container_width=True, disabled=locked):
                    ok, msg = auth.set_user_role(user, uname, new_r)
                    st.success(t("role_updated")) if ok else st.error(t(msg))
                    st.rerun()
            else:
                uc.write("")

            if not is_me:
                lbl = t("deactivate") if u["is_active"] else t("activate")
                if ud.button(lbl, key=f"tog_{uname}", use_container_width=True, disabled=locked):
                    auth.set_user_active(uname, not u["is_active"])
                    audit_service.record(user, "set_active", "user", uname, str(not u["is_active"]))
                    st.rerun()

            if locked:
                st.caption(t("last_super_admin"))

            # manage account: rename / email / reset password (child users only)
            if not is_me and urole in assignable_roles(user):
                with st.expander(f'🔧 {t("manage_account")}'):
                    with st.form(f"rename_{uname}", clear_on_submit=True):
                        new_name = st.text_input(t("change_username"), value=uname, key=f"newname_{uname}")
                        if st.form_submit_button(t("change_username")):
                            ok, msg = auth.change_username(user, uname, new_name)
                            if ok:
                                audit_service.record(user, "change_username", "user", uname, f'-> {new_name.strip()}')
                                st.success(t("username_changed"))
                                st.rerun()
                            else:
                                st.error(t(msg))
                    with st.form(f"email_{uname}"):
                        new_em = st.text_input(t("email_label"), value=u.get("email") or "", key=f"em_{uname}")
                        if st.form_submit_button(t("save_btn")):
                            auth.set_user_email(uname, new_em)
                            audit_service.record(user, "set_email", "user", uname)
                            st.success(t("email_saved"))
                            st.rerun()
                    st.caption(t("reset_password_help"))
                    if st.button(t("reset_password"), key=f"reset_{uname}", type="primary"):
                        ok, msg, info = auth.admin_recover_child(user, uname)
                        if ok:
                            audit_service.record(user, "reset_password", "user", uname)
                            if info["sent"]:
                                st.success(t("recover_sent").format(to=info["recipient"]))
                            else:
                                st.warning(t("recover_fallback").format(
                                    pw=info["new_password"], to=info["recipient"]))
                        else:
                            st.error(t(msg))


# ━━━━━━━━━━━━━━ License (super-admin) — annual unlock + license invoice + SMTP
def _license_tab(user):
    st.subheader(f"🔑 {t('tab_license')}")
    st.caption(t("license_help"))
    ly = lic.licensed_year()
    st.info(t("license_status").format(y=ly))
    # Super-admin designates the licensed-until year from a dropdown (current year
    # through +10) instead of a one-step button — picking a specific year avoids
    # accidental over/under-extension. Date pickers across the app cap at Dec 31 of
    # this year (services/licensing_service.max_date).
    cy = lic.current_year()
    year_opts = list(range(cy, cy + 11))
    default_idx = year_opts.index(ly) if ly in year_opts else 0
    yc1, yc2 = st.columns([2, 1])
    sel_year = yc1.selectbox(t("set_licensed_year_label"), year_opts,
                             index=default_idx, key="lock_year_sel")
    if yc2.button(t("save_btn"), type="primary", key="lock_year_btn"):
        lic.set_licensed_year(int(sel_year))
        audit_service.record(user, "set_licensed_year", "license", str(sel_year))
        st.success(t("licensed_year_saved"))
        st.rerun()

    st.divider()
    # ── License records (CRUD)
    st.subheader(f"📋 {t('license_records')}")
    recs = lrepo.list_licenses()
    if not recs:
        st.info(t("no_licenses"))
    else:
        h = st.columns([1, 1.4, 2, 1.4, 1.6, 2, 2.6])
        for col, key in zip(h, ["col_year", "license_records", "license_licensee",
                                "license_amount", "license_purchase_date",
                                "col_notes", "col_actions"]):
            col.caption(t(key))
        for rec in recs:
            lid = rec["license_id"]
            ys = int(rec["years"])
            period = f'{rec["year"]}–{rec["year"] + ys - 1}' if ys > 1 else str(rec["year"])
            c = st.columns([1, 1.4, 2, 1.4, 1.6, 2, 2.6])
            c[0].write(str(rec["year"]))
            c[1].write(period)
            c[2].write(rec["licensee"] or "—")
            c[3].write(format_eur(rec["amount"]))
            c[4].write(rec["purchase_date"] or "—")
            c[5].write(rec["notes"] or "—")
            a1, a2, a3 = c[6].columns(3)
            if a1.button(t("edit_btn"), key=f"lic_edit_{lid}", use_container_width=True):
                st.dialog(t("edit_license"), width="large")(_license_edit_dialog)(user, lid)
            if a2.button(t("delete_btn"), key=f"lic_del_{lid}", use_container_width=True):
                st.dialog(t("delete_license"))(_license_delete_dialog)(user, lid)
            if a3.button(t("print_invoice"), key=f"lic_inv_{lid}", use_container_width=True):
                st.dialog(t("license_invoice_title"), width="large")(
                    render_license_invoice)(_license_invoice_payload(rec))

    st.divider()
    # ── Add a license
    st.subheader(f"➕ {t('add_license')}")
    with st.form("lic_add_form", clear_on_submit=True):
        licensee = st.text_input(t("license_licensee"), value=cfg.get_business_name())
        c1, c2, c3 = st.columns(3)
        year = c1.number_input(t("col_year"), min_value=2020, max_value=2100,
                               value=lic.current_year())
        years = c2.number_input(t("license_years"), min_value=1, max_value=10, value=1)
        amount = c3.number_input(f'{t("license_amount")} ({CURRENCY_SYMBOL})',
                                 min_value=0, value=0, step=50)
        c4, c5 = st.columns(2)
        pdate = c4.date_input(t("license_purchase_date"), date.today())
        notes = c5.text_input(t("col_notes"))
        if st.form_submit_button(t("add_license"), type="primary"):
            lrepo.add_license(licensee.strip(), int(year), int(years),
                              int(amount) * 100, pdate.isoformat(), notes.strip())
            lic.extend_licensed_year(int(year) + int(years) - 1)
            audit_service.record(user, "add_license", "license", str(int(year)))
            st.toast(t("license_added"))
            st.rerun()

    st.divider()
    _smtp_section(user)

    st.divider()
    _danger_zone(user)


# ━━━━━━━━━━━━━━ Danger zone (super-admin) — reset Finance / Fleet data
def _danger_zone(user):
    st.subheader(f'⚠️ {t("danger_zone")}')
    # Two independent, confirmation-gated resets. Each requires the exact word
    # RESET typed in, so a stray click can never wipe data. Both are audited.
    f1, f2 = st.columns(2)
    with f1, st.container(border=True):
        st.markdown(f'**💰 {t("reset_finance_btn")}**')
        st.caption(t("reset_finance_help"))
        cf = st.text_input(t("reset_confirm_label"), key="dzc_fin")
        if st.button(t("reset_finance_btn"), key="dzreset_fin", type="primary",
                     use_container_width=True, disabled=cf.strip().upper() != "RESET"):
            counts = admin_ops.reset_finance()
            audit_service.record(user, "reset_finance", "settings", "finance", str(counts))
            st.success(t("reset_done"))
            st.rerun()
    with f2, st.container(border=True):
        st.markdown(f'**🚗 {t("reset_fleet_btn")}**')
        st.caption(t("reset_fleet_help"))
        cl = st.text_input(t("reset_confirm_label"), key="dzc_fleet")
        if st.button(t("reset_fleet_btn"), key="dzreset_fleet", type="primary",
                     use_container_width=True, disabled=cl.strip().upper() != "RESET"):
            counts = admin_ops.reset_fleet()
            photos.invalidate_cache()
            audit_service.record(user, "reset_fleet", "settings", "fleet", str(counts))
            st.success(t("reset_done"))
            st.rerun()


def _license_invoice_payload(rec: dict) -> dict:
    """Map a license record → the dict render_license_invoice expects."""
    return {
        "licensee": rec["licensee"] or cfg.get_business_name(),
        "years": rec["years"],
        "start_year": rec["year"],
        "end_year": rec["year"] + rec["years"] - 1,
        "amount_cents": rec["amount"],
        "date": rec["purchase_date"],
        "invoice_no": f'LIC-{rec["year"]}-{rec["license_id"]:03d}',
    }


def _license_edit_dialog(user, license_id: int):
    rec = lrepo.get_license(license_id)
    if not rec:
        st.error(t("no_licenses"))
        return
    try:
        cur_pdate = date.fromisoformat(rec["purchase_date"]) if rec["purchase_date"] else date.today()
    except ValueError:
        cur_pdate = date.today()
    with st.form(f"lic_edit_form_{license_id}"):
        licensee = st.text_input(t("license_licensee"), value=rec["licensee"] or "")
        c1, c2, c3 = st.columns(3)
        year = c1.number_input(t("col_year"), min_value=2020, max_value=2100,
                               value=int(rec["year"]))
        years = c2.number_input(t("license_years"), min_value=1, max_value=10,
                                value=int(rec["years"]))
        amount = c3.number_input(f'{t("license_amount")} ({CURRENCY_SYMBOL})',
                                 min_value=0, value=int(rec["amount"]) // 100, step=50)
        c4, c5 = st.columns(2)
        pdate = c4.date_input(t("license_purchase_date"), cur_pdate)
        notes = c5.text_input(t("col_notes"), value=rec["notes"] or "")
        if st.form_submit_button(t("save_btn"), type="primary"):
            lrepo.update_license(license_id, licensee.strip(), int(year), int(years),
                                 int(amount) * 100, pdate.isoformat(), notes.strip())
            lic.extend_licensed_year(int(year) + int(years) - 1)
            audit_service.record(user, "update_license", "license", str(license_id))
            st.toast(t("license_updated"))
            st.rerun()


def _license_delete_dialog(user, license_id: int):
    rec = lrepo.get_license(license_id)
    if not rec:
        st.error(t("no_licenses"))
        return
    st.write(f'{rec["year"]} · {rec["licensee"] or "—"} · {format_eur(rec["amount"])}')
    confirm = st.checkbox(t("delete_confirm"), key=f"lic_del_conf_{license_id}")
    if st.button(t("delete_btn"), type="primary", disabled=not confirm,
                 key=f"lic_del_go_{license_id}"):
        lrepo.delete_license(license_id)
        audit_service.record(user, "delete_license", "license", str(license_id))
        st.toast(t("license_deleted"))
        st.rerun()


def _smtp_section(user):
    st.subheader(f"✉️ {t('smtp_settings')}")
    st.caption(t("smtp_help"))
    c = email_service.smtp_config()
    badge = "✅ " + t("smtp_configured") if email_service.is_configured() else "⚠️ " + t("smtp_not_set")
    st.caption(badge)
    with st.form("smtp_form"):
        s1, s2 = st.columns(2)
        host = s1.text_input("SMTP host", value=c["smtp_host"])
        port = s2.text_input("SMTP port", value=c["smtp_port"] or "587")
        s3, s4 = st.columns(2)
        suser = s3.text_input("SMTP user", value=c["smtp_user"])
        spass = s4.text_input("SMTP password", value=c["smtp_pass"], type="password")
        sender = st.text_input(t("smtp_from"), value=c["smtp_from"] or email_service.FALLBACK_EMAIL)
        if st.form_submit_button(t("save_btn"), type="primary"):
            email_service.save_smtp_config(host, port, suser, spass, sender)
            audit_service.record(user, "set_smtp", "settings", "smtp")
            st.success(t("business_saved"))
            st.rerun()


# ━━━━━━━━━━━━━━ Profile + Password (everyone)
def _password_tab(user):
    st.subheader(f"👤 {t('my_profile')}")
    with st.form("my_name_form"):
        cur_name = (st.session_state.get("user") or {}).get("full_name") or ""
        my_name = st.text_input(t("full_name"), value=cur_name)
        if st.form_submit_button(t("save_btn"), type="primary"):
            auth.set_user_full_name(user["username"], my_name)
            if isinstance(st.session_state.get("user"), dict):
                st.session_state.user["full_name"] = my_name.strip()
            audit_service.record(user, "set_full_name", "user", user["username"])
            st.success(t("profile_saved"))
            st.rerun()

    with st.form("my_email_form"):
        cur_email = (st.session_state.get("user") or {}).get("email") or ""
        my_email = st.text_input(t("email_label"), value=cur_email, help=t("email_help"))
        if st.form_submit_button(t("save_btn")):
            auth.set_user_email(user["username"], my_email)
            if isinstance(st.session_state.get("user"), dict):
                st.session_state.user["email"] = my_email.strip()
            audit_service.record(user, "set_email", "user", user["username"])
            st.success(t("email_saved"))
            st.rerun()

    st.divider()
    st.subheader(f"🔐 {t('change_password')}")
    with st.form("change_pw_form", clear_on_submit=True):
        cur = st.text_input(t("current_password"), type="password")
        nw = st.text_input(t("new_password"), type="password")
        conf = st.text_input(t("confirm_password"), type="password")
        if st.form_submit_button(t("change_password"), type="primary"):
            if nw != conf:
                st.error(t("pw_mismatch"))
            else:
                ok, msg = auth.change_password(user["username"], cur, nw)
                if ok:
                    audit_service.record(user, "change_password", "user", user["username"])
                    st.success(t("pw_changed"))
                else:
                    st.error(t(msg))


# ━━━━━━━━━━━━━━ Activity log (admin+) — masked + filterable
def _activity_tab(user):
    st.subheader(f"🕑 {t('activity_log')}")
    rows = audit_service.recent(limit=500)
    if not rows:
        st.info(t("no_activity"))
        return

    # ── Return activity (admin+ may undo an archive or a cancellation) ───────
    st.markdown(f"#### ↩️ {t('return_activity')}")
    st.caption(t("return_activity_help"))
    _return_activity_section(user, rows)
    st.divider()

    # mask actors whose role is above the viewer's as "system admin"
    viewer_level = ROLE_LEVEL.get(user["role"], 0)
    role_map = {u["username"]: u["role"] for u in auth.all_users()}

    def _show(uname):
        if ROLE_LEVEL.get(role_map.get(uname), 0) > viewer_level:
            return t("system_admin_label")
        return uname

    # toggle the filter dimension: by action OR by user (masked names)
    mode = st.radio(t("filter_by"), ["action", "user"], horizontal=True,
                    format_func=lambda m: t("col_action") if m == "action" else t("col_user"),
                    key="act_filter_mode")
    if mode == "action":
        opts = sorted({r["action"] for r in rows if r["action"]})
        chosen = st.multiselect(t("col_action"), opts, default=[], key="act_filter_a")
        if chosen:
            rows = [r for r in rows if r["action"] in chosen]
    else:
        opts = sorted({_show(r["username"]) for r in rows if r["username"]})
        chosen = st.multiselect(t("col_user"), opts, default=[], key="act_filter_u")
        if chosen:
            rows = [r for r in rows if _show(r["username"]) in chosen]

    table = [{
        t("col_when"):   (r["ts"] or "")[:19].replace("T", " "),
        t("col_user"):   _show(r["username"]),
        t("col_action"): r["action"],
        t("col_entity"): f'{r["entity"]} {r["entity_id"]}'.strip(),
        t("col_detail"): r["detail"] or "",
    } for r in rows]
    st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)


def _return_activity_section(user, rows):
    """List reversible events still in an undoable state and offer a Return button.

    Reversible = an archived vehicle (currently DELETED → restore) or a cancelled
    rental (currently Closed → reactivate). Entries are de-duplicated by entity and
    filtered by *current* state, so anything already restored/reactivated drops off.
    Hard-deletes and normal rental returns are intentionally not reversible.
    """
    seen, items = set(), []
    for r in rows:
        act, ent, eid = r["action"], r["entity"], str(r["entity_id"] or "")
        if not eid:
            continue
        if act == "archive_vehicle" and ent == "vehicle":
            if ("veh", eid) in seen:
                continue
            seen.add(("veh", eid))
            v = vrepo.get_vehicle(eid)
            if v and v["status"] == "DELETED":
                items.append(("vehicle", eid, r["id"],
                              f'🚘 {eid} · {v.get("make_model") or "—"}'))
        elif act == "cancel_rental" and ent == "rental":
            if ("rent", eid) in seen:
                continue
            seen.add(("rent", eid))
            d = rrepo.get_rental_full(eid)
            if d and d["status"] == "Closed":
                items.append(("rental", eid, r["id"],
                              f'📋 {eid} · {d.get("client_name") or "—"} · {d.get("make_model") or "—"}'))

    if not items:
        st.caption("—")
        return
    for kind, eid, aid, label in items:
        rc1, rc2 = st.columns([4, 1.3])
        rc1.markdown(label)
        if rc2.button(t("return_activity"), key=f"undo_{kind}_{eid}_{aid}",
                      use_container_width=True):
            if kind == "vehicle":
                vrepo.restore_vehicle(eid)
                audit_service.record(user, "restore_vehicle", "vehicle", eid, "return_activity")
                st.toast(t("activity_returned"))
                st.rerun()
            else:
                if rrepo.reactivate_rental(eid):
                    audit_service.record(user, "reactivate_rental", "rental", eid, "return_activity")
                    st.toast(t("activity_returned"))
                    st.rerun()
                else:
                    st.warning(t("not_available_window"))
