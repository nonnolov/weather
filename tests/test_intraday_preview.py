"""Committed-snapshot entrypoint: dedicated PostgreSQL and preview only."""
import json
from argparse import Namespace
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, event, func, select, update
from sqlalchemy.exc import OperationalError

from app.models import ForecastRun, HourlyForecast, Location, NotificationDelivery, User
from app.notifications.intraday_comparison import Decision
from app.notifications.intraday_preview import read_committed_candidate, preview_committed_snapshots
from app.notifications.intraday_preview_cli import main, parser, run
from tests.test_intraday_baseline import NOW, H
from tests.test_intraday_delivery import source_sessions
from tests.test_rain_locking_postgres import PG_URL, pg_sessions

pg = pytest.mark.skipif(not PG_URL, reason="Dedicated localhost PostgreSQL required")


def test_help_and_argument_validation_do_not_initialize_database(capsys):
    with pytest.raises(SystemExit) as stopped:
        main(["--help"])
    assert stopped.value.code == 0
    assert "never sends LINE" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [[], ["--recipient", "U_TEST", "--send"],
                                   ["--recipient", "U_TEST", "--dry-run", "false"],
                                   ["--recipient", "C_GROUP"]])
def test_no_live_send_or_implicit_batch_options(argv):
    with pytest.raises(SystemExit) as stopped:
        main(argv)
    assert stopped.value.code == 2


@pg
@pytest.mark.asyncio
async def test_end_to_end_preview_uses_committed_snapshot_and_does_not_write(source_sessions):
    engine = source_sessions.kw["bind"].sync_engine
    statements = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().upper())
    event.listen(engine, "before_cursor_execute", capture)
    try:
        results = await preview_committed_snapshots(source_sessions, ["U_TEST"], clock=lambda: NOW)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    result = results[0]
    assert result.source_id == 12 and result.result.status == "preview"
    assert result.result.message and result.result.decision.event_id
    assert any("REPEATABLE READ, READ ONLY" in sql for sql in statements)
    assert not any(sql.startswith(("INSERT ", "UPDATE ", "DELETE ")) for sql in statements)
    async with source_sessions() as db:
        assert await db.scalar(select(func.count()).select_from(NotificationDelivery)) == 1


@pg
@pytest.mark.asyncio
async def test_uncommitted_newer_run_is_invisible_then_selected_after_commit(source_sessions):
    async with source_sessions() as writer:
        writer.add(ForecastRun(id=13, location_id=101, provider="open_meteo", retrieved_at=NOW))
        await writer.flush()
        old = await read_committed_candidate(source_sessions, "U_TEST", now=NOW)
        assert old.source_id == 12
        await writer.commit()
    newest = await read_committed_candidate(source_sessions, "U_TEST", now=NOW)
    assert isinstance(newest, Decision)
    assert newest.reasons == ("no_snapshot_hours_for_local_day",)


@pg
@pytest.mark.asyncio
async def test_tied_latest_run_uses_largest_id_without_falling_back(source_sessions):
    async with source_sessions() as db:
        db.add(ForecastRun(id=13, location_id=101, provider="open_meteo", retrieved_at=NOW-H/2))
        await db.commit()
    result = await read_committed_candidate(source_sessions, "U_TEST", now=NOW)
    assert result.reasons == ("no_snapshot_hours_for_local_day",)


@pg
@pytest.mark.asyncio
async def test_current_local_day_keeps_elapsed_unknown_and_midnight_ending_hour(source_sessions):
    midnight = NOW.replace(hour=17) - timedelta(days=1)  # Bangkok midnight at 17 UTC.
    async with source_sessions() as db:
        db.add_all([
            HourlyForecast(forecast_run_id=12, valid_time=midnight, precipitation=None),
            HourlyForecast(forecast_run_id=12, valid_time=midnight+H, precipitation=None),
            HourlyForecast(forecast_run_id=12, valid_time=midnight+24*H, precipitation=None),
            HourlyForecast(forecast_run_id=12, valid_time=midnight+25*H, precipitation=None),
        ])
        await db.commit()
    result = await read_committed_candidate(source_sessions, "U_TEST", now=NOW)
    assert len(result.hours) == 8
    assert result.hours[0].start == midnight and result.hours[0].probability is None
    assert result.hours[-1].end == midnight+24*H
    assert all(hour.start.astimezone(__import__("zoneinfo").ZoneInfo("Asia/Bangkok")).date()
               == NOW.astimezone(__import__("zoneinfo").ZoneInfo("Asia/Bangkok")).date()
               for hour in result.hours)


@pg
@pytest.mark.asyncio
@pytest.mark.parametrize("change,reason", [
    ("missing_user", "no_current_location"), ("inactive", "inactive_location"),
    ("timezone", "invalid_timezone"), ("no_run", "no_committed_snapshot"),
    ("stale", "stale_candidate"), ("missing_hour", "incomplete_coverage"),
    ("null", "incomplete_coverage"), ("provider", "scope_mismatch"),
])
async def test_entrypoint_preserves_fail_closed_decisions(source_sessions, change, reason):
    async with source_sessions() as db:
        if change == "missing_user":
            await db.execute(delete(User))
        elif change == "inactive":
            await db.execute(update(Location).values(is_active=False))
        elif change == "timezone":
            await db.execute(update(Location).values(timezone="invalid/zone"))
        elif change == "no_run":
            await db.execute(delete(ForecastRun))
        elif change == "stale":
            await db.execute(update(ForecastRun).values(retrieved_at=NOW-2*H))
        elif change == "missing_hour":
            await db.execute(delete(HourlyForecast).where(HourlyForecast.valid_time == NOW+H))
        elif change == "null":
            await db.execute(update(HourlyForecast).values(precipitation_probability=None))
        else:
            await db.execute(update(ForecastRun).values(provider="other"))
        await db.commit()
    result = (await preview_committed_snapshots(source_sessions, ["U_TEST"], clock=lambda: NOW))[0]
    assert result.result.status == "skip" and result.result.decision.reasons == (reason,)
    assert result.result.message is None


