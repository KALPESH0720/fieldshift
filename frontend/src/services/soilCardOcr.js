/**
 * soilCardOcr.js
 * Generalized, layout-agnostic Indian Soil Health Card (SHC) & lab report
 * image preprocessor, OCR runner, and dynamic text parser.
 *
 * STRICT ZERO-MOCK POLICY:
 * Every extracted parameter and metadata value is derived strictly at runtime
 * from the uploaded image. Unreadable or absent fields return `null`.
 */

import { apiRequest } from '../api/client.js';

export const SHC_PARAMETER_KEYS = [
  'ph',
  'ec',
  'organicCarbon',
  'nitrogen',
  'phosphorus',
  'potassium',
  'sulphur',
  'zinc',
  'boron',
  'iron',
  'manganese',
  'copper',
];

export const SHC_METADATA_KEYS = [
  'cardNumber',
  'farmerName',
  'soilType',
  'state',
  'district',
  'subDistrict',
  'village',
  'surveyNumber',
  'farmSize',
];

const INDIAN_STATES_AND_UTS = [
  'ANDHRA PRADESH',
  'ARUNACHAL PRADESH',
  'ASSAM',
  'BIHAR',
  'CHHATTISGARH',
  'GOA',
  'GUJARAT',
  'HARYANA',
  'HIMACHAL PRADESH',
  'JHARKHAND',
  'KARNATAKA',
  'KERALA',
  'MADHYA PRADESH',
  'MAHARASHTRA',
  'MANIPUR',
  'MEGHALAYA',
  'MIZORAM',
  'NAGALAND',
  'ODISHA',
  'ORISSA',
  'PUNJAB',
  'RAJASTHAN',
  'SIKKIM',
  'TAMIL NADU',
  'TELANGANA',
  'TRIPURA',
  'UTTAR PRADESH',
  'UTTARAKHAND',
  'WEST BENGAL',
  'ANDAMAN AND NICOBAR',
  'CHANDIGARH',
  'DADRA AND NAGAR HAVELI',
  'DAMAN AND DIU',
  'DELHI',
  'JAMMU AND KASHMIR',
  'LADAKH',
  'LAKSHADWEEP',
  'PUDUCHERRY',
];

/**
 * Parameter definitions ordered with full labels first and symbol fallbacks second.
 */
const PARAMETER_DEFINITIONS = [
  {
    id: 'ph',
    backendKey: 'ph',
    defaultUnit: '',
    min: 0,
    max: 14,
    patterns: [
      /\bSoil\s+Reaction\s*(?:\(\s*p\s*H\s*\))?/i,
      /\bReaction\s*\(\s*p\s*H\s*\)/i,
      /\bp\s*H(?:\s*\(\s*1\s*:\s*2(?:\.5)?\s*\))?\b/i,
    ],
  },
  {
    id: 'ec',
    backendKey: 'ec',
    defaultUnit: 'dS/m',
    min: 0,
    max: 100,
    patterns: [
      /\bElectrical\s+Conductivit[yie]\s*(?:\(\s*E\.?\s*C\.?\s*\))?/i,
      /\bConductivit[yie]\s*\(\s*E\.?\s*C\.?\s*\)/i,
      /\bE\.?\s*C\.?\b/i,
    ],
  },
  {
    id: 'organicCarbon',
    backendKey: 'organic_matter',
    defaultUnit: '%',
    min: 0,
    max: 100,
    patterns: [
      /\bOrgani[ce]\s+Carb[oa]n\s*(?:\(\s*O\.?\s*C\.?\s*\))?/i,
      /\bWalkley\s*[-\s]*Black\s*(?:O\.?\s*C\.?)?/i,
      /\(\s*O\.?\s*C\.?\s*\)/i,
      /\bO\.?\s*C\.?(?=\s*[:|-]?\s*\d)/i,
    ],
  },
  {
    id: 'nitrogen',
    backendKey: 'n_val',
    defaultUnit: 'kg/ha',
    min: 0,
    max: 10000,
    patterns: [
      /\bAvailable\s+Nitrog[ce]n\s*(?:\(\s*N\s*\))?/i,
      /\bNitrog[ce]n\s*(?:\(\s*N\s*\))?/i,
      /\bAlk\.?\s*KMnO4\s*[-\s]*N\b/i,
      /\bAvailable\s+N\b/i,
      /\(\s*N\s*\)(?=\s*\d)/i,
    ],
  },
  {
    id: 'phosphorus',
    backendKey: 'p_val',
    defaultUnit: 'kg/ha',
    min: 0,
    max: 10000,
    patterns: [
      /\bAvailable\s+Phosph?or[ou]{1,2}s\s*(?:\(\s*(?:P|P2O5|P₂O₅)\s*\))?/i,
      /\bPhosph?or[ou]{1,2}s\s*(?:\(\s*(?:P|P2O5|P₂O₅)\s*\))?/i,
      /\bAvailable\s+(?:P2O5|P₂O₅|P)\b/i,
      /\b(?:Olsen|Bray)\s*[-\s]*P\b/i,
      /\(\s*(?:P|P2O5|P₂O₅)\s*\)(?=\s*\d)/i,
    ],
  },
  {
    id: 'potassium',
    backendKey: 'k_val',
    defaultUnit: 'kg/ha',
    min: 0,
    max: 10000,
    patterns: [
      /\bAvailable\s+Potass?ium\s*(?:\(\s*(?:K|K2O|K₂O)\s*\))?/i,
      /\bPotass?ium\s*(?:\(\s*(?:K|K2O|K₂O)\s*\))?/i,
      /\bAvailable\s+(?:Potash|K2O|K₂O|K)\b/i,
      /\bPotash\s*(?:\(\s*(?:K|K2O|K₂O)\s*\))?/i,
      /\(\s*(?:K|K2O|K₂O)\s*\)(?=\s*\d)/i,
    ],
  },
  {
    id: 'sulphur',
    backendKey: 's_val',
    defaultUnit: 'ppm',
    min: 0,
    max: 10000,
    patterns: [
      /\bAvailable\s+Su[l1i](?:ph|f)ur\s*(?:\(\s*S\s*\))?/i,
      /\bSu[l1i](?:ph|f)ur\s*(?:\(\s*S\s*\))?/i,
      /\bAvailable\s+S\b/i,
      /\bSO4\s*[-\s]*S\b/i,
      /\(\s*S\s*\)(?=\s*\d)/i,
    ],
  },
  {
    id: 'zinc',
    backendKey: 'zn_val',
    defaultUnit: 'ppm',
    min: 0,
    max: 10000,
    patterns: [
      /\bAvailable\s+Z[i1l]nc\s*(?:\(\s*Zn\s*\))?/i,
      /\bZ[i1l]nc\s*(?:\(\s*Zn\s*\))?/i,
      /\bDTPA\s*[-\s]*Zn\b/i,
      /\bAvailable\s+Zn\b/i,
      /\(\s*Zn\s*\)/i,
    ],
  },
  {
    id: 'boron',
    backendKey: 'b_val',
    defaultUnit: 'ppm',
    min: 0,
    max: 10000,
    patterns: [
      /\bAvailable\s+B[o0]r[o0]n\s*(?:\(\s*B\s*\))?/i,
      /\bB[o0]r[o0]n\s*(?:\(\s*B\s*\))?/i,
      /\bHot\s+Water\s+B\b/i,
      /\bAvailable\s+B\b/i,
      /\(\s*B\s*\)(?=\s*\d)/i,
    ],
  },
  {
    id: 'iron',
    backendKey: 'fe_val',
    defaultUnit: 'ppm',
    min: 0,
    max: 10000,
    patterns: [
      /\bAvailable\s+[I1l]r[o0]n\s*(?:\(\s*Fe\s*\))?/i,
      /\b[I1l]r[o0]n\s*(?:\(\s*Fe\s*\))?/i,
      /\bDTPA\s*[-\s]*Fe\b/i,
      /\bAvailable\s+Fe\b/i,
      /\(\s*Fe\s*\)/i,
    ],
  },
  {
    id: 'manganese',
    backendKey: 'mn_val',
    defaultUnit: 'ppm',
    min: 0,
    max: 10000,
    patterns: [
      /\bAvailable\s+Mang[ae]n[ce]s[ce]?\s*(?:\(\s*Mn\s*\))?/i,
      /\bMang[ae]n[ce]s[ce]?\s*(?:\(\s*Mn\s*\))?/i,
      /\bDTPA\s*[-\s]*Mn\b/i,
      /\bAvailable\s+Mn\b/i,
      /\(\s*Mn\s*\)/i,
    ],
  },
  {
    id: 'copper',
    backendKey: 'cu_val',
    defaultUnit: 'ppm',
    min: 0,
    max: 10000,
    patterns: [
      /\bAvailable\s+C[o0]pp[ce]r\s*(?:\(\s*Cu\s*\))?/i,
      /\bC[o0]pp[ce]r\s*(?:\(\s*Cu\s*\))?/i,
      /\bDTPA\s*[-\s]*Cu\b/i,
      /\bAvailable\s+Cu\b/i,
      /\(\s*Cu\s*\)/i,
    ],
  },
];

