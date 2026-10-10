"""Forecast-only scheduler and real PostgreSQL serialization, no live network."""
import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import event, func, select, text, update

from app.core.config import settings
from app.models import ForecastRun, HourlyForecast, Location, NotificationDelivery, User
from app.notifications import scheduled_preview as scheduler
from tests.test_intraday_baseline import NOW, H, candidate
from tests.test_intraday_delivery import source_sessions
from tests.test_rain_locking_postgres import PG_URL, pg_sessions

pg = pytest.mark.skipif(not PG_URL, reason="Dedicated localhost PostgreSQL required")


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "INTRADAY_PREVIEW_SCHEDULER_ENABLED", True)


async def due(factory):
    async with factory() as db:
        await db.execute(update(ForecastRun).values(retrieved_at=NOW-H))
        await db.commit()


def mock_ingest(monkeypatch):
    from app.ingestion import service
    async def ingest(db, location, forecast_days):
        assert forecast_days == 7
        run = ForecastRun(id=13, location_id=location.id, provider="open_meteo", retrieved_at=NOW)
        db.add(run)
        await db.flush()
        db.add_all(HourlyForecast(forecast_run_id=13, valid_time=h.end,
                                 precipitation_probability=70, precipitation=0) for h in candidate().hours)
        await db.flush()
        return run
    mocked = AsyncMock(side_effect=ingest)
    monkeypatch.setattr(service, "ingest_forecast_for_location", mocked)
    monkeypatch.setattr(service, "ingest_user_observations", AsyncMock(side_effect=AssertionError("no observations")))
    from app.notifications.line_client import LineClient
    monkeypatch.setattr(LineClient, "push_text", AsyncMock(side_effect=AssertionError("no LINE")))
    return mocked


@pytest.mark.asyncio
async def test_default_off_does_not_open_database():
    assert settings.INTRADAY_PREVIEW_SCHEDULER_ENABLED is False
    report = await scheduler.run_scheduled_preview_cycle(object())
    assert report.status == "disabled"


@pytest.mark.asyncio
async def test_enabled_rejects_non_pg_factory(enabled):
    with pytest.raises(ValueError):
        await scheduler.run_scheduled_preview_cycle(object())


@pg
@pytest.mark.asyncio
async def test_commit_before_real_preview_and_fresh_tick_does_not_fetch_again(source_sessions, enabled, monkeypatch):
    await due(source_sessions)
    fetch = mock_ingest(monkeypatch)
    import app.notifications.intraday_preview as preview
    real = preview.preview_committed_snapshots
    async def check(factory, recipients, clock):
        async with factory() as reader:
            assert await reader.get(ForecastRun, 13) is not None
            assert await reader.scalar(select(func.count()).select_from(HourlyForecast)
                                       .where(HourlyForecast.forecast_run_id == 13)) == 6
        return await real(factory, recipients, clock=clock)
    monkeypatch.setattr(preview, "preview_committed_snapshots", check)
    first = await scheduler.run_scheduled_preview_cycle(source_sessions, clock=lambda: NOW)
    second = await scheduler.run_scheduled_preview_cycle(source_sessions, clock=lambda: NOW+timedelta(minutes=15))
    assert first.status == second.status == "complete"
    assert first.refreshed == 1 and first.processed == 1 and first.statuses == {"preview": 1}
    assert second.fresh == 1 and second.refreshed == 0
    fetch.assert_awaited_once()
    async with source_sessions() as reader:
        assert await reader.scalar(select(func.count()).select_from(NotificationDelivery)) == 1


@pg
@pytest.mark.asyncio
async def test_shared_locations_are_unique_browser_and_inactive_are_excluded(source_sessions, enabled, monkeypatch):
    async with source_sessions() as db:
        db.add_all([User(external_id="U_SECOND", current_location_id=101),
                    User(external_id="BROWSER", current_location_id=102),
                    Location(id=103, name="inactive", slug="inactive", latitude=0, longitude=0, is_active=False),
                    User(external_id="U_INACTIVE", current_location_id=103)])
        await db.commit()
    await due(source_sessions)
    fetch = mock_ingest(monkeypatch)
    report = await scheduler.run_scheduled_preview_cycle(source_sessions, clock=lambda: NOW)
    assert report.locations == report.refreshed == 1 and report.processed == 2
    fetch.assert_awaited_once()


