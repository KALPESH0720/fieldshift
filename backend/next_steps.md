# Field Shift Backend - Detailed Completion Plan

## Purpose and scope

This document compares the backend currently in this repository with the backend commitments in **Field Shift: Adapting Farms with NASA Data - Detailed Implementation Plan (Integrated Ecosystem Features - V2)**. The PDF is treated as the product specification being assessed; its text is not an instruction to run external integrations, contact providers, or deploy anything.

This is a backend-only completion plan. It covers the API, persistence, recommendation services, data ingestion, integrations, workers, security, operational readiness, and backend verification. Frontend screens, PWA/IndexedDB client implementation, farmer interviews, and field-pilot execution are outside this repository, but backend contracts and gates needed by those efforts are called out.

## Executive status

The repository has a useful backend foundation and a working local FastAPI process. Core ORM models, migrations, typed settings, async DB/Redis clients, OTP/JWT code, farmer/plot/history endpoints, a recommendation pipeline, sync processing, integration adapters, and Celery task code exist. The previously recorded automated run was **40 passed and 5 skipped**; that is evidence of unit-level coverage, not proof of production readiness. The skipped database-dependent tests require a disposable PostGIS test database.

The implementation is **not complete against the V2 backend plan**. Major gaps include: OTP cannot be exercised without a configured SMS provider; several API modules are empty and not registered; recommendation/market/crop knowledge data has no production-grade source and curation workflow; Soil Health Card, weather, market, FPO, satellite and integration workflows are not exposed as APIs; models for groups, dealers and warehouses are not registered for migrations; contingency, intercropping, subsidies/PMFBY, human review, consent, data deletion, audit, backups, monitoring, and deployment readiness remain incomplete. Workers and adapters are code-level foundations whose live behavior still depends on provider credentials, real data, integration verification, and operational configuration.

## Repository audit: what is present

| Area | Present in code | Completion assessment |
|---|---|---|
| Configuration and local infrastructure | Pydantic settings; async SQLAlchemy/asyncpg; Redis async client; Docker Compose for PostGIS and Redis | Foundation present. Production secret management, environment validation and operational config remain. |
| ORM and migrations | Farmer, Plot, Season, CropRecord, CropRule, SoilTest, MarketPrice, Alert, sync models; PostGIS geometry; Alembic revisions | Core MVP tables exist. Group, InputDealer and Warehouse files are not exported from `app.models` and therefore are not currently registered in the metadata used for migrations. Need confirm schema constraints/indexes and migration parity. |
| Authentication | OTP generation/hash/verification, Redis expiry/cooldown, JWT issuance and bearer authentication | Core flow exists, but real OTP delivery requires SMS settings. There is no local development OTP delivery mechanism; verification cannot be completed from Swagger without a provider or a test/local-only mechanism. |
| Farmer and plot APIs | Farmer profile GET/POST; plot list/read/create/update with GeoJSON; plot history GET/POST | Core path exists. Farmer profile update, plot delete, local units, broader CRUD behavior and pagination are absent. |
| Recommendations | Filters, rotation rules, scoring, reason construction and authenticated endpoint | Working baseline; requires reviewed, versioned agronomy and market inputs. Explicit minimum-repeat interval, rainfall/sowing-window risk, fertilizer savings/subsidies, confidence/source attribution, uncertain-case handoff and outcome-based calibration are not complete. |
| Offline sync | Sync payload DTO, change log, endpoint and transaction-oriented engine | Foundation exists. Device/client contract, conflict policy acceptance, replay/idempotency, deleted-record/tombstone semantics, pagination/cursor durability and multi-device verification need completion. |
| Speech and messaging | Bhashini adapter and STT/TTS/translation routes; SMS/WhatsApp adapters | Adapter/route code exists. Provider configuration, consent/preferences, delivery status, retry/dead-letter behavior, local test strategy and end-to-end provider verification remain. |
| External data adapters | Weather, NASA SMAP, Sentinel-2, AgriStack and OCR service clients | Clients are present, but several corresponding route modules are empty. AgriStack consent flow, image upload/storage, normalized records and production provider verification are missing. |
| Workers | Celery app and price, weather, reminders task modules with a beat schedule | Task/schedule code exists for three jobs. Live worker/beat deployment, operational monitoring, data-quality/source provenance and error/replay procedures need work. Satellite monitoring task code is present but not registered in Celery includes or periodic schedule. |
| Additional ecosystem models | Group, InputDealer and Warehouse model files exist | They are not exported/registered in `app.models`; there are no complete API/workflow implementations. Subsidy/insurance and pest knowledge models are absent. |
| Verification | Unit, integration and E2E test files exist | Local unit suite was previously run. PostGIS integration/E2E execution, real app startup with migrations, external adapter smoke checks and a repeatable CI pipeline remain to be completed. |

