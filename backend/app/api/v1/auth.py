from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis

from app.core.security import create_access_token, generate_otp, hash_otp, verify_otp
from app.redis.client import get_redis
from app.schemas.auth import OTPRequest, OTPVerify, TokenResponse
from app.services.messaging.sms_gateway import SMSDeliveryUnavailable, send_otp_sms
from config.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/otp/send", status_code=status.HTTP_202_ACCEPTED)
async def send_otp(payload: OTPRequest, request: Request, redis: Redis = Depends(get_redis)) -> dict[str, str]:
    phone = payload.phone
    ip = request.client.host if request.client else "unknown"
    ip_key = f"auth:otp:ip-limit:{ip}"
    ip_attempts = await redis.incr(ip_key)
    if ip_attempts == 1:
        await redis.expire(ip_key, settings.otp_send_window_seconds)
    if ip_attempts > settings.otp_send_limit_per_ip:
        raise HTTPException(status_code=429, detail="Too many code requests from this network")
    cooldown_key = f"auth:otp:cooldown:{phone}"
    if not await redis.set(cooldown_key, "1", ex=settings.otp_resend_cooldown_seconds, nx=True):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Please wait before requesting another code")

    otp = generate_otp()
    otp_key = f"auth:otp:{phone}"
    await redis.set(otp_key, hash_otp(otp), ex=settings.otp_expire_seconds)
    if settings.otp_provider == "development":
        if settings.environment.strip().lower() not in {"development", "dev", "test", "testing"}:
            await redis.delete(otp_key, cooldown_key)
            raise HTTPException(status_code=503, detail="Development OTP provider is disabled")
        # This response field is only returned by the explicitly selected local provider.
        return {"message": "Development verification code created", "development_otp": otp}
    try:
        await send_otp_sms(phone, otp)
    except SMSDeliveryUnavailable as exc:
        await redis.delete(otp_key, cooldown_key)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="OTP delivery is not configured") from exc
    except Exception as exc:
        await redis.delete(otp_key, cooldown_key)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="OTP delivery failed") from exc
    return {"message": "Verification code sent"}


@router.post("/otp/verify", response_model=TokenResponse)
async def verify_otp_code(payload: OTPVerify, redis: Redis = Depends(get_redis)) -> TokenResponse:
    phone = payload.phone
    otp_key = f"auth:otp:{phone}"
    stored_hash = await redis.get(otp_key)
    if stored_hash is None or not verify_otp(payload.otp, stored_hash):
        attempt_key = f"auth:otp:attempts:{phone}"
        attempts = await redis.incr(attempt_key)
        if attempts == 1:
            await redis.expire(attempt_key, settings.otp_attempt_window_seconds)
        if attempts >= settings.otp_attempt_limit:
            await redis.delete(otp_key)
            raise HTTPException(status_code=429, detail="Too many verification attempts; request a new code")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code")
    await redis.delete(otp_key, f"auth:otp:attempts:{phone}", f"auth:revoked_before:{phone}")
    token = create_access_token(phone)
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
    )
