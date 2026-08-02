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
        return [l for l in lines if l.strip()]
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

    warn_html = ""
    if n_exchanges:
        plural = "s" if n_exchanges != 1 else ""
        warn_html = f'<span class="plan-warn">⇄ {n_exchanges} shuffle{plural}</span>'

    return f"""\
<div class="spark-plan" id="{plan_id}_wrap">
  <div class="plan-toolbar">
    <span class="plan-title">Physical plan</span>
    {warn_html}
    <span class="plan-toggle" data-role="plan-toggle">show raw</span>
  </div>
  <div class="plan-tree" data-role="plan-tree">{rows_html}</div>
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
    #{plan_id}_wrap .plan-toggle {{
      margin-left: auto; color: var(--accent); cursor: pointer; font-size: 11px; user-select: none;
    }}
    #{plan_id}_wrap .plan-toggle:hover {{ text-decoration: underline; }}
    #{plan_id}_wrap .plan-tree {{
      padding: 10px 12px; max-height: {max_height}; overflow: auto;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px;
      background: var(--bg);
    }}
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

    warn_html = ""
    if n_exchanges:
        plural = "s" if n_exchanges != 1 else ""
        warn_html = f'<span class="plan-warn">⇄ {n_exchanges} shuffle{plural}</span>'

    script = f"""\
  <script>
    (function() {{
      var wrap = document.getElementById("{plan_id}_wrap");
      var toggle = wrap.querySelector('[data-role="plan-toggle"]');
      var tree = wrap.querySelector('[data-role="plan-tree"]');
      var raw = wrap.querySelector('[data-role="plan-raw"]');
      toggle.addEventListener("click", function() {{
        var showingRaw = !raw.hidden;
        raw.hidden = showingRaw;
        tree.hidden = !showingRaw;
        toggle.textContent = showingRaw ? "show raw" : "show tree";
      }});
    }})();
  </script>"""

    return f"""\
<div id="{plan_id}_wrap">
{style}
  <div class="plan-toolbar">
    <span class="plan-title">Physical plan — {esc_title}</span>
    {warn_html}
    <span class="plan-toggle" data-role="plan-toggle">show raw</span>
  </div>
  <div class="plan-tree" data-role="plan-tree">{rows_html}</div>
  <pre class="plan-raw" data-role="plan-raw" hidden>{html_lib.escape(plan_text)}</pre>
{script}
</div>"""