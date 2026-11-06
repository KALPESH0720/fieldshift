"""Sentinel Hub Process API adapter for Sentinel-2 index summaries."""

import time

import httpx

from app.services.integrations.http import IntegrationUnavailable, request_json
from config.settings import settings


class Sentinel2Adapter:
    def __init__(self, *, client: httpx.AsyncClient | None = None, process_url: str | None = None,
                 token_url: str | None = None, client_id: str | None = None,
                 client_secret: str | None = None, attempts: int = 3, backoff: float = 0.2):
        self.client = client
        self.process_url = process_url or settings.sentinel2_process_url
        self.token_url = token_url or settings.sentinel2_token_url
        self.client_id = client_id or settings.sentinel2_client_id
        self.client_secret = client_secret or (settings.sentinel2_client_secret.get_secret_value() if settings.sentinel2_client_secret else None)
        self.attempts, self.backoff = attempts, backoff
        self._token: str | None = None
        self._token_expires = 0.0

    async def fetch_indices(self, *, geometry: dict, start_date: str, end_date: str,
                            evalscript: str, responses: list[dict] | None = None) -> dict | list:
        if not self.process_url:
            raise IntegrationUnavailable("Sentinel-2 process endpoint is not configured")
        token = await self._access_token()
        payload = {"input": {"bounds": {"geometry": geometry}, "data": [{
            "type": "sentinel-2-l2a", "dataFilter": {"timeRange": {
                "from": start_date, "to": end_date
            }}
        }]}, "output": {"responses": responses or [{"identifier": "default", "format": {"type": "application/json"}}]},
            "evalscript": evalscript}
        return await request_json("POST", self.process_url, client=self.client,
                                  attempts=self.attempts, backoff=self.backoff,
                                  headers={"Authorization": f"Bearer {token}"}, json=payload)

    async def _access_token(self) -> str:
        if self._token and self._token_expires > time.monotonic() + 30:
            return self._token
        if not self.client_id or not self.client_secret:
            raise IntegrationUnavailable("Sentinel Hub OAuth credentials are not configured")
        result = await request_json("POST", self.token_url, client=self.client,
                                    attempts=self.attempts, backoff=self.backoff,
                                    data={"grant_type": "client_credentials", "client_id": self.client_id,
                                          "client_secret": self.client_secret})
        token = result.get("access_token") if isinstance(result, dict) else None
        if not token:
            raise IntegrationUnavailable("Sentinel Hub token response omitted access_token")
        self._token = token
        self._token_expires = time.monotonic() + float(result.get("expires_in", 300))
        return token


async def fetch_indices(**kwargs) -> dict | list:
    return await Sentinel2Adapter().fetch_indices(**kwargs)
