"""Authenticated adapter for the standalone Field Shift suggestion engine."""

from typing import Any

import httpx
from fastapi import HTTPException

from config.settings import settings


class SuggestionEngineClient:
    def _configuration(self) -> tuple[str, dict[str, str]]:
        base_url = (settings.suggestion_engine_url or "").strip().rstrip("/")
        if (not base_url or settings.suggestion_engine_api_key is None
                or not settings.suggestion_engine_api_key.get_secret_value()):
            raise HTTPException(status_code=503, detail="Suggestion engine is not configured")
        return base_url, {
            "X-API-Key": settings.suggestion_engine_api_key.get_secret_value(),
            "Accept": "application/json",
        }

    async def request(self, method: str, path: str, *, json: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
        base_url, headers = self._configuration()
        try:
            async with httpx.AsyncClient(timeout=settings.suggestion_engine_timeout_seconds) as client:
                response = await client.request(method, f"{base_url}/v1{path}", headers=headers, json=json)
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail="Suggestion engine timed out") from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="Suggestion engine is unavailable") from exc

        if response.status_code >= 500:
            raise HTTPException(status_code=502, detail="Suggestion engine failed to process the request")
        if response.is_error:
            try:
                detail = response.json().get("detail", "Suggestion engine rejected the request")
            except (ValueError, AttributeError):
                detail = "Suggestion engine rejected the request"
            raise HTTPException(status_code=response.status_code, detail=detail)
        try:
            result = response.json()
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="Suggestion engine returned invalid JSON") from exc
        if not isinstance(result, (dict, list)):
            raise HTTPException(status_code=502, detail="Suggestion engine returned an invalid response")
        return result


suggestion_engine = SuggestionEngineClient()
