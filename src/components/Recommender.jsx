import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useLiveQuery } from 'dexie-react-hooks';
import { db } from '../db/db';
import { useTranslation } from '../context/LanguageContext';
import VerificationBadge from './VerificationBadge';
import CropImage from './CropImage';
import CropPicker from './CropPicker';
import ListenButton from './ui/ListenButton';
import {
    cropIdFromName,
    getCrop,
    getCropDisplayName,
    getCropLocalName,
    isRealCropId,
} from '../data/crops';
import { getPlotAreaHectares, runOfflineRotationEngine } from '../services/rotationEngine';
import {
    RECOMMENDER_LOADING_STEPS,
    TOTAL_MOCK_DELAY_MS,
} from '../services/mockEngine';
import {
    formatSpeakableCurrency,
    formatSpeakableNumber,
    formatSpeakablePercent,
    formatSpeakablePriceWithUnit,
    formatSpeakableWeightKg,
} from '../utils/speechText';
import {
    Sprout,
    Sparkles,
    Droplets,
    CheckCircle2,
    ArrowRight,
    RotateCcw,
    Calendar,
    MapPin,
    Leaf,
    DollarSign,
    Layers,
    Info,
    Sun,
    CloudRain,
    Check,
    Zap,
    AlertCircle,
    Award,
    Microscope,
    TrendingUp,
    ShieldCheck,
    Landmark,
} from 'lucide-react';

// ── Lucide icon map for dynamic loading step icons ────────────────────────────
const STEP_ICON_MAP = { Microscope, TrendingUp, Sprout, Leaf, CloudRain, Layers };

