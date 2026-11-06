// Speech formatting helpers: joins translated segments, strips emojis/icons/markdown,
// and formats numbers, currency, units, percentages, temperatures, and dates
// in a natural speakable form using Intl with the active BCP-47 speech locale.

const TERMINAL_PUNCTUATION_RE = /[.!?।؟۔。]$/u;

export function stripForSpeech(input) {
  if (input == null) return '';
  return String(input)
    // Markdown links [label](url) -> label
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    // Strip emojis, pictographs, dingbats, variation selectors, zero-width joiners
    .replace(/[\p{Extended_Pictographic}\uFE0E\uFE0F\u200D]/gu, ' ')
    // Strip markdown markers and decorative bullets / arrows / pipes
    .replace(/[*_`~#>]+/g, ' ')
    .replace(/[•·▪▸►→←↑↓↔|]/g, ', ')
    .replace(/\s*[—–]\s*/g, ', ')
    // Collapse repeated commas / periods and whitespace
    .replace(/(,\s*){2,}/g, ', ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function buildSpeechText(parts) {
  const flatParts = (Array.isArray(parts) ? parts.flat(Infinity) : [parts])
    .map((part) => stripForSpeech(part))
    .filter(Boolean);

  if (flatParts.length === 0) return '';

  return flatParts
    .map((segment) => (TERMINAL_PUNCTUATION_RE.test(segment) ? segment : `${segment}.`))
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function formatSpeakableNumber(value, locale = 'en-IN', maximumFractionDigits = 1) {
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value ?? '');
  try {
    return new Intl.NumberFormat(locale, { maximumFractionDigits }).format(num);
  } catch {
    return String(num);
  }
}

export function formatSpeakableCurrency(amount, locale = 'en-IN', currency = 'INR') {
  const num = Number(amount);
  if (!Number.isFinite(num)) return String(amount ?? '');
  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency,
      currencyDisplay: 'name',
      maximumFractionDigits: 0,
    }).format(num);
  } catch {
    try {
      return new Intl.NumberFormat(locale, {
        style: 'currency',
        currency,
        maximumFractionDigits: 0,
      }).format(num);
    } catch {
      return `${Math.round(num)} ${currency}`;
    }
  }
}

export function formatSpeakablePriceWithUnit(amount, translatedUnit, locale = 'en-IN', currency = 'INR') {
  const spokenAmount = formatSpeakableCurrency(amount, locale, currency);
  const cleanUnit = stripForSpeech(translatedUnit);
  return cleanUnit ? `${spokenAmount} ${cleanUnit}` : spokenAmount;
}

export function formatSpeakablePercent(value, locale = 'en-IN', maximumFractionDigits = 1) {
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value ?? '');
  try {
    return new Intl.NumberFormat(locale, {
      style: 'unit',
      unit: 'percent',
      unitDisplay: 'long',
      maximumFractionDigits,
    }).format(num);
  } catch {
    return `${formatSpeakableNumber(num, locale, maximumFractionDigits)}%`;
  }
}

export function formatSpeakableTemperature(value, unit = 'C', locale = 'en-IN') {
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value ?? '');
  const intlUnit = unit === 'F' ? 'fahrenheit' : 'celsius';
  try {
    return new Intl.NumberFormat(locale, {
      style: 'unit',
      unit: intlUnit,
      unitDisplay: 'long',
      maximumFractionDigits: 0,
    }).format(Math.round(num));
  } catch {
    return `${Math.round(num)}°${unit}`;
  }
}

export function formatSpeakableWeightKg(value, locale = 'en-IN') {
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value ?? '');
  try {
    return new Intl.NumberFormat(locale, {
      style: 'unit',
      unit: 'kilogram',
      unitDisplay: 'long',
      maximumFractionDigits: 1,
    }).format(num);
  } catch {
    return `${formatSpeakableNumber(num, locale, 1)} kg`;
  }
}

export function formatSpeakableDate(dateInput, locale = 'en-IN', options = { dateStyle: 'long' }) {
  const dt = dateInput instanceof Date ? dateInput : new Date(dateInput);
  if (Number.isNaN(dt.getTime())) return '';
  try {
    return new Intl.DateTimeFormat(locale, options).format(dt);
  } catch {
    return dt.toLocaleDateString();
  }
}

