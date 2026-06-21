"""
Small reusable UI building blocks used across pages.

- format_eur(cents): the one place money becomes a human string.
- page_header / section_header: titles with an info dot that shows help on hover.
- status_badge: a coloured status pill.
- kpi_tile: a single headline metric.
"""

import html
import streamlit as st

from config.settings import CURRENCY_SYMBOL, STATUS_TOKEN
from config.i18n import t


def format_eur(cents: int) -> str:
    """Integer cents -> '€30' or '€30.50'. Whole amounts drop the decimals."""
    cents = int(cents or 0)
    whole, rem = divmod(abs(cents), 100)
    sign = "-" if cents < 0 else ""
    body = f"{whole:,}" if rem == 0 else f"{whole:,}.{rem:02d}"
    return f"{sign}{CURRENCY_SYMBOL}{body}"


def _info_dot(help_text: str) -> str:
    if not help_text:
        return ""
    return f'<span class="info-dot" data-tip="{html.escape(help_text)}">i</span>'


def page_header(title_key: str, help_key: str = ""):
    title = t(title_key)
    tip = t(help_key) if help_key else ""
    st.markdown(
        f'<div class="page-head"><span class="page-title">{html.escape(title)}</span>'
        f'{_info_dot(tip)}</div>',
        unsafe_allow_html=True,
    )


def section_header(title_key: str, help_key: str = ""):
    title = t(title_key)
    tip = t(help_key) if help_key else ""
    st.markdown(
        f'<div class="section-title">{html.escape(title)}{_info_dot(tip)}</div>',
        unsafe_allow_html=True,
    )


def status_badge(status: str) -> str:
    """Return badge HTML for a vehicle/rental status (translated label)."""
    token = STATUS_TOKEN.get(status, "archived")
    label = t(status) if status in ("Available", "Rented", "In Garage", "Maintenance", "DELETED") else status
    return f'<span class="badge {token}">{html.escape(label)}</span>'


def kpi_tile(label_key: str, value, accent: bool = False):
    cls = "kpi accent" if accent else "kpi"
    st.markdown(
        f'<div class="{cls}"><div class="kpi-value">{value}</div>'
        f'<div class="kpi-label">{html.escape(t(label_key))}</div></div>',
        unsafe_allow_html=True,
    )
