from fastapi import APIRouter,Request
from fastapi.responses import HTMLResponse
import os
router= APIRouter()


@router.get("/health")
def health():
    return {"ok": True, "pid": os.getpid()}

@router.get("/", response_class=HTMLResponse)
def index(request:Request):
    templates=request.app.state.templates
    return templates.TemplateResponse(request,"index.html")