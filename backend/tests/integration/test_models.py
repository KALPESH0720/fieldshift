"""PostGIS integration checks. Set TEST_DATABASE_URL to a disposable PostGIS database."""

import os

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Alert, CropRecord, Farmer, Plot, Season

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL must point to a disposable PostGIS database")


@pytest.fixture
async def session():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await connection.run_sync(Farmer.metadata.drop_all)
        await connection.run_sync(Farmer.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        yield db
    async with engine.begin() as connection:
        await connection.run_sync(Farmer.metadata.drop_all)
    await engine.dispose()


async def test_foreign_keys_and_delete_cascades(session):
    season = Season(name="Kharif", start_month=6, end_month=10)
    farmer = Farmer(phone="+911234567890", name="Test farmer")
    plot = Plot(farmer=farmer, name="North field", area_acres=2.5)
    plot.crop_records.append(CropRecord(season=season, crop_name="Rice"))
    farmer.alerts.append(Alert(alert_type="weather", payload={"rain": True}))
    session.add_all([farmer, season])
    await session.commit()

    assert plot.farmer_id == farmer.id
    assert plot.crop_records[0].season_id == season.id
    await session.delete(farmer)
    await session.commit()

    assert await session.get(Plot, plot.id) is None
    assert await session.get(CropRecord, plot.crop_records[0].id) is None
    assert await session.scalar(select(func.count()).select_from(Alert)) == 0


async def test_postgis_point_intersection_query(session):
    farmer = Farmer(phone="+919876543210", name="Spatial test")
    point = Plot(
        farmer=farmer,
        name="Point plot",
        area_acres=1,
        location=WKTElement("POINT(77.5946 12.9716)", srid=4326),
    )
    session.add(point)
    await session.commit()

    result = await session.scalar(
        select(func.ST_Intersects(Plot.location, func.ST_SetSRID(func.ST_MakePoint(77.5946, 12.9716), 4326)))
        .where(Plot.id == point.id)
    )
    assert result is True
