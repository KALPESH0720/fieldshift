import os
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, CropRecord, Farmer, Plot, Season
from app.schemas.sync import SyncAction, SyncOperation, SyncPayload
from app.services.sync.engine import SyncEngine

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL must point to a disposable PostGIS database",
)


@pytest_asyncio.fixture
async def database_session():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_server_wins_stale_offline_crop_edit(database_session):
    session = database_session
    farmer = Farmer(phone="+919876543210", name="Sync test farmer")
    season = Season(name="Sync test season", start_month=6, end_month=10)
    plot = Plot(farmer=farmer, name="Sync plot", area_acres=2)
    session.add_all([farmer, season])
    await session.flush()
    server_time = datetime.now(UTC)
    crop = CropRecord(
        plot=plot,
        season=season,
        crop_name="Wheat",
        crop_family="Poaceae",
        updated_at=server_time,
    )
    session.add(crop)
    await session.commit()

    # The online server edit happened after the offline phone last saw this record.
    crop.crop_name = "Barley"
    crop.updated_at = server_time + timedelta(minutes=2)
    await session.commit()

    payload = SyncPayload(
        client_id="phone-1",
        operations=[
            SyncOperation(
                operation_id="offline-edit-1",
                entity="crop_record",
                entity_id=str(crop.id),
                action=SyncAction.UPDATE,
                updated_at=(server_time + timedelta(minutes=1)).isoformat(),
                data={"crop_name": "Ragi"},
            )
        ],
    )
    response = await SyncEngine().apply(session, farmer.id, payload)

    assert response.accepted_operation_ids == ["offline-edit-1"]
    assert len(response.conflicts) == 1
    assert response.conflicts[0].winner == "server"
    assert response.conflicts[0].strategy == "last_write_wins"
    await session.refresh(crop)
    assert crop.crop_name == "Barley"