const RATING_REGEX = /\b(Very\s+Low|Very\s+High|Slightly\s+Acidic|Moderately\s+Acidic|Strongly\s+Acidic|Slightly\s+Alkaline|Moderately\s+Alkaline|Strongly\s+Alkaline|Non[-\s]*Saline|Acidic|Neutral|Alkaline|Saline|Normal|Sufficient|Deficient|Low|Medium|Moderate|High|Excessive|Critical)\b/i;

/**
 * Normalize OCR unit strings into canonical units (`dS/m`, `%`, `kg/ha`, `ppm`, `mg/kg`).
 */
export function normalizeSoilUnit(rawUnit, fallback = '') {
  if (!rawUnit) return fallback;
  const cleaned = String(rawUnit).trim().toLowerCase().replace(/\s+/g, '');
  if (!cleaned) return fallback;
  if (cleaned === '%') return '%';
  if (/^(?:ds\/m|d5\/m|0s\/m|ds1m|dsim|ds\/rn|ms\/cm|mmhos\/cm)$/i.test(cleaned)) {
    return 'dS/m';
  }
  if (/^(?:kg\/ha|kgha|kg\/ba|kglha|kg1ha)$/i.test(cleaned)) {
    return 'kg/ha';
  }
  if (/^(?:ppm|p\.p\.m|ppn|ppin)$/i.test(cleaned)) {
    return 'ppm';
  }
  if (/^(?:mg\/kg|mgkg)$/i.test(cleaned)) {
    return 'mg/kg';
  }
  return rawUnit.trim();
}

/**
 * Normalize a rating string to clean title case.
 */
