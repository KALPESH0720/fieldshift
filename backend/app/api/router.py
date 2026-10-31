from fastapi import APIRouter

from app.api.v1 import auth, crop_knowledge_admin, farmers, history, market, plots, recommendations, satellite, seasons, soil, speech, sync, weather

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(farmers.router)
api_router.include_router(seasons.router)
api_router.include_router(crop_knowledge_admin.router)
api_router.include_router(plots.router)
api_router.include_router(soil.router)
api_router.include_router(weather.router)
api_router.include_router(satellite.router)
api_router.include_router(market.router)
api_router.include_router(history.router)
api_router.include_router(recommendations.router)
api_router.include_router(sync.router)
api_router.include_router(speech.router)