@pg
@pytest.mark.asyncio
@pytest.mark.parametrize("age,expected", [(59, "fresh"), (60, "refreshed"), (61, "refreshed")])
async def test_refresh_age_boundary(source_sessions, enabled, monkeypatch, age, expected):
    async with source_sessions() as db:
        await db.execute(update(ForecastRun).values(retrieved_at=NOW-timedelta(minutes=age)))
        await db.commit()
    fetch = mock_ingest(monkeypatch)
    report = await scheduler.run_scheduled_preview_cycle(source_sessions, clock=lambda: NOW)
    assert getattr(report, expected) == 1
    assert fetch.await_count == (expected == "refreshed")


@pg
@pytest.mark.asyncio
async def test_concurrent_cycle_skips_then_cancel_releases_lock(source_sessions, enabled, monkeypatch):
    await due(source_sessions)
    entered = asyncio.Event()
    from app.ingestion import service
    async def block(*args, **kwargs):
        entered.set()
        await asyncio.Future()
    monkeypatch.setattr(service, "ingest_forecast_for_location", block)
    task = asyncio.create_task(scheduler.run_scheduled_preview_cycle(source_sessions, clock=lambda: NOW))
    await asyncio.wait_for(entered.wait(), 3)
    busy = await scheduler.run_scheduled_preview_cycle(source_sessions, clock=lambda: NOW)
    assert busy.status == "busy" and busy.refreshed == 0
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    mock_ingest(monkeypatch)
    resumed = await scheduler.run_scheduled_preview_cycle(source_sessions, clock=lambda: NOW)
    assert resumed.status == "complete" and resumed.refreshed == 1


@pg
@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["fetch", "commit"])
async def test_failed_refresh_never_previews_and_rolls_back(source_sessions, enabled, monkeypatch, caplog, failure):
    await due(source_sessions)
    from app.ingestion import service
    if failure == "fetch":
        monkeypatch.setattr(service, "ingest_forecast_for_location",
                            AsyncMock(side_effect=RuntimeError("PRIVATE credentials")))
    else:
        mock_ingest(monkeypatch)
    import app.notifications.intraday_preview as preview
    checker = AsyncMock()
    monkeypatch.setattr(preview, "preview_committed_snapshots", checker)
    sync = source_sessions.kw["bind"].sync_engine
    def fail(conn):
        # Only the source commit contains a new forecast.
        if conn.info.pop("fail_source", False):
            raise RuntimeError("PRIVATE commit credentials")
    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT INTO FORECAST_RUNS"):
            conn.info["fail_source"] = True
    if failure == "commit":
        event.listen(sync, "before_cursor_execute", capture)
        event.listen(sync, "commit", fail)
    try:
        report = await scheduler.run_scheduled_preview_cycle(source_sessions, clock=lambda: NOW)
    finally:
        if failure == "commit":
            event.remove(sync, "commit", fail)
            event.remove(sync, "before_cursor_execute", capture)
    assert report.refresh_failed == 1 and report.refreshed == 0
    checker.assert_not_awaited()
    assert "PRIVATE" not in caplog.text
    async with source_sessions() as db:
        assert await db.get(ForecastRun, 13) is None


@pg
@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["error", "timeout", "cancel"])
async def test_preview_failure_preserves_committed_forecast(source_sessions, enabled, monkeypatch, failure, caplog):
    await due(source_sessions)
    mock_ingest(monkeypatch)
    import app.notifications.intraday_preview as preview
    if failure == "error":
        checker = AsyncMock(side_effect=RuntimeError("PRIVATE provider recipient"))
    elif failure == "cancel":
        checker = AsyncMock(side_effect=asyncio.CancelledError())
    else:
        async def block(*args, **kwargs):
            await asyncio.Future()
        checker = AsyncMock(side_effect=block)
        monkeypatch.setattr(scheduler, "PREVIEW_TIMEOUT_SECONDS", .01)
    monkeypatch.setattr(preview, "preview_committed_snapshots", checker)
    if failure == "cancel":
        with pytest.raises(asyncio.CancelledError):
            await scheduler.run_scheduled_preview_cycle(source_sessions, clock=lambda: NOW)
    else:
        report = await scheduler.run_scheduled_preview_cycle(source_sessions, clock=lambda: NOW)
        assert report.refreshed == 1 and report.status == ("timeout" if failure == "timeout" else "error")
    assert "PRIVATE" not in caplog.text
    async with source_sessions() as reader:
        assert await reader.get(ForecastRun, 13) is not None
        assert await reader.scalar(select(func.count()).select_from(NotificationDelivery)) == 1


