import pytest
from app.core.config import Settings


def test_default_settings_load() -> None:
    s = Settings()
    assert s.DEFAULT_PROVIDER == "open_meteo"
    assert s.FORECAST_DAYS == 7
    assert s.APP_ENV == "development"


def test_forecast_days_validation_too_low() -> None:
    with pytest.raises(Exception):
        Settings(FORECAST_DAYS=0)


def test_forecast_days_validation_too_high() -> None:
    with pytest.raises(Exception):
        Settings(FORECAST_DAYS=17)


def test_forecast_days_boundary_values() -> None:
    s1 = Settings(FORECAST_DAYS=1)
    assert s1.FORECAST_DAYS == 1
    s16 = Settings(FORECAST_DAYS=16)
    assert s16.FORECAST_DAYS == 16
