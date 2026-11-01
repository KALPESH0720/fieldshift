from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..engine.recommend import Engine
from ..store.models import RecommendRequest, RecommendResponse
from .deps import get_engine

router = APIRouter()


@router.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest, engine: Engine = Depends(get_engine)):
    try:
        return engine.recommend(req)
    except ValueError as e:  # bad season name, unit, etc.
        raise HTTPException(status_code=422, detail=str(e))
