# Field Shift — Code-Level Feature & Plan Audit (`FEATURE_STATUS.md`)

**Audit Date:** 2026-11-02  
**Audited Workspace:** `frontend/` (React 19.3 + Vite 8.3 + Tailwind CSS 4.3 + Framer Motion + Recharts + Leaflet + Dexie IndexedDB + `vite-plugin-pwa`)  
**Methodology:** Conservative static + build-output audit. Every route, component, service, hook, IndexedDB table, locale bundle (`818` keys × `110` locales), API adapter (`src/api/*`), and production build artifact (`dist/`, `dist/sw.js`) was inspected directly. No source code was modified.

## Status Scale

| Score | Label | Definition |
| :---: | :--- | :--- |
| **3** | **REAL** | Works end to end with real logic or real data (external API, device capability, or persisted data), usable offline where the plan requires it. |
| **2** | **PROTOTYPE** | Working UI plus working local logic, but data or intelligence is simulated or hardcoded (mock delay, fixed sample data, rules without sources), or key plan requirements are missing. |
| **1** | **UI ONLY** | Screen or button exists but does nothing meaningful (no persistence, no logic, placeholder/static handlers). |
| **0** | **NOT STARTED** | Nothing found in codebase. |

---

## 1. Summary Section

### 1.1 Master Status Table (Features 1–18 + Plan Items A–F)

| # | Feature / Plan Item | Status (0–3) | One-Line Audit Note |
| :---: | :--- | :---: | :--- |
| **1** | Voice & local-language UI | **2** | Real Web Speech TTS (`useVoice.js`) and 818 native Marathi/Hindi/English keys work offline on all 9 farmer routes, but Marathi (`#17`) and Hindi (`#4`) are not first in the picker (defaults to English) and 4 screens (`FieldMapper`, `GroupDashboard`, `LandingPage`, `NotFound`) + `InstallPrompt` are hardcoded English with no `ListenButton`. |
| **2** | Rotation recommender | **2** | Working plot/season/previous-crop form and offline family/legume/root-depth ranking, but covers only 9 hardcoded crops (`CROP_RULES`) behind a `4.8 s` `setTimeout` animation, ignores soil/weather/market tables, and lacks minimum-gap rules and trade-off sentences. |
| **3** | Profit comparison & fertilizer calculator | **1** | Read-only metric boxes inside Recommender scale hardcoded per-hectare constants by plot area; zero editable inputs, no `yield × price − cost` formula, fixed `0.84` baseline (`+19%` on every crop), and hardcoded `65%`/`35%` bar widths. |
| **4** | Plot-wise history | **2** | Persists plots in Dexie `db.plots` with Leaflet polygon drawing (`@turf/area`) and 6 live-converted area units, but stores only one current crop with zero multi-season timeline and zero history-based conflict flagging. |
| **5** | Offline mode | **2** | Installable Workbox PWA (`dist/sw.js`) with Dexie caches and on-device `rotationEngine.js`, but `db.syncQueue` is strictly write-only (no sync worker, API drain, or conflict handling) and `db.cropRules` is unused. |
| **6** | SMS/WhatsApp reminders | **1** | Four toggles in `Settings.jsx` live only in ephemeral React `useState` (not persisted to `localStorage` or Dexie — resets on navigation despite displaying `"Preferences saved"`), with no scheduler or SMS/WhatsApp gateway. |
| **7** | Soil data import | **2** | Manual NPK/pH/OC/EC form saves to Dexie `db.soilRecords` offline, but photo `"Auto-OCR"` is a `1.8 s` `setTimeout` returning hardcoded `LATERITE_PROFILE`, `plotId` is always `null`, saved records have no viewer, and the recommender ignores `db.soilRecords`. |
| **8** | Weather & sowing alerts | **2** | `WeatherPanel` fetches real live Open-Meteo Forecast & Air Quality APIs by plot centroid/GPS with Dexie offline fallback and 3 threshold advisories, but dashboard alert banners are hardcoded text, sowing-window view is missing, and alerts never shorten or swap crops. |
| **9** | Pest & disease context | **1** | Leaf upload runs a `2.2 s` `setTimeout` laser overlay ignoring image pixels and alternates between 2 hardcoded results (`leaf-blight`, `powdery-mildew`) with no persistence, risk tags, knowledge base, or crop-family carry-over rules. |
| **10** | Market links & glut forecast | **2** | Working mandi explorer, historical/seasonal charts, rule-based sell/hold guidance, and persisted `db.priceAlerts`, but default `USE_MOCKS=true` synthesizes sine-wave prices and buyer listings, glut-avoidance modeling, and recommender profit integration are absent. |
| **11** | Intercropping & cover crops | **1** | `AddPlotModal` saves an optional `intercrop` ID to `db.plots`, but plot cards do not render it and zero companion/cover-crop combination rules or benefit scores exist. |
| **12** | FPO and group view | **1** | Role-gated `/group` screen (`GroupDashboard.jsx`) renders static hardcoded English JSX (`42` farmers, `115 Acres`, 5 sample rows) with zero aggregation logic, persistence, or multi-group permission model. |
| **13** | AgriStack integration | **2** | Country-aware `LandRegistryConsentModal` imports and deduplicates 3 polygon parcels into `db.plots` (prefilling map and recommender), but `fetchVerifiedParcels()` is a `1.2 s` `setTimeout` returning hardcoded Goa polygons with no real AgriStack connector. |
| **14** | Contingency sowing gates | **1** | Dismissible `CatchCropAlert` displays a hardcoded 18-day monsoon delay warning on every `/farm` load and navigates to `/recommender` without delay parameters, threshold monitoring, or recalculated short-duration risk. |
| **15** | Input dealer registry | **1** | Searchable list of 3 hardcoded Goa dealers in `DealerDirectory.jsx` (all sharing placeholder `tel:+919876543210` and a generic Google Maps query), with no district inventory data and no recommender score penalty when certified seed is unavailable. |
| **16** | Mid-season satellite alarms | **1** | `VoiceAdvisory.jsx` speaks one static translated stress script via Web Speech TTS; zero Sentinel-2, NASA SMAP, NDVI, or satellite moisture data or anomaly pipeline exists in the codebase. |
| **17** | Subsidy & PMFBY matcher | **1** | `SchemesHub.jsx` displays 3 hardcoded cards (PM-KISAN, PMFBY, PKVY) whose `"Check Eligibility"` / `"Apply Now"` buttons have no `onClick` handler, with no village/policy parsing, crop badges, or profit-score subsidy inclusion. |
| **18** | Warehouse & e-NWR locator | **0** | Not started — no cold-storage/warehouse map within 30 km, no WDRA registry data, and no e-NWR off-season price recommendation. |
| **A** | Phone-number login with one-time code | **2** | Full E.164 phone + 6-digit OTP UI (`Login.jsx`) and real REST client (`src/api/auth.js`) exist, but `VITE_USE_MOCKS` defaults to `'true'` with no backend server, running `mockAuthAdapter.js` with demo code `'123456'` in `localStorage`. |
| **B** | Family-member role | **0** | Not started — only `'farmer'` and `'extension'` roles exist (`RoleContext.jsx`); no consented relative delegation or multi-farmer account switching exists (switching user logs out and wipes local Dexie plots). |
| **C** | Extension-worker desktop dashboard | **1** | Desktop header role switcher (`hidden sm:flex`) opens `/group` (`GroupDashboard.jsx`), which renders static hardcoded English KPIs and a 5-row dummy table with no interactivity or real data. |
| **D** | Onboarding (language, village, plots) | **2** | New phone numbers complete a profile step (`displayName` + `preferredLocale`) and `/farm` offers empty-state plot import/creation into Dexie, but there is no guided onboarding wizard and **no village input anywhere** (`PlotList.jsx:336` saves `village: ''`). |
| **E** | Delete-my-data and consent/audit features | **1** | Signup and land-import modals require consent checkboxes, but there is no `"Delete my data / account"` button, no consent revocation UI, no audit log, and logout cleanup leaks `priceAlerts`, `marketCache`, and `fieldshift-mock-users`. |
| **F** | Performance (< ~1 MB first load & slow networks) | **2** | Initial critical-path JS+CSS is `498.77 kB` gzip (`1,799.85 kB` raw), under 1 MB gzipped, **but** Service Worker registration immediately precaches 182 files (`6,159.35 KiB` raw / ~`2.50 MB` transferred, including all 109 unused locale chunks), saturating slow 2G/3G networks. |

---

### 1.2 Rollup Counts & Weighted Scores

Weights per rubric: **`3 = 100%`**, **`2 = 60%`**, **`1 = 25%`**, **`0 = 0%`**.  
**UI Coverage** (`status >= 1`) and **Real Functionality** (`status == 3`) are reported separately so visual breadth cannot be confused with production readiness.

| Metric | Core 18 Features (`1–18`) | Plan Items (`A–F`) | All 24 Audited Items (`1–18` + `A–F`) |
| :--- | :---: | :---: | :---: |
| **Status `3` (REAL)** | **0** / 18 (`0.0%`) | **0** / 6 (`0.0%`) | **0** / 24 (`0.0%`) |
| **Status `2` (PROTOTYPE)** | **8** / 18 (`44.4%`) | **3** / 6 (`50.0%`) | **11** / 24 (`45.8%`) |
| **Status `1` (UI ONLY)** | **9** / 18 (`50.0%`) | **2** / 6 (`33.3%`) | **11** / 24 (`45.8%`) |
| **Status `0` (NOT STARTED)** | **1** / 18 (`5.6%`) | **1** / 6 (`16.7%`) | **2** / 24 (`8.3%`) |
| **UI Coverage (`status >= 1`)** | **17 / 18 (`94.4%`)** | **5 / 6 (`83.3%`)** | **22 / 24 (`91.7%`)** |
| **Real Functionality (`status == 3`)** | **0 / 18 (`0.0%`)** | **0 / 6 (`0.0%`)** | **0 / 24 (`0.0%`)** |
| **Weighted Overall Score** | **`39.2%`** (`705 / 1800`) | **`38.3%`** (`230 / 600`) | **`39.0%`** (`935 / 2400`) |

> **Why `Real Functionality (status == 3)` is `0%` despite working subsystems:**  
> Four subsystems use genuine browser/external capabilities today — Web Speech TTS + 818 Marathi/Hindi keys (`#1`), Leaflet + `@turf/area` Dexie plot persistence (`#4`), live Open-Meteo Forecast & Air Quality HTTP ingestion (`#8`), and Dexie-persisted mandi price alerts (`#10`). Under the conservative scoring rule, none of those four features earns a full `3` because each is missing mandatory parts of its plan specification (e.g., `#1` leaves 4 screens in hardcoded English and ranks Marathi `#17`; `#4` has no season history or conflict detection; `#8` has hardcoded alert banners and never adjusts crops; `#10` runs on synthetic sine-wave prices and has no buyer listings or glut forecast).

---

### 1.3 Grouping by Plan Phase & Phase-Gate Readiness

| Phase | Features Included | Status Breakdown | Phase Weighted Score | UI Coverage (`>= 1`) | Real (`== 3`) | Could Phase Gate Pass Today? |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **Phase 1: Core Offline Advisor MVP** | `1` Voice/i18n (`2`), `2` Recommender (`2`), `3` Profit/Fertilizer (`1`), `4` Plot History (`2`), `5` Offline Mode (`2`), `6` SMS/WhatsApp (`1`) | `4 × [2]`, `2 × [1]` | **`48.3%`** | `6 / 6` (`100%`) | `0 / 6` (`0%`) | **NO (Fails Pilot Gate; Partial Demo Gate).** Voice, Marathi/Hindi UI, plot polygon storage, and 9-crop offline ranking work locally, **but** profit calculator inputs don't exist (`+19%` hardcoded), plots lack multi-season history/conflict checks, `syncQueue` never syncs, and SMS/WhatsApp toggles lose state on route change. |
| **Phase 2: Soil, Weather, Pest & Market Context** | `7` Soil Import (`2`), `8` Weather Alerts (`2`), `9` Pest Context (`1`), `10` Market & Glut (`2`) | `3 × [2]`, `1 × [1]` | **`51.3%`** | `4 / 4` (`100%`) | `0 / 4` (`0%`) | **NO.** Despite real Open-Meteo weather calls (`#8`) and Dexie price alerts (`#10`), **zero** Phase 2 modules connect to `rotationEngine.js`. Soil OCR and Pest Scanner ignore uploaded images (`setTimeout` mocks), sowing alerts are static text, and mandi prices are procedural sine curves. |
| **Phase 3: Collective & Registry Workflows** | `11` Intercropping (`1`), `12` FPO Group View (`1`), `13` AgriStack (`2`), `14` Contingency Gates (`1`) | `1 × [2]`, `3 × [1]` | **`33.8%`** | `4 / 4` (`100%`) | `0 / 4` (`0%`) | **NO.** Only mock AgriStack parcel import (`#13`) writes usable data into `db.plots`. Intercrops are hidden on plot cards and unscored, FPO dashboard is static English HTML, and contingency gates do not monitor rainfall delays or recalculate short-duration crop risk. |
| **Phase 4: Ecosystem, Satellite, Subsidies & Warehouses** | `15` Input Dealers (`1`), `16` Satellite Alarms (`1`), `17` Subsidy/PMFBY (`1`), `18` Warehouse & e-NWR (`0`) | `3 × [1]`, `1 × [0]` | **`18.8%`** | `3 / 4` (`75%`) | `0 / 4` (`0%`) | **NO.** Warehouse/e-NWR (`#18`) does not exist, satellite alarms (`#16`) contain zero Sentinel-2/SMAP data, subsidy action buttons (`#17`) have no `onClick` handlers, and dealer seed stock (`#15`) is 3 static cards disconnected from recommendations. |

