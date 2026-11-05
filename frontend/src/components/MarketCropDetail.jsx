/*
 * FieldShift frontend: Market Crop Detail Screen
 * Feature: Shows price trends, crop performance, and regional buying information for a selected commodity.
 * Impact: Farmers can compare current market conditions and decide when and what to sell or plant.
 * Importance: This is critical for economic decision support and makes the app useful beyond agronomy advice.
 */

import { useCallback, useEffect, useId, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useLiveQuery } from 'dexie-react-hooks';
import {
  ArrowDownRight,
  ArrowLeft,
  ArrowUpRight,
  Award,
  Bell,
  BellRing,
  ChevronRight,
  Clock,
  Info,
  Landmark,
  MapPin,
  Minus,
  Phone,
  RefreshCw,
  Share2,
  Sparkles,
  Star,
  Store,
  Trash2,
  Wheat,
} from 'lucide-react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { db } from '../db/db';
import { getCropById, getCropDisplayName, getCropLocalName, resolveKnownCrop } from '../data/crops';
import {
  createPriceAlert,
  deletePriceAlert,
  evaluatePriceAlerts,
  getCropMarketDetail,
  getFavouriteCropIds,
  getPriceAlerts,
  toggleFavouriteCropId,
} from '../services/market';
import { useTranslation } from '../context/LanguageContext';
import CropImage from './CropImage';
import ListenButton from './ui/ListenButton';
import { buildSpeechText, formatSpeakablePriceWithUnit } from '../utils/speechText';

const RANGES = ['7D', '30D', '90D', '1Y'];

function formatCurrency(val, locale = 'en-IN') {
  const n = Number(val);
  if (!Number.isFinite(n)) return '—';
  return `₹${n.toLocaleString(locale)}`;
}

function formatDateLabel(dateStr, locale, range) {
  if (!dateStr) return '';
  const dt = new Date(dateStr);
  if (Number.isNaN(dt.getTime())) return dateStr;
  if (range === '1Y') {
    return new Intl.DateTimeFormat(locale, { month: 'short', day: 'numeric' }).format(dt);
  }
  return new Intl.DateTimeFormat(locale, { month: 'short', day: 'numeric' }).format(dt);
}

function formatTimeShort(iso, locale) {
  if (!iso) return '—';
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return '—';
  return new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit' }).format(dt);
}

