"""Encryption for secrets kept in the database (the Google refresh token).

The key is derived from SESSION_SECRET, so no extra secret has to be managed. Rotating
SESSION_SECRET makes stored tokens unreadable: the owner then clicks "Connect" again.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import Settings


def _fernet(settings: Settings) -> Fernet:
    digest = hashlib.sha256(f"receptly-secrets:{settings.session_secret}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(settings: Settings, text: str) -> str:
    return _fernet(settings).encrypt(text.encode()).decode()


def decrypt(settings: Settings, token: str) -> str | None:
    try:
        return _fernet(settings).decrypt(token.encode()).decode()
    except InvalidToken:
        return None
