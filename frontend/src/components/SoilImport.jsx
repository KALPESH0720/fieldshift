import { useCallback, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useLiveQuery } from 'dexie-react-hooks';
import {
  Camera,
  CheckCircle2,
  ChevronRight,
  FlaskConical,
  Info,
  Loader2,
  Sparkles,
  Upload,
  X,
} from 'lucide-react';
import { db } from '../db/db';
import { apiRequest } from '../api/client';
import { useTranslation } from '../context/LanguageContext';
import ListenButton from './ui/ListenButton';
import {
  formatSpeakableNumber,
  formatSpeakablePercent,
} from '../utils/speechText';

/* ─── Goan laterite soil mock profile ───────────────────────── */
const LATERITE_PROFILE = {
  nitrogen: '140',     // kg/ha — low-medium (typical Goa laterite)
  phosphorus: '18',    // kg/ha — low
  potassium: '210',    // kg/ha — medium-high (K leaches less in laterite)
  ph: '5.5',           // slightly acidic
  organicCarbon: '0.62', // %  — low
  ec: '0.28',          // dS/m — safe
};

const LATERITE_TIP_KEYS = [
  'soil.lateriteTip1',
  'soil.lateriteTip2',
  'soil.lateriteTip3',
];

/* ─── Nutrient field config ──────────────────────────────────── */
const NUTRIENT_FIELDS = [
  { id: 'nitrogen',      labelKey: 'soil.fields.nitrogen.label',      tipKey: 'soil.fields.nitrogen.tip',      unit: 'kg/ha', unitSpeakKey: 'soil.units.kgPerHa', min: 0, max: 600, color: 'emerald' },
  { id: 'phosphorus',    labelKey: 'soil.fields.phosphorus.label',    tipKey: 'soil.fields.phosphorus.tip',    unit: 'kg/ha', unitSpeakKey: 'soil.units.kgPerHa', min: 0, max: 150, color: 'blue' },
  { id: 'potassium',     labelKey: 'soil.fields.potassium.label',     tipKey: 'soil.fields.potassium.tip',     unit: 'kg/ha', unitSpeakKey: 'soil.units.kgPerHa', min: 0, max: 500, color: 'violet' },
  { id: 'ph',            labelKey: 'soil.fields.ph.label',            tipKey: 'soil.fields.ph.tip',            unit: '',      unitSpeakKey: '',                  min: 3, max: 9.5, color: 'amber' },
  { id: 'organicCarbon', labelKey: 'soil.fields.organicCarbon.label', tipKey: 'soil.fields.organicCarbon.tip', unit: '%',     unitSpeakKey: 'percent',           min: 0, max: 5,   color: 'rose' },
  { id: 'ec',            labelKey: 'soil.fields.ec.label',            tipKey: 'soil.fields.ec.tip',            unit: 'dS/m',  unitSpeakKey: 'soil.units.dsPerM',  min: 0, max: 8,   color: 'teal' },
];

const EMPTY_FORM = { nitrogen: '', phosphorus: '', potassium: '', ph: '', organicCarbon: '', ec: '' };

