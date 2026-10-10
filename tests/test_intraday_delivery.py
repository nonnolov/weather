"""Pure formatting and real PostgreSQL delivery with mock LINE only."""
import asyncio
import copy
from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, event, func, select, update

from app.models.forecast import ForecastRun, HourlyForecast
from app.models.notification import NotificationDelivery
from app.notifications.intraday_baseline import evaluate_intraday_from_db
from app.notifications.intraday_comparison import Baseline, Hour, compare_intraday
from app.notifications.intraday_delivery import (
    AcceptedDeliveryNotCommitted, SendOutcomeUnknown, deliver_intraday_update,
)
from app.notifications.intraday_formatter import format_intraday_alert, freeze_intraday_evidence
from app.notifications.line_client import LineApiError
from tests.test_intraday_baseline import NOW, H, candidate, delivery, payload
from tests.test_rain_locking_postgres import PG_URL, pg_sessions, wait_for_database_lock

pg = pytest.mark.skipif(not PG_URL, reason="Explicit dedicated localhost PostgreSQL URL required")


def old_evidence():
    new = candidate()
    return replace(new, source_id=11, retrieved_at=NOW - 4 * H,
                   hours=tuple(replace(hour, probability=10) for hour in new.hours))


def decision_for(new):
    return compare_intraday(Baseline(1, NOW - 4 * H, old_evidence()), new, now=NOW)


@pytest.mark.parametrize("probability", [70, 90, 100])
def test_formatter_reports_hourly_values_and_exact_frozen_text(probability):
    new = candidate(probability)
    decision = decision_for(new)
    rendered = format_intraday_alert(new, decision, now=NOW, location_name="พื้นที่ทดสอบ")
    frozen = freeze_intraday_evidence(new, decision, rendered, now=NOW, baseline_delivery_id=1)
    assert rendered.message == frozen["message_text"]
    assert "ปริมาณฝนสูงสุดต่อชั่วโมง" in rendered.message
    assert "รวมวันนี้" not in rendered.message
    assert "10:00–16:00" in rendered.message
    assert frozen["comparison"]["event_id"] == decision.event_id
    assert len(frozen["hourly_intervals"]) == 6
    assert frozen["daily_aggregate"] is None
    assert "recipient_id" not in str(frozen) and "latitude" not in str(frozen)


def test_three_windows_show_two_actual_triggers_but_archive_all_changes():
    new = candidate(10)
    new = replace(new, hours=tuple(replace(hour, probability={0:70, 2:95, 4:90}.get(i, 10))
                                   for i, hour in enumerate(new.hours)))
    decision = decision_for(new)
    rendered = format_intraday_alert(new, decision, now=NOW, location_name="test")
    assert len(rendered.periods) == 2
    assert [period[0].start for period in rendered.periods] == [NOW + 2 * H, NOW + 4 * H]
    frozen = freeze_intraday_evidence(new, decision, rendered, now=NOW, baseline_delivery_id=1)
    assert len(frozen["comparison"]["triggers"]) == len(decision.triggers)
    assert len(frozen["hourly_intervals"]) == 6


def test_new_third_period_is_displayed_instead_of_unchanged_top_two():
    previous = old_evidence()
    previous = replace(previous, hours=tuple(
        replace(hour, probability={0:90, 2:80}.get(i, 10)) for i, hour in enumerate(previous.hours)))
    new = replace(candidate(10), hours=tuple(
        replace(hour, probability={0:90, 2:80, 4:70}.get(i, 10)) for i, hour in enumerate(candidate().hours)))
    decision = compare_intraday(Baseline(1, NOW - 4 * H, previous), new, now=NOW)
    rendered = format_intraday_alert(new, decision, now=NOW, location_name="test")
    assert len(rendered.periods) == 1 and rendered.periods[0][0].start == NOW + 4 * H
    assert "14:00–15:00" in rendered.message


def test_location_text_cannot_inject_lines_and_message_stays_bounded():
    new = candidate()
    rendered = format_intraday_alert(new, decision_for(new), now=NOW,
                                     location_name="test\nFAKE\r\n" + "ก" * 9000)
    assert "test FAKE" in rendered.message and len(rendered.message) <= 5000
    assert len(rendered.message.splitlines()[1]) < 270


