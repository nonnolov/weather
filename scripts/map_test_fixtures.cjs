const zlib=require('zlib');
function crc32(buffer){let crc=0xffffffff;for(const byte of buffer){crc^=byte;for(let n=0;n<8;n++)crc=(crc>>>1)^((crc&1)?0xedb88320:0);}return(crc^0xffffffff)>>>0;}
function png(rgba){
 const size=256,raw=Buffer.alloc(size*(size*4+1)),pixel=Buffer.from(rgba);
 for(let y=0;y<size;y++)raw.fill(pixel,y*(size*4+1)+1,(y+1)*(size*4+1));
 const chunk=(type,data)=>{const name=Buffer.from(type),len=Buffer.alloc(4),crc=Buffer.alloc(4);len.writeUInt32BE(data.length);crc.writeUInt32BE(crc32(Buffer.concat([name,data])));return Buffer.concat([len,name,data,crc]);};
 const header=Buffer.alloc(13);header.writeUInt32BE(size,0);header.writeUInt32BE(size,4);header[8]=8;header[9]=6;
 return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),chunk('IHDR',header),chunk('IDAT',zlib.deflateSync(raw)),chunk('IEND',Buffer.alloc(0))]);
}
const base=png([238,243,240,255]),radar=png([0,85,136,60]),covered=png([0,0,0,0]),uncovered=png([0,0,0,255]);
function manifest(stale=false){
 const now=Math.floor(Date.now()/600000)*600;
 return{host:'https://tilecache.rainviewer.com',generated:now,frames:Array.from({length:3},(_,i)=>({time:now-(2-i)*600,path:'/v2/radar/fixture'+i})),retrievedAt:Date.now(),stale};
}
async function installMapMocks(page,options={}){
 const requests=[];
 await page.route('**/api/radar',route=>{
  requests.push({kind:'metadata',method:route.request().method()});
  if(options.metadata==='error')return route.fulfill({status:503,json:{error:'radar_unavailable'}});
  const body=manifest(options.metadata==='stale');if(options.metadata==='empty')body.frames=[];
  return route.fulfill({json:body});
 });
 await page.route('https://tile.openstreetmap.org/**',route=>{
  requests.push({kind:'base',method:route.request().method()});
  return options.baseError?route.fulfill({status:503,body:''}):route.fulfill({contentType:'image/png',body:base});
 });
 await page.route('https://tilecache.rainviewer.com/**',route=>{
  const coverage=route.request().url().includes('/coverage/');
  requests.push({kind:coverage?'coverage':'radar',method:route.request().method(),url:route.request().url()});
  if((coverage&&options.coverage==='error')||(!coverage&&options.radarError))return route.fulfill({status:503,body:''});
  return route.fulfill({contentType:'image/png',headers:{'Access-Control-Allow-Origin':'*'},body:coverage?(options.coverage==='uncovered'?uncovered:covered):radar});
 });
 return requests;
}
module.exports={installMapMocks,manifest};
