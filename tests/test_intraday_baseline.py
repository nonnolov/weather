"""Synthetic, file-backed SQLite checks; no live DB, provider or LINE."""
import copy
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import event, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.forecast import ForecastRun
from app.models.location import Location
from app.models.notification import NotificationDelivery
from app.models.user import User
from app.notifications.intraday_baseline import evaluate_intraday_from_db, read_latest_rain_baseline
from app.notifications.intraday_comparison import Evidence, Hour, Scope, compare_intraday

NOW = datetime(2026, 10, 10, 3, tzinfo=timezone.utc)
H = timedelta(hours=1)
SCOPE = Scope("U_TEST", 101, "open_meteo", "Asia/Bangkok")


def candidate(probability=70):
    return Evidence(SCOPE, 12, NOW - timedelta(minutes=30),
                    tuple(Hour(NOW + i * H, NOW + (i + 1) * H, probability, 0)
                          for i in range(6)))


def payload():
    return {
        "schema_version": 1, "timezone": "Asia/Bangkok",
        "alert_local_date": "2026-10-10",
        "source": {"forecast_run_id": 11, "provider": "open_meteo",
                   "retrieved_at": (NOW - 4 * H).isoformat(), "model_run_time": None},
        "hourly_intervals": [
            {"start": hour.start.isoformat(), "end": hour.end.isoformat(),
             "precipitation_probability": 10, "precipitation_mm": 0}
            for hour in candidate().hours],
        "selected_periods": [], "daily_aggregate": {"precipitation_sum_mm": 999},
        "message_text": "synthetic baseline",
    }


def delivery(key="rain:101:2026-10-10", **changes):
    values = dict(location_id=101, channel="line", recipient_id="U_TEST",
                  dedupe_key=key, created_at=NOW - 4 * H, rain_evidence=payload())
    values.update(changes)
    return NotificationDelivery(**values)


