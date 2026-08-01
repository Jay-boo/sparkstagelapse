from typing import Any, Optional

from pydantic import BaseModel


class CardPayload(BaseModel):
    """One card in the dashboard feed: a table, optionally with a plot.

    `table_html` is pre-rendered semantic markup (see rendering/table_html.py)
    — no inline <style>/<script>, those live in static/. `plot` is a Plotly
    figure spec (`{"data": [...], "layout": {...}}`, i.e. what
    `plotly.graph_objects.Figure.to_plotly_json()` returns) rendered
    client-side with Plotly.js; omit it for table-only cards.
    """

    id: str
    title: str
    ts: float
    table_html: str
    columns: list[str]
    plot: Optional[dict[str, Any]] = None
