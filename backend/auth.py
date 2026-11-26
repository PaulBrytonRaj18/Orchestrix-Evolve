"""Supabase authentication.

Bearer tokens are Supabase access JWTs. They are verified locally:

* projects with asymmetric signing keys (current default) → JWKS at
  ``<SUPABASE_URL>/auth/v1/.well-known/jwks.json`` (keys cached in-process);
* legacy projects → HS256 with ``SUPABASE_JWT_SECRET``.

Issuer, expiry and audience are always checked. There is deliberately no
"test mode" switch in this module: tests override the ``get_current_user``
dependency instead (the previous build disabled verification whenever the
service key merely *contained* the substring "test" or "dummy").

The dependency functions are sync ``def`` so FastAPI runs them in its threadpool;
a JWKS cache miss performs blocking network I/O and must not stall the event loop.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from config import get_settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str | None
    username: str | None
    token: str


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient | None:
    s = get_settings()
    if not s.supabase_url:
        return None
    return PyJWKClient(
        f"{s.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json",
        cache_keys=True,
        lifespan=3600,
        timeout=5,
    )


def decode_token(token: str) -> dict:
    s = get_settings()
    issuer = f"{s.supabase_url.rstrip('/')}/auth/v1" if s.supabase_url else None
    options = {"require": ["exp", "sub"], "verify_iss": bool(issuer)}
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") == "HS256":
            if not s.supabase_jwt_secret:
                raise _unauthorized("HS256 tokens require SUPABASE_JWT_SECRET on the server")
            key: object = s.supabase_jwt_secret
            algorithms = ["HS256"]
        else:
            client = _jwks_client()
            if client is None:
                logger.error("SUPABASE_URL is not configured; cannot verify tokens")
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication is not configured"
                )
            key = client.get_signing_key_from_jwt(token).key
            algorithms = ["RS256", "ES256"]
        return jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=s.supabase_jwt_audience,
            issuer=issuer,
            options=options,
            leeway=30,
        )
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Token has expired") from exc
    except jwt.PyJWKClientConnectionError as exc:
        logger.error("Could not reach Supabase JWKS endpoint: %s", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication service temporarily unavailable"
        ) from exc
    except (jwt.InvalidTokenError, jwt.PyJWKClientError) as exc:
        logger.info("Rejected token: %s", exc)
        raise _unauthorized("Invalid authentication token") from exc


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> AuthUser:
    if credentials is None or not credentials.credentials:
        raise _unauthorized("No authorization token provided")
    payload = decode_token(credentials.credentials)
    metadata = payload.get("user_metadata") or {}
    return AuthUser(
        id=payload["sub"],
        email=payload.get("email"),
        username=metadata.get("username"),
        token=credentials.credentials,
    )


def get_current_user(principal: AuthUser = Depends(get_current_principal)) -> str:
    """The authenticated user's id (Supabase ``sub``)."""
    return principal.id


# ─── Supabase clients ────────────────────────────────────────────────────────


def _require_supabase_config() -> tuple[str, str]:
    s = get_settings()
    if not s.supabase_url or not s.supabase_service_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Supabase is not configured")
    return s.supabase_url, s.supabase_service_key


@lru_cache(maxsize=1)
def _admin_client():
    from supabase import create_client

    url, key = _require_supabase_config()
    return create_client(url, key)


def get_supabase_admin():
    """Process-wide service-role client for stateless admin calls only."""
    _require_supabase_config()
    return _admin_client()


def new_supabase_client():
    """A fresh, non-persisting client for sign-in/sign-up/refresh.

    Those calls store the resulting user session *on the client object*; sharing one
    client between concurrent requests would leak sessions across users.
    """
    from supabase import ClientOptions, create_client

    url, key = _require_supabase_config()
    return create_client(
        url, key, options=ClientOptions(auto_refresh_token=False, persist_session=False)
    )
