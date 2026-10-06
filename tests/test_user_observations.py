from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select

from app.ingestion.service import IngestionError, ingest_user_observations
from app.models.location import Location
from app.models.observation import Observation
from app.models.user import User
from tests.conftest import FakeWeatherProvider


async def add_location(db, slug, active=True):
    location = Location(name=slug, slug=slug, latitude=13, longitude=100,
                        timezone="Asia/Bangkok", is_active=active)
    db.add(location)
    await db.flush()
    return location


@pytest.mark.asyncio
async def test_user_observations_unique_active_locations_and_idempotency(db_session):
    used = await add_location(db_session, "used")
    inactive = await add_location(db_session, "inactive", False)
    await add_location(db_session, "unbound-seed")
    db_session.add_all([
        User(external_id="browser-one", current_location_id=used.id),
        User(external_id="U_two", current_location_id=used.id),
        User(external_id="inactive-user", current_location_id=inactive.id),
        User(external_id="no-location"),
    ])
    await db_session.flush()
    fake = FakeWeatherProvider()
    fake.fetch_observations = AsyncMock(wraps=fake.fetch_observations)
    with patch("app.ingestion.service.get_provider", return_value=fake):
        first = await ingest_user_observations(db_session, date(2024, 6, 1), date(2024, 6, 1))
        second = await ingest_user_observations(db_session, date(2024, 6, 1), date(2024, 6, 1))
    assert first == {"locations": 1, "created": 2, "failed": 0}
    assert second == {"locations": 1, "created": 0, "failed": 0}
    assert fake.fetch_observations.await_count == 2
    assert set((await db_session.scalars(select(Observation.location_id))).all()) == {used.id}


@pytest.mark.asyncio
async def test_user_observations_provider_failure_isolated(db_session):
    bad = await add_location(db_session, "bad")
    good = await add_location(db_session, "good")
    db_session.add_all([User(external_id="bad", current_location_id=bad.id),
                       User(external_id="good", current_location_id=good.id)])
    await db_session.flush()
    fake = FakeWeatherProvider()
    result = await fake.fetch_observations(13, 100, date(2024, 6, 1), date(2024, 6, 1))
    fake.fetch_observations = AsyncMock(side_effect=[RuntimeError("unavailable"), result])
    with patch("app.ingestion.service.get_provider", return_value=fake):
        counts = await ingest_user_observations(db_session, date(2024, 6, 1), date(2024, 6, 1))
    assert counts == {"locations": 2, "created": 2, "failed": 1}
    assert await db_session.scalar(select(func.count()).select_from(Observation)) == 2


@pytest.mark.asyncio
async def test_user_observations_default_retries_seven_completed_dates(db_session):
    loc = await add_location(db_session, "rolling")
    db_session.add(User(external_id="rolling", current_location_id=loc.id))
    await db_session.flush()
    with patch("app.ingestion.service.ingest_observations_for_location", new=AsyncMock(return_value=0)) as fetch:
        await ingest_user_observations(db_session, end_date=date(2024, 6, 7))
    assert fetch.await_args.args[2:] == (date(2024, 6, 1), date(2024, 6, 7))


@pytest.mark.asyncio
async def test_user_observations_no_users_does_not_request_seeds(db_session):
    await add_location(db_session, "seed-only")
    with patch("app.ingestion.service.get_provider") as provider:
        assert await ingest_user_observations(db_session) == {"locations": 0, "created": 0, "failed": 0}
    provider.assert_not_called()


@pytest.mark.asyncio
async def test_user_observations_invalid_range(db_session):
    with pytest.raises(IngestionError, match="start_date"):
        await ingest_user_observations(db_session, date(2024, 6, 2), date(2024, 6, 1))


@pytest.mark.asyncio
async def test_morning_pipeline_commits_observations_before_alerts():
    from unittest.mock import MagicMock
    from app.notifications import cli

    events = []
    db = MagicMock()

    async def ingest(session):
        assert session is db
        events.append("observations")
        return {"locations": 2, "created": 2, "failed": 1}

    async def commit():
        events.append("commit")

    async def alerts():
        events.append("alerts")
        return {"sent": 0, "skipped": 1}

    db.commit = AsyncMock(side_effect=commit)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=db)
    context.__aexit__ = AsyncMock(return_value=False)
    with patch.object(cli, "AsyncSessionLocal", return_value=context), \
         patch.object(cli, "ingest_user_observations", side_effect=ingest), \
         patch.object(cli, "send_user_alerts", side_effect=alerts):
        await cli._main()
    assert events == ["observations", "commit", "alerts"]
