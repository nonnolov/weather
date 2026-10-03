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
  refreshUserForecast,
  setUserLocationFromGps,
  type ForecastRun,
  type Location,
} from "../lib/api";

const value = (n: number | null, unit = "") => n === null ? "—" : Math.round(n * 10) / 10 + unit;
const translations = {
  th: { unavailable: "ไม่พร้อมใช้งาน", clear: "ท้องฟ้าแจ่มใส", cloudy: "มีเมฆบางส่วน", fog: "หมอก", drizzle: "ฝนปรอย", rain: "ฝนตก", thunderstorm: "พายุฝนฟ้าคะนอง", weatherCode: "รหัสสภาพอากาศ", monitoring: "ติดตามสภาพอากาศ", dashboard: "แดชบอร์ดพยากรณ์", checking: "กำลังตรวจสอบ", online: "ออนไลน์", offline: "ออฟไลน์", yourLocation: "ตำแหน่งของคุณ", gpsDescription: "ใช้ GPS เพื่อพยากรณ์อากาศในพื้นที่ที่คุณอยู่", detecting: "กำลังค้นหาตำแหน่ง…", useLocation: "ใช้ตำแหน่งของฉัน", seedLocations: "ตำแหน่งทดสอบ", seedDescription: "ใช้สำหรับทดสอบก่อนเปิดใช้งาน GPS", monitoredLocation: "ตำแหน่งที่ติดตาม", noForecast: "ยังไม่มีพยากรณ์อากาศ", allowGps: "อนุญาต GPS เพื่อโหลดพยากรณ์อากาศสำหรับพื้นที่ปัจจุบัน", nextHour: "ชั่วโมงถัดไป", rainChance: "โอกาสฝนตก", wind: "ลม", humidity: "ความชื้น", forecast7: "พยากรณ์ 7 วัน", retrieved: "อัปเดต", precip: "ปริมาณฝน", connectedLine: "เชื่อมต่อ LINE แล้ว", lineUnavailable: "ไม่สามารถเชื่อมต่อ LINE ได้ ขณะนี้ใช้บัญชีในเบราว์เซอร์", gpsUnsupported: "เบราว์เซอร์นี้ไม่รองรับตำแหน่ง GPS", requesting: "กำลังขอตำแหน่งของคุณ…", loaded: "ตรวจพบตำแหน่งและโหลดพยากรณ์แล้ว", locationUnavailable: "บริการระบุตำแหน่งไม่พร้อมใช้งานชั่วคราว", forecastError: "ไม่สามารถโหลดพยากรณ์สำหรับตำแหน่งนี้ได้", permissionDenied: "ไม่ได้รับอนุญาตหรือไม่สามารถระบุตำแหน่งได้", noStored: "ไม่มีพยากรณ์ที่บันทึกไว้สำหรับตำแหน่งนี้", lang: "ภาษา" },
  en: { unavailable: "Unavailable", clear: "Clear sky", cloudy: "Partly cloudy", fog: "Fog", drizzle: "Drizzle", rain: "Rain", thunderstorm: "Thunderstorm", weatherCode: "Weather code", monitoring: "Weather monitoring", dashboard: "Forecast dashboard", checking: "checking", online: "online", offline: "offline", yourLocation: "Your location", gpsDescription: "Use GPS to forecast the exact area you are currently in.", detecting: "Detecting location…", useLocation: "Use my location", seedLocations: "Seed locations", seedDescription: "Fallback for testing before GPS is available.", monitoredLocation: "Monitored location", noForecast: "No forecast loaded", allowGps: "Allow GPS access to load a forecast for your current area.", nextHour: "Next forecast hour", rainChance: "Rain chance", wind: "Wind", humidity: "Humidity", forecast7: "7-day forecast", retrieved: "Retrieved", precip: "Precip.", connectedLine: "Connected to LINE.", lineUnavailable: "LINE connection is unavailable. Local demo identity is still active.", gpsUnsupported: "This browser does not support GPS location.", requesting: "Requesting your location…", loaded: "Location detected and forecast loaded.", locationUnavailable: "Location service is temporarily unavailable.", forecastError: "Could not load the forecast for your location.", permissionDenied: "Location permission was denied or unavailable.", noStored: "No stored forecast is available for this location.", lang: "Language" },
} as const;
type Language = keyof typeof translations;
const weather = (code: number | null, lang: Language) => { const t = translations[lang]; return code === null ? t.unavailable : code === 0 ? t.clear : [1,2,3].includes(code) ? t.cloudy : [45,48].includes(code) ? t.fog : [51,53,55,56,57].includes(code) ? t.drizzle : [61,63,65,66,67,80,81,82].includes(code) ? t.rain : [95,96,99].includes(code) ? t.thunderstorm : t.weatherCode + " " + code; };
const dateLabel = (date: string, lang: Language) => new Intl.DateTimeFormat(lang === "th" ? "th-TH" : "en-GB", { weekday: "short", day: "numeric", month: "short" }).format(new Date(date + "T12:00:00"));
const timeLabel = (date: string, timeZone: string) => new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", timeZone }).format(new Date(date));
const nearestHourly = (hourly: ForecastRun["hourly"]) => hourly.find((hour) => new Date(hour.valid_time).getTime() >= Date.now()) ?? hourly[0];

