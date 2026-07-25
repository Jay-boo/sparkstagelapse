from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from .templates import PAGE_TEMPLATE


def create_app() -> FastAPI:
    """Construit l'app FastAPI du dashboard.

    Toute la state (tables déjà poussées, websockets connectées) vit dans
    ce process — create_app() n'est appelée qu'une fois, dans le process
    serveur détaché (voir server.py). Le client (client.py) ne fait que
    des requêtes HTTP/WS vers ce process, jamais d'import direct de state.
    """
    app = FastAPI(title="spark-prettyprint dashboard")

    state: dict[str, Any] = {
        "tables": [],        # payloads déjà poussés, rejoués aux nouveaux clients
        "connections": [],   # websockets actuellement connectées
    }
    app.state.spp = state

    @app.get("/health")
    def health():
        return {"ok": True, "pid": os.getpid()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return PAGE_TEMPLATE

    @app.post("/api/tables")
    async def push_table(payload: dict):
        state["tables"].append(payload)
        dead = []
        for ws in state["connections"]:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in state["connections"]:
                state["connections"].remove(ws)
        return {"ok": True}

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket):
        await websocket.accept()
        state["connections"].append(websocket)
        try:
            for payload in state["tables"]:
                await websocket.send_json(payload)
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            if websocket in state["connections"]:
                state["connections"].remove(websocket)

    return app
