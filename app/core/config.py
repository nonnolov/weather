from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://weather_user:weather_pass@localhost:5432/weather_db"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://weather_user:weather_pass@localhost:5432/weather_db"

    # Application
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me"
    CORS_ORIGINS: str = "http://localhost:3000"

    # Providers
    DEFAULT_PROVIDER: str = "open_meteo"
    OPEN_METEO_BASE_URL: str = "https://api.open-meteo.com/v1"
    GEOCODER_BASE_URL: str = "https://nominatim.openstreetmap.org"
    GEOCODER_USER_AGENT: str = "weather-forecasting-system/1.0"

    # Ingestion
    FORECAST_DAYS: int = 7

    # LINE Messaging API
    LINE_CHANNEL_ACCESS_TOKEN: str | None = None
    LINE_CHANNEL_SECRET: str | None = None
    LINE_LOGIN_CHANNEL_ID: str | None = None
    LINE_USER_IDS: str = ""
    LINE_API_BASE_URL: str = "https://api.line.me"

    @model_validator(mode="after")
    def production_security(self):
        if self.APP_ENV == "production" and self.SECRET_KEY in {"change-me", "change-me-to-a-long-random-string"}:
            raise ValueError("SECRET_KEY must be changed in production")
        if self.APP_ENV == "production" and self.DEBUG:
            raise ValueError("DEBUG must be false in production")
        return self

    @field_validator("FORECAST_DAYS")
    @classmethod
    def forecast_days_range(cls, v: int) -> int:
        if not (1 <= v <= 16):
            raise ValueError("FORECAST_DAYS must be between 1 and 16")
        return v


settings = Settings()
