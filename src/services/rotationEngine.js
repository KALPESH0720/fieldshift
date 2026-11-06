export const CROP_RULES = [
    { id: 'chickpea', family: 'legume', rootDepth: 'medium', seasons: ['Rabi'], durationRange: [100, 110], waterNeedKey: 'recommender.waterNeeds.low1to2', baseReturnPerHectare: 120000, ureaReductionPerHectare: 86, fertilizerKey: 'recommender.fertilizerUrea', waterSavingsPct: 45, soilHealthScore: 96 },
    { id: 'mustard', family: 'oilseed', rootDepth: 'deep', seasons: ['Rabi'], durationRange: [90, 105], waterNeedKey: 'recommender.waterNeeds.low2', baseReturnPerHectare: 129500, ureaReductionPerHectare: 44, fertilizerKey: 'recommender.fertilizerUrea', waterSavingsPct: 35, soilHealthScore: 84 },
    { id: 'lentil', family: 'legume', rootDepth: 'medium', seasons: ['Rabi'], durationRange: [110, 120], waterNeedKey: 'recommender.waterNeeds.veryLowResidual', baseReturnPerHectare: 109200, ureaReductionPerHectare: 69, fertilizerKey: 'recommender.fertilizerUrea', waterSavingsPct: 55, soilHealthScore: 90 },
    { id: 'moong', family: 'legume', rootDepth: 'shallow', seasons: ['Zaid', 'Kharif'], durationRange: [60, 65], waterNeedKey: 'recommender.waterNeeds.veryLow2', baseReturnPerHectare: 85200, ureaReductionPerHectare: 74, fertilizerKey: 'recommender.fertilizerUrea', waterSavingsPct: 40, soilHealthScore: 95 },
    { id: 'cowpea', family: 'legume', rootDepth: 'medium', seasons: ['Zaid', 'Kharif'], durationRange: [50, 55], waterNeedKey: 'recommender.waterNeeds.low2', baseReturnPerHectare: 69200, ureaReductionPerHectare: 62, fertilizerKey: 'recommender.fertilizerUrea', waterSavingsPct: 35, soilHealthScore: 92 },
    { id: 'wheat', family: 'cereal', rootDepth: 'shallow', seasons: ['Rabi'], durationRange: [115, 125], waterNeedKey: 'recommender.waterNeeds.moderate3to4', baseReturnPerHectare: 135500, ureaReductionPerHectare: 62, fertilizerKey: 'recommender.fertilizerUrea', waterSavingsPct: 20, soilHealthScore: 89 },
    { id: 'maize', family: 'cereal', rootDepth: 'deep', seasons: ['Kharif', 'Zaid'], durationRange: [90, 105], waterNeedKey: 'recommender.waterNeeds.moderate3', baseReturnPerHectare: 115000, ureaReductionPerHectare: 35, fertilizerKey: 'recommender.fertilizerUrea', waterSavingsPct: 18, soilHealthScore: 82 },
    { id: 'groundnut', family: 'oilseed', rootDepth: 'shallow', seasons: ['Kharif'], durationRange: [100, 110], waterNeedKey: 'recommender.waterNeeds.moderate3', baseReturnPerHectare: 118000, ureaReductionPerHectare: 27, fertilizerKey: 'recommender.fertilizerUrea', waterSavingsPct: 25, soilHealthScore: 86 },
    { id: 'cotton', family: 'cash', rootDepth: 'deep', seasons: ['Kharif'], durationRange: [150, 180], waterNeedKey: 'recommender.waterNeeds.moderate4', baseReturnPerHectare: 142000, ureaReductionPerHectare: 12, fertilizerKey: 'recommender.fertilizerUrea', waterSavingsPct: 10, soilHealthScore: 74 },
];

const PREVIOUS_CROP_PROFILES = {
    wheat: { family: 'cereal', rootDepth: 'shallow' },
    rice: { family: 'cereal', rootDepth: 'shallow' },
    paddy: { family: 'cereal', rootDepth: 'shallow' },
    maize: { family: 'cereal', rootDepth: 'deep' },
    cotton: { family: 'cash', rootDepth: 'deep' },
    sugarcane: { family: 'cash', rootDepth: 'deep' },
    soybean: { family: 'legume', rootDepth: 'deep' },
    groundnut: { family: 'oilseed', rootDepth: 'shallow' },
    mustard: { family: 'oilseed', rootDepth: 'deep' },
};

export function getPreviousCropProfile(previousCrop) {
    const normalized = (previousCrop || '').toLowerCase();
    const matchedKey = Object.keys(PREVIOUS_CROP_PROFILES).find((key) => normalized.includes(key));
    return PREVIOUS_CROP_PROFILES[matchedKey] || { family: 'unknown', rootDepth: 'medium' };
}

export function getPlotAreaHectares(plot) {
    if (Number.isFinite(Number(plot?.areaHectares)) && Number(plot.areaHectares) > 0) return Number(plot.areaHectares);
    const match = String(plot?.area || '').match(/[0-9]+(?:\.[0-9]+)?/);
    const numericArea = match ? Number(match[0]) : 1;
    const areaText = String(plot?.area || '').toLowerCase();
    if (areaText.includes('acre')) return numericArea * 0.40468564224;
    if (areaText.includes('sq meter') || areaText.includes('sqm')) return numericArea * 0.0001;
    if (areaText.includes('sq feet') || areaText.includes('sq ft')) return numericArea * 0.000009290304;
    return numericArea;
}

