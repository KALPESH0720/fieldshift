from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field

from app.schemas.common import StrictSchema


class SyncAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class ConflictStrategy(StrEnum):
    LAST_WRITE_WINS = "last_write_wins"
    SERVER_WINS = "server_wins"
    CLIENT_WINS = "client_wins"


class SyncOperation(StrictSchema):
    operation_id: str = Field(min_length=1, max_length=128)
    entity: str = Field(min_length=1, max_length=64)
    entity_id: str | None = Field(default=None, max_length=128)
    action: str = Field(min_length=1, max_length=16)
    updated_at: Any
    data: dict[str, Any] = Field(default_factory=dict)


class SyncPayload(StrictSchema):
    client_id: str = Field(min_length=1, max_length=128)
    operations: list[SyncOperation] = Field(max_length=500)
    cursor: str | None = None
    limit: int = Field(default=200, ge=1, le=500)


class ConflictResolution(StrictSchema):
    operation_id: str
    entity: str
    entity_id: str
    strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS
    resolved_at: datetime
    winner: str = Field(pattern=r"^(client|server)$")
    server_updated_at: datetime | None = None


class SyncOperationError(StrictSchema):
    code: str
    message: str


class SyncOperationResult(StrictSchema):
    operation_id: str
    entity: str
    entity_id: str | None = None
    client_entity_id: str | None = None
    status: Literal["applied", "conflict", "duplicate", "rejected"]
    conflict: ConflictResolution | None = None
    error: SyncOperationError | None = None


class SyncChangeDTO(StrictSchema):
    cursor: int
    entity: str
    entity_id: str
    action: Literal["upsert", "delete"]
    updated_at: datetime | None = None
    data: dict[str, Any]


class SyncResponse(StrictSchema):
    accepted_operation_ids: list[str] = Field(default_factory=list)
    operation_results: list[SyncOperationResult] = Field(default_factory=list)
    conflicts: list[ConflictResolution] = Field(default_factory=list)
    server_changes: list[SyncChangeDTO] = Field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False
