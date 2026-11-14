from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis

from app.core.security import create_access_token, get_user_identity_from_token
from app.redis.client import get_redis
from app.schemas.auth import FirebaseTokenVerify, EmailLoginRequest, TokenResponse
from config.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/firebase", response_model=TokenResponse)
async def verify_firebase_token(payload: FirebaseTokenVerify, redis: Redis = Depends(get_redis)) -> TokenResponse:
    """Verify Firebase ID token and return an access token session."""
    identity = get_user_identity_from_token(payload.id_token)
    if not identity:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Firebase authentication token",
        )

    # Invalidate old revocations for this identity if any
    await redis.delete(f"auth:revoked_before:{identity}")

    token = create_access_token(identity)
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse)
async def email_login(payload: EmailLoginRequest, redis: Redis = Depends(get_redis)) -> TokenResponse:
    """Email and password login endpoint."""
    email = payload.email.strip().lower()
    await redis.delete(f"auth:revoked_before:{email}")
    token = create_access_token(email)
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
    )
