/*
 * FieldShift frontend: Crop Catalog
 * Feature: Defines the crop master data, names, local labels, and agronomic metadata used by the recommendation engine and UI.
 * Impact: This acts as the shared source of truth for crop selection, recommendations, and market integration.
 * Importance: A consistent crop dataset is essential because many features depend on naming, matching, and crop metadata.
 */

import cropCreditsData from './crop-credits.json';
import cropAvailability from './crops-with-images.json';

const CROP_DEFINITIONS = [
    ['rice', 'cereal', '🌾', 'Kharif', 'shallow', 3, [115, 135], 4.2, 2300],
    ['wheat', 'cereal', '🌾', 'Rabi', 'shallow', 2, [110, 130], 3.8, 2425],
    ['maize', 'cereal', '🌽', 'Kharif', 'deep', 2, [95, 115], 5.0, 2225],
    ['sorghum', 'cereal', '🌾', 'Kharif', 'deep', 1, [100, 120], 2.4, 3371],
    ['millet', 'cereal', '🌾', 'Kharif', 'shallow', 1, [85, 105], 2.2, 4290],
    ['barley', 'cereal', '🌾', 'Rabi', 'shallow', 2, [105, 125], 3.2, 1980],
    ['oats', 'cereal', '🌾', 'Rabi', 'shallow', 2, [100, 120], 2.8, null],
    ['chickpea', 'pulse', '🫘', 'Rabi', 'medium', 1, [100, 115], 1.8, 5650],
    ['lentil', 'pulse', '🫘', 'Rabi', 'shallow', 1, [105, 120], 1.5, 6700],
    ['pigeon-pea', 'pulse', '🫘', 'Kharif', 'deep', 2, [140, 170], 1.6, 7550],
    ['moong', 'pulse', '🫘', 'Zaid', 'shallow', 1, [60, 75], 1.2, 8682],
    ['cowpea', 'pulse', '🫘', 'Kharif', 'medium', 1, [70, 90], 1.4, null],
    ['soybean', 'pulse', '🫘', 'Kharif', 'deep', 2, [95, 110], 2.2, 4892],
    ['beans', 'pulse', '🫘', 'Kharif', 'medium', 2, [75, 95], 2.0, null],
    ['peas', 'pulse', '🫛', 'Rabi', 'shallow', 2, [80, 100], 2.5, null],
    ['groundnut', 'pulse', '🥜', 'Kharif', 'shallow', 2, [105, 125], 2.4, 6783],
    ['mustard', 'oilseed', '🌼', 'Rabi', 'deep', 2, [100, 120], 1.7, 5950],
    ['sunflower', 'oilseed', '🌻', 'Zaid', 'deep', 2, [90, 105], 1.9, 7280],
    ['sesame', 'oilseed', '🌱', 'Kharif', 'medium', 1, [85, 100], 0.9, 9267],
    ['rapeseed', 'oilseed', '🌼', 'Rabi', 'deep', 2, [105, 125], 1.8, 5950],
    ['potato', 'root', '🥔', 'Rabi', 'shallow', 2, [90, 110], 22.0, null],
    ['sweet-potato', 'root', '🍠', 'Kharif', 'medium', 2, [105, 125], 16.0, null],
    ['cassava', 'root', '🌿', 'Kharif', 'deep', 2, [240, 300], 25.0, null],
    ['yam', 'root', '🍠', 'Kharif', 'deep', 2, [210, 270], 18.0, null],
    ['onion', 'root', '🧅', 'Rabi', 'shallow', 2, [110, 130], 18.5, null],
    ['garlic', 'root', '🧄', 'Rabi', 'shallow', 1, [120, 150], 8.5, null],
    ['tomato', 'vegetable', '🍅', 'Kharif', 'medium', 2, [90, 115], 24.0, null],
    ['brinjal', 'vegetable', '🍆', 'Kharif', 'medium', 2, [100, 130], 20.0, null],
    ['chilli', 'vegetable', '🌶️', 'Kharif', 'medium', 2, [110, 140], 3.5, null],
    ['cabbage', 'vegetable', '🥬', 'Rabi', 'shallow', 2, [85, 105], 25.0, null],
    ['cauliflower', 'vegetable', '🥦', 'Rabi', 'shallow', 2, [90, 110], 20.0, null],
    ['okra', 'vegetable', '🌱', 'Kharif', 'medium', 2, [60, 80], 12.0, null],
    ['cucumber', 'vegetable', '🥒', 'Kharif', 'shallow', 2, [55, 70], 15.0, null],
    ['pumpkin', 'vegetable', '🎃', 'Kharif', 'medium', 2, [95, 120], 20.0, null],
    ['cotton', 'cash', '🌿', 'Kharif', 'deep', 2, [150, 180], 2.2, 7121],
    ['sugarcane', 'cash', '🎋', 'Kharif', 'deep', 3, [300, 360], 75.0, 340],
    ['jute', 'cash', '🌿', 'Kharif', 'deep', 2, [120, 140], 2.6, 5335],
    ['tea', 'plantation', '🍃', 'Kharif', 'medium', 2, [365, 365], 2.1, null],
    ['coffee', 'plantation', '☕', 'Kharif', 'deep', 2, [270, 330], 1.2, null],
    ['tobacco', 'cash', '🍂', 'Kharif', 'deep', 2, [120, 150], 2.0, null],
    ['coconut', 'plantation', '🥥', 'Kharif', 'deep', 3, [365, 365], 10.5, 11160],
    ['cashew', 'plantation', '🌰', 'Kharif', 'deep', 2, [90, 120], 1.4, null],
    ['arecanut', 'plantation', '🌴', 'Kharif', 'deep', 3, [240, 300], 2.1, null],
    ['banana', 'plantation', '🍌', 'Kharif', 'medium', 3, [300, 365], 32.0, null],
    ['mango', 'plantation', '🥭', 'Kharif', 'deep', 2, [110, 140], 9.5, null],
    ['papaya', 'plantation', '🧡', 'Kharif', 'medium', 2, [270, 330], 40.0, null],
    ['citrus', 'plantation', '🍊', 'Rabi', 'deep', 2, [180, 240], 14.0, null],
    ['apple', 'plantation', '🍎', 'Rabi', 'deep', 2, [150, 180], 12.0, null],
    ['cocoa', 'plantation', '🍫', 'Kharif', 'deep', 3, [180, 240], 1.1, null],
    ['oil-palm', 'plantation', '🌴', 'Kharif', 'deep', 3, [300, 365], 18.0, null],
    ['rubber', 'plantation', '🌳', 'Kharif', 'deep', 2, [300, 365], 1.8, null],
    ['alfalfa', 'fodder', '🌿', 'Rabi', 'deep', 2, [65, 85], 9.0, null],
    ['napier-grass', 'fodder', '🌱', 'Kharif', 'deep', 3, [75, 95], 35.0, null],
    ['black-gram', 'pulse', '🫘', 'Kharif', 'medium', 1, [75, 90], 1.3, 7400],
    ['fenugreek', 'vegetable', '🌿', 'Rabi', 'shallow', 1, [45, 70], 6.5, null],
    ['grape', 'plantation', '🍇', 'Rabi', 'deep', 2, [130, 160], 20.0, null],
    ['paddy', 'cereal', '🌾', 'Kharif', 'shallow', 3, [115, 135], 4.2, 2300],
    ['areca-nut', 'plantation', '🌴', 'Kharif', 'deep', 3, [240, 300], 2.1, null],
    ['vegetables', 'vegetable', '🥬', 'Kharif', 'medium', 2, [65, 95], 16.0, null],
    ['other', 'other', '🌱', 'Kharif', 'medium', 2, [90, 120], 2.5, null],
];

