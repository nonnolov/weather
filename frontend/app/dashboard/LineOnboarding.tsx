"use client";
import {useState} from "react";
import {UiIcon} from "./UiIcon";
import type {DashboardModel} from "./useWeatherDashboard";
export function LineOnboarding({model}:{model:DashboardModel}){
 const {line,language,handleGps,isGpsBusy,busy,selectedId}=model,th=language==="th";
 const [consent,setConsent]=useState(false);
 const status=line.status,connected=Boolean(line.userId),friend=status?.friend===true,located=status?.location_verified===true,ready=status?.ready===true;
 const available=line.config?.enabled===true,waiting=line.busy||busy;
 const friendUrl=line.config?.add_friend_url?.startsWith("https://line.me/R/ti/p/")?line.config.add_friend_url:null;
 return <section className="line-panel line-onboarding" aria-labelledby="line-onboarding-title">
  <span className="line-symbol"><UiIcon name="message"/></span>
  <div className="line-onboarding-body"><div className="line-onboarding-heading"><h2 id="line-onboarding-title">{th?"แจ้งเตือนผ่าน LINE":"Alerts through LINE"}</h2><span className={"line-ready-badge"+(ready?" ready":"")}>{ready?(th?"พร้อมรับแจ้งเตือน":"Alerts enabled"):status?.enabled?(th?"รอตรวจสถานะแจ้งเตือน":"Verify alert status"):(th?"ยังไม่เปิดแจ้งเตือน":"Alerts not enabled")}</span></div>
   <div className="line-status"><span className={"line-dot"+(connected?" connected":"")} aria-hidden="true"/>{connected?(th?"เชื่อมบัญชี LINE แล้ว":"LINE account connected"):(th?"ยังไม่เชื่อมบัญชี LINE":"LINE account not connected")}</div>
   <p className="line-onboarding-intro">{th?"พยากรณ์รายวันและแจ้งเตือนเมื่ออากาศเปลี่ยนสำคัญ สำหรับพื้นที่ที่คุณเลือก":"Daily forecasts and significant weather updates for your selected area."}</p>
   {!ready&&<ol className="line-onboarding-steps">
    <li className={connected?"complete":""}><span className="line-step-number" aria-hidden="true">{connected?"✓":"1"}</span><div><strong>{th?"ล็อกอิน LINE":"Sign in with LINE"}</strong><small>{connected?(th?"เชื่อมบัญชีสำเร็จ":"Account connected"):(th?"ใช้บัญชีที่ต้องการรับข้อความ":"Use the account that will receive alerts")}</small></div>{!connected&&<button className="utility-button" type="button" onClick={line.login} disabled={!line.sdkReady||waiting}>{th?"ล็อกอิน LINE":"LINE login"}</button>}</li>
    <li className={friend?"complete":""}><span className="line-step-number" aria-hidden="true">{friend?"✓":"2"}</span><div><strong>{th?"เพิ่มเพื่อน Weather":"Add Weather as a friend"}</strong><small>{friend?(th?"เพิ่มเพื่อนแล้ว":"Friendship verified"):(th?"เพิ่มเพื่อนหรือยกเลิกบล็อก แล้วตรวจสถานะ":"Add or unblock, then check status")}</small></div>{!friend&&<button className="utility-button" type="button" onClick={()=>void line.addFriend()} disabled={!connected||!available||waiting}>{th?"เพิ่มเพื่อน":"Add friend"}</button>}</li>
    <li className={located?"complete":""}><span className="line-step-number" aria-hidden="true">{located?"✓":"3"}</span><div><strong>{th?"ตั้งพื้นที่แจ้งเตือน":"Set notification area"}</strong><small>{located?(th?"บันทึกพื้นที่แล้ว":"Area saved"):(th?"กดเพื่ออนุญาตใช้ตำแหน่ง":"Tap to allow location access")}</small></div><button className="utility-button" type="button" onClick={handleGps} disabled={!friend||!available||waiting}>{isGpsBusy?"…":located?(th?"เปลี่ยนพื้นที่":"Change area"):(th?"ใช้ตำแหน่ง":"Use location")}</button></li>
    <li><span className="line-step-number" aria-hidden="true">4</span><div><strong>{th?"เปิดรับแจ้งเตือน":"Enable alerts"}</strong><small>{th?"ยืนยันด้วยตัวคุณเอง":"Confirm your choice"}</small></div></li>
   </ol>}
   {friendUrl&&connected&&!friend&&<a className="line-friend-link" href={friendUrl} target="_blank" rel="noreferrer">{th?"เปิดหน้าเพิ่มเพื่อน Weather":"Open Weather friend page"}</a>}
   {located&&selectedId!==null&&<p className="line-area-note">{th?"พื้นที่ตัวอย่างใน Dashboard ไม่เปลี่ยนพื้นที่แจ้งเตือนที่บันทึกไว้":"A Dashboard sample does not change your saved notification area."}</p>}
   {!ready&&<label className="line-consent"><input type="checkbox" checked={consent} disabled={!friend||!located||!available||waiting} onChange={event=>setConsent(event.target.checked)}/><span>{th?"ยินยอมรับพยากรณ์และแจ้งเตือนผ่าน LINE ปิดได้ทุกเมื่อ":"I agree to receive weather forecasts and alerts through LINE. I can turn them off anytime."}</span></label>}
   <div className="line-onboarding-actions">{ready||status?.enabled?<button type="button" className="utility-button" disabled={waiting} onClick={()=>{setConsent(false);void line.subscribe(false);}}>{th?"ปิดแจ้งเตือน":"Turn off alerts"}</button>:<button type="button" className="gps-primary" disabled={!consent||!friend||!located||!available||waiting} onClick={()=>void line.subscribe(true)}>{th?"เปิดรับแจ้งเตือน":"Enable alerts"}</button>}{connected&&<button type="button" className="utility-button" disabled={waiting||!available} onClick={()=>void line.refresh()}>{line.busy?(th?"กำลังตรวจ…":"Checking…"):(th?"ตรวจสถานะ":"Check status")}</button>}{ready&&<button type="button" className="utility-button" onClick={handleGps} disabled={waiting}>{th?"เปลี่ยนพื้นที่":"Change area"}</button>}</div>
   {line.error&&<p className="line-onboarding-error" role="alert">{line.error}</p>}
   {line.config&&!available&&<p className="line-area-note" role="status">{th?"ระบบสมัครแจ้งเตือนสำหรับผู้ใช้ใหม่ยังไม่เปิดใช้งาน":"Notification signup for new users is not available yet."}</p>}
   <p className="line-onboarding-footnote">{th?"รับแจ้งเตือนได้เมื่อสถานะเป็น “พร้อมรับแจ้งเตือน”":"Alerts require the “Alerts enabled” status."}</p>
  </div>
 </section>;
}
