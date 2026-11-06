# Market and pest context

## Market feeds and MSP

Configure `AGMARKNET_API_URL`, `AGMARKNET_RESOURCE_ID`, and `AGMARKNET_API_KEY` in the worker/API environment. The feed key is sent only to the configured provider; it is never written to ingestion logs or response DTOs. Confirm the feed's terms and API-key scope before enabling scheduled ingestion. `AGMARKNET_PAGE_SIZE` and `AGMARKNET_MAX_PAGES` bound each daily backfill run. Celery Beat runs the feed at 02:30 Asia/Kolkata; operators can inspect task failures and safely retry because feed rows are keyed by source, feed version, state, district, mandi, commodity, date, variety, and grade. Re-import updates the matching row and refreshes fetched time. Invalid rows are skipped and summarized without echoing source payloads.

The OGD resource request uses `GET /resource/{AGMARKNET_RESOURCE_ID}?api-key=…&format=json&limit=…&offset=…`. It consumes the lowercase `records` shape (`state`, `district`, `market`, `commodity`, `variety`, `grade`, `arrival_date`, `min_price`, `max_price`, `modal_price`) shown in the OGD sample. State, variety, grade, and the min/max price range are persisted and returned by market history. Reported min/max prices are retained as received; normalized min/max are populated only when a source unit is known. The sample record schema contains no unit field, so leave `AGMARKNET_DEFAULT_PRICE_UNIT` empty unless the feed's unit has been confirmed. If configured, source prices are normalized alongside modal price; unknown units remain `unit_unverified` and recommendations use only verified INR/kg rows for an exact district/crop match no more than 30 days old. `GET /api/v1/market/prices` returns authenticated, paginated history with freshness. `GET /api/v1/market/prices/curve` returns up to 180 days of sourced points.

`POST /api/v1/market/admin/ingest` is an admin-key protected manual ingestion trigger. MSP is a separate table because it has a crop, marketing season/year, effective period, official source and source version. Admins upsert records at `PUT /api/v1/market/admin/msp`; clients read `/api/v1/market/msp?crop=...`. MSP is contextual reference and is not substituted for mandi modal price in net-return scoring.

The glut context is deliberately conservative. It is unavailable until there are at least 60 distinct daily price observations and 30 distinct sourced arrival observations. Once available, the explicitly high-uncertainty heuristic flags elevated risk only when the recent 7-day average arrivals exceed the preceding 90-day average by 25% and the 7-day price average is below 90% of its prior 30-day average. It is a market signal, not a crop yield or price forecast; source and observation counts are returned.

## Reviewed pest and host knowledge

Admins create a draft with `POST /api/v1/market/admin/pest-rules`, including target crop, pest, host crops/families, effective region/season, version, risk contribution, and a source URL/version. Two distinct agronomists from `AGRONOMIST_REVIEWER_KEYS` must approve it using the existing reviewer headers on `POST /api/v1/market/admin/pest-rules/{id}/approve`; only then does it become active. New versions should be created rather than editing released knowledge. There is no pest-photo diagnosis endpoint because a reviewed diagnosis provider and confidence policy are not configured.

Recommendation lookup requires exact effective region and season (or `all`) and active reviewed records. Returned source IDs/citations and pest score metrics identify these records. Matching host crops/families in plot history add the record's risk points; family-continuity fallback remains only for existing crop-rule fields while reviewed regional pest data is absent. No uncertain image result is promoted to a diagnosis.

## Operational limitations

The APIs do not provide buyer/FPO listings. Add those only after source licensing and moderation requirements are established. Monitor Celery task failure/retry counts, skipped/updated/inserted rows, stale-price availability, and ingestion lag. Provider staging verification is not run against live keys by local tests.
