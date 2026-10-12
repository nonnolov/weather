"use client";
import {WeatherArtwork} from "../WeatherArtwork";
import {weather,timeLabel} from "./format";
import {UiIcon} from "./UiIcon";
import type {DashboardModel} from "./useWeatherDashboard";
export function DashboardHeader({model}:{model:DashboardModel}) {
const {setMapOpen,health,forecast,location,lineUserId,theme,setTheme,language,setLanguage,t,ux,isGpsBusy,busy,handleGps,summary}=model;
 return (    <header className="dashboard-header">
      <div className="brand"><span className="brand-weather" role="img" aria-label={summary ? weather(summary.weather_code, language) : language === "th" ? "เมฆ · ยังไม่มีข้อมูลพยากรณ์" : "Cloud · no forecast loaded"}><WeatherArtwork code={summary?.weather_code ?? 3} compact /></span><div><h1>Weather</h1><p className="eyebrow">{ux.intro}</p></div></div>
      <nav className="dashboard-nav" aria-label={language === "th" ? "เมนูหลัก" : "Main navigation"}><a href="#current-conditions" aria-current="page">{language === "th" ? "พยากรณ์ปัจจุบัน" : "Forecast"}</a><a href="#air-quality-heading">PM2.5</a><button type="button" onClick={() => setMapOpen(true)} disabled={!location}>{language === "th" ? "ดูแผนที่" : "Map"}</button></nav>
      <div>
        {location && <div className="header-location"><div><UiIcon name="location" /><strong>{location.province ?? location.name}</strong>{(location.subdistrict || location.district) && <small>{[location.subdistrict, location.district].filter(Boolean).join(" · ")}</small>}<small>{t.retrieved} {forecast ? timeLabel(forecast.retrieved_at, location.timezone) : "—"} · {location.timezone}</small></div><button className="header-location-action" type="button" onClick={handleGps} disabled={busy}>{isGpsBusy ? "…" : ux.update}</button></div>}
        <div className="header-actions"><span className="header-line"><span className={"line-dot" + (lineUserId ? " connected" : "")} aria-hidden="true" />{lineUserId ? t.connectedLine : language === "th" ? "ยังไม่เชื่อม LINE" : "LINE not connected"}</span><button className="utility-button" type="button" onClick={() => setTheme(theme === "light" ? "dark" : "light")} aria-label={theme === "light" ? "Switch to dark theme" : "Switch to light theme"}><UiIcon name={theme === "light" ? "moon" : "sun"} /></button><button className="utility-button" type="button" onClick={() => setLanguage(language === "th" ? "en" : "th")} aria-label={t.lang}>{language === "th" ? "EN" : "TH"}</button></div>
        {health !== "online" && <p className={"connection " + health}><span aria-hidden="true" />{health === "loading" ? t.checking : t.offline}</p>}
      </div>
    </header>);
}
