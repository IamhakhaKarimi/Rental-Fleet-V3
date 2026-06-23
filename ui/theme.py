"""
Visual theme for the whole app.

Typeface system — ONE minimalistic sans-serif for the whole app (loaded from Google
Fonts, free, with full Turkish/Albanian glyph coverage):
  - Inter -> everything: brand wordmark, page titles, KPI numbers, labels, tables,
    controls. Both --font-display and --font-body resolve to Inter; the two CSS
    variables are kept only so size/weight intent stays legible at call sites.

inject_theme() is called once in app.py and:
  - imports the fonts
  - defines the colour tokens as CSS variables
  - applies the fonts and a calm, minimal base style to Streamlit's widgets
"""

import streamlit as st

# Colour tokens — single accent (blue), neutral greys, status colours only as accents.
# ── Brand palette: "Onyx" — a premium dark-sidebar identity for a high-end car
# rental. A clean near-white content canvas + neutral near-black ink keep the work
# area calm and legible; a deep emerald accent carries CTAs, links and the active
# nav state. The navigation sidebar itself is near-black (styled in _POLISH_CSS).
# Status hues stay semantic and distinct from the emerald accent.
TOKENS = {
    "bg": "#FAFAF9",        # clean near-white content canvas
    "surface": "#F4F3F1",   # subtle surface for tiles / cards
    "text": "#1A1C1E",      # neutral near-black ink
    "muted": "#6B7280",     # cool grey
    "border": "#EAE8E3",    # hairline
    "accent": "#0B7A55",    # deep emerald — CTAs, links, focus (AA on light)
    "accent_hover": "#095E42",
    "ok": "#15803D",        # status: Available
    "info": "#2563EB",      # status: Rented
    "warn": "#D97706",      # status: Maintenance / due-soon
    "danger": "#DC2626",    # status: overdue / delete
    "archived": "#9CA3AF",  # neutral grey
}

FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Inter:wght@400;500;600;700;800&display=swap');"
)


