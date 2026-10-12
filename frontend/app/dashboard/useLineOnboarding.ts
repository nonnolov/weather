"use client";
import {useCallback,useEffect,useRef,useState} from "react";
import {authenticateLine,ApiError} from "../../lib/api";
import {getLineConfig,getLineStatus,setLineSubscription,type LineConfig,type LineStatus} from "../../lib/line";
export function useLineOnboarding(language:"th"|"en"){
 const [userId,setUserId]=useState<string|null>(null),[status,setStatus]=useState<LineStatus|null>(null);
 const [config,setConfig]=useState<LineConfig|null>(null),[busy,setBusy]=useState(false),[sdkReady,setSdkReady]=useState(false),[error,setError]=useState("");
 const initialized=useRef(false),mounted=useRef(true),revision=useRef(0),writing=useRef(false);
 const explain=useCallback((problem:unknown)=>{
  const code=problem instanceof ApiError?problem.status:0;
  return language==="th"?(code===401?"กรุณาล็อกอิน LINE อีกครั้ง":code===409?"กรุณาตรวจการเพิ่มเพื่อนและพื้นที่ก่อนเปิดแจ้งเตือน":code===503||code===404?"ระบบสมัครแจ้งเตือนยังไม่เปิดใช้งาน":"ตรวจสถานะ LINE ไม่สำเร็จ กรุณาลองอีกครั้ง"):
  (code===401?"Please sign in with LINE again":code===409?"Check friendship and location before enabling alerts":code===503||code===404?"Notification signup is not available yet":"Could not verify LINE. Please retry.");
 },[language]);
 useEffect(()=>{mounted.current=true;void getLineConfig().then(value=>{if(mounted.current)setConfig(value);}).catch(()=>{if(mounted.current)setConfig({enabled:false,add_friend_url:null});});return()=>{mounted.current=false;};},[]);
 const refresh=useCallback(async()=>{
  if(!window.liff?.isLoggedIn()||writing.current)return;
  const requestId=++revision.current;
  setBusy(true);setError("");
  try{const value=await getLineStatus();if(mounted.current&&requestId===revision.current){setStatus(value);setUserId(value.external_user_id);}}
  catch(problem){if(mounted.current&&requestId===revision.current){setStatus(previous=>previous?{...previous,ready:false}:null);if(problem instanceof ApiError&&problem.status===401){setUserId(null);setStatus(null);}setError(explain(problem));}}
  finally{if(mounted.current&&requestId===revision.current)setBusy(false);}
 },[explain]);
 const initialize=useCallback(async()=>{
  if(initialized.current||!window.liff)return;
  initialized.current=true;
  try{
   await window.liff.init({liffId:process.env.NEXT_PUBLIC_LIFF_ID!});
   if(!mounted.current)return;
   setSdkReady(true);
   if(window.liff.isLoggedIn()){
    const token=window.liff.getIDToken();if(!token)throw new Error("No LINE session");
    const result=await authenticateLine(token);
    if(mounted.current)setUserId(result.external_user_id);
    await refresh();
   }
  }catch(problem){initialized.current=false;if(mounted.current){setStatus(null);setError(explain(problem));}}
 },[refresh,explain]);
 useEffect(()=>{
  const visible=()=>{if(document.visibilityState==="visible"&&userId)void refresh();};
  document.addEventListener("visibilitychange",visible);
  return()=>document.removeEventListener("visibilitychange",visible);
 },[userId,refresh]);
 const login=()=>{
  if(!sdkReady||!window.liff)return;
  window.localStorage.setItem("weather.language",language);
  if(window.liff.isLoggedIn())void refresh();else window.liff.login();
 };
 const addFriend=async()=>{
  setError("");
  const sdk=window.liff;
  if(!sdk)return;
  if(sdk.isInClient?.()&&sdk.requestFriendship){
   setBusy(true);
   try{await sdk.requestFriendship();await refresh();}
   catch{setError(language==="th"?"ใช้ลิงก์เพิ่มเพื่อนด้านล่าง แล้วกลับมาตรวจสถานะอีกครั้ง":"Use the friend link below, then return and check status.");}
   finally{setBusy(false);}
  }else if(config?.add_friend_url?.startsWith("https://line.me/R/ti/p/"))window.open(config.add_friend_url,"_blank","noopener,noreferrer");
  else setError(language==="th"?"ลิงก์เพิ่มเพื่อนยังไม่พร้อม กรุณาเพิ่ม Weather ใน LINE แล้วตรวจสถานะ":"The friend link is not configured. Add Weather in LINE, then check status.");
 };
 const subscribe=async(enabled:boolean)=>{
  if(writing.current)return;
  writing.current=true;
  const requestId=++revision.current;
  if(!enabled)setStatus(previous=>previous?{...previous,ready:false}:null);
  setBusy(true);setError("");
  try{const value=await setLineSubscription(enabled);if(mounted.current&&requestId===revision.current)setStatus(value);}
  catch(problem){if(mounted.current&&requestId===revision.current){setStatus(previous=>previous?{...previous,ready:false}:null);if(problem instanceof ApiError&&problem.status===401){setUserId(null);setStatus(null);}setError(explain(problem));}}
  finally{writing.current=false;if(mounted.current&&requestId===revision.current)setBusy(false);}
 };
 return{userId,status,config,busy,sdkReady,error,initialize,login,addFriend,refresh,subscribe};
}