const creditsLookup = cropCreditsData?.crops || {};

/** Every crop definition (kept so a crop returns automatically once it has a proper photo). */
export const ALL_CROPS = CROP_DEFINITIONS.map(([
    id,
    family,
    emoji,
    season,
    rootDepth,
    waterNeed,
    durationDays,
    yieldPerHectareTonnes,
    mspInrPerQuintal,
]) => {
    const credit = creditsLookup[id] || null;
    const isVerifiedPhoto = Boolean(credit && credit.status === 'verified' && credit.hasPhoto);
    const thumbHash = credit?.thumbHash || credit?.thumbSha256?.slice(0, 10) || 'v2';
    const cardHash = credit?.cardHash || credit?.cardSha256?.slice(0, 10) || 'v2';
    return {
        id,
        family,
        category: family,
        emoji,
        season: String(season).toLowerCase(),
        rootDepth,
        waterNeed,
        durationDays: Array.isArray(durationDays) ? durationDays[1] : durationDays,
        durationRangeDays: durationDays,
        yieldPerHectareTonnes,
        mspInrPerQuintal,
        thumb: `/crops/${id}-thumb.webp?v=${thumbHash}`,
        card: `/crops/${id}-card.webp?v=${cardHash}`,
        thumbHash,
        cardHash,
        hasPhoto: isVerifiedPhoto,
        credit,
        nameKey: `crops.${id}.name`,
        localNameKey: `crops.${id}.localName`,
    };
});

