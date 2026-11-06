from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_farmer
from app.db.session import get_db
from app.models.farmer import Farmer
from app.models.plot import Plot
from app.models.satellite_job import SatelliteJob
from app.schemas.satellite import SatelliteJobResponse, SatelliteSoilMoistureRequest
from app.workers.tasks.satellite_monitoring import process_nasa_smap_job
from config.settings import settings

router = APIRouter(prefix="/satellite", tags=["satellite"])


def _job_response(job: SatelliteJob) -> SatelliteJobResponse:
    return SatelliteJobResponse(
        id=job.id, plot_id=job.plot_id, start_date=job.start_date, end_date=job.end_date,
        status=job.status, observation_count=len(job.observations or []),
        observations=job.observations or [], error_code=job.error_code,
        created_at=job.created_at, updated_at=job.updated_at,
    )


@router.post("/plots/{plot_id}/smap/soil-moisture", response_model=SatelliteJobResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def request_smap_soil_moisture(
    plot_id: int,
    payload: SatelliteSoilMoistureRequest,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> SatelliteJobResponse:
    if not settings.nasa_earthdata_username or not settings.nasa_earthdata_password:
        raise HTTPException(status_code=503, detail="NASA AppEEARS is not configured")
    plot = await session.scalar(select(Plot).where(
        Plot.id == plot_id, Plot.farmer_id == farmer.id, Plot.is_archived.is_(False),
    ))
    if plot is None:
        raise HTTPException(status_code=404, detail="Plot not found")
    if plot.location is None:
        raise HTTPException(status_code=422, detail="Plot needs a Point or Polygon location for satellite sampling")
    job = SatelliteJob(
        farmer_id=farmer.id, plot_id=plot.id, start_date=payload.start_date, end_date=payload.end_date,
        status="queued", observations=[],
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    try:
        process_nasa_smap_job.delay(job.id)
    except Exception as exc:
        job.status = "failed"
        job.error_code = "job_queue_unavailable"
        await session.commit()
        raise HTTPException(status_code=503, detail="Satellite job queue is unavailable") from exc
    return _job_response(job)


@router.get("/smap/jobs/{job_id}", response_model=SatelliteJobResponse)
async def read_smap_job(
    job_id: int,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> SatelliteJobResponse:
    job = await session.scalar(select(SatelliteJob).where(
        SatelliteJob.id == job_id, SatelliteJob.farmer_id == farmer.id,
    ))
    if job is None:
        raise HTTPException(status_code=404, detail="Satellite job not found")
    return _job_response(job)
