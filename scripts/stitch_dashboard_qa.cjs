const fs = require('fs'), path = require('path'), assert = require('assert');
const cache = path.join(process.env.LOCALAPPDATA, 'npm-cache', '_npx');
const entry = fs.readdirSync(cache).map(d => path.join(cache,d,'node_modules','playwright')).find(p => fs.existsSync(p));
if (!entry) throw Error('Playwright package missing');
const { chromium } = require(entry);
const stamp = new Date().toISOString();
const location = {id:1,name:'พื้นที่ทดสอบ',slug:'chon-buri-city',timezone:'Asia/Bangkok',subdistrict:'ตำบลชื่อยาวสำหรับทดสอบการจัดวาง',district:'อำเภอเมืองชลบุรี',province:'ชลบุรี',is_active:true};
const hours = Array.from({length:24},(_,i)=>({id:i,valid_time:new Date(Date.now()+(i+1)*3600000).toISOString(),temperature_2m:28+i%5,weather_code:61,precipitation_probability:65,precipitation:1.2,relative_humidity_2m:78,wind_speed_10m:14}));
const daily = Array.from({length:7},(_,i)=>({id:i,forecast_date:new Date(Date.now()+i*86400000).toISOString().slice(0,10),temperature_2m_min:25,temperature_2m_max:33,weather_code:61,precipitation_sum:8,wind_speed_10m_max:14}));
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const report=[];
 try {
  for(const width of [390,1440]) {
   const context=await browser.newContext({viewport:{width,height:1000}});
   await context.addInitScript(()=>localStorage.setItem('weather.theme','light'));
   const page=await context.newPage(), errors=[], requests=[];
   page.on('pageerror',e=>errors.push(e.message));
   await page.route('**/api/backend/**',route=>{
    requests.push({url:route.request().url(),method:route.request().method()});
    const url=route.request().url();
    const body=url.endsWith('/health')?{status:'ok'}:url.endsWith('/locations')?[location]:url.includes('/air-quality/')?{location_id:1,status:'available',stale:false,retrieved_at:stamp,current:{pm25:28.5,aqi:54,category:'moderate',valid_time:stamp},hourly:[]}: {id:1,provider:'open_meteo',retrieved_at:stamp,hourly:hours,daily};
    return route.fulfill({json:body});
   });
   await page.route('https://static.line-scdn.net/**',route=>route.abort());
   await page.goto('http://localhost:3100');
   await page.locator('.sample-picker summary').click();
   await page.locator('select').selectOption('1');
   await page.locator('.hero-actions').waitFor();
   assert.equal(await page.locator('.hourly-list article').count(),24);
   assert.equal(await page.locator('.forecast-day').count(),7);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Horizontal overflow');
   const before=requests.length;
   await page.getByRole('button',{name:'ดูแผนที่',exact:true}).click();
   await page.getByRole('heading',{name:'แผนที่ยังไม่เปิดใช้งาน'}).waitFor();
   await page.keyboard.press('Escape');
   await page.locator('dialog').waitFor({state:'detached'});
   assert.equal(requests.length,before,'Map triggered API request');
   await page.getByRole('button',{name:'แนวโน้มฝน',exact:true}).click();
   assert(await page.locator('.rain-chart').isVisible());
   await page.getByRole('button',{name:'แนวโน้มอุณหภูมิ',exact:true}).click();
   assert(await page.locator('.temperature-chart').isVisible());
   assert(!requests.some(r=>r.method!=='GET'),'Unexpected write request');
   assert(!requests.some(r=>r.url.includes('flood')),'Flood request');
   assert.equal(errors.length,0,errors.join('; '));
   await page.screenshot({path:'stitch-dashboard-'+width+'.png',fullPage:true});
   report.push({width,status:'passed',hourly:24,daily:7,mapRequests:0,pageErrors:0});
   await context.close();
  }
  console.log(JSON.stringify({status:'passed',mockData:true,productionWrites:0,report},null,2));
 } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exit(1)});
