from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_farmer
from app.db.session import get_db
from app.models.crop_record import CropRecord
from app.models.crop_rule import CropRule
from app.models.farmer import Farmer
from app.models.market_price import MarketPrice
from app.models.pest_host_rule import PestHostRule
from app.models.plot import Plot
from app.models.recommendation import RecommendationOutcome, RecommendationRun
from app.models.season import Season
from app.models.soil_test import SoilTest
from app.schemas.suggestion import RecommendationOutcomeCreate, RecommendationRequest, RecommendationResponse
from app.suggestion_engine.filters import CertifiedSeedFilter, RegionFilter, SeasonFilter, SoilFilter, SowingWindowFilter, WaterFilter
from app.suggestion_engine.pipeline import PipelineOrchestrator
from app.suggestion_engine.rules import CropFamilyRule, CropRepeatGapRule, LegumeRotationRule, RootDepthRule
from app.suggestion_engine.scorers import NetReturnScorer, PestRiskScorer, SoilHealthScorer, WaterRiskScorer

router = APIRouter(prefix="/recommendations", tags=["recommendations"])
RULESET_VERSION = "ruleset-v1"
SCORER_VERSION = "weighted-v1"
PRICE_MAX_AGE_DAYS = 30
SCORE_WEIGHTS = {"soil_health": 0.25, "pest_risk": 0.25, "net_return": 0.30, "water_risk": 0.20}


