import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  TrendingUp,
  CloudSun,
  Leaf,
  Package,
  X,
} from 'lucide-react';

import { useTranslation } from '../context/LanguageContext';
import { getCropById, getCropDisplayName } from '../data/crops';
import ListenButton from './ui/ListenButton';
import {
  buildSpeechText,
  formatSpeakableCurrency,
  formatSpeakableNumber,
  formatSpeakablePercent,
  formatSpeakableWeightKg,
} from '../utils/speechText';

const ICON_MAP = {
  TrendingUp,
  CloudSun,
  Leaf,
  Package,
};

const SEVERITY_STYLES = {
  success: {
    border: 'border-emerald-400/40',
    iconBg: 'bg-emerald-500/20',
    iconColor: 'text-emerald-300',
    dot: 'bg-emerald-400',
    glow: 'shadow-emerald-900/40',
  },
  info: {
    border: 'border-sky-400/40',
    iconBg: 'bg-sky-500/20',
    iconColor: 'text-sky-300',
    dot: 'bg-sky-400',
    glow: 'shadow-sky-900/40',
  },
  warning: {
    border: 'border-amber-400/40',
    iconBg: 'bg-amber-500/20',
    iconColor: 'text-amber-300',
    dot: 'bg-amber-400',
    glow: 'shadow-amber-900/40',
  },
};

const SESSION_KEY = 'fieldshift_startupNotifShown';

function hasShownThisSession() {
  try {
    return sessionStorage.getItem(SESSION_KEY) === 'true';
  } catch {
    return false;
  }
}

function markShownThisSession() {
  try {
    sessionStorage.setItem(SESSION_KEY, 'true');
  } catch {
    /* no-op */
  }
}

function formatDisplayCurrency(amount, locale) {
  const num = Number(amount);
  if (!Number.isFinite(num)) return String(amount ?? '');
  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(num);
  } catch {
    return `₹${num}`;
  }
}

function NotificationToast({ notif, onDismiss, onPinnedChange }) {
  const { t, languageInfo } = useTranslation();
  const locale = languageInfo.speechLang;
  const IconComponent = ICON_MAP[notif.icon] || Leaf;
  const styles = SEVERITY_STYLES[notif.severity] || SEVERITY_STYLES.info;

  const { typeLabel, titleText, bodyText, speechText } = useMemo(() => {
    const rawParams = notif.params || {};
    const cropName = rawParams.cropId
      ? getCropDisplayName(getCropById(rawParams.cropId), t)
      : '';
    const seasonName = rawParams.seasonKey ? t(rawParams.seasonKey) : '';
    const unitText = rawParams.unitKey ? t(rawParams.unitKey) : '';

    const displayParams = {
      ...rawParams,
      crop: cropName,
      season: seasonName,
      unit: unitText,
      price: rawParams.price != null ? formatDisplayCurrency(rawParams.price, locale) : '',
      diff: rawParams.diff != null ? formatDisplayCurrency(rawParams.diff, locale) : '',
      pct: rawParams.pct != null ? formatSpeakableNumber(rawParams.pct, locale) : '',
      days: rawParams.days != null ? formatSpeakableNumber(rawParams.days, locale) : '',
      moisture: rawParams.moisture != null ? formatSpeakableNumber(rawParams.moisture, locale) : '',
      bagKg: rawParams.bagKg != null ? formatSpeakableNumber(rawParams.bagKg, locale) : '',
    };

    const spokenParams = {
      ...displayParams,
      price: rawParams.price != null ? formatSpeakableCurrency(rawParams.price, locale) : '',
      diff: rawParams.diff != null ? formatSpeakableCurrency(rawParams.diff, locale) : '',
      pctFormatted: rawParams.pct != null ? formatSpeakablePercent(rawParams.pct, locale) : '',
      moistureFormatted: rawParams.moisture != null ? formatSpeakablePercent(rawParams.moisture, locale) : '',
      bagWeightFormatted: rawParams.bagKg != null ? formatSpeakableWeightKg(rawParams.bagKg, locale) : '',
    };

    const resolvedType = notif.typeKey ? t(notif.typeKey) : notif.type;
    const resolvedTitle = notif.titleKey ? t(notif.titleKey, displayParams) : notif.title;
    const resolvedBody = notif.bodyKey ? t(notif.bodyKey, displayParams) : notif.body;

    const spokenTitle = notif.titleKey ? t(notif.titleKey, spokenParams) : notif.title;
    const spokenBody = notif.bodyKey ? t(notif.bodyKey, spokenParams) : notif.body;

    return {
      typeLabel: resolvedType,
      titleText: resolvedTitle,
      bodyText: resolvedBody,
      speechText: buildSpeechText([resolvedType, spokenTitle, spokenBody]),
    };
  }, [locale, notif, t]);

  const handleSpeakingChange = useCallback(
    (speaking) => {
      onPinnedChange(notif.id, speaking);
    },
    [notif.id, onPinnedChange],
  );

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 60, scale: 0.92 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 60, scale: 0.88, transition: { duration: 0.22 } }}
      transition={{ type: 'spring', stiffness: 360, damping: 30 }}
      className={`relative flex w-full max-w-sm items-start gap-3 overflow-hidden rounded-2xl border ${styles.border} bg-slate-900/85 px-4 py-3.5 shadow-xl ${styles.glow} backdrop-blur-xl`}
      role="alert"
      aria-live="polite"
    >
      <motion.div
        className="pointer-events-none absolute inset-0 rounded-2xl"
        animate={{ opacity: [0.4, 0.7, 0.4] }}
        transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
        style={{
          background:
            'linear-gradient(135deg, rgba(16,185,129,0.08) 0%, rgba(14,165,233,0.05) 50%, rgba(245,158,11,0.04) 100%)',
        }}
      />

      <div className={`mt-0.5 shrink-0 rounded-xl p-2 ${styles.iconBg}`}>
        <IconComponent size={16} className={styles.iconColor} />
      </div>

      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5">
            <span className={`h-1.5 w-1.5 shrink-0 animate-pulse rounded-full ${styles.dot}`} />
            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-300">
              {typeLabel}
            </span>
          </div>
          <ListenButton
            text={speechText}
            variant="dark"
            size="xs"
            iconOnly
            onSpeakingChange={handleSpeakingChange}
          />
        </div>

        <p className="truncate text-sm font-bold leading-snug tracking-tight text-white">
          {titleText}
        </p>

        <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-slate-300">
          {bodyText}
        </p>
      </div>

      <button
        type="button"
        onClick={() => onDismiss(notif.id)}
        aria-label={`${t('voice.dismiss')}: ${titleText}`}
        className="mt-0.5 shrink-0 rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-700/60 hover:text-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-400"
      >
        <X size={13} />
      </button>
    </motion.div>
  );
}