type LiffClient = {
  init: (options: { liffId: string }) => Promise<void>;
  isLoggedIn: () => boolean;
  login: (options?: { redirectUri?: string }) => void;
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
  const [language, setLanguage] = useState<Language>(() => {
    if (typeof window === "undefined") return "th";
    const redirectLanguage = new URLSearchParams(window.location.search).get("weather_lang");
    if (redirectLanguage === "th" || redirectLanguage === "en") return redirectLanguage;
    const saved = window.localStorage.getItem("weather.language");
    return saved === "th" || saved === "en" ? saved : "th";
  });
  const t = translations[language];

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.has("weather_lang")) {
      params.delete("weather_lang");
      const cleanUrl = window.location.pathname + (params.toString() ? "?" + params.toString() : "") + window.location.hash;
      window.history.replaceState({}, "", cleanUrl);
    }
    document.documentElement.lang = language;
    window.localStorage.setItem("weather.language", language);
  }, [language]);

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
        window.localStorage.setItem("weather.language", language);
        window.liff.login();
        return;
      }
      const token = window.liff.getIDToken();
      if (!token) throw new Error("LINE ID token unavailable.");
      const auth = await authenticateLine(token);
      setLineUserId(auth.external_user_id);
      setMessage(t.connectedLine);
    } catch {
      setMessage(t.lineUnavailable);
    }
  };

  const activeUserId = lineUserId ?? userId;

  const useGps = () => {
    if (!navigator.geolocation) {
      setGpsState("error");
      setMessage(t.gpsUnsupported);
      return;
    }
    setGpsState("locating");
    setMessage(t.requesting);
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          const result = await setUserLocationFromGps(activeUserId, position.coords.latitude, position.coords.longitude);
          setLocation(result.location);
          const refresh = await refreshUserForecast(activeUserId);
          setLocation((current) => current ? { ...current, timezone: refresh.timezone } : current);
          const data = await getUserForecast(activeUserId);
          setForecast(data);
          setGpsState("success");
          setMessage(t.loaded);
        } catch (error) {
          setGpsState("error");
          setMessage(error instanceof ApiError && error.status === 502 ? t.locationUnavailable : t.forecastError);
        }
      },
      () => {
        setGpsState("error");
        setMessage(t.permissionDenied);
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
      setMessage(t.noStored);
    }
  };

  const summary = forecast ? nearestHourly(forecast.hourly) : undefined;

  return <>
    {liffId && <Script src="https://static.line-scdn.net/liff/edge/2/sdk.js" strategy="afterInteractive" onLoad={initializeLiff} />}
    <main className="dashboard-shell">
    <header className="dashboard-header">
      <div><p className="eyebrow">{t.monitoring}</p><h1>{t.dashboard}</h1></div>
      <div>
        <button type="button" onClick={() => setLanguage(language === "th" ? "en" : "th")} aria-label={t.lang}>
          {language === "th" ? "English" : "ไทย"}
        </button>
        <p className={"connection " + health}><span aria-hidden="true" />Backend {health === "loading" ? t.checking : health === "online" ? t.online : t.offline}</p>
      </div>
    </header>

    <section className="card controls" aria-labelledby="location-heading">
      <div>
        <h2 id="location-heading">{t.yourLocation}</h2>
        <p>{t.gpsDescription}</p>
      </div>
      <button onClick={useGps} disabled={gpsState === "locating"}>
        {gpsState === "locating" ? t.detecting : t.useLocation}
      </button>
      {location && <p className="location-meta">{location.subdistrict ?? location.name} · {location.district ?? "—"} · {location.province ?? "—"} · {location.latitude.toFixed(4)}°, {location.longitude.toFixed(4)}°</p>}
      {message && <p aria-live="polite">{message}</p>}
    </section>

    {!location && locations.length > 0 && <section className="card controls">
      <div><h2>{t.seedLocations}</h2><p>{t.seedDescription}</p></div>
      <label className="select-label">{t.monitoredLocation}
        <select value={selectedId ?? ""} onChange={(event) => selectSeedLocation(Number(event.target.value))}>
          {locations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>
    </section>}

    {forecast && location && <p className="location-meta">{location.name} · {location.timezone}</p>}
    {!forecast && <section className="card message"><h2>{t.noForecast}</h2><p>{t.allowGps}</p></section>}

    {forecast && location && <><section className="summary-grid" aria-label={t.forecast7}>
      <article className="card primary-summary"><p className="eyebrow">{t.nextHour}{summary ? " · " + timeLabel(summary.valid_time, location.timezone) : ""}</p><strong>{summary ? value(summary.temperature_2m, "°C") : "—"}</strong><p>{weather(summary?.weather_code ?? null, language)}</p></article>
      <article className="card metric"><span>{t.rainChance}</span><strong>{summary ? value(summary.precipitation_probability, "%") : "—"}</strong></article>
      <article className="card metric"><span>{t.wind}</span><strong>{summary ? value(summary.wind_speed_10m, " km/h") : "—"}</strong></article>
      <article className="card metric"><span>{t.humidity}</span><strong>{summary ? value(summary.relative_humidity_2m, "%") : "—"}</strong></article>
    </section>
    <section className="card forecast-card" aria-labelledby="forecast-heading">
      <div className="section-heading"><div><h2 id="forecast-heading">{t.forecast7}</h2><p>{t.retrieved} {timeLabel(forecast.retrieved_at, location.timezone)} · {forecast.provider.replaceAll("_", " ")}</p></div></div>
      <div className="forecast-list">{forecast.daily.slice(0, 7).map((day) => <article className="forecast-day" key={day.id}>
        <div><strong>{dateLabel(day.forecast_date, language)}</strong><span>{weather(day.weather_code, language)}</span></div>
        <div className="temperatures"><strong>{value(day.temperature_2m_max, "°")}</strong><span>{value(day.temperature_2m_min, "°")}</span></div>
        <div><span>{t.rainChance}</span><strong>{value(day.precipitation_probability_max, "%")}</strong></div>
        <div><span>{t.precip}</span><strong>{value(day.precipitation_sum, " mm")}</strong></div>
        <div><span>{t.wind}</span><strong>{value(day.wind_speed_10m_max, " km/h")}</strong></div>
      </article>)}</div>
    </section></>}
    </main>
  </>;
}
