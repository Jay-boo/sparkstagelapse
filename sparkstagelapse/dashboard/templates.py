# dashboard/templates.py
from __future__ import annotations

import html as html_lib

import pandas as pd


def table_to_html(pdf: pd.DataFrame, title: str, table_id: str,
                   max_height: str = "480px", max_col_width: int = 320) -> str:
    """Renders a DataFrame as a scrollable, filterable, dark-mode-aware HTML table.

    - Sticky header, vertical + horizontal scroll (max_height caps the box).
      Use a fixed px value (not vh) -- in VS Code's notebook output the
      container often auto-sizes to content, so vh can resolve to the full
      content height and silently defeat the scroll.
    - Global text search across all cells
    - Per-column filter inputs; columns with <= 25 unique values get a
      <select> dropdown instead of free text
    - Right-click a cell to "keep only" or "exclude" that exact value on
      its column; active exact filters show as removable chips
    - Right-click a header to pin/unpin that column. Pinning moves the
      column to the leftmost position (most-recently-pinned = furthest
      left) and freezes it there while scrolling horizontally
    - Click a header label to sort (asc/desc toggle)
    - Colors follow prefers-color-scheme (light/dark) automatically
    """
    columns = [str(c) for c in pdf.columns]
    n_rows, n_cols = len(pdf), len(columns)

    col_uniques = {}
    for col in columns:
        try:
            uniq = pdf[col].dropna().astype(str).unique().tolist()
        except Exception:
            uniq = []
        if 0 < len(uniq) <= 25:
            col_uniques[col] = sorted(uniq, key=str.lower)

    def esc(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return ""
        return html_lib.escape(str(v))

    header_cells = "".join(
        f'<th data-col="{i}">'
        f'<span class="th-label" onclick="sortCol_{table_id}({i})">{esc(col)}</span>'
        f'<span class="pin-mark" id="{table_id}_pinmark_{i}"></span>'
        f'<span class="sort-arrow" id="{table_id}_arrow_{i}"></span>'
        f'</th>'
        for i, col in enumerate(columns)
    )

    def filter_cell(i, col):
        if col in col_uniques:
            opts = "".join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in col_uniques[col])
            return (f'<th data-col="{i}"><select data-col="{i}" class="col-filter" '
                    f'onchange="applyFilters_{table_id}()"><option value="">All</option>{opts}</select></th>')
        return (f'<th data-col="{i}"><input data-col="{i}" class="col-filter" type="text" '
                f'placeholder="Filter…" oninput="applyFilters_{table_id}()"></th>')

    filter_row = "".join(filter_cell(i, col) for i, col in enumerate(columns))

    body_rows = []
    for row in pdf.itertuples(index=False, name=None):
        cells = [esc(v) for v in row]
        search_blob = html_lib.escape(" ".join(str(v).lower() for v in row))
        tds = "".join(
            f'<td data-col="{i}" title="{c}">{c}</td>' for i, c in enumerate(cells)
        )
        body_rows.append(f'<tr data-search="{search_blob}">{tds}</tr>')
    body_html = "".join(body_rows)

    col_names_json = "[" + ",".join(f'"{esc(c)}"' for c in columns) + "]"

    return f"""
<div class="spark-wrap" id="{table_id}_wrap">
  <style>
    #{table_id}_wrap {{
      --bg: #ffffff; --bg-alt: #f7f7f8; --border: #ddd; --text: #1a1a1a;
      --text-muted: #6b6b6b; --hover: #f0f3f8; --accent: #3b82f6; --input-bg: #ffffff;
      --chip-bg: #e8edf7; --chip-text: #1f3a63; --menu-bg: #ffffff; --menu-hover: #f0f3f8;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 13px; color: var(--text); margin: 8px 0;
    }}
    @media (prefers-color-scheme: dark) {{
      #{table_id}_wrap {{
        --bg: #1e1e1e; --bg-alt: #252526; --border: #3c3c3c; --text: #e0e0e0;
        --text-muted: #9a9a9a; --hover: #2a2d3a; --accent: #5b9dff; --input-bg: #2d2d2d;
        --chip-bg: #2d3a52; --chip-text: #cfe0ff; --menu-bg: #2d2d2d; --menu-hover: #3a3a3c;
      }}
    }}
    #{table_id}_wrap .spark-toolbar {{
      display: flex; align-items: center; gap: 10px; margin-bottom: 6px; flex-wrap: wrap;
    }}
    #{table_id}_wrap .spark-title {{ font-weight: 600; font-size: 14px; color: var(--text); }}
    #{table_id}_wrap .spark-count {{ color: var(--text-muted); font-size: 12px; }}
    #{table_id}_wrap input.global-search {{
      flex: 1; min-width: 180px; padding: 5px 8px; border: 1px solid var(--border);
      border-radius: 5px; font-size: 12px; background: var(--input-bg); color: var(--text);
    }}
    #{table_id}_wrap button.clear-btn {{
      padding: 5px 10px; border: 1px solid var(--border); border-radius: 5px;
      background: var(--bg-alt); color: var(--text); cursor: pointer; font-size: 12px;
    }}
    #{table_id}_wrap button.clear-btn:hover {{ background: var(--hover); }}
    #{table_id}_wrap .chip-bar {{ display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 6px; }}
    #{table_id}_wrap .chip {{
      display: inline-flex; align-items: center; gap: 6px; background: var(--chip-bg);
      color: var(--chip-text); border-radius: 12px; padding: 3px 8px; font-size: 11px;
    }}
    #{table_id}_wrap .chip .chip-x {{ cursor: pointer; font-weight: bold; opacity: 0.7; }}
    #{table_id}_wrap .chip .chip-x:hover {{ opacity: 1; }}
    #{table_id}_scroll {{
      max-height: {max_height}; overflow: auto; border: 1px solid var(--border); border-radius: 6px;
      background: var(--bg); overscroll-behavior: contain;
    }}
    #{table_id}_wrap table {{
      border-collapse: collapse; width: 100%; white-space: nowrap; background: var(--bg);
    }}
    #{table_id}_wrap th, #{table_id}_wrap td {{
      padding: 6px 10px; border-bottom: 1px solid var(--border); text-align: left;
      max-width: {max_col_width}px; overflow: hidden; text-overflow: ellipsis;
      background: var(--bg); color: var(--text);
    }}
    #{table_id}_wrap thead tr:first-child th {{
      position: sticky; top: 0; background: var(--bg-alt); z-index: 3;
      user-select: none; border-bottom: 2px solid var(--border);
    }}
    #{table_id}_wrap thead tr:nth-child(2) th {{
      position: sticky; top: 29px; background: var(--bg); z-index: 2; padding: 4px 6px;
    }}
    #{table_id}_wrap .th-label {{ cursor: pointer; }}
    #{table_id}_wrap .th-label:hover {{ text-decoration: underline; }}
    #{table_id}_wrap .pin-mark {{ font-size: 10px; margin-left: 4px; }}
    #{table_id}_wrap .pin-mark.active::before {{ content: "📌"; }}
    #{table_id}_wrap .col-filter {{
      width: 100%; box-sizing: border-box; padding: 3px 5px; font-size: 11px;
      border: 1px solid var(--border); border-radius: 4px; background: var(--input-bg); color: var(--text);
    }}
    #{table_id}_wrap tbody tr:hover td {{ background: var(--hover); }}
    #{table_id}_wrap tbody tr.row-hidden {{ display: none; }}
    #{table_id}_wrap tbody td {{ cursor: context-menu; }}
    #{table_id}_wrap .sort-arrow {{ font-size: 10px; margin-left: 4px; color: var(--accent); }}
    #{table_id}_wrap th.pinned-col, #{table_id}_wrap td.pinned-col {{
      position: sticky; z-index: 1; box-shadow: 2px 0 4px rgba(0,0,0,0.15);
    }}
    #{table_id}_wrap thead th.pinned-col {{ z-index: 4; }}
    #{table_id}_ctxmenu {{
      position: fixed; z-index: 1000; background: var(--menu-bg); color: var(--text);
      border: 1px solid var(--border); border-radius: 6px; box-shadow: 0 4px 14px rgba(0,0,0,0.25);
      padding: 4px; font-size: 12px; display: none; min-width: 200px;
    }}
    #{table_id}_ctxmenu .ctx-item {{
      padding: 6px 10px; border-radius: 4px; cursor: pointer; white-space: nowrap;
      overflow: hidden; text-overflow: ellipsis;
    }}
    #{table_id}_ctxmenu .ctx-item:hover {{ background: var(--menu-hover); }}
    #{table_id}_ctxmenu .ctx-label {{
      padding: 4px 10px; color: var(--text-muted); font-size: 10px; text-transform: uppercase;
    }}
  </style>

  <div class="spark-toolbar">
    <span class="spark-title">{esc(title)}</span>
    <span class="spark-count" id="{table_id}_count">{n_rows} rows</span>
    <input class="global-search" id="{table_id}_search" type="text"
           placeholder="Search all columns…" oninput="applyFilters_{table_id}()">
    <button class="clear-btn" onclick="clearFilters_{table_id}()">Clear filters</button>
  </div>

  <div class="chip-bar" id="{table_id}_chips"></div>

  <div id="{table_id}_scroll">
    <table id="{table_id}_table">
      <thead>
        <tr>{header_cells}</tr>
        <tr>{filter_row}</tr>
      </thead>
      <tbody id="{table_id}_tbody">{body_html}</tbody>
    </table>
  </div>

  <div id="{table_id}_ctxmenu"></div>
</div>

<script>
(function() {{
  const tableId = "{table_id}";
  const totalRows = {n_rows};
  const numCols = {n_cols};
  const colNames = {col_names_json};
  let sortState = {{col: null, dir: 1}};
  // pinnedOrder[0] is the leftmost pinned column. Newly pinned columns are
  // unshifted to the front, so "most recently pinned" ends up furthest left.
  let pinnedOrder = [];
  let exactFilters = [];

  const wrap = document.getElementById(tableId + "_wrap");
  const menu = document.getElementById(tableId + "_ctxmenu");

  function allRows() {{
    return [
      wrap.querySelector("thead tr:first-child"),
      wrap.querySelector("thead tr:nth-child(2)"),
      ...wrap.querySelectorAll("#" + tableId + "_tbody tr")
    ];
  }}

  function reorderColumns() {{
    const visualOrder = [
      ...pinnedOrder,
      ...Array.from({{length: numCols}}, (_, i) => i).filter(i => !pinnedOrder.includes(i))
    ];
    allRows().forEach(row => {{
      if (!row) return;
      const cellByCol = {{}};
      row.querySelectorAll(":scope > th, :scope > td").forEach(cell => {{
        cellByCol[cell.dataset.col] = cell;
      }});
      visualOrder.forEach(colIdx => {{
        const cell = cellByCol[colIdx];
        if (cell) row.appendChild(cell);
      }});
    }});
    relayoutStickyOffsets();
  }}

  function relayoutStickyOffsets() {{
    wrap.querySelectorAll("th, td").forEach(el => {{
      el.classList.remove("pinned-col");
      el.style.left = "";
    }});
    if (pinnedOrder.length === 0) return;
    const headerRow = wrap.querySelector("thead tr:first-child");
    let offset = 0;
    pinnedOrder.forEach(colIdx => {{
      const headerCell = headerRow.querySelector('[data-col="' + colIdx + '"]');
      const width = headerCell ? headerCell.getBoundingClientRect().width : 0;
      wrap.querySelectorAll('[data-col="' + colIdx + '"]').forEach(el => {{
        if (el.tagName === "TH" || el.tagName === "TD") {{
          el.classList.add("pinned-col");
          el.style.left = offset + "px";
        }}
      }});
      offset += width;
    }});
  }}

  function updatePinMarks() {{
    for (let i = 0; i < numCols; i++) {{
      const mark = document.getElementById(tableId + "_pinmark_" + i);
      if (mark) mark.classList.toggle("active", pinnedOrder.includes(i));
    }}
  }}

  function pinColumn(colIdx) {{
    pinnedOrder = pinnedOrder.filter(c => c !== colIdx);
    pinnedOrder.unshift(colIdx);
    updatePinMarks();
    reorderColumns();
  }}

  function unpinColumn(colIdx) {{
    pinnedOrder = pinnedOrder.filter(c => c !== colIdx);
    updatePinMarks();
    reorderColumns();
  }}

  function renderChips() {{
    const bar = document.getElementById(tableId + "_chips");
    bar.innerHTML = "";
    exactFilters.forEach((f, idx) => {{
      const chip = document.createElement("span");
      chip.className = "chip";
      const label = (f.exclude ? "≠ " : "= ") + colNames[f.col] + ": " + f.value;
      const textSpan = document.createElement("span");
      textSpan.textContent = label;
      const x = document.createElement("span");
      x.className = "chip-x";
      x.textContent = "✕";
      x.onclick = function() {{
        exactFilters.splice(idx, 1);
        renderChips();
        window["applyFilters_" + tableId]();
      }};
      chip.appendChild(textSpan);
      chip.appendChild(x);
      bar.appendChild(chip);
    }});
  }}

  window["applyFilters_" + tableId] = function() {{
    const globalQ = (document.getElementById(tableId + "_search").value || "").toLowerCase().trim();
    const colFilters = Array.from(wrap.querySelectorAll(".col-filter")).map(el => ({{
      col: parseInt(el.dataset.col, 10),
      val: (el.value || "").toLowerCase().trim()
    }})).filter(f => f.val !== "");

    const rows = wrap.querySelectorAll("#" + tableId + "_tbody tr");
    let visible = 0;
    rows.forEach(row => {{
      let ok = true;
      if (globalQ && !row.dataset.search.includes(globalQ)) ok = false;

      if (ok) {{
        for (const f of colFilters) {{
          const cell = row.querySelector('td[data-col="' + f.col + '"]');
          const text = cell ? cell.textContent.toLowerCase() : "";
          if (!text.includes(f.val)) {{ ok = false; break; }}
        }}
      }}

      if (ok) {{
        for (const f of exactFilters) {{
          const cell = row.querySelector('td[data-col="' + f.col + '"]');
          const text = cell ? cell.textContent : "";
          const matches = text === f.value;
          if (f.exclude ? matches : !matches) {{ ok = false; break; }}
        }}
      }}

      row.classList.toggle("row-hidden", !ok);
      if (ok) visible++;
    }});
    document.getElementById(tableId + "_count").textContent =
      visible === totalRows ? (totalRows + " rows") : (visible + " / " + totalRows + " rows");
  }};

  window["clearFilters_" + tableId] = function() {{
    document.getElementById(tableId + "_search").value = "";
    wrap.querySelectorAll(".col-filter").forEach(el => el.value = "");
    exactFilters = [];
    renderChips();
    window["applyFilters_" + tableId]();
  }};

  window["sortCol_" + tableId] = function(colIdx) {{
    const tbody = document.getElementById(tableId + "_tbody");
    const rows = Array.from(tbody.querySelectorAll("tr"));
    const dir = (sortState.col === colIdx) ? -sortState.dir : 1;
    sortState = {{col: colIdx, dir: dir}};

    rows.sort((a, b) => {{
      const av = a.querySelector('td[data-col="' + colIdx + '"]').textContent.trim();
      const bv = b.querySelector('td[data-col="' + colIdx + '"]').textContent.trim();
      const an = parseFloat(av), bn = parseFloat(bv);
      const bothNum = !isNaN(an) && !isNaN(bn) && av !== "" && bv !== "";
      if (bothNum) return (an - bn) * dir;
      return av.localeCompare(bv) * dir;
    }});
    rows.forEach(r => tbody.appendChild(r));

    for (let i = 0; i < numCols; i++) {{
      const arrow = document.getElementById(tableId + "_arrow_" + i);
      if (arrow) arrow.textContent = (i === colIdx) ? (dir === 1 ? "▲" : "▼") : "";
    }}
  }};

  function hideMenu() {{ menu.style.display = "none"; }}

  function positionMenu(x, y, w, h) {{
    const vw = window.innerWidth, vh = window.innerHeight;
    menu.style.left = Math.min(x, vw - w - 8) + "px";
    menu.style.top = Math.min(y, vh - h - 8) + "px";
    menu.style.display = "block";
  }}

  function addExactFilter(colIdx, value, exclude) {{
    if (!exclude) {{
      exactFilters = exactFilters.filter(f => !(f.col === colIdx && !f.exclude));
    }} else {{
      if (exactFilters.some(f => f.col === colIdx && f.exclude && f.value === value)) return;
    }}
    exactFilters.push({{col: colIdx, value: value, exclude: exclude}});
    renderChips();
    window["applyFilters_" + tableId]();
  }}

  // Right-click a cell -> keep only / exclude that value
  wrap.querySelector("#" + tableId + "_tbody").addEventListener("contextmenu", function(ev) {{
    const td = ev.target.closest("td");
    if (!td) return;
    ev.preventDefault();
    const colIdx = parseInt(td.dataset.col, 10);
    const value = td.textContent;
    const colName = colNames[colIdx];
    const display = value.length > 30 ? value.slice(0, 30) + "…" : value;

    menu.innerHTML = "";
    const label = document.createElement("div");
    label.className = "ctx-label";
    label.textContent = colName;
    menu.appendChild(label);

    const keepItem = document.createElement("div");
    keepItem.className = "ctx-item";
    keepItem.textContent = 'Keep only "' + display + '"';
    keepItem.onclick = function() {{ addExactFilter(colIdx, value, false); hideMenu(); }};
    menu.appendChild(keepItem);

    const excludeItem = document.createElement("div");
    excludeItem.className = "ctx-item";
    excludeItem.textContent = 'Exclude "' + display + '"';
    excludeItem.onclick = function() {{ addExactFilter(colIdx, value, true); hideMenu(); }};
    menu.appendChild(excludeItem);

    positionMenu(ev.clientX, ev.clientY, 220, 90);
  }});

  // Right-click a header -> pin / unpin that column
  wrap.querySelector("thead").addEventListener("contextmenu", function(ev) {{
    const th = ev.target.closest("th");
    if (!th) return;
    ev.preventDefault();
    const colIdx = parseInt(th.dataset.col, 10);
    const colName = colNames[colIdx];
    const isPinned = pinnedOrder.includes(colIdx);

    menu.innerHTML = "";
    const label = document.createElement("div");
    label.className = "ctx-label";
    label.textContent = colName;
    menu.appendChild(label);

    const item = document.createElement("div");
    item.className = "ctx-item";
    item.textContent = isPinned ? "Unpin column" : "Pin column (move to left)";
    item.onclick = function() {{
      if (isPinned) unpinColumn(colIdx); else pinColumn(colIdx);
      hideMenu();
    }};
    menu.appendChild(item);

    positionMenu(ev.clientX, ev.clientY, 220, 60);
  }});

  document.addEventListener("click", function(ev) {{
    if (!menu.contains(ev.target)) hideMenu();
  }});
  document.addEventListener("keydown", function(ev) {{
    if (ev.key === "Escape") hideMenu();
  }});
  window.addEventListener("scroll", hideMenu, true);
}})();
</script>
"""

