"use client";
import {useCallback,useEffect,useRef,useState} from "react";
import {ApiError} from "../../lib/api";
import {LineRequestError,getLineConfig,getLineStatus,setLineSubscription,type LineConfig,type LineStatus} from "../../lib/line";
export function useLineOnboarding(language:"th"|"en"){
 const [userId,setUserId]=useState<string|null>(null),[status,setStatus]=useState<LineStatus|null>(null);
 const [config,setConfig]=useState<LineConfig|null>(null),[busy,setBusy]=useState(false),[sdkReady,setSdkReady]=useState(false),[error,setError]=useState("");
 const initialized=useRef(false),mounted=useRef(true),revision=useRef(0),writing=useRef(false),needsRelogin=useRef(false);
 const explain=useCallback((problem:unknown)=>{
  const code=problem instanceof ApiError?problem.status:0,th=language==="th";
  if(code===401)return th?"กรุณาล็อกอิน LINE อีกครั้ง":"Please sign in with LINE again";
  if(code===409)return th?"กรุณาตรวจสถานะเพื่อนและตั้งพื้นที่ก่อนเปิดแจ้งเตือน":"Check friendship and location before enabling alerts";
  if(problem instanceof LineRequestError&&problem.reason==="friendship")return th?"ตรวจสถานะเพื่อน Weather ไม่สำเร็จ กรุณาลองใหม่ หากยังมีปัญหาให้ติดต่อผู้ดูแล":"Could not verify your friendship with Weather. Retry or contact support.";
  if(problem instanceof LineRequestError&&problem.reason==="disabled")return th?"ระบบสมัครแจ้งเตือนยังไม่เปิดใช้งาน":"Notification signup is not available yet";
  if(code===404)return th?"ไม่พบบริการสมัครแจ้งเตือน กรุณาลองใหม่หรือติดต่อผู้ดูแล":"Notification signup service was not found. Retry or contact support.";
  return th?"เชื่อมต่อบริการ LINE ไม่สำเร็จชั่วคราว กรุณาลองใหม่":"Could not connect to the LINE service. Please retry.";
 },[language]);
 const configError=language==="th"?"โหลดสถานะระบบสมัครแจ้งเตือนไม่สำเร็จ กรุณาเปิดหน้านี้ใหม่":"Could not load notification signup availability. Reopen this page.";
 const [configFailed,setConfigFailed]=useState(false);
 useEffect(()=>{mounted.current=true;void getLineConfig().then(value=>{if(mounted.current){setConfig(value);setConfigFailed(false);}}).catch(()=>{if(mounted.current){setConfig(null);setConfigFailed(true);}});return()=>{mounted.current=false;};},[]);
 const refresh=useCallback(async()=>{
  if(!window.liff?.isLoggedIn()||writing.current)return;
  const requestId=++revision.current;
  setBusy(true);setError("");
  try{const value=await getLineStatus();if(mounted.current&&requestId===revision.current){needsRelogin.current=false;setStatus(value);setUserId(value.external_user_id);}}
  catch(problem){if(mounted.current&&requestId===revision.current){setStatus(previous=>previous?{...previous,ready:false}:null);if(problem instanceof ApiError&&problem.status===401){needsRelogin.current=true;setUserId(null);setStatus(null);}setError(explain(problem));}}
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
    // Status verifies the access token and returns the server-confirmed identity.
    // A cached one-hour ID token must not block a still-valid access-token session.
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
  const sdk=window.liff;
  if(needsRelogin.current){
   ++revision.current;setUserId(null);setStatus(null);setError("");
   if(sdk.isInClient?.()){
    window.location.assign("https://liff.line.me/"+encodeURIComponent(process.env.NEXT_PUBLIC_LIFF_ID!));
    return;
   }
   sdk.logout?.();
   sdk.login({redirectUri:window.location.origin+window.location.pathname});
  }else if(sdk.isLoggedIn())void refresh();else sdk.login();
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
  catch(problem){if(mounted.current&&requestId===revision.current){setStatus(previous=>previous?{...previous,ready:false}:null);if(problem instanceof ApiError&&problem.status===401){needsRelogin.current=true;setUserId(null);setStatus(null);}setError(explain(problem));}}
  finally{writing.current=false;if(mounted.current&&requestId===revision.current)setBusy(false);}
 };
 return{userId,status,config,busy,sdkReady,error:error||(configFailed?configError:""),initialize,login,addFriend,refresh,subscribe};
}
