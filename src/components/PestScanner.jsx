import { useCallback, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AlertTriangle,
  Bug,
  Camera,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Droplets,
  FlaskConical,
  Leaf,
  Loader2,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  Sprout,
  X,
  Zap,
} from 'lucide-react';
import CropImage from './CropImage';
import ListenButton from './ui/ListenButton';
import { useTranslation } from '../context/LanguageContext';
import { getCrop, getCropDisplayName } from '../data/crops';
import {
  formatSpeakableNumber,
  formatSpeakablePercent,
} from '../utils/speechText';

/* ─── Mock disease database (structured keys, translated at render time) ─── */
const DISEASE_RESULTS = [
  {
    id: 'leaf-blight',
    confidence: 94,
    cropId: 'paddy',
    severityColor: 'amber',
    nameKey: 'pest.diseases.leafBlight.name',
    severityKey: 'pest.severity.moderate',
    descriptionKey: 'pest.diseases.leafBlight.description',
    immediateKeys: [
      'pest.diseases.leafBlight.immediate1',
      'pest.diseases.leafBlight.immediate2',
      'pest.diseases.leafBlight.immediate3',
    ],
    organic: {
      labelKey: 'pest.organicTreatment',
      itemKeys: [
        'pest.diseases.leafBlight.organic1',
        'pest.diseases.leafBlight.organic2',
        'pest.diseases.leafBlight.organic3',
      ],
      icon: Leaf,
      color: 'emerald',
    },
    chemical: {
      labelKey: 'pest.chemicalTreatment',
      itemKeys: [
        'pest.diseases.leafBlight.chemical1',
        'pest.diseases.leafBlight.chemical2',
        'pest.diseases.leafBlight.chemical3',
      ],
      icon: FlaskConical,
      color: 'blue',
    },
  },
  {
    id: 'powdery-mildew',
    confidence: 88,
    cropId: 'cashew',
    severityColor: 'red',
    nameKey: 'pest.diseases.powderyMildew.name',
    severityKey: 'pest.severity.high',
    descriptionKey: 'pest.diseases.powderyMildew.description',
    immediateKeys: [
      'pest.diseases.powderyMildew.immediate1',
      'pest.diseases.powderyMildew.immediate2',
      'pest.diseases.powderyMildew.immediate3',
    ],
    organic: {
      labelKey: 'pest.organicTreatment',
      itemKeys: [
        'pest.diseases.powderyMildew.organic1',
        'pest.diseases.powderyMildew.organic2',
        'pest.diseases.powderyMildew.organic3',
      ],
      icon: Leaf,
      color: 'emerald',
    },
    chemical: {
      labelKey: 'pest.chemicalTreatment',
      itemKeys: [
        'pest.diseases.powderyMildew.chemical1',
        'pest.diseases.powderyMildew.chemical2',
        'pest.diseases.powderyMildew.chemical3',
      ],
      icon: FlaskConical,
      color: 'blue',
    },
  },
];

/* ─── Severity badge ─────────────────────────────────────────── */
const SEVERITY_STYLES = {
  amber: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-700',
  red: 'bg-red-50 text-red-600 border-red-200 dark:bg-red-500/10 dark:text-red-300 dark:border-red-700',
  green: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-700',
};

function buildResultSpeechParts(result, t, speechLocale) {
  if (!result) return [];
  const cropName = getCropDisplayName(result.cropId, t);
  const diseaseName = t(result.nameKey);
  const severity = t(result.severityKey);
  const confidence = formatSpeakablePercent(result.confidence, speechLocale, 0);

  return [
    t('pest.resultSpeechIntro', {
      disease: diseaseName,
      crop: cropName,
      severity,
      confidence,
    }),
    t(result.descriptionKey),
    t('pest.immediateActions'),
    ...result.immediateKeys.map((key) => t(key)),
    t(result.organic.labelKey),
    ...result.organic.itemKeys.map((key) => t(key)),
    t(result.chemical.labelKey),
    ...result.chemical.itemKeys.map((key) => t(key)),
    t('pest.disclaimer'),
  ];
}

