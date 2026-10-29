const BASE='http://127.0.0.1:8765';
let busy=false;
async function showCollector(url,tabId){
 const dashboards=await chrome.tabs.query({url:BASE+'/*'});
 const current=await chrome.windows.getLastFocused({windowTypes:['normal']});
 const dashboard=dashboards.find(t=>t.windowId===current.id)||dashboards[0];
 let tab;
 if(tabId)try{
  tab=await chrome.tabs.get(tabId);
  if(dashboard&&tab.windowId!==dashboard.windowId)await chrome.tabs.move(tabId,{windowId:dashboard.windowId,index:-1});
  tab=await chrome.tabs.update(tabId,{url,active:true});
 }catch{tab=null}
 if(!tab){
  tab=await chrome.tabs.create({url,active:true,windowId:dashboard?.windowId??current.id});
 }
 await chrome.windows.update(tab.windowId,{focused:true});
 return tab;
}
async function api(path,body){
 const state=await (await fetch(BASE+'/api/state')).json();
 const options={headers:{'X-Duo-Token':state.token}};
 if(body){options.method='POST';options.headers['Content-Type']='application/json';options.body=JSON.stringify(body)}
 const res=await fetch(BASE+path,options);if(!res.ok)throw Error('Backend '+res.status);return res.json();
}
async function poll(){
 if(busy)return;busy=true;
 try{
  const {task}=await api('/api/collector/task');const old=await chrome.storage.local.get(['task','tabId']);
  if(!task){await chrome.storage.local.remove('task');return}
  if(old.task?.id===task.id){
   if(old.tabId)try{
    const reply=await chrome.tabs.sendMessage(old.tabId,{type:'collect',task});
    if(!reply?.accepted)await showCollector(task.variant.url,old.tabId);
   }catch{
    try{await chrome.tabs.reload(old.tabId)}catch{await chrome.storage.local.remove(['task','tabId'])}
   }
   return;
  }
  await chrome.storage.local.set({task});
  const tab=await showCollector(task.variant.url,old.tabId);
  await chrome.storage.local.set({tabId:tab.id});
 }catch(e){console.warn('Duo collector:',e.message)}finally{busy=false}
}
chrome.runtime.onInstalled.addListener(async()=>{await chrome.storage.local.remove('task');chrome.alarms.create('poll',{periodInMinutes:0.5});poll()});
chrome.runtime.onStartup.addListener(()=>{chrome.alarms.create('poll',{periodInMinutes:0.5});poll()});
chrome.alarms.onAlarm.addListener(a=>{if(a.name==='poll')poll()});
chrome.action.onClicked.addListener(()=>chrome.tabs.create({url:BASE}));
chrome.runtime.onMessage.addListener((msg,sender,respond)=>{
 (async()=>{
  const saved=await chrome.storage.local.get(['task','tabId']);
  if(sender.tab?.id!==saved.tabId)return {ignored:true};
  if(msg.type==='ready')return {task:saved.task};
  if(msg.type==='result'){
   await api('/api/collector/result',msg.result);
   await chrome.storage.local.remove('task');
   // Alarm provides durable scheduling if service worker is suspended.
   setTimeout(poll,2000);
   return {ok:true};
  }
 })().then(respond).catch(e=>respond({error:e.message}));return true;
});
