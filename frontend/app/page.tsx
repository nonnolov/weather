"use client";

import Script from "next/script";
import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  authenticateLine,
  getHealth,
  getLatestForecast,
  getLocations,
  getUserForecast,
  setUserLocationFromGps,
  type ForecastRun,
  type Location,
} from "../lib/api";

const value = (n: number | null, unit = "") => n === null ? "—" : Math.round(n * 10) / 10 + unit;
const weather = (code: number | null) => code === null ? "Unavailable" : code === 0 ? "Clear sky" : [1,2,3].includes(code) ? "Partly cloudy" : [45,48].includes(code) ? "Fog" : [51,53,55,56,57].includes(code) ? "Drizzle" : [61,63,65,66,67,80,81,82].includes(code) ? "Rain" : [95,96,99].includes(code) ? "Thunderstorm" : "Weather code " + code;
const dateLabel = (date: string) => new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short" }).format(new Date(date + "T12:00:00"));
const timeLabel = (date: string, timeZone: string) => new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", timeZone }).format(new Date(date));
const nearestHourly = (hourly: ForecastRun["hourly"]) => hourly.find((hour) => new Date(hour.valid_time).getTime() >= Date.now()) ?? hourly[0];

type LiffClient = {
  init: (options: { liffId: string }) => Promise<void>;
  isLoggedIn: () => boolean;
  login: () => void;
  getIDToken: () => string | null;
};

declare global {
  interface Window {
    liff?: LiffClient;
  }
}

const liffId = process.env.NEXT_PUBLIC_LIFF_ID;