const AVAILABLE_IDS = new Set(cropAvailability?.available || []);

/** Crops that have a proper photo (see src/data/crops-with-images.json, written by npm run crops:audit). */
export const CROPS = ALL_CROPS.filter((crop) => AVAILABLE_IDS.has(crop.id));
export const HIDDEN_CROP_IDS = ALL_CROPS.filter((crop) => !AVAILABLE_IDS.has(crop.id)).map((crop) => crop.id);

if (import.meta.env?.DEV) {
    console.info(`[Field Shift] ${CROPS.length} of ${ALL_CROPS.length} crops have photos; ${HIDDEN_CROP_IDS.length} hidden`);
}

const CROPS_BY_ID = new Map(CROPS.map((crop) => [crop.id, crop]));

export const CROP_ALIASES = {
    'mung': 'moong',
    'mung-bean': 'moong',
    'moong-bean': 'moong',
    'green-gram': 'moong',
    'urad': 'black-gram',
    'urad-dal': 'black-gram',
    'tur': 'pigeon-pea',
    'arhar': 'pigeon-pea',
    'red-gram': 'pigeon-pea',
    'chana': 'chickpea',
    'desi-chana': 'chickpea',
    'bengal-gram': 'chickpea',
    'masoor': 'lentil',
    'masoor-dal': 'lentil',
    'lobia': 'cowpea',
    'black-eyed-pea': 'cowpea',
    'rajma': 'beans',
    'kidney-bean': 'beans',
    'french-bean': 'beans',
    'common-bean': 'beans',
    'bean': 'beans',
    'pea': 'peas',
    'green-pea': 'peas',
    'green-peas': 'peas',
    'peanut': 'groundnut',
    'peanuts': 'groundnut',
    'canola': 'rapeseed',
    'oilseed-rape': 'rapeseed',
    'sarson': 'mustard',
    'yellow-sarson': 'mustard',
    'corn': 'maize',
    'jowar': 'sorghum',
    'bajra': 'millet',
    'pearl-millet': 'millet',
    'finger-millet': 'millet',
    'ragi': 'millet',
    'eggplant': 'brinjal',
    'aubergine': 'brinjal',
    'chili': 'chilli',
    'chillies': 'chilli',
    'hot-pepper': 'chilli',
    'ladyfinger': 'okra',
    'bhindi': 'okra',
    'manioc': 'cassava',
    'tapioca': 'cassava',
    'methi': 'fenugreek',
    'grapes': 'grape',
    'orange': 'citrus',
    'lemon': 'citrus',
    'lime': 'citrus',
    'mandarin': 'citrus',
    'lucerne': 'alfalfa',
    'elephant-grass': 'napier-grass',
    'napier': 'napier-grass',
    'supari': 'arecanut',
    'betel-nut': 'arecanut',
    'paddy-rice': 'paddy',
};

const NON_CROP_LAND_LABELS = new Set([
    'mixed-agriculture',
    'mixed-farming',
    'arable-land',
    'arable',
    'cereal',
    'cereals',
    'tree-crop',
    'tree-crops',
    'plantation',
    'fallow',
    'pasture',
    'grassland',
    'orchard',
    'unassigned',
    'unknown',
    'none',
]);

function normalizeCropKey(value) {
    return String(value || '')
        .trim()
        .toLowerCase()
        .replace(/\([^)]*\)/g, '')
        .trim()
        .replace(/[\s_]+/g, '-')
        .replace(/-+/g, '-');
}

export function resolveKnownCrop(cropId) {
    if (!cropId) return null;
    if (typeof cropId === 'object' && cropId.id) {
        return CROPS_BY_ID.get(cropId.id) || null;
    }
    const normalized = normalizeCropKey(cropId);
    if (!normalized || NON_CROP_LAND_LABELS.has(normalized)) {
        return null;
    }
    if (CROPS_BY_ID.has(normalized)) {
        return CROPS_BY_ID.get(normalized);
    }
    const aliasTarget = CROP_ALIASES[normalized];
    if (aliasTarget && CROPS_BY_ID.has(aliasTarget)) {
        return CROPS_BY_ID.get(aliasTarget);
    }
    return null;
}

