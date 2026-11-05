from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..engine.recommend import Engine
from ..store.models import Job
from .deps import get_engine

router = APIRouter()


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str, engine: Engine = Depends(get_engine)):
    job = engine.store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job_id")
    return job
