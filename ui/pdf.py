"""
PDF rendering for the two invoices (rental + software license).

fpdf2 is pure-Python (no native deps — installs cleanly on Windows), so it is the
download format for both invoices. A Unicode TrueType font is registered when one
is found on disk (Arial on Windows, DejaVu on Linux) so Turkish/Albanian/German
glyphs and the € sign render correctly; if none is found we fall back to the
latin-1 core font. The on-screen *preview* stays HTML (see ui/invoice.py and
ui/license_invoice.py) — only the download button serves these PDF bytes.
"""

import base64
import io
import os

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from config.i18n import t, t_lang
from config.roles import ROLE_LABEL_KEY
from config.settings import (APP_NAME, APP_TAGLINE, APP_VERSION,
                             CURRENCY_SYMBOL, LANGUAGES)
from config.terms import rental_terms

# First existing (regular, bold) pair wins. Arial ships on Windows; DejaVu is the
# usual Linux fallback. Both cover Latin-Extended (TR/SQ/DE) + the € sign.
_FONT_CANDIDATES = [
    (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
]

_ACCENT = (11, 122, 85)    # brand emerald (#0B7A55) — matches ui/theme.py
_TEXT = (33, 28, 23)       # warm ink #211C17
_MUTED = (115, 107, 96)    # warm taupe #736B60
_LIGHT = (242, 239, 233)   # warm surface #F2EFE9

_LINE_LABEL = {
    "rental": "invoice_line_rental",
    "overdue_penalty": "late_fee",
    "damage": "damage_charge",
}


def _eur(cents) -> str:
    """Integer cents -> '€30' / '€30.50' (mirrors ui.components.format_eur)."""
    cents = int(cents or 0)
    whole, rem = divmod(abs(cents), 100)
    sign = "-" if cents < 0 else ""
    body = f"{whole:,}" if rem == 0 else f"{whole:,}.{rem:02d}"
    return f"{sign}{CURRENCY_SYMBOL}{body}"


def _new_pdf():
    """A fresh A4 page with a Unicode font registered (family name returned)."""
    pdf = FPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 14, 15)
    pdf.add_page()
    family = "Helvetica"
    for regular, bold in _FONT_CANDIDATES:
        if os.path.exists(regular):
            pdf.add_font("Uni", "", regular)
            pdf.add_font("Uni", "B", bold if os.path.exists(bold) else regular)
            family = "Uni"
            break
    pdf.set_font(family, size=10)
    return pdf, family


def _logo_stream(logo: str):
    """Return a BytesIO of the base64 logo, or None if absent/undecodable."""
    if not logo:
        return None
    try:
        return io.BytesIO(base64.b64decode(logo))
    except Exception:
        return None


def _txt(value) -> str:
    return "" if value is None else str(value)


