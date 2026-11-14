"""Soil Health Card OCR adapter, image preprocessor, Vision LLM client, and layout-agnostic SHC parser.

STRICT ZERO-MOCK POLICY:
Every extracted soil parameter and metadata field must originate strictly and dynamically
from the uploaded image at runtime. Unreadable or absent fields return `None`.
"""

import asyncio
import base64
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.integrations.http import IntegrationUnavailable, request_json
from config.settings import settings

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover
    Image = None
    ImageOps = None


INDIAN_STATES_AND_UTS = (
    "ANDHRA PRADESH",
    "ARUNACHAL PRADESH",
    "ASSAM",
    "BIHAR",
    "CHHATTISGARH",
    "GOA",
    "GUJARAT",
    "HARYANA",
    "HIMACHAL PRADESH",
    "JHARKHAND",
    "KARNATAKA",
    "KERALA",
    "MADHYA PRADESH",
    "MAHARASHTRA",
    "MANIPUR",
    "MEGHALAYA",
    "MIZORAM",
    "NAGALAND",
    "ODISHA",
    "ORISSA",
    "PUNJAB",
    "RAJASTHAN",
    "SIKKIM",
    "TAMIL NADU",
    "TELANGANA",
    "TRIPURA",
    "UTTAR PRADESH",
    "UTTARAKHAND",
    "WEST BENGAL",
    "DELHI",
    "JAMMU AND KASHMIR",
    "LADAKH",
    "PUDUCHERRY",
)

RATING_CANONICAL_MAP = {
    "very low": "Very Low",
    "low": "Low",
    "medium": "Medium",
    "moderate": "Medium",
    "high": "High",
    "very high": "Very High",
    "sufficient": "Sufficient",
    "deficient": "Deficient",
    "normal": "Normal",
    "non saline": "Normal",
    "non-saline": "Normal",
    "acidic": "Acidic",
    "slightly acidic": "Acidic",
    "strongly acidic": "Acidic",
    "neutral": "Neutral",
    "alkaline": "Alkaline",
    "slightly alkaline": "Alkaline",
    "saline": "Alkaline",
}

RATING_REGEX = re.compile(
    r"\b(Very\s+Low|Very\s+High|Slightly\s+Acidic|Strongly\s+Acidic|Slightly\s+Alkaline|"
    r"Non[-\s]?Saline|Acidic|Neutral|Alkaline|Saline|Sufficient|Deficient|Normal|Medium|Moderate|Low|High)\b",
    re.IGNORECASE,
)

UNIT_REGEX_PART = (
    r"(?:dS\s*/\s*m|mS\s*/\s*cm|mmhos\s*/\s*cm|kg\s*/\s*ha|kg\s+ha(?:\s*-\s*1)?|"
    r"mg\s*/\s*kg|ppm|%|g\s*/\s*kg)"
)