function normalizeRating(rawRating) {
  if (!rawRating) return null;
  return String(rawRating)
    .trim()
    .replace(/\s+/g, ' ')
    .split(' ')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

/**
 * Clean OCR line noise: strip table border characters while preserving decimal
 * points, slashes, percent signs, and numeric hyphen ranges.
 */
export function cleanOcrLine(line) {
  if (!line) return '';
  return String(line)
    // Replace vertical bars, brackets, underscores, tildes with spaces
    .replace(/[|[\]{}¦~_]+/g, ' ')
    // Normalize en-dash / em-dash between digits to standard hyphen for range detection
    .replace(/(\d)\s*[–—]\s*(\d)/g, '$1 - $2')
    // Replace standalone en-dash / em-dash with space
    .replace(/\s+[–—]+\s+/g, ' ')
    // Fix OCR letter 'O' before decimal point (e.g. "O.37" -> "0.37")
    .replace(/\b[Oo]\.(\d+)/g, '0.$1')
    // Fix comma decimal separator when immediately followed by 1-2 digits and unit/space (not "7, Neutral")
    .replace(/(\d),(\d{1,2})(?=\s*(?:dS|ds|kg|ppm|%|mg|\b))/g, '$1.$2')
    // Normalize common OCR unit misreads glued to numbers
    .replace(/(\d)\s*(?:d5\/m|dS\/rn|dSim|dS1m)\b/gi, '$1 dS/m')
    .replace(/(\d)\s*(?:kglha|kg1ha|kg\/ba|kgha)\b/gi, '$1 kg/ha')
    .replace(/(\d)\s*(?:ppn|ppin)\b/gi, '$1 ppm')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Strip leading serial / row number (`1` through `15`) at the start of a table line.
 */
function stripLeadingRowNumber(line) {
  if (!line) return '';
  return line
    .replace(/^\s*(?:sr\.?\s*no\.?\s*)?(?:1[0-5]|0?[1-9])\s*(?:[.):-]\s*|\s+)(?=[A-Za-z(])/i, '')
    .trim();
}

/**
 * Check if a line starts with another distinct parameter label (used to avoid
 * merging across two different parameters when scanning multi-line windows).
 */
function lineStartsNewParameter(line, currentParamId) {
  const stripped = stripLeadingRowNumber(line);
  for (const def of PARAMETER_DEFINITIONS) {
    if (def.id === currentParamId) continue;
    if (def.patterns[0].test(stripped)) {
      return true;
    }
  }
  return false;
}

/**
 * Extract the FIRST valid test value, unit, and rating from the text appearing
 * after a parameter's name, ignoring trailing "Normal Level" reference ranges.
 */
function extractValueUnitRating(afterLabelText, paramDef) {
  if (!afterLabelText) return null;

  let s = String(afterLabelText);

  // 1. Strip any immediate parenthetical symbol or dilution ratio belonging to the label
  s = s.replace(/^\s*\(\s*[A-Za-z0-9₂₅₄:\s.]+\s*\)\s*/, '');

  // 2. Strip chemical formula tokens so digits in P2O5 / K2O / SO4 are never treated as values
  s = s.replace(/\b(?:P2O5|P₂O₅|K2O|K₂O|SO4|SO₄|CaCO3|NO3|NH4)\b/gi, ' ');

  // 3. Strip displaced row serial number (1-15) if followed by (Symbol) or another number
  s = s.replace(
    /^\s*(?:1[0-5]|0?[1-9])\s+(?=(?:\([A-Za-z0-9]+\)\s*)?\d+(?:\.\d+)?)/,
    '',
  );
  s = s.replace(/^\s*\(\s*[A-Za-z0-9]+\s*\)\s*/, '');

  // 4. Remove trailing "Normal Level" reference ranges and inequality thresholds
  //    e.g. "280 - 560 kg/ha", "11-26kg/ha", "> 10 ppm", "< 1.0 dS/m", "7, Neutral"
  const withoutRanges = s
    .replace(
      /[<>≤≥]=?\s*\d+(?:\.\d+)?(?:\s*(?:dS\s*\/\s*m|ds\s*\/\s*m|mS\s*\/\s*cm|kg\s*\/\s*ha|ppm|mg\s*\/\s*kg|%))?/gi,
      ' ',
    )
    .replace(
      /\b\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?(?:\s*(?:dS\s*\/\s*m|ds\s*\/\s*m|mS\s*\/\s*cm|kg\s*\/\s*ha|ppm|mg\s*\/\s*kg|%))?/gi,
      ' ',
    )
    .replace(/\b7(?:\.0+)?\s*,\s*Neutral\b/gi, ' ');

  // 5. Locate the first numeric/decimal value and optional glued/spaced unit
  const valueMatch = withoutRanges.match(
    /(?:^|[\s:=|])(\d+(?:\.\d+)?)\s*(dS\s*\/\s*m|ds\s*\/\s*m|mS\s*\/\s*cm|mmhos\s*\/\s*cm|kg\s*\/\s*ha|ppm|mg\s*\/\s*kg|g\s*\/\s*kg|%)?/i,
  );
  if (!valueMatch) return null;

  // Ensure a rating keyword did not appear BEFORE this number (which would mean
  // the test value cell was empty and this number came from the Normal Level column)
  const prefixBeforeValue = withoutRanges.slice(0, valueMatch.index);
  if (RATING_REGEX.test(prefixBeforeValue)) {
    return null;
  }

  const rawValue = valueMatch[1];
  const numericValue = Number.parseFloat(rawValue);
  if (!Number.isFinite(numericValue)) return null;
  if (numericValue < paramDef.min || numericValue > paramDef.max) return null;

  const matchedUnit = valueMatch[2] || '';
  const unit = normalizeSoilUnit(matchedUnit, paramDef.defaultUnit);

  // 6. Dynamically capture the first rating keyword appearing after the test value
  const afterValueText = withoutRanges.slice(valueMatch.index + valueMatch[0].length);
  const ratingMatch = afterValueText.match(RATING_REGEX) || s.match(RATING_REGEX);
  const rating = ratingMatch ? normalizeRating(ratingMatch[1]) : null;

  return {
    value: numericValue,
    rawValue,
    unit,
    rating,
  };
}

/**
 * Truncate metadata value at the earliest occurrence of any other known SHC field label
 * on the same line (handles side-by-side 2-column Farmer Details / Sample Details tables).
 */
const METADATA_STOP_PATTERNS = [
  /\bSoil\s+Health\s+Card/i,
  /\bSHC\s*(?:Number|No\.?)/i,
  /\bFarmer'?s?\s+Name/i,
  /\bName\s+of\s+Farmer/i,
  /\bFather'?s?\s+Name/i,
  /\bHusband'?s?\s+Name/i,
  /\bAddress\b/i,
  /\bVillage\b/i,
  /\bSub[-\s]*District\b/i,
  /\bTaluka\b/i,
  /\bTehsil\b/i,
  /\bMandal\b/i,
  /(?<!Sub[-\s])(?<!Sub)\bDistrict\b/i,
  /\bState\b/i,
  /\bPIN(?:\s*Code)?\b/i,
  /\bPincode\b/i,
  /\bMobile\b/i,
  /\bPhone\b/i,
  /\bAadhaar\b/i,
  /\bSample\s+(?:Collected|Number|No\.?)/i,
  /\bValidity\b/i,
  /\bSurvey\s*No/i,
  /\bKhasra\s*No/i,
  /\bDag\s*No/i,
  /\bGat\s*No/i,
  /\bFarm\s+Size\b/i,
  /\bLand\s+Area\b/i,
  /\bGeo\s+Position\b/i,
  /\bGPS\b/i,
  /\bLatitude\b/i,
  /\bLongitude\b/i,
  /\bIrrigated\b/i,
  /\bRainfed\b/i,
  /\bSoil\s+Type\b/i,
  /\bSoil\s+Test\s+Results\b/i,
];

function cleanMetadataValue(rawVal, selfPattern = null) {
  if (!rawVal) return null;
  let cleaned = String(rawVal)
    .replace(/^[\s:|\-–—,./]+/, '')
    .trim();

  for (const stopRegex of METADATA_STOP_PATTERNS) {
    if (selfPattern && stopRegex.source === selfPattern.source) continue;
    const match = cleaned.match(stopRegex);
    if (match && match.index !== undefined) {
      cleaned = cleaned.slice(0, match.index).trim();
    }
  }

  cleaned = cleaned.replace(/[\s:|\-–—,]+$/, '').trim();
  return cleaned.length > 0 ? cleaned : null;
}

/**
 * Extract metadata fields (`soilType`, `district`, `state`, `cardNumber`,
 * `farmerName`, `surveyNumber`, `farmSize`, `subDistrict`, `village`)
 * regardless of whether the metadata section is at the top, bottom, or side.
 */
export function extractSoilCardMetadata(rawText, cleanedLines) {
  const metadata = {
    cardNumber: null,
    farmerName: null,
    soilType: null,
    state: null,
    district: null,
    subDistrict: null,
    village: null,
    surveyNumber: null,
    farmSize: null,
    farmSizeValue: null,
    farmSizeUnit: null,
  };

  if (!rawText) return metadata;
  const joinedText = cleanedLines.join('\n');

  // 1. Soil Health Card Number
  // Match explicit label first, or standard Indian SHC slash-delimited code (e.g. AP/2017-18/35499766/2)
  const cardLabelMatch = joinedText.match(
    /(?:Soil\s+Health\s+Card\s*(?:Number|No\.?)|SHC\s*(?:Number|No\.?)|Card\s*(?:Number|No\.?))\s*[:|-]?\s*([A-Z0-9]{2,}(?:\s*[/-]\s*[A-Z0-9.-]+)+)/i,
  );
  if (cardLabelMatch) {
    metadata.cardNumber = cardLabelMatch[1].replace(/\s*([/-])\s*/g, '$1').trim();
  } else {
    const standaloneShcCode = joinedText.match(
      /\b([A-Z]{2,3}\s*\/\s*\d{4}\s*[-–]\s*\d{2,4}\s*\/\s*\d+(?:\s*\/\s*\d+)?)\b/,
    );
    if (standaloneShcCode) {
      metadata.cardNumber = standaloneShcCode[1]
        .replace(/\s*\/\s*/g, '/')
        .replace(/\s*[-–]\s*/g, '-')
        .trim();
    }
  }

  // 2. Soil Type (e.g. "Soil Type: Black soil")
  const soilTypeMatch = joinedText.match(
    /\b(?:Soil\s+Type|Type\s+of\s+Soil|Soil\s+Texture|Soil\s+Class)\s*[:\-|]?\s*([^\n|]+)/i,
  );
  if (soilTypeMatch) {
    metadata.soilType = cleanMetadataValue(soilTypeMatch[1], /\bSoil\s+Type\b/i);
  }

  // 3. State
  // Check explicit "State:" label, then "Department of Agriculture, <STATE>", then known state names in header
  const stateLabelMatch = joinedText.match(
    /\bState[ \t]*[:\-|]?[ \t]*([A-Za-z][A-Za-z \t.&-]{2,35})/i,
  );
  if (stateLabelMatch) {
    const candidate = cleanMetadataValue(stateLabelMatch[1], /\bState\b/i);
    if (candidate && !/^(?:of|government|govt|india|department|ministry|district)\b/i.test(candidate)) {
      metadata.state = candidate;
    }
  }
  if (!metadata.state) {
    for (const line of cleanedLines) {
      const deptBannerMatch = line.match(
        /(?:Department\s+of\s+Agriculture(?:\s*(?:&|and)\s*Farmers?\s+Welfare)?|Government\s+of|Govt\.?\s+of)[ \t]*[,:\-|]?[ \t]*([A-Za-z][A-Za-z \t]{2,30})/i,
      );
      if (deptBannerMatch) {
        const candidate = cleanMetadataValue(deptBannerMatch[1]);
        if (candidate && !/^INDIA\b/i.test(candidate)) {
          const matchedState = INDIAN_STATES_AND_UTS.find((st) =>
            candidate.toUpperCase().includes(st),
          );
          metadata.state = matchedState || candidate;
          break;
        }
      }
    }
  }
  if (!metadata.state) {
    const upperText = joinedText.toUpperCase();
    for (const st of INDIAN_STATES_AND_UTS) {
      const stateRegex = new RegExp(`\\b${st.replace(/\s+/g, '\\s+')}\\b`, 'i');
      if (stateRegex.test(upperText)) {
        metadata.state = st;
        break;
      }
    }
  }

  // 4. District (ensure "Sub-District" is not matched as "District")
  for (const line of cleanedLines) {
    const distMatch = line.match(
      /(?<!Sub[-\s])(?<!Sub)\bDistrict[ \t]*[:\-|]?[ \t]*([A-Za-z][A-Za-z \t.&-]{2,40})/i,
    );
    if (distMatch) {
      const candidate = cleanMetadataValue(
        distMatch[1],
        /(?<!Sub[-\s])(?<!Sub)\bDistrict\b/i,
      );
      if (candidate && !/^(?:sub|name|code)\b/i.test(candidate)) {
        metadata.district = candidate;
        break;
      }
    }
  }
  // Fallback for banner layout where District line is directly below "DEPARTMENT OF AGRICULTURE, <STATE>"
  if (!metadata.district) {
    for (let i = 0; i < cleanedLines.length - 1; i += 1) {
      if (/Department\s+of\s+Agriculture/i.test(cleanedLines[i])) {
        const nextLine = cleanedLines[i + 1].trim();
        if (
          /^[A-Z][A-Z \t]{2,30}$/.test(nextLine) &&
          !/SOIL\s+TEST|SOIL\s+HEALTH|FARMER|SAMPLE|PARAMETER/i.test(nextLine)
        ) {
          metadata.district = nextLine;
          break;
        }
      }
    }
  }

  // 5. Sub-District & Village
  const subDistMatch = joinedText.match(
    /\b(?:Sub[-\s]*District|Taluka|Tehsil|Mandal)[ \t]*[:\-|]?[ \t]*([A-Za-z][A-Za-z \t.&-]{1,35})/i,
  );
  if (subDistMatch) {
    metadata.subDistrict = cleanMetadataValue(subDistMatch[1], /\bSub[-\s]*District\b/i);
  }

  const villageMatch = joinedText.match(
    /\bVillage[ \t]*[:\-|]?[ \t]*([A-Za-z][A-Za-z0-9 \t.,&-]{1,40})/i,
  );
  if (villageMatch) {
    metadata.village = cleanMetadataValue(villageMatch[1], /\bVillage\b/i);
  }

  // 6. Farmer Name
  const farmerMatch = joinedText.match(
    /\b(?:Farmer'?s?\s+Name|Name\s+of\s+Farmer)\s*[:\-|]?\s*([^\n|]+)/i,
  );
  if (farmerMatch) {
    const candidate = cleanMetadataValue(farmerMatch[1], /\bFarmer'?s?\s+Name/i);
    if (candidate && !/^(?:father|address|village|survey|soil)\b/i.test(candidate)) {
      metadata.farmerName = candidate;
    }
  }

  // 7. Survey No., Khasra No./ Dag No. (supports single-line or multi-line wrapped label)
  const surveyMatch = joinedText.match(
    /\b(?:Survey\s*(?:No\.?|Number)?[\s,./\n]*(?:Khasra\s*(?:No\.?|Number)?[\s,./\n]*)?(?:Dag\s*(?:No\.?|Number)?[\s,./\n]*)?(?:Gat\s*(?:No\.?|Number)?[\s,./\n]*)?|Khasra\s*(?:No\.?|Number)?[\s,./\n]*(?:Dag\s*(?:No\.?|Number)?[\s,./\n]*)?|Dag\s*(?:No\.?|Number)?|Gat\s*(?:No\.?|Number)?)\s*[:\-|]?\s*([A-Za-z0-9]+(?:\s*[/-]\s*[A-Za-z0-9]+)*)/i,
  );
  if (surveyMatch) {
    const candidate = cleanMetadataValue(surveyMatch[1]);
    if (
      candidate &&
      !/^(?:khasra|dag|survey|gat|no|number|farm|size|village)$/i.test(candidate)
    ) {
      metadata.surveyNumber = candidate.replace(/\s*\/\s*/g, '/');
    }
  }

  // 8. Farm Size / Land Area (e.g. "1.19 Acre", "0.48 Ha")
  const farmSizeMatch = joinedText.match(
    /\b(?:Farm\s+Size|Land\s+Area|Holding\s+Size)(?:\s*\([^)]*\))?\s*[:\-|]?\s*(\d+(?:\.\d+)?\s*(?:Acres?|Ac\b|Hectares?|Ha\b|Gunthas?|Bighas?)?)/i,
  );
  if (farmSizeMatch) {
    const rawFarmSize = cleanMetadataValue(farmSizeMatch[1], /\bFarm\s+Size\b/i);
    if (rawFarmSize) {
      metadata.farmSize = rawFarmSize;
      const numMatch = rawFarmSize.match(/(\d+(?:\.\d+)?)/);
      if (numMatch) {
        metadata.farmSizeValue = Number.parseFloat(numMatch[1]);
      }
      if (/hectare|\bha\b/i.test(rawFarmSize)) {
        metadata.farmSizeUnit = 'hectares';
      } else if (/acre|\bac\b/i.test(rawFarmSize)) {
        metadata.farmSizeUnit = 'acres';
      } else if (/guntha/i.test(rawFarmSize)) {
        metadata.farmSizeUnit = 'guntha';
      } else if (/bigha/i.test(rawFarmSize)) {
        metadata.farmSizeUnit = 'bigha';
      }
    }
  }

  return metadata;
}

/**
 * Generalized, layout-agnostic parser for Indian Soil Health Card OCR text.
 * Extracts all 12 standard soil parameters, their units and ratings, and card metadata.
 * Returns `null` for any parameter or metadata field not present in `rawText`.
 */
export function parseSoilHealthCardText(rawText) {
  const parameters = {};
  const values = {};
  const rawValues = {};
  const units = {};
  const ratings = {};

  for (const key of SHC_PARAMETER_KEYS) {
    parameters[key] = { value: null, rawValue: null, unit: null, rating: null };
    values[key] = null;
    rawValues[key] = null;
    units[key] = null;
    ratings[key] = null;
  }

  if (!rawText || typeof rawText !== 'string' || !rawText.trim()) {
    return {
      parameters,
      values,
      rawValues,
      units,
      ratings,
      metadata: extractSoilCardMetadata('', []),
      extractedCount: 0,
      rawText: rawText || '',
    };
  }

  const rawLines = rawText.replace(/\r\n/g, '\n').split('\n');
  const cleanedLines = rawLines.map(cleanOcrLine).filter(Boolean);
  const strippedLines = cleanedLines.map(stripLeadingRowNumber);

  let extractedCount = 0;

  for (const paramDef of PARAMETER_DEFINITIONS) {
    let found = null;

    for (const pattern of paramDef.patterns) {
      if (found) break;

      for (let i = 0; i < strippedLines.length; i += 1) {
        const line = strippedLines[i];
        const match = line.match(pattern);
        if (!match || match.index === undefined) continue;

        const afterLabel = line.slice(match.index + match[0].length);
        found = extractValueUnitRating(afterLabel, paramDef);
        if (found) break;

        // Multi-line wrap handling (e.g. "11 Available Manganese\n(Mn) 20.10 ppm Sufficient > 2.0 ppm")
        if (i + 1 < strippedLines.length && !lineStartsNewParameter(strippedLines[i + 1], paramDef.id)) {
          const combinedTwo = `${afterLabel} ${strippedLines[i + 1]}`;
          found = extractValueUnitRating(combinedTwo, paramDef);
          if (found) break;

          if (
            i + 2 < strippedLines.length &&
            !lineStartsNewParameter(strippedLines[i + 2], paramDef.id)
          ) {
            const combinedThree = `${combinedTwo} ${strippedLines[i + 2]}`;
            found = extractValueUnitRating(combinedThree, paramDef);
            if (found) break;
          }
        }
      }
    }

    if (found) {
      parameters[paramDef.id] = found;
      values[paramDef.id] = found.value;
      rawValues[paramDef.id] = found.rawValue;
      units[paramDef.id] = found.unit;
      ratings[paramDef.id] = found.rating;
      extractedCount += 1;
    }
  }

  const metadata = extractSoilCardMetadata(rawText, cleanedLines);

  return {
    parameters,
    values,
    rawValues,
    units,
    ratings,
    metadata,
    extractedCount,
    rawText,
  };
}

/**
 * Load an image File/Blob into an HTMLImageElement in browser context.
 */
function loadImageFromFile(fileOrBlob) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(fileOrBlob);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };
    img.onerror = (err) => {
      URL.revokeObjectURL(url);
      reject(err || new Error('Failed to decode Soil Health Card image'));
    };
    img.src = url;
  });
}

