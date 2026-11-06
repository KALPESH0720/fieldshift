"""Shared async HTTP handling for external service adapters."""

import asyncio
import email.utils
import time
from collections.abc import Callable

import httpx


class IntegrationUnavailable(RuntimeError):
    """An upstream provider failed or returned an unusable response."""


async def request_json(
    method: str,
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    attempts: int = 3,
    backoff: float = 0.2,
    sleep: Callable[[float], object] | None = None,
    **kwargs,
) -> dict | list:
    """Issue a bounded request, retrying network errors and transient statuses."""
    if attempts < 1:
        raise ValueError("attempts must be at least one")
    sleep_fn = sleep or asyncio.sleep
    timeout = kwargs.pop("timeout", 15.0)

    async def perform(active_client: httpx.AsyncClient):
        last_error: Exception | None = None
        for attempt in range(attempts):
            delay = min(backoff * (2**attempt), 5.0)
            try:
                response = await active_client.request(method, url, **kwargs)
                if response.status_code in {408, 425, 429} or response.status_code >= 500:
                    if attempt + 1 < attempts:
                        delay = _retry_after(response, delay)
                        await sleep_fn(delay)
                        continue
                response.raise_for_status()
                if response.status_code == 204 or not response.content:
                    return {}
                try:
                    data = response.json()
                except ValueError as exc:
                    raise IntegrationUnavailable("Provider returned invalid JSON") from exc
                if not isinstance(data, (dict, list)):
                    raise IntegrationUnavailable("Provider returned an unexpected JSON value")
                return data
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    await sleep_fn(delay)
                    continue
                break
            except httpx.HTTPStatusError as exc:
                raise IntegrationUnavailable(
                    f"Provider returned HTTP {exc.response.status_code}"
                ) from exc
        raise IntegrationUnavailable("Provider request failed after retries") from last_error

    if client is not None:
        return await perform(client)
    async with httpx.AsyncClient(timeout=timeout) as owned_client:
        return await perform(owned_client)


def _retry_after(response: httpx.Response, fallback: float) -> float:
    value = response.headers.get("Retry-After")
    if value:
        try:
            return min(max(float(value), 0.0), 5.0)
        except ValueError:
            try:
                when = email.utils.parsedate_to_datetime(value).timestamp()
                return min(max(when - time.time(), 0.0), 5.0)
            except (TypeError, ValueError, OverflowError):
                pass
    return fallback
