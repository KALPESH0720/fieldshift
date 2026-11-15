import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import {
  AlertCircle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  Eye,
  EyeOff,
  Globe2,
  Loader2,
  Lock,
  Mail,
  Moon,
  Send,
  ShieldCheck,
  Sparkles,
  Sprout,
  Sun,
  User,
  UserX,
  WifiOff,
  X,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../context/LanguageContext';
import { useTheme } from '../../context/ThemeContext';
import { stopAllSpeech } from '../../hooks/useVoice';
import ListenButton from '../ui/ListenButton';
import { buildSpeechText } from '../../utils/speechText';

function useLowEndOrReducedMotion() {
  const prefersReduced = useReducedMotion();
  const lowMemory =
    typeof navigator !== 'undefined' &&
    Number(navigator.deviceMemory) > 0 &&
    Number(navigator.deviceMemory) <= 2;
  return Boolean(prefersReduced || lowMemory);
}

/* ─── Compact Searchable Language Picker for Auth Screen ─────── */
function CompactLanguagePicker({
  language,
  languages,
  recentLanguages,
  setLanguage,
  onSelect,
  t,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const containerRef = useRef(null);
  const searchInputRef = useRef(null);

  const currentLang = useMemo(
    () => languages.find((item) => item.code === language) || languages[0],
    [language, languages],
  );

  const normalize = (value) =>
    String(value || '')
      .normalize('NFD')
      .replace(/\p{Diacritic}/gu, '')
      .toLowerCase();

  const filtered = useMemo(() => {
    const needle = normalize(query);
    return languages.filter(
      (item) =>
        !needle ||
        [item.nativeName, item.englishName, item.code].some((val) =>
          normalize(val).includes(needle),
        ),
    );
  }, [languages, query]);

  const recent = useMemo(
    () =>
      recentLanguages
        .map((code) => languages.find((item) => item.code === code))
        .filter(Boolean)
        .filter((item) => filtered.some((c) => c.code === item.code)),
    [filtered, languages, recentLanguages],
  );

  const options = useMemo(
    () => [
      ...recent,
      ...filtered.filter((item) => !recent.some((c) => c.code === item.code)),
    ],
    [filtered, recent],
  );

  useEffect(() => {
    if (!isOpen) return undefined;
    const handleClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    const handleEscape = (event) => {
      if (event.key === 'Escape') setIsOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    window.addEventListener('keydown', handleEscape);
    setTimeout(() => searchInputRef.current?.focus(), 40);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      window.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen]);

  const handleChoose = (code) => {
    setLanguage(code);
    onSelect?.(code);
    setQuery('');
    setIsOpen(false);
  };

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        id="auth-language-picker-btn"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-label={t('settings.languageTitle')}
        className="inline-flex min-h-12 items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-bold text-slate-800 transition hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700"
      >
        <Globe2 size={17} className="shrink-0 text-emerald-600 dark:text-emerald-400" />
        <span className="max-w-28 truncate">{currentLang?.nativeName || 'English'}</span>
        <ChevronDown size={15} className="shrink-0 text-slate-400" />
      </button>

      {isOpen && (
        <div
          role="dialog"
          aria-label={t('settings.searchLanguages')}
          className="absolute end-0 top-full z-50 mt-2 w-72 sm:w-80 rounded-2xl border border-slate-200 bg-white p-2 shadow-2xl dark:border-slate-700 dark:bg-slate-900"
        >
          <div className="relative mb-2">
            <input
              ref={searchInputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t('settings.searchLanguages')}
              aria-label={t('settings.searchLanguages')}
              className="h-11 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 text-sm font-medium text-slate-900 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
            />
          </div>

          <div
            role="listbox"
            aria-label={t('settings.languageTitle')}
            className="max-h-64 overflow-y-auto overscroll-contain language-picker-scrollbar"
          >
            {options.length === 0 && (
              <p className="px-3 py-4 text-center text-sm text-slate-500 dark:text-slate-400">
                {t('settings.noLanguages')}
              </p>
            )}
            {options.map((item) => {
              const selected = item.code === language;
              return (
                <button
                  key={item.code}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  onClick={() => handleChoose(item.code)}
                  className={`flex min-h-12 w-full items-center justify-between gap-2 rounded-xl px-3 py-2 text-start transition ${
                    selected
                      ? 'bg-emerald-50 font-bold text-emerald-900 dark:bg-emerald-950/70 dark:text-emerald-200'
                      : 'hover:bg-slate-100 dark:hover:bg-slate-800'
                  }`}
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-bold text-slate-900 dark:text-slate-100">
                      {item.nativeName}
                    </span>
                    <span className="block truncate text-xs text-slate-500 dark:text-slate-400">
                      {item.englishName}
                    </span>
                  </span>
                  <span className="flex shrink-0 items-center gap-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400">
                    <span dir="ltr">{item.code}</span>
                    {selected && <Check size={16} className="text-emerald-600 dark:text-emerald-400" />}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Privacy & Terms Modal ──────────────────────────────────── */
function PrivacyModal({ isOpen, onClose, t }) {
  if (!isOpen) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="privacy-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-xs"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-700 dark:bg-slate-900">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-300">
              <ShieldCheck size={22} />
            </div>
            <h2 id="privacy-modal-title" className="text-lg font-extrabold text-slate-900 dark:text-white">
              {t('auth.privacyModalTitle') || 'Privacy & Security Notice'}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t('common.close')}
            className="flex h-10 w-10 items-center justify-center rounded-xl text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <X size={18} />
          </button>
        </div>
        <div className="mt-4 space-y-3 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
          <p>{t('auth.privacyModalPoint1') || 'Your email is used securely for account access and recovery.'}</p>
          <p>{t('auth.privacyModalPoint2') || 'Your farm plots, soil records, and rotation plans are stored securely and never sold.'}</p>
          <p>{t('auth.privacyModalPoint3') || 'On shared devices, you can sign out anytime to clear local data.'}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="mt-6 flex min-h-12 w-full items-center justify-center rounded-2xl bg-emerald-600 px-4 text-base font-bold text-white transition hover:bg-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
        >
          {t('common.close')}
        </button>
      </div>
    </div>
  );
}

/* ─── Main Firebase Email/Password Auth Screen ───────────────── */
export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const reduceMotion = useLowEndOrReducedMotion();

  const {
    user,
    status,
    isMock,
    login,
    signup,
    resetPassword,
    logout,
    getUnsyncedCount,
  } = useAuth();

  const { language, languages, recentLanguages, setLanguage, t } = useTranslation();
  const { resolvedTheme, toggleTheme } = useTheme();
  const isDarkMode = resolvedTheme === 'dark';

  const redirectTo = useMemo(() => {
    const fromPath = location.state?.from?.pathname;
    if (fromPath && !['/login', '/signup', '/forgot-password'].includes(fromPath)) {
      return `${fromPath}${location.state?.from?.search || ''}${location.state?.from?.hash || ''}`;
    }
    return '/farm';
  }, [location.state]);

  // Mode: 'signIn' | 'signUp' | 'forgotPassword'
  const [mode, setMode] = useState(() => {
    if (location.pathname === '/signup') return 'signUp';
    if (location.pathname === '/forgot-password') return 'forgotPassword';
    return 'signIn';
  });

  // Form Fields
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [preferredLocale, setPreferredLocale] = useState(language);
  const [consentChecked, setConsentChecked] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [isPrivacyModalOpen, setIsPrivacyModalOpen] = useState(false);

  // Status & Notifications
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [statusAnnouncement, setStatusAnnouncement] = useState('');
  const [isOnline, setIsOnline] = useState(() =>
    typeof navigator !== 'undefined' ? navigator.onLine : true,
  );
  const [switchUserConfirmUnsynced, setSwitchUserConfirmUnsynced] = useState(0);

  const emailInputRef = useRef(null);
  const passwordInputRef = useRef(null);
  const nameInputRef = useRef(null);

  // Track online/offline
  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Autofocus input on mode switch
  useEffect(() => {
    const timer = setTimeout(() => {
      if (mode === 'signUp') {
        nameInputRef.current?.focus();
      } else {
        emailInputRef.current?.focus();
      }
    }, 60);
    return () => clearTimeout(timer);
  }, [mode]);

  const handleLanguageSelect = useCallback(
    async (nextLang) => {
      stopAllSpeech();
      await setLanguage(nextLang);
      setPreferredLocale(nextLang);
    },
    [setLanguage],
  );

  // Friendly error mapping for Firebase Auth error codes
  const translateAuthError = useCallback(
    (err) => {
      if (!isOnline) {
        return t('auth.errors.noNetwork') || 'No internet connection. Please connect and try again.';
      }
      const code = err?.code || err?.message || '';

      if (code.includes('invalid-email') || code === 'email_required') {
        return t('auth.errors.invalidEmail') || 'Please enter a valid email address.';
      }
      if (code.includes('user-not-found') || code.includes('wrong-password') || code.includes('invalid-credential') || code === 'invalid_credentials') {
        return t('auth.errors.invalidCredentials') || 'Invalid email or password. Please check and try again.';
      }
      if (code.includes('email-already-in-use') || code === 'email_in_use') {
        return t('auth.errors.emailInUse') || 'An account with this email already exists. Please sign in instead.';
      }
      if (code.includes('weak-password') || code === 'weak_password') {
        return t('auth.errors.passwordTooShort') || 'Password must be at least 6 characters long.';
      }
      if (code.includes('too-many-requests')) {
        return t('auth.errors.tooManyAttempts') || 'Too many failed attempts. Please wait a moment before trying again.';
      }
      if (code.includes('network-request-failed')) {
        return t('auth.errors.noNetwork') || 'Network error. Please check your internet connection.';
      }

      return err?.message || t('auth.errors.serverError') || 'Authentication failed. Please try again.';
    },
    [isOnline, t],
  );

  // Form Submit Handler
  const handleSubmit = async (event) => {
    event.preventDefault();
    if (loading) return;

    const trimmedEmail = email.trim();
    const trimmedPassword = password;

    if (!trimmedEmail) {
      setErrorMessage(t('auth.errors.emailRequired') || 'Please enter your email address.');
      emailInputRef.current?.focus();
      return;
    }

    if (mode === 'forgotPassword') {
      setLoading(true);
      setErrorMessage('');
      setSuccessMessage('');
      try {
        await resetPassword(trimmedEmail);
        setSuccessMessage(
          t('auth.resetLinkSent') || 'Password reset link sent! Check your email inbox.',
        );
        setStatusAnnouncement('Password reset link sent');
      } catch (err) {
        setErrorMessage(translateAuthError(err));
      } finally {
        setLoading(false);
      }
      return;
    }

    if (!trimmedPassword) {
      setErrorMessage(t('auth.errors.passwordRequired') || 'Please enter your password.');
      passwordInputRef.current?.focus();
      return;
    }

    if (mode === 'signUp') {
      const trimmedName = displayName.trim();
      if (!trimmedName) {
        setErrorMessage(t('auth.errors.nameRequired') || 'Please enter your name.');
        nameInputRef.current?.focus();
        return;
      }
      if (trimmedPassword.length < 6) {
        setErrorMessage(
          t('auth.errors.passwordTooShort') || 'Password must be at least 6 characters long.',
        );
        passwordInputRef.current?.focus();
        return;
      }
      if (trimmedPassword !== confirmPassword) {
        setErrorMessage(t('auth.errors.passwordsDoNotMatch') || 'Passwords do not match.');
        return;
      }
      if (!consentChecked) {
        setErrorMessage(t('auth.errors.consentRequired') || 'Please accept the privacy notice.');
        return;
      }

      setLoading(true);
      setErrorMessage('');
      try {
        await signup(trimmedEmail, trimmedPassword, trimmedName, {
          preferredLocale: preferredLocale || language,
        });
        navigate(redirectTo, { replace: true });
      } catch (err) {
        setErrorMessage(translateAuthError(err));
      } finally {
        setLoading(false);
      }
      return;
    }

    // Sign In mode
    setLoading(true);
    setErrorMessage('');
    try {
      await login(trimmedEmail, trimmedPassword);
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setErrorMessage(translateAuthError(err));
    } finally {
      setLoading(false);
    }
  };



  // "Not you? Switch user" action
  const handleSwitchUser = async (forceConfirm = false) => {
    if (status === 'authenticated' && !forceConfirm) {
      const unsynced = await getUnsyncedCount();
      if (unsynced > 0) {
        setSwitchUserConfirmUnsynced(unsynced);
        return;
      }
    }
    setSwitchUserConfirmUnsynced(0);
    await logout();
    setEmail('');
    setPassword('');
    setConfirmPassword('');
    setDisplayName('');
    setErrorMessage('');
    setSuccessMessage('');
    setMode('signIn');
  };

  // Voice narration text for current screen
  const voiceInstructionText = useMemo(() => {
    if (mode === 'signIn') {
      return buildSpeechText([
        t('auth.signInTitle') || 'Welcome back',
        t('auth.signInSubtitle') || 'Sign in with your email and password.',
      ]);
    }
    if (mode === 'signUp') {
      return buildSpeechText([
        t('auth.signUpTitle') || 'Create your account',
        t('auth.signUpSubtitle') || 'Sign up with your name, email, and password.',
      ]);
    }
    return buildSpeechText([
      t('auth.forgotPasswordTitle') || 'Reset your password',
      t('auth.forgotPasswordSubtitle') || 'Enter your email to receive a password reset link.',
    ]);
  }, [mode, t]);

  const privacyUrl = import.meta.env.VITE_PRIVACY_POLICY_URL || '';

  return (
    <div className="space-y-6">
      {/* Screen-reader live region */}
      <div className="sr-only" role="status" aria-live="polite">
        {statusAnnouncement}
      </div>

      {/* Top Bar: Brand + Language Picker + Theme Toggle */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-400 to-emerald-600 text-white shadow-md shadow-emerald-500/20">
            <Sprout size={22} />
          </span>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-lg font-extrabold tracking-tight text-slate-900 dark:text-slate-100">
                {t('dashboard.brand') || 'Field Shift'}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <CompactLanguagePicker
            language={language}
            languages={languages}
            recentLanguages={recentLanguages}
            setLanguage={handleLanguageSelect}
            t={t}
          />
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={isDarkMode ? t('header.lightMode') : t('header.darkMode')}
            title={isDarkMode ? t('header.lightMode') : t('header.darkMode')}
            className="flex h-12 w-12 items-center justify-center rounded-xl border border-slate-200 bg-slate-50 text-slate-600 transition hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
          >
            {isDarkMode ? <Sun size={19} /> : <Moon size={19} />}
          </button>
        </div>
      </div>

      {/* Listen Aloud Button */}
      <div className="flex items-center justify-between gap-3 rounded-2xl border border-emerald-200/80 bg-emerald-50/70 px-4 py-2.5 dark:border-emerald-800/60 dark:bg-emerald-950/40">
        <span className="text-xs font-semibold text-emerald-900 dark:text-emerald-200">
          {t('auth.listenPrompt') || 'Listen'}
        </span>
        <ListenButton
          id="auth-listen-btn"
          text={voiceInstructionText}
          variant="white"
          size="md"
          className="rounded-xl"
        />
      </div>

      {/* Offline Notice Banner */}
      {!isOnline && (
        <div
          role="status"
          aria-live="polite"
          className="flex items-start gap-3 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm font-semibold text-amber-950 dark:border-amber-600/50 dark:bg-amber-950/60 dark:text-amber-100"
        >
          <WifiOff size={20} className="mt-0.5 shrink-0 text-amber-600 dark:text-amber-400" />
          <span>{t('auth.offlineLoginNotice') || 'You are offline. Connect to the internet to sign in.'}</span>
        </div>
      )}

      {/* Already signed-in session card */}
      {status === 'authenticated' && user && (
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-800/60">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
                {t('auth.signedInAs') || 'Signed in as'}
              </p>
              <p className="mt-0.5 text-base font-extrabold text-slate-900 dark:text-white">
                {user.displayName}
              </p>
              <p dir="ltr" className="text-sm font-semibold text-slate-500 dark:text-slate-400">
                {user.email || user.phoneE164}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => navigate(redirectTo, { replace: true })}
                className="inline-flex min-h-12 items-center gap-1.5 rounded-xl bg-emerald-600 px-4 text-sm font-bold text-white transition hover:bg-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                <span>{t('auth.continueToFarm') || 'Continue to Farm'}</span>
                <ArrowRight size={16} />
              </button>
              <button
                type="button"
                onClick={() => handleSwitchUser(false)}
                className="inline-flex min-h-12 items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3.5 text-sm font-bold text-slate-700 transition hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                <UserX size={16} />
                <span>{t('auth.notYouSwitch') || 'Not you? Switch user'}</span>
              </button>
            </div>
          </div>

          {switchUserConfirmUnsynced > 0 && (
            <div
              role="alert"
              className="mt-3 rounded-xl border border-red-300 bg-red-50 p-3 text-xs font-semibold text-red-900 dark:border-red-700 dark:bg-red-950/70 dark:text-red-200"
            >
              <p>{t('settings.unsyncedLogoutWarning', { count: switchUserConfirmUnsynced })}</p>
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  onClick={() => handleSwitchUser(true)}
                  className="rounded-lg bg-red-600 px-3 py-1.5 font-bold text-white hover:bg-red-500"
                >
                  {t('settings.confirmLogout')}
                </button>
                <button
                  type="button"
                  onClick={() => setSwitchUserConfirmUnsynced(0)}
                  className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 font-bold text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                >
                  {t('common.cancel')}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Mode Switcher Tabs (Sign In / Sign Up) */}
      {status !== 'authenticated' && mode !== 'forgotPassword' && (
        <div className="flex rounded-2xl bg-slate-100 p-1 dark:bg-slate-800">
          <button
            type="button"
            onClick={() => {
              setMode('signIn');
              setErrorMessage('');
            }}
            className={`flex-1 rounded-xl py-2.5 text-sm font-extrabold transition ${
              mode === 'signIn'
                ? 'bg-white text-emerald-800 shadow-sm dark:bg-slate-900 dark:text-emerald-300'
                : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white'
            }`}
          >
            {t('auth.signInTab') || 'Sign In'}
          </button>
          <button
            type="button"
            onClick={() => {
              setMode('signUp');
              setErrorMessage('');
            }}
            className={`flex-1 rounded-xl py-2.5 text-sm font-extrabold transition ${
              mode === 'signUp'
                ? 'bg-white text-emerald-800 shadow-sm dark:bg-slate-900 dark:text-emerald-300'
                : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white'
            }`}
          >
            {t('auth.signUpTab') || 'Create Account'}
          </button>
        </div>
      )}

      {/* Main Form Content */}
      <motion.div
        key={mode}
        initial={reduceMotion ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="space-y-5"
      >
        {/* Header Titles */}
        <div>
          <h1 className="text-2xl font-black tracking-tight text-slate-950 dark:text-white sm:text-3xl">
            {mode === 'signIn' && (t('auth.signInTitle') || 'Welcome back')}
            {mode === 'signUp' && (t('auth.signUpTitle') || 'Create your account')}
            {mode === 'forgotPassword' && (t('auth.forgotPasswordTitle') || 'Reset your password')}
          </h1>
          <p className="mt-1.5 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
            {mode === 'signIn' &&
              (t('auth.signInSubtitle') ||
                'Sign in with your email and password to access your farm dashboard.')}
            {mode === 'signUp' &&
              (t('auth.signUpSubtitle') ||
                'Sign up with your email to personalize your farm plan and soil cards.')}
            {mode === 'forgotPassword' &&
              (t('auth.forgotPasswordSubtitle') ||
                'Enter your registered email and we will send you a password reset link.')}
          </p>
        </div>

        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          {/* Display Name (Only in Sign Up Mode) */}
          {mode === 'signUp' && (
            <div>
              <label
                htmlFor="auth-display-name"
                className="mb-1.5 block text-sm font-bold text-slate-800 dark:text-slate-200"
              >
                {t('auth.nameLabel') || 'Your name'}
              </label>
              <div className="relative">
                <User
                  size={19}
                  className="pointer-events-none absolute start-4 top-1/2 -translate-y-1/2 text-slate-400"
                />
                <input
                  ref={nameInputRef}
                  id="auth-display-name"
                  name="name"
                  type="text"
                  autoComplete="name"
                  disabled={loading}
                  value={displayName}
                  onChange={(e) => {
                    setDisplayName(e.target.value);
                    if (errorMessage) setErrorMessage('');
                  }}
                  placeholder={t('auth.namePlaceholder') || 'e.g. Ramesh Naik'}
                  className="min-h-[52px] w-full rounded-2xl border border-slate-300 bg-slate-50 ps-12 pe-4 text-base font-bold text-slate-900 outline-none transition placeholder:font-normal placeholder:text-slate-400 focus:border-emerald-500 focus:bg-white focus:ring-4 focus:ring-emerald-500/15 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:focus:bg-slate-900"
                />
              </div>
            </div>
          )}

          {/* Email Address Input */}
          <div>
            <label
              htmlFor="auth-email-input"
              className="mb-1.5 block text-sm font-bold text-slate-800 dark:text-slate-200"
            >
              {t('auth.emailLabel') || 'Email address'}
            </label>
            <div className="relative">
              <Mail
                size={19}
                className="pointer-events-none absolute start-4 top-1/2 -translate-y-1/2 text-slate-400"
              />
              <input
                ref={emailInputRef}
                id="auth-email-input"
                name="email"
                type="email"
                inputMode="email"
                autoComplete="email"
                dir="ltr"
                disabled={loading}
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (errorMessage) setErrorMessage('');
                }}
                placeholder={t('auth.emailPlaceholder') || 'farmer@example.com'}
                className="min-h-[52px] w-full rounded-2xl border border-slate-300 bg-slate-50 ps-12 pe-4 text-base font-bold text-slate-900 outline-none transition placeholder:font-normal placeholder:text-slate-400 focus:border-emerald-500 focus:bg-white focus:ring-4 focus:ring-emerald-500/15 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:focus:bg-slate-900"
              />
            </div>
          </div>

          {/* Password Input (Sign In & Sign Up Modes) */}
          {mode !== 'forgotPassword' && (
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <label
                  htmlFor="auth-password-input"
                  className="block text-sm font-bold text-slate-800 dark:text-slate-200"
                >
                  {t('auth.passwordLabel') || 'Password'}
                </label>
                {mode === 'signIn' && (
                  <button
                    type="button"
                    onClick={() => {
                      setMode('forgotPassword');
                      setErrorMessage('');
                    }}
                    className="text-xs font-bold text-emerald-700 hover:underline dark:text-emerald-400"
                  >
                    {t('auth.forgotPasswordLink') || 'Forgot password?'}
                  </button>
                )}
              </div>
              <div className="relative">
                <Lock
                  size={19}
                  className="pointer-events-none absolute start-4 top-1/2 -translate-y-1/2 text-slate-400"
                />
                <input
                  ref={passwordInputRef}
                  id="auth-password-input"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete={mode === 'signIn' ? 'current-password' : 'new-password'}
                  dir="ltr"
                  disabled={loading}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (errorMessage) setErrorMessage('');
                  }}
                  placeholder={t('auth.passwordPlaceholder') || 'Enter your password'}
                  className="min-h-[52px] w-full rounded-2xl border border-slate-300 bg-slate-50 ps-12 pe-12 text-base font-bold text-slate-900 outline-none transition placeholder:font-normal placeholder:text-slate-400 focus:border-emerald-500 focus:bg-white focus:ring-4 focus:ring-emerald-500/15 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:focus:bg-slate-900"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  aria-label={showPassword ? t('auth.hidePassword') : t('auth.showPassword')}
                  className="absolute end-3 top-1/2 -translate-y-1/2 rounded-xl p-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>
          )}

          {/* Confirm Password (Sign Up Mode only) */}
          {mode === 'signUp' && (
            <div>
              <label
                htmlFor="auth-confirm-password-input"
                className="mb-1.5 block text-sm font-bold text-slate-800 dark:text-slate-200"
              >
                {t('auth.confirmPasswordLabel') || 'Confirm password'}
              </label>
              <div className="relative">
                <Lock
                  size={19}
                  className="pointer-events-none absolute start-4 top-1/2 -translate-y-1/2 text-slate-400"
                />
                <input
                  id="auth-confirm-password-input"
                  name="confirmPassword"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  dir="ltr"
                  disabled={loading}
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value);
                    if (errorMessage) setErrorMessage('');
                  }}
                  placeholder={t('auth.confirmPasswordPlaceholder') || 'Re-enter your password'}
                  className="min-h-[52px] w-full rounded-2xl border border-slate-300 bg-slate-50 ps-12 pe-4 text-base font-bold text-slate-900 outline-none transition placeholder:font-normal placeholder:text-slate-400 focus:border-emerald-500 focus:bg-white focus:ring-4 focus:ring-emerald-500/15 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:focus:bg-slate-900"
                />
              </div>
            </div>
          )}

          {/* Terms & Consent (Sign Up Mode only) */}
          {mode === 'signUp' && (
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-800/50">
              <label
                htmlFor="auth-consent-checkbox"
                className="flex cursor-pointer items-start gap-3"
              >
                <input
                  id="auth-consent-checkbox"
                  type="checkbox"
                  checked={consentChecked}
                  onChange={(e) => {
                    setConsentChecked(e.target.checked);
                    if (errorMessage) setErrorMessage('');
                  }}
                  className="mt-1 h-5 w-5 shrink-0 rounded border-slate-300 text-emerald-600 focus:ring-2 focus:ring-emerald-500"
                />
                <span className="text-sm font-medium leading-relaxed text-slate-700 dark:text-slate-200">
                  {t('auth.consentCheckboxLabel') || 'I agree to Field Shift farm alerts and accept the'}{' '}
                  {privacyUrl ? (
                    <a
                      href={privacyUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-bold text-emerald-700 underline dark:text-emerald-400"
                    >
                      {t('auth.privacyPolicyLink') || 'Privacy Notice'}
                    </a>
                  ) : (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.preventDefault();
                        setIsPrivacyModalOpen(true);
                      }}
                      className="font-bold text-emerald-700 underline focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:text-emerald-400"
                    >
                      {t('auth.privacyPolicyLink') || 'Privacy Notice'}
                    </button>
                  )}
                </span>
              </label>
            </div>
          )}

          {/* Success Message Banner (e.g. for Password Reset) */}
          <AnimatePresence>
            {successMessage && (
              <motion.div
                role="status"
                aria-live="polite"
                initial={reduceMotion ? false : { opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="flex items-start gap-2.5 rounded-2xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm font-bold text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-200"
              >
                <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                <span>{successMessage}</span>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Error Message Banner */}
          <AnimatePresence>
            {errorMessage && (
              <motion.div
                role="alert"
                aria-live="assertive"
                initial={reduceMotion ? false : { opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="flex items-start gap-2.5 rounded-2xl border border-red-300 bg-red-50 px-4 py-3 text-sm font-bold text-red-800 dark:border-red-800 dark:bg-red-950/60 dark:text-red-200"
              >
                <AlertCircle size={18} className="mt-0.5 shrink-0 text-red-600 dark:text-red-400" />
                <span>{errorMessage}</span>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Submit Action Button */}
          <button
            type="submit"
            id="auth-submit-btn"
            disabled={loading}
            className="flex min-h-[54px] w-full items-center justify-center gap-2.5 rounded-2xl bg-gradient-to-r from-emerald-600 to-emerald-500 px-5 text-lg font-extrabold text-white shadow-lg shadow-emerald-700/20 transition hover:from-emerald-500 hover:to-emerald-500 focus:outline-none focus:ring-4 focus:ring-emerald-500/30 disabled:cursor-not-allowed disabled:opacity-65"
          >
            {loading ? (
              <>
                <Loader2 size={22} className="animate-spin" />
                <span>
                  {mode === 'signIn' && (t('auth.signingIn') || 'Signing in…')}
                  {mode === 'signUp' && (t('auth.creatingAccount') || 'Creating account…')}
                  {mode === 'forgotPassword' && (t('auth.sendingResetLink') || 'Sending reset link…')}
                </span>
              </>
            ) : (
              <>
                {mode === 'signIn' && (
                  <>
                    <span>{t('auth.signIn') || 'Sign In'}</span>
                    <ArrowRight size={20} />
                  </>
                )}
                {mode === 'signUp' && (
                  <>
                    <span>{t('auth.createAccount') || 'Create Account'}</span>
                    <ArrowRight size={20} />
                  </>
                )}
                {mode === 'forgotPassword' && (
                  <>
                    <Send size={18} />
                    <span>{t('auth.sendResetLink') || 'Send Reset Link'}</span>
                  </>
                )}
              </>
            )}
          </button>

          {/* Mode Switcher Footer Links */}
          <div className="pt-2 text-center text-sm">
            {mode === 'signIn' && (
              <p className="text-slate-600 dark:text-slate-400">
                {t('auth.dontHaveAccount') || "Don't have an account?"}{' '}
                <button
                  type="button"
                  onClick={() => {
                    setMode('signUp');
                    setErrorMessage('');
                  }}
                  className="font-extrabold text-emerald-700 underline underline-offset-2 hover:text-emerald-800 dark:text-emerald-400"
                >
                  {t('auth.signUpTab') || 'Create Account'}
                </button>
              </p>
            )}

            {mode === 'signUp' && (
              <p className="text-slate-600 dark:text-slate-400">
                {t('auth.alreadyHaveAccount') || 'Already have an account?'}{' '}
                <button
                  type="button"
                  onClick={() => {
                    setMode('signIn');
                    setErrorMessage('');
                  }}
                  className="font-extrabold text-emerald-700 underline underline-offset-2 hover:text-emerald-800 dark:text-emerald-400"
                >
                  {t('auth.signInTab') || 'Sign In'}
                </button>
              </p>
            )}

            {mode === 'forgotPassword' && (
              <button
                type="button"
                onClick={() => {
                  setMode('signIn');
                  setErrorMessage('');
                }}
                className="font-extrabold text-emerald-700 underline underline-offset-2 hover:text-emerald-800 dark:text-emerald-400"
              >
                ← {t('auth.backToSignIn') || 'Back to Sign In'}
              </button>
            )}
          </div>
        </form>
      </motion.div>

      {/* Privacy Notice Modal */}
      <PrivacyModal
        isOpen={isPrivacyModalOpen}
        onClose={() => setIsPrivacyModalOpen(false)}
        t={t}
      />
    </div>
  );
}
