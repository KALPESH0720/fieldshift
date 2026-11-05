from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Header, HTTPException, Request

from ..engine.recommend import Engine


def get_engine(request: Request) -> Engine:
    return request.app.state.engine


def require_api_key(request: Request, x_api_key: Optional[str] = Header(default=None)) -> None:
    """Service-to-service key check. Disabled when FIELDSHIFT_API_KEY is unset (local dev)."""
    expected = request.app.state.engine.settings.api_key
    if expected and not (x_api_key and secrets.compare_digest(x_api_key, expected)):
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")
