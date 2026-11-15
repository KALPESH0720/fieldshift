import { useCallback, useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Link } from 'react-router-dom';
import { useLiveQuery } from 'dexie-react-hooks';
import {
  ArrowUpRight,
  ArrowDownRight,
  BellRing,
  Calendar,
  ChevronRight,
  Info,
  MapPin,
  Minus,
  RefreshCw,
  Search,
  Settings,
  Sparkles,
  Sprout,
  Star,
  TrendingUp,
} from 'lucide-react';
import { db } from '../db/db';
import { getCropById, getCropDisplayName, resolveKnownCrop } from '../data/crops';
import {
  evaluatePriceAlerts,
  getFavouriteCropIds,
  getMarketOverview,
  toggleFavouriteCropId,
} from '../services/market';
import { useTranslation } from '../context/LanguageContext';
import CropImage from './CropImage';
import Select from './ui/Select';
import ListenButton from './ui/ListenButton';

function pctChange(crop) {
  if (typeof crop.pctWeek === 'number') return crop.pctWeek;
  return crop.prev ? ((crop.price - crop.prev) / crop.prev) * 100 : 0;
}

function Sparkline({ data = [], positive }) {
  if (!data.length) return null;
  const w = 76;
  const h = 30;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const pts = data
    .map((v, i) => `${(i / Math.max(1, data.length - 1)) * w},${h - ((v - min) / range) * h}`)
    .join(' ');

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="overflow-visible" aria-hidden="true">
      <polyline
        points={pts}
        fill="none"
        stroke={positive ? '#10b981' : '#f43f5e'}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function PriceBadge({ crop }) {
  const pct = pctChange(crop);
  const up = pct > 0.05;
  const flat = Math.abs(pct) <= 0.05;

  if (flat) {
    return (
      <span className="inline-flex items-center gap-0.5 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-bold text-slate-500 dark:bg-slate-800 dark:text-slate-400">
        <Minus size={11} /> 0%
      </span>
    );
  }
  return (
    <span
      className={`inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-bold ${
        up
          ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
          : 'bg-rose-50 text-rose-600 dark:bg-rose-500/15 dark:text-rose-300'
      }`}
    >
      {up ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
      {Math.abs(pct).toFixed(1)}%
    </span>
  );
}

function CropCard({ crop, index, isFavourite, isMyCrop, onToggleFav, t, locale, dir }) {
  const pct = pctChange(crop);
  const up = pct >= 0;
  const cropDef = getCropById(crop.id);
  const displayName = getCropDisplayName(cropDef, t);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: Math.min(index * 0.03, 0.25) }}
      className="group relative flex items-center gap-3 rounded-2xl border border-slate-200/80 bg-white p-3.5 shadow-xs transition-all hover:border-emerald-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-emerald-700 sm:gap-4 sm:p-4"
    >
      <Link
        to={`/market/${crop.id}`}
        aria-label={`${displayName} — ₹${crop.price.toLocaleString(locale)} (${crop.unit})`}
        className="flex min-w-0 flex-1 items-center gap-3.5 rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
      >
        <CropImage cropId={crop.id} size="sm" />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <p className="truncate font-black text-slate-900 dark:text-slate-100">{displayName}</p>
            <PriceBadge crop={crop} />
            {isMyCrop && (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">
                <Sprout size={10} />
                {t('market.myCropBadge')}
              </span>
            )}
          </div>
          <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
            <MapPin size={11} className="shrink-0" />
            <span className="truncate">{crop.market}</span>
            <span className="text-slate-300 dark:text-slate-700">·</span>
            <span className="truncate">{crop.variety}</span>
          </div>
        </div>

        <div className="hidden sm:block">
          <Sparkline data={crop.weekData} positive={up} />
        </div>

        <div className="shrink-0 text-end">
          <p dir="ltr" className="text-base font-black text-slate-900 dark:text-slate-100 sm:text-lg">
            ₹{crop.price.toLocaleString(locale)}
          </p>
          <p className="text-[11px] text-slate-400">{crop.unit}</p>
        </div>

        <ChevronRight
          size={18}
          aria-hidden="true"
          className={`shrink-0 text-slate-400 transition-transform group-hover:translate-x-0.5 group-hover:text-emerald-600 dark:text-slate-500 dark:group-hover:text-emerald-400 ${
            dir === 'rtl' ? 'rotate-180 group-hover:-translate-x-0.5' : ''
          }`}
        />
      </Link>

      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onToggleFav(crop.id);
        }}
        aria-pressed={isFavourite}
        aria-label={
          isFavourite ? t('marketDetail.removeFromFavourites') : t('marketDetail.addToFavourites')
        }
        className={`hidden xs:inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border transition sm:inline-flex ${
          isFavourite
            ? 'border-amber-300 bg-amber-50 text-amber-500 dark:border-amber-600/50 dark:bg-amber-500/15 dark:text-amber-300'
            : 'border-transparent text-slate-300 hover:bg-slate-100 hover:text-slate-600 dark:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300'
        }`}
      >
        <Star size={15} className={isFavourite ? 'fill-current' : ''} />
      </button>
    </motion.div>
  );
}

