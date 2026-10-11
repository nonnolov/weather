"use client";

import Script from "next/script";
import { MapPreview } from "./MapPreview";
import { AirQualityCard } from "./AirQualityCard";
import { WeatherArtwork } from "./WeatherArtwork";
import { useEffect, useMemo, useState, type CSSProperties } from "react";
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
  th: { unavailable: "ไม่พร้อมใช้งาน", clear: "ท้องฟ้าแจ่มใส", cloudy: "มีเมฆบางส่วน", fog: "หมอก", drizzle: "ฝนปรอย", rain: "ฝนตก", thunderstorm: "พายุฝนฟ้าคะนอง", weatherCode: "รหัสสภาพอากาศ", monitoring: "ติดตามสภาพอากาศ", dashboard: "แดชบอร์ดพยากรณ์", checking: "กำลังตรวจสอบ", online: "ออนไลน์", offline: "ออฟไลน์", yourLocation: "ตำแหน่งของคุณ", gpsDescription: "ใช้ GPS เพื่อพยากรณ์อากาศในพื้นที่ที่คุณอยู่", detecting: "กำลังค้นหาตำแหน่ง…", useLocation: "ใช้ตำแหน่งของฉัน", seedLocations: "ตำแหน่งทดสอบ", seedDescription: "ใช้สำหรับทดสอบก่อนเปิดใช้งาน GPS", monitoredLocation: "ตำแหน่งที่ติดตาม", noForecast: "ยังไม่มีพยากรณ์อากาศ", allowGps: "อนุญาต GPS เพื่อโหลดพยากรณ์อากาศสำหรับพื้นที่ปัจจุบัน", nextHour: "ชั่วโมงถัดไป", rainChance: "โอกาสฝนตก", maxRainChance: "โอกาสฝนสูงสุด", rainRiskPeriod: "ช่วงเสี่ยงฝน", wind: "ลม", humidity: "ความชื้น", forecast7: "พยากรณ์ 7 วัน", retrieved: "อัปเดต", precip: "ปริมาณฝน", tempTrend: "แนวโน้มอุณหภูมิ", rainTrend: "แนวโน้มฝน", next24: "24 ชั่วโมงถัดไป", minimum: "ต่ำสุด", maximum: "สูงสุด", current: "ขณะนี้", peak: "สูงสุด", rainfall: "ปริมาณฝน", probability: "โอกาส", theme: "ธีม", light: "สว่าง", dark: "มืด", highRisk: "เสี่ยงสูง", connectedLine: "เชื่อมต่อ LINE แล้ว", lineUnavailable: "ไม่สามารถเชื่อมต่อ LINE ได้ ขณะนี้ใช้บัญชีในเบราว์เซอร์", gpsUnsupported: "เบราว์เซอร์นี้ไม่รองรับตำแหน่ง GPS", requesting: "กำลังขอตำแหน่งของคุณ…", loaded: "ตรวจพบตำแหน่งและโหลดพยากรณ์แล้ว", locationUnavailable: "บริการระบุตำแหน่งไม่พร้อมใช้งานชั่วคราว", forecastError: "ไม่สามารถโหลดพยากรณ์สำหรับตำแหน่งนี้ได้", permissionDenied: "ไม่ได้รับอนุญาตหรือไม่สามารถระบุตำแหน่งได้", noStored: "ไม่มีพยากรณ์ที่บันทึกไว้สำหรับตำแหน่งนี้", lang: "ภาษา" },
  en: { unavailable: "Unavailable", clear: "Clear sky", cloudy: "Partly cloudy", fog: "Fog", drizzle: "Drizzle", rain: "Rain", thunderstorm: "Thunderstorm", weatherCode: "Weather code", monitoring: "Weather monitoring", dashboard: "Forecast dashboard", checking: "checking", online: "online", offline: "offline", yourLocation: "Your location", gpsDescription: "Use GPS to forecast the exact area you are currently in.", detecting: "Detecting location…", useLocation: "Use my location", seedLocations: "Seed locations", seedDescription: "Fallback for testing before GPS is available.", monitoredLocation: "Monitored location", noForecast: "No forecast loaded", allowGps: "Allow GPS access to load a forecast for your current area.", nextHour: "Next forecast hour", rainChance: "Rain chance", maxRainChance: "Peak rain chance", rainRiskPeriod: "Rain-risk period", wind: "Wind", humidity: "Humidity", forecast7: "7-day forecast", retrieved: "Retrieved", precip: "Precip.", tempTrend: "Temperature trend", rainTrend: "Rain trend", next24: "Next 24 hours", minimum: "Min", maximum: "Max", current: "Now", peak: "Peak", rainfall: "Rainfall", probability: "Probability", theme: "Theme", light: "Light", dark: "Dark", highRisk: "High risk", connectedLine: "Connected to LINE.", lineUnavailable: "LINE connection is unavailable. Local demo identity is still active.", gpsUnsupported: "This browser does not support GPS location.", requesting: "Requesting your location…", loaded: "Location detected and forecast loaded.", locationUnavailable: "Location service is temporarily unavailable.", forecastError: "Could not load the forecast for your location.", permissionDenied: "Location permission was denied or unavailable.", noStored: "No stored forecast is available for this location.", lang: "Language" },
} as const;
type Language = keyof typeof translations;
const weather = (code: number | null, lang: Language) => { const t = translations[lang]; return code === null ? t.unavailable : code === 0 ? t.clear : [1,2,3].includes(code) ? t.cloudy : [45,48].includes(code) ? t.fog : [51,53,55,56,57].includes(code) ? t.drizzle : [61,63,65,66,67,80,81,82].includes(code) ? t.rain : [95,96,99].includes(code) ? t.thunderstorm : t.weatherCode + " " + code; };
const dateLabel = (date: string, lang: Language) => new Intl.DateTimeFormat(lang === "th" ? "th-TH" : "en-GB", { weekday: "short", day: "numeric", month: "short" }).format(new Date(date + "T12:00:00"));
const timeLabel = (date: string, timeZone: string) => new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", timeZone }).format(new Date(date));
const localDateKey = (date: string, timeZone: string) => new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "2-digit", day: "2-digit", timeZone }).format(new Date(date));
const nearestHourly = (hourly: ForecastRun["hourly"]) => hourly.find((hour) => new Date(hour.valid_time).getTime() >= Date.now()) ?? hourly[0];
const rainRiskForDay = (dailyDate: string, hourly: ForecastRun["hourly"], timeZone: string) => {
  const dayHours = hourly
    .filter((hour) => localDateKey(hour.valid_time, timeZone) === dailyDate && hour.precipitation_probability !== null)
    .sort((a, b) => new Date(a.valid_time).getTime() - new Date(b.valid_time).getTime());

  if (!dayHours.length) return { maxProbability: null, period: null };

  const maxProbability = Math.max(...dayHours.map((hour) => hour.precipitation_probability as number));
  const riskHours = dayHours.filter((hour) => (hour.precipitation_probability ?? 0) >= 50);

  if (!riskHours.length) return { maxProbability, period: null };

  const periods: Array<{ start: string; end: string }> = [];
  for (const hour of riskHours) {
    const previous = periods[periods.length - 1];
    if (!previous) {
      periods.push({ start: hour.valid_time, end: hour.valid_time });
      continue;
    }

    const gap = new Date(hour.valid_time).getTime() - new Date(previous.end).getTime();
    if (gap === 60 * 60 * 1000) {
      previous.end = hour.valid_time;
    } else {
      periods.push({ start: hour.valid_time, end: hour.valid_time });
    }
  }

  return {
    maxProbability,
    period: periods
      .map((item) => timeLabel(item.start, timeZone) + "–" + timeLabel(item.end, timeZone))
      .join(", "),
  };
};