---

### 1.4 Top 5 Gaps for a Hackathon Demo vs. Top 5 Gaps for a Real Farmer Pilot

#### Top 5 Gaps That Matter Most for a Hackathon Demo
1. **Dead & non-persisting buttons that break live judge click-throughs:**
   - `src/components/SchemesHub.jsx:180-190`: `"Check Eligibility"` / `"Apply Now"` buttons have **no `onClick` handler** — clicking does nothing.
   - `src/components/Settings.jsx:236-241, 513-516`: SMS/WhatsApp reminder switches show `"Preferences saved"` (`✓`), yet reset immediately if the judge clicks away and returns to Settings.
   - `src/components/Recommender.jsx:301-330`: Clicking `"Select Crop"` enqueues to `db.syncQueue` **without updating the selected plot's crop or history in `db.plots`**, so returning to `/farm` shows no change on the plot card.
2. **Siloed screens — Soil, Weather, Market, Dealers, and Subsidies never affect Recommendations:**
   - During `Recommender.jsx`'s `4.8 s` loading animation (`mockEngine.js:23-30`), the UI claims to analyze soil history, 14-day weather forecasts, and mandi trends, yet `runOfflineRotationEngine()` (`src/services/rotationEngine.js:42-115`) takes only `(season, previousCrop, areaHectares)` over **9 hardcoded crops**. Entering low Nitrogen on `/soil` or delayed monsoon alerts on `/farm` produces the exact same 3 cards and rupee numbers.
3. **Profit comparison math is visibly fake (`+19%` on every crop) with zero editable calculator inputs:**
   - `rotationEngine.js:82-84` sets `baselineReturn = Math.round(netReturn * 0.84)`, making `percentageGain` **`+19%` for every single crop and plot**, with hardcoded CSS bar widths `w-[65%]` and `w-[35%]` (`Recommender.jsx:943-944`) and no way for a judge to adjust yield, mandi price, or input cost.
4. **Hardcoded dashboard KPIs & untranslated English screens break Marathi/Hindi demos:**
   - Top dashboard stats (`PlotList.jsx:439-442, 609`) always display `12` fields, `5` active crops, `38.4` acres, `28°C`, and `68%` moisture even when the user has 0 or 1 plot in Dexie.
   - Opening the map boundary tool (`FieldMapper.jsx:126-175`), FPO dashboard (`GroupDashboard.jsx:13-170`), or landing page (`LandingPage.jsx:28-41`) switches abruptly to hardcoded English with no `ListenButton`.
5. **Obvious image-ignoring mocks on Soil OCR and Pest Scanner:**
   - Uploading *any* photo (e.g., a desk or blank image) on `/soil` (`SoilImport.jsx:263-265`) always extracts `N=140, P=18, K=210, pH=5.5`, and `/pest` (`PestScanner.jsx:347-354`) strictly alternates between Paddy Leaf Blight (`94%`) and Cashew Powdery Mildew (`88%`).

#### Top 5 Gaps That Matter Most for a Real Pilot with Farmers
1. **No backend server, real SMS OTP delivery, or `syncQueue` processing (`Offline-only data loss risk`):**
   - `db.syncQueue` (`src/db/db.js:45`) is never drained anywhere in `src/`. All farmer plots, soil tests, and crop choices exist solely in browser IndexedDB and are permanently wiped if the farmer clears browser data or switches phone numbers (`AuthContext.jsx:63-84`). Real pilot deployment requires backend endpoints (`/api/v1/auth/*`, `/api/v1/sync`, `/api/v1/recommend`) and an DLT-registered Indian SMS/WhatsApp OTP & reminder gateway.
2. **Service Worker `6.16 MB` first-load precache storm (`109` unused language bundles) + `1.64 MB` monolithic JS bundle:**
   - `vite.config.js:64` precaches `**/*.js`, forcing `dist/sw.js` to download **182 files (`6,159.35 KiB` raw / ~`2.50 MB` transferred)** — including 109 unused language files — in the background on initial visit, burning mobile data and stalling low-RAM Android phones.
3. **Agronomic rule coverage & safety (`9` unsourced crop rules, no regional agro-climatic/soil/pest validation):**
   - `CROP_RULES` (`rotationEngine.js:1-11`) covers only 9 crops with unsourced fixed return/urea numbers (omitting major Goa/Konkan staples like `paddy`, `cashew`, `coconut`, `arecanut`, `ragi/millet`, `vegetables`), has no multi-season plot history or disease carry-over blocking, and gives chemical pesticide recommendations (`Mancozeb 75% WP @ 2.5g/L`, `Wettable Sulphur 80% WP @ 3g/L` in `en/translation.json`) on fake vision scans — a serious agronomic liability in a real farmer pilot.
4. **Real external data integrations (Agmarknet mandi prices, Soil Health Card OCR, Sentinel-2/SMAP, PMFBY/dealer stock):**
   - Market prices (`market.js:144-183`) are synthetic sine waves; dealer phone numbers all dial `+919876543210` (`DealerDirectory.jsx:193`); satellite stress (`VoiceAdvisory.jsx`) is a static text string; village onboarding (`PlotList.jsx:336`) is blank (`''`), preventing district/taluka-specific advisories.
5. **Privacy, DPDP Act compliance, and shared-phone safety (Delete-my-data, consent revocation, family delegation):**
   - There is no `"Delete my account & data"` flow, no consent audit/revocation screen (`Settings.jsx`), incomplete storage wipe on logout (`priceAlerts` and `fieldshift-mock-users` persist), and no consented family-member role for households sharing one smartphone.

---

### 1.5 UI Claims That May Mislead Users or Judges

| Misleading UI Claim | Exact File Path & Line Numbers | What the Code Actually Does |
| :--- | :--- | :--- |
| **`"Adapting Farms with NASA Data"`** | `src/components/LandingPage.jsx:31` | Zero NASA APIs (SMAP, MODIS, POWER, HLS, Earthdata) or satellite datasets are called or bundled anywhere in the repository. |
| **`"Checking plot soil history..."`, `"Scanning 14-day local weather forecast..."`, `"Analyzing nearby mandi price trends..."`** | `src/services/mockEngine.js:23-30` rendered in `src/components/Recommender.jsx:279-297, 811-843` | Displayed during a `6 × 800 ms = 4,800 ms` `setTimeout` loop before calling `runOfflineRotationEngine()`, which reads **none** of `db.soilRecords`, `db.weatherCache`, or `db.marketCache`. |
| **`"+19% vs a typical repeat crop"` & `65%` vs `35%` profit comparison bars** | `src/services/rotationEngine.js:82-84` & `src/components/Recommender.jsx:935-945` | `baselineReturn` is hardcoded as `Math.round(netReturn * 0.84)`, so `((1 - 0.84) / 0.84)` always rounds to **`+19%`** for every crop, and bar widths are literal Tailwind classes `w-[65%]` and `w-[35%]`. |
| **`"Verified"` badge, `"AgriStack — UFSI (India)"`, & `"View Registry"` (`example.org`)** | `src/services/landRegistry/mockProviders.js:75-103`, `src/components/VerificationBadge.jsx:25-60`, `src/components/PlotList.jsx:364-396` | `fetchVerifiedParcels()` waits `setTimeout(1200)` and inserts 3 hardcoded Goa polygons (`Survey No. 41/2-A`, `41/5`, `38/1-B`) marked `isVerified: true` linking to `https://example.org/registry/...`. |
| **`"You can revoke access anytime in Settings"`** | `src/components/AgriStackConsentModal.jsx:73` (and consent copy in `LandRegistryConsentModal.jsx`) | `src/components/Settings.jsx` has **no** AgriStack/land-registry section and **no** way to revoke consent or unlink imported parcels. |
| **`"Auto-OCR"` badge & `"Values extracted — review below"`** | `src/components/SoilImport.jsx:75, 119-121, 259-269` | `handlePhotoImport()` ignores the image file completely, waits `setTimeout(r, 1800)`, and populates hardcoded `LATERITE_PROFILE` (`N: 140, P: 18, K: 210, pH: 5.5`). |
| **`"AI Crop Doctor"` — `"94% match"` / `"88% match"` leaf diagnosis** | `src/components/PestScanner.jsx:31-45, 224-226, 344-355` | `handleFile()` ignores the uploaded photo, runs a `2,200 ms` `setTimeout` laser animation, and alternates (`scanCount % 2`) between two hardcoded objects (`leaf-blight` and `powdery-mildew`). |
| **`"Preferences saved"` (`✓`) on SMS & WhatsApp Reminders** | `src/components/Settings.jsx:236-241, 513-516` | Permanently renders `"Preferences saved"` even though toggle state is plain `useState` that is **never written** to `localStorage`, IndexedDB, or an API and resets as soon as the user leaves `/settings`. |
| **`"Online & Synced"` / `"Your farm data is backed up and up to date"`** | `src/components/Settings.jsx:604-611` (`settings.onlineTitle`, `settings.onlineBody` in `src/locales/en/translation.json:418-419`) | Shown whenever `navigator.onLine === true`, even though **no sync service exists** and items in `db.syncQueue` are never uploaded or backed up anywhere off-device. |
| **Live Mandi `"Updated Xm ago"` & `"AI Market Insight"` on synthetic prices** | `src/components/MarketInsights.jsx:445-446, 516-556` & `src/services/market.js:144-183` | While `MarketInsights.jsx:447` does show a `"Sample data"` pill when `source === 'mock'`, adjacent `"Updated just now"` timestamps, `"AI Market Insight"` banner, and rupee modal prices/forecasts are deterministic sine/cosine waves (`Math.sin(i * 0.19 + phase)`). |
| **Dashboard top KPIs (`12` Total Fields, `5` Active Crops, `38.4` Acres, `28°C`, `68%` Moisture)** | `src/components/PlotList.jsx:438-443, 608-610` | All 4 hero metric cards on `/farm` are hardcoded literals — they do not count `savedPlots` in Dexie or read `WeatherPanel`'s live Open-Meteo temperature/moisture. |
| **`"Eligible on X verified fields"` on Govt Schemes + inert `"Apply Now"` CTA** | `src/components/SchemesHub.jsx:122-126, 180-190` | Marks PM-KISAN, PMFBY, and PKVY `"Eligible"` solely because `verifiedCount > 0` (from mock parcel import) without checking landholding caps, notified village/crop lists, or farmer category, and the CTA button has no `onClick`. |
| **`"Certified Stock"` dealers with fake phone & generic map URL** | `src/components/DealerDirectory.jsx:8-42, 169-174, 192-205` | All 3 Goa dealers (`Goa State Co-op Marketing`, `Zuari Agro Inputs`, `Krishi Seva Kendra`) dial placeholder `tel:+919876543210` and open `https://maps.google.com/?q=agriculture+store`. |
| **`"Monsoon Delayed by 18 Days"` & `"Mid-Season Moisture Deficit"` alerts** | `src/components/CatchCropAlert.jsx:19-46`, `src/components/PlotList.jsx:55-83`, `src/components/VoiceAdvisory.jsx:23-31` | Hardcoded translation strings shown unconditionally on `/farm` load, even when live Open-Meteo data in `WeatherPanel.jsx` right next to them reports heavy rain or normal conditions. |

---

### 1.6 What Could Not Be Verified (and Why)

1. **External backend server implementation:** Only the `frontend/` workspace exists on disk (`docs/openapi.yaml`, `docs/db-schema.sql`, and `docs/BACKEND_INTEGRATION.md` are design specifications, not running services). Whether an external backend exists in another repository or deployment environment could not be verified.
2. **Real OS-level Marathi (`mr-IN`) & Hindi (`hi-IN`) TTS voice availability on target low-end farmer phones:** `useVoice.js` relies on the browser/OS `window.speechSynthesis` engine. Voice quality and preinstalled language-pack presence vary across Android OEM builds (Xiaomi/Samsung/itel/JioPhone Next WebViews) and could not be hardware-tested in a headless build audit.
3. **Real carrier SMS OTP delivery, DLT template compliance, and Android Chrome WebOTP autofill:** `Login.jsx:579-618` invokes `navigator.credentials.get({ otp: { transport: ['sms'] } })`, which can only be verified end-to-end on a physical Android device receiving a real SMS formatted with `@<domain> #<code >`.
4. **Live Google Satellite tile & Google Fonts behaviour under throttled 2G packet loss:** Static analysis of `vite.config.js` and `dist/sw.js` confirmed Google satellite tiles (`mt1.google.com`) are not cached by Workbox and `dist/sw.js` precaches `6,159.35 KiB`, but real Time-to-Interactive (TTI) under 2G radio jitter was inferred from bundle byte measurements rather than physical network testing.

---

## 2. Detailed Feature-by-Feature Audit (Features 1–18)

---

### Feature 1: Voice & local-language UI
*Plan requires: language switch (Marathi/Hindi first), "Listen" button on every screen, icon-led screens, plain-language reasons.*

