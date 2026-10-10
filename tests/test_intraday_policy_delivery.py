"""Versioned policy through real localhost PostgreSQL delivery; mock LINE only."""
import asyncio
from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select, update

from app.models import IntradaySendAttempt, NotificationDelivery
from app.models.forecast import HourlyForecast
from app.notifications.intraday_baseline import read_latest_rain_baseline
from app.notifications.intraday_candidate_policy import CANDIDATE_POLICY_VERSION as V2
from app.notifications.intraday_comparison import Baseline, POLICY_VERSION
from app.notifications.intraday_delivery import deliver_intraday_update, SendOutcomeUnknown
from tests.test_intraday_baseline import NOW, H, SCOPE, candidate, payload
from tests.test_intraday_delivery import source_sessions
from tests.test_rain_locking_postgres import PG_URL, pg_sessions, wait_for_database_lock

pg = pytest.mark.skipif(not PG_URL, reason="Dedicated localhost PostgreSQL required")


async def prepare(factory, index=0, *, old_p=65, new_p=75, old_mm=0, new_mm=0, age=H):
    rows=tuple(replace(h,probability=new_p if i==index else old_p,
                       rainfall_mm=new_mm if i==index else old_mm)
               for i,h in enumerate(candidate().hours))
    new=replace(candidate(),hours=rows)
    async with factory() as db:
        frozen=payload()
        for row in frozen["hourly_intervals"]:
            row["precipitation_probability"]=old_p
            row["precipitation_mm"]=old_mm
        await db.execute(update(NotificationDelivery).values(
            created_at=NOW-age,rain_evidence=frozen))
        for hour in new.hours:
            await db.execute(update(HourlyForecast).where(HourlyForecast.valid_time==hour.end).values(
                precipitation_probability=hour.probability,precipitation=hour.rainfall_mm))
        await db.commit()
    return new


async def counts(factory):
    async with factory() as db:
        return (await db.scalar(select(func.count()).select_from(NotificationDelivery)),
                await db.scalar(select(func.count()).select_from(IntradaySendAttempt)))


@pg
@pytest.mark.asyncio
async def test_urgent_preview_uses_locked_path_without_line_or_writes(source_sessions):
    new=await prepare(source_sessions)
    client=AsyncMock()
    original=await deliver_intraday_update(source_sessions,new,clock=lambda:NOW,client=client)
    revised=await deliver_intraday_update(source_sessions,new,clock=lambda:NOW,client=client,policy_version=V2)
    assert original.status=="suppress"
    assert revised.status=="preview" and revised.decision.outcome=="notify"
    assert revised.message and await counts(source_sessions)==(1,0)
    client.push_text.assert_not_awaited()


@pg
@pytest.mark.asyncio
@pytest.mark.parametrize("index,expected",[(2,"preview"),(3,"suppress")])
async def test_imminent_boundary_in_delivery(source_sessions,index,expected):
    new=await prepare(source_sessions,index)
    result=await deliver_intraday_update(source_sessions,new,clock=lambda:NOW,policy_version=V2)
    assert result.status==expected


@pg
@pytest.mark.asyncio
async def test_probability_only_escalation_remains_in_cooldown(source_sessions):
    new=await prepare(source_sessions,old_p=70,new_p=90)
    result=await deliver_intraday_update(source_sessions,new,clock=lambda:NOW,policy_version=V2)
    assert result.decision.reasons==("cooldown",)
    assert await counts(source_sessions)==(1,0)


@pg
@pytest.mark.asyncio
async def test_mock_send_versions_evidence_and_replay_across_policies(source_sessions):
    new=await prepare(source_sessions)
    client=AsyncMock()
    sent=await deliver_intraday_update(source_sessions,new,clock=lambda:NOW,client=client,
                                      dry_run=False,durable_attempts=True,policy_version=V2)
    assert sent.status=="sent"
    async with source_sessions() as db:
        saved=await db.get(NotificationDelivery,sent.delivery_id)
        assert saved.dedupe_key.startswith("rain-intraday:v2:101:")
        assert saved.rain_evidence["comparison"]["policy_version"]==V2
        baseline=await read_latest_rain_baseline(db,SCOPE)
        assert isinstance(baseline,Baseline) and baseline.delivery_id==saved.id
        attempt=(await db.scalars(select(IntradaySendAttempt))).one()
        assert attempt.status=="accepted" and attempt.delivery_id==saved.id
    for policy in [POLICY_VERSION,V2]:
        replay=await deliver_intraday_update(source_sessions,new,clock=lambda:NOW,client=client,
                                             dry_run=False,durable_attempts=True,policy_version=policy)
        assert replay.decision.reasons==("identical_content",)
    client.push_text.assert_awaited_once()
    assert await counts(source_sessions)==(2,1)