const next24Hours = (hourly: ForecastRun["hourly"]) => {
  return hourly
    .filter((hour) => new Date(hour.valid_time).getTime() >= Date.now())
    .sort((a, b) => new Date(a.valid_time).getTime() - new Date(b.valid_time).getTime())
    .slice(0, 24);
};

const chartPath = (values: Array<number | null>, min: number, max: number, width: number, height: number, top = 18, bottom = 28) => {
  const usableHeight = height - top - bottom;
  return values.map((value, index) => {
    const x = values.length === 1 ? width / 2 : (index / (values.length - 1)) * width;
    const y = value === null ? null : top + (1 - (value - min) / Math.max(max - min, 1)) * usableHeight;
    return y === null ? null : `${index === 0 || values[index - 1] === null ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
  }).filter(Boolean).join(" ");
};

const chartPoint = (value: number, index: number, count: number, min: number, max: number, width: number, height: number, top = 18, bottom = 28) => ({
  cx: count === 1 ? width / 2 : (index / (count - 1)) * width,
  cy: top + (1 - (value - min) / Math.max(max - min, 1)) * (height - top - bottom),
});

/* Plot geometry. The viewBox stays close to the rendered aspect so the stretched
 * SVG keeps curve slopes honest, and every axis label lives in HTML instead of
 * inside the SVG, where preserveAspectRatio="none" would warp the text. */
const CHART_WIDTH = 640;
const CHART_HEIGHT = 300;
const CHART_PAD = 40;
const PLOT_TOP = CHART_PAD;
const PLOT_BOTTOM = CHART_HEIGHT - CHART_PAD;
const RAIN_BAR_MAX = 120;
const gridLines = (width: number) => [0, .5, 1].map((position) => (
  <line key={position} className="chart-grid" x1="0" x2={width} y1={PLOT_TOP + position * (PLOT_BOTTOM - PLOT_TOP)} y2={PLOT_TOP + position * (PLOT_BOTTOM - PLOT_TOP)} />
));

function ChartScale({ labels }: { labels: string[] }) {
  return <div className="chart-scale" aria-hidden="true">
    {labels.map((label, index) => <span key={label} style={{ top: `${(PLOT_TOP + ((PLOT_BOTTOM - PLOT_TOP) * index) / Math.max(labels.length - 1, 1)) / CHART_HEIGHT * 100}%` }}>{label}</span>)}
  </div>;
}

function ChartTimes({ hours, timeZone }: { hours: ForecastRun["hourly"]; timeZone: string }) {
  const ticks = [0, 6, 12, 18, 23].filter((index) => hours[index]);
  const last = ticks[ticks.length - 1];
  return <div className="chart-times" aria-hidden="true">
    {ticks.map((index) => <span key={index} style={{ left: `${(hours.length === 1 ? .5 : index / (hours.length - 1)) * 100}%`, transform: index === 0 ? undefined : index === last ? "translateX(-100%)" : "translateX(-50%)" }}>{timeLabel(hours[index].valid_time, timeZone).slice(0, 2)}</span>)}
  </div>;
}

function TemperatureTrend({ hourly, timeZone, language }: { hourly: ForecastRun["hourly"]; timeZone: string; language: Language }) {
  const hours = next24Hours(hourly);
  const temperatures = hours.map((hour) => hour.temperature_2m);
  const available = temperatures.filter((temperature): temperature is number => temperature !== null);
  if (!available.length) return null;
  const min = Math.floor(Math.min(...available) - 1);
  const max = Math.ceil(Math.max(...available) + 1);
  const peakValue = Math.max(...available);
  const peakIndex = temperatures.findIndex((temperature) => temperature === peakValue);
  const firstValue = temperatures.find((temperature): temperature is number => temperature !== null);
  const firstIndex = temperatures.findIndex((temperature) => temperature !== null);
  const width = CHART_WIDTH;
  const height = CHART_HEIGHT;
  const summary = language === "th"
    ? `แนวโน้มอุณหภูมิ 24 ชั่วโมง ต่ำสุด ${value(Math.min(...available), "°C")} สูงสุด ${value(peakValue, "°C")}`
    : `24-hour temperature trend. Low ${value(Math.min(...available), "°C")}; high ${value(peakValue, "°C")}.`;

  return <section className="chart-card temperature-chart" aria-labelledby="temperature-trend-heading">
    <div className="chart-heading">
      <div><h2 id="temperature-trend-heading">{language === "th" ? "แนวโน้มอุณหภูมิ" : "Temperature trend"}</h2><p>{language === "th" ? "24 ชั่วโมงข้างหน้า" : "Next 24 hours"}</p></div>
      <dl className="chart-stats"><div><dt>{language === "th" ? "ต่ำสุดวันนี้" : "Low today"}</dt><dd>{value(Math.min(...available), "°C")}</dd></div><div><dt>{language === "th" ? "สูงสุดวันนี้" : "High today"}</dt><dd>{value(peakValue, "°C")}</dd></div><div><dt>{language === "th" ? "ช่วงร้อนสุด" : "Warmest"}</dt><dd>{peakIndex >= 0 ? timeLabel(hours[peakIndex].valid_time, timeZone) : "—"}</dd></div></dl>
    </div>
    <div className="chart-body">
      <div className="chart-plot">
        <svg className="trend-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby="temperature-trend-heading temperature-trend-summary" preserveAspectRatio="none">
          <desc id="temperature-trend-summary">{summary}</desc>
          {gridLines(width)}
          <path className="temperature-area" d={`${chartPath(temperatures, min, max, width, height, CHART_PAD, CHART_PAD)} L ${width} ${PLOT_BOTTOM} L 0 ${PLOT_BOTTOM} Z`} />
          <path className="temperature-line" d={chartPath(temperatures, min, max, width, height, CHART_PAD, CHART_PAD)} />
          {firstValue !== undefined && <circle className="current-point" {...chartPoint(firstValue, firstIndex, hours.length, min, max, width, height, CHART_PAD, CHART_PAD)} r="5" />}
          {peakIndex >= 0 && <circle className="peak-point" {...chartPoint(peakValue, peakIndex, hours.length, min, max, width, height, CHART_PAD, CHART_PAD)} r="4" />}
        </svg>
        <ChartScale labels={[value(max, "°"), value((max + min) / 2, "°"), value(min, "°")]} />
      </div>
      <ChartTimes hours={hours} timeZone={timeZone} />
    </div>
    <p className="chart-summary">{summary}</p>
  </section>;
}

function RainTrend({ hourly, timeZone, language }: { hourly: ForecastRun["hourly"]; timeZone: string; language: Language }) {
  const hours = next24Hours(hourly);
  const probabilities = hours.map((hour) => hour.precipitation_probability);
  const rainfall = hours.map((hour) => hour.precipitation);
  const availableProbabilities = probabilities.filter((probability): probability is number => probability !== null);
  const availableRainfall = rainfall.filter((amount): amount is number => amount !== null);
  if (!availableProbabilities.length && !availableRainfall.length) return null;
  const peakProbability = availableProbabilities.length ? Math.max(...availableProbabilities) : 0;
  const peakIndex = probabilities.findIndex((probability) => probability === peakProbability);
  const maxRainfall = Math.max(...availableRainfall, 0.1);
  const width = CHART_WIDTH;
  const height = CHART_HEIGHT;
  const riskHour = peakIndex >= 0 ? timeLabel(hours[peakIndex].valid_time, timeZone) : "—";
  const scaleHint = language === "th"
    ? `เส้น = โอกาสฝน 0–100% · แท่ง = ปริมาณฝน สูงสุด ${value(maxRainfall, " มม.")}`
    : `Line = chance 0–100% · bars = rainfall, max ${value(maxRainfall, " mm")}`;
  const summary = language === "th"
    ? `แนวโน้มฝน 24 ชั่วโมง โอกาสสูงสุด ${value(peakProbability, "%")} เวลา ${riskHour}`
    : `24-hour rain trend. Peak chance ${value(peakProbability, "%")} at ${riskHour}.`;

  return <section className="chart-card rain-chart" aria-labelledby="rain-trend-heading">
    <div className="chart-heading"><div><h2 id="rain-trend-heading">{language === "th" ? "แนวโน้มฝน" : "Rain trend"}</h2><p>{scaleHint}</p></div><div className={"risk-callout" + (peakProbability >= 50 ? " high-risk" : "")}><span>{peakProbability >= 50 ? translations[language].highRisk : language === "th" ? "ช่วงเสี่ยงสูงสุด" : "Peak risk"}</span><strong>{value(peakProbability, "%")}</strong><small>{riskHour}</small></div></div>
    <div className="chart-body">
      <div className="chart-plot">
        <svg className="trend-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby="rain-trend-heading rain-trend-summary" preserveAspectRatio="none">
          <desc id="rain-trend-summary">{summary}</desc>
          {gridLines(width)}
          {rainfall.map((amount, index) => { const barWidth = Math.max(4, width / Math.max(hours.length, 1) - 5); const x = (index / Math.max(hours.length - 1, 1)) * width - barWidth / 2; const barHeight = amount === null ? 0 : (amount / maxRainfall) * RAIN_BAR_MAX; return <rect className="rain-bar" key={index} x={x} y={PLOT_BOTTOM - barHeight} width={barWidth} height={barHeight} rx="2" />; })}
          <path className="rain-line" d={chartPath(probabilities, 0, 100, width, height, CHART_PAD, CHART_PAD)} />
          {peakIndex >= 0 && probabilities[peakIndex] !== null && <circle className="rain-peak-point" {...chartPoint(probabilities[peakIndex], peakIndex, hours.length, 0, 100, width, height, CHART_PAD, CHART_PAD)} r="5" />}
        </svg>
        <ChartScale labels={["100%", "50%", "0%"]} />
      </div>
      <ChartTimes hours={hours} timeZone={timeZone} />
    </div>
    <p className="chart-summary">{summary}</p>
  </section>;
}

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
  const [mapOpen, setMapOpen] = useState(false);
  const [chartTab, setChartTab] = useState<"temperature" | "rain">("temperature");
  const [health, setHealth] = useState<"loading" | "online" | "offline">("loading");
  const [locations, setLocations] = useState<Location[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [forecast, setForecast] = useState<ForecastRun | null>(null);
  const [location, setLocation] = useState<Location | null>(null);
  const [gpsState, setGpsState] = useState<"idle" | "locating" | "saving" | "forecasting" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const [seedLoading, setSeedLoading] = useState(false);
  const [lineUserId, setLineUserId] = useState<string | null>(null);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [language, setLanguage] = useState<Language>(() => {
    if (typeof window === "undefined") return "th";
    const redirectLanguage = new URLSearchParams(window.location.search).get("weather_lang");
    if (redirectLanguage === "th" || redirectLanguage === "en") return redirectLanguage;
    const saved = window.localStorage.getItem("weather.language");
    return saved === "th" || saved === "en" ? saved : "th";
  });
  const t = translations[language];
  const ux = language === "th" ? {
    title: "อากาศวันนี้ ใกล้คุณ", intro: "เตรียมพร้อมก่อนออกจากบ้าน",
    start: "วันนี้อากาศเป็นอย่างไร?", description: "ดูอุณหภูมิ โอกาสฝน และพยากรณ์ 7 วันสำหรับพื้นที่ที่คุณอยู่",
    privacy: "เบราว์เซอร์จะขออนุญาตใช้ตำแหน่งของคุณ", sample: "หรือดูตัวอย่างพยากรณ์",
    choose: "เลือกพื้นที่ตัวอย่าง", locating: "กำลังหาตำแหน่ง", saving: "กำลังระบุพื้นที่",
    forecasting: "กำลังโหลดพยากรณ์", retry: "ลองอีกครั้ง", update: "อัปเดตตำแหน่ง",
    hourly: "พยากรณ์รายชั่วโมง · 24 ชั่วโมงข้างหน้า", source: "ข้อมูลจาก Open-Meteo", error: "โหลดไม่สำเร็จ",
    timeout: "หาตำแหน่งไม่ทันเวลา ลองอีกครั้งในพื้นที่ที่รับสัญญาณ GPS ได้",
    unavailable: "ยังหาตำแหน่งไม่ได้ กรุณาเปิดบริการตำแหน่งแล้วลองอีกครั้ง",
    lineHint: "เปิดผ่าน LINE เพื่อเชื่อมบัญชีสำหรับการแจ้งเตือน", sampleHint: "กำลังดูพื้นที่ตัวอย่าง ไม่ได้เปลี่ยนตำแหน่งของคุณ",
    low: "ต่ำสุด", high: "สูงสุด", loadingSample: "กำลังโหลดพื้นที่ตัวอย่าง"
  } : {
    title: "Weather around you", intro: "Ready for the day ahead",
    start: "What does today look like?", description: "Temperature, rain chances and a 7-day outlook for wherever you are.",
    privacy: "Your browser will ask for permission to use your location.", sample: "Or explore a sample forecast",
    choose: "Choose a sample area", locating: "Finding your location", saving: "Identifying your area",
    forecasting: "Loading your forecast", retry: "Try again", update: "Update location",
    hourly: "Hourly forecast · next 24 hours", source: "Data from Open-Meteo", error: "Could not load",
    timeout: "Location search timed out. Try again where GPS reception is available.",
    unavailable: "Location is unavailable. Enable location services and try again.",
    lineHint: "Open in LINE to connect your account for alerts.", sampleHint: "Sample area; your saved location has not changed.",
    low: "Low", high: "High", loadingSample: "Loading sample forecast"
  };
  const isGpsBusy = ["locating", "saving", "forecasting"].includes(gpsState);
  const busy = isGpsBusy || seedLoading;
  const progress = gpsState === "locating" ? ux.locating : gpsState === "saving" ? ux.saving : ux.forecasting;
  const sampleLocations = locations.filter((item) => ["chon-buri-city", "pattaya", "si-racha", "bang-lamung"].includes(item.slug));

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

  useEffect(() => {
    const savedTheme = window.localStorage.getItem("weather.theme");
    const initialTheme = savedTheme === "light" || savedTheme === "dark"
      ? savedTheme
      : window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    setTheme(initialTheme);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("weather.theme", theme);
  }, [theme]);

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
      // A placeholder lets the first sample be selected without a second change.
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

  const handleGps = () => {
    setSelectedId(null);
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
          setGpsState("saving");
          const result = await setUserLocationFromGps(activeUserId, position.coords.latitude, position.coords.longitude);
          setGpsState("forecasting");
          const refresh = await refreshUserForecast(activeUserId);
          const data = await getUserForecast(activeUserId);
          // Publish location and forecast together so old weather never labels a new place.
          setLocation({ ...result.location, timezone: refresh.timezone });
          setForecast(data);
          setGpsState("success");
          setMessage(t.loaded);
        } catch (error) {
          setGpsState("error");
          setMessage(error instanceof ApiError && error.status === 502 ? t.locationUnavailable : t.forecastError);
        }
      },
      (error) => {
        setGpsState("error");
        setMessage(error.code === 1 ? t.permissionDenied : error.code === 3 ? ux.timeout : ux.unavailable);
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 },
    );
  };

  const selectSeedLocation = async (id: number) => {
    setSelectedId(id);
    setSeedLoading(true);
    setMessage("");
    try {
      const data = await getLatestForecast(id);
      setForecast(data);
      setLocation(locations.find((item) => item.id === id) ?? null);
      setGpsState("idle");
      setMessage(ux.sampleHint);
    } catch {
      setGpsState("error");
      setMessage(t.noStored);
    } finally {
      setSeedLoading(false);
    }
  };

  const summary = forecast ? nearestHourly(forecast.hourly) : undefined;
  const dailyTemperatures = forecast?.daily.flatMap((day) => [day.temperature_2m_min, day.temperature_2m_max]).filter((temperature): temperature is number => temperature !== null) ?? [];
  const dailyMin = dailyTemperatures.length ? Math.min(...dailyTemperatures) : 0;
  const dailyMax = dailyTemperatures.length ? Math.max(...dailyTemperatures) : 1;

  return <>
    {liffId && <Script src="https://static.line-scdn.net/liff/edge/2/sdk.js" strategy="afterInteractive" onLoad={initializeLiff} />}
    <main className={"dashboard-shell" + (forecast && location ? " has-forecast" : "")} aria-busy={busy}>
    <header className="dashboard-header">
      <div className="brand"><span className="brand-mark" aria-hidden="true">W</span><div><h1>Weather</h1><p className="eyebrow">{ux.intro}</p></div></div>
      <div>
        {location && <div className="header-location"><div><span aria-hidden="true">⌖</span><strong>{location.subdistrict ?? location.name} · {location.district ?? "—"} · {location.province ?? "—"}</strong><small>{t.retrieved} {forecast ? timeLabel(forecast.retrieved_at, location.timezone) : "—"} · {location.timezone}</small></div><button className="header-location-action" type="button" onClick={handleGps} disabled={busy}>{isGpsBusy ? "…" : ux.update}</button></div>}
        <div className="header-actions"><button className="utility-button" type="button" onClick={() => setTheme(theme === "light" ? "dark" : "light")} aria-label={theme === "light" ? "Switch to dark theme" : "Switch to light theme"}>{theme === "light" ? "Dark" : "Light"}</button><button className="utility-button" type="button" onClick={() => setLanguage(language === "th" ? "en" : "th")} aria-label={t.lang}>{language === "th" ? "English" : "ไทย"}</button></div>
        {health !== "online" && <p className={"connection " + health}><span aria-hidden="true" />{health === "loading" ? t.checking : t.offline}</p>}
      </div>
    </header>

    {!forecast && <section className="card welcome-card" aria-labelledby="location-heading">
      <div className="welcome-illustration"><WeatherArtwork code={2} /></div>
      <p className="eyebrow">{t.yourLocation}</p>
      <h2 id="location-heading">{ux.start}</h2>
      <p className="welcome-description">{ux.description}</p>
      <button className="gps-primary" type="button" onClick={handleGps} disabled={busy}>
        {isGpsBusy ? <span className="spinner" aria-hidden="true" /> : <span aria-hidden="true">⌖</span>}
        {isGpsBusy ? progress : t.useLocation}
      </button>
      <p className="permission-note">{ux.privacy}</p>
    </section>}

    {busy ? <section className="status-panel" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <div><strong>{seedLoading ? ux.loadingSample : progress}</strong>
      {isGpsBusy && <ol className="progress-steps" aria-label={progress}>
        {[ux.locating, ux.saving, ux.forecasting].map((step, index) => <li key={step} className={index <= ["locating", "saving", "forecasting"].indexOf(gpsState) ? "active" : ""}>{step}</li>)}
      </ol>}</div>
    </section> : message && <div className={"status-panel" + (gpsState === "error" ? " status-error" : "")} role={gpsState === "error" ? "alert" : "status"}>
      <p>{message === t.lineUnavailable ? ux.lineHint : message}</p>
      {gpsState === "error" && <button type="button" className="retry-button" onClick={() => selectedId !== null ? selectSeedLocation(selectedId) : handleGps()}>{ux.retry}</button>}
    </div>}

    {sampleLocations.length > 0 && <details className="sample-picker">
      <summary>{ux.sample}</summary>
      <label className="select-label">{ux.choose}
        <select value={selectedId ?? ""} disabled={busy} onChange={(event) => selectSeedLocation(Number(event.target.value))}>
          <option value="" disabled>{ux.choose}</option>
          {sampleLocations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>
    </details>}

    {forecast && location && <div className="forecast-layout"><section className="summary-grid" aria-label={t.forecast7}>
      <article className="card primary-summary">
        <div className="weather-hero-copy">
          <p className="eyebrow">{t.nextHour}{summary ? " · " + timeLabel(summary.valid_time, location.timezone) : ""}</p>
          <strong className="hero-temperature">{summary ? value(summary.temperature_2m, "°") : "—"}</strong>
          <p className="hero-condition">{weather(summary?.weather_code ?? null, language)}</p>
          <p className="hero-outlook">{language === "th" ? "โอกาสฝน " : "Rain chance "}{summary ? value(summary.precipitation_probability, "%") : "—"} · {language === "th" ? "พยากรณ์สำหรับพื้นที่ของคุณ" : "Your local outlook"}</p>
        </div>
        <div className="hero-art"><WeatherArtwork code={summary?.weather_code ?? null} compact /></div>
        <div className="hero-actions"><button className="gps-primary" type="button" onClick={handleGps} disabled={busy}>{isGpsBusy ? progress : ux.update}</button><button className="map-button" type="button" onClick={() => setMapOpen(true)}>{language === "th" ? "ดูแผนที่" : "View map"}</button></div>
      </article>
      <article className="card metric rain-probability"><span>{t.rainChance}</span><strong>{summary ? value(summary.precipitation_probability, "%") : "—"}</strong></article>
      <article className="card metric rainfall"><span>{t.precip} · {summary ? timeLabel(summary.valid_time, location.timezone) : "—"}</span><strong>{summary ? value(summary.precipitation, language === "th" ? " มม." : " mm") : "—"}</strong></article>
      <article className="card metric"><span>{t.wind}</span><strong>{summary ? value(summary.wind_speed_10m, " km/h") : "—"}</strong></article>
      <article className="card metric"><span>{t.humidity}</span><strong>{summary ? value(summary.relative_humidity_2m, "%") : "—"}</strong></article>
    </section>
    <AirQualityCard key={location.id} locationId={location.id} timeZone={location.timezone} language={language} />
    <section className="line-panel" aria-label="LINE"><span className={"line-dot" + (lineUserId ? " connected" : "")} aria-hidden="true" /><div><h2>{lineUserId ? t.connectedLine : language === "th" ? "การเชื่อมต่อ LINE" : "LINE connection"}</h2><p>{lineUserId ? (language === "th" ? "แจ้งเตือนตามเงื่อนไขของระบบ การเปิดดูหน้าเว็บหรือแผนที่ไม่ส่งข้อความ" : "Alerts follow the existing policy. Viewing the dashboard or map does not send a message.") : ux.lineHint}</p></div></section>
    <div className="chart-switcher"><div className="chart-tabs" role="group" aria-label={language === "th" ? "เลือกกราฟ" : "Choose chart"}><button type="button" aria-pressed={chartTab === "temperature"} onClick={() => setChartTab("temperature")}>{t.tempTrend}</button><button type="button" aria-pressed={chartTab === "rain"} onClick={() => setChartTab("rain")}>{t.rainTrend}</button></div>{chartTab === "temperature" ? <TemperatureTrend hourly={forecast.hourly} timeZone={location.timezone} language={language} /> : <RainTrend hourly={forecast.hourly} timeZone={location.timezone} language={language} />}</div>
    <section className="card hourly-card" aria-labelledby="hourly-heading">
      <div className="section-heading"><h2 id="hourly-heading">{ux.hourly}</h2></div>
      <div className="hourly-list">{next24Hours(forecast.hourly).map((hour) => <article key={hour.id}>
        <time dateTime={hour.valid_time}>{timeLabel(hour.valid_time, location.timezone)}</time>
        <WeatherArtwork code={hour.weather_code} compact /><strong>{value(hour.temperature_2m, "°")}</strong>
        <span>{value(hour.precipitation_probability, "%")}</span>
        <small>{t.rainChance}</small><small>{value(hour.precipitation, language === "th" ? " มม." : " mm")}</small>
      </article>)}</div>
    </section>
    <section className="forecast-card" aria-labelledby="forecast-heading">
      <div className="section-heading"><div><h2 id="forecast-heading">{t.forecast7}</h2><p>{t.retrieved} {timeLabel(forecast.retrieved_at, location.timezone)} · {forecast.provider.replaceAll("_", " ")}</p></div></div>
      <div className="forecast-list">{forecast.daily.slice(0, 7).map((day) => {
        const rainRisk = rainRiskForDay(day.forecast_date, forecast.hourly, location.timezone);
        const rangeStart = day.temperature_2m_min === null ? 0 : ((day.temperature_2m_min - dailyMin) / Math.max(dailyMax - dailyMin, 1)) * 100;
        const rangeWidth = day.temperature_2m_min === null || day.temperature_2m_max === null ? 0 : ((day.temperature_2m_max - day.temperature_2m_min) / Math.max(dailyMax - dailyMin, 1)) * 100;
        return <article className="forecast-day" key={day.id}>
          <div className="daily-condition"><WeatherArtwork code={day.weather_code} compact /><strong>{dateLabel(day.forecast_date, language)}</strong><span>{weather(day.weather_code, language)}</span></div>
          <div className="temperatures"><span>{value(day.temperature_2m_min, "°")}</span><div className="temperature-range" style={{ "--range-start": `${rangeStart}%`, "--range-width": `${rangeWidth}%` } as CSSProperties} aria-label={`${value(day.temperature_2m_min, "°")} to ${value(day.temperature_2m_max, "°")}`} /><strong>{value(day.temperature_2m_max, "°")}</strong></div>
          <div className="daily-rain-probability"><span>{t.maxRainChance}</span><strong>{value(rainRisk.maxProbability, "%")}</strong></div>
          <div><span>{t.rainRiskPeriod}</span><strong>{rainRisk.period ?? "—"}</strong></div>
          <div className="daily-rainfall"><span>{t.precip}</span><strong>{value(day.precipitation_sum, " mm")}</strong></div>
          <div><span>{t.wind}</span><strong>{value(day.wind_speed_10m_max, " km/h")}</strong></div>
        </article>;
      })}</div>
    </section></div>}
    <footer className="dashboard-footer"><span>{ux.source}</span><span>{lineUserId ? t.connectedLine : ux.lineHint}</span></footer>
    </main>
    {mapOpen && location && <MapPreview location={location} language={language} onClose={() => setMapOpen(false)} />}
  </>;
}