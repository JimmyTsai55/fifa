from fastapi import Header, HTTPException, status

import config
from core.container import build_use_case

_use_case = None


def get_use_case():
    global _use_case
    if _use_case is None:
        _use_case = build_use_case()
    return _use_case


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    allowed = config.api_keys()
    if not allowed or x_api_key not in allowed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="invalid or missing API key")
