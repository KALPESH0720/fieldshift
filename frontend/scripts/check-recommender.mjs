// Verifies the rotation engine returns >= 3 results for every season x previous crop.
import { readFileSync } from 'node:fs';
import { runOfflineRotationEngine } from '../src/services/rotationEngine.js';

const src = readFileSync(new URL('../src/data/crops.js', import.meta.url), 'utf8');
const ids = [...src.matchAll(/^\s+\['([a-z-]+)', '/gm)].map((m) => m[1]);
const available = JSON.parse(readFileSync(new URL('../src/data/crops-with-images.json', import.meta.url), 'utf8')).available;
const isAvail = (id) => available.includes(id);
const affected = [];
let combos = 0;
for (const season of ['Rabi', 'Kharif', 'Zaid']) {
  for (const prev of ids.filter(isAvail)) {
    combos += 1;
    const n = runOfflineRotationEngine(season, prev, 1, isAvail).length;
    if (n < 3) affected.push(`${season} after ${prev}: ${n}`);
  }
}
console.log(`[recommender-check] ${combos} combinations, ${affected.length} with fewer than 3 results`);
affected.forEach((a) => console.log('  - ' + a));
process.exit(affected.length ? 1 : 0);

