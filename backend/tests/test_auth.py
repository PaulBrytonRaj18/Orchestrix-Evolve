"""JWT verification. No dependency overrides here: the real verifier runs."""

import time

import jwt
import pytest
from fastapi.testclient import TestClient

from config import get_settings

SECRET = get_settings().supabase_jwt_secret
ISSUER = f"{get_settings().supabase_url}/auth/v1"


def make_token(**overrides) -> str:
    now = int(time.time())
    claims = {
        "sub": "user-123",
        "email": "u@example.com",
        "aud": "authenticated",
        "iss": ISSUER,
        "iat": now,
        "exp": now + 600,
        "user_metadata": {"username": "u"},
    }
    claims.update(overrides)
    key = overrides.pop("_key", SECRET) if "_key" in overrides else SECRET
    claims.pop("_key", None)
    return jwt.encode(claims, key, algorithm="HS256")


@pytest.fixture
def raw_client():
    from main import app

    app.dependency_overrides.clear()
    with TestClient(app) as c:
        yield c


def _get(client, token):
    return client.get("/sessions", headers={"Authorization": f"Bearer {token}"})


def test_valid_token_is_accepted(raw_client):
    assert _get(raw_client, make_token()).status_code == 200


@pytest.mark.parametrize(
    "token_kwargs, reason",
    [
        ({"exp": int(time.time()) - 120}, "expired"),
        ({"aud": "anon"}, "wrong audience"),
        ({"iss": "https://evil.example/auth/v1"}, "wrong issuer"),
        ({"_key": "a-completely-different-secret-value-xxxxxxxx"}, "bad signature"),
    ],
)
def test_invalid_tokens_are_rejected(raw_client, token_kwargs, reason):
    r = _get(raw_client, make_token(**token_kwargs))
    assert r.status_code == 401, reason


def test_garbage_and_missing_tokens(raw_client):
    assert _get(raw_client, "not-a-jwt").status_code == 401
    assert raw_client.get("/sessions").status_code == 401


def test_no_bypass_from_service_key_contents(raw_client, monkeypatch):
    """The old verifier accepted ANY bearer value when the service key contained 'test'."""
    monkeypatch.setattr(get_settings(), "supabase_service_key", "test-dummy-key")
    assert _get(raw_client, "anything").status_code == 401


def test_users_are_isolated_by_sub(raw_client):
    created = raw_client.post(
        "/sessions",
        json={"name": "mine", "query": "q"},
        headers={"Authorization": f"Bearer {make_token(sub='owner')}"},
    )
    sid = created.json()["id"]
    other = raw_client.get(
        f"/sessions/{sid}", headers={"Authorization": f"Bearer {make_token(sub='intruder')}"}
    )
    assert other.status_code == 404
