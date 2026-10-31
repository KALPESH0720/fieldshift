"""Consent-scoped AgriStack registry adapter.

The integration contract is state/network-manager specific; URLs and paths are
configured by deployment and consent is always supplied by the caller.
"""

import time

import httpx

from app.services.integrations.http import IntegrationUnavailable, request_json
from config.settings import settings


class AgriStackAdapter:
    def __init__(self, *, client: httpx.AsyncClient | None = None, base_url: str | None = None,
                 token_url: str | None = None, client_id: str | None = None,
                 client_secret: str | None = None, attempts: int = 3, backoff: float = 0.2):
        self.client, self.base_url = client, (base_url or settings.agristack_base_url or "").rstrip("/")
        self.token_url = token_url or settings.agristack_token_url
        self.client_id = client_id or settings.agristack_client_id
        self.client_secret = client_secret or (settings.agristack_client_secret.get_secret_value() if settings.agristack_client_secret else None)
        self.attempts, self.backoff = attempts, backoff
        self._token: str | None = None
        self._token_expires = 0.0

    async def prefill_plots(self, farmer_reference: str, consent_token: str, *, path: str = "/plots") -> dict | list:
        if not self.base_url or not consent_token:
            raise IntegrationUnavailable("AgriStack endpoint and farmer consent are required")
        token = await self._access_token()
        return await request_json("GET", f"{self.base_url}/{path.lstrip('/')}", client=self.client,
                                  attempts=self.attempts, backoff=self.backoff,
                                  headers={"Authorization": f"Bearer {token}", "X-Farmer-Consent": consent_token},
                                  params={"farmer_reference": farmer_reference})

    async def _access_token(self) -> str:
        if self._token and self._token_expires > time.monotonic() + 30:
            return self._token
        if not self.token_url or not self.client_id or not self.client_secret:
            raise IntegrationUnavailable("AgriStack OAuth is not configured")
        result = await request_json("POST", self.token_url, client=self.client,
                                    attempts=self.attempts, backoff=self.backoff,
                                    data={"grant_type": "client_credentials", "client_id": self.client_id,
                                          "client_secret": self.client_secret})
        token = result.get("access_token") if isinstance(result, dict) else None
        if not token:
            raise IntegrationUnavailable("AgriStack token response omitted access_token")
        self._token = token
        self._token_expires = time.monotonic() + float(result.get("expires_in", 300))
        return token


async def prefill_plots(farmer_reference: str, consent_token: str, **kwargs) -> dict | list:
    return await AgriStackAdapter().prefill_plots(farmer_reference, consent_token, **kwargs)
