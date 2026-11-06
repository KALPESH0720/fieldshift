# Field Shift — Data Flow & Sync Map

**Reviewed:** 2026-10-31  
**Scope:** Current Dexie/IndexedDB operations, plot and registry UI flow, related local data, and external calls. This is a read-only code review; no application code was changed.

## Key findings

- The local database is `FieldShiftDB`, Dexie schema version 4, defined in `src/db/db.js:1-55`.
- The queue has two write sites: manual plot creation and crop-plan selection. There is no queue reader, network push/pull, retry worker, or Background Sync handler in the current source (`src/components/PlotList.jsx:276-283`; `src/components/Recommender.jsx:341-357`).
- `AgriStackConsentModal` is not used by the current route/component tree. The active `PlotList` flow uses `LandRegistryConsentModal`, whose registry provider functions are mocks (`src/components/PlotList.jsx:12,515-519`; `src/services/landRegistry/mockProviders.js:42-68`).
- `leaflet-geosearch` is a package dependency, but no source import or search-control call was found (`package.json:22`). The only application-level JavaScript `fetch` calls found are the Open-Meteo forecast and air-quality requests (`src/services/weather.js:4-5,60`). The Leaflet maps separately request Google map tiles (`src/components/FieldMapper.jsx:181-187`; `src/components/DashboardMap.jsx:85-91`).

## Data map

| Feature/Module | File Location | Operation/Method | Payload Structure | Status |
|---|---|---|---|---|
| Database/schema | `src/db/db.js:1-55` | `new Dexie('FieldShiftDB')`; `db.version(1..4).stores(...)` | `plots`: auto id, serverId, name, area, village, providerId, externalId; `cropRules`: id, cropFamily, duration, nitrogenEffect, waterNeed; `syncQueue`: auto id, action, status, timestamp; `soilRecords`: auto id, plotId, pH/N/P/K/timestamp; `weatherCache`: id, updatedAt. | Offline Dexie. `cropRules` has no current use site. The queue schema does not define a typed mutation contract. |
| Plot list/dashboard read | `src/components/PlotList.jsx:231,404-428` | `useLiveQuery(() => db.plots.toArray(), [])` | Returns all locally stored plot rows for the map and dashboard cards. | Offline Dexie read; no server read. |
| Draw boundary | `src/components/FieldMapper.jsx:147-202`; `src/components/PlotList.jsx:245-251` | Map click updates React `points`; `onConfirm({ area, unit, coordinates })` calls `handleMapData`. | `{ area: string, unit: string, coordinates: [[latitude, longitude], ...] }`. Area uses Turf, with a local fallback if Turf throws. No database write occurs in `FieldMapper`. | In-memory React state until form submission. |
| Add-plot form | `src/components/AddPlotModal.jsx:34-80` | `handleSubmit` calls the parent `onSubmit(...)`; component itself does not access Dexie. | `{ fieldName, area, areaUnit, primaryCrop, intercrop, coordinates }`. Coordinates are the selected boundary array. | Callback only; not persisted by this component. |
| Save manual plot | `src/components/PlotList.jsx:253-286` | `db.plots.add(plotToSave)` | Plot contains `name`, string `area`, `areaUnit`, `village`, `primaryCrop`, `intercrop`, `boundaryCoordinates`, `coordinates`, `mappedArea`, numeric `areaHectares`, `serverId: null`, `isVerified: false`, `source/providerId: 'manual'`, `externalId: null`, and `provenance`. | Offline Dexie. No API request. |
| Queue manual plot | `src/components/PlotList.jsx:276-283` | `db.syncQueue.add(...)` after the plot add | `{ action: 'CREATE_PLOT', payload: { ...plotToSave, localId }, status: 'pending', timestamp: Date.now() }`; Dexie assigns its own queue `id`. | Offline Dexie outbox. The plot and queue writes are sequential, not in one transaction; queue failure can leave a local plot without a queue item. |
| Queue crop-plan selection | `src/components/Recommender.jsx:334-357` | `db.syncQueue.add(...)` | `{ action: 'ASSIGN_PLOT_ROTATION', payload: { plotId, plotName, cropId, cropName, season, previousCrop, netReturn, fertilizerSavedKg, areaHectares, timestamp }, status: 'pending', timestamp }`. | Offline Dexie outbox. Recommendation itself is generated locally; no server acknowledgement. |
| AgriStack consent UI | `src/components/AgriStackConsentModal.jsx:9-27,95` | `handleAuthorize` invokes `onImport?.()` with no arguments. No `db.*` or `fetch` call. | Consent UI lists requested data in `REQUESTED_DATA`; optional parent callback is expected to do work. | UI only and no call site found. It does not perform AgriStack authorization or import data. |
| Active registry provider lookup | `src/components/LandRegistryConsentModal.jsx:10-24`; `src/services/landRegistry/registry.js:1-43` | Reads selected country and calls the provider passed to `onImport`. Country preference uses `localStorage`. | Country code selects a provider adapter; file may be passed for the generic provider. | Local provider selection; provider adapters are mocked, not registry APIs. |
| Mock parcel generation | `src/services/landRegistry/mockProviders.js:16-29,42-88` | `provider.fetchVerifiedParcels({ countryCode })` is an in-process JavaScript function, not HTTP `fetch`. It waits 1.2 seconds and creates three fixed-shape parcels. | Parcel fields include `id`, `parcelRef`, `countryCode`, GeoJSON `geometry`, `areaHa`, `landUse`, `cropDeclared`, `ownerStatus`, `source`, `isVerified`, `verifiedAt`, and `registryUrl`. | Mocked API behavior. `authMethod` is `mock`; URLs use `example.org`. |
| Deduplicate registry-shaped imports | `src/components/PlotList.jsx:296-319` | Reads `db.plots.toArray()`, compares provider/external keys, maps parcels into local plot records. | Converted plot includes `name`, area/hectares, crop, lat/lon coordinate arrays, survey number, provider/source, `isVerified: true`, verification timestamp, provenance, and `serverId: null`. | Local processing of mock data; the local verified flag is not proof of government validation. |
| Store registry-shaped plots | `src/components/PlotList.jsx:321-323` | `db.plots.bulkAdd(newPlots)` | Array of converted plot rows. | Offline Dexie write; does **not** add corresponding `syncQueue` items. |
| Generic land document | `src/components/PlotList.jsx:288-294`; `src/components/LandRegistryConsentModal.jsx:64-70` | Saves metadata with `localStorage.setItem('fieldshift-land-document', ...)`. | `{ name, size, status: 'document uploaded, pending review' }`. | Browser localStorage only. The selected document bytes are not uploaded or stored in IndexedDB. |
| Soil card record | `src/components/SoilImport.jsx:281-300` | `db.soilRecords.add(...)` | `{ plotId: null, ph, nitrogen, phosphorus, potassium, organicCarbon, ec, hasPhoto, timestamp }`. | Offline Dexie write with no queue item. OCR/sample values are not supplied by a backend. |
| Weather and air quality | `src/services/weather.js:3-5,40-72` | `fetch()` to `https://api.open-meteo.com/v1/forecast` and `https://air-quality-api.open-meteo.com/v1/air-quality`; then `db.weatherCache.put(...)`. | Coordinates plus forecast variables and AQI/PM variables; normalized result includes advisories, coordinates, and `fetchedAt`. Cache row is `{ id: 'dashboard-weather', updatedAt, data }`. | Live third-party API + offline Dexie cache. One cache key is shared across locations. |
| Map tiles / search | `src/components/FieldMapper.jsx:181-187`; `src/components/DashboardMap.jsx:85-91`; `package.json:22` | React Leaflet `<TileLayer>` requests Google tile URLs in the browser. `leaflet-geosearch` is installed but not imported or invoked. | Tile URL template contains `{x}`, `{y}`, `{z}`. No geosearch query payload exists in the current app. | External tile requests are active; GeoSearch integration is absent. |
| Dashboard market data | `src/components/PlotList.jsx:71-87,117-211`; `src/components/MarketInsights.jsx:23-110,257-269` | Reads in-memory constants; refresh waits on a timer. | Weekly/monthly arrays, price highs/lows, trend labels, and static market rows. | Mock data; no APMC/AGMARKNET request. |
| Startup notifications | `src/components/StartupNotifications.jsx:70-77,152-185`; `src/services/mockEngine.js:52-92` | Loads mock notification array and tracks one-time display in `sessionStorage`. | Fixed title/body/type/icon values; no API response or delivery receipt. | Mock array + browser session storage. |

