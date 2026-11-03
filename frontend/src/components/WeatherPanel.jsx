import { useCallback, useEffect, useId, useMemo, useState } from 'react';
import {
  CloudRain,
  CloudSun,
  Droplets,
  Gauge,
  RefreshCw,
  Sprout,
  Thermometer,
  Wind,
} from 'lucide-react';
import {
  Area,
  Bar,
  CartesianGrid,
  ComposedChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useTranslation } from '../context/LanguageContext';
import { buildSampleWeather, fetchWeather, getCachedWeather } from '../services/weather';
import Select from './ui/Select';
import ListenButton from './ui/ListenButton';
import {
  buildSpeechText,
  formatSpeakablePercent,
  formatSpeakableTemperature,
} from '../utils/speechText';

const UNIT_KEY = 'fieldshift-weather-units';
const defaultUnits = { temperature: 'C', speed: 'km/h', precipitation: 'mm' };

function formatTime(value, locale) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat(locale, { hour: 'numeric', minute: '2-digit' }).format(date);
}

function formatHourShort(value, locale) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat(locale, { hour: 'numeric' }).format(date);
}

function convertTemp(celsius, unit) {
  if (!Number.isFinite(Number(celsius))) return 0;
  const c = Number(celsius);
  return unit === 'F' ? Number(((c * 9) / 5 + 32).toFixed(1)) : Number(c.toFixed(1));
}

function convertWind(kmh, unit) {
  if (!Number.isFinite(Number(kmh))) return 0;
  const v = Number(kmh);
  if (unit === 'mph') return Number((v * 0.621371).toFixed(1));
  if (unit === 'm/s') return Number((v / 3.6).toFixed(1));
  return Number(v.toFixed(1));
}

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined;
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const onChange = (event) => setReduced(event.matches);
    media.addEventListener?.('change', onChange);
    return () => media.removeEventListener?.('change', onChange);
  }, []);

  return reduced;
}

function WeatherTooltip({ active, payload, units, t }) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload;
  if (!point) return null;

  return (
    <div className="min-w-[185px] rounded-xl border border-slate-200/90 bg-white/95 p-3 text-xs shadow-lg backdrop-blur-md dark:border-slate-700/90 dark:bg-slate-900/95 dark:text-slate-100">
      <div className="mb-1.5 flex items-center justify-between gap-2 border-b border-slate-100 pb-1.5 dark:border-slate-800">
        <span className="font-bold text-slate-900 dark:text-white">{point.fullTime}</span>
        {point.isNow && (
          <span className="rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-bold text-sky-700 dark:bg-sky-500/20 dark:text-sky-300">
            {t('weather.now')}
          </span>
        )}
      </div>
      <div className="space-y-1 text-[11px]">
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-500 dark:text-slate-400">{t('weather.metricTemperature')}</span>
          <span className="font-bold text-slate-900 dark:text-white">
            {point.temperature}°{units.temperature}
          </span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-500 dark:text-slate-400">{t('weather.feelsLike')}</span>
          <span className="font-semibold text-slate-700 dark:text-slate-200">
            {point.feelsLike}°{units.temperature}
          </span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-500 dark:text-slate-400">{t('weather.rainChance')}</span>
          <span className="font-semibold text-sky-600 dark:text-sky-300">
            {point.rainProb}% ({point.rainMm} {units.precipitation})
          </span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-500 dark:text-slate-400">{t('weather.metricWind')}</span>
          <span className="font-semibold text-emerald-600 dark:text-emerald-300">
            {point.wind} {units.speed}
          </span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-500 dark:text-slate-400">{t('weather.humidity')}</span>
          <span className="font-semibold text-indigo-600 dark:text-indigo-300">
            {point.humidity}%
          </span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-500 dark:text-slate-400">{t('weather.metricSoilMoisture')}</span>
          <span className="font-semibold text-amber-600 dark:text-amber-300">
            {point.soilMoisture}%
          </span>
        </div>
      </div>
    </div>
  );
}

