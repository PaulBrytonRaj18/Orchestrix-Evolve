"""Auth endpoints with Supabase replaced by a fake (no network)."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from routers import auth as auth_routes
from tests.test_auth import make_token

USER = SimpleNamespace(
    id="u-1",
    email="u@example.com",
    user_metadata={"username": "ursula"},
    created_at="2026-01-01T00:00:00+00:00",
)
SESSION = SimpleNamespace(access_token="at", refresh_token="rt")


class FakeAuth:
    def __init__(self, session=SESSION, fail=False):
        self.session, self.fail, self.calls = session, fail, []
        self.admin = self

    def _res(self):
        if self.fail:
            raise RuntimeError("supabase says no")
        return SimpleNamespace(user=USER, session=self.session)

    def sign_up(self, payload):
        self.calls.append(("sign_up", payload))
        return self._res()

    def sign_in_with_password(self, payload):
        self.calls.append(("sign_in", payload))
        return self._res()

    def refresh_session(self, token):
        self.calls.append(("refresh", token))
        return self._res()

    def sign_out(self, jwt, scope):
        self.calls.append(("sign_out", scope))

    def get_user_by_id(self, uid):
        self.calls.append(("get", uid))
        return SimpleNamespace(user=USER)

    def update_user_by_id(self, uid, attrs):
        self.calls.append(("update", uid, attrs))
        return SimpleNamespace(user=USER)


@pytest.fixture
def fake(monkeypatch):
    holder = {"auth": FakeAuth()}
    client = SimpleNamespace(auth=None)
    monkeypatch.setattr(
        auth_routes, "new_supabase_client", lambda: SimpleNamespace(auth=holder["auth"])
    )
    monkeypatch.setattr(
        auth_routes, "get_supabase_admin", lambda: SimpleNamespace(auth=holder["auth"])
    )
    from main import app
    from rate_limit import limiter

    limiter.reset()
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        client = c
        client.holder = holder
        yield client


REG = {
    "email": "u@example.com",
    "username": "ursula",
    "password": "Secure#Pass1",
    "confirm_password": "Secure#Pass1",
}
BEARER = {"Authorization": f"Bearer {make_token(sub='u-1')}"}


def test_register_and_login(fake):
    r = fake.post("/auth/register", json=REG)
    assert r.status_code == 201
    assert r.json()["access_token"] == "at" and r.json()["user"]["username"] == "ursula"
    r = fake.post("/auth/login", json={"email": REG["email"], "password": "x"})
    assert r.status_code == 200 and r.json()["refresh_token"] == "rt"


def test_register_requiring_email_confirmation_returns_no_fake_token(fake):
    fake.holder["auth"] = FakeAuth(session=None)
    body = fake.post("/auth/register", json=REG).json()
    assert body["access_token"] is None
    assert body["email_confirmation_required"] is True


def test_login_failure_is_401(fake):
    fake.holder["auth"] = FakeAuth(fail=True)
    assert fake.post("/auth/login", json={"email": "a@b.co", "password": "x"}).status_code == 401


def test_login_is_rate_limited(fake):
    fake.holder["auth"] = FakeAuth(fail=True)
    codes = [
        fake.post("/auth/login", json={"email": "a@b.co", "password": "x"}).status_code
        for _ in range(11)
    ]
    assert codes[:10] == [401] * 10 and codes[10] == 429


def test_refresh(fake):
    assert fake.post("/auth/refresh", json={"refresh_token": "rt"}).json()["access_token"] == "at"


def test_me_reads_the_calling_user(fake):
    r = fake.get("/auth/me", headers=BEARER)
    assert r.status_code == 200 and r.json()["id"] == "u-1"
    assert ("get", "u-1") in fake.holder["auth"].calls


def test_update_me_targets_the_calling_user(fake):
    r = fake.patch("/auth/me", json={"username": "newname"}, headers=BEARER)
    assert r.status_code == 200
    assert ("update", "u-1", {"user_metadata": {"username": "newname"}}) in fake.holder[
        "auth"
    ].calls


def test_logout_revokes_sessions(fake):
    assert fake.post("/auth/logout", headers=BEARER).status_code == 200
    assert ("sign_out", "global") in fake.holder["auth"].calls
