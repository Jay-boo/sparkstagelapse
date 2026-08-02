from typing import Any, Optional

from pydantic import BaseModel


class CardPayload(BaseModel):
    """One card in the dashboard feed: a table, optionally with a plot.

    `table_html` is pre-rendered semantic markup (see rendering/table_html.py)
    — no inline <style>/<script>, those live in static/. `plot` is a Plotly
    figure spec (`{"data": [...], "layout": {...}}`, i.e. what
    `plotly.graph_objects.Figure.to_plotly_json()` returns) rendered
    client-side with Plotly.js; omit it for table-only cards. `plan_html`
    is pre-rendered markup for the Spark physical-plan tree (see
    rendering/plan_html.py) — same deal as `table_html`, no inline
    <style>/<script>; omit it for cards with no captured plan.
    """

    id: str
    title: str
    ts: float
    table_html: str
    columns: list[str]
    plot: Optional[dict[str, Any]] = None
    plan_html: Optional[str] = None