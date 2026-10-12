// Only visible radar tiles are requested. No prefetch; a conservative 80/minute budget.
type Job={cancelled:boolean;start:()=>void};
let starts:number[]=[];
let jobs:Job[]=[];
let timer:ReturnType<typeof setTimeout>|undefined;
function pump() {
 if(timer) clearTimeout(timer);
 timer=undefined;
 const now=Date.now();
 starts=starts.filter(time=>now-time<60000);
 jobs=jobs.filter(job=>!job.cancelled);
 while(jobs.length && starts.length<80) {
  const job=jobs.shift()!;
  if(!job.cancelled) {starts.push(Date.now());job.start();}
 }
 if(jobs.length) timer=setTimeout(pump,Math.max(50,starts[0]+60010-Date.now()));
}
export function queueRadarImage(image:HTMLImageElement,url:string,done:(error:Error|null)=>void) {
 let timeout:ReturnType<typeof setTimeout>|undefined;
 const job:Job={cancelled:false,start:()=>{
  const complete=(error:Error|null)=>{if(timeout) clearTimeout(timeout);if(!job.cancelled) done(error);};
  image.onload=()=>complete(null);
  image.onerror=()=>complete(new Error("Radar tile unavailable"));
  timeout=setTimeout(()=>{image.onload=image.onerror=null;image.removeAttribute("src");complete(new Error("Radar tile timeout"));},15000);
  image.src=url;
 }};
 jobs.push(job);
 pump();
 return ()=>{
  job.cancelled=true;
  if(timeout) clearTimeout(timeout);
  image.onload=image.onerror=null;
  image.removeAttribute("src");
  if(jobs.every(item=>item.cancelled)) {jobs=[];if(timer) clearTimeout(timer);timer=undefined;}
 };
}
