"""Hash de senhas (argon2) e tokens JWT de acesso e de renovação."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import Settings

_hasher = PasswordHasher()

# Hash de uma senha qualquer, usado para gastar o mesmo tempo quando o e-mail não existe
# e assim não revelar, pela latência, quais e-mails têm conta.
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class InvalidTokenError(Exception):
    """Token ausente, expirado, malformado ou do tipo errado."""


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int  # segundos até o access token expirar


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Confere a senha. Com `password_hash=None` (usuário inexistente) sempre falha."""
    if password_hash is None:
        _matches(_DUMMY_HASH, password)
        return False
    return _matches(password_hash, password)


def _matches(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_token_pair(
    user_id: uuid.UUID, settings: Settings, now: datetime | None = None
) -> TokenPair:
    now = now or datetime.now(UTC)
    access_ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    return TokenPair(
        access_token=_encode(user_id, TokenType.ACCESS, now, access_ttl, settings),
        refresh_token=_encode(
            user_id,
            TokenType.REFRESH,
            now,
            timedelta(days=settings.refresh_token_ttl_days),
            settings,
        ),
        expires_in=int(access_ttl.total_seconds()),
    )


def decode_token(token: str, expected_type: TokenType, settings: Settings) -> uuid.UUID:
    """Valida assinatura, expiração e tipo; retorna o id do usuário."""
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "iat", "type"]},
        )
        if claims["type"] != expected_type:
            raise InvalidTokenError(f"expected {expected_type} token")
        return uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise InvalidTokenError(str(exc)) from exc


def _encode(
    user_id: uuid.UUID, token_type: TokenType, now: datetime, ttl: timedelta, settings: Settings
) -> str:
    claims = {
        "sub": str(user_id),
        "type": token_type.value,
        "iat": now,
        "exp": now + ttl,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, settings.jwt_secret_key.get_secret_value(), settings.jwt_algorithm)
