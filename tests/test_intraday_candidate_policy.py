"""Offline candidate-policy tests; no provider, database or LINE calls."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.notifications.intraday_comparison import Baseline, Evidence, Hour, Scope, compare_intraday
from app.notifications.intraday_candidate_policy import compare_candidate_policy
from app.notifications.intraday_formatter import format_intraday_alert

NOW = datetime(2026, 10, 10, 3, tzinfo=timezone.utc)
H = timedelta(hours=1)
SCOPE = Scope("U_TEST", 1, "open_meteo", "Asia/Bangkok")


def evidence(probability=10, mm=0, source=2, age=timedelta(minutes=15)):
    return Evidence(SCOPE, source, NOW-age,
                    tuple(Hour(NOW+i*H, NOW+(i+1)*H, probability, mm) for i in range(6)))


def setup(old_p=10, old_mm=0, new_p=75, new_mm=0, index=0, age=H):
    old = Baseline(1, NOW-age, evidence(old_p, old_mm, source=1, age=4*H))
    rows = list(evidence(old_p, old_mm).hours)
    rows[index] = replace(rows[index], probability=new_p, rainfall_mm=new_mm)
    return old, replace(evidence(old_p, old_mm), hours=tuple(rows))


@pytest.mark.parametrize("old_p,old_mm,new_p,new_mm", [
    (65,0,75,0), (69.99,0,70,0), (0,9.99,0,10), (80,9,80,10),
])
def test_imminent_threshold_crossing_bypasses_cooldown(old_p,old_mm,new_p,new_mm):
    old,new=setup(old_p,old_mm,new_p,new_mm)
    assert compare_intraday(old,new,now=NOW).outcome=="suppress"
    result=compare_candidate_policy(old,new,now=NOW)
    assert result.outcome=="notify" and result.event_id


@pytest.mark.parametrize("index,expected", [(0,"notify"),(1,"notify"),(2,"notify"),(3,"suppress")])
def test_urgent_horizon_inclusive(index,expected):
    old,new=setup(index=index)
    assert compare_candidate_policy(old,new,now=NOW).outcome==expected


@pytest.mark.parametrize("age,expected", [
    (timedelta(hours=3,seconds=-1),"suppress"),
    (3*H,"notify"), (timedelta(hours=3,seconds=1),"notify"),
])
def test_nonurgent_crossing_respects_cooldown(age,expected):
    old,new=setup(old_p=65,new_p=75,index=3,age=age)
    assert compare_candidate_policy(old,new,now=NOW).outcome==expected


def test_probability_only_escalation_does_not_bypass():
    old,new=setup(old_p=70,new_p=90)
    assert compare_candidate_policy(old,new,now=NOW).reasons==("cooldown",)


@pytest.mark.parametrize("value,expected", [(14.99,"suppress"),(15,"notify"),(15.01,"notify")])
def test_imminent_rainfall_escalation_boundary(value,expected):
    old,new=setup(old_p=70,old_mm=10,new_p=70,new_mm=value)
    assert compare_candidate_policy(old,new,now=NOW).outcome==expected


def test_one_hour_earlier_onset_is_urgent():
    old,new=setup(old_p=69,new_p=69)
    old_rows=list(old.evidence.hours)
    old_rows[2]=replace(old_rows[2],probability=70)
    old=replace(old,evidence=replace(old.evidence,hours=tuple(old_rows)))
    new_rows=list(new.hours)
    new_rows[2]=replace(new_rows[2],probability=70)
    new_rows[1]=replace(new_rows[1],probability=70)
    new=replace(new,hours=tuple(new_rows))
    assert compare_candidate_policy(old,new,now=NOW).outcome=="notify"
    assert "earlier_onset" in compare_candidate_policy(old,new,now=NOW).reasons


@pytest.mark.parametrize("fault", ["no_baseline","unknown","stale","future","source_order",
                                  "same_id_changed","null","missing","scope","model"])
def test_original_safety_gates_preserved(fault):
    old,new=setup()
    if fault=="no_baseline": old=None
    elif fault=="unknown": old=replace(old,evidence=None)
    elif fault=="stale": new=replace(new,retrieved_at=NOW-timedelta(minutes=91))
    elif fault=="future": new=replace(new,retrieved_at=NOW+H)
    elif fault=="source_order": new=replace(new,retrieved_at=old.evidence.retrieved_at)
    elif fault=="same_id_changed": new=replace(new,source_id=old.evidence.source_id)
    elif fault=="null":
        rows=list(new.hours);rows[0]=replace(rows[0],rainfall_mm=None);new=replace(new,hours=tuple(rows))
    elif fault=="missing": new=replace(new,hours=new.hours[:-1])
    elif fault=="scope": new=replace(new,scope=replace(SCOPE,location_id=2))
    elif fault=="model":
        old=replace(old,evidence=replace(old.evidence,model_time=NOW-H))
        new=replace(new,model_time=NOW-2*H)
    assert compare_candidate_policy(old,new,now=NOW)==compare_intraday(old,new,now=NOW)
    assert compare_candidate_policy(old,new,now=NOW).outcome=="skip"


@pytest.mark.parametrize("new_p,new_mm", [(50,0),(10,0),(69.99,0),(10,9.99)])
def test_subthreshold_or_weakening_does_not_alert(new_p,new_mm):
    old,new=setup(old_p=70,old_mm=10,new_p=new_p,new_mm=new_mm,age=4*H)
    assert compare_candidate_policy(old,new,now=NOW).outcome=="suppress"


def test_replayed_content_does_not_alert_after_simulated_acceptance():
    old,new=setup()
    decision=compare_candidate_policy(old,new,now=NOW)
    assert decision.outcome=="notify"
    hypothetical=Baseline(2,NOW,new)
    assert compare_candidate_policy(hypothetical,new,now=NOW).reasons==("identical_content",)


def test_versioned_deterministic_event_and_existing_formatter():
    old,new=setup(age=4*H,new_p=75)
    v1=compare_intraday(old,new,now=NOW)
    v2=compare_candidate_policy(old,new,now=NOW)
    assert v1.outcome==v2.outcome=="notify"
    assert v1.event_id!=v2.event_id
    assert v2==compare_candidate_policy(old,new,now=NOW)
    text=format_intraday_alert(new,v2,now=NOW,location_name="Test").message
    assert "75%" in text
    assert "ฝนหนัก" not in text