/**
 * Preprocess a Soil Health Card image for OCR:
 * 1. Upscale low-resolution images (< 1200px width, e.g. WhatsApp captures) by 2x using high-quality canvas scaling.
 * 2. Convert to luminance grayscale.
 * 3. Apply 2nd–98th percentile histogram contrast normalization so text inside colored
 *    rating boxes (green, yellow, orange) and dense table grids remains sharp and legible.
 */
export async function preprocessSoilCardImage(fileOrBlob) {
  if (typeof document === 'undefined') {
    return {
      blob: fileOrBlob,
      dataUrl: null,
      scaleFactor: 1,
      width: 0,
      height: 0,
    };
  }

  const img = await loadImageFromFile(fileOrBlob);
  const srcWidth = img.naturalWidth || img.width || 1;
  const srcHeight = img.naturalHeight || img.height || 1;

  // Upscale images under 1200px width by 2x
  const scaleFactor = srcWidth < 1200 ? 2 : 1;
  const targetWidth = Math.min(srcWidth * scaleFactor, 3600);
  const targetHeight = Math.round((srcHeight * targetWidth) / srcWidth);

  const canvas = document.createElement('canvas');
  canvas.width = targetWidth;
  canvas.height = targetHeight;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });

  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(img, 0, 0, targetWidth, targetHeight);

  const imageData = ctx.getImageData(0, 0, targetWidth, targetHeight);
  const data = imageData.data;
  const pixelCount = targetWidth * targetHeight;

  // Pass 1: Luminance grayscale + 256-bin histogram
  const histogram = new Uint32Array(256);
  const luminances = new Uint8Array(pixelCount);

  for (let i = 0, p = 0; i < data.length; i += 4, p += 1) {
    const lum = Math.round(0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]);
    luminances[p] = lum;
    histogram[lum] += 1;
  }

  // Compute 2nd and 98th percentile bounds for contrast stretching
  const lowThreshold = Math.floor(pixelCount * 0.02);
  const highThreshold = Math.ceil(pixelCount * 0.98);

  let pLow = 0;
  let cumulative = 0;
  for (let v = 0; v < 256; v += 1) {
    cumulative += histogram[v];
    if (cumulative >= lowThreshold) {
      pLow = v;
      break;
    }
  }

  let pHigh = 255;
  cumulative = 0;
  for (let v = 255; v >= 0; v -= 1) {
    cumulative += histogram[v];
    if (cumulative >= pixelCount - highThreshold) {
      pHigh = v;
      break;
    }
  }

  const range = Math.max(1, pHigh - pLow);

  // Pass 2: Normalize contrast and boost separation between dark ink and colored cell backgrounds
  for (let i = 0, p = 0; i < data.length; i += 4, p += 1) {
    let norm = ((luminances[p] - pLow) * 255) / range;
    if (norm < 0) norm = 0;
    if (norm > 255) norm = 255;

    // Gentle S-curve contrast enhancement preserving anti-aliased decimal points
    const normalized01 = norm / 255;
    const contrasted =
      normalized01 < 0.5
        ? 0.5 * Math.pow(2 * normalized01, 1.25)
        : 1 - 0.5 * Math.pow(2 * (1 - normalized01), 1.25);
    const out = Math.round(contrasted * 255);

    data[i] = out;
    data[i + 1] = out;
    data[i + 2] = out;
    data[i + 3] = 255;
  }

  ctx.putImageData(imageData, 0, 0);

  const blob = await new Promise((resolve) => {
    canvas.toBlob((b) => resolve(b || fileOrBlob), 'image/png');
  });
  const dataUrl = canvas.toDataURL('image/png');

  return {
    blob,
    dataUrl,
    scaleFactor,
    originalWidth: srcWidth,
    originalHeight: srcHeight,
    width: targetWidth,
    height: targetHeight,
  };
}

