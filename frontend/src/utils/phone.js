import {
  AsYouType,
  getCountries,
  getCountryCallingCode,
  parsePhoneNumberFromString,
  validatePhoneNumberLength,
} from 'libphonenumber-js/mobile';

export const DEFAULT_COUNTRY = 'IN';
export const AUTH_COUNTRY_STORAGE_KEY = 'fieldshift-auth-country';
export const REGISTRY_COUNTRY_STORAGE_KEY = 'fieldshift-country';

const LANGUAGE_TO_COUNTRY = {
  en: 'IN',
  hi: 'IN',
  mr: 'IN',
  bn: 'IN',
  te: 'IN',
  ta: 'IN',
  gu: 'IN',
  kn: 'IN',
  ml: 'IN',
  pa: 'IN',
  or: 'IN',
  as: 'IN',
  kok: 'IN',
  mai: 'IN',
  bho: 'IN',
  sat: 'IN',
  mni: 'IN',
  ur: 'PK',
  ne: 'NP',
  si: 'LK',
  'si-LK': 'LK',
  my: 'MM',
  id: 'ID',
  jv: 'ID',
  su: 'ID',
  ms: 'MY',
  fil: 'PH',
  ceb: 'PH',
  vi: 'VN',
  th: 'TH',
  km: 'KH',
  lo: 'LA',
  'zh-CN': 'CN',
  'zh-TW': 'TW',
  ja: 'JP',
  ko: 'KR',
  ar: 'EG',
  fa: 'IR',
  he: 'IL',
  tr: 'TR',
  sw: 'KE',
  'sw-KE': 'KE',
  am: 'ET',
  om: 'ET',
  ti: 'ET',
  so: 'SO',
  ha: 'NG',
  yo: 'NG',
  'yo-NG': 'NG',
  ig: 'NG',
  'ig-NG': 'NG',
  rw: 'RW',
  sn: 'ZW',
  zu: 'ZA',
  xh: 'ZA',
  af: 'ZA',
  st: 'ZA',
  tn: 'ZA',
  wo: 'SN',
  ak: 'GH',
  mg: 'MG',
  es: 'ES',
  'es-MX': 'MX',
  'pt-BR': 'BR',
  'pt-PT': 'PT',
  fr: 'FR',
  'fr-CA': 'CA',
  de: 'DE',
  it: 'IT',
  nl: 'NL',
  pl: 'PL',
  uk: 'UA',
  ru: 'RU',
  ro: 'RO',
  el: 'GR',
  cs: 'CZ',
  hu: 'HU',
  sv: 'SE',
  no: 'NO',
  da: 'DK',
  fi: 'FI',
};

const PRIORITY_COUNTRIES = [
  'IN',
  'US',
  'BR',
  'KE',
  'NG',
  'ID',
  'PH',
  'BD',
  'VN',
  'EG',
  'SA',
  'AE',
  'PK',
  'NP',
  'LK',
  'ET',
  'ZA',
  'GH',
  'TZ',
  'UG',
  'MX',
  'AR',
  'CO',
  'PE',
  'GB',
  'DE',
  'FR',
  'ES',
  'PT',
  'CN',
  'JP',
  'AU',
];

const FALLBACK_COUNTRY_NAMES = {
  IN: 'India',
  US: 'United States',
  BR: 'Brazil',
  KE: 'Kenya',
  NG: 'Nigeria',
  ID: 'Indonesia',
  PH: 'Philippines',
  BD: 'Bangladesh',
  VN: 'Vietnam',
  EG: 'Egypt',
  SA: 'Saudi Arabia',
  AE: 'United Arab Emirates',
  PK: 'Pakistan',
  NP: 'Nepal',
  LK: 'Sri Lanka',
  ET: 'Ethiopia',
  ZA: 'South Africa',
  GH: 'Ghana',
  MX: 'Mexico',
  AR: 'Argentina',
  GB: 'United Kingdom',
  DE: 'Germany',
  FR: 'France',
  ES: 'Spain',
  PT: 'Portugal',
  CN: 'China',
  JP: 'Japan',
  AU: 'Australia',
};

const SUPPORTED_COUNTRY_SET = new Set(getCountries());

export function getCountryFlag(countryCode) {
  if (!countryCode || typeof countryCode !== 'string' || countryCode.length !== 2) {
    return '🌐';
  }
  return countryCode
    .toUpperCase()
    .replace(/./g, (char) => String.fromCodePoint(127397 + char.charCodeAt(0)));
}

