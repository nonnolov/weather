"""PostgreSQL serialization and migration checks; mock LINE only."""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import os
import pytest
from sqlalchemy import select
from app.core.config import settings
from app.models import User
from app.models.line_subscription import LineSubscription
from app.notifications.subscriptions import CONSENT_VERSION, recipient_eligible
from app.api.v1.line_onboarding import locked_user, subscription, apply_friend_events
from app.notifications.rain_locking import evaluate_intraday_locked
from tests.test_intraday_baseline import candidate, NOW
from tests.test_rain_locking_postgres import pg_sessions, wait_for_database_lock
pytestmark=pytest.mark.skipif(not os.environ.get("P104_TEST_POSTGRES_URL"),reason="Explicit disposable PostgreSQL required")

async def seed(sessions):
    async with sessions() as db:
        db.add(LineSubscription(user_id="U_TEST",friend=True,enabled=True,verified_location_id=101,consent_version=CONSENT_VERSION,consented_at=datetime.fromtimestamp(0.001,timezone.utc),updated_at=datetime.now(timezone.utc),friend_event_time=0))
        await db.commit()

@pytest.mark.asyncio
async def test_disable_waiting_on_sender_lock_prevents_next_send(pg_sessions,monkeypatch):
    monkeypatch.setattr(settings,"LINE_SUBSCRIPTIONS_ENABLED",True)
    await seed(pg_sessions)
    async def disable():
        async with pg_sessions() as db:
            await locked_user(db,"U_TEST")
            record=await subscription(db,"U_TEST")
            record.enabled=False
            await db.commit()
    async with pg_sessions() as sender:
        assert await recipient_eligible(sender,"U_TEST",lock=True)
        task=asyncio.create_task(disable())
        try:
            await wait_for_database_lock(pg_sessions,"transactionid")
            assert not task.done()
            await sender.commit()
            await asyncio.wait_for(task,8)
        finally:
            if not task.done():task.cancel();await asyncio.gather(task,return_exceptions=True)
    async with pg_sessions() as db:
        assert not await recipient_eligible(db,"U_TEST",lock=True)
    decision=await evaluate_intraday_locked(pg_sessions,candidate(),clock=lambda:NOW)
    assert decision.reasons==("subscription_not_ready",)

@pytest.mark.asyncio
async def test_waiting_sender_reads_committed_optout(pg_sessions,monkeypatch):
    monkeypatch.setattr(settings,"LINE_SUBSCRIPTIONS_ENABLED",True)
    await seed(pg_sessions)
    async def eligible():
        async with pg_sessions() as db:
            return await recipient_eligible(db,"U_TEST",lock=True)
    async with pg_sessions() as blocker:
        await locked_user(blocker,"U_TEST")
        task=asyncio.create_task(eligible())
        try:
            await wait_for_database_lock(pg_sessions,"transactionid")
            record=await subscription(blocker,"U_TEST");record.enabled=False
            await blocker.commit()
            assert await asyncio.wait_for(task,8) is False
        finally:
            if not task.done():task.cancel();await asyncio.gather(task,return_exceptions=True)

@pytest.mark.asyncio
async def test_concurrent_first_signup_creates_one_record(pg_sessions,monkeypatch):
    monkeypatch.setattr(settings,"LINE_SUBSCRIPTIONS_ENABLED",True)
    async def create():
        async with pg_sessions() as db:
            await locked_user(db,"U"+"b"*32)
            await subscription(db,"U"+"b"*32,create=True)
            await db.commit()
    await asyncio.gather(create(),create())
    async with pg_sessions() as db:
        assert len(list((await db.scalars(select(LineSubscription).where(LineSubscription.user_id=="U"+"b"*32))).all()))==1

@pytest.mark.asyncio
async def test_block_then_unblock_does_not_restore_consent(pg_sessions,monkeypatch):
    monkeypatch.setattr(settings,"LINE_SUBSCRIPTIONS_ENABLED",True)
    await seed(pg_sessions)
    async with pg_sessions() as db:
        await apply_friend_events(db,[{"type":"unfollow","timestamp":10,"source":{"type":"user","userId":"U_TEST"}}])
        await db.commit()
    async with pg_sessions() as db:
        await apply_friend_events(db,[{"type":"follow","timestamp":20,"source":{"type":"user","userId":"U_TEST"}}])
        await db.commit()
    async with pg_sessions() as db:
        record=await db.get(LineSubscription,"U_TEST")
        assert record.friend and not record.enabled
        assert not await recipient_eligible(db,"U_TEST")