/* ─── Colour map helper (Tailwind v4 needs literal classes) ──── */
const colorMap = {
  emerald: { ring: 'focus:ring-emerald-500/20', border: 'focus:border-emerald-500', badge: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-700' },
  blue:    { ring: 'focus:ring-blue-500/20',    border: 'focus:border-blue-500',    badge: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-500/10 dark:text-blue-300 dark:border-blue-700' },
  violet:  { ring: 'focus:ring-violet-500/20',  border: 'focus:border-violet-500',  badge: 'bg-violet-50 text-violet-700 border-violet-200 dark:bg-violet-500/10 dark:text-violet-300 dark:border-violet-700' },
  amber:   { ring: 'focus:ring-amber-500/20',   border: 'focus:border-amber-500',   badge: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-700' },
  rose:    { ring: 'focus:ring-rose-500/20',    border: 'focus:border-rose-500',    badge: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:border-rose-700' },
  teal:    { ring: 'focus:ring-teal-500/20',    border: 'focus:border-teal-500',    badge: 'bg-teal-50 text-teal-700 border-teal-200 dark:bg-teal-500/10 dark:text-teal-300 dark:border-teal-700' },
};

/* ─── Soil Dropzone ──────────────────────────────────────────── */
function SoilDropzone({ onFile, imagePreview, onClear, ocrLoading, t }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const handleFiles = (files) => {
    const file = files?.[0];
    if (file && file.type.startsWith('image/')) onFile(file);
  };

  return (
    <div className="space-y-3">
      <label className="block text-sm font-bold text-slate-700 dark:text-slate-300">
        {t('soil.cardPhotoLabel')}
        <span className="ml-2 rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[10px] font-bold text-blue-600 dark:border-blue-700 dark:bg-blue-500/10 dark:text-blue-300">
          {t('soil.ocrBadge')}
        </span>
      </label>

      <AnimatePresence mode="wait">
        {imagePreview ? (
          <motion.div
            key="preview"
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.96 }}
            transition={{ duration: 0.25 }}
            className="relative overflow-hidden rounded-2xl border-2 border-emerald-300 bg-slate-100 dark:bg-slate-800"
          >
            <img
              src={imagePreview}
              alt={t('soil.cardPhotoLabel')}
              className="h-52 w-full object-cover"
            />
            <AnimatePresence>
              {ocrLoading && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-slate-950/70 backdrop-blur-sm"
                >
                  <Loader2 size={28} className="animate-spin text-emerald-400" />
                  <p className="text-sm font-bold text-white">{t('soil.extractingValues')}</p>
                  <p className="text-xs text-slate-300">{t('soil.extractingSubtext')}</p>
                </motion.div>
              )}
            </AnimatePresence>
            {!ocrLoading && (
              <button
                type="button"
                onClick={onClear}
                aria-label={t('soil.removePhoto')}
                className="absolute right-2 top-2 flex h-8 w-8 items-center justify-center rounded-xl bg-slate-950/60 text-white backdrop-blur-sm transition hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-white"
              >
                <X size={15} />
              </button>
            )}
            {!ocrLoading && (
              <div className="absolute bottom-2 left-2 flex items-center gap-1.5 rounded-xl bg-emerald-600/90 px-3 py-1.5 text-xs font-bold text-white backdrop-blur-sm">
                <CheckCircle2 size={13} /> {t('soil.valuesExtracted')}
              </div>
            )}
          </motion.div>
        ) : (
          <motion.button
            key="dropzone"
            type="button"
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); }}
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
            animate={dragging ? { scale: 1.02, borderColor: '#10b981' } : {}}
            className={`flex w-full flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed py-10 transition-all duration-200 focus:outline-none focus:ring-4 focus:ring-emerald-500/20 ${
              dragging
                ? 'border-emerald-400 bg-emerald-50 dark:bg-emerald-500/10'
                : 'border-slate-300 bg-slate-50 dark:bg-slate-950 hover:border-emerald-400 hover:bg-emerald-50/60'
            }`}
          >
            <motion.div
              animate={{ y: [0, -5, 0] }}
              transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
              className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-400 to-teal-500 shadow-lg shadow-emerald-500/25"
            >
              {dragging ? <Upload size={28} className="text-white" /> : <Camera size={28} className="text-white" />}
            </motion.div>
            <div className="text-center px-3">
              <p className="text-base font-bold text-slate-800 dark:text-slate-200">
                {dragging ? t('soil.dropToUpload') : t('soil.uploadCardTitle')}
              </p>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                {t('soil.uploadCardSubtitle')}
              </p>
              <p className="mt-0.5 text-xs text-slate-400">{t('soil.supportedFormats')}</p>
            </div>
          </motion.button>
        )}
      </AnimatePresence>

      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="sr-only"
        onChange={(e) => handleFiles(e.target.files)}
        aria-label={t('soil.uploadCardTitle')}
      />

      <p className="flex items-start gap-2 rounded-xl border border-blue-100 bg-blue-50/70 px-3 py-2 text-xs leading-5 text-blue-700 dark:border-blue-800 dark:bg-blue-500/10 dark:text-blue-200">
        <Info size={13} className="mt-0.5 shrink-0 text-blue-500" />
        {t('soil.ocrExplain')}
      </p>
    </div>
  );
}

