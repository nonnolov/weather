const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const ts=require('../frontend/node_modules/typescript');
const root=path.join(__dirname,'..'),initial=Date.now();
function compile(file,globals={}){
 const code=ts.transpileModule(fs.readFileSync(path.join(root,file),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 const module={exports:{}};
 vm.runInNewContext(code,{module,exports:module.exports,require,...globals});
 return module.exports;
}
let now=initial;
class Clock extends Date{static now(){return now;}}
const raw=()=>({host:'https://tilecache.rainviewer.com',generated:Math.floor(now/1000),radar:{past:[2,0,1,1].map(i=>({time:Math.floor(now/1000)-(2-i)*600,path:'/v2/radar/hash'+i}))}});
const normal=compile('frontend/lib/radar.ts',{Date:Clock,Map});
let count=0;
const check=(name,fn)=>{fn();count++;};
check('sort and deduplicate actual frames',()=>assert.deepEqual(Array.from(normal.normalizeRadar(raw()).frames,f=>f.time),[0,1,2].map(i=>Math.floor(now/1000)-(2-i)*600)));
check('reject external host',()=>assert.throws(()=>normal.normalizeRadar({...raw(),host:'https://evil.example'})));
check('reject host lookalike',()=>assert.throws(()=>normal.normalizeRadar({...raw(),host:'https://tilecache.rainviewer.com.evil.example'})));
check('reject traversal paths',()=>assert.throws(()=>normal.normalizeRadar({...raw(),radar:{past:[{time:Math.floor(now/1000),path:'/v2/radar/../../secret'}]}})));
check('reject empty history',()=>assert.throws(()=>normal.normalizeRadar({...raw(),radar:{past:[]}})));
check('reject future timestamps',()=>assert.throws(()=>normal.normalizeRadar({...raw(),radar:{past:[{time:Math.floor(now/1000)+600,path:'/v2/radar/future'}]}})));
check('reject obsolete timestamps',()=>assert.throws(()=>normal.normalizeRadar({...raw(),radar:{past:[{time:Math.floor(now/1000)-14400,path:'/v2/radar/expired'}]}})));
check('reject unbounded manifest',()=>assert.throws(()=>normal.normalizeRadar({...raw(),radar:{past:Array(31).fill(raw().radar.past[0])}})));
check('ignore nowcast',()=>assert(!normal.normalizeRadar({...raw(),radar:{...raw().radar,nowcast:[{time:now/1000+600,path:'/v2/radar/future'}]}}).frames.some(f=>f.path.includes('future'))));
check('mark delayed data stale',()=>assert(normal.normalizeRadar({...raw(),radar:{past:[{time:Math.floor(now/1000)-1500,path:'/v2/radar/older'}]}}).stale));
(async()=>{
 let calls=0,fail=false;
 const route=compile('frontend/app/api/radar/route.ts',{
  Date:Clock,AbortSignal,fetch:async()=>{calls++;if(fail)throw Error('provider failure');return{ok:true,text:async()=>JSON.stringify(raw())};},
  require:name=>name==='next/server'?{NextResponse:{json:(body,options={})=>({body,status:options.status??200,headers:options.headers??{}})}}:normal
 });
 const first=await route.GET();assert.equal(first.status,200);assert.equal(calls,1);count++;
 now+=120000;assert.equal((await route.GET()).status,200);assert.equal(calls,1);count++;
 now+=190000;fail=true;const fallback=await route.GET();assert.equal(fallback.status,200);assert(fallback.body.stale);assert.equal(calls,2);count++;
 await route.GET();assert.equal(calls,2,'Failure cooldown did not suppress another fetch');count++;
 now=initial+1900000;const unavailable=await route.GET();assert.equal(unavailable.status,503);assert.equal(unavailable.headers['Cache-Control'],'no-store');count++;
 now+=31000;fail=false;assert.equal((await route.GET()).status,200);count++;
 console.log(JSON.stringify({status:'passed',contractCases:count,providerRequests:'mocked',productionWrites:0}));
})().catch(e=>{console.error(e);process.exit(1)});
