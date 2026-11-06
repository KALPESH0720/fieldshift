import { db } from '../db/db';
import { CROPS, getCropById, resolveKnownCrop } from '../data/crops';
import { getSavedCountry } from './landRegistry/registry';

const FAVOURITES_KEY = 'fieldshift-market-favourites';
const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== 'false';
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const REGIONAL_MARKETS = {
  IN: [
    { id: 'mapusa', name: 'Mapusa APMC', region: 'North Goa', distanceKm: 8 },
    { id: 'margao', name: 'Margao APMC', region: 'South Goa', distanceKm: 18 },
    { id: 'ponda', name: 'Ponda Mandi', region: 'Central Goa', distanceKm: 14 },
    { id: 'belagavi', name: 'Belagavi APMC', region: 'Karnataka', distanceKm: 86 },
    { id: 'kolhapur', name: 'Kolhapur Mandi', region: 'Maharashtra', distanceKm: 138 },
  ],
  US: [
    { id: 'fresno', name: 'Fresno Central Hub', region: 'California', distanceKm: 12 },
    { id: 'salinas', name: 'Salinas Valley Exchange', region: 'California', distanceKm: 28 },
    { id: 'des-moines', name: 'Des Moines Grain Terminal', region: 'Iowa', distanceKm: 45 },
    { id: 'omaha', name: 'Omaha Regional Co-op', region: 'Nebraska', distanceKm: 74 },
  ],
  BR: [
    { id: 'ceagesp', name: 'CEAGESP São Paulo', region: 'SP', distanceKm: 16 },
    { id: 'campinas', name: 'CEASA Campinas', region: 'SP', distanceKm: 34 },
    { id: 'curitiba', name: 'CEASA Curitiba', region: 'PR', distanceKm: 68 },
  ],
  DEFAULT: [
    { id: 'central', name: 'Central Regional Market', region: 'District Hub', distanceKm: 10 },
    { id: 'north-hub', name: 'Northern Growers Exchange', region: 'North Zone', distanceKm: 22 },
    { id: 'south-coop', name: 'Southern Farmers Co-op', region: 'South Zone', distanceKm: 31 },
    { id: 'coastal-terminal', name: 'Wholesale Agro Terminal', region: 'Port Zone', distanceKm: 54 },
  ],
};

// Base prices in INR/kg (or regional equivalent) for realistic agronomy & market metrics
const BASE_CROP_MARKET_SPECS = {
  coconut: { pricePerKg: 38, displayPrice: 1840, unit: '₹/100 nuts', variety: 'Tall variety (100 nuts)', grade: 'Grade A', trendBias: 0.08 },
  cashew: { pricePerKg: 185, displayPrice: 185, unit: '₹/kg', variety: 'Raw Whole Nut', grade: 'FAQ Standard', trendBias: -0.03 },
  arecanut: { pricePerKg: 420, displayPrice: 420, unit: '₹/kg', variety: 'Chali / White Supari', grade: 'FAQ Grade', trendBias: 0.05 },
  'areca-nut': { pricePerKg: 420, displayPrice: 420, unit: '₹/kg', variety: 'Chali / White Supari', grade: 'FAQ Grade', trendBias: 0.05 },
  paddy: { pricePerKg: 23, displayPrice: 2300, unit: '₹/qtl', variety: 'Jyoti / Jaya', grade: 'FAQ Common', trendBias: 0.02 },
  rice: { pricePerKg: 34, displayPrice: 3400, unit: '₹/qtl', variety: 'Sona Masoori', grade: 'Grade A', trendBias: 0.04 },
  wheat: { pricePerKg: 25.5, displayPrice: 2550, unit: '₹/qtl', variety: 'Sharbati / Lokwan', grade: 'FAQ', trendBias: 0.03 },
  maize: { pricePerKg: 22.5, displayPrice: 2250, unit: '₹/qtl', variety: 'Yellow Hybrid', grade: 'FAQ', trendBias: 0.02 },
  banana: { pricePerKg: 32, displayPrice: 78, unit: '₹/doz', variety: 'Nendran / Robusta', grade: 'Grade A', trendBias: 0.06 },
  mango: { pricePerKg: 340, displayPrice: 340, unit: '₹/kg', variety: 'Alphonso / Mankurad', grade: 'Export Grade', trendBias: 0.04 },
  onion: { pricePerKg: 28, displayPrice: 2800, unit: '₹/qtl', variety: 'Nashik Red', grade: 'Medium A', trendBias: 0.09 },
  potato: { pricePerKg: 21, displayPrice: 2100, unit: '₹/qtl', variety: 'Jyoti / Kufri', grade: 'Grade A', trendBias: -0.02 },
  tomato: { pricePerKg: 26, displayPrice: 2600, unit: '₹/qtl', variety: 'Hybrid Round', grade: 'Grade A', trendBias: 0.07 },
  chilli: { pricePerKg: 165, displayPrice: 165, unit: '₹/kg', variety: 'Byadgi / Khola', grade: 'Select', trendBias: 0.05 },
  groundnut: { pricePerKg: 68, displayPrice: 6800, unit: '₹/qtl', variety: 'Bold Pod', grade: 'FAQ', trendBias: 0.03 },
  chickpea: { pricePerKg: 58, displayPrice: 5800, unit: '₹/qtl', variety: 'Desi Chana', grade: 'FAQ', trendBias: 0.02 },
  soybean: { pricePerKg: 49, displayPrice: 4900, unit: '₹/qtl', variety: 'Yellow JS-335', grade: 'FAQ', trendBias: -0.01 },
  cotton: { pricePerKg: 72, displayPrice: 7200, unit: '₹/qtl', variety: 'Long Staple', grade: 'FAQ', trendBias: 0.03 },
  sugarcane: { pricePerKg: 3.4, displayPrice: 340, unit: '₹/qtl', variety: 'Co-86032', grade: 'FRP Standard', trendBias: 0.01 },
  turmeric: { pricePerKg: 145, displayPrice: 14500, unit: '₹/qtl', variety: 'Salem Finger', grade: 'Polished', trendBias: 0.06 },
};

