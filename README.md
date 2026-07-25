# sparkstagelapse

Interactive DataFrame display (Spark or pandas) — whether you're in a
notebook, a script, or a Databricks run — backed by a local web dashboard
that **stays open and up to date even after the script that launched it has
exited.**

## Installation

From the root of this folder:

```bash
pip install -e .
# or, if you also want the full-screen explorer (Textual):
pip install -e ".[tui]"
```

## Quick usage

```python
from sparkstagelapse import display_spark

# df = spark.sql("select * from ...")
display_spark(df, title="Employees")             # "auto" mode: notebook -> rich object, script -> web dashboard
display_spark(df, title="Employees", mode="web")  # force the web dashboard
display_spark(df, title="Employees", mode="tui")  # full-screen explorer (blocking)
display_spark(df, title="Employees", mode="rich") # plain ASCII output in the terminal
```

Or directly on a pandas DataFrame:

```python
from sparkstagelapse import SparkDisplay

SparkDisplay(pdf, title="Preview").show_web()
```

## The persistent dashboard

On the first `show_web()` call (or `mode="web"`), the client:

1. Checks whether a server already responds on `127.0.0.1:8765` (`/health`).
2. If yes: just pushes the new table to it over HTTP — no new process is
   created.
3. If no: **spawns the server as a detached process** (not a thread — a
   daemon thread dies with its parent process, a separate process doesn't).
   Your script keeps running normally, without blocking.

The server therefore stays alive after your script exits. The next run —
even tomorrow, even from a different script — will find the same dashboard
already open in your browser and update it live over WebSocket.

### Managing the server manually

```bash
python -m sparkstagelapse.dashboard status
python -m sparkstagelapse.dashboard stop
python -m sparkstagelapse.dashboard start   # manual foreground start (blocking)
```

Logs and pid files live in `~/.cache/sparkstagelapse/dashboard_<port>.log` / `.pid`.

### Changing the port / host

```python
from sparkstagelapse import DashboardClient, SparkDisplay

client = DashboardClient(host="127.0.0.1", port=9000)
SparkDisplay(pdf, title="Preview", _dashboard=client).show_web()
```

## Package structure

```
sparkstagelapse/
├── __init__.py             # Public API: SparkDisplay, display_spark, DashboardClient
├── display.py               # SparkDisplay / display_spark — renders depending on context
└── dashboard/
    ├── app.py                # FastAPI app (HTTP + WebSocket routes), in-memory state
    ├── server.py              # Server bootstrap (foreground), pid/log files
    ├── client.py               # DashboardClient: health-check, detached spawn, HTTP push
    ├── templates.py            # HTML/JS template + table -> HTML rendering
    └── __main__.py              # CLI: start / stop / status
```

## Development

```bash
pip install -e ".[dev,tui]"

ruff check .          # lint
pytest -v             # unit + integration tests
python -m build        # build sdist + wheel
twine check dist/*     # validate package metadata before upload
```

## CI/CD

See `.github/workflows/ci.yml` (lint + test matrix + build, on every push/PR)
and `.github/workflows/release.yml` (build + publish to PyPI/TestPyPI via
Trusted Publishing, on tagged GitHub Releases). Before the release workflow
can actually publish, you need to register this repo as a Trusted Publisher
on PyPI/TestPyPI — see the CI/CD explanation in this conversation for the
exact steps.