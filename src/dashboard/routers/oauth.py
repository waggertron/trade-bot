"""OAuth endpoints: provider redirect and callback for Google/GitHub."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.auth.oauth import SUPPORTED_PROVIDERS, oauth
from src.auth.tokens import create_access_token, create_refresh_token
from src.dashboard.dependencies import state
from src.db.models import OAuthAccountRecord, UserRecord

router = APIRouter(prefix="/api/auth/oauth", tags=["oauth"])


def _jwt_secret() -> str:
    if state.settings is None or not state.settings.auth.jwt_secret_key:
        raise HTTPException(status_code=503, detail="Auth not configured")
    return state.settings.auth.jwt_secret_key


def _generate_state_token() -> str:
    """Generate a signed CSRF state token: nonce.signature."""
    secret = _jwt_secret()
    nonce = secrets.token_urlsafe(32)
    sig = hmac.new(secret.encode(), nonce.encode(), hashlib.sha256).hexdigest()
    return f"{nonce}.{sig}"


def _verify_state_token(state_token: str) -> bool:
    """Verify that a state token was signed by us."""
    secret = _jwt_secret()
    parts = state_token.split(".", 1)
    if len(parts) != 2:
        return False
    nonce, sig = parts
    expected_sig = hmac.new(secret.encode(), nonce.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected_sig)


def _user_response(user: UserRecord) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
    }


@router.get("/{provider}")
async def oauth_redirect(provider: str, redirect_uri: str):
    """Return the OAuth authorization URL for the given provider."""
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    client = oauth.create_client(provider)
    if client is None:
        raise HTTPException(status_code=503, detail=f"Provider {provider} not configured")

    state_token = _generate_state_token()

    # Build the authorization URL
    if provider == "google":
        metadata = await client.load_server_metadata()
        authorize_url = metadata.get("authorization_endpoint", "")
        params = {
            "client_id": client.client_id,
            "redirect_uri": redirect_uri,
            "scope": "openid email profile",
            "response_type": "code",
            "state": state_token,
        }
    else:
        authorize_url = "https://github.com/login/oauth/authorize"
        params = {
            "client_id": client.client_id,
            "redirect_uri": redirect_uri,
            "scope": "user:email",
            "state": state_token,
        }

    # Build full URL with params
    param_str = "&".join(f"{k}={v}" for k, v in params.items())
    full_url = f"{authorize_url}?{param_str}"
    return {"authorize_url": full_url, "state": state_token}


class OAuthCallbackRequest(BaseModel):
    code: str
    redirect_uri: str
    state: str | None = None


async def _fetch_oauth_user_info(
    provider: str,
    code: str,
    redirect_uri: str,
) -> tuple[str, str, str]:
    """Exchange code for token and fetch user info. Returns (provider_user_id, email, name).

    This function is patched in tests.
    """
    client = oauth.create_client(provider)
    if client is None:
        raise HTTPException(status_code=503, detail=f"Provider {provider} not configured")

    # Exchange code for token
    token = await client.fetch_access_token(
        code=code,
        redirect_uri=redirect_uri,
    )

    if provider == "google":
        resp = await client.get("https://www.googleapis.com/oauth2/v3/userinfo", token=token)
        userinfo = resp.json()
        return userinfo["sub"], userinfo["email"], userinfo.get("name", "")
    else:
        # GitHub
        resp = await client.get("user", token=token)
        userinfo = resp.json()
        # GitHub may not return email in profile; fetch from emails endpoint
        email = userinfo.get("email", "")
        if not email:
            emails_resp = await client.get("user/emails", token=token)
            for e in emails_resp.json():
                if e.get("primary"):
                    email = e["email"]
                    break
        return str(userinfo["id"]), email, userinfo.get("name") or userinfo.get("login", "")


@router.post("/{provider}/callback")
async def oauth_callback(provider: str, req: OAuthCallbackRequest):
    """Handle OAuth callback: exchange code, create/link user, return JWT tokens."""
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")
    if state.db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    # Verify CSRF state token
    if not req.state:
        raise HTTPException(status_code=400, detail="Missing OAuth state parameter")
    if not _verify_state_token(req.state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state parameter")

    provider_user_id, email, name = await _fetch_oauth_user_info(
        provider,
        req.code,
        req.redirect_uri,
    )

    if not email:
        raise HTTPException(
            status_code=400,
            detail="Could not retrieve email from OAuth provider",
        )

    is_new_user = False

    # Check if OAuth account already linked
    user = await state.db.get_user_by_oauth(provider, provider_user_id)

    if user is None:
        # Check if user with this email exists (link only if email is verified)
        existing = await state.db.get_user_by_email(email)

        if existing is not None and not existing.is_verified:
            raise HTTPException(
                status_code=409,
                detail=(
                    "An account with this email exists but is not verified. "
                    "Please verify your email first before linking OAuth."
                ),
            )

        if existing is not None and existing.is_verified:
            user = existing
        else:
            # Create new user
            user = UserRecord(
                email=email,
                name=name,
                is_verified=True,  # OAuth-verified email
            )
            await state.db.create_user(user)
            is_new_user = True

        # Link OAuth account to user
        oauth_account = OAuthAccountRecord(
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
        )
        await state.db.link_oauth_account(oauth_account)

    secret = _jwt_secret()
    return {
        "user": _user_response(user),
        "access_token": create_access_token(user_id=user.id, secret=secret),
        "refresh_token": create_refresh_token(user_id=user.id, secret=secret),
        "token_type": "bearer",
        "is_new_user": is_new_user,
    }
