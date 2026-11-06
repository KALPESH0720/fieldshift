# Field Shift: Project Architecture & Status Report

## Executive Summary

**Field Shift** is an offline-first, smart agriculture Progressive Web App (PWA) specifically designed for farmers in Goa, India. The application addresses the critical challenges of unreliable connectivity in rural areas and the need for precision geospatial data management. By providing a robust, mobile-centric interface, Field Shift empowers farmers to manage their plots, track crop health, and access vital market and weather information without requiring a constant internet connection.

The project bridges the gap between traditional farming practices and modern digital agriculture. It simplifies complex tasks such as field boundary mapping, crop mix optimization, and government data integration (AgriStack), providing a unified dashboard that serves as a digital companion for daily farm operations. Through Field Shift, farmers gain data-driven insights that lead to better resource allocation and improved crop yields.

## Tech Stack & Architecture

- **Frontend Framework:** Built with **React 19** and **Vite** for a reactive and component-based UI.
- **Styling:** Utilizes **Tailwind CSS v4** for a modern, utility-first design system that ensures a responsive and accessible interface.
- **Animations:** **Framer Motion** provides smooth, hardware-accelerated transitions and modal animations, enhancing the premium feel of the PWA.
- **Iconography:** **Lucide React** for a consistent and lightweight icon set.

### Offline-First Strategy
The core of Field Shift's reliability is its **Offline-First** architecture.
- **Storage:** Powered by **Dexie.js**, a minimalist wrapper for **IndexedDB**. This allows all farm data, crop rules, and weather caches to be stored locally on the device.
- **Synchronization:** A **Sync Queue (Outbox)** pattern is implemented. All mutations (Add/Edit/Delete) are first committed to a local `syncQueue` table. This ensures zero-latency user interactions and data persistence even if the app is closed while offline.

### Mapping Stack
Geospatial features are handled by a high-performance mapping stack:
- **React Leaflet:** For rendering interactive maps with specialized layers.
- **Turf.js:** Used for client-side geospatial calculations, specifically for calculating field area from drawn polygons.
- **Google Hybrid Tiles:** Provides high-resolution satellite imagery overlaid with road and label data for precise field identification.

### Structural Patterns (Nuclear Fixes)
To solve rendering and z-index issues common with React Leaflet in complex UI layouts:
- **Strict Mutual Exclusion:** A specialized rendering pattern in `PlotList.jsx` ensures that the Map and Modals are never mounted simultaneously. When the map is active, all other modal components are unmounted to prevent layout collapse and overlapping.
- **Bulletproof Resizer:** The `FieldMapper` includes a `MapResizer` component that forces Leaflet to recalculate container dimensions multiple times during mount, ensuring the map never renders as a collapsed grey box.
- **React Portals:** Modals use `createPortal` to mount at the root of the DOM, ensuring they are never constrained by parent layout overflow or relative positioning.

## Feature Breakdown

### Dashboard & Insights
- **Live Weather:** Multi-day forecast with current conditions (Partly Cloudy, Temperature, Humidity) via Open-Meteo integration.
- **Market Trends:** Live APMC (Agricultural Produce Market Committee) rates for Raw Cashews, featuring dynamic sparkline charts and trend analysis.
- **Smart Alerts:** Contextual notifications for irrigation needs, high-temperature warnings, and operation confirmations.

### Field Management
- **Manual Mapping (FieldMapper):** An intuitive drawing interface where farmers can tap to define plot boundaries. Area is calculated in real-time using Turf.js.
- **Verified Data (AgriStack):** A dedicated consent flow allows farmers to authorize the import of government-verified plot boundaries and soil health records (AgriStack ID integration).

## Data Flow & Sync Map

The application uses **Dexie.js** for all data persistence. Mutations are tracked via a `syncQueue` table to facilitate future backend integration.

### Data Map

