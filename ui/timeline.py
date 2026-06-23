"""
Fleet occupancy timeline — the signature view.

One horizontal row per vehicle; each rental is a bar across a continuous time
axis. Improvements in this version:
  - Mouse-wheel zoom is OFF (it was frustrating). The wheel now scrolls/pans.
  - Two on-screen buttons at the bottom-right zoom in (+) and out (-).
  - The "now" line carries a small text label ("NOW"/"ŞİMDİ") at its base so it
    can't be mistaken for a rental boundary.
Built on vis-timeline (MIT), loaded from a CDN in the browser.
"""

import json
from datetime import datetime, timedelta

import streamlit.components.v1 as components

from config.i18n import t
from services.scheduling_service import return_state

# rental return-state -> CSS class on the timeline bar
_STATE_CLASS = {"overdue": "overdue", "due_soon": "duesoon", "ok": "rented"}


def render_timeline(vehicles: list[dict], rentals: list[dict]):
    groups = [
        {"id": v["vehicle_id"], "content": f'{v["vehicle_id"]} · {v["make_model"]}'}
        for v in vehicles
    ]

    now = datetime.now()
    items = []
    for r in rentals:
        state, _ = return_state(r["end_dt"], now)
        tip = (
            f'<b>{r["client_name"]}</b><br>'
            f'{t("col_id")}: {r["vehicle_id"]} — {r["make_model"]}<br>'
            f'{t("client_phone")}: {r["phone"]}<br>'
            f'{r["start_dt"][:16].replace("T", " ")} → {r["end_dt"][:16].replace("T", " ")}<br>'
            f'{r["deal_id"]}'
        )
        items.append({
            "id": r["deal_id"], "group": r["vehicle_id"],
            "start": r["start_dt"], "end": r["end_dt"],
            "content": r["client_name"], "title": tip,
            "className": _STATE_CLASS.get(state, "rented"),
        })

    window_start = (now - timedelta(days=3)).strftime("%Y-%m-%d")
    window_end = (now + timedelta(days=21)).strftime("%Y-%m-%d")
    now_label = t("now_label")
    height_px = max(220, 78 + len(groups) * 44)

    html = f"""
    <!DOCTYPE html><html><head><meta charset="utf-8"/>
      <script src="https://unpkg.com/vis-timeline@7.7.3/standalone/umd/vis-timeline-graph2d.min.js"></script>
      <link href="https://unpkg.com/vis-timeline@7.7.3/styles/vis-timeline-graph2d.min.css" rel="stylesheet"/>
      <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600&display=swap');
        body {{ margin:0; font-family:'Plus Jakarta Sans',system-ui,sans-serif; background:transparent; }}
        #tlwrap {{ position:relative; }}
        #tl {{ border:1px solid #EAE8E3; border-radius:14px; padding:6px; background:#fff; }}
        .vis-timeline {{ border:none; font-family:'Plus Jakarta Sans',system-ui,sans-serif; }}
        .vis-labelset .vis-label {{ color:#1A1C1E; font-weight:500; font-size:12.5px; }}
        .vis-time-axis .vis-text {{ color:#6B7280; font-size:11px; }}
        .vis-item {{ border:none; border-radius:7px; color:#fff; font-size:11.5px; font-weight:600; padding:1px 6px; }}
        /* Monochrome urgency ramp — darker = more urgent (state also in the tooltip). */
        .vis-item.rented {{ background:#6B7280; }}    /* active rental — mid grey */
        .vis-item.duesoon {{ background:#3F3F46; }}   /* due within 24h — dark grey */
        .vis-item.overdue {{ background:#DC2626; }}   /* past deadline — ALERT RED */
        .vis-tooltip {{ font-family:'Plus Jakarta Sans',system-ui,sans-serif !important; font-size:12px !important;
            background:#1A1C1E !important; color:#F8FAFC !important; border:none !important;
            border-radius:8px !important; padding:9px 12px !important; line-height:1.5 !important;
            box-shadow:0 10px 25px -5px rgba(0,0,0,.35) !important; }}
        /* "now" custom time line + its bottom text label */
        .vis-custom-time.nowline {{ background-color:#1A1C1E; width:2px; }}
        .vis-custom-time.nowline .vis-custom-time-marker {{
            top:auto !important; bottom:0 !important; background:#1A1C1E; color:#fff;
            font-size:10px; font-weight:700; letter-spacing:.05em; padding:1px 6px;
            border-radius:4px; white-space:nowrap; cursor:default; }}
        /* zoom controls, bottom-right */
        .zoom-controls {{ position:absolute; right:14px; bottom:14px; display:flex;
            flex-direction:column; gap:6px; z-index:50; }}
        .zoom-controls button {{ width:34px; height:34px; border:1px solid #EAE8E3; background:#fff;
            border-radius:8px; font-size:20px; font-weight:700; color:#1A1C1E; cursor:pointer;
            box-shadow:0 2px 6px rgba(0,0,0,.10); line-height:1; }}
        .zoom-controls button:hover {{ background:#F2EFE9; border-color:#1A1C1E; color:#1A1C1E; }}
      </style>
    </head><body>
      <div id="tlwrap">
        <div id="tl"></div>
        <div class="zoom-controls">
          <button title="zoom in" onclick="window.tl && window.tl.zoomIn(0.5)">+</button>
          <button title="zoom out" onclick="window.tl && window.tl.zoomOut(0.5)">&minus;</button>
        </div>
      </div>
      <script>
        var groups = new vis.DataSet({json.dumps(groups)});
        var items  = new vis.DataSet({json.dumps(items)});
        var options = {{
          stack: false,
          orientation: {{ axis: 'top' }},
          showCurrentTime: false,      // we draw our own labelled "now" line
          zoomable: false,             // wheel no longer zooms (use the buttons)
          moveable: true,
          horizontalScroll: true,      // wheel scrolls the time axis instead
          margin: {{ item: 6, axis: 8 }},
          start: '{window_start}', end: '{window_end}',
          tooltip: {{ followMouse: true, overflowMethod: 'flip' }},
          xss: {{ disabled: true }}
        }};
        window.tl = new vis.Timeline(document.getElementById('tl'), items, groups, options);
        window.tl.addCustomTime(new Date(), 'nowline');
        window.tl.setCustomTimeMarker('{now_label}', 'nowline', false);
      </script>
    </body></html>
    """
    components.html(html, height=height_px + 24, scrolling=False)
