from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_farmer
from app.db.session import get_db
from app.models.crop_record import CropRecord
from app.models.farmer import Farmer
from app.models.plot import Plot
from app.models.season import Season
from app.schemas.plot import CropHistoryCreate, CropHistoryUpdate, PlotHistoryItem, PlotHistoryResponse
from app.services.sync.engine import record_change

router = APIRouter(tags=["crop history"])


async def _require_owned_plot(session: AsyncSession, plot_id: int, farmer_id: int) -> None:
    plot = await session.scalar(select(Plot.id).where(Plot.id == plot_id, Plot.farmer_id == farmer_id, Plot.is_archived.is_(False)))
    if plot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plot not found")


@router.get("/plots/{plot_id}/history", response_model=PlotHistoryResponse)
async def get_plot_history(
    plot_id: int,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> PlotHistoryResponse:
    await _require_owned_plot(session, plot_id, farmer.id)
    conditions = (CropRecord.plot_id == plot_id,)
    total = await session.scalar(select(func.count(CropRecord.id)).where(*conditions)) or 0
    result = await session.scalars(
        select(CropRecord)
        .where(*conditions)
        .order_by(CropRecord.season_id.desc(), CropRecord.id.desc()).limit(limit).offset(offset)
    )
    return PlotHistoryResponse(
        plot_id=plot_id,
        items=[PlotHistoryItem.model_validate(record) for record in result.all()], total=total, limit=limit, offset=offset,
    )


@router.post(
    "/plots/{plot_id}/history",
    response_model=PlotHistoryItem,
    status_code=status.HTTP_201_CREATED,
)
async def add_plot_history(
    plot_id: int,
    payload: CropHistoryCreate,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> PlotHistoryItem:
    await _require_owned_plot(session, plot_id, farmer.id)
    season_exists = await session.scalar(select(Season.id).where(Season.id == payload.season_id))
    if season_exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    duplicate = await session.scalar(select(CropRecord.id).where(CropRecord.plot_id == plot_id,
                                                                    CropRecord.season_id == payload.season_id,
                                                                    CropRecord.crop_name == payload.crop_name))
    if duplicate is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Crop already exists in this plot and season")
    record = CropRecord(plot_id=plot_id, **payload.model_dump())
    session.add(record)
    try:
        await session.flush()
        change_payload = {
            "id": record.id,
            "plot_id": record.plot_id,
            "season_id": record.season_id,
            "crop_name": record.crop_name,
            "crop_family": record.crop_family,
            "yield_kg": float(record.yield_kg) if record.yield_kg is not None else None,
            "input_costs": float(record.input_costs) if record.input_costs is not None else None,
            "outcome_notes": record.outcome_notes,
            "updated_at": record.updated_at.isoformat(),
        }
        await record_change(session, farmer_id=farmer.id, entity="crop_record", entity_id=record.id, action="upsert", payload=change_payload)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate crop history record") from exc
    await session.refresh(record)
    return PlotHistoryItem.model_validate(record)


@router.put("/plots/{plot_id}/history/{record_id}", response_model=PlotHistoryItem)
async def update_plot_history(
    plot_id: int,
    record_id: int,
    payload: CropHistoryUpdate,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> PlotHistoryItem:
    await _require_owned_plot(session, plot_id, farmer.id)
    record = await session.scalar(select(CropRecord).where(CropRecord.id == record_id, CropRecord.plot_id == plot_id))
    if record is None:
        raise HTTPException(status_code=404, detail="Crop history record not found")
    values = payload.model_dump(exclude_unset=True)
    if "season_id" in values and await session.scalar(select(Season.id).where(Season.id == values["season_id"])) is None:
        raise HTTPException(status_code=404, detail="Season not found")
    crop_name = values.get("crop_name", record.crop_name)
    season_id = values.get("season_id", record.season_id)
    duplicate = await session.scalar(select(CropRecord.id).where(
        CropRecord.plot_id == plot_id, CropRecord.season_id == season_id,
        CropRecord.crop_name == crop_name, CropRecord.id != record.id,
    ))
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Crop already exists in this plot and season")
    for field, value in values.items():
        setattr(record, field, value)
    record.updated_at = datetime.now(UTC)
    try:
        await session.flush()
        await record_change(session, farmer_id=farmer.id, entity="crop_record", entity_id=record.id,
                            action="upsert", payload={"id": record.id, "plot_id": plot_id, **values,
                                                        "season_id": record.season_id, "crop_name": record.crop_name})
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Duplicate crop history record") from exc
    await session.refresh(record)
    return PlotHistoryItem.model_validate(record)


@router.delete("/plots/{plot_id}/history/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plot_history(
    plot_id: int,
    record_id: int,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> Response:
    await _require_owned_plot(session, plot_id, farmer.id)
    record = await session.scalar(select(CropRecord).where(CropRecord.id == record_id, CropRecord.plot_id == plot_id))
    if record is None:
        raise HTTPException(status_code=404, detail="Crop history record not found")
    await record_change(session, farmer_id=farmer.id, entity="crop_record", entity_id=record.id,
                        action="delete", payload={"id": record.id, "plot_id": plot_id})
    await session.delete(record)
    await session.commit()
    return Response(status_code=204)
