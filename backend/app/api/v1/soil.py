import base64
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_farmer
from app.db.session import get_db
from app.models.farmer import Farmer
from app.models.plot import Plot
from app.models.soil_card_upload import SoilCardUpload
from app.models.soil_test import SoilTest
from app.schemas.soil import (
    SoilCardExtractRequest, SoilCardExtractResponse, SoilCardReview,
    SoilCardUploadResponse, SoilTestCreate, SoilTestPage, SoilTestResponse, SoilTestUpdate,
)
from app.services.integrations.http import IntegrationUnavailable
from app.services.integrations.ocr_service import SoilCardOCRAdapter, parse_soil_health_card_text
from app.services.soil_cards import content_sha256, low_confidence_fields, sniff_image
from app.services.storage.malware import MalwareDetected, ScannerUnavailable, get_malware_scanner
from app.services.storage.objects import ObjectStore, ObjectStoreUnavailable, get_object_store
from app.workers.tasks.soil_cards import process_soil_card_upload_task
from config.settings import settings

router = APIRouter(prefix="", tags=["soil health"])


async def _owned_plot(session: AsyncSession, plot_id: int, farmer_id: int) -> Plot:
    plot = await session.scalar(select(Plot).where(
        Plot.id == plot_id, Plot.farmer_id == farmer_id, Plot.is_archived.is_(False),
    ))
    if plot is None:
        raise HTTPException(status_code=404, detail="Plot not found")
    return plot


async def _owned_soil_test(session: AsyncSession, soil_test_id: int, farmer_id: int) -> SoilTest:
    row = await session.scalar(select(SoilTest).join(Plot, Plot.id == SoilTest.plot_id).where(
        SoilTest.id == soil_test_id, Plot.farmer_id == farmer_id,
    ))
    if row is None:
        raise HTTPException(status_code=404, detail="Soil test not found")
    return row


async def _owned_upload(session: AsyncSession, upload_id: int, farmer_id: int) -> SoilCardUpload:
    row = await session.scalar(select(SoilCardUpload).where(
        SoilCardUpload.id == upload_id, SoilCardUpload.farmer_id == farmer_id,
    ))
    if row is None:
        raise HTTPException(status_code=404, detail="Soil card upload not found")
    return row


async def _upload_dto(session: AsyncSession, row: SoilCardUpload) -> SoilCardUploadResponse:
    soil_test_id = await session.scalar(select(SoilTest.id).where(SoilTest.soil_card_upload_id == row.id))
    return SoilCardUploadResponse(
        id=row.id, plot_id=row.plot_id, status=row.status, content_type=row.content_type,
        size_bytes=row.size_bytes, sha256=row.sha256, scan_status=row.scan_status,
        expires_at=row.expires_at, created_at=row.created_at,
        extracted_metrics=row.extracted_metrics or {}, confidence=row.confidence or {},
        low_confidence_fields=low_confidence_fields(row.extracted_metrics or {}, row.confidence or {}),
        ocr_error_code=row.ocr_error_code, soil_test_id=soil_test_id,
    )