/* ─── Scanning overlay animation ─────────────────────────────── */
function ScanOverlay({ onDone, t }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="absolute inset-0 rounded-2xl overflow-hidden bg-slate-950/60 backdrop-blur-[2px]"
    >
      {[
        'top-3 left-3 border-t-2 border-l-2',
        'top-3 right-3 border-t-2 border-r-2',
        'bottom-3 left-3 border-b-2 border-l-2',
        'bottom-3 right-3 border-b-2 border-r-2',
      ].map((cls, i) => (
        <div key={i} className={`absolute h-6 w-6 ${cls} border-emerald-400`} />
      ))}

      <motion.div
        initial={{ top: '8%' }}
        animate={{ top: ['8%', '88%', '8%'] }}
        transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
        onAnimationComplete={onDone}
        className="absolute left-0 right-0 h-0.5"
        style={{ background: 'linear-gradient(90deg, transparent, #10b981, #34d399, #10b981, transparent)' }}
      >
        <div
          className="absolute inset-x-0 -top-3 h-6 opacity-30"
          style={{ background: 'linear-gradient(180deg, transparent, #10b981, transparent)' }}
        />
      </motion.div>

      <div className="absolute bottom-4 left-0 right-0 flex justify-center">
        <div className="flex items-center gap-2 rounded-xl bg-slate-900/80 px-4 py-2 text-xs font-bold text-emerald-300 backdrop-blur-sm">
          <motion.span
            animate={{ opacity: [1, 0.3, 1] }}
            transition={{ duration: 0.7, repeat: Infinity }}
            className="h-2 w-2 rounded-full bg-emerald-400"
          />
          {t('pest.analysingOverlay')}
        </div>
      </div>
    </motion.div>
  );
}

