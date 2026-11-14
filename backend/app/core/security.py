"""Firebase and email/identity JWT security helpers."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from config.settings import settings


def generate_otp(length: int = 6) -> str:
    """Return a cryptographically random numeric one-time password."""
    if length < 4 or length > 10:
        raise ValueError("OTP length must be between 4 and 10")
    return f"{secrets.randbelow(10**length):0{length}d}"


def hash_otp(otp: str) -> str:
    """Hash an OTP before storing it; callers should also enforce expiry and attempt limits."""
    return hashlib.sha256(otp.encode("utf-8")).hexdigest()


def verify_otp(plain_otp: str, hashed_otp: str) -> bool:
    return hmac.compare_digest(hash_otp(plain_otp), hashed_otp)


def create_access_token(identity: str, expires_delta: timedelta | None = None) -> str:
    expires = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    return jwt.encode(
        {"sub": identity, "email": identity, "exp": expires, "iat": datetime.now(UTC)},
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def get_user_identity_from_token(token: str) -> str | None:
    """Decode a bearer token (backend JWT or Firebase ID token) and return user subject/email."""
    # 1. Try local HMAC-signed JWT
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        subject = payload.get("sub") or payload.get("email")
        if isinstance(subject, str) and subject:
            return subject
    except JWTError:
        pass

    # 2. Try Firebase ID token (aud == 'fieldshift-8778f')
    try:
        claims = jwt.get_unverified_claims(token)
        aud = claims.get("aud")
        iss = claims.get("iss")
        if aud == "fieldshift-8778f" or (isinstance(iss, str) and "fieldshift-8778f" in iss):
            identity = claims.get("email") or claims.get("sub")
            if isinstance(identity, str) and identity:
                return identity
    except Exception:
        pass

    return None


get_phone_from_token = get_user_identity_from_token


def get_token_issued_at(token: str) -> int | None:
    try:
        claims = jwt.decode(token, settings.jwt_secret_key.get_secret_value(), algorithms=[settings.jwt_algorithm])
        issued_at = claims.get("iat")
        if isinstance(issued_at, int):
            return issued_at
    except JWTError:
        pass

    try:
        claims = jwt.get_unverified_claims(token)
        issued_at = claims.get("iat")
        if isinstance(issued_at, int):
            return issued_at
    except Exception:
        pass

    return None
