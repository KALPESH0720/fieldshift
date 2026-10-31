import hmac
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.crop_rule import CropRule, CropRuleAudit, CropRuleReview
from app.schemas.crop_knowledge import (
    CropRuleAuditResponse,
    CropRuleDraftCreate,
    CropRuleResponse,
    CropRuleReviewRequest,
    CropRuleRollbackRequest,
)
from config.settings import settings

router = APIRouter(prefix="/admin/crop-rules", tags=["crop knowledge administration"])


def _admin(candidate: str | None) -> str:
    secret = settings.admin_api_key.get_secret_value() if settings.admin_api_key else ""
    if not secret:
        raise HTTPException(status_code=503, detail="Crop knowledge administration is not configured")
    if candidate is None or not hmac.compare_digest(candidate, secret):
        raise HTTPException(status_code=401, detail="Invalid admin credential")
    return "admin"


async def _audit(session: AsyncSession, rule: CropRule, actor: str, action: str, details: dict | None = None) -> None:
    session.add(CropRuleAudit(crop_rule_id=rule.id, actor_id=actor, action=action, details=details or {}))


@router.get("", response_model=list[CropRuleResponse])
async def list_rules(
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    session: AsyncSession = Depends(get_db),
) -> list[CropRuleResponse]:
    _admin(x_admin_key)
    rows = (await session.scalars(select(CropRule).order_by(CropRule.crop_name, CropRule.rule_version.desc()))).all()
    return [CropRuleResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("", response_model=CropRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_draft(
    payload: CropRuleDraftCreate,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    session: AsyncSession = Depends(get_db),
) -> CropRuleResponse:
    actor = _admin(x_admin_key)
    rule = CropRule(**payload.model_dump(), status="draft")
    session.add(rule)
    try:
        await session.flush()
        await _audit(session, rule, actor, "draft_created", {"version": rule.rule_version})
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="This crop rule version already exists") from exc
    await session.refresh(rule)
    return CropRuleResponse.model_validate(rule, from_attributes=True)


@router.post("/{rule_id}/submit-review", response_model=CropRuleResponse)
async def submit_for_review(
    rule_id: int,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    session: AsyncSession = Depends(get_db),
) -> CropRuleResponse:
    actor = _admin(x_admin_key)
    rule = await session.get(CropRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Crop rule not found")
    if rule.status not in {"draft", "rejected"}:
        raise HTTPException(status_code=409, detail="Only draft or rejected rules can enter review")
    rule.status = "in_review"
    await _audit(session, rule, actor, "submitted_for_review")
    await session.commit()
    await session.refresh(rule)
    return CropRuleResponse.model_validate(rule, from_attributes=True)


@router.post("/{rule_id}/reviews", response_model=CropRuleResponse)
async def review_rule(
    rule_id: int,
    payload: CropRuleReviewRequest,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    x_reviewer_id: str | None = Header(default=None, alias="X-Reviewer-ID"),
    x_reviewer_key: str | None = Header(default=None, alias="X-Reviewer-Key"),
    session: AsyncSession = Depends(get_db),
) -> CropRuleResponse:
    _admin(x_admin_key)
    reviewer = (x_reviewer_id or "").strip()
    reviewer_secret = settings.agronomist_reviewer_keys.get(reviewer)
    if not reviewer_secret or not x_reviewer_key or not hmac.compare_digest(
        x_reviewer_key, reviewer_secret.get_secret_value(),
    ):
        raise HTTPException(status_code=403, detail="Reviewer is not in the configured agronomist allowlist")
    rule = await session.get(CropRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Crop rule not found")
    if rule.status != "in_review":
        raise HTTPException(status_code=409, detail="Crop rule is not under review")
    existing = await session.scalar(select(CropRuleReview.id).where(
        CropRuleReview.crop_rule_id == rule.id, CropRuleReview.reviewer_id == reviewer,
    ))
    if existing is not None:
        raise HTTPException(status_code=409, detail="This reviewer has already reviewed this rule version")
    session.add(CropRuleReview(crop_rule_id=rule.id, reviewer_id=reviewer,
                               decision=payload.decision, notes=payload.notes))
    if payload.decision == "reject":
        rule.status = "rejected"
    else:
        approvals = await session.scalar(select(func.count(CropRuleReview.id)).where(
            CropRuleReview.crop_rule_id == rule.id, CropRuleReview.decision == "approve",
        ))
        # SQLAlchemy autoflushes the pending review before counting.
        if int(approvals or 0) >= 2:
            rule.status = "approved"
            rule.approved_at = datetime.now(UTC)
    await _audit(session, rule, reviewer, payload.decision, {"notes": payload.notes})
    await session.commit()
    await session.refresh(rule)
    return CropRuleResponse.model_validate(rule, from_attributes=True)


async def _approval_count(session: AsyncSession, rule_id: int) -> int:
    rows = (await session.scalars(select(CropRuleReview.reviewer_id).where(
        CropRuleReview.crop_rule_id == rule_id, CropRuleReview.decision == "approve",
    ))).all()
    return len(set(rows))


@router.post("/{rule_id}/activate", response_model=CropRuleResponse)
async def activate_rule(
    rule_id: int,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    session: AsyncSession = Depends(get_db),
) -> CropRuleResponse:
    actor = _admin(x_admin_key)
    rule = await session.get(CropRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Crop rule not found")
    if rule.status != "approved" or await _approval_count(session, rule.id) < 2:
        raise HTTPException(status_code=409, detail="At least two distinct agronomist approvals are required")
    required = {
        "expected_yield_kg_per_acre", "yield_source", "yield_date",
        "input_cost_inr_per_acre", "cost_source", "cost_date", "cost_currency", "cost_unit",
        "fertilizer_savings_inr_per_acre", "fertilizer_savings_source", "fertilizer_savings_date",
        "subsidy_eligible", "subsidy_source", "subsidy_checked_date",
        "water_requirement_mm", "water_requirement_source", "pest_risk_index", "soil_benefit_score",
        "pest_source", "soil_benefit_source",
    }
    knowledge = rule.knowledge_data or {}
    missing = sorted(key for key in required if knowledge.get(key) is None)
    if knowledge.get("subsidy_eligible") is True and knowledge.get("eligible_subsidy_inr_per_acre") is None:
        missing.append("eligible_subsidy_inr_per_acre")
    if knowledge.get("sowing_alert_enabled") is True and knowledge.get("sowing_alert_threshold_days") is None:
        missing.append("sowing_alert_threshold_days (required for enabled sowing-window alerts)")
    for numeric_key in ("expected_yield_kg_per_acre", "input_cost_inr_per_acre",
                        "fertilizer_savings_inr_per_acre", "water_requirement_mm", "pest_risk_index",
                        "soil_benefit_score"):
        try:
            numeric_value = float(knowledge.get(numeric_key))
        except (TypeError, ValueError):
            numeric_value = -1
        if numeric_key in {"expected_yield_kg_per_acre", "water_requirement_mm"} and numeric_value <= 0:
            missing.append(numeric_key + " must be positive")
        if numeric_key in {"input_cost_inr_per_acre", "fertilizer_savings_inr_per_acre"} and numeric_value < 0:
            missing.append(numeric_key + " cannot be negative")
        if numeric_key in {"pest_risk_index", "soil_benefit_score"} and not 0 <= numeric_value <= 100:
            missing.append(numeric_key + " must be 0-100")
    if knowledge.get("cost_currency") != "INR" or knowledge.get("cost_unit") != "INR/acre/season":
        missing.append("cost_currency/cost_unit must be INR and INR/acre/season")
    if missing or not rule.source_url or not rule.source_version or not rule.effective_region or not rule.effective_seasons:
        raise HTTPException(status_code=422, detail="Rule lacks required sourced agronomic/economic fields: " + ", ".join(missing or ["provenance or effective scope"]))
    previous_active = (await session.scalars(select(CropRule).where(
        CropRule.crop_name == rule.crop_name, CropRule.effective_region == rule.effective_region,
        CropRule.status == "active", CropRule.id != rule.id,
    ))).all()
    for previous in previous_active:
        previous.status = "superseded"
        await _audit(session, previous, actor, "superseded", {"by_rule_id": rule.id})
    rule.status = "active"
    rule.activated_at = datetime.now(UTC)
    await _audit(session, rule, actor, "activated", {"rule_version": rule.rule_version})
    await session.commit()
    await session.refresh(rule)
    return CropRuleResponse.model_validate(rule, from_attributes=True)


@router.post("/{rule_id}/rollback", response_model=CropRuleResponse | None)
async def rollback_rule(
    rule_id: int,
    payload: CropRuleRollbackRequest,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    session: AsyncSession = Depends(get_db),
) -> CropRuleResponse | None:
    actor = _admin(x_admin_key)
    rule = await session.get(CropRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Crop rule not found")
    if rule.status != "active":
        raise HTTPException(status_code=409, detail="Only an active rule can be rolled back")
    rule.status = "rolled_back"
    previous = await session.scalar(select(CropRule).where(
        CropRule.crop_name == rule.crop_name, CropRule.effective_region == rule.effective_region,
        CropRule.status == "superseded", CropRule.id != rule.id,
    ).order_by(CropRule.rule_version.desc()).limit(1))
    if previous and await _approval_count(session, previous.id) >= 2:
        previous.status = "active"
        previous.activated_at = datetime.now(UTC)
        await _audit(session, previous, actor, "reactivated_by_rollback", {"rolled_back_rule_id": rule.id})
    await _audit(session, rule, actor, "rolled_back", {"reason": payload.reason, "restored_rule_id": previous.id if previous else None})
    await session.commit()
    return CropRuleResponse.model_validate(previous, from_attributes=True) if previous else None


@router.get("/{rule_id}/audit", response_model=list[CropRuleAuditResponse])
async def rule_audit(
    rule_id: int,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    session: AsyncSession = Depends(get_db),
) -> list[CropRuleAuditResponse]:
    _admin(x_admin_key)
    rows = (await session.scalars(select(CropRuleAudit).where(CropRuleAudit.crop_rule_id == rule_id)
                                  .order_by(CropRuleAudit.id))).all()
    return [CropRuleAuditResponse.model_validate(row, from_attributes=True) for row in rows]