const DEFAULT_FEATURED_IDS = [
  'coconut',
  'cashew',
  'arecanut',
  'paddy',
  'banana',
  'mango',
  'onion',
  'tomato',
  'potato',
  'chilli',
  'wheat',
  'rice',
  'groundnut',
  'chickpea',
  'soybean',
  'cotton',
  'sugarcane',
  'maize',
];

function hashString(str = '') {
  let h = 2166136261;
  for (let i = 0; i < str.length; i += 1) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return Math.abs(h >>> 0);
}

function seededRand(seed) {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
}

export function getRegionalMarkets(countryCode) {
  const code = (countryCode || getSavedCountry() || 'IN').toUpperCase();
  return REGIONAL_MARKETS[code] || REGIONAL_MARKETS.IN || REGIONAL_MARKETS.DEFAULT;
}

const UNIT_KEYS_BY_UNIT = {
  '₹/100 nuts': { shortKey: 'market.units.short100Nuts', speakKey: 'market.units.per100Nuts' },
  '₹/kg': { shortKey: 'market.units.shortKg', speakKey: 'market.units.perKg' },
  '₹/qtl': { shortKey: 'market.units.shortQuintal', speakKey: 'market.units.perQuintal' },
  '₹/doz': { shortKey: 'market.units.shortDozen', speakKey: 'market.units.perDozen' },
};

function enrichSpecWithUnitKeys(spec) {
  const unitMeta = UNIT_KEYS_BY_UNIT[spec.unit] || UNIT_KEYS_BY_UNIT['₹/kg'];
  return {
    ...spec,
    unitKey: unitMeta.shortKey,
    unitSpeakKey: unitMeta.speakKey,
  };
}

function getSpecForCrop(crop) {
  const existing = BASE_CROP_MARKET_SPECS[crop.id];
  if (existing) return enrichSpecWithUnitKeys(existing);

  const seed = hashString(crop.id);
  if (crop.mspInrPerQuintal) {
    const modalQtl = Math.round(crop.mspInrPerQuintal * (1.04 + (seed % 12) * 0.01));
    return enrichSpecWithUnitKeys({
      pricePerKg: Number((modalQtl / 100).toFixed(1)),
      displayPrice: modalQtl,
      unit: '₹/qtl',
      variety: 'FAQ Standard (per quintal)',
      grade: 'FAQ Grade',
      trendBias: ((seed % 15) - 6) * 0.01,
    });
  }

  const perKg = 35 + (seed % 110);
  return enrichSpecWithUnitKeys({
    pricePerKg: perKg,
    displayPrice: perKg,
    unit: '₹/kg',
    variety: 'Farm Fresh (per kg)',
    grade: 'Grade A',
    trendBias: ((seed % 17) - 7) * 0.01,
  });
}