- **Status:** **`2` (PROTOTYPE — closest feature to `3`, ~85% complete)** — Real browser Web Speech TTS (`window.speechSynthesis`) and 818 native Marathi/Hindi/English translations work offline across all 9 farmer routes, but Marathi (`#17`) and Hindi (`#4`) are not prioritized first in the picker (defaults to `'en'`) and 4 reachable screens (`FieldMapper`, `GroupDashboard`, `LandingPage`, `NotFound`) plus `InstallPrompt` are hardcoded English without `ListenButton`.
- **Evidence:**
  - Language catalog & speech fallbacks: `src/locales/languages.js:3-230` (`en` at line 4, `hi` at line 7, `mr` at line 20; `SPEECH_FALLBACKS` `mr -> ['hi-IN', 'hi']` at lines 183–208).
  - Locale loader & persistence: `src/context/LanguageContext.jsx:35-185` (`localStorage['fieldshift-lang']`, lazy `import.meta.glob('../locales/*/translation.json')`, RTL `dir` handling).
  - Locale bundles: `src/locales/en/translation.json`, `src/locales/hi/translation.json`, `src/locales/mr/translation.json` (`818` keys each; `npm run i18n:check` passes with `0` missing/corrupted keys across `110` locales).
  - TTS engine & UI: `src/hooks/useVoice.js:74-685` (`ensureVoicesLoaded`, `selectVoiceForLanguage`, `splitIntoSpeechChunks`, `stopAllSpeech`), `src/components/ui/ListenButton.jsx:54-172`, `src/utils/speechText.js:1-132`, `src/App.jsx:389-426` (`VoiceNoticeBanner` + route-change speech stop).
  - Untranslated screens missing `ListenButton`: `src/components/FieldMapper.jsx:126-175`, `src/components/GroupDashboard.jsx:13-170`, `src/components/LandingPage.jsx:28-41`, `src/components/NotFound.jsx:11-20`, `src/components/InstallPrompt.jsx:116-138`.
- **What works today / What is mocked / What is missing:**
  - *Works:* Language switching across 110 locales, native Devanagari Hindi and Marathi translations (810/818 keys distinct from English; remaining 8 are numeric/acronym literals like `"98765 43210"` and `"hPa"`), real `window.speechSynthesis` playback with Devanagari sentence chunking (`।`), `Intl` spoken currency/temperature/unit formatting, automatic cancellation on route/language change, voice diagnostic card in `Settings.jsx:379-457`, and icon-led navigation/cards with real WebP crop photos (`CropImage.jsx`).
  - *Mocked/Hardcoded:* None in the TTS/i18n engine itself, though the plain-language reasons read aloud on Recommender, Soil, Pest, CatchCrop, and VoiceAdvisory originate from hardcoded template keys.
  - *Missing vs. plan:* (1) Picker lists `en`, `zh-CN`, `zh-TW` before `hi` (`#4`) and `mr` (`#17`), and defaults to `'en'` when browser locale isn't matched (`LanguageContext.jsx:40`); (2) `FieldMapper.jsx`, `GroupDashboard.jsx`, `LandingPage.jsx`, `NotFound.jsx`, and `InstallPrompt.jsx` lack `ListenButton` and Marathi/Hindi translations; (3) No cloud/pre-recorded audio fallback when a low-end device lacks an OS-installed `mr-IN`/`hi-IN` TTS voice.
- **Works offline?** **Yes** (once the Service Worker caches `dist/assets/translation-*.js`, provided the device OS has an offline `mr-IN` or `hi-IN` TTS voice installed; dynamic Google Fonts stylesheet injection at `LanguageContext.jsx:115-119` degrades to system Devanagari font if first switched while offline).
- **Marathi / Hindi / English UI coverage:** **Yes on all 9 farmer screens** (`818/818` real keys, zero `"???"`, zero English copy-paste fallbacks in `mr` and `hi`); **No** on `FieldMapper`, `GroupDashboard`, `LandingPage`, `NotFound`, `InstallPrompt`, and `mockProviders.js:81` (`consentScopes`).
- **Backend dependency:** None required for on-device Web Speech TTS (`PATCH /api/v1/me` in `src/api/auth.js:56-61` syncs `preferredLocale` when `VITE_USE_MOCKS=false`). Optional `POST /api/v1/tts` (Bhashini / Google Cloud TTS) if supporting devices without OS Devanagari voices.
- **Smallest next step to move up one level (`2 -> 3`):** Pin Marathi (`mr`) and Hindi (`hi`) to positions 1–2 in `src/locales/languages.js` (and default India locale suggestions), replace hardcoded English with `t()` keys in `FieldMapper.jsx`, `GroupDashboard.jsx`, `LandingPage.jsx`, `NotFound.jsx`, and `InstallPrompt.jsx`, and add `ListenButton` to those screens (**~3–4 hours**).

---

### Feature 2: Rotation recommender
*Plan requires: plot form, ranked result cards (2-3 crops), rules: no same-family back to back, legume after cereal, alternate root depth, minimum gap, explanation + trade-off sentence.*

- **Status:** **`2` (PROTOTYPE)** — Working plot/season/previous-crop form and local rule engine returning 3 ranked cards, but restricted to 9 hardcoded crops behind a `4.8 s` `setTimeout` delay, disconnected from soil/weather/market data, and missing minimum-gap rules and trade-off sentences.
- **Evidence:**
  - Route: `/recommender` (`src/App.jsx:478`).
  - UI Component: `src/components/Recommender.jsx:1-1030` (plot query `useLiveQuery(() => db.plots.toArray())` at line 66, demo plot seeder lines 249–266, loading timer lines 279–297, crop selection queue write lines 301–330).
  - Rule Engine: `src/services/rotationEngine.js:1-115` (`CROP_RULES` lines 1–11, `PREVIOUS_CROP_PROFILES` lines 13–23, `runOfflineRotationEngine` lines 42–115).
  - Mock loading steps: `src/services/mockEngine.js:23-30, 190` (`RECOMMENDER_LOADING_STEPS`, `TOTAL_MOCK_DELAY_MS = 4800`).
  - DB tables: Reads `db.plots` (`src/db/db.js:7`); writes `ASSIGN_PLOT_ROTATION` to `db.syncQueue` (`src/db/db.js:45`); **`db.cropRules` (`src/db/db.js:13`) is never populated or read**.
- **What works today / What is mocked / What is missing:**
  - *Works:* Selecting a saved plot from Dexie (or 1-tap demo plot creation), choosing `Rabi` / `Kharif` / `Zaid`, picking any of 60 previous crops via `CropPicker` (or custom text), filtering out same crop family (`crop.family !== previous.family`, line 49) and same root depth (`crop.rootDepth !== previous.rootDepth`, line 50), boosting legumes after cereals (`+100` score bonus, lines 52–54), rendering 3 ranked cards with nitrogen + root-depth plain-language explanations (`Recommender.jsx:155-164`).
  - *Mocked/Hardcoded:* `CROP_RULES` hardcodes **only 9 crops** (`chickpea`, `mustard`, `lentil`, `moong`, `cowpea`, `wheat`, `maize`, `groundnut`, `cotton`) with unsourced `soilHealthScore`, `baseReturnPerHectare`, and `ureaReductionPerHectare` numbers; `PREVIOUS_CROP_PROFILES` maps only 9 keywords (all other 51 crops fall back to `{ family: 'unknown', rootDepth: 'medium' }`); `Recommender.jsx:279-297` runs six `800 ms` `setTimeout` ticks (`4,800 ms` total) pretending to check soil, weather, and mandi prices. Also note `rotationEngine.js:59-65` tops up to 3 cards by **allowing same-family crops** when fewer than 3 non-same-family crops exist in `CROP_RULES` for that season!
  - *Missing vs. plan:* (1) **Minimum gap rule** (multi-season break interval before repeating a crop/family, e.g., 2–3 year gap for solanaceous/brassica/cotton crops); (2) **Trade-off sentence** on each card (e.g., water demand, harvest labor, or price volatility trade-off); (3) Integration with `db.soilRecords`, `db.weatherCache`, `db.marketCache`, dealer seed availability, and plot multi-season history; (4) `handleSelectCrop` does not update `db.plots` with the chosen crop.
- **Works offline?** **Yes** (`runOfflineRotationEngine` runs 100% client-side in JS memory and reads `db.plots` from IndexedDB).
- **Marathi / Hindi / English UI coverage:** **Yes** (`recommender.*` keys in `en`, `hi`, and `mr` are fully translated and spoken via `ListenButton`).
- **Backend dependency:** `POST /api/v1/recommend` (documented in `mockEngine.js:131` and `docs/openapi.yaml`); **no call exists in `src/api/`**.
- **Smallest next step to move up one level (`2 -> 3`):** Expand agronomic rules to cover all 60 catalog crops from ICAR/state package-of-practices data (persisted in `db.cropRules`), read plot season history + `db.soilRecords` + `db.weatherCache`, enforce `minGapSeasons` without same-family top-up violations, add an explicit localized trade-off sentence per card, update `db.plots` on crop selection, and remove the fake `4.8 s` `setTimeout` (**~3–4 days**).

---

### Feature 3: Profit comparison & fertilizer calculator
*Plan requires: comparison view, editable inputs, exact fertilizer reduction, net return = yield x price - cost.*

- **Status:** **`1` (UI ONLY)** — Read-only comparison sub-cards inside Recommender multiply hardcoded per-hectare constants by plot area, with zero editable inputs, no `yield × price − cost` formula, a hardcoded `0.84` multiplier (`+19%` gain on every crop), and fixed `65%`/`35%` progress bars.
- **Evidence:**
  - Recommender metric sub-cards: `src/components/Recommender.jsx:916-973` (Estimated Net Return card lines 918–946; Fertilizer Savings card lines 948–972).
  - Hardcoded arithmetic: `src/services/rotationEngine.js:80-84` (`fertilizerReductionKg`, `fertilizerSavingsInr`, `netReturn`, `baselineReturn`, `percentageGain`).
  - Market Detail gross-income callout: `src/components/MarketCropDetail.jsx:225-238, 996-1007` (`grossPerHa = avgYield * currentPrice`, read-only, no cost deduction).
- **What works today / What is mocked / What is missing:**
  - *Works:* Multiplies `crop.baseReturnPerHectare` and `crop.ureaReductionPerHectare` by `safeArea` (`plot.areaHectares`) and formats localized `₹` / `kg` strings.
  - *Mocked/Hardcoded:*
    - `fertilizerReductionKg = Math.round(crop.ureaReductionPerHectare * safeArea * 10) / 10` using unsourced constants (`86`, `44`, `69`, `74`, `62`, `35`, `27`, `12` kg/ha) and `fertilizerSavingsInr = Math.round(fertilizerReductionKg * 24)` (`₹24/kg` hardcoded). Even cereals/cash crops after non-legumes claim `12–62 kg/ha` Urea reduction regardless of soil Nitrogen!
    - `netReturn = Math.round(crop.baseReturnPerHectare * safeArea)` — **does not compute `yield × price − cost`**.
    - `baselineReturn = Math.round(netReturn * 0.84)` — guarantees `percentageGain` is **`+19%` for every crop**, paired with hardcoded Tailwind widths `w-[65%]` and `w-[35%]` (`Recommender.jsx:943-944`).
  - *Missing vs. plan:* (1) Dedicated or expandable side-by-side comparison calculator (recommended crop vs. repeat baseline crop); (2) **Editable inputs** for expected yield (`qtl/ha`), mandi selling price (`₹/qtl`), and input cost (`₹/ha` seed + fertilizer + labor); (3) Real formula `netReturn = (yield × price) − (baseCost − fertilizerSavings + subsidy)`; (4) Exact NPK/Urea reduction derived from previous legume N-fixation credit + `db.soilRecords` Nitrogen reading.
- **Works offline?** **Yes** (static local arithmetic).
- **Marathi / Hindi / English UI coverage:** **Yes** for existing labels (`recommender.estNetReturn`, `recommender.fertilizerSavings`, `recommender.vsRepeatCrop`, `recommender.saveApprox`); new editable-calculator labels would need keys added.
- **Backend dependency:** Can run 100% client-side offline once seeded with crop yield/cost tables and cached mandi prices from `/api/v1/market/prices`; **no call exists in `src/api/`**.
- **Smallest next step to move up one level (`1 -> 2`):** Add an expandable interactive calculator drawer on each recommendation card with editable `yield`, `price` (prefilled from `market.js`), and `cost` inputs computing `netReturn = yield * price - (cost - fertilizerSavingsInr)` against the actual previous crop's repeat-crop baseline, and compute N-credit from legume residue (`25–40 kg N/ha` -> `54–87 kg Urea/ha`) (**~6–8 hours**).

---

### Feature 4: Plot-wise history
*Plan requires: plot list, season timeline, area units, conflict flagging from history.*

- **Status:** **`2` (PROTOTYPE)** — Persists plots in Dexie `db.plots` with interactive Leaflet polygon mapping (`@turf/area`) and 6 live-converted area units, but stores only one current crop with zero season timeline and zero conflict flagging from history.
- **Evidence:**
  - Route: `/farm` (`src/App.jsx:477`).
  - Components: `src/components/PlotList.jsx:46-54, 266, 328-361, 474-540`, `src/components/AddPlotModal.jsx:19-336`, `src/components/FieldMapper.jsx:1-198`, `src/components/DashboardMap.jsx:1-130`.
  - DB table: `db.plots` (`src/db/db.js:6-7`, schema: `'++id, name, area, areaUnit, soilType, irrigation, synced, providerId, externalId'`).
