"""Authenticated backend facade for the standalone suggestion engine."""

import json
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_farmer
from app.db.session import get_db
from app.models.crop_record import CropRecord
from app.models.crop_rule import CropRule
from app.models.farmer import Farmer
from app.models.market_price import MarketPrice, MinimumSupportPrice
from app.models.plot import Plot
from app.models.recommendation import RecommendationOutcome, RecommendationRun
from app.models.season import Season
from app.models.soil_test import SoilTest
from app.schemas.suggestion import (
    OptionCard,
    RecommendationOutcomeCreate,
    RecommendationRequest,
    RecommendationRescoreCreate,
    RecommendationResponse,
)
from app.services.suggestion_engine import suggestion_engine

router = APIRouter(prefix="/recommendations", tags=["recommendations"])
PRICE_MAX_AGE_DAYS = 30
SEASON_CODE = {"kharif": "kharif", "rabi": "rabi", "zaid": "summer", "summer": "summer"}


def _season_key(value: str, year: int | None = None) -> tuple[str, int]:
    match = re.fullmatch(r"\s*([a-zA-Z]+)(?:[-\s](\d{4}))?\s*", value)
    if not match:
        raise HTTPException(status_code=422, detail="Season must be a season name, optionally followed by a year")
    code = match.group(1).casefold()
    if code not in SEASON_CODE:
        raise HTTPException(status_code=422, detail=f"Unsupported suggestion-engine season: {code}")
    return SEASON_CODE[code], int(match.group(2)) if match.group(2) else (year or date.today().year)


def _crop_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.casefold())


def _engine_irrigation(value: str | None) -> str:
    normalized = (value or "rainfed").casefold().replace(" ", "_")
    if normalized in {"full", "canal", "drip", "sprinkler", "assured"}:
        return "full"
    if normalized in {"limited", "partial", "supplemental", "well"}:
        return "limited"
    return "rainfed"


def _weights(preferences: list[str]) -> dict[str, float]:
    values = {"soil": 0.30, "return": 0.30, "water_risk": 0.25, "pest": 0.15}
    if "high_return" in preferences:
        values["return"] += 0.10
    if "soil_health" in preferences:
        values["soil"] += 0.10
    total = sum(values.values())
    return {key: round(value / total, 6) for key, value in values.items()}


def _effective_weights(engine_body: dict[str, Any]) -> dict[str, float]:
    values = dict(engine_body["preferences"]["weights"])
    flags = set(engine_body["preferences"].get("flags", []))
    if "low_water" in flags:
        values["water_risk"] += 0.15
    if "needs_cash_soon" in flags:
        values["return"] += 0.15
    total = sum(values.values())
    return {key: round(value / total, 6) for key, value in values.items()}


def _score_percent(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value * 100 if 0 <= value <= 1 else value, 2)


def _option_card(option: dict[str, Any], area_acres: float, engine_body: dict[str, Any]) -> OptionCard:
    sequence = option.get("crop_sequence") or []
    crop_name = str(sequence[0] if sequence else "").strip()
    if not crop_name:
        raise HTTPException(status_code=502, detail="Suggestion engine returned an option without a crop")
    scores = option.get("scores") or {}
    economics = option.get("economics") or {}
    reasons = [str(item.get("text_en") or item.get("code", "")).replace("_", " ")
               for item in option.get("reason_codes", []) if item]
    trade_off = option.get("trade_off_code") or {}
    tradeoff = str(trade_off.get("text_en") or trade_off.get("code", "Confirm local costs and conditions with an advisor.")).replace("_", " ")
    sources = list(option.get("sources") or [])
    return_value = economics.get("net_return_per_acre")
    cost = next((item for item in engine_body.get("costs", []) if item.get("crop") == crop_name), None)
    yield_q = cost.get("expected_yield_q_per_acre") if cost else None
    return OptionCard(
        crop_name=crop_name,
        score=_score_percent((scores or {}).get("total")) or 0,
        expected_yield_kg=round(float(yield_q) * 100 * area_acres, 2) if yield_q is not None else None,
        expected_net_return=round(float(return_value) * area_acres, 2) if return_value is not None else None,
        soil_health_score=_score_percent(scores.get("soil")),
        pest_risk_score=_score_percent(scores.get("pest")),
        water_risk_score=_score_percent(scores.get("water_risk")),
        reasons=reasons,
        tradeoffs=[tradeoff] if tradeoff else [],
        score_components={key: _score_percent(scores[key]) or 0 for key in ("soil", "return", "water_risk", "pest") if key in scores},
        source_ids=sources,
        source_citations=sources,
        freshness={"model": None, "rules": None, "params": None, "layer": None},
        assumptions=[f"Suggested crop sequence: {' → '.join(sequence)}.",
                     "Return estimate is per acre for the first crop in the sequence, scaled to this plot."],
        confidence=option.get("confidence", "low"),
        benefit=reasons[0] if reasons else f"{crop_name} ranked highest for the available plot data.",
        tradeoff=tradeoff,
    )


