"use client";
import {useCallback,useEffect,useState} from "react";
import type {RadarManifest} from "../../lib/radar";
export function useRadar() {
 const [manifest,setManifest]=useState<RadarManifest|null>(null);
 const [loading,setLoading]=useState(true);
 const [error,setError]=useState(false);
 const [revision,setRevision]=useState(0);
 const retry=useCallback(()=>setRevision(value=>value+1),[]);
 useEffect(()=>{
  let active=true;
  const controller=new AbortController();
  async function load(){
   if(document.hidden) return;
   setLoading(true);
   try{
    const response=await fetch("/api/radar",{signal:controller.signal});
    if(!response.ok) throw new Error("Radar unavailable");
    const data=await response.json() as RadarManifest;
    if(!Array.isArray(data.frames) || !data.frames.length || data.host!=="https://tilecache.rainviewer.com") throw new Error("Invalid radar metadata");
    if(active){setManifest(data);setError(false);}
   }catch{if(active){setError(true);setManifest(null);}}
   finally{if(active)setLoading(false);}
  }
  void load();
  const timer=setInterval(()=>void load(),300000);
  return ()=>{active=false;controller.abort();clearInterval(timer);};
 },[revision]);
 return {manifest,loading,error,retry};
}
