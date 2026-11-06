// Playwright CLI run-code function: real page + collector + backend bridge.
// This does not test extension installation or Chrome alarms.
async (page) => {
 const base='http://127.0.0.1:8766';
 const state=await (await page.request.get(base+'/api/state')).json();
 if(state.phone.enabled)throw Error('Disable automatic calls before testing');
 const headers={'X-Duo-Token':state.token};
 const {task}=await (await page.request.get(base+'/api/collector/task',{headers})).json();
 if(!task)return {finished:true};
 if(!/^[0-9]{5}$/.test(task.postcode))throw Error('Unexpected ZIP');
 await page.goto(task.variant.url);
 if(!await page.evaluate(()=>typeof window.duoLiveSubmit==='function')){
  await page.exposeFunction('duoLiveSubmit',async result=>{
   const response=await page.request.post(base+'/api/collector/result',{headers,data:result});
   if(!response.ok())return {error:'Backend '+response.status()};
   return {ok:true};
  });
 }
 await page.evaluate(()=>{window.chrome={runtime:{onMessage:{addListener(){}},sendMessage:async msg=>{
  if(msg.type==='result'){window.liveResult=msg.result;return window.duoLiveSubmit(msg.result)}
  return {};
 }}}});
 await page.addScriptTag({path:'collector/page-input.js'});
 await page.addScriptTag({path:'collector/content.js'});
 await page.evaluate(task=>collect(task),task);
 const r=await page.evaluate(()=>window.liveResult);return {variant:task.variant.id,stores:r?.stores?.length,available:r?.stores?.filter(s=>s.status==='available').length,error:r?.error};
}
