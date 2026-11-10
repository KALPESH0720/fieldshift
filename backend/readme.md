# Field Shift Backend

FastAPI backend using PostgreSQL 16 with PostGIS, Redis, SQLAlchemy async, Alembic, and Celery.

## Local setup

Requirements: Python 3.11+, Docker Desktop (Windows) or Docker Engine with the Compose plugin (Unix), and Git.

## First startup and follow-up startups

The recommended shared setup runs the API, PostGIS, Redis, Celery worker, and Celery beat in Docker. The Compose backend profile also runs configuration validation and Alembic migrations before starting the API or workers. The host-based Python setup below remains available for development.

### First startup

1. Copy the example environment file and edit `.env`. Keep `.env` private and out of source control. Set a unique local `JWT_SECRET_KEY` and `ADMIN_API_KEY`; set `AGMARKNET_API_URL`, `AGMARKNET_RESOURCE_ID`, and `AGMARKNET_API_KEY` if you need market ingestion. Optional providers may stay blank. Never copy real keys into `.env.example`.

   Windows PowerShell:

   ```powershell
   if (-not (Test-Path .env)) { Copy-Item .env.example .env }
   notepad .env
   ```

   macOS / Linux / Unix:

   ```sh
   test -f .env || cp .env.example .env
   ${EDITOR:-vi} .env
   ```

2. Build and start the complete backend stack:

   ```sh
   docker compose --profile backend up --build -d
   ```

   This command works in PowerShell and Unix shells. It starts the database and Redis, runs the migration container to `head`, and then starts the API, worker, and beat scheduler.

3. Confirm readiness and open the API docs:

   ```text
   http://127.0.0.1:8000/health/ready
   http://127.0.0.1:8000/docs
   ```

   Or check container status/logs with `docker compose --profile backend ps` and `docker compose --profile backend logs -f api worker beat`.

### Follow-up startups

After Docker Desktop/Engine or the computer restarts, start the existing containers and preserve their database volumes with:

```sh
docker compose --profile backend up -d
```

Use `docker compose --profile backend logs -f api worker beat` to follow backend logs. To stop the stack without deleting Postgres/Redis data, run `docker compose --profile backend down`. **Do not use `down -v` unless you intend to erase the local databases.**

When you pull code that contains new migrations, rebuild and run the migration service before restarting the application services:

```sh
docker compose --profile backend build
docker compose --profile backend run --rm migrate
docker compose --profile backend up -d
```

The shareable container files are [Dockerfile](Dockerfile), [docker-compose.yml](docker-compose.yml), and [.dockerignore](.dockerignore). `.dockerignore` excludes `.env` and local virtual environments from image builds. Compose publishes Postgres on host port `5434`; containerized backend services use `postgres:5432` over the Compose network. Both addresses point to the same Compose PostGIS database.

After editing `.env` while the Docker stack is running, recreate the services that consume those settings:

```sh
docker compose --profile backend up -d --force-recreate api worker beat
```

### Windows PowerShell

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
docker compose up -d postgres redis
python -m config.validate
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If script activation is disabled, use `.venv\Scripts\python.exe` and `.venv\Scripts\alembic.exe` directly instead of changing machine execution policy.

### macOS / Linux / Unix shell

```sh
test -f .env || cp .env.example .env
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test]'
docker compose up -d postgres redis
python -m config.validate
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

For host-run development, Compose exposes Postgres on **host port 5434** and Redis on **host port 6380** (container port `6379`). The container itself listens on Postgres port `5432`. The example host `DATABASE_URL` is `postgresql+asyncpg://postgres:postgres@localhost:5434/field_shift`, and the host `REDIS_URL` is `redis://localhost:6380/0`; the API, Alembic, and local tools use those host URLs. Containerized backend services override them with `postgresql+asyncpg://postgres:postgres@postgres:5432/field_shift` and `redis://redis:6379/0`, which target the same services through Compose networking.

