"""Fleet page — single action-rich table (no CRUD tabs).

Everyone sees the fleet table. Roles with `edit_fleet` get an "Add" button plus
inline status-change and edit controls; `soft_delete_vehicle` gets the delete
dialog (archive + optional hard-delete); archived vehicles can be restored from
an expander at the bottom. All add/edit/delete forms live in `st.dialog` bodies.
"""
import streamlit as st
from config.i18n import t
from config.roles import can
from config.settings import CURRENCY_SYMBOL
from ui.components import format_eur, status_badge
from ui.photos import PHOTO_TYPES, encode_many, render_photo, render_vehicle_thumb, invalidate_cache
from services import audit_service
from data.repositories import vehicles as vrepo
from data.repositories import vehicle_photos as vphotos
from data.repositories import rentals as rrepo


# Statuses a user may assign manually in the add/edit form. Only "make available"
# and "send to maintenance" are offered — "Rented" is driven by the rental
# lifecycle (not set by hand), and the control is locked while a car is on rental.
_EDITABLE_STATUSES = ["Available", "Maintenance"]


def _veh_label(v: dict) -> str:
    """Selectbox label: 'Make/Model Year · Plate' (not the bare code)."""
    head = v.get("make_model") or v.get("vehicle_id", "")
    if v.get("year"):
        head = f'{head} {v["year"]}'
    plate = v.get("license_plate")
    return f'{head} · {plate}' if plate else head


def render_fleet(user):
    st.title(f"🚘 {t('nav_fleet')}")

    may_edit = can(user, "edit_fleet")
    may_del = can(user, "soft_delete_vehicle")
    may_hard = can(user, "hard_delete_vehicle")
    privileged = may_edit or may_del

    head = st.columns([3, 1])
    head[0].caption(t("fleet_help"))
    if may_edit and head[1].button(f'➕ {t("fleet_add")}', type="primary",
                                    use_container_width=True):
        st.dialog(t("fleet_add"), width="large")(_add_dialog)(user)

    q = st.text_input(t("search"), placeholder=t("search"), key="fl_search",
                      label_visibility="collapsed")
    fleet = vrepo.list_vehicles()
    if q:
        lo = q.lower()
        fleet = [v for v in fleet if lo in " ".join(
            str(v.get(k) or "") for k in
            ("vehicle_id", "make_model", "year", "license_plate", "color", "status", "notes")
        ).lower()]
    st.caption(f"{len(fleet)} {t('col_count')}")

    if not fleet:
        st.info(t("no_cars"))
    else:
        active_ids = ({r["vehicle_id"] for r in rrepo.list_active_rentals_with_vehicle()}
                      if privileged else set())
        _fleet_grid(user, fleet, may_edit, may_del, may_hard, active_ids)

    if privileged:
        _archived_section(user)


# Cards per row on desktop; the responsive CSS in ui/theme.py collapses these to a
# single full-width column on phones, so each card stays legible without zooming.
_GRID_COLS = 2


def _fleet_grid(user, fleet, may_edit, may_del, may_hard, active_ids):
    """Browse-style grid of vehicle cards (photo + specs + prominent price + typed
    actions), inspired by modern car-rental listings. Functionally identical to the
    old table — same search, same CRUD, same status controls — only re-presented.
    With no edit/delete rights the cards simply render without action buttons."""
    for i in range(0, len(fleet), _GRID_COLS):
        row = st.columns(_GRID_COLS)
        for v, col in zip(fleet[i:i + _GRID_COLS], row):
            with col:
                _vehicle_card(user, v, may_edit, may_del, may_hard,
                              v["vehicle_id"] in active_ids)


def _vehicle_card(user, v, may_edit, may_del, may_hard, is_rented):
    vid = v["vehicle_id"]
    with st.container(border=True):
        render_vehicle_thumb(vid, height=150)         # photo (or 🚘 placeholder) on top
        tc = st.columns([2, 1])
        with tc[0]:
            st.markdown(f'**{v["make_model"]}**')
            st.caption(f'{v["year"] or "—"} · {vid}')
        with tc[1]:
            st.markdown(
                '<div style="text-align:right;line-height:1.05">'
                '<span style="font-family:var(--font-display);font-weight:700;'
                f'font-size:1.2rem;color:var(--accent)">{format_eur(v["base_daily_rate"])}</span>'
                '<div style="font-size:.66rem;color:var(--muted);font-weight:500;'
                f'text-transform:uppercase;letter-spacing:.04em">/{t("per_day")}</div></div>',
                unsafe_allow_html=True)
        st.markdown(status_badge(v["status"]), unsafe_allow_html=True)
        st.caption(f'🔖 {v["license_plate"] or "—"} · 🎨 {v["color"] or "—"} · '
                   f'📏 {v.get("mileage", 0):,} km')
        if is_rented:
            st.caption(f'🔒 {t("status_locked_rented")}')

        acts = _vehicle_actions(user, v, may_edit, may_del, may_hard, is_rented)
        # Full-width, labelled buttons stacked vertically so the name is always
        # visible (never clipped) within the half-width grid card.
        for (kp, label, btype, cb, disabled) in acts:
            if st.button(label, key=f"{kp}_{vid}", type=btype,
                         use_container_width=True, disabled=disabled):
                cb()


