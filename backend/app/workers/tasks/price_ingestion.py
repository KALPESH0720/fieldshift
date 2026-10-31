"""Daily market price ingestion from a configured Agmarknet/OGD JSON API."""

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

import httpx

from celery.utils.log import get_task_logger
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.models.market_price import MarketPrice
from app.services.integrations.http import IntegrationUnavailable, request_json
from app.workers.celery_app import celery_app
from app.workers.tasks.common import WorkerSession, run_async
from config.settings import settings

logger = get_task_logger(__name__)


def normalize_price_row(row: dict) -> dict | None:
    """Map common Agmarknet and data.gov.in field spellings into model fields."""
    crop = _first(row, "commodity", "Commodity", "crop_name", "crop")
    mandi = _first(row, "market", "Market", "mandi_name", "mandi")
    modal = _first(row, "modal_price", "Modal_Price", "Modal Price", "modal price")
    minimum = _first(row, "min_price", "Min_Price", "Min_x0020_Price", "Minimum Price")
    maximum = _first(row, "max_price", "Max_Price", "Max_x0020_Price", "Maximum Price")
    price_date = _first(row, "arrival_date", "Arrival_Date", "Arrival Date", "date", "Date")
    reported_unit = _first(row, "price_unit", "unit", "Unit", "reporting_unit") or settings.agmarknet_default_price_unit
    district = _first(row, "district", "District")
    state = _first(row, "state", "State")
    variety = _first(row, "variety", "Variety")
    grade = _first(row, "grade", "Grade")
    mandi_code = _first(row, "market_code", "Market_Code", "mandi_code")
    commodity_code = _first(row, "commodity_code", "Commodity_Code")
    arrivals = _first(row, "arrivals", "Arrivals", "arrival_quantity", "Arrival_Quantity")
    arrivals_unit = _first(row, "arrivals_unit", "Arrivals_Unit", "unit_of_arrival")
    if not crop or not mandi or modal is None or price_date is None:
        return None
    try:
        price = Decimal(str(modal).replace(",", ""))
        parsed_date = _parse_date(str(price_date))
        reported_minimum = Decimal(str(minimum).replace(",", "")) if minimum is not None else None
        reported_maximum = Decimal(str(maximum).replace(",", "")) if maximum is not None else None
    except (InvalidOperation, ValueError):
        return None
    if price < 0 or (reported_minimum is not None and reported_minimum < 0) or (reported_maximum is not None and reported_maximum < 0):
        return None
    if reported_minimum is not None and reported_maximum is not None and reported_minimum > reported_maximum:
        return None
    try:
        arrivals_value = Decimal(str(arrivals).replace(",", "")) if arrivals is not None else None
        if arrivals_value is not None and arrivals_value < 0:
            return None
    except InvalidOperation:
        return None
    normalized_unit = "unknown"
    conversion = Decimal("1")
    if reported_unit:
        unit = str(reported_unit).strip().casefold().replace(" ", "")
        if unit in {"inr/kg", "rs/kg", "₹/kg", "rupees/kg"}:
            normalized_unit = "INR/kg"
        elif unit in {"inr/quintal", "rs/quintal", "rs/qtl", "inr/qtl", "₹/quintal", "₹/qtl"}:
            conversion = Decimal("0.01")
            normalized_unit = "INR/kg"
    normalized_price = price * conversion
    normalized_minimum = reported_minimum * conversion if reported_minimum is not None and normalized_unit != "unknown" else None
    normalized_maximum = reported_maximum * conversion if reported_maximum is not None and normalized_unit != "unknown" else None
    return {
        "crop_name": str(crop).strip(), "mandi_name": str(mandi).strip(),
        "modal_price": normalized_price, "date": parsed_date, "district": str(district).strip() if district else "",
        "state": str(state).strip() if state else None,
        "variety": str(variety).strip() if variety else None,
        "grade": str(grade).strip() if grade else None,
        "min_price": normalized_minimum, "max_price": normalized_maximum,
        "reported_min_price": reported_minimum, "reported_max_price": reported_maximum,
        "source": "AGMARKNET", "source_version": settings.agmarknet_resource_id or "unversioned",
        "currency": "INR", "price_unit": normalized_unit,
        "reported_unit": str(reported_unit) if reported_unit else None,
        "mandi_code": str(mandi_code) if mandi_code else None,
        "commodity_code": str(commodity_code) if commodity_code else None,
        "quality_status": "verified" if normalized_unit != "unknown" else "unit_unverified",
        "fetched_at": datetime.now(UTC),
        "arrivals_quantity": arrivals_value,
        "arrivals_unit": str(arrivals_unit) if arrivals_unit else None,
    }


