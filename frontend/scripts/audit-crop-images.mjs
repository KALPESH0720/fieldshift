import { readFile, stat, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const manifestPath = join(root, 'data', 'crop-image-sources.json');
const creditsPath = join(root, 'src', 'data', 'crop-credits.json');
const cropsDir = join(root, 'public', 'crops');
const beforeAuditJsonPath = join(root, 'docs', 'CROP_IMAGE_AUDIT_BEFORE.json');
const auditDocPath = join(root, 'docs', 'CROP_IMAGE_AUDIT.md');

const MIN_THUMB_BYTES = 3072; // 3 KB minimum for 128x128 WebP thumb
const MIN_CARD_BYTES = 8192;  // 8 KB minimum for 480x480 WebP card

const writeDoc = process.argv.includes('--write-doc');
const checkNetwork = process.argv.includes('--check-network');
const checkOnly = process.argv.includes('--check');
const moveRemoved = process.argv.includes('--move-removed');
const strict = process.argv.includes('--strict');
const availabilityPath = join(root, 'src', 'data', 'crops-with-images.json');
const cropsSourcePath = join(root, 'src', 'data', 'crops.js');
const removedDir = join(root, 'public', 'crops-removed');

async function computeDHash(buffer) {
  // 9x8 grayscale difference hash (64-bit perceptual hash as 16-char hex)
  const { data } = await sharp(buffer)
    .greyscale()
    .resize(9, 8, { fit: 'fill' })
    .raw()
    .toBuffer({ resolveWithObject: true });

  let bits = '';
  for (let row = 0; row < 8; row += 1) {
    for (let col = 0; col < 8; col += 1) {
      const left = data[row * 9 + col];
      const right = data[row * 9 + col + 1];
      bits += left > right ? '1' : '0';
    }
  }
  let hex = '';
  for (let i = 0; i < 64; i += 4) {
    hex += Number.parseInt(bits.slice(i, i + 4), 2).toString(16);
  }
  return hex;
}

async function analyzeWebp(filePath) {
  try {
    const infoStat = await stat(filePath);
    const buf = await readFile(filePath);
    const sha256 = createHash('sha256').update(buf).digest('hex');
    const meta = await sharp(buf).metadata();
    const stats = await sharp(buf).stats();
    const avgStdev =
      (stats.channels[0].stdev + stats.channels[1].stdev + stats.channels[2].stdev) / 3;
    const dHash = await computeDHash(buf);

    // Inspect corners to detect flat-green synthetic emoji tiles
    const { data, info } = await sharp(buf).raw().toBuffer({ resolveWithObject: true });
    const ch = info.channels;
    const w = info.width;
    const h = info.height;
    const corners = [
      [data[0], data[1], data[2]],
      [data[(w - 1) * ch], data[(w - 1) * ch + 1], data[(w - 1) * ch + 2]],
      [data[(h - 1) * w * ch], data[(h - 1) * w * ch + 1], data[(h - 1) * w * ch + 2]],
      [
        data[((h - 1) * w + (w - 1)) * ch],
        data[((h - 1) * w + (w - 1)) * ch + 1],
        data[((h - 1) * w + (w - 1)) * ch + 2],
      ],
    ];
    let cornerSpread = 0;
    for (let i = 1; i < corners.length; i += 1) {
      cornerSpread +=
        Math.abs(corners[i][0] - corners[0][0]) +
        Math.abs(corners[i][1] - corners[0][1]) +
        Math.abs(corners[i][2] - corners[0][2]);
    }
    const isFlatGreenTile =
      cornerSpread < 8 && corners[0][1] > corners[0][0] + 20 && corners[0][1] > corners[0][2] + 15;

    return {
      exists: true,
      size: infoStat.size,
      sha256,
      shortSha: sha256.slice(0, 16),
      dHash,
      width: meta.width || 0,
      height: meta.height || 0,
      format: meta.format || 'unknown',
      stdev: Math.round(avgStdev * 10) / 10,
      isFlatGreenTile,
    };
  } catch {
    return {
      exists: false,
      size: 0,
      sha256: 'MISSING',
      shortSha: 'MISSING',
      dHash: 'MISSING',
      width: 0,
      height: 0,
      format: 'missing',
      stdev: 0,
      isFlatGreenTile: false,
    };
  }
}

const ALLOWED_LICENSE_RE = /^(cc0|public domain|pd|cc[- ]by(-sa)?(\s+\d+(\.\d+)?)?(\s+[a-z]{2,3})?|unsplash.*|pexels.*)$/i;

const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
let creditsData = { crops: {} };
try {
  creditsData = JSON.parse(await readFile(creditsPath, 'utf8'));
} catch {
  // ignore
}

const rows = [];
const shaGroups = new Map();
const dHashGroups = new Map();

for (const entry of manifest) {
  const { cropId, subject, sourceUrl, pageUrl, author, license } = entry;
  const thumbPath = join(cropsDir, `${cropId}-thumb.webp`);
  const cardPath = join(cropsDir, `${cropId}-card.webp`);

  const thumb = await analyzeWebp(thumbPath);
  const card = await analyzeWebp(cardPath);

  if (thumb.exists) {
    const list = shaGroups.get(thumb.shortSha) || [];
    list.push(cropId);
    shaGroups.set(thumb.shortSha, list);

    const pList = dHashGroups.get(thumb.dHash) || [];
    pList.push(cropId);
    dHashGroups.set(thumb.dHash, pList);
  }

  let httpStatus = 'skipped';
  let contentType = 'image/*';
  if (checkNetwork && sourceUrl) {
    try {
      const res = await fetch(sourceUrl, {
        method: 'HEAD',
        headers: {
          'User-Agent': 'FieldShiftCropAudit/1.0 (https://github.com/KALPESH0720/fieldshift)',
        },
      });
      httpStatus = String(res.status);
      contentType = res.headers.get('content-type') || 'unknown';
    } catch (err) {
      httpStatus = `ERR:${err?.cause?.code || err?.message || 'network'}`;
    }
  }

  rows.push({
    cropId,
    subject,
    sourceUrl,
    pageUrl,
    author,
    license,
    creditEntry: creditsData?.crops?.[cropId] || null,
    thumb,
    card,
    httpStatus,
    contentType,
  });
}

const duplicateShaSets = [...shaGroups.entries()].filter(([, ids]) => ids.length > 1);
const duplicateDHashSets = [...dHashGroups.entries()].filter(([, ids]) => ids.length > 1);
const duplicateCropIds = new Set([
  ...duplicateShaSets.flatMap(([, ids]) => ids),
  ...duplicateDHashSets.flatMap(([, ids]) => ids),
]);

for (const row of rows) {
  const issues = [];
  if (!row.thumb.exists) issues.push('Missing thumb.webp');
  if (!row.card.exists) issues.push('Missing card.webp');
  if (row.thumb.exists && row.thumb.size < MIN_THUMB_BYTES) {
    issues.push(`Thumb < 3 KB (${row.thumb.size} B)`);
  }
  if (row.card.exists && row.card.size < MIN_CARD_BYTES) {
    issues.push(`Card < 8 KB (${row.card.size} B)`);
  }
  if (row.thumb.exists && (row.thumb.width !== 128 || row.thumb.height !== 128)) {
    issues.push(`Thumb dimensions ${row.thumb.width}x${row.thumb.height} != 128x128`);
  }
  if (row.card.exists && (row.card.width !== 480 || row.card.height !== 480)) {
    issues.push(`Card dimensions ${row.card.width}x${row.card.height} != 480x480`);
  }
  if (row.thumb.isFlatGreenTile || row.thumb.stdev < 18) {
    issues.push(`Synthetic/flat colour tile (stdev=${row.thumb.stdev})`);
  }
  if (duplicateCropIds.has(row.cropId)) {
    issues.push('Duplicate SHA-256 / perceptual hash shared with another crop');
  }
  if (!row.creditEntry || row.creditEntry.status !== 'verified' || !row.creditEntry.hasPhoto) {
    issues.push('Not marked verified in crop-credits.json');
  }
  if (!ALLOWED_LICENSE_RE.test(String(row.license || '').trim())) {
    issues.push(`Disallowed or missing licence: "${row.license}"`);
  }
  if (/k[oö]hler|blanco|illustration_|medizinal-pflanzen/i.test(row.sourceUrl || '')) {
    issues.push('Botanical illustration URL instead of photograph');
  }
  if (checkNetwork && (row.httpStatus !== '200' || !row.contentType.startsWith('image/'))) {
    issues.push(`Source HTTP ${row.httpStatus} (${row.contentType})`);
  }
  row.issues = issues;
  row.isSyntheticOrInvalid = issues.length > 0;
}

const validCount = rows.filter((r) => !r.isSyntheticOrInvalid).length;
const invalidRows = rows.filter((r) => r.isSyntheticOrInvalid);
const missingRows = rows.filter((r) => !r.thumb.exists || !r.card.exists);
const under3kbRows = rows.filter((r) => r.thumb.exists && r.thumb.size < MIN_THUMB_BYTES);

console.log('──────────────────────────────────────────────────────────────────────────────');
console.log(' FIELD SHIFT — CROP IMAGE AUDIT SUMMARY');
console.log('──────────────────────────────────────────────────────────────────────────────');
console.log(` Total crops in manifest : ${rows.length}`);
console.log(` Verified real photos    : ${validCount}`);
console.log(` Missing files           : ${missingRows.length}`);
console.log(` Thumbnails < 3 KB       : ${under3kbRows.length}`);
console.log(` Duplicate hash groups   : ${duplicateShaSets.length} SHA-256 / ${duplicateDHashSets.length} dHash (${duplicateCropIds.size} crops affected)`);
console.log(` Total flagged / invalid : ${invalidRows.length}`);
console.log('──────────────────────────────────────────────────────────────────────────────');

if (duplicateShaSets.length > 0) {
  console.log('\nDuplicate SHA-256 Hash Groups:');
  for (const [hash, ids] of duplicateShaSets) {
    console.log(`  - ${hash}: ${ids.join(', ')}`);
  }
}
if (duplicateDHashSets.length > 0) {
  console.log('\nDuplicate Perceptual (dHash) Groups:');
  for (const [hash, ids] of duplicateDHashSets) {
    console.log(`  - ${hash}: ${ids.join(', ')}`);
  }
}
if (invalidRows.length > 0) {
  console.log('\nFlagged Crops:');
  for (const r of invalidRows) {
    console.log(`  - ${r.cropId}: ${r.issues.join('; ')}`);
  }
}

// ── Availability: which crops in crops.js have a PROPER image ────────────────
// Proper = thumb + card exist, thumb >= 3 KB, not a flat/emoji tile, and the image is
// not shared with another crop (the shared image stays only with the crop it depicts).
const rowById = new Map(rows.map((row) => [row.cropId, row]));
const manifestById = new Map(manifest.map((entry) => [entry.cropId, entry]));
const squash = (value) => String(value || '').toLowerCase().replace(/[^a-z]/g, '');
function depictsCrop(id) {
  const entry = manifestById.get(id);
  const haystack = squash([entry?.subject, entry?.commonsTitle, entry?.sourceUrl, entry?.pageUrl].join(' '));
  return haystack.includes(squash(id));
}
const duplicateLosers = new Map();
for (const ids of [...duplicateShaSets, ...duplicateDHashSets].map(([, group]) => group)) {
  // Prefer the crop whose recorded credit hash still matches the file (the one that was downloaded for it).
  const hashOwners = ids.filter((id) => {
    const recorded = creditsData?.crops?.[id]?.thumbHash;
    const current = rowById.get(id)?.thumb?.sha256;
    return recorded && current && current.startsWith(recorded);
  });
  const owners = hashOwners.length ? hashOwners : ids.filter(depictsCrop);
  const keep = owners.length === 1 ? owners[0] : null;
  for (const id of ids) {
    if (id !== keep) {
      duplicateLosers.set(id, `Image shared with ${ids.filter((other) => other !== id).join(', ')}`);
    }
  }
}

const cropsSource = await readFile(cropsSourcePath, 'utf8');
const allCropIds = [...cropsSource.matchAll(/^\s+\['([a-z-]+)', '/gm)].map((match) => match[1]);
const available = [];
const removed = [];
for (const id of allCropIds) {
  const row = rowById.get(id);
  const reasons = [];
  if (!row) {
    reasons.push('No entry in data/crop-image-sources.json');
  } else {
    if (!row.thumb.exists) reasons.push('Missing thumb.webp');
    if (!row.card.exists) reasons.push('Missing card.webp');
    if (row.thumb.exists && row.thumb.size < MIN_THUMB_BYTES) reasons.push(`Thumb under 3 KB (${row.thumb.size} B)`);
    if (row.thumb.exists && (row.thumb.isFlatGreenTile || row.thumb.stdev < 18)) {
      reasons.push(`Flat colour / synthetic tile (stdev ${row.thumb.stdev})`);
    }
    if (duplicateLosers.has(id)) reasons.push(duplicateLosers.get(id));
  }
  if (reasons.length) removed.push({ id, reason: reasons.join('; ') });
  else available.push(id);
}

console.log(`\n Crops with proper images: ${available.length} of ${allCropIds.length} (${removed.length} hidden)`);
for (const item of removed) console.log(`  - HIDDEN ${item.id}: ${item.reason}`);

if (checkOnly) {
  const freshAvailable = new Set(available);
  let published = { available: [] };
  try {
    published = JSON.parse(await readFile(availabilityPath, 'utf8'));
  } catch {
    console.error('[crops:check] FAILED: src/data/crops-with-images.json is missing. Run "npm run crops:audit".');
    process.exit(1);
  }
  const bad = published.available.filter((id) => !freshAvailable.has(id));
  if (bad.length) {
    console.error(`[crops:check] FAILED: ${bad.length} exported crop(s) have a missing, synthetic or duplicate image:`);
    for (const id of bad) console.error(`  - ${id}: ${removed.find((item) => item.id === id)?.reason || 'unknown crop id'}`);
    console.error('Run "npm run crops:audit -- --move-removed" to hide them, or add proper photos.');
    process.exit(1);
  }
  const stale = available.filter((id) => !published.available.includes(id));
  if (stale.length) console.log(`[crops:check] note: ${stale.length} crop(s) now have photos but are not published yet (${stale.join(', ')}). Run "npm run crops:audit".`);
  console.log(`[crops:check] OK: all ${published.available.length} exported crops have proper, unique images.`);
  process.exit(0);
}

await writeFile(availabilityPath, `${JSON.stringify({ available, removed }, null, 2)}\n`, 'utf8');
console.log(`Wrote ${availabilityPath.replace(root, '.')}`);

if (moveRemoved && removed.length > 0) {
  const { mkdir, rename } = await import('node:fs/promises');
  await mkdir(removedDir, { recursive: true });
  for (const { id } of removed) {
    for (const suffix of ['thumb', 'card']) {
      try {
        await rename(join(cropsDir, `${id}-${suffix}.webp`), join(removedDir, `${id}-${suffix}.webp`));
        console.log(`  moved ${id}-${suffix}.webp -> public/crops-removed/`);
      } catch {
        // file did not exist
      }
    }
    if (creditsData?.crops?.[id]) delete creditsData.crops[id];
  }
  creditsData.totalCrops = allCropIds.length;
  creditsData.verifiedCount = Object.keys(creditsData.crops).length;
  creditsData.missingCount = allCropIds.length - creditsData.verifiedCount;
  await writeFile(creditsPath, `${JSON.stringify(creditsData, null, 2)}\n`, 'utf8');
}

if (writeDoc) {
  let beforeRows = [];
  try {
    beforeRows = JSON.parse(await readFile(beforeAuditJsonPath, 'utf8'));
  } catch {
    // ignore if not present
  }

  const md = [
    '# Field Shift — Crop Image Audit Report (`docs/CROP_IMAGE_AUDIT.md`)',
    '',
    'This document records the **Before Fix** and **After Fix** technical and visual audit of all 60 crops defined in `src/data/crops.js`.',
    '',
    '## Summary Comparison (Before vs. After)',
    '',
    '| Metric | Before Fix | After Fix |',
    '| :--- | :---: | :---: |',
    `| **Total Crops in \`src/data/crops.js\`** | ${beforeRows.length || 60} | ${rows.length} |`,
    `| **Verified Real Photographs (\`>= 3 KB\` thumb, \`>= 8 KB\` card, unique subject)** | ${beforeRows.length ? beforeRows.filter((r) => !r.flagged).length : 35} | **${validCount}** |`,
    `| **Thumbnails Under 3 KB (\`< 3,072\` bytes)** | ${beforeRows.length ? beforeRows.filter((r) => r.under3kb).length : 6} | **${under3kbRows.length}** |`,
    `| **Duplicate Hash Groups (SHA-256 / Perceptual dHash)** | 1 group (\`rice\`, \`paddy\`) | **${duplicateShaSets.length} groups (${duplicateCropIds.size} crops)** |`,
    `| **Botanical Drawings / Wrong Subjects / Broken \`/640px-\` URLs** | 25 crops | **${invalidRows.length} crops** |`,
    `| **Missing Files** | 0 | **${missingRows.length}** |`,
    '',
    '---',
    '',
    '## 1. Before-Fix Audit Findings (Root Causes Identified)',
    '',
    '### 1.1 Why the Browser Still Showed Synthetic Emoji Tiles & Shared Bean Icons',
    '1. **Service Worker Cache Trap (`vite.config.js` + Unversioned URLs)**: `vite.config.js` enabled the Workbox Service Worker in development (`devOptions: { enabled: true }`) with a catch-all `CacheFirst` rule (`cacheName: "image-cache"`, 30-day expiration) for `/\\.(?:png|jpg|jpeg|svg|gif|webp|ico)$/i` and precached `crops/*-thumb.webp` without version query strings on `/crops/<id>-thumb.webp`. Any browser that had previously loaded the app continued serving the old `456–2,374` byte synthetic flat-green emoji WebP files from Service Worker CacheStorage (`image-cache` / `workbox-precache-v2`), where `beans`, `lentil`, `cowpea`, `chickpea`, `moong`, `pigeon-pea`, `soybean`, and `black-gram` shared the identical `🫘` bean icon tile.',
    '2. **Mock Land Registry & Unmapped Plot Crops (`mockProviders.js` + `PlotList.jsx`)**: `mockProviders.js` assigned `landUse: "mixed agriculture" | "arable land"` and `cropDeclared: "Cereal" | "Vegetables" | "Tree crop"`. When rendered by `<CropImage />`, `getCrop()` fell back to `other` (`other-thumb.webp`) for every unmapped label, causing imported plots to display the same repeated image.',
    '3. **Permissive `MIN_REAL_PHOTO_BYTES = 1500` in `scripts/fetch-crop-images.mjs`**: The previous pipeline accepted thumbnails down to `1,500` bytes, did not check for duplicate SHA-256/perceptual hashes, did not reject 19th-century botanical plates (`Köhler` / `Blanco`), and contained guessed Unsplash photo IDs that returned wrong subjects.',
    '',
    '### 1.2 Duplicate Hash Groups (Before Fix)',
    '- **`46f500a96b72ec25` (thumb) / `609dd9db0ec45b1a` (card)**: Shared identically by `rice` and `paddy` (both downloaded `https://images.unsplash.com/photo-1536304993881-ff6e9eefa2a6`, which depicted a bowl of cooked white restaurant rice).',
    '',
    '### 1.3 Invalid Manifest Sources, Wrong Subjects & Under-3KB Thumbnails (Before Fix)',
    '| Crop ID | Thumb Size (Before) | Card Size (Before) | Thumb SHA-256 | Root Issue (Before Fix) |',
    '| :--- | :---: | :---: | :---: | :--- |',
  ];

  for (const b of beforeRows.filter((r) => r.flagged)) {
    md.push(
      `| \`${b.id}\` | ${b.tSize.toLocaleString()} B | ${b.cSize.toLocaleString()} B | \`${b.tHash}\` | ${b.issue} |`,
    );
  }

  md.push(
    '',
    '---',
    '',
    '## 2. After-Fix Complete 60-Crop Audit Table',
    '',
    '| Crop ID | Exists (Thumb / Card) | Thumb Bytes | Card Bytes | Thumb SHA-256 | Card SHA-256 | Perceptual dHash | Licence | Status |',
    '| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :---: |',
  );

  for (const r of rows) {
    const statusText = r.isSyntheticOrInvalid
      ? `INVALID: ${r.issues.join(', ')}`
      : 'Verified Real Photo';
    md.push(
      `| \`${r.cropId}\` | ${r.thumb.exists ? 'Yes' : 'No'} / ${r.card.exists ? 'Yes' : 'No'} | ${r.thumb.size.toLocaleString()} B | ${r.card.size.toLocaleString()} B | \`${r.thumb.shortSha}\` | \`${r.card.shortSha}\` | \`${r.thumb.dHash}\` | ${r.license} | ${statusText} |`,
    );
  }

  md.push(
    '',
    '---',
    '',
    '## 3. Catalog Availability (`src/data/crops-with-images.json`)',
    '',
    'A crop is offered in the app only if both WebP files exist, the thumb is at least 3 KB, it is not a flat-colour tile (pixel stdev >= 18), and its SHA-256 / perceptual hash is not shared with another crop.',
    '',
    `**${available.length} of ${allCropIds.length} crops available, ${removed.length} hidden.**`,
    '',
    '| Crop ID | Status | Reason |',
    '| :--- | :---: | :--- |',
  );
  for (const id of allCropIds) {
    const gone = removed.find((item) => item.id === id);
    md.push(`| \`${id}\` | ${gone ? 'Hidden' : 'Available'} | ${gone ? gone.reason : 'Proper image'} |`);
  }

  await writeFile(auditDocPath, `${md.join('\n')}\n`, 'utf8');
  console.log(`\nWrote full before/after audit report to docs/CROP_IMAGE_AUDIT.md`);
}

if (strict && invalidRows.length > 0) {
  console.error(
    `\n[crops:audit] FAILED: ${invalidRows.length} crop(s) failed verification. Run "npm run crops:fetch" or inspect docs/CROP_IMAGE_AUDIT.md.`,
  );
  process.exit(1);
}
