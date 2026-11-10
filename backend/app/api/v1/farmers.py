from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_farmer, get_current_phone
from app.db.session import get_db
from app.models.farmer import Farmer
from app.models.plot import Plot
from app.models.crop_record import CropRecord
from app.models.soil_test import SoilTest
from app.models.alert import Alert
from app.models.recommendation import RecommendationRun
from app.models.sync import SyncChange, SyncOperationLog
from app.redis.client import get_redis
from app.schemas.farmer import FarmerCreate, FarmerResponse, FarmerUpdate
from app.services.suggestion_engine import suggestion_engine
from config.settings import settings
from redis.asyncio import Redis

router = APIRouter(prefix="/farmers", tags=["farmers"])


@router.get("/me", response_model=FarmerResponse)
async def read_my_profile(farmer: Farmer = Depends(get_current_farmer)) -> Farmer:
    return farmer


@router.post("/me", response_model=FarmerResponse, status_code=status.HTTP_201_CREATED)
async def create_my_profile(
    payload: FarmerCreate,
    phone: str = Depends(get_current_phone),
    session: AsyncSession = Depends(get_db),
) -> Farmer:
    existing = await session.scalar(select(Farmer).where(Farmer.phone == phone))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Farmer profile already exists")
    farmer = Farmer(phone=phone, **payload.model_dump())
    session.add(farmer)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Farmer profile already exists") from exc
    await session.refresh(farmer)
    return farmer


@router.patch("/me", response_model=FarmerResponse)
@router.put("/me", response_model=FarmerResponse)
async def update_my_profile(
    payload: FarmerUpdate,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> Farmer:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(farmer, field, value)
    await session.commit()
    await session.refresh(farmer)
    return farmer


def _model_rows(rows) -> list[dict]:
    return [jsonable_encoder({column.name: getattr(row, column.name) for column in row.__table__.columns}) for row in rows]


@router.get("/me/export")
async def export_my_account(
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> dict:
    plots = (await session.scalars(select(Plot).where(Plot.farmer_id == farmer.id))).all()
    plot_ids = [plot.id for plot in plots]
    crop_records = (await session.scalars(select(CropRecord).where(CropRecord.plot_id.in_(plot_ids)))).all() if plot_ids else []
    soil_tests = (await session.scalars(select(SoilTest).where(SoilTest.plot_id.in_(plot_ids)))).all() if plot_ids else []
    alerts = (await session.scalars(select(Alert).where(Alert.farmer_id == farmer.id))).all()
    sync_changes = (await session.scalars(select(SyncChange).where(SyncChange.farmer_id == farmer.id))).all()
    sync_operations = (await session.scalars(select(SyncOperationLog).where(SyncOperationLog.farmer_id == farmer.id))).all()
    plot_data = []
    for plot in plots:
        geojson = await session.scalar(select(func.ST_AsGeoJSON(Plot.location)).where(Plot.id == plot.id)) if plot.location else None
        plot_data.append({"id": plot.id, "farmer_id": plot.farmer_id, "name": plot.name,
                          "area_acres": jsonable_encoder(plot.area_acres), "location": geojson,
                          "irrigation_type": plot.irrigation_type, "updated_at": jsonable_encoder(plot.updated_at)})
    return {"profile": jsonable_encoder({column.name: getattr(farmer, column.name) for column in farmer.__table__.columns}),
            "plots": plot_data, "crop_records": _model_rows(crop_records),
            "soil_tests": _model_rows(soil_tests), "alerts": _model_rows(alerts),
            "sync_changes": _model_rows(sync_changes), "sync_operations": _model_rows(sync_operations)}


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Response:
    # The engine stores pseudonymous action logs outside PostgreSQL. Remove those
    # records before deleting their owning backend account/plots.
    run_rows = (await session.execute(select(RecommendationRun.plot_id, RecommendationRun.request_snapshot).where(
        RecommendationRun.farmer_id == farmer.id,
    ))).all()
    plot_ids = {plot_id for plot_id, snapshot in run_rows if snapshot.get("engine_request")}
    for plot_id in plot_ids:
        await suggestion_engine.request("DELETE", f"/actions/{plot_id}")
    # JWTs expire after 60 minutes by default; this subject revocation makes
    # deletion and incident response effective immediately for outstanding tokens.
    await redis.set(f"auth:revoked_before:{farmer.phone}", str(int(datetime.now(UTC).timestamp())),
                    ex=settings.access_token_expire_minutes * 60)
    await session.delete(farmer)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