The default credentials and JWT value in `.env.example` are for local development only. Set a unique, randomly generated `JWT_SECRET_KEY` for any deployed environment. Configuration validation never prints secret values. It lists provider integrations that are not configured; those integrations are optional for local startup but their features need the corresponding settings.

## Migrations and database isolation

Run `alembic upgrade head` after starting the services and whenever new migrations are pulled. Check the current revision with `alembic current`; inspect available revisions with `alembic history`. Alembic reads `DATABASE_URL` through `config.settings`, so it targets the same instance as the app. Do not point the development API or migration command at production.

Tests must use a separate database, never the development database. Create it once in the Compose Postgres instance with `docker compose exec postgres psql -U postgres -c "CREATE DATABASE field_shift_test;"`, then set `TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5434/field_shift_test` for the test process. The integration fixture drops and recreates tables in that database. PowerShell: `$env:TEST_DATABASE_URL='postgresql+asyncpg://postgres:postgres@localhost:5434/field_shift_test'; python -m pytest tests/integration tests/end_to_end`. Unix: `TEST_DATABASE_URL='postgresql+asyncpg://postgres:postgres@localhost:5434/field_shift_test' python -m pytest tests/integration tests/end_to_end`. This setting is isolated from `DATABASE_URL`, which remains the development database for the API and Alembic.

## API and background workers

With the virtual environment active and `.env` configured, run the API as above. In separate terminals, start a Celery worker and scheduler when background jobs are needed:

```sh
celery -A app.workers.celery_app:celery_app worker --loglevel=info
celery -A app.workers.celery_app:celery_app beat --loglevel=info
```

PowerShell accepts the same Celery commands. Worker and beat both use `REDIS_URL`; run only one beat process per environment to avoid duplicate scheduled jobs.

Offline synchronization request/response fields, examples, conflict policy, transaction behavior, cursor paging, ID remapping, and recovery are documented in [docs/offline-sync.md](docs/offline-sync.md).

Soil-card upload/OCR review, private storage and malware scanning, weather units/cache freshness, sowing alert approval rules, notification preferences, retry/dead-letter behavior, and staging verification are documented in [docs/soil-weather.md](docs/soil-weather.md).