@pg
@pytest.mark.asyncio
async def test_pending_uncertain_send_blocks_policy_switch(source_sessions):
    new=await prepare(source_sessions,old_p=10,new_p=75,age=4*H)
    client=AsyncMock()
    client.push_text.side_effect=TimeoutError()
    with pytest.raises(SendOutcomeUnknown):
        await deliver_intraday_update(source_sessions,new,clock=lambda:NOW,client=client,
                                       dry_run=False,durable_attempts=True,policy_version=V2)
    for policy in [POLICY_VERSION,V2]:
        result=await deliver_intraday_update(source_sessions,new,clock=lambda:NOW,
                                             client=client,dry_run=False,durable_attempts=True,
                                             policy_version=policy)
        assert result.status=="skip"
        assert result.decision.reasons==("unresolved_or_replayed_send",)
    assert await counts(source_sessions)==(1,1)
    client.push_text.assert_awaited_once()


@pg
@pytest.mark.asyncio
async def test_two_concurrent_v2_workers_mock_send_once(source_sessions):
    new=await prepare(source_sessions)
    entered,release=asyncio.Event(),asyncio.Event()
    client=AsyncMock()
    async def push(*args):
        entered.set()
        await release.wait()
    client.push_text.side_effect=push
    first=asyncio.create_task(deliver_intraday_update(source_sessions,new,clock=lambda:NOW,
                client=client,dry_run=False,durable_attempts=True,policy_version=V2))
    second=None
    try:
        await asyncio.wait_for(entered.wait(),8)
        second=asyncio.create_task(deliver_intraday_update(source_sessions,new,clock=lambda:NOW,
                    client=client,dry_run=False,durable_attempts=True,policy_version=V2))
        await wait_for_database_lock(source_sessions)
        release.set()
        a,b=await asyncio.gather(first,second)
        assert a.status=="sent" and b.status=="suppress"
        assert await counts(source_sessions)==(2,1)
        client.push_text.assert_awaited_once()
    finally:
        release.set()
        for task in [first,second]:
            if task is not None and not task.done(): task.cancel()
        await asyncio.gather(*(t for t in [first,second] if t is not None),return_exceptions=True)


@pg
@pytest.mark.asyncio
async def test_unknown_policy_fails_before_any_send_or_write(source_sessions):
    with pytest.raises(ValueError,match="Unsupported"):
        await deliver_intraday_update(source_sessions,candidate(),clock=lambda:NOW,
                                       client=AsyncMock(),dry_run=False,policy_version="unknown")
    assert await counts(source_sessions)==(1,0)

@pg
@pytest.mark.asyncio
async def test_v2_history_remains_valid_for_a_followup_event(source_sessions):
    from app.models.forecast import ForecastRun
    first=await prepare(source_sessions)
    client=AsyncMock()
    accepted=await deliver_intraday_update(source_sessions,first,clock=lambda:NOW,client=client,
                      dry_run=False,durable_attempts=True,policy_version=V2)
    assert accepted.status=="sent"
    second=replace(first,source_id=13,retrieved_at=NOW+timedelta(minutes=5),
                   hours=tuple(replace(h,probability=95) if i==1 else h for i,h in enumerate(first.hours)))
    async with source_sessions() as db:
        db.add(ForecastRun(id=13,location_id=101,provider="open_meteo",retrieved_at=second.retrieved_at))
        await db.flush()
        db.add_all(HourlyForecast(forecast_run_id=13,valid_time=h.end,
                                  precipitation_probability=h.probability,precipitation=h.rainfall_mm)
                   for h in second.hours)
        await db.commit()
    result=await deliver_intraday_update(source_sessions,second,clock=lambda:NOW+timedelta(minutes=15),
                         client=client,dry_run=False,durable_attempts=True,policy_version=V2)
    assert result.status=="sent" and await counts(source_sessions)==(3,2)
    assert client.push_text.await_count==2


