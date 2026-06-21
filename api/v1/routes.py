from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from api.v1.deps import require_api_key, get_use_case
from schemas.qa import AskRequest, AskResponse

router = APIRouter()

_STATIC_DIR = Path(__file__).resolve().parents[2] / "static"


@router.get("/healthz")
async def healthz():
    return {"status": "ok"}


@router.get("/", include_in_schema=False)
async def index():
    return FileResponse(_STATIC_DIR / "chat.html")


@router.post("/chat", response_model=AskResponse)
async def chat(req: AskRequest, use_case=Depends(get_use_case)):
    """Public front-end entry point.

    The API key lives server-side; the browser never sees it. This reuses the
    same use case as /ask, so the quota / value / runtime exception handlers in
    main.py apply unchanged (429 / 422 / 502).
    """
    return await use_case.execute(req.question)


@router.post("/ask", response_model=AskResponse,
             dependencies=[Depends(require_api_key)])
async def ask(req: AskRequest, use_case=Depends(get_use_case)):
    return await use_case.execute(req.question)
