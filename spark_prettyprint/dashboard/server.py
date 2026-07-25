from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from .app import create_app

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _state_dir() -> Path:
    d = Path.home() / ".cache" / "spark-prettyprint"
    d.mkdir(parents=True, exist_ok=True)
    return d


def pid_file(port: int) -> Path:
    return _state_dir() / f"dashboard_{port}.pid"


def log_file(port: int) -> Path:
    return _state_dir() / f"dashboard_{port}.log"


def run(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    """Démarre le serveur EN PREMIER PLAN (bloquant) dans le process courant.

    Prévu pour être lancé comme entrypoint d'un process séparé — soit
    manuellement (`python -m spark_prettyprint.dashboard.server`), soit
    spawné en détaché par DashboardClient (voir client.py). Ce n'est
    volontairement PAS un thread : un thread daemon meurt avec son process
    parent, un process séparé survit à la fin du script appelant.
    """
    pid_file(port).write_text(str(os.getpid()))
    app = create_app()
    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    finally:
        try:
            pid_file(port).unlink(missing_ok=True)
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(prog="spark-prettyprint-server")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