PARAMETER_SPECS: tuple[dict[str, Any], ...] = (
    {
        "field": "ph",
        "frontend_key": "ph",
        "default_unit": "",
        "min_val": 1.0,
        "max_val": 14.0,
        "patterns": (
            re.compile(r"\bp\s*\.?\s*H\b(?:\s*\(\s*1\s*:\s*2(?:\.5)?\s*\))?", re.IGNORECASE),
            re.compile(r"\bSoil\s+Reaction\b(?:\s*\(\s*pH\s*\))?", re.IGNORECASE),
        ),
    },
    {
        "field": "ec",
        "frontend_key": "ec",
        "default_unit": "dS/m",
        "min_val": 0.0,
        "max_val": 100.0,
        "patterns": (
            re.compile(r"\bElectrical\s+Conductivity\b(?:\s*\(\s*EC\s*\))?", re.IGNORECASE),
            re.compile(r"\bE\s*\.?\s*C\.?\b", re.IGNORECASE),
        ),
    },
    {
        "field": "organic_matter",
        "frontend_key": "organicCarbon",
        "default_unit": "%",
        "min_val": 0.0,
        "max_val": 50.0,
        "patterns": (
            re.compile(r"\bOrganic\s+Carbon(?:\s*\(\s*O\.?C\.?\s*\))?", re.IGNORECASE),
            re.compile(r"\bOrganic\s+Matter(?:\s*\(\s*O\.?M\.?\s*\))?", re.IGNORECASE),
            re.compile(r"\bO\.?C\.?\s*(?:\(\s*%\s*\))?\b", re.IGNORECASE),
        ),
    },
    {
        "field": "n_val",
        "frontend_key": "nitrogen",
        "default_unit": "kg/ha",
        "min_val": 0.0,
        "max_val": 5000.0,
        "patterns": (
            re.compile(r"\b(?:Available|Avail\.?)\s+Nitrogen(?:\s*\(\s*N\s*\))?", re.IGNORECASE),
            re.compile(r"\bNitrogen\s*\(\s*N\s*\)", re.IGNORECASE),
            re.compile(r"\bNitrogen\b", re.IGNORECASE),
        ),
    },
    {
        "field": "p_val",
        "frontend_key": "phosphorus",
        "default_unit": "kg/ha",
        "min_val": 0.0,
        "max_val": 2000.0,
        "patterns": (
            re.compile(
                r"\b(?:Available|Avail\.?)\s+Phosphor(?:us|ous)(?:\s*\(\s*(?:P|P2O5)\s*\))?",
                re.IGNORECASE,
            ),
            re.compile(r"\bPhosphor(?:us|ous)\s*\(\s*(?:P|P2O5)\s*\)", re.IGNORECASE),
            re.compile(r"\bPhosphor(?:us|ous)\b", re.IGNORECASE),
            re.compile(r"\bP2O5\b", re.IGNORECASE),
        ),
    },
    {
        "field": "k_val",
        "frontend_key": "potassium",
        "default_unit": "kg/ha",
        "min_val": 0.0,
        "max_val": 5000.0,
        "patterns": (
            re.compile(
                r"\b(?:Available|Avail\.?)\s+Potassium(?:\s*\(\s*(?:K|K2O)\s*\))?",
                re.IGNORECASE,
            ),
            re.compile(r"\bPotassium\s*\(\s*(?:K|K2O)\s*\)", re.IGNORECASE),
            re.compile(r"\bPotassium\b", re.IGNORECASE),
            re.compile(r"\bK2O\b", re.IGNORECASE),
        ),
    },
    {
        "field": "s_val",
        "frontend_key": "sulphur",
        "default_unit": "ppm",
        "min_val": 0.0,
        "max_val": 2000.0,
        "patterns": (
            re.compile(r"\b(?:Available|Avail\.?)\s+Sulph?ur(?:\s*\(\s*(?:S|SO4)\s*\))?", re.IGNORECASE),
            re.compile(r"\bSulph?ur\s*\(\s*(?:S|SO4)\s*\)", re.IGNORECASE),
            re.compile(r"\bSulph?ur\b", re.IGNORECASE),
        ),
    },
    {
        "field": "zn_val",
        "frontend_key": "zinc",
        "default_unit": "ppm",
        "min_val": 0.0,
        "max_val": 500.0,
        "patterns": (
            re.compile(r"\b(?:Available|Avail\.?)\s+Zinc(?:\s*\(\s*Zn\s*\))?", re.IGNORECASE),
            re.compile(r"\bZinc\s*\(\s*Zn\s*\)", re.IGNORECASE),
            re.compile(r"\bZinc\b", re.IGNORECASE),
        ),
    },
    {
        "field": "b_val",
        "frontend_key": "boron",
        "default_unit": "ppm",
        "min_val": 0.0,
        "max_val": 500.0,
        "patterns": (
            re.compile(r"\b(?:Available|Avail\.?)\s+Boron(?:\s*\(\s*B\s*\))?", re.IGNORECASE),
            re.compile(r"\bBoron\s*\(\s*B\s*\)", re.IGNORECASE),
            re.compile(r"\bBoron\b", re.IGNORECASE),
        ),
    },
    {
        "field": "fe_val",
        "frontend_key": "iron",
        "default_unit": "ppm",
        "min_val": 0.0,
        "max_val": 2000.0,
        "patterns": (
            re.compile(r"\b(?:Available|Avail\.?)\s+Iron(?:\s*\(\s*Fe\s*\))?", re.IGNORECASE),
            re.compile(r"\bIron\s*\(\s*Fe\s*\)", re.IGNORECASE),
            re.compile(r"\bIron\b", re.IGNORECASE),
        ),
    },
    {
        "field": "mn_val",
        "frontend_key": "manganese",
        "default_unit": "ppm",
        "min_val": 0.0,
        "max_val": 2000.0,
        "patterns": (
            re.compile(
                r"\b(?:Available|Avail\.?)\s+Manganese(?:[\s\n|]*\(\s*Mn\s*\))?",
                re.IGNORECASE,
            ),
            re.compile(r"\bManganese(?:[\s\n|]*\(\s*Mn\s*\))?", re.IGNORECASE),
        ),
    },
    {
        "field": "cu_val",
        "frontend_key": "copper",
        "default_unit": "ppm",
        "min_val": 0.0,
        "max_val": 500.0,
        "patterns": (
            re.compile(r"\b(?:Available|Avail\.?)\s+Copper(?:\s*\(\s*Cu\s*\))?", re.IGNORECASE),
            re.compile(r"\bCopper\s*\(\s*Cu\s*\)", re.IGNORECASE),
            re.compile(r"\bCopper\b", re.IGNORECASE),
        ),
    },
)


