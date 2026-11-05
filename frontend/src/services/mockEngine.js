// ============================================================
//  src/services/mockEngine.js
//  Field Shift PWA — Mock Data Engine
//
//  PURPOSE:
//    Centralises ALL fake/placeholder data that will be replaced
//    by real backend API calls during the production merge.
//
//    Every block is labelled with a prominent
//    🔴 BACKEND INTEGRATION POINT comment that tells the
//    Python / Node backend team EXACTLY what JSON shape to return.
//
//    Nothing in this file should survive past the first real
//    backend sprint. Delete mock implementations one-by-one as
//    real endpoints are wired in.
//
//  LANGUAGE RULE (for farmer-friendly UI copy):
//    ✅  "Adds natural fertilizer back to soil, saves ₹1,200 on Urea"
//    ❌  "Legume nitrogen fixation coefficient: 0.72"
// ============================================================


// ─────────────────────────────────────────────────────────────
// SECTION 1 — STARTUP DASHBOARD NOTIFICATIONS
// These feed into <StartupNotifications /> on the /farm route.
// ─────────────────────────────────────────────────────────────

/**
 * 🔴 BACKEND INTEGRATION POINT — Startup Notifications Feed
 *
 * Replace this function with a GET call to:
 *   GET /api/v1/dashboard/notifications?farmerId={farmerId}&locale=hi
 *
 * Expected JSON response shape:
 * {
 *   "notifications": [
 *     {
 *       "id": "uuid-string",
 *       "type": "market" | "weather" | "plot",
 *       "title": "Short headline (max 50 chars)",
 *       "body":  "One-sentence detail for the farmer (plain language, no jargon)",
 *       "icon":  "TrendingUp" | "CloudSun" | "Leaf",   // Lucide icon name
 *       "severity": "info" | "warning" | "success",
 *       "timestamp": "2026-10-30T08:00:00+05:30",
 *       "delayMs": 400   // stagger hint for the animation (optional, client can override)
 *     }
 *   ]
 * }
 *
 * MOCK DELAY: 0 ms (these are pre-baked; a real endpoint would add ~200-400 ms latency)
 */
export function getMockStartupNotifications() {
  // 🔴 BACKEND INTEGRATION POINT — replace entire return value with live API response
  return [
    {
      id: 'notif-market-1',
      type: 'market',
      typeKey: 'notifications.types.market',
      titleKey: 'notifications.marketRiseTitle',
      bodyKey: 'notifications.marketRiseBody',
      params: {
        cropId: 'cashew',
        pct: 5,
        market: 'Mapusa',
        price: 8400,
        diff: 400,
        unitKey: 'market.unitPerQuintal',
      },
      icon: 'TrendingUp',
      severity: 'success',
      delayMs: 200,
    },
    {
      id: 'notif-weather-1',
      type: 'weather',
      typeKey: 'notifications.types.weather',
      titleKey: 'notifications.clearSkiesTitle',
      bodyKey: 'notifications.clearSkiesBody',
      params: {
        days: 3,
      },
      icon: 'CloudSun',
      severity: 'info',
      delayMs: 900,
    },
    {
      id: 'notif-plot-1',
      type: 'plot',
      typeKey: 'notifications.types.plot',
      titleKey: 'notifications.soilHealthGoodTitle',
      bodyKey: 'notifications.soilHealthGoodBody',
      params: {
        moisture: 62,
        seasonKey: 'recommender.seasonNames.Rabi',
      },
      icon: 'Leaf',
      severity: 'success',
      delayMs: 1600,
    },
    {
      id: 'notif-market-2',
      type: 'market',
      typeKey: 'notifications.types.market',
      titleKey: 'notifications.ureaSubsidyTitle',
      bodyKey: 'notifications.ureaSubsidyBody',
      params: {
        market: 'Panaji',
        bagKg: 25,
        price: 266,
      },
      icon: 'Package',
      severity: 'warning',
      delayMs: 2400,
    },
  ];
}


// ─────────────────────────────────────────────────────────────
// SECTION 2 — RECOMMENDER MULTI-STEP LOADING MESSAGES
// ─────────────────────────────────────────────────────────────