## Priority 0 - make the MVP complete and verifiable

### 1. Make development and deployment configuration deterministic

- Keep Compose's published Postgres port, `.env` `DATABASE_URL`, Alembic, and application settings aligned. The current local fix uses host port `5433` to avoid the observed port-5432 collision; document this in `.env.example` and the setup instructions, and keep all connections pointing at the same Postgres instance.
- Add a startup/config validation command that checks required settings and reports missing provider configuration without printing secret values. Fail clearly for invalid database URLs and weak production JWT secrets.
- Add health/readiness endpoints: liveness should not require third parties; readiness should verify required DB/Redis dependencies with bounded timeouts.
- Add a repeatable setup and migration guide covering Windows PowerShell and Unix shells, test database isolation, worker/beat startup, and common local failures.

**Acceptance:** a clean checkout can start the stack, apply migrations, start the API and connect to the intended database without manually editing package internals; `/health/live` and `/health/ready` return meaningful status; secrets never appear in logs.

### 2. Close authentication and farmer lifecycle gaps

- Add a development-only OTP provider or dependency override that exposes a test OTP safely only in local/test environments. Never return/log OTPs in production. Keep production SMS delivery provider-driven.
- Add integration coverage for OTP send, expiry, resend cooldown, invalid code, single-use verification, JWT expiry, malformed tokens and farmer phone canonicalization.
- Add farmer profile update (`PUT`/`PATCH /farmers/me`) and the agreed delete/deactivation flow. Add consistent ownership checks and responses.
- Add OTP attempt throttling and abuse controls in addition to resend cooldown. Define phone normalization rules for supported countries instead of silently assuming India for every 10-digit number.
- Add an account deletion/export workflow (see privacy section) and document token revocation strategy. If stateless JWTs remain, choose and implement a short expiry/revocation mechanism appropriate for deletion and compromised accounts.

**Acceptance:** an automated local test can complete send -> verify -> bearer-authenticated farmer creation without an external SMS account; rate-limit, expiry, replay, and unauthorized access cases have explicit tests.

### 3. Finish the Phase 1 plot/history data contract

- Add farmer/plot update coverage, plot deletion/archive policy, pagination, and stable response DTOs. Decide whether deleting a farmer cascades, anonymizes, or is blocked by linked records.
- Persist/display plot area local unit and conversion rules (the PDF calls out area units). Validate geometry type, coordinate order, bounds, polygon closure, valid polygons, SRID, and area consistency; add spatial indexes and PostGIS query tests.
- Provide a controlled way to create/manage seasons and seed baseline seasons for a district/year. History currently references an existing `season_id`, so a fresh installation needs seed data or an admin import before the flow is usable.
- Add per-plot crop-history update/delete if required by offline edits; define duplicate crop records for a plot/season and ownership validation.
- Ensure migrations include every intended model, especially Group, InputDealer and Warehouse, and add migration tests that compare model metadata with an upgraded disposable PostGIS database.

**Acceptance:** a clean database supports farmer -> plot with Point/Polygon -> season -> crop history CRUD, correct GeoJSON round trips, foreign-key behavior, ownership isolation, and documented local-unit conversion.

### 4. Make recommendation output agronomically and economically complete