export function getCountryName(countryCode, locale = 'en') {
  if (!countryCode) return '';
  try {
    if (typeof Intl !== 'undefined' && typeof Intl.DisplayNames === 'function') {
      const displayNames = new Intl.DisplayNames([locale, 'en'], { type: 'region' });
      return displayNames.of(countryCode.toUpperCase()) || FALLBACK_COUNTRY_NAMES[countryCode] || countryCode;
    }
  } catch {
    // Fall back to English display name
  }
  return FALLBACK_COUNTRY_NAMES[countryCode] || countryCode;
}

export function getDialCode(countryCode) {
  try {
    return `+${getCountryCallingCode(countryCode)}`;
  } catch {
    return '+91';
  }
}

export function getCountryOptions(locale = 'en') {
  const allCountries = getCountries();
  const englishNames = (() => {
    try {
      return typeof Intl !== 'undefined' && typeof Intl.DisplayNames === 'function'
        ? new Intl.DisplayNames(['en'], { type: 'region' })
        : null;
    } catch {
      return null;
    }
  })();
  const localizedNames = (() => {
    try {
      return typeof Intl !== 'undefined' && typeof Intl.DisplayNames === 'function'
        ? new Intl.DisplayNames([locale, 'en'], { type: 'region' })
        : null;
    } catch {
      return null;
    }
  })();

  const buildOption = (code) => {
    const dialCode = getDialCode(code);
    const name = localizedNames?.of(code) || FALLBACK_COUNTRY_NAMES[code] || code;
    const englishName = englishNames?.of(code) || FALLBACK_COUNTRY_NAMES[code] || code;
    return {
      code,
      name,
      englishName,
      dialCode,
      flag: getCountryFlag(code),
    };
  };

  const prioritySet = new Set(PRIORITY_COUNTRIES.filter((c) => SUPPORTED_COUNTRY_SET.has(c)));
  const priorityList = [...prioritySet].map(buildOption);
  const remainingList = allCountries
    .filter((code) => !prioritySet.has(code))
    .map(buildOption)
    .sort((a, b) => a.name.localeCompare(b.name));

  return [...priorityList, ...remainingList];
}

export function detectDefaultCountry(languageCode) {
  if (typeof window !== 'undefined') {
    try {
      const savedAuthCountry = window.localStorage.getItem(AUTH_COUNTRY_STORAGE_KEY);
      if (savedAuthCountry && SUPPORTED_COUNTRY_SET.has(savedAuthCountry.toUpperCase())) {
        return savedAuthCountry.toUpperCase();
      }
      const savedRegistryCountry = window.localStorage.getItem(REGISTRY_COUNTRY_STORAGE_KEY);
      if (savedRegistryCountry && SUPPORTED_COUNTRY_SET.has(savedRegistryCountry.toUpperCase())) {
        return savedRegistryCountry.toUpperCase();
      }
    } catch {
      // Ignore storage access errors
    }

    const navLocales = Array.isArray(navigator?.languages) && navigator.languages.length
      ? navigator.languages
      : [navigator?.language].filter(Boolean);

    for (const tag of navLocales) {
      const parts = String(tag).replace('_', '-').split('-');
      const regionCandidate = parts.find((part, idx) => idx > 0 && /^[A-Za-z]{2}$/.test(part));
      if (regionCandidate && SUPPORTED_COUNTRY_SET.has(regionCandidate.toUpperCase())) {
        return regionCandidate.toUpperCase();
      }
    }
  }

  if (languageCode && LANGUAGE_TO_COUNTRY[languageCode]) {
    return LANGUAGE_TO_COUNTRY[languageCode];
  }
  const baseLang = String(languageCode || '').split('-')[0];
  if (baseLang && LANGUAGE_TO_COUNTRY[baseLang]) {
    return LANGUAGE_TO_COUNTRY[baseLang];
  }

  return DEFAULT_COUNTRY;
}

/**
 * Formats a phone number as the user types.
 * If the user pastes/types a leading '+' with an international calling code,
 * detects the country code automatically so the selector can stay in sync.
 */
