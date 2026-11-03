from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from ..engine.recommend import Engine
from ..store.models import Indicator
from .deps import get_engine

router = APIRouter()


class IndicatorsIn(BaseModel):
    """Posted by the deep-tier pipeline (P2) when a job finishes."""
    model_config = ConfigDict(extra="forbid")
    cache_key: str
    job_id: Optional[str] = None
    indicators: list[Indicator] = []
    error: Optional[str] = None


@router.post("/indicators")
def put_indicators(body: IndicatorsIn, engine: Engine = Depends(get_engine)):
    job = engine.store.get_job(body.job_id) if body.job_id else None
    if body.job_id and job is None:
        raise HTTPException(status_code=404, detail="unknown job_id")
    if job is not None and job.cache_key != body.cache_key:
        raise HTTPException(status_code=422, detail="cache_key does not match the job")
    if body.error:
        if job is not None:
            engine.store.update_job(job.job_id, status="failed", error=body.error)
        return {"status": "failed_recorded"}
    if not body.indicators:
        raise HTTPException(status_code=422, detail="no indicators and no error given")
    engine.store.put_indicators(body.cache_key, body.indicators)
    if job is not None:
        engine.store.update_job(job.job_id, status="done")
    return {"status": "stored", "count": len(body.indicators)}