class SoilCardMetrics(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    n_val: float | None = Field(default=None, ge=0, alias="N_val")
    p_val: float | None = Field(default=None, ge=0, alias="P_val")
    k_val: float | None = Field(default=None, ge=0, alias="K_val")
    ph: float | None = Field(default=None, ge=0, le=14, alias="pH")
    organic_matter: float | None = Field(default=None, ge=0, alias="organicCarbon")
    ec: float | None = Field(default=None, ge=0, alias="EC")
    s_val: float | None = Field(default=None, ge=0, alias="sulphur")
    zn_val: float | None = Field(default=None, ge=0, alias="zinc")
    b_val: float | None = Field(default=None, ge=0, alias="boron")
    fe_val: float | None = Field(default=None, ge=0, alias="iron")
    mn_val: float | None = Field(default=None, ge=0, alias="manganese")
    cu_val: float | None = Field(default=None, ge=0, alias="copper")
    soil_type: str | None = Field(default=None, alias="soilType")

    raw_values: dict[str, str | None] = Field(default_factory=dict, exclude=True)
    units: dict[str, str | None] = Field(default_factory=dict, exclude=True)
    ratings: dict[str, str | None] = Field(default_factory=dict, exclude=True)
    metadata: dict[str, Any] = Field(default_factory=dict, exclude=True)
    confidence: dict[str, float] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)

    @field_validator("confidence")
    @classmethod
    def valid_confidence(cls, value):
        if any(not 0 <= score <= 1 for score in value.values()):
            raise ValueError("OCR confidence scores must be between 0 and 1")
        return value


def preprocess_soil_card_image_bytes(image: bytes) -> bytes:
    """Dynamically upscale (< 1200px width -> 2x bicubic), convert to grayscale,
    and normalize contrast on a Soil Health Card image before OCR.
    Gracefully returns the original bytes if `image` is not decodable by Pillow.
    """
    if not image or Image is None or ImageOps is None:
        return image
    try:
        with Image.open(io.BytesIO(image)) as im:
            im = ImageOps.exif_transpose(im)
            width, height = im.size
            if width > 0 and width < 1200:
                resample = getattr(Image, "Resampling", Image).BICUBIC
                im = im.resize((width * 2, height * 2), resample=resample)
            gray = im.convert("L")
            enhanced = ImageOps.autocontrast(gray, cutoff=2)
            out = io.BytesIO()
            enhanced.save(out, format="PNG", optimize=True)
            return out.getvalue()
    except Exception:
        return image


def _normalize_unit(raw_unit: str | None, fallback_unit: str = "") -> str:
    if not raw_unit:
        return fallback_unit
    cleaned = re.sub(r"\s+", "", raw_unit).lower()
    if cleaned in {"ds/m", "ms/cm", "mmhos/cm"}:
        return "dS/m"
    if cleaned in {"kg/ha", "kgha-1", "kgha"}:
        return "kg/ha"
    if cleaned in {"ppm", "mg/kg"}:
        return "ppm"
    if cleaned == "%":
        return "%"
    return raw_unit.strip()


