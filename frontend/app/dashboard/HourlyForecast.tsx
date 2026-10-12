"use client";
import {WeatherArtwork} from "../WeatherArtwork";
import {value,timeLabel,next24Hours} from "./format";
import {UiIcon} from "./UiIcon";
import type {DashboardModel} from "./useWeatherDashboard";
export function HourlyForecast({model}:{model:DashboardModel}) {
const {forecast,location,language,t,ux}=model;
 if(!forecast || !location) return null;
 return (    <section className="card hourly-card" aria-labelledby="hourly-heading">
      <div className="section-heading"><UiIcon name="clock" /><h2 id="hourly-heading">{ux.hourly}</h2></div>
      <div className="hourly-list">{next24Hours(forecast.hourly).map((hour) => <article key={hour.id}>
        <time dateTime={hour.valid_time}>{timeLabel(hour.valid_time, location.timezone)}</time>
        <WeatherArtwork code={hour.weather_code} compact /><strong>{value(hour.temperature_2m, "°")}</strong>
        <span>{value(hour.precipitation_probability, "%")}</span>
        <small className="hourly-probability-label">{t.rainChance}</small><small>{value(hour.precipitation, language === "th" ? " มม." : " mm")}</small>
      </article>)}</div>
    </section>);
}
