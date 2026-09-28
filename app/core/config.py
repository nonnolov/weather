from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
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

    # Providers
    DEFAULT_PROVIDER: str = "open_meteo"
    OPEN_METEO_BASE_URL: str = "https://api.open-meteo.com/v1"

    # Ingestion
    FORECAST_DAYS: int = 7

    @field_validator("FORECAST_DAYS")
    @classmethod
    def forecast_days_range(cls, v: int) -> int:
        if not (1 <= v <= 16):
            raise ValueError("FORECAST_DAYS must be between 1 and 16")
        return v


settings = Settings()