@router.post("", response_model=RecommendationResponse)
async def recommend(
    payload: RecommendationRequest,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> RecommendationResponse:
    plot = await session.scalar(select(Plot).where(
        Plot.id == payload.plot_id, Plot.farmer_id == farmer.id, Plot.is_archived.is_(False),
    ))
    if plot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plot not found")

    soil_test = await session.scalar(select(SoilTest).where(SoilTest.plot_id == plot.id, SoilTest.status == "approved")
                                     .order_by(SoilTest.tested_at.desc(), SoilTest.id.desc()).limit(1))
    soil_type = payload.soil_type or (soil_test.soil_type if soil_test else None)
    soil_data = ({
        "soil_type": soil_type,
        "n_val": float(soil_test.n_val) if soil_test and soil_test.n_val is not None else None,
        "p_val": float(soil_test.p_val) if soil_test and soil_test.p_val is not None else None,
        "k_val": float(soil_test.k_val) if soil_test and soil_test.k_val is not None else None,
        "ph": float(soil_test.ph) if soil_test and soil_test.ph is not None else None,
        "organic_matter": float(soil_test.organic_matter) if soil_test and soil_test.organic_matter is not None else None,
    })

    previous_rows = (await session.execute(
        select(CropRecord, Season)
        .join(Season, CropRecord.season_id == Season.id)
        .where(CropRecord.plot_id == plot.id)
        .order_by(Season.year.asc().nullsfirst(), Season.id.asc(), CropRecord.id.asc())
    )).all()
    distinct_seasons = list(dict.fromkeys(record.season_id for record, _ in previous_rows))
    selected_seasons = distinct_seasons[-3:]
    first_distance = len(selected_seasons)
    history = []
    for record, season in previous_rows:
        if record.season_id not in selected_seasons:
            continue
        season_position = selected_seasons.index(record.season_id)
        distance = first_distance - season_position
        rule_for_crop = await session.scalar(select(CropRule).where(
            func.lower(CropRule.crop_name) == record.crop_name.casefold(),
            CropRule.status == "active",
        ).order_by(CropRule.rule_version.desc()).limit(1))
        history.append({
            "crop_name": record.crop_name,
            "crop_family": record.crop_family or (rule_for_crop.crop_family if rule_for_crop else None),
            "root_depth": rule_for_crop.root_depth if rule_for_crop else None,
            "season_id": season.id,
            "season_year": season.year,
            "season_distance": distance,
            "updated_at": record.updated_at.isoformat(),
        })

    region = payload.region or plot.district
    notes: list[str] = []
    if not region:
        notes.append("District or region is missing; district-specific rules and market prices cannot be matched.")
    if not soil_type:
        notes.append("Soil type is missing; soil-specific suitability is uncertain.")
    if soil_test is None or all(getattr(soil_test, key) is None for key in ("n_val", "p_val", "k_val", "ph")):
        notes.append("No measured soil nutrient or pH values are available.")
    if payload.rainfall_mm is None or payload.forecast_rainfall_mm is None:
        notes.append("Observed rainfall or forecast rainfall is missing.")
    if payload.available_water_mm is None:
        notes.append("Available irrigation or water-supply estimate is missing.")
    if payload.sowing_window_days_remaining is None:
        notes.append("Remaining sowing-window days are missing.")
    if not (payload.irrigation_type or plot.irrigation_type):
        notes.append("Irrigation information is missing.")
    if not history:
        notes.append("No previous crop history is recorded for the plot.")

    active_rules = (await session.scalars(select(CropRule).where(
        CropRule.status == "active", CropRule.approved_at.is_not(None),
        CropRule.source_url.is_not(None), CropRule.source_version.is_not(None),
    ).order_by(CropRule.crop_name, CropRule.rule_version.desc()))).all()
    latest_rules: dict[str, CropRule] = {}
    for rule in active_rules:
        if region and rule.effective_region and rule.effective_region.casefold() == region.casefold():
            latest_rules.setdefault(rule.crop_name.casefold(), rule)
    rules = list(latest_rules.values())
    if not rules:
        notes.append("No expert-approved active crop rules match this district. No crop advice was generated.")

    pest_rows = (await session.scalars(select(PestHostRule).where(
        PestHostRule.status == "active", PestHostRule.approved_at.is_not(None),
        PestHostRule.effective_region.ilike(region) if region else False,
        PestHostRule.target_crop.in_([rule.crop_name for rule in rules]) if rules else False,
        PestHostRule.season.in_([payload.season, "all"]),
    ).order_by(PestHostRule.version.desc()))).all() if rules else []
    pest_by_crop: dict[str, list[PestHostRule]] = {}
    for pest_rule in pest_rows:
        pest_by_crop.setdefault(pest_rule.target_crop.casefold(), []).append(pest_rule)

    today = date.today()
    market_snapshot = (await session.scalars(select(MarketPrice).where(
        MarketPrice.district == region,
        MarketPrice.currency == "INR",
        MarketPrice.price_unit == "INR/kg",
        MarketPrice.quality_status == "verified",
        MarketPrice.crop_name.in_([rule.crop_name for rule in rules]) if rules else False,
    ).order_by(MarketPrice.date.desc(), MarketPrice.id.desc()))).all() if region and rules else []
    prices = [p for p in market_snapshot if p.date <= today
              and p.date >= today - timedelta(days=PRICE_MAX_AGE_DAYS)
              and p.source and p.source_version and p.quality_status == "verified"]
    price_by_crop: dict[str, MarketPrice] = {}
    for price in prices:
        price_by_crop.setdefault(price.crop_name.casefold(), price)

    candidates = []
    for rule in rules:
        knowledge = rule.knowledge_data or {}
        approved_pest_rules = pest_by_crop.get(rule.crop_name.casefold(), [])
        market = price_by_crop.get(rule.crop_name.casefold())
        freshness = {"crop_rule_source_version": rule.source_version,
                     "crop_rule_approved_at": rule.approved_at.isoformat() if rule.approved_at else None,
                     "market_price_date": market.date.isoformat() if market else None,
                     "market_price_age_days": str((today - market.date).days) if market else None}
        candidate_notes = []
        if market is None:
            candidate_notes.append(f"No fresh district-matched INR/kg price is available for {rule.crop_name}.")
        if knowledge.get("expected_yield_kg_per_acre") is None:
            candidate_notes.append(f"Expected yield is not recorded for {rule.crop_name}.")
        if any(knowledge.get(key) is None for key in ("input_cost_inr_per_acre", "fertilizer_savings_inr_per_acre", "subsidy_eligible")):
            candidate_notes.append(f"One or more return assumptions are missing for {rule.crop_name}.")
        if knowledge.get("pest_risk_index") is None:
            candidate_notes.append(f"Reviewed pest-risk data is missing for {rule.crop_name}.")
        if knowledge.get("water_requirement_mm") is None:
            candidate_notes.append(f"Reviewed water requirement is missing for {rule.crop_name}.")
        notes.extend(candidate_notes)
        required_inputs_present = all((
            region, soil_type, payload.rainfall_mm is not None, payload.forecast_rainfall_mm is not None,
            payload.sowing_window_days_remaining is not None,
            payload.available_water_mm is not None,
            payload.irrigation_type or plot.irrigation_type,
        ))
        confidence = "high" if not candidate_notes and required_inputs_present and history else ("medium" if not candidate_notes else "low")
        expected_yield = knowledge.get("expected_yield_kg_per_acre")
        candidates.append({
            "crop_name": rule.crop_name,
            "crop_family": rule.crop_family,
            "root_depth": rule.root_depth,
            "water_requirement": rule.water_requirement,
            "water_requirement_mm": knowledge.get("water_requirement_mm"),
            "nitrogen_effect": float(rule.nitrogen_effect) if rule.nitrogen_effect is not None else None,
            "organic_addition": knowledge.get("organic_addition"),
            "duration_days": rule.duration_days,
            "suitable_seasons": rule.effective_seasons,
            "suitable_regions": [rule.effective_region],
            "suitable_soil_types": knowledge.get("suitable_soil_types"),
            "soil_ph_min": knowledge.get("soil_ph_min"),
            "soil_ph_max": knowledge.get("soil_ph_max"),
            "minimum_rainfall_mm": knowledge.get("minimum_rainfall_mm"),
            "suitable_irrigation_types": knowledge.get("suitable_irrigation_types"),
            "maximum_sowing_delay_days": knowledge.get("maximum_sowing_delay_days"),
            "minimum_repeat_gap_seasons": knowledge.get("minimum_repeat_gap_seasons", 1),
            "baseline_pest_risk": knowledge.get("pest_risk_index"),
            "host_crops": sorted({name for pest in approved_pest_rules for name in pest.host_crops}),
            "host_crop_families": sorted({name for pest in approved_pest_rules for name in pest.host_families}),
            "pest_host_rule_records": [{"id": pest.id, "version": pest.version, "pest_name": pest.pest_name,
                                         "risk_points": pest.risk_points, "source_title": pest.source_title,
                                         "source_url": pest.source_url, "source_version": pest.source_version,
                                         "host_crops": pest.host_crops, "host_families": pest.host_families}
                                        for pest in approved_pest_rules],
            "soil_benefit_score": knowledge.get("soil_benefit_score"),
            "soil_benefit_source": knowledge.get("soil_benefit_source"),
            "expected_yield_kg_per_acre": expected_yield,
            "expected_yield_kg": expected_yield * float(plot.area_acres) if expected_yield is not None else None,
            "expected_price": float(market.modal_price) if market else None,
            "price_source": market.source if market else None,
            "price_date": market.date.isoformat() if market else None,
            "input_cost_inr_per_acre": knowledge.get("input_cost_inr_per_acre"),
            "fertilizer_savings_inr_per_acre": knowledge.get("fertilizer_savings_inr_per_acre"),
            "subsidy_eligible": knowledge.get("subsidy_eligible"),
            "eligible_subsidy_inr_per_acre": knowledge.get("eligible_subsidy_inr_per_acre"),
            "currency": market.currency if market else "INR",
            "source_ids": [f"crop_rule:{rule.id}:v{rule.rule_version}"] + [f"pest_host_rule:{p.id}:v{p.version}" for p in approved_pest_rules] + ([f"market_price:{market.id}"] if market else []),
            "source_citations": [f"{rule.source_title}: {rule.source_url}"] + [f"{p.source_title}: {p.source_url} ({p.pest_name})" for p in approved_pest_rules] + ([f"{market.source} {market.date.isoformat()}"] if market else []),
            "freshness": freshness,
            "assumptions": [
                "Net return = expected yield x fresh modal price - input costs + documented fertilizer savings + eligible subsidy.",
                "Yield and cost assumptions are per acre; output return is for this plot and one season.",
            ] + [
                f"Expected yield: {expected_yield} kg/acre ({knowledge.get('yield_source')}, {knowledge.get('yield_date')}).",
                *([f"Market price: INR {float(market.modal_price):.2f}/kg ({market.source}, {market.date.isoformat()})."] if market else ["Market price unavailable: no return estimate is made."]),
                f"Input costs: INR {knowledge.get('input_cost_inr_per_acre')}/acre/season ({knowledge.get('cost_source')}, {knowledge.get('cost_date')}).",
                f"Fertilizer savings: INR {knowledge.get('fertilizer_savings_inr_per_acre')}/acre ({knowledge.get('fertilizer_savings_source')}, {knowledge.get('fertilizer_savings_date')}).",
                (f"Eligible subsidy: INR {knowledge.get('eligible_subsidy_inr_per_acre')}/acre ({knowledge.get('subsidy_source')}, checked {knowledge.get('subsidy_checked_date')})."
                 if knowledge.get("subsidy_eligible") else f"Subsidy: not eligible ({knowledge.get('subsidy_source')}, checked {knowledge.get('subsidy_checked_date')})."),
            ],
            "confidence": confidence,
        })

    orchestrator = PipelineOrchestrator(
        filters=[SeasonFilter(), RegionFilter(), SoilFilter(), WaterFilter(), SowingWindowFilter(), CertifiedSeedFilter()],
        rules=[CropFamilyRule(), CropRepeatGapRule(), LegumeRotationRule(), RootDepthRule()],
        scorers=[
            SoilHealthScorer(weight=SCORE_WEIGHTS["soil_health"]),
            PestRiskScorer(weight=SCORE_WEIGHTS["pest_risk"]),
            NetReturnScorer(weight=SCORE_WEIGHTS["net_return"]),
            WaterRiskScorer(weight=SCORE_WEIGHTS["water_risk"]),
        ],
    )
    response = orchestrator.run(
        plot_id=plot.id, season=payload.season, region=region,
        candidates=candidates, plot_history=history, soil_data=soil_data,
        market_prices=[{"crop_name": p.crop_name, "modal_price": float(p.modal_price)} for p in prices],
        available_water_mm=payload.available_water_mm,
        preferred_crops=payload.preferred_crops,
        limit=min(payload.limit, 3),
        plot_area_acres=float(plot.area_acres),
        data_quality_notes=list(dict.fromkeys(notes)),
        advisor_referral_required=bool(notes),
        advisor_referral_reason=("Several required inputs or expert-approved data sources are missing; consult a local agronomist." if notes else None),
        soil_type=soil_type,
        rainfall_mm=payload.rainfall_mm,
        forecast_rainfall_mm=payload.forecast_rainfall_mm,
        sowing_window_days_remaining=payload.sowing_window_days_remaining,
        irrigation_type=payload.irrigation_type or plot.irrigation_type,
        farmer_preferences=payload.farmer_preferences,
        ruleset_version=RULESET_VERSION,
        scorer_version=SCORER_VERSION,
    )
    if not response.options and not response.advisor_referral_required:
        response.advisor_referral_required = True
        response.advisor_referral_reason = "No candidate passed the approved agronomic filters; consult a local agronomist."
        response.data_quality_notes.append("No crop options passed the reviewed suitability rules.")
    run = RecommendationRun(
        farmer_id=farmer.id,
        plot_id=plot.id,
        ruleset_version=RULESET_VERSION,
        scorer_version=SCORER_VERSION,
        request_snapshot={
            "request": payload.model_dump(mode="json"),
            "plot": {"id": plot.id, "area_acres": float(plot.area_acres), "irrigation_type": plot.irrigation_type},
            "plot_geojson": await session.scalar(select(func.ST_AsGeoJSON(Plot.location)).where(Plot.id == plot.id)),
            "soil": soil_data,
            "history": history,
            "market_price_records": [{"id": p.id, "crop_name": p.crop_name, "price": float(p.modal_price),
                                     "currency": p.currency, "unit": p.price_unit, "date": p.date.isoformat(),
                                     "district": p.district, "source": p.source, "source_version": p.source_version,
                                     "used": p in prices} for p in market_snapshot],
        },
        rule_snapshot=[{
            "id": r.id, "crop_name": r.crop_name, "rule_version": r.rule_version,
            "schema_version": r.schema_version, "source_title": r.source_title, "source_url": r.source_url,
            "source_version": r.source_version, "effective_region": r.effective_region,
            "effective_seasons": r.effective_seasons, "knowledge_data": r.knowledge_data,
            "status": r.status, "approved_at": r.approved_at.isoformat() if r.approved_at else None,
        } for r in rules],
        response_snapshot={},
    )
    session.add(run)
    await session.flush()
    response.recommendation_id = run.id
    run.response_snapshot = response.model_dump(mode="json")
    await session.commit()
    return response


@router.post("/{recommendation_id}/outcome", status_code=status.HTTP_201_CREATED)
async def record_outcome(
    recommendation_id: int,
    payload: RecommendationOutcomeCreate,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> dict:
    run = await session.scalar(select(RecommendationRun).where(
        RecommendationRun.id == recommendation_id, RecommendationRun.farmer_id == farmer.id,
    ))
    if run is None:
        raise HTTPException(status_code=404, detail="Recommendation record not found")
    existing = await session.scalar(select(RecommendationOutcome.id).where(
        RecommendationOutcome.recommendation_id == run.id,
    ))
    if existing:
        raise HTTPException(status_code=409, detail="An outcome has already been recorded")
    outcome = RecommendationOutcome(recommendation_id=run.id, **payload.model_dump())
    session.add(outcome)
    await session.commit()
    await session.refresh(outcome)
    return {"id": outcome.id, "recommendation_id": run.id, "planted_crop": outcome.planted_crop,
            "actual_yield_kg": float(outcome.actual_yield_kg) if outcome.actual_yield_kg is not None else None,
            "actual_input_cost": float(outcome.actual_input_cost) if outcome.actual_input_cost is not None else None,
            "currency": outcome.currency, "outcome_notes": outcome.outcome_notes,
            "observed_at": outcome.observed_at.isoformat()}