export default function WeatherPanel({ plots = [] }) {
  const { languageInfo, t } = useTranslation();
  const gradientId = useId();
  const prefersReducedMotion = usePrefersReducedMotion();
  const [selectedPlotId, setSelectedPlotId] = useState('');
  const [weather, setWeather] = useState(null);
  const [stale, setStale] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeMetric, setActiveMetric] = useState('temperature');
  const [units, setUnits] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(UNIT_KEY) || JSON.stringify(defaultUnits));
    } catch {
      return defaultUnits;
    }
  });
  const selectedPlot = useMemo(
    () => plots.find((plot) => String(plot.id) === String(selectedPlotId)) || plots[0],
    [plots, selectedPlotId],
  );

  const loadWeather = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await fetchWeather(selectedPlot);
      setWeather(result.data);
      setStale(false);
    } catch (loadError) {
      const cached = await getCachedWeather();
      if (cached) {
        setWeather(cached.data);
        setStale(true);
      } else {
        setError(loadError.message || 'Weather service unavailable');
      }
    } finally {
      setLoading(false);
    }
  }, [selectedPlot]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadWeather();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadWeather]);

  const updateUnits = (key, value) => {
    const next = { ...units, [key]: value };
    setUnits(next);
    localStorage.setItem(UNIT_KEY, JSON.stringify(next));
  };

  const handleLoadSample = () => {
    const sample = buildSampleWeather(selectedPlot);
    setWeather(sample);
    setStale(true);
    setError('');
  };

  const hourlySeries = useMemo(() => {
    const rawTimes = weather?.hourly?.time || [];
    if (!rawTimes.length) return [];

    const nowMs = weather?.fetchedAt ? new Date(weather.fetchedAt).getTime() : new Date(rawTimes[0]).getTime();
    let closestIdx = 0;
    let smallestDiff = Infinity;
    rawTimes.forEach((iso, idx) => {
      const ms = new Date(iso).getTime();
      const diff = Math.abs(ms - nowMs);
      if (Number.isFinite(diff) && diff < smallestDiff) {
        smallestDiff = diff;
        closestIdx = idx;
      }
    });

    const startIdx = Math.max(0, Math.min(closestIdx > 2 ? closestIdx - 2 : 0, Math.max(0, rawTimes.length - 24)));
    const sliceTimes = rawTimes.slice(startIdx, startIdx + 24);
    const nowOffset = Math.max(0, Math.min(sliceTimes.length - 1, closestIdx - startIdx));

    return sliceTimes.map((iso, i) => {
      const srcIdx = startIdx + i;
      const rawTemp = weather.hourly.temperature_2m?.[srcIdx] ?? 28;
      const rawFeels = weather.hourly.apparent_temperature?.[srcIdx] ?? rawTemp + 1.5;
      const rawRainProb = weather.hourly.precipitation_probability?.[srcIdx] ?? 0;
      const rawRainMm = weather.hourly.rain?.[srcIdx] ?? weather.hourly.precipitation?.[srcIdx] ?? 0;
      const rawWind = weather.hourly.wind_speed_10m?.[srcIdx] ?? 0;
      const rawHumidity = weather.hourly.relative_humidity_2m?.[srcIdx] ?? weather.current?.relative_humidity_2m ?? 65;
      const rawSoil = weather.hourly.soil_moisture_0_to_1cm?.[srcIdx] ?? weather.current?.soil_moisture_0_to_1cm ?? 0.26;
      const soilPct = rawSoil <= 1 ? Math.round(rawSoil * 100) : Math.round(rawSoil);

      return {
        index: i,
        iso,
        axisLabel: formatHourShort(iso, languageInfo.speechLang),
        fullTime: formatTime(iso, languageInfo.speechLang),
        isNow: i === nowOffset,
        temperature: convertTemp(rawTemp, units.temperature),
        feelsLike: convertTemp(rawFeels, units.temperature),
        rain: Math.round(rawRainProb),
        rainProb: Math.round(rawRainProb),
        rainMm: Number(Number(rawRainMm || 0).toFixed(1)),
        wind: convertWind(rawWind, units.speed),
        humidity: Math.round(rawHumidity),
        soilMoisture: Math.max(0, Math.min(100, soilPct)),
      };
    });
  }, [weather, languageInfo.speechLang, units.temperature, units.speed]);

  const metricConfig = useMemo(() => {
    const configs = {
      temperature: {
        key: 'temperature',
        label: t('weather.metricTemperature'),
        stroke: '#0ea5e9',
        fillTop: '#38bdf8',
        unitSuffix: `°${units.temperature}`,
        shortSuffix: '°',
        isPercent: false,
        icon: Thermometer,
      },
      rain: {
        key: 'rain',
        label: t('weather.metricRain'),
        stroke: '#2563eb',
        fillTop: '#60a5fa',
        unitSuffix: '%',
        shortSuffix: '%',
        isPercent: true,
        icon: CloudRain,
      },
      wind: {
        key: 'wind',
        label: t('weather.metricWind'),
        stroke: '#10b981',
        fillTop: '#34d399',
        unitSuffix: ` ${units.speed}`,
        shortSuffix: '',
        isPercent: false,
        icon: Wind,
      },
      humidity: {
        key: 'humidity',
        label: t('weather.metricHumidity'),
        stroke: '#6366f1',
        fillTop: '#818cf8',
        unitSuffix: '%',
        shortSuffix: '%',
        isPercent: true,
        icon: Droplets,
      },
      soilMoisture: {
        key: 'soilMoisture',
        label: t('weather.metricSoilMoisture'),
        stroke: '#d97706',
        fillTop: '#fbbf24',
        unitSuffix: '%',
        shortSuffix: '%',
        isPercent: true,
        icon: Sprout,
      },
    };
    return configs[activeMetric] || configs.temperature;
  }, [activeMetric, t, units.temperature, units.speed]);

  const chartStats = useMemo(() => {
    if (!hourlySeries.length) return null;
    const key = metricConfig.key;
    let minPoint = hourlySeries[0];
    let maxPoint = hourlySeries[0];
    let peakRainPoint = hourlySeries[0];
    let minTempPoint = hourlySeries[0];
    let maxTempPoint = hourlySeries[0];

    for (const pt of hourlySeries) {
      if (pt[key] < minPoint[key]) minPoint = pt;
      if (pt[key] > maxPoint[key]) maxPoint = pt;
      if (pt.rainProb > peakRainPoint.rainProb) peakRainPoint = pt;
      if (pt.temperature < minTempPoint.temperature) minTempPoint = pt;
      if (pt.temperature > maxTempPoint.temperature) maxTempPoint = pt;
    }

    const nowPoint = hourlySeries.find((pt) => pt.isNow) || hourlySeries[0];
    return {
      minPoint,
      maxPoint,
      nowPoint,
      peakRainPoint,
      minTempPoint,
      maxTempPoint,
    };
  }, [hourlySeries, metricConfig.key]);

  const chartSummaryText = useMemo(() => {
    if (!chartStats) return t('weather.emptyHourly');
    const { minTempPoint, maxTempPoint, peakRainPoint } = chartStats;
    return t('weather.chartSummary', {
      minTemp: `${Math.round(minTempPoint.temperature)}°${units.temperature}`,
      minTime: minTempPoint.fullTime,
      maxTemp: `${Math.round(maxTempPoint.temperature)}°${units.temperature}`,
      maxTime: maxTempPoint.fullTime,
      rainChance: peakRainPoint.rainProb,
      rainTime: peakRainPoint.fullTime,
    });
  }, [chartStats, t, units.temperature]);

  if (loading && !weather) {
    return (
      <div
        aria-busy="true"
        className="animate-pulse rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900"
      >
        <div className="flex items-center justify-between gap-4">
          <div className="h-6 w-44 rounded-lg bg-slate-200 dark:bg-slate-800" />
          <div className="h-9 w-28 rounded-lg bg-slate-200 dark:bg-slate-800" />
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-4">
          {[0, 1, 2, 3].map((idx) => (
            <div key={idx} className="h-24 rounded-xl bg-slate-100 dark:bg-slate-800/70" />
          ))}
        </div>
        <div className="mt-5 h-[220px] rounded-2xl bg-slate-100 dark:bg-slate-800/70" />
      </div>
    );
  }

  if (error && !weather) {
    return (
      <div className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-rose-800 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-200">
        <p className="font-semibold">{t('weather.error')}</p>
        <div className="mt-3 flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            onClick={loadWeather}
            className="inline-flex items-center gap-2 rounded-lg bg-rose-600 px-3.5 py-2 text-sm font-bold text-white hover:bg-rose-700"
          >
            <RefreshCw size={15} />
            {t('weather.retry')}
          </button>
          <button
            type="button"
            onClick={handleLoadSample}
            className="inline-flex items-center gap-2 rounded-lg border border-rose-300 bg-white px-3.5 py-2 text-sm font-semibold text-rose-800 hover:bg-rose-100 dark:border-rose-800 dark:bg-slate-900 dark:text-rose-200"
          >
            {t('weather.loadSampleForecast')}
          </button>
        </div>
      </div>
    );
  }

  const current = weather?.current || {};
  const currentTempDisplay = Math.round(convertTemp(current.temperature_2m || 0, units.temperature));
  const currentWindDisplay = Math.round(convertWind(current.wind_speed_10m || 0, units.speed));

  const daily = (weather?.daily?.time || []).slice(0, 7).map((time, index) => ({
    time: new Intl.DateTimeFormat(languageInfo.speechLang, { weekday: 'short' }).format(new Date(time)),
    min: convertTemp(weather.daily.temperature_2m_min[index], units.temperature),
    max: convertTemp(weather.daily.temperature_2m_max[index], units.temperature),
    rain: weather.daily.precipitation_sum[index] || 0,
  }));

  const voiceNarration = buildSpeechText([
    t('weather.title'),
    selectedPlot?.name || t('weather.locationFallback'),
    t(weather?.conditionKey || 'weather.unknown'),
    formatSpeakableTemperature(currentTempDisplay, units.temperature, languageInfo.speechLang),
    `${t('weather.humidity')} ${formatSpeakablePercent(current.relative_humidity_2m || 0, languageInfo.speechLang)}`,
    chartSummaryText,
    ...(weather?.advisories || []).map((advisory) => t(advisory.key, advisory.params || {})),
  ]);

  const metricTabs = [
    { id: 'temperature', label: t('weather.metricTemperature') },
    { id: 'rain', label: t('weather.metricRain') },
    { id: 'wind', label: t('weather.metricWind') },
    { id: 'humidity', label: t('weather.metricHumidity') },
    { id: 'soilMoisture', label: t('weather.metricSoilMoisture') },
  ];

  const yDomain = metricConfig.isPercent
    ? [0, 100]
    : [(dataMin) => Math.floor((Number.isFinite(dataMin) ? dataMin : 0) - 2), (dataMax) => Math.ceil((Number.isFinite(dataMax) ? dataMax : 30) + 2)];

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-900 dark:text-white">{t('weather.title')}</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {selectedPlot?.name || t('weather.locationFallback')}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {plots.length > 0 && (
            <Select
              aria-label={t('weather.selectPlot')}
              value={selectedPlot?.id || ''}
              onChange={(event) => setSelectedPlotId(event.target.value)}
              className="min-h-10 rounded-lg px-2.5 py-1 text-xs"
            >
              <option value="">{t('weather.selectPlot')}</option>
              {plots.map((plot) => (
                <option key={plot.id} value={plot.id}>
                  {plot.name}
                </option>
              ))}
            </Select>
          )}
          <ListenButton
            text={voiceNarration}
            labelKey="weather.listen"
            ariaLabelKey="weather.listen"
            variant="sky"
            size="xs"
            className="min-h-10 rounded-lg px-3 py-1.5"
          />
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3 text-xs">
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
          {stale
            ? t('weather.offline')
            : t('weather.updated', { time: formatTime(weather?.fetchedAt, languageInfo.speechLang) })}
        </span>
        <Select
          aria-label={t('weather.temperatureUnit')}
          value={units.temperature}
          onChange={(event) => updateUnits('temperature', event.target.value)}
          className="min-h-10 rounded-lg px-2.5 py-1 text-xs"
        >
          <option value="C">°C</option>
          <option value="F">°F</option>
        </Select>
        <Select
          aria-label={t('weather.windUnit')}
          value={units.speed}
          onChange={(event) => updateUnits('speed', event.target.value)}
          className="min-h-10 rounded-lg px-2.5 py-1 text-xs"
        >
          <option value="km/h">km/h</option>
          <option value="mph">mph</option>
          <option value="m/s">m/s</option>
        </Select>
        <button
          type="button"
          onClick={loadWeather}
          className="inline-flex items-center gap-1 font-medium text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
        >
          <RefreshCw size={13} />
          {t('weather.refresh')}
        </button>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-4">
        <div className="rounded-xl bg-sky-50 p-3 dark:bg-sky-500/10">
          <Thermometer size={18} className="text-sky-600 dark:text-sky-400" />
          <p className="mt-2 text-2xl font-black text-slate-900 dark:text-white">
            {currentTempDisplay}°{units.temperature}
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {t(weather?.conditionKey || 'weather.unknown')}
          </p>
        </div>
        <div className="rounded-xl bg-blue-50 p-3 dark:bg-blue-500/10">
          <Droplets size={18} className="text-blue-600 dark:text-blue-400" />
          <p className="mt-2 text-xl font-black text-slate-900 dark:text-white">
            {current.relative_humidity_2m || 0}%
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400">{t('weather.humidity')}</p>
        </div>
        <div className="rounded-xl bg-emerald-50 p-3 dark:bg-emerald-500/10">
          <Wind size={18} className="text-emerald-600 dark:text-emerald-400" />
          <p className="mt-2 text-xl font-black text-slate-900 dark:text-white">{currentWindDisplay}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">{units.speed}</p>
        </div>
        <div className="rounded-xl bg-amber-50 p-3 dark:bg-amber-500/10">
          <Gauge size={18} className="text-amber-600 dark:text-amber-400" />
          <p className="mt-2 text-xl font-black text-slate-900 dark:text-white">
            {Math.round(current.pressure_msl || 0)}
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400">{t('weather.pressureUnit')}</p>
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-12">
        {/* 24-Hour Interactive ComposedChart */}
        <div className="lg:col-span-7 flex flex-col">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-bold text-slate-900 dark:text-white">{t('weather.hourly')}</h3>
            <div
              role="tablist"
              aria-label={t('weather.hourly')}
              className="flex flex-wrap items-center gap-1 rounded-xl bg-slate-100 p-1 dark:bg-slate-800/90"
            >
              {metricTabs.map((tab) => {
                const selected = activeMetric === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    role="tab"
                    aria-selected={selected}
                    onClick={() => setActiveMetric(tab.id)}
                    className={`rounded-lg px-2.5 py-1 text-[11px] font-semibold transition-all ${
                      selected
                        ? 'bg-white text-slate-900 shadow-xs dark:bg-slate-900 dark:text-white'
                        : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200'
                    }`}
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>

          {hourlySeries.length === 0 ? (
            <div className="mt-3 flex min-h-[220px] items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50/60 p-6 text-center text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-400">
              {t('weather.emptyHourly')}
            </div>
          ) : (
            <>
              <div
                dir="ltr"
                className="mt-3 min-h-[220px] h-[230px] w-full min-w-0 rounded-2xl border border-slate-100 bg-slate-50/50 p-2 dark:border-slate-800/80 dark:bg-slate-950/50"
              >
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={hourlySeries} margin={{ top: 20, right: 8, left: -8, bottom: 4 }}>
                    <defs>
                      <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={metricConfig.fillTop} stopOpacity={0.38} />
                        <stop offset="95%" stopColor={metricConfig.fillTop} stopOpacity={0.02} />
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
                      tickFormatter={(idx) => hourlySeries[idx]?.axisLabel || ''}
                      interval={2}
                      axisLine={false}
                      tickLine={false}
                      tick={{ fontSize: 11, fill: '#64748b' }}
                      dy={4}
                    />

                    <YAxis
                      yAxisId="primary"
                      domain={yDomain}
                      tickCount={5}
                      width={40}
                      axisLine={false}
                      tickLine={false}
                      tick={{ fontSize: 11, fill: '#64748b' }}
                      tickFormatter={(val) => `${Math.round(val)}${metricConfig.shortSuffix}`}
                    />

                    <YAxis
                      yAxisId="rain"
                      orientation="right"
                      domain={[0, 100]}
                      tickCount={5}
                      width={34}
                      axisLine={false}
                      tickLine={false}
                      tick={{ fontSize: 11, fill: '#64748b' }}
                      tickFormatter={(val) => `${val}%`}
                    />

                    <Tooltip
                      content={<WeatherTooltip units={units} t={t} />}
                      cursor={{ stroke: '#94a3b8', strokeOpacity: 0.35, strokeDasharray: '3 3' }}
                    />

                    {activeMetric !== 'rain' && (
                      <Bar
                        yAxisId="rain"
                        dataKey="rainProb"
                        name={t('weather.rainChance')}
                        fill="#38bdf8"
                        fillOpacity={0.28}
                        barSize={7}
                        radius={[3, 3, 0, 0]}
                        isAnimationActive={!prefersReducedMotion}
                      />
                    )}

                    <Area
                      yAxisId="primary"
                      type="monotone"
                      dataKey={metricConfig.key}
                      stroke={metricConfig.stroke}
                      strokeWidth={2.5}
                      fill={`url(#${gradientId})`}
                      dot={false}
                      activeDot={{ r: 5, strokeWidth: 2, stroke: '#ffffff', fill: metricConfig.stroke }}
                      isAnimationActive={!prefersReducedMotion}
                    />

                    {chartStats?.nowPoint && (
                      <ReferenceLine
                        yAxisId="primary"
                        x={chartStats.nowPoint.index}
                        stroke={metricConfig.stroke}
                        strokeDasharray="3 3"
                        strokeOpacity={0.75}
                        label={{
                          value: t('weather.now'),
                          position: 'insideTop',
                          fill: metricConfig.stroke,
                          fontSize: 10,
                          fontWeight: 700,
                        }}
                      />
                    )}

                    {chartStats?.nowPoint && (
                      <ReferenceDot
                        yAxisId="primary"
                        x={chartStats.nowPoint.index}
                        y={chartStats.nowPoint[metricConfig.key]}
                        r={4.5}
                        fill={metricConfig.stroke}
                        stroke="#ffffff"
                        strokeWidth={2}
                      />
                    )}

                    {chartStats?.minPoint && (
                      <ReferenceDot
                        yAxisId="primary"
                        x={chartStats.minPoint.index}
                        y={chartStats.minPoint[metricConfig.key]}
                        r={3.5}
                        fill="#0284c7"
                        stroke="#ffffff"
                        strokeWidth={1.5}
                        label={{
                          value: `${t('weather.lowShort')} ${Math.round(chartStats.minPoint[metricConfig.key])}${metricConfig.shortSuffix}`,
                          position: 'bottom',
                          fill: '#64748b',
                          fontSize: 10,
                          fontWeight: 600,
                        }}
                      />
                    )}

                    {chartStats?.maxPoint && chartStats.maxPoint.index !== chartStats.minPoint?.index && (
                      <ReferenceDot
                        yAxisId="primary"
                        x={chartStats.maxPoint.index}
                        y={chartStats.maxPoint[metricConfig.key]}
                        r={3.5}
                        fill="#f97316"
                        stroke="#ffffff"
                        strokeWidth={1.5}
                        label={{
                          value: `${t('weather.highShort')} ${Math.round(chartStats.maxPoint[metricConfig.key])}${metricConfig.shortSuffix}`,
                          position: 'top',
                          fill: '#ea580c',
                          fontSize: 10,
                          fontWeight: 700,
                        }}
                      />
                    )}
                  </ComposedChart>
                </ResponsiveContainer>
              </div>

              <p
                className="mt-2.5 text-xs leading-relaxed text-slate-600 dark:text-slate-300"
                aria-live="polite"
              >
                {chartSummaryText}
              </p>
            </>
          )}
        </div>

        {/* 7-Day Outlook */}
        <div className="lg:col-span-5">
          <h3 className="text-sm font-bold text-slate-900 dark:text-white">{t('weather.daily')}</h3>
          <div className="mt-3 space-y-2">
            {daily.map((day) => (
              <div
                key={day.time}
                className="flex items-center justify-between rounded-xl bg-slate-50 px-3.5 py-2.5 text-xs dark:bg-slate-950/80"
              >
                <span className="font-semibold text-slate-700 dark:text-slate-200">{day.time}</span>
                <span className="font-bold text-slate-900 dark:text-white">
                  {Math.round(day.min)}° / {Math.round(day.max)}°
                </span>
                <span className="text-sky-600 dark:text-sky-400 font-medium">
                  {day.rain.toFixed(1)} {units.precipitation}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-2 sm:grid-cols-3">
        {weather.advisories?.map((advisory) => (
          <p
            key={advisory.key}
            className={`rounded-lg px-3 py-2 text-xs font-semibold ${
              advisory.severity === 'warning'
                ? 'bg-amber-50 text-amber-800 dark:bg-amber-500/10 dark:text-amber-200'
                : 'bg-emerald-50 text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-200'
            }`}
          >
            {t(advisory.key)}
          </p>
        ))}
      </div>

      <div className="mt-4 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
        <CloudSun size={15} />
        {t('weather.farmingHint')} · AQI {weather.air?.hourly?.us_aqi?.[0] ?? '—'}
      </div>
    </section>
  );
}
