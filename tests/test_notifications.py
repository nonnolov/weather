from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.forecast import DailyForecast, ForecastRun
from app.models.location import Location
from app.notifications.formatter import format_forecast_alert
from app.notifications.line_client import LineClient
from app.notifications.service import send_forecast_alert


UTC = timezone.utc


@pytest.mark.asyncio
async def test_line_client_pushes_bearer_json() -> None:
    client = LineClient("secret", "https://line.test")
    response = httpx.Response(200, request=httpx.Request("POST", "https://line.test"))
    client._request = AsyncMock(return_value=response)

    await client.push_text("U123", "hello")

    client._request.assert_awaited_once_with("U123", "hello")


@pytest.mark.asyncio
async def test_notification_is_deduplicated(db_session: AsyncSession) -> None:
    location = Location(
        name="Pattaya", slug="notify-pattaya", latitude=12.9, longitude=100.8,
        timezone="UTC", provider="open_meteo",
    )
    db_session.add(location)
    await db_session.flush()
    run = ForecastRun(
        location_id=location.id, provider="open_meteo",
        retrieved_at=datetime(2024, 6, 1, tzinfo=UTC), forecast_days=7,
    )
    db_session.add(run)
    await db_session.flush()
    db_session.add(DailyForecast(
        forecast_run_id=run.id, forecast_date=date(2024, 6, 1),
        temperature_2m_min=25.0, temperature_2m_max=32.0,
        precipitation_probability_max=70.0,
    ))
    await db_session.flush()

    fake_client = AsyncMock()
    fake_client.push_text = AsyncMock()

    first = await send_forecast_alert(db_session, run, "U123", fake_client)
    second = await send_forecast_alert(db_session, run, "U123", fake_client)

    assert first is True
    assert second is False
    fake_client.push_text.assert_awaited_once()


def test_formatter_includes_rain_warning() -> None:
    run = ForecastRun(
        id=1, location_id=1, provider="open_meteo",
        retrieved_at=datetime(2024, 6, 1, tzinfo=UTC), forecast_days=7,
    )
    run.location = Location(name="Pattaya", slug="pattaya", latitude=12.9, longitude=100.8, timezone="UTC")
    run.daily_forecasts = [DailyForecast(
        forecast_date=date(2024, 6, 1), temperature_2m_min=25.0,
        temperature_2m_max=32.0, precipitation_probability_max=80.0,
    )]

    text = format_forecast_alert(run)

    assert "Pattaya" in text
    assert "25-32°C" in text
    assert "rain 80%" in text
    assert "Rain warning" in text

@pytest.mark.asyncio
async def test_current_location_alert_targets_each_user(db_session: AsyncSession) -> None:
    from app.models.user import User
    from app.notifications.service import send_current_location_alerts

    location = Location(name="User Area", slug="user-area", latitude=12.9, longitude=100.8, timezone="UTC", provider="open_meteo")
    db_session.add(location)
    await db_session.flush()
    user = User(external_id="U999", current_location_id=location.id)
    db_session.add(user)
    await db_session.flush()
    run = ForecastRun(location_id=location.id, provider="open_meteo", retrieved_at=datetime(2024, 6, 1, tzinfo=UTC), forecast_days=7)
    db_session.add(run)
    await db_session.flush()
    db_session.add(DailyForecast(forecast_run_id=run.id, forecast_date=date(2024, 6, 1), temperature_2m_min=25.0, temperature_2m_max=32.0))
    await db_session.flush()

    fake_client = AsyncMock()
    result = await send_current_location_alerts(db_session, fake_client)
    assert result == {"sent": 1, "skipped": 0}
    fake_client.push_text.assert_awaited_once()
    assert fake_client.push_text.await_args.args[0] == "U999"
