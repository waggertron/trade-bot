"""Authentication endpoints: register, login, refresh, me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.auth.passwords import hash_password, verify_password
from src.auth.tokens import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from src.dashboard.dependencies import _jwt_secret, require_user, state
from src.dashboard.schemas import (  # noqa: TC001
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    UpdateProfileRequest,
)
from src.db.models import UserRecord

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_response(user: UserRecord) -> dict:
    """Serialize user for API responses, excluding sensitive fields."""
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest):
    if state.db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    existing = await state.db.get_user_by_email(req.email)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = UserRecord(
        email=req.email,
        hashed_password=hash_password(req.password),
        name=req.name,
    )
    await state.db.create_user(user)

    secret = _jwt_secret()
    return {
        "user": _user_response(user),
        "access_token": create_access_token(user_id=user.id, secret=secret),
        "refresh_token": create_refresh_token(user_id=user.id, secret=secret),
        "token_type": "bearer",
    }


@router.post("/login")
async def login(req: LoginRequest):
    if state.db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    user = await state.db.get_user_by_email(req.email)
    if user is None or user.hashed_password is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    secret = _jwt_secret()
    return {
        "access_token": create_access_token(user_id=user.id, secret=secret),
        "refresh_token": create_refresh_token(user_id=user.id, secret=secret),
        "token_type": "bearer",
    }


@router.post("/refresh")
async def refresh(req: RefreshRequest):
    if state.db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    secret = _jwt_secret()
    try:
        payload = decode_token(req.refresh_token, secret=secret)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from None

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = await state.db.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    return {
        "access_token": create_access_token(user_id=user.id, secret=secret),
        "token_type": "bearer",
    }


@router.get("/me")
async def me(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    return _user_response(current_user)


@router.put("/me")
async def update_me(
    req: UpdateProfileRequest,
    current_user: UserRecord = Depends(require_user),  # noqa: B008
):
    if state.db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    updates: dict = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.password is not None:
        updates["hashed_password"] = hash_password(req.password)

    if updates:
        await state.db.update_user(current_user.id, **updates)

    updated = await state.db.get_user_by_id(current_user.id)
    return _user_response(updated)  # type: ignore[arg-type]


@router.get("/verify/{token}")
async def verify_email(token: str):
    """Verify a user's email address using a verification token."""
    if state.db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    secret = _jwt_secret()
    try:
        payload = decode_token(token, secret=secret)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification token",
        ) from None

    if payload.get("type") != "verification":
        raise HTTPException(status_code=400, detail="Invalid verification token")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=400, detail="Invalid verification token")

    user = await state.db.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    await state.db.update_user(user_id, is_verified=True)
    return {"verified": True, "user_id": user_id}