export function formatPhoneAsYouType(rawInput, countryCode = DEFAULT_COUNTRY) {
  const safeCountry = SUPPORTED_COUNTRY_SET.has(countryCode) ? countryCode : DEFAULT_COUNTRY;
  const cleaned = String(rawInput || '').replace(/[^\d+]/g, '');

  if (!cleaned) {
    return { formatted: '', detectedCountry: safeCountry };
  }

  if (cleaned.startsWith('+')) {
    const typer = new AsYouType();
    typer.input(cleaned);
    const detected = typer.getCountry();
    if (detected && SUPPORTED_COUNTRY_SET.has(detected)) {
      const nationalDigits = typer.getNationalNumber();
      if (nationalDigits) {
        const nationalTyper = new AsYouType(detected);
        return {
          formatted: nationalTyper.input(nationalDigits),
          detectedCountry: detected,
        };
      }
      return { formatted: '', detectedCountry: detected };
    }
  }

  const digitsOnly = cleaned.replace(/\D/g, '');
  const dialDigits = getDialCode(safeCountry).replace(/\D/g, '');

  // Handle pasted full number with country calling code (e.g. 919876543210 for IN)
  let nationalCandidate = digitsOnly;
  if (digitsOnly.length > 10 && digitsOnly.startsWith(dialDigits)) {
    const stripped = digitsOnly.slice(dialDigits.length);
    const parsedStripped = parsePhoneNumberFromString(stripped, safeCountry);
    if (parsedStripped?.isValid()) {
      nationalCandidate = stripped;
    }
  }

  const typer = new AsYouType(safeCountry);
  const formatted = typer.input(nationalCandidate);
  return {
    formatted: formatted || nationalCandidate,
    detectedCountry: safeCountry,
  };
}

/**
 * Validates a phone number for the chosen country and returns its E.164 representation.
 */
export function validateAndFormatPhone(rawInput, countryCode = DEFAULT_COUNTRY) {
  const safeCountry = SUPPORTED_COUNTRY_SET.has(countryCode) ? countryCode : DEFAULT_COUNTRY;
  const trimmed = String(rawInput || '').trim();
  const digits = trimmed.replace(/\D/g, '');

  if (!digits) {
    return {
      valid: false,
      errorKey: 'auth.errors.phoneRequired',
      phoneE164: null,
      formattedInternational: '',
      countryCode: safeCountry,
    };
  }

  const lengthResult = validatePhoneNumberLength(
    trimmed.startsWith('+') ? trimmed : digits,
    safeCountry,
  );

  if (lengthResult === 'TOO_SHORT') {
    return {
      valid: false,
      errorKey: 'auth.errors.phoneTooShort',
      phoneE164: null,
      formattedInternational: '',
      countryCode: safeCountry,
    };
  }

  if (lengthResult === 'TOO_LONG') {
    return {
      valid: false,
      errorKey: 'auth.errors.phoneTooLong',
      phoneE164: null,
      formattedInternational: '',
      countryCode: safeCountry,
    };
  }

  const parsed = trimmed.startsWith('+')
    ? parsePhoneNumberFromString(trimmed)
    : parsePhoneNumberFromString(digits, safeCountry);

  if (!parsed || !parsed.isValid()) {
    return {
      valid: false,
      errorKey: 'auth.errors.phoneInvalidForCountry',
      phoneE164: null,
      formattedInternational: '',
      countryCode: safeCountry,
    };
  }

  if (parsed.country && parsed.country !== safeCountry) {
    return {
      valid: false,
      errorKey: 'auth.errors.phoneInvalidForCountry',
      phoneE164: null,
      formattedInternational: '',
      countryCode: safeCountry,
    };
  }

  return {
    valid: true,
    errorKey: null,
    phoneE164: parsed.number,
    formattedInternational: parsed.formatInternational(),
    formattedNational: parsed.formatNational(),
    countryCode: parsed.country || safeCountry,
  };
}

/**
 * Formats an E.164 phone number for human display (e.g. "+91 98765 43210").
 */
export function formatPhoneDisplay(phoneE164) {
  if (!phoneE164) return '';
  const parsed = parsePhoneNumberFromString(String(phoneE164));
  if (parsed) {
    return parsed.formatInternational();
  }
  return String(phoneE164);
}

/**
 * Masks an E.164 phone number for Settings and the header menu.
 * Example: "+919876543210" -> "+91 ••••• ••210"
 */
export function maskPhoneE164(phoneE164) {
  if (!phoneE164) return '';
  const parsed = parsePhoneNumberFromString(String(phoneE164));
  if (parsed) {
    const callingCode = parsed.countryCallingCode;
    const national = String(parsed.nationalNumber || '');
    if (national.length > 3) {
      const visibleTail = national.slice(-3);
      const hiddenCount = national.length - 3;
      if (hiddenCount >= 5) {
        const firstGroup = '•'.repeat(hiddenCount - 2);
        const secondGroup = `••${visibleTail}`;
        return `+${callingCode} ${firstGroup} ${secondGroup}`;
      }
      return `+${callingCode} ${'•'.repeat(hiddenCount)}${visibleTail}`;
    }
    return `+${callingCode} •••`;
  }

  const cleaned = String(phoneE164).replace(/\s+/g, '');
  if (cleaned.length > 6) {
    const prefix = cleaned.slice(0, 3);
    const tail = cleaned.slice(-3);
    return `${prefix} ••••• ••${tail}`;
  }
  return cleaned;
}
