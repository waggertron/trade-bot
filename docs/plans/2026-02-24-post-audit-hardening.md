# Trade-Bot: Post-Audit Hardening Plan

## Context

After completing the initial 7-phase SaaS transformation (auth, multi-tenancy, frontend, features, production hardening), a full codebase audit uncovered **21 issues** across security, code quality, and operational readiness. This plan addresses them in priority order: **critical security fixes first**, then feature completion, then operational improvements.

All work follows TDD. The finished plan will also be saved to `docs/plans/`.

---

## Phase 1: Critical Security Fixes (Tasks 1-8)

### 1.1 Validate JWT secret at startup
- **File:** `src/core/config.py` (line ~130)
- **Problem:** `JWT_SECRET_KEY` defaults to empty string — app starts without a real secret
- **Fix:** Add a `@field_validator` on `JWT_SECRET_KEY` that raises `ValueError` if the value is empty or shorter than 32 chars in non-test environments
- **Test:** `tests/unit/core/test_config_jwt.py` — verify startup fails with empty/short secret, passes with valid one
- **Verify:** `uv run pytest tests/unit/core/test_config_jwt.py -x`

### 1.2 Add `is_active` check to `get_current_user`
- **File:** `src/auth/dependencies.py` (line ~41-45)
- **Problem:** Deactivated users can still authenticate — `get_current_user` doesn't check `is_active`
- **Fix:** After fetching user from DB, raise `HTTPException(403)` if `user.is_active is False`
- **Test:** `tests/unit/auth/test_dependencies.py` — verify inactive user gets 403
- **Verify:** `uv run pytest tests/unit/auth/test_dependencies.py -x`

### 1.3 Add JWT revocation via `jti` claim + blacklist
- **Files:** `src/auth/tokens.py`, `src/db/database.py`
- **Problem:** No way to revoke tokens — compromised tokens valid until expiry
- **Fix:**
  - Add `jti` (UUID) claim to all tokens in `create_access_token()` and `create_refresh_token()`
  - Add `revoked_tokens` table: `jti (PK)`, `revoked_at`, `expires_at`
  - Add `revoke_token()` and `is_token_revoked()` methods to `Database`
  - Check revocation in `get_current_user` dependency
  - Add `POST /api/auth/logout` endpoint that revokes current token
- **Test:** `tests/unit/auth/test_token_revocation.py` — verify revoked token is rejected
- **Verify:** `uv run pytest tests/unit/auth/test_token_revocation.py -x`

### 1.4 Secure OAuth flow with CSRF state tokens
- **File:** `src/dashboard/routers/oauth.py` (lines ~32-63)
- **Problem:** No CSRF protection — vulnerable to login CSRF attacks
- **Fix:**
  - Generate random `state` parameter, store in signed cookie before redirect
  - Validate `state` on callback, reject if missing/mismatched
  - Whitelist `redirect_uri` against configured allowed origins
- **Test:** `tests/unit/dashboard/routers/test_oauth_csrf.py` — verify missing/bad state is rejected
- **Verify:** `uv run pytest tests/unit/dashboard/routers/test_oauth_csrf.py -x`

### 1.5 Require email verification before OAuth account linking
- **File:** `src/dashboard/routers/oauth.py` (lines ~135-136)
- **Problem:** Auto-links OAuth accounts by email without verifying email ownership
- **Fix:** Only auto-link if the existing user's email is verified (`is_verified=True`); otherwise create a new user
- **Test:** `tests/unit/dashboard/routers/test_oauth_linking.py` — verify unverified email doesn't auto-link
- **Verify:** `uv run pytest tests/unit/dashboard/routers/test_oauth_linking.py -x`

### 1.6 Protect system control endpoints
- **File:** `src/dashboard/app.py` (lines ~112-141)
- **Problem:** `/api/system/kill`, `/api/system/pause`, `/api/system/resume` have NO authentication — anyone can kill the trading bot
- **Fix:** Add `Depends(get_current_user)` to all system endpoints; optionally require admin role
- **Test:** `tests/unit/dashboard/test_system_auth.py` — verify unauthenticated requests get 401
- **Verify:** `uv run pytest tests/unit/dashboard/test_system_auth.py -x`

### 1.7 Fix rate limiter deterministic hashing
- **File:** `src/dashboard/rate_limit.py` (line ~75)
- **Problem:** Uses Python's `hash()` which is randomized per process (PYTHONHASHSEED) — rate limits don't work across workers
- **Fix:** Replace `hash(auth)` with `hashlib.sha256(auth.encode()).hexdigest()` for deterministic key generation
- **Test:** `tests/unit/dashboard/test_rate_limit_hash.py` — verify same input produces same bucket across calls
- **Verify:** `uv run pytest tests/unit/dashboard/test_rate_limit_hash.py -x`

