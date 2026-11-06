"""Phone input policy: unprefixed ten-digit Indian mobiles map to +91; otherwise require E.164."""

import re


def canonicalize_phone(phone: str) -> str:
    value = phone.strip()
    if re.fullmatch(r"[6-9][0-9]{9}", value):
        return "+91" + value
    if re.fullmatch(r"\+[1-9][0-9]{7,14}", value):
        return value
    raise ValueError("Phone must be E.164, or a ten-digit Indian mobile beginning 6-9")