def test_unknown_unselected_hour_is_frozen_without_becoming_zero():
    new = replace(candidate(), hours=(Hour(NOW - H, NOW, None, None),) + candidate().hours)
    rendered = format_intraday_alert(new, decision_for(new), now=NOW, location_name="test")
    frozen = freeze_intraday_evidence(new, decision_for(new), rendered, now=NOW, baseline_delivery_id=1)
    assert len(frozen["hourly_intervals"]) == 7
    assert frozen["hourly_intervals"][0]["precipitation_mm"] is None


def test_suppression_cannot_be_formatted_as_sendable_alert():
    new = candidate(10)
    with pytest.raises(ValueError, match="notify"):
        format_intraday_alert(new, decision_for(new), now=NOW, location_name="test")


@pytest_asyncio.fixture
async def source_sessions(pg_sessions):
    new = candidate()
    async with pg_sessions() as db:
        db.add(ForecastRun(id=12, location_id=101, provider="open_meteo", retrieved_at=new.retrieved_at))
        await db.flush()
        db.add_all(HourlyForecast(forecast_run_id=12, valid_time=hour.end,
                                 precipitation_probability=float(hour.probability),
                                 precipitation=float(hour.rainfall_mm)) for hour in new.hours)
        await db.commit()
    return pg_sessions


async def rows(sessions):
    async with sessions() as db:
        return list((await db.scalars(select(NotificationDelivery).order_by(NotificationDelivery.id))).all())


@pg
@pytest.mark.asyncio
async def test_default_preview_never_pushes_or_advances_baseline(source_sessions):
    client = AsyncMock()
    result = await deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW, client=client)
    assert result.status == "preview" and result.message
    client.push_text.assert_not_awaited()
    assert len(await rows(source_sessions)) == 1


@pg
@pytest.mark.asyncio
async def test_mock_acceptance_is_committed_and_replay_suppresses(source_sessions):
    client = AsyncMock()
    result = await deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW,
                                          client=client, dry_run=False)
    assert result.status == "sent" and result.delivery_id
    records = await rows(source_sessions)
    assert len(records) == 2
    saved = records[-1]
    assert saved.forecast_run_id == 12
    assert saved.rain_evidence["message_text"] == result.message == client.push_text.await_args.args[1]
    assert saved.rain_evidence["comparison"]["baseline_delivery_id"] == records[0].id
    assert saved.rain_evidence["comparison"]["candidate_fingerprint"] == result.decision.candidate_fingerprint
    assert saved.dedupe_key.endswith(result.decision.event_id)
    replay = await deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW,
                                          client=client, dry_run=False)
    assert replay.status == "suppress" and replay.decision.reasons == ("identical_content",)
    client.push_text.assert_awaited_once()


@pg
@pytest.mark.asyncio
@pytest.mark.parametrize("error,expected", [
    (LineApiError("mock rejected"), LineApiError),
    (TimeoutError("mock timeout"), SendOutcomeUnknown),
    (httpx.ReadError("mock connection lost after request"), SendOutcomeUnknown),
])
async def test_failed_or_ambiguous_push_never_creates_delivery(source_sessions, error, expected):
    client = AsyncMock()
    client.push_text.side_effect = error
    with pytest.raises(expected):
        await deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW,
                                      client=client, dry_run=False)
    assert len(await rows(source_sessions)) == 1
    client.push_text.assert_awaited_once()


@pg
@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["flush", "commit"])
async def test_accepted_push_then_persistence_failure_is_explicit_and_not_retried(source_sessions, stage):
    engine = source_sessions.kw["bind"].sync_engine
    client = AsyncMock()
    def fail(*args):
        if stage == "commit" or args[2].lstrip().startswith("INSERT INTO notification_deliveries"):
            raise RuntimeError("mock " + stage + " failure")
    name = "commit" if stage == "commit" else "before_cursor_execute"
    event.listen(engine, name, fail)
    try:
        with pytest.raises(AcceptedDeliveryNotCommitted) as error:
            await deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW,
                                          client=client, dry_run=False)
        assert error.value.event_id
        assert isinstance(error.value.__cause__, RuntimeError)
    finally:
        event.remove(engine, name, fail)
    assert len(await rows(source_sessions)) == 1
    client.push_text.assert_awaited_once()


