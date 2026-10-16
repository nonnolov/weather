"use client";
import {useEffect,useMemo,useState} from "react";
import {useLineOnboarding} from "./useLineOnboarding";
import {getLineForecast,setLineLocation,refreshLineForecast} from "../../lib/line";
import {translations,nextHourly,type Language} from "./format";
import {
  ApiError,
  getHealth,
  getLatestForecast,
  getLocations,
  getUserForecast,
  refreshUserForecast,
  setUserLocationFromGps,
  type ForecastRun,
  type Location,
} from "../../lib/api";

type LiffClient = {
  init: (options: { liffId: string }) => Promise<void>;
  isLoggedIn: () => boolean;
  login: (options?: { redirectUri?: string }) => void;
  logout?: () => void;
  getIDToken: () => string | null;
  getAccessToken?: () => string | null;
  isInClient?: () => boolean;
  requestFriendship?: () => Promise<void>;
};

declare global {
  interface Window {
    liff?: LiffClient;
  }
}

export const liffId = process.env.NEXT_PUBLIC_LIFF_ID;

export function useWeatherDashboard() {
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
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [language, setLanguage] = useState<Language>(() => {
    if (typeof window === "undefined") return "th";
    const redirectLanguage = new URLSearchParams(window.location.search).get("weather_lang");
    if (redirectLanguage === "th" || redirectLanguage === "en") return redirectLanguage;
    const saved = window.localStorage.getItem("weather.language");
    return saved === "th" || saved === "en" ? saved : "th";
  });
  const line=useLineOnboarding(language);
  const lineUserId=line.userId;
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
    low: "ต่ำสุด", high: "สูงสุด", loadingSample: "กำลังโหลดพื้นที่ตัวอย่าง",
    forecastUnavailable: "ระบุตำแหน่งได้แล้ว แต่บริการพยากรณ์ขัดข้อง กรุณาลองอีกครั้งภายหลัง",
    cachedForecast: "อัปเดตพยากรณ์ไม่สำเร็จ กำลังแสดงข้อมูลเดิมของพื้นที่นี้ โปรดตรวจเวลาอัปเดตและลองอีกครั้งภายหลัง",
    locationSaveError: "ไม่สามารถบันทึกพื้นที่จากพิกัดได้ กรุณาลองอีกครั้ง"
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
    low: "Low", high: "High", loadingSample: "Loading sample forecast",
    forecastUnavailable: "Location found, but the forecast service is unavailable. Please try again later.",
    cachedForecast: "Forecast refresh failed. Showing saved data for this area; check its update time and retry later.",
    locationSaveError: "Could not save the area for your coordinates. Please try again."
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
      const randomId=typeof crypto.randomUUID==="function"?crypto.randomUUID():Array.from(crypto.getRandomValues(new Uint8Array(16)),byte=>byte.toString(16).padStart(2,"0")).join("");
      id = "browser-" + randomId;
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

  const initializeLiff = line.initialize;

  const activeUserId = lineUserId ?? userId;

  const secureLine=Boolean(lineUserId && line.config?.enabled);
  const readUserForecast=()=>secureLine?getLineForecast():getUserForecast(activeUserId);
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
        let resolvedLocation: Location | null = null;
        try {
          setGpsState("saving");
          const result = await (secureLine?setLineLocation(position.coords.latitude, position.coords.longitude):setUserLocationFromGps(activeUserId, position.coords.latitude, position.coords.longitude));
          resolvedLocation = result.location;
          if(secureLine)await line.refresh();
          setGpsState("forecasting");
          const refresh = await (secureLine?refreshLineForecast():refreshUserForecast(activeUserId));
          const data = await readUserForecast();
          // Publish location and forecast together so old weather never labels a new place.
          setLocation({ ...result.location, timezone: refresh.timezone });
          setForecast(data);
          setGpsState("success");
          setMessage(t.loaded);
        } catch (error) {
          // A refresh failure does not mean GPS/geocoding failed. Read-only recovery
          // must match the newly resolved location and still cover future hours.
          if (resolvedLocation) {
            try {
              const saved = await readUserForecast();
              if (saved.location_id === resolvedLocation.id &&
                  saved.hourly.some(hour => new Date(hour.valid_time).getTime() >= Date.now())) {
                setLocation(resolvedLocation);
                setForecast(saved);
                setGpsState("error");
                setMessage(ux.cachedForecast);
                return;
              }
            } catch {
              // Missing or unavailable saved data leaves the displayed pair intact.
            }
          }
          setGpsState("error");
          setMessage(resolvedLocation ? ux.forecastUnavailable :
            error instanceof ApiError && error.status === 502 ? t.locationUnavailable : ux.locationSaveError);
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

  const summary = forecast ? nextHourly(forecast.hourly) : undefined;

  return {line,mapOpen,setMapOpen,chartTab,setChartTab,health,selectedId,forecast,location,gpsState,message,seedLoading,lineUserId,theme,setTheme,language,setLanguage,t,ux,isGpsBusy,busy,progress,sampleLocations,initializeLiff,handleGps,selectSeedLocation,summary};
}
export type DashboardModel = ReturnType<typeof useWeatherDashboard>;
