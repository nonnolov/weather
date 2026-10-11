"""Source-backed rain screening; this is not a calibrated flood prediction."""
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any

SOURCE_URL = "https://vlg-water-r.disaster.go.th/osm2rain/"
RULE_VERSION = "ddpm_rain_screening_forecast_v1"
MAX_FORECAST_AGE_HOURS = 6  # Application freshness policy, not an official rainfall rule.
BANGKOK_NAMES = {"bangkok", "bangkok metropolis", "กรุงเทพมหานคร", "กรุงเทพ"}
# Other named urban areas require verified administrative scope before selecting 40 mm.
SPECIAL_PROVINCES = {
    "nonthaburi", "pathum thani", "samut prakan", "nakhon pathom", "samut sakhon",
    "chon buri", "chonburi", "rayong", "phuket",
    "นนทบุรี", "ปทุมธานี", "สมุทรปราการ", "นครปฐม", "สมุทรสาคร",
    "ชลบุรี", "ระยอง", "ภูเก็ต",
}


def evaluate_rainfall_screening(run: Any, location: Any, values: list,
                               ends: list, now: datetime) -> dict:
    result = {
        "assessment_status": "not_assessed",
        "risk_detected": None,
        "risk_level": None,
        "assessment_reason_codes": [],
        "screening_rule_version": RULE_VERSION,
        "screening_source_url": SOURCE_URL,
        "assessment_basis": "forecast_adaptation_of_observed_rainfall_screening",
        "historical_validation_status": "not_calibrated",
        "location_profile": None,
        "trigger_windows": [],
        "limitations": [
            "forecast_rainfall_not_station_observation",
            "rainfall_only_not_flood_confirmation_or_probability",
            "drainage_terrain_antecedent_water_and_tides_not_modelled",
            "administrative_metadata_not_verified_boundary",
        ],
        "max_consecutive_rain_hours": 0,
    }
    consecutive = 0
    for amount in values:
        consecutive = consecutive + 1 if amount is not None and amount > 0 else 0
        result["max_consecutive_rain_hours"] = max(
            result["max_consecutive_rain_hours"], consecutive)
    reasons = result["assessment_reason_codes"]
    if run.provider != "open_meteo":
        reasons.append("forecast_interval_semantics_unverified")
        return result
    if location is None:
        reasons.append("location_profile_unavailable")
        return result
    if location.id != run.location_id:
        reasons.append("location_forecast_mismatch")
        return result
    country = (getattr(location, "country_code", None) or "").upper()
    province = (getattr(location, "province", None) or "").strip().lower()
    coordinates = [getattr(location, name, None) for name in ("latitude", "longitude")]
    if country != "TH" or not province or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v)
        for v in coordinates
    ) or not (5 <= coordinates[0] <= 21 and 97 <= coordinates[1] <= 106):
        reasons.append("location_profile_unavailable")
        return result
    if province in SPECIAL_PROVINCES:
        reasons.append("urban_threshold_scope_unverified")
        return result
    hourly_threshold = 40 if province in BANGKOK_NAMES else 75
    result["location_profile"] = {
        "name": "bangkok_urban" if hourly_threshold == 40 else "thailand_general",
        "hourly_threshold_mm": hourly_threshold,
        "selection_basis": "stored_country_province_and_coordinate_sanity_check",
    }
    retrieved = run.retrieved_at
    if retrieved.tzinfo is None:
        retrieved = retrieved.replace(tzinfo=timezone.utc)
    age = now - retrieved
    if age < timedelta(minutes=-5):
        reasons.append("forecast_retrieval_in_future")
        return result
    if age > timedelta(hours=MAX_FORECAST_AGE_HOURS):
        reasons.append("forecast_stale")
        return result
    for index, amount in enumerate(values):
        if amount is not None and amount >= hourly_threshold:
            result["trigger_windows"].append({
                "hours": 1, "amount_mm": amount, "threshold_mm": hourly_threshold,
                "interval_start": (ends[index] - timedelta(hours=1)).isoformat(),
                "interval_end": ends[index].isoformat(),
                "reason_code": "hourly_rainfall_threshold_reached",
            })
    complete = len(values) == 24 and all(v is not None for v in values)
    if complete:
        # Thailand local month at the end of the forecast window determines season.
        month = (ends[-1] + timedelta(hours=7)).month
        daily_threshold = 100 if 5 <= month <= 10 else 150
        total = sum(values)
        if total >= daily_threshold:
            result["trigger_windows"].append({
                "hours": 24, "amount_mm": total, "threshold_mm": daily_threshold,
                "interval_start": (ends[0] - timedelta(hours=1)).isoformat(),
                "interval_end": ends[-1].isoformat(),
                "reason_code": "accumulated_rainfall_threshold_reached",
            })
        result["location_profile"]["24h_threshold_mm"] = daily_threshold
    if result["trigger_windows"]:
        result.update(assessment_status="rainfall_flood_potential",
                      risk_detected=True, risk_level="watch")
        reasons.extend(sorted({w["reason_code"] for w in result["trigger_windows"]}))
        if not complete:
            reasons.append("forecast_horizon_incomplete")
    elif complete:
        result.update(assessment_status="rainfall_below_trigger", risk_detected=False)
        reasons.append("rainfall_below_screening_thresholds")
    else:
        reasons.append("forecast_horizon_incomplete")
    return result
