import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import from_url
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Farmer, Plot
from app.models.soil_card_upload import SoilCardUpload
from app.redis.client import get_redis
from app.schemas.soil import SoilCardReview
from app.services.integrations.ocr_service import SoilCardMetrics
from app.services.soil_cards import process_soil_card_upload
from app.services.storage.malware import get_malware_scanner
from app.services.storage.objects import get_object_store
from app.services.storage.malware import ScannerUnavailable

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/15")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL must point to disposable PostGIS")


class FakeObjectStore:
    def __init__(self):
        self.objects = {}

    async def put(self, key, data, content_type, sha256):
        self.objects[key] = data

    async def get(self, key):
        return self.objects[key]

    async def signed_read_url(self, key, expires_seconds=300):
        return f"https://private.test/{key}?signed=short"

    async def delete(self, key):
        self.objects.pop(key, None)


class FakeScanner:
    async def scan(self, _data):
        return "clamav-test:clean"


class FailedScanner:
    async def scan(self, _data):
        raise ScannerUnavailable("scanner offline")


class FakeOCR:
    async def extract_metrics(self, _image, *, content_type):
        assert content_type == "image/png"
        return SoilCardMetrics(
            n_val=120, p_val=35, k_val=60, ph=6.4, organic_matter=1.2,
            confidence={"n_val": 0.35, "p_val": 0.98, "k_val": 0.98, "ph": 0.99, "organic_matter": 0.85},
            raw={"provider_job": "job-test", "source_fields": ["N_val"]},
        )


@pytest_asyncio.fixture
async def soil_client(monkeypatch):
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = from_url(TEST_REDIS_URL, encoding="utf-8", decode_responses=True)
    await redis.ping()
    store = FakeObjectStore()
    monkeypatch.setattr("app.api.v1.soil.process_soil_card_upload_task.delay", lambda _id: None)

    async def override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: redis
    app.dependency_overrides[get_object_store] = lambda: store
    app.dependency_overrides[get_malware_scanner] = lambda: FakeScanner()
    suffix = uuid4().hex[:12]
    phone_a, phone_b = f"+1415{suffix}", f"+1617{suffix}"
    async with factory() as session:
        farmer_a, farmer_b = Farmer(phone=phone_a), Farmer(phone=phone_b)
        session.add_all([farmer_a, farmer_b])
        await session.flush()
        plot_a = Plot(farmer_id=farmer_a.id, name="Soil plot A", area_acres=1)
        plot_b = Plot(farmer_id=farmer_b.id, name="Soil plot B", area_acres=1)
        session.add_all([plot_a, plot_b])
        await session.commit()
        ids = {"a": farmer_a.id, "b": farmer_b.id, "plot_a": plot_a.id, "plot_b": plot_b.id}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, {"a": {"Authorization": f"Bearer {create_access_token(phone_a)}"},
                       "b": {"Authorization": f"Bearer {create_access_token(phone_b)}"}}, factory, store, ids
    app.dependency_overrides.clear()
    await redis.aclose()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_soil_card_upload_ocr_review_and_approved_provenance(soil_client):
    client, headers, factory, store, ids = soil_client
    png = b"\x89PNG\r\n\x1a\n" + b"test-image-bytes"
    uploaded = await client.post(f"/api/v1/plots/{ids['plot_a']}/soil-card-uploads",
                                 content=png, headers={**headers["a"], "Content-Type": "image/png"})
    assert uploaded.status_code == 202, uploaded.text
    body = uploaded.json()
    assert body["status"] == "queued"
    assert body["scan_status"] == "clean"
    assert body["sha256"] and body["low_confidence_fields"] == []
    async with factory() as session:
        row = await session.get(SoilCardUpload, body["id"])
        await process_soil_card_upload(session, row, object_store=store, adapter=FakeOCR())
        assert row.raw_ocr_metadata["provider_job"] == "job-test"
        assert row.status == "needs_review"

    pending = await client.get(f"/api/v1/soil-card-uploads/{body['id']}", headers=headers["a"])
    assert pending.json()["low_confidence_fields"] == ["n_val"]
    signed = await client.get(f"/api/v1/soil-card-uploads/{body['id']}/photo-url", headers=headers["a"])
    assert signed.status_code == 200 and "signed=short" in signed.json()["url"]
    forbidden = await client.get(f"/api/v1/soil-card-uploads/{body['id']}", headers=headers["b"])
    assert forbidden.status_code == 404

    needs_correction = await client.post(f"/api/v1/soil-card-uploads/{body['id']}/review", headers=headers["a"], json={
        "tested_at": datetime.now(UTC).isoformat(), "p_val": 35,
    })
    assert needs_correction.status_code == 422
    reviewed = await client.post(f"/api/v1/soil-card-uploads/{body['id']}/review", headers=headers["a"], json={
        "tested_at": datetime.now(UTC).isoformat(), "n_val": 125,
    })
    assert reviewed.status_code == 201, reviewed.text
    assert reviewed.json()["n_val"] == 125
    assert reviewed.json()["provenance"] == "soil_card_ocr_reviewed"
    assert reviewed.json()["status"] == "approved"

    history = await client.get(f"/api/v1/plots/{ids['plot_a']}/soil-tests", headers=headers["a"])
    assert history.status_code == 200
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["soil_card_upload_id"] == body["id"]


