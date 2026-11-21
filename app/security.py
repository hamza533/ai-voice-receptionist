"""Authentication: Argon2 passwords, DB-backed sessions, CSRF and rate limits.

- Session cookie: random token, only its SHA-256 is stored; httpOnly, SameSite=Lax,
  Secure in production.
- CSRF: double-submit. The `csrf_token` cookie (readable by JS) must be echoed in the
  `X-CSRF-Token` header on every state-changing request, and must match the session.
- Rate limits: fixed windows counted in Postgres, so they hold across API replicas.
- The agent authenticates with a separate service token (AGENT_SERVICE_TOKEN).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.models import RateLimit, User, UserSession
from app.services.timeutil import utcnow

SESSION_COOKIE = "rcp_session"
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"
SESSION_TTL = timedelta(hours=12)
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def _sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User, response: Response, settings: Settings) -> str:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    db.add(
        UserSession(
            token_hash=_sha(token),
            csrf_token=csrf,
            user_id=user.id,
            expires_at=utcnow() + SESSION_TTL,
        )
    )
    user.last_login_at = utcnow()
    db.commit()
    max_age = int(SESSION_TTL.total_seconds())
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=max_age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return csrf


def destroy_session(db: Session, request: Request, response: Response) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        sess = db.scalar(select(UserSession).where(UserSession.token_hash == _sha(token)))
        if sess:
            db.delete(sess)
            db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def current_session(request: Request, db: Session = Depends(get_db)) -> UserSession:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    sess = db.scalar(select(UserSession).where(UserSession.token_hash == _sha(token)))
    if sess is None or sess.expires_at < utcnow() or not sess.user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    if request.method not in SAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER, "")
        if not sent or not hmac.compare_digest(sent, sess.csrf_token):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF token missing or invalid")
    return sess


def current_user(sess: UserSession = Depends(current_session)) -> User:
    return sess.user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user


def require_agent(request: Request, settings: Settings = Depends(get_settings)) -> None:
    expected = settings.agent_service_token
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if not expected or not token or not hmac.compare_digest(token, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid service token")


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def hit_rate_limit(
    db: Session, key: str, *, limit: int, window: timedelta, now: datetime | None = None
) -> bool:
    """Count one hit; return True when the caller is over the limit for this window."""
    now = now or utcnow()
    seconds = int(window.total_seconds())
    start = datetime.fromtimestamp(int(now.timestamp()) // seconds * seconds, tz=now.tzinfo)
    stmt = (
        pg_insert(RateLimit)
        .values(key=key, window_start=start, count=1)
        .on_conflict_do_update(
            index_elements=["key", "window_start"], set_={"count": RateLimit.count + 1}
        )
        .returning(RateLimit.count)
    )
    count = db.execute(stmt).scalar_one()
    db.commit()
    return count > limit


def rate_limit(name: str, limit: int, window_s: int = 60) -> Callable[..., None]:
    """FastAPI dependency factory: per-IP limit for a named endpoint group."""

    def _dep(request: Request, db: Session = Depends(get_db)) -> None:
        if hit_rate_limit(
            db, f"{name}:{client_ip(request)}", limit=limit, window=timedelta(seconds=window_s)
        ):
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many requests, try again shortly",
                headers={"Retry-After": str(window_s)},
            )

    return _dep
