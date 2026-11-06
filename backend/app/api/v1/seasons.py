import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.season import Season
from app.models.crop_record import CropRecord
from app.schemas.season import SeasonCreateRequest, SeasonResponse, SeasonSeedRequest, SeasonSeedResponse, SeasonUpdateRequest
from config.settings import settings

router = APIRouter(prefix="/seasons", tags=["seasons"])


def _require_admin_key(candidate: str | None) -> None:
    configured = settings.admin_api_key.get_secret_value() if settings.admin_api_key else ""
    if not configured:
        raise HTTPException(status_code=503, detail="Season administration is not configured")
    if candidate is None or not hmac.compare_digest(candidate, configured):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credential")


@router.get("", response_model=list[SeasonResponse])
async def list_seasons(
    district: str | None = Query(default=None, min_length=1, max_length=120),
    year: int | None = Query(default=None, ge=2000, le=2100),
    session: AsyncSession = Depends(get_db),
) -> list[SeasonResponse]:
    query = select(Season)
    if district is not None:
        query = query.where(Season.district == district)
    if year is not None:
        query = query.where(Season.year == year)
    rows = (await session.scalars(query.order_by(Season.year.desc().nullslast(), Season.name))).all()
    return [SeasonResponse.model_validate(row, from_attributes=True) for row in rows]


@router.put("/seed", response_model=SeasonSeedResponse)
async def seed_baseline_seasons(
    payload: SeasonSeedRequest,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    session: AsyncSession = Depends(get_db),
) -> SeasonSeedResponse:
    _require_admin_key(x_admin_key)

    definitions = (("kharif", "Kharif", 6, 10), ("rabi", "Rabi", 10, 3), ("zaid", "Zaid", 3, 6))
    seasons = []
    for code, label, start, end in definitions:
        season = await session.scalar(select(Season).where(
            Season.district == payload.district,
            Season.year == payload.year,
            Season.season_code == code,
        ))
        if season is None:
            season = Season(name=f"{label} {payload.year} ({payload.district})", district=payload.district,
                            year=payload.year, season_code=code, start_month=start, end_month=end)
            session.add(season)
        seasons.append(season)
    await session.commit()
    for season in seasons:
        await session.refresh(season)
    return SeasonSeedResponse(district=payload.district, year=payload.year,
                              seasons=[SeasonResponse.model_validate(item, from_attributes=True) for item in seasons])


@router.post("", response_model=SeasonResponse, status_code=status.HTTP_201_CREATED)
async def create_season(
    payload: SeasonCreateRequest,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    session: AsyncSession = Depends(get_db),
) -> SeasonResponse:
    _require_admin_key(x_admin_key)
    season = Season(**payload.model_dump())
    session.add(season)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="A season with this district, year, and code already exists") from exc
    await session.refresh(season)
    return SeasonResponse.model_validate(season, from_attributes=True)


@router.put("/{season_id}", response_model=SeasonResponse)
async def update_season(
    season_id: int,
    payload: SeasonUpdateRequest,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    session: AsyncSession = Depends(get_db),
) -> SeasonResponse:
    _require_admin_key(x_admin_key)
    season = await session.get(Season, season_id)
    if season is None:
        raise HTTPException(status_code=404, detail="Season not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")
        setattr(season, field, value)
    await session.commit()
    await session.refresh(season)
    return SeasonResponse.model_validate(season, from_attributes=True)


@router.delete("/{season_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_season(
    season_id: int,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    session: AsyncSession = Depends(get_db),
) -> Response:
    _require_admin_key(x_admin_key)
    season = await session.get(Season, season_id)
    if season is None:
        raise HTTPException(status_code=404, detail="Season not found")
    used = await session.scalar(select(CropRecord.id).where(CropRecord.season_id == season_id).limit(1))
    if used is not None:
        raise HTTPException(status_code=409, detail="Season cannot be deleted while crop history references it")
    await session.delete(season)
    await session.commit()
    return Response(status_code=204)
