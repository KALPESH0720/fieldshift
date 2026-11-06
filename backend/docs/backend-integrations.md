# Backend external integrations and onboarding

This is the backend integration inventory for the V2 plan. It excludes frontend work and CI/CD. It distinguishes service adapters that already exist from actual provider connections: provider environment variables are empty in the current local `.env`, so the adapters cannot reach real accounts yet. Never put credentials in source control or send them in chat; enter them in the local `.env` or the deployment secret manager.

## Backend runtime dependencies

PostgreSQL/PostGIS and Redis are required and already run as local Compose services. The API and Celery worker/beat must use the same database and Redis configuration. `httpx` handles HTTP providers, Celery handles jobs, `boto3` handles S3-compatible private object storage, and `asyncpg` connects to PostgreSQL. `boto3` is declared in `pyproject.toml`; reinstall/sync the project environment if it is missing from the current venv.

ClamAV is an external local service, not an account-based vendor. Soil uploads intentionally fail closed if it is unavailable. The storage adapter supports S3-compatible APIs. For a hosted low-volume option, Cloudflare R2 currently includes a free monthly allowance of 10 GB-month storage, 1 million Class A and 10 million Class B requests, with no egress charge; usage beyond the allowance is billable. Create a private bucket and S3 API token, then set `OBJECT_STORAGE_ENDPOINT_URL`, `OBJECT_STORAGE_REGION`, `OBJECT_STORAGE_BUCKET`, `OBJECT_STORAGE_ACCESS_KEY_ID`, `OBJECT_STORAGE_SECRET_ACCESS_KEY`, and `OBJECT_STORAGE_SECURE`. Do not expose public bucket URLs. R2 pricing: <https://developers.cloudflare.com/r2/pricing/>.

## Provider choices and setup needed