- Define a versioned crop-knowledge schema and import pipeline from ICAR/state-university-reviewed sources. Persist source, source version, effective region/season, reviewer, approval date, and active status for each crop rule. Do not treat unreviewed sample rules as agronomic advice.
- Define and seed a pilot dataset for one selected district, 2-3 crops and one language, as the V2 Phase 0/Phase 1 gate requests. Keep seed data separate from production curation.
- Extend inputs to include soil type, rainfall/forecast, sowing window, irrigation, farmer preference (e.g. low-water or early cash), and previous 2-3 seasons. Validate unknown/missing data and avoid fabricating precision.
- Implement the minimum crop-repeat gap rule, explicit weights and score normalization for soil benefit, pest-risk reduction, net return, and water/risk fit. Current request has a `limit` default of five; align the MVP contract with the PDF's top 2-3 and make this an explicit API policy.
- Complete net-return calculation using expected yield x price - input costs + exact fertilizer savings + eligible subsidies. Store cost assumptions, currency/unit, date and source. Expose assumptions to clients so the return can be explained and reproduced.
- Add price/MSP freshness and source checks, fallback behavior when price data is stale or missing, and crop-market/location matching. Implement historical price curves and glut forecasting only after enough reliable data exists.
- Return score components, source citations/IDs, data freshness, assumptions, confidence, one plain-language benefit and one trade-off per option. Add an explicit human-advisor referral result for low-confidence or out-of-distribution cases.
- Record recommendation requests and eventual planted crop/yield/cost/outcome, linked to rule and scorer versions. Add an offline evaluation set of 50-100 expert-approved scenarios and calibration reports.
- Have 2-3 agronomists approve every active rule before release. Add admin-only draft/review/approve/rollback workflow and audit history.

**Acceptance:** every recommendation can be reproduced from persisted versioned inputs; ranked options are limited to the chosen MVP policy; score components and explanation match; stale/uncertain cases are clearly identified or routed for review; expert-approved benchmark scenarios pass agreed thresholds.

### 5. Complete offline synchronization as a stable client contract

- Publish the operation schema and examples for plot and crop-history create/update/delete, identifiers, timestamps, client IDs, cursor semantics, and server ID remapping.
- Make operation application idempotent using `operation_id`; define transaction behavior when a batch contains invalid or conflicting operations (atomic batch vs per-operation results) and return actionable per-operation errors.
- Specify and implement the conflict policy per entity. Validate client timestamps and tie-breaking; protect against future timestamps and ensure plot geometry conflicts have deterministic behavior.
- Add tombstones/deletion propagation, durable change retention, cursor pagination, expired cursor recovery, and multi-device synchronization. Ensure sync only reads/writes the authenticated farmer's records.
- Add explicit handling for stale offline writes, duplicate deliveries, partial failures, malformed timestamps and unknown entity/action values.

**Acceptance:** integration tests use real disposable PostGIS/Redis services to exercise two clients editing the same crop/plot, retries, deleted records, cursor paging, ID remapping and cross-farmer isolation.

## Priority 1 - complete Phase 2 backend channels and data

### 6. Soil Health Card import and soil APIs

- Implement and register `app/api/v1/soil.py`: authenticated CRUD/read-history for plot soil tests, validation for N/P/K/pH/organic matter, provenance and tested-at date.
- Add secure image upload to object storage (not a raw local URL), file type/size validation, malware scanning policy, retention policy, and signed URLs.
- Connect OCR adapter to an upload/job flow; persist extracted values, confidence and raw OCR metadata; require human correction when confidence is low; never silently treat uncertain OCR as measured truth.
- Add tests for OCR provider failure, malformed metrics, duplicate cards and plot ownership.

**Acceptance:** upload -> OCR -> review/correction -> soil record is traceable, authenticated, and feeds only approved values into recommendations.

### 7. Weather, sowing alerts and reminders

- Implement and register `app/api/v1/weather.py` for current/forecast data and per-farmer reminder/alert preferences. Define provider/location cache keys, freshness and units.
- Connect weather ingestion to plot coordinates, persist forecast snapshots, and define what “sowing window compresses” means for each crop/region with agronomist approval.
- Add alert deduplication, quiet hours, language/template selection, user opt-out, delivery receipts, retry/dead-letter records and replay tools for SMS/WhatsApp. Avoid duplicate notifications from hourly jobs.
- Make the reminder schedule read farmer preferences and crop calendar data rather than broadcasting all due alerts indiscriminately.
- Add provider contract tests and a staging smoke test for IMD/weather and messaging providers.

**Acceptance:** forecast updates produce deterministic, deduplicated alerts for opted-in users; failures are visible and retryable; users can inspect and change their preferences.

### 8. Market prices, MSP, buyer links and glut context

- Implement and register `app/api/v1/market.py` for authenticated market-price history and freshness metadata, plus admin/import endpoints as appropriate.
- Add provenance columns for source/feed, fetched time, mandi/location mapping, commodity mapping, units, currency and quality status. Enforce idempotent upsert and duplicate detection.
- Add pagination/backfill/reconciliation for feeds, source terms and API-key handling. Model MSP separately with season/year/effective period and official source.
- Build historical price curves and a conservative glut forecast only when sufficient data exists; include uncertainty and source freshness. Add buyer/FPO listing data only after source and moderation rules are defined.

