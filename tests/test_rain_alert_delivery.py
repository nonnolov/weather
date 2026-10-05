from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.forecast import ForecastRun
from app.models.location import Location
from app.models.user import User
from app.notifications.line_client import LineApiError
from app.notifications.rain_alerts import send_current_rain_alerts


UTC = timezone.utc


async def _add_user_with_run(
    db_session: AsyncSession, external_id: str, slug: str
) -> ForecastRun:
    location = Location(
        name=slug,
        slug=slug,
        latitude=12.9,
        longitude=100.8,
        timezone="Asia/Bangkok",
        provider="open_meteo",
    )
    db_session.add(location)
    await db_session.flush()
    db_session.add(User(external_id=external_id, current_location_id=location.id))
    run = ForecastRun(
        location_id=location.id,
        provider="open_meteo",
        retrieved_at=datetime(2026, 10, 5, tzinfo=UTC),
        forecast_days=7,
    )
    db_session.add(run)
    await db_session.flush()
    return run


@pytest.mark.asyncio
async def test_current_rain_alert_skips_browser_identity(
    db_session: AsyncSession,
) -> None:
    await _add_user_with_run(db_session, "browser-123", "browser-area")
    client = AsyncMock()

    result = await send_current_rain_alerts(db_session, client)

    assert result == {"sent": 0, "skipped": 1, "failed": 0}
    client.push_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_line_failure_does_not_abort_remaining_users(
    db_session: AsyncSession,
) -> None:
    await _add_user_with_run(db_session, "U_BAD", "bad-area")
    await _add_user_with_run(db_session, "U_GOOD", "good-area")
    client = AsyncMock()

    with patch(
        "app.notifications.rain_alerts.send_rain_alert",
        new=AsyncMock(side_effect=[LineApiError("bad recipient"), True]),
    ) as send_alert:
        result = await send_current_rain_alerts(db_session, client)

    assert result == {"sent": 1, "skipped": 0, "failed": 1}
    assert send_alert.await_count == 2