/**
 * Convert a Blob/File to a base64 payload (without data URL prefix).
 */
function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = String(reader.result || '');
      const commaIdx = result.indexOf(',');
      resolve(commaIdx >= 0 ? result.slice(commaIdx + 1) : result);
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

let tesseractModulePromise = null;

/**
 * Dynamically load Tesseract.js from local package if installed, or CDN fallback.
 */
async function loadTesseract() {
  if (typeof globalThis !== 'undefined' && globalThis.Tesseract) {
    return globalThis.Tesseract;
  }
  if (tesseractModulePromise) {
    return tesseractModulePromise;
  }

  tesseractModulePromise = (async () => {
    try {
      const localSpec = 'tesseract.js';
      const mod = await import(/* @vite-ignore */ localSpec);
      return mod.default || mod;
    } catch {
      // Fallback to jsDelivr ESM / script bundle in browser
      try {
        const cdnSpec = 'https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.esm.min.js';
        const mod = await import(/* @vite-ignore */ cdnSpec);
        return mod.default || mod;
      } catch {
        if (typeof document !== 'undefined') {
          await new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js';
            script.async = true;
            script.onload = resolve;
            script.onerror = () => reject(new Error('Could not load Tesseract OCR engine'));
            document.head.appendChild(script);
          });
          if (globalThis.Tesseract) return globalThis.Tesseract;
        }
        throw new Error('Tesseract OCR engine is unavailable');
      }
    }
  })();

  try {
    return await tesseractModulePromise;
  } catch (err) {
    tesseractModulePromise = null;
    throw err;
  }
}

