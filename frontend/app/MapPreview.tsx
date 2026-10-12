"use client";
import dynamic from "next/dynamic";
import {useEffect,useRef,useState} from "react";
import type {Location} from "../lib/api";
import {useRadar} from "./map/useRadar";
import type {CoverageState,LayerState} from "./map/MapCanvas";
const MapCanvas=dynamic(()=>import("./map/MapCanvas").then(module=>module.MapCanvas),{ssr:false,loading:()=> <p className="map-loading" role="status">กำลังเปิดแผนที่ / Loading map…</p>});
export function MapPreview({location,language,onClose,isSample=false}:{location:Location;language:"th"|"en";onClose:()=>void;isSample?:boolean}) {
 const dialog=useRef<HTMLDialogElement>(null),th=language==="th";
 const {manifest,loading,error,retry}=useRadar();
 const [radarOn,setRadarOn]=useState(true),[coverageOn,setCoverageOn]=useState(false);
 const [index,setIndex]=useState(-1),[playing,setPlaying]=useState(false);
 const [locateTick,setLocateTick]=useState(0),[retryTick,setRetryTick]=useState(0);
 const [baseState,setBaseState]=useState<LayerState>("loading"),[radarState,setRadarState]=useState<LayerState>("loading");
 const [coverage,setCoverage]=useState<CoverageState>("checking"),[cadence,setCadence]=useState(8000);
 const frames=manifest?.frames??[],selected=index<0?frames.length-1:Math.min(index,frames.length-1),frame=frames[selected];
 const valid=Number.isFinite(location.latitude) && Number.isFinite(location.longitude) && Math.abs(location.latitude)<=85.0511 && Math.abs(location.longitude)<=180;
 const pointLabel=isSample?(th?"พื้นที่ตัวอย่างที่เลือก":"Selected sample area"):(th?"พื้นที่ที่ใช้พยากรณ์":"Forecast location");
 const stamp=(time:number)=>new Intl.DateTimeFormat(th?"th-TH":"en-GB",{day:"numeric",month:"short",hour:"2-digit",minute:"2-digit",timeZone:location.timezone}).format(new Date(time*1000));
 useEffect(()=>{
  const element=dialog.current,overflow=document.body.style.overflow,previousFocus=document.activeElement;
  document.body.style.overflow="hidden";element?.showModal();
  return ()=>{element?.close();document.body.style.overflow=overflow;if(previousFocus instanceof HTMLElement && previousFocus.isConnected)previousFocus.focus({preventScroll:true});};
 },[]);
 useEffect(()=>{setIndex(-1);setPlaying(false);},[manifest?.generated]);
 useEffect(()=>{
  const stop=()=>{if(document.hidden)setPlaying(false);};
  document.addEventListener("visibilitychange",stop);
  return ()=>document.removeEventListener("visibilitychange",stop);
 },[]);
 useEffect(()=>{
  if(!playing || !radarOn || frames.length<2 || manifest?.stale)return;
  const timer=setInterval(()=>{if(radarState!=="loading")setIndex(value=>value<0?0:(value+1)%frames.length);},cadence);
  return ()=>clearInterval(timer);
 },[playing,radarOn,frames.length,cadence,radarState,manifest?.stale]);
 const refresh=()=>{setPlaying(false);retry();setRetryTick(value=>value+1);};
 return <dialog ref={dialog} className="map-dialog" onCancel={event=>{event.preventDefault();onClose();}} aria-labelledby="map-title">
  <header className="map-header"><button className="map-button" type="button" onClick={onClose}>{th?"← กลับ Dashboard":"← Back to Dashboard"}</button><div className="map-heading"><p className="eyebrow">{pointLabel}</p><h1 id="map-title">{[location.subdistrict??location.name,location.district,location.province].filter(Boolean).join(" · ")}</h1></div></header>
  <section className="map-workspace">
   {valid?<MapCanvas location={location} language={language} host={manifest?.host} frame={frame} radarOn={radarOn} coverageOn={coverageOn} locateTick={locateTick} retryTick={retryTick} pointLabel={pointLabel} onBase={setBaseState} onRadar={setRadarState} onCoverage={setCoverage} onCadence={setCadence}/>:<p className="map-loading" role="status">{th?"พื้นที่นี้ไม่มีพิกัดที่แสดงบนแผนที่ได้":"This area has no usable map coordinates."}</p>}
   <div className="map-toolbar"><button className="utility-button" type="button" disabled={!manifest||!valid} aria-pressed={radarOn} onClick={()=>{setRadarOn(value=>!value);setPlaying(false);}}>{th?"เรดาร์ฝน":"Rain radar"} <span className={"map-switch"+(radarOn&&manifest?" enabled":"")} aria-hidden="true"/></button><button className="utility-button" type="button" disabled={!valid} onClick={()=>setLocateTick(value=>value+1)}>{th?"⌖ กลับพื้นที่นี้":"⌖ Centre on area"}</button><button className="utility-button" type="button" disabled={loading} onClick={refresh}>{th?"โหลดใหม่":"Reload"}</button></div>
   {baseState!=="ready"&&valid&&<p className="map-base-status" role="status">{baseState==="loading"?(th?"กำลังโหลดแผนที่…":"Loading map…"):(th?"แผนที่บางส่วนโหลดไม่สำเร็จ ลองโหลดใหม่":"Map tiles could not load. Try Reload.")}</p>}
  </section>
  <footer className="map-radar-panel">
   <div className="radar-heading"><div><h2>{th?"ภาพเรดาร์ฝนย้อนหลัง":"Past rain radar"}</h2><p className="radar-time">{frame?<time dateTime={new Date(frame.time*1000).toISOString()}>{stamp(frame.time)} · {location.timezone}</time>:(th?"ยังไม่มีภาพเรดาร์":"No radar frame available")}</p></div><span className="radar-state" role="status">{loading?(th?"กำลังโหลดข้อมูล…":"Loading metadata…"):error?(th?"เรดาร์ไม่พร้อมใช้งาน":"Radar unavailable"):!radarOn?(th?"ปิดชั้นเรดาร์":"Radar layer off"):radarState==="loading"?(th?"กำลังโหลดภาพ…":"Loading frame…"):radarState==="error"||radarState==="partial"?(th?"ภาพบางส่วนโหลดไม่ได้":"Some radar tiles failed"):(th?"ภาพย้อนหลัง":"Historical frame")}</span></div>
   {(error||manifest?.stale)&&<p className="map-warning" role="status">{error?(th?"ข้อมูลเรดาร์ไม่พร้อมใช้งาน แผนที่ยังเปิดดูได้":"Radar is unavailable; the base map remains usable."):(th?"ภาพเรดาร์อัปเดตล่าช้า โปรดตรวจเวลาภาพ":"Radar updates are delayed. Check the frame time.")}</p>}
   <div className="radar-timeline"><button type="button" className="utility-button" disabled={!radarOn||frames.length<2||manifest?.stale||!valid} aria-pressed={playing} onClick={()=>setPlaying(value=>!value)}>{playing?(th?"❚❚ หยุด":"❚❚ Pause"):(th?"▶ เล่น":"▶ Play")}</button><div className="radar-scrubber"><input type="range" min="0" max={Math.max(0,frames.length-1)} value={Math.max(0,selected)} disabled={!radarOn||!frames.length||!valid} aria-label={th?"เลือกเวลาภาพเรดาร์":"Select radar frame time"} aria-valuetext={frame?stamp(frame.time):undefined} onChange={event=>{setPlaying(false);setIndex(Number(event.target.value));}}/><div className="radar-range-labels"><span>{frames.length?stamp(frames[0].time):"—"}</span><span>{frames.length?stamp(frames.at(-1)!.time):"—"}</span></div></div></div>
   <div className="radar-details"><label className="coverage-toggle"><input type="checkbox" checked={coverageOn} disabled={!manifest||!radarOn||!valid} onChange={event=>setCoverageOn(event.target.checked)}/>{th?"แสดงพื้นที่ไม่มีข้อมูล (สีเทา)":"Show areas without coverage (grey)"}</label><span className="radar-legend"><i style={{background:"#88ddee"}}/><i style={{background:"#005588"}}/><i style={{background:"#ff4400"}}/>{th?"สัญญาณสะท้อน: อ่อน → แรง":"Radar echoes: weak → strong"}</span></div>
   <p className="map-data-note">{coverage==="uncovered"?(th?"จุดนี้อยู่นอกขอบเขตข้อมูลเรดาร์ที่แจ้งไว้ · ":"This point is outside the reported coverage · "):coverage==="unknown"?(th?"ตรวจขอบเขตข้อมูลของจุดนี้ไม่ได้ · ":"Coverage at this point could not be verified · "):""}{th?"บริเวณไม่มีสีอาจไม่มีฝนหรือไม่มีข้อมูล ภาพนี้ไม่ใช่พยากรณ์ล่วงหน้า":"A blank area may mean no rain or no data. These frames are not future forecasts."}</p>
   <p className="map-source">{th?"เวลาคือเวลารวมภาพของหลายสถานี · ซูมเข้าไม่ได้เพิ่มความละเอียดเรดาร์":"Times refer to composite frames · Zooming in does not increase radar detail"} · <a href="https://www.rainviewer.com/" target="_blank" rel="noreferrer">Weather data by RainViewer</a></p>
  </footer>
 </dialog>;
}
