const fs=require('fs'),path=require('path'),assert=require('assert');
const cache=path.join(process.env.LOCALAPPDATA,'npm-cache','_npx');
const entry=fs.readdirSync(cache).map(d=>path.join(cache,d,'node_modules','playwright')).find(p=>fs.existsSync(p));
const {chromium}=require(entry),{installMapMocks}=require('./map_test_fixtures.cjs');
const UID='U'+'a'.repeat(32);
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true}),report=[];
 try{for(const scenario of [
 {name:'mobile-light',width:360,insecureUuid:true},{name:'mobile-dark',width:390,dark:true},{name:'desktop-light',width:1440},{name:'desktop-dark',width:1440,dark:true},{name:'external-mobile',width:390,external:true},{name:'external-desktop',width:1440,external:true},
 {name:'friend-config-error',friendConfigFailure:true},{name:'config-load-error',configLoadFailure:true},{name:'signup-disabled',signupDisabled:true},{name:'gps-denied',gpsDenied:true},{name:'friend-service-down',friendFailure:true},{name:'expired-session',expired:true,external:true},{name:'expired-liff-session',expired:true},{name:'cached-id-token',staleIdToken:true},
 {name:'enable-failed',enableFailure:true},{name:'disable-pending',pendingDisable:true,ready:true},{name:'disable-failed',disableFailure:true,ready:true},{name:'blocked-account',blocked:true,ready:true}
 ]){
 const context=await browser.newContext({viewport:{width:scenario.width||390,height:1000}});
 await context.addInitScript(s=>{
 localStorage.setItem('weather.theme',s.dark?'dark':'light');
 if(s.insecureUuid)Object.defineProperty(crypto,'randomUUID',{value:undefined});
 if(s.friendConfigFailure||s.friendFailure||s.expired||s.ready||s.staleIdToken)localStorage.setItem('qa.lineSignedIn','1');
 navigator.geolocation.getCurrentPosition=(success,failure)=>s.gpsDenied?failure({code:1}):success({coords:{latitude:13.7563,longitude:100.5018}});
 },scenario);
 const page=await context.newPage(),errors=[],requests=[];
 let heldDisable,notice;const held=new Promise(resolve=>notice=resolve);
 page.on('pageerror',e=>errors.push(e.message));
 let friend=!!scenario.ready,located=!!scenario.ready,enabled=!!scenario.ready;
 if(scenario.blocked){friend=false;enabled=false;}
 const loc={id:1,name:'พื้นที่ทดสอบ',slug:'chon-buri-city',latitude:13.7563,longitude:100.5018,timezone:'Asia/Bangkok',subdistrict:'ตำบลทดสอบ',district:'อำเภอทดสอบ',province:'กรุงเทพมหานคร',is_active:true};
 const hourly=Array.from({length:24},(_,i)=>({id:i,valid_time:new Date(Date.now()+(i+1)*3600000).toISOString(),temperature_2m:29,apparent_temperature:32,weather_code:61,precipitation_probability:50,precipitation:1,relative_humidity_2m:70,wind_speed_10m:10}));
 const daily=Array.from({length:7},(_,i)=>({id:i,forecast_date:new Date(Date.now()+i*86400000).toISOString().slice(0,10),temperature_2m_min:25,temperature_2m_max:33,weather_code:61,precipitation_sum:5,wind_speed_10m_max:15}));
 const forecast={id:1,location_id:1,provider:'open_meteo',retrieved_at:new Date().toISOString(),hourly,daily};
 const status=()=>({external_user_id:UID,friend,location_verified:located,location_id:located?loc.id:null,enabled,ready:friend&&located&&enabled,consent_version:'weather-alerts-v1',next_step:!friend?'friend':!located?'location':!enabled?'consent':'ready'});
 await page.route('https://static.line-scdn.net/**',route=>route.fulfill({contentType:'application/javascript',body:"window.liff={init:async()=>{},isLoggedIn:()=>localStorage.getItem('qa.lineSignedIn')==='1',logout:()=>{localStorage.removeItem('qa.lineSignedIn');localStorage.setItem('qa.reauth','1');localStorage.setItem('qa.logoutCalls',String(Number(localStorage.getItem('qa.logoutCalls')||0)+1))},login:()=>{localStorage.setItem('qa.lineSignedIn','1');localStorage.setItem('qa.loginCalls',String(Number(localStorage.getItem('qa.loginCalls')||0)+1));location.reload()},getIDToken:()=> 'mock-id-token',getAccessToken:()=>localStorage.getItem('qa.reauth')?'mock-fresh-token':'mock-access-token',isInClient:()=>"+(!scenario.external)+",requestFriendship:async()=>{await fetch('/__qa/friend')}};"}));
 await context.route('https://line.me/**',r=>{friend=true;return r.fulfill({contentType:'text/html',body:'<html><body>Mock Weather friend page</body></html>'});});
 await page.route('**/__qa/friend',r=>{friend=true;return r.fulfill({json:{ok:true}})});
 await page.route('**/api/backend/**',r=>{
 const url=new URL(r.request().url()).pathname.replace('/api/backend',''),method=r.request().method();requests.push({url,method,body:r.request().postData()});
 if(url.endsWith('/onboarding/config'))return scenario.configLoadFailure?r.fulfill({status:503,json:{detail:'proxy unavailable'}}):r.fulfill({json:{enabled:!scenario.signupDisabled,add_friend_url:'https://line.me/R/ti/p/%40weather'}});
 if(url.endsWith('/line/auth'))return r.fulfill({json:{external_user_id:UID}});
 if(url.endsWith('/line/onboarding')){
 if(scenario.expired&&r.request().headers().authorization!=='Bearer mock-fresh-token')return r.fulfill({status:401,json:{detail:'session expired'}});
 if(scenario.friendConfigFailure)return r.fulfill({status:503,json:{detail:'Weather friendship verification is not configured.'}});
 if(scenario.friendFailure)return r.fulfill({status:503,json:{detail:'friend service unavailable'}});
 return r.fulfill({json:status()});
 }
 if(url.endsWith('/line/subscription')){
 assert.equal(method,'PUT');
 assert.equal(r.request().headers().authorization,'Bearer mock-access-token');
 const body=r.request().postDataJSON();
 if((body.enabled&&scenario.enableFailure)||(!body.enabled&&scenario.disableFailure))return r.fulfill({status:502,json:{detail:'temporarily unavailable'}});
 if(scenario.pendingDisable&&!body.enabled){heldDisable=r;notice();return;}
 if(body.enabled)assert.equal(body.consent_version,'weather-alerts-v1');
 enabled=body.enabled;return r.fulfill({json:status()});
 }
 if(url.endsWith('/line/location/from-gps')){
 assert.equal(method,'POST');
 assert.equal(r.request().headers().authorization,'Bearer mock-access-token');
 located=true;return r.fulfill({json:{external_user_id:UID,location:loc}});
 }
 if(url.endsWith('/line/forecast/refresh')){assert.equal(method,'POST','Forecast refresh must use POST');assert.equal(r.request().headers().authorization,'Bearer mock-access-token');return r.fulfill({status:201,json:{location_id:loc.id,timezone:loc.timezone}}); }
 if(url.endsWith('/line/forecast'))return r.fulfill({json:forecast});
 if(url.endsWith('/health'))return r.fulfill({json:{status:'ok'}});
 if(url.endsWith('/locations'))return r.fulfill({json:[loc]});
 if(url.includes('/air-quality/'))return r.fulfill({json:{status:'unavailable'}});
 throw Error('Unmocked backend route '+url);
 });
 await installMapMocks(page);
 await page.route('https://liff.line.me/**',r=>r.fulfill({contentType:'text/html',body:'<html><body>Mock LIFF relaunch</body></html>'}));
 await page.goto(process.env.LINE_ONBOARDING_QA_URL||'http://localhost:3103');
 const panel=page.locator('.line-onboarding');
 await panel.waitFor();await page.waitForTimeout(400);
 if(scenario.configLoadFailure){await panel.getByRole('alert').waitFor();assert((await panel.getByRole('alert').innerText()).includes('โหลดสถานะระบบสมัครแจ้งเตือนไม่สำเร็จ'));assert.equal(await panel.locator('[role="status"]').count(),0,'Config network error claimed feature disabled');assert(await panel.locator('.gps-primary').isDisabled());}
 else if(scenario.signupDisabled){await panel.locator('[role="status"]').waitFor();assert(await panel.locator('.gps-primary').isDisabled());}
 else if(scenario.friendConfigFailure){await panel.getByRole('alert').waitFor();assert((await panel.getByRole('alert').innerText()).includes('ตรวจสถานะเพื่อน Weather ไม่สำเร็จ'));assert(!(await panel.getByRole('alert').innerText()).includes('ระบบสมัครแจ้งเตือนยังไม่เปิดใช้งาน'));assert(!enabled);}
 else if(scenario.friendFailure){await panel.getByRole('alert').waitFor();assert(!(await panel.getByRole('alert').innerText()).includes('ระบบสมัครแจ้งเตือนยังไม่เปิดใช้งาน'));assert(!enabled);assert.equal(await panel.locator('.line-ready-badge.ready').count(),0);}
 else if(scenario.expired){
  await panel.getByRole('alert').waitFor();
  await panel.locator('.line-onboarding-steps li:first-child button').click();
  if(scenario.external){
   await panel.locator('.line-status .line-dot.connected').waitFor();
   assert.equal(await page.evaluate(()=>localStorage.getItem('qa.logoutCalls')),'1');
   assert.equal(await page.evaluate(()=>localStorage.getItem('qa.loginCalls')),'1');
   assert(requests.some(r=>r.url.endsWith('/line/onboarding')));
  }else{await page.waitForURL('https://liff.line.me/**');assert(await page.getByText('Mock LIFF relaunch').isVisible());}
  assert(!enabled);
 }
 else if(scenario.staleIdToken){await panel.locator('.line-status .line-dot.connected').waitFor();assert(!requests.some(r=>r.url.endsWith('/line/auth')),'Unnecessary cached ID-token verification');}
 else if(scenario.blocked){await panel.getByRole('button',{name:'เพิ่มเพื่อน',exact:true}).waitFor();assert.equal(await panel.locator('.line-ready-badge.ready').count(),0);assert(await panel.getByRole('button',{name:'เปิดรับแจ้งเตือน',exact:true}).isDisabled());}
 else if(scenario.pendingDisable){await panel.getByRole('button',{name:'ปิดแจ้งเตือน',exact:true}).click();await held;const before=requests.filter(r=>r.url.endsWith('/line/onboarding')).length;await page.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')));await page.waitForTimeout(200);assert.equal(requests.filter(r=>r.url.endsWith('/line/onboarding')).length,before,'Refresh raced with opt-out');enabled=false;await heldDisable.fulfill({json:status()});await panel.locator('.line-consent input').waitFor();assert.equal(await panel.locator('.line-ready-badge.ready').count(),0);}
 else if(scenario.disableFailure){await panel.getByRole('button',{name:'ปิดแจ้งเตือน',exact:true}).click();await panel.getByRole('alert').waitFor();assert.equal(await panel.locator('.line-ready-badge.ready').count(),0);assert(enabled,'Failed disable should not pretend server succeeded');assert(await panel.getByRole('button',{name:'ปิดแจ้งเตือน',exact:true}).isVisible(),'Cannot retry failed disable');scenario.disableFailure=false;await panel.getByRole('button',{name:'ปิดแจ้งเตือน',exact:true}).click();await panel.locator('.line-consent input').waitFor();assert(!enabled);}
 else{
 assert.equal(await page.evaluate(()=>localStorage.getItem('qa.lineSignedIn')),null,'Unexpected automatic login');
 await panel.getByRole('button',{name:'ล็อกอิน LINE',exact:true}).click();
 await panel.getByText('เชื่อมบัญชี LINE แล้ว',{exact:true}).waitFor();
 if(scenario.external){const popup=context.waitForEvent('page');await panel.getByRole('button',{name:'เพิ่มเพื่อน',exact:true}).click();const friendPage=await popup;await friendPage.waitForLoadState('domcontentloaded');await friendPage.close();await panel.getByRole('button',{name:'ตรวจสถานะ',exact:true}).click();}
 else await panel.getByRole('button',{name:'เพิ่มเพื่อน',exact:true}).click();
 await panel.getByText('เพิ่มเพื่อนแล้ว',{exact:true}).waitFor();
 await panel.getByRole('button',{name:'ใช้ตำแหน่ง',exact:true}).click();
 if(scenario.gpsDenied){await page.getByRole('alert').first().waitFor();assert(!located);assert(await panel.getByRole('button',{name:'เปิดรับแจ้งเตือน',exact:true}).isDisabled());}
 else{
 await panel.getByText('บันทึกพื้นที่แล้ว',{exact:true}).waitFor();
 await page.locator('.hero-actions').waitFor();
 assert(await panel.getByRole('button',{name:'เปิดรับแจ้งเตือน',exact:true}).isDisabled(),'Enabled without explicit consent');
 await page.screenshot({path:path.join(process.env.TEMP,'line-onboarding-setup-'+scenario.name+'.png'),fullPage:true});
 await panel.locator('.line-consent input').check();await panel.getByRole('button',{name:'เปิดรับแจ้งเตือน',exact:true}).click();
 if(scenario.enableFailure){await panel.getByRole('alert').waitFor();assert.equal(await panel.locator('.line-ready-badge.ready').count(),0);assert(!enabled);}
 else{
 await panel.locator('.line-ready-badge.ready').waitFor();
 const headerDot=page.locator((scenario.width||390)<900?'.header-line-mobile .line-dot':'.header-line .line-dot');
 assert.equal(await headerDot.evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(36, 200, 121)');
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Horizontal overflow');
 const actions=panel.locator('.line-onboarding-actions button');
 assert.equal(await actions.count(),3,'Ready state must expose all three actions');
 let checked=page.waitForResponse(r=>r.url().endsWith('/line/onboarding')&&r.request().method()==='GET');
 await actions.nth(1).click();
 let checkedState=await (await checked).json();assert(checkedState.ready&&checkedState.enabled,'Status check changed consent');
 await actions.nth(2).waitFor({state:'visible'});await page.waitForFunction(()=>!document.querySelector('.line-onboarding-actions button:last-child').disabled);
 loc.id=2;forecast.location_id=2;
 await page.evaluate(()=>{navigator.geolocation.getCurrentPosition=success=>success({coords:{latitude:13.7,longitude:100.4}})});
 const changed=page.waitForResponse(r=>r.url().endsWith('/line/forecast')&&r.request().method()==='GET');
 await actions.nth(2).click();
 assert.equal((await (await changed).json()).location_id,2,'Changed area forecast was not loaded');
 assert.equal(JSON.parse(requests.filter(r=>r.url.endsWith('/line/location/from-gps')).at(-1).body).latitude,13.7,'Change area did not use new GPS coordinates');
 await page.waitForFunction(()=>!document.querySelector('.line-onboarding-actions button:nth-child(2)').disabled);
 checked=page.waitForResponse(r=>r.url().endsWith('/line/onboarding')&&r.request().method()==='GET');
 await actions.nth(1).click();checkedState=await (await checked).json();
 assert.equal(checkedState.location_id,2,'Changed notification area was not retained');
 assert(checkedState.ready&&checkedState.enabled,'Change area lost enabled consent');
 await page.waitForFunction(()=>!document.querySelector('.line-onboarding-actions button:first-child').disabled);

 await page.screenshot({path:path.join(process.env.TEMP,'line-onboarding-'+scenario.name+'.png'),fullPage:true});
 await panel.getByRole('button',{name:'ปิดแจ้งเตือน',exact:true}).click();
 await panel.locator('.line-consent input').waitFor();assert(!enabled);assert(!(await panel.locator('.line-consent input').isChecked()));
 }
 }
 }
 assert(!requests.some(r=>r.url.includes('/users/')),'Used unscoped identity route during signup');
 assert(!requests.some(r=>r.url.includes('send')),'Sent a LINE message');
 assert.equal(errors.length,0,errors.join(';'));report.push({scenario:scenario.name,status:'passed'});await context.close();
 }console.log(JSON.stringify({status:'passed',lineAndBackend:'mocked',productionWrites:0,report},null,2));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