**Acceptance:** daily ingestion is repeatable, auditable, monitored, and recommendation scoring can query a location-relevant current price or clearly state why it cannot.

### 9. Pest and disease context

- Define a reviewed pest/host-crop/region/season knowledge base and migration; link pest carryover logic to that data rather than generic crop-family assumptions alone.
- Add a secure image/object-storage workflow if pest photos are part of the product; create a reviewed diagnosis service only with a reliable provider and confidence thresholds.
- Add explainable pest-risk factors, versioning and regional agronomist approval; route uncertain cases to a human advisor.

**Acceptance:** pest scores can be traced to an approved knowledge record and crop history; uncertain photo results never become definitive advice without review.

## Priority 2 - scale features in Phases 3 and 4

### 10. Intercropping and cover crops

- Design multi-crop-per-plot-per-season persistence: crop combinations, proportions/area allocation, planting dates, compatibility and outcome records. Preserve backward compatibility for single-crop records.
- Add combination filters/rules/scorers for competition, water/nutrients, soil benefit and market return. Return reasons and trade-offs per combination.
- Add migration, API DTOs, sync operations and agronomist-reviewed test cases.

### 11. FPO/group workflows

- Register the existing Group model and add migrations. Define group membership, invitations, roles, permissions, consent and audit rules.
- Implement and register `app/api/v1/fpo.py`: create/manage groups, membership, aggregated demand and approved group dashboards. Prevent unauthorized member-level plot/history disclosure.
- Define aggregation thresholds and privacy safeguards so small groups do not leak individual farmer data. Add bulk demand records for seed/fertilizer.

### 12. AgriStack consent and prefill

- Implement a consent lifecycle (purpose, data categories, validity, revoke, provider reference and audit event) before calling the adapter.
- Add authenticated API endpoints for consent start/callback/status/revoke and plot/history prefill. Validate provider response schema and reconcile imported data with user edits rather than silently overwriting.
- Add provider sandbox tests, token refresh/error behavior, data minimization, retry semantics and a complete audit trail.

### 13. Contingency sowing gates

- Define monitored thresholds and source data for sowing delays from NASA/IMD. Keep thresholds versioned and region/crop-specific with expert approval.
- Add decision evaluation and alert APIs/jobs for short-duration alternative crops; rerun suitability, availability, cost and return using current data.
- Return the trigger, timestamp, source, uncertainty, alternatives and human-review route.

### 14. Input dealer and certified-seed registry

- Register the InputDealer model, add migrations and district-level dealer/inventory/seed-lot schemas including certification source, validity, stock timestamp and location.
- Implement authenticated/admin ingestion and farmer lookup endpoints; add moderation, duplicate resolution and stock freshness policy.
- Connect the availability data to CertifiedSeedFilter with “unknown” separated from “unavailable”; do not penalize a crop based on stale/unverified inventory.

### 15. Mid-season satellite alarms

- Register `satellite_monitoring` task with Celery and define a schedule, job lock/idempotency, region/plot query strategy and rate limits. Current task code is not included in Celery's task include list or beat schedule.
- Implement and register `app/api/v1/satellite.py` for plot observations, anomaly history and alert acknowledgement.
- Persist Sentinel-2 indices/SMAP moisture observations with geometry, acquisition time, cloud/quality flags, processing version, provider provenance and confidence. Add anomaly baselines and thresholds reviewed by experts.
- Map anomalies to actionable, cautious mitigation guidance; include opt-in messaging and human escalation. Test provider outages, missing scenes and cloudy imagery.

### 16. Subsidy and PMFBY matching

- Define official policy, eligibility, geography, crop, season, application window and source-version data models. Add ingestion/validation and effective-date handling.
- Add consent-aware eligibility queries and explain exactly which farmer/plot facts drove a potential match. Do not imply approval or guaranteed payment.
- Include only verified eligible subsidy amounts in net-return scoring, preserve source/date/assumptions and allow agronomist/admin review.

### 17. Warehouse and e-NWR locator

- Register Warehouse model and migrations; define WDRA source, coordinates, capacity, commodity, service, availability and last verified time.
- Implement ingestion and authenticated geospatial nearby-search endpoints, distance/radius filters and data freshness display.
- Add recommendation support for storage/e-NWR only when availability and eligibility data are verified; include costs and price assumptions.

