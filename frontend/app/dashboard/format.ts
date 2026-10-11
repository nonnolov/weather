import type { ForecastRun } from "../../lib/api";
export const value = (n: number | null | undefined, unit = "") => n == null || !Number.isFinite(n) ? "—" : Math.round(n * 10) / 10 + unit;
export const translations = {
  th: { unavailable: "ไม่พร้อมใช้งาน", clear: "ท้องฟ้าแจ่มใส", cloudy: "มีเมฆบางส่วน", fog: "หมอก", drizzle: "ฝนปรอย", rain: "ฝนตก", thunderstorm: "พายุฝนฟ้าคะนอง", weatherCode: "รหัสสภาพอากาศ", monitoring: "ติดตามสภาพอากาศ", dashboard: "แดชบอร์ดพยากรณ์", checking: "กำลังตรวจสอบ", online: "ออนไลน์", offline: "ออฟไลน์", yourLocation: "ตำแหน่งของคุณ", gpsDescription: "ใช้ GPS เพื่อพยากรณ์อากาศในพื้นที่ที่คุณอยู่", detecting: "กำลังค้นหาตำแหน่ง…", useLocation: "ใช้ตำแหน่งของฉัน", seedLocations: "ตำแหน่งทดสอบ", seedDescription: "ใช้สำหรับทดสอบก่อนเปิดใช้งาน GPS", monitoredLocation: "ตำแหน่งที่ติดตาม", noForecast: "ยังไม่มีพยากรณ์อากาศ", allowGps: "อนุญาต GPS เพื่อโหลดพยากรณ์อากาศสำหรับพื้นที่ปัจจุบัน", nextHour: "ชั่วโมงถัดไป", rainChance: "โอกาสฝนตก", maxRainChance: "โอกาสฝนสูงสุด", rainRiskPeriod: "ช่วงเสี่ยงฝน", wind: "ลม", humidity: "ความชื้น", forecast7: "พยากรณ์ 7 วัน", retrieved: "อัปเดต", precip: "ปริมาณฝน", tempTrend: "แนวโน้มอุณหภูมิ", rainTrend: "แนวโน้มฝน", next24: "24 ชั่วโมงถัดไป", minimum: "ต่ำสุด", maximum: "สูงสุด", current: "ขณะนี้", peak: "สูงสุด", rainfall: "ปริมาณฝน", probability: "โอกาส", theme: "ธีม", light: "สว่าง", dark: "มืด", highRisk: "เสี่ยงสูง", connectedLine: "เชื่อมต่อ LINE แล้ว", lineUnavailable: "ไม่สามารถเชื่อมต่อ LINE ได้ ขณะนี้ใช้บัญชีในเบราว์เซอร์", gpsUnsupported: "เบราว์เซอร์นี้ไม่รองรับตำแหน่ง GPS", requesting: "กำลังขอตำแหน่งของคุณ…", loaded: "ตรวจพบตำแหน่งและโหลดพยากรณ์แล้ว", locationUnavailable: "บริการระบุตำแหน่งไม่พร้อมใช้งานชั่วคราว", forecastError: "ไม่สามารถโหลดพยากรณ์สำหรับตำแหน่งนี้ได้", permissionDenied: "ไม่ได้รับอนุญาตหรือไม่สามารถระบุตำแหน่งได้", noStored: "ไม่มีพยากรณ์ที่บันทึกไว้สำหรับตำแหน่งนี้", lang: "ภาษา" },
  en: { unavailable: "Unavailable", clear: "Clear sky", cloudy: "Partly cloudy", fog: "Fog", drizzle: "Drizzle", rain: "Rain", thunderstorm: "Thunderstorm", weatherCode: "Weather code", monitoring: "Weather monitoring", dashboard: "Forecast dashboard", checking: "checking", online: "online", offline: "offline", yourLocation: "Your location", gpsDescription: "Use GPS to forecast the exact area you are currently in.", detecting: "Detecting location…", useLocation: "Use my location", seedLocations: "Seed locations", seedDescription: "Fallback for testing before GPS is available.", monitoredLocation: "Monitored location", noForecast: "No forecast loaded", allowGps: "Allow GPS access to load a forecast for your current area.", nextHour: "Next forecast hour", rainChance: "Rain chance", maxRainChance: "Peak rain chance", rainRiskPeriod: "Rain-risk period", wind: "Wind", humidity: "Humidity", forecast7: "7-day forecast", retrieved: "Retrieved", precip: "Precip.", tempTrend: "Temperature trend", rainTrend: "Rain trend", next24: "Next 24 hours", minimum: "Min", maximum: "Max", current: "Now", peak: "Peak", rainfall: "Rainfall", probability: "Probability", theme: "Theme", light: "Light", dark: "Dark", highRisk: "High risk", connectedLine: "Connected to LINE.", lineUnavailable: "LINE connection is unavailable. Local demo identity is still active.", gpsUnsupported: "This browser does not support GPS location.", requesting: "Requesting your location…", loaded: "Location detected and forecast loaded.", locationUnavailable: "Location service is temporarily unavailable.", forecastError: "Could not load the forecast for your location.", permissionDenied: "Location permission was denied or unavailable.", noStored: "No stored forecast is available for this location.", lang: "Language" },
} as const;
export type Language = keyof typeof translations;
export const weather = (code: number | null, lang: Language) => { const t = translations[lang]; return code === null ? t.unavailable : code === 0 ? t.clear : [1,2,3].includes(code) ? t.cloudy : [45,48].includes(code) ? t.fog : [51,53,55,56,57].includes(code) ? t.drizzle : [61,63,65,66,67,80,81,82].includes(code) ? t.rain : [95,96,99].includes(code) ? t.thunderstorm : t.weatherCode + " " + code; };
export const dateLabel = (date: string, lang: Language) => new Intl.DateTimeFormat(lang === "th" ? "th-TH" : "en-GB", { weekday: "short", day: "numeric", month: "short" }).format(new Date(date + "T12:00:00"));
export const timeLabel = (date: string, timeZone: string) => new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", timeZone }).format(new Date(date));
const localDateKey = (date: string, timeZone: string) => new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "2-digit", day: "2-digit", timeZone }).format(new Date(date));
export const nearestHourly = (hourly: ForecastRun["hourly"]) => hourly.find((hour) => new Date(hour.valid_time).getTime() >= Date.now()) ?? hourly[0];
export const rainRiskForDay = (dailyDate: string, hourly: ForecastRun["hourly"], timeZone: string) => {
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

export const next24Hours = (hourly: ForecastRun["hourly"]) => {
  return hourly
    .filter((hour) => new Date(hour.valid_time).getTime() >= Date.now())
    .sort((a, b) => new Date(a.valid_time).getTime() - new Date(b.valid_time).getTime())
    .slice(0, 24);
};
