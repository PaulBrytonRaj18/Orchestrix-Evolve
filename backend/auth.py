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
        jwks_client = _get_jwks_client()
        if not jwks_client:
            logger.error("JWKS client not configured — cannot verify JWT")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service misconfigured",
            )

        try:
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                issuer=ISSUER,
                options={
                    "verify_aud": False,
                    "verify_exp": True,
                    "verify_iat": True,
                },
            )
        except jwt.exceptions.PyJWKClientConnectionError:
            logger.error("Could not connect to Supabase JWKS endpoint")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service temporarily unavailable",
            )

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



