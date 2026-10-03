from __future__ import annotations

from datetime import date

from app.models.forecast import ForecastRun


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
