"""Synthetic replay tests; never count these fixtures as measured weather."""
from datetime import datetime, timedelta, timezone

import pytest

from app.notifications.intraday_comparison import Evidence, Hour, Scope

NOW = datetime(2026, 10, 10, 3, tzinfo=timezone.utc)
H = timedelta(hours=1)


def evidence(probability, *, source, age):
    return Evidence(Scope("U_TEST", 1, "open_meteo", "Asia/Bangkok"), source, NOW-age,
                    tuple(Hour(NOW+i*H, NOW+(i+1)*H, probability, 0) for i in range(6)))
from app.notifications.intraday_policy_replay import replay_history


def record(ev):
    return {"source_id": ev.source_id, "provider": ev.scope.provider, "retrieved_at": ev.retrieved_at.isoformat(),
            "model_time": None, "hours": [
                {"start": h.start.isoformat(), "end": h.end.isoformat(),
                 "probability": h.probability, "rainfall_mm": h.rainfall_mm}
                for h in ev.hours]}


def payload():
    old = evidence(65, source=1, age=4*H)
    new = evidence(75, source=2, age=timedelta())
    return {"provider": "open_meteo", "timezone": "Asia/Bangkok",
            "baseline": {"delivery_id": 1, "accepted_at": (NOW-H).isoformat(), "evidence": record(old)},
            "sources": [record(old), record(new)], "export_limit": 2000}


def test_as_of_visibility_and_hypothetical_advance(monkeypatch):
    import socket
    def forbid(*args, **kwargs):
        raise AssertionError("Replay must never use network")
    monkeypatch.setattr(socket.socket, "connect", forbid)
    report = replay_history(payload())
    fixed = report["results"]["fixed_recorded_baseline"]
    simulated = report["results"]["hypothetical_acceptance"]
    events = fixed["candidate_v2"]["eligible_events"]
    assert len(events)==1
    assert events[0]["at"]==NOW.isoformat()
    assert events[0]["source_id"]==2
    assert simulated["candidate_v2"]["outcomes"]["notify"]==1
    assert not fixed["v1"]["eligible_events"]
    assert report["line_calls"]==report["production_writes"]==0
    assert report["accuracy_measured"] is False


def test_each_tick_uses_latest_visible_source():
    data = payload()
    later = record(evidence(10, source=3, age=-H))
    data["sources"].append(later)
    report = replay_history(data)
    events = report["results"]["hypothetical_acceptance"]["candidate_v2"]["eligible_events"]
    assert len(events)==1 and events[0]["source_id"]==2
    assert report["last_retrieval"]==(NOW+H).isoformat()


def test_retained_content_is_suppressed_after_hypothetical_acceptance():
    data=payload()
    later=record(evidence(75,source=3,age=-timedelta(minutes=30)))
    data["sources"].append(later)
    report=replay_history(data)
    result=report["results"]["hypothetical_acceptance"]["candidate_v2"]
    assert len(result["eligible_events"])==1
    assert result["reasons"]["identical_content"]>=2


@pytest.mark.parametrize("fault", ["empty","truncated","reversed","unbounded"])
def test_reject_insufficient_or_unbounded_input(fault):
    data=payload()
    if fault=="empty": data["sources"]=[]
    elif fault=="truncated": data["export_limit"]=len(data["sources"])
    elif fault=="reversed": data["baseline"]["accepted_at"]=(NOW+H).isoformat()
    else: data["baseline"]["accepted_at"]=(NOW-timedelta(days=8)).isoformat()
    with pytest.raises(ValueError):
        replay_history(data)
