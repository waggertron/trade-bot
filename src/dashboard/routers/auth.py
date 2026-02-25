"""Authentication endpoints: register, login, refresh, me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from src.auth.passwords import hash_password, verify_password
from src.auth.tokens import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from src.dashboard import dependencies
from src.dashboard.dependencies import _jwt_secret, require_user, state
from src.dashboard.schemas import (  # noqa: TC001
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    UpdateProfileRequest,
)
from src.db.models import UserRecord

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_token_cookies(response: JSONResponse, access_token: str, refresh_token: str) -> None:
    """Set access and refresh tokens as HTTP-only cookies, plus CSRF token."""
    import secrets

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=30 * 60,  # 30 minutes
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=7 * 24 * 60 * 60,  # 7 days
        path="/api/auth/refresh",
    )
    # CSRF token: readable by JavaScript so it can be sent as a header
    response.set_cookie(
        key="csrf_token",
        value=secrets.token_urlsafe(32),
        httponly=False,
        secure=True,
        samesite="strict",
        max_age=30 * 60,
        path="/",
    )


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
    access_token = create_access_token(user_id=user.id, secret=secret)
    refresh_token = create_refresh_token(user_id=user.id, secret=secret)
    body = {
        "user": _user_response(user),
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }
    response = JSONResponse(content=body, status_code=201)
    _set_token_cookies(response, access_token, refresh_token)
    return response


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
    access_token = create_access_token(user_id=user.id, secret=secret)
    refresh_token = create_refresh_token(user_id=user.id, secret=secret)
    body = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }
    response = JSONResponse(content=body)
    _set_token_cookies(response, access_token, refresh_token)
    return response


@router.post("/refresh")
async def refresh(
    request: Request,
    req: RefreshRequest | None = None,
):
    if state.db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    # Accept refresh token from body (API clients) or cookie (browser)
    token = req.refresh_token if req and req.refresh_token else None
    if not token:
        token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token provided")

    secret = _jwt_secret()
    try:
        payload = decode_token(token, secret=secret)
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

    new_access = create_access_token(user_id=user.id, secret=secret)
    body = {"access_token": new_access, "token_type": "bearer"}
    response = JSONResponse(content=body)
    # Update the access_token cookie
    response.set_cookie(
        key="access_token",
        value=new_access,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=30 * 60,
        path="/",
    )
    return response


@router.post("/logout")
async def logout(
    request: Request,
    current_user: UserRecord = Depends(require_user),  # noqa: B008
    token: str | None = Depends(dependencies.oauth2_scheme),
):
    """Revoke the current access token and clear auth cookies."""
    if state.db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    # Try header token first, then cookie
    effective_token = token or request.cookies.get("access_token")
    if effective_token:
        secret = _jwt_secret()
        try:
            payload = decode_token(effective_token, secret=secret)
            jti = payload.get("jti")
            if jti:
                await state.db.revoke_token(jti)
        except Exception:
            pass  # Token already invalid — still clear cookies

    response = JSONResponse(content={"detail": "Logged out"})
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/auth/refresh")
    return response


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
