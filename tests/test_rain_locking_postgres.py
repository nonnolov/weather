"""Opt-in real PostgreSQL tests, disposable localhost instance/schema only."""
import asyncio
import copy
from dataclasses import replace
from datetime import timedelta
import os
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import Base
from app.models.forecast import ForecastRun
from app.models.location import Location
from app.models.notification import NotificationDelivery
from app.models.user import User
from app.notifications.intraday_baseline import evaluate_intraday_from_db
from app.notifications.rain_alerts import send_rain_alert
from app.notifications.rain_locking import (
    evaluate_intraday_locked, locked_intraday_evaluation,
    lock_rain_scope, rain_scope_lock_key,
)
from tests.test_intraday_baseline import NOW, H, SCOPE, candidate, delivery, payload
from tests.test_rain_delivery_evidence import make_run

PG_URL = os.environ.get("P104_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="Explicit local P104_TEST_POSTGRES_URL required")


@pytest_asyncio.fixture
async def pg_sessions():
    if not PG_URL:
        pytest.skip("Explicit local P104_TEST_POSTGRES_URL required")
    url = make_url(PG_URL)
    # Dedicated test instance only; never borrow the user's normal local server.
    assert url.drivername == "postgresql+asyncpg"
    assert url.host == "127.0.0.1" and url.port == 55434 and not url.query
    assert url.username == "p104_test" and url.database == "postgres"
    schema = "weather_p104_test_" + uuid4().hex
    admin = create_async_engine(url, poolclass=NullPool)
    created = False
    engine = None
    try:
        async with admin.begin() as conn:
            assert 160000 <= int(await conn.scalar(text("SHOW server_version_num"))) < 170000
            assert await conn.scalar(text("SELECT current_user")) == "p104_test"
            await conn.execute(text('CREATE SCHEMA "' + schema + '"'))
            created = True
        engine = create_async_engine(
            url, poolclass=NullPool, isolation_level="READ COMMITTED",
            connect_args={"server_settings": {"search_path": schema, "application_name": schema}},
        )
        async with engine.begin() as conn:
            assert await conn.scalar(text("SHOW search_path")) == schema
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        async with factory() as db:
            db.add_all([
                Location(id=101, name="test", slug="p104", latitude=0, longitude=0,
                         timezone="Asia/Bangkok"),
                Location(id=102, name="other", slug="p104-other", latitude=1, longitude=1,
                         timezone="Asia/Bangkok"),
                User(external_id="U_TEST", current_location_id=101),
            ])
            await db.flush()
            db.add(delivery())
            await db.commit()
        yield factory
    finally:
        if engine is not None:
            await engine.dispose()
        if created:
            async with admin.begin() as conn:
                await conn.execute(text('DROP SCHEMA "' + schema + '" CASCADE'))
        await admin.dispose()


async def wait_for_database_lock(sessions, kind="advisory"):
    """Prove the worker is blocked in PostgreSQL, not with an arbitrary sleep."""
    async def observe():
        while True:
            async with sessions() as db:
                count = await db.scalar(text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE application_name=current_setting('application_name') "
                    "AND wait_event_type='Lock' AND wait_event=:kind"
                ), {"kind": kind})
            if count:
                return
            await asyncio.sleep(0.01)
    await asyncio.wait_for(observe(), 8)


@pytest.mark.asyncio
async def test_locked_preview_does_not_write_or_call_line(pg_sessions, monkeypatch):
    from app.notifications.line_client import LineClient
    async def forbidden(*args, **kwargs):
        raise AssertionError("LINE must not be called")
    monkeypatch.setattr(LineClient, "push_text", forbidden)
    before = await evaluate_intraday_from_db(pg_sessions, candidate(), now=NOW)
    result = await evaluate_intraday_locked(pg_sessions, candidate(), clock=lambda: NOW)
    assert result == before and result.outcome == "notify"
    async with pg_sessions() as db:
        assert await db.scalar(select(func.count()).select_from(NotificationDelivery)) == 1
        assert (await db.scalar(select(NotificationDelivery.rain_evidence))) == payload()


@pytest.mark.asyncio
@pytest.mark.parametrize("other_recipient,other_location", [("U_OTHER", 101), ("U_TEST", 102)])
async def test_lock_is_scoped_by_recipient_and_location(pg_sessions, other_recipient, other_location):
    async with pg_sessions() as first, pg_sessions() as second:
        await lock_rain_scope(first, "U_TEST", 101)
        acquired = await second.scalar(select(func.pg_try_advisory_xact_lock(
            rain_scope_lock_key(other_recipient, other_location))))
        assert acquired is True


