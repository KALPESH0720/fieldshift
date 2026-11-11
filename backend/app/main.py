from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.router import api_router
from app.db.session import dispose_engine, engine
from app.redis.client import close_redis, redis_client
from config.settings import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_runtime_configuration()
    yield
    await close_redis()
    await dispose_engine()


app = FastAPI(title="Field Shift API", lifespan=lifespan)

# Enable CORS for frontend clients (Vite dev server, PWA, mobile)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health/live")
async def live() -> dict[str, str]:
    """Process liveness; deliberately independent of external services."""
    return {"status": "ok"}


@app.get("/health/ready")
async def ready() -> JSONResponse:
    checks: dict[str, str] = {}
    for name, probe in (
        ("database", _check_database),
        ("redis", _check_redis),
    ):
        try:
            await asyncio.wait_for(probe(), timeout=2.0)
            checks[name] = "ok"
        except Exception:
            checks[name] = "unavailable"
    status = "ok" if all(value == "ok" for value in checks.values()) else "unavailable"
    return JSONResponse({"status": status, "checks": checks}, status_code=200 if status == "ok" else 503)


async def _check_database() -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def _check_redis() -> None:
    if not await redis_client.ping():
        raise RuntimeError("Redis ping failed")
