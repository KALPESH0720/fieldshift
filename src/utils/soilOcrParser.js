import { createWorker } from 'tesseract.js';

/**
 * Parses raw text recognized by OCR into structured soil metrics and horizon metadata.
 * If metrics are not in the document, they remain empty string '' (no hardcoded fake values).
 */
export function parseSoilReportText(text = '') {
  const result = {
    form: {
      nitrogen: '',
      phosphorus: '',
      potassium: '',
      ph: '',
      organicCarbon: '',
      ec: '',
    },
    confidence: {},
    detectedInfo: {
      soilName: '',
      horizon: '',
      source: '',
      rawText: text.trim(),
    },
    foundNutrientsCount: 0,
  };

  const normalized = text.replace(/[\r\n]+/g, '\n');

  // 1. Detect Source / Provider
  if (/soils?\.usda\.gov/i.test(normalized)) {
    result.detectedInfo.source = 'USDA Natural Resources Conservation Service (soils.usda.gov)';
  } else if (/soil\s*health\s*card/i.test(normalized)) {
    result.detectedInfo.source = 'Soil Health Card (Govt of India)';
  } else if (/icar|krishi/i.test(normalized)) {
    result.detectedInfo.source = 'ICAR / Krishi Vigyan Kendra';
  } else {
    result.detectedInfo.source = 'Soil Laboratory Report';
  }

  // 2. Detect Horizons & Depth (e.g. USDA horizon card)
  const hasHorizonA = /horizon\s*a|\bA\b[\s\S]{0,10}12/i.test(normalized);
  const hasHorizonB = /horizon\s*b|\b[B8]\b[\s\S]{0,15}(?:24|36)/i.test(normalized);
  const hasHorizonC = /horizon\s*c|\b[Cc]\b[\s\S]{0,15}(?:48|60|72)/i.test(normalized);
  if (hasHorizonA || hasHorizonB || hasHorizonC) {
    const horizons = [];
    if (hasHorizonA) horizons.push('Horizon A (0–12″)');
    if (hasHorizonB) horizons.push('Horizon B (12–36″)');
    if (hasHorizonC) horizons.push('Horizon C (36–72″)');
    result.detectedInfo.horizon = horizons.join(', ');
  }

  // 3. Detect Soil Name / Series
  const nameMatch = normalized.match(/soil\s*name\s*[:_]*\s*([^\r\n_]{2,35})/i);
  if (nameMatch && nameMatch[1]) {
    const rawVal = nameMatch[1].trim();
    if (rawVal && !/^(horizon|sample|date|id|card|survey|table|soil\s*name)$/i.test(rawVal)) {
      result.detectedInfo.soilName = rawVal;
    }
  }
  if (!result.detectedInfo.soilName) {
    if (/usda/i.test(normalized)) {
      result.detectedInfo.soilName = 'USDA Soil Survey Profile';
    } else if (/laterite/i.test(normalized)) {
      result.detectedInfo.soilName = 'Laterite Soil Series';
    } else {
      result.detectedInfo.soilName = 'Soil Profile';
    }
  }

  // 4. Extract pH (3.0 - 10.5)
  const phMatch = normalized.match(/(?:soil\s*ph|ph\s*val(?:ue)?|\bph\b)[:\s=]*([0-9]+(?:\.[0-9]+)?)/i);
  if (phMatch) {
    const val = parseFloat(phMatch[1]);
    if (val >= 3.0 && val <= 10.5) {
      result.form.ph = String(val);
      result.confidence.ph = 0.95;
      result.foundNutrientsCount++;
    }
  }

  // 5. Extract Nitrogen (0 - 800 kg/ha)
  const nMatch = normalized.match(/(?:available\s*nitrogen|nitrogen(?:\s*\(?N\)?)?|avail(?:able)?\s*N|N\s*val(?:ue)?|(?:\bN\s*[:=]))[:\s=]*([0-9]+(?:\.[0-9]+)?)/i);
  if (nMatch) {
    const val = parseFloat(nMatch[1]);
    if (val >= 0 && val <= 800) {
      result.form.nitrogen = String(val);
      result.confidence.nitrogen = 0.92;
      result.foundNutrientsCount++;
    }
  }

  // 6. Extract Phosphorus (0 - 250 kg/ha)
  const pMatch = normalized.match(/(?:available\s*phosphorus|phosphorus(?:\s*\(?P\)?)?|P2O5|avail(?:able)?\s*P|P\s*val(?:ue)?|(?:\bP\s*[:=]))[:\s=]*([0-9]+(?:\.[0-9]+)?)/i);
  if (pMatch) {
    const val = parseFloat(pMatch[1]);
    if (val >= 0 && val <= 250) {
      result.form.phosphorus = String(val);
      result.confidence.phosphorus = 0.90;
      result.foundNutrientsCount++;
    }
  }

  // 7. Extract Potassium (0 - 800 kg/ha)
  const kMatch = normalized.match(/(?:available\s*potassium|potassium(?:\s*\(?K\)?)?|K2O|avail(?:able)?\s*K|K\s*val(?:ue)?|(?:\bK\s*[:=]))[:\s=]*([0-9]+(?:\.[0-9]+)?)/i);
  if (kMatch) {
    const val = parseFloat(kMatch[1]);
    if (val >= 0 && val <= 800) {
      result.form.potassium = String(val);
      result.confidence.potassium = 0.91;
      result.foundNutrientsCount++;
    }
  }

  // 8. Extract Organic Carbon / Matter (0 - 10%)
  const ocMatch = normalized.match(/(?:organic\s*carbon|organic\s*matter|\bOC\b|\bOM\b)[:\s=]*([0-9]+(?:\.[0-9]+)?)/i);
  if (ocMatch) {
    const val = parseFloat(ocMatch[1]);
    if (val >= 0 && val <= 10.0) {
      result.form.organicCarbon = String(val);
      result.confidence.organicCarbon = 0.88;
      result.foundNutrientsCount++;
    }
  }

  // 9. Extract EC / Salinity (0 - 15 dS/m)
  const ecMatch = normalized.match(/(?:electrical\s*conductivity|salinity|\bEC\b)[:\s=]*([0-9]+(?:\.[0-9]+)?)/i);
  if (ecMatch) {
    const val = parseFloat(ecMatch[1]);
    if (val >= 0 && val <= 15.0) {
      result.form.ec = String(val);
      result.confidence.ec = 0.90;
      result.foundNutrientsCount++;
    }
  }

  return result;
}

/**
 * Runs client-side OCR using Tesseract.js worker with safety timeout.
 * Automatically tries local pre-bundled tessdata for fast offline OCR, with CDN fallback.
 */
export async function recognizeSoilReport(imageFile) {
  let worker = null;
  try {
    const isBrowser = typeof window !== 'undefined';
    const workerOptions = isBrowser
      ? {
          langPath: `${window.location.origin}/tessdata`,
          gzip: true,
        }
      : {
          langPath: 'c:/Users/manas/OneDrive/Desktop/nasa/fieldshift',
          gzip: false,
        };

    try {
      worker = await createWorker('eng', 1, workerOptions);
    } catch (optErr) {
      console.warn('Custom worker options failed, falling back to standard createWorker:', optErr);
      worker = await createWorker('eng');
    }

    const ret = await Promise.race([
      worker.recognize(imageFile),
      new Promise((_, reject) => setTimeout(() => reject(new Error('OCR Timeout')), 25000)),
    ]);
    const text = ret?.data?.text || '';
    return parseSoilReportText(text);
  } catch (err) {
    console.warn('Client OCR parsing notice:', err);
    return parseSoilReportText('');
  } finally {
    if (worker) {
      try {
        await worker.terminate();
      } catch (_) {}
    }
  }
}
