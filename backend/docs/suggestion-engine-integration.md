# Suggestion engine integration

The backend is the authenticated facade for the standalone suggestion engine. Farmer clients call only `/api/v1/recommendations`; the backend verifies plot ownership, derives a plot point and approved context from PostgreSQL, calls the engine with its service key, normalizes the response, and stores both the public response and raw engine response for audit.

## Backend routes

| Route | Purpose |
| --- | --- |
| `POST /api/v1/recommendations` | Build engine inputs from the owned plot, crop history, approved soil tests, reviewed crop costs, fresh market prices, and MSP; request suggestions and persist the result. |
| `GET /api/v1/recommendations/{id}` | Retrieve a farmer-owned persisted response. |
| `GET /api/v1/recommendations/{id}/job` | Poll only the refinement job attached to that farmer-owned recommendation. When the engine job is done, request the refined response and persist it. |
| `POST /api/v1/recommendations/{id}/rescore` | Re-rank a prior engine request with optional weights and flags. |
| `GET /api/v1/recommendations/plots/{plot_id}/alerts` | Retrieve monitor alerts for the owned plot's snapped cell. |
| `POST /api/v1/recommendations/{id}/outcome` | Save the outcome in PostgreSQL and forward a pseudonymous action record to the engine. The response includes `engine_log_synced`. |

Engine-only pipeline routes `/v1/indicators` and `/v1/optimize` are not exposed as farmer endpoints: indicators are posted by the engine's batch worker, and optimizer currently returns HTTP 501. Before deleting a farmer account, the backend calls the engine's `/v1/actions/{plot_id}` deletion route for plots with suggestion history.

## Configuration

Set `SUGGESTION_ENGINE_URL` and `SUGGESTION_ENGINE_API_KEY` in `backend/.env`. The key must match `FIELDSHIFT_API_KEY` in the engine deployment. Production requires an engine URL and a key of at least 32 characters. Requests have a configurable `SUGGESTION_ENGINE_TIMEOUT_SECONDS` timeout. The backend reports a clear 503 when the engine is not configured/unavailable, 504 on timeout, and 502 when the engine fails or returns malformed data; it never falls back to the retired in-backend recommendation implementation.

The `backend/docker-compose.yml` backend profile builds the existing engine Dockerfile and starts one engine instance before the backend API. Copy `.env.example` to `.env` and set a shared random key before running Compose. The standalone engine uses an in-memory store, so keep one instance until its store is made shared/persistent.

## Input mapping and constraints

- Point plots use their point. Polygon plots use `ST_PointOnSurface` so the suggestion cell is sampled from within the field.
- Crop history is translated to the engine's `{season: "kharif-2026", crop: "pigeonpea"}` shape. Names are normalized to lowercase crop identifiers.
- The backend uses approved soil tests for pH/texture and reviewed/active crop records for supplementary price/cost inputs. The standalone engine applies its own packaged crop rules and knowledge; those are not replaced by the backend rule table. Soil organic matter is not relabeled as organic carbon.
- Verified market prices are restricted to 30 days and converted to INR/quintal. MSP is used only when there is no fresh market value for that crop.
- Engine returns are per acre; the backend scales them by the plot's stored acreage.
- The engine's committed knowledge currently covers Kharif and Rabi only. Zaid is translated to `summer`, but the stock engine season cycle and crop catalogue do not contain summer crops. Until engine knowledge is extended and reviewed, Zaid requests will not produce valid recommendations. Do not relabel another season to make them pass.
- The standalone request contract has no fields for live rainfall/forecast, remaining sowing-window days, available plot water, or a preferred-crop list. Its climate and sowing signals come from its configured cell layers; these backend request values cannot affect a recommendation until the standalone contract supports them.

## Readiness and data quality

The backend passes through the engine's confidence, notes, missing inputs, and human-review flag as data-quality notes and advisor referral. It also forces advisor referral for `KNOWLEDGE_NOT_REVIEWED` and `SYNTHETIC_CELL_DATA`. The engine README identifies its crop knowledge as illustrative and warns that synthetic cell fixtures are invented data. A successful API response therefore does not imply production approval of the engine knowledge or pilot data.