function AISummaryCard({ crops, t }) {
  const best = useMemo(() => {
    if (!crops.length) return null;
    return [...crops].sort((a, b) => pctChange(b) - pctChange(a))[0];
  }, [crops]);

  if (!best) return null;
  const bestCropName = getCropDisplayName(getCropById(best.id), t);
  const pct = pctChange(best);
  const summary =
    pct >= 0
      ? t('market.aiSummaryRising', {
          crop: bestCropName,
          pct: Math.abs(pct).toFixed(1),
          market: best.market,
        })
      : t('market.aiSummaryFalling', {
          crop: bestCropName,
          pct: Math.abs(pct).toFixed(1),
          market: best.market,
        });

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-5 text-white shadow-xl"
    >
      <div className="absolute -right-8 -top-8 h-40 w-40 rounded-full bg-emerald-500/15 blur-2xl" />
      <div className="relative z-10">
        <div className="mb-3 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl border border-emerald-500/30 bg-emerald-500/20">
              <Sparkles size={15} className="text-emerald-300" />
            </div>
            <span className="text-xs font-bold uppercase tracking-widest text-emerald-300">
              {t('market.aiInsightHeading')}
            </span>
          </div>
          <ListenButton
            text={[t('market.aiInsightHeading'), summary]}
            variant="dark"
            size="xs"
          />
        </div>

        <p className="text-sm leading-6 text-slate-200">{summary}</p>

        <div className="mt-4 flex items-center gap-2 text-[11px] text-slate-400">
          <Calendar size={11} />
          <span>{t('market.aiDataSourceNote')}</span>
          <Info size={11} className="ms-auto" />
        </div>
      </div>
    </motion.div>
  );
}