@pytest_asyncio.fixture
async def sessions(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///" + (tmp_path / "p103.sqlite").as_posix())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with factory() as db:
        db.add_all([
            Location(id=101, name="test", slug="p103", latitude=0, longitude=0,
                     timezone="Asia/Bangkok"),
            Location(id=102, name="other", slug="p103-other", latitude=1, longitude=1,
                     timezone="Asia/Bangkok"),
            User(external_id="U_TEST", current_location_id=101),
        ])
        await db.commit()
    yield factory
    await engine.dispose()


async def save(sessions, *rows):
    async with sessions() as db:
        db.add_all(rows)
        await db.commit()


@pytest.mark.asyncio
async def test_notify_matches_pure_comparator_and_only_executes_reads(sessions, monkeypatch):
    from app.notifications.line_client import LineClient
    async def forbidden(*args, **kwargs):
        raise AssertionError("LINE must never be called")
    monkeypatch.setattr(LineClient, "push_text", forbidden)
    await save(sessions, delivery())
    async with sessions() as db:
        baseline = await read_latest_rain_baseline(db, SCOPE)
        before = copy.deepcopy((await db.scalars(select(NotificationDelivery))).one().rain_evidence)
    statements = []
    engine = sessions.kw["bind"]
    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(engine.sync_engine, "before_cursor_execute", record)
    try:
        actual = await evaluate_intraday_from_db(sessions, candidate(), now=NOW)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record)
    assert statements and set(statements) == {"SELECT"}
    assert actual == compare_intraday(baseline, candidate(), now=NOW)
    assert actual.outcome == "notify" and actual.event_id
    async with sessions() as db:
        rows = (await db.scalars(select(NotificationDelivery))).all()
        assert len(rows) == 1 and rows[0].rain_evidence == before


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,reason", [
    ("absent", "no_baseline"), ("null", "unknown_baseline"),
    ("version", "unsupported_baseline"), ("bool_version", "unsupported_baseline"),
    ("not_dict", "malformed_baseline_evidence"),
    ("missing_source", "malformed_baseline_evidence"),
    ("invalid_time", "malformed_baseline_evidence"),
    ("duplicate", "malformed_baseline_evidence"),
    ("negative", "malformed_baseline_evidence"),
    ("wrong_day", "malformed_baseline_evidence"),
    ("missing_hour", "incomplete_coverage"),
    ("null_metric", "incomplete_coverage"),
    ("provider", "scope_mismatch"), ("zone", "scope_mismatch"),
    ("stale", "stale_baseline"), ("future", "future_timestamp"),
])
async def test_newest_bad_evidence_never_falls_back(sessions, kind, reason):
    if kind != "absent":
        await save(sessions, delivery())
        data = payload()
        created = NOW - 3 * H
        if kind == "null": data = None
        elif kind == "version": data["schema_version"] = 2
        elif kind == "bool_version": data["schema_version"] = True
        elif kind == "not_dict": data = []
        elif kind == "missing_source": del data["source"]
        elif kind == "invalid_time": data["source"]["retrieved_at"] = "bad"
        elif kind == "duplicate": data["hourly_intervals"].append(data["hourly_intervals"][0])
        elif kind == "negative": data["hourly_intervals"][0]["precipitation_mm"] = -1
        elif kind == "wrong_day": data["alert_local_date"] = "2026-10-09"
        elif kind == "missing_hour": data["hourly_intervals"].pop()
        elif kind == "null_metric": del data["hourly_intervals"][0]["precipitation_mm"]
        elif kind == "provider": data["source"]["provider"] = "other"
        elif kind == "zone": data["timezone"] = "UTC"
        elif kind == "stale": data["source"]["retrieved_at"] = (NOW - 25 * H).isoformat()
        elif kind == "future": created = NOW + H
        await save(sessions, delivery("rain-intraday:v1:101:new", rain_evidence=data, created_at=created))
    result = await evaluate_intraday_from_db(sessions, candidate(), now=NOW)
    assert result.outcome == "skip" and result.reasons == (reason,)


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["recipient", "location", "channel", "namespace", "prefix"])
async def test_unrelated_newer_deliveries_do_not_replace_baseline(sessions, change):
    await save(sessions, delivery())
    values = {"created_at": NOW, "rain_evidence": None}
    key = "rain:101:2026-10-11"
    if change == "recipient": values["recipient_id"] = "U_OTHER"
    elif change == "location": values["location_id"] = 102; key = "rain:102:2026-10-10"
    elif change == "channel": values["channel"] = "email"
    elif change == "namespace": key = "forecast:101:new"
    elif change == "prefix": key = "rain:1010:2026-10-10"
    await save(sessions, delivery(key, **values))
    assert (await evaluate_intraday_from_db(sessions, candidate(), now=NOW)).outcome == "notify"


@pytest.mark.asyncio
async def test_equal_timestamp_uses_descending_delivery_id(sessions):
    await save(sessions, delivery())
    await save(sessions, delivery("rain-intraday:v1:101:tie", rain_evidence=None))
    assert (await evaluate_intraday_from_db(sessions, candidate(), now=NOW)).reasons == ("unknown_baseline",)


@pytest.mark.asyncio
async def test_uncommitted_newest_record_is_not_baseline(sessions):
    await save(sessions, delivery())
    async with sessions() as writer:
        writer.add(delivery("rain-intraday:v1:101:pending", rain_evidence=None, created_at=NOW))
        await writer.flush()
        assert (await evaluate_intraday_from_db(sessions, candidate(), now=NOW)).outcome == "notify"
        await writer.commit()
    assert (await evaluate_intraday_from_db(sessions, candidate(), now=NOW)).reasons == ("unknown_baseline",)


@pytest.mark.asyncio
async def test_rollback_cannot_advance_baseline(sessions):
    await save(sessions, delivery())
    async with sessions() as writer:
        writer.add(delivery("rain-intraday:v1:101:rollback", rain_evidence=None, created_at=NOW))
        await writer.flush()
        await writer.rollback()
    assert (await evaluate_intraday_from_db(sessions, candidate(), now=NOW)).outcome == "notify"


@pytest.mark.asyncio
async def test_deleted_source_fk_uses_frozen_unselected_hourly_evidence(sessions):
    await save(sessions, delivery(forecast_run_id=None))
    async with sessions() as db:
        baseline = await read_latest_rain_baseline(db, SCOPE)
    assert baseline.evidence.source_id == 11
    assert len(baseline.evidence.hours) == 6
    assert (await evaluate_intraday_from_db(sessions, candidate(), now=NOW)).outcome == "notify"