/**
 * 🔴 BACKEND INTEGRATION POINT — Recommender Analysis Steps
 *
 * When the real ML recommendation engine is live, these steps
 * should be driven by Server-Sent Events (SSE) or WebSocket
 * progress frames so the UI reflects genuine computation stages.
 *
 * SSE stream endpoint:
 *   GET /api/v1/recommend/stream?plotId={id}&season={season}&previousCrop={crop}
 *
 * Each SSE event:
 * { "step": 1, "label": "Step name", "icon": "Microscope", "durationHint": 1200 }
 *
 * Final SSE event:
 * { "step": "DONE", "recommendations": [ ...see Section 3... ] }
 *
 * MOCK: Fixed six-step sequence, each 800 ms, total about 5 s.
 */
export const RECOMMENDER_LOADING_STEPS = [
  {
    id: 'field-details',
    titleKey: 'recommender.stepTitles.fieldDetails',
    detailKey: 'recommender.stepDetails.fieldDetails',
    icon: 'Microscope',
    durationMs: 800,
  },
  {
    id: 'soil-history',
    titleKey: 'recommender.stepTitles.soilHistory',
    detailKey: 'recommender.stepDetails.soilHistory',
    icon: 'Leaf',
    durationMs: 800,
  },
  {
    id: 'weather',
    titleKey: 'recommender.stepTitles.weather',
    detailKey: 'recommender.stepDetails.weather',
    icon: 'CloudRain',
    durationMs: 800,
  },
  {
    id: 'crop-families',
    titleKey: 'recommender.stepTitles.cropFamilies',
    detailKey: 'recommender.stepDetails.cropFamilies',
    icon: 'Layers',
    durationMs: 800,
  },
  {
    id: 'market',
    titleKey: 'recommender.stepTitles.market',
    detailKey: 'recommender.stepDetails.market',
    icon: 'TrendingUp',
    durationMs: 800,
  },
  {
    id: 'rotation-plan',
    titleKey: 'recommender.stepTitles.rotationPlan',
    detailKey: 'recommender.stepDetails.rotationPlan',
    icon: 'Sprout',
    durationMs: 800,
  },
];

/** Total mock analysis delay (ms). Sum of all step durations. */
export const TOTAL_MOCK_DELAY_MS = RECOMMENDER_LOADING_STEPS.reduce(
  (acc, s) => acc + s.durationMs,
  0
); // → 3000 ms

/**
 * MOCK: replace with the real AgriStack API call.
 */
export async function importAgriStackPlots() {
  await new Promise((resolve) => setTimeout(resolve, 1500));

  return [
    {
      name: 'Bardez Cashew Block',
      village: 'Mapusa',
      surveyNumber: 'Survey 145/2A',
      primaryCrop: 'Cashew',
      area: '1.8',
      areaUnit: 'hectares',
      areaHectares: 1.8,
      coordinates: [[15.5938, 73.8087], [15.5961, 73.8122], [15.5937, 73.8151], [15.5914, 73.8114]],
      boundaryCoordinates: [[15.5938, 73.8087], [15.5961, 73.8122], [15.5937, 73.8151], [15.5914, 73.8114]],
      isVerified: true,
      source: 'agristack',
      verifiedAt: new Date().toISOString(),
      serverId: null,
    },
    {
      name: 'Assagao Paddy Plot',
      village: 'Assagao',
      surveyNumber: 'Survey 88/1B',
      primaryCrop: 'Paddy',
      area: '1.2',
      areaUnit: 'hectares',
      areaHectares: 1.2,
      coordinates: [[15.5949, 73.7704], [15.5972, 73.773], [15.5956, 73.776], [15.5929, 73.7734]],
      boundaryCoordinates: [[15.5949, 73.7704], [15.5972, 73.773], [15.5956, 73.776], [15.5929, 73.7734]],
      isVerified: true,
      source: 'agristack',
      verifiedAt: new Date().toISOString(),
      serverId: null,
    },
    {
      name: 'Parra Vegetable Field',
      village: 'Parra',
      surveyNumber: 'Survey 212/4C',
      primaryCrop: 'Vegetables',
      area: '0.9',
      areaUnit: 'hectares',
      areaHectares: 0.9,
      coordinates: [[15.6121, 73.8267], [15.614, 73.8292], [15.6122, 73.8311], [15.6104, 73.8288]],
      boundaryCoordinates: [[15.6121, 73.8267], [15.614, 73.8292], [15.6122, 73.8311], [15.6104, 73.8288]],
      isVerified: true,
      source: 'agristack',
      verifiedAt: new Date().toISOString(),
      serverId: null,
    },
  ];
}


