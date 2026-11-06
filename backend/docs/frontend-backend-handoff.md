# Frontend to Backend Handoff

This document is the integration contract for the frontend engineer. The backend is served under `/api/v1`; OpenAPI is at `/docs` when the stack is running. All farmer-owned endpoints below require `Authorization: Bearer <access_token>`. Use the exact snake_case JSON property names shown by OpenAPI.

## Current integration status

The frontend currently defaults to mock mode (`VITE_USE_MOCKS=true`). Its real auth adapter and market service do not yet match this backend's paths or payloads. Before end-to-end integration, configure `VITE_USE_MOCKS=false`, set `VITE_API_BASE_URL` to the API base URL (for local Docker, `http://localhost:8000/api/v1`), and update frontend API calls to the contracts below. No frontend files were changed as part of this backend handoff.

Specific mismatches to account for:

- Backend OTP uses `POST /auth/otp/send` with `{ "phone": "+91..." }`, then `POST /auth/otp/verify` with `{ "phone": "+91...", "otp": "123456" }`. Verification returns a bearer token. The current frontend real adapter instead calls `/auth/otp/request`, expects a challenge ID and cookie/CSRF session, and calls `/me`; those endpoints and cookie session flow are not implemented.
- Backend farmer profile is `/farmers/me` and uses `name`, `language`, and `village`; the frontend currently sends `displayName`, `preferredLocale`, `countryCode`, and `consents`.
- Backend market reads are `/market/prices?crop=...&district=...` and `/market/prices/curve?...`; the frontend service currently requests `/market/markets` and `/market/prices/{crop}/history`.
- Recommendation inputs are submitted to `POST /recommendations`; the existing browser recommender is local and must call this API when real mode is enabled.
- Plot, soil, weather, and sync backend routes exist. The frontend needs to replace local Dexie-only reads/writes with API-backed calls and queue offline mutations for `/sync`.

## Recommended onboarding sequence

1. `POST /auth/otp/send` with phone. In development, the response includes `development_otp`; in production the code is sent through the configured SMS provider and is never returned.
2. `POST /auth/otp/verify` with phone and code. Save `access_token` securely in the app's auth state and send it as a bearer token on subsequent API requests. Do not persist the token in localStorage.
3. `GET /farmers/me`. A `404` means the phone is authenticated but has no profile yet. Create it with `POST /farmers/me`.
4. Seed/list seasons for the farmer's district: an administrator runs `PUT /seasons/seed` with `X-Admin-Key`; the client reads `GET /seasons?district=...&year=...`.
5. Create plots with `POST /plots`. Plot geometry is GeoJSON WGS84; coordinate order is `[longitude, latitude]`. Send `area_value` plus `area_unit` (`acre` or `hectare`), or send canonical `area_acres`.
6. Load plot history and soil data from `GET /plots/{plot_id}/history` and `GET /plots/{plot_id}/soil-tests`.

## Farmer and plot APIs

| Method | Path | Purpose |
|---|---|---|
| GET, POST, PUT, PATCH | `/farmers/me` | Read, create, or update the authenticated farmer profile |
| GET | `/farmers/me/export` | Export the farmer's owned backend data |
| DELETE | `/farmers/me` | Permanently delete the account and its owned records |
| GET | `/plots?limit=50&offset=0` | Paginated active plot list |
| POST | `/plots` | Create a plot |
| GET, PUT, PATCH, DELETE | `/plots/{plot_id}` | Read, update, or archive a plot |
| POST | `/plots/{plot_id}/restore` | Restore an archived plot |
| GET, POST | `/plots/{plot_id}/history` | Read paginated crop history or add an entry |
| PUT, DELETE | `/plots/{plot_id}/history/{record_id}` | Edit or remove crop history |
| GET | `/seasons?district=...&year=...` | List seasons used by crop-history records |

Paginated list responses use `{ "items": [], "total": 0, "limit": 50, "offset": 0 }`. Plot deletion archives the record; farmer deletion removes owned records.

## Soil test flow

