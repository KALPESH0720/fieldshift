"""Configurable NASA SMAP data endpoint adapter.

The URL is deployment-configured because NASA products are exposed through
different APIs (Earthdata/LP DAAC, AppEEARS, and EGI) with distinct schemas.
"""

import httpx

from app.services.integrations.http import IntegrationUnavailable, request_json
from config.settings import settings


class NASASMAPAdapter:
    def __init__(self, *, client: httpx.AsyncClient | None = None, url: str | None = None,
                 earthdata_token: str | None = None, attempts: int = 3, backoff: float = 0.2):
        self.client, self.url = client, url or settings.nasa_smap_url
        self.token = earthdata_token or (settings.nasa_earthdata_token.get_secret_value() if settings.nasa_earthdata_token else None)
        self.attempts, self.backoff = attempts, backoff

    async def fetch(self, *, bbox: tuple[float, float, float, float], start_date: str,
                    end_date: str, product: str | None = None) -> dict | list:
        if not self.url:
            raise IntegrationUnavailable("NASA SMAP endpoint is not configured")
        params = {"bbox": ",".join(map(str, bbox)), "start_date": start_date, "end_date": end_date}
        if product:
            params["product"] = product
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        return await request_json("GET", self.url, client=self.client, attempts=self.attempts,
                                  backoff=self.backoff, params=params, headers=headers)


async def fetch_soil_moisture(**kwargs) -> dict | list:
    return await NASASMAPAdapter().fetch(**kwargs)
