"""Real local PostgreSQL, mock LINE only; durable ambiguous-send protection."""
import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import event, func, select

from app.core.config import Settings, settings
from app.models import IntradaySendAttempt, NotificationDelivery
from app.notifications.intraday_delivery import (
    AcceptedDeliveryNotCommitted, SendOutcomeUnknown, deliver_intraday_update,
)
from app.notifications.intraday_live import send_committed_snapshots
from app.notifications.line_client import LineApiError, LineClient
from tests.test_intraday_baseline import NOW, candidate
from tests.test_intraday_delivery import source_sessions
from tests.test_rain_locking_postgres import PG_URL, pg_sessions

pg = pytest.mark.skipif(not PG_URL, reason="Dedicated localhost PostgreSQL required")


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setattr(settings, "INTRADAY_SEND_ENABLED", True)
    monkeypatch.setattr(settings, "LINE_CHANNEL_ACCESS_TOKEN", "mock-token")
    monkeypatch.setattr(settings, "INTRADAY_SEND_RECIPIENT_IDS", "U_TEST")


async def counts(factory):
    async with factory() as db:
        return (await db.scalar(select(func.count()).select_from(NotificationDelivery)),
                list((await db.scalars(select(IntradaySendAttempt))).all()))


@pytest.mark.parametrize("override", [
    {"INTRADAY_PREVIEW_SCHEDULER_ENABLED": False},
    {"LINE_CHANNEL_ACCESS_TOKEN": None},
    {"INTRADAY_SEND_RECIPIENT_IDS": ""},
    {"INTRADAY_SEND_RECIPIENT_IDS": "BROWSER"},
])
def test_live_config_fails_closed(override):
    args = dict(INTRADAY_SEND_ENABLED=True, INTRADAY_PREVIEW_SCHEDULER_ENABLED=True,
                LINE_CHANNEL_ACCESS_TOKEN="mock", INTRADAY_SEND_RECIPIENT_IDS="U_TEST")
    args.update(override)
    with pytest.raises(ValueError):
        Settings(_env_file=None, **args)


def test_live_off_by_default():
    assert Settings(_env_file=None).INTRADAY_SEND_ENABLED is False


@pg
@pytest.mark.asyncio
async def test_acceptance_intent_and_delivery_commit_together_then_replay(source_sessions, live, monkeypatch):
    async def accepted(recipient, message):
        total, attempts = await counts(source_sessions)
        assert total == 1 and len(attempts) == 1 and attempts[0].status == "pending"
        assert attempts[0].evidence["message_text"] == message
    push = AsyncMock(side_effect=accepted)
    monkeypatch.setattr(LineClient, "push_text", push)
    first = await send_committed_snapshots(source_sessions, ["U_TEST", "U_TEST"], clock=lambda: NOW)
    second = await send_committed_snapshots(source_sessions, ["U_TEST"], clock=lambda: NOW)
    assert first[0].result.status == "sent" and second[0].result.status == "suppress"
    total, attempts = await counts(source_sessions)
    assert total == 2 and len(attempts) == 1 and attempts[0].status == "accepted"
    assert attempts[0].delivery_id == first[0].result.delivery_id
    push.assert_awaited_once()


@pg
@pytest.mark.asyncio
@pytest.mark.parametrize("error", [TimeoutError(), httpx.ReadError("private"), LineApiError("private")])
async def test_failed_send_survives_new_worker_and_blocks_automatic_retry(source_sessions, live, monkeypatch, error):
    push = AsyncMock(side_effect=error)
    monkeypatch.setattr(LineClient, "push_text", push)
    first = await send_committed_snapshots(source_sessions, ["U_TEST"], clock=lambda: NOW)
    # New adapter/client invocation simulates next tick/process restart.
    second = await send_committed_snapshots(source_sessions, ["U_TEST"], clock=lambda: NOW)
    assert first[0].result.status == "error"
    assert second[0].result.decision.reasons == ("unresolved_or_replayed_send",)
    total, attempts = await counts(source_sessions)
    assert total == 1 and len(attempts) == 1 and attempts[0].status == "pending"
    push.assert_awaited_once()


@pg
@pytest.mark.asyncio
async def test_cancel_during_push_leaves_durable_guard(source_sessions, live, monkeypatch):
    entered = asyncio.Event()
    async def push(*args):
        entered.set()
        await asyncio.Future()
    mocked = AsyncMock(side_effect=push)
    monkeypatch.setattr(LineClient, "push_text", mocked)
    task = asyncio.create_task(send_committed_snapshots(source_sessions, ["U_TEST"], clock=lambda: NOW))
    await asyncio.wait_for(entered.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    resumed = await send_committed_snapshots(source_sessions, ["U_TEST"], clock=lambda: NOW)
    assert resumed[0].result.decision.reasons == ("unresolved_or_replayed_send",)
    mocked.assert_awaited_once()


@pg
@pytest.mark.asyncio
async def test_accepted_but_delivery_flush_failed_retains_pending_intent(source_sessions):
    sync = source_sessions.kw["bind"].sync_engine
    def fail(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT INTO NOTIFICATION_DELIVERIES"):
            raise RuntimeError("mock persistence failure")
    event.listen(sync, "before_cursor_execute", fail)
    client = AsyncMock()
    try:
        with pytest.raises(AcceptedDeliveryNotCommitted):
            await deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW,
                                          client=client, dry_run=False, durable_attempts=True)
    finally:
        event.remove(sync, "before_cursor_execute", fail)
    result = await deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW,
                                          client=client, dry_run=False, durable_attempts=True)
    assert result.decision.reasons == ("unresolved_or_replayed_send",)
    total, attempts = await counts(source_sessions)
    assert total == 1 and attempts[0].status == "pending"
    client.push_text.assert_awaited_once()