async def _engine_request(
    payload: RecommendationRequest, plot: Plot, geojson: str | None, session: AsyncSession,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    if not geojson:
        raise HTTPException(status_code=422, detail="A plot location is required to generate suggestions")
    geometry = json.loads(geojson)
    coordinates = geometry.get("coordinates")
    if geometry.get("type") == "Point":
        longitude, latitude = coordinates
    elif geometry.get("type") == "Polygon":
        # PointOnSurface is computed by PostGIS below; polygon centroid may fall outside a concave plot.
        point = await session.scalar(select(func.ST_AsGeoJSON(func.ST_PointOnSurface(Plot.location))).where(Plot.id == plot.id))
        if not point:
            raise HTTPException(status_code=422, detail="Plot boundary has no usable interior point")
        longitude, latitude = json.loads(point)["coordinates"]
    else:
        raise HTTPException(status_code=422, detail="Plot location must be a point or polygon")

    season_name, season_year = _season_key(payload.season)
    season_label = f"{season_name}-{season_year}"
    seasons = (await session.execute(
        select(CropRecord, Season)
        .join(Season, CropRecord.season_id == Season.id)
        .where(CropRecord.plot_id == plot.id)
        .order_by(Season.year.desc().nullslast(), Season.id.desc(), CropRecord.id.desc())
        .limit(30)
    )).all()
    history = []
    for record, season in seasons:
        code = SEASON_CODE.get((season.season_code or "").casefold())
        if code and season.year:
            history.append({"season": f"{code}-{season.year}", "crop": _crop_id(record.crop_name)})

    soil_test = await session.scalar(select(SoilTest).where(
        SoilTest.plot_id == plot.id, SoilTest.status == "approved",
    ).order_by(SoilTest.tested_at.desc(), SoilTest.id.desc()).limit(1))
    soil = {
        "texture": payload.soil_type or (soil_test.soil_type if soil_test else None),
        "ph": float(soil_test.ph) if soil_test and soil_test.ph is not None else None,
        # Organic matter and organic carbon are different measurements; do not relabel one as the other.
        "organic_carbon": None,
    }

    today = date.today()
    region = payload.region or plot.district
    candidates = (await session.scalars(select(CropRule).where(
        CropRule.status == "active", CropRule.approved_at.is_not(None),
        CropRule.source_url.is_not(None), CropRule.source_version.is_not(None),
    ).order_by(CropRule.crop_name, CropRule.rule_version.desc()))).all()
    latest_rules: dict[str, CropRule] = {}
    for rule in candidates:
        if region and rule.effective_region and rule.effective_region.casefold() == region.casefold():
            latest_rules.setdefault(_crop_id(rule.crop_name), rule)
    market_rows = (await session.scalars(select(MarketPrice).where(
        MarketPrice.district == region,
        MarketPrice.currency == "INR",
        MarketPrice.quality_status == "verified",
        MarketPrice.crop_name.in_([rule.crop_name for rule in latest_rules.values()]) if latest_rules else False,
        MarketPrice.date <= today,
        MarketPrice.date >= today - timedelta(days=PRICE_MAX_AGE_DAYS),
    ).order_by(MarketPrice.date.desc(), MarketPrice.id.desc()))).all() if region and latest_rules else []
    prices: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in market_rows:
        crop = _crop_id(row.crop_name)
        unit = row.price_unit.casefold().replace(" ", "")
        if crop in seen or not row.source or not row.source_version:
            continue
        if unit in {"inr/kg", "rs/kg"}:
            price = float(row.modal_price) * 100
        elif unit in {"inr/quintal", "inr/q", "rs/quintal"}:
            price = float(row.modal_price)
        elif unit in {"inr/tonne", "inr/ton", "rs/tonne"}:
            price = float(row.modal_price) / 10
        else:
            continue
        prices.append({"crop": crop, "price": price, "unit": "INR/quintal", "source": "market", "date": row.date.isoformat()})
        seen.add(crop)

    msp_rows = (await session.scalars(select(MinimumSupportPrice).where(
        MinimumSupportPrice.currency == "INR", MinimumSupportPrice.year == season_year,
        func.lower(MinimumSupportPrice.season).contains(season_name),
        MinimumSupportPrice.crop_name.in_([rule.crop_name for rule in latest_rules.values()]) if latest_rules else False,
    ).order_by(MinimumSupportPrice.effective_from.desc()))).all() if latest_rules else []
    for row in msp_rows:
        crop = _crop_id(row.crop_name)
        if crop not in seen and row.source_version and row.price_unit:
            prices.append({"crop": crop, "price": float(row.amount), "unit": row.price_unit,
                           "source": "msp", "date": row.effective_from.isoformat()})
            seen.add(crop)

    costs = []
    for crop, rule in latest_rules.items():
        knowledge = rule.knowledge_data or {}
        cost = knowledge.get("input_cost_inr_per_acre")
        yield_kg = knowledge.get("expected_yield_kg_per_acre")
        if cost is None:
            continue
        costs.append({"crop": crop, "cost_per_acre": float(cost),
                      "expected_yield_q_per_acre": float(yield_kg) / 100 if yield_kg is not None else None})

    irrigation = _engine_irrigation(payload.irrigation_type or plot.irrigation_type)
    engine_body = {
        "request_id": str(uuid4()),
        "location": {"lat": latitude, "lon": longitude},
        "season": season_label,
        "crop_history": history,
        "soil": soil,
        "irrigation": irrigation,
        "preferences": {
            "weights": _weights(payload.farmer_preferences),
            "flags": ["low_water" if flag == "low_water" else "needs_cash_soon"
                      for flag in payload.farmer_preferences if flag in {"low_water", "early_cash"}],
        },
        "prices": prices,
        "costs": costs,
        "horizon_seasons": 1,
    }
    snapshot = {
        "request": payload.model_dump(mode="json"),
        "engine_request": engine_body,
        "plot": {"id": plot.id, "area_acres": float(plot.area_acres), "district": region},
        "soil_test_id": soil_test.id if soil_test else None,
        "crop_rule_ids": [rule.id for rule in latest_rules.values()],
    }
    rule_snapshot = [{
        "id": rule.id,
        "crop_name": rule.crop_name,
        "rule_version": rule.rule_version,
        "source_title": rule.source_title,
        "source_url": rule.source_url,
        "source_version": rule.source_version,
        "effective_region": rule.effective_region,
        "effective_seasons": rule.effective_seasons,
        "knowledge_data": rule.knowledge_data,
    } for rule in latest_rules.values()]
    return engine_body, snapshot, rule_snapshot


def _backend_response(payload: RecommendationRequest, plot: Plot, engine_body: dict[str, Any],
                      engine_result: dict[str, Any]) -> RecommendationResponse:
    if not isinstance(engine_result.get("options"), list):
        raise HTTPException(status_code=502, detail="Suggestion engine returned an invalid recommendation")
    versions = engine_result.get("versions") or {}
    engine_notes = engine_result.get("notes", [])
    notes = list(dict.fromkeys(engine_notes + engine_result.get("missing_inputs", [])))
    needs_review = bool(engine_result.get("needs_human_review")) or any(
        note in {"KNOWLEDGE_NOT_REVIEWED", "SYNTHETIC_CELL_DATA"} for note in engine_notes
    )
    return RecommendationResponse(
        plot_id=plot.id,
        season=payload.season,
        generated_at=datetime.now(UTC),
        engine_request_id=engine_result.get("request_id"),
        engine_job_id=engine_result.get("job_id"),
        engine_status=engine_result.get("status"),
        engine_confidence=engine_result.get("confidence"),
        needs_human_review=needs_review,
        missing_inputs=engine_result.get("missing_inputs", []),
        excluded_first_season=engine_result.get("excluded_first_season", []),
        ruleset_version=str(versions.get("rules", "unknown")),
        scorer_version=str(versions.get("model", "unknown")),
        scoring_weights=_effective_weights(engine_body),
        options=[_option_card(option, float(plot.area_acres), engine_body)
                 for option in engine_result["options"][:min(payload.limit, 3)]],
        advisor_referral_required=needs_review,
        advisor_referral_reason=("; ".join(notes) or None) if needs_review else None,
        data_quality_notes=notes,
    )


@router.post("", response_model=RecommendationResponse)
async def recommend(
    payload: RecommendationRequest,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> RecommendationResponse:
    row = await session.execute(select(Plot, func.ST_AsGeoJSON(Plot.location)).where(
        Plot.id == payload.plot_id, Plot.farmer_id == farmer.id, Plot.is_archived.is_(False),
    ))
    owned_plot = row.one_or_none()
    if owned_plot is None:
        raise HTTPException(status_code=404, detail="Plot not found")
    plot, geojson = owned_plot
    engine_body, request_snapshot, rules_snapshot = await _engine_request(payload, plot, geojson, session)
    engine_result = await suggestion_engine.request("POST", "/recommend", json=engine_body)
    if not isinstance(engine_result, dict):
        raise HTTPException(status_code=502, detail="Suggestion engine returned an invalid recommendation")
    response = _backend_response(payload, plot, engine_body, engine_result)
    run = RecommendationRun(
        farmer_id=farmer.id,
        plot_id=plot.id,
        ruleset_version=response.ruleset_version,
        scorer_version=response.scorer_version,
        request_snapshot=request_snapshot,
        rule_snapshot=rules_snapshot,
        response_snapshot={"backend_response": response.model_dump(mode="json"), "engine_response": engine_result},
    )
    session.add(run)
    await session.flush()
    response.recommendation_id = run.id
    if response.engine_job_id:
        response.refinement_url = f"/api/v1/recommendations/{run.id}/job"
    run.response_snapshot = {**run.response_snapshot, "backend_response": response.model_dump(mode="json")}
    await session.commit()
    return response


@router.get("/{recommendation_id}", response_model=RecommendationResponse)
async def read_recommendation(
    recommendation_id: int,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> RecommendationResponse:
    run = await session.scalar(select(RecommendationRun).where(
        RecommendationRun.id == recommendation_id, RecommendationRun.farmer_id == farmer.id,
    ))
    if run is None:
        raise HTTPException(status_code=404, detail="Recommendation record not found")
    return RecommendationResponse.model_validate(run.response_snapshot["backend_response"])


@router.get("/{recommendation_id}/job")
async def recommendation_job(
    recommendation_id: int,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    run = await session.scalar(select(RecommendationRun).where(
        RecommendationRun.id == recommendation_id, RecommendationRun.farmer_id == farmer.id,
    ))
    if run is None:
        raise HTTPException(status_code=404, detail="Recommendation record not found")
    engine_id = (run.response_snapshot.get("engine_response", {}).get("job_id")
                 or run.response_snapshot.get("completed_job_id"))
    if not engine_id:
        raise HTTPException(status_code=404, detail="This recommendation has no refinement job")
    result = await suggestion_engine.request("GET", f"/jobs/{engine_id}")
    if not isinstance(result, dict):
        raise HTTPException(status_code=502, detail="Suggestion engine returned an invalid job")
    if result.get("status") == "done" and run.response_snapshot.get("engine_response", {}).get("status") != "refined":
        plot = await session.scalar(select(Plot).where(
            Plot.id == run.plot_id, Plot.farmer_id == farmer.id, Plot.is_archived.is_(False),
        ))
        if plot is not None:
            request_body = run.request_snapshot.get("engine_request", {})
            refined = await suggestion_engine.request("POST", "/recommend", json=request_body)
            if isinstance(refined, dict):
                request_values = run.request_snapshot.get("request", {})
                request_model = RecommendationRequest.model_validate(request_values)
                response = _backend_response(request_model, plot, request_body, refined)
                response.recommendation_id = run.id
                run.response_snapshot = {**run.response_snapshot, "backend_response": response.model_dump(mode="json"),
                                         "engine_response": refined, "completed_job_id": engine_id}
                await session.commit()
    return result


@router.post("/{recommendation_id}/rescore", response_model=RecommendationResponse)
async def rescore_recommendation(
    recommendation_id: int,
    payload: RecommendationRescoreCreate,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> RecommendationResponse:
    run = await session.scalar(select(RecommendationRun).where(
        RecommendationRun.id == recommendation_id, RecommendationRun.farmer_id == farmer.id,
    ))
    if run is None:
        raise HTTPException(status_code=404, detail="Recommendation record not found")
    request_id = run.response_snapshot.get("engine_response", {}).get("request_id")
    if not request_id:
        raise HTTPException(status_code=409, detail="The suggestion engine request is no longer available for rescoring")
    body: dict[str, Any] = {"request_id": request_id}
    if payload.weights is not None:
        try:
            body["weights"] = payload.weights.engine_dict()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if payload.flags is not None:
        body["flags"] = payload.flags
    engine_result = await suggestion_engine.request("POST", "/rescore", json=body)
    if not isinstance(engine_result, dict):
        raise HTTPException(status_code=502, detail="Suggestion engine returned an invalid rescore")
    plot = await session.scalar(select(Plot).where(
        Plot.id == run.plot_id, Plot.farmer_id == farmer.id, Plot.is_archived.is_(False),
    ))
    if plot is None:
        raise HTTPException(status_code=404, detail="Plot not found")
    request_body = run.request_snapshot.get("engine_request", {})
    if payload.weights is not None:
        request_body = {**request_body, "preferences": {**request_body.get("preferences", {}),
                                                         "weights": body["weights"]}}
    if payload.flags is not None:
        request_body = {**request_body, "preferences": {**request_body.get("preferences", {}), "flags": payload.flags}}
    original_request = RecommendationRequest.model_validate(run.request_snapshot.get("request", {}))
    response = _backend_response(original_request, plot, request_body, engine_result)
    response.recommendation_id = run.id
    response.refinement_url = f"/api/v1/recommendations/{run.id}/job" if response.engine_job_id else None
    run.response_snapshot = {**run.response_snapshot, "backend_response": response.model_dump(mode="json"),
                             "engine_response": engine_result,
                             **({"completed_job_id": run.response_snapshot["completed_job_id"]}
                                if run.response_snapshot.get("completed_job_id") else {})}
    run.request_snapshot = {**run.request_snapshot, "engine_request": request_body}
    await session.commit()
    return response


@router.get("/plots/{plot_id}/alerts")
async def suggestion_alerts(
    plot_id: int,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    row = await session.execute(select(Plot, func.ST_AsGeoJSON(func.ST_PointOnSurface(Plot.location))).where(
        Plot.id == plot_id, Plot.farmer_id == farmer.id, Plot.is_archived.is_(False),
    ))
    owned_plot = row.one_or_none()
    if owned_plot is None:
        raise HTTPException(status_code=404, detail="Plot not found")
    _, point_geojson = owned_plot
    if not point_geojson:
        raise HTTPException(status_code=422, detail="A plot location is required to retrieve local suggestion alerts")
    longitude, latitude = json.loads(point_geojson)["coordinates"]
    result = await suggestion_engine.request("GET", f"/alerts?lat={latitude}&lon={longitude}")
    if not isinstance(result, list):
        raise HTTPException(status_code=502, detail="Suggestion engine returned invalid alerts")
    return result


@router.post("/{recommendation_id}/outcome", status_code=status.HTTP_201_CREATED)
async def record_outcome(
    recommendation_id: int,
    payload: RecommendationOutcomeCreate,
    farmer: Farmer = Depends(get_current_farmer),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
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
    engine_body = run.request_snapshot.get("engine_request", {})
    engine_log_synced = False
    if engine_body.get("season"):
        season = engine_body["season"]
        try:
            await suggestion_engine.request("POST", "/actions", json={
                "plot_id": str(run.plot_id),
                "cell_id": run.response_snapshot.get("engine_response", {}).get("grid_cell_id"),
                "request_id": run.response_snapshot.get("engine_response", {}).get("request_id"),
                "season": season,
                "planted_crop": _crop_id(payload.planted_crop),
                "yield_q_per_acre": (float(payload.actual_yield_kg) / (float(run.request_snapshot.get("plot", {}).get("area_acres", 1)) * 100))
                if payload.actual_yield_kg is not None else None,
                "cost_per_acre": float(payload.actual_input_cost) / float(run.request_snapshot.get("plot", {}).get("area_acres", 1))
                if payload.actual_input_cost is not None else None,
                "notes": payload.outcome_notes,
            })
            engine_log_synced = True
        except HTTPException:
            # Backend remains the durable record; caller sees that engine learning sync did not complete.
            engine_log_synced = False
    return {"id": outcome.id, "recommendation_id": run.id, "planted_crop": outcome.planted_crop,
            "actual_yield_kg": float(outcome.actual_yield_kg) if outcome.actual_yield_kg is not None else None,
            "actual_input_cost": float(outcome.actual_input_cost) if outcome.actual_input_cost is not None else None,
            "currency": outcome.currency, "outcome_notes": outcome.outcome_notes,
            "observed_at": outcome.observed_at.isoformat(), "engine_log_synced": engine_log_synced}
