import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  ExternalLink,
  Landmark,
  MapPin,
  ShieldCheck,
  Sprout,
  X,
} from 'lucide-react';
import { useLiveQuery } from 'dexie-react-hooks';
import { db } from '../db/db';
import { useTranslation } from '../context/LanguageContext';
import useScrollLock from '../hooks/useScrollLock';
import CropImage from './CropImage';
import ListenButton from './ui/ListenButton';
import { cropIdFromName, getCropDisplayName } from '../data/crops';
import { getPlotAreaHectares } from '../services/rotationEngine';
import {
  buildSpeechText,
  formatSpeakableNumber,
  formatSpeakablePriceWithUnit,
} from '../utils/speechText';

const PMFBY_NOTIFIED_CROPS = new Set([
  'paddy',
  'rice',
  'wheat',
  'maize',
  'sorghum',
  'millet',
  'barley',
  'oats',
  'chickpea',
  'lentil',
  'pigeon-pea',
  'moong',
  'cowpea',
  'black-gram',
  'soybean',
  'beans',
  'peas',
  'groundnut',
  'mustard',
  'sunflower',
  'sesame',
  'rapeseed',
  'cotton',
  'sugarcane',
  'jute',
  'potato',
  'onion',
  'tomato',
  'chilli',
]);

const PKVY_ORGANIC_CROPS = new Set([
  'cashew',
  'coconut',
  'arecanut',
  'areca-nut',
  'mango',
  'banana',
  'papaya',
  'citrus',
  'apple',
  'grape',
  'tea',
  'coffee',
  'cocoa',
  'moong',
  'cowpea',
  'chickpea',
  'lentil',
  'pigeon-pea',
  'black-gram',
  'beans',
  'peas',
  'soybean',
  'groundnut',
  'sesame',
  'sunflower',
  'vegetables',
  'tomato',
  'brinjal',
  'chilli',
  'cabbage',
  'cauliflower',
  'okra',
  'cucumber',
  'pumpkin',
  'fenugreek',
  'onion',
  'garlic',
  'potato',
  'sweet-potato',
  'alfalfa',
  'millet',
  'sorghum',
]);

const SCHEMES = [
  {
    id: 'pmKisan',
    nameKey: 'schemes.items.pmKisan.name',
    focusKey: 'schemes.items.pmKisan.focus',
    badgeKey: 'schemes.items.pmKisan.badge',
    benefitKey: 'schemes.items.pmKisan.benefit',
    benefitAmount: 6000,
    benefitUnitKey: 'schemes.perYear',
    descriptionKey: 'schemes.items.pmKisan.description',
    actionKey: 'schemes.items.pmKisan.action',
    isPrimaryAction: false,
    requiresVerification: true,
    portalUrl: 'https://pmkisan.gov.in/',
    portalDomain: 'pmkisan.gov.in',
    icon: Landmark,
    iconClass: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-300',
    badgeClass: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300',
  },
  {
    id: 'pmfby',
    nameKey: 'schemes.items.pmfby.name',
    focusKey: 'schemes.items.pmfby.focus',
    badgeKey: 'schemes.items.pmfby.badge',
    benefitKey: 'schemes.items.pmfby.benefit',
    benefitAmount: null,
    benefitUnitKey: null,
    descriptionKey: 'schemes.items.pmfby.description',
    actionKey: 'schemes.items.pmfby.action',
    isPrimaryAction: false,
    requiresVerification: true,
    portalUrl: 'https://pmfby.gov.in/',
    portalDomain: 'pmfby.gov.in',
    icon: ShieldCheck,
    iconClass: 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-300',
    badgeClass: 'bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300',
  },
  {
    id: 'pkvy',
    nameKey: 'schemes.items.pkvy.name',
    focusKey: 'schemes.items.pkvy.focus',
    badgeKey: 'schemes.items.pkvy.badge',
    benefitKey: 'schemes.items.pkvy.benefit',
    benefitAmount: 50000,
    benefitUnitKey: 'schemes.perHectare',
    descriptionKey: 'schemes.items.pkvy.description',
    actionKey: 'schemes.items.pkvy.action',
    isPrimaryAction: true,
    requiresVerification: false,
    portalUrl: 'https://pgsindia-ncof.gov.in/',
    portalDomain: 'pgsindia-ncof.gov.in',
    icon: Sprout,
    iconClass: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-300',
    badgeClass: 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300',
  },
];

