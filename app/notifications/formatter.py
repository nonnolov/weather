from __future__ import annotations

from datetime import date, timezone
from zoneinfo import ZoneInfo

from app.models.forecast import ForecastRun, HourlyForecast
from app.notifications.rain_risk import RainRiskPeriod

_FORECAST_URL = "https://weather-iota-five-83.vercel.app"
_THAI_MONTHS = (
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
)


def _thai_date(value: date) -> str:
    return f"{value.day} {_THAI_MONTHS[value.month - 1]} {value.year + 543}"


def _local_time(value, tz):
    # PostgreSQL timestamps are aware; SQLite test timestamps can be naive UTC.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(tz)


def format_rain_alert(
    run: ForecastRun,
    periods: list[RainRiskPeriod],
    *,
    alert_date: date,
    location_name: str | None = None,
    daily_peak: bool = False,
    hourly_rows: list[HourlyForecast] | None = None,
    daily_rows=None,
) -> str:
    """Format qualifying rain alerts or a below-threshold daily summary."""
    timezone_name = getattr(run.location, "timezone", None) or "Asia/Bangkok"
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("Asia/Bangkok")
    qualifying = bool(periods)
    location = location_name or run.location.name
    lines = [
        "🌧️ แจ้งเตือนฝนวันนี้" if qualifying else "🌤️ สรุปฝนวันนี้",
        f"📍 {location}",
        f"📅 {_thai_date(alert_date)}",
        "",
        "มีโอกาสฝนถึงเกณฑ์แจ้งเตือน" if qualifying else "พยากรณ์ฝนยังไม่ถึงเกณฑ์",
    ]

    hours = [
        row for row in (hourly_rows or [])
        if _local_time(row.valid_time, tz).date() == alert_date
    ]
    daily = next(
        (row for row in (daily_rows or []) if row.forecast_date == alert_date), None
    )
    probabilities = [
        row.precipitation_probability for row in hours
        if row.precipitation_probability is not None
    ]
    if daily is not None and daily.precipitation_probability_max is not None:
        probabilities.append(daily.precipitation_probability_max)
    if not probabilities and hourly_rows is None:
        probabilities = [period.max_probability for period in periods]
    if probabilities:
        lines.append(f"💧 โอกาสฝนสูงสุด: {max(probabilities):.0f}%")

    if qualifying:
        windows = []
        for period in sorted(periods, key=lambda item: item.start):
            start = _local_time(period.start, tz)
            end = _local_time(period.end, tz)
            windows.append(f"{start:%H:%M}–{end:%H:%M}")
        lines.append(f"🕒 ช่วงที่ควรระวัง: {', '.join(windows)} น.")

    total = daily.precipitation_sum if daily is not None else None
    # Never label a partial hourly sum as the full-day total.
    if total is None and len(hours) == 24 and all(row.precipitation is not None for row in hours):
        total = sum(row.precipitation for row in hours)
    if total is not None:
        lines.append(f"🌧️ ปริมาณฝนคาดการณ์รวมวันนี้: {total:g} มม.")

    lines.extend([
        "",
        "แนะนำพกร่มและตรวจพยากรณ์ก่อนออกเดินทาง" if qualifying
        else "ยังอาจมีฝนบางช่วง ตรวจพยากรณ์ล่าสุดก่อนออกเดินทาง",
        "",
    ])
    if run.retrieved_at is not None:
        updated = _local_time(run.retrieved_at, tz)
        lines.append(f"อัปเดตพยากรณ์: {_thai_date(updated.date())} {updated:%H:%M} น.")
    lines.append(f"ดูรายละเอียด: {_FORECAST_URL}")
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