PAGE_TEMPLATE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Spark Dashboard</title>
<style>
  :root {
    --bg: #ffffff; --bg-alt: #f7f7f8; --border: #ddd; --text: #1a1a1a;
    --text-muted: #6b6b6b; --hover: #f0f3f8; --accent: #3b82f6;
    --ok: #16a34a; --warn: #d97706;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #14161a; --bg-alt: #1a1d23; --border: #2a2e37; --text: #e5e7eb;
      --text-muted: #8b93a1; --hover: #20242c; --accent: #5b9dff;
      --ok: #4ade80; --warn: #fbbf24;
    }
  }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Arial, sans-serif;
    background: var(--bg); color: var(--text); margin: 0; padding: 0;
  }
  header {
    position: sticky; top: 0; z-index: 10; background: var(--bg-alt);
    border-bottom: 1px solid var(--border); padding: 14px 24px;
    display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
  }
  header h1 {
    font-size: 15px; font-weight: 700; margin: 0; color: var(--text);
    display: flex; align-items: center; gap: 8px;
  }
  header .subtitle {
    font-size: 11.5px; color: var(--text-muted); margin: 0;
  }
  .header-spacer { flex: 1; }
  #status {
    font-size: 11.5px; color: var(--text-muted); display: flex; align-items: center; gap: 6px;
  }
  #status .dot {
    width: 7px; height: 7px; border-radius: 50%; background: var(--warn);
    display: inline-block; transition: background 0.2s;
  }
  #status.connected .dot { background: var(--ok); }
  #table-count {
    font-size: 11.5px; color: var(--text-muted); background: var(--bg);
    border: 1px solid var(--border); border-radius: 10px; padding: 3px 10px;
  }
  #clear-btn {
    font-size: 11.5px; padding: 5px 11px; border: 1px solid var(--border);
    border-radius: 6px; background: var(--bg); color: var(--text); cursor: pointer;
  }
  #clear-btn:hover { background: var(--hover); }
  main { padding: 20px 24px 60px; max-width: 1400px; margin: 0 auto; }
  #empty-state {
    text-align: center; color: var(--text-muted); font-size: 13px;
    padding: 80px 20px; border: 1px dashed var(--border); border-radius: 12px; margin-top: 20px;
  }
  .table-card {
    background: var(--bg-alt); border: 1px solid var(--border); border-radius: 12px;
    padding: 14px 16px; margin-bottom: 18px; animation: fadeIn 0.35s ease;
  }
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(-6px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .table-card .card-meta {
    display: flex; align-items: center; gap: 8px; margin-bottom: 8px;
    font-size: 11px; color: var(--text-muted);
  }
  .table-card .latest-pill {
    background: var(--accent); color: #fff; border-radius: 8px;
    padding: 1px 8px; font-size: 10px; font-weight: 700; letter-spacing: 0.03em;
  }
  .table-card .card-time { cursor: default; }
</style>
</head>
<body>
  <header>
    <h1>⚡ Spark Dashboard</h1>
    <span class="subtitle">le plus récent en haut, le plus ancien en bas</span>
    <div class="header-spacer"></div>
    <span id="table-count">0 table(s)</span>
    <button id="clear-btn" title="Vide uniquement la vue locale — les tables restent en mémoire côté serveur, reconnectez-vous (F5) pour les revoir">Effacer la vue</button>
    <span id="status"><span class="dot"></span><span id="status-text">connexion…</span></span>
  </header>
  <main>
    <div id="empty-state">En attente de la première table… lancez <code>display(df)</code> depuis votre script.</div>
    <div id="container"></div>
  </main>

<script>
const container = document.getElementById("container");
const statusEl = document.getElementById("status");
const statusText = document.getElementById("status-text");
const emptyState = document.getElementById("empty-state");
const countEl = document.getElementById("table-count");
const clearBtn = document.getElementById("clear-btn");

let tableCount = 0;

function updateCount() {
  countEl.textContent = tableCount + (tableCount === 1 ? " table" : " tables");
}

function relativeTime(ts) {
  if (!ts) return "";
  const diffSec = Math.max(0, Math.floor((Date.now() / 1000) - ts));
  if (diffSec < 5) return "à l'instant";
  if (diffSec < 60) return diffSec + "s";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return diffMin + " min";
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return diffH + " h";
  return Math.floor(diffH / 24) + " j";
}

function refreshRelativeTimes() {
  document.querySelectorAll(".card-time").forEach(el => {
    const ts = parseFloat(el.dataset.ts || "0");
    el.textContent = ts ? "il y a " + relativeTime(ts) : "";
  });
}
setInterval(refreshRelativeTimes, 15000);

function clearLatestPills() {
  document.querySelectorAll(".latest-pill").forEach(el => el.remove());
}

function addTable(payload) {
  if (document.getElementById("card_" + payload.id)) return;
  emptyState.style.display = "none";

  const card = document.createElement("div");
  card.className = "table-card";
  card.id = "card_" + payload.id;

  const meta = document.createElement("div");
  meta.className = "card-meta";
  const pill = document.createElement("span");
  pill.className = "latest-pill";
  pill.textContent = "PLUS RÉCENT";
  const time = document.createElement("span");
  time.className = "card-time";
  time.dataset.ts = payload.ts || "";
  time.title = payload.ts ? new Date(payload.ts * 1000).toLocaleString() : "";
  meta.appendChild(pill);
  meta.appendChild(time);
  card.appendChild(meta);

  // payload.html contains a <div class="spark-wrap">...</div> followed by a
  // sibling <script> that wires up sort/filter/pin/context-menu for that
  // specific table. Parsing it via innerHTML keeps both nodes, but a
  // <script> created that way is inert by spec -- it never auto-executes.
  // So we walk the parsed nodes, move the real content into the card, and
  // re-create any <script> as a fresh element so the browser actually runs it.
  const temp = document.createElement("div");
  temp.innerHTML = payload.html;
  const inlineScripts = [];
  Array.from(temp.childNodes).forEach(node => {
    if (node.nodeType === 1 && node.tagName === "SCRIPT") {
      inlineScripts.push(node.textContent);
    } else {
      card.appendChild(node);
    }
  });

  clearLatestPills();
  container.prepend(card);
  refreshRelativeTimes();

  inlineScripts.forEach(code => {
    const s = document.createElement("script");
    s.textContent = code;
    document.body.appendChild(s);
    document.body.removeChild(s); // executed synchronously on append, safe to detach
  });

  tableCount++;
  updateCount();
}

clearBtn.addEventListener("click", () => {
  container.innerHTML = "";
  tableCount = 0;
  updateCount();
  emptyState.style.display = "block";
});

function connect() {
  const ws = new WebSocket("ws://" + location.host + "/ws");
  ws.onopen = () => {
    statusEl.classList.add("connected");
    statusText.textContent = "connecté";
  };
  ws.onclose = () => {
    statusEl.classList.remove("connected");
    statusText.textContent = "déconnecté, reconnexion…";
    setTimeout(connect, 1000);
  };
  ws.onerror = () => ws.close();
  ws.onmessage = (event) => addTable(JSON.parse(event.data));
}
connect();
</script>
</body>
</html>
"""