Manual or lab data is saved through `POST /plots/{plot_id}/soil-tests`. Provide any measured value among `n_val`, `p_val`, `k_val`, `ph`, `organic_matter`, or `soil_type`, plus `tested_at` (timezone-aware ISO timestamp), units, and provenance as applicable. The backend treats a farmer-submitted record as reviewed/approved. `GET /plots/{plot_id}/soil-tests` returning an empty `items` array with `total: 0` means no test has been saved; it is not an API failure.

For a card photo, send the raw image bytes to `POST /plots/{plot_id}/soil-card-uploads` with its image `Content-Type`. Poll `GET /soil-card-uploads/{upload_id}` until OCR completes. Review the extracted fields with `POST /soil-card-uploads/{upload_id}/review`; low-confidence values must be explicitly corrected. Photo OCR requires object storage, ClamAV, and OCR provider settings. Without them, use the manual soil-test path.

## Recommendation flow and automatic inputs

Call `POST /recommendations` with the selected `plot_id` and `season`. Backend-owned inputs are assembled automatically: plot boundary/area, irrigation, latest approved soil test, recent crop history, current location-matched market price, MSP context, and active approved crop rules. The client should not ask the farmer to re-enter those values. Optional `farmer_preferences` can contain `low_water`, `early_cash`, `soil_health`, or `high_return`; `limit` is 1–3.

Example:

```json
{
  "plot_id": 12,
  "season": "Kharif-2026",
  "farmer_preferences": ["low_water", "soil_health"],
  "limit": 3
}
```

The response includes `recommendation_id`, ranked `options`, score components, assumptions, freshness, confidence, `missing_inputs`, and advisor-referral flags. A run is persisted and can be fetched again at `GET /recommendations/{recommendation_id}`. If `engine_status` is `fast` and an `engine_job_id` exists, poll `GET /recommendations/{recommendation_id}/job`; use `POST /recommendations/{recommendation_id}/rescore` for changed preference weights/flags. A farmer can submit planting/outcome data once at `POST /recommendations/{recommendation_id}/outcome`.

The engine currently does not accept every legacy optional recommendation field (for example, user-supplied available water and sowing-window days). Those are not required for the standard autofill path. Rainfall context comes from the engine's location layers; the backend does not fabricate missing measurements. If no approved crop rules or suitable current prices exist, the correct result may contain no options and request advisor review. Production agronomic recommendations require reviewed active rules and configured data providers.

## Weather, alerts, and market

| Method | Path | Purpose |
|---|---|---|
| GET | `/weather/plots/{plot_id}/forecast` | Fresh/cached forecast for an owned plot |
| GET | `/weather/plots/{plot_id}/snapshots` | Forecast history |
| GET, PUT | `/weather/preferences` | Notification preferences |
| GET | `/weather/alerts` | Farmer alert inbox |
| GET | `/market/prices?crop=...&district=...` | Price history and freshness |
| GET | `/market/prices/curve?crop=...&district=...` | Aggregated price curve |
| GET | `/market/msp?crop=...` | Minimum support price context |

Market prices are only useful when a feed has been configured and ingested. Do not substitute browser mock prices for API results while real mode is enabled. Provider attribution/freshness should be shown with the data.

## Offline sync

Use `POST /sync` with the versioned payload described in [offline-sync.md](offline-sync.md). Send stable operation IDs and the device ID so retries are idempotent. Apply returned ID mappings and conflicts to the local cache; do not silently discard server conflicts. The sync route is the write path for queued offline changes, while online flows may use the entity endpoints directly.

## Operational and feature gates

- Start backend from the `backend/` directory with `docker compose --profile backend up --build -d`; readiness is `GET /health/ready`, API docs are `/docs`.
- Local auth defaults to the development OTP provider. Production requires SMS configuration, strong secrets, and managed infrastructure.
- Soil-card OCR requires the configured object store, malware scanner, and OCR integration. Manual soil entry remains available without those providers.
- Weather requires outbound access to Open-Meteo. Market prices require configured ingestion/source data. Crop recommendations require the separately running suggestion engine, its API key, active reviewed crop rules, and usable location-matched prices.
- This repository does not currently implement the frontend's cookie/CSRF session interface, AgriStack consent/prefill callback lifecycle, pest-photo diagnosis, or complete FPO membership workflows. These require agreed contracts/product rules before they can be represented as complete backend features.
