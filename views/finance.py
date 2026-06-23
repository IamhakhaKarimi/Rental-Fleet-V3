"""
Finance page — comprehensive income / cost / profit evaluation (admin+ only).

Five tabs:
  • Overview  — headline KPIs (revenue, cost, net, margin) + revenue & cost mix
  • Monthly   — income vs cost vs net, per calendar month
  • Yearly    — income vs cost vs net, per year
  • By Vehicle— per-car profitability (income − cost = net)
  • Costs      — record operating costs and review recent entries

Income is drawn from the `charges` ledger, costs from `vehicle_costs`. Everything
is computed in cents by finance_service and only formatted to euros at display.
"""
from datetime import date

import pandas as pd
import streamlit as st

from config.i18n import t
from config.roles import can
from ui.components import format_eur, kpi_tile
from services import finance_service as fin
from services import audit_service
from services import licensing_service as lic
from data.repositories import vehicle_costs as costs_repo
from data.repositories import vehicles as vrepo


def _eur_df(rows: list[dict], cols: list[str]) -> pd.DataFrame:
    """Convert selected cent columns to euros for charting."""
    df = pd.DataFrame(rows)
    for c in cols:
        if c in df.columns:
            df[c] = df[c] / 100.0
    return df


def render_finance(user):
    st.title(f"💰 {t('finance_title')}")
    st.caption(t("finance_help"))

    if not can(user, "view_finance"):
        st.error(t("access_denied"))
        return

    pnl = fin.pnl_summary()
    have_costs = costs_repo.cost_total() > 0
    if pnl["income"] == 0 and not have_costs:
        st.info(t("no_finance_data"))
        # Still allow cost entry so the first numbers can be captured.
        _costs_tab(user)
        return

    # ── headline KPIs ───────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi_tile("total_revenue", format_eur(pnl["income"]), accent=True)
    with c2: kpi_tile("total_cost",    format_eur(pnl["cost"]))
    with c3: kpi_tile("net_profit",    format_eur(pnl["net"]), accent=pnl["net"] >= 0)
    with c4: kpi_tile("profit_margin", f'{pnl["margin"]:.0f}%')

    st.divider()

    tabs = st.tabs([
        f"📊 {t('fin_tab_overview')}",
        f"📅 {t('fin_tab_monthly')}",
        f"🗓️ {t('fin_tab_yearly')}",
        f"🚗 {t('fin_tab_vehicle')}",
        f"🧾 {t('fin_tab_costs')}",
    ])

    with tabs[0]:
        _overview_tab()
    with tabs[1]:
        _period_tab(fin.pnl_by_month(), t("monthly_eval"))
    with tabs[2]:
        _period_tab(fin.pnl_by_year(), t("yearly_eval"))
    with tabs[3]:
        _by_vehicle_tab()
    with tabs[4]:
        _costs_tab(user)


# ── tab: overview ────────────────────────────────────────────────────────────
def _overview_tab():
    s = fin.revenue_summary()
    c1, c2, c3 = st.columns(3)
    with c1: kpi_tile("rental_revenue",  format_eur(s["rental"]))
    with c2: kpi_tile("penalty_revenue", format_eur(s["penalty"]))
    with c3: kpi_tile("damage_revenue",  format_eur(s["damage"]))

    st.divider()
    st.subheader(t("cost_breakdown"))
    by_type = fin.cost_by_type()
    if not by_type:
        st.info(t("no_costs"))
        return
    rows = [{
        t("cost_type"): t(f'cost_{r["type"]}'),
        t("col_cost"):  format_eur(r["amount"]),
    } for r in by_type]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ── tabs: monthly / yearly ───────────────────────────────────────────────────
def _period_tab(rows: list[dict], heading: str):
    st.subheader(heading)
    if not rows:
        st.info(t("no_finance_data"))
        return

    chart = _eur_df(rows, ["income", "cost"]).rename(columns={
        "period": t("col_period"),
        "income": t("col_income"),
        "cost":   t("col_cost"),
    }).set_index(t("col_period"))
    st.bar_chart(chart[[t("col_income"), t("col_cost")]], stack=False)

    table = [{
        t("col_period"): r["period"],
        t("col_income"): format_eur(r["income"]),
        t("col_cost"):   format_eur(r["cost"]),
        t("col_net"):    format_eur(r["net"]),
    } for r in rows]
    st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)
    _totals_row(sum(r["income"] for r in rows),
                sum(r["cost"] for r in rows),
                sum(r["net"] for r in rows))