/* ─── Treatment section ──────────────────────────────────────── */
function TreatmentSection({ data, t }) {
  const [open, setOpen] = useState(false);
  const colorMap = {
    emerald: { bg: 'bg-emerald-50 dark:bg-emerald-500/10', border: 'border-emerald-200 dark:border-emerald-700', icon: 'text-emerald-600 dark:text-emerald-300', title: 'text-emerald-800 dark:text-emerald-200', bullet: 'bg-emerald-400' },
    blue: { bg: 'bg-blue-50 dark:bg-blue-500/10', border: 'border-blue-200 dark:border-blue-700', icon: 'text-blue-600 dark:text-blue-300', title: 'text-blue-800 dark:text-blue-200', bullet: 'bg-blue-400' },
  };
  const c = colorMap[data.color];

  return (
    <div className={`rounded-2xl border ${c.border} ${c.bg} overflow-hidden`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 px-4 py-3.5 text-left focus:outline-none"
      >
        <data.icon size={17} className={c.icon} />
        <span className={`flex-1 text-sm font-bold ${c.title}`}>{t(data.labelKey)}</span>
        {open ? <ChevronUp size={15} className={c.icon} /> : <ChevronDown size={15} className={c.icon} />}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <ul className="space-y-2 border-t border-current/10 px-4 py-3">
              {data.itemKeys.map((itemKey) => (
                <li key={itemKey} className="flex items-start gap-2.5 text-xs leading-5 text-slate-700 dark:text-slate-300">
                  <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${c.bullet}`} />
                  {t(itemKey)}
                </li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ─── Results Card ───────────────────────────────────────────── */
function ResultsCard({ result, speechParts, t, speechLocale }) {
  const cropName = getCropDisplayName(result.cropId, t);

  return (
    <motion.div
      initial={{ opacity: 0, y: 40 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 28 }}
      className="space-y-4 rounded-3xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 shadow-lg"
    >
      {/* Header */}
      <div className="flex items-start gap-4">
        <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-red-500 to-rose-600 shadow-md shadow-red-500/25">
          <ShieldAlert size={26} className="text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-black text-slate-900 dark:text-slate-100">
                {t(result.nameKey)}
              </h2>
              <span className={`rounded-full border px-2 py-0.5 text-xs font-bold ${SEVERITY_STYLES[result.severityColor]}`}>
                {t('pest.severityBadge', { severity: t(result.severityKey) })}
              </span>
            </div>

            <ListenButton
              id={`pest-result-${result.id}`}
              variant="rose"
              text={speechParts}
            />
          </div>

          <div className="mt-2 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
            <CropImage cropId={result.cropId} size="sm" showName={false} />
            <span>
              {t('pest.detectedOn')}{' '}
              <strong className="text-slate-700 dark:text-slate-300">{cropName}</strong>
            </span>
          </div>
          <div className="mt-2 flex items-center gap-1.5">
            <div className="h-2 flex-1 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${result.confidence}%` }}
                transition={{ duration: 0.8, delay: 0.3, ease: 'easeOut' }}
                className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-500"
              />
            </div>
            <span className="text-xs font-bold text-emerald-700 dark:text-emerald-300">
              {t('pest.confidenceLabel', {
                pct: formatSpeakableNumber(result.confidence, speechLocale, 0),
              })}
            </span>
          </div>
        </div>
      </div>

      {/* Description */}
      <p className="rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-4 py-3 text-sm leading-6 text-slate-600 dark:text-slate-400">
        {t(result.descriptionKey)}
      </p>

      {/* Immediate actions */}
      <div>
        <div className="mb-3 flex items-center gap-2">
          <Zap size={15} className="text-amber-500" />
          <p className="text-sm font-black text-slate-800 dark:text-slate-200">
            {t('pest.immediateActions')}
          </p>
        </div>
        <ul className="space-y-2">
          {result.immediateKeys.map((actionKey, i) => (
            <motion.li
              key={actionKey}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2 + i * 0.07 }}
              className="flex items-start gap-3 rounded-xl border border-amber-100 bg-amber-50 px-3 py-2.5 dark:border-amber-800 dark:bg-amber-500/10"
            >
              <AlertTriangle size={14} className="mt-0.5 shrink-0 text-amber-500" />
              <p className="text-xs font-medium leading-5 text-amber-900 dark:text-amber-100">
                {t(actionKey)}
              </p>
            </motion.li>
          ))}
        </ul>
      </div>

      {/* Treatment accordions */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Droplets size={15} className="text-blue-500" />
          <p className="text-sm font-black text-slate-800 dark:text-slate-200">
            {t('pest.treatmentOptions')}
          </p>
        </div>
        <TreatmentSection data={result.organic} t={t} />
        <TreatmentSection data={result.chemical} t={t} />
      </div>

      <p className="text-center text-[11px] text-slate-400">
        {t('pest.disclaimer')}
      </p>
    </motion.div>
  );
}

/* ─── PestScanner ────────────────────────────────────────────── */
export default function PestScanner() {
  const { t, languageInfo } = useTranslation();
  const speechLocale = languageInfo.speechLang;

  const fileRef = useRef(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [isObjectUrl, setIsObjectUrl] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [result, setResult] = useState(null);
  const [scanCount, setScanCount] = useState(0);

  const handleFile = useCallback(async (file) => {
    if (!file?.type.startsWith('image/')) return;
    const url = URL.createObjectURL(file);
    setImagePreview(url);
    setIsObjectUrl(true);
    setResult(null);
    setScanning(true);
    await new Promise((r) => setTimeout(r, 2200));
    setScanning(false);
    setResult(DISEASE_RESULTS[scanCount % DISEASE_RESULTS.length]);
    setScanCount((c) => c + 1);
  }, [scanCount]);

  const handleSampleScan = useCallback(async () => {
    const sampleResult = DISEASE_RESULTS[scanCount % DISEASE_RESULTS.length];
    const sampleCrop = getCrop(sampleResult.cropId);
    setImagePreview(sampleCrop?.card || '/crops/paddy-card.webp');
    setIsObjectUrl(false);
    setResult(null);
    setScanning(true);
    await new Promise((r) => setTimeout(r, 950));
    setScanning(false);
    setResult(sampleResult);
    setScanCount((c) => c + 1);
  }, [scanCount]);

  const reset = () => {
    if (imagePreview && isObjectUrl) URL.revokeObjectURL(imagePreview);
    setImagePreview(null);
    setIsObjectUrl(false);
    setResult(null);
    setScanning(false);
  };

  const resultSpeechParts = useMemo(
    () => buildResultSpeechParts(result, t, speechLocale),
    [result, speechLocale, t],
  );

  const headerSpeechParts = useMemo(() => {
    if (result && !scanning) return resultSpeechParts;
    return [
      t('pest.title'),
      t('pest.overviewSpeech'),
      t('pest.howStep1'),
      t('pest.howStep2'),
      t('pest.howStep3'),
    ];
  }, [result, resultSpeechParts, scanning, t]);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 pb-28">
      {/* ── Header ── */}
      <div className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700/80 px-4 py-5 sm:px-6">
        <div className="mx-auto max-w-2xl flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-rose-500 to-pink-600 shadow-md shadow-rose-500/25">
              <Bug size={22} className="text-white" />
            </div>
            <div className="min-w-0">
              <h1 className="text-xl font-black tracking-tight text-slate-900 dark:text-slate-100">
                {t('pest.title')}
              </h1>
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                {t('pest.subtitle')}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <ListenButton
              id="pest-header-listen"
              variant="rose"
              text={headerSpeechParts}
            />
            {(imagePreview || result) && (
              <motion.button
                type="button"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                onClick={reset}
                aria-label={t('pest.scanAnotherAria')}
                className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 transition hover:bg-slate-200 focus:outline-none focus:ring-2 focus:ring-rose-500"
              >
                <RefreshCw size={17} />
              </motion.button>
            )}
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-2xl space-y-5 px-4 pt-6 sm:px-6">

        {/* ── Camera zone ── */}
        <AnimatePresence mode="wait">
          {!imagePreview ? (
            <div key="dropzone-wrap" className="space-y-3">
              <motion.button
                type="button"
                onClick={() => fileRef.current?.click()}
                initial={{ opacity: 0, scale: 0.97 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.97 }}
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.99 }}
                className="flex w-full flex-col items-center justify-center gap-5 rounded-3xl border-2 border-dashed border-slate-300 bg-white dark:bg-slate-900 py-14 transition-all hover:border-rose-400 hover:bg-rose-50/40 dark:hover:bg-rose-500/5 focus:outline-none focus:ring-4 focus:ring-rose-500/20"
              >
                <motion.div
                  animate={{ scale: [1, 1.08, 1], opacity: [0.9, 1, 0.9] }}
                  transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
                  className="flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-rose-400 to-pink-600 shadow-xl shadow-rose-500/30"
                >
                  <Camera size={36} className="text-white" />
                </motion.div>
                <div className="text-center px-4">
                  <p className="text-lg font-black text-slate-800 dark:text-slate-200">
                    {t('pest.takeOrUploadTitle')}
                  </p>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                    {t('pest.takeOrUploadSubtitle')}
                  </p>
                  <div className="mt-3 flex items-center justify-center gap-4 text-xs text-slate-400">
                    <span className="flex items-center gap-1"><Sprout size={12} /> {t('pest.partLeaves')}</span>
                    <span className="flex items-center gap-1"><Droplets size={12} /> {t('pest.partStems')}</span>
                    <span className="flex items-center gap-1"><Bug size={12} /> {t('pest.partInsects')}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2 rounded-full border border-rose-200 bg-rose-50 px-4 py-2 text-xs font-bold text-rose-600 dark:border-rose-800 dark:bg-rose-500/10 dark:text-rose-300">
                  <Camera size={13} /> {t('pest.tapToOpenCamera')}
                </div>
              </motion.button>

              <div className="flex justify-center">
                <button
                  type="button"
                  onClick={handleSampleScan}
                  className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-700 shadow-xs transition hover:border-rose-300 hover:bg-rose-50 hover:text-rose-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-rose-700 dark:hover:bg-rose-500/10"
                >
                  <Sparkles size={13} className="text-rose-500" />
                  {t('pest.trySampleScan')}
                </button>
              </div>
            </div>
          ) : (
            <motion.div
              key="preview"
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              className="relative overflow-hidden rounded-3xl border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 shadow-lg"
            >
              <img
                src={imagePreview}
                alt={t('pest.cropPhotoAlt')}
                className="h-64 w-full object-cover sm:h-80"
              />

              <AnimatePresence>
                {scanning && <ScanOverlay onDone={() => {}} t={t} />}
              </AnimatePresence>

              {!scanning && result && (
                <div className="absolute right-3 top-3 flex items-center gap-1.5 rounded-xl bg-emerald-600/90 px-3 py-1.5 text-xs font-bold text-white backdrop-blur-sm">
                  <CheckCircle2 size={13} /> {t('pest.analysisComplete')}
                </div>
              )}

              {!scanning && (
                <button
                  type="button"
                  onClick={reset}
                  aria-label={t('pest.removePhotoAria')}
                  className="absolute left-3 top-3 flex h-8 w-8 items-center justify-center rounded-xl bg-slate-950/60 text-white backdrop-blur-sm transition hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-white"
                >
                  <X size={15} />
                </button>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Scanning status ── */}
        <AnimatePresence>
          {scanning && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="flex items-center gap-4 rounded-2xl border border-blue-100 bg-blue-50 px-5 py-4 dark:border-blue-800 dark:bg-blue-500/10"
            >
              <Loader2 size={22} className="shrink-0 animate-spin text-blue-600" />
              <div>
                <p className="text-sm font-bold text-blue-800 dark:text-blue-200">
                  {t('pest.scanningStatusTitle')}
                </p>
                <p className="text-xs text-blue-600 dark:text-blue-300">
                  {t('pest.scanningStatusSubtitle')}
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Results ── */}
        <AnimatePresence>
          {result && !scanning && (
            <ResultsCard
              result={result}
              speechParts={resultSpeechParts}
              t={t}
              speechLocale={speechLocale}
            />
          )}
        </AnimatePresence>

        {/* ── How-it-works hint (only when idle) ── */}
        {!imagePreview && !result && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 shadow-sm"
          >
            <p className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-400">
              {t('pest.howItWorksTitle')}
            </p>
            <div className="space-y-3">
              {[
                { icon: Camera, labelKey: 'pest.howStep1' },
                { icon: Bug, labelKey: 'pest.howStep2' },
                { icon: CheckCircle2, labelKey: 'pest.howStep3' },
              ].map(({ icon: Icon, labelKey }) => (
                <div key={labelKey} className="flex items-center gap-3">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-rose-50 text-rose-500 dark:bg-rose-500/10 dark:text-rose-300">
                    <Icon size={16} />
                  </span>
                  <p className="text-sm text-slate-600 dark:text-slate-400">{t(labelKey)}</p>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </div>

      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="sr-only"
        onChange={(e) => handleFile(e.target.files?.[0])}
        aria-label={t('pest.takeOrUploadTitle')}
      />
    </div>
  );
}
