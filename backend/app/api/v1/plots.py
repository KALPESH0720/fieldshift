import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_farmer
from app.db.session import get_db
from app.models.farmer import Farmer
from app.models.plot import Plot
from app.schemas.plot import ACRES_PER_HECTARE, PlotCreate, PlotGeometry, PlotListResponse, PlotResponse, PlotUpdate
from app.services.sync.engine import record_change
from app.schemas.plot import PlotGeometry

router = APIRouter(prefix="/plots", tags=["plots"])


def _geometry_to_wkt(geometry: PlotGeometry | None) -> WKTElement | None:
    if geometry is None:
        return None
    coordinates = geometry.coordinates
    if geometry.type == "Point":
        x, y = coordinates
        wkt = f"POINT ({x} {y})"
    else:
        rings = ["(" + ", ".join(f"{x} {y}" for x, y in ring) + ")" for ring in coordinates]
        wkt = "POLYGON (" + ", ".join(rings) + ")"
    return WKTElement(wkt, srid=4326)


def _plot_response(plot: Plot, geojson: str | None) -> PlotResponse:
    location = json.loads(geojson) if geojson else None
    return PlotResponse(
        id=plot.id,
        farmer_id=plot.farmer_id,
        name=plot.name,
        area_acres=plot.area_acres,
        area_value=plot.area_value,
        area_unit=plot.area_unit,
        irrigation_type=plot.irrigation_type,
        location=location,
        is_archived=plot.is_archived,
    )


async def _fetch_plot(session: AsyncSession, plot_id: int, farmer_id: int) -> tuple[Plot, str | None] | None:
    result = await session.execute(
        select(Plot, func.ST_AsGeoJSON(Plot.location))
        .where(Plot.id == plot_id, Plot.farmer_id == farmer_id, Plot.is_archived.is_(False))
    )
    return result.one_or_none()


