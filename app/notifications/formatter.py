from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from math import fsum, isfinite
from zoneinfo import ZoneInfo

from app.models.forecast import ForecastRun, HourlyForecast
from app.notifications.rain_risk import RainRiskPeriod, rain_interval_local_date

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


def _period_metrics(period, rows):
    """Aggregate every preceding-hour interval in the displayed window."""
    start = _local_time(period.start, timezone.utc)
    end = _local_time(period.end, timezone.utc)
    span = (end - start).total_seconds() / 3600
    if span <= 0 or not span.is_integer():
        return None, None, None, ()
    expected = {start + timedelta(hours=i) for i in range(1, int(span) + 1)}
    grouped = {}
    for row in rows:
        instant = _local_time(row.valid_time, timezone.utc)
        if instant in expected:
            grouped.setdefault(instant, []).append(row)

    def values(attribute, maximum=None):
        result = []
        for instant in sorted(expected):
            candidates = grouped.get(instant, [])
            items = [getattr(row, attribute, None) for row in candidates]
            if not items or any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                or not isfinite(value) or value < 0
                or (maximum is not None and value > maximum)
                for value in items
            ) or len(set(items)) != 1:
                return None
            result.append(items[0])
        return result

    probabilities = values("precipitation_probability", 100)
    rainfall = values("precipitation")
    return (
        max(probabilities) if probabilities is not None else None,
        fsum(rainfall) if rainfall is not None else None,
        max(rainfall) if rainfall is not None else None,
        tuple(end for end, value in zip(sorted(expected), rainfall)
              if value == max(rainfall)) if rainfall is not None and max(rainfall) > 0 else (),
    )


def _rain_amount(value):
    return f"{value:.2f}".rstrip("0").rstrip(".") if value is not None else None


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
        "────────────" if qualifying else "พยากรณ์ฝนยังไม่ถึงเกณฑ์",
    ]

    hours = [
        row for row in (hourly_rows or [])
        if rain_interval_local_date(row, tz.key) == alert_date
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
    if probabilities and not qualifying:
        lines.append(f"💧 โอกาสฝนสูงสุด: {max(probabilities):.0f}%")

    if qualifying:
        lines.extend(["ช่วงที่ควรระวังฝน", ""])
        for index, period in enumerate(sorted(periods, key=lambda item: item.start)):
            if index:
                lines.extend(["", "────────────"])
            start = _local_time(period.start, tz)
            end = _local_time(period.end, tz)
            probability, amount, peak, peak_ends = _period_metrics(period, hourly_rows or [])
            probability_text = f"{probability:.0f}%" if probability is not None else "ข้อมูลไม่ครบ"
            amount_text = f"{_rain_amount(amount)} มม." if amount is not None else "ข้อมูลไม่ครบ"
            peak_text = f"{_rain_amount(peak)} มม." if peak is not None else "ข้อมูลไม่ครบ"
            if peak is None:
                peak_hours = "ข้อมูลไม่ครบ"
            elif not peak_ends:
                peak_hours = "ไม่มีฝนคาดการณ์ในช่วงนี้"
            else:
                peak_hours = ", ".join(
                    f"{_local_time(instant - timedelta(hours=1), tz):%H:%M}–{_local_time(instant, tz):%H:%M}"
                    for instant in peak_ends
                ) + " น."
            lines.extend([
                f"🕒 {start:%H:%M}–{end:%H:%M} น.",
                f"💧 โอกาสฝนสูงสุดในช่วง: {probability_text}",
                f"🌧️ ฝนคาดการณ์รวมในช่วง: {amount_text}",
                f"⛈️ ฝนสูงสุดต่อชั่วโมง: {peak_text}",
                f"🕐 ชั่วโมงที่คาดว่าฝนมากที่สุด: {peak_hours}",
            ])
        lines.extend(["", "────────────"])

    total = daily.precipitation_sum if daily is not None else None
    # Never label a partial hourly sum as the full-day total.
    if total is not None and (
        isinstance(total, bool) or not isfinite(total) or total < 0
    ):
        total = None
    if total is None:
        day_start = datetime.combine(alert_date, datetime.min.time(), tz)
        day_period = RainRiskPeriod(day_start, day_start + timedelta(days=1), 0, 0, 24, 0)
        _, total, _, _ = _period_metrics(day_period, hours)
    if total is not None:
        if qualifying:
            lines.append(f"📊 ฝนคาดการณ์รวมทั้งวัน: {_rain_amount(total)} มม.")
        else:
            lines.append(f"🌧️ ปริมาณฝนคาดการณ์รวมวันนี้: {total:g} มม.")
    elif qualifying:
        lines.append("📊 ฝนคาดการณ์รวมทั้งวัน: ข้อมูลไม่ครบ")

    lines.extend([
        "",
        "☂️ แนะนำพกร่มและตรวจพยากรณ์ก่อนออกเดินทาง" if qualifying
        else "ยังอาจมีฝนบางช่วง ตรวจพยากรณ์ล่าสุดก่อนออกเดินทาง",
        "",
    ])
    if qualifying:
        lines[-1:-1] = [
            "โอกาสฝนและปริมาณฝนอาจแตกต่างกันในแต่ละชั่วโมง",
            "ข้อมูลเป็นการพยากรณ์ สภาพอากาศจริงอาจแตกต่างและเปลี่ยนแปลงได้",
        ]
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