export const NFSM_SUBSIDY_PER_HECTARE = 5000;

export const PMFBY_PREMIUM_RATES = {
    Rabi: 0.015,
    Kharif: 0.02,
};

const SUBSIDIZED_FAMILIES = new Set(['legume', 'pulse']);

export function runOfflineRotationEngine(
    season,
    previousCrop,
    areaHectares = 1,
    isCropAvailable = () => true,
    isVerified = false,
) {
    const cropFilter = typeof isCropAvailable === 'function' ? isCropAvailable : () => true;
    const verifiedPlot = typeof isCropAvailable === 'boolean' ? isCropAvailable : Boolean(isVerified);
    const previous = getPreviousCropProfile(previousCrop);
    const safeArea = Number.isFinite(Number(areaHectares)) && Number(areaHectares) > 0 ? Number(areaHectares) : 1;
    // Rules that refer to crops without a proper photo are ignored (catalog is data-driven).
    const rules = CROP_RULES.filter((crop) => cropFilter(crop.id));
    const candidates = rules
        .filter((crop) => crop.seasons.includes(season))
        .filter((crop) => crop.family !== previous.family)
        .filter((crop) => crop.rootDepth !== previous.rootDepth)
        .sort((first, second) => {
            const firstLegumeBonus = previous.family === 'cereal' && first.family === 'legume' ? 100 : 0;
            const secondLegumeBonus = previous.family === 'cereal' && second.family === 'legume' ? 100 : 0;
            return (secondLegumeBonus + second.soilHealthScore) - (firstLegumeBonus + first.soilHealthScore);
        });
    const fallbackCandidates = rules.filter((crop) => crop.seasons.includes(season) && crop.family !== previous.family);
    const selected = (candidates.length >= 2 ? candidates : fallbackCandidates).slice(0, 3);
    // Top up to 3 with the best remaining in-season crops (same family allowed) so results are never thin.
    if (selected.length < 3) {
        const chosen = new Set(selected.map((crop) => crop.id));
        const extras = rules
            .filter((crop) => crop.seasons.includes(season) && !chosen.has(crop.id))
            .sort((first, second) => second.soilHealthScore - first.soilHealthScore);
        selected.push(...extras.slice(0, 3 - selected.length));
    }

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

    const isRabiSeason = season === 'Rabi';
    const pmfbyPremiumRate = isRabiSeason ? PMFBY_PREMIUM_RATES.Rabi : PMFBY_PREMIUM_RATES.Kharif;
    const pmfbyPremiumRatePct = isRabiSeason ? 1.5 : 2;

    return selected.map((crop, index) => {
        const fertilizerReductionKg = Math.round(crop.ureaReductionPerHectare * safeArea * 10) / 10;
        const fertilizerSavingsInr = Math.round(fertilizerReductionKg * 24);

        const rawBaseReturn = Math.round(crop.baseReturnPerHectare * safeArea);
        const baselineReturn = Math.max(1, Math.round(rawBaseReturn * 0.84));

        const pmfbyPremiumInr = verifiedPlot
            ? Math.round(crop.baseReturnPerHectare * pmfbyPremiumRate * safeArea)
            : 0;
        const nfsmSubsidyEligible = SUBSIDIZED_FAMILIES.has(crop.family);
        const subsidyBonusInr = nfsmSubsidyEligible
            ? Math.round(NFSM_SUBSIDY_PER_HECTARE * safeArea)
            : 0;

        const netReturn = Math.max(0, rawBaseReturn - pmfbyPremiumInr + subsidyBonusInr);
        const percentageGain = Math.round(((netReturn - baselineReturn) / baselineReturn) * 100);

        const nitrogenReasonKey = previous.family === 'legume'
            ? 'recommender.reasons.afterLegume'
            : previous.family === 'cereal'
                ? 'recommender.reasons.afterCereal'
                : 'recommender.reasons.differentFamily';

        const rootReasonKey = crop.rootDepth !== previous.rootDepth
            ? 'recommender.reasons.alternateRoots'
            : 'recommender.reasons.coverSoil';

        return {
            ...crop,
            rank: index + 1,
            rankTagKey: rankTagKeys[index] || rankTagKeys[2],
            recommendedBadgeKey: badgeKeys[index] || badgeKeys[2],
            familyKey: `recommender.families.${crop.family}`,
            nitrogenReasonKey,
            rootReasonKey,
            prevRootDepthKey: `recommender.rootDepths.${previous.rootDepth}`,
            currRootDepthKey: `recommender.rootDepths.${crop.rootDepth}`,
            durationMinDays: crop.durationRange[0],
            durationMaxDays: crop.durationRange[1],
            baseReturn: rawBaseReturn,
            netReturn,
            baselineReturn,
            percentageGain,
            pmfbyInsured: verifiedPlot,
            pmfbySeasonType: isRabiSeason ? 'Rabi' : 'Kharif',
            pmfbyPremiumRatePct,
            pmfbyPremiumInr,
            nfsmSubsidyEligible,
            subsidyBonusInr,
            fertilizerReductionKg,
            fertilizerSavingsInr,
        };
    });
}
