from fastapi import APIRouter,Request
from ..state import DashboardState
from ..models import CardPayload


router=APIRouter()

@router.post("/api/tables")
async def push_table(payload: CardPayload,request:Request):
    state:DashboardState=request.app.state.spp
    data= payload.model_dump()
    state.add_card(data)
    await state.broadcast(payload)
    return {"ok": True}