- **What works today / What is mocked / What is missing:**
  - *Works:* Creating plots via `AddPlotModal`, drawing multi-vertex polygons on satellite imagery in `FieldMapper.jsx` with real geodesic square-meter area via `@turf/area` (`FieldMapper.jsx:78-85`), live conversion across **6 area units** (`acres`, `hectares`, `guntha`, `bigha`, `sqm`, `sqft` in `AddPlotModal.jsx:57-67, 116-123`), reactive IndexedDB persistence via `useLiveQuery(() => db.plots.toArray())`, and polygon rendering on `DashboardMap.jsx`.
  - *Mocked/Hardcoded:* Top 4 KPI summary cards on `/farm` (`PlotList.jsx:439-442, 609`: `12` fields, `5` active crops, `38.4` acres) are hardcoded literals disconnected from `savedPlots`!
  - *Missing vs. plan:* (1) **Season timeline** (`Kharif 2025 -> Rabi 2025-26 -> Zaid 2026` history per plot — `db.plots` only stores a single `primaryCrop` string, and there is no `plotHistory` table or `history[]` array); (2) **Conflict flagging from history** (warning badges when a plot planted the same crop family in consecutive seasons or violated a rotation break); (3) Plot edit/delete actions and crop-assignment write-back from `Recommender.jsx`.
- **Works offline?** **Mostly Yes** — Plot list, unit conversion, and form persistence work 100% offline in Dexie, **except** Leaflet satellite map tiles (`https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}` in `FieldMapper.jsx:186` and `DashboardMap.jsx:90`) and `OpenStreetMapProvider` geosearch (`FieldMapper.jsx:103`) have no Workbox runtime cache rule in `vite.config.js` and render gray tiles offline.
- **Marathi / Hindi / English UI coverage:** **Partial** — `PlotList.jsx` and `AddPlotModal.jsx` are fully translated in `mr`/`hi`/`en`, **but** `FieldMapper.jsx:126-175` (`"Tap points on your field boundary"`, `"Search village, town, or landmark..."`, `"Undo"`, `"Clear"`, `"Confirm Boundary"`) is 100% hardcoded English.
- **Backend dependency:** `GET/POST/PATCH/DELETE /api/v1/plots` and `GET/POST /api/v1/plots/:id/seasons` (documented in `docs/openapi.yaml`); **no call exists in `src/api/`**.
- **Smallest next step to move up one level (`2 -> 3`):** Add a `seasons` history array/table per plot (`{ year, season, cropId, family }`), render a 4-season timeline chip strip on each plot card in `PlotList.jsx`, flag consecutive same-family/disease-carryover conflicts directly on the card, wire top KPIs to `savedPlots`, and localize `FieldMapper.jsx` (**~1.5–2 days**).

---

### Feature 5: Offline mode
*Plan requires: installable PWA, local cache, sync queue, "saved on phone" status, rules shipped to the device, sync processing and conflict handling.*

- **Status:** **`2` (PROTOTYPE)** — Installable Workbox PWA (`dist/manifest.webmanifest` + `dist/sw.js`) with Dexie tables, online/offline indicator, and bundled JS rotation rules, **but** `db.syncQueue` is strictly write-only with zero sync processor, zero conflict handling, and an unused `db.cropRules` table.
- **Evidence:**
  - PWA & Workbox config: `vite.config.js:22-148`; build artifacts `dist/manifest.webmanifest`, `dist/sw.js` (`182` precached entries), `dist/registerSW.js`.
  - Install banner: `src/components/InstallPrompt.jsx:1-147` (`beforeinstallprompt` + iOS `"Add to Home Screen"` instructions).
  - IndexedDB schema: `src/db/db.js:1-66` (v4 stores: `plots`, `cropRules`, `soilRecords`, `syncQueue`, `weatherCache`, `marketCache`, `priceAlerts`).
  - Queue writes (never drained): `src/components/PlotList.jsx:352-357` (`CREATE_PLOT`), `src/components/Recommender.jsx:307-320` (`ASSIGN_PLOT_ROTATION`), `src/services/market.js:235-239` (`CREATE_PRICE_ALERT`).
  - Status UI & logout guard: `src/components/Settings.jsx:234, 295-304, 597-627, 687-697`, `src/context/AuthContext.jsx:151-161, 314-317`.