@pg
@pytest.mark.asyncio
async def test_preview_rechecks_assignment_changed_after_snapshot(source_sessions, monkeypatch):
    import app.notifications.intraday_preview as module
    original = module.read_committed_candidate
    async def change(*args, **kwargs):
        candidate = await original(*args, **kwargs)
        async with source_sessions() as db:
            await db.execute(update(User).values(current_location_id=102))
            await db.commit()
        return candidate
    monkeypatch.setattr(module, "read_committed_candidate", change)
    result = (await module.preview_committed_snapshots(source_sessions, ["U_TEST"], clock=lambda: NOW))[0]
    assert result.result.decision.reasons == ("location_changed",)


@pg
@pytest.mark.asyncio
async def test_preview_rechecks_source_changed_after_snapshot(source_sessions, monkeypatch):
    import app.notifications.intraday_preview as module
    original = module.read_committed_candidate
    async def change(*args, **kwargs):
        candidate = await original(*args, **kwargs)
        async with source_sessions() as db:
            await db.execute(update(HourlyForecast).values(precipitation_probability=99))
            await db.commit()
        return candidate
    monkeypatch.setattr(module, "read_committed_candidate", change)
    result = (await module.preview_committed_snapshots(source_sessions, ["U_TEST"], clock=lambda: NOW))[0]
    assert result.result.decision.reasons == ("candidate_source_mismatch",)


@pg
@pytest.mark.asyncio
async def test_batch_deduplicates_orders_and_samples_fresh_clock(source_sessions):
    calls = []
    def clock():
        calls.append(NOW)
        return NOW
    results = await preview_committed_snapshots(source_sessions, ["U_TEST", "U_NONE", "U_TEST"], clock=clock)
    assert [item.recipient_id for item in results] == ["U_NONE", "U_TEST"]
    assert [item.result.status for item in results] == ["skip", "preview"]
    assert len(calls) == 4  # One per build, plus two locked/final delivery checks.


@pg
@pytest.mark.asyncio
async def test_cli_summary_does_not_expose_recipient_or_messages(source_sessions, capsys, monkeypatch):
    import app.notifications.intraday_preview as module
    original = module.preview_committed_snapshots
    async def at_fixed_clock(sessions, recipients):
        return await original(sessions, recipients, clock=lambda: NOW)
    monkeypatch.setattr(module, "preview_committed_snapshots", at_fixed_clock)
    assert await run(Namespace(recipient=["U_TEST"], show_messages=False), source_sessions) == 0
    raw = capsys.readouterr().out
    report = json.loads(raw)
    assert report["mode"] == "preview" and report["statuses"] == {"preview": 1}
    assert "U_TEST" not in raw and "messages" not in report


@pg
@pytest.mark.asyncio
async def test_database_error_is_reported_without_retry_or_secret_text(source_sessions, monkeypatch, capsys):
    import app.notifications.intraday_preview as module
    reader = AsyncMock(side_effect=OperationalError("private credentials", {}, RuntimeError("private")))
    monkeypatch.setattr(module, "read_committed_candidate", reader)
    args = Namespace(recipient=["U_TEST"], show_messages=False)
    assert await run(args, source_sessions) == 1
    report = capsys.readouterr().out
    assert "database_error" in report and "private" not in report
    reader.assert_awaited_once()


@pg
@pytest.mark.asyncio
async def test_snapshot_queries_do_not_mix_concurrently_committed_versions(source_sessions, monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession
    original = AsyncSession.execute
    changed = False
    async def intercept(self, statement, *args, **kwargs):
        nonlocal changed
        result = await original(self, statement, *args, **kwargs)
        sql = str(statement)
        if not changed and sql.startswith("SELECT forecast_runs.id"):
            changed = True
            async with source_sessions() as writer:
                await original(writer, update(HourlyForecast).values(precipitation_probability=99))
                await original(writer, update(ForecastRun).values(retrieved_at=NOW))
                await writer.commit()
        return result
    monkeypatch.setattr(AsyncSession, "execute", intercept)
    candidate = await read_committed_candidate(source_sessions, "U_TEST", now=NOW)
    assert changed and candidate.retrieved_at == NOW-H/2
    assert all(hour.probability == 70 for hour in candidate.hours)
    # The next private transaction sees the fully committed newer version.
    next_candidate = await read_committed_candidate(source_sessions, "U_TEST", now=NOW)
    assert next_candidate.retrieved_at == NOW
    assert all(hour.probability == 99 for hour in next_candidate.hours)


@pytest.mark.asyncio
async def test_caller_owned_uncommitted_connection_factory_is_rejected():
    from sqlalchemy.ext.asyncio import async_sessionmaker
    with pytest.raises(ValueError, match="engine-bound"):
        await read_committed_candidate(async_sessionmaker(), "U_TEST", now=NOW)
