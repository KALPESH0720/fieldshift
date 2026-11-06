import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from app.api.v1 import market
from app.services.integrations.http import IntegrationUnavailable
from app.workers.tasks import price_ingestion
from config.settings import Settings


@pytest.mark.asyncio
async def test_ingestion_api_maps_provider_outage_to_safe_503(monkeypatch):
    monkeypatch.setattr(market, "settings", Settings(admin_api_key=SecretStr("test-admin-key")))

    async def unavailable():
        raise IntegrationUnavailable("provider URL and credential details must not escape")

    monkeypatch.setattr(price_ingestion, "_ingest", unavailable)
    with pytest.raises(HTTPException) as caught:
        await market.run_price_ingestion(x_admin_key="test-admin-key")

    assert caught.value.status_code == 503
    assert caught.value.detail == "AGMARKNET provider unavailable or returned an unsupported response"
    assert "credential" not in caught.value.detail
