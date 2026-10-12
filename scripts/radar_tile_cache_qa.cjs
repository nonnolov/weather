const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const ts=require('../frontend/node_modules/typescript');
const source=ts.transpileModule(fs.readFileSync(path.join(__dirname,'../frontend/app/map/tileBudget.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
function setup(){
 let now=1000000,requests=[],timers=new Map(),id=0,mode='ok';
 const exported={},context={exports:exported,Blob,AbortController,URL,Error,Map,Set,Date:class extends Date{static now(){return now}},
 setTimeout:(fn,ms)=>{timers.set(++id,{fn,ms});return id},clearTimeout:id=>timers.delete(id),
 fetch:async(url,options)=>{requests.push({url,signal:options.signal});if(mode==='pending')return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(Error('aborted'))));return{ok:mode!=='error',blob:async()=>new Blob(['png'],{type:'image/png'})};}};
 vm.runInNewContext(source,context);
 const image=()=>({onload:null,onerror:null,removeAttribute(){},set src(value){this.value=value;queueMicrotask(()=>this.onload?.())}});
 return{queue:exported.queueRadarImage,image,requests,timers,advance:ms=>now+=ms,mode:value=>mode=value};
}
const flush=async()=>{for(let i=0;i<10;i++)await Promise.resolve();await new Promise(resolve=>setImmediate(resolve));};
(async()=>{
 let e=setup(),callbacks=0;
 e.queue(e.image(),'same',()=>callbacks++);e.queue(e.image(),'same',()=>callbacks++);
 await flush();assert.equal(e.requests.length,1);assert.equal(callbacks,2);
 e.queue(e.image(),'same',()=>callbacks++);await flush();assert.equal(e.requests.length,1);assert.equal(callbacks,3);
 e.advance(1800001);e.queue(e.image(),'same',()=>callbacks++);await flush();assert.equal(e.requests.length,2);
 e=setup();e.mode('pending');let cancelledCalls=0;
 const a=e.queue(e.image(),'shared',()=>cancelledCalls++),b=e.queue(e.image(),'shared',()=>cancelledCalls++);
 a();assert.equal(e.requests[0].signal.aborted,false);b();assert.equal(e.requests[0].signal.aborted,true);
 await flush();assert.equal(cancelledCalls,0);assert.equal(e.timers.size,0);
 e=setup();e.mode('error');let failures=0;
 e.queue(e.image(),'bad',error=>{if(error)failures++});await flush();e.queue(e.image(),'bad',()=>{});await flush();assert.equal(e.requests.length,2);assert.equal(failures,1);
 e=setup();e.queue(e.image(),'cached',()=>{});await flush();e.mode('pending');
 const cleanup=[];for(let i=0;i<79;i++)cleanup.push(e.queue(e.image(),'new'+i,()=>{}));
 assert.equal(e.requests.length,80);let hit=false;
 e.queue(e.image(),'cached',()=>hit=true);await flush();assert(hit,'Cached image waited behind saturated quota');assert.equal(e.requests.length,80);
 const cancel=e.queue(e.image(),'queued',()=>assert.fail('Cancelled queued image completed'));
 assert.equal(e.requests.length,80);cancel();cleanup.forEach(fn=>fn());await flush();
 assert(!e.requests.some(r=>r.url==='queued'));assert.equal(e.timers.size,0);
 console.log(JSON.stringify({status:'passed',cases:['inflight-dedup','cache-reuse','cache-expiry','shared-cancel','failed-retry','80-network-start-limit','cache-bypasses-full-queue','queued-cancel-cleanup'],network:'mocked'}));
})().catch(error=>{console.error(error);process.exit(1)});
