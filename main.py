import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.v1.routes import router
from services.quota_service import QuotaExhausted

log = logging.getLogger("wc")

app = FastAPI(title="World Cup QA")
app.include_router(router)


@app.exception_handler(QuotaExhausted)
async def _quota_handler(request: Request, exc: QuotaExhausted):
    return JSONResponse(status_code=429,
                        content={"detail": "API quota exhausted, try later"})


@app.exception_handler(ValueError)
async def _value_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(RuntimeError)
async def _runtime_handler(request: Request, exc: RuntimeError):
    log.exception("upstream error")
    return JSONResponse(status_code=502, content={"detail": "upstream data error"})
