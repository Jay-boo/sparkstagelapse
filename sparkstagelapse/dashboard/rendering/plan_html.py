from __future__ import annotations

import html as html_lib
import re

# Spark's tree-string renderer (TreeNode.generateTreeString) builds each
# line's prefix out of 3-char chunks: "   " / ":  " to continue an
# ancestor branch, and "+- " / ":- " as the marker immediately before a
# node's own content. Depth == number of 3-char chunks consumed.
_INDENT_CHUNKS = ("   ", ":  ")
_MARKER_CHUNKS = ("+- ", ":- ")
_OP_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*")

# (category, keywords) — first match wins, checked in order so more
# specific categories (e.g. "Exchange") are tested before generic ones.
_CATEGORIES: list[tuple[str, tuple[str, ...]]] = [
    ("exchange", ("Exchange",)),
    ("join", ("Join",)),
    ("aggregate", ("Aggregate",)),
    ("scan", ("Scan", "RDDScan")),
    ("sort", ("Sort",)),
    ("filter", ("Filter",)),
    ("project", ("Project",)),
    ("adaptive", ("AdaptiveSparkPlan", "WholeStageCodegen", "InputAdapter",
                   "ColumnarToRow", "Subquery")),
]


def _categorize(op_name: str) -> str:
    for category, keywords in _CATEGORIES:
        if any(k in op_name for k in keywords):
            return category
    return "other"


def _op_name(node_text: str) -> str:
    m = _OP_NAME_RE.match(node_text.strip())
    return m.group(0) if m else (node_text.strip()[:24] or "?")


def _render_rows(nodes: list[dict]) -> tuple[str, int]:
    """Builds the `.plan-node` divs for a parsed node list. Returns
    (rows_html, n_exchanges) — the latter feeds the shuffle-count badge."""
    n_exchanges = sum(1 for node in nodes if node["category"] == "exchange")
    rows = []
    for node in nodes:
        detail_esc = html_lib.escape(node["detail"])
        op_esc = html_lib.escape(node["op"])
        full_line = html_lib.escape(f'{node["op"]} {node["detail"]}'.strip())
        rows.append(
            f'<div class="plan-node cat-{node["category"]}" style="--depth:{node["depth"]}" '
            f'title="{full_line}">'
            f'<span class="plan-guide"></span>'
            f'<span class="plan-op">{op_esc}</span>'
            f'<span class="plan-detail">{detail_esc}</span>'
            f'</div>'
        )
    return "".join(rows), n_exchanges