| Backend feature | Recommended production path | Setup you must complete | Environment / code state |
|---|---|---|---|
| Daily mandi price and history | Ministry of Agriculture's AGMARKNET feed published in India's OGD portal | Register/log in on data.gov.in, generate an OGD API key, confirm the dataset/resource ID and applicable use terms | Worker uses OGD resource path and paged JSON feed (`AGMARKNET_API_URL`, `AGMARKNET_RESOURCE_ID`, `AGMARKNET_API_KEY`); sample base template is in `.env.example`. The key is sent as the provider-required `api-key` query parameter and never logged. |
| Numeric plot forecasts | Open-Meteo for the approved non-commercial pilot | No key/signup; include required CC BY attribution in client/product attribution | `WEATHER_PROVIDER=open_meteo` is the default. The adapter requests current conditions, seven-day hourly agricultural weather/soil variables, and daily summaries, keyed by rounded plot coordinates. Free API use is non-commercial only and subject to published limits; obtain a commercial plan or replace the provider before commercial operation. It does not generate crop sowing windows or agronomic conclusions. |
| SMS OTP/reminders | An India SMS provider account that supports transactional/service SMS and TRAI DLT | Choose your SMS gateway, register the Principal Entity, sender header and message templates with the relevant telecom/provider, and obtain an API credential | Current gateway adapter accepts a provider-specific configured endpoint/key. `SMS_GATEWAY_URL`, `SMS_GATEWAY_API_KEY`, `SMS_SENDER_ID` are empty. No legitimate free production SMS route is assumed. TRAI requirements: <https://trai.gov.in/advice-to-senders>. |
| WhatsApp alerts | Meta WhatsApp Business Cloud API directly | Create a Meta developer app/business portfolio and WhatsApp Business Account, configure a sender, create approved templates, and issue a production system-user token | Current adapter is a generic gateway contract, not a direct Meta Graph API adapter. If chosen, implement the Meta-specific payload, token handling, webhook delivery receipts and template contract before sending. WhatsApp charges vary by recipient country and message category. Setup: <https://developers.facebook.com/docs/whatsapp/cloud-api/get-started/>; pricing: <https://whatsappbusiness.com/products/platform-pricing/>. |
| Soil card OCR | Self-hosted PaddleOCR in the backend worker, with human review retained | No vendor account or external image transfer; provision worker CPU/RAM/disk for model downloads and inference | Current code expects a remote OCR endpoint and key (`SOIL_CARD_OCR_URL`, `SOIL_CARD_OCR_API_KEY`). Replace that adapter with a worker-local implementation before treating the feature as connected. PaddleOCR is Apache-2.0 and supports 100+ languages: <https://github.com/PaddlePaddle/PaddleOCR>. OCR extraction is never accepted as measured data without farmer review. Tesseract is a smaller Apache-2.0 alternative for simpler typed cards, but is less capable at document layout: <https://github.com/tesseract-ocr/tesseract>. |
| Speech/translation | BHASHINI, as named in the V2 plan; only under granted access/usage terms | Create a BHASHINI onboarding account and generate a ULCA API key; obtain its user ID and pipeline ID. Service IDs can be resolved from the pipeline configuration response | Backend proxy now follows the documented config call (`userID`/`ulcaApiKey`) then uses the returned compute URL, auth header and service ID. Set `BHASHINI_USER_ID`, `BHASHINI_API_KEY` (ULCA key), `BHASHINI_PIPELINE_ID`, and config URL; terms: <https://bhashini.gov.in/gyankosh?tab=terms-of-use>. |
| Soil card image storage | Private S3-compatible storage (R2 is one option) plus ClamAV | Create the private bucket/token and run ClamAV in the backend environment | S3 adapter is present; `boto3` must be installed from declared dependencies. Bucket credentials and `CLAMAV_HOST` are empty. |
| NASA SMAP soil-moisture signal | NASA AppEEARS point sampling with Earthdata Login; current product is `SPL3SMP_E.006` (daily, 9 km) | Create a free Earthdata Login, sign in to AppEEARS once to authorize the app, and configure the username/password in the deployment secret store | Product-specific adapter, async job API, Celery worker, owner-scoped persistence, AM/PM retrieval-quality fields, and migration are implemented. No separate NASA developer API key is required. The current local `.env` credentials are blank until supplied by the owner. NASA product: <https://nsidc.org/data/spl3smp_e/versions/6>; AppEEARS: <https://appeears.earthdatacloud.nasa.gov/>. |
| Sentinel-2 vegetation/stress signal | Copernicus Data Space Ecosystem (CDSE) open data and documented APIs; prefer it over a trial-only commercial processor for a free path | Register and verify a CDSE user account; review API quotas and terms | Current adapter targets Sentinel Hub OAuth/Process API, not CDSE. `SENTINEL2_PROCESS_URL`, `SENTINEL2_CLIENT_ID`, `SENTINEL2_CLIENT_SECRET` are empty. Phase 4: <https://documentation.dataspace.copernicus.eu/Registration.html> and <https://documentation.dataspace.copernicus.eu/APIs.html>. |
| AgriStack plot prefill | API Setu/AgriStack only after official provider authorization and farmer consent | Apply with a valid organizational use case and required organization evidence; subscribe and obtain provider approval | Current adapter is only a consent-token client skeleton. `AGRISTACK_*` values are empty. API Setu's SOP states signup/use-case review and provider subscription approval: <https://partners.apisetu.gov.in/signup> and <https://cdn.apisetu.gov.in/portal/assets/SOP-APISETU.pdf>. Phase 3. |
| Pest photo diagnosis | No external diagnosis provider selected | Do not register/upload farmer photos to a generic vision API. Select a vetted agronomy provider and approved confidence/review protocol first, if photo diagnosis is required | Not connected by design. Backend stores reviewed knowledge and should refer low-confidence cases to an advisor. |
| Buyer/FPO listings | Curated/partner-supplied data with moderation and explicit source terms | Identify a data-owning FPO/buyer partner and agree update, verification, and moderation responsibilities | No open, authoritative buyer API selected. Keep this unconnected until a licensed source is approved. |

## Recommended onboarding order

