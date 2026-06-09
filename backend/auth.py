"""
Supabase Authentication for Orchestrix Backend
"""

import logging
import os
from functools import lru_cache

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

ISSUER = f"{SUPABASE_URL}/auth/v1" if SUPABASE_URL else None
JWKS_URL = f"{ISSUER}/.well-known/jwks.json" if ISSUER else None

security = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def _get_jwks_client():
    if not JWKS_URL:
        logger.warning("JWKS_URL not configured - JWT verification will fail")
        return None
    return PyJWKClient(JWKS_URL)


class SupabaseUser:
    def __init__(
        self,
        user_id: str,
        email: str | None = None,
        username: str | None = None,
        **kwargs,
    ):
        self.id = user_id
        self.email = email
        self.username = username
        self.extra_data = kwargs


async def verify_supabase_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> SupabaseUser:
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
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    user: SupabaseUser = Depends(verify_supabase_token),
) -> str:
    return user.id


async def get_current_user_optional(
    user: SupabaseUser | None = Depends(verify_supabase_token),
) -> str | None:
    if user is None:
        return None
    return user.id


def get_supabase_client():
    from supabase import create_client

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("SUPABASE_URL or SUPABASE_SERVICE_KEY not configured")
        raise ValueError("Supabase configuration missing")

    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