def _first(row: dict, *keys):
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _parse_date(value: str) -> date:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value[:10], fmt).date()
        except ValueError:
            continue
    raise ValueError("Unsupported market price date")


async def _fetch_rows(*, client: httpx.AsyncClient | None = None) -> list[dict]:
    if not settings.agmarknet_api_url:
        raise IntegrationUnavailable("Agmarknet API URL is not configured")
    if settings.agmarknet_resource_id and "{resource_id}" in settings.agmarknet_api_url:
        url = settings.agmarknet_api_url.format(resource_id=settings.agmarknet_resource_id)
    elif settings.agmarknet_resource_id:
        url = f"{settings.agmarknet_api_url.rstrip('/')}/{settings.agmarknet_resource_id}"
    else:
        url = settings.agmarknet_api_url
    params = {"format": "json", "limit": settings.agmarknet_page_size, "offset": 0}
    if settings.agmarknet_api_key:
        params["api-key"] = settings.agmarknet_api_key.get_secret_value()
    rows: list[dict] = []
    for page in range(settings.agmarknet_max_pages):
        params["offset"] = page * settings.agmarknet_page_size
        result = await request_json(
            "GET", url, client=client, attempts=3,
            headers={"User-Agent": "FieldShiftBackend/1.0", "Accept": "application/json"},
            params=params,
        )
        if isinstance(result, list):
            records = [row for row in result if isinstance(row, dict)]
        else:
            records_value = result.get("records", result.get("data", [])) if isinstance(result, dict) else []
            records = [row for row in records_value if isinstance(row, dict)] if isinstance(records_value, list) else []
        rows.extend(records)
        if len(records) < settings.agmarknet_page_size:
            break
    return rows


async def _ingest() -> dict:
    rows = await _fetch_rows()
    inserted = updated = skipped = 0
    async with WorkerSession() as session:
        for source_row in rows:
            row = normalize_price_row(source_row)
            if row is None:
                skipped += 1
                continue
            existing = await session.scalar(select(MarketPrice).where(
                MarketPrice.crop_name == row["crop_name"],
                MarketPrice.mandi_name == row["mandi_name"],
                MarketPrice.date == row["date"],
                MarketPrice.district == row["district"],
                MarketPrice.state == row["state"],
                MarketPrice.variety == row["variety"],
                MarketPrice.grade == row["grade"],
            ))
            if existing:
                existing.modal_price = row["modal_price"]
                existing.source = row["source"]
                existing.source_version = row["source_version"]
                existing.price_unit = row["price_unit"]
                existing.reported_unit = row["reported_unit"]
                existing.mandi_code = row["mandi_code"]
                existing.commodity_code = row["commodity_code"]
                existing.quality_status = row["quality_status"]
                existing.state = row["state"]
                existing.variety = row["variety"]
                existing.grade = row["grade"]
                existing.min_price = row["min_price"]
                existing.max_price = row["max_price"]
                existing.reported_min_price = row["reported_min_price"]
                existing.reported_max_price = row["reported_max_price"]
                existing.fetched_at = row["fetched_at"]
                existing.arrivals_quantity = row["arrivals_quantity"]
                existing.arrivals_unit = row["arrivals_unit"]
                updated += 1
            else:
                session.add(MarketPrice(**row))
                inserted += 1
        await session.commit()
    logger.info("Market price ingestion complete: inserted=%s updated=%s skipped=%s", inserted, updated, skipped)
    return {"inserted": inserted, "updated": updated, "skipped": skipped}


@celery_app.task(name="field_shift.ingest_daily_prices", autoretry_for=(IntegrationUnavailable, SQLAlchemyError),
                 retry_backoff=True, retry_kwargs={"max_retries": 3})
def ingest_daily_prices() -> dict:
    return run_async(_ingest())
