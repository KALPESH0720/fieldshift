from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..engine.recommend import Engine
from ..grid.snap import snap
from ..store.models import Alert
from .deps import get_engine

router = APIRouter()


@router.get("/alerts", response_model=list[Alert])
def alerts(
    cell_id: Optional[str] = None,
    lat: Optional[float] = Query(default=None, ge=-90, le=90),
    lon: Optional[float] = Query(default=None, ge=-180, le=180),
    engine: Engine = Depends(get_engine),
):
    """Alerts written by the season monitor (pipeline P3), by cell id or by point."""
    if cell_id is None:
        if lat is None or lon is None:
            raise HTTPException(status_code=422, detail="give cell_id, or lat and lon")
        cell_id = snap(lat, lon, engine.settings.cell_size_deg).cell_id
    return engine.store.list_alerts(cell_id)
