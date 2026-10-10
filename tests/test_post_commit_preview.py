"""Actual request commit boundary with isolated PostgreSQL; no live sender."""
import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import event, func, select, update

from app.core import database
from app.core.config import settings
from app.models import ForecastRun, HourlyForecast, NotificationDelivery, User
from app.notifications import post_commit_preview as bridge
from tests.test_intraday_baseline import NOW, H, candidate
from tests.test_intraday_delivery import source_sessions
from tests.test_rain_locking_postgres import PG_URL, pg_sessions

pytestmark = pytest.mark.skipif(not PG_URL, reason="Dedicated local PostgreSQL required")


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "INTRADAY_PREVIEW_AFTER_REFRESH", True)


async def request_session(factory, monkeypatch):
    monkeypatch.setattr(database, "AsyncSessionLocal", factory)
    dependency = database.get_db()
    return dependency, await anext(dependency)


async def seed_new_run(db):
    db.add(ForecastRun(id=13, location_id=101, provider="open_meteo", retrieved_at=NOW-H/2))
    await db.flush()
    db.add_all(HourlyForecast(forecast_run_id=13, valid_time=hour.end,
                              precipitation_probability=70, precipitation=0)
               for hour in candidate().hours)
    await db.flush()
    bridge.queue_forecast_preview(db, 101, 13)


async def finish(dependency):
    with pytest.raises(StopAsyncIteration):
        await anext(dependency)


@pytest.mark.asyncio
async def test_default_off_does_not_queue_or_run(source_sessions, monkeypatch):
    assert settings.INTRADAY_PREVIEW_AFTER_REFRESH is False
    runner = AsyncMock()
    monkeypatch.setattr(bridge, "_evaluate", runner)
    dependency, db = await request_session(source_sessions, monkeypatch)
    await seed_new_run(db)
    await finish(dependency)
    runner.assert_not_awaited()


@pytest.mark.asyncio
async def test_commit_precedes_preview_and_no_delivery_is_written(source_sessions, enabled, monkeypatch):
    original = bridge._evaluate
    results = []
    async def checked(factory, queued):
        async with factory() as reader:
            assert await reader.get(ForecastRun, 13) is not None
            assert await reader.scalar(select(func.count()).select_from(HourlyForecast)
                                       .where(HourlyForecast.forecast_run_id == 13)) == 6
        import app.notifications.intraday_preview as preview
        real = preview.preview_committed_snapshots
        async def fixed(factory, recipients):
            return await real(factory, recipients, clock=lambda: NOW)
        monkeypatch.setattr(preview, "preview_committed_snapshots", fixed)
        value = await original(factory, queued)
        results.extend(value[0])
        return value
    monkeypatch.setattr(bridge, "_evaluate", checked)
    dependency, db = await request_session(source_sessions, monkeypatch)
    await seed_new_run(db)
    assert results == []
    await finish(dependency)
    assert len(results) == 1 and results[0].result.status == "preview"
    async with source_sessions() as reader:
        assert await reader.scalar(select(func.count()).select_from(NotificationDelivery)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["handler", "commit", "cancel"])
async def test_failed_transaction_never_previews(source_sessions, enabled, monkeypatch, failure):
    runner = AsyncMock()
    monkeypatch.setattr(bridge, "_evaluate", runner)
    dependency, db = await request_session(source_sessions, monkeypatch)
    await seed_new_run(db)
    engine = source_sessions.kw["bind"].sync_engine
    def fail(*args):
        raise RuntimeError("mock commit failure")
    if failure == "commit":
        event.listen(engine, "commit", fail)
    try:
        if failure == "handler":
            with pytest.raises(RuntimeError):
                await dependency.athrow(RuntimeError("mock handler failure"))
        elif failure == "cancel":
            with pytest.raises(asyncio.CancelledError):
                await dependency.athrow(asyncio.CancelledError())
        else:
            with pytest.raises(RuntimeError, match="mock commit"):
                await anext(dependency)
    finally:
        if failure == "commit":
            event.remove(engine, "commit", fail)
        await dependency.aclose()
    runner.assert_not_awaited()
    async with source_sessions() as reader:
        assert await reader.get(ForecastRun, 13) is None


@pytest.mark.asyncio
async def test_failed_flush_then_handler_error_does_not_preview(source_sessions, enabled, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    runner = AsyncMock()
    monkeypatch.setattr(bridge, "_evaluate", runner)
    dependency, db = await request_session(source_sessions, monkeypatch)
    bridge.queue_forecast_preview(db, 101, 13)
    db.add(ForecastRun(id=12, location_id=101, provider="open_meteo", retrieved_at=NOW))
    with pytest.raises(IntegrityError) as caught:
        await db.flush()
    with pytest.raises(IntegrityError):
        await dependency.athrow(caught.value)
    runner.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["error", "timeout"])
