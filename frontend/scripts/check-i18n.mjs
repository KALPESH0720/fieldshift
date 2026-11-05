import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';

const localeRoot = 'src/locales';
const source = JSON.parse(await readFile(join(localeRoot, 'en', 'translation.json'), 'utf8'));

function flatten(value, prefix = '', result = new Set()) {
  Object.entries(value).forEach(([key, child]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    if (child && typeof child === 'object' && !Array.isArray(child)) flatten(child, path, result);
    else result.add(path);
  });
  return result;
}

function getValue(value, path) {
  return path.split('.').reduce((current, part) => current?.[part], value);
}

const keys = [...flatten(source)];
const localeCodes = (await readdir(localeRoot, { withFileTypes: true }))
  .filter((entry) => entry.isDirectory())
  .map((entry) => entry.name);
const failures = [];

for (const code of localeCodes) {
  const file = join(localeRoot, code, 'translation.json');
  let locale;
  try {
    locale = JSON.parse(await readFile(file, 'utf8'));
  } catch {
    failures.push(`${code}: locale file is missing or invalid`);
    continue;
  }
  const missing = keys.filter((key) => getValue(locale, key) == null || String(getValue(locale, key)).trim() === '');
  const corrupted = keys.filter((key) => /^\?+$/.test(String(getValue(locale, key) ?? '').trim()));
  console.log(`${code}: ${missing.length} missing keys, ${corrupted.length} corrupted values`);
  if (missing.length || corrupted.length) failures.push(`${code}: ${missing.length} missing, ${corrupted.length} corrupted`);
}

const componentFiles = [
  'src/App.jsx',
  'src/components/ui/ListenButton.jsx',
  'src/components/Settings.jsx',
  'src/components/auth/Login.jsx',
  'src/layouts/AuthLayout.jsx',
  'src/components/PlotList.jsx',
  'src/components/WeatherPanel.jsx',
  'src/components/CatchCropAlert.jsx',
  'src/components/StartupNotifications.jsx',
  'src/components/VoiceAdvisory.jsx',
  'src/components/AddPlotModal.jsx',
  'src/components/CropPicker.jsx',
  'src/components/Recommender.jsx',
  'src/components/SoilImport.jsx',
  'src/components/PestScanner.jsx',
  'src/components/SchemesHub.jsx',
  'src/components/DealerDirectory.jsx',
  'src/components/MarketInsights.jsx',
  'src/components/MarketCropDetail.jsx',
  'src/components/GroupDashboard.jsx',
];
const usedKeys = [];
for (const file of componentFiles) {
  const content = await readFile(file, 'utf8');
  for (const match of content.matchAll(/\bt\(['"]([^'"]+)['"]/g)) usedKeys.push(`${file}: ${match[1]}`);
}
const unknownKeys = usedKeys.filter((item) => !keys.includes(item.split(': ').at(-1)));
if (unknownKeys.length) failures.push(...unknownKeys.map((item) => `missing English key: ${item}`));

const hardcoded = [];
for (const file of componentFiles) {
  const content = await readFile(file, 'utf8');
  for (const match of content.matchAll(/>([A-Za-z][A-Za-z ,.'·:+&-]{2,})<\/(?:span|p|button|h[1-6])>/g)) {
    hardcoded.push(`${file}: ${match[1].trim()}`);
  }
}
if (hardcoded.length) {
  console.warn(`\nPotential hardcoded JSX strings (${hardcoded.length}); migrate these through t():`);
  hardcoded.slice(0, 20).forEach((item) => console.warn(`- ${item}`));
}

if (failures.length) {
  console.error('\ni18n check failed:\n' + failures.join('\n'));
  process.exit(1);
}

console.log(`\nChecked ${keys.length} English translation keys across ${localeCodes.length} locale files.`);
