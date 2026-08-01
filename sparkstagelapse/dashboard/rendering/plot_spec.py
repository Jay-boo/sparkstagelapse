import json
from typing import Any, Optional


def to_plot_spec(plot: Any) -> Optional[dict]:
    """Normalizes `plot` into a JSON-safe {"data": [...], "layout": {...}}
    dict that static/js/dashboard.js hands straight to Plotly.newPlot().

    Accepts:
      - None                          -> None (no plot on this card)
      - a plotly.graph_objects.Figure -> converted via its own JSON encoder
        (handles numpy/pandas dtypes Figure.data may contain; plain
        json.dumps would choke on those)
      - a plain dict already shaped like {"data": [...], "layout": {...}}
    """
    if plot is None:
        return None

    if isinstance(plot, dict):
        return plot

    to_json = getattr(plot, "to_json", None)
    if callable(to_json):
        return json.loads(to_json())

    raise TypeError(
        "plot must be a plotly.graph_objects.Figure, a dict with "
        f"'data'/'layout' keys, or None — got {type(plot)!r}"
    )
