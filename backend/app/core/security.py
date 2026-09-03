"""
JWT Authentication and password hashing utilities.
All credentials read from environment — never hardcoded.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import hashlib
import hmac
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()
SALT = "finspectra_salt_2026_dev"

def hash_password(plain: str) -> str:
    """Hash a plaintext password deterministically."""
    return hashlib.sha256(f"{SALT}:{plain}".encode("utf-8")).hexdigest()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against stored hash."""
    expected = hashlib.sha256(f"{SALT}:{plain}".encode("utf-8")).hexdigest()
    return hmac.compare_digest(expected, hashed)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT token. Returns payload or None if invalid."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None
