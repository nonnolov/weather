"use client";
import {WeatherArtwork} from "../WeatherArtwork";
import {weather,timeLabel} from "./format";
import {UiIcon} from "./UiIcon";
import {AudienceStats} from "./AudienceStats";
import {locationLabels} from "../../lib/locationLabels";
import type {DashboardModel} from "./useWeatherDashboard";
export function DashboardHeader({model}:{model:DashboardModel}) {
const {health,forecast,location,lineUserId,theme,setTheme,language,setLanguage,t,ux,isGpsBusy,busy,handleGps,summary}=model;
const labels=location ? locationLabels(location,language) : null;
const lineLabel=lineUserId ? t.connectedLine : language === "th" ? "ยังไม่เชื่อม LINE" : "LINE not connected";
const lineIndicator=<span className={"line-dot" + (lineUserId ? " connected" : "")} aria-hidden="true" />;
 return (    <header className="dashboard-header">
      <div className="brand"><span className="brand-weather" role="img" aria-label={summary ? weather(summary.weather_code, language) : language === "th" ? "เมฆ · ยังไม่มีข้อมูลพยากรณ์" : "Cloud · no forecast loaded"}><WeatherArtwork code={summary?.weather_code ?? 3} compact /></span><div><h1>Weather</h1><div className="brand-meta"><p className="eyebrow">{ux.intro}</p><AudienceStats language={language} lineUserId={lineUserId} /></div><span className="header-line-mobile">{lineIndicator}{lineLabel}</span></div></div>
      <div>
        {location && <div className="header-location"><div><UiIcon name="location" /><strong>{labels?.province || location.name}</strong>{(location.subdistrict || location.district) && <small>{[labels?.subdistrict, labels?.district].filter(Boolean).join(" · ")}</small>}<small>{t.retrieved} {forecast ? timeLabel(forecast.retrieved_at, location.timezone) : "—"} · {location.timezone}</small></div><button className="header-location-action" type="button" onClick={handleGps} disabled={busy}>{isGpsBusy ? "…" : ux.update}</button></div>}
        <div className="header-actions"><span className="header-line">{lineIndicator}{lineLabel}</span><button className="utility-button" type="button" onClick={() => setTheme(theme === "light" ? "dark" : "light")} aria-label={theme === "light" ? "Switch to dark theme" : "Switch to light theme"}><UiIcon name={theme === "light" ? "moon" : "sun"} /></button><button className="utility-button" type="button" onClick={() => setLanguage(language === "th" ? "en" : "th")} aria-label={t.lang}>{language === "th" ? "EN" : "TH"}</button></div>
        {health !== "online" && <p className={"connection " + health}><span aria-hidden="true" />{health === "loading" ? t.checking : t.offline}</p>}
      </div>
    </header>);
}
