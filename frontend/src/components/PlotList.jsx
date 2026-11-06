import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Link, useNavigate } from 'react-router-dom';
import { db } from '../db/db';
import { useLiveQuery } from 'dexie-react-hooks';
import AddPlotModal from './AddPlotModal';
import LandRegistryConsentModal from './LandRegistryConsentModal';
import CatchCropAlert from './CatchCropAlert';
import DealerDirectory from './DealerDirectory';
import VoiceAdvisory from './VoiceAdvisory';
import FieldMapper from './FieldMapper';
import DashboardMap from './DashboardMap';
import WeatherPanel from './WeatherPanel';
import CropImage from './CropImage';
import { getCropDisplayName, getCropOrUnknown, resolveKnownCrop } from '../data/crops';
import { getIntercropPairingRule } from '../services/intercropRules';
import {
    ArrowDownRight,
    ArrowRight,
    ArrowUpRight,
    CheckCircle2,
    Leaf,
    Droplets,
    Maximize2,
    Plus,
    Sprout,
    Thermometer,
    TriangleAlert,
    Wheat,
    X,
} from 'lucide-react';
import StartupNotifications from './StartupNotifications';
import useScrollLock from '../hooks/useScrollLock';
import VerificationBadge from './VerificationBadge';
import { getProviderForCountry, getSavedCountry } from '../services/landRegistry/registry';
import { useTranslation } from '../context/LanguageContext';
import ListenButton from './ui/ListenButton';
import {
    buildSpeechText,
    formatSpeakableDate,
    formatSpeakableNumber,
    formatSpeakablePercent,
    formatSpeakablePriceWithUnit,
    formatSpeakableTemperature,
} from '../utils/speechText';

const AREA_UNITS = {
    acres: { label: 'Acres', hectares: 0.40468564224 },
    hectares: { label: 'Hectares', hectares: 1 },
    guntha: { label: 'Guntha', hectares: 0.010117141056 },
    bigha: { label: 'Bigha', hectares: 0.2529285 },
    sqm: { label: 'Sq meters', hectares: 0.0001 },
    sqft: { label: 'Sq feet', hectares: 0.000009290304 },
};

const ALERTS = [
    {
        id: 'moisture',
        titleKey: 'dashboard.alerts.moistureTitle',
        detailKey: 'dashboard.alerts.moistureDetail',
        actionKey: 'dashboard.alerts.moistureAction',
        href: '/soil',
        icon: TriangleAlert,
        iconClass: 'bg-red-50 text-red-500 dark:bg-red-950 dark:text-red-300',
    },
    {
        id: 'temperature',
        titleKey: 'dashboard.alerts.tempTitle',
        detailKey: 'dashboard.alerts.tempDetail',
        actionKey: 'dashboard.alerts.tempAction',
        href: '#weather-forecast',
        icon: TriangleAlert,
        iconClass: 'bg-amber-50 text-amber-500 dark:bg-amber-950 dark:text-amber-300',
    },
    {
        id: 'irrigation',
        titleKey: 'dashboard.alerts.irrigationTitle',
        detailKey: 'dashboard.alerts.irrigationDetail',
        actionKey: 'dashboard.alerts.irrigationAction',
        href: '#field-overview',
        icon: CheckCircle2,
        iconClass: 'bg-emerald-50 text-emerald-500 dark:bg-emerald-950 dark:text-emerald-300',
    },
];

const MARKET_TRENDS = {
    weekly: {
        label: 'This week',
        high: 198,
        low: 180,
        values: [198, 194, 190, 193, 187, 180, 185],
        change: '−3.1%',
        changeClass: 'text-rose-600 dark:text-rose-400',
    },
    monthly: {
        label: 'This month',
        high: 220,
        low: 175,
        values: [178, 184, 175, 196, 188, 220, 185],
        change: '+4.5%',
        changeClass: 'text-emerald-600 dark:text-emerald-400',
    },
};

const containerVariants = {
    hidden: {},
    show: { transition: { staggerChildren: 0.08 } },
};

const itemVariants = {
    hidden: { opacity: 0, y: 18 },
    show: { opacity: 1, y: 0, transition: { duration: 0.45, ease: 'easeOut' } },
};

