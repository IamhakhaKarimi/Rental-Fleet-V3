"""
Print-ready rental invoice.

The invoice language is chosen at registration (stored on rentals.invoice_lang)
and is independent of the UI language — all labels and the rental terms are
rendered through t_lang(key, lang). The layout is intentionally compact so the
whole document (including the terms & conditions) prints comfortably **within a
single A4 page** rather than spilling onto a second sheet.

The HTML is used for the inline preview and browser print (window.print()); the
download button serves a PDF rendered by ui/pdf.build_invoice_pdf (same content,
deposit deducted), so the saved file is a portable PDF rather than raw HTML.
"""

import html as _html

import streamlit as st
import streamlit.components.v1 as components

from config.i18n import t, t_lang
from config.roles import ROLE_LABEL_KEY
from config.settings import APP_TAGLINE, LANGUAGES
from config.terms import rental_terms
from ui.components import format_eur
from ui.pdf import build_invoice_pdf
from data.repositories import rentals as rentals_repo
from data.repositories import app_settings as app_cfg

_LINE_LABEL = {
    "rental": "invoice_line_rental",
    "overdue_penalty": "late_fee",
    "damage": "damage_charge",
}


def _esc(value) -> str:
    return _html.escape(str(value if value is not None else ""))


def build_invoice_html(deal: dict, charges: list[dict], business_name: str,
                       lang: str = "tr", logo: str = "") -> str:
    """Return a complete, standalone, compact HTML invoice in `lang`."""
    if lang not in LANGUAGES:
        lang = "tr"
    T = lambda k: t_lang(k, lang)

    logo_img = ""
    if logo:
        logo_img = (
            f'<img src="data:image/png;base64,{logo}" '
            f'style="max-height:46px;max-width:170px;margin-bottom:5px;display:block"/>'
        )

    billable = [c for c in charges if c["type"] != "deposit"]
    deposit = sum(c["amount"] for c in charges if c["type"] == "deposit") \
        or int(deal.get("deposit") or 0)
    grand_total = sum(c["amount"] for c in billable) or int(deal.get("total_amount") or 0)

    days = int(deal.get("rental_days") or 0)
    daily_rate = int(deal.get("daily_rate") or 0)

    line_rows = []
    for c in billable:
        ctype = c["type"]
        label = T(_LINE_LABEL.get(ctype, ctype))
        if ctype == "rental":
            qty, unit = str(days), format_eur(daily_rate)
        else:
            qty, unit = "1", format_eur(c["amount"])
        line_rows.append(
            f"<tr><td>{_esc(label)}</td><td class='num'>{_esc(qty)}</td>"
            f"<td class='num'>{_esc(unit)}</td>"
            f"<td class='num'>{format_eur(c['amount'])}</td></tr>"
        )
    if not line_rows:
        line_rows.append(
            f"<tr><td>{_esc(T('invoice_line_rental'))}</td><td class='num'>{days}</td>"
            f"<td class='num'>{format_eur(daily_rate)}</td>"
            f"<td class='num'>{format_eur(grand_total)}</td></tr>"
        )

    start = (deal.get("start_dt") or "")[:16].replace("T", " ")
    end = (deal.get("end_dt") or "")[:16].replace("T", " ")
    inv_date = (deal.get("created_at") or "")[:10]
    signed = str(deal.get("contract_signed", "No")).lower() in ("yes", "1", "true")
    signed_txt = T("invoice_signed") if signed else T("invoice_unsigned")

    issuer_name = deal.get("created_by_name") or deal.get("created_by") or "—"
    issuer_role = deal.get("created_by_role") or ""
    issuer_role_label = T(ROLE_LABEL_KEY.get(issuer_role, "")) if issuer_role else ""
    issued_by = _esc(issuer_name) + (f" ({_esc(issuer_role_label)})" if issuer_role_label else "")

    # The deposit already taken is DEDUCTED from the subtotal, so the grand total
    # shows the exact remaining balance due (no ambiguity for the customer).
    balance_due = grand_total - deposit
    deposit_row = ""
    if deposit > 0:
        deposit_row = (
            f"<tr><td>− {_esc(T('invoice_line_deposit'))}</td>"
            f"<td class='num'>− {format_eur(deposit)}</td></tr>"
        )

    terms = rental_terms(lang)
    terms_items = "".join(f"<li>{_esc(r)}</li>" for r in terms["rules"])

    return f"""<!DOCTYPE html><html lang="{lang}"><head><meta charset="utf-8"/>
<title>{_esc(T('invoice_heading'))} {_esc(deal.get('deal_id',''))}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
  * {{ box-sizing: border-box; }}
  body {{ font-family:'Plus Jakarta Sans',system-ui,sans-serif; color:#211C17; margin:0;
         background:#F2EFE9; padding:16px; }}
  /* Compact sheet — narrower than A4 so it always fits one page */
  .sheet {{ max-width:640px; margin:0 auto; background:#fff; border:1px solid #E7E0D5;
            border-radius:10px; padding:20px 24px; font-size:12px; }}
  .top {{ display:flex; justify-content:space-between; align-items:flex-start;
          border-bottom:2px solid #1A1C1E; padding-bottom:10px; margin-bottom:14px; }}
  .brand {{ font-family:'Plus Jakarta Sans',system-ui,sans-serif; font-weight:700; font-size:17px;
            color:#211C17; line-height:1.1; }}
  .brand small {{ display:block; font-family:'Plus Jakarta Sans'; font-weight:500; font-size:9px;
                  letter-spacing:.12em; text-transform:uppercase; color:#736B60; margin-top:3px; }}
  .inv-title {{ text-align:right; }}
  .inv-title h1 {{ font-family:'Plus Jakarta Sans',system-ui,sans-serif; font-size:20px; margin:0;
                   color:#1A1C1E; letter-spacing:.03em; }}
  .meta {{ font-size:11px; color:#475569; margin-top:4px; line-height:1.5; }}
  .meta b {{ color:#211C17; }}
  .cols {{ display:flex; gap:22px; margin-bottom:12px; }}
  .cols .box {{ flex:1; }}
  .lbl {{ font-size:9px; font-weight:600; letter-spacing:.07em; text-transform:uppercase;
          color:#736B60; margin-bottom:3px; }}
  .val {{ font-size:12px; line-height:1.5; }}
  table {{ width:100%; border-collapse:collapse; margin-top:4px; }}
  th {{ text-align:left; font-size:9px; letter-spacing:.05em; text-transform:uppercase;
        color:#736B60; border-bottom:1px solid #E7E0D5; padding:5px 5px; }}
  td {{ font-size:12px; padding:6px 5px; border-bottom:1px solid #F2EFE9; }}
  td.num, th.num {{ text-align:right; }}
  tr.soft td {{ color:#475569; }}
  .totals {{ margin-top:8px; display:flex; justify-content:flex-end; }}
  .totals table {{ width:auto; min-width:220px; }}
  .totals td {{ border:none; padding:3px 5px; }}
  .grand td {{ font-family:'Plus Jakarta Sans',system-ui,sans-serif; font-weight:700; font-size:15px;
               color:#211C17; border-top:2px solid #211C17; padding-top:7px; }}
  .grand td.num {{ color:#1A1C1E; }}
  .chip {{ display:inline-block; font-size:9px; font-weight:600; padding:2px 8px;
           border-radius:999px; background:#EDEDEA; color:#1A1C1E; margin-top:10px; }}
  /* Terms & conditions — small two-column list so it still fits one A4 page */
  .terms {{ margin-top:14px; padding-top:10px; border-top:1px dashed #CBD5E1; }}
  .terms h3 {{ font-family:'Plus Jakarta Sans',system-ui,sans-serif; font-size:11px; margin:0 0 6px;
               text-transform:uppercase; letter-spacing:.04em; color:#211C17; }}
  .terms ol {{ margin:0; padding-left:16px; columns:2; column-gap:20px;
               font-size:8.2px; line-height:1.35; color:#475569; }}
  .terms li {{ margin-bottom:3px; break-inside:avoid; }}
  .foot {{ margin-top:12px; font-size:9px; color:#736B60; line-height:1.5; }}
  .toolbar {{ max-width:640px; margin:0 auto 10px; text-align:right; }}
  .toolbar button {{ font-family:'Plus Jakarta Sans',sans-serif; font-size:12px; font-weight:600;
           background:#1A1C1E; color:#fff; border:none; border-radius:8px;
           padding:7px 14px; cursor:pointer; }}
  .toolbar button:hover {{ background:#3F3F46; }}
  @media print {{
    @page {{ size: A4; margin: 10mm; }}
    body {{ background:#fff; padding:0; }}
    .sheet {{ border:none; border-radius:0; max-width:none; }}
    .toolbar {{ display:none !important; }}
  }}
</style></head><body>
  <div class="toolbar"><button onclick="window.print()">{_esc(T('invoice_print'))}</button></div>
  <div class="sheet">
    <div class="top">
      <div class="brand">{logo_img}{_esc(business_name)}<small>{_esc(APP_TAGLINE)}</small></div>
      <div class="inv-title">
        <h1>{_esc(T('invoice_heading'))}</h1>
        <div class="meta">
          <div>{_esc(T('invoice_no'))}: <b>{_esc(deal.get('deal_id',''))}</b></div>
          <div>{_esc(T('invoice_date'))}: <b>{_esc(inv_date)}</b></div>
          <div>{_esc(T('invoice_issued_by'))}: <b>{issued_by}</b></div>
        </div>
      </div>
    </div>

    <div class="cols">
      <div class="box">
        <div class="lbl">{_esc(T('bill_to'))}</div>
        <div class="val"><b>{_esc(deal.get('client_name',''))}</b><br>
          {_esc(deal.get('phone','') or '—')} &nbsp; {_esc(deal.get('id_passport','') or '—')}</div>
      </div>
      <div class="box">
        <div class="lbl">{_esc(T('invoice_vehicle'))}</div>
        <div class="val"><b>{_esc(deal.get('vehicle_id',''))}</b> {_esc(deal.get('make_model',''))} ·
          {_esc(deal.get('license_plate','') or '—')}<br>
          <span class="lbl" style="display:inline">{_esc(T('invoice_period'))}:</span>
          {_esc(start)} &rarr; {_esc(end)}</div>
      </div>
    </div>

    <table>
      <thead><tr>
        <th>{_esc(T('invoice_desc'))}</th>
        <th class="num">{_esc(T('invoice_qty'))}</th>
        <th class="num">{_esc(T('invoice_unit'))}</th>
        <th class="num">{_esc(T('invoice_amount'))}</th>
      </tr></thead>
      <tbody>{''.join(line_rows)}</tbody>
    </table>

    <div class="totals"><table>
      <tr><td>{_esc(T('invoice_subtotal'))}</td><td class="num">{format_eur(grand_total)}</td></tr>
      {deposit_row}
      <tr class="grand"><td>{_esc(T('invoice_total'))}</td>
          <td class="num">{format_eur(balance_due)}</td></tr>
    </table></div>

    <span class="chip">{_esc(signed_txt)}</span>

    <div class="terms">
      <h3>{_esc(terms['title'])}</h3>
      <ol>{terms_items}</ol>
    </div>

    <div class="foot">{_esc(T('invoice_thanks'))} · {_esc(T('invoice_footer'))}</div>
  </div>
</body></html>"""


def render_invoice(deal_id: str, key_prefix: str = "inv", lang: str | None = None):
    """Inline invoice preview + language switch + print/download controls."""
    deal = rentals_repo.get_rental_full(deal_id)
    if not deal:
        return
    charges = rentals_repo.list_charges_for_deal(deal_id)
    business = app_cfg.get_business_name()
    logo = app_cfg.get_logo()

    opts = list(LANGUAGES)
    default_lang = lang or deal.get("invoice_lang") or "tr"
    chosen = st.radio(
        t("invoice_language"), opts,
        index=opts.index(default_lang) if default_lang in opts else 0,
        format_func=lambda l: LANGUAGES[l],
        horizontal=True, key=f"{key_prefix}_lang_{deal_id}",
    )
    doc = build_invoice_html(deal, charges, business, lang=chosen, logo=logo)
    components.html(doc, height=760, scrolling=True)
    pdf_bytes = build_invoice_pdf(deal, charges, business, lang=chosen, logo=logo)
    st.download_button(
        t("invoice_download"), data=pdf_bytes,
        file_name=f"invoice_{deal_id}_{chosen}.pdf", mime="application/pdf",
        key=f"{key_prefix}_dl_{deal_id}", use_container_width=True,
    )
