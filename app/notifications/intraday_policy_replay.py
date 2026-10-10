"""Offline, no-send replay of recorded forecasts; not an accuracy measurement.

Run: python -m app.notifications.intraday_policy_replay INPUT.json OUTPUT.json
Input is the sanitized forecast-history export documented in P1_13_POLICY_HANDOFF.
No provider, database, scheduler, settings or LINE client is imported here.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from app.notifications.intraday_comparison import Baseline, Evidence, Hour, Scope, _utc, compare_intraday
from app.notifications.intraday_candidate_policy import compare_candidate_policy, CANDIDATE_POLICY_VERSION


def _evidence(data, scope):
    return Evidence(
        scope, data["source_id"], _utc(datetime.fromisoformat(data["retrieved_at"])),
        tuple(Hour(_utc(datetime.fromisoformat(h["start"])),
                   _utc(datetime.fromisoformat(h["end"])), h["probability"], h["rainfall_mm"])
              for h in data["hours"]),
        None if data.get("model_time") is None else _utc(datetime.fromisoformat(data["model_time"])),
    )


def replay_history(payload):
    """15-minute as-of simulation, comparing a fixed and hypothetical baseline.

    Only snapshots already retrieved at a tick are visible. Hypothetical
    acceptances advance separate v1/v2 baselines immediately; no real delivery,
    network latency, scheduler timing, source-refresh behavior or send failures
    are simulated. Fixed-baseline decisions never advance the recorded baseline.
    """
    scope = Scope("U_REPLAY", 1, payload["provider"], payload["timezone"])
    raw = payload["baseline"]
    original = Baseline(raw["delivery_id"], _utc(datetime.fromisoformat(raw["accepted_at"])),
                        _evidence(raw["evidence"], scope))
    sources = sorted((_evidence(s, Scope("U_REPLAY", 1, s["provider"], scope.timezone))
                      for s in payload["sources"]), key=lambda e: (e.retrieved_at, str(e.source_id)))
    if not sources:
        raise ValueError("Recorded sources required")
    if len(sources) >= payload.get("export_limit", 2000):
        raise ValueError("Possibly truncated export; do not report complete replay")
    end = sources[-1].retrieved_at
    start = original.accepted_at
    if end < start or end-start > timedelta(days=7):
        raise ValueError("Replay window must be ordered and bounded to seven days")
    ticks = []
    now = start
    while now <= end:
        ticks.append(now)
        now += timedelta(minutes=15)
    if not ticks or ticks[-1] != end:
        ticks.append(end)
    functions = {"v1": compare_intraday, "candidate_v2": compare_candidate_policy}
    report = {}
    disagreements = []
    for mode in ("fixed_recorded_baseline", "hypothetical_acceptance"):
        baselines = {name: original for name in functions}
        counts = {name: Counter() for name in functions}
        reasons = {name: Counter() for name in functions}
        events = {name: [] for name in functions}
        tick_count = 0
        for now in ticks:
            available = [s for s in sources if s.retrieved_at <= now]
            if not available:
                continue
            source = available[-1]
            today = now.astimezone(ZoneInfo(scope.timezone)).date()
            candidate = Evidence(
                source.scope, source.source_id, source.retrieved_at,
                tuple(h for h in source.hours if h.start.astimezone(ZoneInfo(scope.timezone)).date()==today),
                source.model_time,
            )
            tick_count += 1
            decisions = {}
            for name, compare in functions.items():
                decision = compare(baselines[name], candidate, now=now)
                decisions[name] = decision
                counts[name][decision.outcome] += 1
                reasons[name].update(decision.reasons)
                if decision.outcome == "notify":
                    events[name].append({"at": now.isoformat(), "source_id": source.source_id,
                                         "reasons": list(decision.reasons), "event_id": decision.event_id})
                    if mode == "hypothetical_acceptance":
                        baselines[name] = Baseline(f"simulation-{name}-{len(events[name])}", now, candidate)
            if decisions["v1"].outcome != decisions["candidate_v2"].outcome:
                disagreements.append({"mode": mode, "at": now.isoformat(),
                                      "v1": decisions["v1"].outcome,
                                      "candidate_v2": decisions["candidate_v2"].outcome})
        report[mode] = {name: {"evaluated_ticks": tick_count, "outcomes": dict(counts[name]),
                               "reasons": dict(reasons[name]), "eligible_events": events[name]}
                        for name in functions}
    return {"candidate_policy_version": CANDIDATE_POLICY_VERSION,
            "recorded_sources": len(sources), "first_retrieval": sources[0].retrieved_at.isoformat(),
            "last_retrieval": end.isoformat(), "baseline_accepted_at": start.isoformat(),
            "cadence_minutes": 15, "includes_final_retrieval_tick": True,
            "actual_rain_observations_included": False, "accuracy_measured": False,
            "line_calls": 0, "production_writes": 0, "simulation_only": True,
            "results": report, "outcome_disagreements": disagreements}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        raise ValueError("Output must not overwrite recorded input")
    raw = args.input.read_bytes()
    result = replay_history(json.loads(raw))
    result["input_sha256"] = sha256(raw).hexdigest()
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"recorded_sources": result["recorded_sources"],
                      "outcome_disagreements": len(result["outcome_disagreements"]),
                      "accuracy_measured": False, "line_calls": 0}))


if __name__ == "__main__":
    main()