NASA AppEEARS/SMAP account setup, `.env` settings, on-demand sampling API, quality fields and provenance are documented in [docs/backend-integrations.md](docs/backend-integrations.md#nasa-smap-setup).

Frontend endpoint mapping, auth/session differences, automatic recommendation inputs, and provider-dependent feature gates are documented in [docs/frontend-backend-handoff.md](docs/frontend-backend-handoff.md).

The full method-by-method endpoint reference, with request/response contracts and workflow notes, is available as [Field Shift Backend API Reference](docs/FieldShift_Backend_API_Reference.pdf).

### Frontend integration quick start

With Docker running, the frontend should use `http://localhost:8000/api/v1` as its API base URL and `http://localhost:8000/docs` to inspect request/response schemas. Set `VITE_USE_MOCKS=false` and `VITE_API_BASE_URL=http://localhost:8000/api/v1` in the frontend environment to enable real API integration. Farmer-owned API requests must send `Authorization: Bearer <access_token>`; the current backend issues bearer tokens from `POST /auth/otp/verify`.

The frontend's current real auth adapter expects a cookie/CSRF session API (`/auth/otp/request`, `/auth/refresh`, `/auth/logout`, and `/me`) that this backend does not expose. It must be adapted to the backend's `/auth/otp/send`, `/auth/otp/verify`, and `/farmers/me` contract before real auth works. Likewise, update frontend market calls to `/market/prices` and `/market/prices/curve`; `/market/markets` and `/market/prices/{crop}/history` are not backend routes. Recommendations are requested from `POST /recommendations`; backend fills supported plot, soil, crop-history, and market inputs automatically. See the handoff guide for the full onboarding sequence, soil-test flow, payload examples, offline sync behavior, and provider gates.

## Health and configuration

- `GET /health/live` reports that the API process is running and does not contact dependencies.
- `GET /health/ready` checks PostgreSQL and Redis with a two-second bound per dependency; it returns `503` and per-service availability when either check fails.
- `python -m config.validate` validates settings and reports missing provider configuration without disclosing values. Invalid database URLs and production JWT secrets shorter than 32 characters fail validation.

## Authentication, privacy, and account lifecycle

Phone inputs follow one explicit rule: an unprefixed ten-digit Indian mobile number beginning with 6-9 is normalized to `+91`; any other country must use E.164 form (for example, `+14155552671`). OTPs use `OTP_PROVIDER=development` locally and are returned only in the send response as `development_otp`; the local provider is rejected outside development/test. Set `OTP_PROVIDER=sms` in production to deliver through the configured SMS gateway. OTPs expire, resends are cooldown limited, verification attempts are capped per phone, and sends are capped per source IP.

Access tokens expire after 15 minutes by default. Account deletion immediately records a Redis subject revocation timestamp, invalidating existing tokens; Redis is therefore required for authenticated requests. OTP verification after deletion clears that subject revocation so the verified owner can intentionally register again. `GET /api/v1/farmers/me/export` returns the profile and associated plots, crop records, soil tests, alerts, and sync history. `DELETE /api/v1/farmers/me` permanently deletes the account and cascades its owned data; the operation requires a valid bearer token.

## Plot, season, and crop history contract

- Plot coordinates use GeoJSON WGS84 with `[longitude, latitude]` ordering and SRID 4326. Points must use longitude `[-180, 180]` and latitude `[-90, 90]`. Polygons need closed rings with at least four positions and must pass PostGIS validity checks. Plot polygons are checked against the entered area with a 25% tolerance.
- `area_value` and `area_unit` preserve the value a user entered; `area_acres` stores its canonical conversion. Supported local units are acres (`acre`) and hectares (`hectare`), with `1 hectare = 2.4710538147 acres`. Existing clients may continue sending `area_acres`; responses include all three fields.
- `GET /api/v1/plots?limit=50&offset=0` returns a stable `{items,total,limit,offset}` page. Deleting a plot archives it, hiding it from normal plot/history operations while preserving its history. `POST /api/v1/plots/{id}/restore` restores it. Deleting a farmer permanently cascades its data.
- Crop history pages use the same `items/total/limit/offset` envelope. A plot can have multiple crops per season, but the same crop name can appear only once for the same plot and season. `PUT` and `DELETE /api/v1/plots/{plot_id}/history/{record_id}` support offline edits; plot ownership is checked on every operation.
- Manage seasons with `ADMIN_API_KEY` using `POST /api/v1/seasons`, `PUT /api/v1/seasons/{id}`, and `DELETE /api/v1/seasons/{id}`. Season deletion is blocked while crop history references it. Seed baseline district seasons with `PUT /api/v1/seasons/seed` using `X-Admin-Key` and `{"district":"Mysuru","year":2026}`; this idempotently creates Kharif, Rabi, and Zaid rows. `GET /api/v1/seasons?district=Mysuru&year=2026` lists seasons for history creation. Admin endpoints return `503` until an admin key is configured.
- Alembic revision `0004_phase1_data_contract` registers Group, InputDealer, and Warehouse tables plus the plot/history constraints and indexes. Migration parity is tested by `tests/integration/test_migrations.py`, which resets the disposable `TEST_DATABASE_URL`, applies the entire Alembic chain, and compares database tables and spatial indexes with SQLAlchemy metadata. Never use a development or production database as `TEST_DATABASE_URL`.

## Crop recommendations and agronomy data

The recommendation MVP returns at most **three** ranked options (`limit` defaults to 3 and cannot exceed 3). Scores are normalized to 0–100 and combine soil benefit (25%), pest-risk reduction (25%), net return (30%), and water/risk fit (20%). The response includes those component scores, explicit weights, cited rule/price identifiers, freshness, assumptions, confidence, preference matches, a benefit, and a trade-off. Missing or stale required inputs lower confidence and require a human-advisor referral; the system does not fill unknown values with estimates.

Net return is computed for the requested plot and season: `expected yield (kg/acre) × fresh market price (INR/kg) × plot acres − input cost + documented fertilizer savings + eligible subsidy`. Rule inputs store their source/date, currency and unit. Price matching requires the requested district, INR/kg, an identified source/version, and a report no more than 30 days old. Older, unmatched, or unit-ambiguous prices are excluded and trigger referral. Ingested prices with a recognized Rs/quintal unit are converted to INR/kg by dividing by 100; unknown source units stay unusable until explicitly normalized.

Crop knowledge uses the versioned `CropKnowledgeDataV1` schema. `scripts/import_crop_knowledge.py data/pilot/mysuru/phase0-v1.json` validates and previews a seed; append `--apply` after migrations to import it as **drafts**. Pilot scope is Mysuru, Kannada, and finger millet, field bean, and maize. The pilot records source metadata and display names only; it intentionally lacks enough reviewed yield, cost, water, and pest data to generate recommendations. Draft/sample rules are never treated as advice. A production rule must have a source/version, region/season scope, complete sourced assumptions, two distinct allowlisted agronomist approvals, and explicit admin activation.

Configure `ADMIN_API_KEY` and `AGRONOMIST_REVIEWER_KEYS` (a JSON object of reviewer IDs to distinct secrets) before using `/api/v1/admin/crop-rules`. Admins create and submit drafts; each reviewer calls `POST /{id}/reviews` with `X-Reviewer-ID` and `X-Reviewer-Key`; after two approvals an admin calls `POST /{id}/activate`. `GET /{id}/audit` shows the audit trail. `POST /{id}/rollback` deactivates the active rule and restores the prior reviewed version when available. Keep reviewer credentials separate; never put them in source control.

Each recommendation persists the request/plot/soil/history/price snapshot, exact rule versions and provenance, scorer/ruleset versions, and response. The owner may report planted crop, yield, and costs once at `/api/v1/recommendations/{recommendation_id}/outcome`. Market feed setup, MSP curation, price curves and conservative arrivals-based glut context are described in [`docs/market-pest.md`](docs/market-pest.md). Benchmark-based calibration remains deferred until 50–100 scenarios have two expert approvals and a project-approved threshold is supplied; see [`docs/recommendation-evaluation.md`](docs/recommendation-evaluation.md).

## Common local failures

Backend provider accounts, free-tier limits, credentials and access blockers are tracked in [`docs/backend-integrations.md`](docs/backend-integrations.md). Do not commit `.env` or send provider secrets in chat.

- **Host port 5432 or 5433 is occupied:** Compose publishes the container port `5432` on host port `5434`; use host port `5434` in `DATABASE_URL` and leave the container port unchanged.
- **Database connection refused:** run `docker compose ps` and `docker compose logs postgres`; wait for the health check, then rerun validation and migrations.
- **Host port 8000 is already in use:** do not run the Docker API and host `uvicorn` at the same time; stop one of them or change the published API port in Compose.
- **Admin route says administration is not configured:** set a non-empty `ADMIN_API_KEY` in the local `.env`, then recreate the API container so it reloads the setting. Use the same value in the `X-Admin-Key` header.
- **Redis connection refused or readiness 503:** run `docker compose ps` and `docker compose logs redis`; confirm `REDIS_URL=redis://localhost:6380/0` for a host process.
- **Migrations connect to an unexpected database:** inspect the active `DATABASE_URL` environment override and `.env`. Environment variables override `.env`; run `python -m config.validate` before `alembic upgrade head`.
- **PostGIS extension errors:** use the configured `postgis/postgis:16-3.5` image, not a plain PostgreSQL image.
- **Provider configuration warnings:** set the credentials for the provider feature you need. Missing optional provider configuration does not prevent local API startup.