## Cross-cutting security, privacy and operations (release blockers)

### Security and privacy

- Add explicit consent records for integrations, messaging, location and data sharing; make revocation effective in downstream jobs.
- Add a farmer data export and delete-my-data workflow. Specify legal retention, anonymization, cascading references, backups and deletion propagation.
- Add append-only audit events for staff/admin access and sensitive changes; define role-based access control for agronomists, extension workers, FPO admins and system operators.
- Use TLS for deployed DB/Redis/provider connections, encrypted object storage and managed secret storage. Define database encryption-at-rest and key rotation operationally.
- Add request validation and upload limits, rate limiting, CORS policy, trusted-host configuration, safe error responses, dependency patching and security scans.
- Ensure logs do not contain OTPs, tokens, provider secrets, consent tokens, raw soil-card images or unnecessary personal data.

### Operations and reliability

- Add separate development, staging and production configuration, container healthchecks, migration release procedure and rollback plan.
- Add automated encrypted backups, retention, restore drills, migration recovery and disaster-recovery targets.
- Add structured logs, request IDs, metrics/traces, alerting, error reporting, worker/queue depth and job-success dashboards. Monitor stale market/weather/satellite feeds.
- Add worker and Celery Beat deployment instructions/process definitions; define concurrency, timeouts, retries, task idempotency and dead-letter/replay operations.
- Add admin interfaces or documented secured admin APIs to manage/import/approve crop rules and providers. Every agronomy rule change must be versioned, reviewed, attributable and reversible.

## Verification plan and release gates

### Automated checks

1. Run formatting, lint/type checks and unit tests on every change. Keep pure rule/scorer tests fast and deterministic.
2. Run Alembic upgrade from an empty disposable PostGIS database and from the prior supported migration; verify PostGIS extension and expected indexes/constraints.
3. Run all integration and E2E tests with isolated PostGIS and Redis services. Do not skip these in CI. Never use a developer's retained local data as a test database.
4. Add API tests for validation, auth, ownership, pagination, errors, replay, rate limits and provider-unavailable behavior.
5. Add contract tests using HTTPX MockTransport for every provider adapter, plus staging smoke tests gated on explicit credentials.
6. Add Celery eager tests for logic and a separate integration test that starts worker/beat against Redis, verifies schedule registration and observes a task run.
7. Add recommendation benchmark checks against the 50-100 agronomist-approved scenarios, with documented acceptance thresholds, confidence behavior and regression report.
8. Add migration, backup/restore, delete/export, security and load checks before production release.

### Phase gates for backend delivery

- **Phase 0 / MVP readiness:** select pilot district, crops and language; receive agronomist-approved rule set; complete auth/plot/history/recommendation/sync/reminder backend; demonstrate exact transparent economics and offline conflict behavior.
- **Phase 1 completion:** pilot-ready provider setup, usable local-language speech backend, tested notification preferences, reliable fresh data and evidence that integration/E2E suites pass against disposable infrastructure.
- **Phase 2:** soil-card import, weather alerts, pest context and market curves/glut signals are deployed with data provenance, source freshness, quality review and human escalation.
- **Phase 3:** intercropping, privacy-preserving FPO aggregation, consented AgriStack and contingency gates each pass regional expert sign-off before enabling a new region.
- **Phase 4:** dealer inventory, satellite alarms, subsidy/PMFBY and warehouse search have verified supply-chain/provider agreements, audited data and operational support.

## Suggested implementation order

1. Stabilize local/CI setup and migrations; register all intended models; add seed/import tooling for seasons and pilot crop data.
2. Complete auth testability, farmer/plot/history CRUD, ownership/security and integration test execution.
3. Make the MVP recommendation inputs, economic assumptions, versioned agronomy, explanations, confidence and outcome tracking complete.
4. Harden sync semantics and pass the full offline E2E flow using disposable PostGIS and Redis.
5. Complete soil import and weather/reminder APIs and delivery lifecycle, then market provenance/MSP and pest context.
6. Build operations/privacy/admin controls before any real farmer pilot with personal data.
7. Deliver Phase 3 and Phase 4 domains incrementally, each behind migrations, feature flags, provider contracts and local expert approval.

Do not mark the backend complete merely because Swagger opens or the API process starts. Completion requires the applicable phase gate, migrations, provider behavior, security/privacy controls, and automated tests to pass in a repeatable environment.