- **What works today / What is mocked / What is missing:**
  - *Works:* Standalone PWA manifest (`start_url: '/farm'`), Workbox app-shell + 60 crop thumbnail precache, runtime `CacheFirst` for 480px crop cards & Google Fonts, Dexie local storage for plots/soil/weather/market/priceAlerts, offline session preservation in `AuthContext.jsx:151-161`, `"Offline Mode — Saved Locally"` / `"Stored on your phone"` status in `Settings.jsx:597-627`, unsynced-item count warning before logout (`Settings.jsx:687-697`), and client-side `rotationEngine.js`.
  - *Mocked/Hardcoded:* `Settings.jsx:604-611` displays `"Online & Synced"` / `"Your farm data is backed up and up to date"` whenever `navigator.onLine` is true — purely checking browser connectivity, not actual sync state!
  - *Missing vs. plan:* (1) **Sync processing** (no `window.addEventListener('online')` sync runner, no Background Sync registration, no batch/drain worker reading `db.syncQueue`, no `synced: true` promotion on `db.plots` or `db.soilRecords`, and `SoilImport.jsx:325` doesn't even enqueue `CREATE_SOIL_RECORD`); (2) **Conflict handling** (no `updatedAt`/version vectors, last-write-wins or merge prompt on 409 conflicts); (3) `db.cropRules` table (`src/db/db.js:13`) is never seeded or queried; (4) Visible `"Saved on phone / X pending sync"` pill in the main header (`AppHeader`).
- **Works offline?** **Yes** (navigation shell, auth session, Dexie reads/writes, cached weather/market views, and rotation recommender all load offline after SW install).
- **Marathi / Hindi / English UI coverage:** **Mostly Yes** (`Settings.jsx` offline/privacy labels are translated in `mr`/`hi`/`en`), **except** `InstallPrompt.jsx:116-138` (`"Add Field Shift to your Home screen"`, `"Install"`) is hardcoded English.
- **Backend dependency:** `POST /api/v1/sync` (batch mutation endpoint with idempotency keys & conflict responses) + `GET /api/v1/rules/crops`; **no call exists in `src/api/`**.
- **Smallest next step to move up one level (`2 -> 3`):** Build `src/services/syncManager.js` triggered on `online` event and post-mutation when `VITE_USE_MOCKS=false` to drain `db.syncQueue` via `apiRequest('/api/v1/sync')` with exponential backoff, mark `db.plots`/`db.soilRecords` `synced = true`, handle HTTP `409` timestamp/version conflicts, and show truthful `"Saved on phone (unsynced)"` vs `"Synced"` status (**~2–3 days** including backend endpoint).

---

### Feature 6: SMS/WhatsApp reminders
*Plan requires: preferences screen, persisted preferences, scheduler, gateway.*

- **Status:** **`1` (UI ONLY)** — Preferences card in `Settings.jsx` renders 4 toggle switches stored only in transient React `useState` (not persisted to `localStorage`, Dexie, or backend — resets upon leaving `/settings`), with zero scheduler and zero SMS/WhatsApp gateway.
- **Evidence:**
  - UI Component: `src/components/Settings.jsx:236-241` (`const [reminders, setReminders] = useState({ sowing: true, fertilizer: false, sms: true, whatsapp: false })`), `lines 317-318` (`toggleReminder`), `lines 459-517` (switches + hardcoded `"Preferences saved"` footer at lines 513–516).
  - Unused storage key hint: `src/context/AuthContext.jsx:19` lists `'fieldshift-reminders'` in `USER_SCOPED_STORAGE_KEYS` cleared on logout, proving `localStorage` persistence was intended but never wired in `Settings.jsx`.
- **What works today / What is mocked / What is missing:**
  - *Works:* Accessible `role="switch"` toggle buttons for Sowing alerts, Fertilizer schedule, SMS delivery, and WhatsApp delivery with localized labels and voice support.
  - *Mocked/Hardcoded:* Initial state `{ sowing: true, fertilizer: false, sms: true, whatsapp: false }` resets on every component remount, while line 515 unconditionally displays `"Preferences saved"`.
  - *Missing vs. plan:* (1) **Persisted preferences** (`localStorage` / Dexie + `syncQueue` + user profile sync); (2) **Scheduler** (cron/queue calculating sowing and top-dressing dates from each plot's sowing date and crop duration); (3) **Gateway** (Twilio / Gupshup / MSG91 DLT SMS & WhatsApp Business template integration, plus local PWA Web Push / Notification fallback).
- **Works offline?** **No** (toggles flip in memory offline, but lose state as soon as the user navigates to another tab).
- **Marathi / Hindi / English UI coverage:** **Yes** (`settings.remindersTitle`, `settings.sowing`, `settings.fertilizer`, `settings.sms`, `settings.whatsapp` are fully translated in `mr`/`hi`/`en`).
- **Backend dependency:** `PUT /api/v1/me/reminders` + backend cron scheduler + SMS/WhatsApp provider gateway (MSG91 / Gupshup / Twilio); **no call exists in `src/api/`**.
- **Smallest next step to move up one level (`1 -> 2`):** Persist `reminders` to `localStorage['fieldshift-reminders']` (and Dexie `syncQueue`), add a sowing-date picker on plots to generate a real local reminder schedule preview (and browser `Notification` reminders), and show `"Preferences saved"` only after actual persistence (**~3–4 hours** for `1 -> 2`; **~2–3 days** with backend cron + MSG91/Twilio gateway for `3`).

---

### Feature 7: Soil data import
*Plan requires: values form, photo upload, OCR, storage, nutrient-balance rules used by the recommender.*

- **Status:** **`2` (PROTOTYPE)** — Manual 6-parameter soil form writes to Dexie `db.soilRecords` offline, **but** photo OCR is a `1.8 s` `setTimeout` returning hardcoded Goa laterite values, records are saved with `plotId: null` and cannot be viewed anywhere, and the recommender completely ignores `db.soilRecords`.
- **Evidence:**
  - Route: `/soil` (`src/App.jsx:479`).
  - Component: `src/components/SoilImport.jsx:1-512` (`LATERITE_PROFILE` lines 23–30, `SoilDropzone` lines 61–177, `handlePhotoImport` `setTimeout(r, 1800)` lines 259–269, `handleSave` `db.soilRecords.add` lines 321–336).
  - DB table: `db.soilRecords` (`src/db/db.js:28`, schema `'++id, plotId, n, p, k, ph, oc, ec, source, createdAt'`).
- **What works today / What is mocked / What is missing:**
  - *Works:* Validated numeric inputs for Nitrogen (`kg/ha`), Phosphorus (`kg/ha`), Potassium (`kg/ha`), Soil pH (`0–14`), Organic Carbon (`%`), and Electrical Conductivity (`dS/m`), threshold badges (`Low` / `Normal` / `Acidic` / `Optimal` via `getFieldStatus` lines 48–56), 1-tap Goa Laterite preset, photo file/camera picker with preview thumbnail, and persistence via `db.soilRecords.add()`.
  - *Mocked/Hardcoded:* `handlePhotoImport` (`SoilImport.jsx:259-269`) awaits `new Promise((r) => setTimeout(r, 1800))`, discards `file`, and sets `values` to `LATERITE_PROFILE = { n: '140', p: '18', k: '210', ph: '5.5', oc: '0.62', ec: '0.28' }`. The 3 recommendation bullets at the bottom (`SoilImport.jsx:39-43, 471-505`) are static Goa laterite strings that do not even change when the user types alkaline pH `8.2` or high Nitrogen `450`!
  - *Missing vs. plan:* (1) **Plot selector** (`plotId` is hardcoded to `null` at line 326); (2) **Real OCR** (Tesseract.js on-device or Vision OCR endpoint parsing Indian Soil Health Card tables); (3) **Saved soil history viewer** (there is zero `db.soilRecords` read query anywhere in `src/`); (4) **Nutrient-balance rules in `rotationEngine.js`** (e.g., prioritizing N-fixing legumes when `N < 280 kg/ha`, acid-tolerant crops/liming advice when `pH < 6.0`, salt-tolerant crops when `EC > 1.0`, and adjusting fertilizer reduction math).
- **Works offline?** **Yes** (manual form entry and `db.soilRecords.add()` work 100% offline).
- **Marathi / Hindi / English UI coverage:** **Yes** (`soil.*` keys are fully translated in `mr`/`hi`/`en` with working `ListenButton`s).
- **Backend dependency:** `POST /api/v1/soil/ocr` (or client-side `tesseract.js` WASM worker) and `GET/POST /api/v1/soil-records`; **no call exists in `src/api/`**.
- **Smallest next step to move up one level (`2 -> 3`):** Add a plot selector + saved soil record loader on `/soil`, wire `db.soilRecords` for the selected plot into `runOfflineRotationEngine()` (boosting legumes on low N, penalizing pH-incompatible crops, and computing dynamic NPK deficit), and integrate real OCR (`tesseract.js` or `/api/v1/soil/ocr` Vision parser, removing fake `"Auto-OCR"` fallback) (**~2–3 days**).

---

### Feature 8: Weather & sowing alerts
*Plan requires: alert banner, sowing window view, weather ingestion, alerts that shorten or swap crops.*

- **Status:** **`2` (PROTOTYPE)** — `WeatherPanel` performs real live HTTP weather & air-quality ingestion from Open-Meteo with Dexie offline caching and rule-based advisories, **but** dashboard alert banners are static hardcoded text, there is no sowing-window view, and weather alerts never shorten or swap crops in the recommender.
- **Evidence:**
  - Service: `src/services/weather.js:1-285` (`OPEN_METEO_FORECAST_URL` & `OPEN_METEO_AIR_URL` lines 3–4, `buildAdvisories` lines 28–43, `fetchWeather` lines 133–160, `getCachedWeather` lines 162–168, `buildSampleWeather` lines 199–284).
  - Component: `src/components/WeatherPanel.jsx:1-512` (plot centroid / geolocation lookup, 24h `Recharts` `ComposedChart` lines 371–454, 7-day forecast strip, `°C`/`°F` persisted toggle).
  - Hardcoded dashboard banners disconnected from weather: `src/components/PlotList.jsx:55-83` (`ALERTS`), `src/components/CatchCropAlert.jsx:7-60`, `src/services/mockEngine.js:73-85` (`getMockStartupNotifications`).
  - DB table: `db.weatherCache` (`src/db/db.js:54`, schema `'locationKey, fetchedAt'`).
- **What works today / What is mocked / What is missing:**
  - *Works:* **Real external API calls** (`fetch`) to `https://api.open-meteo.com/v1/forecast` (hourly temp, humidity, precipitation probability, wind, pressure, `soil_moisture_0_to_1cm`, 7-day daily summary) and `https://air-quality-api.open-meteo.com/v1/air-quality` (`european_aqi`, `us_aqi`) for the farmer's plot polygon centroid (`getCentroid`) or device GPS (`navigator.geolocation`), cached in `db.weatherCache` with offline fallback, plus 3 computed advisories (`spray` when rain `<25%` & wind `<15 km/h`, `irrigate` when soil moisture `<22%` & 48h rain `<5 mm`, `heavyRain` sowing warning when 3-day rain `>45 mm`).
  - *Mocked/Hardcoded:* `buildSampleWeather()` (`weather.js:199-284`, labeled `"Sample forecast"` only when user clicks `"Load sample forecast"` offline with empty cache); **all alert banners outside `WeatherPanel`** (`PlotList.jsx` `ALERTS`, `CatchCropAlert.jsx`, `StartupNotifications.jsx`, and top `28°C` / `68%` KPI cards at `PlotList.jsx:441-442`) are hardcoded static data.
  - *Missing vs. plan:* (1) **Sowing window view** (crop-by-crop optimal sowing date range vs. current soil moisture and 14-day rainfall onset); (2) **Dynamic alert banner** driven by `db.weatherCache` / `fetchWeather()` instead of static `ALERTS`; (3) **Alerts that shorten or swap crops** in `Recommender.jsx` / `rotationEngine.js` (e.g., automatically swapping 120-day crops for 55–65 day `moong`/`cowpea` when monsoon onset is delayed or terminal heat/heavy rain is forecast).
- **Works offline?** **Yes, after first online fetch** (`WeatherPanel.jsx:169-173` loads the last cached payload from Dexie `db.weatherCache` with an `"Offline — showing last saved forecast"` badge).
- **Marathi / Hindi / English UI coverage:** **Yes** (`weather.*` and `alerts.*` keys are fully translated in `mr`/`hi`/`en` with speakable temperature/percentage formatting via `speechText.js`).
- **Backend dependency:** Already calls public Open-Meteo APIs directly from `src/services/weather.js` (no API key required; optional backend IMD/agromet proxy `/api/v1/weather` if extended beyond 7–16 days).
- **Smallest next step to move up one level (`2 -> 3`):** Drive dashboard alert banners and top temp/moisture KPIs from `fetchWeather()`/`db.weatherCache`, add a 14-day sowing-window timeline strip in `WeatherPanel`, and pass cached rainfall/soil-moisture thresholds into `runOfflineRotationEngine()` to demote long-duration crops or auto-swap to short-duration catch crops (**~1–1.5 days**).

---

### Feature 9: Pest & disease context
*Plan requires: risk tags, photo upload, knowledge base, carry-over rules by crop family.*

- **Status:** **`1` (UI ONLY)** — Photo upload runs a `2.2 s` `setTimeout` laser animation ignoring image pixels and alternates between 2 hardcoded diagnoses, with zero persistence, zero risk tags, zero searchable knowledge base, and zero crop-family carry-over rules in the recommender.
- **Evidence:**
  - Route: `/pest` (`src/App.jsx:481`).
  - Component: `src/components/PestScanner.jsx:1-505` (`DISEASE_RESULTS` lines 31–45, `ScanOverlay` lines 48–100, `handleFile` `setTimeout(2200)` lines 344–355, `handleSampleScan` lines 357–367).
- **What works today / What is mocked / What is missing:**
  - *Works:* Camera (`capture="environment"`) and gallery file picker with image preview, localized organic + chemical treatment accordion cards, deep-link `"Find nearby dealers ->"` (`navigate('/farm?dealerQuery=...')` at line 292), and `ListenButton` speech narration.
  - *Mocked/Hardcoded:* `DISEASE_RESULTS` (`PestScanner.jsx:31-45`) contains **only 2 hardcoded items**: `leaf-blight` (Paddy, `confidence: 94`, `severity: 'high'`) and `powdery-mildew` (Cashew, `confidence: 88`, `severity: 'medium'`). `handleFile` (`lines 344-355`) waits `setTimeout(..., 2200)` and picks `DISEASE_RESULTS[scanCount % DISEASE_RESULTS.length]` without inspecting the uploaded file at all.
  - *Missing vs. plan:* (1) **Pest/disease risk tags** on plot cards and recommender crop cards; (2) **Browseable offline pest & disease knowledge base** across crops/families; (3) **Real image classification** (on-device ONNX/TFLite model or `/api/v1/pest/analyze` vision endpoint) and Dexie `pestObservations` persistence linked to a `plotId`; (4) **Carry-over rules by crop family** in `rotationEngine.js` (e.g., blocking solanaceous/cereal/legume host crops for N seasons on a plot after a recorded soil-borne/residue-borne disease).
- **Works offline?** **UI loads offline**, returning the same 2 alternating mock cards.
- **Marathi / Hindi / English UI coverage:** **Yes** (`pest.*` keys including disease names, symptoms, organic remedies, and chemical fallbacks are fully translated in `mr`/`hi`/`en`).
- **Backend dependency:** `POST /api/v1/pest/diagnose` (vision/LLM classifier) + `GET /api/v1/pest/kb`; **no call exists in `src/api/`**.
- **Smallest next step to move up one level (`1 -> 2`):** Add a structured offline pest/disease knowledge base JSON (`20+` common pests mapped to crop families and host carry-over seasons), allow tagging a plot with observed pest/disease history in Dexie, display risk tags on recommender cards, and penalize host-family crops in `runOfflineRotationEngine()` (**~1–1.5 days** for `1 -> 2`; **+2 days** with real vision API/model for `3`).

---

### Feature 10: Market links & glut forecast
*Plan requires: mandi prices, buyer listing, harvest timing, historical modal price curves, glut avoidance, price feeding the profit score.*

- **Status:** **`2` (PROTOTYPE)** — Rich mandi price list, historical/seasonal Recharts views, rule-based sell/hold guidance, and Dexie-persisted price alerts work locally, **but** default `USE_MOCKS=true` generates procedural sine-wave prices, and buyer listings, glut-avoidance forecasting, and recommender profit-score integration are missing.
- **Evidence:**
  - Routes: `/market` (`src/App.jsx:480`), `/market/:cropId` (`src/App.jsx:481`, lazy-loaded `MarketCropDetail`).
  - Components: `src/components/MarketInsights.jsx:1-740`, `src/components/MarketCropDetail.jsx:1-1253`, plus separate static dashboard card `MarketInsightsCard` in `src/components/PlotList.jsx:85-102, 200-255`.
  - Service: `src/services/market.js:1-604` (`USE_MOCKS = (import.meta.env.VITE_USE_MOCKS ?? 'true') !== 'false'` line 6, `BASE_CROP_MARKET_SPECS` lines 16–85, `generateDailySeries` lines 144–183, `createPriceAlert`/`evaluatePriceAlerts` lines 211–280, live `fetch('/api/v1/market/...')` branches lines 325–341 & 381–399).
  - DB tables: `db.marketCache` (`src/db/db.js:55`), `db.priceAlerts` (`src/db/db.js:56`).
- **What works today / What is mocked / What is missing:**
  - *Works:* Search/sort/filter across 59 crops & regional mandis, `"My Crop"` filter reading `db.plots`, favourites (`localStorage['fieldshift-market-favourites']`), **real persisted `db.priceAlerts`** (`above`/`below` threshold triggers persisted in IndexedDB), `7D`/`30D`/`90D`/`1Y` historical modal price area chart with prior-year comparison toggle, 12-month seasonal bar chart (`bestMonths`), 7-day linear regression forecast band, rule-based `sell_now` / `hold` / `wait` recommendation (`market.js:461-497`), personalized gross revenue/ha estimate from `db.plots`, and conditional `fetch('/api/v1/market/prices')` when `VITE_USE_MOCKS=false`.
  - *Mocked/Hardcoded:* With default `USE_MOCKS=true`, every price and 365-day series is synthesized by `generateDailySeries()` (`Math.sin(i * 0.19 + phase)` + `Math.cos(...)`, `market.js:144-183`). Nearby input dealers inside `market.js:538-555` are 2 hardcoded Goa stores (`Mapusa Krishi Kendra`, `Margao Agro Service`), and `PlotList.jsx:85-102` has a separate hardcoded cashew/coconut/paddy widget (`₹185/kg`) unrelated to `market.js`.
  - *Missing vs. plan:* (1) **Buyer listings** (FPO procurement centers, e-NAM buyers, processors/offtakers with contact/quote details — only 2 *input* dealers are shown); (2) **Glut forecast & glut avoidance** (predicting harvest-window price crashes from regional sowing acreage surges + crop maturity dates; currently only 1 generic paragraph `marketDetail.harvestTimingBody` exists at `MarketCropDetail.jsx:1032`); (3) **Price feeding the recommender profit score** (`rotationEngine.js:82` uses static `baseReturnPerHectare` and never reads `market.js` or `db.marketCache`).
- **Works offline?** **Yes** (mock generator and `db.marketCache` + `db.priceAlerts` work 100% offline).
- **Marathi / Hindi / English UI coverage:** **Yes** (`market.*`, `marketDetail.*`, and all 60 `crops.<id>.name` entries are fully translated in `mr`/`hi`/`en` with `Intl` spoken currency units).
- **Backend dependency:** `GET /api/v1/market/prices` and `GET /api/v1/market/crops/:cropId` (backed by data.gov.in Agmarknet API + buyer directory); **`fetch()` calls DO exist in `src/services/market.js:326, 383`** (bypassing `src/api/client.js`), inactive while `VITE_USE_MOCKS !== 'false'`.
- **Smallest next step to move up one level (`2 -> 3`):** Connect `/api/v1/market/*` to live Agmarknet mandi arrival + modal price feeds, feed expected harvest-month modal price from `db.marketCache` into `rotationEngine.js` net-return scoring (penalizing high-arrival glut months), and add verified crop buyer/offtaker listings (**~2–3 days**).

---

### Feature 11: Intercropping & cover crops
*Plan requires: multi-crop plot entry, combination rules, benefit scores.*

- **Status:** **`1` (UI ONLY)** — `AddPlotModal` lets a user pick one optional `intercrop` saved as a field on `db.plots`, **but** plot cards don't even display it and zero intercrop/cover-crop combination rules or benefit scores exist anywhere.
- **Evidence:**
  - Form input: `src/components/AddPlotModal.jsx:53, 136, 282-298` (`showIntercrop`, `CropPicker` with `exclude={[form.primaryCrop]}`).
  - Persistence: `src/components/PlotList.jsx:338` (`intercrop: plotData.intercrop || null`), `lines 513-535` (plot card renders only `primaryCrop`, omitting `intercrop`!).
  - Market `"My Crop"` filter reference: `src/components/MarketInsights.jsx:252`, `src/components/MarketCropDetail.jsx:228`.
- **What works today / What is mocked / What is missing:**
  - *Works:* Optional second crop selector in `AddPlotModal` prevents choosing the exact same ID as `primaryCrop` and persists `intercrop` in `db.plots`.
  - *Mocked/Hardcoded:* None (no rules exist at all).
  - *Missing vs. plan:* (1) Displaying `plot.intercrop` on plot cards in `PlotList.jsx`; (2) **Intercrop & cover-crop combination rules** (compatible row ratios like `Maize + Cowpea`, `Sugarcane + Chickpea`, `Coconut + Banana/Turmeric`, cover/green-manure crops in fallow windows, and blocking incompatible allelopathic/shading/same-pest pairs); (3) **Benefit scores** (nitrogen transfer, weed suppression, Land Equivalent Ratio / combined return score in `Recommender.jsx`).
- **Works offline?** **Yes** (`intercrop` string saves to Dexie offline).
- **Marathi / Hindi / English UI coverage:** **Yes** for the 2 existing modal strings (`addField.addIntercrop`, `addField.intercropLabel`).
- **Backend dependency:** None required for client-side agronomic companion-crop matrix (`GET /api/v1/rules/intercrops` optional); **no call exists in `src/api/`**.
- **Smallest next step to move up one level (`1 -> 2`):** Render `plot.intercrop` on `PlotList.jsx` cards, add a companion/cover-crop compatibility & benefit matrix (`src/services/intercropRules.js`) that flags compatible/incompatible pairs in `AddPlotModal`, and surface recommended intercrop/cover-crop pairings with soil/income benefit scores in `Recommender.jsx` (**~1 day**).

---

### Feature 12: FPO and group view
*Plan requires: group dashboard, bulk seed/fertilizer demand aggregation, groups/roles/permissions.*

- **Status:** **`1` (UI ONLY)** — Role-gated `/group` screen (`GroupDashboard.jsx`) renders static hardcoded English JSX (`42` farmers, `115 Acres`, `450 kg` seed, `1,200 kg` Urea, 5 hardcoded farmer rows) with zero aggregation logic, zero persistence, and only a binary `'farmer' | 'extension'` flag.
- **Evidence:**
  - Route & guard: `/group` (`src/App.jsx:484, 490-509`, `src/context/RoleContext.jsx:1-54`).
  - Component: `src/components/GroupDashboard.jsx:1-171` (`KPI_CARDS` lines 13–42, `FARMERS` lines 44–50, `₹2.4L` banner lines 155–165).
  - Mock role grant: `src/services/auth/mockAuthAdapter.js:61-87` (`VITE_MOCK_EXTENSION_PHONES`).
- **What works today / What is mocked / What is missing:**
  - *Works:* `RoleContext` restricts `/group` to users whose `user.roles` array contains `'extension'` and toggles between Farmer and Extension views on desktop (`App.jsx:189-221`).
  - *Mocked/Hardcoded:* 100% of `GroupDashboard.jsx` is static constants (`42` Enrolled Farmers, `115 Acres` Mapped Area, `450 kg` Moong & Cowpea Seed Demand, `1,200 kg` Urea Savings, 5 hardcoded farmers `Ramesh Naik` through `Prakash Gaonkar`, and `₹2.4L` bulk procurement estimate).
  - *Missing vs. plan:* (1) **Dynamic bulk seed & fertilizer demand aggregation** computed from member farmers' plots and selected crop plans (`seedRateKgPerHa × areaHa`, aggregated NPK/Urea demand); (2) **FPO / group membership, invite/join codes, and granular permissions** (FPO admin vs. agronomist vs. member farmer consent); (3) Interactive actions (filter by village/season, export bulk order CSV/PDF, send group advisories); (4) Localization and voice (`GroupDashboard.jsx` uses zero `t()` calls).
- **Works offline?** **Static JSX renders offline**, with zero real data.
- **Marathi / Hindi / English UI coverage:** **NO — English only.** `GroupDashboard.jsx` contains 100% hardcoded English strings and does not import `useTranslation` or `ListenButton`.
- **Backend dependency:** `GET /api/v1/groups/:groupId/dashboard`, `GET /api/v1/groups/:groupId/demand`, `POST /api/v1/groups/:groupId/members`; **no call exists in `src/api/`**.
- **Smallest next step to move up one level (`1 -> 2`):** Localize `GroupDashboard.jsx` (`mr`/`hi`/`en`), seed/store FPO member plots in Dexie (including the local farmer's plots + sample/synced group plots), dynamically compute total acreage, crop-wise seed kg (`areaHa × seedRate`), and fertilizer demand from actual plot records, and add CSV export (**~1 day**).

---

### Feature 13: AgriStack integration
*Plan requires: consent screen, consent-brokered connector, prefilled plot and crop inputs.*

- **Status:** **`2` (PROTOTYPE)** — Country-aware consent modal imports and deduplicates 3 polygon parcels into `db.plots` that render on `DashboardMap` and prefill `Recommender`, **but** the connector is a `1.2 s` `setTimeout` returning hardcoded Goa parcels with no real AgriStack UFSI / consent-artifact broker.
- **Evidence:**
  - Active consent UI & registry: `src/components/LandRegistryConsentModal.jsx:1-214`, `src/components/VerificationBadge.jsx:1-62`, `src/services/landRegistry/registry.js:1-38`, `src/services/landRegistry/mockProviders.js:75-103` (`inAgriStackProvider`), `src/components/PlotList.jsx:363-405` (`handleImportProvider`).
  - Unused legacy duplicates: `src/components/AgriStackConsentModal.jsx:1-130` and `importAgriStackPlots` in `src/services/mockEngine.js:195-245` (dead code).
- **What works today / What is mocked / What is missing:**
  - *Works:* Selecting country (`IN` -> `in-agristack`), reviewing requested scopes, checking explicit consent checkbox (`agreed`), deduplicating against existing `db.plots` by `${providerId}:${externalId}` (`PlotList.jsx:368-375`), converting `parcel.areaHa` into the user's preferred area unit, writing polygons + `primaryCrop` (`paddy`, `cashew`, `coconut`) into `db.plots`, displaying verified green polygon outlines on `DashboardMap.jsx:57` + `VerificationBadge`, and making imported plots selectable in `Recommender.jsx`.
  - *Mocked/Hardcoded:* `inAgriStackProvider.fetchVerifiedParcels()` (`mockProviders.js:83-102`) awaits `setTimeout(resolve, 1200)` and returns 3 hardcoded Goa parcels (`IN-GA-BAR-41-2A`, `IN-GA-BAR-41-5`, `IN-GA-BAR-38-1B`) around `[15.55, 73.83]` with `registryUrl: 'https://example.org/registry/...'`. Note also that clicking `"Import"` in `PlotList.jsx:386` sets `synced: true` locally without recording a consent artifact or calling any server.
  - *Missing vs. plan:* (1) **Real consent-brokered AgriStack UFSI / DEPA consent artifact flow** (Farmer ID / Aadhaar-linked OTP verification, signed consent handle with expiry & revocation); (2) Persisted consent receipt + `"Revoke / Unlink AgriStack"` control in `Settings.jsx`; (3) Importing multi-season Digital Crop Survey (DCS) history per parcel rather than a single `cropDeclared` string.
- **Works offline?** **Yes** (the `1.2 s` mock import writes directly to Dexie offline; once imported, parcels remain available offline).
- **Marathi / Hindi / English UI coverage:** **Mostly Yes** (`landRegistry.*` modal copy is translated in `mr`/`hi`/`en`), **except** `consentScopes` (`['parcel boundary', 'land-use record', 'eligibility status']` in `mockProviders.js:81`) and `surveyNumber` strings render in English.
- **Backend dependency:** `POST /api/v1/land-registry/agristack/consent`, `GET /api/v1/land-registry/agristack/parcels` (UFSI / State Land Records / Digital Crop Survey gateway); **no call exists in `src/api/`**.
- **Smallest next step to move up one level (`2 -> 3`):** Implement backend UFSI/state-ROR adapter (`/api/v1/land-registry/agristack/*` or Setu/DigiLocker sandbox), persist signed consent artifacts (`consentId`, `grantedAt`, `expiresAt`, `scopes`) with revocation in `Settings.jsx`, and map historical Digital Crop Survey seasons into plot history (**~3–5 days**, subject to AgriStack sandbox credentials).

---

### Feature 14: Contingency sowing gates
*Plan requires: alert for alternative catch crops, threshold monitoring of sowing delays, recalculated risk for short-duration crops.*

- **Status:** **`1` (UI ONLY)** — `CatchCropAlert.jsx` renders a single static monsoon-delay banner on every `/farm` page load and navigates to `/recommender` without passing any context; zero sowing-delay threshold monitoring or short-duration risk recalculation exists.
- **Evidence:**
  - Banner component: `src/components/CatchCropAlert.jsx:1-60` (`const [visible, setVisible] = useState(true)` line 9).
  - Usage on `/farm`: `src/components/PlotList.jsx:261, 463-468` (`onUpdatePlan={() => navigate('/recommender')}`).
- **What works today / What is mocked / What is missing:**
  - *Works:* Renders an amber warning card with localized speech playback (`ListenButton`), dismiss button (in-memory `useState` only), and a button navigating to `/recommender`.
  - *Mocked/Hardcoded:* Always claims `"Monsoon Delayed by 18 Days — Long-duration Paddy is now high risk. Consider short-duration Moong (60 days) or Torai"` (`alerts.sowingTitle` / `alerts.sowingDetail` in `src/locales/*/translation.json`) regardless of calendar month, plot crops, or live Open-Meteo rainfall! Note also `"Torai"` (ridge gourd) is not even in `CROP_RULES` (`rotationEngine.js:1-11`).
  - *Missing vs. plan:* (1) **Threshold monitoring of sowing delays** (comparing current date + cumulative rainfall / soil moisture from `weather.js` against regional normal sowing cutoff dates for Kharif/Rabi crops); (2) **Recalculated risk for short-duration crops** (computing remaining growing degree-days / moisture window and dynamically filtering/re-scoring `50–70 day` catch crops like `moong`, `cowpea`, `black-gram` vs. penalizing `120–180 day` crops in `Recommender.jsx`); (3) Passing contingency mode (`?contingency=delayed-monsoon&maxDays=70`) into `/recommender`.
- **Works offline?** **Static banner renders offline.**
- **Marathi / Hindi / English UI coverage:** **Yes** (`alerts.sowingTag`, `alerts.sowingTitle`, `alerts.sowingDetail`, `alerts.sowingCta` are fully translated in `mr`/`hi`/`en`).
- **Backend dependency:** Can run locally using cached Open-Meteo precipitation + regional crop calendar cutoff table (`GET /api/v1/crop-calendar` optional); **no call exists in `src/api/`**.
- **Smallest next step to move up one level (`1 -> 2`):** Add a regional sowing-cutoff table (`cropId`, `normalSowingEnd`, `latestContingencyEnd`, `durationDays`), trigger `CatchCropAlert` only when calendar date + `db.weatherCache` rain/moisture cross the delay threshold for an unsown/at-risk plot, and pass `maxDurationDays` to `Recommender.jsx` to recalculate risk scores and filter catch crops (**~1 day**).

---

### Feature 15: Input dealer registry
*Plan requires: local dealer and seed availability, district inventory data, recommender score lowered when certified seed is unavailable.*

- **Status:** **`1` (UI ONLY)** — Searchable list of 3 hardcoded Goa dealers on `/farm` (with placeholder phone/map links), zero district inventory data, and zero connection to recommender crop scoring.
- **Evidence:**
  - Component: `src/components/DealerDirectory.jsx:1-217` (`DEALERS` lines 8–42, search filter lines 69–88, `tel:+919876543210` line 193, generic Google Maps link line 199), mounted at bottom of `src/components/PlotList.jsx:583`.
  - Secondary mock list: `src/services/market.js:538-555` (`fetchNearbyDealersForCrop` returning 2 hardcoded stores).
- **What works today / What is mocked / What is missing:**
  - *Works:* Text search filtering across 3 dealer cards (plus `?dealerQuery=` URL query param from `PestScanner.jsx:292`), localized UI (`mr`/`hi`/`en`), and `ListenButton` per dealer.
  - *Mocked/Hardcoded:* `DEALERS` (`DealerDirectory.jsx:8-42`) hardcodes 3 stores (`Goa State Co-op Marketing` in Mapusa, `Zuari Agro Inputs` in Panjim, `Krishi Seva Kendra` in Margao) with static English stock tags (`'Moong (Certified)'`, `'Trichoderma'`, etc.), identical dummy `href="tel:+919876543210"`, and generic `https://maps.google.com/?q=agriculture+store`.
  - *Missing vs. plan:* (1) **District/taluka seed & fertilizer inventory data** (SATHI seed portal / state agri department / FPO stock feed keyed by `cropId` and certification status); (2) **Lowering recommender score when certified seed is unavailable** (`rotationEngine.js` has zero reference to dealer inventory or seed stock); (3) Real dealer coordinates, distance calculation from farmer's plot, and real phone numbers.
- **Works offline?** **Static 3-card list filters offline.**
- **Marathi / Hindi / English UI coverage:** **Mostly Yes** (`dealers.*` UI labels, dealer names, and stock item names are translated via `dealers.items.*` in `mr`/`hi`/`en`).
- **Backend dependency:** `GET /api/v1/dealers?district=...&cropId=...` (district certified seed & input inventory); **no call exists in `src/api/`**.
- **Smallest next step to move up one level (`1 -> 2`):** Structure dealer inventory by canonical `cropId` + `{ certifiedSeedInStock: boolean, quantityKg, distanceKm, phone, lat, lng }` in Dexie/local dataset, compute real Haversine distance from plot centroid, and pass seed availability into `runOfflineRotationEngine()` to penalize crops lacking certified seed within district/radius and show a `"Certified seed low nearby"` warning badge (**~6–8 hours**).

---

### Feature 16: Mid-season satellite alarms
*Plan requires: voice notes for stress mitigation, Sentinel-2/SMAP data, moisture/stress anomalies mapped to advice.*

- **Status:** **`1` (UI ONLY)** — `VoiceAdvisory.jsx` plays one hardcoded translated voice script via Web Speech TTS; zero Sentinel-2, NASA SMAP, NDVI, NDWI, or satellite anomaly logic exists anywhere in the app.
- **Evidence:**
  - Component: `src/components/VoiceAdvisory.jsx:1-121` (mounted on `/farm` in `src/components/PlotList.jsx:579`, hardcoded `"0:45"` duration badge at line 99).
  - Static alert cards: `src/components/PlotList.jsx:55-83` (`ALERTS[0]`: `alerts.soilMoistureTitle` / `alerts.soilMoistureMessage`).
  - Landing page claim: `src/components/LandingPage.jsx:31` (`"Adapting Farms with NASA Data"`).
- **What works today / What is mocked / What is missing:**
  - *Works:* Tapping the circular play/stop button or `ListenButton` on `VoiceAdvisory.jsx` speaks `t('advisory.fullScript')` aloud in Marathi, Hindi, or English using `useVoice()`, with animated waveform bars while `isSpeaking` is true.
  - *Mocked/Hardcoded:* Single static translation string (`advisory.title`, `advisory.summary`, `advisory.fullScript` in `src/locales/*/translation.json`) plus hardcoded `"0:45"` label regardless of plot location, season, or actual moisture.
  - *Missing vs. plan:* (1) **Sentinel-2 (NDVI/NDWI 10 m) and NASA SMAP / NASA POWER root-zone soil moisture ingestion** for each plot's GeoJSON polygon in `db.plots`; (2) **Anomaly detection** (comparing current 10-day NDVI/moisture against historical baseline / crop growth-stage curve); (3) **Rule mapper** dynamically generating plot-specific stress mitigation advisories and voice notes (water stress, waterlogging, canopy vigor drop).
- **Works offline?** **Yes** (speaks the static bundled translation string offline if OS TTS voice is available).
- **Marathi / Hindi / English UI coverage:** **Yes** (`advisory.*` keys are fully translated in `mr`/`hi`/`en`).
- **Backend dependency:** `GET /api/v1/plots/:plotId/satellite-health` (backend querying Google Earth Engine / Copernicus Data Space Sentinel-2 + NASA POWER/SMAP APIs over plot GeoJSON); **no call exists in `src/api/`**.
- **Smallest next step to move up one level (`1 -> 2`):** Query public **NASA POWER Agroclimatology API** (`power.larc.nasa.gov/api/temporal/daily/point` for root-zone soil wetness `GWETROOT` & evapotranspiration — free, CORS-enabled, no key required!) for each saved plot centroid, cache in Dexie, detect moisture/heat anomalies against crop stage thresholds, and dynamically assemble the spoken `VoiceAdvisory` script per plot (**~1–1.5 days**; add Sentinel-2 NDVI backend endpoint for full `3` in **~3 days**).

---

### Feature 17: Subsidy & PMFBY matcher
*Plan requires: subsidy and insurance badges, policy and village-list parsing, subsidies included in the profit score.*

- **Status:** **`1` (UI ONLY)** — `SchemesHub.jsx` renders 3 static scheme cards whose action buttons (`"Check Eligibility"` / `"Apply Now"`) have no `onClick` handler, with zero village-list/notified-crop parsing, zero badges on recommender cards, and zero subsidy inclusion in profit scores.
- **Evidence:**
  - Route: `/schemes` (`src/App.jsx:482`).
  - Component: `src/components/SchemesHub.jsx:1-198` (`SCHEMES` lines 9–46, `verifiedCount` check lines 70–76 & 122–126, inert `<button type="button">` with **no `onClick`** lines 180–190).
  - Market MSP callout: `src/components/MarketCropDetail.jsx:1072-1094` (shows MSP from static `BASE_CROP_MARKET_SPECS` in `market.js:16-85`).
- **What works today / What is mocked / What is missing:**
  - *Works:* Displays 3 cards (`PM-KISAN`, `PMFBY`, `PKVY`), counts `isVerified` plots in `db.plots` to toggle a status badge (`"Eligible on X verified fields"` vs. `"Link AgriStack to check"`), and reads each card aloud via `ListenButton`.
  - *Mocked/Hardcoded:* `SCHEMES` (`SchemesHub.jsx:9-46`) is 3 static constants; `"Check Eligibility"` / `"Apply Now"` buttons (`lines 180-190`) have **no click handler at all**!
  - *Missing vs. plan:* (1) **Policy & notified village/crop list parsing** (matching farmer's state/district/taluka/village, landholding size, irrigation status, and season crop against PMFBY notified crops, NFSM pulse/oilseed minikit/seed subsidies, and PKVY clusters); (2) **Subsidy & PMFBY insurance badges on recommender result cards**; (3) **Including per-hectare crop subsidies (and PMFBY farmer premium deduction `1.5%` Rabi / `2%` Kharif) in the recommender profit score**; (4) Working eligibility checklist modal / official portal deep links.
- **Works offline?** **Static cards + Dexie `verifiedCount` check work offline.**
- **Marathi / Hindi / English UI coverage:** **Yes** (`schemes.*` keys are fully translated in `mr`/`hi`/`en`).
- **Backend dependency:** `GET /api/v1/schemes/match?district=...&village=...&crops=...` (PMFBY NCIP notified crop-village tables & state DBT scheme rules); **no call exists in `src/api/`**.
- **Smallest next step to move up one level (`1 -> 2`):** Add a structured scheme/PMFBY rule dataset keyed by crop family/ID, season, and district/village, wire working eligibility breakdown modals + official portal links on the `/schemes` buttons, render `"PMFBY 1.5% Insured"` / `"Pulse Subsidy +₹X/ha"` badges on `Recommender.jsx` cards, and fold net subsidy minus insurance premium into the profit calculator (**~1–1.5 days**).

---

### Feature 18: Warehouse & e-NWR locator
*Plan requires: map of cold storage within 30 km, WDRA registry, e-NWR suggestion for off-season prices.*

- **Status:** **`0` (NOT STARTED)** — Nothing implemented in the codebase (no route, component, service, map layer, Dexie store, or WDRA dataset).
- **Evidence:**
  - Checked all routes in `src/App.jsx:465-487`, all 27 components in `src/components/`, all services in `src/services/`, and all tables in `src/db/db.js:1-66`: **zero matches** for `warehouse`, `WDRA`, `e-NWR` / `eNWR`, or `cold storage` (only one generic static storage tip sentence `marketDetail.storageTipsBody` in `src/components/MarketCropDetail.jsx:1042`).
- **What works today / What is mocked / What is missing:**
  - *Works:* Nothing.
  - *Missing vs. plan:* (1) Leaflet/list locator of warehouses and cold storages within `30 km` of the farmer's plot centroid; (2) WDRA-registered warehouse directory (capacity, commodity accreditation, cold vs. dry storage, pledge finance availability); (3) **e-NWR off-season price arbitrage calculator** comparing immediate harvest sale vs. storing `N` months (`expectedOffSeasonPrice − storageFee − pledgeInterest` using `market.js` seasonal `bestMonths` curve).
- **Works offline?** **N/A (Not started).**
- **Marathi / Hindi / English UI coverage:** **No** (no translation keys exist).
- **Backend dependency:** `GET /api/v1/warehouses?lat=...&lng=...&radiusKm=30&cropId=...` (synced from WDRA registered warehouse directory); **no call exists in `src/api/`**.
- **Smallest next step to move up one level (`0 -> 1` or `0 -> 2`):** Add a WDRA Goa/Maharashtra warehouse JSON snapshot + Leaflet `30 km` radius map & e-NWR pledge-vs-sell-now net-gain calculator card inside `MarketCropDetail.jsx` (and `/warehouses` or `/market` tab) with `mr`/`hi`/`en` translations (**~1–1.5 days** to reach `2`).

---

## 3. Audit of Additional Plan Items (A–F)

---

### Item A: Phone-number login with one-time code (real, or demo code only)

- **Status:** **`2` (PROTOTYPE — Demo code `'123456'` active by default; real REST client implemented in `src/api/auth.js`)** — Full E.164 phone + 6-digit OTP UI and production HTTP adapter exist, **but** `VITE_USE_MOCKS` defaults to `'true'` and no backend/SMS service exists in the project, so the app runs purely on demo code `'123456'`.
- **Evidence:**
  - Route & UI: `/login` (`src/App.jsx:467`), `src/components/auth/Login.jsx:1-1582` (`CountryDialPicker`, 6-box OTP input, WebOTP `navigator.credentials.get` lines 579–618, demo hint banner & 1-tap `123456` auto-fill button lines 1014–1034), `src/layouts/AuthLayout.jsx:1-79`, `src/utils/phone.js:1-185` (`libphonenumber-js/mobile`).
  - Auth state & mode switch: `src/context/AuthContext.jsx:23` (`export const IS_MOCK_AUTH = (import.meta.env.VITE_USE_MOCKS ?? 'true') !== 'false'`).
  - Mock adapter (active): `src/services/auth/mockAuthAdapter.js:1-290` (`MOCK_OTP_CODE = '123456'` line 3, `MOCK_DELAY_MS = 350` line 12, `localStorage['fieldshift-mock-users']` line 4).
  - Real HTTP adapter (inactive until `VITE_USE_MOCKS=false`): `src/api/auth.js:1-66` & `src/api/client.js:1-154`.
- **What works today / What is mocked / What is missing:**
  - *Works:* Mobile number validation via `libphonenumber-js/mobile`, country dial picker, 6-digit paste/keyboard/WebOTP handling, 30s resend timer (`MAX_RESENDS_PER_PHONE = 3`), wrong-code attempt counter & lockout, voice-call OTP button (`handleResendOtp('voice')`), new-user profile completion step, RTL digit safety (`dir="ltr"`), masked phone display in header/Settings, and offline cached session restoration (`AuthContext.jsx:151-161`).
  - *Mocked/Hardcoded:* `MOCK_OTP_CODE = '123456'` (`mockAuthAdapter.js:3`) with `350 ms` `setTimeout` (`line 12`), prominent `"DEMO"` pill + `"Demo code: 123456"` button on `/login`, and user records stored in browser `localStorage['fieldshift-mock-users']`.
  - *Missing vs. plan:* Live backend auth service + SMS/Voice OTP delivery gateway (MSG91 / Twilio Verify) + `HttpOnly` refresh cookie endpoint so `VITE_USE_MOCKS=false` works in production.
- **Works offline?** **Yes for existing signed-in sessions** (`AuthContext.jsx:151-161` preserves cached user when `!navigator.onLine`; new OTP requests while offline correctly show `auth.offlineLoginNotice` in real mode, or run locally in mock mode).
- **Marathi / Hindi / English UI coverage:** **Yes** (`auth.*` keys are 100% translated in `mr`/`hi`/`en` with step-aware `ListenButton`).
- **Backend dependency:** `POST /api/v1/auth/otp/request`, `POST /api/v1/auth/otp/verify`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`, `GET /api/v1/me`, `PATCH /api/v1/me` — **calls DO exist in `src/api/auth.js:10-64`** via `src/api/client.js`!
- **Smallest next step to move up one level (`2 -> 3`):** Stand up the FastAPI/Node auth endpoints matching `docs/AUTH_PHONE_OTP.md` / `src/api/auth.js` wired to an SMS OTP provider (e.g., Twilio Verify or MSG91 DLT template) and build with `VITE_USE_MOCKS=false` (**~1–1.5 days**).

---

### Item B: Family-member role (a relative switches into a farmer's account with consent)

- **Status:** **`0` (NOT STARTED)** — No family-member / relative delegation role, invitation/consent flow, or multi-farmer switcher exists anywhere in the codebase.
- **Evidence:**
  - Role definitions: `src/context/RoleContext.jsx:8-42` (supports only `'farmer'` and `'extension'`), `src/services/auth/mockAuthAdapter.js:61-87`.
  - Account switch behavior: `src/App.jsx:160-172` and `src/components/auth/Login.jsx:849-867` (`"Not you? Switch account"` calls `logout()`, which invokes `clearUserDatabaseAndCaches()` at `src/context/AuthContext.jsx:63-84` and **deletes local Dexie plots** when a different phone logs in!).
- **What works today / What is mocked / What is missing:**
  - *Works:* Nothing for delegated family access.
  - *Missing vs. plan:* (1) Farmer granting OTP-verified delegation consent to a relative's phone number (read-only or edit permissions); (2) Account-context switcher (`"Viewing farm of: <Farmer Name>"` banner) allowing a relative to switch between their own account and a consented parent/relative's farm **without wiping local IndexedDB data**; (3) Audit attribution (`createdByUserId` vs. `farmOwnerId`).
- **Works offline?** **N/A (Not started).**
- **Marathi / Hindi / English UI coverage:** **No** (no translation keys exist).
- **Backend dependency:** `POST /api/v1/delegations/invite`, `POST /api/v1/delegations/accept`, `GET /api/v1/me/farms`; **no call exists in `src/api/`**.
- **Smallest next step to move up one level (`0 -> 1` or `0 -> 2`):** Namespace Dexie records by `farmOwnerId` (instead of wiping DB on switch), add a `"Family Access"` section in `Settings.jsx` to link a relative's phone number via OTP consent, and add a farm switcher in `AppHeader` (**~1.5–2 days** to reach `2`).

---

### Item C: Extension-worker desktop dashboard

- **Status:** **`1` (UI ONLY)** — Desktop role toggle (`hidden sm:flex`) opens `/group` (`GroupDashboard.jsx`), which renders static hardcoded English KPIs and a 5-farmer HTML table with zero real data, filtering, drill-down, or actions.
- **Evidence:**
  - Desktop toggle: `src/App.jsx:189-221` (`className="hidden ... sm:flex"`), `src/context/RoleContext.jsx:18-48`.
  - Dashboard component: `src/components/GroupDashboard.jsx:1-171`.
- **What works today / What is mocked / What is missing:**
  - *Works:* Role guard redirects unauthorized users away from `/group` (`App.jsx:490-509`), and desktop viewports (`>= 640px`) display the Farmer / Extension switcher when `user.roles` includes `'extension'`.
  - *Mocked/Hardcoded:* Static `KPI_CARDS` and 5-row `FARMERS` array (`GroupDashboard.jsx:13-50`); hidden completely in default mock login unless `VITE_MOCK_EXTENSION_PHONES` env var is set (`mockAuthAdapter.js:61-87`).
  - *Missing vs. plan:* Village/cluster filtering, clicking a farmer row to inspect their plots/soil/crop alerts, bulk advisory broadcast, seed/fertilizer procurement export, responsive/i18n support, and real data aggregation.
- **Works offline?** **Static JSX renders offline.**
- **Marathi / Hindi / English UI coverage:** **Partially translated header toggle** (`header.farmer`, `header.extension`), **0% translated dashboard body** (`GroupDashboard.jsx` is hardcoded English).
- **Backend dependency:** `GET /api/v1/extension/farmers`, `GET /api/v1/extension/clusters/:id/summary`; **no call exists in `src/api/`**.
- **Smallest next step to move up one level (`1 -> 2`):** Add search/village filter, farmer plot-detail drawer, CSV procurement export, `mr`/`hi`/`en` translations, and dynamic aggregation over Dexie/seeded multi-farmer plot records (**~1 day**).

---

### Item D: Onboarding (language, village, plots)

- **Status:** **`2` (PROTOTYPE)** — New phone numbers complete a profile step (`displayName` + `preferredLocale`) and `/farm` provides empty-state plot import/creation persisted to Dexie, **but** there is no guided onboarding wizard and **no village input anywhere in the app** (`village: ''` is saved empty).
- **Evidence:**
  - Language & name step (Step 2b): `src/components/auth/Login.jsx:1397-1573` (`displayName`, `preferredLocale`, consent checkbox -> `navigate('/farm')` at line 911).
  - Missing village field: `src/components/PlotList.jsx:336` (`village: ''` hardcoded on plot creation); `src/components/AddPlotModal.jsx:47-55` (no `village` state or input); `src/services/auth/mockAuthAdapter.js:228-252` (user profile stores `countryCode`, `displayName`, `preferredLocale` — no `village` or `district`).
  - First-plot empty states: `src/components/PlotList.jsx:493-511` (`"Import verified fields"` / `"Add Field"`), `src/components/Recommender.jsx:249-266, 488-524` (`"Quick-Add Demo Plot"`).
- **What works today / What is mocked / What is missing:**
  - *Works:* Language selection before/during sign-up (persisted to `localStorage` and user profile), name capture for new phone numbers, and creating or importing plots on `/farm` persisted to `db.plots`.
  - *Mocked/Hardcoded:* `PlotList.jsx:336` hardcodes `village: ''`; weather/market/schemes fallback defaults assume Goa (`15.4909, 73.8278` Panaji / Mapusa / Margao).
  - *Missing vs. plan:* (1) **Village / Taluka / District selection** during onboarding and plot creation (essential for village-level weather, nearby mandis, dealers, and PMFBY notified-village matching); (2) Guided 3-step first-run onboarding flow (`1. Language -> 2. Village -> 3. Add/Import First Plot`) before dropping a new farmer onto a complex multi-widget dashboard.
- **Works offline?** **Yes** (in mock mode, profile creation and Dexie plot creation work offline).
- **Marathi / Hindi / English UI coverage:** **Yes** (`auth.*`, `dashboard.*`, and `addField.*` keys are fully translated in `mr`/`hi`/`en`).
- **Backend dependency:** `PATCH /api/v1/me` (`src/api/auth.js:56-61` already exists and can carry `village`/`district`) + `POST /api/v1/plots`.
- **Smallest next step to move up one level (`2 -> 3`):** Add District/Taluka/Village selector (searchable offline village list + GPS reverse-lookup fallback) to `Login.jsx` Step 2b and `AddPlotModal.jsx`, populate `plot.village` and `user.village`, and guide new users with 0 plots directly into plot creation/import (**~6–8 hours**).

---

### Item E: Delete-my-data and consent/audit features

- **Status:** **`1` (UI ONLY)** — Signup and land-import modals gate actions behind consent checkboxes, **but** there is no `"Delete my data / Delete account"` feature, no consent revocation UI, no consent/audit log viewer, and logout leaves `priceAlerts`, `marketCache`, and `fieldshift-mock-users` behind on disk.
- **Evidence:**
  - Signup consent checkbox & modal: `src/components/auth/Login.jsx:171-226, 880-905, 1490-1533` (stores `consents: { privacyNoticeVersion: '2026-10', dataProcessing: true, smsMessages: true, acceptedAt }` inside `localStorage['fieldshift-mock-users']`).
  - Land registry consent modal (no persisted receipt): `src/components/LandRegistryConsentModal.jsx:64-207`, `src/components/AgriStackConsentModal.jsx:73` (promises revocation in Settings that does not exist).
  - Settings screen (no delete/consent controls): `src/components/Settings.jsx:618-634` (static text row `"Privacy: Stored on your phone"`, logout button lines 637–702).
  - Incomplete logout cleanup: `src/context/AuthContext.jsx:14-21, 63-84` (`clearUserDatabaseAndCaches` clears `plots`, `soilRecords`, `weatherCache`, `syncQueue`, **omitting** `db.priceAlerts`, `db.marketCache`, `localStorage['fieldshift-mock-users']`, `localStorage['fieldshift-market-favourites']`, and `localStorage['fieldshift-country']`).
- **What works today / What is mocked / What is missing:**
  - *Works:* Mandatory consent checkbox + privacy notice modal before completing registration (`Login.jsx`), and explicit consent modal before running mock land parcel import (`LandRegistryConsentModal.jsx`).
  - *Mocked/Hardcoded:* Static privacy row in `Settings.jsx:625`; unfulfilled claim `"You can revoke access anytime in Settings"` (`AgriStackConsentModal.jsx:73`).
  - *Missing vs. plan:* (1) **`"Delete my data & account"` button** with confirmation in `Settings.jsx` that deletes the entire IndexedDB database (`db.delete()`), clears all `fieldshift-*` `localStorage` keys (including `fieldshift-mock-users`), unregisters caches, and calls `DELETE /api/v1/me`; (2) **Consent & audit trail** table/screen showing timestamps of granted consents (privacy, SMS, AgriStack land fetch) with 1-tap **Revoke Consent** buttons.
- **Works offline?** **Local consent checkboxes work offline**; local data deletion could work offline if implemented, but does not exist today.
- **Marathi / Hindi / English UI coverage:** **Yes** for signup/land-import consent prompts; **No** for delete-my-data or audit/revocation (missing).
- **Backend dependency:** `DELETE /api/v1/me`, `GET /api/v1/me/consents`, `POST /api/v1/me/consents/:id/revoke`; **no call exists in `src/api/`**.
- **Smallest next step to move up one level (`1 -> 2`):** Add a `db.consents` audit table logging signup + land-registry consent timestamps, render a `"Privacy, Consents & Delete My Data"` card in `Settings.jsx` with working consent revocation and a `"Delete all my data"` action (`await db.delete()` + full `localStorage` wipe + `DELETE /api/v1/me` hook), and fix `clearUserDatabaseAndCaches()` to clear `priceAlerts` (**~4–6 hours**).

---

### Item F: Performance — first load under ~1 MB & behaviour on slow networks

- **Status:** **`2` (PROTOTYPE)** — Critical-path initial HTML + CSS + JS is **`499.90 kB` gzipped** (JS + CSS = **`498.77 kB` gzip**, passing `< 1 MB` gzipped), **but** the main JS chunk is `1.64 MB` uncompressed and Service Worker registration immediately precaches **182 files (`6,159.35 KiB` raw / ~`2.50 MB` transferred)** — including all 109 unused locale chunks — choking slow 2G/3G networks.
- **Evidence (Measured directly from `npm run build` & `dist/` files on disk):**
  - **Critical-Path First-Load Bundle (`dist/`):**
    - `dist/index.html`: `3.05 kB` (`3,050 B`) raw | **`1.13 kB` (`1,129 B`) gzip**
    - `dist/assets/index-CRStOH46.css`: `160.52 kB` (`160,527 B`) raw | **`25.24 kB` (`25,259 B`) gzip**
    - `dist/assets/index-ChfXYrgq.js`: `1,639.33 kB` (`1,639,330 B`) raw | **`473.53 kB` (`469,638 B` Node zlib) gzip** *(triggers Vite `> 500 kB` chunk size warning)*
    - **Total Initial Critical-Path JS + CSS:** **`1,799.85 kB` (`1.72 MiB`) raw | `498.77 kB` gzip**
    - **If active language is Marathi (`mr`) or Hindi (`hi`):** adds 1 lazy locale chunk (`40.18–51.75 kB` raw / **`15.83–17.07 kB` gzip**) -> **`~515.8 kB` total JS + CSS gzip**.
  - **Route Lazy Chunks (`src/App.jsx:29-30`):**
    - `dist/assets/LandingPage-C4qwFhHR.js`: `1.60 kB` raw | `0.81 kB` gzip
    - `dist/assets/MarketCropDetail-B2QcVzxZ.js`: `39.98 kB` raw | `8.89 kB` gzip
    - *(All other 9 route components — including Leaflet `PlotList`/`FieldMapper`/`DashboardMap` and Recharts `WeatherPanel`/`MarketInsights` — are statically imported in `src/App.jsx:16-28`!)*
  - **Service Worker Install Storm (`vite.config.js:64` -> `dist/sw.js`):**
    - `globPatterns: ['**/*.{js,css,html,ico,png,svg,woff,woff2}', 'crops/*-thumb.webp']`
    - Workbox output: **`precache 182 entries (6159.35 KiB)`**:
      - `109` lazy locale JS chunks (`dist/assets/translation-*.js`): `4,058.19 kB` raw / **`1,604.66 kB` (`1.60 MB`) gzip** downloaded even though the farmer uses 1–2 languages!
      - `60` crop thumbnails (`dist/crops/*-thumb.webp`): `388.64 kB`
      - Main JS + CSS + lazy route JS + HTML/SVGs: `~1,846 kB` raw / `~510 kB` gzip
      - **Total actual network transfer on first visit (page load + SW install):** **`~2.50 MB` transferred (`6.16 MB` uncompressed)** — **exceeds the `~1 MB` first-load budget by 2.5×!**
  - **Unused heavy dependencies in `package.json:21, 36`:** `@splinetool/react-spline` and `three` remain listed in `dependencies` (currently tree-shaken only because no file imports them, while `vite.config.js:116` still keeps a `spline-3d-assets` cache rule).
- **Behaviour on Slow Networks & Low-End Phones:**
  - *Good optimizations present:* `useLowEndOrReducedMotion()` (`src/components/auth/Login.jsx:48-55`, `src/layouts/AuthLayout.jsx:13-20`) disables Framer Motion animations and ambient blurs when `navigator.deviceMemory <= 2`; crop images use compact `128×128` WebP thumbnails (`~6.5 kB` avg) with `loading="lazy"` (`CropImage.jsx:117`) and `CacheFirst` 480px cards (`vite.config.js:75-83`); `LanguageContext.jsx` lazy-loads non-English JSONs (though `en/translation.json` is both statically and dynamically imported, triggering Vite's `[INEFFECTIVE_DYNAMIC_IMPORT]` warning).
  - *Slow-network problems:* (1) Background SW precaching of 109 unused locale chunks competes for bandwidth on 2G/3G right as the user requests an OTP or live weather; (2) Parsing `1.64 MB` of uncompressed JS on `/login` blocks main-thread startup on `1–2 GB` RAM Android phones because Leaflet, Recharts, Dexie, and all dashboard screens load eagerly before login; (3) `LanguageContext.jsx:115-119` fetches Google Fonts over the network when switching to Devanagari/non-Latin scripts; (4) `Recommender.jsx:279-297` adds an artificial `4,800 ms` `setTimeout` wait even offline.
- **Works offline?** **Yes, once initial SW precache completes.**
- **Marathi / Hindi / English UI coverage:** **N/A (Cross-cutting performance item).**
- **Backend dependency:** None (pure Vite/Workbox build & code-splitting configuration).
- **Smallest next step to move up one level (`2 -> 3`):**
  1. Add `'**/assets/translation-*.js'` to `workbox.globIgnores` in `vite.config.js:65` and add a `CacheFirst` `runtimeCaching` rule for `/assets/translation-.*\.js$` (cuts SW first-load precache by **`4.06 MB` raw / `1.60 MB` gzip** immediately — bringing total first-visit transfer including SW install under **`~900 kB`!**).
  2. Convert `Login`, `PlotList`, `FieldMapper`, `WeatherPanel`, `Recommender`, `SoilImport`, `MarketInsights`, `PestScanner`, `SchemesHub`, `GroupDashboard`, and `Settings` in `src/App.jsx:16-28` to `React.lazy()` + `manualChunks` (`vendor-maps`, `vendor-charts`, `vendor-motion`) so `/login` loads `< 160 kB` gzipped (**~2–3 hours**).

