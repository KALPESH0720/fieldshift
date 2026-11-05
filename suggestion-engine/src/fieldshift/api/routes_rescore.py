from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..engine.recommend import Engine
from ..store.models import RecommendResponse, RescoreRequest
from .deps import get_engine

router = APIRouter()


@router.post("/rescore", response_model=RecommendResponse)
def rescore(body: RescoreRequest, engine: Engine = Depends(get_engine)):
    """What-if: same request, new weights or flags. Cached indicators are reused, nothing is recomputed."""
    original = engine.store.get_request(body.request_id)
    if original is None:
        raise HTTPException(status_code=404, detail="unknown request_id")
    prefs = original.preferences.model_copy(deep=True)
    if body.weights is not None:
        prefs.weights = body.weights
    if body.flags is not None:
        prefs.flags = body.flags
    return engine.recommend(original.model_copy(update={"preferences": prefs}))
