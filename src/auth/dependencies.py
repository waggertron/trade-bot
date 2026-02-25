"""FastAPI dependencies for authentication."""

from __future__ import annotations

from fastapi import HTTPException, status
from jose import JWTError

from src.auth.tokens import decode_token
from src.db.database import Database
from src.db.models import UserRecord


async def get_current_user(
    *,
    token: str,
    db: Database,
    secret: str,
) -> UserRecord:
    """Validate an access token and return the corresponding user."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token, secret=secret)
    except JWTError:
        raise credentials_exc

    if payload.get("type") != "access":
        raise credentials_exc

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise credentials_exc

    user = await db.get_user_by_id(user_id)
    if user is None:
        raise credentials_exc

    return user
