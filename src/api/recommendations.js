import { apiRequest, getAuthToken } from './client';
import { cropIdFromName } from '../data/crops';

const SEASON_MAP = {
  Rabi: 'Rabi',
  Kharif: 'Kharif',
  Zaid: 'Zaid',
};

const DEFAULT_CROP_SPECS = {
  chickpea: { family: 'legume', rootDepth: 'medium', duration: [100, 110], waterNeed: 'low1to2' },
  mustard: { family: 'oilseed', rootDepth: 'deep', duration: [90, 105], waterNeed: 'low2' },
  lentil: { family: 'legume', rootDepth: 'medium', duration: [110, 120], waterNeed: 'veryLowResidual' },
  moong: { family: 'legume', rootDepth: 'shallow', duration: [60, 65], waterNeed: 'veryLow2' },
  cowpea: { family: 'legume', rootDepth: 'medium', duration: [50, 55], waterNeed: 'low2' },
  wheat: { family: 'cereal', rootDepth: 'shallow', duration: [115, 125], waterNeed: 'moderate3to4' },
  maize: { family: 'cereal', rootDepth: 'deep', duration: [90, 105], waterNeed: 'moderate3' },
  groundnut: { family: 'oilseed', rootDepth: 'shallow', duration: [100, 110], waterNeed: 'moderate3' },
  cotton: { family: 'cash', rootDepth: 'deep', duration: [150, 180], waterNeed: 'moderate4' },
};

export async function fetchBackendRecommendations({
  plotId,
  season = 'Rabi',
  farmerPreferences = ['low_water', 'soil_health'],
  limit = 3,
}) {
  const token = getAuthToken();
  if (!token) {
    throw new Error('Unauthenticated');
  }

  const normalizedSeason = SEASON_MAP[season] || season || 'Rabi';
  const validPreferences = (farmerPreferences || []).filter((p) =>
    ['low_water', 'early_cash', 'soil_health', 'high_return'].includes(p),
  );

  const payload = {
    plot_id: Number(plotId),
    season: normalizedSeason,
    farmer_preferences: validPreferences.length > 0 ? validPreferences : ['low_water', 'soil_health'],
    limit: Math.min(Math.max(1, limit), 3),
  };

  const response = await apiRequest('/recommendations', {
    method: 'POST',
    body: payload,
  });

  const rawOptions = response?.options || [];
  const rankTagKeys = [
    'recommender.rankTags.bestFit',
    'recommender.rankTags.soilBalance',
    'recommender.rankTags.lowInput',
  ];
  const badgeKeys = [
    'recommender.badges.soilBalance',
    'recommender.badges.marketChoice',
    'recommender.badges.lowWater',
  ];

  const mappedResults = rawOptions.map((opt, idx) => {
    const rawCropId = cropIdFromName(opt.crop_name);
    const spec = DEFAULT_CROP_SPECS[rawCropId] || {
      family: 'legume',
      rootDepth: 'medium',
      duration: [90, 110],
      waterNeed: 'low2',
    };

    const score = opt.score ?? 80;
    const netReturn = opt.expected_net_return ?? Math.round(score * 1200);
    const baselineReturn = Math.max(1, Math.round(netReturn * 0.84));
    const percentageGain = Math.round(((netReturn - baselineReturn) / baselineReturn) * 100);

    const soilScore = Math.round(opt.soil_health_score ?? score);
    const fertReductionKg = Math.round(((soilScore / 100) * 80) * 10) / 10;
    const fertSavingsInr = Math.round(fertReductionKg * 24);

    return {
      id: rawCropId,
      cropName: opt.crop_name,
      rank: idx + 1,
      rankTagKey: rankTagKeys[idx] || rankTagKeys[2],
      recommendedBadgeKey: badgeKeys[idx] || badgeKeys[2],
      family: spec.family,
      familyKey: `recommender.families.${spec.family}`,
      durationMinDays: spec.duration[0],
      durationMaxDays: spec.duration[1],
      waterNeedKey: `recommender.waterNeeds.${spec.waterNeed}`,
      fertilizerKey: 'recommender.fertilizerUrea',
      fertilizerReductionKg: fertReductionKg,
      fertilizerSavingsInr: fertSavingsInr,
      nitrogenReasonKey: 'recommender.reasons.afterCereal',
      rootReasonKey: 'recommender.reasons.alternateRoots',
      prevRootDepthKey: 'recommender.rootDepths.shallow',
      currRootDepthKey: `recommender.rootDepths.${spec.rootDepth}`,
      baseReturn: netReturn,
      netReturn,
      baselineReturn,
      percentageGain,
      pmfbyInsured: true,
      pmfbySeasonType: normalizedSeason === 'Rabi' ? 'Rabi' : 'Kharif',
      pmfbyPremiumRatePct: normalizedSeason === 'Rabi' ? 1.5 : 2.0,
      pmfbyPremiumInr: Math.round(netReturn * 0.015),
      nfsmSubsidyEligible: spec.family === 'legume',
      subsidyBonusInr: spec.family === 'legume' ? 5000 : 0,
      score,
      soilHealthScore: soilScore,
      pestRiskScore: Math.round(opt.pest_risk_score ?? 40),
      waterRiskScore: Math.round(opt.water_risk_score ?? 40),
      expectedYieldKg: opt.expected_yield_kg ?? null,
      reasons: opt.reasons || [],
      tradeoffs: opt.tradeoffs || [],
      benefit: opt.benefit || '',
      tradeoff: opt.tradeoff || '',
      confidence: opt.confidence || response.engine_confidence || 'medium',
      assumptions: opt.assumptions || [],
      sourceCitations: opt.source_citations || opt.source_ids || [],
      nasaSources: (opt.source_citations || []).filter((s) => s.toLowerCase().includes('nasa')),
      isRealEngine: true,
    };
  });

  return {
    results: mappedResults,
    recommendationId: response.recommendation_id,
    engineStatus: response.engine_status,
    engineJobId: response.engine_job_id,
    refinementUrl: response.refinement_url,
    confidence: response.engine_confidence,
    needsHumanReview: response.needs_human_review,
    advisorReferralRequired: response.advisor_referral_required,
    advisorReferralReason: response.advisor_referral_reason,
    dataQualityNotes: response.data_quality_notes || [],
    rulesetVersion: response.ruleset_version,
    scorerVersion: response.scorer_version,
  };
}

export async function pollRecommendationJob(recommendationId) {
  return apiRequest(`/recommendations/${recommendationId}/job`, { method: 'GET' });
}

export async function recordRecommendationOutcome(recommendationId, {
  plantedCrop,
  actualYieldKg = null,
  actualInputCost = null,
  outcomeNotes = '',
}) {
  return apiRequest(`/recommendations/${recommendationId}/outcome`, {
    method: 'POST',
    body: {
      planted_crop: plantedCrop,
      actual_yield_kg: actualYieldKg != null ? Number(actualYieldKg) : null,
      actual_input_cost: actualInputCost != null ? Number(actualInputCost) : null,
      outcome_notes: outcomeNotes || null,
    },
  });
}

export async function fetchPlotAlerts(plotId) {
  return apiRequest(`/recommendations/plots/${plotId}/alerts`, { method: 'GET' });
}