function toPositiveNumber(value) {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
}

function DashboardCard({ children, className = '', ...props }) {
    return (
        <motion.section
            variants={itemVariants}
            className={`rounded-2xl border border-slate-200 bg-white shadow-sm transition-colors duration-300 dark:border-slate-800 dark:bg-slate-900 ${className}`}
            {...props}
        >
            {children}
        </motion.section>
    );
}

function MarketSparkline({ values, timeframe, t }) {
    const width = 600;
    const height = 152;
    const padding = 8;
    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    const range = maximum - minimum || 1;
    const points = values.map((value, index) => {
        const x = padding + index * ((width - padding * 2) / (values.length - 1));
        const y = height - padding - ((value - minimum) / range) * (height - padding * 2);
        return [x, y];
    });
    const line = points.map(([x, y]) => `${x},${y}`).join(' ');
    const area = `${points[0][0]},${height} ${line} ${points[points.length - 1][0]},${height}`;

    return (
        <div className="relative mt-3 h-28 overflow-hidden rounded-xl bg-gradient-to-b from-emerald-50/80 to-transparent dark:from-emerald-950/40">
            <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="h-full w-full" role="img" aria-label={`${timeframe} cashew price trend chart`}>
                <defs>
                    <linearGradient id={`market-area-${timeframe}`} x1="0" x2="0" y1="0" y2="1">
                        <stop offset="0%" stopColor="#10b981" stopOpacity=".3" />
                        <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
                    </linearGradient>
                    <filter id={`market-glow-${timeframe}`} x="-20%" y="-30%" width="140%" height="170%">
                        <feGaussianBlur stdDeviation="3" result="blur" />
                        <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
                    </filter>
                </defs>
                <path d={`M ${area.replaceAll(' ', ' L ')} Z`} fill={`url(#market-area-${timeframe})`} />
                <polyline points={line} fill="none" stroke="#10b981" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" filter={`url(#market-glow-${timeframe})`} vectorEffect="non-scaling-stroke" />
                <circle cx={points.at(-1)[0]} cy={points.at(-1)[1]} r="6" fill="#10b981" stroke="white" strokeWidth="3" vectorEffect="non-scaling-stroke" />
            </svg>
            <div className="pointer-events-none absolute inset-x-3 bottom-2 flex justify-between text-[10px] font-medium text-slate-400 dark:text-slate-500">
                <span>{timeframe === 'weekly' ? '7 days ago' : '30 days ago'}</span>
                <span>{t('dashboard.today')}</span>
            </div>
        </div>
    );
}

