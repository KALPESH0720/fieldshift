"""Async NASA AppEEARS SMAP point-sampling worker."""

from celery.utils.log import get_task_logger
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.models.plot import Plot
from app.models.satellite_job import SatelliteJob
from app.services.integrations.http import IntegrationUnavailable
from app.services.integrations.nasa_smap import NASASMAPAdapter
from app.workers.celery_app import celery_app
from app.workers.tasks.common import WorkerSession, run_async

logger = get_task_logger(__name__)


async def _process_smap_job(job_id: int) -> dict:
    async with WorkerSession() as session:
        job = await session.get(SatelliteJob, job_id)
        if job is None:
            return {"status": "missing"}
        if job.status == "completed":
            return {"status": "completed", "observations": len(job.observations)}
        if job.status not in {"queued", "failed"}:
            return {"status": job.status}
        job.status = "processing"
        job.error_code = None
        await session.commit()
        coordinates = await session.execute(select(
            func.ST_Y(func.ST_PointOnSurface(Plot.location)),
            func.ST_X(func.ST_PointOnSurface(Plot.location)),
        ).where(Plot.id == job.plot_id, Plot.farmer_id == job.farmer_id))
        location = coordinates.one_or_none()
        if location is None or location[0] is None or location[1] is None:
            job.status = "failed"
            job.error_code = "plot_location_missing"
            await session.commit()
            return {"status": job.status}
        try:
            result = await NASASMAPAdapter().fetch_point(
                latitude=float(location[0]), longitude=float(location[1]),
                start_date=job.start_date.isoformat(), end_date=job.end_date.isoformat(),
                plot_id=job.plot_id,
            )
            job.provider_task_id = result["provider_task_id"]
            job.observations = result["observations"]
            job.status = "completed"
        except Exception as exc:
            logger.warning("NASA SMAP extraction failed job_id=%s error_type=%s", job.id, type(exc).__name__)
            job.status = "failed"
            job.error_code = "provider_unavailable" if isinstance(exc, IntegrationUnavailable) else type(exc).__name__[:64]
        await session.commit()
        return {"status": job.status, "observations": len(job.observations or [])}


@celery_app.task(name="field_shift.process_nasa_smap_job", acks_late=True)
def process_nasa_smap_job(job_id: int) -> dict:
    return run_async(_process_smap_job(job_id))
