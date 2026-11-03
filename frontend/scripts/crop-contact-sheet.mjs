import { readFile, stat, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const manifestPath = join(root, 'data', 'crop-image-sources.json');
const creditsPath = join(root, 'src', 'data', 'crop-credits.json');
const cropsDir = join(root, 'public', 'crops');
const outHtmlPath = join(root, 'public', 'crop-preview.html');

function escapeHtml(value = '') {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
let creditsData = { crops: {} };
try {
  creditsData = JSON.parse(await readFile(creditsPath, 'utf8'));
} catch {
  // ignore
}

const cards = [];
for (const entry of manifest) {
  const { cropId, subject, author, license, pageUrl } = entry;
  const credit = creditsData?.crops?.[cropId] || {};
  const thumbPath = join(cropsDir, `${cropId}-thumb.webp`);
  const cardPath = join(cropsDir, `${cropId}-card.webp`);

  let thumbBytes = 0;
  let cardBytes = 0;
  let hash = credit.thumbHash || 'missing';
  try {
    const tStat = await stat(thumbPath);
    const cStat = await stat(cardPath);
    thumbBytes = tStat.size;
    cardBytes = cStat.size;
    const tBuf = await readFile(thumbPath);
    hash = createHash('sha256').update(tBuf).digest('hex').slice(0, 10);
  } catch {
    // missing
  }

  const thumbUrl = `/crops/${cropId}-thumb.webp?v=${hash}`;
  const cardUrl = `/crops/${cropId}-card.webp?v=${hash}`;
  const verified = thumbBytes >= 3072 && cardBytes >= 8192;

  cards.push(`
    <article class="card ${verified ? 'verified' : 'invalid'}">
      <div class="media-row">
        <a href="${escapeHtml(cardUrl)}" target="_blank" rel="noopener noreferrer" title="Open 480x480 card WebP">
          <img src="${escapeHtml(thumbUrl)}" width="128" height="128" alt="${escapeHtml(cropId)}" loading="lazy" />
        </a>
        <div class="meta">
          <div class="id-row">
            <code>${escapeHtml(cropId)}</code>
            <span class="badge ${verified ? 'ok' : 'err'}">${verified ? 'VERIFIED' : 'INVALID'}</span>
          </div>
          <p class="subject">${escapeHtml(subject)}</p>
          <p class="stats">
            Thumb: <strong>${thumbBytes.toLocaleString()} B</strong> · Card: <strong>${cardBytes.toLocaleString()} B</strong><br/>
            SHA-256: <code>${escapeHtml(hash)}</code> · dHash: <code>${escapeHtml(credit.dHash || 'n/a')}</code>
          </p>
          <p class="credit">
            ${escapeHtml(author)} · <a href="${escapeHtml(pageUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(license)}</a>
          </p>
        </div>
      </div>
    </article>
  `);
}

const html = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Field Shift — 60-Crop Visual Contact Sheet</title>
  <style>
    :root {
      color-scheme: light dark;
      font-family: Inter, system-ui, -apple-system, sans-serif;
    }
    body {
      margin: 0;
      padding: 24px;
      background: #0f172a;
      color: #f8fafc;
    }
    header {
      max-width: 1440px;
      margin: 0 auto 24px;
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      border-bottom: 1px solid #334155;
      padding-bottom: 16px;
    }
    h1 {
      margin: 0;
      font-size: 1.5rem;
    }
    .subtitle {
      margin: 4px 0 0;
      color: #94a3b8;
      font-size: 0.9rem;
    }
    .grid {
      max-width: 1440px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
      gap: 14px;
    }
    .card {
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 14px;
      padding: 12px;
    }
    .card.invalid {
      border-color: #ef4444;
      background: #2a1215;
    }
    .media-row {
      display: flex;
      gap: 14px;
      align-items: center;
    }
    img {
      width: 96px;
      height: 96px;
      object-fit: cover;
      border-radius: 12px;
      background: #0f172a;
      border: 1px solid rgba(255,255,255,0.1);
      flex-shrink: 0;
    }
    .meta {
      min-width: 0;
      flex: 1;
    }
    .id-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }
    code {
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.85rem;
      color: #38bdf8;
    }
    .badge {
      font-size: 0.68rem;
      font-weight: 700;
      padding: 2px 7px;
      border-radius: 999px;
    }
    .badge.ok {
      background: rgba(16, 185, 129, 0.18);
      color: #34d399;
    }
    .badge.err {
      background: rgba(239, 68, 68, 0.25);
      color: #fca5a5;
    }
    .subject {
      margin: 4px 0;
      font-size: 0.82rem;
      color: #e2e8f0;
    }
    .stats {
      margin: 4px 0;
      font-size: 0.74rem;
      color: #94a3b8;
      line-height: 1.4;
    }
    .credit {
      margin: 4px 0 0;
      font-size: 0.72rem;
      color: #64748b;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    a {
      color: #34d399;
      text-decoration: none;
    }
    a:hover {
      text-decoration: underline;
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Field Shift — 60-Crop Visual Contact Sheet</h1>
      <p class="subtitle">Generated at ${new Date().toISOString()} · Click any thumbnail to open its 480×480 card WebP</p>
    </div>
    <div>
      <strong>Total: ${manifest.length} crops</strong>
    </div>
  </header>
  <main class="grid">
    ${cards.join('\n')}
  </main>
</body>
</html>
`;

await writeFile(outHtmlPath, html, 'utf8');
console.log(`Wrote visual contact sheet for ${manifest.length} crops to public/crop-preview.html`);

