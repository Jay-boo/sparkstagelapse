
from fastapi import APIRouter,WebSocket,WebSocketDisconnect
from ..state import DashboardState

router=APIRouter()

@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    state:DashboardState=websocket.app.state.spp
    state.add_connection(websocket)
    try:
        for card in state.cards:
            await websocket.send_json(card)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in state["connections"]:
            state["connections"].remove(websocket)
