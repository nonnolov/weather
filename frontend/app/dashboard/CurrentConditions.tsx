"use client";
import {WeatherArtwork} from "../WeatherArtwork";
import {value,weather,timeLabel} from "./format";
import {UiIcon} from "./UiIcon";
import {locationLabels} from "../../lib/locationLabels";
import type {DashboardModel} from "./useWeatherDashboard";
export function CurrentConditions({model}:{model:DashboardModel}) {
const {setMapOpen,forecast,location,language,t,ux,isGpsBusy,busy,progress,handleGps,summary}=model;
 if(!forecast || !location) return null;
 return (<section id="current-conditions" className="summary-grid" aria-label={t.monitoredLocation}>
      <article className="card primary-summary">
        <div className="hero-location"><div><p className="eyebrow"><UiIcon name="location" />{t.monitoredLocation}</p><h2>{locationLabels(location,language).parts.join(", ")}</h2></div><div className="hero-stamp"><span>{t.retrieved}</span><time dateTime={forecast.retrieved_at}>{timeLabel(forecast.retrieved_at, location.timezone)}</time></div></div>
        <div className="weather-hero-copy">
          <p className="eyebrow">{t.nextHour}{summary ? " · " + timeLabel(summary.valid_time, location.timezone) : ""}</p>
          <div className="hero-reading"><strong className="hero-temperature">{summary ? value(summary.temperature_2m) : "—"}<small>°C</small></strong><span className="feels-like">{language === "th" ? "รู้สึกเหมือน" : "Feels like"}<strong>{summary ? value(summary.apparent_temperature, "°C") : "—"}</strong></span></div>

          <p className="hero-outlook">{language === "th" ? "โอกาสฝน " : "Rain chance "}{summary ? value(summary.precipitation_probability, "%") : "—"} · {language === "th" ? "พยากรณ์สำหรับพื้นที่ของคุณ" : "Your local outlook"}</p>
        </div>
        <div className="hero-art"><WeatherArtwork code={summary?.weather_code ?? null} /><p className="hero-condition">{weather(summary?.weather_code ?? null, language)}</p></div>
      </article>
      <article className="card metric rain-probability"><span className="metric-label">{t.rainChance}<UiIcon name="rain" /></span><strong>{summary ? value(summary.precipitation_probability, "%") : "—"}</strong>{summary?.precipitation_probability != null && <div className="probability-track" aria-hidden="true"><span style={{width: Math.max(0, Math.min(100, summary.precipitation_probability)) + "%"}} /></div>}</article>
      <article className="card metric rainfall"><span className="metric-label">{t.precip}<UiIcon name="drop" /></span><strong>{summary ? value(summary.precipitation, language === "th" ? " มม." : " mm") : "—"}</strong></article>
      <article className="card metric"><span className="metric-label">{t.wind}<UiIcon name="wind" /></span><strong>{summary ? value(summary.wind_speed_10m) : "—"}<small className="metric-unit"> km/h</small></strong></article>
      <article className="card metric"><span className="metric-label">{t.humidity}<UiIcon name="drop" /></span><strong>{summary ? value(summary.relative_humidity_2m, "%") : "—"}</strong></article>
        <div className="hero-actions"><button className="gps-primary" type="button" onClick={handleGps} disabled={busy}><UiIcon name="gps" className="action-icon" />{isGpsBusy ? progress : ux.update}</button><button className="map-button" type="button" onClick={() => setMapOpen(true)}><UiIcon name="map" />{language === "th" ? "ดูแผนที่" : "View map"}</button></div>
    </section>);
}