# ── tab: by vehicle ──────────────────────────────────────────────────────────
def _by_vehicle_tab():
    st.subheader(t("by_vehicle_profit"))
    rows = fin.profit_by_vehicle()
    if not rows:
        st.info(t("no_finance_data"))
        return
    table = [{
        t("col_id"):     r["vehicle_id"],
        t("col_model"):  r["make_model"],
        t("col_income"): format_eur(r["income"]),
        t("col_cost"):   format_eur(r["cost"]),
        t("col_net"):    format_eur(r["net"]),
    } for r in rows]
    st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)
    _totals_row(sum(r["income"] for r in rows),
                sum(r["cost"] for r in rows),
                sum(r["net"] for r in rows))


def _totals_row(income: int, cost: int, net: int):
    """Shared income / cost / net summary tiles for a finance sub-tab."""
    st.caption(f"**{t('fin_totals')}**")
    m1, m2, m3 = st.columns(3)
    with m1: kpi_tile("total_revenue", format_eur(income), accent=True)
    with m2: kpi_tile("total_cost",    format_eur(cost))
    with m3: kpi_tile("net_profit",    format_eur(net), accent=net >= 0)


# ── tab: costs (entry + recent) ──────────────────────────────────────────────
def _costs_tab(user):
    st.subheader(f"➕ {t('add_cost_section')}")
    fleet = vrepo.list_vehicles()
    if not fleet:
        st.info(t("no_cars"))
        return
    ids = [v["vehicle_id"] for v in fleet]
    labels = {v["vehicle_id"]: f'{v["vehicle_id"]} · {v["make_model"]}' for v in fleet}

    with st.form("add_cost_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        veh = c1.selectbox(t("select_vehicle"), ids, format_func=lambda i: labels[i])
        ctype = c2.selectbox(t("cost_type"), costs_repo.COST_TYPES,
                             format_func=lambda x: t(f"cost_{x}"))
        c3, c4 = st.columns(2)
        amount = c3.number_input(f'{t("cost_amount")} (€)', min_value=0, value=0, step=10)
        cdate = c4.date_input(t("cost_date"), date.today(), max_value=lic.max_date())
        note = st.text_input(t("cost_note"))
        if st.form_submit_button(t("add_cost_btn"), type="primary"):
            if amount > 0:
                costs_repo.add_cost(veh, ctype, int(amount) * 100, cdate.isoformat(), note.strip())
                audit_service.record(user, "add_cost", "vehicle_cost", veh,
                                     f'{ctype} {format_eur(int(amount) * 100)}')
                st.success(t("cost_added"))
                st.rerun()
            else:
                st.warning(t("fields_required"))

    st.divider()
    st.subheader(f"📋 {t('recent_costs')}")
    recent = costs_repo.list_costs(limit=100)
    if not recent:
        st.info(t("no_costs"))
        return
    tc1, _ = st.columns(2)
    with tc1:
        kpi_tile("total_cost", format_eur(costs_repo.cost_total()))
    for c in recent:
        type_label = t(f'cost_{c["type"]}')
        meta = f'{type_label} · {c["period_date"][:10]}'
        if c["note"]:
            meta += f' · {c["note"]}'
        cc1, cc2, cc3, cc4 = st.columns([2, 2.4, 1.4, 1])
        cc1.markdown(f'**{c["vehicle_id"]}** {c.get("make_model") or "—"}')
        cc2.caption(meta)
        cc3.markdown(format_eur(c["amount"]))
        if cc4.button(t("delete_btn"), key=f'delc_{c["cost_id"]}', use_container_width=True):
            costs_repo.delete_cost(c["cost_id"])
            audit_service.record(user, "delete_cost", "vehicle_cost", c["vehicle_id"])
            st.rerun()