# ──────────────────────────────────────────────────────────────────────────────
# Rental invoice
# ──────────────────────────────────────────────────────────────────────────────
def build_invoice_pdf(deal: dict, charges: list[dict], business_name: str,
                      lang: str = "tr", logo: str = "") -> bytes:
    """Return the rental invoice as PDF bytes, in `lang` (validated)."""
    if lang not in LANGUAGES:
        lang = "tr"
    T = lambda k: t_lang(k, lang)

    pdf, F = _new_pdf()
    L, R = 15, 195            # left / right page edges (usable width 180mm)
    right_x = 120

    billable = [c for c in charges if c["type"] != "deposit"]
    deposit = sum(c["amount"] for c in charges if c["type"] == "deposit") \
        or int(deal.get("deposit") or 0)
    grand_total = sum(c["amount"] for c in billable) or int(deal.get("total_amount") or 0)
    balance_due = grand_total - deposit
    days = int(deal.get("rental_days") or 0)
    daily_rate = int(deal.get("daily_rate") or 0)

    # ── header: brand (left) + invoice meta (right) ──────────────────────────
    top = 14
    y = top
    stream = _logo_stream(logo)
    if stream is not None:
        try:
            pdf.image(stream, x=L, y=y, w=38)
            y += 17
        except Exception:
            pass
    pdf.set_xy(L, y)
    pdf.set_font(F, "B", 15)
    pdf.set_text_color(*_TEXT)
    pdf.cell(95, 7, text=_txt(business_name), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(L)
    pdf.set_font(F, "", 8)
    pdf.set_text_color(*_MUTED)
    pdf.cell(95, 4, text=APP_TAGLINE.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    left_bottom = pdf.get_y()

    issuer_name = deal.get("created_by_name") or deal.get("created_by") or "—"
    issuer_role = deal.get("created_by_role") or ""
    issuer_role_label = T(ROLE_LABEL_KEY.get(issuer_role, "")) if issuer_role else ""
    issued_by = issuer_name + (f" ({issuer_role_label})" if issuer_role_label else "")
    meta = [
        (T("invoice_no"), _txt(deal.get("deal_id", ""))),
        (T("invoice_date"), _txt(deal.get("created_at", ""))[:10]),
        (T("invoice_issued_by"), issued_by),
    ]
    pdf.set_xy(right_x, top)
    pdf.set_font(F, "B", 22)
    pdf.set_text_color(*_ACCENT)
    pdf.cell(R - right_x, 11, text=T("invoice_heading"), align="R",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(F, "", 9)
    pdf.set_text_color(*_MUTED)
    for label, val in meta:
        pdf.set_x(right_x)
        pdf.cell(R - right_x, 5, text=f"{label}: {val}", align="R",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    right_bottom = pdf.get_y()

    y = max(left_bottom, right_bottom) + 2
    pdf.set_draw_color(*_ACCENT)
    pdf.set_line_width(0.6)
    pdf.line(L, y, R, y)
    y += 5

    # ── bill-to / vehicle ────────────────────────────────────────────────────
    start = _txt(deal.get("start_dt", ""))[:16].replace("T", " ")
    end = _txt(deal.get("end_dt", ""))[:16].replace("T", " ")
    pdf.set_xy(L, y)
    pdf.set_font(F, "B", 8)
    pdf.set_text_color(*_MUTED)
    pdf.cell(90, 5, text=T("bill_to").upper(), new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(85, 5, text=T("invoice_vehicle").upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    row_y = pdf.get_y()
    pdf.set_xy(L, row_y)
    pdf.set_font(F, "B", 10)
    pdf.set_text_color(*_TEXT)
    pdf.cell(90, 5, text=_txt(deal.get("client_name", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(L)
    pdf.set_font(F, "", 9)
    pdf.set_text_color(*_MUTED)
    pdf.cell(90, 5, text=f'{T("col_phone")}: {deal.get("phone", "") or "—"}',
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(L)
    pdf.cell(90, 5, text=f'{T("col_idno")}: {deal.get("id_passport", "") or "—"}',
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    veh_line = f'{deal.get("vehicle_id", "")}  {deal.get("make_model", "")}'
    pdf.set_xy(right_x - 10, row_y)
    pdf.set_font(F, "B", 10)
    pdf.set_text_color(*_TEXT)
    pdf.cell(R - (right_x - 10), 5, text=veh_line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(right_x - 10)
    pdf.set_font(F, "", 9)
    pdf.set_text_color(*_MUTED)
    pdf.cell(R - (right_x - 10), 5, text=_txt(deal.get("license_plate", "") or "—"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(right_x - 10)
    pdf.cell(R - (right_x - 10), 5, text=f'{T("invoice_period")}: {start} -> {end}',
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    y = pdf.get_y() + 4

    # ── line items ───────────────────────────────────────────────────────────
    w_desc, w_qty, w_unit, w_amt = 90, 25, 32, 33
    pdf.set_xy(L, y)
    pdf.set_font(F, "B", 8)
    pdf.set_text_color(*_MUTED)
    pdf.set_fill_color(*_LIGHT)
    pdf.cell(w_desc, 7, text=T("invoice_desc").upper(), border=0, fill=True)
    pdf.cell(w_qty, 7, text=T("invoice_qty").upper(), align="R", border=0, fill=True)
    pdf.cell(w_unit, 7, text=T("invoice_unit").upper(), align="R", border=0, fill=True)
    pdf.cell(w_amt, 7, text=T("invoice_amount").upper(), align="R", border=0, fill=True,
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font(F, "", 10)
    pdf.set_text_color(*_TEXT)

    def _item(label, qty, unit, amount):
        pdf.set_x(L)
        pdf.cell(w_desc, 7, text=label, border="B")
        pdf.cell(w_qty, 7, text=qty, align="R", border="B")
        pdf.cell(w_unit, 7, text=unit, align="R", border="B")
        pdf.cell(w_amt, 7, text=_eur(amount), align="R", border="B",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_draw_color(*_LIGHT)
    if billable:
        for c in billable:
            ctype = c["type"]
            label = T(_LINE_LABEL.get(ctype, ctype))
            if ctype == "rental":
                _item(label, str(days), _eur(daily_rate), c["amount"])
            else:
                _item(label, "1", _eur(c["amount"]), c["amount"])
    else:
        _item(T("invoice_line_rental"), str(days), _eur(daily_rate), grand_total)

    # ── totals (right aligned) ───────────────────────────────────────────────
    y = pdf.get_y() + 3
    tot_x = 120
    tot_lbl, tot_val = 45, 30
    pdf.set_xy(tot_x, y)
    pdf.set_font(F, "", 10)
    pdf.set_text_color(*_TEXT)
    pdf.cell(tot_lbl, 6, text=T("invoice_subtotal"))
    pdf.cell(tot_val, 6, text=_eur(grand_total), align="R",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if deposit > 0:
        pdf.set_x(tot_x)
        pdf.set_text_color(*_MUTED)
        pdf.cell(tot_lbl, 6, text=f'- {T("invoice_line_deposit")}')
        pdf.cell(tot_val, 6, text=f'- {_eur(deposit)}', align="R",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(tot_x)
    pdf.set_draw_color(*_TEXT)
    pdf.set_line_width(0.4)
    yy = pdf.get_y()
    pdf.line(tot_x, yy, tot_x + tot_lbl + tot_val, yy)
    pdf.set_font(F, "B", 13)
    pdf.set_text_color(*_TEXT)
    pdf.cell(tot_lbl, 9, text=T("invoice_total"))
    pdf.set_text_color(*_ACCENT)
    pdf.cell(tot_val, 9, text=_eur(balance_due), align="R",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # signed / unsigned
    signed = str(deal.get("contract_signed", "No")).lower() in ("yes", "1", "true")
    pdf.set_xy(L, max(pdf.get_y(), y) + 2)
    pdf.set_font(F, "B", 9)
    pdf.set_text_color(*_ACCENT)
    pdf.cell(0, 6, text=T("invoice_signed") if signed else T("invoice_unsigned"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── terms & conditions ───────────────────────────────────────────────────
    terms = rental_terms(lang)
    pdf.ln(2)
    pdf.set_x(L)
    pdf.set_font(F, "B", 9)
    pdf.set_text_color(*_TEXT)
    pdf.multi_cell(0, 5, text=_txt(terms.get("title", "")),
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(F, "", 7.5)
    pdf.set_text_color(*_MUTED)
    for i, rule in enumerate(terms.get("rules", []), start=1):
        pdf.set_x(L)
        pdf.multi_cell(0, 3.8, text=f"{i}. {rule}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── footer ───────────────────────────────────────────────────────────────
    pdf.ln(2)
    pdf.set_x(L)
    pdf.set_font(F, "", 8)
    pdf.set_text_color(*_MUTED)
    pdf.multi_cell(0, 4, text=f'{T("invoice_thanks")}  -  {T("invoice_footer")}',
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())


# ──────────────────────────────────────────────────────────────────────────────
# Software-license invoice
# ──────────────────────────────────────────────────────────────────────────────
def build_license_invoice_pdf(d: dict) -> bytes:
    """Return the software-license invoice as PDF bytes (UI-language labels)."""
    pdf, F = _new_pdf()
    L, R = 15, 195
    right_x = 120
    from data.repositories import app_settings as app_cfg
    logo = app_cfg.get_logo()

    top = 14
    y = top
    stream = _logo_stream(logo)
    if stream is not None:
        try:
            pdf.image(stream, x=L, y=y, w=38)
            y += 17
        except Exception:
            pass
    pdf.set_xy(L, y)
    pdf.set_font(F, "B", 15)
    pdf.set_text_color(*_TEXT)
    pdf.cell(95, 7, text=APP_NAME, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(L)
    pdf.set_font(F, "", 8)
    pdf.set_text_color(*_MUTED)
    pdf.cell(95, 4, text=APP_TAGLINE.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    left_bottom = pdf.get_y()

    pdf.set_xy(right_x, top)
    pdf.set_font(F, "B", 20)
    pdf.set_text_color(*_ACCENT)
    pdf.cell(R - right_x, 11, text=t("license_invoice_title"), align="R",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(F, "", 9)
    pdf.set_text_color(*_MUTED)
    for label, val in [(t("invoice_no"), _txt(d.get("invoice_no", ""))),
                       (t("invoice_date"), _txt(d.get("date", "")))]:
        pdf.set_x(right_x)
        pdf.cell(R - right_x, 5, text=f"{label}: {val}", align="R",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    right_bottom = pdf.get_y()

    y = max(left_bottom, right_bottom) + 2
    pdf.set_draw_color(*_ACCENT)
    pdf.set_line_width(0.6)
    pdf.line(L, y, R, y)
    y += 5

    pdf.set_xy(L, y)
    pdf.set_font(F, "B", 8)
    pdf.set_text_color(*_MUTED)
    pdf.cell(0, 5, text=t("license_licensee").upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(L)
    pdf.set_font(F, "B", 11)
    pdf.set_text_color(*_TEXT)
    pdf.cell(0, 6, text=_txt(d.get("licensee", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    period = f'{d.get("start_year")} - {d.get("end_year")}'
    rows = [
        (t("license_product"), f"{APP_NAME} · {APP_TAGLINE} v{APP_VERSION}"),
        (t("license_period"), period),
        (t("license_years"), str(d.get("years") or 1)),
        (t("license_purchase_date"), _txt(d.get("date", ""))),
    ]
    pdf.set_font(F, "", 10)
    for k, v in rows:
        pdf.set_x(L)
        pdf.set_text_color(*_MUTED)
        pdf.cell(70, 7, text=k, border="B")
        pdf.set_text_color(*_TEXT)
        pdf.cell(110, 7, text=_txt(v), border="B", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(4)
    pdf.set_x(L)
    pdf.set_draw_color(*_TEXT)
    pdf.set_line_width(0.4)
    yy = pdf.get_y()
    pdf.line(L, yy, R, yy)
    pdf.set_font(F, "B", 14)
    pdf.set_text_color(*_TEXT)
    pdf.cell(120, 10, text=t("invoice_total"))
    pdf.set_text_color(*_ACCENT)
    pdf.cell(60, 10, text=_eur(int(d.get("amount_cents") or 0)), align="R",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(3)
    pdf.set_x(L)
    pdf.set_font(F, "", 8)
    pdf.set_text_color(*_MUTED)
    pdf.multi_cell(0, 4, text=f'{t("invoice_thanks")}  -  {t("invoice_footer")}',
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())
