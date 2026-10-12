"use client";
import { useEffect, useRef } from "react";
import type { Location } from "../lib/api";

export function MapPreview({ location, language, onClose }: { location: Location; language: "th" | "en"; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const th = language === "th";
  useEffect(() => {
    const element = dialog.current;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    element?.showModal();
    return () => { element?.close(); document.body.style.overflow = overflow; };
  }, []);
  return <dialog ref={dialog} className="map-dialog" onCancel={onClose} aria-labelledby="map-title">
    <header className="map-header"><button type="button" className="map-button" onClick={onClose}>{th ? "← กลับหน้า Dashboard" : "← Back to Dashboard"}</button><span>Weather / Map</span></header>
    <div className="map-content"><p className="eyebrow">{th ? "พื้นที่ที่เลือก" : "Selected area"}</p><h1 id="map-title">{location.subdistrict ?? location.name}</h1><p>{[location.district, location.province].filter(Boolean).join(" · ")}</p>
    <section className="map-unavailable"><span className="map-outline" aria-hidden="true">⌖</span><h2>{th ? "แผนที่ยังไม่เปิดใช้งาน" : "Map is not available yet"}</h2><p>{th ? "กำลังเตรียมแผนที่และชั้นเรดาร์ฝน คุณสามารถกลับไปดูพยากรณ์ได้ตามปกติ" : "The map and rain radar are planned. Your weather forecast remains available on the dashboard."}</p><span className="planned-badge">{th ? "เรดาร์ฝน · ยังไม่เปิดใช้งาน" : "Rain radar · not available yet"}</span></section></div>
  </dialog>;
}
