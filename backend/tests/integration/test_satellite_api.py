"""Owner-scoped NASA SMAP job API contract against disposable PostGIS."""

import os
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
import pytest_asyncio
from geoalchemy2.elements import WKTElement
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Farmer, Plot
from app.redis.client import get_redis
from app.workers.tasks import satellite_monitoring
from config.settings import settings

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL must point to disposable PostGIS")


class MemoryRedis:
    async def get(self, _key):
        return None


@pytest_asyncio.fixture
async def satellite_client(monkeypatch):
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_db():
        async with factory() as session:
            yield session

    monkeypatch.setattr(settings, "nasa_earthdata_username", "earthdata-user")
    monkeypatch.setattr(settings, "nasa_earthdata_password", "earthdata-password")
    queued = []
    monkeypatch.setattr(satellite_monitoring.process_nasa_smap_job, "delay", lambda job_id: queued.append(job_id))
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: MemoryRedis()

    suffix = uuid4().hex[:12]
    async with factory() as session:
        owner = Farmer(phone=f"+1415{suffix}")
        other = Farmer(phone=f"+1617{suffix}")
        session.add_all([owner, other])
        await session.flush()
        plot = Plot(farmer_id=owner.id, name="Satellite plot", area_acres=1,
                    location=WKTElement("POINT(77.5 12.9)", srid=4326))
        other_plot = Plot(farmer_id=other.id, name="Private plot", area_acres=1,
                          location=WKTElement("POINT(77.5 12.9)", srid=4326))
        session.add_all([plot, other_plot])
        await session.commit()
        identifiers = {"plot": plot.id, "other_plot": other_plot.id, "farmer": owner.id}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, {
            "owner": {"Authorization": f"Bearer {create_access_token(owner.phone)}"},
            "other": {"Authorization": f"Bearer {create_access_token(other.phone)}"},
        }, queued, identifiers, factory
    app.dependency_overrides.clear()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_smap_job_is_queued_readable_and_owner_scoped(satellite_client):
    client, headers, queued, ids, _factory = satellite_client
    response = await client.post(
        f"/api/v1/satellite/plots/{ids['plot']}/smap/soil-moisture",
        headers=headers["owner"], json={"start_date": "2026-10-01", "end_date": "2026-10-07"},
    )
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["status"] == "queued" and job["observation_count"] == 0
    assert queued == [job["id"]]

    own = await client.get(f"/api/v1/satellite/smap/jobs/{job['id']}", headers=headers["owner"])
    assert own.status_code == 200 and own.json()["plot_id"] == ids["plot"]
    private = await client.get(f"/api/v1/satellite/smap/jobs/{job['id']}", headers=headers["other"])
    assert private.status_code == 404
    other_plot = await client.post(
        f"/api/v1/satellite/plots/{ids['other_plot']}/smap/soil-moisture",
        headers=headers["owner"], json={"start_date": "2026-10-01", "end_date": "2026-10-07"},
    )
    assert other_plot.status_code == 404


@pytest.mark.asyncio
async def test_smap_worker_persists_quality_aware_observations(satellite_client, monkeypatch):
    client, headers, _queued, ids, factory = satellite_client
    requested = await client.post(
        f"/api/v1/satellite/plots/{ids['plot']}/smap/soil-moisture",
        headers=headers["owner"], json={"start_date": "2026-10-01", "end_date": "2026-10-07"},
    )
    job_id = requested.json()["id"]

    @asynccontextmanager
    async def worker_session():
        async with factory() as session:
            yield session

    class FakeAdapter:
        async def fetch_point(self, **kwargs):
            assert kwargs["latitude"] == pytest.approx(12.9)
            assert kwargs["longitude"] == pytest.approx(77.5)
            return {"provider_task_id": "nasa-task", "observations": [{
                "date": "2026-10-03", "latitude": 12.9, "longitude": 77.5,
                "product": "SPL3SMP_E.006", "product_doi": "10.5067/M20OXIZHY3RJ",
                "resolution_km": 9, "soil_moisture_am": 0.23, "soil_moisture_pm": None,
                "retrieval_qual_flag_am": 0, "retrieval_qual_flag_pm": None,
                "quality_am": "recommended", "quality_pm": "unavailable", "unit": "m3/m3",
            }]}

    monkeypatch.setattr(satellite_monitoring, "WorkerSession", worker_session)
    monkeypatch.setattr(satellite_monitoring, "NASASMAPAdapter", FakeAdapter)
    result = await satellite_monitoring._process_smap_job(job_id)
    assert result == {"status": "completed", "observations": 1}
    saved = await client.get(f"/api/v1/satellite/smap/jobs/{job_id}", headers=headers["owner"])
    assert saved.status_code == 200
    assert saved.json()["observations"][0]["soil_moisture_am"] == pytest.approx(0.23)
    assert saved.json()["observations"][0]["quality_am"] == "recommended"