@pg
@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["metrics", "retrieved", "model", "missing_hour", "location", "missing_run"])
async def test_untrusted_candidate_must_match_committed_source(source_sessions, change):
    async with source_sessions() as db:
        if change == "metrics":
            await db.execute(update(HourlyForecast).values(precipitation_probability=99))
        elif change == "retrieved":
            await db.execute(update(ForecastRun).values(retrieved_at=NOW - H))
        elif change == "model":
            await db.execute(update(ForecastRun).values(model_run_time=NOW - 2 * H))
        elif change == "missing_hour":
            await db.execute(delete(HourlyForecast).where(HourlyForecast.valid_time == candidate().hours[0].end))
        elif change == "location":
            await db.execute(update(ForecastRun).values(location_id=102))
        elif change == "missing_run":
            await db.execute(delete(ForecastRun))
        await db.commit()
    client = AsyncMock()
    result = await deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW,
                                          client=client, dry_run=False)
    assert result.status == "skip" and result.decision.reasons == ("candidate_source_mismatch",)
    client.push_text.assert_not_awaited()


@pg
@pytest.mark.asyncio
async def test_uncommitted_candidate_source_cannot_back_a_delivery(source_sessions):
    new = replace(candidate(), source_id=13)
    async with source_sessions() as writer:
        writer.add(ForecastRun(id=13, location_id=101, provider="open_meteo", retrieved_at=new.retrieved_at))
        await writer.flush()
        client = AsyncMock()
        result = await deliver_intraday_update(source_sessions, new, clock=lambda: NOW,
                                              client=client, dry_run=False)
        assert result.status == "skip"
        client.push_text.assert_not_awaited()
        await writer.rollback()


@pg
@pytest.mark.asyncio
async def test_concurrent_real_delivery_function_pushes_mock_once(source_sessions):
    entered, release = asyncio.Event(), asyncio.Event()
    client = AsyncMock()
    async def push(*args):
        entered.set()
        await release.wait()
    client.push_text.side_effect = push
    task1 = asyncio.create_task(deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW,
                                                       client=client, dry_run=False))
    task2 = None
    try:
        await asyncio.wait_for(entered.wait(), 8)
        task2 = asyncio.create_task(deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW,
                                                           client=client, dry_run=False))
        await wait_for_database_lock(source_sessions)
        release.set()
        first, second = await asyncio.gather(task1, task2)
        assert first.status == "sent" and second.status == "suppress"
        client.push_text.assert_awaited_once()
        assert len(await rows(source_sessions)) == 2
    finally:
        release.set()
        tasks = [task for task in (task1, task2) if task is not None]
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@pg
@pytest.mark.asyncio
async def test_existing_source_rows_stay_locked_until_mock_acceptance_commits(source_sessions):
    updater = None
    client = AsyncMock()
    async def mutate():
        async with source_sessions() as db:
            await db.execute(update(HourlyForecast).values(precipitation_probability=99))
            await db.commit()
    async def push(*args):
        nonlocal updater
        updater = asyncio.create_task(mutate())
        await wait_for_database_lock(source_sessions, "transactionid")
        assert not updater.done()
    client.push_text.side_effect = push
    try:
        result = await deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW,
                                              client=client, dry_run=False)
        await asyncio.wait_for(updater, 8)
        saved = (await rows(source_sessions))[-1].rain_evidence
        assert saved["hourly_intervals"][0]["precipitation_probability"] == 70
        assert saved["message_text"] == result.message
    finally:
        if updater is not None and not updater.done():
            updater.cancel()
            await asyncio.gather(updater, return_exceptions=True)


@pg
@pytest.mark.asyncio
async def test_source_deletion_after_commit_retains_frozen_message(source_sessions):
    result = await deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW,
                                          client=AsyncMock(), dry_run=False)
    before = copy.deepcopy((await rows(source_sessions))[-1].rain_evidence)
    async with source_sessions() as db:
        await db.execute(delete(ForecastRun).where(ForecastRun.id == 12))
        await db.commit()
    saved = (await rows(source_sessions))[-1]
    assert saved.forecast_run_id is None and saved.rain_evidence == before
    assert saved.rain_evidence["message_text"] == result.message


@pg
@pytest.mark.asyncio
async def test_historical_same_source_mutation_is_rejected_before_push(source_sessions):
    previous = candidate(80)
    decision = decision_for(previous)
    rendered = format_intraday_alert(previous, decision, now=NOW, location_name="test")
    frozen = freeze_intraday_evidence(previous, decision, rendered, now=NOW, baseline_delivery_id=999)
    async with source_sessions() as db:
        db.add(delivery("rain-intraday:v1:101:" + decision.event_id,
                       rain_evidence=frozen, created_at=NOW - 5 * H))
        await db.commit()
    client = AsyncMock()
    result = await deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW,
                                          client=client, dry_run=False)
    assert result.decision.reasons == ("inconsistent_historical_replay",)
    client.push_text.assert_not_awaited()