// ─────────────────────────────────────────────────────────────
// SECTION 3 — CROP RECOMMENDATION RESULT SCHEMA (Documentation)
// ─────────────────────────────────────────────────────────────

/**
 * 🔴 BACKEND INTEGRATION POINT — Crop Recommendation Results
 *
 * POST /api/v1/recommend
 * Request body:
 * {
 *   "plotId": "string | number",
 *   "season": "Rabi" | "Kharif" | "Zaid",
 *   "previousCrop": "string",
 *   "areaHectares": number
 * }
 *
 * Expected response body (array of max 3 ranked crops):
 * [
 *   {
 *     "id": "chickpea",
 *     "name": "Chickpea (Desi Chana)",
 *     "localName": "Chana",
 *     "family": "legume",
 *     "seasons": ["Rabi"],
 *     "duration": "100 - 110 Days",
 *     "waterNeed": "Low — only 1 or 2 watering sessions needed",
 *     "soilHealthScore": 96,
 *     "rank": 1,
 *     "rankTag": "#1 Best Rotation Fit",
 *     "plainReason": "This crop puts natural fertilizer back into your soil on its own — saving you roughly ₹2,064 on Urea next season. It also uses water stored deep underground, so you only need to water it once or twice all season.",
 *     "netReturn": 120000,
 *     "netReturnFormatted": "₹1,20,000 / plot",
 *     "baselineReturn": 100800,
 *     "netReturnDelta": "+19% vs a typical repeat crop",
 *     "fertilizerName": "Urea",
 *     "fertilizerReductionKg": 86,
 *     "fertilizerCostSavings": "₹2,064 estimated Urea savings",
 *     "recommendedBadge": "Best Soil Balance",
 *     "waterSavingsPct": 45
 *   }
 * ]
 *
 * NOTES FOR BACKEND TEAM:
 *  1. Keep plainReason conversational — max 2 sentences, no jargon.
 *  2. netReturnDelta must start with "+" so the badge renders correctly.
 *  3. Sort by soilHealthScore DESC (already done by offline engine).
 */
export const MOCK_RECOMMENDATION_RESULT_SCHEMA = {
  _comment: 'Documentation only — mirrors what runOfflineRotationEngine() returns.',
  requiredFields: [
    'id', 'name', 'localName', 'family', 'seasons', 'duration', 'waterNeed',
    'soilHealthScore', 'rank', 'rankTag', 'plainReason',
    'netReturn', 'netReturnFormatted', 'baselineReturn', 'netReturnDelta',
    'fertilizerName', 'fertilizerReductionKg', 'fertilizerCostSavings',
    'recommendedBadge', 'waterSavingsPct',
  ],
};


// ─────────────────────────────────────────────────────────────
// SECTION 4 — MARKET PRICE MOCK DATA
// ─────────────────────────────────────────────────────────────

/**
 * 🔴 BACKEND INTEGRATION POINT — Live APMC Mandi Prices
 *
 * Replace with:
 *   GET /api/v1/market/prices?state=GOA&crops=cashew,rice,coconut,areca
 *
 * Expected JSON response shape:
 * {
 *   "updatedAt": "2026-10-30T06:00:00+05:30",
 *   "mandi": "Panaji APMC",
 *   "prices": [
 *     {
 *       "cropId": "cashew",
 *       "cropName": "Cashew (Raw)",
 *       "localName": "Kaju",
 *       "unit": "quintal",
 *       "priceToday": 8400,
 *       "pricePrevious": 8000,
 *       "changePercent": 5.0,
 *       "trend": "up" | "down" | "flat"
 *     }
 *   ]
 * }
 *
 * Data source: eNAM API or Agmarknet webscraper microservice.
 */
