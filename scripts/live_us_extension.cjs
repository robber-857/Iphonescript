/** Real extension smoke run. Requires Playwright + its bundled Chromium.
 * node scripts/live_us_extension.cjs 97204 duo
 * Uses an isolated browser profile, pauses monitoring on exit, never configures phone.
 * Binding the selected tab is simulated through the extension's own storage/API;
 * all subsequent polling, page scripts, ZIP input and result uploads are real.
 */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs'),path=require('node:path');
const zip=process.argv[2],model=process.argv[3]||'pro-test';
if(!/^[0-9]{5}$/.test(zip)||!['duo','pro-test'].includes(model))throw Error('Usage: node scripts/live_us_extension.cjs ZIP [duo|pro-test]');
const base='http://127.0.0.1:8766';
let token,context,originalSettings,started=false;
const output=path.resolve('output/playwright');
async function api(route,data){
 const res=await fetch(base+'/api/'+route,{headers:{'X-Duo-Token':token||'','Content-Type':'application/json'},...(data===undefined?{}:{method:'POST',body:JSON.stringify(data)})});
 const value=await res.json();if(!res.ok)throw Error(value.error||String(res.status));return value;
}
(async()=>{
 fs.mkdirSync(output,{recursive:true});
 const initial=await api('state');token=initial.token;originalSettings={notifications:initial.notifications,clear_apple_cookies:initial.clear_apple_cookies,interval:initial.interval};
 if(initial.phone.enabled)throw Error('Disable automatic phone alerts before live smoke testing.');
 await api('pause',{});started=true;
 await api('settings',{postcode:zip,model,interval:300,notifications:false,clear_apple_cookies:true});
 const ext=path.resolve('collector');
 context=await chromium.launchPersistentContext(path.resolve('.tmp/us-extension-'+Date.now()),{channel:'chromium',headless:false,args:['--disable-extensions-except='+ext,'--load-extension='+ext]});
 let [worker]=context.serviceWorkers();if(!worker)worker=await context.waitForEvent('serviceworker');
 const page=await context.newPage();
 page.on('response',response=>{if(response.status()>=400)console.log(JSON.stringify({phase:'http-error',status:response.status(),url:response.url().split('?')[0]}))});
 page.on('requestfailed',request=>console.log(JSON.stringify({phase:'request-failed',url:request.url().split('?')[0],error:request.failure()?.errorText})));

 const configured=await api('state');await page.goto(configured.variants[0].url);
 // Simulate the user selecting this tab via the action button, then use
 // the unmodified service worker and Chrome alarms for the complete cycle.
 const bound=await worker.evaluate(async url=>{
  const tabs=await chrome.tabs.query({});const tab=tabs.find(t=>t.url===url);if(!tab)throw Error('Product tab not found');
  await chrome.storage.local.remove('task');await chrome.storage.local.set({tabId:tab.id,manualBinding:true});
  await badge('已选','美国站真实扩展测试');return {tabId:tab.id,version:chrome.runtime.getManifest().version};
 },configured.variants[0].url);
 console.log(JSON.stringify({phase:'bound',zip,model,...bound}));
 const begun=Date.now()/1000;await api('start',{});await worker.evaluate(()=>poll());
 const deadline=Date.now()+300000;let previous='';let final;
 while(Date.now()<deadline){
  const state=await api('state');
  if(state.current!==previous){previous=state.current;console.log(JSON.stringify({phase:'progress',current:state.current,results:Object.keys(state.results).length}));}
  if(state.last_cycle>=begun&&!state.running&&!state.cookie_cleanup){final=state;break;}
  await new Promise(r=>setTimeout(r,1000));
 }
 if(!final)throw Error('Extension cycle did not complete in 5 minutes');
 const results=Object.entries(final.results).map(([id,r])=>({id,error:r.error,checked:r.checked,stores:r.stores}));
 const evidence={tested_at:new Date().toISOString(),zip,model,extension:bound.version,last_cycle:final.last_cycle,next_check:final.next_check,cookie_cleanup:final.events.find(e=>e.message.includes('Cookie 清理完成')),results};
 fs.writeFileSync(path.join(output,model+'-'+zip+'-extension.json'),JSON.stringify(evidence,null,2));
 const failures=results.filter(r=>r.error||!r.stores.length||r.checked<begun);
 if(results.length!==configured.variants.length||failures.length){
  await page.screenshot({path:path.join(output,'extension-failure.png'),fullPage:true});
  console.log(JSON.stringify(await page.evaluate(()=>({url:location.href,title:document.title,body:document.body.innerText.slice(0,350),inputs:Array.from(document.querySelectorAll('input[type=radio]')).map(e=>({name:e.name,value:e.value,checked:e.checked,disabled:e.disabled})),pickup:Array.from(document.querySelectorAll('[data-autom^=productLocatorTriggerLink_]')).map(e=>({text:e.textContent,visible:e.getClientRects().length}))}))));
  throw Error('Incomplete/failed real results: '+JSON.stringify(failures));
 }
 if(!evidence.cookie_cleanup||evidence.cookie_cleanup.time<begun)throw Error('No successful cookie cleanup acknowledgement');
 if(Math.abs(final.next_check-evidence.cookie_cleanup.time-300)>2)throw Error('Incorrect post-cleanup interval');
 await api('pause',{});
 const dashboard=await context.newPage();await dashboard.goto(base);await dashboard.locator('#rows tr').first().waitFor();
 await dashboard.screenshot({path:path.join(output,model+'-'+zip+'-extension.png'),fullPage:true});
 console.log(JSON.stringify({phase:'complete',variants:results.length,rows:results.reduce((n,r)=>n+r.stores.length,0),available:results.reduce((n,r)=>n+r.stores.filter(s=>s.status==='available').length,0),cleanup:true,paused:true}));
})().catch(e=>{console.error(e.stack);process.exitCode=1}).finally(async()=>{
 if(started){try{await api('pause',{});await api('settings',{postcode:zip,model,interval:300,...originalSettings})}catch(e){console.error(e.message)}}
 if(context)await context.close();
});
