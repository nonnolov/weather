export type RadarFrame = {time:number;path:string};
export type RadarManifest = {host:string;generated:number;frames:RadarFrame[];retrievedAt:number;stale:boolean};
export function normalizeRadar(raw:unknown,now=Date.now()):RadarManifest {
 if(!raw || typeof raw!=="object") throw new Error("Invalid radar metadata");
 const data=raw as Record<string,unknown>, radar=data.radar as Record<string,unknown>|undefined;
 if(data.host!=="https://tilecache.rainviewer.com" || !Number.isInteger(data.generated) || !radar || !Array.isArray(radar.past) || radar.past.length>30) throw new Error("Invalid radar metadata");
 const frames=new Map<number,RadarFrame>();
 for(const item of radar.past) {
  if(!item || typeof item!=="object") continue;
  const {time,path}=item as RadarFrame;
  if(Number.isInteger(time) && time*1000<=now+300000 && time*1000>=now-10800000 && typeof path==="string" && /^\/v2\/radar\/[a-zA-Z0-9_-]{1,80}$/.test(path)) frames.set(time,{time,path});
 }
 const sorted=[...frames.values()].sort((a,b)=>a.time-b.time);
 if(!sorted.length || ((data.generated as number)*1000>now+300000 || (data.generated as number)*1000<now-10800000)) throw new Error("No usable radar frames");
 return {host:data.host as string,generated:data.generated as number,frames:sorted,retrievedAt:now,stale:now-sorted.at(-1)!.time*1000>1200000};
}
