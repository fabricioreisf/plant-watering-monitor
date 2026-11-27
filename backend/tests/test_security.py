import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.core.security import (
    InvalidTokenError,
    TokenType,
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
)

SETTINGS = Settings(
    database_url="postgresql+psycopg://x:x@localhost/x",
    jwt_secret_key="unit-test-secret-key-with-32-characters!",
)
USER_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


class TestPasswords:
    def test_hash_is_not_the_password_and_is_salted(self) -> None:
        first, second = hash_password("s3nha-segura"), hash_password("s3nha-segura")
        assert "s3nha-segura" not in first
        assert first.startswith("$argon2")
        assert first != second

    def test_verify_accepts_correct_password(self) -> None:
        assert verify_password("s3nha-segura", hash_password("s3nha-segura"))

    def test_verify_rejects_wrong_password(self) -> None:
        assert not verify_password("outra", hash_password("s3nha-segura"))

    def test_verify_rejects_missing_user(self) -> None:
        assert not verify_password("qualquer", None)

    def test_verify_rejects_malformed_hash(self) -> None:
        assert not verify_password("qualquer", "not-a-hash")


class TestTokens:
    def test_access_token_round_trip(self) -> None:
        pair = create_token_pair(USER_ID, SETTINGS)
        assert decode_token(pair.access_token, TokenType.ACCESS, SETTINGS) == USER_ID
        assert pair.expires_in == SETTINGS.access_token_ttl_minutes * 60

    def test_refresh_token_round_trip(self) -> None:
        pair = create_token_pair(USER_ID, SETTINGS)
        assert decode_token(pair.refresh_token, TokenType.REFRESH, SETTINGS) == USER_ID

    @pytest.mark.parametrize(
        ("attribute", "expected"),
        [("refresh_token", TokenType.ACCESS), ("access_token", TokenType.REFRESH)],
    )
    def test_token_types_are_not_interchangeable(self, attribute: str, expected: TokenType) -> None:
        token = getattr(create_token_pair(USER_ID, SETTINGS), attribute)
        with pytest.raises(InvalidTokenError):
            decode_token(token, expected, SETTINGS)

    def test_expired_token_is_rejected(self) -> None:
        long_ago = datetime.now(UTC) - timedelta(days=1)
        pair = create_token_pair(USER_ID, SETTINGS, now=long_ago)
        with pytest.raises(InvalidTokenError):
            decode_token(pair.access_token, TokenType.ACCESS, SETTINGS)

    def test_token_signed_with_another_key_is_rejected(self) -> None:
        other = SETTINGS.model_copy(update={"jwt_secret_key": SecretStr("x" * 40)})
        pair = create_token_pair(USER_ID, other)
        with pytest.raises(InvalidTokenError):
            decode_token(pair.access_token, TokenType.ACCESS, SETTINGS)

    def test_unsigned_token_is_rejected(self) -> None:
        token = jwt.encode(
            {"sub": str(USER_ID), "type": "access", "iat": 0, "exp": 2**31},
            key=None,
            algorithm="none",
        )
        with pytest.raises(InvalidTokenError):
            decode_token(token, TokenType.ACCESS, SETTINGS)

    def test_garbage_is_rejected(self) -> None:
        with pytest.raises(InvalidTokenError):
            decode_token("not-a-jwt", TokenType.ACCESS, SETTINGS)

    def test_tokens_are_unique(self) -> None:
        first = create_token_pair(USER_ID, SETTINGS)
        second = create_token_pair(USER_ID, SETTINGS)
        assert first.access_token != second.access_token


def test_settings_reject_short_jwt_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="postgresql+psycopg://x:x@localhost/x", jwt_secret_key="curta")