### 1.8 Strengthen password requirements
- **File:** `src/dashboard/schemas.py`
- **Problem:** Password only requires `min_length=6` — too weak for a financial application
- **Fix:** Add `@field_validator` requiring: min 8 chars, at least 1 uppercase, 1 lowercase, 1 digit
- **Test:** `tests/unit/dashboard/test_password_validation.py` — verify weak passwords rejected
- **Verify:** `uv run pytest tests/unit/dashboard/test_password_validation.py -x`

---

## Phase 2: Frontend Security (Tasks 9-10)

### 2.1 Move JWT storage from localStorage to HTTP-only cookies
- **Files:** `web/src/stores/authStore.ts`, `web/src/lib/api.ts`, `src/dashboard/app.py`
- **Problem:** localStorage is accessible to any XSS — tokens can be stolen
- **Fix:**
  - Backend: Set tokens as `HttpOnly`, `Secure`, `SameSite=Strict` cookies on login/register/refresh responses
  - Backend: Read tokens from cookies in `get_current_user` (fall back to `Authorization` header for API clients)
  - Frontend: Remove token storage from localStorage; rely on cookies
  - Frontend: Add `credentials: 'include'` to all fetch calls
- **Test:** `tests/unit/auth/test_cookie_auth.py` — verify cookie-based auth works
- **Verify:** `uv run pytest tests/unit/auth/ -x` + manual browser test

### 2.2 Add CSRF protection for cookie-based auth
- **Files:** `src/dashboard/app.py`, `web/src/lib/api.ts`
- **Problem:** Cookie-based auth needs CSRF protection for state-changing requests
- **Fix:**
  - Backend: Generate CSRF token, set as non-HttpOnly cookie; validate `X-CSRF-Token` header on POST/PUT/DELETE
  - Frontend: Read CSRF cookie, send as header on mutations
- **Test:** `tests/unit/dashboard/test_csrf_protection.py` — verify missing CSRF token rejected on POST
- **Verify:** `uv run pytest tests/unit/dashboard/test_csrf_protection.py -x`

---

## Phase 3: Stub Endpoint Completion (Tasks 11-16)

### 3.1 Implement news router endpoints
- **File:** `src/dashboard/routers/news.py` — all 5 endpoints return empty/hardcoded data
- **Fix:** Wire to `Database.get_articles_for_symbol()`, `list_feeds()`, etc.
- **Test:** `tests/unit/dashboard/routers/test_news_live.py` — verify real data returned
- **Verify:** `uv run pytest tests/unit/dashboard/routers/test_news_live.py -x`

### 3.2 Implement ML router endpoints
- **File:** `src/dashboard/routers/ml.py` — all 6 endpoints return hardcoded data
- **Fix:** Wire model status to actual `LSTMModel` state; predictions to real inference
- **Test:** `tests/unit/dashboard/routers/test_ml_live.py` — verify real model state returned
- **Verify:** `uv run pytest tests/unit/dashboard/routers/test_ml_live.py -x`

### 3.3 Implement analytics aggregation endpoint
- **File:** `src/dashboard/routers/analytics.py`
- **Fix:** Wire to `AttributionEngine` for real strategy attribution data
- **Test:** `tests/unit/dashboard/routers/test_analytics_live.py`
- **Verify:** `uv run pytest tests/unit/dashboard/routers/test_analytics_live.py -x`

### 3.4 Implement risk exposure endpoint
- **File:** `src/dashboard/routers/risk.py`
- **Fix:** Wire to `RiskManager` for real exposure/correlation data
- **Test:** `tests/unit/dashboard/routers/test_risk_live.py`
- **Verify:** `uv run pytest tests/unit/dashboard/routers/test_risk_live.py -x`

### 3.5 Implement backtest history endpoint
- **File:** `src/dashboard/routers/backtest.py`
- **Fix:** Store and retrieve historical backtest results from DB
- **Test:** `tests/unit/dashboard/routers/test_backtest_history.py`
- **Verify:** `uv run pytest tests/unit/dashboard/routers/test_backtest_history.py -x`

### 3.6 Implement strategies CRUD
- **File:** `src/dashboard/routers/strategies.py`
- **Fix:** Wire to user_settings for per-user strategy configuration (enable/disable, weights)
- **Test:** `tests/unit/dashboard/routers/test_strategies_crud.py`
- **Verify:** `uv run pytest tests/unit/dashboard/routers/test_strategies_crud.py -x`

