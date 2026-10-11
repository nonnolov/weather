"""Read-only HTTP smoke checks for the existing daily-use release (no LINE send)."""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

def get_json(base, path):
    with urlopen(Request(base.rstrip("/") + path, headers={"Accept": "application/json"}), timeout=30) as response:
        if response.status != 200:
            raise ValueError("unexpected_http_status")
        return json.load(response)

def check_forecast(data, location_id, now):
    if data["location_id"] != location_id or data["provider"] != "open_meteo":
        raise ValueError("forecast_identity_mismatch")
    retrieved = datetime.fromisoformat(data["retrieved_at"].replace("Z", "+00:00"))
    if retrieved.tzinfo is None:
        raise ValueError("retrieval_timezone_missing")
    age = (now - retrieved).total_seconds()
    if not -300 <= age <= 10800:
        raise ValueError("forecast_not_fresh")
    hourly = data["hourly"]
    future = [row for row in hourly if datetime.fromisoformat(row["valid_time"].replace("Z", "+00:00")) >= now]
    if len(future) < 24 or len(data["daily"]) < 7:
        raise ValueError("forecast_horizon_incomplete")
    hours = sorted(datetime.fromisoformat(row["valid_time"].replace("Z", "+00:00")) for row in future)
    if any(b - a != timedelta(hours=1) for a, b in zip(hours[:24], hours[1:24])):
        raise ValueError("hourly_gaps_or_duplicates")
    for row in future[:24]:
        if row["temperature_2m"] is None or row["precipitation"] is None or row["precipitation_probability"] is None:
            raise ValueError("essential_hourly_values_missing")
        if row["precipitation"] < 0 or not 0 <= row["precipitation_probability"] <= 100:
            raise ValueError("invalid_rain_values")
    return {"location_id": location_id, "forecast_run_id": data["id"],
            "forecast_age_minutes": round(age / 60, 1), "future_hours": len(future),
            "daily_records": len(data["daily"]), "status": "passed"}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="API URL or frontend URL ending /api/backend")
    parser.add_argument("--location-id", type=int, action="append", required=True)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    report = {"checked_at": now.isoformat(), "line_calls": 0, "checks": [], "warnings": []}
    try:
        health = get_json(args.base_url, "/health")
        if health.get("status") not in ("ok", "healthy"):
            raise ValueError("health_not_ready")
        report["checks"].append({"name": "health", "status": "passed"})
        for location_id in args.location_id:
            forecast = get_json(args.base_url, "/api/v1/forecast/" + str(location_id))
            report["checks"].append(check_forecast(forecast, location_id, now))
            air = get_json(args.base_url, "/api/v1/air-quality/" + str(location_id))
            if air["location_id"] != location_id or air["measurement_available"] or air["source"]["source_type"] != "model_estimate":
                raise ValueError("air_quality_contract_mismatch")
            report["checks"].append({"location_id": location_id, "name": "air_quality", "status": air["status"]})
            if air["status"] != "available":
                report["warnings"].append({"location_id": location_id, "name": "air_quality", "status": air["status"]})
        report["status"] = "passed"
    except (HTTPError, URLError, ValueError, KeyError, TypeError) as exc:
        report["status"] = "failed"
        report["error_type"] = type(exc).__name__
        if isinstance(exc, HTTPError):
            report["http_status"] = exc.code
        elif isinstance(exc, ValueError):
            report["reason"] = str(exc)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1

if __name__ == "__main__":
    sys.exit(main())
