import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  Globe2,
  Loader2,
  MessageSquareText,
  Moon,
  Phone,
  PhoneCall,
  RefreshCw,
  Search,
  ShieldCheck,
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
import {
  AUTH_COUNTRY_STORAGE_KEY,
  detectDefaultCountry,
  formatPhoneAsYouType,
  formatPhoneDisplay,
  getCountryName,
  getCountryOptions,
  maskPhoneE164,
  validateAndFormatPhone,
} from '../../utils/phone';

const OTP_LENGTH = 6;
const DEFAULT_RESEND_SECONDS = 30;
const MAX_RESENDS_PER_PHONE = 3;

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
            <Search
              size={16}
              className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-slate-400"
            />
            <input
              ref={searchInputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t('settings.searchLanguages')}
              aria-label={t('settings.searchLanguages')}
              className="h-11 w-full rounded-xl border border-slate-200 bg-slate-50 ps-9 pe-3 text-sm font-medium text-slate-900 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
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

/* ─── Searchable Country Dial-Code Picker ────────────────────── */
function CountryDialPicker({ countryCode, onChange, locale, t, disabled }) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const containerRef = useRef(null);
  const searchRef = useRef(null);

  const countries = useMemo(() => getCountryOptions(locale), [locale]);
  const selectedCountry = useMemo(
    () => countries.find((c) => c.code === countryCode) || countries[0],
    [countries, countryCode],
  );

  const filteredCountries = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return countries;
    return countries.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.englishName.toLowerCase().includes(q) ||
        c.code.toLowerCase().includes(q) ||
        c.dialCode.includes(q.replace(/^\+?/, '')),
    );
  }, [countries, query]);

  useEffect(() => {
    if (!isOpen) return undefined;
    const handleOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    const handleEscape = (event) => {
      if (event.key === 'Escape') setIsOpen(false);
    };
    document.addEventListener('mousedown', handleOutside);
    window.addEventListener('keydown', handleEscape);
    setTimeout(() => searchRef.current?.focus(), 40);
    return () => {
      document.removeEventListener('mousedown', handleOutside);
      window.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen]);

  return (
    <div ref={containerRef} className="relative shrink-0">
      <button
        type="button"
        id="country-dial-code-btn"
        disabled={disabled}
        onClick={() => setIsOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-label={`${t('auth.countryCodeLabel')}: ${selectedCountry?.name} ${selectedCountry?.dialCode}`}
        className="flex min-h-[54px] items-center gap-1.5 rounded-2xl border border-slate-300 bg-slate-50 px-3.5 text-[18px] font-bold text-slate-900 transition hover:border-slate-400 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700"
      >
        <span className="text-xl leading-none" aria-hidden="true">
          {selectedCountry?.flag}
        </span>
        <span dir="ltr" className="font-extrabold tracking-tight">
          {selectedCountry?.dialCode}
        </span>
        <ChevronDown size={16} className="text-slate-500 dark:text-slate-400" />
      </button>

      {isOpen && (
        <div
          role="dialog"
          aria-label={t('auth.searchCountry')}
          className="absolute start-0 top-full z-50 mt-2 w-72 sm:w-80 rounded-2xl border border-slate-200 bg-white p-2 shadow-2xl dark:border-slate-700 dark:bg-slate-900"
        >
          <div className="relative mb-2">
            <Search
              size={16}
              className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-slate-400"
            />
            <input
              ref={searchRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t('auth.searchCountry')}
              aria-label={t('auth.searchCountry')}
              className="h-11 w-full rounded-xl border border-slate-200 bg-slate-50 ps-9 pe-3 text-sm font-medium text-slate-900 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
            />
          </div>

          <div
            role="listbox"
            aria-label={t('auth.countryCodeLabel')}
            className="max-h-64 overflow-y-auto overscroll-contain language-picker-scrollbar"
          >
            {filteredCountries.length === 0 && (
              <p className="px-3 py-4 text-center text-sm text-slate-500 dark:text-slate-400">
                {t('auth.noCountryFound')}
              </p>
            )}
            {filteredCountries.map((c) => {
              const isSelected = c.code === countryCode;
              return (
                <button
                  key={c.code}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  onClick={() => {
                    onChange(c.code);
                    setQuery('');
                    setIsOpen(false);
                  }}
                  className={`flex min-h-12 w-full items-center justify-between gap-2 rounded-xl px-3 py-2 text-start transition ${
                    isSelected
                      ? 'bg-emerald-50 font-bold text-emerald-900 dark:bg-emerald-950/70 dark:text-emerald-200'
                      : 'hover:bg-slate-100 dark:hover:bg-slate-800'
                  }`}
                >
                  <span className="flex min-w-0 items-center gap-2.5">
                    <span className="text-xl leading-none" aria-hidden="true">
                      {c.flag}
                    </span>
                    <span className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
                      {c.name}
                    </span>
                  </span>
                  <span
                    dir="ltr"
                    className="flex shrink-0 items-center gap-1.5 text-sm font-bold text-slate-600 dark:text-slate-300"
                  >
                    <span>{c.dialCode}</span>
                    {isSelected && <Check size={16} className="text-emerald-600 dark:text-emerald-400" />}
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

/* ─── Privacy & SMS Terms Modal ──────────────────────────────── */
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
              {t('auth.privacyModalTitle')}
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
          <p>{t('auth.privacyModalPoint1')}</p>
          <p>{t('auth.privacyModalPoint2')}</p>
          <p>{t('auth.privacyModalPoint3')}</p>
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

/* ─── Main Unified Phone + OTP Login / Sign-Up Screen ────────── */
export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const reduceMotion = useLowEndOrReducedMotion();

  const {
    user,
    status,
    isMock,
    requestOtp,
    verifyOtp,
    completeProfile,
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

  // Step state: 'phone' | 'otp' | 'profile'
  const [step, setStep] = useState('phone');
  const [countryCode, setCountryCode] = useState(() => detectDefaultCountry(language));
  const [userManuallyChangedCountry, setUserManuallyChangedCountry] = useState(false);
  const [phoneInput, setPhoneInput] = useState('');
  const [phoneE164, setPhoneE164] = useState('');
  const [formattedPhone, setFormattedPhone] = useState('');

  // OTP state
  const [otpDigits, setOtpDigits] = useState(() => Array(OTP_LENGTH).fill(''));
  const [resendCooldown, setResendCooldown] = useState(0);
  const [resendCountsByPhone, setResendCountsByPhone] = useState({});
  const [voiceAvailable, setVoiceAvailable] = useState(false);

  // New user profile state (Step 2b)
  const [displayName, setDisplayName] = useState('');
  const [preferredLocale, setPreferredLocale] = useState(language);
  const [consentChecked, setConsentChecked] = useState(false);
  const [isPrivacyModalOpen, setIsPrivacyModalOpen] = useState(false);

  // Request / error / network state
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [statusAnnouncement, setStatusAnnouncement] = useState('');
  const [isOnline, setIsOnline] = useState(() =>
    typeof navigator !== 'undefined' ? navigator.onLine : true,
  );
  const [switchUserConfirmUnsynced, setSwitchUserConfirmUnsynced] = useState(0);

  const inFlightRef = useRef(false);
  const phoneInputRef = useRef(null);
  const otpInputRefs = useRef([]);
  const nameInputRef = useRef(null);

  const handleLanguageSelect = useCallback(
    async (nextLang) => {
      stopAllSpeech();
      await setLanguage(nextLang);
      setPreferredLocale(nextLang);
      if (!userManuallyChangedCountry && !phoneInput.trim()) {
        setCountryCode(detectDefaultCountry(nextLang));
      }
    },
    [phoneInput, setLanguage, userManuallyChangedCountry],
  );

  // Track online/offline state
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

  // Resend countdown timer
  useEffect(() => {
    if (resendCooldown <= 0) return undefined;
    const timer = window.setInterval(() => {
      setResendCooldown((prev) => {
        if (prev <= 1) {
          setStatusAnnouncement(t('auth.resendReadyAnnouncement'));
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [resendCooldown, t]);

  // Focus management when changing steps
  useEffect(() => {
    if (step === 'phone') {
      const id = setTimeout(() => phoneInputRef.current?.focus(), 60);
      return () => clearTimeout(id);
    }
    if (step === 'otp') {
      const id = setTimeout(() => otpInputRefs.current[0]?.focus(), 60);
      return () => clearTimeout(id);
    }
    if (step === 'profile') {
      const id = setTimeout(() => nameInputRef.current?.focus(), 60);
      return () => clearTimeout(id);
    }
    return undefined;
  }, [step]);

  // Map API errors to clear translated messages
  const translateAuthError = useCallback(
    (err) => {
      const code = err?.code;
      if (code === 'network' || (!isOnline && !isMock)) {
        return t('auth.errors.noNetwork');
      }
      if (code === 'timeout') {
        return t('auth.errors.timeout');
      }
      if (code === 'invalid_phone') {
        return t('auth.errors.phoneInvalidForCountry', {
          country: getCountryName(countryCode, language),
        });
      }
      if (code === 'otp_invalid') {
        const remaining = err?.details?.attemptsRemaining;
        if (typeof remaining === 'number') {
          return t('auth.errors.wrongCodeWithAttempts', { count: remaining });
        }
        return t('auth.errors.wrongCode');
      }
      if (code === 'otp_expired') {
        return t('auth.errors.expiredCode');
      }
      if (code === 'otp_attempts_exceeded' || code === 'rate_limited') {
        const seconds = err?.retryAfterSeconds || 60;
        return t('auth.errors.tooManyAttempts', { seconds });
      }
      return t('auth.errors.serverError');
    },
    [countryCode, isMock, isOnline, language, t],
  );

  // Verify 6-digit OTP code
  const submitOtpCode = useCallback(
    async (sixDigitCode) => {
      const cleanCode = String(sixDigitCode || '').replace(/\D/g, '');
      if (cleanCode.length !== OTP_LENGTH) {
        setErrorMessage(t('auth.errors.codeIncomplete'));
        return;
      }
      if (inFlightRef.current) return;

      if (!isOnline && !isMock) {
        setErrorMessage(t('auth.errors.noNetwork'));
        return;
      }

      inFlightRef.current = true;
      setLoading(true);
      setErrorMessage('');

      try {
        const result = await verifyOtp(phoneE164, cleanCode, {
          preferredLocale: language,
          countryCode,
        });

        if (result.isNewUser) {
          setPreferredLocale(language);
          setStep('profile');
          setStatusAnnouncement(t('auth.profileStepTitle'));
        } else {
          navigate(redirectTo, { replace: true });
        }
      } catch (err) {
        setErrorMessage(translateAuthError(err));
      } finally {
        setLoading(false);
        inFlightRef.current = false;
      }
    },
    [countryCode, isMock, isOnline, language, navigate, phoneE164, redirectTo, t, translateAuthError, verifyOtp],
  );

  // Web OTP API auto-read on Android/supported browsers
  useEffect(() => {
    if (step !== 'otp') return undefined;
    if (
      typeof window === 'undefined' ||
      !('OTPCredential' in window) ||
      !navigator.credentials ||
      typeof navigator.credentials.get !== 'function'
    ) {
      return undefined;
    }

    const abortController = new AbortController();
    navigator.credentials
      .get({
        otp: { transport: ['sms'] },
        signal: abortController.signal,
      })
      .then((credential) => {
        const received = String(credential?.code || '').replace(/\D/g, '').slice(0, OTP_LENGTH);
        if (received.length === OTP_LENGTH) {
          setOtpDigits(received.split(''));
          submitOtpCode(received);
        }
      })
      .catch(() => {
        // Fallback gracefully when Web OTP is aborted or unsupported
      });

    return () => {
      abortController.abort();
    };
  }, [step, submitOtpCode]);

  // Handle country selection change
  const handleCountryChange = (nextCountryCode) => {
    setCountryCode(nextCountryCode);
    setUserManuallyChangedCountry(true);
    try {
      window.localStorage.setItem(AUTH_COUNTRY_STORAGE_KEY, nextCountryCode);
    } catch {
      // Ignore storage errors
    }
    if (phoneInput.trim()) {
      const { formatted } = formatPhoneAsYouType(phoneInput, nextCountryCode);
      setPhoneInput(formatted);
    }
    if (errorMessage) setErrorMessage('');
  };

  // Handle phone input typing/pasting
  const handlePhoneInputChange = (event) => {
    const raw = event.target.value;
    const { formatted, detectedCountry } = formatPhoneAsYouType(raw, countryCode);
    if (detectedCountry && detectedCountry !== countryCode) {
      setCountryCode(detectedCountry);
      setUserManuallyChangedCountry(true);
    }
    setPhoneInput(formatted);
    if (errorMessage) setErrorMessage('');
  };

  // Step 1 submit -> Request OTP
  const handleRequestOtp = async (event) => {
    event?.preventDefault();
    if (inFlightRef.current) return;

    const validation = validateAndFormatPhone(phoneInput, countryCode);
    if (!validation.valid) {
      setErrorMessage(
        t(validation.errorKey, {
          country: getCountryName(countryCode, language),
        }),
      );
      phoneInputRef.current?.focus();
      return;
    }

    if (!isOnline && !isMock) {
      setErrorMessage(t('auth.errors.noNetwork'));
      return;
    }

    inFlightRef.current = true;
    setLoading(true);
    setErrorMessage('');

    try {
      const response = await requestOtp(validation.phoneE164, {
        channel: 'sms',
        locale: language,
      });

      setPhoneE164(validation.phoneE164);
      setFormattedPhone(validation.formattedInternational || formatPhoneDisplay(validation.phoneE164));
      setVoiceAvailable(Boolean(response?.voiceAvailable));
      setOtpDigits(Array(OTP_LENGTH).fill(''));
      setResendCooldown(response?.resendAfterSeconds ?? DEFAULT_RESEND_SECONDS);
      setStep('otp');
      setStatusAnnouncement(
        t('auth.codeSentTo', {
          phone: validation.formattedInternational || validation.phoneE164,
        }),
      );
    } catch (err) {
      setErrorMessage(translateAuthError(err));
    } finally {
      setLoading(false);
      inFlightRef.current = false;
    }
  };

  // Handle OTP box changes (single digit or multi-digit autofill)
  const handleOtpChange = (index, rawValue) => {
    if (errorMessage) setErrorMessage('');
    const digitsOnly = String(rawValue || '').replace(/\D/g, '');

    if (digitsOnly.length > 1) {
      // Multi-digit paste or SMS autofill
      const nextDigits = [...otpDigits];
      for (let i = 0; i < OTP_LENGTH; i += 1) {
        const char = digitsOnly[i];
        if (char !== undefined) {
          nextDigits[i] = char;
        }
      }
      setOtpDigits(nextDigits);
      const focusIdx = Math.min(digitsOnly.length, OTP_LENGTH) - 1;
      otpInputRefs.current[focusIdx]?.focus();

      const joined = nextDigits.join('');
      if (joined.length === OTP_LENGTH && ! nextDigits.includes('')) {
        submitOtpCode(joined);
      }
      return;
    }

    const digit = digitsOnly.slice(-1);
    const nextDigits = [...otpDigits];
    nextDigits[index] = digit;
    setOtpDigits(nextDigits);

    if (digit && index < OTP_LENGTH - 1) {
      otpInputRefs.current[index + 1]?.focus();
    }

    const joined = nextDigits.join('');
    if (digit && joined.length === OTP_LENGTH && !nextDigits.includes('')) {
      submitOtpCode(joined);
    }
  };

  // Handle OTP keydown (Backspace, ArrowLeft, ArrowRight)
  const handleOtpKeyDown = (index, event) => {
    if (event.key === 'Backspace') {
      if (otpDigits[index]) {
        const nextDigits = [...otpDigits];
        nextDigits[index] = '';
        setOtpDigits(nextDigits);
      } else if (index > 0) {
        event.preventDefault();
        const nextDigits = [...otpDigits];
        nextDigits[index - 1] = '';
        setOtpDigits(nextDigits);
        otpInputRefs.current[index - 1]?.focus();
      }
    } else if (event.key === 'ArrowLeft' && index > 0) {
      event.preventDefault();
      otpInputRefs.current[index - 1]?.focus();
    } else if (event.key === 'ArrowRight' && index < OTP_LENGTH - 1) {
      event.preventDefault();
      otpInputRefs.current[index + 1]?.focus();
    }
  };

  // Handle paste anywhere in the OTP boxes
  const handleOtpPaste = (event) => {
    event.preventDefault();
    const pastedText = event.clipboardData?.getData('text') || '';
    const digitsOnly = pastedText.replace(/\D/g, '').slice(0, OTP_LENGTH);
    if (!digitsOnly) return;

    const nextDigits = Array(OTP_LENGTH)
      .fill('')
      .map((_, idx) => digitsOnly[idx] || '');
    setOtpDigits(nextDigits);
    if (errorMessage) setErrorMessage('');

    const focusIdx = Math.min(digitsOnly.length, OTP_LENGTH) - 1;
    otpInputRefs.current[Math.max(0, focusIdx)]?.focus();

    if (digitsOnly.length === OTP_LENGTH) {
      submitOtpCode(digitsOnly);
    }
  };

  // Resend OTP (SMS or Voice)
  const resendsUsed = resendCountsByPhone[phoneE164] || 0;
  const canResendMore = resendsUsed < MAX_RESENDS_PER_PHONE;

  const handleResendOtp = async (channel = 'sms') => {
    if (inFlightRef.current || resendCooldown > 0) return;
    if (!canResendMore) {
      setErrorMessage(t('auth.errors.maxResendsReached'));
      return;
    }
    if (!isOnline && !isMock) {
      setErrorMessage(t('auth.errors.noNetwork'));
      return;
    }

    inFlightRef.current = true;
    setLoading(true);
    setErrorMessage('');

    try {
      const response = await requestOtp(phoneE164, {
        channel,
        locale: language,
      });
      setResendCountsByPhone((prev) => ({
        ...prev,
        [phoneE164]: (prev[phoneE164] || 0) + 1,
      }));
      setOtpDigits(Array(OTP_LENGTH).fill(''));
      setResendCooldown(response?.resendAfterSeconds ?? DEFAULT_RESEND_SECONDS);
      setStatusAnnouncement(t('auth.codeResentAnnouncement'));
      otpInputRefs.current[0]?.focus();
    } catch (err) {
      setErrorMessage(translateAuthError(err));
    } finally {
      setLoading(false);
      inFlightRef.current = false;
    }
  };

  // Return to phone step ("Change number")
  const handleChangeNumber = () => {
    setStep('phone');
    setOtpDigits(Array(OTP_LENGTH).fill(''));
    setErrorMessage('');
  };

  // "Not you? Switch user" action (logs out current user and resets to phone step)
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
    setStep('phone');
    setPhoneInput('');
    setPhoneE164('');
    setFormattedPhone('');
    setDisplayName('');
    setConsentChecked(false);
    setOtpDigits(Array(OTP_LENGTH).fill(''));
    setErrorMessage('');
  };

  // Step 2b submit -> Complete new user registration
  const handleCompleteProfile = async (event) => {
    event.preventDefault();
    if (inFlightRef.current) return;

    const trimmedName = displayName.trim();
    if (!trimmedName) {
      setErrorMessage(t('auth.errors.nameRequired'));
      nameInputRef.current?.focus();
      return;
    }
    if (!consentChecked) {
      setErrorMessage(t('auth.errors.consentRequired'));
      return;
    }
    if (!isOnline && !isMock) {
      setErrorMessage(t('auth.errors.noNetwork'));
      return;
    }

    inFlightRef.current = true;
    setLoading(true);
    setErrorMessage('');

    try {
      const nowIso = new Date().toISOString();
      await completeProfile({
        displayName: trimmedName,
        preferredLocale: preferredLocale || language,
        countryCode,
        consents: {
          privacyNoticeVersion: '2026-10',
          dataProcessing: true,
          smsMessages: true,
          acceptedAt: nowIso,
        },
      });

      if (preferredLocale && preferredLocale !== language) {
        await setLanguage(preferredLocale);
      }

      navigate(redirectTo, { replace: true });
    } catch (err) {
      setErrorMessage(translateAuthError(err));
    } finally {
      setLoading(false);
      inFlightRef.current = false;
    }
  };

  // Voice narration text for current step
  const voiceInstructionText = useMemo(() => {
    if (step === 'phone') {
      return buildSpeechText([t('auth.phoneStepTitle'), t('auth.phoneStepSubtitle')]);
    }
    if (step === 'otp') {
      return buildSpeechText([
        t('auth.otpStepTitle'),
        t('auth.codeSentTo', { phone: formattedPhone }),
        t('auth.otpStepSubtitle'),
      ]);
    }
    return buildSpeechText([t('auth.profileStepTitle'), t('auth.profileStepSubtitle')]);
  }, [formattedPhone, step, t]);

  const privacyUrl = import.meta.env.VITE_PRIVACY_POLICY_URL || '';

  return (
    <div className="space-y-6">
      {/* Screen-reader live region for countdown & step announcements */}
      <div className="sr-only" role="status" aria-live="polite">
        {statusAnnouncement}
      </div>

      {/* Top Bar: Logo + Demo Badge + Language Picker + Theme + Listen */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-400 to-emerald-600 text-white shadow-md shadow-emerald-500/20">
            <Sprout size={22} />
          </span>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-lg font-extrabold tracking-tight text-slate-900 dark:text-slate-100">
                {t('dashboard.brand')}
              </span>
              {isMock && (
                <span
                  id="auth-demo-badge"
                  className="inline-flex items-center rounded-full border border-amber-300 bg-amber-100 px-2.5 py-0.5 text-xs font-extrabold uppercase tracking-wider text-amber-900 dark:border-amber-500/50 dark:bg-amber-950 dark:text-amber-200"
                >
                  {t('auth.demoBadge')}
                </span>
              )}
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

      {/* Listen Aloud Button for Low-Literacy Support */}
      <div className="flex items-center justify-between gap-3 rounded-2xl border border-emerald-200/80 bg-emerald-50/70 px-4 py-2.5 dark:border-emerald-800/60 dark:bg-emerald-950/40">
        <span className="text-xs font-semibold text-emerald-900 dark:text-emerald-200">
          {t('auth.listenPrompt')}
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
          <span>{t('auth.offlineLoginNotice')}</span>
        </div>
      )}

      {/* Demo Mode Hint Banner (Strictly only when VITE_USE_MOCKS=true) */}
      {isMock && (
        <div
          id="auth-demo-hint"
          role="note"
          className="flex items-center justify-between gap-3 rounded-2xl border border-amber-300/90 bg-amber-50/90 px-4 py-3 text-sm font-bold text-amber-950 dark:border-amber-500/40 dark:bg-amber-950/50 dark:text-amber-100"
        >
          <span>{t('auth.demoHint', { code: '123456' })}</span>
          {step === 'otp' && (
            <button
              type="button"
              onClick={() => {
                setOtpDigits(['1', '2', '3', '4', '5', '6']);
                submitOtpCode('123456');
              }}
              className="shrink-0 rounded-xl bg-amber-600 px-3 py-1.5 text-xs font-extrabold text-white transition hover:bg-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500"
            >
              123456
            </button>
          )}
        </div>
      )}

      {/* Already signed-in session card with "Not you? Switch user" */}
      {status === 'authenticated' && user && step === 'phone' && (
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-800/60">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
                {t('auth.signedInAs')}
              </p>
              <p className="mt-0.5 text-base font-extrabold text-slate-900 dark:text-white">
                {user.displayName}
              </p>
              <p dir="ltr" className="text-sm font-semibold text-slate-500 dark:text-slate-400">
                {maskPhoneE164(user.phoneE164)}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => navigate(redirectTo, { replace: true })}
                className="inline-flex min-h-12 items-center gap-1.5 rounded-xl bg-emerald-600 px-4 text-sm font-bold text-white transition hover:bg-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                <span>{t('auth.continueToFarm')}</span>
                <ArrowRight size={16} />
              </button>
              <button
                type="button"
                onClick={() => handleSwitchUser(false)}
                className="inline-flex min-h-12 items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3.5 text-sm font-bold text-slate-700 transition hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                <UserX size={16} />
                <span>{t('auth.notYouSwitch')}</span>
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

      {/* ─── STEP 1: PHONE NUMBER ─────────────────────────────────── */}
      {step === 'phone' && (
        <motion.div
          key="step-phone"
          initial={reduceMotion ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
          className="space-y-5"
        >
          <div className="flex items-start gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
              <Phone size={28} />
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
                {t('auth.step1Badge')}
              </p>
              <h1 className="mt-0.5 text-2xl font-black tracking-tight text-slate-950 dark:text-white sm:text-3xl">
                {t('auth.phoneStepTitle')}
              </h1>
              <p className="mt-1.5 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
                {t('auth.phoneStepSubtitle')}
              </p>
            </div>
          </div>

          <form onSubmit={handleRequestOtp} noValidate className="space-y-4">
            <div>
              <label
                htmlFor="auth-phone-input"
                className="mb-2 block text-sm font-bold text-slate-800 dark:text-slate-200"
              >
                {t('auth.phoneLabel')}
              </label>

              {/* Keep dial code + phone digits strictly left-to-right even in RTL locales */}
              <div dir="ltr" className="flex items-stretch gap-2">
                <CountryDialPicker
                  countryCode={countryCode}
                  onChange={handleCountryChange}
                  locale={language}
                  t={t}
                  disabled={loading}
                />

                <div className="relative flex-1">
                  <input
                    ref={phoneInputRef}
                    id="auth-phone-input"
                    name="phone"
                    type="tel"
                    inputMode="tel"
                    autoComplete="tel"
                    dir="ltr"
                    disabled={loading}
                    value={phoneInput}
                    onChange={handlePhoneInputChange}
                    placeholder={t('auth.phonePlaceholder')}
                    aria-invalid={Boolean(errorMessage)}
                    aria-describedby={errorMessage ? 'auth-phone-error' : undefined}
                    className={`min-h-[54px] w-full rounded-2xl border bg-slate-50 px-4 text-[18px] font-bold tracking-wide text-slate-900 outline-none transition placeholder:font-normal placeholder:text-slate-400 focus:bg-white focus:ring-4 dark:bg-slate-950 dark:text-slate-100 dark:focus:bg-slate-900 ${
                      errorMessage
                        ? 'border-red-500 focus:border-red-500 focus:ring-red-500/15'
                        : 'border-slate-300 focus:border-emerald-500 focus:ring-emerald-500/15 dark:border-slate-700'
                    }`}
                  />
                </div>
              </div>
            </div>

            {/* Inline Validation / Network Error */}
            <AnimatePresence>
              {errorMessage && (
                <motion.div
                  id="auth-phone-error"
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

            <button
              type="submit"
              id="auth-send-code-btn"
              disabled={loading}
              className="flex min-h-[54px] w-full items-center justify-center gap-2.5 rounded-2xl bg-gradient-to-r from-emerald-600 to-emerald-500 px-5 text-lg font-extrabold text-white shadow-lg shadow-emerald-700/20 transition hover:from-emerald-500 hover:to-emerald-500 focus:outline-none focus:ring-4 focus:ring-emerald-500/30 disabled:cursor-not-allowed disabled:opacity-65"
            >
              {loading ? (
                <>
                  <Loader2 size={22} className="animate-spin" />
                  <span>{t('auth.sendingCode')}</span>
                </>
              ) : (
                <>
                  <MessageSquareText size={20} />
                  <span>{t('auth.sendCode')}</span>
                  <ArrowRight size={20} />
                </>
              )}
            </button>
          </form>
        </motion.div>
      )}

      {/* ─── STEP 2: 6-DIGIT OTP VERIFICATION ─────────────────────── */}
      {step === 'otp' && (
        <motion.div
          key="step-otp"
          initial={reduceMotion ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
          className="space-y-5"
        >
          <div className="flex items-start gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
              <MessageSquareText size={28} />
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
                {t('auth.step2Badge')}
              </p>
              <h1 className="mt-0.5 text-2xl font-black tracking-tight text-slate-950 dark:text-white sm:text-3xl">
                {t('auth.otpStepTitle')}
              </h1>
              <p className="mt-1 text-sm font-semibold text-slate-700 dark:text-slate-200">
                {t('auth.codeSentTo', { phone: '' })}{' '}
                <span dir="ltr" className="font-extrabold text-emerald-700 dark:text-emerald-300">
                  {formattedPhone}
                </span>
              </p>
            </div>
          </div>

          {/* Change Number / Switch User Row */}
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5 dark:border-slate-800 dark:bg-slate-800/60">
            <button
              type="button"
              id="auth-change-number-btn"
              onClick={handleChangeNumber}
              disabled={loading}
              className="inline-flex min-h-11 items-center gap-1.5 text-sm font-bold text-emerald-700 underline-offset-2 hover:underline focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:text-emerald-300"
            >
              <ArrowLeft size={16} />
              <span>{t('auth.changeNumber')}</span>
            </button>

            <button
              type="button"
              onClick={() => handleSwitchUser(false)}
              disabled={loading}
              className="inline-flex min-h-11 items-center gap-1.5 text-xs font-bold text-slate-600 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:text-slate-400 dark:hover:text-white"
            >
              <UserX size={14} />
              <span>{t('auth.notYouSwitch')}</span>
            </button>
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              submitOtpCode(otpDigits.join(''));
            }}
            noValidate
            className="space-y-4"
          >
            <div>
              <label
                htmlFor="otp-digit-0"
                className="mb-2 block text-sm font-bold text-slate-800 dark:text-slate-200"
              >
                {t('auth.otpLabel')}
              </label>

              {/* 6 Single-Digit Boxes — dir="ltr" so digits always flow left-to-right */}
              <div
                dir="ltr"
                onPaste={handleOtpPaste}
                className="grid grid-cols-6 gap-2 sm:gap-2.5"
              >
                {otpDigits.map((digit, idx) => (
                  <input
                    key={idx}
                    ref={(el) => {
                      otpInputRefs.current[idx] = el;
                    }}
                    id={`otp-digit-${idx}`}
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    autoComplete={idx === 0 ? 'one-time-code' : 'off'}
                    dir="ltr"
                    disabled={loading}
                    value={digit}
                    onChange={(e) => handleOtpChange(idx, e.target.value)}
                    onKeyDown={(e) => handleOtpKeyDown(idx, e)}
                    aria-label={`${t('auth.otpDigitAria', { index: idx + 1 })}`}
                    aria-invalid={Boolean(errorMessage)}
                    className={`min-h-[54px] w-full rounded-2xl border bg-slate-50 text-center text-xl font-black text-slate-950 outline-none transition focus:bg-white focus:ring-4 dark:bg-slate-950 dark:text-white dark:focus:bg-slate-900 ${
                      errorMessage
                        ? 'border-red-500 focus:border-red-500 focus:ring-red-500/15'
                        : digit
                        ? 'border-emerald-500 bg-emerald-50/40 dark:border-emerald-500 dark:bg-emerald-950/30'
                        : 'border-slate-300 focus:border-emerald-500 focus:ring-emerald-500/15 dark:border-slate-700'
                    }`}
                  />
                ))}
              </div>
            </div>

            {/* Error Alert */}
            <AnimatePresence>
              {errorMessage && (
                <motion.div
                  id="auth-otp-error"
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

            {/* Verify Button */}
            <button
              type="submit"
              id="auth-verify-code-btn"
              disabled={loading || otpDigits.join('').length < OTP_LENGTH}
              className="flex min-h-[54px] w-full items-center justify-center gap-2.5 rounded-2xl bg-gradient-to-r from-emerald-600 to-emerald-500 px-5 text-lg font-extrabold text-white shadow-lg shadow-emerald-700/20 transition hover:from-emerald-500 hover:to-emerald-500 focus:outline-none focus:ring-4 focus:ring-emerald-500/30 disabled:cursor-not-allowed disabled:opacity-65"
            >
              {loading ? (
                <>
                  <Loader2 size={22} className="animate-spin" />
                  <span>{t('auth.verifyingCode')}</span>
                </>
              ) : (
                <>
                  <CheckCircle2 size={20} />
                  <span>{t('auth.verifyCode')}</span>
                </>
              )}
            </button>
          </form>

          {/* Resend Countdown + Voice OTP Option */}
          <div className="flex flex-col gap-2 pt-1 sm:flex-row sm:items-center sm:justify-between">
            {resendCooldown > 0 ? (
              <p
                role="timer"
                aria-live="off"
                className="text-sm font-semibold text-slate-500 dark:text-slate-400"
              >
                {t('auth.resendIn', { seconds: resendCooldown })}
              </p>
            ) : (
              <button
                type="button"
                id="auth-resend-code-btn"
                disabled={loading || !canResendMore}
                onClick={() => handleResendOtp('sms')}
                className="inline-flex min-h-12 items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 text-sm font-bold text-slate-800 transition hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700"
              >
                <RefreshCw size={16} />
                <span>
                  {canResendMore
                    ? t('auth.resendCode')
                    : t('auth.errors.maxResendsReached')}
                </span>
              </button>
            )}

            {voiceAvailable && (
              <button
                type="button"
                id="auth-voice-call-btn"
                disabled={loading || resendCooldown > 0 || !canResendMore}
                onClick={() => handleResendOtp('voice')}
                className="inline-flex min-h-12 items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 text-sm font-bold text-emerald-800 transition hover:bg-emerald-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:cursor-not-allowed disabled:opacity-50 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200"
              >
                <PhoneCall size={16} />
                <span>{t('auth.callMeWithCode')}</span>
              </button>
            )}
          </div>
        </motion.div>
      )}

      {/* ─── STEP 2b (NEW NUMBER): DISPLAY NAME + LANGUAGE + CONSENT ─ */}
      {step === 'profile' && (
        <motion.div
          key="step-profile"
          initial={reduceMotion ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
          className="space-y-5"
        >
          <div className="flex items-start gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
              <CheckCircle2 size={28} />
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
                {t('auth.phoneVerifiedBadge')}
              </p>
              <h1 className="mt-0.5 text-2xl font-black tracking-tight text-slate-950 dark:text-white sm:text-3xl">
                {t('auth.profileStepTitle')}
              </h1>
              <p className="mt-1 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
                {t('auth.profileStepSubtitle')}
              </p>
            </div>
          </div>

          <div className="flex items-center justify-between gap-2 rounded-2xl border border-emerald-200 bg-emerald-50/60 px-4 py-2.5 text-sm dark:border-emerald-800/60 dark:bg-emerald-950/40">
            <span dir="ltr" className="font-extrabold text-emerald-800 dark:text-emerald-200">
              ✓ {formattedPhone}
            </span>
            <button
              type="button"
              onClick={() => handleSwitchUser(true)}
              className="text-xs font-bold text-slate-600 underline hover:text-slate-900 dark:text-slate-300"
            >
              {t('auth.notYouSwitch')}
            </button>
          </div>

          <form onSubmit={handleCompleteProfile} noValidate className="space-y-4">
            {/* Display Name */}
            <div>
              <label
                htmlFor="auth-display-name"
                className="mb-2 block text-sm font-bold text-slate-800 dark:text-slate-200"
              >
                {t('auth.nameLabel')}
              </label>
              <div className="relative">
                <User
                  size={20}
                  className="pointer-events-none absolute start-4 top-1/2 -translate-y-1/2 text-slate-400"
                />
                <input
                  ref={nameInputRef}
                  id="auth-display-name"
                  name="displayName"
                  type="text"
                  autoComplete="name"
                  disabled={loading}
                  value={displayName}
                  onChange={(e) => {
                    setDisplayName(e.target.value);
                    if (errorMessage) setErrorMessage('');
                  }}
                  placeholder={t('auth.namePlaceholder')}
                  className="min-h-[54px] w-full rounded-2xl border border-slate-300 bg-slate-50 ps-12 pe-4 text-[18px] font-bold text-slate-900 outline-none transition placeholder:font-normal placeholder:text-slate-400 focus:border-emerald-500 focus:bg-white focus:ring-4 focus:ring-emerald-500/15 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:focus:bg-slate-900"
                />
              </div>
            </div>

            {/* Preferred Language (Pre-filled from current language) */}
            <div className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-3.5 dark:border-slate-800 dark:bg-slate-800/50">
              <div>
                <p className="text-sm font-bold text-slate-900 dark:text-white">
                  {t('auth.preferredLanguageLabel')}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {getCountryName(countryCode, language)} ({countryCode})
                </p>
              </div>
              <CompactLanguagePicker
                language={preferredLocale}
                languages={languages}
                recentLanguages={recentLanguages}
                setLanguage={(code) => {
                  setPreferredLocale(code);
                  setLanguage(code);
                }}
                t={t}
              />
            </div>

            {/* Privacy Notice & Required Consent Checkbox */}
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-800/50">
              <label
                htmlFor="auth-consent-checkbox"
                className="flex min-h-12 cursor-pointer items-start gap-3"
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
                <span className="text-sm leading-relaxed font-medium text-slate-700 dark:text-slate-200">
                  {t('auth.consentCheckboxLabel')}{' '}
                  {privacyUrl ? (
                    <a
                      href={privacyUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-bold text-emerald-700 underline dark:text-emerald-400"
                    >
                      {t('auth.privacyPolicyLink')}
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
                      {t('auth.privacyPolicyLink')}
                    </button>
                  )}
                </span>
              </label>
              <p className="mt-2 ps-8 text-xs text-slate-500 dark:text-slate-400">
                {t('auth.privacyNotice')}
              </p>
            </div>

            {/* Error Alert */}
            <AnimatePresence>
              {errorMessage && (
                <motion.div
                  id="auth-profile-error"
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

            <button
              type="submit"
              id="auth-complete-signup-btn"
              disabled={loading}
              className="flex min-h-[54px] w-full items-center justify-center gap-2.5 rounded-2xl bg-gradient-to-r from-emerald-600 to-emerald-500 px-5 text-lg font-extrabold text-white shadow-lg shadow-emerald-700/20 transition hover:from-emerald-500 hover:to-emerald-500 focus:outline-none focus:ring-4 focus:ring-emerald-500/30 disabled:cursor-not-allowed disabled:opacity-65"
            >
              {loading ? (
                <>
                  <Loader2 size={22} className="animate-spin" />
                  <span>{t('auth.savingProfile')}</span>
                </>
              ) : (
                <>
                  <span>{t('auth.completeSignUp')}</span>
                  <ArrowRight size={20} />
                </>
              )}
            </button>
          </form>
        </motion.div>
      )}

      <PrivacyModal
        isOpen={isPrivacyModalOpen}
        onClose={() => setIsPrivacyModalOpen(false)}
        t={t}
      />
    </div>
  );
}
