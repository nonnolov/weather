"use client";

import { useEffect, useState } from "react";
import { getFloodRisk, type FloodRiskReport } from "../lib/api";
import styles from "./FloodRiskCard.module.css";

type Language = "th" | "en";
const labels = {
  th: {
    title: "ฝนสะสมและความเสี่ยงน้ำท่วม",
    subtitle: "สรุปจากพยากรณ์ฝนรายชั่วโมง · เป็นค่าประมาณจากแบบจำลอง",
    reload: "โหลดใหม่",
    loading: "กำลังโหลดข้อมูลฝนสะสม…",
    failed: "ไม่สามารถโหลดรายงานฝนได้ชั่วคราว",
    unavailable: "ข้อมูลพยากรณ์ช่วง 24 ชั่วโมงไม่พร้อม",
    partial: "ข้อมูลฝนมีช่วงขาดหรือมีชั่วโมงที่ไม่มีค่า ยอดสะสมจึงคำนวณเฉพาะหน้าต่างที่ครบ",
    notAssessed: "ยังไม่ได้จัดระดับความเสี่ยงน้ำท่วม",
    reasons: "ยังไม่มีเกณฑ์ฝนเฉพาะพื้นที่และข้อมูลเหตุการณ์น้ำท่วมย้อนหลังที่ตรวจสอบได้ จึงยังประเมินโอกาสน้ำท่วมไม่ได้",
    source: "ผลนี้ใช้พยากรณ์แบบจำลองเท่านั้น ไม่ใช่ฝนที่ตรวจวัดจริง และไม่ยืนยันว่าจะเกิดน้ำท่วม",
    coverage: "ชั่วโมงที่มีค่าฝนครบ",
    interval: "ช่วงพยากรณ์",
    noWindow: "คำนวณไม่ได้: ข้อมูลในหน้าต่างไม่ครบ",
    windows: "หน้าต่างครบ",
    hour: "ชั่วโมง",
    retrieved: "พยากรณ์ดึงข้อมูลเมื่อ",
  },
  en: {
    title: "Forecast rainfall and flood risk",
    subtitle: "Hourly forecast summary · model estimate",
    reload: "Reload",
    loading: "Loading rainfall summary…",
    failed: "Rainfall report is temporarily unavailable.",
    unavailable: "24-hour forecast data are unavailable.",
    partial: "Rainfall data have gaps; totals use complete windows only.",
    notAssessed: "Flood risk level not assessed",
    reasons: "Validated local rainfall thresholds and historical flood-event evidence are not connected, so flood potential cannot yet be assessed.",
    source: "Forecast-model output only; not measured rainfall and not confirmation that flooding will occur.",
    coverage: "Hours with rainfall values",
    interval: "Forecast period",
    noWindow: "Unavailable: window is incomplete",
    windows: "complete windows",
    hour: "hours",
    retrieved: "Forecast retrieved",
  },
} as const;

const amount = (value: number | null, language: Language) =>
  value === null ? "—" : new Intl.NumberFormat(language === "th" ? "th-TH" : "en-GB", { maximumFractionDigits: 1 }).format(value) + " mm";