export default function StartupNotifications() {
  const { t } = useTranslation();
  const [queue] = useState([]);
  const [visible, setVisible] = useState([]);
  const pinnedIdsRef = useRef(new Set());

  const dismiss = useCallback((id) => {
    pinnedIdsRef.current.delete(id);
    setVisible((prev) => prev.filter((v) => v !== id));
  }, []);

  const handlePinnedChange = useCallback((id, pinned) => {
    if (pinned) {
      pinnedIdsRef.current.add(id);
    } else {
      pinnedIdsRef.current.delete(id);
    }
  }, []);

  useEffect(() => {
    if (queue.length === 0) return undefined;
    markShownThisSession();

    const showTimers = queue.map((notif) =>
      setTimeout(() => {
        setVisible((prev) => (prev.includes(notif.id) ? prev : [...prev, notif.id]));
      }, notif.delayMs),
    );

    // Give farmers 6.5 s to read or tap Listen; keep toast open if currently speaking
    const hideTimers = queue.map((notif) =>
      setTimeout(() => {
        if (pinnedIdsRef.current.has(notif.id)) return;
        setVisible((prev) => prev.filter((v) => v !== notif.id));
      }, notif.delayMs + 6500),
    );

    return () => {
      [...showTimers, ...hideTimers].forEach(clearTimeout);
    };
  }, [queue]);

  const activeToasts = queue.filter((n) => visible.includes(n.id));

  return (
    <div
      className="pointer-events-none fixed end-3 top-20 z-50 flex flex-col items-end gap-2.5 sm:end-5"
      aria-label={t('notifications.ariaRegion')}
    >
      <AnimatePresence mode="popLayout">
        {activeToasts.map((notif) => (
          <div key={notif.id} className="pointer-events-auto w-full">
            <NotificationToast
              notif={notif}
              onDismiss={dismiss}
              onPinnedChange={handlePinnedChange}
            />
          </div>
        ))}
      </AnimatePresence>
    </div>
  );
}