// ==========================================
// FEATURE 2 & 3: OFFLINE AGRONOMIC RULE ENGINE
// ==========================================
export default function Recommender() {
    const [searchParams] = useSearchParams();
    const queryPlotId = searchParams.get('plotId') || '';
    const { t, languageInfo } = useTranslation();
    const speechLocale = languageInfo.speechLang;

    // 1. Fetch plots offline from Dexie IndexedDB
    const plots = useLiveQuery(() => db.plots.toArray());

    // Form inputs state
    const [selectedPlotId, setSelectedPlotId] = useState(queryPlotId);
    const [season, setSeason] = useState('Rabi');
    const [previousCrop, setPreviousCrop] = useState('wheat');
    const [customCrop, setCustomCrop] = useState('');
    const [isCustomCropActive, setIsCustomCropActive] = useState(false);

    // Engine calculation state
    const [isCalculating, setIsCalculating] = useState(false);
    const [customCalculations, setCustomCalculations] = useState(null);
    const [selectedCropRecord, setSelectedCropRecord] = useState(null);
    const [toastMessage, setToastMessage] = useState(null);

    // ── Premium multi-step loading sequence state ─────────────────────────────
    const [loadingStepIndex, setLoadingStepIndex] = useState(-1);
    const stepTimersRef = useRef([]);
    const loadingViewRef = useRef(null);

    // Derived active plot object (handles initial fallback without effect-based setState)
    const currentPlot = useMemo(() => {
        if (!plots || plots.length === 0) return null;
        if (selectedPlotId) {
            const found = plots.find((p) => String(p.id) === String(selectedPlotId));
            if (found) return found;
        }
        return plots[0];
    }, [plots, selectedPlotId]);

    const isCurrentPlotVerified = Boolean(
        currentPlot?.isVerified === true || currentPlot?.provenance?.verified === true,
    );

    const activePreviousCropRaw =
        isCustomCropActive && customCrop.trim() ? customCrop.trim() : previousCrop;

    const previousCropLabel = useMemo(() => {
        const matchedId = cropIdFromName(activePreviousCropRaw);
        if (matchedId) {
            return getCropDisplayName(matchedId, t);
        }
        return activePreviousCropRaw;
    }, [activePreviousCropRaw, t]);

    const translatedSteps = useMemo(() => {
        const values = {
            plotName: currentPlot?.name || t('recommender.yourPlot'),
            area: currentPlot?.area || '—',
            unit: currentPlot?.areaUnit || t('recommender.defaultAreaUnit'),
            previousCrop: previousCropLabel,
            season: t(`recommender.seasons.${season}`),
            region: currentPlot?.village || t('recommender.regionFallback'),
        };
        return RECOMMENDER_LOADING_STEPS.map((step) => ({
            ...step,
            label: t(step.titleKey),
            subLabel: t(step.detailKey, values),
        }));
    }, [currentPlot, previousCropLabel, season, t]);

    useEffect(() => () => {
        stepTimersRef.current.forEach(clearTimeout);
        stepTimersRef.current = [];
    }, []);

    useEffect(() => {
        if (!isCalculating || !loadingViewRef.current) return;
        const prefersReducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
        loadingViewRef.current.scrollIntoView({
            behavior: prefersReducedMotion ? 'auto' : 'smooth',
            block: 'start',
        });
    }, [isCalculating]);

    // Decorate recommendations in the active language so UI and voice stay 100% in sync
    const recommendations = useMemo(() => {
        if (!customCalculations) return null;
        return customCalculations.map((crop) => {
            const translatedCropName = getCropDisplayName(crop.id, t);
            const translatedLocalName = getCropLocalName(crop.id, t) || translatedCropName;
            const rankTag = t(crop.rankTagKey, {
                rank: formatSpeakableNumber(crop.rank, speechLocale, 0),
            });
            const family = t(crop.familyKey);
            const duration = t('recommender.durationRangeDays', {
                min: formatSpeakableNumber(crop.durationMinDays, speechLocale, 0),
                max: formatSpeakableNumber(crop.durationMaxDays, speechLocale, 0),
            });
            const waterNeed = t(crop.waterNeedKey);
            const fertilizerName = t(crop.fertilizerKey);
            const formattedKg = formatSpeakableNumber(crop.fertilizerReductionKg, speechLocale, 1);

            const nitrogenReason = t(crop.nitrogenReasonKey, {
                crop: translatedCropName,
                kg: formattedKg,
                fertilizer: fertilizerName,
            });
            const rootReason = t(crop.rootReasonKey, {
                prevDepth: t(crop.prevRootDepthKey),
                currDepth: t(crop.currRootDepthKey),
            });
            const plainReason = `${nitrogenReason} ${rootReason}`;

            const netReturnFormatted = `₹${formatSpeakableNumber(crop.netReturn, speechLocale, 0)} / ${t('recommender.plotUnit')}`;
            const netReturnSpoken = formatSpeakablePriceWithUnit(
                crop.netReturn,
                t('recommender.perPlot'),
                speechLocale,
            );
            const netReturnDelta = t('recommender.netReturnDelta', {
                pct: formatSpeakableNumber(crop.percentageGain, speechLocale, 0),
            });
            const fertilizerSavedLabel = t('recommender.savesFertilizerKg', {
                kg: formattedKg,
                fertilizer: fertilizerName,
            });
            const fertilizerCostSavings = t('recommender.estimatedFertilizerSavings', {
                amount: `₹${formatSpeakableNumber(crop.fertilizerSavingsInr, speechLocale, 0)}`,
            });

            const pmfbyBadgeLabel = crop.pmfbyInsured
                ? crop.pmfbySeasonType === 'Rabi'
                    ? t('recommender.pmfbyInsuredRabi')
                    : t('recommender.pmfbyInsuredKharif')
                : null;
            const nfsmBadgeLabel = crop.nfsmSubsidyEligible
                ? t('recommender.nfsmSubsidyEligible')
                : null;

            const profitAdjustmentNote =
                crop.pmfbyInsured && crop.nfsmSubsidyEligible
                    ? t('recommender.includesSubsidyAndPmfby', {
                          subsidy: `₹${formatSpeakableNumber(crop.subsidyBonusInr, speechLocale, 0)}`,
                          premium: `₹${formatSpeakableNumber(crop.pmfbyPremiumInr, speechLocale, 0)}`,
                      })
                    : crop.pmfbyInsured
                      ? t('recommender.includesPmfbyPremium', {
                            premium: `₹${formatSpeakableNumber(crop.pmfbyPremiumInr, speechLocale, 0)}`,
                        })
                      : crop.nfsmSubsidyEligible
                        ? t('recommender.includesNfsmSubsidy', {
                              subsidy: `₹${formatSpeakableNumber(crop.subsidyBonusInr, speechLocale, 0)}`,
                          })
                        : null;

            const speechParts = [
                translatedCropName,
                rankTag,
                ...(pmfbyBadgeLabel ? [pmfbyBadgeLabel] : []),
                ...(nfsmBadgeLabel ? [nfsmBadgeLabel] : []),
                plainReason,
                t('recommender.cardReturnSpeech', {
                    netReturn: netReturnSpoken,
                    gain: formatSpeakablePercent(crop.percentageGain, speechLocale, 0),
                }),
                t('recommender.cardFertilizerSpeech', {
                    weight: formatSpeakableWeightKg(crop.fertilizerReductionKg, speechLocale),
                    fertilizer: fertilizerName,
                    savings: formatSpeakableCurrency(crop.fertilizerSavingsInr, speechLocale),
                }),
                t('recommender.cardWaterSpeech', {
                    waterNeed,
                    duration,
                }),
            ];

            return {
                ...crop,
                translatedCropName,
                translatedLocalName,
                rankTag,
                family,
                duration,
                waterNeed,
                fertilizerName,
                plainReason,
                netReturnFormatted,
                netReturnSpoken,
                netReturnDelta,
                fertilizerSavedLabel,
                fertilizerCostSavings,
                pmfbyBadgeLabel,
                nfsmBadgeLabel,
                profitAdjustmentNote,
                speechParts,
            };
        });
    }, [customCalculations, speechLocale, t]);

    const summarySpeechParts = useMemo(() => {
        if (!recommendations || recommendations.length === 0) return [];
        const top = recommendations[0];
        return [
            t('recommender.resultsSummaryIntro', {
                plot: currentPlot?.name || t('recommender.yourPlot'),
                previousCrop: previousCropLabel,
                season: t(`recommender.seasonNames.${season}`),
            }),
            t('recommender.resultsSummaryTop', {
                crop: top.translatedCropName,
                reason: top.plainReason,
                weight: formatSpeakableWeightKg(top.fertilizerReductionKg, speechLocale),
                fertilizer: top.fertilizerName,
                netReturn: top.netReturnSpoken,
            }),
        ];
    }, [currentPlot?.name, previousCropLabel, recommendations, season, speechLocale, t]);

    const showToast = useCallback((msg) => {
        setToastMessage(msg);
        setTimeout(() => {
            setToastMessage(null);
        }, 3600);
    }, []);

    // Quick seed demo plot if Dexie DB has no plots yet (Zero-friction onboarding)
    const handleAddDemoPlot = async () => {
        try {
            const demoId = await db.plots.add({
                name: 'East Canal Block',
                area: '3.5 Acres',
                areaUnit: 'acres',
                areaHectares: 1.4164,
                village: 'Rampur',
                serverId: null,
                isVerified: false,
                source: 'manual',
            });
            setSelectedPlotId(String(demoId));
            showToast(t('recommender.demoPlotSavedToast'));
        } catch (err) {
            console.error('Failed to create demo plot:', err);
        }
    };

    const handleCalculate = (e) => {
        if (e) e.preventDefault();
        const activePrev = activePreviousCropRaw;

        stepTimersRef.current.forEach(clearTimeout);
        stepTimersRef.current = [];

        setIsCalculating(true);
        setLoadingStepIndex(0);

        let elapsed = 0;
        translatedSteps.forEach((step, idx) => {
            if (idx === 0) return;
            elapsed += RECOMMENDER_LOADING_STEPS[idx - 1].durationMs;
            const timer = setTimeout(() => setLoadingStepIndex(idx), elapsed);
            stepTimersRef.current.push(timer);
        });

        const finalTimer = setTimeout(() => {
            const results = runOfflineRotationEngine(
                season,
                activePrev,
                getPlotAreaHectares(currentPlot),
                isRealCropId,
                isCurrentPlotVerified,
            );
            setCustomCalculations(results);
            setIsCalculating(false);
            setLoadingStepIndex(-1);
        }, TOTAL_MOCK_DELAY_MS);
        stepTimersRef.current.push(finalTimer);
    };

    // User chooses a recommended crop: Offline-first Dexie Sync Queue entry
    const handleSelectCrop = async (crop) => {
        setSelectedCropRecord(crop);
        const now = new Date().getTime();
        const cropName = crop.translatedCropName || getCropDisplayName(crop.id, t);

        try {
            await db.syncQueue.add({
                action: 'ASSIGN_PLOT_ROTATION',
                payload: {
                    plotId: currentPlot?.id,
                    plotName: currentPlot?.name,
                    cropId: crop.id,
                    cropName,
                    season,
                    previousCrop: activePreviousCropRaw,
                    netReturn: crop.netReturn,
                    fertilizerSavedKg: crop.fertilizerReductionKg,
                    areaHectares: getPlotAreaHectares(currentPlot),
                    timestamp: now,
                },
                status: 'pending',
                timestamp: now,
            });

            showToast(t('recommender.cropSelectedToast', { crop: cropName }));
        } catch (error) {
            console.error('Error queuing rotation selection:', error);
            showToast(t('recommender.cropSelectedFallbackToast', { crop: cropName }));
        }
    };

    const seasonsList = [
        {
            id: 'Rabi',
            name: t('recommender.seasonNames.Rabi'),
            label: t('recommender.seasonRanges.Rabi'),
            icon: Sprout,
        },
        {
            id: 'Kharif',
            name: t('recommender.seasonNames.Kharif'),
            label: t('recommender.seasonRanges.Kharif'),
            icon: CloudRain,
        },
        {
            id: 'Zaid',
            name: t('recommender.seasonNames.Zaid'),
            label: t('recommender.seasonRanges.Zaid'),
            icon: Sun,
        },
    ];

    return (
        <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 pb-24 font-sans selection:bg-emerald-100 selection:text-emerald-900">
            {/* Top Navigation Bar */}
            <div className="relative z-0 border-b border-slate-200 bg-white px-4 py-3 dark:border-slate-700/80 dark:bg-slate-900 sm:px-6">
                <div className="max-w-3xl mx-auto flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                        <Link
                            to="/"
                            className="p-2 -ml-2 rounded-xl text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors focus:ring-2 focus:ring-emerald-500"
                            aria-label={t('recommender.backToPlots')}
                        >
                            <RotateCcw size={18} />
                        </Link>
                        <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                                <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
                                    {t('recommender.pageTitle')}
                                </h1>
                                <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-800 dark:border-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-200">
                                    <Zap size={10} className="fill-emerald-600 text-emerald-600" />
                                    {t('recommender.offlineReady')}
                                </span>
                            </div>
                            <p className="text-xs text-slate-500 dark:text-slate-400 hidden sm:block">
                                {t('recommender.pageSubtitle')}
                            </p>
                        </div>
                    </div>

                    {/* Global Page Voice Listen Button */}
                    <ListenButton
                        id="screen-overview"
                        labelKey="recommender.explainScreen"
                        textKey="recommender.screenOverviewSpeech"
                    />
                </div>
            </div>

            <main className="max-w-3xl mx-auto px-4 sm:px-6 pt-6 space-y-6">
                {/* ========================================================= */}
                {/* SECTION 1: THE PLOT & CONTEXT FORM (INPUT)                */}
                {/* ========================================================= */}
                <motion.section
                    initial={{ opacity: 0, y: 15 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.35 }}
                    className="bg-white dark:bg-slate-900 rounded-3xl p-5 sm:p-7 shadow-sm border border-slate-200 dark:border-slate-700/90 relative overflow-hidden"
                >
                    {/* Top Accent Gradient Border */}
                    <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-emerald-500 via-teal-500 to-emerald-600" />

                    <div className="flex items-start justify-between gap-3 mb-5">
                        <div>
                            <span className="rounded-lg bg-emerald-50 px-2.5 py-1 text-xs font-bold uppercase tracking-wider text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">
                                {t('recommender.step1Badge')}
                            </span>
                            <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 mt-2">
                                {t('recommender.tellUsTitle')}
                            </h2>
                            <p className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">
                                {t('recommender.tellUsSubtitle')}
                            </p>
                        </div>

                        <ListenButton
                            id="form-instructions"
                            labelKey="recommender.listen"
                            textKey="recommender.formInstructionsSpeech"
                        />
                    </div>

                    <form onSubmit={handleCalculate} className="space-y-6">
                        {/* 1.1 Plot Selection */}
                        <div>
                            <div className="text-sm font-semibold text-slate-800 dark:text-slate-200 mb-2 flex items-center justify-between">
                                <span className="flex items-center gap-1.5">
                                    <MapPin size={16} className="text-emerald-600" />
                                    {t('recommender.selectPlotLabel')}
                                </span>
                                {plots && plots.length > 0 && (
                                    <span className="text-xs font-normal text-slate-500 dark:text-slate-400">
                                        {t('recommender.plotsSavedCount', {
                                            count: formatSpeakableNumber(plots.length, speechLocale, 0),
                                        })}
                                    </span>
                                )}
                            </div>

                            {/* Loading State Skeleton for Dexie LiveQuery */}
                            {plots === undefined ? (
                                <div className="animate-pulse bg-slate-100 dark:bg-slate-800 rounded-2xl h-14 w-full flex items-center px-4">
                                    <div className="h-4 bg-slate-200 rounded w-1/3"></div>
                                </div>
                            ) : plots.length === 0 ? (
                                /* Empty DB Fallback with Instant 1-Click Demo Plot */
                                <div className="flex flex-col items-start justify-between gap-3 rounded-2xl border border-amber-200/80 bg-amber-50 p-4 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100 sm:flex-row sm:items-center">
                                    <div className="flex items-center gap-2">
                                        <AlertCircle size={20} className="text-amber-600 shrink-0" />
                                        <div className="text-xs sm:text-sm">
                                            <p className="font-semibold">{t('recommender.noPlotsTitle')}</p>
                                            <p className="text-amber-700 dark:text-amber-200/80">
                                                {t('recommender.noPlotsSubtitle')}
                                            </p>
                                        </div>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={handleAddDemoPlot}
                                        className="shrink-0 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold px-3 py-2 rounded-xl shadow-sm transition-colors"
                                    >
                                        {t('recommender.quickAddDemoPlot')}
                                    </button>
                                </div>
                            ) : (
                                /* Plot Selector Carousel / Grid */
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                                    {plots.map((plot) => {
                                        const isSelected = String(plot.id) === String(currentPlot?.id);
                                        return (
                                            <button
                                                key={plot.id}
                                                type="button"
                                                onClick={() => {
                                                    setSelectedPlotId(String(plot.id));
                                                    setCustomCalculations(null);
                                                }}
                                                className={`text-left p-3.5 rounded-2xl border-2 transition-all flex items-center justify-between focus:outline-none focus:ring-2 focus:ring-emerald-500 ${
                                                    isSelected
                                                        ? 'border-emerald-500 bg-emerald-50/70 text-emerald-950 shadow-sm dark:border-emerald-400 dark:bg-emerald-500/15 dark:text-emerald-100'
                                                        : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 bg-white dark:bg-slate-900'
                                                }`}
                                            >
                                                <div className="truncate">
                                                    <div className={`flex flex-wrap items-center gap-1.5 text-sm font-bold ${isSelected ? 'text-emerald-950 dark:text-emerald-100' : 'text-slate-900 dark:text-slate-100'}`}>
                                                        <span>{plot.name}</span>
                                                        <VerificationBadge isVerified={plot.isVerified || plot.provenance?.verified} providerName={plot.providerId} />
                                                        {isSelected && (
                                                            <CheckCircle2 size={16} className="text-emerald-600 shrink-0" />
                                                        )}
                                                    </div>
                                                    {plot.surveyNumber && (
                                                        <div className={`mt-1 text-[11px] ${isSelected ? 'text-emerald-700 dark:text-emerald-200/75' : 'text-slate-500 dark:text-slate-400'}`}>
                                                            {plot.surveyNumber}
                                                        </div>
                                                    )}
                                                    <div className={`mt-0.5 flex items-center gap-2 text-xs ${isSelected ? 'text-emerald-700 dark:text-emerald-200/75' : 'text-slate-500 dark:text-slate-400'}`}>
                                                        <span>{plot.area || t('recommender.standardAcre')}</span>
                                                        <span>•</span>
                                                        <span>{plot.village || t('recommender.localVillage')}</span>
                                                    </div>
                                                </div>
                                                <span className={`rounded-md px-2 py-0.5 text-[11px] font-semibold ${isSelected ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-400/20 dark:text-emerald-100' : 'bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-400'}`}>
                                                    #{plot.id}
                                                </span>
                                            </button>
                                        );
                                    })}
                                </div>
                            )}
                        </div>

                        {/* 1.2 Upcoming Season Selector */}
                        <div>
                            <label className="block text-sm font-semibold text-slate-800 dark:text-slate-200 mb-2 flex items-center gap-1.5">
                                <Calendar size={16} className="text-emerald-600" />
                                {t('recommender.upcomingSeasonLabel')}
                            </label>
                            <div className="grid grid-cols-3 gap-2.5">
                                {seasonsList.map((item) => {
                                    const IconComponent = item.icon;
                                    const isSelected = season === item.id;
                                    return (
                                        <button
                                            key={item.id}
                                            type="button"
                                            onClick={() => {
                                                setSeason(item.id);
                                                setCustomCalculations(null);
                                            }}
                                            className={`p-3 rounded-2xl border-2 flex flex-col items-center justify-center text-center transition-all min-h-[76px] focus:outline-none focus:ring-2 focus:ring-emerald-500 ${
                                                isSelected
                                                    ? 'border-emerald-600 bg-emerald-600 text-white shadow-md'
                                                    : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300'
                                            }`}
                                        >
                                            <IconComponent
                                                size={20}
                                                className={`mb-1 ${isSelected ? 'text-white' : 'text-emerald-700'}`}
                                            />
                                            <span className="font-bold text-sm leading-tight">{item.name}</span>
                                            <span className={`text-[10px] mt-0.5 line-clamp-1 ${isSelected ? 'text-emerald-100' : 'text-slate-400'}`}>
                                                {item.label}
                                            </span>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        {/* 1.3 Previous Harvested Crop */}
                        <div>
                            <div className="flex items-center justify-between mb-2">
                                <label className="text-sm font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                                    <Layers size={16} className="text-emerald-600" />
                                    {t('recommender.previousCrop')}
                                </label>
                                <button
                                    type="button"
                                    onClick={() => {
                                        setIsCustomCropActive(!isCustomCropActive);
                                        if (!isCustomCropActive) setCustomCrop('');
                                        setCustomCalculations(null);
                                    }}
                                    className="text-xs text-emerald-700 hover:text-emerald-800 font-semibold underline underline-offset-2 dark:text-emerald-300"
                                >
                                    {isCustomCropActive
                                        ? t('recommender.chooseFromList')
                                        : t('recommender.otherCropBtn')}
                                </button>
                            </div>

                            {!isCustomCropActive ? (
                                <CropPicker
                                    value={cropIdFromName(previousCrop)}
                                    onChange={(cropId) => {
                                        setPreviousCrop(getCrop(cropId).id);
                                        setCustomCalculations(null);
                                    }}
                                    label={t('recommender.previousCrop')}
                                />
                            ) : (
                                <div className="relative">
                                    <input
                                        type="text"
                                        placeholder={t('recommender.customCropPlaceholder')}
                                        value={customCrop}
                                        onChange={(e) => {
                                            setCustomCrop(e.target.value);
                                            setCustomCalculations(null);
                                        }}
                                        className="w-full bg-slate-50 dark:bg-slate-950 border-2 border-slate-200 dark:border-slate-700 focus:border-emerald-600 p-3 rounded-2xl outline-none text-sm transition-all focus:ring-2 focus:ring-emerald-500"
                                        autoFocus
                                    />
                                </div>
                            )}
                        </div>

                        {/* Submit Button */}
                        <motion.button
                            type="submit"
                            disabled={isCalculating}
                            whileHover={{ scale: 1.01 }}
                            whileTap={{ scale: 0.97 }}
                            className="w-full relative overflow-hidden bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold py-4 px-6 rounded-2xl shadow-lg shadow-emerald-700/25 flex items-center justify-center gap-2 text-base tracking-tight transition-all disabled:opacity-70 focus:outline-none focus:ring-4 focus:ring-emerald-400/40 min-h-[54px]"
                        >
                            <motion.div
                                className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/10 to-white/0 pointer-events-none"
                                animate={{ x: ['-100%', '100%'] }}
                                transition={{ duration: 2.5, repeat: Infinity, ease: 'linear', repeatDelay: 1.5 }}
                            />
                            {isCalculating ? (
                                <>
                                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                    <span>{t('recommender.buildingPlan')}</span>
                                </>
                            ) : (
                                <>
                                    <Sparkles size={18} />
                                    <span>{t('recommender.calculateBestRotations')}</span>
                                    <ArrowRight size={18} className="ml-1" />
                                </>
                            )}
                        </motion.button>
                    </form>
                </motion.section>

                {/* ========================================================= */}
                {/* SECTION 2: RANKED RESULT CARDS (OUTPUT)                   */}
                {/* ========================================================= */}
                <section className="space-y-4">
                    {/* Results Header Bar */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-2">
                        <div>
                            <div className="flex items-center gap-2">
                                <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
                                    {t('recommender.recommendedNextCrops')}
                                </h2>
                                {recommendations && (
                                    <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-bold text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-200">
                                        {t('recommender.optionsCount', {
                                            count: formatSpeakableNumber(recommendations.length, speechLocale, 0),
                                        })}
                                    </span>
                                )}
                            </div>
                            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                                {t('recommender.tailoredContext', {
                                    plot: currentPlot ? currentPlot.name : t('recommender.yourPlot'),
                                    previousCrop: previousCropLabel,
                                    season: t(`recommender.seasonNames.${season}`),
                                })}
                            </p>
                        </div>

                        {recommendations && recommendations.length > 0 && (
                            <ListenButton
                                id="results-overview"
                                labelKey="recommender.listenSummary"
                                text={summarySpeechParts}
                            />
                        )}
                    </div>

                    {/* PREMIUM MULTI-STEP LOADING SEQUENCE */}
                    <AnimatePresence mode="wait">
                        {isCalculating && (
                            <motion.div
                                key="loading-sequence"
                                ref={loadingViewRef}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -10 }}
                                transition={{ duration: 0.3 }}
                                className="py-4 space-y-3"
                                aria-label={t('recommender.loadingHeader')}
                                role="status"
                            >
                                <div className="mb-4 flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
                                    <CropImage
                                        cropId={cropIdFromName(activePreviousCropRaw)}
                                        size="md"
                                        showName
                                    />
                                    <div className="min-w-0">
                                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                                            {t('recommender.analysingPlot')}
                                        </p>
                                        <p className="truncate text-sm font-bold text-slate-900 dark:text-slate-100">
                                            {currentPlot?.name || t('recommender.yourPlot')}
                                        </p>
                                    </div>
                                </div>
                                <div className="mb-4 flex items-center justify-between gap-2">
                                    <div className="flex gap-1">
                                        {RECOMMENDER_LOADING_STEPS.map((step, i) => (
                                            <motion.span
                                                key={step.id}
                                                className={`block h-1.5 w-5 rounded-full ${loadingStepIndex >= i ? 'bg-emerald-500' : 'bg-slate-200 dark:bg-slate-700'}`}
                                            />
                                        ))}
                                    </div>
                                    <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">
                                        {t('recommender.stepProgress', {
                                            current: Math.min(loadingStepIndex + 1, 6),
                                            total: 6,
                                        })}
                                    </span>
                                </div>

                                {/* Step cards */}
                                {translatedSteps.map((step, idx) => {
                                    const StepIcon = STEP_ICON_MAP[step.icon] || Sprout;
                                    const isDone = loadingStepIndex > idx;
                                    const isActive = loadingStepIndex === idx;
                                    const isPending = loadingStepIndex < idx;

                                    return (
                                        <motion.div
                                            key={step.id}
                                            initial={{ opacity: 0, x: -16 }}
                                            animate={{
                                                opacity: isPending ? 0.35 : 1,
                                                x: 0,
                                            }}
                                            transition={{ duration: 0.4, delay: idx * 0.05 }}
                                            className={`flex items-center gap-3.5 p-4 rounded-2xl border transition-all ${
                                                isActive
                                                    ? 'bg-emerald-50 border-emerald-200/80 shadow-sm shadow-emerald-100 dark:bg-emerald-500/15 dark:border-emerald-400/60 dark:shadow-emerald-950/30'
                                                    : isDone
                                                    ? 'bg-slate-50 dark:bg-slate-950 border-slate-200 dark:border-slate-700/60'
                                                    : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-700/40'
                                            }`}
                                        >
                                            <div className={`shrink-0 w-9 h-9 rounded-xl flex items-center justify-center transition-all ${
                                                isActive ? 'bg-emerald-500 text-white shadow-md shadow-emerald-400/30'
                                                : isDone ? 'bg-slate-200 text-slate-500 dark:text-slate-400'
                                                : 'bg-slate-100 dark:bg-slate-800 text-slate-400'
                                            }`}>
                                                {isDone ? (
                                                    <Check size={16} className="text-slate-600 dark:text-slate-400" />
                                                ) : (
                                                    <StepIcon size={16} className={isActive ? 'text-white' : ''} />
                                                )}
                                            </div>

                                            <div className="flex-1 min-w-0">
                                                <p className={`text-sm font-bold leading-tight tracking-tight ${
                                                    isActive ? 'text-emerald-900 dark:text-emerald-100' : isDone ? 'text-slate-800 dark:text-slate-200' : 'text-slate-600 dark:text-slate-300'
                                                }`}>
                                                    {step.label}
                                                </p>
                                                {isActive && (
                                                    <motion.p
                                                        initial={{ opacity: 0 }}
                                                        animate={{ opacity: 1 }}
                                                        className="mt-0.5 text-xs leading-relaxed text-emerald-700 dark:text-emerald-200"
                                                    >
                                                        {step.subLabel}
                                                    </motion.p>
                                                )}
                                            </div>

                                            {isActive && (
                                                <div className="shrink-0 w-4 h-4 border-2 border-emerald-300 border-t-emerald-600 rounded-full animate-spin" />
                                            )}
                                        </motion.div>
                                    );
                                })}
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {!isCalculating && recommendations && recommendations.length < 3 && (
                        <p role="status" className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs font-semibold text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100">
                            {t('recommender.fewResults', { count: recommendations.length })}
                        </p>
                    )}

                    {/* STAGGERED ANIMATED RESULT CARDS */}
                    <AnimatePresence mode="wait">
                        {!isCalculating && recommendations && (
                            <motion.div
                                initial="hidden"
                                animate="visible"
                                variants={{
                                    hidden: { opacity: 0 },
                                    visible: {
                                        opacity: 1,
                                        transition: {
                                            staggerChildren: 0.12,
                                        },
                                    },
                                }}
                                className="space-y-5"
                            >
                                {recommendations.map((crop) => {
                                    const isChosen = selectedCropRecord?.id === crop.id;

                                    const badgeStyles =
                                        crop.rank === 1
                                            ? 'bg-emerald-600 text-white'
                                            : crop.rank === 2
                                            ? 'bg-blue-600 text-white'
                                            : 'bg-amber-600 text-white';

                                    const cardBorder =
                                        isChosen
                                            ? 'border-2 border-emerald-600 ring-4 ring-emerald-500/20'
                                            : crop.rank === 1
                                            ? 'border-2 border-emerald-200 shadow-md hover:border-emerald-300'
                                            : 'border border-slate-200 dark:border-slate-700/90 shadow-sm hover:border-slate-300';

                                    return (
                                        <motion.article
                                            key={crop.id}
                                            variants={{
                                                hidden: { opacity: 0, y: 30, scale: 0.97 },
                                                visible: {
                                                    opacity: 1,
                                                    y: 0,
                                                    scale: 1,
                                                    transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] },
                                                },
                                            }}
                                            whileHover={{ y: -3, boxShadow: '0 20px 40px -12px rgba(0,0,0,0.10)' }}
                                            className={`bg-white dark:bg-slate-900 rounded-3xl p-5 sm:p-7 transition-all ${cardBorder} relative overflow-hidden`}
                                        >
                                            {/* Top Banner for Rank 1 */}
                                            {crop.rank === 1 && (
                                                <div className="absolute top-0 right-0 bg-emerald-500 text-white text-[11px] font-bold px-4 py-1 rounded-bl-2xl shadow-sm flex items-center gap-1">
                                                    <Award size={13} />
                                                    <span>{t('recommender.optimalBalance')}</span>
                                                </div>
                                            )}

                                            {/* Card Top Row: Rank Tag, Listen Button */}
                                            <div className="flex items-center justify-between gap-2 mb-3 pt-2">
                                                <div className="flex items-center gap-2 flex-wrap">
                                                    <span className={`text-xs font-bold px-3 py-1 rounded-full ${badgeStyles}`}>
                                                        {crop.rankTag}
                                                    </span>
                                                    <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2.5 py-1 rounded-full">
                                                        {crop.family}
                                                    </span>
                                                </div>

                                                {/* Card-Level Shared Listen Button */}
                                                <ListenButton
                                                    id={`crop-card-${crop.id}`}
                                                    labelKey="recommender.listen"
                                                    text={crop.speechParts}
                                                    ariaLabel={t('crops.listenTo', {
                                                        name: crop.translatedCropName,
                                                    })}
                                                />
                                            </div>

                                            {/* Crop Name & Photo */}
                                            <div className="flex items-start justify-between gap-3 mb-4">
                                                <div className="flex items-start gap-3 min-w-0">
                                                    <CropImage
                                                        cropId={crop.id}
                                                        size="lg"
                                                        showName={false}
                                                        speakOnTap
                                                    />
                                                    <div className="min-w-0">
                                                        <div className="flex flex-wrap items-center gap-2">
                                                            <h3 className="text-2xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight">
                                                                {crop.translatedCropName}
                                                            </h3>
                                                            <span className="text-sm font-medium text-slate-400 bg-slate-50 dark:bg-slate-950 px-2 py-0.5 rounded-md border border-slate-200 dark:border-slate-700/60">
                                                                {crop.translatedLocalName}
                                                            </span>
                                                        </div>
                                                        {(crop.pmfbyBadgeLabel || crop.nfsmBadgeLabel) && (
                                                            <div className="mt-2 flex flex-wrap items-center gap-2">
                                                                {crop.pmfbyBadgeLabel && (
                                                                    <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-bold text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/15 dark:text-emerald-300">
                                                                        <ShieldCheck size={13} className="shrink-0 text-emerald-600 dark:text-emerald-400" />
                                                                        <span>{crop.pmfbyBadgeLabel}</span>
                                                                    </span>
                                                                )}
                                                                {crop.nfsmBadgeLabel && (
                                                                    <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-bold text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/15 dark:text-amber-300">
                                                                        <Landmark size={13} className="shrink-0 text-amber-600 dark:text-amber-400" />
                                                                        <span>{crop.nfsmBadgeLabel}</span>
                                                                    </span>
                                                                )}
                                                            </div>
                                                        )}
                                                        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500 dark:text-slate-400 mt-1.5">
                                                            <span className="flex items-center gap-1">
                                                                <Calendar size={13} className="text-emerald-600" />
                                                                {crop.duration}
                                                            </span>
                                                            <span>•</span>
                                                            <span className="flex items-center gap-1">
                                                                <Droplets size={13} className="text-blue-500" />
                                                                {crop.waterNeed}
                                                            </span>
                                                        </div>
                                                    </div>
                                                </div>

                                                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-emerald-100 bg-emerald-50 dark:border-emerald-700 dark:bg-emerald-500/10">
                                                    <Sprout size={26} className="text-emerald-700 dark:text-emerald-300" />
                                                </div>
                                            </div>

                                            {/* PLAIN-LANGUAGE REASON */}
                                            <div className="relative mb-5 rounded-2xl border border-amber-200/80 bg-gradient-to-br from-amber-50 to-orange-50/60 p-4 text-amber-950 shadow-sm shadow-amber-100/50 dark:border-amber-500/30 dark:from-amber-500/15 dark:to-orange-500/10 dark:text-amber-100 dark:shadow-amber-950/30">
                                                <div className="absolute top-0 left-4 right-4 h-px bg-gradient-to-r from-transparent via-amber-300/60 to-transparent" />

                                                <div className="flex items-start gap-3">
                                                    <div className="mt-0.5 shrink-0 rounded-xl bg-amber-100 p-2 text-amber-700 shadow-sm dark:bg-amber-400/20 dark:text-amber-200">
                                                        <Info size={15} />
                                                    </div>
                                                    <div>
                                                        <span className="mb-1 block text-[10px] font-black uppercase tracking-widest text-amber-600 dark:text-amber-300">
                                                            {t('recommender.whyThisCrop')}
                                                        </span>
                                                        <p className="text-sm font-semibold leading-relaxed text-amber-950 dark:text-amber-100">
                                                            {crop.plainReason}
                                                        </p>
                                                    </div>
                                                </div>
                                            </div>

                                            {/* PROFIT COMPARISON & FERTILIZER SAVINGS */}
                                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
                                                {/* Metric Card A: Net-Return Score */}
                                                <div className="flex flex-col justify-between rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 to-slate-100/80 p-4 shadow-md shadow-slate-200/50 dark:border-slate-700/60 dark:from-slate-800 dark:to-slate-900 dark:shadow-slate-950/40">
                                                    <div>
                                                        <div className="flex items-center justify-between text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">
                                                            <span className="flex items-center gap-1">
                                                                <DollarSign size={14} className="text-emerald-600" />
                                                                {t('recommender.estimatedNetReturn')}
                                                            </span>
                                                            <span className="rounded-full border border-emerald-200/70 bg-emerald-50 px-2 py-0.5 text-[11px] font-bold text-emerald-700 dark:border-emerald-700/60 dark:bg-emerald-500/15 dark:text-emerald-200">
                                                                {crop.netReturnDelta}
                                                            </span>
                                                        </div>
                                                        <div className="text-2xl font-black text-slate-900 dark:text-slate-100 tracking-tight mt-1">
                                                            {crop.netReturnFormatted}
                                                        </div>
                                                        {crop.profitAdjustmentNote && (
                                                            <p className="mt-1.5 text-[11px] font-semibold text-emerald-700 dark:text-emerald-300">
                                                                {crop.profitAdjustmentNote}
                                                            </p>
                                                        )}
                                                    </div>

                                                    <div className="mt-3">
                                                        <div className="flex justify-between text-[11px] text-slate-500 dark:text-slate-400 font-medium mb-1">
                                                            <span>{t('recommender.monoCropBase')}</span>
                                                            <span className="font-bold text-emerald-700 dark:text-emerald-300">
                                                                {t('recommender.thisRotation')}
                                                            </span>
                                                        </div>
                                                        <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                                                            <div className="bg-slate-400 h-full w-[65%]" title={t('recommender.monoCropBase')}></div>
                                                            <div className="bg-emerald-500 h-full w-[35%]" title={t('recommender.thisRotation')}></div>
                                                        </div>
                                                    </div>
                                                </div>

                                                {/* Metric Card B: Fertilizer Savings */}
                                                <div className="flex flex-col justify-between rounded-2xl border border-emerald-200/60 bg-gradient-to-br from-emerald-50 to-teal-50/80 p-4 shadow-md shadow-emerald-100/60 dark:border-emerald-700/50 dark:from-emerald-500/15 dark:to-teal-500/10 dark:shadow-emerald-950/30">
                                                    <div>
                                                        <div className="mb-1 flex items-center justify-between text-xs font-semibold text-emerald-900 dark:text-emerald-100">
                                                            <span className="flex items-center gap-1">
                                                                <Leaf size={14} className="text-emerald-700" />
                                                                {t('recommender.fertilizerReduction')}
                                                            </span>
                                                            <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-bold text-emerald-800 dark:bg-emerald-400/20 dark:text-emerald-200">
                                                                {t('recommender.soilRestored')}
                                                            </span>
                                                        </div>
                                                        <div className="mt-1 text-2xl font-black tracking-tight text-emerald-950 dark:text-emerald-100">
                                                            {crop.fertilizerSavedLabel}
                                                        </div>
                                                    </div>

                                                    <div className="mt-3 flex items-center justify-between border-t border-emerald-200/70 pt-2 text-xs font-medium text-emerald-800 dark:border-emerald-700/60 dark:text-emerald-200">
                                                        <span>{t('recommender.chemicalBillCut')}</span>
                                                        <span className="font-bold text-emerald-950 dark:text-emerald-100">
                                                            {crop.fertilizerCostSavings}
                                                        </span>
                                                    </div>
                                                </div>
                                            </div>

                                            {/* Action Button: Select This Crop */}
                                            <div className="pt-1">
                                                <motion.button
                                                    type="button"
                                                    whileHover={{ scale: 1.01 }}
                                                    whileTap={{ scale: 0.97 }}
                                                    onClick={() => handleSelectCrop(crop)}
                                                    className={`w-full py-3.5 px-5 rounded-2xl font-bold text-sm flex items-center justify-center gap-2 transition-all min-h-[48px] focus:outline-none focus:ring-4 relative overflow-hidden ${
                                                        isChosen
                                                            ? 'bg-slate-900 text-white hover:bg-slate-800 ring-slate-400/40 shadow-lg shadow-slate-900/25'
                                                            : 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-lg shadow-emerald-700/30 ring-emerald-300'
                                                    }`}
                                                >
                                                    {isChosen ? (
                                                        <>
                                                            <CheckCircle2 size={18} className="text-emerald-400" />
                                                            <span>
                                                                {t('recommender.selectedForPlotBtn', {
                                                                    plot: currentPlot?.name || t('recommender.yourPlot'),
                                                                })}
                                                            </span>
                                                        </>
                                                    ) : (
                                                        <>
                                                            <Check size={18} />
                                                            <span>{t('recommender.selectCropBtn')}</span>
                                                        </>
                                                    )}
                                                </motion.button>
                                            </div>
                                        </motion.article>
                                    );
                                })}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </section>
            </main>

            {/* Offline Sync & Feedback Toast */}
            <AnimatePresence>
                {toastMessage && (
                    <motion.div
                        initial={{ opacity: 0, y: 30, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 20, scale: 0.95 }}
                        className="fixed bottom-20 left-1/2 -translate-x-1/2 z-50 bg-slate-900 text-white text-xs sm:text-sm font-semibold px-5 py-3 rounded-2xl shadow-xl flex items-center gap-3 border border-slate-700 max-w-[90vw]"
                    >
                        <Zap size={16} className="text-emerald-400 shrink-0" />
                        <span>{toastMessage}</span>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