/**
 * Merge two parsed extraction objects, keeping non-null fields from `primary`
 * and filling any missing (`null`) fields from `secondary`.
 */
export function mergeParsedExtractions(primary, secondary) {
  if (!primary) return secondary;
  if (!secondary) return primary;

  const parameters = { ...primary.parameters };
  const values = { ...primary.values };
  const rawValues = { ...primary.rawValues };
  const units = { ...primary.units };
  const ratings = { ...primary.ratings };

  let extractedCount = 0;
  for (const key of SHC_PARAMETER_KEYS) {
    if (values[key] == null && secondary.values?.[key] != null) {
      parameters[key] = secondary.parameters[key];
      values[key] = secondary.values[key];
      rawValues[key] = secondary.rawValues[key];
      units[key] = secondary.units[key];
      ratings[key] = secondary.ratings[key];
    } else if (!ratings[key] && secondary.ratings?.[key]) {
      ratings[key] = secondary.ratings[key];
      if (parameters[key]) parameters[key].rating = secondary.ratings[key];
    }
    if (values[key] != null) extractedCount += 1;
  }

  const metadata = { ...primary.metadata };
  for (const mKey of Object.keys(metadata)) {
    if (metadata[mKey] == null && secondary.metadata?.[mKey] != null) {
      metadata[mKey] = secondary.metadata[mKey];
    }
  }

  return {
    parameters,
    values,
    rawValues,
    units,
    ratings,
    metadata,
    extractedCount,
    rawText: [primary.rawText, secondary.rawText].filter(Boolean).join('\n---\n'),
  };
}

