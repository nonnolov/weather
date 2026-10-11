const fs=require('fs'),path=require('path'),assert=require('assert');
const cache=path.join(process.env.LOCALAPPDATA,'npm-cache','_npx');
const entry=fs.readdirSync(cache).map(d=>path.join(cache,d,'node_modules','playwright')).find(p=>fs.existsSync(p));
const {chromium}=require(entry);
const stamp=new Date().toISOString();
const place={id:1,name:'ชลบุรี',slug:'chon-buri-city',timezone:'Asia/Bangkok',subdistrict:'บางปลาสร้อย',district:'เมืองชลบุรี',province:'ชลบุรี',is_active:true};
const forecast={id:1,provider:'open_meteo',retrieved_at:stamp,hourly:[{id:1,valid_time:new Date(Date.now()+3600000).toISOString(),temperature_2m:29,apparent_temperature:32,weather_code:2,precipitation_probability:40,precipitation:0.3,relative_humidity_2m:70,wind_speed_10m:8}],daily:[]};
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const results=[];
 try {
 for(const mode of ['missing-air','stale-air','failed-air','empty-forecast','failed-forecast','gps-denied','gps-success']){
  const ctx=await browser.newContext({viewport:{width:390,height:844}});
  await ctx.addInitScript(mode=>{
   localStorage.setItem('weather.theme','light');
   Object.defineProperty(navigator,'geolocation',{value:{getCurrentPosition(success,error){mode==='gps-success'?success({coords:{latitude:13.36,longitude:100.98}}):error({code:1});}}});
  },mode);
  const page=await ctx.newPage(),requests=[],errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('https://static.line-scdn.net/**',r=>r.abort());
  await page.route('**/api/backend/**',r=>{
   const url=r.request().url();requests.push({url,method:r.request().method()});
   let data;
   if(url.endsWith('/health'))data={status:'ok'};
   else if(url.endsWith('/locations'))data=[place];
   else if(url.includes('/air-quality/')){
    if(mode==='failed-air')return r.fulfill({status:503,json:{error:'unavailable'}});
    data={location_id:1,status:mode==='missing-air'?'missing':mode==='stale-air'?'stale':'available',stale:mode==='stale-air',retrieved_at:stamp,current:mode==='missing-air'?null:{valid_time:stamp,pm25:18,aqi:40,category:'fair'},hourly:[]};
   } else if(url.endsWith('/location/from-gps'))data={external_user_id:'mock-user',location:place};
   else if(url.endsWith('/forecast/refresh'))data={timezone:'Asia/Bangkok'};
   else {
    if(mode==='failed-forecast')return r.fulfill({status:503,json:{error:'unavailable'}});
    data=mode==='empty-forecast'?{...forecast,hourly:[],daily:[]}:forecast;
   }
   return r.fulfill({json:data});
  });
  await page.goto('http://localhost:3100');
  if(mode.startsWith('gps-')){
   await page.locator('.welcome-card .gps-primary').click();
   if(mode==='gps-denied'){
    await page.locator('.status-error[role=alert]').waitFor();
    assert.equal(requests.filter(r=>r.method==='POST').length,0);
    assert(await page.locator('.retry-button').isVisible());
   } else {
    await page.locator('.hero-actions').waitFor();
    assert.equal(requests.filter(r=>r.method==='POST').length,2);
    assert((await page.locator('.hero-location h2').innerText()).includes('บางปลาสร้อย'));
   }
  } else {
   await page.locator('.sample-picker summary').click();
   await page.locator('select').selectOption('1');
   if(mode==='failed-forecast'){await page.locator('.status-error[role=alert]').waitFor();assert(await page.locator('.retry-button').isVisible());}
   else{
    await page.locator('.hero-actions').waitFor();
    if(mode==='missing-air')await page.getByText('ไม่มีค่าครบสำหรับชั่วโมงปัจจุบัน',{exact:true}).waitFor();
    if(mode==='stale-air')await page.getByText('ข้อมูลเดิม: การอัปเดตล่าช้าหรือล้มเหลว',{exact:true}).waitFor();
    if(mode==='failed-air')await page.getByText('ข้อมูลคุณภาพอากาศไม่พร้อมใช้งานชั่วคราว',{exact:true}).waitFor();
    if(mode==='empty-forecast'){assert.equal(await page.locator('.hourly-list article').count(),0);assert((await page.locator('.hero-reading').innerText()).includes('—'));}
   }
   assert.equal(requests.filter(r=>r.method==='POST').length,0);
  }
  assert.equal(errors.length,0,errors.join('; '));
  assert(!requests.some(r=>r.url.includes('flood')));
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Overflow in '+mode);
  results.push({mode,status:'passed',mocked:true});await ctx.close();
 }
 console.log(JSON.stringify({status:'passed',productionWrites:0,results},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
