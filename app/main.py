import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.notifications.scheduled_preview import scheduled_preview_lifespan

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("weather.api")

app = FastAPI(
    title="Weather Forecasting System",
    lifespan=scheduled_preview_lifespan,
    description="Modular 7-day weather forecasting API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

cors_origins = [item.strip() for item in settings.CORS_ORIGINS.split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "%s %s -> %s %.1fms request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        request_id,
    )
    return response


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Liveness probe — returns 200 when the application is running."""
    return {"status": "ok", "version": "1.0.0"}


app.include_router(api_router, prefix="/api/v1")