/**
 * Normalize backend OCR response into the unified frontend extraction shape.
 */
export function normalizeBackendExtraction(backendData) {
  if (!backendData || typeof backendData !== 'object') return null;

  const metrics = backendData.extracted_metrics || backendData.metrics || backendData;
  const rawText = backendData.raw_text || metrics.raw_text || '';
  const textParsed = rawText ? parseSoilHealthCardText(rawText) : parseSoilHealthCardText('');

  const keyMap = {
    ph: ['ph', 'pH'],
    ec: ['ec', 'EC'],
    organicCarbon: ['organicCarbon', 'organic_carbon', 'organic_matter'],
    nitrogen: ['nitrogen', 'n_val', 'N_val'],
    phosphorus: ['phosphorus', 'p_val', 'P_val'],
    potassium: ['potassium', 'k_val', 'K_val'],
    sulphur: ['sulphur', 's_val', 'S_val'],
    zinc: ['zinc', 'zn_val', 'Zn_val'],
    boron: ['boron', 'b_val', 'B_val'],
    iron: ['iron', 'fe_val', 'Fe_val'],
    manganese: ['manganese', 'mn_val', 'Mn_val'],
    copper: ['copper', 'cu_val', 'Cu_val'],
  };

  const backendUnits = metrics.units || backendData.units || {};
  const backendRatings = metrics.ratings || backendData.ratings || {};

  let extractedCount = 0;
  for (const paramDef of PARAMETER_DEFINITIONS) {
    const aliases = keyMap[paramDef.id] || [paramDef.id];
    let val = null;
    for (const alias of aliases) {
      if (metrics[alias] != null && metrics[alias] !== '') {
        val = metrics[alias];
        break;
      }
    }

    if (val != null) {
      const numVal = Number.parseFloat(val);
      if (Number.isFinite(numVal)) {
        const rawStr = typeof val === 'string' ? val.trim() : String(numVal);
        const unit = normalizeSoilUnit(
          backendUnits[paramDef.id] || backendUnits[paramDef.backendKey],
          paramDef.defaultUnit,
        );
        const rating = normalizeRating(
          backendRatings[paramDef.id] || backendRatings[paramDef.backendKey] || null,
        );
        textParsed.parameters[paramDef.id] = {
          value: numVal,
          rawValue: rawStr,
          unit,
          rating,
        };
        textParsed.values[paramDef.id] = numVal;
        textParsed.rawValues[paramDef.id] = rawStr;
        textParsed.units[paramDef.id] = unit;
        textParsed.ratings[paramDef.id] = rating;
      }
    }
    if (textParsed.values[paramDef.id] != null) {
      extractedCount += 1;
    }
  }

  const metaSource = metrics.metadata || backendData.metadata || metrics;
  const metaMap = {
    cardNumber: ['cardNumber', 'card_number', 'shc_number'],
    farmerName: ['farmerName', 'farmer_name'],
    soilType: ['soilType', 'soil_type'],
    state: ['state'],
    district: ['district'],
    subDistrict: ['subDistrict', 'sub_district'],
    village: ['village'],
    surveyNumber: ['surveyNumber', 'survey_number'],
    farmSize: ['farmSize', 'farm_size'],
  };

  for (const [mKey, aliases] of Object.entries(metaMap)) {
    for (const alias of aliases) {
      if (metaSource[alias] != null && String(metaSource[alias]).trim() !== '') {
        textParsed.metadata[mKey] = String(metaSource[alias]).trim();
        break;
      }
    }
  }

  textParsed.extractedCount = extractedCount;
  return textParsed;
}

