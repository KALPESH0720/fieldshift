"""Soil Health Card OCR adapter with normalized N-P-K output."""

import base64
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.integrations.http import IntegrationUnavailable, request_json
from config.settings import settings


class SoilCardMetrics(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    n_val: float | None = Field(default=None, ge=0, alias="N_val")
    p_val: float | None = Field(default=None, ge=0, alias="P_val")
    k_val: float | None = Field(default=None, ge=0, alias="K_val")
    ph: float | None = Field(default=None, ge=0, le=14, alias="pH")
    organic_matter: float | None = Field(default=None, ge=0)
    confidence: dict[str, float] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)

    @field_validator("confidence")
    @classmethod
    def valid_confidence(cls, value):
        if any(not 0 <= score <= 1 for score in value.values()):
            raise ValueError("OCR confidence scores must be between 0 and 1")
        return value


class SoilCardOCRAdapter:
    def __init__(self, *, client: httpx.AsyncClient | None = None, url: str | None = None,
                 api_key: str | None = None, attempts: int = 3, backoff: float = 0.2):
        self.client, self.url = client, url or settings.soil_card_ocr_url
        self.api_key = api_key or (settings.soil_card_ocr_api_key.get_secret_value() if settings.soil_card_ocr_api_key else None)
        self.attempts, self.backoff = attempts, backoff

    async def extract_metrics(self, image: bytes, *, content_type: str = "image/jpeg") -> SoilCardMetrics:
        if not image:
            raise ValueError("image cannot be empty")
        if not self.url:
            raise IntegrationUnavailable("Soil card OCR endpoint is not configured")
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        data = await request_json("POST", self.url, client=self.client, attempts=self.attempts,
                                  backoff=self.backoff, headers=headers,
                                  json={"image": base64.b64encode(image).decode("ascii"), "content_type": content_type})
        if not isinstance(data, dict):
            raise IntegrationUnavailable("OCR provider returned an unexpected response")
        metrics = data.get("metrics", data)
        if not isinstance(metrics, dict):
            raise IntegrationUnavailable("OCR provider omitted soil metrics")
        try:
            confidence = data.get("confidence", metrics.get("confidence", {}))
            if not isinstance(confidence, dict):
                raise ValueError("confidence must be a field-to-score object")
            aliases = {"N_val": "n_val", "P_val": "p_val", "K_val": "k_val", "pH": "ph"}
            confidence = {aliases.get(key, key): value for key, value in confidence.items()}
            return SoilCardMetrics.model_validate({**metrics, "confidence": confidence, "raw": data})
        except Exception as exc:
            raise IntegrationUnavailable("OCR provider returned invalid soil metrics") from exc


async def extract_metrics(image: bytes, **kwargs) -> SoilCardMetrics:
    return await SoilCardOCRAdapter().extract_metrics(image, **kwargs)
