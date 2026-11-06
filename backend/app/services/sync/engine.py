"""Transactional, idempotent delta-sync application for plots and crop records."""

from datetime import UTC, datetime, timedelta
from typing import Any

from geoalchemy2.elements import WKTElement
from pydantic import TypeAdapter
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crop_record import CropRecord
from app.models.plot import Plot
from app.models.sync import SyncChange, SyncOperationLog
from app.schemas.sync import (
    ConflictResolution,
    ConflictStrategy,
    SyncAction,
    SyncOperation,
    SyncPayload,
    SyncResponse,
)
from app.schemas.plot import CropHistoryCreate, PlotCreate, PlotGeometry, PlotUpdate, from_acres, to_acres

PLOT_FIELDS = {"name", "area_acres", "area_value", "area_unit", "irrigation_type", "location", "district"}
CROP_FIELDS = {"plot_id", "season_id", "crop_name", "crop_family", "yield_kg", "input_costs", "outcome_notes"}


async def record_change(
    session: AsyncSession,
    *,
    farmer_id: int,
    entity: str,
    entity_id: int | str,
    action: str,
    payload: dict[str, Any],
) -> SyncChange:
    """Append a durable change event in the same transaction as the entity write."""
    change = SyncChange(
        farmer_id=farmer_id,
        entity=entity,
        entity_id=str(entity_id),
        action=action,
        payload=payload,
    )
    session.add(change)
    await session.flush()
    return change


