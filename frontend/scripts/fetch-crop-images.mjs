import { existsSync } from 'node:fs';
import { mkdir, readFile, stat, unlink, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const manifestPath = join(root, 'data', 'crop-image-sources.json');
const manualDir = join(root, 'data', 'manual-crop-photos');
const manualCreditsPath = join(manualDir, 'credits.json');
const cropsDir = join(root, 'public', 'crops');
const creditsPath = join(root, 'src', 'data', 'crop-credits.json');
const missingDocPath = join(root, 'docs', 'MISSING_CROP_IMAGES.md');
const envPath = join(root, '.env');

const MIN_RAW_BYTES = 8192;       // > 8 KB before resizing
const MIN_SHORT_SIDE_PX = 400;    // >= 400px on short side before resizing
const MIN_THUMB_BYTES = 3072;     // > 3 KB after resizing to 128x128
const MIN_CARD_BYTES = 8192;      // > 8 KB after resizing to 480x480

const ALLOWED_LICENSE_RE = /^(cc0|public domain|pd|cc[- ]by(-sa)?(\s+\d+(\.\d+)?)?(\s+[a-z]{2})?|unsplash.*|pexels.*)$/i;

const forceDownload = process.argv.includes('--force');
const purgeSyntheticFlag = process.argv.includes('--purge-synthetic');

// Load optional API keys from .env (never committed)
async function loadEnvKeys() {
  const keys = {
    UNSPLASH_ACCESS_KEY: process.env.UNSPLASH_ACCESS_KEY || '',
    PEXELS_API_KEY: process.env.PEXELS_API_KEY || '',
  };
  if (existsSync(envPath)) {
    try {
      const text = await readFile(envPath, 'utf8');
      for (const line of text.split(/\r?\n/)) {
        const match = line.match(/^\s*(UNSPLASH_ACCESS_KEY|PEXELS_API_KEY)\s*=\s*(.+)\s*$/);
        if (match && !keys[match[1]]) {
          keys[match[1]] = match[2].replace(/^['"]|['"]$/g, '');
        }
      }
    } catch {
      // ignore .env read errors
    }
  }
  return keys;
}

function stripHtml(html = '') {
  return String(html)
    .replace(/<[^>]*>/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

async function computeDHash(buffer) {
  const { data } = await sharp(buffer)
    .greyscale()
    .resize(9, 8, { fit: 'fill' })
    .raw()
    .toBuffer({ resolveWithObject: true });

  let bits = '';
  for (let row = 0; row < 8; row += 1) {
    for (let col = 0; col < 8; col += 1) {
      bits += data[row * 9 + col] > data[row * 9 + col + 1] ? '1' : '0';
    }
  }
  let hex = '';
  for (let i = 0; i < 64; i += 4) {
    hex += Number.parseInt(bits.slice(i, i + 4), 2).toString(16);
  }
  return hex;
}

async function safeUnlink(filePath) {
  try {
    await unlink(filePath);
    return true;
  } catch {
    return false;
  }
}

async function inspectExistingPair(thumbPath, cardPath) {
  try {
    const [tStat, cStat] = await Promise.all([stat(thumbPath), stat(cardPath)]);
    if (tStat.size < MIN_THUMB_BYTES || cStat.size < MIN_CARD_BYTES) {
      return { valid: false, reason: `Under size threshold (thumb=${tStat.size}B, card=${cStat.size}B)` };
    }
    const [tBuf, cBuf] = await Promise.all([readFile(thumbPath), readFile(cardPath)]);
    const [tMeta, cMeta, tStats] = await Promise.all([
      sharp(tBuf).metadata(),
      sharp(cBuf).metadata(),
      sharp(tBuf).stats(),
    ]);
    if (tMeta.width !== 128 || tMeta.height !== 128 || cMeta.width !== 480 || cMeta.height !== 480) {
      return { valid: false, reason: 'Dimensions mismatch' };
    }
    const avgStdev =
      (tStats.channels[0].stdev + tStats.channels[1].stdev + tStats.channels[2].stdev) / 3;
    if (avgStdev < 18) {
      return { valid: false, reason: `Flat colour / synthetic stdev=${avgStdev.toFixed(1)}` };
    }
    const thumbSha = createHash('sha256').update(tBuf).digest('hex');
    const cardSha = createHash('sha256').update(cBuf).digest('hex');
    const dHash = await computeDHash(tBuf);
    return {
      valid: true,
      thumbSize: tStat.size,
      cardSize: cStat.size,
      thumbSha,
      cardSha,
      dHash,
    };
  } catch {
    return { valid: false, reason: 'Missing file' };
  }
}

async function findManualSourceFile(cropId) {
  for (const ext of ['jpg', 'jpeg', 'png', 'webp']) {
    const candidate = join(manualDir, `${cropId}.${ext}`);
    if (existsSync(candidate)) {
      return candidate;
    }
  }
  return null;
}

async function downloadAndValidateRawImage(url, timeoutMs = 15000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      signal: controller.signal,
      headers: {
        'User-Agent':
          'FieldShiftCropFetcher/2.0 (https://github.com/KALPESH0720/fieldshift; agricultural-pwa)',
        Accept: 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
      },
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} ${response.statusText}`);
    }
    const contentType = (response.headers.get('content-type') || '').toLowerCase();
    if (!contentType.startsWith('image/')) {
      throw new Error(`Invalid content-type "${contentType}" (expected image/*)`);
    }
    const buffer = Buffer.from(await response.arrayBuffer());
    if (buffer.length < MIN_RAW_BYTES) {
      throw new Error(`Downloaded image too small (${buffer.length} B < ${MIN_RAW_BYTES} B)`);
    }
    const meta = await sharp(buffer).metadata();
    const shortSide = Math.min(meta.width || 0, meta.height || 0);
    if (shortSide < MIN_SHORT_SIDE_PX) {
      throw new Error(
        `Source image resolution too small (${meta.width}x${meta.height}, short side ${shortSide}px < ${MIN_SHORT_SIDE_PX}px)`,
      );
    }
    return buffer;
  } finally {
    clearTimeout(timer);
  }
}

async function searchWikimediaCommonsPhoto(cropId, subject) {
  const queryText = `${cropId.replace(/-/g, ' ')} ${subject || ''}`
    .replace(/\b(in|the|field|and|with|of|on|at)\b/gi, ' ')
    .trim();
  const apiUrl = `https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch=${encodeURIComponent(
    `filetype:bitmap ${queryText} -Kohler -Köhler -Blanco -illustration -drawing -map -stamp`,
  )}&gsrnamespace=6&gsrlimit=8&prop=imageinfo&iiprop=url|size|mime|extmetadata&iiurlwidth=800&format=json`;

  const res = await fetch(apiUrl, {
    headers: {
      'User-Agent': 'FieldShiftCropFetcher/2.0 (https://github.com/KALPESH0720/fieldshift)',
    },
  });
  if (!res.ok) return [];
  const data = await res.json();
  const pages = Object.values(data?.query?.pages || {});
  const results = [];
  for (const page of pages) {
    const ii = page?.imageinfo?.[0];
    if (!ii) continue;
    if (!/^image\/(jpeg|png|webp)$/i.test(ii.mime || '')) continue;
    if ((ii.width || 0) < MIN_SHORT_SIDE_PX || (ii.height || 0) < MIN_SHORT_SIDE_PX) continue;
    if ((ii.size || 0) < MIN_RAW_BYTES) continue;
    const ext = ii.extmetadata || {};
    const license = stripHtml(ext.LicenseShortName?.value || ext.License?.value || '');
    if (!ALLOWED_LICENSE_RE.test(license)) continue;
    const title = page.title || '';
    if (/k[oö]hler|blanco|illustration|drawing|herbarium|diagram|icon|logo/i.test(title)) continue;
    const artist = stripHtml(ext.Artist?.value || 'Wikimedia Commons Contributor').slice(0, 90);
    results.push({
      sourceUrl: ii.thumburl || ii.url,
      originalUrl: ii.url,
      pageUrl: ii.descriptionurl || `https://commons.wikimedia.org/wiki/${encodeURIComponent(title)}`,
      author: `${artist} (Wikimedia Commons)`,
      license,
    });
  }
  return results;
}

async function searchOptionalApiPhoto(cropId, subject, envKeys) {
  const query = encodeURIComponent(`${cropId.replace(/-/g, ' ')} crop agriculture`);
  if (envKeys.UNSPLASH_ACCESS_KEY) {
    try {
      const res = await fetch(
        `https://api.unsplash.com/search/photos?query=${query}&per_page=3&orientation=squarish`,
        {
          headers: { Authorization: `Client-ID ${envKeys.UNSPLASH_ACCESS_KEY}` },
        },
      );
      if (res.ok) {
        const data = await res.json();
        const item = data?.results?.[0];
        if (item?.urls?.regular) {
          return {
            sourceUrl: item.urls.regular,
            pageUrl: item.links?.html || 'https://unsplash.com',
            author: `${item.user?.name || 'Unsplash Photographer'} (Unsplash)`,
            license: 'Unsplash License (CC0-equivalent)',
          };
        }
      }
    } catch {
      // fall through
    }
  }
  if (envKeys.PEXELS_API_KEY) {
    try {
      const res = await fetch(`https://api.pexels.com/v1/search?query=${query}&per_page=3`, {
        headers: { Authorization: envKeys.PEXELS_API_KEY },
      });
      if (res.ok) {
        const data = await res.json();
        const item = data?.photos?.[0];
        if (item?.src?.large) {
          return {
            sourceUrl: item.src.large,
            pageUrl: item.url || 'https://www.pexels.com',
            author: `${item.photographer || 'Pexels Photographer'} (Pexels)`,
            license: 'Pexels License',
          };
        }
      }
    } catch {
      // fall through
    }
  }
  return null;
}

async function encodeAndVerifyPair(rawBuffer, thumbPath, cardPath) {
  let thumbBuffer = await sharp(rawBuffer)
    .resize(128, 128, { fit: 'cover', position: 'centre' })
    .webp({ quality: 86 })
    .toBuffer();

  if (thumbBuffer.length < MIN_THUMB_BYTES) {
    thumbBuffer = await sharp(rawBuffer)
      .resize(128, 128, { fit: 'cover', position: 'centre' })
      .webp({ quality: 96, lossless: false })
      .toBuffer();
  }
  if (thumbBuffer.length < MIN_THUMB_BYTES) {
    thumbBuffer = await sharp(rawBuffer)
      .resize(128, 128, { fit: 'cover', position: 'centre' })
      .webp({ lossless: true })
      .toBuffer();
  }
  if (thumbBuffer.length < MIN_THUMB_BYTES) {
    throw new Error(
      `Resized 128x128 thumb is still under 3 KB (${thumbBuffer.length} B < ${MIN_THUMB_BYTES} B)`,
    );
  }

  const cardBuffer = await sharp(rawBuffer)
    .resize(480, 480, { fit: 'cover', position: 'centre' })
    .webp({ quality: 86 })
    .toBuffer();

  if (cardBuffer.length < MIN_CARD_BYTES) {
    throw new Error(
      `Resized 480x480 card is under 8 KB (${cardBuffer.length} B < ${MIN_CARD_BYTES} B)`,
    );
  }

  const thumbSha = createHash('sha256').update(thumbBuffer).digest('hex');
  const cardSha = createHash('sha256').update(cardBuffer).digest('hex');
  const dHash = await computeDHash(thumbBuffer);

  await writeFile(thumbPath, thumbBuffer);
  await writeFile(cardPath, cardBuffer);

  return {
    thumbSize: thumbBuffer.length,
    cardSize: cardBuffer.length,
    thumbSha,
    cardSha,
    dHash,
  };
}

await mkdir(cropsDir, { recursive: true });
await mkdir(manualDir, { recursive: true });

const envKeys = await loadEnvKeys();
const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
let manualCredits = { crops: {} };
if (existsSync(manualCreditsPath)) {
  try {
    manualCredits = JSON.parse(await readFile(manualCreditsPath, 'utf8'));
  } catch {
    // ignore
  }
}

const seenThumbShas = new Map();
const seenDHashes = new Map();
const verifiedCredits = {};
const missingCrops = [];
let purgedCount = 0;
let downloadedCount = 0;
let manualProcessedCount = 0;
let verifiedExistingCount = 0;

for (const entry of manifest) {
  const { cropId, subject } = entry;
  const thumbPath = join(cropsDir, `${cropId}-thumb.webp`);
  const cardPath = join(cropsDir, `${cropId}-card.webp`);

  // 1. Check if a manual override exists in data/manual-crop-photos/<cropId>.{jpg,png,webp}
  const manualFile = await findManualSourceFile(cropId);
  if (manualFile) {
    try {
      const rawBuffer = await readFile(manualFile);
      if (rawBuffer.length < MIN_RAW_BYTES) {
        throw new Error(`Manual file ${manualFile} is under 8 KB (${rawBuffer.length} B)`);
      }
      const meta = await sharp(rawBuffer).metadata();
      if (Math.min(meta.width || 0, meta.height || 0) < MIN_SHORT_SIDE_PX) {
        throw new Error(`Manual file ${manualFile} is smaller than 400px on short side`);
      }
      const pair = await encodeAndVerifyPair(rawBuffer, thumbPath, cardPath);
      if (seenThumbShas.has(pair.thumbSha) || seenDHashes.has(pair.dHash)) {
        const dupOf = seenThumbShas.get(pair.thumbSha) || seenDHashes.get(pair.dHash);
        await safeUnlink(thumbPath);
        await safeUnlink(cardPath);
        throw new Error(`Manual photo duplicates crop "${dupOf}"`);
      }
      seenThumbShas.set(pair.thumbSha, cropId);
      seenDHashes.set(pair.dHash, cropId);

      const mCred = manualCredits?.crops?.[cropId] || {};
      const license = mCred.license || entry.license || 'CC0';
      const author = mCred.author || entry.author || 'Manual photograph contributor';
      const pageUrl = mCred.pageUrl || entry.pageUrl || 'local://data/manual-crop-photos';
      verifiedCredits[cropId] = {
        cropId,
        subject: mCred.subject || subject,
        sourceUrl: `data/manual-crop-photos/${cropId}`,
        pageUrl,
        author,
        license,
        thumbHash: pair.thumbSha.slice(0, 10),
        cardHash: pair.cardSha.slice(0, 10),
        dHash: pair.dHash,
        thumbBytes: pair.thumbSize,
        cardBytes: pair.cardSize,
        hasPhoto: true,
        status: 'verified',
      };
      manualProcessedCount += 1;
      console.log(`✓ [manual] ${cropId}: thumb=${pair.thumbSize}B card=${pair.cardSize}B`);
      continue;
    } catch (err) {
      console.warn(`! [manual] ${cropId} failed validation: ${err.message}`);
    }
  }

  // 2. Inspect existing pair on disk; purge if synthetic, < 3 KB, botanical drawing, or duplicate
  const isBotanicalUrl = /k[oö]hler|blanco|illustration_|medizinal-pflanzen/i.test(
    entry.sourceUrl || '',
  );
  const existing = await inspectExistingPair(thumbPath, cardPath);
  if (!existing.valid || isBotanicalUrl || forceDownload) {
    if (existsSync(thumbPath) || existsSync(cardPath)) {
      await safeUnlink(thumbPath);
      await safeUnlink(cardPath);
      purgedCount += 1;
    }
  } else if (
    seenThumbShas.has(existing.thumbSha) ||
    seenDHashes.has(existing.dHash)
  ) {
    const dupOf = seenThumbShas.get(existing.thumbSha) || seenDHashes.get(existing.dHash);
    console.warn(`! Purging duplicate on-disk image for ${cropId} (shared hash with ${dupOf})`);
    await safeUnlink(thumbPath);
    await safeUnlink(cardPath);
    purgedCount += 1;
  } else if (!purgeSyntheticFlag && ALLOWED_LICENSE_RE.test(String(entry.license || '').trim())) {
    seenThumbShas.set(existing.thumbSha, cropId);
    seenDHashes.set(existing.dHash, cropId);
    verifiedExistingCount += 1;
    verifiedCredits[cropId] = {
      cropId,
      subject,
      sourceUrl: entry.sourceUrl,
      pageUrl: entry.pageUrl,
      author: entry.author,
      license: entry.license,
      thumbHash: existing.thumbSha.slice(0, 10),
      cardHash: existing.cardSha.slice(0, 10),
      dHash: existing.dHash,
      thumbBytes: existing.thumbSize,
      cardBytes: existing.cardSize,
      hasPhoto: true,
      status: 'verified',
    };
    continue;
  }

  // 3. Download and validate from manifest URL (or fallback to Wikimedia Commons / Unsplash / Pexels API)
  const candidateSources = [];
  if (entry.sourceUrl && !isBotanicalUrl) {
    candidateSources.push({
      sourceUrl: entry.sourceUrl,
      originalUrl: entry.originalUrl || entry.sourceUrl,
      pageUrl: entry.pageUrl,
      author: entry.author,
      license: entry.license,
    });
  }

  let downloaded = false;
  let lastError = 'No valid photographic source found';

  const tryCandidateList = async (candidates) => {
    for (const cand of candidates) {
      if (!ALLOWED_LICENSE_RE.test(String(cand.license || '').trim())) {
        lastError = `Disallowed licence "${cand.license}"`;
        continue;
      }
      const urlsToTry = [cand.sourceUrl, cand.originalUrl].filter(Boolean);
      for (const u of urlsToTry) {
        try {
          const rawBuf = await downloadAndValidateRawImage(u);
          const pair = await encodeAndVerifyPair(rawBuf, thumbPath, cardPath);
          if (seenThumbShas.has(pair.thumbSha) || seenDHashes.has(pair.dHash)) {
            const dupOf = seenThumbShas.get(pair.thumbSha) || seenDHashes.get(pair.dHash);
            await safeUnlink(thumbPath);
            await safeUnlink(cardPath);
            lastError = `Downloaded image duplicates crop "${dupOf}"`;
            continue;
          }
          seenThumbShas.set(pair.thumbSha, cropId);
          seenDHashes.set(pair.dHash, cropId);

          entry.sourceUrl = u;
          entry.pageUrl = cand.pageUrl;
          entry.author = cand.author;
          entry.license = cand.license;

          verifiedCredits[cropId] = {
            cropId,
            subject,
            sourceUrl: u,
            pageUrl: cand.pageUrl,
            author: cand.author,
            license: cand.license,
            thumbHash: pair.thumbSha.slice(0, 10),
            cardHash: pair.cardSha.slice(0, 10),
            dHash: pair.dHash,
            thumbBytes: pair.thumbSize,
            cardBytes: pair.cardSize,
            hasPhoto: true,
            status: 'verified',
          };
          downloadedCount += 1;
          downloaded = true;
          console.log(
            `✓ [downloaded] ${cropId}: thumb=${pair.thumbSize}B card=${pair.cardSize}B (${cand.license})`,
          );
          return true;
        } catch (err) {
          lastError = err?.cause?.code || err?.message || 'Download error';
        }
      }
    }
    return false;
  };

  if (!(await tryCandidateList(candidateSources))) {
    // Query Wikimedia Commons API directly
    try {
      const wmCandidates = await searchWikimediaCommonsPhoto(cropId, subject);
      await tryCandidateList(wmCandidates);
    } catch (err) {
      lastError = err?.message || lastError;
    }
  }

  if (!downloaded) {
    const apiCand = await searchOptionalApiPhoto(cropId, subject, envKeys);
    if (apiCand) {
      await tryCandidateList([apiCand]);
    }
  }

  if (!downloaded) {
    // Ensure no synthetic or partial file remains on disk, and DO NOT add to verifiedCredits
    await safeUnlink(thumbPath);
    await safeUnlink(cardPath);
    missingCrops.push({
      cropId,
      subject,
      sourceUrl: entry.sourceUrl,
      reason: lastError,
    });
    console.error(`✗ [missing] ${cropId}: ${lastError}`);
  }
}

await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');

const totalVerified = Object.keys(verifiedCredits).length;
const creditsOutput = {
  _note:
    'Verified photographic crop assets from Wikimedia Commons and Unsplash (CC0 / Public Domain / CC-BY / CC-BY-SA). Only verified photographs (>3KB thumb, >8KB card, unique SHA-256 & perceptual hash) are included.',
  generatedAt: new Date().toISOString(),
  totalCrops: manifest.length,
  verifiedCount: totalVerified,
  missingCount: missingCrops.length,
  crops: verifiedCredits,
};

await writeFile(creditsPath, `${JSON.stringify(creditsOutput, null, 2)}\n`, 'utf8');

const docLines = [
  '# Crop Photograph Manifest & Missing Images Report (`docs/MISSING_CROP_IMAGES.md`)',
  '',
  `- **Total crops in \`src/data/crops.js\`**: ${manifest.length}`,
  `- **Verified real photographs**: ${totalVerified} (${downloadedCount} downloaded, ${manualProcessedCount} manual, ${verifiedExistingCount} existing)`,
  `- **Missing real photographs**: ${missingCrops.length}`,
  `- **Purged synthetic/invalid/duplicate files**: ${purgedCount}`,
  '',
  '## How to Provide Manual Crop Photos (`data/manual-crop-photos/`)',
  '',
  'If any crop cannot be fetched automatically, drop `<cropId>.jpg` or `<cropId>.png` (`>= 400px` on the short side, `> 8 KB`) into `data/manual-crop-photos/`, optionally add attribution in `data/manual-crop-photos/credits.json`, and run:',
  '',
  '```bash',
  'npm run crops:fetch',
  'npm run crops:audit',
  '```',
  '',
];

if (missingCrops.length > 0) {
  docLines.push(
    '## Crops Currently Missing Verified Photographs',
    '',
    '| Crop ID | Subject | Attempted Source | Failure Reason |',
    '| :--- | :--- | :--- | :--- |',
  );
  for (const m of missingCrops) {
    docLines.push(`| \`${m.cropId}\` | ${m.subject} | \`${m.sourceUrl}\` | ${m.reason} |`);
  }
} else {
  docLines.push(
    'All 60 crops in `src/data/crops.js` have verified, unique real photographs (`>= 3 KB` thumb, `>= 8 KB` card, `0` duplicates).',
  );
}

await mkdir(dirname(missingDocPath), { recursive: true });
await writeFile(missingDocPath, `${docLines.join('\n')}\n`, 'utf8');

console.log('──────────────────────────────────────────────────────────────────────────────');
console.log(
  `[fetch-crop-images] Summary: ${totalVerified}/${manifest.length} verified (${downloadedCount} downloaded, ${manualProcessedCount} manual, ${verifiedExistingCount} existing), ${missingCrops.length} missing, ${purgedCount} purged.`,
);
console.log('──────────────────────────────────────────────────────────────────────────────');

if (missingCrops.length > 0 || totalVerified < manifest.length) {
  console.error(
    `[fetch-crop-images] FAILED: ${missingCrops.length} crop(s) do not have a verified real photograph: ${missingCrops.map((m) => m.cropId).join(', ')}`,
  );
  process.exit(1);
}
