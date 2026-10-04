from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from app.models.forecast import ForecastRun, HourlyForecast
from app.notifications.rain_risk import RainRiskPeriod


def format_rain_alert(
    run: ForecastRun,
    periods: list[RainRiskPeriod],
    *,
    alert_date: date,
    location_name: str | None = None,
) -> str:
    """Format the highest-risk rain periods for a LINE alert."""
    timezone_name = getattr(run.location, "timezone", None) or "Asia/Bangkok"
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("Asia/Bangkok")

    location = location_name or run.location.name
    lines = [
        "🌧️ แจ้งเตือนฝนวันนี้",
        f"📍 {location}",
    ]
    for period in periods:
        start = period.start.astimezone(tz)
        end = period.end.astimezone(tz)
        lines.append(
            f"⚠️ {start:%H:%M}–{end:%H:%M} "
            f"โอกาสฝนสูงสุด {period.max_probability:.0f}% "
            f"ฝนสูงสุดประมาณ {period.max_rainfall_mm:.1f} mm/h"
        )
    lines.append("แนะนำเตรียมร่มก่อนออกจากบ้าน")
    return "\n".join(lines)


def format_forecast_alert(
    run: ForecastRun,
    rows=None,
    alert_date: date | None = None,
    location_name: str | None = None,
) -> str:
    """Format concise 7-day forecast alert from a stored forecast run."""
    rows = sorted(rows if rows is not None else run.daily_forecasts, key=lambda item: item.forecast_date)
    if alert_date is not None:
        rows = [row for row in rows if row.forecast_date >= alert_date]
    rows = rows[:7]

    lines = [f"Weather alert: {location_name or run.location.name}", ""]
    for row in rows:
        rain = row.precipitation_probability_max
        rain_text = f"rain {rain:.0f}%" if rain is not None else "rain n/a"
        lines.append(
            f"{row.forecast_date:%d %b}: "
            f"{row.temperature_2m_min:.0f}-{row.temperature_2m_max:.0f}°C, {rain_text}"
            if row.temperature_2m_min is not None and row.temperature_2m_max is not None
            else f"{row.forecast_date:%d %b}: temperature n/a, {rain_text}"
        )

        if rain is not None and rain >= 60:
            lines.append("  Rain warning: high precipitation probability.")
    return "\n".join(lines)
