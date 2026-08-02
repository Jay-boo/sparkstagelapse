import logging
from typing import Any

from fastapi import WebSocket

logger=logging.getLogger(__name__)
class DashboardState:
    """in-memory store for pushed cards and connected websocket clients.

    lives once per server process (constructed in create_app(), which is
    itself only called once — see server.py). 
    """
    def __init__(self)->None:
        self.cards:list[dict[str,Any]]=[]
        self.connections:list[WebSocket]=[]

    def add_card(self,payload:dict[str,Any])->None:
        self.cards.append(payload)
    def add_connection(self,websocket:WebSocket) ->None:
        self.connections.append(websocket)

    def remove_connection(self,websocket:WebSocket)->None:
        if websocket is self.connections:
            self.connections.remove(websocket)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        """Send payload to every connected client, dropping dead sockets."""
        dead: list[WebSocket] = []
        for ws in self.connections:
            try:
                await ws.send_json(payload)
            except Exception:
                logger.debug("dropping dead websocket connection",exc_info=True)
                dead.append(ws)
        for ws in dead:
            self.remove_connection(ws)