1. The selected pilot is non-commercial research. Open-Meteo supplies numerical plot forecasts; use the API response attribution label/link in the consuming product and re-evaluate provider terms before commercial operation.
2. Provision the OGD/AGMARKNET key. IMD is intentionally skipped; the weather API currently uses Open-Meteo only. Keep stale/unmatched data as an explicit unavailable state.
3. Pick an India transactional SMS gateway and complete the sender/header/template registration. In parallel, create a Meta developer app and test WABA for WhatsApp; production sending still requires approved sender/template assets and may incur message charges.
4. Create a private R2 (or existing AWS S3) bucket and API token; provide a ClamAV service endpoint for the worker environment.
5. Confirm the OCR deployment budget. The recommendation is worker-local PaddleOCR to keep sensitive soil-card images within the backend; no OCR account is needed.
6. Add the Earthdata Login settings described below to activate on-demand SMAP sampling. Schedule broader Earthdata/CDSE integration only when the Phase 4 satellite feature is approved. Start AgriStack only after API Setu and provider approval.

## What to provide back to continue

Do not paste secrets into this chat. Add approved values to your local `.env` (or deployment secret manager), then tell me which provider profiles/accounts are ready and which environment variable names are populated. For the SMS and WhatsApp choices, tell me the provider names first; I can then implement their exact backend request/receipt/webhook contracts and test with a controlled recipient. For AgriStack, provide its approved technical spec only after authorization.

## NASA SMAP setup

This backend uses NASA's AppEEARS point-sampling API for the current `SPL3SMP_E.006` SMAP Enhanced L3 Radiometer product. It returns daily AM/PM surface soil-moisture estimates and retrieval quality flags at a 9 km grid scale. Celery runs the extraction because NASA processes each sample asynchronously. Point plots use their coordinate; polygon plots use a point on the plot surface. This is satellite context for the representative plot point, not a field-level lab measurement; it does not replace a plot's Soil Health Card.

1. Create a free account at [NASA Earthdata Login](https://urs.earthdata.nasa.gov/).
2. Sign in to [AppEEARS](https://appeears.earthdatacloud.nasa.gov/) with that account and approve the AppEEARS application authorization when prompted. No separate `api.nasa.gov` key is used by this integration.
3. In the repository's ignored local `.env` (or your deployment secret store), set:

   ```dotenv
   NASA_APPEEARS_API_URL=https://appeears.earthdatacloud.nasa.gov/api/
   NASA_EARTHDATA_USERNAME=your-earthdata-login-username
   NASA_EARTHDATA_PASSWORD=your-earthdata-login-password
   NASA_SMAP_PRODUCT=SPL3SMP_E.006
   NASA_SMAP_MAX_RANGE_DAYS=90
   NASA_SMAP_POLL_INTERVAL_SECONDS=5
   NASA_SMAP_MAX_WAIT_SECONDS=900
   ```

4. Keep the password out of source control. Run `python -m config.validate` and `alembic upgrade head`, then restart the API and Celery worker so the migration and credentials are loaded.
5. Submit an authenticated request to `POST /api/v1/satellite/plots/{plot_id}/smap/soil-moisture` with `{"start_date":"2026-10-01","end_date":"2026-10-07"}`. Poll `GET /api/v1/satellite/smap/jobs/{job_id}` until `status` is `completed`; the response contains daily observations, AM/PM retrieval values, quality flags, product DOI, and unit.

The date range is limited to 90 days by default and future dates are rejected. Quote the password in `.env` if it contains whitespace or `#`. SMAP is not an instantaneous feed; recent days may be absent. The selected product reports volumetric moisture (`m³/m³`), and retrieval flags must be checked before interpretation. Cite [NSIDC's SPL3SMP_E Version 6 product](https://nsidc.org/data/spl3smp_e/versions/6), DOI `10.5067/M20OXIZHY3RJ`, when using these observations. Product access and variables are documented by [NSIDC](https://nsidc.org/data/user-resources/help-center/what-data-subsetting-reformatting-and-reprojection-services-are-available-smap-data) and [NASA AppEEARS](https://appeears.earthdatacloud.nasa.gov/api/).
