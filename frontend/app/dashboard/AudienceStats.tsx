"use client";
import {useEffect,useState} from "react";
import {apiUrl} from "../../lib/api";
import type {Language} from "./format";

type Counts={line_accounts:number;website_visitors:number};
const visitorKey="weather.audience.visitor.v1";
const uuid4=/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
function visitorId(){
 try{
  let id=window.localStorage.getItem(visitorKey);
  if(!id||!uuid4.test(id)){
   const bytes=crypto.getRandomValues(new Uint8Array(16));
   bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
   const hex=Array.from(bytes,byte=>byte.toString(16).padStart(2,"0")).join("");
   id=[hex.slice(0,8),hex.slice(8,12),hex.slice(12,16),hex.slice(16,20),hex.slice(20)].join("-");
   window.localStorage.setItem(visitorKey,id);
  }
  return id;
 }catch{return null;}
}
export function AudienceStats({language,lineUserId}:{language:Language;lineUserId:string|null}){
 const [counts,setCounts]=useState<Counts|null>(null);
 useEffect(()=>{
  let active=true;
  const id=visitorId();
  const load=async()=>{
   try{
    const response=await fetch(apiUrl(id?"/api/v1/audience/visit":"/api/v1/audience"),{
     method:id?"POST":"GET",cache:"no-store",
     ...(id?{headers:{"Content-Type":"application/json"},body:JSON.stringify({visitor_id:id})}:{})
    });
    if(!response.ok)throw new Error("Audience unavailable");
    const data:Counts=await response.json();
    if(!Number.isSafeInteger(data.line_accounts)||data.line_accounts<0||
       !Number.isSafeInteger(data.website_visitors)||data.website_visitors<0)throw new Error("Invalid counts");
    if(active)setCounts(data);
   }catch{if(active)setCounts(null);}
  };
  void load();
  return()=>{active=false;};
 },[lineUserId]);
 const th=language==="th";
 const number=(n:number|undefined)=>n===undefined?"—":n.toLocaleString(th?"th-TH":"en-US");
 const note=th?"สถิติตั้งแต่เริ่มเปิดใช้ตัวนับ: LINE นับบัญชีที่ยืนยันแล้วครั้งเดียว ส่วนผู้เข้าชมนับเบราว์เซอร์ไม่ซ้ำ":"Since counters were enabled: verified LINE accounts and unique browsers.";
 return <div className="audience-stats" title={note} aria-label={note}>
  <span><span className="audience-label">{th?"ล็อกอิน LINE":"LINE accounts"}</span><strong data-audience="line">{number(counts?.line_accounts)}</strong></span>
  <span><span className="audience-label">{th?"ผู้เข้าชมเว็บ":"Web visitors"}</span><strong data-audience="visitors">{number(counts?.website_visitors)}</strong></span>
 </div>;
}
