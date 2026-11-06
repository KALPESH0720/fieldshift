import hmac
from datetime import UTC, date, datetime, timedelta
from statistics import mean

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_farmer
from app.db.session import get_db
from app.models.farmer import Farmer
from app.models.market_price import MarketPrice, MinimumSupportPrice
from app.models.pest_host_rule import PestHostRule
from app.models.crop_record import CropRecord
from app.models.season import Season
from app.services.integrations.http import IntegrationUnavailable
from config.settings import settings

router = APIRouter(prefix="/market", tags=["market context"])


class MSPImport(BaseModel):
    crop_name: str = Field(min_length=1, max_length=120)
    season: str = Field(min_length=1, max_length=80)
    year: int = Field(ge=2000, le=2100)
    amount: float = Field(gt=0)
    currency: str = Field(default="INR", pattern="^[A-Z]{3}$")
    price_unit: str = Field(default="INR/quintal", max_length=32)
    effective_from: date
    effective_to: date | None = None
    source: str = Field(min_length=1, max_length=240)
    source_version: str = Field(min_length=1, max_length=120)


class PestRuleDraft(BaseModel):
    target_crop: str = Field(min_length=1, max_length=120)
    pest_name: str = Field(min_length=1, max_length=160)
    host_crops: list[str] = []
    host_families: list[str] = []
    effective_region: str = Field(min_length=1, max_length=120)
    season: str = Field(min_length=1, max_length=80)
    version: int = Field(ge=1)
    risk_points: float = Field(default=20, ge=0, le=100)
    source_title: str = Field(min_length=1, max_length=240)
    source_url: str = Field(min_length=1, max_length=2048)
    source_version: str = Field(min_length=1, max_length=120)
    notes: str | None = None


def _admin(value: str | None) -> None:
    secret = settings.admin_api_key.get_secret_value() if settings.admin_api_key else ""
    if not secret:
        raise HTTPException(status_code=503, detail="Market administration is not configured")
    if value is None or not hmac.compare_digest(value, secret):
        raise HTTPException(status_code=401, detail="Invalid admin credential")


@router.get("/prices")
async def price_history(
    crop: str = Query(min_length=1, max_length=120), district: str = Query(min_length=1, max_length=120),
    limit: int = Query(default=30, ge=1, le=100), offset: int = Query(default=0, ge=0),
    farmer: Farmer = Depends(get_current_farmer), session: AsyncSession = Depends(get_db),
) -> dict:
    del farmer
    rows = (await session.scalars(select(MarketPrice).where(
        MarketPrice.crop_name.ilike(crop), MarketPrice.district.ilike(district),
    ).order_by(MarketPrice.date.desc(), MarketPrice.id.desc()).offset(offset).limit(limit))).all()
    today = date.today()
    return {"items": [{"id": p.id, "crop": p.crop_name, "mandi": p.mandi_name, "mandi_code": p.mandi_code,
                       "district": p.district, "state": p.state, "variety": p.variety, "grade": p.grade,
                       "price": str(p.modal_price), "min_price": str(p.min_price) if p.min_price is not None else None,
                       "max_price": str(p.max_price) if p.max_price is not None else None,
                       "reported_min_price": str(p.reported_min_price) if p.reported_min_price is not None else None,
                       "reported_max_price": str(p.reported_max_price) if p.reported_max_price is not None else None,
                       "currency": p.currency,
                       "unit": p.price_unit, "date": p.date, "fetched_at": p.fetched_at,
                       "source": p.source, "source_version": p.source_version,
                       "quality_status": p.quality_status,
                       "arrivals_quantity": str(p.arrivals_quantity) if p.arrivals_quantity is not None else None,
                       "arrivals_unit": p.arrivals_unit, "age_days": (today-p.date).days,
                       "fresh": p.date <= today and p.date >= today-timedelta(days=30) and p.quality_status == "verified"}
                      for p in rows], "limit": limit, "offset": offset}


@router.get("/prices/curve")
async def price_curve(crop: str = Query(min_length=1, max_length=120),
                      district: str = Query(min_length=1, max_length=120),
                      farmer: Farmer = Depends(get_current_farmer),
                      session: AsyncSession = Depends(get_db)) -> dict:
    del farmer
    today = date.today()
    rows = (await session.scalars(select(MarketPrice).where(
        MarketPrice.crop_name.ilike(crop), MarketPrice.district.ilike(district),
        MarketPrice.date >= today - timedelta(days=180), MarketPrice.date <= today,
        MarketPrice.quality_status == "verified", MarketPrice.price_unit == "INR/kg",
    ).order_by(MarketPrice.date, MarketPrice.id))).all()
    points = [{"date": row.date, "price": str(row.modal_price), "currency": row.currency,
               "unit": row.price_unit, "source": row.source, "source_version": row.source_version,
               "arrivals_quantity": str(row.arrivals_quantity) if row.arrivals_quantity is not None else None,
               "arrivals_unit": row.arrivals_unit} for row in rows]
    dates = {row.date for row in rows}
    arrival_rows = [row for row in rows if row.arrivals_quantity is not None and row.arrivals_unit]
    supply_dates = {row.date for row in arrival_rows}
    glut = {"status": "unavailable", "reason": "At least 60 daily price records and 30 sourced arrival observations are required."}
    if len(dates) >= 60 and len(supply_dates) >= 30:
        recent_supply = [float(row.arrivals_quantity) for row in arrival_rows if row.date >= today - timedelta(days=7)]
        baseline_supply = [float(row.arrivals_quantity) for row in arrival_rows if today - timedelta(days=90) <= row.date < today - timedelta(days=7)]
        recent_prices = [float(row.modal_price) for row in rows if row.date >= today - timedelta(days=7)]
        baseline_prices = [float(row.modal_price) for row in rows if today - timedelta(days=30) <= row.date < today - timedelta(days=7)]
        if recent_supply and baseline_supply and recent_prices and baseline_prices:
            elevated_supply = mean(recent_supply) > mean(baseline_supply) * 1.25
            falling_prices = mean(recent_prices) < mean(baseline_prices) * 0.90
            glut = {"status": "heuristic", "signal": "elevated_glut_risk" if elevated_supply and falling_prices else "not_indicated",
                    "uncertainty": "high", "method": "7-day arrivals > 1.25x 90-day baseline and 7-day price < 90% of 30-day baseline",
                    "observations": len(supply_dates), "source": "market price feed arrivals"}
    last_day = max((row.date for row in rows), default=None)
    return {"crop": crop, "district": district, "currency": "INR", "unit": "INR/kg", "items": points,
            "glut_context": glut, "freshness": {"last_observed": last_day,
            "age_days": (today - last_day).days if last_day else None, "source_records": len(rows)}}


