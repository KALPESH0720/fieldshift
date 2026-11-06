"""Shared API authentication dependencies."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_phone_from_token, get_token_issued_at
from app.db.session import get_db
from app.models.farmer import Farmer
from app.redis.client import get_redis
from redis.asyncio import Redis

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_phone(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    redis: Redis = Depends(get_redis),
) -> str:
    if credentials is None or (phone := get_phone_from_token(credentials.credentials)) is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    revoked_before = await redis.get(f"auth:revoked_before:{phone}")
    issued_at = get_token_issued_at(credentials.credentials)
    if issued_at is None or (revoked_before is not None and issued_at <= int(revoked_before)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked bearer token", headers={"WWW-Authenticate": "Bearer"})
    return phone


async def get_current_farmer(
    phone: str = Depends(get_current_phone),
    session: AsyncSession = Depends(get_db),
) -> Farmer:
    farmer = await session.scalar(select(Farmer).where(Farmer.phone == phone))
    if farmer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farmer profile not found")
    return farmer
