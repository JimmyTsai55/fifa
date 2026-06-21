from fastapi import APIRouter, Depends

from api.v1.deps import require_api_key, get_use_case
from schemas.qa import AskRequest, AskResponse

router = APIRouter()


@router.get("/healthz")
async def healthz():
    return {"status": "ok"}


@router.post("/ask", response_model=AskResponse,
             dependencies=[Depends(require_api_key)])
async def ask(req: AskRequest, use_case=Depends(get_use_case)):
    return await use_case.execute(req.question)