@router.get("/msp")
async def msp_history(crop: str = Query(min_length=1, max_length=120),
                       farmer: Farmer = Depends(get_current_farmer),
                       session: AsyncSession = Depends(get_db)) -> list[dict]:
    del farmer
    rows = (await session.scalars(select(MinimumSupportPrice).where(
        MinimumSupportPrice.crop_name.ilike(crop)
    ).order_by(MinimumSupportPrice.year.desc(), MinimumSupportPrice.effective_from.desc()))).all()
    return [{"id": r.id, "crop": r.crop_name, "season": r.season, "year": r.year, "amount": str(r.amount),
             "currency": r.currency, "unit": r.price_unit, "effective_from": r.effective_from,
             "effective_to": r.effective_to, "source": r.source, "source_version": r.source_version} for r in rows]


@router.post("/admin/ingest")
async def run_price_ingestion(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")) -> dict:
    _admin(x_admin_key)
    from app.workers.tasks.price_ingestion import _ingest
    try:
        return await _ingest()
    except IntegrationUnavailable as exc:
        # Keep provider details/URLs out of API responses and logs.
        raise HTTPException(status_code=503, detail="AGMARKNET provider unavailable or returned an unsupported response") from exc


@router.put("/admin/msp", status_code=201)
async def upsert_msp(payload: MSPImport, x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
                     session: AsyncSession = Depends(get_db)) -> dict:
    _admin(x_admin_key)
    if payload.effective_to and payload.effective_to < payload.effective_from:
        raise HTTPException(status_code=422, detail="effective_to must be on or after effective_from")
    row = await session.scalar(select(MinimumSupportPrice).where(
        MinimumSupportPrice.crop_name == payload.crop_name, MinimumSupportPrice.season == payload.season,
        MinimumSupportPrice.year == payload.year, MinimumSupportPrice.source_version == payload.source_version,
    ))
    values = payload.model_dump()
    if row is None:
        row = MinimumSupportPrice(**values)
        session.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Duplicate MSP source record") from exc
    await session.refresh(row)
    return {"id": row.id, "crop": row.crop_name, "season": row.season, "year": row.year,
            "amount": str(row.amount), "source": row.source, "source_version": row.source_version}


@router.post("/admin/pest-rules", status_code=201)
async def create_pest_rule(payload: PestRuleDraft, x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
                           session: AsyncSession = Depends(get_db)) -> dict:
    _admin(x_admin_key)
    row = PestHostRule(**payload.model_dump(), status="draft", reviewer_ids=[])
    session.add(row)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Pest knowledge version already exists") from exc
    await session.refresh(row)
    return _pest_dto(row)


@router.post("/admin/pest-rules/{rule_id}/approve")
async def approve_pest_rule(rule_id: int, x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
                            x_reviewer_id: str | None = Header(default=None, alias="X-Reviewer-ID"),
                            x_reviewer_key: str | None = Header(default=None, alias="X-Reviewer-Key"),
                            session: AsyncSession = Depends(get_db)) -> dict:
    _admin(x_admin_key)
    reviewer = (x_reviewer_id or "").strip()
    secret = settings.agronomist_reviewer_keys.get(reviewer)
    if not secret or not x_reviewer_key or not hmac.compare_digest(secret.get_secret_value(), x_reviewer_key):
        raise HTTPException(status_code=403, detail="Reviewer is not in the configured agronomist allowlist")
    row = await session.get(PestHostRule, rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Pest rule not found")
    if row.status not in {"draft", "in_review"}:
        raise HTTPException(status_code=409, detail="Pest rule is already finalized")
    ids = list(row.reviewer_ids or [])
    if reviewer in ids:
        raise HTTPException(status_code=409, detail="Reviewer already approved this record")
    ids.append(reviewer)
    row.reviewer_ids = ids
    if len(ids) >= 2:
        row.status = "active"
        row.approved_at = datetime.now(UTC)
    else:
        row.status = "in_review"
    await session.commit()
    await session.refresh(row)
    return _pest_dto(row)


def _pest_dto(row: PestHostRule) -> dict:
    return {"id": row.id, "target_crop": row.target_crop, "pest_name": row.pest_name,
            "host_crops": row.host_crops, "host_families": row.host_families, "region": row.effective_region,
            "season": row.season, "version": row.version, "risk_points": row.risk_points,
            "source_title": row.source_title, "source_url": row.source_url,
            "source_version": row.source_version, "status": row.status, "reviewer_ids": row.reviewer_ids,
            "approved_at": row.approved_at}