export function FloodRiskCard({ locationId, timeZone, language }: { locationId: number; timeZone: string; language: Language }) {
  const [report, setReport] = useState<FloodRiskReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [revision, setRevision] = useState(0);
  const t = labels[language];

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    setLoading(true);
    setFailed(false);
    getFloodRisk(locationId, controller.signal).then((data) => {
      if (!cancelled) setReport(data);
    }).catch(() => {
      if (!cancelled) setFailed(true);
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; controller.abort(); };
  }, [locationId, revision]);

  const data = report?.location_id === locationId ? report : null;
  const stamp = (date: string | null) => date
    ? new Intl.DateTimeFormat(language === "th" ? "th-TH" : "en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone }).format(new Date(date))
    : "—";

  const status = data?.assessment_status === "rainfall_flood_potential"
    ? (language === "th" ? "ฝนพยากรณ์เข้าเกณฑ์เฝ้าระวังน้ำท่วม" : "Forecast rainfall reaches flood-watch screening")
    : data?.assessment_status === "rainfall_below_trigger"
      ? (language === "th" ? "ฝนพยากรณ์ยังไม่เข้าเกณฑ์เฝ้าระวัง" : "Forecast rainfall below screening thresholds")
      : (language === "th" ? "ข้อมูลไม่พอประเมินตามเกณฑ์" : "Insufficient data for screening");
  const reasonLabels: Record<string, string> = language === "th" ? {
    forecast_interval_semantics_unverified: "ยังไม่ยืนยันช่วงสะสมฝนของผู้ให้บริการนี้",
    location_profile_unavailable: "ข้อมูลประเทศหรือจังหวัดยังไม่พร้อมสำหรับเลือกเกณฑ์",
    location_forecast_mismatch: "พื้นที่พยากรณ์ไม่ตรงกับพื้นที่ที่เลือก",
    urban_threshold_scope_unverified: "ยังไม่ยืนยันขอบเขตเมืองสำหรับเลือกเกณฑ์พื้นที่นี้",
    forecast_stale: "พยากรณ์เก่ากว่า 6 ชั่วโมง",
    forecast_retrieval_in_future: "เวลาบันทึกพยากรณ์อยู่ในอนาคต",
    forecast_horizon_incomplete: "ข้อมูลพยากรณ์ 24 ชั่วโมงไม่ครบ",
    hourly_rainfall_threshold_reached: "ฝนรายชั่วโมงเข้าเกณฑ์",
    accumulated_rainfall_threshold_reached: "ฝนสะสม 24 ชั่วโมงเข้าเกณฑ์",
    rainfall_below_screening_thresholds: "ข้อมูลครบและฝนยังไม่ถึงเกณฑ์ แต่ไม่ยืนยันว่าจะไม่มีน้ำท่วม",
  } : {
    forecast_interval_semantics_unverified: "Provider rainfall interval semantics unverified",
    location_profile_unavailable: "Country or province data unavailable for selecting thresholds",
    location_forecast_mismatch: "Forecast does not match selected location",
    urban_threshold_scope_unverified: "Urban threshold boundary not verified",
    forecast_stale: "Forecast older than 6 hours",
    forecast_retrieval_in_future: "Forecast retrieval timestamp is in the future",
    forecast_horizon_incomplete: "24-hour forecast incomplete",
    hourly_rainfall_threshold_reached: "Hourly rainfall threshold reached",
    accumulated_rainfall_threshold_reached: "24-hour rainfall threshold reached",
    rainfall_below_screening_thresholds: "Complete data below thresholds; flooding is still possible",
  };

  return <section className={"card " + styles.panel} aria-labelledby="flood-risk-heading" aria-busy={loading}>
    <div className={styles.heading}>
      <div><h2 id="flood-risk-heading">{t.title}</h2><p>{t.subtitle}</p></div>
      <button type="button" className="utility-button" onClick={() => setRevision((n) => n + 1)} disabled={loading}>{t.reload}</button>
    </div>
    {loading && !data && <p role="status">{t.loading}</p>}
    {failed && <p role="status">{t.failed}</p>}
    {data && <>
      <p className={styles.coverage}>{t.retrieved}: <time dateTime={data.retrieved_at}>{stamp(data.retrieved_at)}</time> · {timeZone} · {data.provider.replaceAll("_", " ")}</p>
      <div className={styles.status}><span>{status}</span></div>
      {data.data_status === "unavailable" ? <p role="status">{t.unavailable}</p> : <>
        {data.data_status === "partial" && <p className={styles.notice} role="status">{t.partial}</p>}
        <p className={styles.coverage}>{t.coverage}: {data.hours_with_precipitation}/{data.hours_expected}</p>
        <dl className={styles.metrics}>{data.rolling_accumulations.map((item) => <div key={item.hours}>
          <dt>{item.hours} {t.hour}</dt>
          <dd>{amount(item.max_accumulation_mm, language)}</dd>
          <small>{item.complete_windows}/{item.expected_windows} {t.windows}</small>
          {item.interval_start && item.interval_end
            ? <small>{stamp(item.interval_start)}–{stamp(item.interval_end)}</small>
            : <small>{t.noWindow}</small>}
        </div>)}</dl>
        <p className={styles.window}>{t.interval}: {stamp(data.forecast_window_start)}–{stamp(data.forecast_window_end)} · {timeZone}</p>
      </>}
      <p className={styles.limitation}>{data.assessment_reason_codes.map((code) => reasonLabels[code] ?? code).join(" · ")}</p>
      {data.trigger_windows.map((window) => <p key={window.hours + window.interval_end}>
        {window.hours} {t.hour}: {amount(window.amount_mm, language)} ≥ {amount(window.threshold_mm, language)}
        {" · "}{stamp(window.interval_start)}–{stamp(window.interval_end)}
      </p>)}
      <p className={styles.limitation}>{language === "th" ? "ประยุกต์เกณฑ์ฝนตรวจวัดของ ปภ. กับพยากรณ์ เป็นการคัดกรองเฝ้าระวัง ยังไม่ผ่านการปรับเทียบกับเหตุการณ์น้ำท่วม และยังไม่รวมระบบระบายน้ำหรือระดับน้ำเดิม" : "DDPM observed-rain screening adapted to forecasts; not calibrated against flood events and excludes drainage and antecedent water."} <a href={data.screening_source_url} target="_blank" rel="noreferrer">{language === "th" ? "แหล่งอ้างอิง" : "Source"}</a></p>
      <p className={styles.source}>{t.source}</p>
    </>}
  </section>;
}
