"""
Visual theme for the whole app.

Typeface system (loaded from Google Fonts, free, with Turkish glyph coverage):
  - Display  : Space Grotesk  -> brand wordmark, page titles, KPI numbers
  - Body/UI  : Inter          -> everything else (labels, tables, controls)

inject_theme() is called once in app.py and:
  - imports the fonts
  - defines the colour tokens as CSS variables
  - applies the fonts and a calm, minimal base style to Streamlit's widgets
"""

import streamlit as st

# Colour tokens — single accent (blue), neutral greys, status colours only as accents.
TOKENS = {
    "bg": "#FFFFFF",
    "surface": "#F8FAFC",
    "text": "#0F172A",
    "muted": "#64748B",
    "border": "#E2E8F0",
    "accent": "#2563EB",
    "accent_hover": "#1D4ED8",
    "ok": "#16A34A",
    "info": "#2563EB",
    "warn": "#D97706",
    "danger": "#DC2626",
    "archived": "#94A3B8",
}

FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Inter:wght@400;500;600;700&"
    "family=Space+Grotesk:wght@500;600;700&display=swap');"
)


def inject_theme():
    css = f"""
    <style>
    {FONT_IMPORT}

    :root {{
        --bg: {TOKENS['bg']};
        --surface: {TOKENS['surface']};
        --text: {TOKENS['text']};
        --muted: {TOKENS['muted']};
        --border: {TOKENS['border']};
        --accent: {TOKENS['accent']};
        --accent-hover: {TOKENS['accent_hover']};
        --ok: {TOKENS['ok']};
        --info: {TOKENS['info']};
        --warn: {TOKENS['warn']};
        --danger: {TOKENS['danger']};
        --archived: {TOKENS['archived']};
        --font-display: 'Space Grotesk', system-ui, sans-serif;
        --font-body: 'Inter', system-ui, sans-serif;
    }}

    /* Base font on the whole app */
    html, body, [data-testid="stAppViewContainer"], .stMarkdown, p, span, div,
    label, input, textarea, select, button, table {{
        font-family: var(--font-body);
    }}
    h1, h2, h3, h4 {{ font-family: var(--font-display); letter-spacing: -0.01em; }}

    /* Sidebar brand */
    .bcr-brand {{ font-family: var(--font-display); font-weight: 700;
        font-size: 1.2rem; color: var(--text); line-height: 1.1; }}
    .bcr-brand small {{ display:block; font-family: var(--font-body); font-weight: 500;
        font-size: 0.72rem; letter-spacing: .12em; text-transform: uppercase;
        color: var(--muted); margin-top: 2px; }}

    /* Page header with hover help */
    .page-head {{ display:flex; align-items:center; gap:10px; margin: 2px 0 2px; }}
    .page-title {{ font-family: var(--font-display); font-weight: 600;
        font-size: 1.55rem; color: var(--text); }}
    .section-title {{ font-family: var(--font-display); font-weight: 600;
        font-size: 1.08rem; color: var(--text); margin: 6px 0 2px; display:flex;
        align-items:center; gap:8px; }}
    .info-dot {{ position: relative; display:inline-flex; align-items:center;
        justify-content:center; width:18px; height:18px; border-radius:50%;
        background: var(--surface); border:1px solid var(--border);
        color: var(--muted); font-size: 11px; font-weight:700; cursor: help; }}
    .info-dot:hover::after {{ content: attr(data-tip); position:absolute; left:24px; top:-4px;
        width: max-content; max-width: 320px; background: #0f172a; color: #f8fafc;
        padding: 8px 11px; border-radius: 8px; font-family: var(--font-body);
        font-weight: 400; font-size: 12px; line-height: 1.45; z-index: 9999;
        box-shadow: 0 10px 25px -5px rgba(0,0,0,.35); }}

    /* Status badge */
    .badge {{ display:inline-flex; align-items:center; gap:6px; padding: 2px 10px;
        border-radius: 999px; font-size: 0.78rem; font-weight: 600; }}
    .badge::before {{ content:''; width:7px; height:7px; border-radius:50%; background: currentColor; }}
    .badge.ok {{ color: var(--ok); background: rgba(22,163,74,.10); }}
    .badge.info {{ color: var(--info); background: rgba(37,99,235,.10); }}
    .badge.warn {{ color: var(--warn); background: rgba(217,119,6,.12); }}
    .badge.danger {{ color: var(--danger); background: rgba(220,38,38,.10); }}
    .badge.archived {{ color: var(--archived); background: rgba(148,163,184,.15); }}

    /* KPI tile */
    .kpi {{ background: var(--surface); border:1px solid var(--border);
        border-radius: 14px; padding: 14px 16px; }}
    .kpi .kpi-value {{ font-family: var(--font-display); font-weight: 700;
        font-size: 1.9rem; color: var(--text); line-height: 1; }}
    .kpi .kpi-label {{ font-size: 0.78rem; font-weight: 500; letter-spacing: .04em;
        text-transform: uppercase; color: var(--muted); margin-top: 6px; }}
    .kpi.accent .kpi-value {{ color: var(--accent); }}

    /* Vehicle photo placeholder (🚘 avatar when no photo is uploaded) */
    .car-ph {{ display:flex; align-items:center; justify-content:center;
        background: var(--surface); border:1px solid var(--border);
        border-radius: 12px; font-size: 3.2rem; color: var(--muted); width:100%; }}

    /* Calculated return highlight */
    .return-box {{ background: linear-gradient(180deg, rgba(37,99,235,.06), rgba(37,99,235,.02));
        border:1px solid rgba(37,99,235,.25); border-radius: 14px; padding: 16px; }}
    .return-box .lbl {{ font-size:.74rem; font-weight:500; letter-spacing:.08em;
        text-transform:uppercase; color: var(--muted); }}
    .return-box .val {{ font-family: var(--font-display); font-weight:700;
        font-size: 1.35rem; color: var(--accent); }}

    /* Buttons: quiet, single accent */
    .stButton > button[kind="primary"] {{ background: var(--accent); border:none; border-radius:10px; }}
    .stButton > button[kind="primary"]:hover {{ background: var(--accent-hover); }}
    /* Nav buttons: keep the emoji+label on one line, ellipsis if truly cramped */
    .stButton > button {{ white-space: nowrap; }}

    /* Trim default top padding */
    .block-container {{ padding-top: 2.2rem; }}

    /* ── Mobile responsiveness ───────────────────────────────────────────
       On phones, stack every column row vertically and clamp components to the
       viewport so the page fits without the user having to pinch-zoom out. */
    @media (max-width: 640px) {{
        [data-testid="stAppViewContainer"] {{ overflow-x: hidden; }}
        .block-container {{ padding: 1rem 0.7rem 2rem !important; max-width: 100% !important; }}
        /* Stack all st.columns rows (nav, KPIs, booking, cards, forms…) */
        div[data-testid="stHorizontalBlock"] {{ flex-wrap: wrap !important; gap: 0.45rem !important; }}
        div[data-testid="stHorizontalBlock"] > div {{
            flex: 1 1 100% !important; width: 100% !important; min-width: 0 !important; }}
        /* Nothing wider than the screen */
        iframe, img, [data-testid="stDataFrame"], [data-testid="stTable"] {{
            max-width: 100% !important; }}
        /* Nav labels can wrap when stacked full-width */
        .stButton > button {{ white-space: normal; }}
        /* Tame display type so headings don't overflow */
        h1 {{ font-size: 1.5rem !important; }}
        .page-title {{ font-size: 1.25rem; }}
        .kpi .kpi-value {{ font-size: 1.6rem; }}
        .inv-title h1, .brand {{ font-size: 1.3rem !important; }}
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