| Feature / Module | File Location | Operation / Method | Payload Structure | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Field Management** | `PlotList.jsx` | `db.plots.add` | `{ name, area, areaUnit, boundaryCoordinates, ... }` | Offline Dexie |
| **Sync Tracking** | `PlotList.jsx` | `db.syncQueue.add` | `{ action: 'CREATE_PLOT', payload: plotToSave, status: 'pending' }` | Offline Dexie |
| **Crop Planning** | `Recommender.jsx` | `db.syncQueue.add` | `{ action: 'ASSIGN_PLOT_ROTATION', payload: { plotId, cropId, ... }, status: 'pending' }` | Offline Dexie |
| **Area Calculation** | `AddPlotModal.jsx` | `turf.area` | `polygon([coordinates])` | Client-side (Turf.js) |
| **AgriStack Sync** | `AgriStackConsentModal.jsx` | `onImport` (Mock) | N/A (Triggers parent sync handler) | Mocked API |
| **Plot Retrieval** | `PlotList.jsx` | `useLiveQuery` | `db.plots.toArray()` | Reactive Dexie |
| **Weather Cache** | `db.js` | `weatherCache` table | `{ id, updatedAt, data }` | Schema Defined |

### Sync Queue Analysis
The `syncQueue` table in `db.js` acts as an **Audit Log** and **Outbox**. Each entry contains an `id`, `action`, `payload`, `status` (pending/synced/error), and `timestamp`. To transition to a live server, a Background Sync worker will be required to process these items when connectivity is detected.

## Authentication (Phone Number + 6-Digit SMS OTP Only)

Field Shift uses **mobile phone number + 6-digit one-time SMS code (OTP)** as its sole authentication method. Email addresses and passwords are not used anywhere in the application.

- **Single Entry Point (`/login`):** Shared 2-step flow for both returning farmers and first-time sign-ups (`/signup` and `/forgot-password` redirect to `/login`).
  1. **Step 1 (Phone Input):** Searchable country dial-code selector (flag + dial code, defaults from detected region/language with fallback to `+91` India) + mobile number parsed, validated, and formatted to E.164 (`+919876543210`) via `libphonenumber-js/mobile`.
  2. **Step 2 (6-Digit OTP):** 6 single-digit numeric inputs (`inputMode="numeric"`, `autoComplete="one-time-code"`, Web OTP API SMS autofill, clipboard paste, auto-advance, backspace navigation,auto-submit on 6th digit, 30s resend countdown with max 3 resends). For new phone numbers (`isNewUser: true`), prompts for the farmer's name, preferred language, and SMS/privacy consent after code verification.
- **Accessibility & Low-End Device Support:** Includes a `"Listen"` TTS button (`useVoice`), compact language picker, theme toggle, offline banner, and automatic animation reduction on low-RAM (`navigator.deviceMemory <= 2`) or `prefers-reduced-motion` devices.
- **Shared-Phone Safety:** Displays the farmer's masked phone number (`+91 ••••• ••210`) in the header and `Settings.jsx` along with a **"Not you? Switch user"** action that revokes the session, clears user-specific IndexedDB tables (`plots`, `soilRecords`, `weatherCache`, `syncQueue`), and warns before logging out if `db.syncQueue` has unsynced offline changes.
- **Demo / Mock Mode (`VITE_USE_MOCKS=true`):**
  - Default in local development (`VITE_USE_MOCKS` defaults to `true` unless set to `'false'`).
  - Uses `src/services/auth/mockAuthAdapter.js`, displays a **Demo** badge and hint (`Demo mode: use code 123456`), accepts only code `123456`, and persists registered demo phone numbers in `localStorage` (`fieldshift-mock-users`) so both first-time sign-up and returning login work offline.
  - Set `VITE_USE_MOCKS=false` and `VITE_API_BASE_URL=/api/v1` to connect to the real backend endpoints (`POST /auth/otp/request`, `POST /auth/otp/verify`, `PATCH /me`, `GET /me`, `POST /auth/refresh`, `POST /auth/logout`) with `credentials: 'include'`.
- **Specifications:** See [`docs/AUTH_PHONE_OTP.md`](docs/AUTH_PHONE_OTP.md), [`docs/openapi.yaml`](docs/openapi.yaml), and [`docs/db-schema.sql`](docs/db-schema.sql).

## Next Steps

1. **Service Worker Integration:** Implement a full PWA Service Worker to enable background synchronization of the `syncQueue` and provide asset caching for offline reliability.
2. **Multilingual Support (Konkani/Marathi):** Expand the internationalization layer to support local Goan languages.
3. **Boundary Validation Logic:** Add client-side validation to prevent overlapping plot boundaries and ensure polygons are valid.
