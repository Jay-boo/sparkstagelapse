from __future__ import annotations

import os
from typing import Any
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from .state import DashboardState
from .routers import pages,ws,tables
from fastapi.templating import Jinja2Templates


_DASHBOARD_DIR = Path(__file__).parent

def create_app() -> FastAPI:
    """Construit l'app FastAPI du dashboard.

    Toute la state (tables déjà poussées, websockets connectées) vit dans
    ce process — create_app() n'est appelée qu'une fois, dans le process
    serveur détaché (voir server.py). Le client (client.py) ne fait que
    des requêtes HTTP/WS vers ce process, jamais d'import direct de state.
    """
    app = FastAPI(title="sparkstagelapse dashboard")

    app.state.spp = DashboardState()
    app.state.templates=Jinja2Templates(directory=str(_DASHBOARD_DIR/"templates"))
    app.mount("/static",StaticFiles(directory=str(_DASHBOARD_DIR/"static")),name="static")

    app.include_router(pages.router)
    app.include_router(ws.router)
    app.include_router(tables.router)




    return app
