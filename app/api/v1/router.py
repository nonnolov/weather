from fastapi import APIRouter

from app.api.v1 import locations, forecasts, line, users, rain_reference, flood_risk

api_router = APIRouter()
api_router.include_router(locations.router, prefix="/locations", tags=["locations"])
api_router.include_router(forecasts.router, tags=["forecasts"])
api_router.include_router(line.router, prefix="/line", tags=["line"])
api_router.include_router(users.router, prefix="/users", tags=["users"])

api_router.include_router(rain_reference.router, tags=["rain-reference"])
api_router.include_router(flood_risk.router)

from app.api.v1 import air_quality
api_router.include_router(air_quality.router)
