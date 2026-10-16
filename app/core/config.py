from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, model_validator
from typing import Optional, Literal


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
    ADMIN_API_KEY: str | None = None
    CORS_ORIGINS: str = "http://localhost:3000"

    # Providers
    DEFAULT_PROVIDER: str = "open_meteo"
    OPEN_METEO_BASE_URL: str = "https://api.open-meteo.com/v1"
    GEOCODER_PROVIDER: str = "arcgis"
    GEOCODER_BASE_URL: str = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer"
    GEOCODER_USER_AGENT: str = "weather-forecasting-system/1.0"

    # Shared forecast acquisition; explicit rollout keeps older environments compatible.
    FORECAST_SHARING_ENABLED: bool = False
    FORECAST_REFRESH_SECONDS: int = Field(default=3600, ge=60, le=3600)
    FORECAST_FAILURE_BACKOFF_SECONDS: int = Field(default=300, ge=60, le=3600)
    GOOGLE_WEATHER_API_KEY: str | None = None
    GOOGLE_WEATHER_PREVIEW_ENABLED: bool = False
    GOOGLE_WEATHER_CONTRACT_VERIFIED: bool = False
    GOOGLE_WEATHER_MONTHLY_LIMIT: int = Field(default=9000, ge=1, le=9000)
    GOOGLE_WEATHER_DAILY_LIMIT: int = Field(default=290, ge=1, le=290)

    # Ingestion
    FORECAST_DAYS: int = 7
    # Explicit refresh preview only; never enables LINE sending.
    INTRADAY_PREVIEW_AFTER_REFRESH: bool = False
    # Existing API process only; forecast-only polling, preview unless live enabled.
    INTRADAY_PREVIEW_SCHEDULER_ENABLED: bool = False
    # Live delivery only from this scheduler; explicit recipient allowlist required.
    INTRADAY_SEND_ENABLED: bool = False
    INTRADAY_SEND_RECIPIENT_IDS: str = ""
    # Explicit rollout selection; unchanged default keeps current production v1.
    INTRADAY_POLICY_VERSION: Literal["intraday-v1", "intraday-v2-candidate"] = "intraday-v1"

    # Separate hourly measured-reference staging; never enables LINE.
    P2_RAIN_COLLECTION_ENABLED: bool = False

    # LINE Messaging API
    LINE_CHANNEL_ACCESS_TOKEN: str | None = None
    LINE_CHANNEL_SECRET: str | None = None
    LINE_LOGIN_CHANNEL_ID: str | None = None
    LINE_USER_IDS: str = ""
    LINE_SUBSCRIPTIONS_ENABLED: bool = False
    LINE_OFFICIAL_ACCOUNT_ID: str | None = None
    LINE_API_BASE_URL: str = "https://api.line.me"

    @model_validator(mode="after")
    def production_security(self):
        if self.APP_ENV == "production" and self.SECRET_KEY in {"change-me", "change-me-to-a-long-random-string"}:
            raise ValueError("SECRET_KEY must be changed in production")
        if self.APP_ENV == "production" and self.DEBUG:
            raise ValueError("DEBUG must be false in production")
        if self.LINE_SUBSCRIPTIONS_ENABLED and not (self.LINE_LOGIN_CHANNEL_ID and self.LINE_CHANNEL_ACCESS_TOKEN and self.LINE_CHANNEL_SECRET and self.LINE_OFFICIAL_ACCOUNT_ID):
            raise ValueError("LINE signup requires Login channel, Messaging token/secret and Weather account ID")
        if self.INTRADAY_SEND_ENABLED:
            recipients = [x.strip() for x in self.INTRADAY_SEND_RECIPIENT_IDS.split(",") if x.strip()]
            if (not self.INTRADAY_PREVIEW_SCHEDULER_ENABLED or not self.LINE_CHANNEL_ACCESS_TOKEN
                    or (not recipients and not self.LINE_SUBSCRIPTIONS_ENABLED)
                    or any(not x.startswith("U") for x in recipients)):
                raise ValueError("Live intraday requires scheduler, LINE token and explicit LINE recipients")
        return self

    @field_validator("FORECAST_DAYS")
    @classmethod
    def forecast_days_range(cls, v: int) -> int:
        if not (1 <= v <= 16):
            raise ValueError("FORECAST_DAYS must be between 1 and 16")
        return v


settings = Settings()
