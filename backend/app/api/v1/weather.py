from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.api.dependencies import get_current_farmer
from app.db.session import get_db
from app.models.alert import Alert
from app.models.farmer import Farmer
from app.models.farmer_preferences import FarmerPreferences
from app.models.plot import Plot
from app.models.weather_snapshot import WeatherSnapshot
from app.redis.client import get_redis
from app.schemas.weather import (
    AlertResponse, FarmerNotificationPreferences, FarmerNotificationPreferencesResponse,
    WeatherForecastResponse, WeatherSnapshotHistoryItem,
)
from app.services.integrations.http import IntegrationUnavailable
from app.services.integrations.weather_api import IMDAdapter
from app.services.weather import forecast_for_plot

router = APIRouter(prefix="/weather", tags=["weather and alerts"])


async def _owned_plot(session: AsyncSession, plot_id: int, farmer_id: int) -> Plot:
    row = await session.scalar(select(Plot).where(
        Plot.id == plot_id, Plot.farmer_id == farmer_id, Plot.is_archived.is_(False),
    ))
    if row is None:
        raise HTTPException(status_code=404, detail="Plot not found")
    return row


@router.get("/plots/{plot_id}/forecast", response_model=WeatherForecastResponse)
async def get_plot_forecast(
    plot_id: int,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> WeatherForecastResponse:
    plot = await _owned_plot(session, plot_id, farmer.id)
    try:
        return await forecast_for_plot(session, farmer, plot, redis)
    except IntegrationUnavailable as exc:
        raise HTTPException(status_code=503, detail="Weather provider is unavailable or returned invalid data") from exc


@router.get("/plots/{plot_id}/official-warnings")
async def get_plot_official_warnings(
    plot_id: int,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return IMD's district warning records without deriving numeric forecasts."""
    plot = await _owned_plot(session, plot_id, farmer.id)
    if not plot.district:
        raise HTTPException(status_code=422, detail="Plot district is required for official weather warnings")
    try:
        warnings = await IMDAdapter().district_warnings(plot.district)
    except IntegrationUnavailable as exc:
        raise HTTPException(status_code=503, detail="Official IMD warnings are unavailable") from exc
    return {"plot_id": plot.id, "district": plot.district, "provider": "imd",
            "warnings": warnings, "count": len(warnings)}


@router.get("/plots/{plot_id}/snapshots", response_model=list[WeatherSnapshotHistoryItem])
async def get_plot_weather_snapshots(
    plot_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> list[WeatherSnapshotHistoryItem]:
    await _owned_plot(session, plot_id, farmer.id)
    rows = (await session.scalars(select(WeatherSnapshot).where(
        WeatherSnapshot.plot_id == plot_id, WeatherSnapshot.farmer_id == farmer.id,
    ).order_by(WeatherSnapshot.fetched_at.desc(), WeatherSnapshot.id.desc()).limit(limit).offset(offset))).all()
    return [WeatherSnapshotHistoryItem.model_validate(row, from_attributes=True) for row in rows]


@router.get("/preferences", response_model=FarmerNotificationPreferencesResponse)
async def get_notification_preferences(
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> FarmerNotificationPreferencesResponse:
    row = await session.get(FarmerPreferences, farmer.id)
    data = FarmerNotificationPreferences.model_validate(row, from_attributes=True) if row else FarmerNotificationPreferences()
    return FarmerNotificationPreferencesResponse(farmer_id=farmer.id, **data.model_dump())


@router.put("/preferences", response_model=FarmerNotificationPreferencesResponse)
async def update_notification_preferences(
    payload: FarmerNotificationPreferences,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> FarmerNotificationPreferencesResponse:
    try:
        ZoneInfo(payload.timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="timezone must be a valid IANA timezone") from exc
    row = await session.get(FarmerPreferences, farmer.id)
    if row is None:
        row = FarmerPreferences(farmer_id=farmer.id)
        session.add(row)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    await session.commit()
    await session.refresh(row)
    return FarmerNotificationPreferencesResponse(farmer_id=farmer.id, **payload.model_dump())


@router.get("/alerts", response_model=list[AlertResponse])
async def list_my_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> list[AlertResponse]:
    rows = (await session.scalars(select(Alert).where(Alert.farmer_id == farmer.id)
                                  .order_by(Alert.created_at.desc(), Alert.id.desc())
                                  .limit(limit).offset(offset))).all()
    return [AlertResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("/alerts/{alert_id}/replay", response_model=AlertResponse)
async def replay_my_dead_letter(
    alert_id: int,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> AlertResponse:
    row = await session.scalar(select(Alert).where(Alert.id == alert_id, Alert.farmer_id == farmer.id))
    if row is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    if row.status != "dead_letter":
        raise HTTPException(status_code=409, detail="Only dead-letter alerts can be replayed")
    row.status = "pending"
    row.attempt_count = 0
    row.next_attempt_at = datetime.now(UTC)
    row.last_error_code = None
    row.dead_lettered_at = None
    await session.commit()
    await session.refresh(row)
    return AlertResponse.model_validate(row, from_attributes=True)