export default function MarketInsights() {
  const { languageInfo, t } = useTranslation();
  const savedPlots = useLiveQuery(() => db.plots.toArray(), []);

  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const [activeMarket, setActiveMarket] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('change');
  const [myCropsFirst, setMyCropsFirst] = useState(true);
  const [favourites, setFavourites] = useState(() => getFavouriteCropIds());
  const [triggeredAlerts, setTriggeredAlerts] = useState([]);

  const myPlotCropSet = useMemo(() => {
    const plots = savedPlots || [];
    const ids = new Set();
    for (const plot of plots) {
      const primary = resolveKnownCrop(plot.primaryCrop);
      const inter = resolveKnownCrop(plot.intercrop);
      if (primary && primary.id !== 'other') ids.add(primary.id);
      if (inter && inter.id !== 'other') ids.add(inter.id);
    }
    return ids;
  }, [savedPlots]);

  const loadMarket = useCallback(
    async (isManualRefresh = false) => {
      if (isManualRefresh) setRefreshing(true);
      else setLoading(true);
      setError('');
      try {
        const res = await getMarketOverview({
          plotCropIds: Array.from(myPlotCropSet),
        });
        setOverview(res);
        const triggered = await evaluatePriceAlerts(res.items || []);
        setTriggeredAlerts(triggered);
      } catch (err) {
        setError(err?.message || 'Unable to load market prices');
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [myPlotCropSet],
  );

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadMarket(false);
    }, 0);
    return () => clearTimeout(timer);
  }, [loadMarket]);

  const handleToggleFav = (cropId) => {
    const next = toggleFavouriteCropId(cropId);
    setFavourites(next);
  };

  const marketList = useMemo(() => overview?.markets || [], [overview]);

  const filteredAndSorted = useMemo(() => {
    const items = overview?.items || [];
    const needle = searchQuery.trim().toLocaleLowerCase();
    const favSet = new Set(favourites);

    const matching = items.filter((item) => {
      if (activeMarket !== 'ALL' && item.marketId !== activeMarket && item.market !== activeMarket) {
        return false;
      }
      if (!needle) return true;
      const cropDef = getCropById(item.id);
      const text = `${getCropDisplayName(cropDef, t)} ${item.id} ${item.market} ${item.variety}`.toLocaleLowerCase();
      return text.includes(needle);
    });

    return [...matching].sort((a, b) => {
      const aFav = favSet.has(a.id) ? 1 : 0;
      const bFav = favSet.has(b.id) ? 1 : 0;
      if (aFav !== bFav) return bFav - aFav;

      if (myCropsFirst) {
        const aMine = myPlotCropSet.has(a.id) ? 1 : 0;
        const bMine = myPlotCropSet.has(b.id) ? 1 : 0;
        if (aMine !== bMine) return bMine - aMine;
      }

      if (sortBy === 'price') return b.price - a.price;
      if (sortBy === 'name') {
        const nameA = getCropDisplayName(getCropById(a.id), t);
        const nameB = getCropDisplayName(getCropById(b.id), t);
        return nameA.localeCompare(nameB, languageInfo.speechLang);
      }
      return Math.abs(pctChange(b)) - Math.abs(pctChange(a));
    });
  }, [overview, activeMarket, searchQuery, favourites, myCropsFirst, myPlotCropSet, sortBy, t, languageInfo.speechLang]);

  return (
    <div className="min-h-screen bg-slate-50 pb-28 dark:bg-slate-950">
      {/* Header */}
      <div className="border-b border-slate-200 bg-white px-4 pb-3 pt-5 dark:border-slate-800 dark:bg-slate-900 sm:px-6">
        <div className="mx-auto max-w-2xl">
          <div className="flex items-center justify-between pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-md shadow-blue-500/25">
                <TrendingUp size={22} className="text-white" />
              </div>
              <div>
                <h1 className="text-xl font-black tracking-tight text-slate-900 dark:text-slate-100">
                  {t('market.title')}
                </h1>
                <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                  {t('market.subtitle')}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => loadMarket(true)}
              aria-label={t('weather.refresh')}
              className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-600 transition hover:bg-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-slate-800 dark:text-slate-400"
            >
              <motion.span
                animate={refreshing ? { rotate: 360 } : {}}
                transition={{ duration: 0.7, repeat: refreshing ? Infinity : 0, ease: 'linear' }}
              >
                <RefreshCw size={18} />
              </motion.span>
            </button>
          </div>

          {/* Search + Sort + My Crops First */}
          <div className="mb-3 flex flex-col gap-2.5 sm:flex-row">
            <label className="relative flex-1">
              <span className="sr-only">{t('crops.search')}</span>
              <Search
                size={16}
                className="pointer-events-none absolute start-3.5 top-1/2 -translate-y-1/2 text-slate-400"
              />
              <input
                type="search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={t('market.searchPlaceholder')}
                className="h-11 w-full rounded-xl border border-slate-200 bg-slate-50 ps-10 pe-3.5 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:bg-white dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:focus:bg-slate-900"
              />
            </label>

            <div className="flex items-center gap-2">
              <Select
                aria-label={t('market.sortByLabel')}
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="h-11 rounded-xl text-xs font-semibold"
              >
                <option value="change">{t('market.sortByChange')}</option>
                <option value="price">{t('market.sortByPrice')}</option>
                <option value="name">{t('market.sortByName')}</option>
              </Select>

              <button
                type="button"
                aria-pressed={myCropsFirst}
                onClick={() => setMyCropsFirst((prev) => !prev)}
                className={`inline-flex h-11 shrink-0 items-center gap-1.5 rounded-xl border px-3 text-xs font-bold transition ${
                  myCropsFirst
                    ? 'border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200'
                    : 'border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300'
                }`}
              >
                <Sprout size={14} />
                <span>{t('market.myCropsFirst')}</span>
              </button>
            </div>
          </div>

          {/* Regional Market Filter Pills */}
          <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 scrollbar-hide">
            <button
              type="button"
              onClick={() => setActiveMarket('ALL')}
              className={`shrink-0 rounded-full px-3.5 py-1.5 text-xs font-bold transition ${
                activeMarket === 'ALL'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400'
              }`}
            >
              {t('market.allMarkets')}
            </button>
            {marketList.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => setActiveMarket(m.id)}
                className={`shrink-0 rounded-full px-3.5 py-1.5 text-xs font-bold transition ${
                  activeMarket === m.id
                    ? 'bg-blue-600 text-white shadow-xs'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400'
                }`}
              >
                {m.name}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-2xl space-y-4 px-4 pt-5 sm:px-6">
        {/* Triggered price alert banners */}
        {triggeredAlerts.map((al) => {
          const cName = getCropDisplayName(getCropById(al.cropId), t);
          return (
            <div
              key={al.id}
              role="alert"
              className="flex items-center justify-between gap-3 rounded-2xl border border-emerald-300 bg-emerald-50 p-3.5 text-xs text-emerald-950 dark:border-emerald-700/70 dark:bg-emerald-950/60 dark:text-emerald-100"
            >
              <div className="flex items-center gap-2.5">
                <BellRing size={17} className="shrink-0 text-emerald-600 dark:text-emerald-400" />
                <span>
                  <strong>{cName}</strong>: ₹{al.currentPrice} ({al.unit}) —{' '}
                  {t('marketDetail.alertTriggeredShort', { target: `₹${al.targetPrice}` })}
                </span>
              </div>
              <Link
                to={`/market/${al.cropId}`}
                className="shrink-0 font-bold text-emerald-700 underline dark:text-emerald-300"
              >
                {t('marketDetail.viewPrice')}
              </Link>
            </div>
          );
        })}

        {loading && !overview ? (
          <div className="space-y-3" aria-busy="true">
            <div className="h-32 animate-pulse rounded-2xl bg-slate-200 dark:bg-slate-800" />
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-20 animate-pulse rounded-2xl bg-white dark:bg-slate-900" />
            ))}
          </div>
        ) : error && !overview ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-rose-900 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
            <p className="font-semibold">{t('marketDetail.loadError')}</p>
            <button
              type="button"
              onClick={() => loadMarket(false)}
              className="mt-3 inline-flex items-center gap-2 rounded-xl bg-rose-600 px-4 py-2 text-xs font-bold text-white"
            >
              <RefreshCw size={14} />
              {t('weather.retry')}
            </button>
          </div>
        ) : (
          <>
            <AISummaryCard
              crops={filteredAndSorted.length ? filteredAndSorted : overview?.items || []}
              t={t}
            />

            <div className="space-y-2.5">
              <div className="flex items-center justify-between px-1">
                <p className="text-xs font-bold uppercase tracking-widest text-slate-400">
                  {t('market.priceVsLastWeek')}
                </p>
                <span className="text-xs text-slate-400">
                  {t('market.cropsCount', { count: filteredAndSorted.length })}
                </span>
              </div>

              {filteredAndSorted.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
                  {t('crops.noResults')}
                </div>
              ) : (
                <AnimatePresence mode="popLayout">
                  {filteredAndSorted.map((crop, i) => (
                    <CropCard
                      key={crop.id}
                      crop={crop}
                      index={i}
                      isFavourite={favourites.includes(crop.id)}
                      isMyCrop={myPlotCropSet.has(crop.id)}
                      onToggleFav={handleToggleFav}
                      t={t}
                      locale={languageInfo.speechLang}
                      dir={languageInfo.dir}
                    />
                  ))}
                </AnimatePresence>
              )}
            </div>
          </>
        )}

        {/* Settings link chip */}
        <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
          <Link
            to="/settings"
            className="flex items-center gap-3 text-sm font-semibold text-slate-600 transition-colors hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
          >
            <Settings size={16} className="text-slate-400" />
            <span>{t('market.alertSettingsLink')}</span>
            <ChevronRight size={15} className="ms-auto text-slate-300" />
          </Link>
        </div>
      </div>
    </div>
  );
}