# ── UX polish layer ──────────────────────────────────────────────────────────
# A second, plain-string stylesheet injected after the themed CSS above. Kept as a
# non-f-string so literal CSS braces need no escaping. It only refines depth,
# motion, focus and roundness on top of the existing tokens — no colour/brand
# changes — so it is safe across every page. Motion respects prefers-reduced-motion.
_POLISH_CSS = """
<style>
/* Gentle, meaningful motion — only when the user hasn't asked to reduce it */
@media (prefers-reduced-motion: no-preference) {
  .stButton > button,
  .kpi,
  div[data-testid="stVerticalBlockBorderWrapper"],
  [data-testid="stExpander"] details { transition: transform .16s ease, box-shadow .16s ease, border-color .16s ease; }
}
@media (prefers-reduced-motion: reduce) {
  .stButton > button:hover, .kpi:hover,
  div[data-testid="stVerticalBlockBorderWrapper"]:hover { transform: none !important; }
}

/* Keyboard accessibility: clear focus rings (never removed) */
.stButton > button:focus-visible,
.stTextInput input:focus-visible,
.stNumberInput input:focus-visible,
[data-baseweb="select"] [role="button"]:focus-visible {
  outline: 2px solid var(--accent) !important; outline-offset: 2px !important;
}

/* Buttons: soft depth + tactile press */
.stButton > button { box-shadow: 0 1px 2px rgba(15,23,42,.06); }
.stButton > button:hover { transform: translateY(-1px); box-shadow: 0 6px 16px -8px rgba(15,23,42,.30); }
.stButton > button:active { transform: translateY(0); box-shadow: 0 1px 2px rgba(15,23,42,.12); }
.stButton > button[kind="primary"] { box-shadow: 0 2px 10px -3px rgba(11,122,85,.40); }
[class*="st-key-fldel_"] button,
[class*="st-key-dzreset_"] button { box-shadow: 0 2px 10px -3px rgba(220,38,38,.45) !important; }

/* Bordered containers read as real cards */
div[data-testid="stVerticalBlockBorderWrapper"] {
  border-radius: 14px !important; box-shadow: 0 1px 2px rgba(15,23,42,.04);
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover { box-shadow: 0 10px 28px -16px rgba(15,23,42,.22); }

/* KPI tiles lift slightly on hover */
.kpi:hover { transform: translateY(-2px); box-shadow: 0 12px 26px -14px rgba(15,23,42,.24); }

/* Inputs: rounder with an accent focus glow */
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"] { border-radius: 10px !important; }
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within {
  border-color: var(--accent) !important; box-shadow: 0 0 0 3px rgba(11,122,85,.16) !important;
}

/* Dataframes: contained and rounded */
[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }

/* Tabs: tidy spacing, accented active tab */
.stTabs [data-baseweb="tab-list"] { gap: 4px; }
.stTabs [aria-selected="true"] { color: var(--accent) !important; }

/* Expanders + dialog: rounder, with a hover surface on the summary */
[data-testid="stExpander"] details { border-radius: 12px !important; }
[data-testid="stExpander"] summary:hover { background: var(--surface); }
div[role="dialog"] { border-radius: 16px !important; }

/* Quieter dividers, more readable captions, consistent links */
hr { opacity: .7; }
[data-testid="stCaptionContainer"] { line-height: 1.5; }
a { color: var(--accent); }

/* Visitor home hero (customer-facing browse banner) */
.visitor-hero {
  background: linear-gradient(135deg, #101826 0%, #0B7A55 100%);
  color: #fff; border-radius: 18px; padding: 30px 28px; margin-bottom: 18px;
  box-shadow: 0 16px 40px -20px rgba(11,122,85,.45);
}
.visitor-hero .vh-brand { font-family: var(--font-display); font-weight: 700;
  font-size: 1.05rem; opacity: .9; letter-spacing: .02em; }
.visitor-hero .vh-title { font-family: var(--font-display); font-weight: 700;
  font-size: 1.95rem; margin-top: 6px; line-height: 1.1; }
.visitor-hero .vh-sub { font-size: 1rem; opacity: .92; margin-top: 8px; max-width: 640px; }
@media (max-width: 640px) {
  .visitor-hero { padding: 22px 18px; }
  .visitor-hero .vh-title { font-size: 1.45rem; }
}

/* ===== Minimalistic two-state navigation sidebar (Gemini-style) =====
   Always visible. A custom toggle (ui/nav.py → session_state['nav_expanded'])
   switches between an EXPANDED icon+label list and a slim COLLAPSED icon rail —
   never hidden, so the section icons stay reachable. Page content reflows in both
   states because the sidebar keeps a real (non-zero) flex width. Idle rows are
   muted grey with a rounded inset highlight on hover; the active section keeps a
   soft-emerald highlight. The per-state width / alignment / label-hiding, plus the
   mobile icon-rail, are injected per-run at the end of inject_theme(). */
section[data-testid="stSidebar"] {
  background: #FFFFFF !important;
  border-right: 1px solid var(--border);
  /* Always on screen — collapse is driven by our OWN toggle (ui/nav.py →
     session_state['nav_expanded']), never Streamlit's native hide. The width and
     row alignment for each state are injected per-run at the end of inject_theme(). */
  transform: none !important; visibility: visible !important; margin-left: 0 !important;
}
/* Hide Streamlit's native collapse/expand/resize controls — our toggle replaces them. */
[data-testid="stSidebarCollapseButton"], [data-testid="stExpandSidebarButton"],
section[data-testid="stSidebar"] [data-testid="stSidebarResizeHandle"] { display: none !important; }
/* Small inset so the rounded row highlight keeps a margin from the edges. */
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding: 10px 8px 16px !important; }

/* Keep page content clear of the sidebar. A sidebar at its natural width
   (~200px+) lets Streamlit's flex layout offset the main column correctly; the
   old 78px rail was far below that, so the absolutely-positioned stMain
   collapsed back to x=0 and rendered *under* the rail, clipping the page's left
   edge (titles, the timeline's vehicle names). The 236px width above resolves
   that. This positioning-context rule on the main wrapper is a belt-and-braces
   safeguard so stMain can never escape its flex column again. */
[data-testid="stAppViewContainer"] > div:has([data-testid="stMain"]) {
  position: relative !important;
}

/* Full-height flex column so the footer pins to the bottom (with a fallback gap).
   align-items:stretch lets rows fill the sidebar width. */
section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"]:first-of-type {
  min-height: calc(100vh - 46px); display: flex; flex-direction: column; align-items: stretch; gap: 4px;
}
section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"]:first-of-type > div:has(.rail-spacer) {
  flex: 1 1 auto;
}
.rail-spacer { min-height: 8vh; }

/* Brand header: gradient mark + name + tagline, with a hairline divider below */
.rail-brand-row {
  display: flex; align-items: center; gap: 11px; width: 100%;
  padding: 2px 10px 12px; margin-bottom: 4px; border-bottom: 1px solid var(--border);
}
.rail-brand-mark {
  width: 38px; height: 38px; border-radius: 11px; flex: 0 0 auto;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #0B7A55, #34D399); color: #fff;
  font-family: var(--font-display); font-weight: 700; font-size: 1.05rem;
  box-shadow: 0 6px 16px -7px rgba(11,122,85,.55);
}
.rail-brand-text { min-width: 0; }
.rbt-name { font-family: var(--font-display); font-weight: 700; font-size: .9rem; letter-spacing: -.01em;
  color: var(--text); line-height: 1.15; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rbt-tag { font-size: .6rem; letter-spacing: .14em; text-transform: uppercase;
  color: var(--muted); margin-top: 2px; }

/* Account row in the footer: avatar + name + role */
.rail-user-row { display: flex; align-items: center; gap: 10px; width: 100%; padding: 10px 10px 2px; }
.rail-user-avatar {
  width: 34px; height: 34px; border-radius: 50%; flex: 0 0 auto;
  display: flex; align-items: center; justify-content: center;
  background: var(--surface); border: 1px solid var(--border);
  color: var(--text); font-weight: 600; font-size: .82rem;
}
.rail-user-text { min-width: 0; }
.ru-name { font-weight: 600; font-size: .84rem; color: var(--text); line-height: 1.15;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ru-role { font-size: .7rem; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* Nav / footer rows: left-aligned icon + label, rounded inset highlight.
   (Per-state alignment/width — and label-hiding in the collapsed rail — are set in
   the dynamic block at the end of inject_theme.) */
section[data-testid="stSidebar"] button[data-testid^="stBaseButton"] {
  width: 100% !important; min-width: 0 !important; height: auto !important;
  padding: 10px 12px !important; margin: 1px 0 !important;
  background: transparent !important; border: none !important; box-shadow: none !important;
  color: #4B5563 !important; font-size: .92rem !important; font-weight: 500 !important; line-height: 1.3 !important;
  border-radius: 10px !important; white-space: nowrap !important; text-align: left !important;
  display: flex !important; align-items: center !important; justify-content: flex-start !important;
  transition: background .14s ease, color .14s ease !important;
}
section[data-testid="stSidebar"] button[data-testid^="stBaseButton"]:hover {
  background: rgba(17,24,39,.05) !important; color: var(--text) !important;
  transform: none !important; box-shadow: none !important;
}
/* Streamlit centers a button's label via two nested flex wrappers (jc:center);
   pin them left so every row's icon lines up in one column. */
section[data-testid="stSidebar"] button[data-testid^="stBaseButton"] > div,
section[data-testid="stSidebar"] button[data-testid^="stBaseButton"] > div > span {
  justify-content: flex-start !important; width: 100% !important;
}
/* Material icon inside a row: a touch larger than the label, with breathing room */
section[data-testid="stSidebar"] button[data-testid^="stBaseButton"] span[role="img"] {
  font-size: 1.3rem !important; margin-right: 11px !important; flex: 0 0 auto !important;
}
/* Active section: soft-emerald rounded highlight, emerald icon + label */
section[data-testid="stSidebar"] [class*="st-key-nav_"] button[kind="primary"] {
  background: rgba(11,122,85,.10) !important; color: var(--accent) !important; font-weight: 600 !important;
}
section[data-testid="stSidebar"] [class*="st-key-nav_"] button[kind="primary"]:hover {
  background: rgba(11,122,85,.16) !important; color: var(--accent) !important;
}
/* An overdue reminders bell stays a real alarm (filled red row) */
section[data-testid="stSidebar"] [class*="st-key-notif_bell"] button[kind="primary"],
section[data-testid="stSidebar"] [class*="st-key-notif_bell"] button[kind="primary"]:hover {
  background: var(--danger) !important; color: #fff !important;
}
section[data-testid="stSidebar"] [class*="st-key-notif_bell"] button[kind="primary"] span[role="img"] {
  color: #fff !important;
}
/* Logout row: a quiet danger tint on hover */
section[data-testid="stSidebar"] [class*="st-key-logout_btn"] button:hover {
  background: rgba(220,38,38,.08) !important; color: var(--danger) !important;
}
/* Keyboard focus ring (WCAG 2.4.7) */
section[data-testid="stSidebar"] button[data-testid^="stBaseButton"]:focus-visible {
  outline: 2px solid var(--accent) !important; outline-offset: 2px !important;
}
</style>
"""


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
        --font-display: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
        --font-body: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
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
    /* Badge text uses a darker shade of each status hue (not the token itself) so
       the small pill text clears WCAG AA (4.5:1) on its light tint; the coloured
       dot (::before, currentColor) stays clearly status-coded. */
    .badge.ok {{ color:#166534; background: rgba(21,128,61,.12); }}
    .badge.info {{ color:#1D4ED8; background: rgba(37,99,235,.12); }}
    .badge.warn {{ color:#92400E; background: rgba(217,119,6,.16); }}
    .badge.danger {{ color:#B91C1C; background: rgba(220,38,38,.12); }}
    .badge.archived {{ color:#57534E; background: rgba(168,162,158,.22); }}

    /* KPI tile — uppercase label + optional icon chip on top, a large
       tabular-figure value below (tnum/lnum so digits align like a fintech stat). */
    .kpi {{ position: relative; background: var(--surface); border: 1px solid var(--border);
        border-radius: 14px; padding: 13px 15px 15px; display: flex; flex-direction: column;
        gap: 8px; min-height: 94px; box-shadow: 0 1px 2px rgba(15,23,42,.04); }}
    .kpi .kpi-head {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
    .kpi .kpi-label {{ font-size: 0.72rem; font-weight: 600; letter-spacing: .06em;
        text-transform: uppercase; color: var(--muted); line-height: 1.3; }}
    .kpi .kpi-chip {{ width: 30px; height: 30px; border-radius: 9px; flex: 0 0 auto;
        display: flex; align-items: center; justify-content: center; font-size: .92rem;
        line-height: 1; background: rgba(11,122,85,.10); }}
    .kpi .kpi-value {{ font-family: var(--font-display); font-weight: 700; font-size: 2rem;
        color: var(--text); line-height: 1; letter-spacing: -.02em;
        font-variant-numeric: tabular-nums lining-nums; font-feature-settings: "tnum" 1, "lnum" 1; }}
    .kpi.accent .kpi-value {{ color: var(--accent); }}
    .kpi.accent .kpi-chip {{ background: rgba(11,122,85,.16); }}

    /* Vehicle photo placeholder (🚘 avatar when no photo is uploaded) */
    .car-ph {{ display:flex; align-items:center; justify-content:center;
        background: var(--surface); border:1px solid var(--border);
        border-radius: 12px; font-size: 3.2rem; color: var(--muted); width:100%; }}

    /* Calculated return highlight */
    .return-box {{ background: linear-gradient(180deg, rgba(11,122,85,.08), rgba(11,122,85,.02));
        border:1px solid rgba(11,122,85,.25); border-radius: 14px; padding: 16px; }}
    .return-box .lbl {{ font-size:.74rem; font-weight:500; letter-spacing:.08em;
        text-transform:uppercase; color: var(--muted); }}
    .return-box .val {{ font-family: var(--font-display); font-weight:700;
        font-size: 1.35rem; color: var(--accent); }}

    /* Buttons: quiet, single accent */
    .stButton > button[kind="primary"] {{ background: var(--accent); border:none; border-radius:10px; }}
    .stButton > button[kind="primary"]:hover {{ background: var(--accent-hover); }}
    /* Nav buttons: keep the emoji+label on one line, ellipsis if truly cramped */
    .stButton > button {{ white-space: nowrap; }}
    /* Danger / alert buttons — Fleet Delete-Archive + the super-admin reset-data
       actions, targeted by widget key prefix (Streamlit emits `st-key-<key>`). */
    [class*="st-key-fldel_"] button,
    [class*="st-key-dzreset_"] button {{
        background: var(--danger) !important; border:1px solid var(--danger) !important;
        color:#fff !important; border-radius:10px; }}
    [class*="st-key-fldel_"] button:hover,
    [class*="st-key-dzreset_"] button:hover {{
        background:#B91C1C !important; border-color:#B91C1C !important; color:#fff !important; }}

    /* Trim default top padding */
    .block-container {{ padding-top: 2.2rem; }}

    /* Keep mobile browsers from auto-inflating text (a cause of pinch-zoom). */
    html {{ -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }}
    /* Per-field labels that appear ONLY on phones, so a stacked table cell still
       says what it is (e.g. "Plate: 34 ABC 12"). Hidden on desktop. */
    .m-label {{ display: none; }}

    /* ── Mobile responsiveness ───────────────────────────────────────────
       On phones, stack every column row vertically and clamp components to the
       viewport so the page fits without the user having to pinch-zoom out. */
    @media (max-width: 640px) {{
        [data-testid="stAppViewContainer"] {{ overflow-x: hidden; }}
        .block-container {{ padding: 0.8rem 0.6rem 2rem !important; max-width: 100% !important; }}
        /* Stack all st.columns rows (nav, KPIs, booking, cards, forms, fleet…) */
        div[data-testid="stHorizontalBlock"] {{ flex-wrap: wrap !important; gap: 0.4rem !important; }}
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"],
        div[data-testid="stHorizontalBlock"] > div {{
            flex: 1 1 100% !important; width: 100% !important; min-width: 0 !important; }}
        /* Nothing wider than the screen; wide tables scroll instead of overflowing */
        iframe, img {{ max-width: 100% !important; }}
        [data-testid="stDataFrame"], [data-testid="stTable"] {{
            max-width: 100% !important; overflow-x: auto !important; }}
        /* Comfortable tap targets (WCAG 44px); nav/action labels wrap when stacked */
        .stButton > button {{ white-space: normal; min-height: 44px; }}
        /* Reveal the per-field mobile labels; hide desktop-only table headers */
        .m-label {{ display: inline; font-weight: 600; color: var(--muted); margin-right: 4px; }}
        .hide-mobile {{ display: none !important; }}
        /* Tame display type so headings don't overflow */
        h1 {{ font-size: 1.5rem !important; }}
        .page-title {{ font-size: 1.25rem; }}
        .kpi .kpi-value {{ font-size: 1.6rem; }}
        .inv-title h1, .brand {{ font-size: 1.3rem !important; }}
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
    st.markdown(_POLISH_CSS, unsafe_allow_html=True)

    # ── Per-run sidebar state: expanded label list ⇄ collapsed icon rail ──────
    # The custom toggle in ui/nav.py flips session_state['nav_expanded']; we inject
    # the matching width + row alignment here, so a toggle simply re-renders the
    # right state. The collapsed rail hides labels via the font-size:0 trick (the
    # icon <span> keeps its own size) rather than re-rendering icon-only in Python.
    # Phones are always the icon rail. Injected last, so it wins over the static
    # rules above on equal specificity.
    expanded = st.session_state.get("nav_expanded", True)
    rail_css = """
      section[data-testid="stSidebar"],
      section[data-testid="stSidebar"] > div:first-child { width: 68px !important; min-width: 68px !important; }
      section[data-testid="stSidebar"] button[data-testid^="stBaseButton"] {
        justify-content: center !important; padding-left: 0 !important; padding-right: 0 !important; }
      section[data-testid="stSidebar"] button[data-testid^="stBaseButton"] > div,
      section[data-testid="stSidebar"] button[data-testid^="stBaseButton"] > div > span { justify-content: center !important; }
      section[data-testid="stSidebar"] button[data-testid^="stBaseButton"] p { font-size: 0 !important; }
      section[data-testid="stSidebar"] button[data-testid^="stBaseButton"] span[role="img"] {
        font-size: 1.3rem !important; margin-right: 0 !important; }
      section[data-testid="stSidebar"] .rail-brand-text,
      section[data-testid="stSidebar"] .rail-user-text { display: none !important; }
      section[data-testid="stSidebar"] .rail-brand-row,
      section[data-testid="stSidebar"] .rail-user-row {
        justify-content: center !important; padding-left: 0 !important; padding-right: 0 !important; }
    """
    expanded_css = """
      section[data-testid="stSidebar"],
      section[data-testid="stSidebar"] > div:first-child { width: 248px !important; min-width: 248px !important; }
    """
    state_css = expanded_css if expanded else rail_css
    st.markdown(
        f"<style>{state_css}\n@media (max-width: 640px) {{{rail_css}}}</style>",
        unsafe_allow_html=True,
    )
