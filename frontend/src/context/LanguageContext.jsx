/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { DEFAULT_LANGUAGE, getLanguage, SUPPORTED_LANGUAGES } from '../locales/languages';
import englishLocale from '../locales/en/translation.json';

const LANGUAGE_KEY = 'fieldshift-language';
const RECENT_LANGUAGE_KEY = 'fieldshift-recent-languages';
const localeModules = import.meta.glob('../locales/*/translation.json', {
  eager: false,
  import: 'default',
});
const LanguageContext = createContext(null);

function getValue(locale, key) {
  return key.split('.').reduce((value, part) => value?.[part], locale);
}

function normalizeLanguage(value) {
  return getLanguage(value).code;
}

function findLocaleModule(code) {
  const exact = `../locales/${code}/translation.json`;
  if (localeModules[exact]) return localeModules[exact];
  const base = code.split('-')[0];
  return localeModules[`../locales/${base}/translation.json`] || null;
}

async function loadLocale(code) {
  const loader = findLocaleModule(code);
  if (!loader) throw new Error(`Locale bundle not found for ${code}`);
  return loader();
}

function detectInitialLanguage() {
  const stored = window.localStorage.getItem(LANGUAGE_KEY);
  if (stored) return normalizeLanguage(stored);
  const candidates = Array.isArray(navigator.languages) ? navigator.languages : [navigator.language];
  return candidates.map(normalizeLanguage).find((code) => code !== DEFAULT_LANGUAGE.code) || DEFAULT_LANGUAGE.code;
}

function readRecentLanguages() {
  try {
    const stored = JSON.parse(window.localStorage.getItem(RECENT_LANGUAGE_KEY) || '[]');
    return Array.isArray(stored) ? stored.filter((code) => SUPPORTED_LANGUAGES.some((item) => item.code === code)) : [];
  } catch {
    return [];
  }
}

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(detectInitialLanguage);
  const [locale, setLocale] = useState(englishLocale);
  const [isLoading, setIsLoading] = useState(true);
  const [languageError, setLanguageError] = useState(null);
  const [recentLanguages, setRecentLanguages] = useState(readRecentLanguages);
  const languageInfo = getLanguage(language);

  useEffect(() => {
    let active = true;
    loadLocale(languageInfo.code)
      .then((loaded) => {
        if (active) {
          setLocale(loaded);
          setIsLoading(false);
        }
      })
      .catch((error) => {
        console.warn(`Unable to load locale ${languageInfo.code}; using English fallback.`, error);
        if (active) {
          setLocale(englishLocale);
          setLanguageError(languageInfo.code);
          setIsLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [languageInfo.code]);

  useEffect(() => {
    document.documentElement.lang = languageInfo.speechLang;
    document.documentElement.dir = languageInfo.dir;
    document.documentElement.dataset.language = languageInfo.code;
    document.documentElement.dataset.script = languageInfo.script;
    const fontFamilies = {
      Devanagari: 'Noto Sans Devanagari',
      Bengali: 'Noto Sans Bengali',
      Tamil: 'Noto Sans Tamil',
      Telugu: 'Noto Sans Telugu',
      Kannada: 'Noto Sans Kannada',
      Malayalam: 'Noto Sans Malayalam',
      Gujarati: 'Noto Sans Gujarati',
      Gurmukhi: 'Noto Sans Gurmukhi',
      Sinhala: 'Noto Sans Sinhala',
      Thai: 'Noto Sans Thai',
      Khmer: 'Noto Sans Khmer',
      Lao: 'Noto Sans Lao',
      Myanmar: 'Noto Sans Myanmar',
      Arabic: 'Noto Naskh Arabic',
      Hebrew: 'Noto Sans Hebrew',
      Georgian: 'Noto Sans Georgian',
      Armenian: 'Noto Sans Armenian',
      Ethiopic: 'Noto Sans Ethiopic',
      Han: 'Noto Sans SC',
      Japanese: 'Noto Sans JP',
      Korean: 'Noto Sans KR',
    };
    const family = fontFamilies[languageInfo.script];
    let link = document.getElementById('fieldshift-script-font');
    if (family) {
      if (!link) {
        link = document.createElement('link');
        link.id = 'fieldshift-script-font';
        link.rel = 'stylesheet';
        document.head.appendChild(link);
      }
      link.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(family).replace(/%20/g, '+')}:wght@400;500;600;700;800&display=swap`;
      document.documentElement.style.setProperty('--script-font', `'${family}'`);
    } else if (link) {
      link.remove();
      document.documentElement.style.removeProperty('--script-font');
    }
  }, [languageInfo]);

  const setLanguage = useCallback(async (nextLanguage) => {
    const next = normalizeLanguage(nextLanguage);
    if (next === language) return;
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      try {
        window.speechSynthesis.cancel();
      } catch {
        // ignore cancel errors
      }
    }
    setIsLoading(true);
    setLanguageError(null);
    try {
      const loaded = await loadLocale(next);
      setLocale(loaded);
      setLanguageState(next);
    } catch (error) {
      console.warn(`Unable to load locale ${next}; language was not changed.`, error);
      setLocale(englishLocale);
      setLanguageError(next);
      setIsLoading(false);
      return;
    }
    window.localStorage.setItem(LANGUAGE_KEY, next);
    setRecentLanguages((current) => {
      const updated = [next, ...current.filter((code) => code !== next)].slice(0, 5);
      window.localStorage.setItem(RECENT_LANGUAGE_KEY, JSON.stringify(updated));
      return updated;
    });
    setIsLoading(false);
  }, [language]);

  const value = useMemo(() => ({
    language,
    languageInfo,
    languages: SUPPORTED_LANGUAGES,
    recentLanguages,
    setLanguage,
    isLoading,
    languageError,
    t: (key, values = {}) => {
      const translated = getValue(locale, key);
      const fallback = getValue(englishLocale, key);
      const result = translated ?? fallback ?? key;
      const interpolated = String(result).replace(/\{(\w+)\}/g, (_, name) => values[name] ?? `{${name}}`);
      if (import.meta.env.DEV && (!translated || /^\?+$/.test(String(translated)))) {
        console.warn(`Missing or corrupted translation: ${language}.${key}`);
      }
      return interpolated;
    },
  }), [language, languageInfo, locale, recentLanguages, setLanguage, isLoading, languageError]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useTranslation() {
  const context = useContext(LanguageContext);
  if (!context) throw new Error('useTranslation must be used within LanguageProvider');
  return context;
}