def _clean_ocr_line(line: str) -> str:
    if not line:
        return ""
    cleaned = (
        line.replace("\u2014", " ")
        .replace("\u2013", "-")
        .replace("|", " ")
        .replace("[", " ")
        .replace("]", " ")
        .replace("{", "(")
        .replace("}", ")")
        .replace("_", " ")
    )
    cleaned = re.sub(r"(\d),(\d{1,2})(?!\d)", r"\1.\2", cleaned)
    cleaned = re.sub(r"\bkq\s*/\s*ha\b", "kg/ha", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bd[5s]\s*/\s*m\b", "dS/m", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bpp[rn]\b", "ppm", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


def _strip_leading_row_number(line: str) -> str:
    return re.sub(r"^\s*(?:Sr\.?\s*No\.?\s*)?(?:1[0-5]|[1-9])(?:\s*[.):\-])?\s+(?=[A-Za-z(])", "", line).strip()


def _strip_trailing_reference_ranges(segment: str) -> str:
    if not segment:
        return ""
    out = re.sub(
        rf"\b\d+(?:\.\d+)?\s*[-–~]\s*\d+(?:\.\d+)?\s*(?:{UNIT_REGEX_PART})?",
        " ",
        segment,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        rf"(?:[<>≤≥]=?|\b(?:above|below|more\s+than|less\s+than)\b)\s*\d+(?:\.\d+)?\s*(?:{UNIT_REGEX_PART})?",
        " ",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(r"\b7(?:\.0)?\s*,\s*Neutral\b", " ", out, flags=re.IGNORECASE)
    return out


def _extract_value_unit_rating(after_label_text: str, spec: dict[str, Any]) -> dict[str, Any] | None:
    if not after_label_text:
        return None
    remainder = re.sub(
        r"^\s*\(\s*(?:O\.?C\.?|O\.?M\.?|N|P|P2O5|K|K2O|S|SO4|Zn|B|Fe|Mn|Cu|EC|pH|1\s*:\s*2(?:\.5)?)\s*\)\s*",
        " ",
        after_label_text,
        flags=re.IGNORECASE,
    )
    remainder = re.sub(r"^\s*(?:1[0-5]|[1-9])(?:\s*[.):\-])?\s+(?=\d+\.\d+)", " ", remainder)
    cleaned = _strip_trailing_reference_ranges(remainder)

    rating: str | None = None
    rating_match = RATING_REGEX.search(cleaned) or RATING_REGEX.search(remainder)
    if rating_match:
        key = re.sub(r"\s+", " ", rating_match.group(1)).lower()
        rating = RATING_CANONICAL_MAP.get(key, rating_match.group(1))

    value_search_zone = cleaned[: rating_match.start()] if rating_match and rating_match.start() > 0 else cleaned
    value_regex = re.compile(rf"(?<![A-Za-z0-9/.-])(\d+(?:\.\d+)?)\s*({UNIT_REGEX_PART})?", re.IGNORECASE)

    for match in value_regex.finditer(value_search_zone):
        raw_num = match.group(1)
        raw_unit = match.group(2)
        num = float(raw_num)

        prefix = value_search_zone[: match.start()].strip()
        if not prefix and "." not in raw_num and not raw_unit and 1 <= num <= 15:
            after_token = value_search_zone[match.end() :]
            if re.search(r"\d+\.\d+", after_token):
                continue

        if num < spec["min_val"] or num > spec["max_val"]:
            continue

        unit = _normalize_unit(raw_unit, spec["default_unit"])
        return {
            "value": num,
            "raw_value": raw_num,
            "unit": unit,
            "rating": rating,
        }
    return None


def _clean_metadata_value(raw: str | None, stop_pattern: re.Pattern | None = None) -> str | None:
    if not raw:
        return None
    val = raw.strip()
    val = re.split(
        r"\b(?:Soil\s+Health\s+Card|Card\s+No|Farmer'?s?\s+Name|Name\s+of\s+Farmer|Father'?s?\s+Name|"
        r"Address|Village|Sub[-\s]*District|Taluka|Tehsil|Mandal|Panchayat|Pin\s*Code|Mobile|Phone|"
        r"Aadhaar|Sample\s+No|Lab\s+Name|Date\s+of|Survey\s+No|Khasra\s+No|Dag\s+No|Farm\s+Size|"
        r"Land\s+Area|Irrigation|Crop|Latitude|Longitude|Sr\.?\s*No|Parameter)\b",
        val,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    if stop_pattern is not None:
        val = stop_pattern.split(val, maxsplit=1)[0]
    val = re.sub(r"^[\s:.\-|,/]+|[\s:.\-|,/]+$", "", val)
    val = re.sub(r"\s+", " ", val).strip()
    return val if len(val) >= 2 else None


def extract_soil_card_metadata(raw_text: str, cleaned_lines: list[str] | None = None) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "card_number": None,
        "farmer_name": None,
        "soil_type": None,
        "state": None,
        "district": None,
        "sub_district": None,
        "village": None,
        "survey_number": None,
        "farm_size": None,
    }
    if not raw_text:
        return metadata
    if cleaned_lines is None:
        cleaned_lines = [_clean_ocr_line(line) for line in raw_text.splitlines() if _clean_ocr_line(line)]
    joined = "\n".join(cleaned_lines)

    # 1. Card Number
    card_match = re.search(
        r"(?:Soil\s+Health\s+Card\s*(?:Number|No\.?)|SHC\s*(?:Number|No\.?)|Card\s*(?:Number|No\.?))"
        r"[ \t]*[:\-|]?[ \t]*([A-Z0-9]{2,}(?:[ \t]*[/-][ \t]*[A-Z0-9.\-]+)+)",
        joined,
        re.IGNORECASE,
    )
    if card_match:
        metadata["card_number"] = re.sub(r"\s*([/-])\s*", r"\1", card_match.group(1)).strip()
    else:
        standalone = re.search(
            r"\b([A-Z]{2,3}\s*/\s*\d{4}\s*[-–]\s*\d{2,4}\s*/\s*\d+(?:\s*/\s*\d+)?)\b",
            joined,
        )
        if standalone:
            metadata["card_number"] = re.sub(r"\s*([/\-–])\s*", lambda m: "-" if m.group(1) in "-–" else "/", standalone.group(1)).strip()

    # 2. Soil Type
    soil_type_match = re.search(
        r"\b(?:Soil\s+Type|Type\s+of\s+Soil|Soil\s+Texture|Soil\s+Class)[ \t]*[:\-|]?[ \t]*([^\n|]+)",
        joined,
        re.IGNORECASE,
    )
    if soil_type_match:
        metadata["soil_type"] = _clean_metadata_value(soil_type_match.group(1), re.compile(r"\bSoil\s+Type\b", re.I))

    # 3. State
    state_label_match = re.search(
        r"\bState[ \t]*[:\-|]?[ \t]*([A-Za-z][A-Za-z \t.&-]{2,35})",
        joined,
        re.IGNORECASE,
    )
    if state_label_match:
        candidate = _clean_metadata_value(state_label_match.group(1), re.compile(r"\bState\b", re.I))
        if candidate and not re.match(r"^(?:of|government|govt|india|department|ministry|district)\b", candidate, re.I):
            metadata["state"] = candidate

    if not metadata["state"]:
        for line in cleaned_lines:
            banner_match = re.search(
                r"(?:Department\s+of\s+Agriculture(?:\s*(?:&|and)\s*Farmers?\s+Welfare)?|Government\s+of|Govt\.?\s+of)"
                r"[ \t]*[,:\-|]?[ \t]*([A-Za-z][A-Za-z \t]{2,30})",
                line,
                re.IGNORECASE,
            )
            if banner_match:
                candidate = _clean_metadata_value(banner_match.group(1))
                if candidate and not re.match(r"^INDIA\b", candidate, re.I):
                    matched_st = next((st for st in INDIAN_STATES_AND_UTS if st in candidate.upper()), None)
                    metadata["state"] = matched_st or candidate
                    break

    if not metadata["state"]:
        upper_text = joined.upper()
        for st in INDIAN_STATES_AND_UTS:
            if re.search(rf"\b{re.escape(st)}\b", upper_text):
                metadata["state"] = st
                break

    # 4. District (exclude Sub-District)
    for line in cleaned_lines:
        dist_match = re.search(
            r"(?<!Sub-)(?<!Sub )\bDistrict[ \t]*[:\-|]?[ \t]*([A-Za-z][A-Za-z \t.&-]{2,40})",
            line,
            re.IGNORECASE,
        )
        if dist_match:
            candidate = _clean_metadata_value(dist_match.group(1), re.compile(r"(?<!Sub-)(?<!Sub )\bDistrict\b", re.I))
            if candidate and not re.match(r"^(?:sub|name|code)\b", candidate, re.I):
                metadata["district"] = candidate
                break

    if not metadata["district"]:
        for idx in range(len(cleaned_lines) - 1):
            if re.search(r"Department\s+of\s+Agriculture", cleaned_lines[idx], re.I):
                next_line = cleaned_lines[idx + 1].strip()
                if re.match(r"^[A-Z][A-Z \t]{2,30}$", next_line) and not re.search(
                    r"SOIL\s+TEST|SOIL\s+HEALTH|FARMER|SAMPLE|PARAMETER", next_line, re.I
                ):
                    metadata["district"] = next_line
                    break

    # 5. Sub-District & Village
    sub_dist = re.search(
        r"\b(?:Sub[-\s]*District|Taluka|Tehsil|Mandal)[ \t]*[:\-|]?[ \t]*([A-Za-z][A-Za-z \t.&-]{1,35})",
        joined,
        re.IGNORECASE,
    )
    if sub_dist:
        metadata["sub_district"] = _clean_metadata_value(sub_dist.group(1), re.compile(r"\bSub[-\s]*District\b", re.I))

    village_match = re.search(
        r"\bVillage[ \t]*[:\-|]?[ \t]*([A-Za-z][A-Za-z0-9 \t.,&-]{1,40})",
        joined,
        re.IGNORECASE,
    )
    if village_match:
        metadata["village"] = _clean_metadata_value(village_match.group(1), re.compile(r"\bVillage\b", re.I))

    # 6. Farmer Name
    farmer_match = re.search(
        r"\b(?:Farmer'?s?\s+Name|Name\s+of\s+Farmer)[ \t]*[:\-|]?[ \t]*([^\n|]+)",
        joined,
        re.IGNORECASE,
    )
    if farmer_match:
        candidate = _clean_metadata_value(farmer_match.group(1), re.compile(r"\bFarmer'?s?\s+Name", re.I))
        if candidate and not re.match(r"^(?:father|address|village|survey|soil)\b", candidate, re.I):
            metadata["farmer_name"] = candidate

    # 7. Survey No., Khasra No./ Dag No.
    survey_match = re.search(
        r"\b(?:Survey\s*(?:No\.?|Number)?[\s,./\n]*(?:Khasra\s*(?:No\.?|Number)?[\s,./\n]*)?"
        r"(?:Dag\s*(?:No\.?|Number)?[\s,./\n]*)?(?:Gat\s*(?:No\.?|Number)?[\s,./\n]*)?|"
        r"Khasra\s*(?:No\.?|Number)?[\s,./\n]*(?:Dag\s*(?:No\.?|Number)?[\s,./\n]*)?|"
        r"Dag\s*(?:No\.?|Number)?|Gat\s*(?:No\.?|Number)?)[ \t]*[:\-|]?[ \t]*([A-Za-z0-9]+(?:[ \t]*[/-][ \t]*[A-Za-z0-9]+)*)",
        joined,
        re.IGNORECASE,
    )
    if survey_match:
        candidate = _clean_metadata_value(survey_match.group(1))
        if candidate and not re.match(r"^(?:khasra|dag|survey|gat|no|number|farm|size|village)$", candidate, re.I):
            metadata["survey_number"] = re.sub(r"\s*/\s*", "/", candidate)

    # 8. Farm Size
    farm_size_match = re.search(
        r"\b(?:Farm\s+Size|Land\s+Area|Holding\s+Size)(?:\s*\([^)]*\))?[ \t]*[:\-|]?[ \t]*"
        r"(\d+(?:\.\d+)?[ \t]*(?:Acres?|Ac\b|Hectares?|Ha\b|Gunthas?|Bighas?)?)",
        joined,
        re.IGNORECASE,
    )
    if farm_size_match:
        metadata["farm_size"] = _clean_metadata_value(farm_size_match.group(1), re.compile(r"\bFarm\s+Size\b", re.I))

    return metadata


def _line_starts_other_parameter(line: str, current_field: str) -> bool:
    for spec in PARAMETER_SPECS:
        if spec["field"] == current_field:
            continue
        if any(pattern.search(line) for pattern in spec["patterns"]):
            return True
    return False


def parse_soil_health_card_text(raw_text: str) -> SoilCardMetrics:
    """Parse raw OCR text from any Indian Soil Health Card into a `SoilCardMetrics` model.
    Returns `None` for any parameter or metadata field not found in `raw_text`.
    """
    cleaned_lines = [_clean_ocr_line(line) for line in (raw_text or "").splitlines()]
    cleaned_lines = [line for line in cleaned_lines if line]
    stripped_lines = [_strip_leading_row_number(line) for line in cleaned_lines]

    extracted_values: dict[str, float | None] = {}
    raw_values: dict[str, str | None] = {}
    units: dict[str, str | None] = {}
    ratings: dict[str, str | None] = {}
    confidence: dict[str, float] = {}

    for spec in PARAMETER_SPECS:
        field_name = spec["field"]
        frontend_key = spec["frontend_key"]
        found: dict[str, Any] | None = None

        for pattern in spec["patterns"]:
            if found is not None:
                break
            for idx, line in enumerate(stripped_lines):
                match = pattern.search(line)
                if not match:
                    continue
                after_label = line[match.end() :]
                found = _extract_value_unit_rating(after_label, spec)
                if found is not None:
                    break
                if idx + 1 < len(stripped_lines) and not _line_starts_other_parameter(stripped_lines[idx + 1], field_name):
                    combined_two = f"{after_label} {stripped_lines[idx + 1]}"
                    found = _extract_value_unit_rating(combined_two, spec)
                    if found is not None:
                        break
                    if idx + 2 < len(stripped_lines) and not _line_starts_other_parameter(stripped_lines[idx + 2], field_name):
                        combined_three = f"{combined_two} {stripped_lines[idx + 2]}"
                        found = _extract_value_unit_rating(combined_three, spec)
                        if found is not None:
                            break

        if found is not None:
            extracted_values[field_name] = found["value"]
            raw_values[frontend_key] = found["raw_value"]
            units[frontend_key] = found["unit"]
            ratings[frontend_key] = found["rating"]
            confidence[field_name] = 0.92
        else:
            extracted_values[field_name] = None
            raw_values[frontend_key] = None
            units[frontend_key] = None
            ratings[frontend_key] = None

    metadata = extract_soil_card_metadata(raw_text, cleaned_lines)
    return SoilCardMetrics(
        **extracted_values,
        soil_type=metadata.get("soil_type"),
        raw_values=raw_values,
        units=units,
        ratings=ratings,
        metadata=metadata,
        confidence=confidence,
        raw={
            "raw_text": raw_text,
            "raw_values": raw_values,
            "units": units,
            "ratings": ratings,
            "metadata": metadata,
        },
    )


VISION_LLM_PROMPT = """You are an expert Indian Soil Health Card (SHC) optical extraction engine.
Read the uploaded Soil Health Card / agricultural lab report image and extract all visible parameters and metadata.
CRITICAL RULE: Return `null` for any parameter or metadata field that is absent or unreadable on the card.
Never guess, invent, or substitute default numbers. Ignore trailing 'Normal Level' reference ranges (e.g. '280 - 560 kg/ha', '> 10 ppm').
Return ONLY a valid JSON object matching this exact structure:
{
  "parameters": {
    "ph": {"value": <number|null>, "rawValue": <string|null>, "unit": <string|null>, "rating": <string|null>},
    "ec": {"value": <number|null>, "rawValue": <string|null>, "unit": <string|null>, "rating": <string|null>},
    "organicCarbon": {"value": <number|null>, "rawValue": <string|null>, "unit": <string|null>, "rating": <string|null>},
    "nitrogen": {"value": <number|null>, "rawValue": <string|null>, "unit": <string|null>, "rating": <string|null>},
    "phosphorus": {"value": <number|null>, "rawValue": <string|null>, "unit": <string|null>, "rating": <string|null>},
    "potassium": {"value": <number|null>, "rawValue": <string|null>, "unit": <string|null>, "rating": <string|null>},
    "sulphur": {"value": <number|null>, "rawValue": <string|null>, "unit": <string|null>, "rating": <string|null>},
    "zinc": {"value": <number|null>, "rawValue": <string|null>, "unit": <string|null>, "rating": <string|null>},
    "boron": {"value": <number|null>, "rawValue": <string|null>, "unit": <string|null>, "rating": <string|null>},
    "iron": {"value": <number|null>, "rawValue": <string|null>, "unit": <string|null>, "rating": <string|null>},
    "manganese": {"value": <number|null>, "rawValue": <string|null>, "unit": <string|null>, "rating": <string|null>},
    "copper": {"value": <number|null>, "rawValue": <string|null>, "unit": <string|null>, "rating": <string|null>}
  },
  "metadata": {
    "cardNumber": <string|null>,
    "farmerName": <string|null>,
    "soilType": <string|null>,
    "state": <string|null>,
    "district": <string|null>,
    "subDistrict": <string|null>,
    "village": <string|null>,
    "surveyNumber": <string|null>,
    "farmSize": <string|null>
  }
}"""


def _metrics_from_vision_json(payload: dict[str, Any]) -> SoilCardMetrics:
    params = payload.get("parameters") or {}
    meta = payload.get("metadata") or {}
    frontend_to_backend = {spec["frontend_key"]: spec["field"] for spec in PARAMETER_SPECS}

    values: dict[str, float | None] = {}
    raw_values: dict[str, str | None] = {}
    units: dict[str, str | None] = {}
    ratings: dict[str, str | None] = {}
    confidence: dict[str, float] = {}

    for frontend_key, backend_field in frontend_to_backend.items():
        entry = params.get(frontend_key)
        if isinstance(entry, dict) and entry.get("value") is not None:
            try:
                num_val = float(entry["value"])
                values[backend_field] = num_val
                raw_values[frontend_key] = str(entry.get("rawValue") or entry["value"])
                units[frontend_key] = entry.get("unit")
                ratings[frontend_key] = entry.get("rating")
                confidence[backend_field] = 0.96
            except (TypeError, ValueError):
                values[backend_field] = None
                raw_values[frontend_key] = None
                units[frontend_key] = None
                ratings[frontend_key] = None
        else:
            values[backend_field] = None
            raw_values[frontend_key] = None
            units[frontend_key] = None
            ratings[frontend_key] = None

    normalized_meta = {
        "card_number": meta.get("cardNumber") or meta.get("card_number"),
        "farmer_name": meta.get("farmerName") or meta.get("farmer_name"),
        "soil_type": meta.get("soilType") or meta.get("soil_type"),
        "state": meta.get("state"),
        "district": meta.get("district"),
        "sub_district": meta.get("subDistrict") or meta.get("sub_district"),
        "village": meta.get("village"),
        "survey_number": meta.get("surveyNumber") or meta.get("survey_number"),
        "farm_size": meta.get("farmSize") or meta.get("farm_size"),
    }

    return SoilCardMetrics(
        **values,
        soil_type=normalized_meta.get("soil_type"),
        raw_values=raw_values,
        units=units,
        ratings=ratings,
        metadata=normalized_meta,
        confidence=confidence,
        raw={"vision_response": payload, "raw_values": raw_values, "units": units, "ratings": ratings, "metadata": normalized_meta},
    )


def _run_local_tesseract(image: bytes) -> str | None:
    tesseract_bin = shutil.which("tesseract")
    if not tesseract_bin:
        return None
    preprocessed = preprocess_soil_card_image_bytes(image)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(preprocessed)
        tmp_path = tmp.name
    try:
        proc = subprocess.run(
            [tesseract_bin, tmp_path, "stdout", "--oem", "1", "--psm", "6"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout
        return None
    except Exception:
        return None
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


class SoilCardOCRAdapter:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        url: str | None = None,
        api_key: str | None = None,
        attempts: int = 3,
        backoff: float = 0.2,
    ):
        self.client = client
        self.url = url or settings.soil_card_ocr_url
        self.api_key = api_key or (
            settings.soil_card_ocr_api_key.get_secret_value() if settings.soil_card_ocr_api_key else None
        )
        self.attempts = attempts
        self.backoff = backoff

    async def _extract_via_gemini_vision(
        self, image: bytes, *, content_type: str, gemini_api_key: str, endpoint_url: str | None = None
    ) -> SoilCardMetrics:
        target_url = endpoint_url or (
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_api_key}"
        )
        preprocessed = preprocess_soil_card_image_bytes(image)
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": VISION_LLM_PROMPT},
                        {
                            "inline_data": {
                                "mime_type": content_type if content_type in {"image/jpeg", "image/png", "image/webp"} else "image/png",
                                "data": base64.b64encode(preprocessed).decode("ascii"),
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.0,
            },
        }
        data = await request_json(
            "POST",
            target_url,
            client=self.client,
            attempts=self.attempts,
            backoff=self.backoff,
            json=payload,
        )
        try:
            candidates = data.get("candidates") or []
            text_part = candidates[0]["content"]["parts"][0]["text"]
            parsed_json = json.loads(text_part)
            return _metrics_from_vision_json(parsed_json)
        except Exception as exc:
            raise IntegrationUnavailable("Vision LLM returned an invalid structured JSON payload") from exc

    async def extract_metrics(self, image: bytes, *, content_type: str = "image/jpeg") -> SoilCardMetrics:
        if not image:
            raise ValueError("image cannot be empty")

        # 1. Configured OCR / Vision endpoint
        if self.url:
            if "generativelanguage.googleapis.com" in self.url:
                return await self._extract_via_gemini_vision(
                    image, content_type=content_type, gemini_api_key=self.api_key or "", endpoint_url=self.url
                )

            preprocessed = preprocess_soil_card_image_bytes(image)
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            data = await request_json(
                "POST",
                self.url,
                client=self.client,
                attempts=self.attempts,
                backoff=self.backoff,
                headers=headers,
                json={"image": base64.b64encode(preprocessed).decode("ascii"), "content_type": content_type},
            )
            if not isinstance(data, dict):
                raise IntegrationUnavailable("OCR provider returned an unexpected response")

            # Support Vision-structured JSON response (`parameters` + `metadata`)
            if isinstance(data.get("parameters"), dict):
                return _metrics_from_vision_json(data)

            # Support raw OCR text response from provider (`raw_text` / `text` / `ocr_text`)
            raw_ocr_text = data.get("raw_text") or data.get("ocr_text") or data.get("text")
            if isinstance(raw_ocr_text, str) and "metrics" not in data:
                return parse_soil_health_card_text(raw_ocr_text)

            metrics = data.get("metrics", data)
            if not isinstance(metrics, dict):
                raise IntegrationUnavailable("OCR provider omitted soil metrics")
            try:
                confidence = data.get("confidence", metrics.get("confidence", {}))
                if not isinstance(confidence, dict):
                    raise ValueError("confidence must be a field-to-score object")
                aliases = {
                    "N_val": "n_val",
                    "P_val": "p_val",
                    "K_val": "k_val",
                    "pH": "ph",
                    "EC": "ec",
                    "organicCarbon": "organic_matter",
                }
                confidence = {aliases.get(key, key): value for key, value in confidence.items()}
                return SoilCardMetrics.model_validate({**metrics, "confidence": confidence, "raw": data})
            except Exception as exc:
                raise IntegrationUnavailable("OCR provider returned invalid soil metrics") from exc

        # 2. Optional Gemini Vision API key from environment if configured
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if gemini_key:
            return await self._extract_via_gemini_vision(image, content_type=content_type, gemini_api_key=gemini_key)

        # 3. Local Tesseract CLI fallback if installed on host/container
        ocr_text = await asyncio.to_thread(_run_local_tesseract, image)
        if ocr_text is not None:
            return parse_soil_health_card_text(ocr_text)

        raise IntegrationUnavailable("Soil card OCR endpoint is not configured")


async def extract_metrics(image: bytes, **kwargs) -> SoilCardMetrics:
    return await SoilCardOCRAdapter().extract_metrics(image, **kwargs)
