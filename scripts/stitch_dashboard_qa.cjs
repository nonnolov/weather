const fs = require('fs'), path = require('path'), assert = require('assert');
const cache = path.join(process.env.LOCALAPPDATA, 'npm-cache', '_npx');
const entry = fs.readdirSync(cache).map(d => path.join(cache,d,'node_modules','playwright')).find(p => fs.existsSync(p));
if (!entry) throw Error('Playwright package missing');
const { chromium } = require(entry);
const stamp = new Date().toISOString();
const location = {id:1,name:'พื้นที่ทดสอบ',slug:'chon-buri-city',timezone:'Asia/Bangkok',subdistrict:'ตำบลชื่อยาวสำหรับทดสอบการจัดวาง',district:'อำเภอเมืองชลบุรี',province:'ชลบุรี',is_active:true};
const hours = Array.from({length:24},(_,i)=>({id:i,valid_time:new Date(Date.now()+(i+1)*3600000).toISOString(),temperature_2m:28+i%5,apparent_temperature:31+i%5,weather_code:[61,0,2,3,95,45,71][i%7],precipitation_probability:65,precipitation:1.2,relative_humidity_2m:78,wind_speed_10m:14}));
const daily = Array.from({length:7},(_,i)=>({id:i,forecast_date:new Date(Date.now()+i*86400000).toISOString().slice(0,10),temperature_2m_min:25,temperature_2m_max:33,weather_code:[61,0,2,3,95,45,71][i%7],precipitation_sum:8,wind_speed_10m_max:14}));
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const report=[];
 try {
  for(const {width,theme} of [{width:320,theme:"dark"},{width:360,theme:"light"},{width:390,theme:"light"},{width:1440,theme:"light"},{width:390,theme:"dark"},{width:1440,theme:"dark"},{width:1024,theme:"light"},{width:1280,theme:"dark"},{width:1366,theme:"dark"},{width:1920,theme:"dark"}]) {
   const context=await browser.newContext({viewport:{width,height:1000},colorScheme:theme==="light"?"dark":"light"});
   await context.addInitScript(theme=>localStorage.setItem('weather.theme',theme),theme);
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
   if(width<900) assert(await page.locator('.header-line-mobile .line-dot').isVisible(),'Mobile LINE indicator hidden');
   if(width>=900) {
    assert(await page.locator('.header-line .line-dot').isVisible(),'Desktop LINE indicator hidden');
    const province=page.locator('.header-location strong');
    assert.equal(await province.innerText(),location.province);
    assert(await province.evaluate(el=>el.scrollWidth<=el.clientWidth),'Province clipped');
   }

   const artwork=page.locator('img.weather-artwork');
   await artwork.evaluateAll(images=>images.forEach(img=>img.loading='eager'));
   await page.waitForFunction(()=>Array.from(document.querySelectorAll('img.weather-artwork')).every(img=>img.complete&&img.naturalWidth>0));
   const sources=await page.locator('.hourly-list img.weather-artwork').evaluateAll(images=>images.map(img=>new URL(img.src).searchParams.get('url')));
   for(const name of ['clear','partly-cloudy','cloudy','rain','storm','fog','snow']) assert(sources.includes('/weather/'+name+'.png'),'Missing condition artwork: '+name);

   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Horizontal overflow');
   const before=requests.length;
   await page.locator('.hero-actions .map-button').click();
   await page.getByRole('heading',{name:'แผนที่ยังไม่เปิดใช้งาน'}).waitFor();
   await page.keyboard.press('Escape');
   await page.locator('dialog').waitFor({state:'detached'});
   assert.equal(requests.length,before,'Map triggered API request');
   await page.getByRole('button',{name:'แนวโน้มฝน',exact:true}).click();
   assert(await page.locator('.rain-chart').isVisible());
   await page.getByRole('button',{name:'แนวโน้มอุณหภูมิ',exact:true}).click();
   assert(await page.locator('.temperature-chart').isVisible());
   await page.locator('.chart-inspector input').focus(); await page.keyboard.press('Home'); await page.keyboard.press('ArrowRight');
   assert((await page.locator('.chart-tooltip time').innerText()).length > 0);
   await page.locator('.chart-plot').scrollIntoViewIfNeeded();
   const plot=await page.locator('.trend-svg').boundingBox();
   await page.mouse.move(plot.x+plot.width*0.52,plot.y+plot.height*0.5);
   assert.equal(await page.locator('.chart-inspector input').inputValue(),'12','Pointer inspection failed');
   await page.locator('.day-summary').first().click();
   assert(await page.locator('.forecast-day[open] .day-details').isVisible());
   const expected=theme==='dark'?'rgb(0, 0, 0)':'rgb(255, 255, 255)';
   assert.equal(await page.evaluate(()=>getComputedStyle(document.body).backgroundColor),expected,'Selected theme lost to OS preference');
   assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).backgroundColor),expected,'Scroll canvas theme mismatch');
   assert.equal(await page.locator('meta[name="theme-color"]').getAttribute('content'),theme==='dark'?'#000000':'#ffffff','Browser bar theme mismatch');
   await page.emulateMedia({reducedMotion:'reduce'});
   assert.equal(await page.locator('.chart-card').evaluate(el=>getComputedStyle(el).animationName),'none');
   await page.emulateMedia({reducedMotion:'no-preference'});
   assert(!requests.some(r=>r.method!=='GET'),'Unexpected write request');
   assert(!requests.some(r=>r.url.includes('flood')),'Flood request');
   assert.equal(errors.length,0,errors.join('; '));
   assert(!(await page.locator('.hero-reading').innerText()).includes('NaN'));
   await page.locator('.day-summary').first().click();
   await page.locator('.sample-picker summary').click();
   await page.evaluate(()=>window.scrollTo(0,0));
   await page.waitForTimeout(400);
   assert.equal(await page.locator('.dashboard-header').evaluate(el=>Math.round(el.getBoundingClientRect().top)),0);
   await page.evaluate(()=>document.fonts.ready);
   assert(await page.evaluate(()=>document.fonts.check('400 15px "IBM Plex Sans Thai"')),'Thai font unavailable');
   await page.getByRole('button',{name:'ภาษา',exact:true}).click();
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'English overflow');
   await page.getByRole('button',{name:'Language',exact:true}).click();
   await page.evaluate(()=>document.querySelectorAll('.hourly-list').forEach(el=>el.scrollLeft=0));
   await page.screenshot({path:'stitch-dashboard-'+width+'-'+theme+'.png',fullPage:true});
   report.push({width,theme,status:'passed',hourly:24,daily:7,mapRequests:0,pageErrors:0});
   await context.close();
  }
  console.log(JSON.stringify({status:'passed',mockData:true,productionWrites:0,report},null,2));
 } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exit(1)});