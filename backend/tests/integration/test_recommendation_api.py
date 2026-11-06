import os
from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from pydantic import SecretStr

from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import CropRecord, CropRule, Farmer, MarketPrice, Plot, RecommendationRun, Season, SoilTest
from app.models.crop_rule import CropRuleAudit
from app.models.market_price import MinimumSupportPrice
from app.models.pest_host_rule import PestHostRule
from app.redis.client import get_redis
from config.settings import settings

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL must point to a disposable PostGIS database")


class TestRedis:
    async def get(self, key):
        return None


@pytest_asyncio.fixture
async def rec_client():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: TestRedis()
    phone = "+919876543210"
    async with factory() as session:
        farmer = Farmer(phone=phone, name="Recommendation farmer")
        season = Season(name="Kharif previous", district="Mysuru", year=2025,
                        season_code="kharif", start_month=6, end_month=10)
        session.add_all([farmer, season])
        await session.flush()
        plot = Plot(farmer_id=farmer.id, name="Test plot", area_acres=1.5,
                    area_value=1.5, area_unit="acre", irrigation_type="drip")
        session.add(plot)
        await session.flush()
        session.add_all([
            SoilTest(plot_id=plot.id, soil_type="red", n_val=80, p_val=40, k_val=50, ph=6.2),
            CropRecord(plot_id=plot.id, season_id=season.id, crop_name="Maize", crop_family="Poaceae"),
        ])
        await session.commit()
        plot_id = plot.id

    headers = {"Authorization": f"Bearer {create_access_token(phone)}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, headers, factory, plot_id
    app.dependency_overrides.clear()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def complete_knowledge():
    return {
        "expected_yield_kg_per_acre": 1000,
        "yield_source": "UASB field trial report",
        "yield_date": "2025-06-01",
        "input_cost_inr_per_acre": 5000,
        "cost_source": "UASB cost of cultivation study",
        "cost_date": "2025-06-01",
        "cost_currency": "INR",
        "cost_unit": "INR/acre/season",
        "fertilizer_savings_inr_per_acre": 500,
        "fertilizer_savings_source": "Reviewed nutrient budget",
        "fertilizer_savings_date": "2025-06-01",
        "subsidy_eligible": False,
        "subsidy_source": "Official scheme eligibility review",
        "subsidy_checked_date": "2025-06-01",
        "water_requirement_mm": 500,
        "water_requirement_source": "UASB package of practices",
        "pest_risk_index": 25,
        "pest_source": "Reviewed Mysuru pest surveillance",
        "soil_benefit_score": 65,
        "soil_benefit_source": "UASB soil health trial",
        "suitable_soil_types": ["red"],
        "minimum_repeat_gap_seasons": 1,
    }


async def activate_rule(client, headers, version=1):
    body = {
        "crop_name": "Chickpea", "rule_version": version, "schema_version": "1.0",
        "crop_family": "Fabaceae", "root_depth": "shallow", "water_requirement": "medium",
        "source_title": "Reviewed Mysuru agronomy record",
        "source_url": "https://example.org/agronomy/chickpea", "source_version": "2025.1",
        "effective_region": "Mysuru", "effective_seasons": ["Kharif"],
        "knowledge_data": complete_knowledge(),
    }
    draft = await client.post("/api/v1/admin/crop-rules", json=body, headers=headers)
    assert draft.status_code == 201, draft.text
    rule_id = draft.json()["id"]
    submitted = await client.post(f"/api/v1/admin/crop-rules/{rule_id}/submit-review", headers=headers)
    assert submitted.status_code == 200
    for reviewer, key in (("agro-1", "review-key-1"), ("agro-2", "review-key-2")):
        reviewed = await client.post(
            f"/api/v1/admin/crop-rules/{rule_id}/reviews", json={"decision": "approve", "notes": "Reviewed"},
            headers={**headers, "X-Reviewer-ID": reviewer, "X-Reviewer-Key": key},
        )
        assert reviewed.status_code == 200, reviewed.text
    activated = await client.post(f"/api/v1/admin/crop-rules/{rule_id}/activate", headers=headers)
    assert activated.status_code == 200, activated.text
    return rule_id


@pytest.mark.asyncio
async def test_recommendation_uses_approved_data_exact_weights_fresh_price_and_saves_outcome(rec_client, monkeypatch):
    client, headers, factory, plot_id = rec_client
    monkeypatch.setattr(settings, "admin_api_key", SecretStr("test-admin"))
    monkeypatch.setattr(settings, "agronomist_reviewer_keys", {
        "agro-1": SecretStr("review-key-1"), "agro-2": SecretStr("review-key-2"),
    })
    await activate_rule(client, {"X-Admin-Key": "test-admin"})
    async with factory() as session:
        session.add(MarketPrice(crop_name="Chickpea", mandi_name="Mysuru", modal_price=20, date=date.today(),
                                district="Mysuru", source="AGMARKNET", source_version="resource-v1",
                                currency="INR", price_unit="INR/kg"))
        await session.commit()

    response = await client.post("/api/v1/recommendations", json={
        "plot_id": plot_id, "season": "Kharif", "region": "Mysuru", "soil_type": "red",
        "rainfall_mm": 400, "forecast_rainfall_mm": 100, "sowing_window_days_remaining": 20,
        "irrigation_type": "drip", "available_water_mm": 800,
    }, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["advisor_referral_required"] is False
    assert len(body["options"]) <= 3
    option = body["options"][0]
    assert option["crop_name"] == "Chickpea"
    assert option["expected_net_return"] == pytest.approx(23250.0)  # 1,500 kg x ₹20 - ₹7,500 + ₹750 savings
    assert option["return_currency"] == "INR"
    assert option["score_components"].keys() == {"soil_health", "pest_risk", "net_return", "water_risk"}
    assert body["scoring_weights"] == {"soil_health": 0.25, "pest_risk": 0.25, "net_return": 0.3, "water_risk": 0.2}
    assert option["source_ids"] and option["source_citations"]
    assert option["freshness"]["market_price_age_days"] == "0"
    assert any("INR 5000.0/acre/season" in item for item in option["assumptions"])
    assert any("INR 20.00/kg" in item for item in option["assumptions"])

    async with factory() as session:
        run = await session.get(RecommendationRun, body["recommendation_id"])
        assert run.request_snapshot["request"]["forecast_rainfall_mm"] == 100
        assert run.rule_snapshot[0]["rule_version"] == 1
        assert run.response_snapshot["options"][0]["expected_net_return"] == 23250.0
    outcome = await client.post(f"/api/v1/recommendations/{body['recommendation_id']}/outcome", json={
        "planted_crop": "Chickpea", "actual_yield_kg": 1320, "actual_input_cost": 7100,
        "outcome_notes": "Harvest recorded",
    }, headers=headers)
    assert outcome.status_code == 201, outcome.text


@pytest.mark.asyncio
async def test_draft_rules_never_become_advice_without_two_distinct_reviewer_keys(rec_client, monkeypatch):
    client, headers, _, _ = rec_client
    monkeypatch.setattr(settings, "admin_api_key", SecretStr("test-admin"))
    monkeypatch.setattr(settings, "agronomist_reviewer_keys", {"agro-1": SecretStr("review-key-1")})
    admin_headers = {"X-Admin-Key": "test-admin"}
    body = {
        "crop_name": "Draft crop", "rule_version": 1,
        "source_title": "Source", "source_url": "https://example.org/source", "source_version": "1",
        "effective_region": "Mysuru", "effective_seasons": ["Kharif"], "knowledge_data": {},
    }
    draft = await client.post("/api/v1/admin/crop-rules", json=body, headers=admin_headers)
    assert draft.status_code == 201
    rule_id = draft.json()["id"]
    assert draft.json()["status"] == "draft"
    await client.post(f"/api/v1/admin/crop-rules/{rule_id}/submit-review", headers=admin_headers)
    review_headers = {**admin_headers, "X-Reviewer-ID": "agro-1", "X-Reviewer-Key": "review-key-1"}
    first = await client.post(f"/api/v1/admin/crop-rules/{rule_id}/reviews", json={"decision": "approve"}, headers=review_headers)
    assert first.json()["status"] == "in_review"
    activation = await client.post(f"/api/v1/admin/crop-rules/{rule_id}/activate", headers=admin_headers)
    assert activation.status_code == 409
    audit = await client.get(f"/api/v1/admin/crop-rules/{rule_id}/audit", headers=admin_headers)
    assert [item["action"] for item in audit.json()] == ["draft_created", "submitted_for_review", "approve"]


@pytest.mark.asyncio
async def test_stale_price_is_not_used_and_triggers_advisor_referral(rec_client, monkeypatch):
    client, headers, factory, plot_id = rec_client
    monkeypatch.setattr(settings, "admin_api_key", SecretStr("test-admin"))
    monkeypatch.setattr(settings, "agronomist_reviewer_keys", {
        "agro-1": SecretStr("review-key-1"), "agro-2": SecretStr("review-key-2"),
    })
    await activate_rule(client, {"X-Admin-Key": "test-admin"})
    async with factory() as session:
        session.add(MarketPrice(crop_name="Chickpea", mandi_name="Mysuru", modal_price=20,
                                date=date.today() - timedelta(days=60), district="Mysuru", source="AGMARKNET",
                                currency="INR", price_unit="INR/kg"))
        await session.commit()
    response = await client.post("/api/v1/recommendations", json={
        "plot_id": plot_id, "season": "Kharif", "region": "Mysuru", "soil_type": "red",
        "rainfall_mm": 400, "forecast_rainfall_mm": 100, "sowing_window_days_remaining": 20,
        "irrigation_type": "drip", "available_water_mm": 800,
    }, headers=headers)
    assert response.status_code == 200
    assert response.json()["advisor_referral_required"] is True
    assert response.json()["options"][0]["expected_net_return"] is None
    assert any("fresh district-matched" in note for note in response.json()["data_quality_notes"])


@pytest.mark.asyncio
async def test_rule_rollback_restores_previous_reviewed_version(rec_client, monkeypatch):
    client, _, _, _ = rec_client
    monkeypatch.setattr(settings, "admin_api_key", SecretStr("test-admin"))
    monkeypatch.setattr(settings, "agronomist_reviewer_keys", {
        "agro-1": SecretStr("review-key-1"), "agro-2": SecretStr("review-key-2"),
    })
    headers = {"X-Admin-Key": "test-admin"}
    first_id = await activate_rule(client, headers, version=1)
    second_id = await activate_rule(client, headers, version=2)
    assert second_id != first_id
    rolled_back = await client.post(f"/api/v1/admin/crop-rules/{second_id}/rollback",
                                    json={"reason": "Detected issue in new local assumptions"}, headers=headers)
    assert rolled_back.status_code == 200 and rolled_back.json()["id"] == first_id
    old_rule = await client.get("/api/v1/admin/crop-rules", headers=headers)
    statuses = {(item["rule_version"]): item["status"] for item in old_rule.json()}
    assert statuses == {1: "active", 2: "rolled_back"}


@pytest.mark.asyncio
async def test_market_history_is_authenticated_and_exposes_provenance_and_freshness(rec_client):
    client, headers, factory, _ = rec_client
    async with factory() as session:
        session.add(MarketPrice(crop_name="Chickpea", mandi_name="Mysuru", modal_price=25,
                                date=date.today(), district="Mysuru", source="AGMARKNET",
                                source_version="feed-v1", currency="INR", price_unit="INR/kg",
                                quality_status="verified"))
        await session.commit()
    response = await client.get("/api/v1/market/prices?crop=Chickpea&district=Mysuru", headers=headers)
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["source"] == "AGMARKNET" and item["source_version"] == "feed-v1"
    assert item["fresh"] is True and item["quality_status"] == "verified"
    assert (await client.get("/api/v1/market/prices?crop=Chickpea&district=Mysuru")).status_code == 401


@pytest.mark.asyncio
async def test_recommendation_traces_active_region_and_season_pest_host_record(rec_client, monkeypatch):
    client, headers, factory, plot_id = rec_client
    monkeypatch.setattr(settings, "admin_api_key", SecretStr("test-admin"))
    monkeypatch.setattr(settings, "agronomist_reviewer_keys", {
        "agro-1": SecretStr("review-key-1"), "agro-2": SecretStr("review-key-2"),
    })
    await activate_rule(client, {"X-Admin-Key": "test-admin"})
    async with factory() as session:
        session.add(MarketPrice(crop_name="Chickpea", mandi_name="Mysuru", modal_price=20,
                                date=date.today(), district="Mysuru", source="AGMARKNET", source_version="v1",
                                currency="INR", price_unit="INR/kg"))
        pest = PestHostRule(target_crop="Chickpea", pest_name="Pod borer", host_crops=["Maize"],
                            host_families=["Poaceae"], effective_region="Mysuru", season="Kharif", version=1,
                            risk_points=32, source_title="UASB surveillance bulletin",
                            source_url="https://example.org/pest", source_version="2025.1",
                            status="active", approved_at=datetime.now(UTC), reviewer_ids=["agro-1", "agro-2"])
        session.add(pest)
        await session.commit()
        pest_id = pest.id
    result = await client.post("/api/v1/recommendations", json={
        "plot_id": plot_id, "season": "Kharif", "region": "Mysuru", "soil_type": "red",
        "rainfall_mm": 400, "forecast_rainfall_mm": 100, "sowing_window_days_remaining": 20,
        "irrigation_type": "drip", "available_water_mm": 800,
    }, headers=headers)
    assert result.status_code == 200, result.text
    option = result.json()["options"][0]
    assert f"pest_host_rule:{pest_id}:v1" in option["source_ids"]
    assert any("Pod borer" in citation for citation in option["source_citations"])
    assert any("associated with Pod borer" in reason for reason in option["reasons"])


@pytest.mark.asyncio
async def test_msp_upsert_and_two_reviewer_pest_knowledge_workflow(rec_client, monkeypatch):
    client, _, _, _ = rec_client
    monkeypatch.setattr(settings, "admin_api_key", SecretStr("test-admin"))
    monkeypatch.setattr(settings, "agronomist_reviewer_keys", {
        "agro-1": SecretStr("review-key-1"), "agro-2": SecretStr("review-key-2"),
    })
    admin = {"X-Admin-Key": "test-admin"}
    msp_body = {"crop_name": "Chickpea", "season": "Rabi", "year": 2026, "amount": 5650,
                "currency": "INR", "price_unit": "INR/quintal", "effective_from": "2026-10-01",
                "source": "Commission for Agricultural Costs and Prices", "source_version": "2026-rabi"}
    first = await client.put("/api/v1/market/admin/msp", json=msp_body, headers=admin)
    second = await client.put("/api/v1/market/admin/msp", json=msp_body | {"amount": 5700}, headers=admin)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert (await client.get("/api/v1/market/msp?crop=Chickpea", headers={"Authorization": f"Bearer {create_access_token('+919876543210')}"})).json()[0]["amount"] == "5700.00"

    draft = await client.post("/api/v1/market/admin/pest-rules", headers=admin, json={
        "target_crop": "Chickpea", "pest_name": "Pod borer", "host_crops": ["Maize"],
        "host_families": ["Poaceae"], "effective_region": "Mysuru", "season": "Kharif", "version": 1,
        "risk_points": 25, "source_title": "UASB regional surveillance", "source_url": "https://example.org/pests",
        "source_version": "2025.1",
    })
    assert draft.status_code == 201 and draft.json()["status"] == "draft"
    rule_id = draft.json()["id"]
    for reviewer in ("agro-1", "agro-2"):
        approval = await client.post(f"/api/v1/market/admin/pest-rules/{rule_id}/approve", headers={
            **admin, "X-Reviewer-ID": reviewer, "X-Reviewer-Key": f"review-key-{reviewer[-1]}",
        })
    assert approval.json()["status"] == "active"
