import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useLiveQuery } from 'dexie-react-hooks';
import {
  AlertTriangle,
  BellRing,
  Check,
  ChevronLeft,
  Globe2,
  MessageCircle,
  MessageSquareText,
  Phone,
  Settings as SettingsIcon,
  UserCheck,
  Volume2,
  LogOut,
  Wifi,
  WifiOff,
  ShieldCheck,
  Smartphone,
  ChevronRight,
  Info,
  Moon,
  Sun,
} from 'lucide-react';
import useVoice from '../hooks/useVoice';
import { useTheme } from '../context/ThemeContext';
import { useTranslation } from '../context/LanguageContext';
import { useAuth } from '../context/AuthContext';
import { db } from '../db/db';
import { maskPhoneE164, getCountryName } from '../utils/phone';
import { CROP_CREDITS, CROPS, getCropDisplayName } from '../data/crops';
import CropImage from './CropImage';
import ListenButton from './ui/ListenButton';
import { buildSpeechText } from '../utils/speechText';

// -----------------------------------------------------------------------------
//  Settings.jsx - Premium Dribbble-quality UI
//
//  KEY FEATURES:
//    - Language toggle (English / Marathi / Hindi) with TTS narration
//    - Farm reminders toggle (Sowing, Fertilizer)
//    - Notification channel selector (SMS / WhatsApp)
//    - Offline Sync Status indicator (reads from navigator.onLine)
//    - App version / About row
//    - Full-width LOG OUT button clears localStorage and navigates to login
// -----------------------------------------------------------------------------

// -- Sub-components ------------------------------------------------------------