export default function Home() {
  const [health, setHealth] = useState<"loading" | "online" | "offline">("loading");
  const [locations, setLocations] = useState<Location[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [forecast, setForecast] = useState<ForecastRun | null>(null);
  const [location, setLocation] = useState<Location | null>(null);
  const [gpsState, setGpsState] = useState<"idle" | "locating" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const [lineUserId, setLineUserId] = useState<string | null>(null);

  const userId = useMemo(() => {
    if (typeof window === "undefined") return "browser";
    const key = "weather.external_user_id";
    let id = window.localStorage.getItem(key);
    if (!id) {
      id = "browser-" + crypto.randomUUID();
      window.localStorage.setItem(key, id);
    }
    return id;
  }, []);

  useEffect(() => {
    getHealth().then(() => setHealth("online")).catch(() => setHealth("offline"));
    getLocations().then((data) => {
      const active = data.filter((item) => item.is_active);
      setLocations(active);
      if (active[0]) setSelectedId(active[0].id);
    }).catch(() => setLocations([]));
  }, []);

  const initializeLiff = async () => {
    if (!liffId || !window.liff) return;
    try {
      await window.liff.init({ liffId });
      if (!window.liff.isLoggedIn()) {
        window.liff.login();
        return;
      }
      const token = window.liff.getIDToken();
      if (!token) throw new Error("LINE ID token unavailable.");
      const auth = await authenticateLine(token);
      setLineUserId(auth.external_user_id);
      setMessage("Connected to LINE.");
    } catch {
      setMessage("LINE connection is unavailable. Local demo identity is still active.");
    }
  };

  const activeUserId = lineUserId ?? userId;

  const useGps = () => {
    if (!navigator.geolocation) {
      setGpsState("error");
      setMessage("This browser does not support GPS location.");
      return;
    }
    setGpsState("locating");
    setMessage("Requesting your location…");
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          const result = await setUserLocationFromGps(activeUserId, position.coords.latitude, position.coords.longitude);
          setLocation(result.location);
          const data = await getUserForecast(activeUserId);
          setForecast(data);
          setGpsState("success");
          setMessage("Location detected and forecast loaded.");
        } catch (error) {
          setGpsState("error");
          setMessage(error instanceof ApiError && error.status === 502 ? "Location service is temporarily unavailable." : "Could not load the forecast for your location.");
        }
      },
      () => {
        setGpsState("error");
        setMessage("Location permission was denied or unavailable.");
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 },
    );
  };

  const selectSeedLocation = async (id: number) => {
    setSelectedId(id);
    setForecast(null);
    try {
      const data = await getLatestForecast(id);
      setForecast(data);
      setLocation(locations.find((item) => item.id === id) ?? null);
    } catch {
      setMessage("No stored forecast is available for this location.");
    }
  };

  const summary = forecast ? nearestHourly(forecast.hourly) : undefined;

  return <>
    {liffId && <Script src="https://static.line-scdn.net/liff/edge/2/sdk.js" strategy="afterInteractive" onLoad={initializeLiff} />}
    <main className="dashboard-shell">
    <header className="dashboard-header">
      <div><p className="eyebrow">Weather monitoring</p><h1>Forecast dashboard</h1></div>
      <p className={"connection " + health}><span aria-hidden="true" />Backend {health === "loading" ? "checking" : health}</p>
    </header>

    <section className="card controls" aria-labelledby="location-heading">
      <div>
        <h2 id="location-heading">Your location</h2>
        <p>Use GPS to forecast the exact area you are currently in.</p>
      </div>
      <button onClick={useGps} disabled={gpsState === "locating"}>
        {gpsState === "locating" ? "Detecting location…" : "Use my location"}
      </button>
      {location && <p className="location-meta">{location.subdistrict ?? location.name} · {location.district ?? "—"} · {location.province ?? "—"} · {location.latitude.toFixed(4)}°, {location.longitude.toFixed(4)}°</p>}
      {message && <p aria-live="polite">{message}</p>}
    </section>

    {!location && locations.length > 0 && <section className="card controls">
      <div><h2>Seed locations</h2><p>Fallback for testing before GPS is available.</p></div>
      <label className="select-label">Monitored location
        <select value={selectedId ?? ""} onChange={(event) => selectSeedLocation(Number(event.target.value))}>
          {locations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>
    </section>}

    {forecast && location && <p className="location-meta">{location.name} · {location.timezone}</p>}
    {!forecast && <section className="card message"><h2>No forecast loaded</h2><p>Allow GPS access to load a forecast for your current area.</p></section>}

    {forecast && location && <><section className="summary-grid" aria-label="Forecast summary">
      <article className="card primary-summary"><p className="eyebrow">Next forecast hour{summary ? " · " + timeLabel(summary.valid_time, location.timezone) : ""}</p><strong>{summary ? value(summary.temperature_2m, "°C") : "—"}</strong><p>{weather(summary?.weather_code ?? null)}</p></article>
      <article className="card metric"><span>Rain chance</span><strong>{summary ? value(summary.precipitation_probability, "%") : "—"}</strong></article>
      <article className="card metric"><span>Wind</span><strong>{summary ? value(summary.wind_speed_10m, " km/h") : "—"}</strong></article>
      <article className="card metric"><span>Humidity</span><strong>{summary ? value(summary.relative_humidity_2m, "%") : "—"}</strong></article>
    </section>
    <section className="card forecast-card" aria-labelledby="forecast-heading">
      <div className="section-heading"><div><h2 id="forecast-heading">7-day forecast</h2><p>Retrieved {timeLabel(forecast.retrieved_at, location.timezone)} · {forecast.provider.replaceAll("_", " ")}</p></div></div>
      <div className="forecast-list">{forecast.daily.slice(0, 7).map((day) => <article className="forecast-day" key={day.id}>
        <div><strong>{dateLabel(day.forecast_date)}</strong><span>{weather(day.weather_code)}</span></div>
        <div className="temperatures"><strong>{value(day.temperature_2m_max, "°")}</strong><span>{value(day.temperature_2m_min, "°")}</span></div>
        <div><span>Rain</span><strong>{value(day.precipitation_probability_max, "%")}</strong></div>
        <div><span>Precip.</span><strong>{value(day.precipitation_sum, " mm")}</strong></div>
        <div><span>Wind</span><strong>{value(day.wind_speed_10m_max, " km/h")}</strong></div>
      </article>)}</div>
    </section></>}
    </main>
  </>;
}
