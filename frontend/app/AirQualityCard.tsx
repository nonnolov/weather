"use client";
import { useEffect, useState } from "react";
import { getAirQuality, type AirQualityReport } from "../lib/api";
import {UiIcon} from "./dashboard/UiIcon";
import styles from "./AirQualityCard.module.css";

const labels: Record<string, [string, string]> = {
  good: ["ดี", "Good"], fair: ["พอใช้", "Fair"], moderate: ["ปานกลาง", "Moderate"],
  poor: ["แย่", "Poor"], very_poor: ["แย่มาก", "Very poor"],
  extremely_poor: ["แย่รุนแรง", "Extremely poor"],
};
const show = (n: number | null | undefined) => n == null ? "—" : n.toFixed(1);
export function AirQualityCard({ locationId, timeZone, language }: { locationId: number; timeZone: string; language: "th" | "en" }) {
  const [result, setResult] = useState<AirQualityReport | null>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const th = language === "th";
  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    setLoading(true);
    setFailed(false);
    async function load() {
      try {
        const data = await getAirQuality(locationId, controller.signal);
        if (!cancelled) { setResult(data); setFailed(false); }
      } catch {
        if (!cancelled) setFailed(true);
      } finally { if (!cancelled) setLoading(false); }
    }
    void load();
    const timer = window.setInterval(() => { void load(); }, 600000);
    return () => { cancelled = true; controller.abort(); window.clearInterval(timer); };
  }, [locationId, revision]);
  const data = result?.location_id === locationId ? result : null;
  const unavailable = failed || data?.status === "unavailable";
  const stamp = (time: string) => new Intl.DateTimeFormat(th ? "th-TH" : "en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone }).format(new Date(time));
  const category = data?.current?.category;
  const hours = data?.hourly ?? [];
  const hasTrend = hours.filter(row => row.pm25 !== null).length >= 2;
  const max = Math.max(1, ...hours.map(row => row.pm25 ?? 0));
  return <section className={"card " + styles.panel} aria-labelledby="air-quality-heading" aria-busy={loading}>
    <div className={styles.heading}><div><h2 id="air-quality-heading"><UiIcon name="air" />{th ? "คุณภาพอากาศ PM2.5" : "PM2.5 & air quality"}</h2><p>{th ? "ค่าประมาณจากแบบจำลอง · ไม่ใช่ค่าตรวจวัด ณ จุดจริง" : "Model estimate · not an at-point measurement"}</p></div>
      <button type="button" className="utility-button" onClick={() => setRevision(n => n + 1)} disabled={loading}>{th ? "โหลดใหม่" : "Reload"}</button></div>
    {loading && !data && <p role="status">{th ? "กำลังโหลดข้อมูลคุณภาพอากาศ…" : "Loading air quality…"}</p>}
    {unavailable && <p role="status">{th ? "ข้อมูลคุณภาพอากาศไม่พร้อมใช้งานชั่วคราว" : "Air quality is temporarily unavailable."}</p>}
    {data && !unavailable && <>
      {(data.stale || data.status === "missing") && <p className={styles.notice} role="status">{data.stale ? (th ? "ข้อมูลเดิม: การอัปเดตล่าช้าหรือล้มเหลว" : "Older data: refresh delayed or failed.") : (th ? "ไม่มีค่าครบสำหรับชั่วโมงปัจจุบัน" : "Current-hour data are missing.")}</p>}
      <div className={styles.metrics}><div><span>PM2.5</span><p>{show(data.current?.pm25)} <small>µg/m³</small></p></div>
        <div className={styles.aqi}><span>European AQI</span><p>{show(data.current?.aqi)}</p><span className={styles.badge} data-category={category ?? undefined}>{category ? labels[category]?.[th ? 0 : 1] ?? "—" : "—"}</span></div></div>
      <details className={styles.info}><summary>{th ? "ข้อมูลแบบจำลองและเวลาการอัปเดต" : "Model details & update time"}</summary><p>{th ? "AQI ใช้เกณฑ์ยุโรป ไม่ใช่ AQI ไทย และรวมมลพิษหลายชนิด" : "European AQI, not Thai AQI; includes several pollutants."}</p>
      {data.current && <p>{th ? "เวลาของค่าแบบจำลอง" : "Model valid time"}: <time dateTime={data.current.valid_time}>{stamp(data.current.valid_time)}</time> · {timeZone}</p>}
      {data.retrieved_at && <p>{th ? "ดึงข้อมูลเมื่อ" : "Retrieved"}: <time dateTime={data.retrieved_at}>{stamp(data.retrieved_at)}</time></p>}
      <details className={styles.trend}><summary>{th ? "แนวโน้มแบบจำลอง 24 ชั่วโมง" : "24-hour model outlook"}</summary>
        {hasTrend ? <><div className={styles.bars} aria-hidden="true">{hours.map(row => <span key={row.valid_time} className={row.pm25 === null ? styles.gap : styles.bar} style={{ height: row.pm25 === null ? "4px" : Math.max(2, row.pm25 / max * 80) + "px" }} />)}</div>
          <div className={styles.table}><table><caption>{th ? "ผลลัพธ์รายชั่วโมงจากแบบจำลองต้นทางความถี่ 3 ชั่วโมง" : "Hourly output from a model with 3-hour native resolution"}</caption><thead><tr><th>{th ? "เวลา" : "Time"}</th><th>PM2.5 (µg/m³)</th><th>European AQI</th></tr></thead><tbody>{hours.map(row => <tr key={row.valid_time}><td>{stamp(row.valid_time)}</td><td>{show(row.pm25)}</td><td>{show(row.aqi)}</td></tr>)}</tbody></table></div></> : <p>{th ? "ข้อมูลยังไม่พอแสดงแนวโน้ม" : "Insufficient data for an outlook."}</p>}
      </details></details>
    </>}
    <p className={styles.source}>{th ? "แหล่งข้อมูล" : "Source"}: <a href="https://open-meteo.com/en/docs/air-quality-api" target="_blank" rel="noreferrer">Open-Meteo</a> · <a href="https://ads.atmosphere.copernicus.eu/datasets/cams-global-atmospheric-composition-forecasts" target="_blank" rel="noreferrer">CAMS Global</a> · {th ? "แบบจำลองกริดประมาณ 45 กม." : "~45 km model grid"}</p>
  </section>;
}