@pg
@pytest.mark.asyncio
async def test_unauthorized_recipient_never_pushes_or_reserves(source_sessions, live, monkeypatch):
    monkeypatch.setattr(settings, "INTRADAY_SEND_RECIPIENT_IDS", "U_OTHER")
    push = AsyncMock()
    monkeypatch.setattr(LineClient, "push_text", push)
    results = await send_committed_snapshots(source_sessions, ["U_TEST"], clock=lambda: NOW)
    assert results[0].result.decision.reasons == ("recipient_not_authorized",)
    assert await counts(source_sessions) == (1, [])
    push.assert_not_awaited()


@pg
@pytest.mark.asyncio
async def test_preview_with_durable_option_never_reserves(source_sessions):
    result = await deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW,
                                          durable_attempts=True)
    assert result.status == "preview"
    assert await counts(source_sessions) == (1, [])


@pg
@pytest.mark.asyncio
async def test_native_scheduler_routes_live_and_next_tick_does_not_send_again(source_sessions, live, monkeypatch):
    from app.notifications import scheduled_preview as scheduler
    monkeypatch.setattr(settings, "INTRADAY_PREVIEW_SCHEDULER_ENABLED", True)
    push = AsyncMock()
    monkeypatch.setattr(LineClient, "push_text", push)
    first = await scheduler.run_scheduled_preview_cycle(source_sessions, clock=lambda: NOW)
    second = await scheduler.run_scheduled_preview_cycle(source_sessions, clock=lambda: NOW)
    assert first.status == second.status == "complete"
    assert first.statuses == {"sent": 1} and second.statuses == {"suppress": 1}
    push.assert_awaited_once()


@pg
@pytest.mark.asyncio
async def test_intent_commit_failure_prevents_network_call(source_sessions):
    sync = source_sessions.kw["bind"].sync_engine
    def fail(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT INTO INTRADAY_SEND_ATTEMPTS"):
            raise RuntimeError("intent unavailable")
    event.listen(sync, "before_cursor_execute", fail)
    client = AsyncMock()
    try:
        with pytest.raises(RuntimeError):
            await deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW,
                                          client=client, dry_run=False, durable_attempts=True)
    finally:
        event.remove(sync, "before_cursor_execute", fail)
    assert await counts(source_sessions) == (1, [])
    client.push_text.assert_not_awaited()


@pg
@pytest.mark.asyncio
async def test_accepted_then_commit_failure_is_blocked_after_restart(source_sessions):
    sync = source_sessions.kw["bind"].sync_engine
    def mark(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT INTO NOTIFICATION_DELIVERIES"):
            conn.info["fail_delivery_commit"] = True
    def fail(conn):
        if conn.info.pop("fail_delivery_commit", False):
            raise RuntimeError("delivery commit unavailable")
    event.listen(sync, "before_cursor_execute", mark)
    event.listen(sync, "commit", fail)
    client = AsyncMock()
    try:
        with pytest.raises(AcceptedDeliveryNotCommitted):
            await deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW,
                                          client=client, dry_run=False, durable_attempts=True)
    finally:
        event.remove(sync, "commit", fail)
        event.remove(sync, "before_cursor_execute", mark)
    result = await deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW,
                                          client=client, dry_run=False, durable_attempts=True)
    assert result.decision.reasons == ("unresolved_or_replayed_send",)
    total, attempts = await counts(source_sessions)
    assert total == 1 and attempts[0].status == "pending"
    client.push_text.assert_awaited_once()


@pg
@pytest.mark.asyncio
async def test_pending_scope_blocks_new_forecast_event(source_sessions):
    from dataclasses import replace
    from app.models import ForecastRun, HourlyForecast
    client = AsyncMock()
    client.push_text.side_effect = TimeoutError()
    with pytest.raises(SendOutcomeUnknown):
        await deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW,
                                      client=client, dry_run=False, durable_attempts=True)
    new = replace(candidate(95), source_id=13)
    async with source_sessions() as db:
        db.add(ForecastRun(id=13, location_id=101, provider="open_meteo", retrieved_at=new.retrieved_at))
        await db.flush()
        db.add_all(HourlyForecast(forecast_run_id=13, valid_time=h.end,
                                 precipitation_probability=h.probability, precipitation=h.rainfall_mm)
                   for h in new.hours)
        await db.commit()
    result = await deliver_intraday_update(source_sessions, new, clock=lambda: NOW,
                                          client=client, dry_run=False, durable_attempts=True)
    assert result.decision.reasons == ("unresolved_or_replayed_send",)
    client.push_text.assert_awaited_once()


@pg
@pytest.mark.asyncio
async def test_concurrent_live_workers_commit_one_intent_and_push_once(source_sessions):
    entered, release = asyncio.Event(), asyncio.Event()
    async def push(*args):
        entered.set()
        await release.wait()
    client = AsyncMock()
    client.push_text.side_effect = push
    async def send():
        return await deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW,
                                             client=client, dry_run=False, durable_attempts=True)
    first = asyncio.create_task(send())
    second = None
    try:
        await asyncio.wait_for(entered.wait(), 5)
        second = asyncio.create_task(send())
        from tests.test_rain_locking_postgres import wait_for_database_lock
        await wait_for_database_lock(source_sessions)
        release.set()
        results = await asyncio.gather(first, second)
        assert [x.status for x in results] == ["sent", "suppress"]
        assert len((await counts(source_sessions))[1]) == 1
        client.push_text.assert_awaited_once()
    finally:
        release.set()
        for task in (first, second):
            if task is not None and not task.done():
                task.cancel()
        await asyncio.gather(*(x for x in (first, second) if x is not None), return_exceptions=True)