export const MOCK_MARKET_PRICES = [
  // 🔴 BACKEND INTEGRATION POINT — replace each item with live API row
  { cropId: 'cashew', nameKey: 'crops.cashew.name', localNameKey: 'crops.cashew.localName', unitKey: 'market.units.perQuintal', priceToday: 8400, pricePrevious: 8000, changePercent: 5.0, trend: 'up' },
  { cropId: 'rice', nameKey: 'crops.rice.name', localNameKey: 'crops.rice.localName', unitKey: 'market.units.perQuintal', priceToday: 2150, pricePrevious: 2150, changePercent: 0.0, trend: 'flat' },
  { cropId: 'coconut', nameKey: 'crops.coconut.name', localNameKey: 'crops.coconut.localName', unitKey: 'market.units.per100Nuts', priceToday: 1800, pricePrevious: 1920, changePercent: -6.25, trend: 'down' },
  { cropId: 'arecanut', nameKey: 'crops.arecanut.name', localNameKey: 'crops.arecanut.localName', unitKey: 'market.units.perQuintal', priceToday: 42000, pricePrevious: 40500, changePercent: 3.7, trend: 'up' },
];


// ─────────────────────────────────────────────────────────────
// SECTION 5 — WEATHER FORECAST MOCK DATA
// ─────────────────────────────────────────────────────────────

/**
 * 🔴 BACKEND INTEGRATION POINT — 3-Day Weather Forecast
 *
 * Replace with:
 *   GET /api/v1/weather/forecast?lat={lat}&lon={lon}&days=3
 *
 * Expected JSON response shape:
 * {
 *   "location": "Panaji, Goa",
 *   "updatedAt": "2026-10-30T06:00:00+05:30",
 *   "days": [
 *     {
 *       "date": "2026-10-30",
 *       "label": "Today",
 *       "condition": "Clear" | "Partly Cloudy" | "Rain",
 *       "icon": "Sun" | "CloudSun" | "CloudRain",
 *       "tempMax": 34,
 *       "tempMin": 24,
 *       "rainMm": 0,
 *       "humidity": 62,
 *       "farmerTip": "Good day to apply foliar spray."
 *     }
 *   ]
 * }
 *
 * Data source: OpenMeteo (free, no API key) or IMD XML feed.
 */
export const MOCK_WEATHER_FORECAST = [
  // 🔴 BACKEND INTEGRATION POINT — replace with live weather data
  { date: '2026-10-30', conditionKey: 'weather.clear', icon: 'Sun', tempMax: 34, tempMin: 24, rainMm: 0, humidity: 58, farmerTipKey: 'weather.adviceSpray' },
  { date: '2026-10-31', conditionKey: 'weather.cloudy', icon: 'CloudSun', tempMax: 32, tempMin: 23, rainMm: 2, humidity: 64, farmerTipKey: 'weather.adviceIrrigate' },
  { date: '2026-11-01', conditionKey: 'weather.clear', icon: 'Sun', tempMax: 35, tempMin: 25, rainMm: 0, humidity: 55, farmerTipKey: 'weather.adviceSowing' },
];


// ─────────────────────────────────────────────────────────────
// SECTION 6 — SESSION CACHE HELPERS
// ─────────────────────────────────────────────────────────────

/** Storage key for the recommender session-animation cache. */
export const RECOMMENDER_CACHE_KEY = 'fieldshift_recommenderCached';

/**
 * Returns true if the farmer has already run the recommender
 * once in this browser session (animation should be skipped).
 *
 * 🔴 BACKEND INTEGRATION POINT (minor):
 *   When the backend is live, consider persisting this server-side
 *   per farmerId so it survives across sessions and devices.
 *   For offline-first, sessionStorage (cleared on browser close) is correct.
 */
export function hasRecommenderCache() {
  try {
    return sessionStorage.getItem(RECOMMENDER_CACHE_KEY) === 'true';
  } catch {
    return false; // private browsing or storage quota exceeded — silently degrade
  }
}

/** Call once after the 3-step loading sequence completes. */
export function markRecommenderCached() {
  try {
    sessionStorage.setItem(RECOMMENDER_CACHE_KEY, 'true');
  } catch { /* storage unavailable — animation will replay; acceptable trade-off */ }
}

/** Clears the cache flag (useful for dev/testing or user-triggered reset). */
export function clearRecommenderCache() {
  try {
    sessionStorage.removeItem(RECOMMENDER_CACHE_KEY);
  } catch { /* no-op */ }
}
