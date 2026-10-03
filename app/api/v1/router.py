from fastapi import APIRouter

from app.api.v1 import locations, forecasts, line, users

api_router = APIRouter()
api_router.include_router(locations.router, prefix="/locations", tags=["locations"])
api_router.include_router(forecasts.router, tags=["forecasts"])
api_router.include_router(line.router, prefix="/line", tags=["line"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
