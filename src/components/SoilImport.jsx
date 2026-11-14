import { useCallback, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useLiveQuery } from 'dexie-react-hooks';
import {
  AlertCircle,
  Camera,
  CheckCircle2,
  ChevronRight,
  FileText,
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
import SoilSensor3D from './SoilSensor3D';
import {
  formatSpeakableNumber,
  formatSpeakablePercent,
} from '../utils/speechText';
import { extractSoilCardFromImage } from '../services/soilCardOcr';

const LATERITE_TIP_KEYS = [
  'soil.lateriteTip1',
  'soil.lateriteTip2',
  'soil.lateriteTip3',
];

/* ─── Primary & Secondary / Micronutrient SHC Field Configs ──── */
const PRIMARY_NUTRIENT_FIELDS = [
  { id: 'ph',            labelKey: 'soil.fields.ph.label',            tipKey: 'soil.fields.ph.tip',            unit: '',      unitSpeakKey: '',                  min: 1, max: 14,   color: 'amber' },
  { id: 'ec',            labelKey: 'soil.fields.ec.label',            tipKey: 'soil.fields.ec.tip',            unit: 'dS/m',  unitSpeakKey: 'soil.units.dsPerM',  min: 0, max: 100,  color: 'teal' },
  { id: 'organicCarbon', labelKey: 'soil.fields.organicCarbon.label', tipKey: 'soil.fields.organicCarbon.tip', unit: '%',     unitSpeakKey: 'percent',           min: 0, max: 50,   color: 'rose' },
  { id: 'nitrogen',      labelKey: 'soil.fields.nitrogen.label',      tipKey: 'soil.fields.nitrogen.tip',      unit: 'kg/ha', unitSpeakKey: 'soil.units.kgPerHa', min: 0, max: 5000, color: 'emerald' },
  { id: 'phosphorus',    labelKey: 'soil.fields.phosphorus.label',    tipKey: 'soil.fields.phosphorus.tip',    unit: 'kg/ha', unitSpeakKey: 'soil.units.kgPerHa', min: 0, max: 2000, color: 'blue' },
  { id: 'potassium',     labelKey: 'soil.fields.potassium.label',     tipKey: 'soil.fields.potassium.tip',     unit: 'kg/ha', unitSpeakKey: 'soil.units.kgPerHa', min: 0, max: 5000, color: 'violet' },
];

const MICRONUTRIENT_FIELDS = [
  { id: 'sulphur',   label: 'Available Sulphur (S)',   tip: 'Normal level: > 10 ppm',  unit: 'ppm', min: 0, max: 2000, color: 'amber' },
  { id: 'zinc',      label: 'Available Zinc (Zn)',     tip: 'Normal level: > 0.6 ppm', unit: 'ppm', min: 0, max: 500,  color: 'teal' },
  { id: 'boron',     label: 'Available Boron (B)',     tip: 'Normal level: > 0.5 ppm', unit: 'ppm', min: 0, max: 500,  color: 'violet' },
  { id: 'iron',      label: 'Available Iron (Fe)',     tip: 'Normal level: > 4.5 ppm', unit: 'ppm', min: 0, max: 2000, color: 'rose' },
  { id: 'manganese', label: 'Available Manganese (Mn)', tip: 'Normal level: > 2.0 ppm', unit: 'ppm', min: 0, max: 2000, color: 'blue' },
  { id: 'copper',    label: 'Available Copper (Cu)',   tip: 'Normal level: > 0.2 ppm', unit: 'ppm', min: 0, max: 500,  color: 'emerald' },
];

const ALL_SOIL_FIELDS = [...PRIMARY_NUTRIENT_FIELDS, ...MICRONUTRIENT_FIELDS];

const METADATA_FIELDS = [
  { id: 'cardNumber',   label: 'Soil Health Card Number',        placeholder: 'e.g. AP/2017-18/35499766/2' },
  { id: 'farmerName',   label: 'Farmer Name',                    placeholder: 'As printed on card' },
  { id: 'soilType',     label: 'Soil Type',                      placeholder: 'e.g. Black soil, Red soil, Alluvial' },
  { id: 'state',        label: 'State',                          placeholder: 'e.g. ANDHRA PRADESH' },
  { id: 'district',     label: 'District',                       placeholder: 'e.g. WEST GODAVARI' },
  { id: 'surveyNumber', label: 'Survey No., Khasra No./ Dag No.', placeholder: 'e.g. 90/5' },
  { id: 'farmSize',     label: 'Farm Size',                      placeholder: 'e.g. 1.19 Acre' },
];

const EMPTY_FORM = {
  ph: '',
  ec: '',
  organicCarbon: '',
  nitrogen: '',
  phosphorus: '',
  potassium: '',
  sulphur: '',
  zinc: '',
  boron: '',
  iron: '',
  manganese: '',
  copper: '',
};

const EMPTY_METADATA = {
  cardNumber: '',
  farmerName: '',
  soilType: '',
  state: '',
  district: '',
  surveyNumber: '',
  farmSize: '',
};

/* ─── Colour map helper (Tailwind v4 needs literal classes) ──── */
const colorMap = {
  emerald: { ring: 'focus-within:ring-emerald-500/20', border: 'focus-within:border-emerald-500 dark:focus-within:border-emerald-400', badge: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-700' },
  blue:    { ring: 'focus-within:ring-blue-500/20',    border: 'focus-within:border-blue-500 dark:focus-within:border-blue-400',       badge: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-500/10 dark:text-blue-300 dark:border-blue-700' },
  violet:  { ring: 'focus-within:ring-violet-500/20',  border: 'focus-within:border-violet-500 dark:focus-within:border-violet-400',   badge: 'bg-violet-50 text-violet-700 border-violet-200 dark:bg-violet-500/10 dark:text-violet-300 dark:border-violet-700' },
  amber:   { ring: 'focus-within:ring-amber-500/20',   border: 'focus-within:border-amber-500 dark:focus-within:border-amber-400',     badge: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-700' },
  rose:    { ring: 'focus-within:ring-rose-500/20',    border: 'focus-within:border-rose-500 dark:focus-within:border-rose-400',       badge: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:border-rose-700' },
  teal:    { ring: 'focus-within:ring-teal-500/20',    border: 'focus-within:border-teal-500 dark:focus-within:border-teal-400',       badge: 'bg-teal-50 text-teal-700 border-teal-200 dark:bg-teal-500/10 dark:text-teal-300 dark:border-teal-700' },
};

function getRatingBadgeStyle(rating) {
  if (!rating) return '';
  const lower = rating.toLowerCase();
  if (lower.includes('sufficient') || lower.includes('normal') || lower.includes('neutral') || lower.includes('high')) {
    return 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-700';
  }
  if (lower.includes('medium') || lower.includes('moderate')) {
    return 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-700';
  }
  return 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:border-rose-700';
}

/* ─── Soil Dropzone ──────────────────────────────────────────── */
function SoilDropzone({ onFile, imagePreview, onClear, ocrLoading, ocrProgress, ocrStatus, t }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const handleFiles = (files) => {
    const file = files?.[0];
    if (file && file.type.startsWith('image/')) onFile(file);
  };

  const progressPct = Math.round((ocrProgress?.progress || 0) * 100);

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
              className="h-56 w-full object-contain bg-slate-900/5 dark:bg-slate-950"
            />
            <AnimatePresence>
              {ocrLoading && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-slate-950/75 px-6 text-center backdrop-blur-sm"
                >
                  <Loader2 size={28} className="animate-spin text-emerald-400" />
                  <p className="text-sm font-bold text-white">{t('soil.extractingValues')}</p>
                  <p className="text-xs text-slate-300">
                    {ocrProgress?.message || t('soil.extractingSubtext')}
                  </p>
                  {progressPct > 0 && (
                    <div className="h-1.5 w-48 overflow-hidden rounded-full bg-slate-800">
                      <div
                        className="h-full bg-emerald-400 transition-all duration-300"
                        style={{ width: `${progressPct}%` }}
                      />
                    </div>
                  )}
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
            {!ocrLoading && ocrStatus && (
              <div
                className={`absolute bottom-2 left-2 right-2 flex items-center justify-between gap-2 rounded-xl px-3 py-1.5 text-xs font-bold text-white backdrop-blur-sm ${
                  ocrStatus.extractedCount > 0 ? 'bg-emerald-600/90' : 'bg-amber-600/90'
                }`}
              >
                <span className="flex items-center gap-1.5">
                  {ocrStatus.extractedCount > 0 ? <CheckCircle2 size={13} /> : <AlertCircle size={13} />}
                  {ocrStatus.summary}
                </span>
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
function NutrientInput({ field, value, unitOverride, rating, needsManualReview, onChange, t }) {
  const [focused, setFocused] = useState(false);
  const { ring, border, badge } = colorMap[field.color];
  const labelUp = focused || String(value || '').length > 0;
  const displayLabel = field.labelKey ? t(field.labelKey) : field.label;
  const displayTip = field.tipKey ? t(field.tipKey) : field.tip;
  const displayUnit = unitOverride || field.unit;
  const reviewWarningText = 'Not detected on card — enter manually if available';

  return (
    <div className="space-y-1">
      <div
        className={`relative flex min-h-[3.5rem] w-full items-center rounded-2xl border bg-slate-50 dark:bg-slate-950 transition-all duration-200 hover:border-slate-300 dark:hover:border-slate-600 focus-within:bg-white dark:focus-within:bg-slate-900 focus-within:ring-4 ${ring} ${border} ${
          needsManualReview
            ? 'border-amber-300 dark:border-amber-600/80 bg-amber-50/30 dark:bg-amber-500/5'
            : 'border-slate-200 dark:border-slate-700'
        }`}
      >
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
          className="soil-nutrient-input peer w-full flex-1 min-w-0 bg-transparent border-0 outline-none pl-4 pr-2 pb-2 pt-5 text-base font-semibold text-slate-900 dark:text-slate-50 focus:bg-transparent focus:outline-none focus:ring-0"
        />
        <label
          htmlFor={`soil-${field.id}`}
          className={`pointer-events-none absolute left-4 font-medium transition-all duration-200 ${
            labelUp
              ? `top-1.5 translate-y-0 text-[10px] uppercase tracking-wide ${focused ? 'text-slate-600 dark:text-slate-300' : 'text-slate-400'}`
              : 'top-1/2 -translate-y-1/2 text-sm text-slate-500 dark:text-slate-400'
          }`}
        >
          {displayLabel}
        </label>
        {(rating || displayUnit) && (
          <div className="pointer-events-none flex shrink-0 items-center gap-1.5 pr-3">
            {rating && (
              <span className={`rounded-lg border px-2 py-0.5 text-[10px] font-bold ${getRatingBadgeStyle(rating)}`}>
                {rating}
              </span>
            )}
            {displayUnit && (
              <span className={`rounded-lg border px-2 py-0.5 text-xs font-bold ${badge}`}>
                {displayUnit}
              </span>
            )}
          </div>
        )}
      </div>
      <p className={`flex items-center gap-1 pl-1 text-[11px] ${needsManualReview ? 'text-amber-600 dark:text-amber-400 font-medium' : 'text-slate-400'}`}>
        {needsManualReview ? <AlertCircle size={10} className="shrink-0" /> : <Info size={10} className="shrink-0" />}
        {needsManualReview ? reviewWarningText : displayTip}
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
  const [metadataForm, setMetadataForm] = useState(EMPTY_METADATA);
  const [extractedRatings, setExtractedRatings] = useState({});
  const [extractedUnits, setExtractedUnits] = useState({});
  const [ocrScanned, setOcrScanned] = useState(false);
  const [ocrStatus, setOcrStatus] = useState(null);
  const [ocrProgress, setOcrProgress] = useState(null);
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [lateriteTipsVisible, setLateriteTipsVisible] = useState(false);

  /* Photo upload: Dynamic Image Preprocessing + Real OCR Extraction (Zero-Mock Policy) */
  const handleFile = useCallback(async (file) => {
    setImageFile(file);
    setImagePreview((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return URL.createObjectURL(file);
    });
    setOcrLoading(true);
    setOcrScanned(false);
    setOcrStatus(null);
    setOcrProgress({ stage: 'preprocessing', progress: 0.05, message: 'Preprocessing Soil Health Card image...' });

    try {
      const result = await extractSoilCardFromImage(file, {
        onProgress: (p) => setOcrProgress(p),
      });

      // Strictly populate only values dynamically detected from the uploaded image.
      // Any absent or unreadable parameter remains '' (empty) for manual review.
      const nextForm = { ...EMPTY_FORM };
      let detectedParamCount = 0;
      for (const field of ALL_SOIL_FIELDS) {
        const rawVal = result.rawValues?.[field.id];
        const numVal = result.values?.[field.id];
        if (rawVal != null && rawVal !== '') {
          nextForm[field.id] = String(rawVal);
          detectedParamCount += 1;
        } else if (numVal != null && Number.isFinite(Number(numVal))) {
          nextForm[field.id] = String(numVal);
          detectedParamCount += 1;
        } else {
          nextForm[field.id] = '';
        }
      }

      const nextMeta = { ...EMPTY_METADATA };
      let detectedMetaCount = 0;
      for (const metaField of METADATA_FIELDS) {
        const val = result.metadata?.[metaField.id];
        if (val != null && String(val).trim() !== '') {
          nextMeta[metaField.id] = String(val).trim();
          detectedMetaCount += 1;
        } else {
          nextMeta[metaField.id] = '';
        }
      }

      setForm(nextForm);
      setMetadataForm(nextMeta);
      setExtractedRatings(result.ratings || {});
      setExtractedUnits(result.units || {});
      setOcrScanned(true);
      setOcrStatus({
        extractedCount: detectedParamCount + detectedMetaCount,
        summary:
          detectedParamCount + detectedMetaCount > 0
            ? `Extracted ${detectedParamCount}/12 soil parameters & ${detectedMetaCount} card details`
            : 'Could not detect readable SHC values — please review & enter manually',
      });
    } catch (err) {
      console.error('Soil Health Card OCR failed:', err);
      setForm(EMPTY_FORM);
      setMetadataForm(EMPTY_METADATA);
      setExtractedRatings({});
      setExtractedUnits({});
      setOcrScanned(true);
      setOcrStatus({
        extractedCount: 0,
        summary: 'OCR scan could not read card — please enter values manually',
      });
    } finally {
      setOcrLoading(false);
      setOcrProgress(null);
    }
  }, []);

  const clearImage = () => {
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    setImageFile(null);
    setImagePreview(null);
    setForm(EMPTY_FORM);
    setMetadataForm(EMPTY_METADATA);
    setExtractedRatings({});
    setExtractedUnits({});
    setOcrScanned(false);
    setOcrStatus(null);
    setOcrProgress(null);
  };

  const updateField = useCallback((id, val) => {
    setForm((f) => ({ ...f, [id]: val }));
  }, []);

  const updateMetadataField = useCallback((id, val) => {
    setMetadataForm((m) => ({ ...m, [id]: val }));
  }, []);

  const toggleAgronomicTips = () => {
    setLateriteTipsVisible((v) => !v);
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
    const enteredReadings = ALL_SOIL_FIELDS.map((field) => {
      const raw = form[field.id];
      if (raw === '' || raw == null) return null;
      const num = Number(raw);
      if (!Number.isFinite(num)) return null;
      const label = field.labelKey ? t(field.labelKey) : field.label;
      if (field.unitSpeakKey === 'percent') {
        return `${label}: ${formatSpeakablePercent(num, speechLocale, 2)}`;
      }
      if (field.unitSpeakKey) {
        return `${label}: ${formatSpeakableNumber(num, speechLocale, 2)} ${t(field.unitSpeakKey)}`;
      }
      return `${label}: ${formatSpeakableNumber(num, speechLocale, 2)} ${field.unit || ''}`.trim();
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

      const parseNum = (val) => {
        if (val === '' || val == null) return null;
        const n = Number.parseFloat(val);
        return Number.isFinite(n) ? n : null;
      };

      await db.soilRecords.add({
        plotId,
        ph: parseNum(form.ph),
        ec: parseNum(form.ec),
        organicCarbon: parseNum(form.organicCarbon),
        nitrogen: parseNum(form.nitrogen),
        phosphorus: parseNum(form.phosphorus),
        potassium: parseNum(form.potassium),
        sulphur: parseNum(form.sulphur),
        zinc: parseNum(form.zinc),
        boron: parseNum(form.boron),
        iron: parseNum(form.iron),
        manganese: parseNum(form.manganese),
        copper: parseNum(form.copper),
        ratings: extractedRatings,
        units: extractedUnits,
        cardNumber: metadataForm.cardNumber || null,
        farmerName: metadataForm.farmerName || null,
        soilType: metadataForm.soilType || null,
        state: metadataForm.state || null,
        district: metadataForm.district || null,
        surveyNumber: metadataForm.surveyNumber || null,
        farmSize: metadataForm.farmSize || null,
        hasPhoto: Boolean(imageFile),
        timestamp: new Date().toISOString(),
      });

      if (selectedPlot?.id) {
        const plotUpdates = {};
        if (metadataForm.soilType && !selectedPlot.soilType) plotUpdates.soilType = metadataForm.soilType;
        if (metadataForm.district && !selectedPlot.district) plotUpdates.district = metadataForm.district;
        if (metadataForm.state && !selectedPlot.state) plotUpdates.state = metadataForm.state;
        if (metadataForm.surveyNumber && !selectedPlot.surveyNumber) plotUpdates.surveyNumber = metadataForm.surveyNumber;
        if (Object.keys(plotUpdates).length > 0) {
          await db.plots.update(selectedPlot.id, plotUpdates);
        }
      }

      const USE_MOCKS = String(import.meta.env?.VITE_USE_MOCKS ?? 'true').toLowerCase() === 'true';
      if (!USE_MOCKS && selectedPlot?.serverId && typeof navigator !== 'undefined' && navigator.onLine) {
        try {
          await apiRequest(`/plots/${selectedPlot.serverId}/soil-tests`, {
            method: 'POST',
            body: {
              n_val: parseNum(form.nitrogen),
              p_val: parseNum(form.phosphorus),
              k_val: parseNum(form.potassium),
              ph: parseNum(form.ph),
              organic_matter: parseNum(form.organicCarbon),
              soil_type: metadataForm.soilType || null,
              source_reference: metadataForm.cardNumber || null,
              nutrient_unit: 'kg/ha',
              organic_matter_unit: 'percent',
              provenance: imageFile ? 'imported' : 'manual',
            },
          });
        } catch (apiErr) {
          console.warn('Backend soil test sync deferred:', apiErr);
        }
      }

      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      setForm(EMPTY_FORM);
      setMetadataForm(EMPTY_METADATA);
      setExtractedRatings({});
      setExtractedUnits({});
      setOcrScanned(false);
      setOcrStatus(null);
      clearImage();
      setLateriteTipsVisible(false);
    } catch (err) {
      console.error('Field Shift: soil record save failed', err);
    } finally {
      setSaving(false);
    }
  };

  const metadataSectionTitle = 'Soil Health Card & Farmer Details';
  const metadataSectionSubtitle = 'Dynamically extracted from card header & farmer details table';
  const micronutrientsSectionTitle = 'Secondary & Micronutrients (Rows 7–12)';
  const micronutrientsBadgeText = 'S · Zn · B · Fe · Mn · Cu';

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 pb-28">
      {/* ── Page header ── */}
      <div className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700/80 px-4 py-5 sm:px-6">
        <div className="mx-auto max-w-7xl flex items-center justify-between gap-3">
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

      {/* ── Main content: Side-by-side layout (forms to the left, 3D animation to the right) ── */}
      <div className="mx-auto max-w-7xl px-4 pt-6 sm:px-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          {/* ── Left Column: Form & OCR (rest to the left) ── */}
          <div className="order-2 lg:order-1 lg:col-span-7 space-y-6">

        {/* ── Agronomic tips banner (purely informational; never injects mock data) ── */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="overflow-hidden rounded-2xl border border-amber-200 bg-gradient-to-br from-amber-50 to-orange-50 dark:border-amber-700 dark:from-amber-500/10 dark:to-orange-500/10"
        >
          <button
            type="button"
            onClick={toggleAgronomicTips}
            className="flex w-full items-center gap-4 px-5 py-4 text-left transition hover:bg-amber-100/60 focus:outline-none focus:ring-2 focus:ring-amber-400 focus:ring-inset dark:hover:bg-amber-500/20"
          >
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 shadow-sm shadow-amber-500/20">
              <Sparkles size={20} className="text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-black text-slate-800 dark:text-slate-200">
                {t('soil.lateriteActionsHeading')}
              </p>
              <p className="mt-0.5 text-xs text-slate-600 dark:text-slate-400 leading-5">
                {t('soil.populateLateriteDesc')}
              </p>
            </div>
            <ChevronRight
              size={18}
              className={`shrink-0 text-amber-500 transition-transform ${lateriteTipsVisible ? 'rotate-90' : ''}`}
            />
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
            ocrProgress={ocrProgress}
            ocrStatus={ocrStatus}
            t={t}
          />
        </motion.div>

        {/* ── Card & Farmer Metadata Form ── */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.12 }}
          className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 shadow-sm"
        >
          <div className="mb-4 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <FileText size={18} className="text-violet-500 shrink-0" />
              <div>
                <h2 className="text-base font-black text-slate-900 dark:text-slate-100">
                  {metadataSectionTitle}
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {metadataSectionSubtitle}
                </p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
            {METADATA_FIELDS.map((meta) => {
              const val = metadataForm[meta.id] || '';
              const missingAfterScan = ocrScanned && !val;
              return (
                <div key={meta.id} className={meta.id === 'cardNumber' ? 'sm:col-span-2' : ''}>
                  <label
                    htmlFor={`shc-meta-${meta.id}`}
                    className="mb-1 block text-xs font-bold text-slate-600 dark:text-slate-400"
                  >
                    {meta.label}
                  </label>
                  <input
                    id={`shc-meta-${meta.id}`}
                    type="text"
                    value={val}
                    placeholder={meta.placeholder}
                    onChange={(e) => updateMetadataField(meta.id, e.target.value)}
                    className={`w-full rounded-xl border px-3.5 py-2.5 text-sm font-semibold text-slate-900 dark:text-slate-50 outline-none transition focus:bg-white dark:focus:bg-slate-900 focus:border-violet-500 dark:focus:border-violet-400 focus:ring-2 focus:ring-violet-500/30 ${
                      missingAfterScan
                        ? 'border-amber-300 dark:border-amber-600/80 bg-amber-50/30 dark:bg-amber-500/5'
                        : 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950'
                    }`}
                  />
                </div>
              );
            })}
          </div>
        </motion.div>

        {/* ── Soil Parameters Entry Form (All 12 SHC Parameters) ── */}
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
                  {t('weather.selectPlot')}
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
              {PRIMARY_NUTRIENT_FIELDS.map((field) => (
                <NutrientInput
                  key={field.id}
                  field={field}
                  value={form[field.id]}
                  unitOverride={extractedUnits[field.id]}
                  rating={extractedRatings[field.id]}
                  needsManualReview={ocrScanned && !form[field.id]}
                  onChange={updateField}
                  t={t}
                />
              ))}
            </div>

            <div className="mt-6 mb-4 flex items-center justify-between border-t border-slate-100 dark:border-slate-800 pt-5">
              <div>
                <h3 className="text-sm font-black text-slate-900 dark:text-slate-100">
                  {micronutrientsSectionTitle}
                </h3>
              </div>
              <span className="rounded-full border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                {micronutrientsBadgeText}
              </span>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {MICRONUTRIENT_FIELDS.map((field) => (
                <NutrientInput
                  key={field.id}
                  field={field}
                  value={form[field.id]}
                  unitOverride={extractedUnits[field.id]}
                  rating={extractedRatings[field.id]}
                  needsManualReview={ocrScanned && !form[field.id]}
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

          {/* ── Right Column: 3D Animation (animation to the right) ── */}
          <div className="order-1 lg:order-2 lg:col-span-5 lg:sticky lg:top-6 space-y-6">
            <SoilSensor3D />
          </div>

        </div>
      </div>

      <SaveToast show={saved} t={t} />
    </div>
  );
}