function HistoryTooltip({ active, payload, unit, compareLastYear, locale, t }) {
  if (!active || !payload?.length) return null;
  const pt = payload[0]?.payload;
  if (!pt) return null;

  return (
    <div className="min-w-[175px] rounded-xl border border-slate-200 bg-white/95 p-3 text-xs shadow-lg backdrop-blur-md dark:border-slate-700 dark:bg-slate-900/95 dark:text-slate-100">
      <p className="mb-1.5 border-b border-slate-100 pb-1 font-bold text-slate-900 dark:border-slate-800 dark:text-white">
        {pt.fullDate}
      </p>
      <div className="space-y-1">
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-500 dark:text-slate-400">{t('marketDetail.modalPrice')}</span>
          <span className="font-black text-emerald-600 dark:text-emerald-400">
            {formatCurrency(pt.price, locale)} <span className="text-[10px] font-normal">{unit}</span>
          </span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-500 dark:text-slate-400">{t('marketDetail.dayRange')}</span>
          <span className="font-semibold text-slate-700 dark:text-slate-300">
            {formatCurrency(pt.minPrice, locale)} – {formatCurrency(pt.maxPrice, locale)}
          </span>
        </div>
        {compareLastYear && (
          <div className="flex items-center justify-between gap-3">
            <span className="text-slate-500 dark:text-slate-400">{t('marketDetail.lastYear')}</span>
            <span className="font-semibold text-indigo-600 dark:text-indigo-300">
              {formatCurrency(pt.lastYearPrice, locale)}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

function ChangeChip({ pct, diff, label, locale }) {
  const up = pct > 0.05;
  const down = pct < -0.05;
  return (
    <div
      className={`inline-flex items-center gap-1.5 rounded-xl border px-2.5 py-1 text-xs font-bold ${
        up
          ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800/60 dark:bg-emerald-500/15 dark:text-emerald-300'
          : down
            ? 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-800/60 dark:bg-rose-500/15 dark:text-rose-300'
            : 'border-slate-200 bg-slate-100 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300'
      }`}
    >
      {up ? <ArrowUpRight size={14} /> : down ? <ArrowDownRight size={14} /> : <Minus size={13} />}
      <span dir="ltr">
        {up ? '+' : ''}
        {pct.toFixed(1)}% ({diff >= 0 ? '+' : ''}
        {formatCurrency(diff, locale)})
      </span>
      <span className="font-medium opacity-80">· {label}</span>
    </div>
  );
}

export default function MarketCropDetail() {
  const { cropId = 'cashew' } = useParams();
  const { t } = useTranslation();

  // Crops without a proper photo are hidden from the catalog: show a friendly screen instead of crashing.
  if (!resolveKnownCrop(cropId)) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center bg-slate-50 px-4 pb-28 dark:bg-slate-950">
        <div role="status" className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <CropImage cropId={cropId} size="lg" className="mx-auto" />
          <h1 className="mt-4 text-lg font-black text-slate-900 dark:text-slate-100">{t('crops.unavailableTitle')}</h1>
          <p className="mt-1.5 text-sm text-slate-600 dark:text-slate-400">{t('crops.unavailableBody')}</p>
          <Link
            to="/market"
            className="mt-5 inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-sm font-bold text-white hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            <ArrowLeft size={16} />
            {t('crops.backToMarket')}
          </Link>
        </div>
      </div>
    );
  }
  return <MarketCropDetailView key={cropId} cropId={cropId} />;
}

function MarketCropDetailView({ cropId }) {
  const navigate = useNavigate();
  const { languageInfo, t } = useTranslation();
  const priceGradId = useId();

  const [range, setRange] = useState('30D');
  const [compareLastYear, setCompareLastYear] = useState(false);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [favourites, setFavourites] = useState(() => getFavouriteCropIds());
  const [alerts, setAlerts] = useState([]);
  const [triggeredBanner, setTriggeredBanner] = useState(null);
  const [alertDirection, setAlertDirection] = useState('above');
  const [alertTargetPrice, setAlertTargetPrice] = useState('');
  const [alertFeedback, setAlertFeedback] = useState('');
  const [shareToast, setShareToast] = useState('');

  const savedPlots = useLiveQuery(() => db.plots.toArray(), []);

  const loadDetail = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getCropMarketDetail(cropId, range);
      setDetail(data);
      setAlertTargetPrice((prev) => prev || String(Math.round(data.currentPrice * 1.05)));
      const existingAlerts = await getPriceAlerts(data.cropId);
      setAlerts(existingAlerts);
      const triggered = await evaluatePriceAlerts([
        {
          id: data.cropId,
          price: data.currentPrice,
          unit: data.unit,
          market: data.primaryMarket,
        },
      ]);
      setTriggeredBanner(triggered[0] || null);
    } catch (err) {
      setError(err?.message || 'Failed to load crop market details');
    } finally {
      setLoading(false);
    }
  }, [cropId, range]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadDetail();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadDetail]);

  const cropObj = useMemo(() => detail?.crop || getCropById(cropId), [detail, cropId]);
  const cropName = getCropDisplayName(cropObj, t);
  const cropLocalName = getCropLocalName(cropObj, t);
  const isFavourite = favourites.includes(cropObj.id);

  // Calculate total hectares for plots growing this crop
  const userCropAreaHa = useMemo(() => {
    const plots = savedPlots || [];
    const matching = plots.filter(
      (p) => p.primaryCrop === cropObj.id || p.intercrop === cropObj.id,
    );
    if (!matching.length) return 0;
    const totalHa = matching.reduce((sum, p) => {
      const ha = Number(p.areaHectares);
      if (Number.isFinite(ha) && ha > 0) return sum + ha;
      const raw = Number.parseFloat(p.area);
      return sum + (Number.isFinite(raw) && raw > 0 ? raw * 0.404686 : 0);
    }, 0);
    return Number(totalHa.toFixed(2));
  }, [savedPlots, cropObj.id]);

  const chartSeries = useMemo(() => {
    if (!detail?.history?.length) return [];
    return detail.history.map((pt, index) => ({
      ...pt,
      index,
      axisLabel: formatDateLabel(pt.iso, languageInfo.speechLang, range),
      fullDate: new Intl.DateTimeFormat(languageInfo.speechLang, { dateStyle: 'medium' }).format(
        new Date(pt.iso),
      ),
    }));
  }, [detail, languageInfo.speechLang, range]);

  const seasonalData = useMemo(() => {
    if (!detail?.analysis?.seasonalMonthly) return [];
    return detail.analysis.seasonalMonthly.map((item) => {
      const monthDate = new Date(2026, item.monthIndex, 15);
      return {
        ...item,
        monthLabel: new Intl.DateTimeFormat(languageInfo.speechLang, { month: 'short' }).format(
          monthDate,
        ),
      };
    });
  }, [detail, languageInfo.speechLang]);

  const plainAnalysisText = useMemo(() => {
    if (!detail) return '';
    const { trendDirection, pct7d, vsAvgPct, recommendation } = detail.analysis;
    const trendSentence =
      trendDirection === 'rising'
        ? t('marketDetail.analysisRising', { crop: cropName, pct: Math.abs(pct7d).toFixed(1) })
        : trendDirection === 'falling'
          ? t('marketDetail.analysisFalling', { crop: cropName, pct: Math.abs(pct7d).toFixed(1) })
          : t('marketDetail.analysisSteady', { crop: cropName });

    const avgSentence =
      vsAvgPct >= 0
        ? t('marketDetail.analysisAboveAvg', { pct: Math.abs(vsAvgPct).toFixed(1) })
        : t('marketDetail.analysisBelowAvg', { pct: Math.abs(vsAvgPct).toFixed(1) });

    const recSentence =
      recommendation === 'sell_now'
        ? t('marketDetail.recSellNowReason')
        : recommendation === 'wait'
          ? t('marketDetail.recWaitReason')
          : t('marketDetail.recHoldReason');

    return `${trendSentence} ${avgSentence} ${recSentence}`;
  }, [detail, cropName, t]);

  const handleToggleFavourite = () => {
    const next = toggleFavouriteCropId(cropObj.id);
    setFavourites(next);
  };

  const handleShare = async () => {
    if (!detail) return;
    const shareText = `${cropName}: ${formatCurrency(detail.currentPrice, languageInfo.speechLang)} (${detail.unit}) at ${detail.primaryMarket}. ${plainAnalysisText}`;
    const shareUrl = typeof window !== 'undefined' ? window.location.href : '';
    try {
      if (typeof navigator !== 'undefined' && navigator.share) {
        await navigator.share({
          title: `${cropName} — ${t('market.title')}`,
          text: shareText,
          url: shareUrl,
        });
        return;
      }
      if (typeof navigator !== 'undefined' && navigator.clipboard) {
        await navigator.clipboard.writeText(`${shareText} ${shareUrl}`.trim());
        setShareToast(t('marketDetail.copiedToClipboard'));
        setTimeout(() => setShareToast(''), 3000);
      }
    } catch {
      // user cancelled share sheet
    }
  };

  const handleCreateAlert = async (event) => {
    event.preventDefault();
    if (!detail) return;
    const cleaned = String(alertTargetPrice).trim().replace(/,/g, '.');
    const numeric = Number(cleaned);
    if (!Number.isFinite(numeric) || numeric <= 0) {
      setAlertFeedback(t('marketDetail.invalidTargetPrice'));
      return;
    }
    try {
      await createPriceAlert({
        cropId: cropObj.id,
        targetPrice: numeric,
        direction: alertDirection,
        market: detail.primaryMarket,
      });
      const updated = await getPriceAlerts(cropObj.id);
      setAlerts(updated);
      const triggered = await evaluatePriceAlerts([
        {
          id: cropObj.id,
          price: detail.currentPrice,
          unit: detail.unit,
          market: detail.primaryMarket,
        },
      ]);
      setTriggeredBanner(triggered[0] || null);
      setAlertFeedback(t('marketDetail.alertSaved'));
      setTimeout(() => setAlertFeedback(''), 3500);
    } catch {
      setAlertFeedback(t('marketDetail.invalidTargetPrice'));
    }
  };

  const handleDeleteAlert = async (id) => {
    await deletePriceAlert(id);
    const updated = await getPriceAlerts(cropObj.id);
    setAlerts(updated);
  };

  if (loading && !detail) {
    return (
      <div className="min-h-screen bg-slate-50 pb-28 dark:bg-slate-950" aria-busy="true">
        <div className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur-md dark:border-slate-800 dark:bg-slate-900/95">
          <div className="mx-auto flex max-w-4xl items-center gap-3">
            <div className="h-10 w-10 animate-pulse rounded-xl bg-slate-200 dark:bg-slate-800" />
            <div className="h-6 w-44 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
          </div>
        </div>
        <div className="mx-auto max-w-4xl space-y-5 px-4 pt-5 sm:px-6">
          <div className="h-44 animate-pulse rounded-3xl bg-white p-6 dark:bg-slate-900" />
          <div className="h-72 animate-pulse rounded-3xl bg-white p-6 dark:bg-slate-900" />
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {[1, 2, 3, 4, 5, 6].map((n) => (
              <div key={n} className="h-24 animate-pulse rounded-2xl bg-white dark:bg-slate-900" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error && !detail) {
    return (
      <div className="min-h-screen bg-slate-50 p-6 dark:bg-slate-950">
        <div className="mx-auto max-w-xl rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-900 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
          <p className="font-bold">{t('marketDetail.loadError')}</p>
          <div className="mt-4 flex gap-3">
            <button
              type="button"
              onClick={loadDetail}
              className="inline-flex items-center gap-2 rounded-xl bg-rose-600 px-4 py-2 text-sm font-bold text-white"
            >
              <RefreshCw size={15} />
              {t('weather.retry')}
            </button>
            <button
              type="button"
              onClick={() => navigate('/market')}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-bold text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
            >
              {t('marketDetail.backToMarket')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const minIdx = chartSeries.findIndex((pt) => pt.date === detail.minPoint?.date);
  const maxIdx = chartSeries.findIndex((pt) => pt.date === detail.maxPoint?.date);

  const recBadgeStyles =
    detail.analysis.recommendation === 'sell_now'
      ? 'bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-500/20 dark:text-emerald-200 dark:border-emerald-700'
      : detail.analysis.recommendation === 'wait'
        ? 'bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-500/20 dark:text-amber-200 dark:border-amber-700'
        : 'bg-sky-100 text-sky-900 border-sky-300 dark:bg-sky-500/20 dark:text-sky-200 dark:border-sky-700';

  const recLabel =
    detail.analysis.recommendation === 'sell_now'
      ? t('marketDetail.recSellNow')
      : detail.analysis.recommendation === 'wait'
        ? t('marketDetail.recWait')
        : t('marketDetail.recHold');

  const bestMonthNames = seasonalData
    .filter((m) => m.isBestMonth)
    .map((m) => m.monthLabel)
    .join(', ');

  return (
    <div className="min-h-screen bg-slate-50 pb-28 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      {/* Sticky sub-header with back button & quick actions */}
      <header className="sticky top-0 z-30 border-b border-slate-200/90 bg-white/95 px-4 py-3 backdrop-blur-md dark:border-slate-800 dark:bg-slate-900/95 sm:px-6">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <button
              type="button"
              onClick={() => navigate('/market')}
              aria-label={t('marketDetail.backToMarket')}
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-slate-200 bg-slate-50 text-slate-700 transition hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            >
              <ArrowLeft size={19} className={languageInfo.dir === 'rtl' ? 'rotate-180' : ''} />
            </button>
            <div className="min-w-0">
              <h1 className="truncate text-base font-black tracking-tight text-slate-900 dark:text-white sm:text-lg">
                {cropName}
              </h1>
              <p className="truncate text-xs text-slate-500 dark:text-slate-400">
                {detail.primaryMarket} · {detail.variety}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <ListenButton
              text={buildSpeechText([
                cropName,
                formatSpeakablePriceWithUnit(
                  detail.currentPrice,
                  detail.unitSpeakKey ? t(detail.unitSpeakKey) : detail.unit,
                  languageInfo.speechLang,
                ),
                plainAnalysisText,
              ])}
              variant="slate"
              size="xs"
              hideLabelOnMobile
              className="h-10 rounded-xl px-3"
            />

            <button
              type="button"
              onClick={handleToggleFavourite}
              aria-pressed={isFavourite}
              aria-label={
                isFavourite
                  ? t('marketDetail.removeFromFavourites')
                  : t('marketDetail.addToFavourites')
              }
              className={`inline-flex h-10 w-10 items-center justify-center rounded-xl border transition ${
                isFavourite
                  ? 'border-amber-300 bg-amber-50 text-amber-600 dark:border-amber-600/60 dark:bg-amber-500/15 dark:text-amber-300'
                  : 'border-slate-200 bg-slate-50 text-slate-500 hover:text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300'
              }`}
            >
              <Star size={17} className={isFavourite ? 'fill-current' : ''} />
            </button>

            <button
              type="button"
              onClick={handleShare}
              aria-label={t('marketDetail.share')}
              className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 bg-slate-50 text-slate-700 transition hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            >
              <Share2 size={17} />
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-4xl space-y-5 px-4 pt-5 sm:px-6">
        {/* Triggered Price Alert Notification Banner */}
        {triggeredBanner && (
          <div
            role="alert"
            className="flex items-start justify-between gap-3 rounded-2xl border border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-950 shadow-sm dark:border-emerald-700/70 dark:bg-emerald-950/60 dark:text-emerald-100"
          >
            <div className="flex items-start gap-3">
              <BellRing size={20} className="mt-0.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
              <div>
                <p className="font-bold">
                  {t('marketDetail.alertTriggeredTitle', {
                    crop: cropName,
                    price: formatCurrency(triggeredBanner.currentPrice, languageInfo.speechLang),
                  })}
                </p>
                <p className="mt-0.5 text-xs opacity-90">
                  {t('marketDetail.alertTriggeredBody', {
                    direction:
                      triggeredBanner.direction === 'above'
                        ? t('marketDetail.directionAbove')
                        : t('marketDetail.directionBelow'),
                    target: formatCurrency(triggeredBanner.targetPrice, languageInfo.speechLang),
                    market: triggeredBanner.market,
                  })}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setTriggeredBanner(null)}
              className="text-xs font-bold underline"
            >
              {t('voice.dismiss')}
            </button>
          </div>
        )}

        {/* (a) HERO CARD */}
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-6">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
            <CropImage cropId={cropObj.id} size="hero" className="shrink-0" />

            <div className="min-w-0 flex-1 space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
                  {cropName}
                </h2>
                {cropLocalName && cropLocalName !== cropName && (
                  <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                    {cropLocalName}
                  </span>
                )}
                {detail.isMock && (
                  <span className="rounded-full border border-amber-300 bg-amber-50 px-2.5 py-0.5 text-[11px] font-bold text-amber-800 dark:border-amber-600/50 dark:bg-amber-950/60 dark:text-amber-300">
                    {t('marketDetail.sampleDataBadge')}
                  </span>
                )}
              </div>

              <div className="flex flex-wrap items-baseline gap-2.5">
                <span
                  dir="ltr"
                  className="text-3xl font-black tracking-tight text-slate-900 dark:text-white sm:text-4xl"
                >
                  {formatCurrency(detail.currentPrice, languageInfo.speechLang)}
                </span>
                <span className="text-sm font-semibold text-slate-500 dark:text-slate-400">
                  {detail.unit}
                </span>
              </div>

              <div className="flex flex-wrap gap-2">
                <ChangeChip
                  pct={detail.pctDay}
                  diff={detail.diffDay}
                  label={t('marketDetail.vsYesterday')}
                  locale={languageInfo.speechLang}
                />
                <ChangeChip
                  pct={detail.pctWeek}
                  diff={detail.diffWeek}
                  label={t('marketDetail.vsLastWeek')}
                  locale={languageInfo.speechLang}
                />
              </div>

              <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 pt-1 text-xs text-slate-500 dark:text-slate-400">
                <span className="inline-flex items-center gap-1 font-semibold text-slate-700 dark:text-slate-300">
                  <MapPin size={13} className="text-emerald-600 dark:text-emerald-400" />
                  {detail.primaryMarket}
                </span>
                <span>
                  {t('marketDetail.gradeLabel')}: <strong className="text-slate-700 dark:text-slate-200">{detail.grade}</strong> ({detail.variety})
                </span>
                <span className="inline-flex items-center gap-1">
                  <Clock size={12} />
                  {t('weather.updated', {
                    time: formatTimeShort(detail.updatedAt, languageInfo.speechLang),
                  })}
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* (b) PRICE HISTORY CHART */}
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-white">
                {t('marketDetail.priceHistoryTitle')}
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {t('marketDetail.averageLineLabel')}: {formatCurrency(detail.averagePrice, languageInfo.speechLang)} ({detail.unit})
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200">
                <input
                  type="checkbox"
                  checked={compareLastYear}
                  onChange={(e) => setCompareLastYear(e.target.checked)}
                  className="h-3.5 w-3.5 rounded accent-emerald-600"
                />
                <span>{t('marketDetail.compareLastYear')}</span>
              </label>

              <div
                role="tablist"
                aria-label={t('marketDetail.priceHistoryTitle')}
                className="inline-flex rounded-xl bg-slate-100 p-1 dark:bg-slate-800"
              >
                {RANGES.map((r) => (
                  <button
                    key={r}
                    type="button"
                    role="tab"
                    aria-selected={range === r}
                    onClick={() => setRange(r)}
                    className={`rounded-lg px-2.5 py-1 text-xs font-bold transition ${
                      range === r
                        ? 'bg-white text-slate-900 shadow-xs dark:bg-slate-900 dark:text-white'
                        : 'text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white'
                    }`}
                  >
                    {r}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div
            dir="ltr"
            className="mt-4 h-[250px] min-h-[220px] w-full rounded-2xl border border-slate-100 bg-slate-50/50 p-2 dark:border-slate-800/80 dark:bg-slate-950/50"
          >
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartSeries} margin={{ top: 20, right: 12, left: 4, bottom: 4 }}>
                <defs>
                  <linearGradient id={priceGradId} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  horizontal
                  vertical={false}
                  stroke="#94a3b8"
                  strokeOpacity={0.14}
                  strokeDasharray="3 3"
                />
                <XAxis
                  dataKey="index"
                  tickFormatter={(idx) => chartSeries[idx]?.axisLabel || ''}
                  interval={Math.max(1, Math.floor(chartSeries.length / 6))}
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 11, fill: '#64748b' }}
                />
                <YAxis
                  domain={[
                    (dataMin) => Math.floor(dataMin * 0.95),
                    (dataMax) => Math.ceil(dataMax * 1.05),
                  ]}
                  tickCount={5}
                  width={52}
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 11, fill: '#64748b' }}
                  tickFormatter={(v) => `₹${Math.round(v)}`}
                />
                <Tooltip
                  content={
                    <HistoryTooltip
                      unit={detail.unit}
                      compareLastYear={compareLastYear}
                      locale={languageInfo.speechLang}
                      t={t}
                    />
                  }
                />
                <ReferenceLine
                  y={detail.averagePrice}
                  stroke="#64748b"
                  strokeDasharray="4 4"
                  strokeOpacity={0.75}
                  label={{
                    value: `${t('marketDetail.avgShort')} ₹${detail.averagePrice}`,
                    position: 'insideTopRight',
                    fill: '#64748b',
                    fontSize: 10,
                    fontWeight: 600,
                  }}
                />
                {compareLastYear && (
                  <Area
                    type="monotone"
                    dataKey="lastYearPrice"
                    stroke="#6366f1"
                    strokeWidth={1.75}
                    strokeDasharray="4 3"
                    fill="none"
                    dot={false}
                  />
                )}
                <Area
                  type="monotone"
                  dataKey="price"
                  stroke="#10b981"
                  strokeWidth={2.5}
                  fill={`url(#${priceGradId})`}
                  dot={false}
                />
                {minIdx >= 0 && (
                  <ReferenceDot
                    x={minIdx}
                    y={chartSeries[minIdx].price}
                    r={4}
                    fill="#f43f5e"
                    stroke="#ffffff"
                    strokeWidth={1.5}
                    label={{
                      value: `${t('weather.lowShort')} ₹${chartSeries[minIdx].price}`,
                      position: 'bottom',
                      fill: '#e11d48',
                      fontSize: 10,
                      fontWeight: 700,
                    }}
                  />
                )}
                {maxIdx >= 0 && maxIdx !== minIdx && (
                  <ReferenceDot
                    x={maxIdx}
                    y={chartSeries[maxIdx].price}
                    r={4}
                    fill="#059669"
                    stroke="#ffffff"
                    strokeWidth={1.5}
                    label={{
                      value: `${t('weather.highShort')} ₹${chartSeries[maxIdx].price}`,
                      position: 'top',
                      fill: '#059669',
                      fontSize: 10,
                      fontWeight: 700,
                    }}
                  />
                )}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* (c) KEY STATS GRID */}
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-6">
          <h2 className="text-lg font-bold text-slate-900 dark:text-white">
            {t('marketDetail.keyStatsTitle')}
          </h2>
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div className="rounded-2xl bg-slate-50 p-3.5 dark:bg-slate-950/70">
              <p className="text-xs text-slate-500 dark:text-slate-400">{t('marketDetail.todayModal')}</p>
              <p className="mt-1 text-lg font-black text-slate-900 dark:text-white">
                {formatCurrency(detail.stats.modalToday, languageInfo.speechLang)}
              </p>
              <p className="mt-0.5 text-[11px] text-slate-400">
                {formatCurrency(detail.stats.minToday, languageInfo.speechLang)} –{' '}
                {formatCurrency(detail.stats.maxToday, languageInfo.speechLang)}
              </p>
            </div>

            <div className="rounded-2xl bg-slate-50 p-3.5 dark:bg-slate-950/70">
              <p className="text-xs text-slate-500 dark:text-slate-400">{t('marketDetail.avg30d')}</p>
              <p className="mt-1 text-lg font-black text-slate-900 dark:text-white">
                {formatCurrency(detail.stats.avg30d, languageInfo.speechLang)}
              </p>
              <p className="mt-0.5 text-[11px] text-slate-400">{detail.unit}</p>
            </div>

            <div className="rounded-2xl bg-slate-50 p-3.5 dark:bg-slate-950/70">
              <p className="text-xs text-slate-500 dark:text-slate-400">{t('marketDetail.highLow52w')}</p>
              <p className="mt-1 text-lg font-black text-slate-900 dark:text-white">
                {formatCurrency(detail.stats.low52w, languageInfo.speechLang)} –{' '}
                {formatCurrency(detail.stats.high52w, languageInfo.speechLang)}
              </p>
              <p className="mt-0.5 text-[11px] text-slate-400">{t('marketDetail.yearlySpread')}</p>
            </div>

            <div className="rounded-2xl bg-slate-50 p-3.5 dark:bg-slate-950/70">
              <p className="text-xs text-slate-500 dark:text-slate-400">{t('marketDetail.volatility')}</p>
              <p className="mt-1 text-lg font-black capitalize text-slate-900 dark:text-white">
                {t(`marketDetail.volatility_${detail.stats.volatility}`)}
              </p>
              <p className="mt-0.5 text-[11px] text-slate-400">{t('marketDetail.priceStability')}</p>
            </div>

            <div className="rounded-2xl bg-slate-50 p-3.5 dark:bg-slate-950/70">
              <p className="text-xs text-slate-500 dark:text-slate-400">{t('marketDetail.arrivalsToday')}</p>
              <p className="mt-1 text-lg font-black text-slate-900 dark:text-white">
                {detail.stats.arrivalsTonnes} t
              </p>
              <p className="mt-0.5 text-[11px] text-slate-400">
                {detail.stats.arrivalsQuintals} {t('marketDetail.quintals')}
              </p>
            </div>

            <div className="rounded-2xl bg-slate-50 p-3.5 dark:bg-slate-950/70">
              <p className="text-xs text-slate-500 dark:text-slate-400">{t('marketDetail.gradeLabel')}</p>
              <p className="mt-1 text-lg font-black text-slate-900 dark:text-white">{detail.grade}</p>
              <p className="mt-0.5 truncate text-[11px] text-slate-400">{detail.variety}</p>
            </div>
          </div>
        </section>

        {/* (d) NEARBY MARKET COMPARISON */}
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-6">
          <div className="flex items-center justify-between gap-2">
            <div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-white">
                {t('marketDetail.nearbyMarketsTitle')}
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {t('marketDetail.nearbyMarketsSubtitle')}
              </p>
            </div>
          </div>

          <div className="mt-4 divide-y divide-slate-100 dark:divide-slate-800">
            {detail.nearbyMarkets.map((mkt) => (
              <div
                key={mkt.id}
                className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-bold text-slate-900 dark:text-white">{mkt.name}</span>
                    {mkt.isBestPrice && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-[11px] font-bold text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-300">
                        <Award size={12} />
                        {t('marketDetail.bestPriceBadge')}
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                    {mkt.region} · {mkt.distanceKm} km · {t('marketDetail.dayRange')}:{' '}
                    {formatCurrency(mkt.minPrice, languageInfo.speechLang)}–
                    {formatCurrency(mkt.maxPrice, languageInfo.speechLang)}
                  </p>
                </div>

                <div className="shrink-0 text-end">
                  <p className="text-base font-black text-slate-900 dark:text-white">
                    {formatCurrency(mkt.modalPrice, languageInfo.speechLang)}
                  </p>
                  <p className="text-[11px] text-slate-400">{detail.unit}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* (e) PLAIN-LANGUAGE ANALYSIS, SEASONAL PATTERN & FORECAST */}
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-300">
                <Sparkles size={19} />
              </div>
              <div>
                <h2 className="text-lg font-bold text-slate-900 dark:text-white">
                  {t('marketDetail.analysisTitle')}
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {t('marketDetail.analysisSubtitle')}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className={`rounded-xl border px-3 py-1 text-xs font-extrabold ${recBadgeStyles}`}>
                {recLabel}
              </span>
              <ListenButton
                text={[t('marketDetail.analysisTitle'), recLabel, plainAnalysisText]}
                variant="emerald"
                size="xs"
              />
            </div>
          </div>

          <p className="mt-4 rounded-2xl bg-slate-50 p-4 text-sm leading-relaxed text-slate-700 dark:bg-slate-950/70 dark:text-slate-200">
            {plainAnalysisText}
          </p>

          {/* Seasonal Pattern Chart (12 months) */}
          <div className="mt-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                {t('marketDetail.seasonalTitle')}
              </h3>
              <span className="text-xs font-semibold text-emerald-700 dark:text-emerald-300">
                {t('marketDetail.bestMonthsToSell', { months: bestMonthNames })}
              </span>
            </div>
            <div dir="ltr" className="mt-3 h-44 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={seasonalData} margin={{ top: 8, right: 6, left: -12, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke="#94a3b8" strokeOpacity={0.12} />
                  <XAxis
                    dataKey="monthLabel"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 10, fill: '#64748b' }}
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    width={46}
                    tick={{ fontSize: 10, fill: '#64748b' }}
                    tickFormatter={(v) => `₹${v}`}
                  />
                  <Bar dataKey="avgPrice" radius={[4, 4, 0, 0]}>
                    {seasonalData.map((entry) => (
                      <Cell
                        key={entry.monthIndex}
                        fill={entry.isBestMonth ? '#10b981' : '#94a3b8'}
                        fillOpacity={entry.isBestMonth ? 0.9 : 0.45}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 7-day Forecast Band (labelled as estimate) */}
          <div className="mt-5 rounded-2xl border border-slate-200/80 bg-slate-50/70 p-4 dark:border-slate-800 dark:bg-slate-950/60">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                {t('marketDetail.forecast7dTitle')}
              </span>
              <span className="rounded-full bg-slate-200/80 px-2 py-0.5 text-[10px] font-bold text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                {t('marketDetail.estimateBadge')}
              </span>
            </div>
            <p className="mt-1.5 text-xs text-slate-600 dark:text-slate-300">
              {t('marketDetail.forecastRangeBody', {
                low: formatCurrency(detail.analysis.forecast7d.at(-1)?.lowBand, languageInfo.speechLang),
                high: formatCurrency(detail.analysis.forecast7d.at(-1)?.highBand, languageInfo.speechLang),
                mid: formatCurrency(detail.analysis.forecast7d.at(-1)?.midPrice, languageInfo.speechLang),
              })}
            </p>
          </div>

          <p className="mt-3 flex items-start gap-1.5 text-[11px] text-slate-400 dark:text-slate-500">
            <Info size={13} className="mt-0.5 shrink-0" />
            <span>{t('marketDetail.financialDisclaimer')}</span>
          </p>
        </section>

        {/* (f) FARMING INFO & PERSONALIZED INCOME CALCULATOR */}
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-6">
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-300">
              <Wheat size={19} />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-white">
                {t('marketDetail.farmingInfoTitle')}
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {t('marketDetail.farmingInfoSubtitle')}
              </p>
            </div>
          </div>

          {userCropAreaHa > 0 && (
            <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50/90 p-4 text-sm font-semibold text-emerald-950 dark:border-emerald-800/70 dark:bg-emerald-950/50 dark:text-emerald-100">
              {t('marketDetail.personalizedIncomeBanner', {
                area: userCropAreaHa,
                crop: cropName,
                amount: formatCurrency(
                  Math.round(userCropAreaHa * detail.farming.expectedIncomePerHectare),
                  languageInfo.speechLang,
                ),
              })}
            </div>
          )}

          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-2xl bg-slate-50 p-3.5 dark:bg-slate-950/70">
              <p className="text-xs text-slate-500 dark:text-slate-400">{t('marketDetail.growingSeason')}</p>
              <p className="mt-1 text-sm font-bold capitalize text-slate-900 dark:text-white">
                {t(`marketDetail.season_${detail.farming.season}`)}
              </p>
            </div>
            <div className="rounded-2xl bg-slate-50 p-3.5 dark:bg-slate-950/70">
              <p className="text-xs text-slate-500 dark:text-slate-400">{t('marketDetail.cropDuration')}</p>
              <p className="mt-1 text-sm font-bold text-slate-900 dark:text-white">
                {t('marketDetail.durationDaysValue', { days: detail.farming.durationDays })}
              </p>
            </div>
            <div className="rounded-2xl bg-slate-50 p-3.5 dark:bg-slate-950/70">
              <p className="text-xs text-slate-500 dark:text-slate-400">{t('marketDetail.typicalYield')}</p>
              <p className="mt-1 text-sm font-bold text-slate-900 dark:text-white">
                {detail.farming.yieldPerHectareTonnes} t/ha
              </p>
            </div>
            <div className="rounded-2xl bg-slate-50 p-3.5 dark:bg-slate-950/70">
              <p className="text-xs text-slate-500 dark:text-slate-400">{t('marketDetail.expectedIncomeHa')}</p>
              <p className="mt-1 text-sm font-bold text-emerald-700 dark:text-emerald-300">
                {formatCurrency(detail.farming.expectedIncomePerHectare, languageInfo.speechLang)}/ha
              </p>
            </div>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-3.5 text-xs dark:border-slate-800 dark:bg-slate-950/50">
              <p className="font-bold text-slate-800 dark:text-slate-200">
                {t('marketDetail.storageTipsTitle')}
              </p>
              <p className="mt-1 leading-relaxed text-slate-600 dark:text-slate-400">
                {t('marketDetail.storageTipsBody')}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-3.5 text-xs dark:border-slate-800 dark:bg-slate-950/50">
              <p className="font-bold text-slate-800 dark:text-slate-200">
                {t('marketDetail.harvestTimingTitle')}
              </p>
              <p className="mt-1 leading-relaxed text-slate-600 dark:text-slate-400">
                {t('marketDetail.harvestTimingBody')}
              </p>
            </div>
          </div>
        </section>

        {/* (g) INPUTS & NEARBY HELP */}
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-6">
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-50 text-sky-600 dark:bg-sky-500/15 dark:text-sky-300">
              <Store size={19} />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-white">
                {t('marketDetail.inputsAndHelpTitle')}
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {t('marketDetail.inputsAndHelpSubtitle')}
              </p>
            </div>
          </div>

          {detail.inputsAndHelp.mspInrPerQuintal && (
            <div className="mt-4 flex items-center justify-between gap-3 rounded-2xl border border-amber-200 bg-amber-50/80 p-3.5 text-xs dark:border-amber-800/60 dark:bg-amber-950/40">
              <div className="flex items-center gap-2.5">
                <Landmark size={17} className="shrink-0 text-amber-700 dark:text-amber-300" />
                <div>
                  <p className="font-bold text-amber-950 dark:text-amber-100">
                    {t('marketDetail.mspTitle')}
                  </p>
                  <p className="text-amber-800 dark:text-amber-300">
                    {t('marketDetail.mspBody', {
                      msp: formatCurrency(detail.inputsAndHelp.mspInrPerQuintal, languageInfo.speechLang),
                    })}
                  </p>
                </div>
              </div>
              <Link
                to="/schemes"
                className="shrink-0 rounded-xl bg-amber-600 px-3 py-1.5 font-bold text-white hover:bg-amber-700"
              >
                {t('nav.schemes')}
              </Link>
            </div>
          )}

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {detail.inputsAndHelp.dealers.map((dealer) => (
              <div
                key={dealer.id}
                className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200/80 bg-slate-50/70 p-3.5 dark:border-slate-800 dark:bg-slate-950/60"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-bold text-slate-900 dark:text-white">
                    {dealer.name}
                  </p>
                  <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                    {dealer.location} · {dealer.distanceKm} km
                  </p>
                  <p className="mt-1 text-[11px] font-medium text-emerald-700 dark:text-emerald-300">
                    {t(dealer.stockKey)}
                  </p>
                </div>
                <a
                  href={`tel:${dealer.phone}`}
                  aria-label={`${t('marketDetail.callDealer')} ${dealer.name}`}
                  className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-600 text-white hover:bg-emerald-700"
                >
                  <Phone size={16} />
                </a>
              </div>
            ))}
          </div>
        </section>

        {/* (h) SET PRICE ALERT CARD */}
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-6">
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-50 text-violet-600 dark:bg-violet-500/15 dark:text-violet-300">
              <Bell size={19} />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-white">
                {t('marketDetail.setAlertTitle')}
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {t('marketDetail.setAlertSubtitle', { crop: cropName })}
              </p>
            </div>
          </div>

          <form onSubmit={handleCreateAlert} className="mt-4 flex flex-col gap-3 sm:flex-row">
            <select
              aria-label={t('marketDetail.alertCondition')}
              value={alertDirection}
              onChange={(e) => setAlertDirection(e.target.value)}
              className="h-11 rounded-xl border border-slate-300 bg-white px-3 text-[15px] font-semibold text-slate-900 outline-none focus:border-emerald-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 [&>option]:bg-white [&>option]:text-slate-900 dark:[&>option]:bg-slate-900 dark:[&>option]:text-slate-100"
            >
              <option value="above">{t('marketDetail.whenPriceAbove')}</option>
              <option value="below">{t('marketDetail.whenPriceBelow')}</option>
            </select>

            <div className="flex h-11 flex-1 items-center overflow-hidden rounded-xl border border-slate-300 bg-white focus-within:border-emerald-500 dark:border-slate-700 dark:bg-slate-950">
              <input
                type="text"
                inputMode="decimal"
                dir="ltr"
                value={alertTargetPrice}
                onChange={(e) => setAlertTargetPrice(e.target.value)}
                aria-label={t('marketDetail.targetPriceLabel')}
                placeholder="e.g. 200"
                className="h-full min-w-0 flex-1 bg-transparent px-3.5 text-[15px] font-semibold text-slate-900 outline-none dark:text-slate-100"
              />
              <span className="border-s border-slate-200 bg-slate-50 px-3 text-xs font-semibold text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
                {detail.unit}
              </span>
            </div>

            <button
              type="submit"
              className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-emerald-600 px-5 text-sm font-bold text-white transition hover:bg-emerald-700"
            >
              <Bell size={16} />
              <span>{t('marketDetail.saveAlertBtn')}</span>
            </button>
          </form>

          {alertFeedback && (
            <p role="status" className="mt-2.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
              {alertFeedback}
            </p>
          )}

          {alerts.length > 0 && (
            <div className="mt-4 space-y-2 border-t border-slate-100 pt-3 dark:border-slate-800">
              {alerts.map((al) => (
                <div
                  key={al.id}
                  className="flex items-center justify-between rounded-xl bg-slate-50 px-3.5 py-2 text-xs dark:bg-slate-950"
                >
                  <span className="font-semibold text-slate-700 dark:text-slate-200">
                    {al.direction === 'above'
                      ? t('marketDetail.whenPriceAbove')
                      : t('marketDetail.whenPriceBelow')}{' '}
                    <strong>{formatCurrency(al.targetPrice, languageInfo.speechLang)}</strong> ({detail.unit})
                  </span>
                  <button
                    type="button"
                    onClick={() => handleDeleteAlert(al.id)}
                    aria-label={t('common.delete')}
                    className="rounded-lg p-1 text-slate-400 hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-950/50"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* (i) RELATED CROPS */}
        {detail.relatedCropIds?.length > 0 && (
          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-6">
            <h2 className="text-lg font-bold text-slate-900 dark:text-white">
              {t('marketDetail.relatedCropsTitle')}
            </h2>
            <div className="mt-3 flex gap-3 overflow-x-auto pb-2">
              {detail.relatedCropIds.map((relId) => {
                const relCrop = getCropById(relId);
                return (
                  <Link
                    key={relId}
                    to={`/market/${relId}`}
                    className="flex min-w-[130px] shrink-0 items-center gap-2.5 rounded-2xl border border-slate-200 bg-slate-50/70 p-2.5 transition hover:border-emerald-400 hover:bg-emerald-50/40 dark:border-slate-800 dark:bg-slate-950/60 dark:hover:border-emerald-700"
                  >
                    <CropImage cropId={relId} size="sm" />
                    <div className="min-w-0">
                      <p className="truncate text-xs font-bold text-slate-900 dark:text-white">
                        {getCropDisplayName(relCrop, t)}
                      </p>
                      <span className="inline-flex items-center gap-0.5 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
                        {t('marketDetail.viewPrice')}
                        <ChevronRight size={12} className={languageInfo.dir === 'rtl' ? 'rotate-180' : ''} />
                      </span>
                    </div>
                  </Link>
                );
              })}
            </div>
          </section>
        )}
      </main>

      {shareToast && (
        <div
          role="status"
          className="fixed bottom-24 left-1/2 z-50 -translate-x-1/2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-xs font-bold text-emerald-900 shadow-lg dark:border-emerald-700 dark:bg-emerald-950 dark:text-emerald-200"
        >
          {shareToast}
        </div>
      )}
    </div>
  );
}
