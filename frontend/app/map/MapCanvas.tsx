"use client";
import {useEffect,useRef,useState} from "react";
import type * as Leaflet from "leaflet";
import type {Location} from "../../lib/api";
import type {RadarFrame} from "../../lib/radar";
import {queueRadarImage} from "./tileBudget";
export type LayerState="loading"|"ready"|"partial"|"error";
export type CoverageState="checking"|"covered"|"uncovered"|"unknown";
type Scene={map:Leaflet.Map;L:typeof Leaflet;base:Leaflet.TileLayer};
type Props={location:Location;language:"th"|"en";host?:string;frame?:RadarFrame;radarOn:boolean;coverageOn:boolean;locateTick:number;retryTick:number;pointLabel:string;onBase:(state:LayerState)=>void;onRadar:(state:LayerState)=>void;onCoverage:(state:CoverageState)=>void;onCadence:(ms:number)=>void};
export function MapCanvas({location,language,host,frame,radarOn,coverageOn,locateTick,retryTick,pointLabel,onBase,onRadar,onCoverage,onCadence}:Props) {
 const element=useRef<HTMLDivElement>(null);
 const [scene,setScene]=useState<Scene|null>(null);
 const [failed,setFailed]=useState(false);
 const lat=location.latitude,lon=location.longitude;
 useEffect(()=>{
  let active=true, map:Leaflet.Map|undefined,observer:ResizeObserver|undefined;
  void import("leaflet").then(L=>{
   if(!active || !element.current)return;
   const reduced=matchMedia("(prefers-reduced-motion: reduce)").matches;
   // Avoid Leaflet delayed zoom callbacks after the full-screen dialog unmounts.
   map=L.map(element.current,{zoomControl:false,minZoom:7,maxZoom:16,zoomAnimation:false,fadeAnimation:!reduced}).setView([lat,lon],10);
   map.attributionControl.setPrefix(false);
   L.control.zoom({position:"topright",zoomInTitle:language==="th"?"ซูมเข้า":"Zoom in",zoomOutTitle:language==="th"?"ซูมออก":"Zoom out"}).addTo(map);
   const base=L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:19,keepBuffer:0,updateWhenIdle:true,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors'});
   let errors=0,success=0;
   base.on("loading",()=>{errors=0;success=0;onBase("loading");});
   base.on("tileerror",()=>{errors++;});
   base.on("tileload",()=>{success++;});
   base.on("load",()=>{if(active)onBase(errors?(success?"partial":"error"):"ready");});
   base.addTo(map);
   map.createPane("weatherRadar").style.zIndex="410";
   map.createPane("weatherCoverage").style.zIndex="420";
   const label=document.createElement("div");label.textContent=pointLabel;
   const icon=L.divIcon({className:"weather-location-pin",html:'<span aria-hidden="true"></span>',iconSize:[24,24],iconAnchor:[12,12]});
   L.marker([lat,lon],{icon,title:pointLabel,alt:pointLabel,keyboard:true}).addTo(map).bindPopup(label);
   const cadence=()=>{
    if(!map)return;
    const size=map.getSize(),scale=256*2**Math.max(0,map.getZoom()-7);
    const tiles=(Math.ceil(size.x/scale)+1)*(Math.ceil(size.y/scale)+1);
    onCadence(Math.max(8000,Math.ceil(tiles*60000/60)));
   };
   map.on("moveend resize",cadence);cadence();
   observer=new ResizeObserver(()=>{if(map && active){map.invalidateSize({pan:false});cadence();}});
   observer.observe(element.current);
   setScene({map,L,base});
  }).catch(()=>{if(active){setFailed(true);onBase("error");}});
  return ()=>{active=false;observer?.disconnect();map?.remove();};
 },[lat,lon,language,pointLabel,onBase,onCadence]);
 useEffect(()=>{if(scene && locateTick)scene.map.setView([lat,lon],10,{animate:false});},[locateTick,scene,lat,lon]);
 useEffect(()=>{if(scene && retryTick)scene.base.redraw();},[scene,retryTick]);
 useEffect(()=>{
  if(!scene || !host || !frame || !radarOn)return;
  const {L,map}=scene;
  let active=true,errors=0,success=0;
  const cancels=new Map<HTMLElement,()=>void>();
  class VisibleRadarLayer extends L.TileLayer {
   createTile(coords:Leaflet.Coords,done:Leaflet.DoneCallback):HTMLElement {
    const image=document.createElement("img");image.alt="";image.setAttribute("role","presentation");
    cancels.set(image,queueRadarImage(image,this.getTileUrl(coords),error=>done(error??undefined,image)));
    return image;
   }
  }
  const layer=new VisibleRadarLayer(host+frame.path+"/256/{z}/{x}/{y}/2/1_0.png",{pane:"weatherRadar",maxNativeZoom:7,maxZoom:16,opacity:.72,keepBuffer:0,updateWhenIdle:true,updateWhenZooming:false});
  layer.on("tileunload",event=>{cancels.get(event.tile)?.();cancels.delete(event.tile);});
  layer.on("loading",()=>{errors=0;success=0;if(active)onRadar("loading");});
  layer.on("tileerror",()=>{errors++;});
  layer.on("tileload",()=>{success++;});
  layer.on("load",()=>{if(active)onRadar(errors?(success?"partial":"error"):"ready");});
  onRadar("loading");layer.addTo(map);
  return ()=>{active=false;layer.remove();layer.off();cancels.forEach(cancel=>cancel());cancels.clear();};
 },[scene,host,frame,radarOn,retryTick,onRadar]);
 useEffect(()=>{
  if(!scene || !host || !coverageOn || !radarOn)return;
  const {L,map}=scene,cancels=new Map<HTMLElement,()=>void>();
  class CoverageLayer extends L.TileLayer {
   createTile(coords:Leaflet.Coords,done:Leaflet.DoneCallback):HTMLElement {
    const image=document.createElement("img");image.alt="";
    cancels.set(image,queueRadarImage(image,this.getTileUrl(coords),error=>done(error??undefined,image)));return image;
   }
  }
  const layer=new CoverageLayer(host+"/v2/coverage/0/256/{z}/{x}/{y}/0/0_0.png",{pane:"weatherCoverage",maxNativeZoom:7,maxZoom:16,opacity:.25,keepBuffer:0,updateWhenIdle:true,updateWhenZooming:false});
  layer.on("tileunload",event=>{cancels.get(event.tile)?.();cancels.delete(event.tile);});
  layer.addTo(map);
  return ()=>{layer.remove();layer.off();cancels.forEach(cancel=>cancel());};
 },[scene,host,coverageOn,radarOn,retryTick]);
 useEffect(()=>{
  if(!scene || !host)return;
  let active=true;
  const point=scene.L.CRS.EPSG3857.latLngToPoint(scene.L.latLng(lat,lon),7),n=128;
  const x=(Math.floor(point.x/256)%n+n)%n,y=Math.max(0,Math.min(127,Math.floor(point.y/256)));
  const px=(Math.floor(point.x)%256+256)%256,py=(Math.floor(point.y)%256+256)%256;
  const image=new Image();image.crossOrigin="anonymous";onCoverage("checking");
  const cancel=queueRadarImage(image,host+"/v2/coverage/0/256/7/"+x+"/"+y+"/0/0_0.png",error=>{
   if(!active)return;
   if(error){onCoverage("unknown");return;}
   try{
    const canvas=document.createElement("canvas");canvas.width=canvas.height=256;
    const context=canvas.getContext("2d");if(!context)throw new Error("Canvas unavailable");
    context.drawImage(image,0,0,256,256);
    onCoverage(context.getImageData(px,py,1,1).data[3]>128?"uncovered":"covered");
   }catch{onCoverage("unknown");}
  });
  return ()=>{active=false;cancel();};
 },[scene,host,lat,lon,retryTick,onCoverage]);
 return <div ref={element} className="weather-map-canvas" role="region" aria-label={language==="th"?"แผนที่สภาพอากาศ":"Weather map"}>{failed && <p role="status">{language==="th"?"โหลดแผนที่ไม่สำเร็จ กรุณาปิดแล้วลองใหม่":"Map failed to load. Close and try again."}</p>}</div>;
}
