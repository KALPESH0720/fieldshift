import { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Mic, Play, Square } from 'lucide-react';
import useVoice from '../hooks/useVoice';
import { useTranslation } from '../context/LanguageContext';
import ListenButton from './ui/ListenButton';
import { buildSpeechText } from '../utils/speechText';

export default function VoiceAdvisory() {
  const { t, languageInfo } = useTranslation();
  const { speak, stop, isSpeaking, isSupported, voiceInfo } = useVoice();

  const advisorySpeech = useMemo(
    () =>
      buildSpeechText([
        t('advisory.title'),
        t('advisory.summary'),
        t('advisory.fullScript'),
      ]),
    [t],
  );

  const noVoiceInstalled = !isSupported || (voiceInfo.voicesLoaded && !voiceInfo.hasVoice);
  const disabledTooltip = !isSupported
    ? t('voice.unsupported')
    : !voiceInfo.hasVoice
      ? t('voice.noVoiceForLanguage', {
          language: languageInfo.nativeName || languageInfo.englishName,
        })
      : '';

  const handleTogglePlay = () => {
    if (isSpeaking) {
      stop();
      return;
    }
    void speak(advisorySpeech);
  };

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      className="rounded-2xl border border-blue-100 bg-sky-50 p-4 shadow-sm dark:border-sky-400/20 dark:bg-sky-500/10 sm:p-5"
    >
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-100 text-blue-600 dark:bg-blue-500/20 dark:text-blue-300">
          <Mic size={20} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-bold tracking-tight text-slate-900 dark:text-slate-100">
              {t('advisory.title')}
            </h2>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-blue-700 dark:text-blue-300">
                {t('advisory.badge')}
              </span>
              <ListenButton
                text={advisorySpeech}
                variant="sky"
                size="xs"
                ariaLabelKey="advisory.playAria"
              />
            </div>
          </div>
          <p className="mt-1 text-sm font-medium leading-5 text-slate-600 dark:text-slate-300">
            {t('advisory.summary')}
          </p>
          <div className="mt-4 flex items-center gap-3 rounded-xl border border-blue-100 bg-white/70 p-3 dark:border-slate-700 dark:bg-slate-800">
            <span
              title={noVoiceInstalled ? disabledTooltip : undefined}
              onClick={noVoiceInstalled ? () => void speak(advisorySpeech) : undefined}
              className="inline-flex shrink-0"
            >
              <button
                type="button"
                disabled={noVoiceInstalled}
                onClick={handleTogglePlay}
                aria-label={isSpeaking ? t('advisory.stopAria') : t('advisory.playAria')}
                aria-pressed={isSpeaking}
                title={noVoiceInstalled ? disabledTooltip : isSpeaking ? t('advisory.stopAria') : t('advisory.playAria')}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-600 text-white shadow-sm transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isSpeaking ? (
                  <Square size={15} fill="currentColor" />
                ) : (
                  <Play size={17} fill="currentColor" className="ms-0.5" />
                )}
              </button>
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex h-6 items-center gap-1" aria-hidden="true">
                {[3, 5, 8, 12, 7, 15, 10, 5, 9, 13, 7, 4, 8, 11, 6, 3, 7, 10, 5, 3].map((height, index) => (
                  <span
                    key={`${height}-${index}`}
                    className={`w-1 rounded-full transition-colors ${
                      isSpeaking ? 'animate-pulse bg-blue-500' : 'bg-blue-300 dark:bg-slate-600'
                    }`}
                    style={{ height: `${height}px` }}
                  />
                ))}
              </div>
              <div className="mt-1 h-1 rounded-full bg-blue-100 dark:bg-slate-600">
                <div
                  className={`h-1 rounded-full bg-blue-500 transition-all dark:bg-blue-400 ${
                    isSpeaking ? 'w-3/4' : 'w-1/4'
                  }`}
                />
              </div>
            </div>
            <span className="text-xs font-bold text-slate-600 dark:text-slate-300">
              {isSpeaking ? t('settings.stop') : t('settings.listen')}
            </span>
          </div>
        </div>
      </div>
    </motion.section>
  );
}
