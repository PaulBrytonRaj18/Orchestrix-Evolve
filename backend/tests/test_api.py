import pytest
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = "sqlite:///./test_api.db"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["GROQ_API_KEY"] = "test-key"
os.environ["GEMINI_API_KEY"] = "test-key"

from fastapi.testclient import TestClient
from main import app
from database import init_db, engine


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c
    from database import close_engine

    close_engine()


class TestHealthEndpoint:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestAuthEndpoints:
    def test_register_success(self, client):
        response = client.post(
            "/auth/register",
            json={
                "email": "newuser@example.com",
                "username": "newuser",
                "password": "securepassword123",
                "confirm_password": "securepassword123",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == "newuser@example.com"

    def test_register_password_mismatch(self, client):
        response = client.post(
            "/auth/register",
            json={
                "email": "test2@example.com",
                "username": "testuser2",
                "password": "password1",
                "confirm_password": "password2",
            },
        )
        assert response.status_code == 400
        assert "Passwords do not match" in response.json()["detail"]

    def test_register_duplicate_email(self, client):
        client.post(
            "/auth/register",
            json={
                "email": "duplicate@example.com",
                "username": "uniqueuser1",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        response = client.post(
            "/auth/register",
            json={
                "email": "duplicate@example.com",
                "username": "uniqueuser2",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        assert response.status_code == 400

    def test_login_success(self, client):
        client.post(
            "/auth/register",
            json={
                "email": "loginuser@example.com",
                "username": "loginuser",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        response = client.post(
            "/auth/login",
            json={"email": "loginuser@example.com", "password": "password123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    def test_login_wrong_password(self, client):
        client.post(
            "/auth/register",
            json={
                "email": "wrongpass@example.com",
                "username": "wrongpass",
                "password": "correctpassword",
                "confirm_password": "correctpassword",
            },
        )
        response = client.post(
            "/auth/login",
            json={"email": "wrongpass@example.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        response = client.post(
            "/auth/login",
            json={"email": "nonexistent@example.com", "password": "password123"},
        )
        assert response.status_code == 401

    def test_get_me_authenticated(self, client):
        register_response = client.post(
            "/auth/register",
            json={
                "email": "meuser@example.com",
                "username": "meuser",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        token = register_response.json()["access_token"]

        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["email"] == "meuser@example.com"

    def test_get_me_unauthenticated(self, client):
        response = client.get("/auth/me")
        assert response.status_code == 403


class TestSessionEndpoints:
    def test_create_session_authenticated(self, client):
        register_response = client.post(
            "/auth/register",
            json={
                "email": "sessionuser@example.com",
                "username": "sessionuser",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        token = register_response.json()["access_token"]

        response = client.post(
            "/sessions",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "My Session", "query": "machine learning"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "My Session"
        assert "id" in data

    def test_create_session_unauthenticated(self, client):
        response = client.post(
            "/sessions", json={"name": "Unauthorized Session", "query": "test"}
        )
        assert response.status_code == 403

    def test_get_sessions_authenticated(self, client):
        register_response = client.post(
            "/auth/register",
            json={
                "email": "getsession@example.com",
                "username": "getsession",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        token = register_response.json()["access_token"]

        response = client.get("/sessions", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_session_not_found(self, client):
        register_response = client.post(
            "/auth/register",
            json={
                "email": "getsession2@example.com",
                "username": "getsession2",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        token = register_response.json()["access_token"]

        response = client.get(
            "/sessions/nonexistent-id", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 404


class TestProtectedEndpoints:
    def test_all_protected_endpoints_require_auth(self, client):
        protected_endpoints = [
            ("/sessions", "post"),
            ("/sessions", "get"),
            ("/digests", "post"),
            ("/digests", "get"),
        ]

        for endpoint, method in protected_endpoints:
            if method == "get":
                response = client.get(endpoint)
            else:
                response = client.post(endpoint, json={})

            assert response.status_code == 403, (
                f"{method.upper()} {endpoint} should require auth"
            )


class TestCORSHeaders:
    def test_cors_headers_present(self, client):
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
