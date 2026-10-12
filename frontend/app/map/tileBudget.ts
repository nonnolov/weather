// Only visible images are fetched; cached images never wait for the network budget.
type Listener=(blob:Blob|null,error:Error|null)=>void;
type Job={url:string;listeners:Set<Listener>;controller:AbortController;started:boolean};
type Cached={blob:Blob;expires:number};
const cache=new Map<string,Cached>(),pending=new Map<string,Job>();
let cacheBytes=0,starts:number[]=[],jobs:Job[]=[];
let timer:ReturnType<typeof setTimeout>|undefined;
function remember(url:string,blob:Blob) {
 const old=cache.get(url);if(old)cacheBytes-=old.blob.size;
 cache.delete(url);cache.set(url,{blob,expires:Date.now()+1800000});cacheBytes+=blob.size;
 while(cache.size>64 || cacheBytes>8388608) {
  const key=cache.keys().next().value;if(!key)break;
  cacheBytes-=cache.get(key)!.blob.size;cache.delete(key);
 }
}
function cachedImage(url:string):Blob|null {
 const item=cache.get(url);if(!item)return null;
 cache.delete(url);
 if(item.expires<=Date.now()){cacheBytes-=item.blob.size;return null;}
 cache.set(url,item);return item.blob;
}
async function fetchJob(job:Job) {
 const timeout=setTimeout(()=>job.controller.abort(),15000);
 try {
  const response=await fetch(job.url,{signal:job.controller.signal,credentials:"omit"});
  if(!response.ok)throw new Error("Radar tile unavailable");
  const blob=await response.blob();
  if(blob.size>1048576 || !blob.type.startsWith("image/"))throw new Error("Invalid radar tile");
  if(job.controller.signal.aborted)return;
  remember(job.url,blob);
  job.listeners.forEach(listener=>listener(blob,null));
 } catch {
  if(!job.controller.signal.aborted || job.listeners.size)job.listeners.forEach(listener=>listener(null,new Error("Radar tile unavailable")));
 } finally {
  clearTimeout(timeout);
  if(pending.get(job.url)===job)pending.delete(job.url);
 }
}
function pump() {
 if(timer)clearTimeout(timer);timer=undefined;
 const now=Date.now();starts=starts.filter(time=>now-time<60000);
 jobs=jobs.filter(job=>job.listeners.size>0);
 while(jobs.length && starts.length<80) {
  const job=jobs.shift()!;job.started=true;starts.push(Date.now());void fetchJob(job);
 }
 if(jobs.length)timer=setTimeout(pump,Math.max(50,starts[0]+60010-Date.now()));
}
export function queueRadarImage(image:HTMLImageElement,url:string,done:(error:Error|null)=>void) {
 let cancelled=false,objectUrl:string|undefined,job:Job|undefined;
 const deliver:Listener=(blob,error)=>{
  if(cancelled)return;
  if(error || !blob){done(error??new Error("Radar tile unavailable"));return;}
  objectUrl=URL.createObjectURL(blob);
  const complete=(failure:Error|null)=>{
   image.onload=image.onerror=null;
   if(!cancelled)done(failure);
   if(objectUrl){URL.revokeObjectURL(objectUrl);objectUrl=undefined;}
  };
  image.onload=()=>complete(null);image.onerror=()=>{const item=cache.get(url);if(item){cacheBytes-=item.blob.size;cache.delete(url);}complete(new Error("Radar tile unavailable"));};
  image.src=objectUrl;
 };
 const hit=cachedImage(url);
 if(hit)deliver(hit,null);
 else {
  job=pending.get(url);
  if(!job){job={url,listeners:new Set(),controller:new AbortController(),started:false};pending.set(url,job);jobs.push(job);}
  job.listeners.add(deliver);pump();
 }
 return ()=>{
  cancelled=true;image.onload=image.onerror=null;image.removeAttribute("src");
  if(objectUrl){URL.revokeObjectURL(objectUrl);objectUrl=undefined;}
  if(job){
   job.listeners.delete(deliver);
   if(!job.listeners.size){job.controller.abort();if(pending.get(url)===job)pending.delete(url);}
  }
  jobs=jobs.filter(item=>item.listeners.size>0);
  if(!jobs.length && timer){clearTimeout(timer);timer=undefined;}
 };
}