---

## Phase 4: Performance & Operational Fixes (Tasks 17-23)

### 4.1 Fix N+1 query in `get_articles_for_symbol`
- **File:** `src/db/database.py` (line ~579-611)
- **Problem:** Executes separate query per symbol in a loop
- **Fix:** Use `IN` clause to batch-query all symbols at once
- **Test:** `tests/unit/db/test_articles_batch.py` — verify single query for multiple symbols
- **Verify:** `uv run pytest tests/unit/db/test_articles_batch.py -x`

### 4.2 Add connection pool configuration
- **File:** `src/db/database.py` (line ~167)
- **Problem:** No pool size config — defaults may be too low for concurrent users
- **Fix:** Add `pool_size`, `max_overflow`, `pool_recycle` params to `create_async_engine()`, configurable via env vars
- **Test:** `tests/unit/db/test_pool_config.py` — verify pool settings applied
- **Verify:** `uv run pytest tests/unit/db/test_pool_config.py -x`

### 4.3 Parallelize feed fetching
- **File:** `src/feeds/manager.py` (lines ~38-70)
- **Problem:** Sequential feed fetching with nested for loops — very slow with 100+ feeds
- **Fix:** Use `asyncio.gather()` with `asyncio.Semaphore` for bounded concurrency (e.g., 10 concurrent fetches)
- **Test:** `tests/unit/feeds/test_parallel_fetch.py` — verify concurrent execution and semaphore limiting
- **Verify:** `uv run pytest tests/unit/feeds/test_parallel_fetch.py -x`

### 4.4 Reuse httpx client in Ollama sentiment provider
- **File:** `src/providers/ollama_sentiment.py` (line ~86)
- **Problem:** Creates new `httpx.AsyncClient` per call — connection overhead, no keep-alive
- **Fix:** Use a shared client instance with connection pooling (context manager or class-level client)
- **Test:** `tests/unit/providers/test_ollama_client_reuse.py` — verify same client used across calls
- **Verify:** `uv run pytest tests/unit/providers/test_ollama_client_reuse.py -x`

### 4.5 Add Alembic migration for `revoked_tokens` table
- **Files:** `alembic/versions/` (new migration)
- **Depends on:** Task 1.3 (revoked_tokens table definition)
- **Fix:** Create migration for the revoked_tokens table added in 1.3
- **Verify:** `uv run alembic upgrade head` succeeds

### 4.6 Add structured request logging
- **File:** `src/dashboard/app.py`
- **Problem:** No request-level logging — hard to debug issues in production
- **Fix:** Add middleware that logs: method, path, status, duration, user_id (if authenticated)
- **Test:** `tests/unit/dashboard/test_request_logging.py` — verify log entries include expected fields
- **Verify:** `uv run pytest tests/unit/dashboard/test_request_logging.py -x`

### 4.7 Add CI Postgres service for integration tests
- **File:** `.github/workflows/ci.yml`
- **Problem:** CI runs only with SQLite — Postgres-specific issues not caught
- **Fix:** Add `services: postgres` to test job, set `DATABASE_URL` env var
- **Verify:** CI pipeline passes with Postgres service container

---

## Verification Plan

After each phase:
1. `uv run pytest tests/ -x -q` — all tests pass
2. `uv run ruff check src/ tests/` — zero lint violations
3. Manual smoke test of affected endpoints

After all phases:
1. Register user, login, access protected endpoints
2. Verify system endpoints require auth
3. Verify OAuth flow includes CSRF state
4. Verify revoked tokens are rejected
5. Verify rate limiter works across requests
6. Verify news/ML/analytics endpoints return real data
7. CI passes on push

---

## Key Files

| Area | Files |
|------|-------|
| JWT config | `src/core/config.py` |
| Auth dependencies | `src/auth/dependencies.py` |
| Token creation | `src/auth/tokens.py` |
| OAuth router | `src/dashboard/routers/oauth.py` |
| System endpoints | `src/dashboard/app.py` |
| Rate limiter | `src/dashboard/rate_limit.py` |
| Password schemas | `src/dashboard/schemas.py` |
| Frontend auth | `web/src/stores/authStore.ts`, `web/src/lib/api.ts` |
| DB layer | `src/db/database.py` |
| Feed manager | `src/feeds/manager.py` |
| Ollama provider | `src/providers/ollama_sentiment.py` |
| CI workflow | `.github/workflows/ci.yml` |
| Stub routers | `src/dashboard/routers/{news,ml,analytics,risk,backtest,strategies}.py` |