@router.get("", response_model=PlotListResponse)
async def list_plots(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> PlotListResponse:
    conditions = (Plot.farmer_id == farmer.id, Plot.is_archived.is_(False))
    total = await session.scalar(select(func.count(Plot.id)).where(*conditions)) or 0
    result = await session.execute(
        select(Plot, func.ST_AsGeoJSON(Plot.location))
        .where(*conditions)
        .order_by(Plot.id).limit(limit).offset(offset)
    )
    return PlotListResponse(items=[_plot_response(plot, geojson) for plot, geojson in result.all()], total=total, limit=limit, offset=offset)


@router.get("/{plot_id}", response_model=PlotResponse)
async def read_plot(
    plot_id: int,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> PlotResponse:
    row = await _fetch_plot(session, plot_id, farmer.id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plot not found")
    return _plot_response(*row)


@router.post("", response_model=PlotResponse, status_code=status.HTTP_201_CREATED)
async def create_plot(
    payload: PlotCreate,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> PlotResponse:
    await _validate_geometry_and_area(session, payload.location, payload.area_acres)
    values = payload.model_dump(exclude={"location"})
    plot = Plot(farmer_id=farmer.id, **values, location=_geometry_to_wkt(payload.location))
    session.add(plot)
    try:
        await session.flush()
        change_payload = {
            "id": plot.id,
            "farmer_id": farmer.id,
            **values,
            "area_acres": float(plot.area_acres),
            "location": payload.location.model_dump(mode="json") if payload.location else None,
        }
        await record_change(session, farmer_id=farmer.id, entity="plot", entity_id=plot.id, action="upsert", payload=change_payload)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plot could not be saved") from exc
    await session.refresh(plot)
    row = await _fetch_plot(session, plot.id, farmer.id)
    return _plot_response(*row)


@router.put("/{plot_id}", response_model=PlotResponse)
async def update_plot(
    plot_id: int,
    payload: PlotUpdate,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> PlotResponse:
    row = await _fetch_plot(session, plot_id, farmer.id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plot not found")
    plot, _ = row
    values = payload.model_dump(exclude_unset=True)
    for required_field in ("name", "area_acres"):
        if values.get(required_field, object()) is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{required_field} cannot be null")
    if "location" in values:
        await _validate_geometry_and_area(session, payload.location, float(plot.area_acres))
        plot.location = _geometry_to_wkt(payload.location)
        values.pop("location")
    area_fields = {"area_acres", "area_value", "area_unit"} & values.keys()
    if area_fields:
        unit = values.get("area_unit") or plot.area_unit
        if "area_value" in values:
            area_value = values["area_value"]
            area_acres = area_value * (ACRES_PER_HECTARE if unit == "hectare" else 1)
            if "area_acres" in values and abs(values["area_acres"] - area_acres) > max(0.01, area_acres * 0.001):
                raise HTTPException(status_code=422, detail="area_acres conflicts with area_value and area_unit")
        elif "area_acres" in values:
            area_acres = values["area_acres"]
            area_value = area_acres / (ACRES_PER_HECTARE if unit == "hectare" else 1)
        else:
            area_acres = float(plot.area_acres)
            area_value = area_acres / (ACRES_PER_HECTARE if unit == "hectare" else 1)
        if area_acres > 10_000_000:
            raise HTTPException(status_code=422, detail="Canonical plot area cannot exceed 10,000,000 acres")
        if "location" in payload.model_fields_set:
            await _validate_geometry_and_area(session, payload.location, area_acres)
        else:
            await _validate_existing_geometry_area(session, plot.id, area_acres)
        plot.area_acres = area_acres
        plot.area_value = area_value
        plot.area_unit = unit
        values = {key: value for key, value in values.items() if key not in {"area_acres", "area_value", "area_unit"}}
    for field, value in values.items():
        setattr(plot, field, value)
    try:
        plot.updated_at = datetime.now(UTC)
        await session.flush()
        change_payload = payload.model_dump(mode="json", exclude_unset=True)
        change_payload.update({"id": plot.id, "farmer_id": farmer.id, "updated_at": plot.updated_at.isoformat()})
        await record_change(session, farmer_id=farmer.id, entity="plot", entity_id=plot.id, action="upsert", payload=change_payload)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plot could not be updated") from exc
    await session.refresh(plot)
    result = await _fetch_plot(session, plot.id, farmer.id)
    return _plot_response(*result)


async def _validate_geometry_and_area(session: AsyncSession, geometry: PlotGeometry | None, area_acres: float) -> None:
    if geometry is None:
        return
    value = _geometry_to_wkt(geometry)
    result = await session.execute(
        select(func.ST_IsValid(value), func.ST_SRID(value), func.GeometryType(value),
               func.ST_Area(func.ST_Transform(value, 6933)) / 4046.8564224)
    )
    valid, srid, geometry_type, polygon_acres = result.one()
    expected_type = geometry.type.upper()
    if not valid or srid != 4326 or geometry_type.upper() != expected_type:
        raise HTTPException(status_code=422, detail="Location must be a valid WGS84 Point or Polygon")
    if geometry.type == "Polygon":
        _ensure_area_consistent(area_acres, float(polygon_acres))


async def _validate_existing_geometry_area(session: AsyncSession, plot_id: int, area_acres: float) -> None:
    geometry_type, polygon_acres = (await session.execute(
        select(func.GeometryType(Plot.location), func.ST_Area(func.ST_Transform(Plot.location, 6933)) / 4046.8564224)
        .where(Plot.id == plot_id)
    )).one()
    if geometry_type and geometry_type.upper() == "POLYGON":
        _ensure_area_consistent(area_acres, float(polygon_acres))


def _ensure_area_consistent(area_acres: float, polygon_acres: float) -> None:
    if polygon_acres <= 0 or abs(area_acres - polygon_acres) / max(area_acres, polygon_acres) > 0.25:
        raise HTTPException(status_code=422, detail="Entered plot area must be within 25% of the polygon area")


@router.delete("/{plot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_plot(
    plot_id: int,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> None:
    row = await _fetch_plot(session, plot_id, farmer.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Plot not found")
    plot, _ = row
    plot.is_archived = True
    await record_change(session, farmer_id=farmer.id, entity="plot", entity_id=plot.id,
                        action="delete", payload={"id": plot.id, "farmer_id": farmer.id, "is_archived": True})
    await session.commit()


@router.post("/{plot_id}/restore", response_model=PlotResponse)
async def restore_plot(
    plot_id: int,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> PlotResponse:
    result = await session.execute(select(Plot, func.ST_AsGeoJSON(Plot.location))
                                   .where(Plot.id == plot_id, Plot.farmer_id == farmer.id, Plot.is_archived.is_(True)))
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Archived plot not found")
    plot, geojson = row
    plot.is_archived = False
    await record_change(session, farmer_id=farmer.id, entity="plot", entity_id=plot.id,
                        action="upsert", payload={"id": plot.id, "farmer_id": farmer.id, "is_archived": False})
    await session.commit()
    await session.refresh(plot)
    return _plot_response(plot, geojson)