@pytest.mark.asyncio
@pytest.mark.parametrize("change,reason", [
    ("location", "location_changed"), ("timezone", "scope_mismatch"),
    ("null_baseline", "unknown_baseline"), ("cooldown", "cooldown"),
    ("same_content", "identical_content"),
])
async def test_waiting_worker_rereads_committed_state(pg_sessions, change, reason):
    async with pg_sessions() as blocker:
        await lock_rain_scope(blocker, "U_TEST", 101)
        task = asyncio.create_task(evaluate_intraday_locked(pg_sessions, candidate(), clock=lambda: NOW))
        try:
            await wait_for_database_lock(pg_sessions)
            if change == "location":
                await blocker.execute(update(User).values(current_location_id=102))
            elif change == "timezone":
                await blocker.execute(update(Location).where(Location.id == 101).values(timezone="UTC"))
            else:
                data = payload()
                if change == "null_baseline":
                    data = None
                elif change == "cooldown":
                    data["source"]["retrieved_at"] = (NOW - H).isoformat()
                elif change == "same_content":
                    data["source"]["forecast_run_id"] = 12
                    data["source"]["retrieved_at"] = candidate().retrieved_at.isoformat()
                    for row in data["hourly_intervals"]:
                        row["precipitation_probability"] = 70
                blocker.add(delivery("rain-intraday:v1:101:latest",
                                     rain_evidence=data, created_at=NOW - H))
            await blocker.commit()
            result = await asyncio.wait_for(task, 8)
            assert result.reasons == (reason,)
            assert result.outcome != "notify"
        finally:
            await blocker.rollback()
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_clock_and_freshness_are_checked_after_waiting(pg_sessions):
    samples = []
    def clock():
        samples.append(True)
        return NOW + 2 * H
    async with pg_sessions() as blocker:
        await lock_rain_scope(blocker, "U_TEST", 101)
        task = asyncio.create_task(evaluate_intraday_locked(pg_sessions, candidate(), clock=clock))
        try:
            await wait_for_database_lock(pg_sessions)
            assert samples == []
            await blocker.commit()
            result = await asyncio.wait_for(task, 8)
            assert samples == [True] and result.reasons == ("stale_candidate",)
        finally:
            await blocker.rollback()
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_duplicate_committed_event_is_suppressed(pg_sessions):
    preview = await evaluate_intraday_from_db(pg_sessions, candidate(), now=NOW)
    async with pg_sessions() as db:
        db.add(delivery("rain-intraday:v1:101:" + preview.event_id, created_at=NOW - 5 * H))
        await db.commit()
    result = await evaluate_intraday_locked(pg_sessions, candidate(), clock=lambda: NOW)
    assert result.outcome == "suppress" and result.reasons == ("event_already_delivered",)
    assert result.event_id is None


@pytest.mark.asyncio
async def test_exception_rolls_back_mock_acceptance_and_releases_lock(pg_sessions):
    with pytest.raises(RuntimeError, match="mock failure"):
        async with locked_intraday_evaluation(pg_sessions, candidate(), clock=lambda: NOW) as evaluation:
            assert evaluation.decision.outcome == "notify"
            evaluation.session.add(delivery("rain-intraday:v1:101:failed", created_at=NOW))
            await evaluation.session.flush()
            raise RuntimeError("mock failure")
    async with pg_sessions() as db:
        assert await db.scalar(select(func.count()).select_from(NotificationDelivery)) == 1
    assert (await evaluate_intraday_locked(pg_sessions, candidate(), clock=lambda: NOW)).outcome == "notify"


