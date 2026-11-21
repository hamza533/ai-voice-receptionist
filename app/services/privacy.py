"""Normalisation and redaction of personal data (phone, email, names)."""

from __future__ import annotations

import re
from typing import Any

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_DIGITS = re.compile(r"\D+")
PII_KEYS = {"phone", "email", "customer_name", "name", "callback_number", "contact", "message"}


def normalize_phone(phone: str) -> str:
    """Digits only, keeping a leading '+' if present. Empty string if nothing usable."""
    phone = (phone or "").strip()
    digits = _DIGITS.sub("", phone)
    if len(digits) < 7:
        return ""
    return ("+" if phone.startswith("+") else "") + digits


def phones_match(a: str, b: str) -> bool:
    """Compare on the last 10 digits so '+92 300 1234567' matches '0300 1234567'."""
    da, db = _DIGITS.sub("", a or ""), _DIGITS.sub("", b or "")
    if len(da) < 7 or len(db) < 7:
        return False
    return da[-10:] == db[-10:]


def normalize_email(email: str) -> str:
    email = (email or "").strip().lower()
    return email if _EMAIL.fullmatch(email) else ""


def mask_phone(phone: str) -> str:
    digits = _DIGITS.sub("", phone or "")
    if len(digits) < 4:
        return "•••"
    return f"•••• {digits[-4:]}"


def mask_email(email: str) -> str:
    if "@" not in (email or ""):
        return ""
    user, domain = email.split("@", 1)
    return f"{user[:1]}•••@{domain}"


def redact(args: dict[str, Any]) -> dict[str, Any]:
    """Copy of tool args with personal data replaced, safe to store and log."""
    out: dict[str, Any] = {}
    for k, v in args.items():
        if k in PII_KEYS and isinstance(v, str) and v:
            if k in {"phone", "callback_number"}:
                out[k] = mask_phone(v)
            elif k == "email":
                out[k] = mask_email(v)
            elif k == "contact":
                out[k] = mask_email(v) if "@" in v else mask_phone(v)
            else:
                out[k] = "[redacted]"
        else:
            out[k] = v
    return out