const cardVariants = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
};

function isPlotVerified(plot) {
  return Boolean(plot?.isVerified === true || plot?.provenance?.verified === true);
}

function getPlotCropIds(plot) {
  const rawCrops = [plot?.primaryCrop, plot?.crop, plot?.intercrop].filter(Boolean);
  const ids = [];
  for (const raw of rawCrops) {
    const resolved = cropIdFromName(String(raw));
    if (resolved && !ids.includes(resolved)) {
      ids.push(resolved);
    }
  }
  return ids;
}

function matchesSchemeCropRule(schemeId, plot) {
  const cropIds = getPlotCropIds(plot);
  if (schemeId === 'pmfby') {
    return cropIds.some((id) => PMFBY_NOTIFIED_CROPS.has(id));
  }
  if (schemeId === 'pkvy') {
    const hasOrganicFlag = Boolean(
      plot?.isOrganic === true || plot?.organic === true || plot?.intercrop,
    );
    return hasOrganicFlag || cropIds.some((id) => PKVY_ORGANIC_CROPS.has(id));
  }
  // PM-KISAN applies to cultivable agricultural holdings with positive mapped area
  return getPlotAreaHectares(plot) > 0;
}

function evaluateSchemeEligibility(scheme, savedPlots, t, locale) {
  if (!scheme) return null;

  const verifiedPlots = savedPlots.filter(isPlotVerified);
  const cropMatchedPlots = savedPlots.filter((plot) => matchesSchemeCropRule(scheme.id, plot));
  const eligiblePlots = verifiedPlots.filter((plot) => matchesSchemeCropRule(scheme.id, plot));

  const totalSavedAreaHa = savedPlots.reduce(
    (sum, plot) => sum + getPlotAreaHectares(plot),
    0,
  );
  const eligibleAreaHa = eligiblePlots.reduce(
    (sum, plot) => sum + getPlotAreaHectares(plot),
    0,
  );

  const matchedCropIds = [];
  for (const plot of cropMatchedPlots) {
    for (const cropId of getPlotCropIds(plot)) {
      const relevant =
        scheme.id === 'pmfby'
          ? PMFBY_NOTIFIED_CROPS.has(cropId)
          : scheme.id === 'pkvy'
            ? PKVY_ORGANIC_CROPS.has(cropId) || Boolean(plot?.intercrop)
            : true;
      if (relevant && !matchedCropIds.includes(cropId)) {
        matchedCropIds.push(cropId);
      }
    }
  }

  const matchedCropNames = matchedCropIds.map((id) => getCropDisplayName(id, t));

  const verifiedCriterion = {
    id: 'verified-land',
    passed: verifiedPlots.length > 0,
    title: t('schemes.modal.critVerifiedTitle'),
    detail:
      verifiedPlots.length > 0
        ? t('schemes.modal.critVerifiedPass', {
            count: formatSpeakableNumber(verifiedPlots.length, locale, 0),
          })
        : t('schemes.modal.critVerifiedFail'),
  };

  let cropCriterion;
  let combinedCriterion;

  if (scheme.id === 'pmfby') {
    cropCriterion = {
      id: 'crop-rule',
      passed: cropMatchedPlots.length > 0,
      title: t('schemes.modal.critCropPmfbyTitle'),
      detail:
        cropMatchedPlots.length > 0
          ? t('schemes.modal.critCropPmfbyPass', {
              crops: matchedCropNames.join(', '),
            })
          : t('schemes.modal.critCropPmfbyFail'),
    };
    combinedCriterion = {
      id: 'combined-rule',
      passed: eligiblePlots.length > 0,
      title: t('schemes.modal.critCombinedPmfbyTitle'),
      detail:
        eligiblePlots.length > 0
          ? t('schemes.modal.critCombinedPmfbyPass', {
              count: formatSpeakableNumber(eligiblePlots.length, locale, 0),
            })
          : t('schemes.modal.critCombinedPmfbyFail'),
    };
  } else if (scheme.id === 'pkvy') {
    const cropsText =
      matchedCropNames.length > 0
        ? matchedCropNames.join(', ')
        : t('schemes.items.pkvy.badge');
    const withinCap = eligiblePlots.length > 0 && eligibleAreaHa <= 20;
    cropCriterion = {
      id: 'crop-rule',
      passed: cropMatchedPlots.length > 0,
      title: t('schemes.modal.critCropPkvyTitle'),
      detail:
        cropMatchedPlots.length > 0
          ? t('schemes.modal.critCropPkvyPass', { crops: cropsText })
          : t('schemes.modal.critCropPkvyFail'),
    };
    combinedCriterion = {
      id: 'combined-rule',
      passed: withinCap,
      title: t('schemes.modal.critCombinedPkvyTitle'),
      detail: withinCap
        ? t('schemes.modal.critCombinedPkvyPass', {
            area: formatSpeakableNumber(eligibleAreaHa, locale, 2),
          })
        : t('schemes.modal.critCombinedPkvyFail'),
    };
  } else {
    cropCriterion = {
      id: 'crop-rule',
      passed: cropMatchedPlots.length > 0,
      title: t('schemes.modal.critCropPmKisanTitle'),
      detail:
        cropMatchedPlots.length > 0
          ? t('schemes.modal.critCropPmKisanPass', {
              count: formatSpeakableNumber(cropMatchedPlots.length, locale, 0),
              area: formatSpeakableNumber(totalSavedAreaHa, locale, 2),
            })
          : t('schemes.modal.critCropPmKisanFail'),
    };
    combinedCriterion = {
      id: 'combined-rule',
      passed: eligiblePlots.length > 0,
      title: t('schemes.modal.critCombinedPmKisanTitle'),
      detail:
        eligiblePlots.length > 0
          ? t('schemes.modal.critCombinedPmKisanPass', {
              count: formatSpeakableNumber(eligiblePlots.length, locale, 0),
            })
          : t('schemes.modal.critCombinedPmKisanFail'),
    };
  }

  const criteria = [verifiedCriterion, cropCriterion, combinedCriterion];
  const isEligible = criteria.every((item) => item.passed);

  return {
    isEligible,
    criteria,
    verifiedPlots,
    eligiblePlots,
    eligibleAreaHa,
  };
}

