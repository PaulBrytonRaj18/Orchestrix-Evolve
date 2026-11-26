"""Auth endpoints — thin wrappers over Supabase Auth.

The SPA normally talks to Supabase directly (supabase-js); these endpoints exist for
API clients and keep the same contract.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool

from auth import AuthUser, get_current_principal, get_supabase_admin, new_supabase_client
from rate_limit import rate_limited
from schemas import (
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])


def _user_response(user: Any) -> UserResponse:
    metadata = getattr(user, "user_metadata", None) or {}
    return UserResponse(
        id=user.id,
        email=user.email or "",
        username=metadata.get("username", ""),
        is_active=True,
        is_admin=False,
        created_at=getattr(user, "created_at", None) or datetime.now(UTC),
    )


def _token_response(res: Any) -> TokenResponse:
    session = getattr(res, "session", None)
    return TokenResponse(
        access_token=session.access_token if session else None,
        refresh_token=session.refresh_token if session else None,
        user=_user_response(res.user),
        email_confirmation_required=session is None,
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limited("register", 5, 300))],
)
async def register(body: UserCreate) -> TokenResponse:
    def call():
        return new_supabase_client().auth.sign_up(
            {
                "email": body.email,
                "password": body.password,
                "options": {"data": {"username": body.username}},
            }
        )

    try:
        res = await run_in_threadpool(call)
    except HTTPException:
        raise
    except Exception as exc:
        logger.info("Registration rejected: %s", exc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Registration failed") from exc
    if res.user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Registration failed")
    # No token is invented when Supabase requires e-mail confirmation (the old code
    # returned the literal string "mock_token", which the SPA then stored).
    return _token_response(res)


@router.post(
    "/login", response_model=TokenResponse, dependencies=[Depends(rate_limited("login", 10, 300))]
)
async def login(body: UserLogin) -> TokenResponse:
    def call():
        return new_supabase_client().auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )

    try:
        res = await run_in_threadpool(call)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password") from exc
    if res.user is None or res.session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return _token_response(res)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limited("refresh", 20, 300))],
)
async def refresh_token(body: RefreshTokenRequest) -> TokenResponse:
    try:
        res = await run_in_threadpool(
            lambda: new_supabase_client().auth.refresh_session(body.refresh_token)
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Failed to refresh token") from exc
    if res.session is None or res.user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    return _token_response(res)


@router.post("/logout")
async def logout(principal: AuthUser = Depends(get_current_principal)) -> dict[str, str]:
    """Revoke the caller's refresh tokens (the access JWT stays valid until it expires)."""
    try:
        await run_in_threadpool(
            lambda: get_supabase_admin().auth.admin.sign_out(principal.token, "global")
        )
    except Exception as exc:
        logger.warning("Supabase sign-out failed: %s", exc)
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def me(principal: AuthUser = Depends(get_current_principal)) -> UserResponse:
    try:
        res = await run_in_threadpool(
            lambda: get_supabase_admin().auth.admin.get_user_by_id(principal.id)
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_user_by_id failed: %s", exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Failed to load user") from exc
    if not res or not res.user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return _user_response(res.user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UserUpdate, principal: AuthUser = Depends(get_current_principal)
) -> UserResponse:
    attrs: dict[str, Any] = {}
    if body.email is not None:
        attrs["email"] = body.email
    if body.password is not None:
        attrs["password"] = body.password
    if body.username is not None:
        attrs["user_metadata"] = {"username": body.username}
    admin = get_supabase_admin().auth.admin
    try:
        if attrs:
            res = await run_in_threadpool(lambda: admin.update_user_by_id(principal.id, attrs))
        else:
            res = await run_in_threadpool(lambda: admin.get_user_by_id(principal.id))
    except Exception as exc:
        logger.error("update_user_by_id failed: %s", exc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Failed to update user") from exc
    return _user_response(res.user)