@pytest.mark.asyncio
async def test_concurrent_mock_accepted_delivery_advances_baseline_once(pg_sessions):
    entered = asyncio.Event()
    release = asyncio.Event()
    outcomes = []
    async def first():
        async with locked_intraday_evaluation(pg_sessions, candidate(), clock=lambda: NOW) as evaluation:
            outcomes.append(evaluation.decision.outcome)
            data = payload()
            data["source"]["forecast_run_id"] = 12
            data["source"]["retrieved_at"] = candidate().retrieved_at.isoformat()
            for row in data["hourly_intervals"]:
                row["precipitation_probability"] = 70
            # Synthetic acceptance only. No provider, sender or LINE is used.
            evaluation.session.add(delivery("rain-intraday:v1:101:" + evaluation.decision.event_id,
                                            rain_evidence=data, created_at=NOW))
            await evaluation.session.flush()
            entered.set()
            await release.wait()
    task1 = asyncio.create_task(first())
    task2 = None
    try:
        await asyncio.wait_for(entered.wait(), 8)
        task2 = asyncio.create_task(evaluate_intraday_locked(pg_sessions, candidate(), clock=lambda: NOW))
        await wait_for_database_lock(pg_sessions)
        release.set()
        await asyncio.wait_for(task1, 8)
        outcomes.append((await asyncio.wait_for(task2, 8)).outcome)
        assert outcomes == ["notify", "suppress"]
        async with pg_sessions() as db:
            assert await db.scalar(select(func.count()).select_from(NotificationDelivery)) == 2
    finally:
        release.set()
        tasks = [task for task in (task1, task2) if task is not None]
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_user_reassignment_update_waits_for_locked_context(pg_sessions):
    task = None
    async def move():
        async with pg_sessions() as db:
            await db.execute(update(User).where(User.external_id == "U_TEST").values(current_location_id=102))
            await db.commit()
    try:
        async with locked_intraday_evaluation(pg_sessions, candidate(), clock=lambda: NOW) as evaluation:
            assert evaluation.decision.outcome == "notify"
            task = asyncio.create_task(move())
            await wait_for_database_lock(pg_sessions, "transactionid")
            assert not task.done()
        await asyncio.wait_for(task, 8)
        assert (await evaluate_intraday_locked(pg_sessions, candidate(), clock=lambda: NOW)).reasons == ("location_changed",)
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_timezone_update_waits_for_locked_context(pg_sessions):
    task = None
    async def change_zone():
        async with pg_sessions() as db:
            await db.execute(update(Location).where(Location.id == 101).values(timezone="UTC"))
            await db.commit()
    try:
        async with locked_intraday_evaluation(pg_sessions, candidate(), clock=lambda: NOW):
            task = asyncio.create_task(change_zone())
            await wait_for_database_lock(pg_sessions, "transactionid")
            assert not task.done()
        await asyncio.wait_for(task, 8)
        assert (await evaluate_intraday_locked(pg_sessions, candidate(), clock=lambda: NOW)).reasons == ("scope_mismatch",)
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_daily_send_uses_same_lock_before_mock_push(pg_sessions):
    async with pg_sessions() as db:
        run, _ = await make_run(db, 80)
        run_id, location_id = run.id, run.location_id
        await db.commit()
    client = AsyncMock()
    async def daily():
        async with pg_sessions() as db:
            async with db.begin():
                run = await db.get(ForecastRun, run_id)
                return await send_rain_alert(db, run, "U_TEST", client)
    async with pg_sessions() as blocker:
        await lock_rain_scope(blocker, "U_TEST", location_id)
        task = asyncio.create_task(daily())
        try:
            await wait_for_database_lock(pg_sessions)
            client.push_text.assert_not_awaited()
            await blocker.commit()
            assert await asyncio.wait_for(task, 8)
            client.push_text.assert_awaited_once()
        finally:
            await blocker.rollback()
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_lock_timeout_fails_without_notify_and_retry_can_acquire(pg_sessions):
    async with pg_sessions() as blocker:
        await lock_rain_scope(blocker, "U_TEST", 101)
        with pytest.raises(DBAPIError) as error:
            await evaluate_intraday_locked(pg_sessions, candidate(), clock=lambda: NOW, lock_timeout_ms=50)
        assert getattr(error.value.orig, "sqlstate", None) == "55P03"
        await blocker.rollback()
    assert (await evaluate_intraday_locked(pg_sessions, candidate(), clock=lambda: NOW)).outcome == "notify"


@pytest.mark.asyncio
@pytest.mark.parametrize("level", ["REPEATABLE READ", "SERIALIZABLE"])
async def test_snapshot_isolation_cannot_authorize_post_lock_read(pg_sessions, level):
    engine = pg_sessions.kw["bind"].execution_options(isolation_level=level)
    with pytest.raises(ValueError, match="READ COMMITTED"):
        await evaluate_intraday_locked(async_sessionmaker(engine), candidate(), clock=lambda: NOW)


@pytest.mark.asyncio
async def test_sqlite_cannot_claim_postgres_locking():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        with pytest.raises(ValueError, match="requires PostgreSQL"):
            await evaluate_intraday_locked(async_sessionmaker(engine), candidate(), clock=lambda: NOW)
    finally:
        await engine.dispose()


@pytest.mark.parametrize("recipient,location", [("", 1), ("U_TEST", 0), ("U_TEST", True)])
def test_invalid_lock_scope_is_rejected(recipient, location):
    with pytest.raises(ValueError):
        rain_scope_lock_key(recipient, location)


def test_lock_identity_is_stable_and_unambiguous():
    assert rain_scope_lock_key("U_TEST", 101) == rain_scope_lock_key("U_TEST", 101)
    assert rain_scope_lock_key("U_TEST", 101) != rain_scope_lock_key("U_OTHER", 101)
    assert rain_scope_lock_key("U_TEST", 101) != rain_scope_lock_key("U_TEST", 102)
    assert -(2**63) <= rain_scope_lock_key("U_TEST", 101) < 2**63