## Current queue structure

Dexie schema versions 1–4 keep `syncQueue` indexed as `++id, action, status, timestamp` (`src/db/db.js:16,25,34,52`). The actual writers add `action`, arbitrary `payload`, `status: 'pending'`, and `timestamp` (`src/components/PlotList.jsx:277-282`; `src/components/Recommender.jsx:341-357`). There is no explicit entity type, client mutation/idempotency key, base server version, attempt count, retry time, device/account scope, or error/conflict record. Payloads are action-specific and currently unvalidated.

One consistency risk is visible in manual plot creation: `db.plots.add` completes before `db.syncQueue.add` starts. If the second operation fails, the UI can retain a plot that will never sync unless repaired. A Dexie transaction should write both rows together.

## What a real background sync worker needs

1. **Define the mutation envelope and migrate Dexie.** Add a stable `clientMutationId`, entity type/local id, operation, payload, base version, account/device scope, created time, status, attempts, next retry time, attachment references, and last error. Preserve legacy queue rows through a Dexie version migration.
2. **Write entity and queue item atomically.** Every offline mutation—plot create/edit/delete, crop-plan assignment, soil record, and supported import—should commit its local record and outbox item in one transaction. Do not queue read-only actions.
3. **Drain the outbox safely.** A sync service should select pending rows by timestamp, mark them in flight, send a bounded batch to an authenticated backend, and use `clientMutationId` for idempotency. Apply canonical server ids/versions on acknowledgement; persist validation errors and conflicts for user resolution.
4. **Pull remote changes.** After push, request changes using a cursor/version token; upsert remote records, preserve local pending edits, and represent remote deletion with tombstones. Scope cached records and queues to the signed-in account so shared-device account changes cannot mix data.
5. **Retry and trigger sync.** Use capped exponential backoff with jitter for transient failures, stop retrying permanent validation/auth errors until corrected, and expose pending/failed status. Trigger on reconnect and app foreground; add a service-worker Background Sync handler where the deployment/browser supports it, with foreground retry as fallback.
6. **Handle media separately.** Store a local attachment reference and upload large files via resumable/presigned upload when online; enqueue metadata processing after upload succeeds. Do not put large image blobs inside ordinary JSON mutation batches.

## Later backend connections

- `CREATE_PLOT` and `ASSIGN_PLOT_ROTATION` should map to authenticated plot and season-plan endpoints, with server-generated IDs and versions.
- Registry import should use an authorized consent/callback flow. Until then, mock results should remain explicitly labeled demo and unverified.
- Soil records and image/OCR results need file upload and record endpoints; current local record writes do not sync.
- Weather can remain a third-party request or move behind a backend proxy; use per-plot/geohash cache keys and preserve source/fetched time.
- Market, alert, and notification fixtures need stable source, units, timestamps, and server ownership before users rely on them.

