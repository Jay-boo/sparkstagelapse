from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .routers import pages, tables, ws
from .state import DashboardState

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
