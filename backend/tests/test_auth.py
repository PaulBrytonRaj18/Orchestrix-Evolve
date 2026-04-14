import pytest
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")

from auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_token,
    get_current_user,
    get_current_user_optional,
)


class TestPasswordHashing:
    def test_hash_password(self):
        password = "secure_password_123"
        hashed = get_password_hash(password)
        assert hashed != password
        assert len(hashed) > 0

    def test_verify_correct_password(self):
        password = "my_secure_password"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) == True

    def test_verify_incorrect_password(self):
        password = "correct_password"
        wrong_password = "wrong_password"
        hashed = get_password_hash(password)
        assert verify_password(wrong_password, hashed) == False

    def test_hash_different_each_time(self):
        password = "same_password"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        assert hash1 != hash2
        assert verify_password(password, hash1) == True
        assert verify_password(password, hash2) == True


class TestTokenCreation:
    def test_create_access_token(self):
        user_id = "test-user-123"
        token = create_access_token(data={"sub": user_id})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_valid_token(self):
        user_id = "user-456"
        token = create_access_token(data={"sub": user_id})
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == user_id
        assert "exp" in payload

    def test_decode_invalid_token(self):
        payload = decode_token("invalid.token.here")
        assert payload is None

    def test_decode_empty_token(self):
        payload = decode_token("")
        assert payload is None

    def test_token_with_custom_expiry(self):
        user_id = "user-789"
        token = create_access_token(
            data={"sub": user_id}, expires_delta=timedelta(hours=2)
        )
        payload = decode_token(token)
        assert payload["sub"] == user_id


class TestTokenDecoding:
    def test_token_contains_expected_claims(self):
        user_id = "test-claims-user"
        token = create_access_token(data={"sub": user_id, "role": "admin"})
        payload = decode_token(token)
        assert "sub" in payload
        assert "exp" in payload
        assert payload["sub"] == user_id
        assert payload["role"] == "admin"

    def test_token_missing_sub(self):
        token = create_access_token(data={})
        payload = decode_token(token)
        assert payload is not None
        assert "sub" not in payload or payload.get("sub") is None


class TestTokenSecurity:
    def test_different_secrets_produce_different_tokens(self):
        from auth import SECRET_KEY
        import os as os_module
        from jose import jwt

        original_secret = SECRET_KEY

        token1 = create_access_token(data={"sub": "user1"})

        os_module.environ["SECRET_KEY"] = "different-secret-key"
        from importlib import reload
        import auth

        reload(auth)
        token2 = auth.create_access_token(data={"sub": "user1"})

        os_module.environ["SECRET_KEY"] = original_secret
        reload(auth)

        assert token1 != token2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