@pg
@pytest.mark.asyncio
async def test_total_cycle_deadline_releases_lock_and_cancels_uncommitted_refresh(source_sessions, enabled, monkeypatch):
    await due(source_sessions)
    from app.ingestion import service
    async def block(*args, **kwargs):
        await asyncio.Future()
    monkeypatch.setattr(service, "ingest_forecast_for_location", block)
    monkeypatch.setattr(scheduler, "CYCLE_TIMEOUT_SECONDS", .1)
    report = await scheduler.run_scheduled_preview_cycle(source_sessions, clock=lambda: NOW)
    assert report.status == "timeout"
    async with source_sessions() as db:
        assert await db.scalar(select(func.pg_try_advisory_xact_lock(scheduler.CYCLE_LOCK_KEY))) is True


@pg
@pytest.mark.asyncio
async def test_assignment_rechecked_before_provider_fetch(source_sessions, enabled, monkeypatch):
    from app.ingestion import service
    fetch = AsyncMock()
    monkeypatch.setattr(service, "ingest_forecast_for_location", fetch)
    async with source_sessions() as db:
        await db.execute(update(User).values(current_location_id=102))
        await db.commit()
    assert await scheduler._refresh_if_due(source_sessions, 101, lambda: NOW) == "out_of_scope"
    fetch.assert_not_awaited()


@pg
@pytest.mark.asyncio
async def test_location_bound_chooses_oldest_and_reports_truncation(source_sessions, enabled, monkeypatch):
    async with source_sessions() as db:
        db.add(User(external_id="U_NO_SOURCE", current_location_id=102))
        await db.commit()
    monkeypatch.setattr(scheduler, "MAX_LOCATIONS", 1)
    refreshed = []
    async def fake(factory, location_id, clock):
        refreshed.append(location_id)
        return "fresh"
    monkeypatch.setattr(scheduler, "_refresh_if_due", fake)
    report = await scheduler.run_scheduled_preview_cycle(source_sessions, clock=lambda: NOW)
    assert refreshed == [102] and report.locations == 1 and report.truncated


@pg
@pytest.mark.asyncio
async def test_recipient_batch_is_bounded_and_no_delivery_written(source_sessions, enabled, monkeypatch):
    async with source_sessions() as db:
        db.add_all(User(external_id=f"U_BATCH_{i:03}", current_location_id=101) for i in range(103))
        await db.commit()
    import app.notifications.intraday_preview as preview
    check = AsyncMock(return_value=())
    monkeypatch.setattr(preview, "preview_committed_snapshots", check)
    report = await scheduler.run_scheduled_preview_cycle(source_sessions, clock=lambda: NOW)
    recipients = check.await_args.args[1]
    assert len(recipients) == 100 and recipients == sorted(set(recipients))
    assert report.truncated


@pytest.mark.asyncio
async def test_disabled_lifespan_never_creates_task(monkeypatch):
    serve = AsyncMock()
    monkeypatch.setattr(scheduler, "_serve", serve)
    async with scheduler.scheduled_preview_lifespan(None):
        pass
    serve.assert_not_awaited()


@pg
@pytest.mark.asyncio
async def test_actual_api_lifespan_starts_and_cancels_owned_task(source_sessions, enabled, monkeypatch):
    from app.core import database
    from app.main import app
    monkeypatch.setattr(database, "AsyncSessionLocal", source_sessions)
    started = asyncio.Event()
    stopped = asyncio.Event()
    async def serve(factory):
        assert factory is source_sessions
        started.set()
        try:
            await asyncio.Future()
        finally:
            stopped.set()
    monkeypatch.setattr(scheduler, "_serve", serve)
    async with app.router.lifespan_context(app):
        await asyncio.wait_for(started.wait(), 1)
    assert stopped.is_set()


@pytest.mark.asyncio
async def test_loop_waits_for_each_cycle_and_never_catches_up(monkeypatch):
    delays = []
    async def sleep(delay):
        delays.append(delay)
        if len(delays) == 3:
            raise asyncio.CancelledError()
    run = AsyncMock()
    monkeypatch.setattr(scheduler, "asyncio", SimpleNamespace(sleep=sleep))
    monkeypatch.setattr(scheduler, "run_scheduled_preview_cycle", run)
    with pytest.raises(asyncio.CancelledError):
        await scheduler._serve("factory")
    assert delays == [60, 900, 900] and run.await_count == 2