/**
 * Full end-to-end dynamic extraction pipeline for an uploaded Soil Health Card image:
 * 1. Dynamically preprocesses image on canvas (2x upscale if < 1200px, grayscale, contrast normalization).
 * 2. Attempts backend OCR / Vision extraction (`/soil-cards/extract`) if reachable.
 * 3. Runs client-side Tesseract OCR on the preprocessed image (and merges with raw image pass if needed).
 * 4. Returns strictly what was detected in the image; missing fields remain `null`.
 */
export async function extractSoilCardFromImage(file, { onProgress } = {}) {
  if (!file) {
    throw new Error('No Soil Health Card image provided');
  }

  onProgress?.({ stage: 'preprocessing', progress: 0.1 });
  const preprocessed = await preprocessSoilCardImage(file);

  let backendResult = null;
  if (typeof navigator === 'undefined' || navigator.onLine !== false) {
    try {
      onProgress?.({ stage: 'backend_ocr', progress: 0.25 });
      const base64Image = await blobToBase64(preprocessed.blob || file);
      const response = await apiRequest('/soil-cards/extract', {
        method: 'POST',
        body: {
          image: base64Image,
          content_type: 'image/png',
        },
        timeoutMs: 12000,
      });
      backendResult = normalizeBackendExtraction(response);
      if (backendResult && backendResult.extractedCount >= 6) {
        onProgress?.({ stage: 'complete', progress: 1 });
        return {
          ...backendResult,
          preprocessing: {
            scaleFactor: preprocessed.scaleFactor,
            originalWidth: preprocessed.originalWidth,
            originalHeight: preprocessed.originalHeight,
            processedWidth: preprocessed.width,
            processedHeight: preprocessed.height,
          },
          source: 'backend',
        };
      }
    } catch {
      // Backend OCR endpoint unavailable or unconfigured; proceed with client-side OCR
    }
  }

  onProgress?.({ stage: 'client_ocr', progress: 0.35 });
  const Tesseract = await loadTesseract();

  const recognizeSource = async (imageSource, progressOffset, progressSpan) => {
    const result = await Tesseract.recognize(imageSource, 'eng', {
      logger: (m) => {
        if (m?.status === 'recognizing text' && Number.isFinite(m.progress)) {
          onProgress?.({
            stage: 'recognizing',
            progress: Math.min(0.95, progressOffset + m.progress * progressSpan),
          });
        }
      },
    });
    return result?.data?.text || '';
  };

  // Pass 1: Preprocessed image (2x upscaled, grayscale, contrast-normalized)
  const preprocessedText = await recognizeSource(preprocessed.blob || file, 0.35, 0.45);
  let parsed = parseSoilHealthCardText(preprocessedText);

  // Pass 2: If some parameters or metadata were missed (e.g. colored header banners),
  // run a second pass on the original image and merge non-null detections.
  if (parsed.extractedCount < 10 || !parsed.metadata.soilType || !parsed.metadata.cardNumber) {
    const rawText = await recognizeSource(file, 0.8, 0.15);
    const rawParsed = parseSoilHealthCardText(rawText);
    parsed = mergeParsedExtractions(parsed, rawParsed);
  }

  if (backendResult) {
    parsed = mergeParsedExtractions(backendResult, parsed);
  }

  onProgress?.({ stage: 'complete', progress: 1 });

  return {
    ...parsed,
    preprocessing: {
      scaleFactor: preprocessed.scaleFactor,
      originalWidth: preprocessed.originalWidth,
      originalHeight: preprocessed.originalHeight,
      processedWidth: preprocessed.width,
      processedHeight: preprocessed.height,
    },
    source: 'tesseract_ocr',
  };
}
