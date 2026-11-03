"""HTTP client with retries and backoff, used by all data clients.

Retries network errors and HTTP 429/5xx; other 4xx errors fail immediately. A `transport`
(httpx.MockTransport) can be injected so clients are testable without network access.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Optional

import httpx

RETRY_STATUS = {429, 500, 502, 503, 504}


class HttpError(RuntimeError):
    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


class HttpClient:
    def __init__(
        self,
        *,
        timeout: float = 60.0,
        retries: int = 4,
        backoff: float = 1.0,
        headers: Optional[dict[str, str]] = None,
        transport: Optional[httpx.BaseTransport] = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.retries = retries
        self.backoff = backoff
        self._sleep = sleep
        self._client = httpx.Client(timeout=timeout, headers=headers, transport=transport, follow_redirects=True)

    def close(self) -> None:
        self._client.close()

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last: Optional[str] = None
        for attempt in range(self.retries + 1):
            try:
                resp = self._client.request(method, url, **kwargs)
            except httpx.TransportError as e:
                last = f"{type(e).__name__}: {e}"
            else:
                if resp.status_code < 400:
                    return resp
                if resp.status_code not in RETRY_STATUS:
                    raise HttpError(f"{method} {url} -> {resp.status_code}: {resp.text[:200]}", resp.status_code)
                last = f"HTTP {resp.status_code}"
            if attempt < self.retries:
                self._sleep(self.backoff * (2 ** attempt))
        raise HttpError(f"{method} {url} failed after {self.retries + 1} attempts ({last})")

    def get_json(self, url: str, **kwargs: Any) -> Any:
        return self.request("GET", url, **kwargs).json()

    def get_text(self, url: str, **kwargs: Any) -> str:
        return self.request("GET", url, **kwargs).text

    def post_json(self, url: str, **kwargs: Any) -> Any:
        return self.request("POST", url, **kwargs).json()
