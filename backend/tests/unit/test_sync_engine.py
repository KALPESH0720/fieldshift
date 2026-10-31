from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.models.crop_record import CropRecord
from app.schemas.sync import SyncAction, SyncOperation
from app.services.sync.engine import SyncEngine


@pytest.mark.asyncio
async def test_sync_conflict_rule_keeps_newer_server_crop_edit():
    server_time = datetime.now(UTC)
    record = CropRecord(id=42, plot_id=7, season_id=3, crop_name="Barley", updated_at=server_time)
    operation = SyncOperation(
        operation_id="offline-1",
        entity="crop_record",
        entity_id="42",
        action=SyncAction.UPDATE,
        updated_at=(server_time - timedelta(minutes=1)).isoformat(),
        data={"crop_name": "Ragi"},
    )

    conflict, entity_id, _ = await SyncEngine()._mutate_existing(
        AsyncMock(), 7, "crop_record", record, operation, {}
    )

    assert entity_id == 42
    assert conflict.winner == "server"
    assert conflict.strategy == "last_write_wins"
    assert record.crop_name == "Barley"
