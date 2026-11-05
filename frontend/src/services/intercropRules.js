/*
 * FieldShift frontend: Intercrop Rule Engine
 * Feature: Defines agronomic rules for compatible or beneficial crop combinations in a rotation strategy.
 * Impact: It helps the app recommend smarter multi-crop systems that improve soil health and reduce risk.
 * Importance: Crop combination logic is a differentiating feature because it moves recommendations beyond single-crop planning.
 */

import { cropIdFromName, isRealCropId } from '../data/crops';

/**
 * Compatibility matrix for Feature 11: Intercropping & Cover Crops.
 * Maps canonical primaryCrop IDs to recommended companion/cover crops
 * with an agronomic benefitScore (0-100), benefitText, i18n benefitKey,
 * and UI accent ('emerald' | 'amber').
 */
export const INTERCROP_COMPATIBILITY_MATRIX = {
  maize: [
    {
      companionCropId: 'cowpea',
      benefitScore: 95,
      benefitText: 'Nitrogen Fixation',
      benefitKey: 'intercrop.benefits.nitrogenFixation',
      accent: 'emerald',
    },
    {
      companionCropId: 'beans',
      benefitScore: 89,
      benefitText: 'Weed Suppression',
      benefitKey: 'intercrop.benefits.weedSuppression',
      accent: 'amber',
    },
  ],
  sugarcane: [
    {
      companionCropId: 'chickpea',
      benefitScore: 93,
      benefitText: 'Nitrogen Fixation',
      benefitKey: 'intercrop.benefits.nitrogenFixation',
      accent: 'emerald',
    },
    {
      companionCropId: 'moong',
      benefitScore: 90,
      benefitText: 'Weed Suppression',
      benefitKey: 'intercrop.benefits.weedSuppression',
      accent: 'amber',
    },
  ],
  coconut: [
    {
      companionCropId: 'banana',
      benefitScore: 94,
      benefitText: 'Canopy & Moisture Retention',
      benefitKey: 'intercrop.benefits.canopyMoisture',
      accent: 'emerald',
    },
    {
      companionCropId: 'cocoa',
      benefitScore: 88,
      benefitText: 'Shade Synergy',
      benefitKey: 'intercrop.benefits.shadeSynergy',
      accent: 'amber',
    },
  ],
  paddy: [
    {
      companionCropId: 'cowpea',
      benefitScore: 92,
      benefitText: 'Nitrogen Fixation',
      benefitKey: 'intercrop.benefits.nitrogenFixation',
      accent: 'emerald',
    },
    {
      companionCropId: 'moong',
      benefitScore: 90,
      benefitText: 'Residual Moisture Cover',
      benefitKey: 'intercrop.benefits.moistureCover',
      accent: 'amber',
    },
  ],
  rice: [
    {
      companionCropId: 'cowpea',
      benefitScore: 92,
      benefitText: 'Nitrogen Fixation',
      benefitKey: 'intercrop.benefits.nitrogenFixation',
      accent: 'emerald',
    },
    {
      companionCropId: 'moong',
      benefitScore: 90,
      benefitText: 'Residual Moisture Cover',
      benefitKey: 'intercrop.benefits.moistureCover',
      accent: 'amber',
    },
  ],
  cashew: [
    {
      companionCropId: 'cowpea',
      benefitScore: 91,
      benefitText: 'Weed Suppression',
      benefitKey: 'intercrop.benefits.weedSuppression',
      accent: 'amber',
    },
    {
      companionCropId: 'groundnut',
      benefitScore: 89,
      benefitText: 'Nitrogen Fixation',
      benefitKey: 'intercrop.benefits.nitrogenFixation',
      accent: 'emerald',
    },
  ],
  wheat: [
    {
      companionCropId: 'chickpea',
      benefitScore: 92,
      benefitText: 'Nitrogen Fixation',
      benefitKey: 'intercrop.benefits.nitrogenFixation',
      accent: 'emerald',
    },
    {
      companionCropId: 'mustard',
      benefitScore: 87,
      benefitText: 'Natural Pest Deterrence',
      benefitKey: 'intercrop.benefits.pestDeterrence',
      accent: 'amber',
    },
  ],
};

function normalizeCropId(rawCrop) {
  if (!rawCrop) return '';
  return cropIdFromName(String(rawCrop)) || String(rawCrop).toLowerCase().trim();
}

/**
 * Returns recommended companion crops for a given primaryCrop,
 * filtered to available photo-verified crops and sorted by benefitScore descending.
 */
export function getRecommendedIntercrops(primaryCrop) {
  const primaryId = normalizeCropId(primaryCrop);
  if (!primaryId) return [];

  const rules = INTERCROP_COMPATIBILITY_MATRIX[primaryId] || [];
  return rules
    .filter(
      (rule) =>
        rule.companionCropId !== primaryId && isRealCropId(rule.companionCropId),
    )
    .sort((a, b) => b.benefitScore - a.benefitScore);
}

/**
 * Finds the compatibility rule for a (primaryCrop, intercrop) pair,
 * checking both forward and reverse directions.
 */
export function getIntercropPairingRule(primaryCrop, intercrop) {
  const primaryId = normalizeCropId(primaryCrop);
  const companionId = normalizeCropId(intercrop);
  if (!primaryId || !companionId || primaryId === companionId) return null;

  const forwardMatch = (INTERCROP_COMPATIBILITY_MATRIX[primaryId] || []).find(
    (rule) => rule.companionCropId === companionId,
  );
  if (forwardMatch) return forwardMatch;

  const reverseMatch = (INTERCROP_COMPATIBILITY_MATRIX[companionId] || []).find(
    (rule) => rule.companionCropId === primaryId,
  );
  if (reverseMatch) {
    return {
      ...reverseMatch,
      companionCropId: companionId,
    };
  }

  return null;
}

