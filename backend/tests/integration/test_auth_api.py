import os
import time
from datetime import timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import create_access_token
from app.core.phone import canonicalize_phone
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Farmer
from app.redis.client import get_redis
from config.settings import settings

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL must point to a disposable PostGIS database")


class MemoryRedis:
    def __init__(self):
        self.data: dict[str, tuple[str, float | None]] = {}

    def _get(self, key):
        record = self.data.get(key)
        if record and record[1] is not None and record[1] <= time.monotonic():
            self.data.pop(key, None)
            return None
        return record[0] if record else None

    async def set(self, key, value, ex=None, nx=False):
        if nx and self._get(key) is not None:
            return None
        self.data[key] = (str(value), time.monotonic() + ex if ex else None)
        return True

    async def get(self, key):
        return self._get(key)

    async def getdel(self, key):
        value = self._get(key)
        self.data.pop(key, None)
        return value

    async def delete(self, *keys):
        return sum(self.data.pop(key, None) is not None for key in keys)

    async def incr(self, key):
        value = int(self._get(key) or 0) + 1
        expiry = self.data.get(key, ("", None))[1]
        self.data[key] = (str(value), expiry)
        return value

    async def expire(self, key, seconds):
        if key in self.data:
            self.data[key] = (self.data[key][0], time.monotonic() + seconds)
            return True
        return False

    def elapse(self, seconds):
        for key, (value, expiry) in list(self.data.items()):
            if expiry is not None:
                self.data[key] = (value, expiry - seconds)


@pytest_asyncio.fixture
async def api_client(monkeypatch):
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = MemoryRedis()

    async def override_get_db():
        async with session_factory() as session:
            yield session

    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "otp_provider", "development")
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, redis, session_factory
    app.dependency_overrides.clear()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_email_login_to_authenticated_farmer_creation(api_client):
    client, _, _ = api_client
    login_resp = await client.post("/api/v1/auth/login", json={"email": "farmer@fieldshift.org", "password": "password123"})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post("/api/v1/farmers/me", json={"name": "Test farmer"}, headers=headers)
    assert created.status_code == 201, created.text
    assert created.json()["phone"] == "farmer@fieldshift.org"


@pytest.mark.asyncio
async def test_malformed_and_expired_jwt_are_rejected(api_client):
    client, _, _ = api_client
    assert (await client.get("/api/v1/farmers/me")).status_code == 401
    malformed = await client.get("/api/v1/farmers/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert malformed.status_code == 401
    expired_token = create_access_token("farmer@fieldshift.org", expires_delta=timedelta(seconds=-1))
    expired_auth = await client.get("/api/v1/farmers/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert expired_auth.status_code == 401


def test_phone_normalization_requires_explicit_country_for_non_indian_local_numbers():
    assert canonicalize_phone(" 9876543210 ") == "+919876543210"
    assert canonicalize_phone("+14155552671") == "+14155552671"
    with pytest.raises(ValueError):
        canonicalize_phone("4155552671")


@pytest.mark.asyncio
async def test_profile_update_export_deletion_and_immediate_token_revocation(api_client):
    client, _, session_factory = api_client
    phone = "+919876543210"
    async with session_factory() as session:
        session.add(Farmer(phone=phone, name="Before"))
        await session.commit()
    token = create_access_token(phone)
    headers = {"Authorization": f"Bearer {token}"}
    updated = await client.patch("/api/v1/farmers/me", json={"name": "After"}, headers=headers)
    assert updated.status_code == 200 and updated.json()["name"] == "After"
    exported = await client.get("/api/v1/farmers/me/export", headers=headers)
    assert exported.status_code == 200 and exported.json()["profile"]["phone"] == phone
    deleted = await client.delete("/api/v1/farmers/me", headers=headers)
    assert deleted.status_code == 204
    assert (await client.get("/api/v1/farmers/me", headers=headers)).status_code == 401


@pytest.mark.asyncio
async def test_verified_but_unregistered_phone_cannot_read_another_farmer(api_client):
    client, _, session_factory = api_client
    async with session_factory() as session:
        session.add(Farmer(phone="+919876543210", name="Private profile"))
        await session.commit()
    another_user = create_access_token("+14155552671")
    response = await client.get("/api/v1/farmers/me", headers={"Authorization": f"Bearer {another_user}"})
    assert response.status_code == 404