def _vehicle_actions(user, v, may_edit, may_del, may_hard, is_rented):
    """Typed, labelled action buttons for a card (icon + name): Edit = primary,
    status toggles = secondary, Delete-Archive = alert/red (styled via the
    st-key-fldel_ rule). Status toggles are disabled while the car is on an active
    rental."""
    vid = v["vehicle_id"]
    acts = []  # (key_prefix, label, type, callback, disabled)
    if may_edit:
        acts.append(("edt", f'✏️ {t("edit_btn")}', "primary",
                     lambda vid=vid: _open_edit(user, vid), False))
        if v["status"] != "In Garage":
            acts.append(("gar", f'🅿️ {t("to_garage")}', "secondary",
                         lambda vid=vid: _set_status(user, vid, "In Garage"), is_rented))
        if v["status"] != "Maintenance":
            acts.append(("mnt", f'🔧 {t("to_maintenance")}', "secondary",
                         lambda vid=vid: _set_status(user, vid, "Maintenance"), is_rented))
        if v["status"] in ("In Garage", "Maintenance"):
            acts.append(("avl", f'✅ {t("to_available")}', "secondary",
                         lambda vid=vid: _set_status(user, vid, "Available"), is_rented))
    if may_del:
        acts.append(("fldel", f'🗑️ {t("soft_delete")}', "primary",
                     lambda vid=vid, mh=may_hard: _open_delete(user, vid, mh), False))
    return acts


def _open_edit(user, vid):
    st.dialog(t("fleet_edit"), width="large")(_edit_dialog)(user, vid)


def _open_delete(user, vid, may_hard):
    st.dialog(t("fleet_delete"), width="large")(_delete_dialog)(user, vid, may_hard)


def _set_status(user, vid, status):
    vrepo.set_status(vid, status)
    audit_service.record(user, "set_status", "vehicle", vid, status)
    st.toast(t("status_updated"))
    st.rerun()