@pg
@pytest.mark.asyncio
async def test_identical_history_under_same_baseline_is_suppressed(source_sessions):
    previous = replace(candidate(), source_id=99)
    decision = decision_for(previous)
    rendered = format_intraday_alert(previous, decision, now=NOW, location_name="test")
    frozen = freeze_intraday_evidence(previous, decision, rendered, now=NOW, baseline_delivery_id=1)
    frozen["comparison"]["event_id"] = "f" * 64
    async with source_sessions() as db:
        db.add(delivery("rain-intraday:v1:101:" + frozen["comparison"]["event_id"],
                       rain_evidence=frozen, created_at=NOW - 5 * H))
        await db.commit()
    client = AsyncMock()
    result = await deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW,
                                          client=client, dry_run=False)
    assert result.decision.reasons == ("historical_identical_content",)
    client.push_text.assert_not_awaited()


@pg
@pytest.mark.asyncio
async def test_unknown_history_is_not_treated_as_permission_to_send(source_sessions):
    async with source_sessions() as db:
        db.add(delivery("rain-intraday:v1:101:legacy", created_at=NOW - 5 * H))
        await db.commit()
    client = AsyncMock()
    result = await deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW,
                                          client=client, dry_run=False)
    assert result.decision.reasons == ("unknown_replay_history",)
    client.push_text.assert_not_awaited()


@pg
@pytest.mark.asyncio
async def test_cancellation_during_push_rolls_back_and_releases_lock(source_sessions):
    entered = asyncio.Event()
    client = AsyncMock()
    async def push(*args):
        entered.set()
        await asyncio.Future()
    client.push_text.side_effect = push
    task = asyncio.create_task(deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW,
                                                       client=client, dry_run=False))
    await asyncio.wait_for(entered.wait(), 8)
    task.cancel()
    with pytest.raises(asyncio.CancelledError) as error:
        await task
    assert "unknown" in " ".join(error.value.__notes__)
    assert len(await rows(source_sessions)) == 1
    preview = await deliver_intraday_update(source_sessions, candidate(), clock=lambda: NOW)
    assert preview.status == "preview"
    client.push_text.assert_awaited_once()


def test_earlier_onset_reason_does_not_claim_a_daily_total():
    previous = replace(old_evidence(), hours=tuple(
        replace(hour, probability=70 if i == 3 else 69) for i, hour in enumerate(candidate().hours)))
    new = replace(candidate(69), hours=tuple(
        replace(hour, probability=70 if i in (1, 3) else 69) for i, hour in enumerate(candidate().hours)))
    decision = compare_intraday(Baseline(1, NOW - 4 * H, previous), new, now=NOW)
    rendered = format_intraday_alert(new, decision, now=NOW, location_name="test")
    assert decision.reasons == ("earlier_onset",)
    assert "เริ่มเร็วกว่า" in rendered.message and "รวมวันนี้" not in rendered.message


def test_freezing_cannot_silently_round_high_precision_metrics():
    from decimal import Decimal
    new = replace(candidate(), hours=tuple(replace(hour, probability=Decimal("70.0000000000000000001"))
                                          for hour in candidate().hours))
    decision = decision_for(new)
    rendered = format_intraday_alert(new, decision, now=NOW, location_name="test")
    with pytest.raises(ValueError, match="precision"):
        freeze_intraday_evidence(new, decision, rendered, now=NOW, baseline_delivery_id=1)

@pg
@pytest.mark.asyncio
async def test_final_clock_after_source_verification_can_cancel_stale_eligibility(source_sessions):
    times = iter([NOW, NOW + 2 * H])
    client = AsyncMock()
    result = await deliver_intraday_update(source_sessions, candidate(), clock=lambda: next(times),
                                          client=client, dry_run=False)
    assert result.status == "skip" and result.decision.reasons == ("stale_candidate",)
    client.push_text.assert_not_awaited()
    assert len(await rows(source_sessions)) == 1


@pg
@pytest.mark.asyncio
async def test_invalid_acceptance_clock_is_not_reported_as_committed_success(source_sessions):
    times = iter([NOW, NOW, NOW - H])
    client = AsyncMock()
    with pytest.raises(AcceptedDeliveryNotCommitted):
        await deliver_intraday_update(source_sessions, candidate(), clock=lambda: next(times),
                                      client=client, dry_run=False)
    client.push_text.assert_awaited_once()
    assert len(await rows(source_sessions)) == 1
