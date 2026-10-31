"""Soil-card file validation and reviewable OCR job processing."""

import hashlib
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.soil_card_upload import SoilCardUpload
from app.services.integrations.ocr_service import SoilCardOCRAdapter
from app.services.storage.objects import ObjectStore
from config.settings import settings


def sniff_image(data: bytes, declared_content_type: str) -> tuple[str, str]:
    if data.startswith(b"\xff\xd8\xff"):
        content_type, extension = "image/jpeg", "jpg"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        content_type, extension = "image/png", "png"
    else:
        raise ValueError("Only JPEG and PNG Soil Health Card images are accepted")
    if declared_content_type not in {content_type, "application/octet-stream"}:
        raise ValueError("Uploaded content type does not match the image file")
    return content_type, extension


def content_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def low_confidence_fields(metrics: dict, confidence: dict[str, float]) -> list[str]:
    threshold = settings.soil_card_ocr_confidence_threshold
    return sorted(
        field for field, value in metrics.items()
        if value is not None and confidence.get(field, 0.0) < threshold
    )


async def process_soil_card_upload(
    session: AsyncSession,
    upload: SoilCardUpload,
    *,
    object_store: ObjectStore,
    adapter: SoilCardOCRAdapter | None = None,
) -> SoilCardUpload:
    if upload.status not in {"queued", "failed", "processing"}:
        return upload
    upload.status = "processing"
    upload.ocr_error_code = None
    await session.commit()
    try:
        image = await object_store.get(upload.object_key)
        result = await (adapter or SoilCardOCRAdapter()).extract_metrics(image, content_type=upload.content_type)
        metrics = result.model_dump(exclude={"raw", "confidence"})
        confidence = result.confidence
        upload.extracted_metrics = metrics
        upload.confidence = confidence
        upload.raw_ocr_metadata = result.raw
        upload.status = "needs_review"
        upload.updated_at = datetime.now(UTC)
        await session.commit()
    except Exception as exc:
        # Persist a non-sensitive error class; provider response bodies and credentials
        # are never copied to logs or client-visible error fields.
        upload.status = "failed"
        upload.ocr_error_code = type(exc).__name__[:64]
        upload.updated_at = datetime.now(UTC)
        await session.commit()
        raise
    return upload