@router.get("/plots/{plot_id}/soil-tests", response_model=SoilTestPage)
async def list_soil_tests(
    plot_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> SoilTestPage:
    await _owned_plot(session, plot_id, farmer.id)
    base = select(SoilTest).where(SoilTest.plot_id == plot_id).order_by(SoilTest.tested_at.desc(), SoilTest.id.desc())
    total = await session.scalar(select(func.count()).select_from(SoilTest).where(SoilTest.plot_id == plot_id)) or 0
    rows = (await session.scalars(base.limit(limit).offset(offset))).all()
    return SoilTestPage(items=[SoilTestResponse.model_validate(row, from_attributes=True) for row in rows],
                        total=total, limit=limit, offset=offset)


@router.post("/plots/{plot_id}/soil-tests", response_model=SoilTestResponse, status_code=status.HTTP_201_CREATED)
async def create_soil_test(
    plot_id: int,
    payload: SoilTestCreate,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> SoilTestResponse:
    await _owned_plot(session, plot_id, farmer.id)
    row = SoilTest(plot_id=plot_id, **payload.model_dump(), status="approved",
                   reviewed_by_farmer_id=farmer.id, reviewed_at=datetime.now(UTC))
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return SoilTestResponse.model_validate(row, from_attributes=True)


@router.get("/soil-tests/{soil_test_id}", response_model=SoilTestResponse)
async def read_soil_test(
    soil_test_id: int,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> SoilTestResponse:
    row = await _owned_soil_test(session, soil_test_id, farmer.id)
    return SoilTestResponse.model_validate(row, from_attributes=True)


@router.patch("/soil-tests/{soil_test_id}", response_model=SoilTestResponse)
@router.put("/soil-tests/{soil_test_id}", response_model=SoilTestResponse)
async def update_soil_test(
    soil_test_id: int,
    payload: SoilTestUpdate,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> SoilTestResponse:
    row = await _owned_soil_test(session, soil_test_id, farmer.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value.astimezone(UTC) if field == "tested_at" and value else value)
    if not any(getattr(row, key) is not None for key in ("n_val", "p_val", "k_val", "ph", "organic_matter")):
        raise HTTPException(status_code=422, detail="A soil test must retain at least one measured value")
    row.provenance = "manual_correction"
    row.reviewed_by_farmer_id = farmer.id
    row.reviewed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(row)
    return SoilTestResponse.model_validate(row, from_attributes=True)


@router.delete("/soil-tests/{soil_test_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_soil_test(
    soil_test_id: int,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> None:
    row = await _owned_soil_test(session, soil_test_id, farmer.id)
    await session.delete(row)
    await session.commit()


@router.post("/plots/{plot_id}/soil-card-uploads", response_model=SoilCardUploadResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def upload_soil_card(
    plot_id: int,
    request: Request,
    content_type_header: str | None = Header(default=None, alias="Content-Type"),
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
    object_store: ObjectStore = Depends(get_object_store),
    scanner=Depends(get_malware_scanner),
) -> SoilCardUploadResponse:
    await _owned_plot(session, plot_id, farmer.id)
    received = bytearray()
    async for chunk in request.stream():
        received.extend(chunk)
        if len(received) > settings.soil_card_max_upload_bytes:
            raise HTTPException(status_code=413, detail="Soil card image exceeds the configured size limit")
    data = bytes(received)
    if not data:
        raise HTTPException(status_code=422, detail="Uploaded image is empty")
    try:
        content_type, extension = sniff_image(data, content_type_header or "application/octet-stream")
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    digest = content_sha256(data)
    existing = await session.scalar(select(SoilCardUpload.id).where(
        SoilCardUpload.plot_id == plot_id, SoilCardUpload.sha256 == digest,
    ))
    if existing is not None:
        raise HTTPException(status_code=409, detail="This Soil Health Card image was already uploaded for this plot")
    try:
        scan_engine = await scanner.scan(data)
        key = f"soil-cards/{farmer.id}/{plot_id}/{uuid4().hex}.{extension}"
        await object_store.put(key, data, content_type, digest)
    except MalwareDetected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (ScannerUnavailable, ObjectStoreUnavailable) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    row = SoilCardUpload(
        farmer_id=farmer.id, plot_id=plot_id, object_key=key, sha256=digest,
        content_type=content_type, size_bytes=len(data), scan_status="clean", scan_engine=scan_engine,
        status="queued", expires_at=datetime.now(UTC) + timedelta(days=settings.soil_card_retention_days),
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        await object_store.delete(key)
        raise HTTPException(status_code=409, detail="This Soil Health Card image was already uploaded for this plot") from exc
    await session.refresh(row)
    try:
        process_soil_card_upload_task.delay(row.id)
    except Exception:
        row.status = "failed"
        row.ocr_error_code = "job_queue_unavailable"
        await session.commit()
    return await _upload_dto(session, row)


@router.post("/soil-card-uploads/{upload_id}/retry", response_model=SoilCardUploadResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def retry_soil_card_ocr(
    upload_id: int,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> SoilCardUploadResponse:
    row = await _owned_upload(session, upload_id, farmer.id)
    if row.status not in {"failed", "queued"}:
        raise HTTPException(status_code=409, detail="Only queued or failed OCR jobs can be retried")
    row.status = "queued"
    row.ocr_error_code = None
    await session.commit()
    try:
        process_soil_card_upload_task.delay(row.id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="OCR job queue is unavailable; retry shortly") from exc
    return await _upload_dto(session, row)


@router.get("/soil-card-uploads/{upload_id}", response_model=SoilCardUploadResponse)
async def read_soil_card_upload(
    upload_id: int,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> SoilCardUploadResponse:
    return await _upload_dto(session, await _owned_upload(session, upload_id, farmer.id))


@router.get("/soil-card-uploads/{upload_id}/photo-url")
async def soil_card_photo_url(
    upload_id: int,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
    object_store: ObjectStore = Depends(get_object_store),
) -> dict[str, str | int]:
    row = await _owned_upload(session, upload_id, farmer.id)
    if row.expires_at <= datetime.now(UTC) or row.status == "expired":
        raise HTTPException(status_code=410, detail="Soil card image has reached its retention deadline")
    try:
        return {"url": await object_store.signed_read_url(row.object_key, expires_seconds=300),
                "expires_in_seconds": 300}
    except ObjectStoreUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/soil-card-uploads/{upload_id}/review", response_model=SoilTestResponse,
             status_code=status.HTTP_201_CREATED)
async def review_soil_card(
    upload_id: int,
    payload: SoilCardReview,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> SoilTestResponse:
    upload = await _owned_upload(session, upload_id, farmer.id)
    if upload.status != "needs_review":
        raise HTTPException(status_code=409, detail="Only completed OCR results can be reviewed")
    low_fields = low_confidence_fields(upload.extracted_metrics or {}, upload.confidence or {})
    for field in low_fields:
        if field not in payload.model_fields_set or getattr(payload, field) is None:
            raise HTTPException(status_code=422, detail=f"Correct low-confidence field '{field}' before approving this card")
    values = {}
    for field in ("n_val", "p_val", "k_val", "ph", "organic_matter", "soil_type"):
        value = getattr(payload, field) if field in payload.model_fields_set else (upload.extracted_metrics or {}).get(field)
        values[field] = value
    if not any(values[field] is not None for field in ("n_val", "p_val", "k_val", "ph", "organic_matter")):
        raise HTTPException(status_code=422, detail="Review must confirm or correct at least one measured soil value")
    row = SoilTest(
        plot_id=upload.plot_id, **values, tested_at=payload.tested_at.astimezone(UTC),
        nutrient_unit=payload.nutrient_unit, organic_matter_unit=payload.organic_matter_unit,
        provenance="soil_card_ocr_reviewed", source_reference=f"soil-card-upload:{upload.id}",
        confidence=upload.confidence or {}, status="approved", reviewed_by_farmer_id=farmer.id,
        reviewed_at=datetime.now(UTC), soil_card_upload_id=upload.id,
    )
    session.add(row)
    upload.status = "approved"
    upload.updated_at = datetime.now(UTC)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="This Soil Health Card already has a reviewed soil record") from exc
    await session.refresh(row)
    return SoilTestResponse.model_validate(row, from_attributes=True)


@router.post("/soil-cards/extract", response_model=SoilCardExtractResponse, status_code=status.HTTP_200_OK)
async def extract_soil_card_synchronous(payload: SoilCardExtractRequest) -> SoilCardExtractResponse:
    """Synchronously extract soil parameters, ratings, units, and card metadata from
    an uploaded Soil Health Card image (via Vision LLM / OCR adapter) or raw OCR text.
    Never injects placeholder or mock data; absent fields remain `None`.
    """
    if payload.raw_text:
        parsed = parse_soil_health_card_text(payload.raw_text)
    else:
        try:
            raw_b64 = (payload.image_base64 or "").split(",")[-1]
            image_bytes = base64.b64decode(raw_b64, validate=False)
        except Exception as exc:
            raise HTTPException(status_code=422, detail="Invalid base64 image payload") from exc
        if not image_bytes:
            raise HTTPException(status_code=422, detail="Uploaded image is empty")
        try:
            parsed = await SoilCardOCRAdapter().extract_metrics(image_bytes, content_type=payload.content_type)
        except IntegrationUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    return SoilCardExtractResponse(
        metrics=parsed.model_dump(exclude={"raw", "confidence"}),
        raw_values=parsed.raw_values,
        units=parsed.units,
        ratings=parsed.ratings,
        metadata=parsed.metadata,
        confidence=parsed.confidence,
    )

