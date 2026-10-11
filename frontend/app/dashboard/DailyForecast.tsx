"use client";
import {WeatherArtwork} from "../WeatherArtwork";
import {value,weather,timeLabel,dateLabel,rainRiskForDay} from "./format";
import type {CSSProperties} from "react";
import {UiIcon} from "./UiIcon";
import type {DashboardModel} from "./useWeatherDashboard";
export function DailyForecast({model}:{model:DashboardModel}) {
const {forecast,location,language,t}=model;
 if(!forecast || !location) return null;
 const temps=forecast.daily.flatMap(d=>[d.temperature_2m_min,d.temperature_2m_max]).filter((n):n is number=>n!=null);
 const dailyMin=temps.length?Math.min(...temps):0, dailyMax=temps.length?Math.max(...temps):1;
 return (    <section className="forecast-card" aria-labelledby="forecast-heading">
      <div className="section-heading"><UiIcon name="calendar" /><div><h2 id="forecast-heading">{t.forecast7}</h2><p>{t.retrieved} {timeLabel(forecast.retrieved_at, location.timezone)} · {forecast.provider.replaceAll("_", " ")}</p></div></div>
      <div className="forecast-list">{forecast.daily.slice(0, 7).map((day) => {
        const rainRisk = rainRiskForDay(day.forecast_date, forecast.hourly, location.timezone);
        const rangeStart = day.temperature_2m_min === null ? 0 : ((day.temperature_2m_min - dailyMin) / Math.max(dailyMax - dailyMin, 1)) * 100;
        const rangeWidth = day.temperature_2m_min === null || day.temperature_2m_max === null ? 0 : ((day.temperature_2m_max - day.temperature_2m_min) / Math.max(dailyMax - dailyMin, 1)) * 100;
        return <details className="forecast-day" key={day.id}>
          <summary className="day-summary"><div className="daily-date"><strong>{dateLabel(day.forecast_date, language)}</strong><span>{weather(day.weather_code, language)}</span></div><WeatherArtwork code={day.weather_code} compact /><span className="day-probability">{value(day.precipitation_probability_max ?? rainRisk.maxProbability, "%")}</span><div className="temperatures"><span>{value(day.temperature_2m_min, "°")}</span><div className="temperature-range" style={{ "--range-start": `${rangeStart}%`, "--range-width": `${rangeWidth}%` } as CSSProperties} /><strong>{value(day.temperature_2m_max, "°")}</strong></div></summary>
          <dl className="day-details"><div><dt>{t.rainRiskPeriod}</dt><dd>{rainRisk.period ?? "—"}</dd></div><div><dt>{t.precip}</dt><dd>{value(day.precipitation_sum, language === "th" ? " มม." : " mm")}</dd></div><div><dt>{t.wind}</dt><dd>{value(day.wind_speed_10m_max, " km/h")}</dd></div></dl>
        </details>;
      })}</div>
    </section>);
}
