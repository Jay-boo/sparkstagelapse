from __future__ import annotations
import io
import uuid

import json
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
from pyspark.sql.dataframe import DataFrame
from rich.console import Console
from rich.table import Table
import contextlib
import logging

from .dashboard.client import DashboardClient
from .dashboard.rendering import table_to_html_with_style,plan_to_html_with_style,plan_to_html

logger=logging.getLogger(__name__)

def _is_notebook() -> bool:
    try:
        shell = get_ipython().__class__.__name__  # noqa: F821  # type: ignore[name-defined]
        return shell == "ZMQInteractiveShell"
    except Exception:
        return False


def _safe_str(value):
    if value is None:
        return "null"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)

def _capture_explain(df:DataFrame,mode:str="simple")->str:
    """
    """
    if not hasattr(df,"explain"):
        return None
    buf= io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            df.explain(mode=mode)
        return buf.getvalue()
    except Exception:
        logger.warning("failed to capture spark plan",exc_info=True)
        return None

_default_client = DashboardClient()


@dataclass
class SparkDisplay:
    pdf: pd.DataFrame
    title: str = "Spark preview"
    console: Optional[Console] = None
    plan_text:Optional[str]=None
    _dashboard: DashboardClient = field(default_factory=lambda: _default_client)

    def _repr_html_(self):
        table_id = f"tbl_{uuid.uuid4().hex[:8]}"
        html=table_to_html_with_style(self.pdf, self.title, table_id)
        if self.plan_text:
            plan_id = f"plan_{uuid.uuid4().hex[:8]}"
            html+= plan_to_html_with_style(self.plan_text,self.title,plan_id)
        return html

    def __str__(self):
        return self.pdf.to_string(index=False)

    def to_rich_table(self, max_width: int = 40) -> Table:
        table = Table(title=self.title, header_style="bold cyan",
                      title_style="bold white", show_lines=False, expand=True)
        for col in self.pdf.columns:
            table.add_column(str(col), overflow="ellipsis", max_width=max_width, no_wrap=False)
        for row in self.pdf.itertuples(index=False, name=None):
            table.add_row(*[_safe_str(v) for v in row])
        return table

    def show_rich(self, max_width: int = 40, log: bool = False):
        console = self.console or Console()
        table = self.to_rich_table(max_width=max_width)
        if log:
            console.log(table)
        else:
            console.print(table)
        return self

    def show_web(self):
        """Pousse la table vers le dashboard web local (persistant, process
        séparé). Non bloquant : retourne immédiatement, le script continue."""
        plan_html=None
        if self.plan_text:
            plan_id = f"plan_{uuid.uuid4().hex[:8]}"
            plan_html = plan_to_html(self.plan_text, self.title, plan_id)
        self._dashboard.push(self.pdf, self.title, plan_html=plan_html)
        return self

    def show_tui(self):
        """Explorateur plein écran (Textual). Bloquant par nature."""
        from textual.app import App, ComposeResult
        from textual.containers import Vertical
        from textual.widgets import DataTable, Footer, Header, Input, Static

        pdf = self.pdf.copy()
        title = self.title

        class SparkPreviewApp(App):
            CSS = """
            Screen { layout: vertical; }
            #topbar { height: auto; padding: 0 1; }
            #filter_input { margin: 1 0; }
            #summary { color: $text-muted; padding-bottom: 1; }
            DataTable { height: 1fr; }
            """
            BINDINGS = [("q", "quit", "Quit"), ("f", "focus_filter", "Filter"),
                        ("escape", "clear_filter", "Clear filter")]

            def compose(self) -> ComposeResult:
                yield Header(show_clock=True)
                with Vertical(id="topbar"):
                    yield Input(placeholder="Type to filter rows... (press f to focus)", id="filter_input")
                    yield Static("", id="summary")
                yield DataTable(id="table")
                yield Footer()

            def on_mount(self) -> None:
                self.full_pdf = pdf
                self.filtered_pdf = pdf
                self.table = self.query_one(DataTable)
                self.filter_input = self.query_one("#filter_input", Input)
                self.summary = self.query_one("#summary", Static)
                self.table.cursor_type = "row"
                self.table.zebra_stripes = True
                self._load_table(self.filtered_pdf)
                self.filter_input.focus()

            def _load_table(self, current_pdf: pd.DataFrame) -> None:
                self.table.clear(columns=True)
                self.table.add_columns(*[str(c) for c in current_pdf.columns])
                rows = [tuple(_safe_str(v) for v in row)
                        for row in current_pdf.itertuples(index=False, name=None)]
                if rows:
                    self.table.add_rows(rows)
                self.summary.update(
                    f"{title} • {len(current_pdf)} visible row(s) / {len(self.full_pdf)} loaded row(s) • {len(current_pdf.columns)} column(s)"
                )

            def _apply_filter(self, query: str) -> None:
                q = (query or "").strip().lower()
                if not q:
                    self.filtered_pdf = self.full_pdf
                else:
                    mask = self.full_pdf.apply(
                        lambda row: row.astype(str).str.lower().str.contains(q, regex=False).any(), axis=1)
                    self.filtered_pdf = self.full_pdf[mask]
                self._load_table(self.filtered_pdf)

            def on_input_changed(self, event: Input.Changed) -> None:
                if event.input.id == "filter_input":
                    self._apply_filter(event.value)

            def action_focus_filter(self) -> None:
                self.filter_input.focus()

            def action_clear_filter(self) -> None:
                self.filter_input.value = ""
                self._apply_filter("")
                self.filter_input.focus()

        SparkPreviewApp().run()
        return self

    def show(self, force: Optional[str] = None, max_width: int = 40, log: bool = False):
        mode = force or ("notebook" if _is_notebook() else "web")

        if mode == "notebook":
            try:
                from IPython.display import HTML, display
                return display(HTML(self._repr_html_()))
            except Exception:
                return self.show_rich(max_width=max_width, log=log)

        if mode == "web":
            
            return self.show_web()

        if mode == "tui":
            return self.show_tui()

        return self.show_rich(max_width=max_width, log=log)


def display(df:DataFrame, n: int = 200, title: str = "Spark DataFrame",
                   console: Optional[Console] = None, mode: str = "auto",truncate:bool|None=True,plan:bool=False,plan_mode:str="simple"):
    """
    mode:
      - "auto"     : notebook -> displays immediately (like Databricks' display()),
                     script -> web dashboard
      - "notebook" : returns the object WITHOUT displaying it — only shows up if
                     it ends up being the last expression evaluated in the cell.
                     Use "auto" (or call obj.show()) if you want it to render
                     immediately regardless of what code follows.
      - "web"      : persistent local web dashboard, non-blocking (recommended in scripts)
      - "tui"      : full-screen Textual explorer, blocking
      - "rich"     : plain ASCII output in the terminal
    """
    plan_text=None
    if mode=="auto" and not _is_notebook():
        plan=True
    if plan:
        plan_text=_capture_explain(df,mode=plan_mode)
    pdf = df.limit(n).toPandas()
    if hasattr(df, "show") and not _is_notebook():
        df.show(n, truncate=truncate) 
    obj = SparkDisplay(pdf=pdf, title=title, console=console,plan_text=plan_text)

    if mode == "auto":
        if _is_notebook():
            return obj.show(force="notebook")
        return obj.show(force="web")

    if mode == "notebook":
        return obj

    return obj.show(force=mode)