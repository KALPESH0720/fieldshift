"""OCR and retention jobs for securely uploaded Soil Health Cards."""

from datetime import UTC, datetime

from celery.utils.log import get_task_logger
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.models.soil_card_upload import SoilCardUpload
from app.services.integrations.http import IntegrationUnavailable
from app.services.soil_cards import process_soil_card_upload
from app.services.storage.objects import get_object_store
from app.workers.celery_app import celery_app
from app.workers.tasks.common import WorkerSession, run_async
from config.settings import settings

logger = get_task_logger(__name__)


async def _process_upload(upload_id: int) -> dict:
    async with WorkerSession() as session:
        upload = await session.get(SoilCardUpload, upload_id)
        if upload is None:
            return {"status": "missing"}
        if upload.status not in {"queued", "failed", "processing"}:
            return {"status": upload.status}
        try:
            await process_soil_card_upload(session, upload, object_store=get_object_store())
        except Exception as exc:
            logger.warning("Soil card OCR failed upload_id=%s error_type=%s", upload.id, type(exc).__name__)
            raise IntegrationUnavailable("Soil card OCR processing failed") from exc
        return {"status": upload.status}


@celery_app.task(name="field_shift.process_soil_card_upload", autoretry_for=(IntegrationUnavailable, SQLAlchemyError),
                 retry_backoff=True, retry_kwargs={"max_retries": 3})
def process_soil_card_upload_task(upload_id: int) -> dict:
    return run_async(_process_upload(upload_id))


async def _purge_expired() -> dict:
    purged = failed = 0
    async with WorkerSession() as session:
        rows = (await session.scalars(select(SoilCardUpload).where(
            SoilCardUpload.expires_at <= datetime.now(UTC), SoilCardUpload.status != "expired",
        ).limit(500))).all()
        store = get_object_store()
        for upload in rows:
            try:
                await store.delete(upload.object_key)
                upload.status = "expired"
                upload.raw_ocr_metadata = {}
                upload.updated_at = datetime.now(UTC)
                await session.commit()
                purged += 1
            except Exception as exc:
                logger.warning("Soil card retention purge failed upload_id=%s error_type=%s", upload.id, type(exc).__name__)
                failed += 1
    return {"purged": purged, "failed": failed}


@celery_app.task(name="field_shift.purge_expired_soil_cards", autoretry_for=(SQLAlchemyError,),
                 retry_backoff=True, retry_kwargs={"max_retries": 3})
def purge_expired_soil_cards() -> dict:
    return run_async(_purge_expired())