function ReminderToggle({ checked, onChange, label, description, icon: Icon }) {
  return (
    <motion.button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={onChange}
      whileTap={{ scale: 0.98 }}
      className={`flex min-h-[80px] w-full items-center gap-4 rounded-2xl border p-4 text-left transition-all focus:outline-none focus:ring-2 focus:ring-emerald-500 ${
        checked
          ? 'border-emerald-200/80 bg-gradient-to-r from-emerald-50 to-teal-50/60 shadow-sm dark:border-emerald-700/60 dark:from-emerald-500/15 dark:to-teal-500/10'
          : 'border-slate-200 dark:border-slate-700/60 bg-white dark:bg-slate-900 hover:border-slate-300 hover:bg-slate-50 dark:hover:bg-slate-950/60'
      }`}
    >
      <span
        className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl transition-all ${
          checked
            ? 'bg-gradient-to-br from-emerald-500 to-teal-600 text-white shadow-md shadow-emerald-200'
            : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400'
        }`}
      >
        <Icon size={22} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-bold text-slate-900 dark:text-slate-100 tracking-tight leading-tight">{label}</span>
        <span className="mt-1 block text-sm leading-relaxed text-slate-500 dark:text-slate-400">{description}</span>
      </span>
      <motion.span
        animate={{ backgroundColor: checked ? '#059669' : '#e2e8f0' }}
        transition={{ duration: 0.2 }}
        className="flex h-7 w-12 shrink-0 items-center rounded-full p-1"
      >
        <motion.span
          animate={{ x: checked ? 20 : 0 }}
          transition={{ type: 'spring', stiffness: 500, damping: 30 }}
          className="h-5 w-5 rounded-full bg-white dark:bg-slate-900 shadow-sm"
        />
      </motion.span>
    </motion.button>
  );
}

// -- Section wrapper -----------------------------------------------------------
function SettingsCard({ children, delay = 0, accentColor = 'from-emerald-500 via-teal-500 to-emerald-600' }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: [0.22, 1, 0.36, 1] }}
      className="relative overflow-visible rounded-3xl border border-slate-200 dark:border-slate-700/60 bg-white dark:bg-slate-900 shadow-sm shadow-slate-200/60"
    >
      {/* Top gradient accent bar */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-1 overflow-hidden rounded-t-3xl">
        <div className={`h-full w-full bg-gradient-to-r ${accentColor} dark:brightness-125`} />
      </div>
      <div className="p-5 sm:p-7 pt-6">{children}</div>
    </motion.section>
  );
}

// -- Info row (for About section) ----------------------------------------------
function InfoRow({ icon: Icon, label, value, onClick, expanded = false }) {
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag
      type={onClick ? 'button' : undefined}
      onClick={onClick}
      aria-expanded={onClick ? expanded : undefined}
      className={`flex w-full items-center justify-between py-3 text-start border-b border-slate-100 dark:border-slate-800 last:border-0 ${
        onClick ? 'cursor-pointer hover:bg-slate-50/70 dark:hover:bg-slate-800/40 rounded-xl px-1 -mx-1 transition-colors' : ''
      }`}
    >
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center shrink-0">
          <Icon size={16} className="text-slate-600 dark:text-slate-400" />
        </div>
        <span className="text-sm font-semibold text-slate-700 dark:text-slate-300 tracking-tight">{label}</span>
      </div>
      <span className="text-xs font-medium text-slate-400 flex items-center gap-1">
        {value}
        <ChevronRight
          size={13}
          className={`text-slate-300 transition-transform ${expanded ? 'rotate-90' : ''}`}
        />
      </span>
    </Tag>
  );
}

function LanguagePicker({ language, languages, recentLanguages, setLanguage, onLanguageChange, emptyLabel, searchLabel, recentLabel }) {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const activeOptionRef = useRef(null);
  const normalize = (value) => String(value).normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase();
  const filtered = languages.filter((item) => {
    const needle = normalize(query);
    return !needle || [item.nativeName, item.englishName, item.code].some((value) => normalize(value).includes(needle));
  });
  const recent = recentLanguages
    .map((code) => languages.find((item) => item.code === code))
    .filter(Boolean)
    .filter((item) => filtered.some((candidate) => candidate.code === item.code));
  const options = [...recent, ...filtered.filter((item) => !recent.some((candidate) => candidate.code === item.code))];
  useEffect(() => {
    activeOptionRef.current?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex]);
  const selectLanguage = (code) => {
    setLanguage(code);
    onLanguageChange?.();
    setQuery('');
    setIsOpen(false);
  };
  const handleKeyDown = (event) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setIsOpen(true);
      setActiveIndex((index) => Math.min(index + 1, options.length - 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === 'Enter' && options[activeIndex]) {
      event.preventDefault();
      selectLanguage(options[activeIndex].code);
    } else if (event.key === 'Escape') {
      setIsOpen(false);
    }
  };

  return (
    <div className="relative">
      <input
        role="combobox"
        aria-label={searchLabel}
        aria-expanded={isOpen}
        aria-controls="language-options"
        aria-activedescendant={options[activeIndex] ? `language-option-${options[activeIndex].code}` : undefined}
        value={query}
        onChange={(event) => { setQuery(event.target.value); setIsOpen(true); setActiveIndex(0); }}
        onFocus={() => setIsOpen(true)}
        onKeyDown={handleKeyDown}
        placeholder={searchLabel}
        className="h-12 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 text-sm font-medium text-slate-900 outline-none placeholder:text-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
      />
      {isOpen && (
        <div id="language-options" role="listbox" aria-label={searchLabel} className="mt-2 max-h-[min(60vh,420px)] overscroll-contain overflow-y-auto rounded-xl border border-slate-200 bg-white p-1 shadow-xl dark:border-slate-700 dark:bg-slate-900 language-picker-scrollbar">
          {options.length === 0 && <p className="px-3 py-4 text-sm text-slate-500 dark:text-slate-400">{emptyLabel}</p>}
          {options.length > 0 && recent.length > 0 && <div className="sticky top-0 z-10 bg-white/95 px-3 py-2 text-[11px] font-bold uppercase tracking-wide text-slate-500 backdrop-blur dark:bg-slate-900/95 dark:text-slate-400">{recentLabel}</div>}
          {options.map((item, index) => (
            <button
              key={item.code}
              ref={index === activeIndex ? activeOptionRef : null}
              id={`language-option-${item.code}`}
              type="button"
              role="option"
              aria-selected={item.code === language}
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => selectLanguage(item.code)}
              className={`flex min-h-12 w-full items-center justify-between gap-3 rounded-lg border border-transparent px-3 py-2.5 text-start normal-case tracking-normal leading-relaxed transition ${index === activeIndex ? 'border-emerald-200 bg-emerald-50 dark:border-emerald-400 dark:bg-emerald-500/15' : 'hover:bg-slate-50 focus:bg-slate-50 dark:hover:bg-slate-800 dark:focus:bg-slate-800'} [content-visibility:auto]`}
            >
              <span className="min-w-0">
                <span className="block truncate text-sm font-bold text-slate-900 dark:text-slate-100">{item.nativeName}</span>
                <span className="block truncate text-xs text-slate-500 dark:text-slate-400">{item.englishName}</span>
              </span>
              <span className="flex shrink-0 items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                <span>{item.code}</span>
                {item.code === language && <Check size={16} className="text-emerald-600 dark:text-emerald-300" />}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// -- Main export ---------------------------------------------------------------
export default function Settings() {
  const navigate = useNavigate();
  const { theme, setTheme } = useTheme();
  const { language, languageInfo, languages, recentLanguages, setLanguage, t } = useTranslation();
  const { user, logout } = useAuth();
  const unsyncedCount = useLiveQuery(() => db.syncQueue.count(), [], 0);

  const [reminders, setReminders] = useState({
    sowing: true,
    fertilizer: false,
    sms: true,
    whatsapp: false,
  });
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [logOutConfirm, setLogOutConfirm] = useState(false);
  const [showImageCredits, setShowImageCredits] = useState(false);
  const creditEntries = useMemo(() => {
    const map = CROP_CREDITS?.crops || CROP_CREDITS || {};
    return CROPS.filter((crop) => map[crop.id]).map((crop) => ({
      crop,
      credit: map[crop.id],
    }));
  }, []);

  const copy = useMemo(() => ({
    title: t('settings.title'),
    subtitle: t('settings.subtitle'),
    languageTitle: t('settings.languageTitle'),
    languageBody: t('settings.languageBody'),
    remindersTitle: t('settings.remindersTitle'),
    remindersBody: t('settings.remindersBody'),
    sowing: t('settings.sowing'),
    sowingBody: t('settings.sowingBody'),
    fertilizer: t('settings.fertilizer'),
    fertilizerBody: t('settings.fertilizerBody'),
    channels: t('settings.channels'),
    sms: t('settings.sms'),
    whatsapp: t('settings.whatsapp'),
    listen: t('settings.listen'),
    stop: t('settings.stop'),
    saved: t('settings.saved'),
    unavailable: t('settings.unavailable'),
    offline: t('settings.offline'),
    offlineBody: t('settings.offlineBody'),
    online: t('settings.online'),
    onlineBody: t('settings.onlineBody'),
    logOut: t('settings.logOut'),
    logOutBody: t('settings.logOutBody'),
    about: t('settings.about'),
    version: t('settings.version'),
    textMessage: t('settings.textMessage'),
    chatMessage: t('settings.chatMessage'),
    light: t('settings.light'),
    dark: t('settings.dark'),
    system: t('settings.system'),
    back: t('settings.back'),
    voiceTest: t('voice.voiceTest'),
    testVoice: t('voice.testVoice'),
    usingVoice: t('voice.usingVoice'),
    voiceSample: t('voice.testSample'),
    dismiss: t('voice.dismiss'),
  }), [t]);
  const nativeTextClass = languageInfo.script === 'Latin' ? '' : 'normal-case tracking-normal leading-relaxed';
  const voice = useVoice();

  // Track live online/offline status
  useEffect(() => {
    const onOnline  = () => setIsOnline(true);
    const onOffline = () => setIsOnline(false);
    window.addEventListener('online',  onOnline);
    window.addEventListener('offline', onOffline);
    return () => {
      window.removeEventListener('online',  onOnline);
      window.removeEventListener('offline', onOffline);
    };
  }, []);

  const reminderText = useMemo(
    () =>
      buildSpeechText([
        copy.remindersTitle,
        `${copy.sowing}: ${copy.sowingBody}`,
        `${copy.fertilizer}: ${copy.fertilizerBody}`,
        `${copy.channels}: ${copy.sms}, ${copy.whatsapp}`,
      ]),
    [copy],
  );

  const toggleReminder = (key) =>
    setReminders((current) => ({ ...current, [key]: !current[key] }));

  // -- Log Out handler ---------------------------------------------------------
  const handleLogOut = async () => {
    if (!logOutConfirm) {
      setLogOutConfirm(true);
      if (unsyncedCount === 0) {
        setTimeout(() => setLogOutConfirm(false), 5000);
      }
      return;
    }
    await logout();
    navigate('/login', { replace: true });
  };

  const handleSwitchUserClick = async () => {
    if (unsyncedCount > 0 && !logOutConfirm) {
      setLogOutConfirm(true);
      return;
    }
    await logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100/60 pb-28 font-sans text-slate-900 dark:text-slate-100 dark:from-slate-950 dark:to-slate-900 dark:text-slate-100">

      {/* -- Sticky header ---------------------------------------------------- */}
      <header className="relative z-0 border-b border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900 sm:px-6">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => navigate(-1)}
              aria-label={copy.back}
              className="rounded-xl p-2 -ml-1 text-slate-600 dark:text-slate-400 transition-colors hover:bg-slate-100 dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              <ChevronLeft size={21} />
            </button>
            <div>
              <div className="flex items-center gap-2">
                <SettingsIcon size={18} className="text-emerald-700" />
                <h1 className={`text-xl font-bold tracking-tight ${nativeTextClass}`}>{copy.title}</h1>
              </div>
              <p className="hidden text-xs leading-relaxed text-slate-500 dark:text-slate-400 sm:block">{copy.subtitle}</p>
            </div>
          </div>
          <ListenButton
            text={[copy.title, copy.subtitle]}
            size="md"
          />
        </div>
        <div className="mx-auto mt-3 flex max-w-3xl justify-end gap-2">
          {[
          { value: 'light', label: copy.light, Icon: Sun },
          { value: 'dark', label: copy.dark, Icon: Moon },
          { value: 'system', label: copy.system, Icon: SettingsIcon },
          ].map(({ value, label, Icon }) => (
            <button
              key={value}
              type="button"
              onClick={() => setTheme(value)}
              className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-bold transition ${theme === value ? 'bg-slate-900 text-white dark:bg-slate-700' : 'text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-800'}`}
            >
              <Icon size={13} /> {label}
            </button>
          ))}
        </div>
      </header>

      <main className="mx-auto max-w-3xl space-y-4 px-4 pt-5 sm:px-6">

        {/* -- 0. Account / Profile Card --------------------------------------- */}
        {user && (
          <SettingsCard delay={0} accentColor="from-emerald-600 via-teal-500 to-cyan-600">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-start gap-3.5 min-w-0">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 text-white shadow-md shadow-emerald-500/20">
                  <UserCheck size={22} />
                </div>
                <div className="min-w-0">
                  <span className={`block text-[11px] font-black text-emerald-600 dark:text-emerald-400 ${language === 'en' ? 'uppercase tracking-widest' : nativeTextClass}`}>
                    {t('settings.accountTitle')}
                  </span>
                  <h2 className={`mt-0.5 text-lg font-bold tracking-tight text-slate-900 dark:text-slate-100 truncate ${nativeTextClass}`}>
                    {user.displayName || t('settings.accountSubtitle')}
                  </h2>
                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-600 dark:text-slate-300">
                    <span className="inline-flex items-center gap-1.5 font-semibold" dir="ltr">
                      <Phone size={14} className="text-emerald-600 dark:text-emerald-400 shrink-0" />
                      {maskPhoneE164(user.phoneE164)}
                    </span>
                    {user.country && (
                      <span className="text-xs font-medium text-slate-400 dark:text-slate-500">
                        • {getCountryName(user.country, language)}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <button
                type="button"
                id="settings-switch-user-btn"
                onClick={handleSwitchUserClick}
                className="inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/80 px-4 py-2.5 text-xs font-bold text-slate-700 dark:text-slate-200 transition hover:bg-slate-100 dark:hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                <LogOut size={15} className="text-emerald-600 dark:text-emerald-400" />
                <span>{t('auth.notYouSwitch')}</span>
              </button>
            </div>
          </SettingsCard>
        )}

        {/* -- 1. Language Card ------------------------------------------------ */}
        <SettingsCard delay={0}>
          <div className="flex items-start justify-between gap-3 mb-5">
            <div>
              <div className="mb-1.5 flex items-center gap-2 text-emerald-700">
                <Globe2 size={18} />
                <span className={`text-[11px] font-black text-emerald-600 ${language === 'en' ? 'uppercase tracking-widest' : nativeTextClass}`}>
                  {t('settings.featureLanguage')}
                </span>
              </div>
              <h2 className={`text-xl font-bold tracking-tight ${nativeTextClass}`}>{copy.languageTitle}</h2>
              <p className="mt-1 text-sm leading-relaxed text-slate-500 dark:text-slate-400">{copy.languageBody}</p>
            </div>
          </div>
          <LanguagePicker
            language={language}
            languages={languages}
            recentLanguages={recentLanguages}
            setLanguage={setLanguage}
            onLanguageChange={() => voice.stop()}
                    emptyLabel={t('settings.noLanguages')}
                   searchLabel={t('settings.searchLanguages')}
                   recentLabel={t('settings.recentlyUsed')}
                  />
        </SettingsCard>

        {/* -- 2. Farm Reminders Card ------------------------------------------ */}
        <SettingsCard delay={0.06} accentColor="from-violet-500 via-purple-500 to-violet-600">
          <div className="flex items-start justify-between gap-3 mb-5">
            <div>
              <div className="mb-1.5 flex items-center gap-2">
                <BellRing size={18} className="text-violet-600" />
                <span className={`text-[11px] font-black text-violet-600 ${language === 'en' ? 'uppercase tracking-widest' : nativeTextClass}`}>
                  {t('settings.featureReminders')}
                </span>
              </div>
              <h2 className={`text-xl font-bold tracking-tight ${nativeTextClass}`}>{copy.remindersTitle}</h2>
              <p className="mt-1 text-sm leading-relaxed text-slate-500 dark:text-slate-400">{copy.remindersBody}</p>
            </div>
            <ListenButton text={reminderText} size="md" />
          </div>

          <div className="space-y-2.5">
            <ReminderToggle
              checked={reminders.sowing}
              onChange={() => toggleReminder('sowing')}
              label={copy.sowing}
              description={copy.sowingBody}
              icon={BellRing}
            />
            <ReminderToggle
              checked={reminders.fertilizer}
              onChange={() => toggleReminder('fertilizer')}
              label={copy.fertilizer}
              description={copy.fertilizerBody}
              icon={MessageSquareText}
            />
          </div>

          {/* Channel selector */}
          <div className="mt-5 border-t border-slate-100 dark:border-slate-800 pt-5">
            <p className="mb-3 text-sm font-bold text-slate-800 dark:text-slate-200 tracking-tight">{copy.channels}</p>
            <div className="grid grid-cols-2 gap-2.5">
              <ReminderToggle
                checked={reminders.sms}
                onChange={() => toggleReminder('sms')}
                label={copy.sms}
                description={copy.textMessage}
                icon={MessageSquareText}
              />
              <ReminderToggle
                checked={reminders.whatsapp}
                onChange={() => toggleReminder('whatsapp')}
                label={copy.whatsapp}
                description={copy.chatMessage}
                icon={MessageCircle}
              />
            </div>
          </div>

          {/* Saved confirmation chip */}
          <div className="mt-4 flex items-center gap-2 rounded-2xl border border-emerald-200/60 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800 dark:border-emerald-700/60 dark:bg-emerald-500/10 dark:text-emerald-200">
            <Check size={16} className="shrink-0 text-emerald-600" />
            <span className="leading-relaxed">{copy.saved}</span>
          </div>

          {!voice.isSupported && (
            <p className="mt-3 text-xs leading-relaxed text-slate-400" role="status">
              {copy.unavailable}
            </p>
          )}
          {voice.error && (
            <p className="mt-3 text-xs leading-relaxed text-amber-700 dark:text-amber-300" role="status">
              {voice.error}
            </p>
          )}
        </SettingsCard>

        {/* -- 3. Voice Test Card ---------------------------------------------- */}
        <SettingsCard delay={0.1} accentColor="from-cyan-500 via-sky-500 to-blue-600">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <div className="mb-1.5 flex items-center gap-2 text-sky-700 dark:text-sky-300">
                <Volume2 size={18} />
                <span className={`text-[11px] font-black ${language === 'en' ? 'uppercase tracking-widest' : nativeTextClass}`}>
                  {copy.voiceTest}
                </span>
              </div>
              <p className={`text-sm leading-relaxed text-slate-600 dark:text-slate-300 ${nativeTextClass}`}>
                {copy.voiceSample}
              </p>

              <div className="mt-3 space-y-1.5 rounded-2xl border border-slate-100 bg-slate-50/80 p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-950/60 dark:text-slate-300" role="status">
                <p>
                  {t('voice.languageCodeLabel')}:{' '}
                  <span dir="ltr" className="font-mono font-bold text-slate-800 dark:text-slate-100">
                    {voice.voiceInfo.languageCode} ({voice.voiceInfo.speechLang}
                    {voice.voiceInfo.usedFallback ? ` → ${voice.voiceInfo.utteranceLocale}` : ''})
                  </span>
                </p>
                <p>
                  {copy.usingVoice}:{' '}
                  <span className="font-semibold text-slate-800 dark:text-slate-100">
                    {voice.voiceInfo.voiceName || t('voice.noVoice')}
                  </span>
                </p>
                <div>
                  <p className="font-medium text-slate-500 dark:text-slate-400">
                    {t('voice.availableVoicesLabel')} ({voice.voiceInfo.availableVoices.length}):
                  </p>
                  {voice.voiceInfo.availableVoices.length > 0 ? (
                    <ul className="mt-1.5 flex flex-wrap gap-1.5">
                      {voice.voiceInfo.availableVoices.map((item) => (
                        <li
                          key={`${item.name}-${item.lang}`}
                          className={`rounded-lg border px-2 py-0.5 text-[11px] font-medium ${
                            item.name === voice.voiceInfo.voiceName
                              ? 'border-sky-300 bg-sky-100/80 text-sky-900 dark:border-sky-600 dark:bg-sky-500/20 dark:text-sky-100'
                              : 'border-slate-200 bg-white text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300'
                          }`}
                        >
                          {item.name} <span dir="ltr" className="opacity-70">({item.lang})</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-1 text-[11px] text-amber-700 dark:text-amber-300">
                      {t('voice.noVoiceForLanguage', {
                        language: languageInfo.nativeName || languageInfo.englishName,
                      })}
                    </p>
                  )}
                </div>
              </div>
            </div>
            <ListenButton
              text={copy.voiceSample}
              labelKey="voice.testVoice"
              variant="sky"
              size="md"
            />
          </div>
        </SettingsCard>

        {/* -- 4. Offline Sync Status Card ------------------------------------- */}
        <SettingsCard delay={0.12} accentColor={isOnline ? 'from-sky-500 via-blue-500 to-sky-600' : 'from-amber-500 via-orange-400 to-amber-500'}>
          <div className="flex items-center gap-4">
            <div className={`shrink-0 w-12 h-12 rounded-2xl flex items-center justify-center shadow-sm ${
              isOnline
                ? 'bg-gradient-to-br from-sky-500 to-blue-600 text-white'
                : 'bg-gradient-to-br from-amber-400 to-orange-500 text-white'
            }`}>
              {isOnline ? <Wifi size={22} /> : <WifiOff size={22} />}
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-bold text-slate-900 dark:text-slate-100 tracking-tight">
                {isOnline ? copy.online : copy.offline}
              </p>
              <p className="text-sm leading-relaxed text-slate-500 dark:text-slate-400 mt-0.5">
                {isOnline ? copy.onlineBody : copy.offlineBody}
              </p>
            </div>
            <div className={`shrink-0 w-2.5 h-2.5 rounded-full ${isOnline ? 'bg-sky-400 animate-pulse' : 'bg-amber-400'}`} />
          </div>
        </SettingsCard>

        {/* -- 5. About Card --------------------------------------------------- */}
        <SettingsCard delay={0.18} accentColor="from-slate-400 via-slate-500 to-slate-400">
          <div className="mb-1.5 flex items-center gap-2 text-slate-500 dark:text-slate-400">
            <Info size={16} />
            <span className={`text-[11px] font-black ${language === 'en' ? 'uppercase tracking-widest' : nativeTextClass}`}>{copy.about}</span>
          </div>
          <div className="mt-3 divide-y divide-slate-100 dark:divide-slate-800">
            <InfoRow icon={ShieldCheck} label={t('settings.privacy')} value={t('settings.privacyBody')} />
            <InfoRow icon={Smartphone}  label={t('settings.appVersion')} value={copy.version} />
            <InfoRow
              icon={Info}
              label={t('settings.imageCredits')}
              value={t('settings.imageCreditsBody')}
              expanded={showImageCredits}
              onClick={() => setShowImageCredits((prev) => !prev)}
            />
          </div>
          {showImageCredits && (
            <div className="mt-3 rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-950/60 p-3">
              <p className="mb-2.5 text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                {t('settings.imageCreditsIntro')}
              </p>
              <div className="max-h-72 overflow-y-auto divide-y divide-slate-200/70 dark:divide-slate-800 pr-1">
                {creditEntries.map(({ crop, credit }) => (
                  <div key={crop.id} className="flex items-center justify-between gap-3 py-2 text-xs">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <CropImage cropId={crop.id} size="sm" className="h-9 w-9 rounded-xl" />
                      <div className="min-w-0">
                        <p className="truncate font-bold text-slate-800 dark:text-slate-100">
                          {getCropDisplayName(crop, t)}
                        </p>
                        <p className="truncate text-[11px] text-slate-500 dark:text-slate-400">
                          {credit.author} · {credit.license}
                        </p>
                      </div>
                    </div>
                    {credit.pageUrl && (
                      <a
                        href={credit.pageUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="shrink-0 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-2.5 py-1 text-[11px] font-semibold text-emerald-700 dark:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-950/40"
                      >
                        {t('settings.viewSource')}
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </SettingsCard>

        {/* -- 6. LOG OUT Button ----------------------------------------------- */}
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.24, ease: [0.22, 1, 0.36, 1] }}
        >
          <AnimatePresence mode="wait">
            {logOutConfirm ? (
              // -- Confirmation state ------------------------------------------
              <motion.div
                key="confirm"
                initial={{ scale: 0.96, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.96, opacity: 0 }}
                className="space-y-3"
              >
                {unsyncedCount > 0 && (
                  <div
                    role="alert"
                    className="flex items-start gap-3 rounded-2xl border border-amber-300 bg-amber-50 dark:border-amber-700/60 dark:bg-amber-950/60 p-4 text-sm text-amber-900 dark:text-amber-200"
                  >
                    <AlertTriangle size={20} className="mt-0.5 shrink-0 text-amber-600 dark:text-amber-400" />
                    <span className={`font-medium leading-relaxed ${nativeTextClass}`}>
                      {t('settings.unsyncedLogoutWarning', { count: unsyncedCount })}
                    </span>
                  </div>
                )}
                <div className="flex flex-col sm:flex-row gap-2.5">
                  <motion.button
                    type="button"
                    id="settings-logout-confirm-btn"
                    whileTap={{ scale: 0.96 }}
                    onClick={handleLogOut}
                    className="flex-1 min-h-[56px] rounded-2xl border-2 border-red-400 bg-red-600 text-white font-bold text-base tracking-tight flex items-center justify-center gap-2 shadow-lg shadow-red-900/20 focus:outline-none focus:ring-4 focus:ring-red-400/40"
                  >
                    <LogOut size={18} />
                    <span>{t('settings.confirmLogout')}</span>
                  </motion.button>
                  <button
                    type="button"
                    onClick={() => setLogOutConfirm(false)}
                    className="min-h-[56px] px-6 rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 font-bold text-sm hover:bg-slate-50 dark:hover:bg-slate-700 transition focus:outline-none focus:ring-2 focus:ring-slate-400"
                  >
                    {t('settings.cancelLogout')}
                  </button>
                </div>
              </motion.div>
            ) : (
              // -- Default state -----------------------------------------------
              <motion.button
                key="default"
                type="button"
                id="settings-logout-btn"
                initial={{ scale: 0.96, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.96, opacity: 0 }}
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.96 }}
                onClick={handleLogOut}
                className="w-full min-h-[56px] rounded-2xl border border-red-200/80 bg-red-50 dark:border-red-900/60 dark:bg-red-950/30 text-red-700 dark:text-red-300 font-bold text-base tracking-tight flex items-center justify-center gap-2 hover:bg-red-100 dark:hover:bg-red-950/50 hover:border-red-300 transition-all shadow-sm focus:outline-none focus:ring-4 focus:ring-red-300/40"
              >
                <LogOut size={18} className="text-red-500" />
                <span>{copy.logOut}</span>
              </motion.button>
            )}
          </AnimatePresence>
          <p className="text-center text-xs text-slate-400 leading-relaxed mt-2">{copy.logOutBody}</p>
        </motion.div>

      </main>
    </div>
  );
}