function generateDailySeries(cropId, daysCount = 365) {
  const crop = getCropById(cropId);
  const spec = getSpecForCrop(crop);
  const base = spec.displayPrice;
  const seedBase = hashString(crop.id);
  const now = new Date();
  now.setHours(9, 30, 0, 0);

  const series = [];
  for (let d = daysCount - 1; d >= 0; d -= 1) {
    const dt = new Date(now.getTime() - d * 86400 * 1000);
    const dayOfYear = Math.floor(
      (dt - new Date(dt.getFullYear(), 0, 0)) / (1000 * 60 * 60 * 24),
    );
    const seasonalWave = Math.sin(((dayOfYear + (seedBase % 90)) / 365) * Math.PI * 2) * 0.085;
    const mediumWave = Math.cos(((daysCount - d + (seedBase % 19)) / 18) * Math.PI) * 0.032;
    const recentTrend = d < 14 ? ((14 - d) / 14) * spec.trendBias : 0;
    const noise = (seededRand(seedBase + d * 13) - 0.5) * 0.022;

    const factor = Math.max(0.72, 1 + seasonalWave + mediumWave + recentTrend + noise);
    const price = Math.max(10, Math.round(base * factor));

    const lastYearFactor = Math.max(
      0.68,
      0.93 + seasonalWave * 0.9 + (seededRand(seedBase + d * 29 + 777) - 0.5) * 0.03,
    );
    const lastYearPrice = Math.max(9, Math.round(base * lastYearFactor));

    const spread = Math.max(2, Math.round(price * 0.045));
    series.push({
      date: dt.toISOString().slice(0, 10),
      iso: dt.toISOString(),
      price,
      lastYearPrice,
      minPrice: price - spread,
      maxPrice: price + spread,
    });
  }
  return series;
}

