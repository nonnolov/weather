const fs=require('fs'),path=require('path'),assert=require('assert');
const cache=path.join(process.env.LOCALAPPDATA,'npm-cache','_npx');
const entry=fs.readdirSync(cache).map(d=>path.join(cache,d,'node_modules','playwright')).find(p=>fs.existsSync(p));
const {chromium}=require(entry),{installMapMocks}=require('./map_test_fixtures.cjs');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true}),report=[];
 try{
 for(const scenario of [
 {name:'mobile-light',width:360},{name:'desktop-dark',width:1440,dark:true},
 {name:'metadata-failed',metadata:'error'},{name:'metadata-empty',metadata:'empty'},
 {name:'stale',metadata:'stale'},{name:'radar-failed',radarError:true},
 {name:'base-failed',baseError:true},{name:'uncovered',coverage:'uncovered'},
 {name:'coverage-unknown',coverage:'error'},{name:'invalid-coordinates',invalid:true}
 ]){
 const context=await browser.newContext({viewport:{width:scenario.width||390,height:900}});
 await context.addInitScript(dark=>{localStorage.setItem('weather.theme',dark?'dark':'light');window.__gpsCalls=0;navigator.geolocation.getCurrentPosition=()=>window.__gpsCalls++;},!!scenario.dark);
 const page=await context.newPage(),errors=[],backend=[];
 page.on('pageerror',e=>errors.push(e.message));
 const loc={id:1,latitude:scenario.invalid?90:13.7563,longitude:100.5018,name:'<img src=x onerror=alert(1)>',slug:'chon-buri-city',timezone:'Asia/Bangkok',subdistrict:'ตำบลทดสอบ',district:'อำเภอทดสอบ',province:'กรุงเทพมหานคร',is_active:true};
 const hourly=Array.from({length:24},(_,i)=>({id:i,valid_time:new Date(Date.now()+i*3600000).toISOString(),temperature_2m:29,apparent_temperature:32,weather_code:61,precipitation_probability:60,precipitation:1,relative_humidity_2m:70,wind_speed_10m:10}));
 const daily=Array.from({length:7},(_,i)=>({id:i,forecast_date:new Date(Date.now()+i*86400000).toISOString().slice(0,10),temperature_2m_min:25,temperature_2m_max:33,weather_code:61,precipitation_sum:8,wind_speed_10m_max:12}));
 await page.route('**/api/backend/**',r=>{const url=r.request().url();backend.push(r.request().method());return r.fulfill({json:url.endsWith('/health')?{status:'ok'}:url.endsWith('/locations')?[loc]:url.includes('/air-quality/')?{status:'unavailable'}:{id:1,provider:'open_meteo',retrieved_at:new Date().toISOString(),hourly,daily}});});
 await page.route('https://static.line-scdn.net/**',r=>r.abort());
 const requests=await installMapMocks(page,scenario);
 await page.goto(process.env.DASHBOARD_QA_URL||'http://localhost:3103');await page.locator('.sample-picker summary').click();await page.locator('select').selectOption('1');await page.locator('.hero-actions').waitFor();
 assert.equal(requests.length,0);const before=backend.length;
 await page.locator('.hero-actions .map-button').click();await page.locator('.map-dialog').waitFor();
 await page.waitForTimeout(250);const rect=await page.locator('.map-dialog').boundingBox();assert.equal(Math.round(rect.y),0);assert.equal(Math.round(rect.height),900);
 if(scenario.invalid){await page.getByText('พื้นที่นี้ไม่มีพิกัดที่แสดงบนแผนที่ได้').waitFor();assert.equal(requests.filter(r=>r.kind==='base').length,0);}
 else{
 await page.locator('.weather-location-pin').waitFor();
 await page.waitForTimeout(600);
 assert(await page.getByRole('link',{name:'Weather data by RainViewer',exact:true}).isVisible());
 assert(await page.evaluate(()=>document.querySelector('.map-dialog').scrollWidth<=innerWidth),'Map overflow');
 if(['error','empty'].includes(scenario.metadata)){await page.getByText('ข้อมูลเรดาร์ไม่พร้อมใช้งาน แผนที่ยังเปิดดูได้').waitFor();assert(await page.locator('.radar-timeline button').isDisabled());}
 else{
 const range=page.locator('.map-dialog input[type=range]');await range.waitFor();await range.focus();await page.keyboard.press('Home');assert.equal(await range.inputValue(),'0');await page.keyboard.press('ArrowRight');assert.equal(await range.inputValue(),'1');
 if(scenario.metadata==='stale'){assert(await page.locator('.radar-timeline button').isDisabled());await page.getByText('ภาพเรดาร์อัปเดตล่าช้า โปรดตรวจเวลาภาพ').waitFor();}
 if(scenario.radarError)await page.getByText('ภาพบางส่วนโหลดไม่ได้').waitFor();
 if(scenario.baseError)await page.getByText('แผนที่บางส่วนโหลดไม่สำเร็จ ลองโหลดใหม่').waitFor();
 if(scenario.coverage==='uncovered')await page.getByText(/จุดนี้อยู่นอกขอบเขตข้อมูลเรดาร์/).waitFor();
 if(scenario.coverage==='error')await page.getByText(/ตรวจขอบเขตข้อมูลของจุดนี้ไม่ได้/).waitFor();
 if(scenario.name==='mobile-light'||scenario.name==='desktop-dark'){
 await page.locator('.coverage-toggle input').check();await page.waitForTimeout(300);assert(requests.some(r=>r.kind==='coverage'));await page.locator('.coverage-toggle input').uncheck();
 await page.getByRole('button',{name:'เรดาร์ฝน',exact:false}).click();assert(await range.isDisabled());await page.getByRole('button',{name:'เรดาร์ฝน',exact:false}).click();
 await page.getByRole('button',{name:'▶ เล่น',exact:true}).click();assert.equal(await page.locator('.radar-timeline button').getAttribute('aria-pressed'),'true');
 await page.waitForTimeout(8500);assert.notEqual(await range.inputValue(),'1','Playback did not advance');await page.getByRole('button',{name:'❚❚ หยุด',exact:true}).click();
 const canvas=await page.locator('.weather-map-canvas').boundingBox();await page.mouse.move(canvas.x+canvas.width/2,canvas.y+canvas.height/2);await page.mouse.down();await page.mouse.move(canvas.x+canvas.width/2+60,canvas.y+canvas.height/2+40,{steps:5});await page.mouse.up();
 await page.getByRole('button',{name:'⌖ กลับพื้นที่นี้',exact:true}).click();await page.locator('.leaflet-control-zoom-in').click();
 await page.screenshot({path:path.join(process.env.TEMP,'map-preview-'+scenario.name+'.png'),fullPage:false});
 }
 }
 const count=requests.filter(r=>r.kind==='metadata').length;await page.locator('.map-dialog').getByRole('button',{name:'โหลดใหม่',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.map-toolbar button:last-child')?.disabled===false);assert(requests.filter(r=>r.kind==='metadata').length>count);
 }
 await page.keyboard.press('Escape');await page.locator('.map-dialog').waitFor({state:'detached'});
 assert.equal(await page.evaluate(()=>document.body.style.overflow),'');assert(await page.locator('.hero-actions .map-button').evaluate(el=>document.activeElement===el),'Focus not restored');assert.equal(await page.evaluate(()=>window.__gpsCalls),0);
 assert.equal(backend.length,before);assert(backend.every(m=>m==='GET'));assert(requests.every(r=>r.method==='GET'));assert.equal(errors.length,0,errors.join(';'));
 const count=requests.length;await page.waitForTimeout(500);assert.equal(requests.length,count,'Map kept loading after close');
 report.push({scenario:scenario.name,status:'passed'});await context.close();
 }
 console.log(JSON.stringify({status:'passed',mockProviderTiles:true,productionWrites:0,report},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
