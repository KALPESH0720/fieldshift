import { useEffect, useMemo } from 'react';
import { Square, Volume2, VolumeX } from 'lucide-react';
import useVoice from '../../hooks/useVoice';
import { useTranslation } from '../../context/LanguageContext';
import { buildSpeechText } from '../../utils/speechText';

const VARIANT_CLASSES = {
  emerald: {
    idle: 'border-emerald-200/90 bg-emerald-50 text-emerald-800 hover:bg-emerald-100 dark:border-emerald-700/80 dark:bg-emerald-500/10 dark:text-emerald-200 dark:hover:bg-emerald-500/20',
    active: 'border-emerald-600 bg-emerald-600 text-white shadow-sm ring-2 ring-emerald-300/60 dark:border-emerald-500 dark:bg-emerald-600',
  },
  sky: {
    idle: 'border-sky-200 bg-sky-50/80 text-sky-800 hover:bg-sky-100 dark:border-sky-800 dark:bg-sky-500/10 dark:text-sky-200 dark:hover:bg-sky-500/20',
    active: 'border-sky-600 bg-sky-600 text-white shadow-sm ring-2 ring-sky-300/60',
  },
  slate: {
    idle: 'border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700',
    active: 'border-emerald-600 bg-emerald-600 text-white shadow-sm',
  },
  amber: {
    idle: 'border-amber-300/80 bg-amber-100/70 text-amber-900 hover:bg-amber-200/70 dark:border-amber-700 dark:bg-amber-500/15 dark:text-amber-100 dark:hover:bg-amber-500/25',
    active: 'border-amber-600 bg-amber-600 text-white shadow-sm',
  },
  violet: {
    idle: 'border-violet-200 bg-violet-50 text-violet-800 hover:bg-violet-100 dark:border-violet-700/80 dark:bg-violet-500/10 dark:text-violet-200 dark:hover:bg-violet-500/20',
    active: 'border-violet-600 bg-violet-600 text-white shadow-sm',
  },
  rose: {
    idle: 'border-rose-200 bg-rose-50 text-rose-800 hover:bg-rose-100 dark:border-rose-700/80 dark:bg-rose-500/10 dark:text-rose-200 dark:hover:bg-rose-500/20',
    active: 'border-rose-600 bg-rose-600 text-white shadow-sm',
  },
  dark: {
    idle: 'border-white/15 bg-white/10 text-white hover:bg-white/20',
    active: 'border-emerald-400 bg-emerald-500/35 text-white ring-1 ring-emerald-400',
  },
  white: {
    idle: 'border-emerald-200/80 bg-white text-emerald-800 shadow-xs hover:bg-emerald-100 dark:border-slate-700 dark:bg-slate-800 dark:text-emerald-200 dark:hover:bg-slate-700',
    active: 'border-emerald-700 bg-emerald-700 text-white shadow-sm',
  },
};

const SIZE_CLASSES = {
  xs: 'min-h-8 px-2.5 py-1 text-xs gap-1.5 rounded-xl',
  sm: 'min-h-9 px-3 py-1.5 text-xs gap-1.5 rounded-full',
  md: 'min-h-11 px-3.5 py-2 text-sm gap-2 rounded-full',
};

const ICON_ONLY_SIZE_CLASSES = {
  xs: 'h-8 w-8 rounded-xl justify-center',
  sm: 'h-9 w-9 rounded-xl justify-center',
  md: 'h-11 w-11 rounded-xl justify-center',
};

export default function ListenButton({
  id,
  text,
  textKey,
  params,
  label,
  labelKey = 'settings.listen',
  stopLabelKey = 'settings.stop',
  ariaLabel,
  ariaLabelKey,
  size = 'sm',
  variant = 'emerald',
  iconOnly = false,
  hideLabelOnMobile = false,
  onSpeakingChange,
  className = '',
}) {
  const { t, languageInfo } = useTranslation();
  const { speak, stop, isSpeaking, isSupported, voiceInfo } = useVoice();

  useEffect(() => {
    onSpeakingChange?.(isSpeaking);
  }, [isSpeaking, onSpeakingChange]);

  const resolvedText = useMemo(() => {
    if (textKey) {
      return buildSpeechText(t(textKey, params || {}));
    }
    if (Array.isArray(text)) {
      return buildSpeechText(text);
    }
    return buildSpeechText(text || '');
  }, [params, t, text, textKey]);

  const listenLabel = label || t(labelKey);
  const stopLabel = t(stopLabelKey);

  const noVoiceInstalled = !isSupported || (voiceInfo.voicesLoaded && !voiceInfo.hasVoice);
  const isDisabled = noVoiceInstalled || !resolvedText;

  const disabledTooltip = !isSupported
    ? t('voice.unsupported')
    : !voiceInfo.hasVoice
      ? t('voice.noVoiceForLanguage', {
          language: languageInfo.nativeName || languageInfo.englishName,
        })
      : '';

  const computedAriaLabel = isSpeaking
    ? stopLabel
    : disabledTooltip ||
      ariaLabel ||
      (ariaLabelKey ? t(ariaLabelKey, params || {}) : listenLabel);

  const variantStyle = VARIANT_CLASSES[variant] || VARIANT_CLASSES.emerald;
  const sizeStyle = iconOnly
    ? ICON_ONLY_SIZE_CLASSES[size] || ICON_ONLY_SIZE_CLASSES.sm
    : SIZE_CLASSES[size] || SIZE_CLASSES.sm;
  const iconSize = size === 'md' ? 17 : 15;

  const handleClick = (event) => {
    event.stopPropagation();
    if (isSpeaking) {
      stop();
      return;
    }
    if (!resolvedText) return;
    void speak(resolvedText);
  };

  const handleDisabledTap = (event) => {
    if (!noVoiceInstalled || !resolvedText) return;
    event.stopPropagation();
    // Surfaces the non-blocking translated fallback/no-voice notice on touch devices too
    void speak(resolvedText);
  };

  const buttonEl = (
    <button
      type="button"
      id={id}
      disabled={isDisabled}
      onClick={handleClick}
      aria-label={computedAriaLabel}
      aria-pressed={isSpeaking}
      title={isDisabled ? disabledTooltip : computedAriaLabel}
      className={`inline-flex shrink-0 items-center border font-bold transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:cursor-not-allowed disabled:opacity-50 ${sizeStyle} ${
        isSpeaking ? variantStyle.active : variantStyle.idle
      } ${className}`}
    >
      {isSpeaking ? (
        <Square size={iconSize - 2} className="shrink-0 fill-current" aria-hidden="true" />
      ) : noVoiceInstalled ? (
        <VolumeX size={iconSize} className="shrink-0" aria-hidden="true" />
      ) : (
        <Volume2 size={iconSize} className="shrink-0" aria-hidden="true" />
      )}
      {!iconOnly && (
        <span className={hideLabelOnMobile ? 'hidden sm:inline' : ''}>
          {isSpeaking ? stopLabel : listenLabel}
        </span>
      )}
    </button>
  );

  if (noVoiceInstalled && disabledTooltip) {
    return (
      <span
        title={disabledTooltip}
        onClick={handleDisabledTap}
        className="inline-flex shrink-0"
      >
        {buttonEl}
      </span>
    );
  }

  return buttonEl;
}