export function getFavouriteCropIds() {
  try {
    const raw = localStorage.getItem(FAVOURITES_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function toggleFavouriteCropId(cropId) {
  const current = new Set(getFavouriteCropIds());
  if (current.has(cropId)) {
    current.delete(cropId);
  } else {
    current.add(cropId);
  }
  const next = Array.from(current);
  try {
    localStorage.setItem(FAVOURITES_KEY, JSON.stringify(next));
  } catch {
    // ignore storage quota errors
  }
  return next;
}

export async function getPriceAlerts(cropId = null) {
  try {
    const all = await db.priceAlerts.toArray();
    return cropId ? all.filter((item) => item.cropId === cropId) : all;
  } catch {
    return [];
  }
}

export async function createPriceAlert({ cropId, targetPrice, direction = 'above', market = '' }) {
  const numericTarget = Number(targetPrice);
  if (!cropId || !Number.isFinite(numericTarget) || numericTarget <= 0) {
    throw new Error('Invalid target price');
  }
  const alertRecord = {
    cropId,
    targetPrice: numericTarget,
    direction: direction === 'below' ? 'below' : 'above',
    market,
    active: true,
    triggeredAt: null,
    createdAt: new Date().toISOString(),
  };
  const id = await db.priceAlerts.add(alertRecord);
  await db.syncQueue.add({
    action: 'CREATE_PRICE_ALERT',
    payload: { ...alertRecord, localId: id },
    status: 'pending',
    timestamp: Date.now(),
  });
  return { ...alertRecord, id };
}

export async function deletePriceAlert(id) {
  await db.priceAlerts.delete(id);
}

export async function evaluatePriceAlerts(items = []) {
  try {
    const alerts = await db.priceAlerts.toArray();
    const priceByCrop = new Map(items.map((item) => [item.id, item]));
    const triggered = [];

    for (const alert of alerts) {
      if (!alert.active) continue;
      const cropItem = priceByCrop.get(alert.cropId);
      if (!cropItem) continue;
      const currentPrice = Number(cropItem.price);
      const hit =
        (alert.direction === 'above' && currentPrice >= alert.targetPrice) ||
        (alert.direction === 'below' && currentPrice <= alert.targetPrice);
      if (hit) {
        const triggeredAt = alert.triggeredAt || new Date().toISOString();
        if (!alert.triggeredAt) {
          await db.priceAlerts.update(alert.id, { triggeredAt });
        }
        triggered.push({
          ...alert,
          currentPrice,
          unit: cropItem.unit,
          market: cropItem.market,
          triggeredAt,
        });
      }
    }
    return triggered;
  } catch {
    return [];
  }
}

function buildCropOverviewItem(cropId, markets, index = 0) {
  const crop = getCropById(cropId);
  const spec = getSpecForCrop(crop);
  const series30 = generateDailySeries(crop.id, 30);
  const todayPt = series30[series30.length - 1];
  const yesterdayPt = series30[series30.length - 2] || todayPt;
  const weekAgoPt = series30[series30.length - 8] || series30[0];
  const marketObj = markets[index % markets.length] || markets[0];

  const pctWeek = weekAgoPt.price
    ? Number((((todayPt.price - weekAgoPt.price) / weekAgoPt.price) * 100).toFixed(1))
    : 0;
  const pctDay = yesterdayPt.price
    ? Number((((todayPt.price - yesterdayPt.price) / yesterdayPt.price) * 100).toFixed(1))
    : 0;

  return {
    id: crop.id,
    nameKey: crop.nameKey,
    localNameKey: crop.localNameKey,
    category: crop.category,
    variety: spec.variety,
    grade: spec.grade,
    marketId: marketObj.id,
    market: marketObj.name,
    region: marketObj.region,
    price: todayPt.price,
    prev: weekAgoPt.price,
    yesterdayPrice: yesterdayPt.price,
    pctWeek,
    pctDay,
    unit: spec.unit,
    unitKey: spec.unitKey,
    unitSpeakKey: spec.unitSpeakKey,
    weekData: series30.slice(-7).map((d) => d.price),
    updatedAt: new Date(Date.now() - 18 * 60 * 1000).toISOString(),
    isMock: USE_MOCKS,
  };
}

export async function getMarketOverview({ countryCode, plotCropIds = [] } = {}) {
  const cacheKey = `overview:${countryCode || getSavedCountry() || 'IN'}`;

  if (!USE_MOCKS) {
    try {
      const response = await fetch(`${API_BASE}/market/markets`);
      if (response.ok) {
        const payload = await response.json();
        await db.marketCache.put({
          id: cacheKey,
          updatedAt: new Date().toISOString(),
          data: payload,
        });
        return payload;
      }
    } catch {
      const cached = await db.marketCache.get(cacheKey);
      if (cached?.data) return { ...cached.data, stale: true };
    }
  }

  const markets = getRegionalMarkets(countryCode);
  const validPlotCropIds = plotCropIds
    .map((id) => resolveKnownCrop(id)?.id)
    .filter((id) => Boolean(id && id !== 'other'));
  const combinedIds = Array.from(
    new Set([
      ...validPlotCropIds,
      ...DEFAULT_FEATURED_IDS,
      ...CROPS.map((c) => c.id),
    ]),
  ).filter((id) => id !== 'other' && resolveKnownCrop(id));

  const items = combinedIds.map((id, idx) => buildCropOverviewItem(id, markets, idx));
  const payload = {
    markets,
    items,
    updatedAt: new Date(Date.now() - 18 * 60 * 1000).toISOString(),
    isMock: true,
    stale: false,
  };

  try {
    await db.marketCache.put({
      id: cacheKey,
      updatedAt: payload.updatedAt,
      data: payload,
    });
  } catch {
    // ignore IndexedDB errors in restricted environments
  }

  return payload;
}

export async function getCropMarketDetail(cropId, range = '30D', { countryCode } = {}) {
  const normalizedCrop = getCropById(cropId);
  const cacheKey = `detail:${normalizedCrop.id}:${range}`;

  if (!USE_MOCKS) {
    try {
      const response = await fetch(
        `${API_BASE}/market/prices/${encodeURIComponent(normalizedCrop.id)}/history?range=${encodeURIComponent(range)}`,
      );
      if (response.ok) {
        const data = await response.json();
        await db.marketCache.put({
          id: cacheKey,
          updatedAt: new Date().toISOString(),
          data,
        });
        return data;
      }
    } catch {
      const cached = await db.marketCache.get(cacheKey);
      if (cached?.data) return { ...cached.data, stale: true };
    }
  }

  const markets = getRegionalMarkets(countryCode);
  const spec = getSpecForCrop(normalizedCrop);
  const fullYear = generateDailySeries(normalizedCrop.id, 365);

  const rangeDays =
    range === '7D' ? 7 : range === '90D' ? 90 : range === '1Y' ? 365 : 30;
  const sliced = fullYear.slice(-rangeDays);

  // Downsample 1Y to weekly points (~52 points) so chart stays crisp and fast on low-end phones
  const history =
    range === '1Y'
      ? sliced.filter((_, idx) => idx % 7 === 0 || idx === sliced.length - 1)
      : sliced;

  const todayPt = fullYear[fullYear.length - 1];
  const yesterdayPt = fullYear[fullYear.length - 2] || todayPt;
  const weekAgoPt = fullYear[fullYear.length - 8] || fullYear[0];
  const last30 = fullYear.slice(-30);

  const avgRangePrice = Math.round(
    history.reduce((sum, pt) => sum + pt.price, 0) / Math.max(1, history.length),
  );
  const avg30d = Math.round(
    last30.reduce((sum, pt) => sum + pt.price, 0) / Math.max(1, last30.length),
  );

  let minPoint = history[0];
  let maxPoint = history[0];
  for (const pt of history) {
    if (pt.price < minPoint.price) minPoint = pt;
    if (pt.price > maxPoint.price) maxPoint = pt;
  }

  const prices52w = fullYear.map((pt) => pt.price);
  const high52w = Math.max(...prices52w);
  const low52w = Math.min(...prices52w);

  const mean30 = avg30d || 1;
  const variance30 =
    last30.reduce((acc, pt) => acc + (pt.price - mean30) ** 2, 0) / Math.max(1, last30.length);
  const stdDevPct = (Math.sqrt(variance30) / mean30) * 100;
  const volatility = stdDevPct < 3.2 ? 'stable' : stdDevPct < 6.8 ? 'moderate' : 'volatile';

  const seed = hashString(normalizedCrop.id);
  const arrivalsTonnes = Number((14.5 + (seed % 42) * 1.3).toFixed(1));
  const arrivalsQuintals = Math.round(arrivalsTonnes * 10);

  // Nearby market comparison sorted by modal price descending
  const rawNearby = markets.map((mkt, idx) => {
    const deltaPct = ((seededRand(seed + idx * 17) - 0.45) * 0.09);
    const modalPrice = Math.max(10, Math.round(todayPt.price * (1 + deltaPct)));
    const spread = Math.max(2, Math.round(modalPrice * 0.04));
    return {
      id: mkt.id,
      name: mkt.name,
      region: mkt.region,
      distanceKm: mkt.distanceKm,
      modalPrice,
      minPrice: modalPrice - spread,
      maxPrice: modalPrice + spread,
      updatedAt: new Date(Date.now() - (12 + idx * 9) * 60 * 1000).toISOString(),
    };
  });
  rawNearby.sort((a, b) => b.modalPrice - a.modalPrice);
  const nearbyMarkets = rawNearby.map((mkt, idx) => ({
    ...mkt,
    isBestPrice: idx === 0,
    diffVsPrimary: mkt.modalPrice - todayPt.price,
  }));

  const pctDay = yesterdayPt.price
    ? Number((((todayPt.price - yesterdayPt.price) / yesterdayPt.price) * 100).toFixed(1))
    : 0;
  const pctWeek = weekAgoPt.price
    ? Number((((todayPt.price - weekAgoPt.price) / weekAgoPt.price) * 100).toFixed(1))
    : 0;
  const vsAvgPct = avg30d
    ? Number((((todayPt.price - avg30d) / avg30d) * 100).toFixed(1))
    : 0;

  const trendDirection = pctWeek > 1.5 ? 'rising' : pctWeek < -1.5 ? 'falling' : 'steady';

  let recommendation = 'hold';
  if (vsAvgPct >= 3 && pctWeek >= 0) {
    recommendation = 'sell_now';
  } else if (vsAvgPct <= -3 && trendDirection === 'falling') {
    recommendation = 'wait';
  } else if (pctWeek >= 4) {
    recommendation = 'sell_now';
  }

  // 12-month seasonal pattern
  const monthTotals = Array.from({ length: 12 }, () => ({ sum: 0, count: 0 }));
  for (const pt of fullYear) {
    const m = new Date(pt.iso).getMonth();
    monthTotals[m].sum += pt.price;
    monthTotals[m].count += 1;
  }
  const monthAvgs = monthTotals.map((m, idx) => ({
    monthIndex: idx,
    avgPrice: m.count ? Math.round(m.sum / m.count) : todayPt.price,
  }));
  const sortedMonths = [...monthAvgs].sort((a, b) => b.avgPrice - a.avgPrice);
  const bestMonthSet = new Set(sortedMonths.slice(0, 2).map((m) => m.monthIndex));
  const seasonalMonthly = monthAvgs.map((m) => ({
    ...m,
    isBestMonth: bestMonthSet.has(m.monthIndex),
  }));

  // 7-day simple linear projection with confidence band
  const slopePerDay = (todayPt.price - weekAgoPt.price) / 7;
  const forecast7d = Array.from({ length: 7 }, (_, i) => {
    const dayOffset = i + 1;
    const dt = new Date(Date.now() + dayOffset * 86400 * 1000);
    const projected = Math.max(10, Math.round(todayPt.price + slopePerDay * dayOffset * 0.65));
    const band = Math.max(3, Math.round(projected * (0.03 + dayOffset * 0.008)));
    return {
      date: dt.toISOString().slice(0, 10),
      iso: dt.toISOString(),
      midPrice: projected,
      lowBand: Math.max(5, projected - band),
      highBand: projected + band,
    };
  });

  // Farming info & income calculation per hectare
  const yieldTonnes = normalizedCrop.yieldPerHectareTonnes || 2.5;
  const expectedIncomePerHectare = Math.round(yieldTonnes * 1000 * spec.pricePerKg);

  // Related crops (same category first, then popular companions)
  const relatedCropIds = CROPS.filter(
    (c) => c.id !== normalizedCrop.id && c.id !== 'other' && c.category === normalizedCrop.category,
  )
    .slice(0, 6)
    .map((c) => c.id);

  // Nearby input dealers & government schemes
  const dealers = [
    {
      id: 'dealer-1',
      name: 'Krishi Seva Agro Kendra',
      distanceKm: 6.4,
      phone: '+918322260142',
      location: markets[0]?.name || 'Mapusa',
      stockKey: 'marketDetail.dealerStockSeedsFertilizer',
    },
    {
      id: 'dealer-2',
      name: 'Sahyadri Farmers Co-op Society',
      distanceKm: 13.8,
      phone: '+918322731908',
      location: markets[1]?.name || 'Margao',
      stockKey: 'marketDetail.dealerStockBioInputs',
    },
  ];

  const detail = {
    cropId: normalizedCrop.id,
    crop: normalizedCrop,
    variety: spec.variety,
    grade: spec.grade,
    unit: spec.unit,
    unitKey: spec.unitKey,
    unitSpeakKey: spec.unitSpeakKey,
    pricePerKg: spec.pricePerKg,
    primaryMarket: nearbyMarkets[0]?.name || markets[0]?.name,
    currentPrice: todayPt.price,
    yesterdayPrice: yesterdayPt.price,
    weekAgoPrice: weekAgoPt.price,
    diffDay: todayPt.price - yesterdayPt.price,
    diffWeek: todayPt.price - weekAgoPt.price,
    pctDay,
    pctWeek,
    updatedAt: new Date(Date.now() - 18 * 60 * 1000).toISOString(),
    isMock: USE_MOCKS,
    stale: false,
    range,
    history,
    averagePrice: avgRangePrice,
    minPoint,
    maxPoint,
    stats: {
      minToday: todayPt.minPrice,
      maxToday: todayPt.maxPrice,
      modalToday: todayPt.price,
      avg30d,
      high52w,
      low52w,
      volatility,
      arrivalsTonnes,
      arrivalsQuintals,
    },
    nearbyMarkets,
    analysis: {
      trendDirection,
      pct7d: pctWeek,
      vsAvgPct,
      recommendation,
      seasonalMonthly,
      bestMonths: sortedMonths.slice(0, 2).map((m) => m.monthIndex),
      forecast7d,
    },
    farming: {
      season: normalizedCrop.season || 'kharif',
      waterNeed: normalizedCrop.waterNeed || 'medium',
      durationDays: normalizedCrop.durationDays || 110,
      yieldPerHectareTonnes: yieldTonnes,
      expectedIncomePerHectare,
      mspInrPerQuintal: normalizedCrop.mspInrPerQuintal || null,
    },
    inputsAndHelp: {
      dealers,
      mspInrPerQuintal: normalizedCrop.mspInrPerQuintal || null,
    },
    relatedCropIds,
  };

  try {
    await db.marketCache.put({
      id: cacheKey,
      updatedAt: detail.updatedAt,
      data: detail,
    });
  } catch {
    // ignore cache errors
  }

  return detail;
}

