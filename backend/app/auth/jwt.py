import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    REFRESH_TOKEN_EXPIRE_DAYS,
)


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": expire,
        "type": "access",
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def verify_access_token(token: str):
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )

        if payload.get("type") != "access":
            return "invalid"

        return payload

    except jwt.ExpiredSignatureError:
        return "expired"

    except jwt.InvalidTokenError:
        return "invalid"


def create_refresh_token() -> tuple[str, datetime]:
    """
    Creates a secure random refresh token
    and returns the token with its expiration date.
    """
    refresh_token = secrets.token_urlsafe(64)

    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    return refresh_token, expires_at


def hash_refresh_token(token: str) -> str:
    """
    Creates a SHA-256 hash of the refresh token.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