@pytest.mark.asyncio
async def test_active_subscription_reaches_locked_policy(pg_sessions,monkeypatch):
    monkeypatch.setattr(settings,"LINE_SUBSCRIPTIONS_ENABLED",True)
    await seed(pg_sessions)
    decision=await evaluate_intraday_locked(pg_sessions,candidate(),clock=lambda:NOW)
    assert decision.outcome=="notify"

@pytest.mark.asyncio
async def test_daily_source_area_is_rechecked_after_location_change(pg_sessions,monkeypatch):
    from types import SimpleNamespace
    from app.notifications.rain_alerts import send_rain_alert
    monkeypatch.setattr(settings,"LINE_SUBSCRIPTIONS_ENABLED",True)
    await seed(pg_sessions)
    client=AsyncMock()
    async with pg_sessions() as db:
        assert not await recipient_eligible(db,"U_TEST",expected_location_id=102,lock=True)
        assert not await send_rain_alert(db,SimpleNamespace(location_id=102),"U_TEST",client)
        client.push_text.assert_not_awaited()

@pytest.mark.asyncio
async def test_subscription_migration_round_trip_and_safe_defaults(pg_sessions):
    import importlib.util
    from pathlib import Path
    from alembic.operations import Operations
    from alembic.migration import MigrationContext
    from sqlalchemy import inspect, text
    file=Path(__file__).parents[1]/"alembic/versions/0010_line_subscriptions.py"
    spec=importlib.util.spec_from_file_location("line_subscription_migration",file)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    def check(connection):
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
            assert not inspect(connection).has_table("line_subscriptions")
            migration.upgrade()
            connection.execute(text("INSERT INTO line_subscriptions (user_id, updated_at) VALUES ('U_TEST', now())"))
            row=connection.execute(text("SELECT enabled, friend, friend_event_time FROM line_subscriptions WHERE user_id='U_TEST'")).one()
            assert row==(False,False,0)
            migration.downgrade()
            assert not inspect(connection).has_table("line_subscriptions")
            migration.upgrade()
    async with pg_sessions.kw["bind"].begin() as connection:
        await connection.run_sync(check)

@pytest.mark.asyncio
async def test_live_adapter_uses_consent_and_rereads_optout(pg_sessions,monkeypatch):
    from app.notifications.intraday_live import send_committed_snapshots
    from app.notifications.intraday_delivery import IntradayDeliveryResult
    from app.notifications.intraday_comparison import Decision
    monkeypatch.setattr(settings,"LINE_SUBSCRIPTIONS_ENABLED",True)
    monkeypatch.setattr(settings,"INTRADAY_SEND_ENABLED",True)
    monkeypatch.setattr(settings,"LINE_CHANNEL_ACCESS_TOKEN","mock-channel-token")
    monkeypatch.setattr(settings,"INTRADAY_SEND_RECIPIENT_IDS","")
    await seed(pg_sessions)
    accepted=IntradayDeliveryResult("accepted",Decision("notify",("mock_acceptance",)))
    sender=AsyncMock(return_value=accepted)
    with patch("app.notifications.intraday_live.read_committed_candidate",AsyncMock(return_value=candidate())),patch("app.notifications.intraday_live.deliver_intraday_update",sender):
        result=await send_committed_snapshots(pg_sessions,["U_TEST"],clock=lambda:NOW)
        assert result[0].result.status=="accepted"
        assert sender.await_count==1
        async with pg_sessions() as db:
            await locked_user(db,"U_TEST")
            record=await subscription(db,"U_TEST");record.enabled=False
            await db.commit()
        result=await send_committed_snapshots(pg_sessions,["U_TEST"],clock=lambda:NOW)
        assert result[0].result.decision.reasons==("recipient_not_authorized",)
        assert sender.await_count==1

@pytest.mark.asyncio
async def test_legacy_allowlist_cannot_bypass_new_optin_policy(pg_sessions,monkeypatch):
    from app.notifications.intraday_live import send_committed_snapshots
    monkeypatch.setattr(settings,"LINE_SUBSCRIPTIONS_ENABLED",True)
    monkeypatch.setattr(settings,"INTRADAY_SEND_ENABLED",True)
    monkeypatch.setattr(settings,"LINE_CHANNEL_ACCESS_TOKEN","mock-channel-token")
    monkeypatch.setattr(settings,"INTRADAY_SEND_RECIPIENT_IDS","U_TEST")
    with patch("app.notifications.intraday_live.deliver_intraday_update",AsyncMock()) as sender:
        result=await send_committed_snapshots(pg_sessions,["U_TEST"],clock=lambda:NOW)
    assert result[0].result.decision.reasons==("recipient_not_authorized",)
    sender.assert_not_awaited()