function EligibilityModal({ scheme, savedPlots, onClose }) {
  const { t, languageInfo } = useTranslation();
  const locale = languageInfo.speechLang || 'en-IN';
  const isOpen = Boolean(scheme);

  useScrollLock(isOpen);

  useEffect(() => {
    if (!isOpen) return undefined;
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const evaluation = useMemo(
    () => evaluateSchemeEligibility(scheme, savedPlots, t, locale),
    [locale, savedPlots, scheme, t],
  );

  const modalSpeech = useMemo(() => {
    if (!scheme || !evaluation) return '';
    const statusTitle = evaluation.isEligible
      ? t('schemes.modal.eligibleBannerTitle')
      : t('schemes.modal.pendingBannerTitle');
    const statusSubtitle = evaluation.isEligible
      ? t('schemes.modal.eligibleBannerSubtitle', {
          count: formatSpeakableNumber(evaluation.eligiblePlots.length, locale, 0),
          area: formatSpeakableNumber(evaluation.eligibleAreaHa, locale, 2),
        })
      : t('schemes.modal.pendingBannerSubtitle');

    return buildSpeechText([
      t(scheme.nameKey),
      statusTitle,
      statusSubtitle,
      ...evaluation.criteria.map((item) => `${item.title}: ${item.detail}`),
    ]);
  }, [evaluation, locale, scheme, t]);

  if (typeof document === 'undefined') return null;

  return createPortal(
    <AnimatePresence>
      {scheme && evaluation && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="app-modal-layer fixed inset-0 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              onClose();
            }
          }}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="scheme-eligibility-title"
            initial={{ opacity: 0, y: 20, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.96 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="max-h-[90dvh] w-full max-w-lg overflow-y-auto overscroll-contain rounded-2xl border border-slate-200 bg-white p-6 text-slate-900 shadow-2xl dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            {/* Modal Header */}
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-3">
                <div
                  className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${scheme.iconClass}`}
                >
                  <scheme.icon size={22} />
                </div>
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
                    {t(scheme.focusKey)}
                  </p>
                  <h2
                    id="scheme-eligibility-title"
                    className="mt-0.5 text-xl font-black tracking-tight text-slate-900 dark:text-slate-100"
                  >
                    {t(scheme.nameKey)}
                  </h2>
                </div>
              </div>

              <div className="flex shrink-0 items-center gap-2">
                <ListenButton text={modalSpeech} variant="emerald" size="xs" />
                <button
                  type="button"
                  onClick={onClose}
                  aria-label={t('schemes.modal.closeAria')}
                  className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 text-slate-500 transition hover:bg-slate-100 hover:text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* Dynamic Overall Eligibility Banner */}
            <div
              className={`mt-5 flex items-start gap-3 rounded-xl border p-4 ${
                evaluation.isEligible
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-950 dark:border-emerald-500/30 dark:bg-emerald-500/15 dark:text-emerald-100'
                  : 'border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-500/30 dark:bg-amber-500/15 dark:text-amber-100'
              }`}
            >
              {evaluation.isEligible ? (
                <CheckCircle2
                  size={22}
                  className="mt-0.5 shrink-0 text-emerald-600 dark:text-emerald-400"
                />
              ) : (
                <AlertCircle
                  size={22}
                  className="mt-0.5 shrink-0 text-amber-600 dark:text-amber-400"
                />
              )}
              <div>
                <p className="text-sm font-extrabold">
                  {evaluation.isEligible
                    ? t('schemes.modal.eligibleBannerTitle')
                    : t('schemes.modal.pendingBannerTitle')}
                </p>
                <p
                  className={`mt-0.5 text-xs font-medium ${
                    evaluation.isEligible
                      ? 'text-emerald-800 dark:text-emerald-200/90'
                      : 'text-amber-800 dark:text-amber-200/90'
                  }`}
                >
                  {evaluation.isEligible
                    ? t('schemes.modal.eligibleBannerSubtitle', {
                        count: formatSpeakableNumber(evaluation.eligiblePlots.length, locale, 0),
                        area: formatSpeakableNumber(evaluation.eligibleAreaHa, locale, 2),
                      })
                    : t('schemes.modal.pendingBannerSubtitle')}
                </p>
              </div>
            </div>

            {/* Dynamic Criteria Checklist */}
            <div className="mt-5">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                {t('schemes.modal.criteriaHeading')}
              </h3>
              <ul className="mt-2.5 space-y-2.5">
                {evaluation.criteria.map((criterion) => (
                  <li
                    key={criterion.id}
                    className={`flex items-start gap-3 rounded-xl border p-3.5 ${
                      criterion.passed
                        ? 'border-emerald-200/80 bg-emerald-50/50 dark:border-emerald-500/25 dark:bg-slate-800/80'
                        : 'border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/50'
                    }`}
                  >
                    <div
                      className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${
                        criterion.passed
                          ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-400'
                          : 'bg-amber-100 text-amber-600 dark:bg-amber-500/20 dark:text-amber-400'
                      }`}
                    >
                      {criterion.passed ? (
                        <CheckCircle2 size={15} />
                      ) : (
                        <AlertCircle size={15} />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-bold text-slate-900 dark:text-slate-100">
                        {criterion.title}
                      </p>
                      <p className="mt-0.5 text-xs font-medium text-slate-600 dark:text-slate-400">
                        {criterion.detail}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>

            {/* Qualifying Verified Plots from Dexie */}
            {evaluation.eligiblePlots.length > 0 ? (
              <div className="mt-5">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  {t('schemes.modal.matchedPlotsHeading')}
                </h3>
                <div className="mt-2.5 space-y-2">
                  {evaluation.eligiblePlots.map((plot) => {
                    const primaryCropId = getPlotCropIds(plot)[0] || null;
                    const cropLabel = primaryCropId
                      ? getCropDisplayName(primaryCropId, t)
                      : t('common.primaryCrop');
                    const areaHa = formatSpeakableNumber(
                      getPlotAreaHectares(plot),
                      locale,
                      2,
                    );

                    return (
                      <div
                        key={plot.id}
                        className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800"
                      >
                        <div className="flex min-w-0 items-center gap-3">
                          {primaryCropId ? (
                            <CropImage cropId={primaryCropId} size="sm" />
                          ) : (
                            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300">
                              <MapPin size={15} />
                            </div>
                          )}
                          <div className="min-w-0">
                            <p className="truncate text-sm font-bold text-slate-900 dark:text-slate-100">
                              {plot.name}
                            </p>
                            <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                              {cropLabel} · {t('schemes.modal.plotAreaHa', { area: areaHa })}
                            </p>
                          </div>
                        </div>
                        <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-1 text-[11px] font-bold text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-300">
                          <CheckCircle2 size={12} />
                          <span>{t('schemes.modal.verifiedPlotPill')}</span>
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="mt-5 flex flex-col gap-2.5 rounded-xl border border-slate-200 bg-slate-50 p-3.5 dark:border-slate-700 dark:bg-slate-800 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs font-medium text-slate-600 dark:text-slate-300">
                  {t('schemes.modal.noVerifiedPlotsHint')}
                </p>
                <Link
                  to="/farm"
                  onClick={onClose}
                  className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-xl border border-emerald-600 px-3 py-2 text-xs font-bold text-emerald-700 transition hover:bg-emerald-50 dark:border-emerald-500 dark:text-emerald-300 dark:hover:bg-emerald-500/10"
                >
                  <span>{t('schemes.modal.goToFarmLink')}</span>
                  <ArrowRight size={13} />
                </Link>
              </div>
            )}

            {/* Financial Benefit & Official Portal Actions */}
            <div className="mt-5 rounded-xl bg-slate-50 px-4 py-3 dark:bg-slate-800/80">
              <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                {t('schemes.financialBenefit')}
              </p>
              <p className="mt-0.5 text-base font-black text-slate-900 dark:text-slate-100">
                {t(scheme.benefitKey)}
              </p>
            </div>

            <div className="mt-6 flex flex-col-reverse gap-2.5 sm:flex-row sm:items-center">
              <button
                type="button"
                onClick={onClose}
                className="inline-flex h-11 items-center justify-center rounded-xl border border-slate-200 px-4 text-sm font-bold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
              >
                {t('common.close')}
              </button>
              <a
                href={scheme.portalUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-11 flex-1 items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 text-sm font-bold text-white shadow-sm transition hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
              >
                <span>
                  {t('schemes.modal.openOfficialPortal', { domain: scheme.portalDomain })}
                </span>
                <ExternalLink size={16} />
              </a>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

export default function SchemesHub() {
  const { t, languageInfo } = useTranslation();
  const locale = languageInfo.speechLang;
  const [selectedScheme, setSelectedScheme] = useState(null);
  const rawPlots = useLiveQuery(() => db.plots.toArray(), []);
  const savedPlots = useMemo(() => rawPlots || [], [rawPlots]);

  const verifiedCount = useMemo(
    () => savedPlots.filter(isPlotVerified).length,
    [savedPlots],
  );

  const overviewSpeech = useMemo(
    () =>
      buildSpeechText([
        t('schemes.title'),
        t('schemes.subtitle'),
        ...SCHEMES.map((s) => {
          const spokenBenefit = s.benefitAmount
            ? formatSpeakablePriceWithUnit(s.benefitAmount, t(s.benefitUnitKey), locale)
            : t(s.benefitKey);
          return `${t(s.nameKey)}: ${t(s.focusKey)}, ${spokenBenefit}`;
        }),
      ]),
    [locale, t],
  );

  return (
    <div className="min-h-screen bg-slate-50 px-4 pb-12 pt-24 dark:bg-slate-950 sm:px-6 lg:px-8">
      <motion.main
        initial="hidden"
        animate="show"
        transition={{ staggerChildren: 0.08 }}
        className="mx-auto flex max-w-7xl flex-col gap-6"
      >
        <motion.header
          variants={cardVariants}
          className="flex flex-wrap items-start justify-between gap-4"
        >
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-emerald-700 dark:text-emerald-400">
              {t('schemes.eyebrow')}
            </p>
            <h1 className="mt-1 text-3xl font-black tracking-tight text-slate-900 dark:text-slate-100">
              {t('schemes.title')}
            </h1>
            <p className="mt-2 text-sm font-medium text-slate-500 dark:text-slate-400">
              {t('schemes.subtitle')}
            </p>
          </div>
          <ListenButton text={overviewSpeech} variant="emerald" size="md" />
        </motion.header>

        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
          {SCHEMES.map((scheme) => {
            const Icon = scheme.icon;
            const eligibilityText = scheme.requiresVerification
              ? verifiedCount > 0
                ? t('schemes.eligibleFields', { count: String(verifiedCount) })
                : t('schemes.linkToUnlock')
              : '';
            const spokenBenefit = scheme.benefitAmount
              ? formatSpeakablePriceWithUnit(scheme.benefitAmount, t(scheme.benefitUnitKey), locale)
              : t(scheme.benefitKey);
            const cardSpeech = buildSpeechText([
              t(scheme.nameKey),
              t(scheme.focusKey),
              t(scheme.badgeKey),
              t(scheme.descriptionKey),
              eligibilityText,
              `${t('schemes.financialBenefit')}: ${spokenBenefit}`,
            ]);

            return (
              <motion.article
                key={scheme.id}
                variants={cardVariants}
                className="flex flex-col rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${scheme.iconClass}`}>
                    <Icon size={23} />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${scheme.badgeClass}`}>
                      {t(scheme.badgeKey)}
                    </span>
                    <ListenButton text={cardSpeech} variant="emerald" size="xs" />
                  </div>
                </div>
                <div className="mt-5 flex-1">
                  <p className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    {t(scheme.focusKey)}
                  </p>
                  <h2 className="mt-1 text-xl font-black tracking-tight text-slate-900 dark:text-slate-100">
                    {t(scheme.nameKey)}
                  </h2>
                  <p className="mt-3 text-sm font-medium leading-6 text-slate-500 dark:text-slate-400">
                    {t(scheme.descriptionKey)}
                  </p>
                  {scheme.requiresVerification && (
                    <p className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-200">
                      {eligibilityText}
                    </p>
                  )}
                </div>
                <div className="mt-5 rounded-xl bg-slate-50 px-3.5 py-3 dark:bg-slate-800/80">
                  <p className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    {t('schemes.financialBenefit')}
                  </p>
                  <p className="mt-1 text-lg font-black text-slate-900 dark:text-slate-100">
                    {t(scheme.benefitKey)}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedScheme(scheme)}
                  className={`mt-5 inline-flex h-11 items-center justify-center gap-2 rounded-xl px-4 text-sm font-bold transition focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 ${
                    scheme.isPrimaryAction
                      ? 'bg-emerald-600 text-white shadow-sm hover:bg-emerald-700'
                      : 'border border-slate-200 text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700'
                  }`}
                >
                  <span>{t(scheme.actionKey)}</span>
                  <ArrowRight size={16} />
                </button>
              </motion.article>
            );
          })}
        </div>
      </motion.main>

      <EligibilityModal
        scheme={selectedScheme}
        savedPlots={savedPlots}
        onClose={() => setSelectedScheme(null)}
      />
    </div>
  );
}