@pg
@pytest.mark.asyncio
async def test_newest_unknown_v2_evidence_never_falls_back_to_daily(source_sessions):
    async with source_sessions() as db:
        db.add(NotificationDelivery(location_id=101,channel="line",recipient_id="U_TEST",
                   dedupe_key="rain-intraday:v2:101:"+"a"*64,created_at=NOW-H,rain_evidence=None))
        await db.commit()
    client=AsyncMock()
    result=await deliver_intraday_update(source_sessions,candidate(),clock=lambda:NOW,
                         client=client,dry_run=False,policy_version=V2)
    assert result.decision.reasons==("unknown_baseline",)
    client.push_text.assert_not_awaited()


@pg
@pytest.mark.asyncio
async def test_v2_still_rejects_candidate_not_matching_committed_source(source_sessions):
    new=await prepare(source_sessions)
    new=replace(new,hours=tuple(replace(h,probability=76) if i==0 else h for i,h in enumerate(new.hours)))
    client=AsyncMock()
    result=await deliver_intraday_update(source_sessions,new,clock=lambda:NOW,
                         client=client,dry_run=False,policy_version=V2)
    assert result.decision.reasons==("candidate_source_mismatch",)
    client.push_text.assert_not_awaited()


def test_policy_setting_defaults_to_v1():
    from app.core.config import Settings
    assert Settings(_env_file=None).INTRADAY_POLICY_VERSION==POLICY_VERSION


def test_policy_setting_rejects_unknown_value():
    from app.core.config import Settings
    with pytest.raises(ValueError):
        Settings(_env_file=None,INTRADAY_POLICY_VERSION="unknown")


def configure_live(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings,"INTRADAY_POLICY_VERSION",V2)
    monkeypatch.setattr(settings,"INTRADAY_SEND_ENABLED",True)
    monkeypatch.setattr(settings,"INTRADAY_SEND_RECIPIENT_IDS","U_TEST")
    monkeypatch.setattr(settings,"LINE_CHANNEL_ACCESS_TOKEN","mock-token")


@pg
@pytest.mark.asyncio
async def test_configured_preview_and_live_adapter_share_policy(source_sessions,monkeypatch):
    from app.notifications.intraday_preview import preview_committed_snapshots
    from app.notifications.intraday_live import send_committed_snapshots
    from app.notifications.line_client import LineClient
    await prepare(source_sessions)
    configure_live(monkeypatch)
    push=AsyncMock()
    monkeypatch.setattr(LineClient,"push_text",push)
    previews=await preview_committed_snapshots(source_sessions,["U_TEST"],clock=lambda:NOW)
    assert previews[0].result.status=="preview"
    assert await counts(source_sessions)==(1,0)
    push.assert_not_awaited()
    live=await send_committed_snapshots(source_sessions,["U_TEST"],clock=lambda:NOW)
    assert live[0].result.status=="sent"
    assert live[0].result.decision.event_id==previews[0].result.decision.event_id
    assert await counts(source_sessions)==(2,1)
    push.assert_awaited_once()


@pg
@pytest.mark.asyncio
async def test_live_adapter_policy_switch_retains_uncertain_send_guard(source_sessions,monkeypatch):
    from app.core.config import settings
    from app.notifications.intraday_live import send_committed_snapshots
    from app.notifications.line_client import LineClient
    await prepare(source_sessions,old_p=10,new_p=75,age=4*H)
    configure_live(monkeypatch)
    push=AsyncMock(side_effect=TimeoutError())
    monkeypatch.setattr(LineClient,"push_text",push)
    first=await send_committed_snapshots(source_sessions,["U_TEST"],clock=lambda:NOW)
    assert first[0].result.status=="error"
    monkeypatch.setattr(settings,"INTRADAY_POLICY_VERSION",POLICY_VERSION)
    second=await send_committed_snapshots(source_sessions,["U_TEST"],clock=lambda:NOW)
    assert second[0].result.decision.reasons==("unresolved_or_replayed_send",)
    assert await counts(source_sessions)==(1,1)
    push.assert_awaited_once()
