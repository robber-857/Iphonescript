const BASE='http://127.0.0.1:8765';
let busy=false;
async function clearAppleCookies(tabId){
 const stores=await chrome.cookies.getAllCookieStores();
 const store=stores.find(s=>s.tabIds.includes(tabId));
 if(!store)throw Error('无法确认指定页 Cookie 存储区');
 const cookies=await chrome.cookies.getAll({domain:'apple.com',storeId:store.id});
 for(const cookie of cookies){
  const domain=cookie.domain.replace(/^\./,'');
  if(domain!=='apple.com'&&!domain.endsWith('.apple.com'))continue;
  const details={url:'https://'+domain+cookie.path,name:cookie.name,storeId:store.id};
  if(cookie.partitionKey)details.partitionKey=cookie.partitionKey;
  await chrome.cookies.remove(details);
 }
 const remaining=await chrome.cookies.getAll({domain:'apple.com',storeId:store.id});
 if(remaining.length)throw Error('Apple Cookie 未完全清除');
}
function supported(url){return /^https:\/\/www\.apple\.com\/au\/shop\/buy-iphone\/(iphone-duo|iphone-18-pro)\//.test(url||'')}
async function badge(text,title){
 await chrome.action.setBadgeText({text});
 await chrome.action.setTitle({title});
}
async function release(){
 await chrome.storage.local.remove(['task','tabId','manualBinding']);
 await badge('选页','请手动打开 Apple 商品页，点击此图标指定采集页');
}
async function showCollector(url,tabId){
 const tab=await chrome.tabs.get(tabId);
 if(!supported(tab.url))throw Error('指定页已离开 Apple 商品页，请重新指定');
 await chrome.tabs.update(tabId,{active:true});
 await chrome.windows.update(tab.windowId,{focused:true});
 if(tab.url.split('?')[0]===url)await chrome.tabs.reload(tabId);
 else await chrome.tabs.update(tabId,{url});
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
  const old=await chrome.storage.local.get(['task','tabId','manualBinding']);
  if(!old.manualBinding||!old.tabId){await badge('选页','请手动打开 Apple 商品页，点击此图标指定采集页');return}
  let selected;
  try{selected=await chrome.tabs.get(old.tabId)}catch{await release();return}
  if(!supported(selected.url)){await release();return}
  const {task,cleanup}=await api('/api/collector/task');
  if(cleanup){
   let error=false;
   try{await clearAppleCookies(old.tabId)}catch(e){error=true;console.warn('Apple Cookie cleanup failed')}
   await api('/api/collector/cleanup',{id:cleanup,error});
   await chrome.storage.local.remove('task');
   return;
  }
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
  await showCollector(task.variant.url,old.tabId);
 }catch(e){console.warn('Duo collector:',e.message)}finally{busy=false}
}
chrome.runtime.onInstalled.addListener(async()=>{await release();chrome.alarms.create('poll',{periodInMinutes:0.5});poll()});
chrome.runtime.onStartup.addListener(async()=>{await release();chrome.alarms.create('poll',{periodInMinutes:0.5});poll()});
chrome.alarms.onAlarm.addListener(a=>{if(a.name==='poll')poll()});
chrome.action.onClicked.addListener(async tab=>{
 if(!supported(tab.url)){await badge('选页','请先打开 Duo 或 Pro 的具体商品配置页，再点击图标');return}
 // Wait for an in-flight poll before changing the user-selected target.
 if(busy){await badge('稍候','正在结束当前操作，请稍后再点一次指定采集页');return}
 await chrome.storage.local.remove('task');
 await chrome.storage.local.set({tabId:tab.id,manualBinding:true});
 await badge('已选','已指定此 Apple 标签页为采集页；关闭后需重新指定');
 poll();
});
chrome.tabs.onRemoved.addListener(async tabId=>{
 const saved=await chrome.storage.local.get('tabId');
 if(saved.tabId===tabId)await release();
});
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
