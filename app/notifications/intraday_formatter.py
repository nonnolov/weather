"""Deterministic intraday text and frozen v1 evidence, separate from daily."""
from dataclasses import dataclass
from copy import deepcopy
from app.notifications.flood_enrichment import enrich_rain_message
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.notifications.formatter import _FORECAST_URL, _thai_date
from app.notifications.intraday_comparison import Decision, Evidence, Hour, POLICY_VERSION

from app.notifications.intraday_policy import comparator_for


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _json_metric(value):
    if value is None:
        return None
    number = float(value)
    if Decimal(str(number)) != Decimal(str(value)):
        raise ValueError("Metric precision cannot be preserved in JSON")
    return number


def hour_json(hour: Hour) -> dict:
    return {"start": utc(hour.start).isoformat(), "end": utc(hour.end).isoformat(),
            "precipitation_probability": _json_metric(hour.probability),
            "precipitation_mm": _json_metric(hour.rainfall_mm)}


@dataclass(frozen=True)
class RenderedIntraday:
    message: str
    periods: tuple[tuple[Hour, ...], ...]
    flood_evidence: dict | None = None


def format_intraday_alert(candidate: Evidence, decision: Decision, *,
                          now: datetime, location_name: str,
                          flood_evidence: dict | None = None) -> RenderedIntraday:
    """Display at most two trigger-containing periods; no full-day totals."""
    if decision.outcome != "notify" or not decision.triggers or not decision.event_id:
        raise ValueError("A locked notify decision is required")
    zone = ZoneInfo(candidate.scope.timezone.strip())
    rows = sorted({(item.candidate.start, item.candidate.end): item.candidate
                   for item in decision.triggers}.values(), key=lambda item: item.start)
    groups = []
    for row in rows:
        if groups and groups[-1][-1].end == row.start:
            groups[-1].append(row)
        else:
            groups.append([row])
    priority = {"earlier_onset": 0, "new_rain": 1, "escalation": 2}
    def rank(group):
        keys = {(row.start, row.end) for row in group}
        reasons = [priority[item.reason] for item in decision.triggers
                   if (item.candidate.start, item.candidate.end) in keys]
        return (min(reasons), -max(row.probability for row in group),
                -max(row.rainfall_mm for row in group), group[0].start)
    periods = tuple(tuple(group) for group in sorted(sorted(groups, key=rank)[:2],
                                                    key=lambda group: group[0].start))
    # Database names are data, not permission to add arbitrary message lines.
    name = " ".join(location_name.split())[:255] or "พื้นที่ปัจจุบัน"
    local_now = utc(now).astimezone(zone)
    lines = ["🌧️ อัปเดตพยากรณ์ฝนระหว่างวัน", f"📍 {name}",
             f"📅 {_thai_date(local_now.date())}", ""]
    if "earlier_onset" in decision.reasons:
        lines.append("ช่วงฝนถึงเกณฑ์อาจเริ่มเร็วกว่าพยากรณ์ที่แจ้งก่อนหน้า")
    if "new_rain" in decision.reasons:
        lines.append("พบช่วงฝนถึงเกณฑ์เพิ่มจากพยากรณ์ที่แจ้งก่อนหน้า")
    elif "escalation" in decision.reasons:
        lines.append("บางช่วงมีโอกาสฝนหรือปริมาณฝนเพิ่มขึ้นจากพยากรณ์ที่แจ้งก่อนหน้า")
    for period in periods:
        start, end = (utc(period[0].start).astimezone(zone),
                      utc(period[-1].end).astimezone(zone))
        lines.extend(["", f"🕒 {start:%H:%M}–{end:%H:%M} น.",
                      f"โอกาสฝนสูงสุดในช่วง: {max(row.probability for row in period):g}%",
                      f"ปริมาณฝนสูงสุดต่อชั่วโมง: {max(row.rainfall_mm for row in period):g} มม."])
    lines.extend(["", "แนะนำพกร่มและตรวจพยากรณ์ก่อนออกเดินทาง",
                  "พยากรณ์อาจเปลี่ยนแปลงได้"])
    retrieved = utc(candidate.retrieved_at).astimezone(zone)
    lines.extend([f"อัปเดตพยากรณ์: {_thai_date(retrieved.date())} {retrieved:%H:%M} น.",
                  f"ดูรายละเอียด: {_FORECAST_URL}"])
    message = enrich_rain_message("\n".join(lines), flood_evidence,
                                  source_id=candidate.source_id, location_id=candidate.scope.location_id)
    if len(message) > 5000:
        raise ValueError("Intraday message exceeds LINE text limit")
    return RenderedIntraday(message, periods, deepcopy(flood_evidence))


def freeze_intraday_evidence(candidate: Evidence, decision: Decision, rendered: RenderedIntraday,
                             *, now: datetime, baseline_delivery_id: int,
                             policy_version: str = POLICY_VERSION) -> dict:
    """Fresh JSON value; recipient/GPS excluded, all local-day hours retained."""
    comparator_for(policy_version)
    zone = ZoneInfo(candidate.scope.timezone.strip())
    day = utc(now).astimezone(zone).date()
    return {
        "schema_version": 1, "template_version": "rain-intraday-v1",
        "selection_version": "intraday-trigger-periods-v1", "mode": "intraday_update",
        "alert_local_date": day.isoformat(), "timezone": zone.key,
        "source": {"forecast_run_id": candidate.source_id, "provider": candidate.scope.provider,
                   "retrieved_at": utc(candidate.retrieved_at).isoformat(),
                   "model_run_time": None if candidate.model_time is None else utc(candidate.model_time).isoformat()},
        "hourly_intervals": [hour_json(row) for row in sorted(candidate.hours, key=lambda row: utc(row.start))
                             if utc(row.start).astimezone(zone).date() == day],
        "selected_periods": [
            {"start": utc(period[0].start).isoformat(), "end": utc(period[-1].end).isoformat(),
             "max_probability": float(max(row.probability for row in period)),
             "max_rainfall_mm": float(max(row.rainfall_mm for row in period)),
             "duration_hours": len(period)} for period in rendered.periods],
        "daily_aggregate": None, "message_text": rendered.message,
        "flood_screening": deepcopy(rendered.flood_evidence),
        "comparison": {"policy_version": policy_version, "baseline_delivery_id": baseline_delivery_id,
                       "evaluated_at": utc(now).isoformat(), "event_id": decision.event_id,
                       "candidate_fingerprint": decision.candidate_fingerprint,
                       "reasons": list(decision.reasons),
                       "window": [[utc(start).isoformat(), utc(end).isoformat()] for start, end in decision.window],
                       "triggers": [{"reason": item.reason, "baseline": hour_json(item.baseline),
                                     "candidate": hour_json(item.candidate)} for item in decision.triggers]},
    }