class SyncEngine:
    async def apply(self, session: AsyncSession, farmer_id: int, payload: SyncPayload) -> SyncResponse:
        cursor = self._parse_cursor(payload.cursor)
        maximum_cursor = int(await session.scalar(select(func.coalesce(func.max(SyncChange.id), 0))) or 0)
        if cursor > maximum_cursor:
            raise ValueError("Sync cursor is ahead of the server. Retry with cursor=null for a full resync.")
        accepted: list[str] = []
        conflicts: list[ConflictResolution] = []
        remapped_ids: dict[str, int] = {}
        operation_results: list[dict[str, Any]] = []

        # Each valid operation is saved in a per-operation savepoint; validation
        # failures are isolated and returned while successful siblings commit.
        for operation in payload.operations:
            await session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"), {
                "lock_key": f"sync:{farmer_id}:{payload.client_id}:{operation.operation_id}",
            })
            try:
                async with session.begin_nested():
                    self._parse_client_timestamp(operation.updated_at)
                    prior = await session.scalar(select(SyncOperationLog).where(
                        SyncOperationLog.farmer_id == farmer_id,
                        SyncOperationLog.client_id == payload.client_id,
                        SyncOperationLog.operation_id == operation.operation_id,
                    ))
                    if prior is not None:
                        cached = prior.result
                        if cached.get("conflict"):
                            conflicts.append(ConflictResolution.model_validate(cached["conflict"]))
                        server_id = cached.get("entity_id")
                        if operation.entity_id is not None and server_id:
                            try:
                                remapped_ids[operation.entity_id] = int(server_id)
                            except (TypeError, ValueError):
                                pass
                        accepted.append(operation.operation_id)
                        operation_results.append({**cached, "operation_id": operation.operation_id,
                                                  "client_entity_id": operation.entity_id, "status": "duplicate"})
                        continue

                    entity = self._canonical_entity(operation.entity)
                    if operation.action not in {item.value for item in SyncAction}:
                        raise ValueError(f"Unknown action '{operation.action}'; use create, update, or delete")
                    if entity not in {"plot", "crop_record"}:
                        raise ValueError(f"Unknown entity '{operation.entity}'; use plot or crop_record")
                    if operation.action == SyncAction.CREATE and operation.entity_id is None:
                        raise ValueError("Create requires a client-generated entity_id for server ID remapping")
                    if operation.action == SyncAction.CREATE and operation.entity_id.isdecimal():
                        raise ValueError("Create entity_id must be a client-generated string, not a server numeric ID")
                    conflict, entity_id, _ = await self._apply_one(session, farmer_id, entity, operation, remapped_ids)
                    if conflict:
                        conflicts.append(conflict)
                    server_id = str(entity_id) if entity_id is not None else None
                    if operation.entity_id is not None and entity_id is not None:
                        remapped_ids[operation.entity_id] = entity_id
                    result = {
                        "operation_id": operation.operation_id,
                        "entity": entity,
                        "entity_id": server_id,
                        "client_entity_id": operation.entity_id,
                        "status": "conflict" if conflict else "applied",
                        "conflict": conflict.model_dump(mode="json") if conflict else None,
                        "error": None,
                    }
                    session.add(SyncOperationLog(farmer_id=farmer_id, client_id=payload.client_id,
                                                 operation_id=operation.operation_id, result=result))
                    accepted.append(operation.operation_id)
                    operation_results.append(result)
            except (ValueError, SQLAlchemyError) as exc:
                detail = str(exc) if isinstance(exc, ValueError) else "Operation failed a database validation or uniqueness constraint"
                operation_results.append({
                    "operation_id": operation.operation_id, "entity": operation.entity,
                    "client_entity_id": operation.entity_id, "status": "rejected",
                    "error": {"code": "invalid_operation", "message": detail},
                })

        await session.commit()
        rows = await session.scalars(
            select(SyncChange).where(SyncChange.farmer_id == farmer_id, SyncChange.id > cursor)
            .order_by(SyncChange.id).limit(payload.limit + 1)
        )
        page = list(rows.all())
        has_more = len(page) > payload.limit
        changes = page[:payload.limit]
        return SyncResponse(
            accepted_operation_ids=accepted,
            operation_results=operation_results,
            conflicts=conflicts,
            server_changes=[{
                "cursor": item.id, "entity": item.entity, "entity_id": item.entity_id,
                "action": item.action, "updated_at": item.changed_at.isoformat() if item.changed_at else None,
                "data": item.payload,
            } for item in changes],
            next_cursor=str(changes[-1].id) if changes else str(cursor),
            has_more=has_more,
        )

    async def _apply_one(
        self,
        session: AsyncSession,
        farmer_id: int,
        entity: str,
        operation: SyncOperation,
        remapped_ids: dict[str, int],
    ) -> tuple[ConflictResolution | None, int | None, dict[str, Any] | None]:
        entity_id = self._resolve_id(operation.entity_id, remapped_ids)
        if entity == "plot":
            row = await session.scalar(select(Plot).where(Plot.id == entity_id, Plot.farmer_id == farmer_id, Plot.is_archived.is_(False))) if entity_id else None
            if row is None and operation.action == SyncAction.UPDATE:
                raise ValueError("Plot update references a plot that does not belong to this farmer")
            if row is None and operation.action == SyncAction.DELETE:
                # Deleting an already absent client row is idempotent from the domain's perspective.
                return None, entity_id, None
            if row is None:
                return await self._create_plot(session, farmer_id, operation)
            return await self._mutate_existing(session, farmer_id, entity, row, operation, remapped_ids)

        if entity == "crop_record":
            row = await session.scalar(
                select(CropRecord)
                .join(Plot, CropRecord.plot_id == Plot.id)
                .where(CropRecord.id == entity_id, Plot.farmer_id == farmer_id, Plot.is_archived.is_(False))
            ) if entity_id else None
            if row is None and operation.action == SyncAction.UPDATE:
                raise ValueError("Crop record update references a record that does not belong to this farmer")
            if row is None and operation.action == SyncAction.DELETE:
                return None, entity_id, None
            if row is None:
                return await self._create_crop_record(session, farmer_id, operation, remapped_ids)
            return await self._mutate_existing(session, farmer_id, entity, row, operation, remapped_ids)
        raise ValueError(f"Unsupported sync entity: {operation.entity}")

    async def _create_plot(self, session: AsyncSession, farmer_id: int, operation: SyncOperation):
        data = self._allowed_data(operation.data, PLOT_FIELDS)
        validated = PlotCreate.model_validate(data)
        await self._validate_geometry_area(session, validated.location, float(validated.area_acres))
        data = validated.model_dump(mode="json")
        data["location"] = self._geometry(data.get("location"))
        row = Plot(farmer_id=farmer_id, **data, updated_at=datetime.now(UTC),
                   client_updated_at=self._parse_client_timestamp(operation.updated_at))
        session.add(row)
        await session.flush()
        snapshot = self._jsonable({key: value for key, value in data.items() if key != "location"})
        if operation.data.get("location") is not None:
            snapshot["location"] = operation.data["location"]
        snapshot.update({"id": row.id, "farmer_id": farmer_id, "updated_at": row.updated_at.isoformat()})
        await record_change(session, farmer_id=farmer_id, entity="plot", entity_id=row.id, action="upsert", payload=snapshot)
        return None, row.id, snapshot

    async def _create_crop_record(
        self,
        session: AsyncSession,
        farmer_id: int,
        operation: SyncOperation,
        remapped_ids: dict[str, int],
    ):
        data = self._allowed_data(operation.data, CROP_FIELDS)
        plot_ref = str(data.get("plot_id", ""))
        data["plot_id"] = remapped_ids.get(plot_ref, data.get("plot_id"))
        owned_plot = await session.scalar(select(Plot.id).where(Plot.id == data.get("plot_id"), Plot.farmer_id == farmer_id, Plot.is_archived.is_(False)))
        if owned_plot is None:
            raise ValueError("Crop record references a plot that does not belong to this farmer")
        validated = CropHistoryCreate.model_validate({key: value for key, value in data.items() if key != "plot_id"})
        data = {**validated.model_dump(), "plot_id": data["plot_id"]}
        row = CropRecord(**data, updated_at=datetime.now(UTC),
                         client_updated_at=self._parse_client_timestamp(operation.updated_at))
        session.add(row)
        await session.flush()
        snapshot = self._jsonable({**data, "id": row.id, "updated_at": row.updated_at.isoformat()})
        await record_change(session, farmer_id=farmer_id, entity="crop_record", entity_id=row.id, action="upsert", payload=snapshot)
        return None, row.id, snapshot

    async def _mutate_existing(
        self,
        session: AsyncSession,
        farmer_id: int,
        entity: str,
        row: Plot | CropRecord,
        operation: SyncOperation,
        remapped_ids: dict[str, int],
    ):
        incoming_time = self._parse_client_timestamp(operation.updated_at)
        current_time = max(filter(None, (row.updated_at, row.client_updated_at)))
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=UTC)
        if incoming_time.tzinfo is None:
            incoming_time = incoming_time.replace(tzinfo=UTC)
        strategy = ConflictStrategy.SERVER_WINS if entity == "plot" else ConflictStrategy.LAST_WRITE_WINS
        if incoming_time <= current_time:
            conflict = ConflictResolution(
                operation_id=operation.operation_id,
                entity=entity,
                entity_id=str(row.id),
                strategy=strategy,
                resolved_at=datetime.now(UTC),
                winner="server",
                server_updated_at=current_time,
            )
            return conflict, row.id, None

        if operation.action == SyncAction.DELETE:
            if entity == "plot":
                row.is_archived = True
                row.updated_at = datetime.now(UTC)
            else:
                await session.delete(row)
            await record_change(
                session,
                farmer_id=farmer_id,
                entity=entity,
                entity_id=row.id,
                action="delete",
                payload={"id": row.id},
            )
            return None, row.id, None

        allowed_fields = PLOT_FIELDS if entity == "plot" else CROP_FIELDS
        data = self._allowed_data(operation.data, allowed_fields)
        if entity == "plot":
            data = PlotUpdate.model_validate(data).model_dump(mode="json", exclude_unset=True)
        else:
            if "crop_name" in data and (not isinstance(data["crop_name"], str) or not data["crop_name"].strip()):
                raise ValueError("crop_name cannot be empty")
            for numeric_field in ("yield_kg", "input_costs"):
                if numeric_field in data and data[numeric_field] is not None and float(data[numeric_field]) < 0:
                    raise ValueError(f"{numeric_field} cannot be negative")
        if entity == "crop_record" and "plot_id" in data:
            plot_ref = str(data["plot_id"])
            data["plot_id"] = remapped_ids.get(plot_ref, data["plot_id"])
            remapped_plot = data["plot_id"]
            owned_plot = await session.scalar(select(Plot.id).where(Plot.id == remapped_plot, Plot.farmer_id == farmer_id, Plot.is_archived.is_(False)))
            if owned_plot is None:
                raise ValueError("Crop record cannot be moved to a plot owned by another farmer")
        if entity == "plot" and "location" in data:
            original_location = data["location"]
            row.location = self._geometry(original_location)
            data["location"] = original_location
        if entity == "plot" and ({"area_value", "area_unit", "area_acres"} & data.keys()):
            unit = data.get("area_unit", row.area_unit)
            if "area_value" in data:
                area_value = float(data["area_value"])
                area_acres = to_acres(area_value, unit)
                if "area_acres" in data and abs(float(data["area_acres"]) - area_acres) > max(0.01, area_acres * 0.001):
                    raise ValueError("area_acres conflicts with area_value and area_unit")
            elif "area_acres" in data:
                area_acres = float(data["area_acres"])
                area_value = from_acres(area_acres, unit)
            else:
                area_acres = float(row.area_acres)
                area_value = from_acres(area_acres, unit)
            data.update({"area_acres": area_acres, "area_value": area_value, "area_unit": unit})
        for field, value in data.items():
            if entity == "plot" and field == "location":
                continue
            if value is None and field in {"name", "area_acres", "plot_id", "season_id", "crop_name"}:
                raise ValueError(f"{field} cannot be null")
            setattr(row, field, value)
        if entity == "plot" and "area_acres" in data and float(data["area_acres"]) <= 0:
            raise ValueError("area_acres must be positive")
        if entity == "plot" and "name" in data and not str(data["name"]).strip():
            raise ValueError("name cannot be empty")
        if entity == "plot" and "location" in data:
            await self._validate_geometry_area(session, data["location"], float(row.area_acres))
        row.updated_at = datetime.now(UTC)
        row.client_updated_at = incoming_time
        await session.flush()
        snapshot = self._jsonable(data)
        snapshot.update({"id": row.id, "updated_at": row.updated_at.isoformat()})
        await record_change(session, farmer_id=farmer_id, entity=entity, entity_id=row.id, action="upsert", payload=snapshot)
        return None, row.id, snapshot

    @staticmethod
    def _canonical_entity(entity: str) -> str:
        name = entity.strip().casefold()
        if name in {"plot", "plots"}:
            return "plot"
        if name in {"crop_record", "crop_records", "history", "crop_history"}:
            return "crop_record"
        return name

    @staticmethod
    def _resolve_id(entity_id: str | None, remapped_ids: dict[str, int]) -> int | None:
        if entity_id is None:
            return None
        if entity_id in remapped_ids:
            return remapped_ids[entity_id]
        try:
            return int(entity_id)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _allowed_data(data: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(f"Unsupported mutation fields: {', '.join(sorted(unknown))}")
        return dict(data)

    @staticmethod
    def _geometry(value: Any) -> WKTElement | None:
        if value is None:
            return None
        geometry = TypeAdapter(PlotGeometry).validate_python(value)
        coordinates = geometry.coordinates
        if geometry.type == "Point":
            wkt = f"POINT ({float(coordinates[0])} {float(coordinates[1])})"
        elif geometry.type == "Polygon":
            rings = []
            for ring in coordinates:
                rings.append("(" + ", ".join(f"{float(x)} {float(y)}" for x, y in ring) + ")")
            wkt = "POLYGON (" + ", ".join(rings) + ")"
        else:
            raise ValueError("Plot location must be a GeoJSON Point or Polygon")
        return WKTElement(wkt, srid=4326)

    async def _validate_geometry_area(self, session: AsyncSession, value: Any, area_acres: float) -> None:
        if value is None:
            return
        geometry = TypeAdapter(PlotGeometry).validate_python(value)
        wkt = self._geometry(geometry)
        valid, srid, geometry_type, polygon_acres = (await session.execute(
            select(func.ST_IsValid(wkt), func.ST_SRID(wkt), func.GeometryType(wkt),
                   func.ST_Area(func.ST_Transform(wkt, 6933)) / 4046.8564224)
        )).one()
        if not valid or srid != 4326 or geometry_type.upper() != geometry.type.upper():
            raise ValueError("Location must be a valid WGS84 Point or Polygon")
        if geometry.type == "Polygon" and (
            polygon_acres <= 0 or abs(area_acres - float(polygon_acres)) / max(area_acres, float(polygon_acres)) > 0.25
        ):
            raise ValueError("Entered plot area must be within 25% of the polygon area")

    @staticmethod
    def _parse_cursor(cursor: str | None) -> int:
        if cursor in (None, ""):
            return 0
        try:
            parsed = int(cursor)
        except ValueError as exc:
            raise ValueError("Sync cursor must be a non-negative integer") from exc
        if parsed < 0:
            raise ValueError("Sync cursor must be a non-negative integer")
        return parsed

    @staticmethod
    def _parse_client_timestamp(value: Any) -> datetime:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("updated_at must be an ISO-8601 timestamp with a timezone") from exc
        else:
            raise ValueError("updated_at must be an ISO-8601 timestamp with a timezone")
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("updated_at must include a timezone, such as Z or +05:30")
        parsed = parsed.astimezone(UTC)
        if parsed > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError("updated_at is more than five minutes in the future")
        return parsed

    @staticmethod
    def _jsonable(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: SyncEngine._jsonable(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [SyncEngine._jsonable(item) for item in value]
        if hasattr(value, "isoformat"):
            return value.isoformat()
        try:
            from decimal import Decimal

            if isinstance(value, Decimal):
                return float(value)
        except ImportError:
            pass
        return value


sync_engine = SyncEngine()
