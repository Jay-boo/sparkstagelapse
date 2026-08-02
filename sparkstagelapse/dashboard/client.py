from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
import uuid
import webbrowser
from datetime import datetime, timezone

import pandas as pd
import requests

from .rendering import table_to_html, to_plot_spec
from .server import DEFAULT_HOST, DEFAULT_PORT, log_file

logger=logging.getLogger(__name__)

_READY_TIMEOUT_S = 5.0
_POLL_INTERVAL_S = 0.05


def _open_browser_quiet(url: str) -> None:
    """webbrowser.open() shells out to every known browser in turn and,
    on headless machines (no DISPLAY, no permissions, CI containers...),
    each failed attempt prints straight to the process' real stdout/stderr
    file descriptors — bypassing normal exception handling entirely. We
    redirect fds 1/2 to /dev/null for the duration of the call (subprocess
    inherits them) and swallow any exception; failing to open a browser is
    never fatal, the dashboard URL is still printed/usable regardless.
    """
    try:
        saved_out, saved_err = os.dup(1), os.dup(2)
        devnull = os.open(os.devnull, os.O_RDWR)
        try:
            os.dup2(devnull, 1)
            os.dup2(devnull, 2)
            webbrowser.open(url)
        finally:
            os.dup2(saved_out, 1)
            os.dup2(saved_err, 2)
            os.close(saved_out)
            os.close(saved_err)
            os.close(devnull)
    except Exception:
        pass


class DashboardClient:
    """Pousse des tables vers un serveur dashboard qui tourne dans SON
    PROPRE PROCESS OS, détaché de celui qui appelle push().

    - Si un serveur répond déjà sur host:port -> on lui pousse la table,
      aucun nouveau process n'est démarré.
    - Sinon -> on spawn le serveur en process détaché (survit à la fin de
      CE script), on attend qu'il soit prêt, puis on pousse.

    Plusieurs scripts / runs / notebooks partagent donc le même dashboard
    tant qu'ils utilisent le même host:port, et il reste ouvert dans le
    navigateur même une fois le script qui l'a démarré terminé.
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                 open_browser: bool = True):
        self.host = host
        self.port = port
        self.open_browser = open_browser
        self._opened_browser = False

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def is_alive(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/health", timeout=0.3)
            return r.status_code == 200
        except Exception:
            return False

    def _spawn_detached_server(self) -> None:
        logf = open(log_file(self.port), "a")
        popen_kwargs: dict = dict(
            stdout=logf,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
        )
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            )
        else:
            popen_kwargs["start_new_session"] = True

        subprocess.Popen(
            [
                sys.executable, "-m", "sparkstagelapse.dashboard.server",
                "--host", self.host, "--port", str(self.port),
            ],
            **popen_kwargs,
        )

    def ensure_running(self) -> bool:
        if self.is_alive():
            return True

        self._spawn_detached_server()

        deadline = time.monotonic() + _READY_TIMEOUT_S
        while time.monotonic() < deadline:
            if self.is_alive():
                return True
            time.sleep(_POLL_INTERVAL_S)
        return False

    def push(self, pdf: pd.DataFrame, title: str,plot=None) -> bool:
        if not self.ensure_running():
            logger.warning(
                "impossible de démarrer/joindre le dahsboard sur %s - voir %s",
                self.base_url,log_file(self.port)
            )
            return False

        if self.open_browser and not self._opened_browser:
            _open_browser_quiet(self.base_url)
            self._opened_browser = True

        table_id = f"tbl_{uuid.uuid4().hex[:8]}"

        payload = {
            "id": table_id,
            "title": title,
            "ts": datetime.now(timezone.utc).timestamp(),
            "table_html": table_to_html(pdf, title, table_id),
            "columns": [str(c) for c in pdf.columns],
            "plot": to_plot_spec(plot),
        }
        try:
            requests.post(f"{self.base_url}/api/tables", json=payload, timeout=2)
            return True
        except Exception:
            logger.warning("dashboard indisponible, table %r non affichée",title,exc_info=True)
            return False