/* ─── Nutrient Input ─────────────────────────────────────────── */
function NutrientInput({ field, value, onChange, t }) {
  const [focused, setFocused] = useState(false);
  const { ring, border, badge } = colorMap[field.color];
  const labelUp = focused || value.length > 0;

  return (
    <div className="space-y-1">
      <div className="relative">
        <input
          id={`soil-${field.id}`}
          type="number"
          step="0.01"
          min={field.min}
          max={field.max}
          value={value}
          onChange={(e) => onChange(field.id, e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder=" "
          className={`peer min-h-[3.5rem] w-full rounded-2xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 pl-4 pr-16 pb-2 pt-5 text-base font-semibold text-slate-900 dark:text-slate-100 outline-none transition-all duration-200 hover:border-slate-300 focus:bg-white dark:bg-slate-900 focus:ring-4 ${ring} ${border}`}
        />
        <label
          htmlFor={`soil-${field.id}`}
          className={`pointer-events-none absolute left-4 font-medium transition-all duration-200 ${
            labelUp
              ? `top-1.5 translate-y-0 text-[10px] uppercase tracking-wide ${focused ? 'text-slate-600 dark:text-slate-400' : 'text-slate-400'}`
              : 'top-1/2 -translate-y-1/2 text-sm text-slate-500 dark:text-slate-400'
          }`}
        >
          {t(field.labelKey)}
        </label>
        {field.unit && (
          <span className={`pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 rounded-lg border px-2 py-0.5 text-xs font-bold ${badge}`}>
            {field.unit}
          </span>
        )}
      </div>
      <p className="flex items-center gap-1 pl-1 text-[11px] text-slate-400">
        <Info size={10} className="shrink-0" />
        {t(field.tipKey)}
      </p>
    </div>
  );
}

/* ─── Save feedback toast ────────────────────────────────────── */
function SaveToast({ show, t }) {
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 0, y: 24, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 24, scale: 0.95 }}
          transition={{ type: 'spring', stiffness: 380, damping: 28 }}
          className="fixed bottom-24 left-1/2 z-50 -translate-x-1/2 flex items-center gap-3 rounded-2xl bg-slate-900 px-5 py-3.5 text-sm font-semibold text-white shadow-xl shadow-black/30"
        >
          <CheckCircle2 size={18} className="text-emerald-400" />
          {t('soil.savedOfflineToast')}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/* ─── SoilImport page ────────────────────────────────────────── */
export default function SoilImport() {
  const { t, languageInfo } = useTranslation();
  const speechLocale = languageInfo.speechLang;

  const plots = useLiveQuery(() => db.plots.toArray(), []);
  const [selectedPlotId, setSelectedPlotId] = useState('');
  const [form, setForm] = useState(EMPTY_FORM);
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [lateriteTipsVisible, setLateriteTipsVisible] = useState(false);

  /* Photo upload: mock OCR after 1.8s */
  const handleFile = useCallback(async (file) => {
    setImageFile(file);
    setImagePreview(URL.createObjectURL(file));
    setOcrLoading(true);
    await new Promise((r) => setTimeout(r, 1800));
    setForm(LATERITE_PROFILE);
    setOcrLoading(false);
  }, []);

  const clearImage = () => {
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    setImageFile(null);
    setImagePreview(null);
    setForm(EMPTY_FORM);
  };

  const updateField = useCallback((id, val) => {
    setForm((f) => ({ ...f, [id]: val }));
  }, []);

  /* Populate laterite preset */
  const populateLaterite = () => {
    setForm(LATERITE_PROFILE);
    setLateriteTipsVisible(true);
  };

  const lateriteSpeechParts = useMemo(
    () => [
      t('soil.lateriteActionsHeading'),
      ...LATERITE_TIP_KEYS.map((key) => t(key)),
    ],
    [t],
  );

  const pageSpeechParts = useMemo(() => {
    const parts = [t('soil.title'), t('soil.overviewSpeech')];
    const enteredReadings = NUTRIENT_FIELDS.map((field) => {
      const raw = form[field.id];
      if (raw === '' || raw == null) return null;
      const num = Number(raw);
      if (!Number.isFinite(num)) return null;
      const label = t(field.labelKey);
      if (field.unitSpeakKey === 'percent') {
        return `${label}: ${formatSpeakablePercent(num, speechLocale, 2)}`;
      }
      if (field.unitSpeakKey) {
        return `${label}: ${formatSpeakableNumber(num, speechLocale, 2)} ${t(field.unitSpeakKey)}`;
      }
      return `${label}: ${formatSpeakableNumber(num, speechLocale, 2)}`;
    }).filter(Boolean);

    if (enteredReadings.length > 0) {
      parts.push(t('soil.currentReadingsIntro'));
      parts.push(...enteredReadings);
    }
    if (lateriteTipsVisible) {
      parts.push(...lateriteSpeechParts);
    }
    return parts;
  }, [form, lateriteSpeechParts, lateriteTipsVisible, speechLocale, t]);

  /* Save to Dexie and sync with backend if online */
  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const selectedPlot = plots?.find((p) => String(p.id) === String(selectedPlotId)) || plots?.[0] || null;
      const plotId = selectedPlot?.id || null;

      await db.soilRecords.add({
        plotId,
        ph: parseFloat(form.ph) || null,
        nitrogen: parseFloat(form.nitrogen) || null,
        phosphorus: parseFloat(form.phosphorus) || null,
        potassium: parseFloat(form.potassium) || null,
        organicCarbon: parseFloat(form.organicCarbon) || null,
        ec: parseFloat(form.ec) || null,
        hasPhoto: Boolean(imageFile),
        timestamp: new Date().toISOString(),
      });

      const USE_MOCKS = String(import.meta.env.VITE_USE_MOCKS ?? 'true').toLowerCase() === 'true';
      if (!USE_MOCKS && selectedPlot?.serverId && typeof navigator !== 'undefined' && navigator.onLine) {
        try {
          await apiRequest(`/plots/${selectedPlot.serverId}/soil-tests`, {
            method: 'POST',
            body: {
              n_val: parseFloat(form.nitrogen) || null,
              p_val: parseFloat(form.phosphorus) || null,
              k_val: parseFloat(form.potassium) || null,
              ph: parseFloat(form.ph) || null,
              organic_matter: parseFloat(form.organicCarbon) || null,
              nutrient_unit: 'kg/ha',
              organic_matter_unit: 'percent',
              provenance: 'manual',
            },
          });
        } catch (apiErr) {
          console.warn('Backend soil test sync deferred:', apiErr);
        }
      }

      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      setForm(EMPTY_FORM);
      clearImage();
      setLateriteTipsVisible(false);
    } catch (err) {
      console.error('Field Shift: soil record save failed', err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 pb-28">
      {/* ── Page header ── */}
      <div className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700/80 px-4 py-5 sm:px-6">
        <div className="mx-auto max-w-2xl flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600 shadow-md shadow-violet-500/25">
              <FlaskConical size={22} className="text-white" />
            </div>
            <div className="min-w-0">
              <h1 className="text-xl font-black tracking-tight text-slate-900 dark:text-slate-100">
                {t('soil.title')}
              </h1>
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                {t('soil.subtitle')}
              </p>
            </div>
          </div>

          <ListenButton
            id="soil-header-listen"
            variant="violet"
            text={pageSpeechParts}
          />
        </div>
      </div>

      <div className="mx-auto max-w-2xl space-y-6 px-4 pt-6 sm:px-6">

        {/* ── Laterite quick-fill card ── */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="overflow-hidden rounded-2xl border border-amber-200 bg-gradient-to-br from-amber-50 to-orange-50 dark:border-amber-700 dark:from-amber-500/10 dark:to-orange-500/10"
        >
          <button
            type="button"
            onClick={populateLaterite}
            className="flex w-full items-center gap-4 px-5 py-4 text-left transition hover:bg-amber-100/60 focus:outline-none focus:ring-2 focus:ring-amber-400 focus:ring-inset dark:hover:bg-amber-500/20"
          >
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 shadow-sm shadow-amber-500/20">
              <Sparkles size={20} className="text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-black text-slate-800 dark:text-slate-200">
                {t('soil.populateLateriteTitle')}
              </p>
              <p className="mt-0.5 text-xs text-slate-600 dark:text-slate-400 leading-5">
                {t('soil.populateLateriteDesc')}
              </p>
            </div>
            <ChevronRight size={18} className="shrink-0 text-amber-500" />
          </button>

          <AnimatePresence>
            {lateriteTipsVisible && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.3, ease: 'easeInOut' }}
                className="overflow-hidden border-t border-amber-200 bg-amber-100/40 px-5 py-3 dark:border-amber-700 dark:bg-amber-500/10"
              >
                <div className="mb-2 flex items-center justify-between gap-2">
                  <p className="text-[11px] font-bold uppercase tracking-wide text-amber-700 dark:text-amber-300">
                    {t('soil.lateriteActionsHeading')}
                  </p>
                  <ListenButton
                    id="soil-laterite-listen"
                    variant="amber"
                    size="xs"
                    text={lateriteSpeechParts}
                  />
                </div>
                <ul className="space-y-1.5">
                  {LATERITE_TIP_KEYS.map((tipKey) => (
                    <li key={tipKey} className="flex items-start gap-2 text-xs leading-5 text-amber-900 dark:text-amber-100">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
                      {t(tipKey)}
                    </li>
                  ))}
                </ul>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>

        {/* ── Photo upload ── */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.08 }}
          className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 shadow-sm"
        >
          <SoilDropzone
            onFile={handleFile}
            imagePreview={imagePreview}
            onClear={clearImage}
            ocrLoading={ocrLoading}
            t={t}
          />
        </motion.div>

        {/* ── Manual entry form ── */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.15 }}
          className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 shadow-sm"
        >
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h2 className="text-base font-black text-slate-900 dark:text-slate-100">
                {t('soil.manualEntryTitle')}
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {t('soil.manualEntrySubtitle')}
              </p>
            </div>
            <span className="rounded-full border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {t('soil.primaryMacrosBadge')}
            </span>
          </div>

          <form id="soil-form" onSubmit={handleSubmit} noValidate>
            {plots && plots.length > 0 && (
              <div className="mb-4">
                <label htmlFor="soil-plot-select" className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                  {t('soil.selectPlot', { defaultValue: 'Associated Plot' })}
                </label>
                <select
                  id="soil-plot-select"
                  value={selectedPlotId || (plots[0]?.id ?? '')}
                  onChange={(e) => setSelectedPlotId(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-semibold text-slate-900 shadow-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                >
                  {plots.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} {p.village ? `(${p.village})` : ''}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {NUTRIENT_FIELDS.map((field) => (
                <NutrientInput
                  key={field.id}
                  field={field}
                  value={form[field.id]}
                  onChange={updateField}
                  t={t}
                />
              ))}
            </div>
          </form>
        </motion.div>

        {/* ── Submit bar ── */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.22 }}
          className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 shadow-sm"
        >
          <motion.button
            type="submit"
            form="soil-form"
            disabled={saving}
            whileTap={{ scale: 0.98 }}
            whileHover={{ scale: 1.01 }}
            className="flex min-h-14 w-full items-center justify-center gap-2.5 rounded-2xl bg-gradient-to-r from-violet-600 to-purple-600 px-5 text-base font-bold text-white shadow-lg shadow-violet-700/25 transition-all hover:shadow-violet-600/35 focus:outline-none focus:ring-4 focus:ring-violet-500/30 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {saving ? (
              <Loader2 size={20} className="animate-spin" />
            ) : (
              <>
                <FlaskConical size={20} />
                {t('soil.saveRecordBtn')}
              </>
            )}
          </motion.button>
          <p className="mt-3 text-center text-xs text-slate-400">
            {t('soil.storedLocallyNote')}
          </p>
        </motion.div>
      </div>

      <SaveToast show={saved} t={t} />
    </div>
  );
}
