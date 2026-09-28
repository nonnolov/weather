from fastapi import APIRouter

from app.api.v1 import locations, forecasts

api_router = APIRouter()
api_router.include_router(locations.router, prefix="/locations", tags=["locations"])
api_router.include_router(forecasts.router, tags=["forecasts"])