@pytest.mark.asyncio
async def test_soil_manual_validation_duplicate_image_and_plot_ownership(soil_client):
    client, headers, _, _, ids = soil_client
    invalid = await client.post(f"/api/v1/plots/{ids['plot_a']}/soil-tests", headers=headers["a"], json={
        "ph": 14.1,
    })
    assert invalid.status_code == 422
    other_plot = await client.post(f"/api/v1/plots/{ids['plot_b']}/soil-tests", headers=headers["a"], json={"n_val": 10})
    assert other_plot.status_code == 404
    manual = await client.post(f"/api/v1/plots/{ids['plot_a']}/soil-tests", headers=headers["a"], json={
        "n_val": 42, "p_val": 20, "k_val": 15, "ph": 6.1, "organic_matter": 1.5,
        "provenance": "lab", "source_reference": "lab-report-77",
    })
    assert manual.status_code == 201, manual.text
    assert manual.json()["provenance"] == "lab"
    png = b"\x89PNG\r\n\x1a\n" + b"duplicate-image"
    first = await client.post(f"/api/v1/plots/{ids['plot_a']}/soil-card-uploads", content=png,
                              headers={**headers["a"], "Content-Type": "image/png"})
    second = await client.post(f"/api/v1/plots/{ids['plot_a']}/soil-card-uploads", content=png,
                               headers={**headers["a"], "Content-Type": "image/png"})
    assert first.status_code == 202
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_soil_upload_fails_closed_without_scanner_and_ocr_failure_is_retryable(soil_client):
    client, headers, factory, store, ids = soil_client
    app.dependency_overrides[get_malware_scanner] = lambda: FailedScanner()
    png = b"\x89PNG\r\n\x1a\n" + b"ocr-error-image"
    scan_failed = await client.post(f"/api/v1/plots/{ids['plot_a']}/soil-card-uploads", content=png,
                                    headers={**headers["a"], "Content-Type": "image/png"})
    assert scan_failed.status_code == 503
    assert store.objects == {}

    app.dependency_overrides[get_malware_scanner] = lambda: FakeScanner()
    uploaded = await client.post(f"/api/v1/plots/{ids['plot_a']}/soil-card-uploads", content=png,
                                 headers={**headers["a"], "Content-Type": "image/png"})
    assert uploaded.status_code == 202

    class FailedOCR:
        async def extract_metrics(self, *_args, **_kwargs):
            raise RuntimeError("provider failure")

    async with factory() as session:
        row = await session.get(SoilCardUpload, uploaded.json()["id"])
        with pytest.raises(RuntimeError):
            await process_soil_card_upload(session, row, object_store=store, adapter=FailedOCR())
        assert row.status == "failed"
        assert row.ocr_error_code == "RuntimeError"
    retried = await client.post(f"/api/v1/soil-card-uploads/{uploaded.json()['id']}/retry", headers=headers["a"])
    assert retried.status_code == 202
    assert retried.json()["status"] == "queued"