def _tree_lines(plan_text: str) -> list[str]:
    """Isolates the `== Physical Plan ==` tree out of a raw explain()
    string, dropping the `(1) NodeName` detail sections that "formatted"/
    "extended" modes append below it."""
    lines = plan_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "== Physical Plan ==":
            start = i + 1
            break
    if start is None:
        # No header found (already-trimmed text) — treat it all as tree.
        return [line for line in lines if line.strip()]
    out = []
    for line in lines[start:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("== "):
            break
        out.append(line)
    return out


def parse_physical_plan(plan_text: str) -> list[dict]:
    """Parses a Spark physical-plan explain() string into a flat,
    pre-order list of `{depth, op, detail, category}` nodes.

    `depth` is the node's indentation level in the tree (0 = root).
    `op` is the operator name (e.g. "HashAggregate", "Exchange").
    `detail` is the rest of the line (args), unparsed.
    """
    nodes = []
    for raw in _tree_lines(plan_text):
        i, n = 0, len(raw)
        while i + 3 <= n and raw[i:i + 3] in (*_INDENT_CHUNKS, *_MARKER_CHUNKS):
            chunk = raw[i:i + 3]
            i += 3
            if chunk in _MARKER_CHUNKS:
                break
        depth = i // 3
        content = raw[i:].strip()
        if not content:
            continue
        op = _op_name(content)
        detail = content[len(op):].strip()
        nodes.append({"depth": depth, "op": op, "detail": detail, "category": _categorize(op)})
    return nodes


# ---------------------------------------------------------------------------
# DAG layout
#
# A Spark physical-plan tree is, structurally, an actual tree (each node has
# exactly one parent) — so a classic "children first, parent centered above
# its children" layout gives a clean, crossing-free diagram without needing
# a real graph-layout library. We lay it out with the root at the top (same
# reading order as the tree-text view) and draw edges from each child
# upward into its parent, since that's the direction data actually flows
# (a child computes first, its output becomes the parent's input).
NODE_W = 196
NODE_H = 52
COL_GAP = 22
ROW_GAP = 54
PAD = 24


def _build_tree(nodes: list[dict]) -> tuple[list, list]:
    """Reconstructs parent/children indices from the flat pre-order node
    list using `depth`. Nearest preceding node at depth-1 is the parent."""
    n = len(nodes)
    parent: list = [None] * n
    children: list = [[] for _ in range(n)]
    last_at_depth: dict = {}
    for i, node in enumerate(nodes):
        d = node["depth"]
        pd = d - 1
        while pd >= 0 and pd not in last_at_depth:
            pd -= 1
        p = last_at_depth.get(pd) if pd >= 0 else None
        parent[i] = p
        if p is not None:
            children[p].append(i)
        last_at_depth[d] = i
        for dd in [k for k in last_at_depth if k > d]:
            del last_at_depth[dd]
    return parent, children


def _layout_dag(nodes: list[dict], parent: list, children: list) -> tuple[list, list, float, float]:
    """Returns (x, y, canvas_width, canvas_height) for each node, in px —
    top-left corner of each node's box (padding already included)."""
    n = len(nodes)
    x = [0.0] * n
    leaf_slot = [0]

    def place(i: int) -> float:
        kids = children[i]
        if not kids:
            xi = leaf_slot[0] * (NODE_W + COL_GAP)
            leaf_slot[0] += 1
        else:
            xs = [place(k) for k in kids]
            xi = sum(xs) / len(xs)
        x[i] = xi
        return xi

    for i in range(n):
        if parent[i] is None:
            place(i)

    max_depth = max((node["depth"] for node in nodes), default=0)
    y = [node["depth"] * (NODE_H + ROW_GAP) for node in nodes]
    n_leaves = max(leaf_slot[0], 1)
    width = n_leaves * (NODE_W + COL_GAP) - COL_GAP + 2 * PAD
    height = (max_depth + 1) * (NODE_H + ROW_GAP) - ROW_GAP + 2 * PAD
    return x, y, width, height


def _dag_to_html(nodes: list[dict], plan_id: str) -> str:
    """Renders the parsed node list as an absolutely-positioned node
    diagram: an <svg> layer draws the curved parent/child edges, plain
    <div> boxes (on top, via CSS) draw the operator nodes. Kept as plain
    divs (rather than SVG <text>) so long detail strings can truncate with
    ordinary CSS ellipsis and get a native tooltip on hover."""
    parent, children = _build_tree(nodes)
    x, y, width, height = _layout_dag(nodes, parent, children)

    edge_paths = []
    used_categories = set()
    for i, p in enumerate(parent):
        if p is None:
            continue
        cat = nodes[i]["category"]
        used_categories.add(cat)
        cx = x[i] + PAD + NODE_W / 2
        cy_top = y[i] + PAD
        px = x[p] + PAD + NODE_W / 2
        py_bottom = y[p] + PAD + NODE_H
        mid = (cy_top + py_bottom) / 2
        edge_paths.append(
            f'<path class="plan-dag-edge cat-{cat}" '
            f'd="M{cx:.1f},{cy_top:.1f} C{cx:.1f},{mid:.1f} {px:.1f},{mid:.1f} {px:.1f},{py_bottom:.1f}" '
            f'marker-end="url(#{plan_id}_arrow_{cat})" fill="none"/>'
        )

    marker_defs = "".join(
        f'<marker id="{plan_id}_arrow_{cat}" viewBox="0 0 10 10" refX="8" refY="5" '
        f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M0,0 L10,5 L0,10 z" class="plan-dag-arrowhead cat-{cat}"/></marker>'
        for cat in used_categories
    )

    node_boxes = []
    for i, node in enumerate(nodes):
        left = x[i] + PAD
        top = y[i] + PAD
        op_esc = html_lib.escape(node["op"])
        detail_esc = html_lib.escape(node["detail"])
        full_line = html_lib.escape(f'{node["op"]} {node["detail"]}'.strip())
        node_boxes.append(
            f'<div class="plan-dag-node cat-{node["category"]}" '
            f'style="left:{left:.1f}px; top:{top:.1f}px; width:{NODE_W}px; height:{NODE_H}px;" '
            f'title="{full_line}">'
            f'<span class="plan-dag-dot"></span>'
            f'<span class="plan-dag-text">'
            f'<span class="plan-dag-op">{op_esc}</span>'
            f'<span class="plan-dag-detail">{detail_esc or "&nbsp;"}</span>'
            f'</span></div>'
        )

    return f"""\
<div class="plan-dag" style="width:{width:.0f}px; height:{height:.0f}px;">
  <svg class="plan-dag-edges" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">
    <defs>{marker_defs}</defs>
    {"".join(edge_paths)}
  </svg>
  {"".join(node_boxes)}
</div>"""


def _view_switcher() -> str:
    return (
        '<div class="plan-viewsw" data-role="plan-viewsw">'
        '<button type="button" class="plan-view-btn active" data-view="tree">Tree</button>'
        '<button type="button" class="plan-view-btn" data-view="dag">DAG</button>'
        '<button type="button" class="plan-view-btn" data-view="raw">Raw</button>'
        '</div>'
    )


def plan_to_html(plan_text: str, title: str, plan_id: str) -> str:
    """Renders a Spark physical-plan explain() string as a collapsible,
    color-coded tree for the `.spark-plan` component (see
    static/js/dashboard.js + static/css/dashboard.css).

    Falls back to a raw `<pre>` block if the tree can't be parsed (e.g.
    unexpected explain() output) so the card still shows *something*
    useful instead of silently dropping the plan.
    """
    if not plan_text or not plan_text.strip():
        return ""

    nodes = parse_physical_plan(plan_text)
    if not nodes:
        return (
            f'<div class="spark-plan" id="{plan_id}_wrap">'
            f'<div class="plan-toolbar"><span class="plan-title">Physical plan</span></div>'
            f'<pre class="plan-raw">{html_lib.escape(plan_text)}</pre></div>'
        )

    rows_html, n_exchanges = _render_rows(nodes)
    dag_html = _dag_to_html(nodes, plan_id)

    warn_html = ""
    if n_exchanges:
        plural = "s" if n_exchanges != 1 else ""
        warn_html = f'<span class="plan-warn">⇄ {n_exchanges} shuffle{plural}</span>'

    return f"""\
<div class="spark-plan" id="{plan_id}_wrap">
  <div class="plan-toolbar">
    <span class="plan-title">Physical plan</span>
    {warn_html}
    {_view_switcher()}
  </div>
  <div class="plan-tree" data-role="plan-tree">{rows_html}</div>
  <div class="plan-dag-scroll" data-role="plan-dag-scroll" hidden>{dag_html}</div>
  <pre class="plan-raw" data-role="plan-raw" hidden>{html_lib.escape(plan_text)}</pre>
</div>"""


def plan_to_html_with_style(plan_text: str, title: str, plan_id: str,
                             max_height: str = "360px") -> str:
    """Self-contained version of `plan_to_html`: inline `<style>` scoped
    to `#{plan_id}_wrap` and an inline `<script>` (functions suffixed by
    `plan_id` so multiple plan cards can coexist on one page) for the
    show-tree/show-raw toggle.

    Use this instead of `plan_to_html` wherever the page won't have
    static/css/dashboard.css + static/js/dashboard.js loaded — notebooks
    (Jupyter, VS Code, Databricks), `_repr_html_`, or any standalone HTML
    export. Colors follow prefers-color-scheme (light/dark) automatically,
    same as `table_to_html_with_style`.
    """
    if not plan_text or not plan_text.strip():
        return ""

    nodes = parse_physical_plan(plan_text)
    esc_title = html_lib.escape(title)

    style = f"""\
  <style>
    #{plan_id}_wrap {{
      --bg: #ffffff; --bg-alt: #f7f7f8; --border: #ddd; --text: #1a1a1a;
      --text-muted: #6b6b6b; --accent: #3b82f6; --warn: #d97706;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 13px; color: var(--text); margin: 8px 0;
      border: 1px solid var(--border); border-radius: 10px; overflow: hidden;
    }}
    @media (prefers-color-scheme: dark) {{
      #{plan_id}_wrap {{
        --bg: #1e1e1e; --bg-alt: #252526; --border: #3c3c3c; --text: #e0e0e0;
        --text-muted: #9a9a9a; --accent: #5b9dff; --warn: #fbbf24;
      }}
    }}
    #{plan_id}_wrap .plan-toolbar {{
      display: flex; align-items: center; gap: 10px; padding: 8px 12px;
      background: var(--bg-alt); border-bottom: 1px solid var(--border); font-size: 11.5px;
    }}
    #{plan_id}_wrap .plan-title {{ font-weight: 600; color: var(--text); }}
    #{plan_id}_wrap .plan-warn {{
      color: var(--warn); font-size: 11px; background: rgba(217, 119, 6, 0.14);
      border-radius: 8px; padding: 2px 8px;
    }}
    #{plan_id}_wrap .plan-viewsw {{
      margin-left: auto; display: flex; gap: 2px; background: var(--bg);
      border: 1px solid var(--border); border-radius: 7px; padding: 2px;
    }}
    #{plan_id}_wrap .plan-view-btn {{
      border: none; background: transparent; color: var(--text-muted); font-size: 11px;
      padding: 3px 9px; border-radius: 5px; cursor: pointer; font-family: inherit;
    }}
    #{plan_id}_wrap .plan-view-btn:hover {{ color: var(--text); }}
    #{plan_id}_wrap .plan-view-btn.active {{ background: var(--accent); color: #fff; }}
    #{plan_id}_wrap .plan-tree {{
      padding: 10px 12px; max-height: {max_height}; overflow: auto;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px;
      background: var(--bg);
    }}
    #{plan_id}_wrap .plan-dag-scroll {{
      max-height: {max_height}; overflow: auto; background: var(--bg);
      background-image: radial-gradient(var(--border) 1px, transparent 1px);
      background-size: 16px 16px;
      cursor: grab; touch-action: none; overscroll-behavior: contain;
    }}
    #{plan_id}_wrap .plan-dag-scroll.dragging {{ cursor: grabbing; user-select: none; }}
    #{plan_id}_wrap .plan-dag-scroll.dragging .plan-dag-node {{ pointer-events: none; }}
    #{plan_id}_wrap .plan-dag {{ position: relative; }}
    #{plan_id}_wrap .plan-dag-edges {{ position: absolute; top: 0; left: 0; pointer-events: none; }}
    #{plan_id}_wrap .plan-dag-edge {{ stroke: var(--text-muted); stroke-width: 1.6; opacity: 0.75; }}
    #{plan_id}_wrap .plan-dag-arrowhead {{ fill: var(--text-muted); opacity: 0.75; }}
    #{plan_id}_wrap .plan-dag-node {{
      position: absolute; display: flex; align-items: center; gap: 8px;
      padding: 0 10px; border-radius: 9px; background: var(--bg-alt);
      border: 1px solid var(--border); box-shadow: 0 1px 2px rgba(0,0,0,0.06);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      transition: transform 0.12s ease, box-shadow 0.12s ease; cursor: default;
    }}
    #{plan_id}_wrap .plan-dag-node:hover {{
      transform: translateY(-1px); box-shadow: 0 4px 10px rgba(0,0,0,0.12); z-index: 2;
    }}
    #{plan_id}_wrap .plan-dag-dot {{
      width: 9px; height: 9px; border-radius: 50%; flex: none; background: var(--text-muted);
    }}
    #{plan_id}_wrap .plan-dag-text {{ min-width: 0; display: flex; flex-direction: column; gap: 1px; }}
    #{plan_id}_wrap .plan-dag-op {{ font-weight: 600; font-size: 12px; color: var(--text); }}
    #{plan_id}_wrap .plan-dag-detail {{
      font-size: 10.5px; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }}
    #{plan_id}_wrap .cat-exchange.plan-dag-node {{ border-color: var(--warn); }}
    #{plan_id}_wrap .cat-exchange .plan-dag-dot {{ background: var(--warn); }}
    #{plan_id}_wrap path.plan-dag-edge.cat-exchange {{ stroke: var(--warn); opacity: 0.9; }}
    #{plan_id}_wrap .plan-dag-arrowhead.cat-exchange {{ fill: var(--warn); }}
    #{plan_id}_wrap .cat-join.plan-dag-node {{ border-color: #a855f7; }}
    #{plan_id}_wrap .cat-join .plan-dag-dot {{ background: #a855f7; }}
    #{plan_id}_wrap path.plan-dag-edge.cat-join {{ stroke: #a855f7; opacity: 0.9; }}
    #{plan_id}_wrap .plan-dag-arrowhead.cat-join {{ fill: #a855f7; }}
    #{plan_id}_wrap .cat-aggregate.plan-dag-node {{ border-color: #14b8a6; }}
    #{plan_id}_wrap .cat-aggregate .plan-dag-dot {{ background: #14b8a6; }}
    #{plan_id}_wrap path.plan-dag-edge.cat-aggregate {{ stroke: #14b8a6; opacity: 0.9; }}
    #{plan_id}_wrap .plan-dag-arrowhead.cat-aggregate {{ fill: #14b8a6; }}
    #{plan_id}_wrap .cat-scan.plan-dag-node {{ border-color: var(--accent); }}
    #{plan_id}_wrap .cat-scan .plan-dag-dot {{ background: var(--accent); }}
    #{plan_id}_wrap path.plan-dag-edge.cat-scan {{ stroke: var(--accent); opacity: 0.9; }}
    #{plan_id}_wrap .plan-dag-arrowhead.cat-scan {{ fill: var(--accent); }}
    #{plan_id}_wrap .cat-sort.plan-dag-node {{ border-color: #eab308; }}
    #{plan_id}_wrap .cat-sort .plan-dag-dot {{ background: #eab308; }}
    #{plan_id}_wrap path.plan-dag-edge.cat-sort {{ stroke: #eab308; opacity: 0.9; }}
    #{plan_id}_wrap .plan-dag-arrowhead.cat-sort {{ fill: #eab308; }}
    #{plan_id}_wrap .cat-filter.plan-dag-node, #{plan_id}_wrap .cat-project.plan-dag-node {{ border-color: #16a34a; }}
    #{plan_id}_wrap .cat-filter .plan-dag-dot, #{plan_id}_wrap .cat-project .plan-dag-dot {{ background: #16a34a; }}
    #{plan_id}_wrap path.plan-dag-edge.cat-filter, #{plan_id}_wrap path.plan-dag-edge.cat-project {{ stroke: #16a34a; opacity: 0.9; }}
    #{plan_id}_wrap .plan-dag-arrowhead.cat-filter, #{plan_id}_wrap .plan-dag-arrowhead.cat-project {{ fill: #16a34a; }}
    #{plan_id}_wrap .plan-dag-arrowhead.cat-adaptive, #{plan_id}_wrap .plan-dag-arrowhead.cat-other {{ fill: var(--text-muted); }}
    #{plan_id}_wrap .plan-node {{
      display: flex; align-items: baseline; gap: 8px;
      padding: 2px 0 2px calc(var(--depth) * 16px);
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }}
    #{plan_id}_wrap .plan-guide {{
      width: 7px; height: 7px; border-radius: 50%; flex: none; background: var(--text-muted);
    }}
    #{plan_id}_wrap .plan-op {{ font-weight: 600; color: var(--text); flex: none; }}
    #{plan_id}_wrap .plan-detail {{ color: var(--text-muted); overflow: hidden; text-overflow: ellipsis; }}
    #{plan_id}_wrap .plan-raw {{
      margin: 0; padding: 10px 12px; max-height: {max_height}; overflow: auto;
      font-size: 11.5px; white-space: pre; background: var(--bg-alt); color: var(--text);
    }}
    #{plan_id}_wrap .cat-exchange .plan-guide, #{plan_id}_wrap .cat-exchange .plan-op {{ color: var(--warn); }}
    #{plan_id}_wrap .cat-exchange .plan-guide {{ background: var(--warn); }}
    #{plan_id}_wrap .cat-join .plan-guide, #{plan_id}_wrap .cat-join .plan-op {{ color: #a855f7; }}
    #{plan_id}_wrap .cat-join .plan-guide {{ background: #a855f7; }}
    #{plan_id}_wrap .cat-aggregate .plan-guide, #{plan_id}_wrap .cat-aggregate .plan-op {{ color: #14b8a6; }}
    #{plan_id}_wrap .cat-aggregate .plan-guide {{ background: #14b8a6; }}
    #{plan_id}_wrap .cat-scan .plan-guide, #{plan_id}_wrap .cat-scan .plan-op {{ color: var(--accent); }}
    #{plan_id}_wrap .cat-scan .plan-guide {{ background: var(--accent); }}
    #{plan_id}_wrap .cat-sort .plan-guide, #{plan_id}_wrap .cat-sort .plan-op {{ color: #eab308; }}
    #{plan_id}_wrap .cat-sort .plan-guide {{ background: #eab308; }}
    #{plan_id}_wrap .cat-filter .plan-guide, #{plan_id}_wrap .cat-filter .plan-op,
    #{plan_id}_wrap .cat-project .plan-guide, #{plan_id}_wrap .cat-project .plan-op {{ color: #16a34a; }}
    #{plan_id}_wrap .cat-filter .plan-guide, #{plan_id}_wrap .cat-project .plan-guide {{ background: #16a34a; }}
    #{plan_id}_wrap .cat-adaptive .plan-guide, #{plan_id}_wrap .cat-adaptive .plan-op {{ color: var(--text-muted); }}
  </style>"""

    if not nodes:
        return f"""\
<div id="{plan_id}_wrap">
{style}
  <div class="plan-toolbar"><span class="plan-title">Physical plan — {esc_title}</span></div>
  <pre class="plan-raw">{html_lib.escape(plan_text)}</pre>
</div>"""

    rows_html, n_exchanges = _render_rows(nodes)
    dag_html = _dag_to_html(nodes, plan_id)

    warn_html = ""
    if n_exchanges:
        plural = "s" if n_exchanges != 1 else ""
        warn_html = f'<span class="plan-warn">⇄ {n_exchanges} shuffle{plural}</span>'

    script = f"""\
  <script>
    (function() {{
      var wrap = document.getElementById("{plan_id}_wrap");
      var buttons = wrap.querySelectorAll('[data-role="plan-viewsw"] .plan-view-btn');
      var views = {{
        tree: wrap.querySelector('[data-role="plan-tree"]'),
        dag: wrap.querySelector('[data-role="plan-dag-scroll"]'),
        raw: wrap.querySelector('[data-role="plan-raw"]')
      }};
      buttons.forEach(function(btn) {{
        btn.addEventListener("click", function() {{
          buttons.forEach(function(b) {{ b.classList.toggle("active", b === btn); }});
          Object.keys(views).forEach(function(name) {{
            if (views[name]) views[name].hidden = name !== btn.dataset.view;
          }});
        }});
      }});

      // Click-and-drag panning on the DAG canvas (mouse/touch/pen via
      // Pointer Events); still scrollable normally via wheel/scrollbar.
      var dagScroll = views.dag;
      if (dagScroll) {{
        var dragging = false, startX = 0, startY = 0, startLeft = 0, startTop = 0;
        dagScroll.addEventListener("pointerdown", function(e) {{
          if (e.button !== 0) return;
          dragging = true;
          startX = e.clientX; startY = e.clientY;
          startLeft = dagScroll.scrollLeft; startTop = dagScroll.scrollTop;
          dagScroll.classList.add("dragging");
          dagScroll.setPointerCapture(e.pointerId);
        }});
        dagScroll.addEventListener("pointermove", function(e) {{
          if (!dragging) return;
          dagScroll.scrollLeft = startLeft - (e.clientX - startX);
          dagScroll.scrollTop = startTop - (e.clientY - startY);
        }});
        var stopDrag = function() {{ dragging = false; dagScroll.classList.remove("dragging"); }};
        dagScroll.addEventListener("pointerup", stopDrag);
        dagScroll.addEventListener("pointercancel", stopDrag);
        dagScroll.addEventListener("pointerleave", stopDrag);
      }}
    }})();
  </script>"""

    return f"""\
<div id="{plan_id}_wrap">
{style}
  <div class="plan-toolbar">
    <span class="plan-title">Physical plan — {esc_title}</span>
    {warn_html}
    {_view_switcher()}
  </div>
  <div class="plan-tree" data-role="plan-tree">{rows_html}</div>
  <div class="plan-dag-scroll" data-role="plan-dag-scroll" hidden>{dag_html}</div>
  <pre class="plan-raw" data-role="plan-raw" hidden>{html_lib.escape(plan_text)}</pre>
{script}
</div>"""