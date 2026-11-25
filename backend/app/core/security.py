from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Literal
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jwt import InvalidTokenError

from app.core.config import Settings

TokenType = Literal["access", "refresh"]
password_hasher = PasswordHasher()


@dataclass(frozen=True)
class TokenClaims:
    user_id: UUID
    family_id: UUID
    token_id: UUID


def verify_password(hash_value: str, password: str) -> bool:
    try:
        return password_hasher.verify(hash_value, password)
    except VerifyMismatchError:
        return False


def issue_token(
    settings: Settings, claims: TokenClaims, kind: TokenType, now: datetime, expires: datetime
) -> str:
    return jwt.encode(
        {
            "sub": str(claims.user_id),
            "sid": str(claims.family_id),
            "jti": str(claims.token_id),
            "type": kind,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": now,
            "exp": expires,
        },
        settings.secret_key.get_secret_value(),
        algorithm="HS256",
    )


def read_token(settings: Settings, token: str, kind: TokenType) -> TokenClaims | None:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={
                "require": ["sub", "sid", "jti", "type", "iss", "aud", "iat", "exp"],
                "strict_aud": True,
            },
        )
        if payload["type"] == kind:
            return TokenClaims(UUID(payload["sub"]), UUID(payload["sid"]), UUID(payload["jti"]))
    except (InvalidTokenError, ValueError, TypeError, AttributeError, OverflowError):
        return None
    return None


def token_hash(token: str) -> str:
    return sha256(token.encode()).hexdigest()
