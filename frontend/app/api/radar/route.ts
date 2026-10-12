import {NextResponse} from "next/server";
import {normalizeRadar,type RadarManifest} from "../../../lib/radar";
export const runtime="nodejs";
let cached:RadarManifest|null=null;
let attemptedAt=0;
let pending:Promise<RadarManifest>|null=null;
async function acquire():Promise<RadarManifest> {
 const now=Date.now();
 if(cached && now-cached.retrievedAt<300000) return {...cached,stale:cached.stale || now-cached.frames.at(-1)!.time*1000>1200000};
 if(pending) return pending;
 if(now-attemptedAt<30000) {
  if(cached && now-cached.retrievedAt<1800000) return {...cached,stale:true};
  throw new Error("Radar cooling down");
 }
 attemptedAt=now;
 pending=(async()=>{
  try {
   const response=await fetch("https://api.rainviewer.com/public/weather-maps.json",{cache:"no-store",signal:AbortSignal.timeout(8000)});
   if(!response.ok) throw new Error("Radar unavailable");
   const body=await response.text();
   if(body.length>65536) throw new Error("Invalid radar metadata");
   cached=normalizeRadar(JSON.parse(body),Date.now());
   return cached;
  } catch {
   if(cached && Date.now()-cached.retrievedAt<1800000) return {...cached,stale:true};
   throw new Error("Radar unavailable");
  }
 })();
 try { return await pending; } finally {pending=null;}
}
export async function GET() {
 try {
  const data=await acquire();
  return NextResponse.json(data,{headers:{"Cache-Control":data.stale?"public, max-age=15, s-maxage=30":"public, max-age=60, s-maxage=300"}});
 } catch {
  return NextResponse.json({error:"radar_unavailable"},{status:503,headers:{"Cache-Control":"no-store","Retry-After":"30"}});
 }
}
