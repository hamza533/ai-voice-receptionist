"""Google OAuth for the "Connect Google Calendar" button (authorization-code flow).

The owner signs in with Google once; we keep only the refresh token (encrypted) and the
calendar they pick. No service account, calendar sharing or pasted IDs needed.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - endpoint, not a secret
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"
SCOPES = ["openid", "email", CALENDAR_SCOPE]


class OAuthError(Exception):
    pass


def redirect_uri(settings: Settings) -> str:
    return settings.public_url.rstrip("/") + "/api/integrations/google/callback"


def auth_url(settings: Settings, state: str) -> str:
    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": redirect_uri(settings),
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",  # we need a refresh token
        "prompt": "consent",  # always return one, even on reconnect
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def exchange_code(
    settings: Settings, code: str, transport: httpx.BaseTransport | None = None
) -> dict[str, Any]:
    with httpx.Client(timeout=15, transport=transport) as client:
        resp = client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "redirect_uri": redirect_uri(settings),
                "grant_type": "authorization_code",
            },
        )
    if resp.status_code != 200:
        raise OAuthError(f"token exchange failed ({resp.status_code})")
    tokens: dict[str, Any] = resp.json()
    if not tokens.get("refresh_token"):
        raise OAuthError("Google did not return a refresh token")
    return tokens


def account_email(access_token: str, transport: httpx.BaseTransport | None = None) -> str:
    with httpx.Client(timeout=10, transport=transport) as client:
        resp = client.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
    return str(resp.json().get("email", "")) if resp.status_code == 200 else ""


def revoke(token: str, transport: httpx.BaseTransport | None = None) -> None:
    """Best effort: the local connection is removed even if Google can't be reached."""
    try:
        with httpx.Client(timeout=10, transport=transport) as client:
            client.post(REVOKE_URL, data={"token": token})
    except httpx.HTTPError:
        pass
