"""
Supabase Authentication for Orchestrix Backend
Replaces custom JWT auth with Supabase Auth
"""

import os
import logging
from typing import Optional
from functools import lru_cache
from datetime import datetime, timezone

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

# JWT verification settings
ISSUER = f"{SUPABASE_URL}/auth/v1" if SUPABASE_URL else None
JWKS_URL = f"{ISSUER}/.well-known/jwks.json" if ISSUER else None

security = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def _get_jwks_client():
    """Get JWKS client for verifying Supabase JWTs"""
    if not JWKS_URL:
        logger.warning("JWKS_URL not configured - JWT verification may fail")
        return None
    return PyJWKClient(JWKS_URL)


class SupabaseUser:
    """Represents an authenticated Supabase user"""

    def __init__(
        self,
        user_id: str,
        email: Optional[str] = None,
        username: Optional[str] = None,
        **kwargs,
    ):
        self.id = user_id
        self.email = email
        self.username = username
        self.extra_data = kwargs


async def verify_supabase_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> SupabaseUser:
    """
    Verify Supabase JWT token and return user information.
    Uses JWKS for signature verification (more secure).
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authorization token provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty token provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Try JWKS verification first (recommended for production)
        jwks_client = _get_jwks_client()

        if jwks_client:
            try:
                signing_key = jwks_client.get_signing_key_from_jwt(token)
                payload = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["RS256", "ES256"],
                    issuer=ISSUER,
                    options={
                        "verify_aud": False,  # Audience claim varies
                        "verify_exp": True,
                        "verify_iat": True,
                    },
                )
            except jwt.exceptions.PyJWKClientConnectionError:
                logger.warning(
                    "Could not connect to JWKS, falling back to decoded claims only"
                )
                # Fall back to decoding without verification (less secure but works offline)
                payload = jwt.decode(token, options={"verify_signature": False})
        else:
            # No JWKS client - decode without verification (dev mode)
            payload = jwt.decode(token, options={"verify_signature": False})
            logger.warning("Running without JWT signature verification")

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: no user ID found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return SupabaseUser(
            user_id=user_id,
            email=payload.get("email"),
            username=payload.get("user_metadata", {}).get("username"),
        )

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    user: SupabaseUser = Depends(verify_supabase_token),
) -> str:
    """Get current user ID from Supabase auth"""
    return user.id


async def get_current_user_optional(
    user: Optional[SupabaseUser] = Depends(verify_supabase_token),
) -> Optional[str]:
    """Get current user ID if authenticated, None otherwise"""
    if user is None:
        return None
    return user.id


def get_supabase_client():
    """Get Supabase client for server-side operations"""
    from supabase import create_client, Client

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("SUPABASE_URL or SUPABASE_SERVICE_KEY not configured")
        raise ValueError("Supabase configuration missing")

    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# Keep these for backward compatibility (no-op functions)
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Deprecated - password verification now handled by Supabase"""
    logger.warning("verify_password is deprecated - Supabase handles auth")
    return False


def get_password_hash(password: str) -> str:
    """Deprecated - password hashing now handled by Supabase"""
    logger.warning("get_password_hash is deprecated - Supabase handles auth")
    return ""


def create_access_token(data: dict, expires_delta: Optional[int] = None) -> str:
    """Deprecated - tokens now managed by Supabase"""
    logger.warning("create_access_token is deprecated - Supabase handles tokens")
    return ""


def decode_token(token: str) -> Optional[dict]:
    """Deprecated - use verify_supabase_token instead"""
    logger.warning("decode_token is deprecated - use verify_supabase_token instead")
    try:
        return jwt.decode(token, options={"verify_signature": False})
    except Exception:
        return None