@pytest.mark.asyncio
async def test_mutated_live_source_cannot_change_frozen_comparison(sessions):
    await save(sessions, ForecastRun(id=11, location_id=101, provider="changed",
                                    retrieved_at=NOW, model_run_time=NOW))
    await save(sessions, delivery(forecast_run_id=11))
    assert (await evaluate_intraday_from_db(sessions, candidate(), now=NOW)).outcome == "notify"


@pytest.mark.asyncio
async def test_conflicting_nonnull_fk_is_rejected(sessions):
    await save(sessions, ForecastRun(id=99, location_id=101, provider="other", retrieved_at=NOW))
    await save(sessions, delivery(forecast_run_id=99))
    assert (await evaluate_intraday_from_db(sessions, candidate(), now=NOW)).reasons == ("malformed_baseline_evidence",)


@pytest.mark.asyncio
@pytest.mark.parametrize("case,reason", [
    ("missing_user", "no_current_location"), ("null_location", "no_current_location"),
    ("changed", "location_changed"), ("zone", "scope_mismatch"),
    ("inactive", "inactive_location"), ("reassigned", "location_reassigned"),
    ("browser", "invalid_recipient"),
])
async def test_current_scope_is_checked(sessions, case, reason):
    await save(sessions, delivery())
    new = candidate()
    async with sessions() as db:
        if case == "null_location":
            await db.execute(update(User).values(current_location_id=None))
        elif case == "changed":
            await db.execute(update(User).values(current_location_id=102))
        elif case == "zone":
            await db.execute(update(Location).values(timezone="UTC"))
        elif case == "inactive":
            await db.execute(update(Location).values(is_active=False))
        await db.commit()
    if case in ("missing_user", "browser"):
        new = replace(new, scope=replace(SCOPE, recipient_id="U_MISSING" if case == "missing_user" else "browser"))
    result = await evaluate_intraday_from_db(sessions, new, now=NOW,
                                             known_location_reassigned=case == "reassigned")
    assert result.reasons == (reason,) and result.outcome == "skip"


@pytest.mark.asyncio
@pytest.mark.parametrize("probability,outcome,reason", [
    (10, "suppress", "identical_content"), (30, "suppress", "no_significant_change"),
    (70, "notify", "new_rain"),
])
async def test_comparator_decisions_are_preserved(sessions, probability, outcome, reason):
    await save(sessions, delivery())
    result = await evaluate_intraday_from_db(sessions, candidate(probability), now=NOW)
    assert result.outcome == outcome and reason in result.reasons


@pytest.mark.asyncio
async def test_latest_intraday_controls_cooldown_without_writes(sessions):
    await save(sessions, delivery())
    await save(sessions, delivery("rain-intraday:v1:101:recent", created_at=NOW - H))
    result = await evaluate_intraday_from_db(sessions, candidate(), now=NOW)
    assert result.outcome == "suppress" and result.reasons == ("cooldown",)


@pytest.mark.asyncio
async def test_naive_frozen_utc_and_unknown_model_are_supported(sessions):
    data = payload()
    data["source"]["retrieved_at"] = (NOW - 4 * H).replace(tzinfo=None).isoformat()
    for row in data["hourly_intervals"]:
        for key in ("start", "end"):
            row[key] = datetime.fromisoformat(row[key]).replace(tzinfo=None).isoformat()
    await save(sessions, delivery(rain_evidence=data))
    assert (await evaluate_intraday_from_db(sessions, candidate(), now=NOW)).outcome == "notify"


@pytest.mark.asyncio
async def test_database_failure_propagates_instead_of_notify(sessions):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        with pytest.raises(Exception, match="no such table"):
            await evaluate_intraday_from_db(async_sessionmaker(engine), candidate(), now=NOW)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_factory_bound_to_uncommitted_connection_is_rejected(sessions):
    async with sessions.kw["bind"].connect() as conn:
        factory = async_sessionmaker(conn)
        with pytest.raises(ValueError, match="engine-bound"):
            await evaluate_intraday_from_db(factory, candidate(), now=NOW)
