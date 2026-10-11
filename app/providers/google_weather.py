"""Google Weather transport and normalization for transient verification only.

Production persistence is blocked: standard Weather API terms restrict weather
apps and hourly caching to one hour, incompatible with immutable P1/P2 evidence.
Live preview requires a separately verified contract and a server-side key.
"""
from datetime import datetime, date, timedelta, timezone as dt_timezone
from math import isfinite, fsum
from zoneinfo import ZoneInfo
import httpx
from app.core.config import settings
from app.providers.base import BaseWeatherProvider, ProviderForecastResult, NormalizedHourlyForecast, NormalizedDailyForecast
from app.ingestion.fetch_control import reserve_requests, ForecastControlError


class GoogleWeatherProvider(BaseWeatherProvider):
    @property
    def name(self):
        return "google_weather"

    async def fetch_forecast(self, latitude, longitude, forecast_days=7, timezone="UTC"):
        if not settings.GOOGLE_WEATHER_CONTRACT_VERIFIED or not settings.GOOGLE_WEATHER_PREVIEW_ENABLED:
            raise ForecastControlError("Google live access requires verified usage rights and explicit preview enablement")
        if not settings.GOOGLE_WEATHER_API_KEY:
            raise ForecastControlError("Google Weather API key is not configured")
        if not 1 <= forecast_days <= 10:
            raise ForecastControlError("Google supports at most ten forecast days")
        from app.core.database import AsyncSessionLocal
        # Seven days take seven HTTP pages. No automatic retry or fallback.
        await reserve_requests(AsyncSessionLocal, self.name, forecast_days)
        async with httpx.AsyncClient(timeout=20) as client:
            raw = await self._fetch_pages(client, latitude, longitude, forecast_days * 24)
        return self.normalize(raw)

    async def fetch_observations(self, latitude, longitude, start_date, end_date, timezone="UTC"):
        raise ForecastControlError("Google modeled history must not be ingested as measured observations")

    async def _fetch_pages(self, client, latitude, longitude, hours):
        params = {"location.latitude": latitude, "location.longitude": longitude,
                  "hours": hours, "pageSize": 24, "unitsSystem": "METRIC", "languageCode": "th"}
        token = None
        seen = set()
        records = []
        timezone_name = None
        for _ in range((hours + 23) // 24):
            if token:
                params["pageToken"] = token
            response = await client.get("https://weather.googleapis.com/v1/forecast/hours:lookup",
                params=params, headers={"X-Goog-Api-Key": settings.GOOGLE_WEATHER_API_KEY})
            if response.status_code != 200:
                raise ForecastControlError("Google Weather request failed")
            page = response.json()
            tz = page.get("timeZone", {}).get("id")
            if not tz or (timezone_name and tz != timezone_name):
                raise ForecastControlError("Google timezone changed across pages")
            timezone_name = tz
            records.extend(page.get("forecastHours", []))
            token = page.get("nextPageToken")
            if not token:
                break
            if token in seen:
                raise ForecastControlError("Repeated Google pagination token")
            seen.add(token)
        if token or len(records) != hours:
            raise ForecastControlError("Google forecast is incomplete")
        return {"forecastHours": records, "timeZone": {"id": timezone_name}}

    @staticmethod
    def normalize(raw):
        tz_name = raw["timeZone"]["id"]
        tz = ZoneInfo(tz_name)
        hourly = []
        def number(value, maximum=None):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                return None
            if maximum is not None and not 0 <= value <= maximum:
                return None
            return value
        def metric(value, unit, field):
            return number(value.get(field)) if value and value.get("unit") == unit else None
        codes = {"CLEAR": 0, "MOSTLY_CLEAR": 1, "PARTLY_CLOUDY": 2, "MOSTLY_CLOUDY": 3,
                 "CLOUDY": 3, "FOG": 45, "LIGHT_RAIN": 61, "RAIN": 63, "HEAVY_RAIN": 65,
                 "LIGHT_RAIN_SHOWERS": 80, "RAIN_SHOWERS": 81, "HEAVY_RAIN_SHOWERS": 82,
                 "THUNDERSTORM": 95, "LIGHT_THUNDERSTORM_RAIN": 95, "THUNDERSTORM_RAIN": 95}
        for value in raw.get("forecastHours", []):
            start = datetime.fromisoformat(value["interval"]["startTime"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(value["interval"]["endTime"].replace("Z", "+00:00"))
            if start.tzinfo is None or end.tzinfo is None or end - start != timedelta(hours=1):
                raise ForecastControlError("Invalid Google hourly interval")
            rain = value.get("precipitation", {})
            amount = metric(rain.get("qpf"), "MILLIMETERS", "quantity")
            if amount is not None and amount < 0:
                amount = None
            wind = value.get("wind", {})
            hourly.append(NormalizedHourlyForecast(
                valid_time=end.astimezone(dt_timezone.utc),
                temperature_2m=metric(value.get("temperature"), "CELSIUS", "degrees"),
                apparent_temperature=metric(value.get("feelsLikeTemperature"), "CELSIUS", "degrees"),
                dewpoint_2m=metric(value.get("dewPoint"), "CELSIUS", "degrees"),
                relative_humidity_2m=number(value.get("relativeHumidity"), 100),
                precipitation=amount, precipitation_probability=number(rain.get("probability", {}).get("percent"), 100),
                weather_code=codes.get(value.get("weatherCondition", {}).get("type")),
                cloud_cover=number(value.get("cloudCover"), 100),
                wind_speed_10m=metric(wind.get("speed"), "KILOMETERS_PER_HOUR", "value"),
                wind_gusts_10m=metric(wind.get("gust"), "KILOMETERS_PER_HOUR", "value"),
                wind_direction_10m=number(wind.get("direction", {}).get("degrees"), 360),
                visibility=metric(value.get("visibility"), "KILOMETERS", "distance"),
                uv_index=number(value.get("uvIndex")), is_day=value.get("isDaytime"),
            ))
            if hourly[-1].visibility is not None:
                hourly[-1].visibility *= 1000
        hourly.sort(key=lambda h: h.valid_time)
        if any(b.valid_time - a.valid_time != timedelta(hours=1) for a, b in zip(hourly, hourly[1:])):
            raise ForecastControlError("Google hourly data has duplicates or gaps")
        daily = []
        dates = sorted({(h.valid_time - timedelta(hours=1)).astimezone(tz).date() for h in hourly})
        for day in dates:
            start = datetime.combine(day, datetime.min.time(), tzinfo=tz).astimezone(dt_timezone.utc)
            end = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=tz).astimezone(dt_timezone.utc)
            rows = [h for h in hourly if start < h.valid_time <= end]
            complete = len(rows) == int((end - start).total_seconds() / 3600)
            # Current partial day remains null; never label remaining-day rain as whole-day rain.
            def aggregate(field, op):
                vals = [getattr(h, field) for h in rows]
                return op(vals) if complete and vals and all(v is not None for v in vals) else None
            daily.append(NormalizedDailyForecast(forecast_date=day,
                precipitation_sum=aggregate("precipitation", fsum),
                precipitation_probability_max=aggregate("precipitation_probability", max),
                temperature_2m_max=aggregate("temperature_2m", max), temperature_2m_min=aggregate("temperature_2m", min)))
        return ProviderForecastResult(provider="google_weather", retrieved_at=datetime.now(dt_timezone.utc),
            model_run_time=None, hourly=hourly, daily=daily,
            metadata={"timezone": tz_name, "interval_semantics": "explicit_start_end_preceding_hour",
                "transient_only": True, "attribution": "Source: Includes weather data from Google",
                "storage_restriction": "hourly_one_hour", "production_eligible": False})
