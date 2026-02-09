"""Indian license plate format validation and OCR error correction."""

from __future__ import annotations

import re
from typing import Optional

# Standard Indian plate patterns
INDIAN_PLATE_PATTERNS = [
    r"^[A-Z]{2}\d{2}[A-Z]{1,2}\d{4}$",       # Standard: MH12AB1234
    r"^[A-Z]{2}\d{2}[A-Z]{1,3}\d{1,4}$",      # Variations: MH12ABC1234
    r"^[A-Z]{2}\d{2}\d{4}$",                    # Without alpha: MH121234
    r"^\d{2}BH\d{4}[A-Z]{1,2}$",               # BH (Bharat) series: 22BH1234AB
    r"^[A-Z]{2}\d{2}[A-Z]\d{4}$",              # Single letter: MH12A1234
    r"^CD\d{2}\d{4}$",                          # Diplomatic: CD121234
    r"^[A-Z]{2}\d{2}S\d{4}$",                   # Govt/special: DL01S1234
]

# All valid Indian state/UT RTO codes
INDIAN_STATE_CODES = {
    "AN",  # Andaman & Nicobar
    "AP",  # Andhra Pradesh
    "AR",  # Arunachal Pradesh
    "AS",  # Assam
    "BR",  # Bihar
    "CG",  # Chhattisgarh
    "CH",  # Chandigarh
    "DD",  # Dadra & Nagar Haveli and Daman & Diu
    "DL",  # Delhi
    "GA",  # Goa
    "GJ",  # Gujarat
    "HP",  # Himachal Pradesh
    "HR",  # Haryana
    "JH",  # Jharkhand
    "JK",  # Jammu & Kashmir
    "KA",  # Karnataka
    "KL",  # Kerala
    "LA",  # Ladakh
    "MH",  # Maharashtra
    "ML",  # Meghalaya
    "MN",  # Manipur
    "MP",  # Madhya Pradesh
    "MZ",  # Mizoram
    "NL",  # Nagaland
    "OD",  # Odisha
    "PB",  # Punjab
    "PY",  # Puducherry
    "RJ",  # Rajasthan
    "SK",  # Sikkim
    "TN",  # Tamil Nadu
    "TR",  # Tripura
    "TS",  # Telangana
    "UK",  # Uttarakhand
    "UP",  # Uttar Pradesh
    "WB",  # West Bengal
}

# Common OCR misreads mapped by position context
# Position types: 'alpha' (must be letter), 'digit' (must be number)
OCR_CORRECTIONS_TO_ALPHA = {
    "0": "O",
    "1": "I",
    "2": "Z",
    "5": "S",
    "8": "B",
}

OCR_CORRECTIONS_TO_DIGIT = {
    "O": "0",
    "o": "0",
    "I": "1",
    "i": "1",
    "l": "1",
    "L": "1",
    "S": "5",
    "s": "5",
    "Z": "2",
    "z": "2",
    "B": "8",
    "b": "8",
    "G": "6",
    "g": "6",
    "T": "7",
}


def clean_plate_text(raw: str) -> str:
    """Normalize raw OCR text: remove spaces/hyphens, uppercase.

    Args:
        raw: Raw OCR output string.

    Returns:
        Cleaned uppercase string.
    """
    cleaned = raw.replace(" ", "").replace("-", "").replace(".", "").upper()
    # Remove any non-alphanumeric characters
    cleaned = re.sub(r"[^A-Z0-9]", "", cleaned)
    return cleaned


def correct_ocr_errors(text: str) -> str:
    """Apply position-aware OCR error correction for Indian plates.

    Indian plate structure: AA 00 XX 0000
    - Positions 0-1: Always letters (state code)
    - Positions 2-3: Always digits (district code)
    - Positions 4-5 (or 4): Letters (series)
    - Remaining: Digits (number)

    Args:
        text: Cleaned plate text.

    Returns:
        Corrected plate text.
    """
    if len(text) < 6:
        return text

    result = list(text)

    # Positions 0-1: must be alpha (state code)
    for i in range(min(2, len(result))):
        if result[i].isdigit():
            result[i] = OCR_CORRECTIONS_TO_ALPHA.get(result[i], result[i])

    # Positions 2-3: must be digit (district code)
    for i in range(2, min(4, len(result))):
        if result[i].isalpha():
            result[i] = OCR_CORRECTIONS_TO_DIGIT.get(result[i], result[i])

    # Find where the trailing digits start (last 4 chars should be digits)
    # Work backwards from end
    trailing_start = max(4, len(result) - 4)
    for i in range(trailing_start, len(result)):
        if result[i].isalpha():
            result[i] = OCR_CORRECTIONS_TO_DIGIT.get(result[i], result[i])

    # Middle section (between district code and trailing number): must be alpha
    for i in range(4, trailing_start):
        if result[i].isdigit():
            result[i] = OCR_CORRECTIONS_TO_ALPHA.get(result[i], result[i])

    return "".join(result)


def validate_plate(text: str) -> bool:
    """Check if text matches any known Indian plate format.

    Args:
        text: Cleaned (and optionally corrected) plate text.

    Returns:
        True if valid Indian plate format.
    """
    cleaned = clean_plate_text(text)
    return any(re.match(p, cleaned) for p in INDIAN_PLATE_PATTERNS)


def extract_state_code(plate: str) -> Optional[str]:
    """Extract the 2-letter state code from a plate number.

    Args:
        plate: Cleaned plate text.

    Returns:
        State code if valid, None otherwise.
    """
    cleaned = clean_plate_text(plate)
    if len(cleaned) >= 2:
        code = cleaned[:2]
        if code in INDIAN_STATE_CODES:
            return code
    return None


def process_plate(raw_text: str) -> tuple[str, bool, Optional[str]]:
    """Full plate processing pipeline: clean, correct, validate, extract state.

    Args:
        raw_text: Raw OCR output.

    Returns:
        (corrected_text, is_valid, state_code) tuple.
    """
    cleaned = clean_plate_text(raw_text)
    corrected = correct_ocr_errors(cleaned)
    is_valid = validate_plate(corrected)
    state_code = extract_state_code(corrected) if is_valid else None
    return corrected, is_valid, state_code
