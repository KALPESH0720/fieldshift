from __future__ import annotations

from fastapi import APIRouter, Depends

from ..engine.recommend import Engine
from ..store.models import ActionLog
from .deps import get_engine

router = APIRouter()


@router.post("/actions", status_code=201)
def log_action(action: ActionLog, engine: Engine = Depends(get_engine)):
    """Record what the farmer actually did. Pseudonymous plot id only."""
    if action.request_id and action.cell_id is None:
        original = engine.store.get_request(action.request_id)
        if original:
            from ..grid.snap import snap
            action = action.model_copy(update={"cell_id": snap(
                original.location.lat, original.location.lon, engine.settings.cell_size_deg).cell_id})
    engine.store.log_action(action)
    return {"status": "logged", "plot_id": action.plot_id}


@router.delete("/actions/{plot_id}")
def delete_actions(plot_id: str, engine: Engine = Depends(get_engine)):
    """Called when the backend deletes a farmer's data."""
    return {"deleted": engine.store.delete_actions(plot_id)}