function MarketInsightsCard({ timeframe, setTimeframe }) {
    const trend = MARKET_TRENDS[timeframe];
    const { t, languageInfo } = useTranslation();
    const marketCardSpeech = buildSpeechText([
        t('market.live'),
        t('market.place'),
        formatSpeakablePriceWithUnit(185, t('market.units.perKg'), languageInfo.speechLang),
        t('market.open'),
    ]);

    return (
        <DashboardCard className="p-5 sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <Link
                    to="/market/cashew"
                    className="group flex items-center gap-3 rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
                >
                    <CropImage cropId="cashew" size="sm" />
                    <div>
                        <h2 className="text-lg font-bold tracking-tight text-slate-900 group-hover:text-emerald-700 dark:text-white dark:group-hover:text-emerald-300">
                            {t('market.live')}
                        </h2>
                        <p className="mt-0.5 text-sm font-medium text-slate-500 dark:text-slate-400">{t('market.place')}</p>
                    </div>
                </Link>
                <div className="flex items-center gap-2">
                    <ListenButton text={marketCardSpeech} variant="emerald" size="xs" />
                    <div role="group" aria-label={t('market.title')} className="inline-flex rounded-xl bg-slate-100 p-1 dark:bg-slate-800">
                        {['weekly', 'monthly'].map((period) => (
                            <button
                                key={period}
                                type="button"
                                aria-pressed={timeframe === period}
                                onClick={() => setTimeframe(period)}
                                className={`rounded-lg px-3 py-1.5 text-xs font-bold transition focus:outline-none focus:ring-2 focus:ring-emerald-500 ${timeframe === period ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white' : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white'}`}
                            >
                                {t(`dashboard.timeframe.${period}`)}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            <div className="mt-6 flex flex-wrap items-end justify-between gap-3">
                <Link to="/market/cashew" className="group rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500">
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400 dark:text-slate-500">{t('market.grade')}</p>
                    <div className="mt-1 flex items-baseline gap-2">
                        <p className="text-4xl font-black tracking-tight text-slate-900 group-hover:text-emerald-700 dark:text-white dark:group-hover:text-emerald-300">₹185<span className="ml-1 text-lg font-semibold text-slate-500 dark:text-slate-400">/kg</span></p>
                        <span className={`text-xs font-bold ${trend.changeClass}`}>{trend.change}</span>
                    </div>
                </Link>
                <p className="rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-bold text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">{t('market.open')}</p>
            </div>

            <MarketSparkline values={trend.values} timeframe={timeframe} t={t} />

            <div className="mt-4 grid grid-cols-2 gap-3">
                <div className="rounded-xl border border-emerald-100 bg-emerald-50/70 p-3.5 dark:border-emerald-900/70 dark:bg-emerald-950/45">
                    <p className="text-[11px] font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">High · {trend.label}</p>
                    <p className="mt-1.5 flex items-center gap-1 text-xl font-black text-emerald-700 dark:text-emerald-300"><ArrowUpRight size={18} />₹{trend.high}<span className="text-xs font-semibold">/kg</span></p>
                </div>
                <div className="rounded-xl border border-rose-100 bg-rose-50/70 p-3.5 dark:border-rose-900/70 dark:bg-rose-950/45">
                    <p className="text-[11px] font-bold uppercase tracking-wider text-rose-700 dark:text-rose-400">Low · {trend.label}</p>
                    <p className="mt-1.5 flex items-center gap-1 text-xl font-black text-rose-700 dark:text-rose-300"><ArrowDownRight size={18} />₹{trend.low}<span className="text-xs font-semibold">/kg</span></p>
                </div>
            </div>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                <p className="text-[11px] font-medium text-slate-400 dark:text-slate-500">{t('market.updated')}</p>
                <Link
                    to="/market/cashew"
                    className="inline-flex items-center gap-1 text-xs font-bold text-emerald-700 hover:text-emerald-800 dark:text-emerald-400 dark:hover:text-emerald-300"
                >
                    <span>{t('marketDetail.viewCropAnalysis')}</span>
                    <ArrowRight size={13} />
                </Link>
            </div>
        </DashboardCard>
    );
}

export default function PlotList() {
    const navigate = useNavigate();
    const { t, languageInfo } = useTranslation();
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [isConsentOpen, setIsConsentOpen] = useState(false);
    const [showMap, setShowMap] = useState(false);
    const [mappingUnit, setMappingUnit] = useState('acres');
    const [mapResult, setMapResult] = useState(null);
    const [mappedCoordinates, setMappedCoordinates] = useState([]);
    const [mappedArea, setMappedArea] = useState(null);
    const [showCatchCropAlert, setShowCatchCropAlert] = useState(true);
    const [isMapExpanded, setIsMapExpanded] = useState(false);
    const [marketTimeframe, setMarketTimeframe] = useState('weekly');
    const [importToast, setImportToast] = useState('');
    const currentRegistryProvider = getProviderForCountry(getSavedCountry());
    const rawSavedPlots = useLiveQuery(() => db.plots.toArray(), []);
    const savedPlots = useMemo(() => rawSavedPlots || [], [rawSavedPlots]);

    // Migrate legacy mock parcels in IndexedDB that stored "mixed agriculture" / "Cereal" / "Tree crop"
    useEffect(() => {
        if (!savedPlots.length) return;
        const legacyFallbackCrops = ['paddy', 'cashew', 'coconut'];
        const legacyLandLabels = ['Lowland Plot', 'Canal Block', 'Upland Terrace'];
        const updates = [];

        savedPlots.forEach((plot, idx) => {
            if (!plot?.id) return;
            const resolved = resolveKnownCrop(plot.primaryCrop);
            const rawName = String(plot.name || '');
            const hasLegacyName = /^(mixed agriculture|arable land)\b/i.test(rawName);
            const isMockRegistry = Boolean(plot.externalId && /-[123]$/.test(String(plot.externalId)));

            // Only the old generic mock labels are migrated; plots with a real (possibly hidden) crop id are never rewritten.
            const isLegacyLabel = /^(mixed agriculture|arable land|cereal|vegetables|tree crop)$/i.test(String(plot.primaryCrop || '').trim());
            if (!resolved && (isLegacyLabel || hasLegacyName)) {
                const parcelIdx = isMockRegistry
                    ? Math.max(0, (Number(String(plot.externalId).split('-').pop()) || 1) - 1) % 3
                    : idx % 3;
                const nextCrop = isMockRegistry ? legacyFallbackCrops[parcelIdx] : '';
                const nextName = hasLegacyName
                    ? `${legacyLandLabels[parcelIdx]} ${plot.surveyNumber || ''}`.trim()
                    : rawName;
                updates.push(
                    db.plots.update(plot.id, {
                        primaryCrop: nextCrop,
                        name: nextName,
                    }),
                );
            }
        });

        if (updates.length > 0) {
            void Promise.all(updates).catch(() => {});
        }
    }, [savedPlots]);

    useEffect(() => {
        if (!isMapExpanded) return undefined;
        const handleEscape = (event) => {
            if (event.key === 'Escape') {
                setIsMapExpanded(false);
            }
        };
        window.addEventListener('keydown', handleEscape);
        return () => window.removeEventListener('keydown', handleEscape);
    }, [isMapExpanded]);

    useScrollLock(isMapExpanded);

    const handleMapData = ({ area, unit, coordinates }) => {
        setMappedArea(area);
        setMappedCoordinates(coordinates);
        setMapResult({ area, unit: unit || mappingUnit, coordinates });
        if (unit) setMappingUnit(unit);
        setShowMap(false);
    };

    const handleAddPlot = async (plotData) => {
        try {
            const numericArea = toPositiveNumber(plotData.area);
            const areaHectares = Number((numericArea * AREA_UNITS[plotData.areaUnit].hectares).toFixed(6));
            const plotToSave = {
                name: plotData.fieldName.trim(),
                area: plotData.area.trim(),
                areaUnit: plotData.areaUnit,
                village: '',
                primaryCrop: plotData.primaryCrop,
                intercrop: plotData.intercrop || null,
                boundaryCoordinates: mappedCoordinates,
                coordinates: plotData.coordinates || mappedCoordinates,
                mappedArea,
                areaHectares,
                serverId: null,
                isVerified: false,
                source: 'manual',
                providerId: 'manual',
                externalId: null,
                provenance: { providerId: 'manual', verified: false, evidenceType: 'user-entered' },
            };

            const localId = await db.plots.add(plotToSave);
            await db.syncQueue.add({
                action: 'CREATE_PLOT',
                payload: { ...plotToSave, localId },
                status: 'pending',
                timestamp: Date.now(),
            });
        } catch (error) {
            console.error('Error saving plot:', error);
        }
    };

    const handleImportProvider = async (provider, documentFile) => {
        if (provider.id === 'generic') {
            if (!documentFile) throw new Error(t('landRegistry.documentRequired'));
            window.localStorage.setItem('fieldshift-land-document', JSON.stringify({ name: documentFile.name, size: documentFile.size, status: 'document uploaded, pending review' }));
            setImportToast(t('landRegistry.documentUploaded'));
            window.setTimeout(() => setImportToast(''), 3500);
            return;
        }
        const parcels = await provider.fetchVerifiedParcels({ countryCode: getSavedCountry() });
        const existingPlots = await db.plots.toArray();
        const existingKeys = new Set(existingPlots.map((plot) => `${plot.providerId || plot.source || 'manual'}:${plot.externalId || plot.surveyNumber || ''}`));
        const newPlots = parcels
            .map((parcel) => {
                const validCrop = resolveKnownCrop(parcel.cropDeclared);
                return {
                    name: `${parcel.landUse} ${parcel.parcelRef}`,
                    area: String(parcel.areaHa),
                    areaUnit: 'hectares',
                    areaHectares: parcel.areaHa,
                    village: parcel.countryCode,
                    primaryCrop: validCrop ? validCrop.id : '',
                    intercrop: null,
                    coordinates: parcel.geometry.coordinates[0].map(([longitude, latitude]) => [latitude, longitude]),
                    boundaryCoordinates: parcel.geometry.coordinates[0].map(([longitude, latitude]) => [latitude, longitude]),
                    surveyNumber: parcel.parcelRef,
                    isVerified: true,
                    source: parcel.source,
                    providerId: parcel.source,
                    externalId: parcel.id,
                    verifiedAt: parcel.verifiedAt,
                    provenance: { providerId: parcel.source, externalId: parcel.id, verified: true, verifiedAt: parcel.verifiedAt },
                    serverId: null,
                };
            })
            .filter((plot) => !existingKeys.has(`${plot.providerId}:${plot.externalId}`));

        if (newPlots.length > 0) {
            await db.plots.bulkAdd(newPlots);
        }

        setImportToast(`${newPlots.length} verified ${newPlots.length === 1 ? 'field' : 'fields'} imported`);
        window.setTimeout(() => setImportToast(''), 3500);
    };

    return (
        <div className="min-h-screen bg-slate-50 px-4 pb-12 pt-24 transition-colors duration-300 dark:bg-slate-950 sm:px-6 lg:px-8">
            <StartupNotifications />
            <motion.main variants={containerVariants} initial="hidden" animate="show" className="mx-auto flex max-w-7xl flex-col gap-6">
                <div className="flex flex-wrap items-end justify-between gap-3">
                    <div>
                        <p className="text-xs font-bold uppercase tracking-[0.18em] text-emerald-700 dark:text-emerald-400">{t('dashboard.farmOperations')}</p>
                        <h1 className="mt-1 text-2xl font-black tracking-tight text-slate-900 dark:text-white sm:text-3xl">{t('dashboard.brand')}</h1>
                    </div>
                    <div className="flex flex-wrap items-center gap-3">
                        <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
                            {t('dashboard.location')} <span className="px-1 text-slate-300 dark:text-slate-700">·</span>{' '}
                            {new Intl.DateTimeFormat(languageInfo.speechLang, { dateStyle: 'medium' }).format(new Date())}
                        </p>
                        <ListenButton
                            text={buildSpeechText([
                                t('dashboard.brand'),
                                t('dashboard.location'),
                                formatSpeakableDate(new Date(), languageInfo.speechLang),
                                `${t('dashboard.totalFields')}: ${formatSpeakableNumber(12, languageInfo.speechLang)}`,
                                `${t('dashboard.activeCrops')}: ${formatSpeakableNumber(5, languageInfo.speechLang)}`,
                                `${t('dashboard.soilMoisture')}: ${formatSpeakablePercent(68, languageInfo.speechLang)}`,
                                `${t('dashboard.temperature')}: ${formatSpeakableTemperature(28, 'C', languageInfo.speechLang)}`,
                            ])}
                            variant="emerald"
                            size="sm"
                        />
                    </div>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    {[
                    { label: t('dashboard.totalFields'), value: '12', note: t('dashboard.totalFieldsNote'), icon: Leaf, iconClass: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-300' },
                    { label: t('dashboard.activeCrops'), value: '5', note: t('dashboard.activeCropsNote'), icon: Wheat, iconClass: 'bg-amber-50 text-amber-600 dark:bg-amber-950 dark:text-amber-300' },
                    { label: t('dashboard.soilMoisture'), value: '68%', note: t('dashboard.soilMoistureNote'), icon: Droplets, iconClass: 'bg-sky-50 text-sky-600 dark:bg-sky-950 dark:text-sky-300' },
                    { label: t('dashboard.temperature'), value: '28°C', note: t('dashboard.temperatureNote'), icon: Thermometer, iconClass: 'bg-rose-50 text-rose-600 dark:bg-rose-950 dark:text-rose-300' },
                    ].map(({ label, value, note, icon: Icon, iconClass }) => (
                        <motion.section key={label} variants={itemVariants} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition-colors duration-300 dark:border-slate-800 dark:bg-slate-900 sm:p-5">
                            <div className="flex items-start justify-between">
                                <div>
                                    <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{label}</p>
                                    <p className="mt-2 text-4xl font-bold tracking-tight text-slate-900 dark:text-white">{value}</p>
                                    <p className="mt-2 text-xs font-medium text-slate-500 dark:text-slate-400">{note}</p>
                                </div>
                                <div className={`rounded-xl p-2.5 ${iconClass}`}><Icon size={20} /></div>
                            </div>
                            {label === t('dashboard.activeCrops') && (
                                <div className="mt-3 flex items-center gap-1">
                                    {['rice', 'wheat', 'coconut', 'chickpea'].map((cropId) => <CropImage key={cropId} cropId={cropId} size="sm" />)}
                                </div>
                            )}
                        </motion.section>
                    ))}
                </div>

                <AnimatePresence>
                    {showCatchCropAlert && (
                        <CatchCropAlert
                            onDismiss={() => setShowCatchCropAlert(false)}
                            onUpdatePlan={() => navigate('/recommender')}
                        />
                    )}
                </AnimatePresence>

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                    <DashboardCard id="field-overview" className="overflow-hidden">
                        <div className="flex items-center justify-between gap-3 p-5 pb-4 sm:px-6">
                            <div>
                                <h2 className="text-lg font-bold tracking-tight text-slate-900 dark:text-white">{t('dashboard.fieldOverview')}</h2>
                                <p className="mt-1 text-sm font-medium text-slate-500 dark:text-slate-400">{t('dashboard.fieldsAtGlance')}</p>
                            </div>
                            <div className="flex items-center gap-2">
                                <div className="flex items-center gap-2">
                                    <button type="button" onClick={() => setIsConsentOpen(true)} className="inline-flex rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-bold text-emerald-700 transition hover:bg-emerald-100 focus:outline-none focus:ring-2 focus:ring-emerald-500">
                                        {t('landRegistry.importTitle')}: {t(currentRegistryProvider.name)}
                                    </button>
                                    <button type="button" onClick={() => setIsModalOpen(true)} className="inline-flex items-center gap-1.5 rounded-xl bg-slate-900 px-3 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:bg-emerald-600 dark:hover:bg-emerald-500">
                                        <Plus size={14} /> {t('dashboard.addField')}
                                    </button>
                                </div>
                                <button type="button" onClick={() => setIsMapExpanded(true)}                                 aria-label={t('dashboard.expandMap')} title={t('dashboard.expandMap')} className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white">
                                    <Maximize2 size={17} />
                                </button>
                            </div>
                        </div>
                        <button
                            type="button"
                            onClick={() => setIsMapExpanded(true)}
                            aria-label={t('dashboard.openMap')}
                            className="block w-full cursor-zoom-in overflow-hidden text-left focus:outline-none focus-visible:ring-4 focus-visible:ring-inset focus-visible:ring-emerald-400"
                        >
                            {!isMapExpanded && <DashboardMap plots={savedPlots} />}
                        </button>
                        {savedPlots.length === 0 ? (
                            <div className="flex flex-col items-start justify-between gap-3 border-t border-slate-100 px-5 py-4 text-sm text-slate-500 dark:border-slate-800 dark:text-slate-400 sm:flex-row sm:items-center">
                                <span>{t('dashboard.noFields')}</span>
                                <button
                                    type="button"
                                    onClick={() => setIsConsentOpen(true)}
                                    className="inline-flex shrink-0 items-center rounded-xl bg-emerald-600 px-3 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                                >
                                    {t('landRegistry.importTitle')}: {t(currentRegistryProvider.name)}
                                </button>
                            </div>
                        ) : (
                            <div className="grid gap-2 border-t border-slate-100 p-5 dark:border-slate-800 sm:grid-cols-2">
                                {savedPlots.map((plot) => {
                                    const plotCrop = getCropOrUnknown(plot.primaryCrop, plot.primaryCrop);
                                    const isGenericLabel = /^(mixed agriculture|arable land|cereal|vegetables|tree crop)$/i.test(String(plot.primaryCrop || '').trim());
                                    const primaryCropLabel = plotCrop.isUnknown
                                        ? (plot.primaryCrop && !isGenericLabel ? String(plot.primaryCrop).replace(/-/g, ' ') : '')
                                        : getCropDisplayName(plotCrop, t);

                                    const rawIntercrop = String(plot.intercrop || '').trim();
                                    const intercropObj = rawIntercrop ? getCropOrUnknown(rawIntercrop, rawIntercrop) : null;
                                    const intercropLabel = intercropObj
                                        ? (intercropObj.isUnknown ? rawIntercrop.replace(/-/g, ' ') : getCropDisplayName(intercropObj, t))
                                        : '';
                                    const hasIntercrop = Boolean(intercropLabel);
                                    const companionKnownCrop = hasIntercrop ? resolveKnownCrop(rawIntercrop) : null;
                                    const pairingRule = hasIntercrop
                                        ? getIntercropPairingRule(plot.primaryCrop, rawIntercrop)
                                        : null;

                                    const cropLabel =
                                        primaryCropLabel && hasIntercrop
                                            ? t('dashboard.cropPairLabel', {
                                                  primary: primaryCropLabel,
                                                  intercrop: intercropLabel,
                                              })
                                            : primaryCropLabel || intercropLabel;

                                    return (
                                        <div key={plot.id} className="rounded-xl border border-slate-200/60 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-950">
                                            <div className="flex flex-wrap items-start justify-between gap-2">
                                                <div className="flex min-w-[155px] flex-1 items-start gap-2.5">
                                                    <div className="relative shrink-0">
                                                        <CropImage
                                                            cropId={plot.primaryCrop || rawIntercrop || null}
                                                            size="sm"
                                                        />
                                                        {hasIntercrop && plot.primaryCrop && companionKnownCrop?.hasPhoto && (
                                                            <img
                                                                src={companionKnownCrop.thumb}
                                                                alt={intercropLabel}
                                                                loading="lazy"
                                                                decoding="async"
                                                                className="absolute -bottom-1 -end-1 h-5 w-5 rounded-md object-cover ring-2 ring-slate-50 dark:ring-slate-950"
                                                            />
                                                        )}
                                                    </div>
                                                    <div className="min-w-0 flex-1">
                                                        <p className="truncate text-sm font-bold text-slate-900 dark:text-slate-100">
                                                            {plot.name}
                                                        </p>
                                                        <p className="mt-0.5 line-clamp-2 break-words text-[11px] font-medium text-slate-600 dark:text-slate-400">
                                                            {[cropLabel, plot.surveyNumber].filter(Boolean).join(' · ')}
                                                        </p>
                                                        {hasIntercrop && (
                                                            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                                                                <span className="inline-flex max-w-full items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/15 dark:text-emerald-300">
                                                                    <Sprout size={11} className="shrink-0" />
                                                                    <span className="truncate">
                                                                        {t('dashboard.intercropBadge', {
                                                                            crop: intercropLabel,
                                                                        })}
                                                                    </span>
                                                                </span>
                                                                {pairingRule && (
                                                                    <span className="inline-flex max-w-full items-center rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/15 dark:text-amber-300">
                                                                        <span className="truncate">
                                                                            {t(pairingRule.benefitKey)}
                                                                        </span>
                                                                    </span>
                                                                )}
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                                <VerificationBadge
                                                    className="shrink-0"
                                                    isVerified={plot.isVerified || plot.provenance?.verified}
                                                    providerName={plot.providerId}
                                                />
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </DashboardCard>

                    <div id="weather-forecast">
                        <WeatherPanel plots={savedPlots} />
                    </div>

                    <MarketInsightsCard timeframe={marketTimeframe} setTimeframe={setMarketTimeframe} />

                    <DashboardCard className="p-5 sm:p-6">
                        <div className="flex items-center justify-between gap-3">
                            <div>
                                <h2 className="text-lg font-bold tracking-tight text-slate-900 dark:text-white">{t('dashboard.recentAlerts')}</h2>
                                <p className="mt-1 text-sm font-medium text-slate-500 dark:text-slate-400">{t('dashboard.alertsAttention')}</p>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-bold text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                                    {t('dashboard.actionsCount', { count: 2 })}
                                </span>
                                <ListenButton
                                    text={buildSpeechText([
                                        t('dashboard.recentAlerts'),
                                        t('dashboard.alertsAttention'),
                                        ...ALERTS.map((a) => `${t(a.titleKey)}. ${t(a.detailKey)}`),
                                    ])}
                                    variant="amber"
                                    size="xs"
                                />
                            </div>
                        </div>
                        <div className="mt-5 divide-y divide-slate-100 dark:divide-slate-800">
                            {ALERTS.map(({ id, titleKey, detailKey, actionKey, href, icon: Icon, iconClass }) => (
                                <div key={id} className="flex items-center gap-3 py-4 first:pt-0 last:pb-0">
                                    <div className={`rounded-xl p-2.5 ${iconClass}`}><Icon size={18} /></div>
                                    <div className="min-w-0 flex-1">
                                        <p className="text-sm font-semibold text-slate-900 dark:text-white">{t(titleKey)}</p>
                                        <p className="mt-0.5 text-xs font-medium text-slate-500 dark:text-slate-400">{t(detailKey)}</p>
                                        <Link to={href} className="mt-1.5 inline-flex items-center gap-1 text-xs font-bold text-emerald-700 hover:text-emerald-800 dark:text-emerald-400 dark:hover:text-emerald-300">{t(actionKey)}<ArrowRight size={12} /></Link>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </DashboardCard>
                </div>

                <VoiceAdvisory />
                <DealerDirectory />
            </motion.main>

            {isMapExpanded && createPortal(
                <AnimatePresence>
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="app-expanded-map-layer fixed inset-0 flex h-[100dvh] w-screen bg-slate-950/80 p-0 backdrop-blur-sm"
                        onMouseDown={(event) => { if (event.target === event.currentTarget) setIsMapExpanded(false); }}
                    >
                        <motion.section
                            role="dialog"
                            aria-modal="true"
                            aria-labelledby="expanded-map-title"
                            initial={{ opacity: 0, scale: 0.97, y: 14 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.98, y: 10 }}
                            transition={{ duration: 0.24, ease: 'easeOut' }}
                            className="flex min-h-0 h-full w-full flex-col bg-white dark:bg-slate-950"
                        >
                            <div className="flex shrink-0 items-center justify-between gap-4 border-b border-slate-200 px-4 py-3 dark:border-slate-800 sm:px-6">
                                <div>
                                    <h2 id="expanded-map-title" className="text-base font-bold text-slate-900 dark:text-white sm:text-lg">{t('dashboard.fieldOverview')}</h2>
                                    <p className="mt-0.5 text-xs font-medium text-slate-500 dark:text-slate-400">12 fields · 38.4 acres · Dicholi, Goa</p>
                                </div>
                                <button type="button" onClick={() => setIsMapExpanded(false)} className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-3.5 py-2.5 text-sm font-bold text-white transition hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:bg-slate-800 dark:hover:bg-slate-700">
                                    <X size={17} /><span>{t('dashboard.closeMap')}</span>
                                </button>
                            </div>
                            <div className="min-h-0 flex-1 overflow-hidden bg-slate-950">
                                <DashboardMap plots={savedPlots} className="h-full" isExpanded />
                            </div>
                        </motion.section>
                    </motion.div>
                </AnimatePresence>,
                document.body
            )}

            <AddPlotModal
                isOpen={isModalOpen && !showMap}
                onClose={() => { setIsModalOpen(false); setShowMap(false); }}
                onSubmit={handleAddPlot}
                showMap={showMap}
                mapResult={mapResult}
                onShowMap={(nextShowMap, unit) => {
                    if (unit) setMappingUnit(unit);
                    setShowMap(nextShowMap);
                }}
            />

            <LandRegistryConsentModal
                isOpen={isConsentOpen && !showMap}
                onClose={() => setIsConsentOpen(false)}
                onImport={handleImportProvider}
            />

            {showMap && (
                <FieldMapper
                    unit={mappingUnit}
                    onClose={() => setShowMap(false)}
                    onConfirm={(data) => {
                        handleMapData(data);
                        setShowMap(false);
                    }}
                />
            )}
            {importToast && (
                <div className="fixed bottom-24 left-1/2 z-[100] -translate-x-1/2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-800 shadow-lg dark:border-emerald-700/60 dark:bg-emerald-500/10 dark:text-emerald-200" role="status">
                    {importToast}
                </div>
            )}
    </div>
  );
}