async def test_preview_failure_preserves_committed_source_and_sanitizes_logs(
    source_sessions, enabled, monkeypatch, caplog, failure,
):
    if failure == "error":
        runner = AsyncMock(side_effect=RuntimeError("PRIVATE secret recipient"))
    else:
        async def forever(*args):
            await asyncio.Future()
        runner = AsyncMock(side_effect=forever)
        monkeypatch.setattr(bridge, "PREVIEW_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(bridge, "_evaluate", runner)
    dependency, db = await request_session(source_sessions, monkeypatch)
    await seed_new_run(db)
    await finish(dependency)
    async with source_sessions() as reader:
        assert await reader.get(ForecastRun, 13) is not None
    assert "no retry" in caplog.text and "PRIVATE" not in caplog.text
    runner.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancellation_after_commit_does_not_erase_source(source_sessions, enabled, monkeypatch):
    monkeypatch.setattr(bridge, "_evaluate", AsyncMock(side_effect=asyncio.CancelledError()))
    dependency, db = await request_session(source_sessions, monkeypatch)
    await seed_new_run(db)
    with pytest.raises(asyncio.CancelledError):
        await anext(dependency)
    async with source_sessions() as reader:
        assert await reader.get(ForecastRun, 13) is not None


@pytest.mark.asyncio
async def test_queue_deduplicates_and_is_consumed_once(source_sessions, enabled, monkeypatch):
    runner = AsyncMock(return_value=((), False))
    monkeypatch.setattr(bridge, "_evaluate", runner)
    async with source_sessions() as db:
        bridge.queue_forecast_preview(db, 101, 12)
        bridge.queue_forecast_preview(db, 101, 13)
        await db.commit()
        await bridge.run_forecast_previews(db, source_sessions)
        await bridge.run_forecast_previews(db, source_sessions)
    runner.assert_awaited_once_with(source_sessions, {101: 13})


@pytest.mark.asyncio
async def test_uncommitted_session_cannot_run_hook(source_sessions, enabled):
    async with source_sessions() as db:
        await db.execute(select(ForecastRun.id))
        bridge.queue_forecast_preview(db, 101, 12)
        with pytest.raises(ValueError, match="transaction"):
            await bridge.run_forecast_previews(db, source_sessions)


@pytest.mark.asyncio
async def test_nonexistent_or_wrong_location_run_does_not_discover_recipients(
    source_sessions, enabled, monkeypatch,
):
    import app.notifications.intraday_preview as module
    runner = AsyncMock()
    monkeypatch.setattr(module, "preview_committed_snapshots", runner)
    async with source_sessions() as db:
        bridge.queue_forecast_preview(db, 102, 12)
        bridge.queue_forecast_preview(db, 101, 999)
        await db.commit()
        assert await bridge.run_forecast_previews(db, source_sessions) == ()
    runner.assert_not_awaited()


@pytest.mark.asyncio
async def test_recipient_discovery_is_current_unique_bounded_and_line_only(source_sessions, enabled, monkeypatch):
    import app.notifications.intraday_preview as module
    async with source_sessions() as db:
        db.add_all([User(external_id="BROWSER", current_location_id=101),
                    User(external_id="U_OTHER_LOCATION", current_location_id=102)] +
                   [User(external_id=f"U_BATCH_{i:03}", current_location_id=101) for i in range(105)])
        await db.commit()
        bridge.queue_forecast_preview(db, 101, 12)
        runner = AsyncMock(return_value=())
        monkeypatch.setattr(module, "preview_committed_snapshots", runner)
        await bridge.run_forecast_previews(db, source_sessions)
    recipients = runner.await_args.args[1]
    assert len(recipients) == 100 and recipients == sorted(set(recipients))
    assert "BROWSER" not in recipients and "U_OTHER_LOCATION" not in recipients


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["user", "location"])
async def test_explicit_refresh_routes_queue_only_after_successful_ingestion(
    source_sessions, enabled, monkeypatch, route,
):
    from app.api.v1 import users, forecasts
    module = users if route == "user" else forecasts
    async def ingest(db, location, forecast_days):
        await seed_new_run(db)
        return await db.get(ForecastRun, 13)
    monkeypatch.setattr(module, "ingest_forecast_for_location", ingest)
    queued = []
    original = bridge.queue_forecast_preview
    def spy(db, location_id, run_id):
        queued.append((location_id, run_id))
        original(db, location_id, run_id)
    monkeypatch.setattr(bridge, "queue_forecast_preview", spy)
    async with source_sessions() as db:
        if route == "user":
            result = await users.refresh_user_forecast("U_TEST", 7, db)
        else:
            result = await forecasts.trigger_ingestion(101, 7, db)
        assert result.forecast_run_id == 13 and queued[-1] == (101, 13)
        await db.rollback()