def _add_dialog(user):
    st.caption(t("fleet_add_help"))
    with st.form("add_vehicle_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        mm = c1.text_input(t("col_model") + " *")
        yr = c2.number_input(t("col_year"), min_value=1970, max_value=2035, value=2022)
        c3, c4, c5 = st.columns(3)
        lp = c3.text_input(t("col_plate"))
        col = c4.text_input(t("col_color"))
        mi = c5.number_input(t("col_mileage"), min_value=0, value=0, step=100)
        c6, c7 = st.columns(2)
        rate = c6.number_input(f'{t("col_rate")} ({CURRENCY_SYMBOL})', min_value=0, value=30, step=5)
        st_v = c7.selectbox(t("col_status"), _EDITABLE_STATUSES, format_func=lambda s: t(s))
        notes = st.text_area(t("col_notes"))
        photo_files = st.file_uploader(t("vehicle_photos"), type=PHOTO_TYPES,
                                       accept_multiple_files=True, help=t("vehicle_photo_help"))
        if st.form_submit_button(t("add_btn"), type="primary"):
            if not mm.strip():
                st.error(t("fields_required"))
            else:
                vid = vrepo.add_vehicle(mm.strip(), int(yr), lp.strip(), col.strip(),
                                        int(mi), st_v, int(rate) * 100, notes.strip())
                if photo_files:
                    vphotos.add_photos(vid, encode_many(photo_files))
                    invalidate_cache()
                audit_service.record(user, "add_vehicle", "vehicle", vid, mm.strip())
                st.toast(f"{t('added_ok')} → {vid}")
                st.rerun()


def _edit_dialog(user, vehicle_id):
    st.caption(t("fleet_edit_help"))
    v = vrepo.get_vehicle(vehicle_id)
    if not v:
        return
    is_rented = rrepo.vehicle_has_active_rental(vehicle_id)

    cur_photo_col, _ = st.columns([1, 2])
    with cur_photo_col:
        render_vehicle_thumb(vehicle_id, height=120)
    if is_rented:
        st.info(f'🔒 {t("status_locked_rented")}')

    with st.form("edit_vehicle_form"):
        c1, c2 = st.columns(2)
        mm = c1.text_input(t("col_model") + "*", value=v["make_model"])
        yr = c2.number_input(t("col_year"), min_value=1970, max_value=2035,
                             value=int(v["year"] or 2022))
        c3, c4, c5 = st.columns(3)
        lp = c3.text_input(t("col_plate"), value=v["license_plate"] or "")
        col = c4.text_input(t("col_color"), value=v["color"] or "")
        mi = c5.number_input(t("col_mileage"), min_value=0, value=int(v["mileage"] or 0), step=100)
        c6, c7 = st.columns(2)
        cur_rate = max(0, int(round((v["base_daily_rate"] or 0) / 100)))
        rate = c6.number_input(f'{t("col_rate")} ({CURRENCY_SYMBOL})', min_value=0, value=cur_rate, step=5)
        if is_rented:
            # status is driven by the rental lifecycle — locked here
            c7.selectbox(t("col_status"), [v["status"]], format_func=lambda s: t(s), disabled=True)
            st_v = v["status"]
        else:
            cur_st = v["status"] if v["status"] in _EDITABLE_STATUSES else _EDITABLE_STATUSES[0]
            st_v = c7.selectbox(t("col_status"), _EDITABLE_STATUSES,
                                index=_EDITABLE_STATUSES.index(cur_st),
                                format_func=lambda s: t(s))
        notes = st.text_area(t("col_notes"), value=v["notes"] or "")
        if st.form_submit_button(t("update_btn"), type="primary"):
            vrepo.update_vehicle(vehicle_id, mm.strip(), int(yr), lp.strip(),
                                 col.strip(), int(mi), st_v,
                                 int(rate) * 100, notes.strip())
            audit_service.record(user, "edit_vehicle", "vehicle", vehicle_id)
            st.toast(t("updated_ok"))
            st.rerun()

    # photos are managed below the form (multiple, loaded lazily on demand)
    _photo_manager(user, vehicle_id)


def _photo_manager(user, vehicle_id):
    """Lazy multi-photo manager: only loads/renders the gallery when expanded."""
    n = vphotos.photo_count(vehicle_id)
    if not st.toggle(f'🖼️ {t("manage_photos")} ({n})', key=f"pm_{vehicle_id}"):
        return
    photos = vphotos.list_photos(vehicle_id)
    if photos:
        per_row = 4
        for i in range(0, len(photos), per_row):
            cols = st.columns(per_row)
            for ph, c in zip(photos[i:i + per_row], cols):
                with c:
                    render_photo(ph["photo"], height=90)
                    if st.button(f'🗑️', key=f'delph_{ph["photo_id"]}', use_container_width=True,
                                 help=t("delete_btn")):
                        vphotos.delete_photo(ph["photo_id"])
                        invalidate_cache()
                        audit_service.record(user, "delete_photo", "vehicle", vehicle_id)
                        st.rerun()
    else:
        st.caption(t("no_photos"))
    new_files = st.file_uploader(t("add_photos"), type=PHOTO_TYPES,
                                 accept_multiple_files=True, key=f"addph_{vehicle_id}")
    if new_files and st.button(f'➕ {t("add_photos")}', key=f"addphbtn_{vehicle_id}", type="primary"):
        vphotos.add_photos(vehicle_id, encode_many(new_files))
        invalidate_cache()
        audit_service.record(user, "add_photos", "vehicle", vehicle_id, str(len(new_files)))
        st.toast(t("photos_added"))
        st.rerun()


def _delete_dialog(user, vehicle_id, may_hard):
    st.caption(t("fleet_delete_help"))
    v = vrepo.get_vehicle(vehicle_id)
    if v:
        st.markdown(f'**{v["vehicle_id"]}** · {_veh_label(v)}')
    confirm = st.checkbox(t("delete_confirm"), key=f"del_confirm_{vehicle_id}")
    c1, c2 = st.columns(2)
    if c1.button(f'📁 {t("soft_delete")}', disabled=not confirm, use_container_width=True):
        vrepo.soft_delete(vehicle_id)
        audit_service.record(user, "archive_vehicle", "vehicle", vehicle_id)
        st.toast(t("soft_deleted_done"))
        st.rerun()
    if may_hard:
        if c2.button(f'🗑️ {t("hard_delete")}', disabled=not confirm,
                     type="primary", use_container_width=True):
            vrepo.hard_delete(vehicle_id)
            audit_service.record(user, "delete_vehicle", "vehicle", vehicle_id)
            st.toast(t("hard_deleted_done"))
            st.rerun()


def _archived_section(user):
    archived = [v for v in vrepo.list_vehicles(include_deleted=True) if v["status"] == "DELETED"]
    if not archived:
        return
    st.divider()
    with st.expander(f"📂 {t('archived_list')} ({len(archived)})"):
        for v in archived:
            cc1, cc2, cc3 = st.columns([2, 2, 1])
            cc1.markdown(f'**{v["vehicle_id"]}** {v["make_model"]}')
            cc2.caption(v["license_plate"] or "—")
            if cc3.button(t("restore_btn"), key=f"rst_{v['vehicle_id']}",
                          use_container_width=True):
                vrepo.restore_vehicle(v["vehicle_id"])
                audit_service.record(user, "restore_vehicle", "vehicle", v["vehicle_id"])
                st.toast(t("restored_ok"))
                st.rerun()
