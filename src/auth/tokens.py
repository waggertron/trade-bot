"""JWT token creation and verification."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

ALGORITHM = "HS256"
DEFAULT_ACCESS_EXPIRE_MINUTES = 30
DEFAULT_REFRESH_EXPIRE_DAYS = 7


def create_access_token(
    *,
    user_id: str,
    secret: str,
    expire_minutes: int = DEFAULT_ACCESS_EXPIRE_MINUTES,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def create_refresh_token(
    *,
    user_id: str,
    secret: str,
    expire_days: int = DEFAULT_REFRESH_EXPIRE_DAYS,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=expire_days),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def create_verification_token(
    *,
    user_id: str,
    secret: str,
    expire_hours: int = 24,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "verification",
        "iat": now,
        "exp": now + timedelta(hours=expire_hours),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_token(token: str, *, secret: str) -> dict:
    """Decode and validate a JWT token. Raises JWTError on failure."""
    return jwt.decode(token, secret, algorithms=[ALGORITHM])