export function isRealCropId(cropId) {
    const resolved = resolveKnownCrop(cropId);
    return Boolean(resolved && resolved.id !== 'other');
}

export function getCrop(cropId) {
    if (cropId && typeof cropId === 'object' && cropId.id && CROPS_BY_ID.has(cropId.id)) {
        return CROPS_BY_ID.get(cropId.id);
    }
    const resolved = resolveKnownCrop(cropId);
    if (resolved) return resolved;

    const fallbackBase = ALL_CROPS.find((crop) => crop.id === 'other');
    const rawLabel = typeof cropId === 'string' ? cropId.trim() : '';
    const normalized = normalizeCropKey(rawLabel) || 'unmapped';
    return {
        ...fallbackBase,
        id: normalized,
        rawLabel,
        isUnmapped: true,
        hasPhoto: false,
        thumb: null,
        card: null,
    };
}

export const getCropById = getCrop;

/**
 * Safe lookup for crop ids coming from stored data (plots, soil records, alerts...).
 * Returns the crop when it is available, otherwise a neutral "Other crop" entry that
 * keeps the stored text, has no photo and never borrows another crop's image.
 */
export function getCropOrUnknown(cropId, storedName) {
    const resolved = resolveKnownCrop(cropId);
    if (resolved) return resolved;
    const base = getCrop(cropId);
    return {
        ...base,
        isUnknown: true,
        rawLabel: storedName || base.rawLabel || (typeof cropId === 'string' ? cropId : ''),
    };
}

export function getCropDisplayName(cropOrId, t) {
    const resolved = resolveKnownCrop(cropOrId);
    if (resolved) {
        if (typeof t === 'function') {
            const translated = t(resolved.nameKey);
            if (translated && translated !== resolved.nameKey) return translated;
        }
        return resolved.id.replace(/-/g, ' ');
    }
    if (typeof cropOrId === 'string' && cropOrId.trim()) {
        return cropOrId.trim();
    }
    if (cropOrId && typeof cropOrId === 'object' && cropOrId.rawLabel) {
        return cropOrId.rawLabel;
    }
    return '';
}

export function getCropLocalName(cropOrId, t) {
    const resolved = resolveKnownCrop(cropOrId);
    if (!resolved) return '';
    if (typeof t === 'function') {
        const translated = t(resolved.localNameKey);
        if (translated && translated !== resolved.localNameKey) return translated;
    }
    return '';
}

export function cropIdFromName(name) {
    return resolveKnownCrop(name)?.id || '';
}

export const CROP_CREDITS_META = {
    note: cropCreditsData?._note || '',
    generatedAt: cropCreditsData?.generatedAt || null,
    totalCrops: cropCreditsData?.totalCrops || CROPS.length,
    verifiedCount: cropCreditsData?.verifiedCount ?? 0,
    missingCount: cropCreditsData?.missingCount ?? 0,
};

export const CROP_CREDITS = Object.fromEntries(
    CROPS.map((crop) => {
        const entry = creditsLookup[crop.id];
        return [
            crop.id,
            entry || {
                cropId: crop.id,
                subject: crop.id,
                sourceUrl: null,
                pageUrl: null,
                license: null,
                author: null,
                hasPhoto: false,
                status: 'missing',
            },
        ];
    }),
);

// Dev-only diagnostic logging for missing crop photographs
const runtimeMissingSet = new Set(
    CROPS.filter((crop) => !crop.hasPhoto).map((crop) => crop.id),
);
let devWarnLogged = false;

export function logMissingCropPhotosWarning() {
    if (!import.meta.env?.DEV || devWarnLogged) return;
    devWarnLogged = true;
    if (runtimeMissingSet.size > 0) {
        console.warn(
            `[Field Shift] ${runtimeMissingSet.size} crop(s) missing real photographs in public/crops/ (run "npm run crops:fetch" or see docs/MISSING_CROP_IMAGES.md): ${[...runtimeMissingSet].join(', ')}`,
        );
    }
}

export function reportFailedCropImage(cropId) {
    if (!import.meta.env?.DEV || !cropId) return;
    if (!runtimeMissingSet.has(cropId)) {
        runtimeMissingSet.add(cropId);
        console.warn(
            `[Field Shift] Crop image failed to load for "${cropId}". Missing crop IDs: ${[...runtimeMissingSet].join(', ')}`,
        );
    }
}
