const stores={R238:'Apple Sydney',R523:'Apple Broadway',R254:'Apple Bondi',R253:'Apple Chatswood Chase',R606:'Apple Miranda',R344:'Apple Castle Towers',R440:'Apple Penrith'};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let active=null,finished=null;
function until(fn,timeout=40000){return new Promise((resolve,reject)=>{
 const check=()=>{const value=fn();if(value){observer.disconnect();clearTimeout(timer);resolve(value)}};
 const observer=new MutationObserver(check);
 const timer=setTimeout(()=>{observer.disconnect();reject(Error('Apple 页面未返回库存，请打开采集标签页检查；本次无法确认'))},timeout);
 observer.observe(document.documentElement,{subtree:true,childList:true,attributes:true,characterData:true});check();
})}
function dialog(){return document.querySelector('[role="dialog"]')}
async function collect(task){
 if(active===task.id||finished===task.id)return;
 if(location.href.split('?')[0]!==task.variant.url)return;
 active=task.id;
 const postcode=task.postcode||'2000';
 let stage='等待库存查询按钮';
 try{
  const button=await until(()=>Array.from(document.querySelectorAll('button')).find(b=>/^Check availability/.test(b.textContent.trim())));
  button.click();stage='等待库存弹窗';await until(dialog);
  stage='填写邮编';
  const input=await until(()=>Array.from(dialog().querySelectorAll('input')).find(e=>e.type==='text'||e.getAttribute('aria-label')==='Postcode'));
  stage='提交邮编并等待门店结果';
  await new Promise((resolve,reject)=>{
   const id=task.id;
   const timer=setTimeout(()=>{document.removeEventListener('duo-postcode-response',receive);reject(Error('页面输入模块未响应，请确认扩展版本 1.1.0'))},10000);
   function receive(event){
    let response;try{response=JSON.parse(event.detail)}catch{return}
    if(response.id!==id)return;
    clearTimeout(timer);document.removeEventListener('duo-postcode-response',receive);
    if(response.error)reject(Error(response.error));else resolve();
   }
   document.addEventListener('duo-postcode-response',receive);
   document.dispatchEvent(new CustomEvent('duo-postcode-request',{detail:JSON.stringify({id,postcode})}));
  });
  await until(()=>new RegExp('near:\\s*'+postcode+'\\b').test(dialog()?.innerText||''));
  await until(()=>dialog()?.querySelector('[data-autom^="pickupStore_"]')||/nearest stores/.test(dialog()?.innerText||''));
  stage='展开门店列表';
  const expand=Array.from(dialog().querySelectorAll('button')).find(b=>/nearest stores/.test(b.textContent));
  if(expand&&expand.getAttribute('aria-expanded')!=='true')expand.click();
  await until(()=>dialog()?.querySelectorAll('[data-autom^="pickupStore_"]').length>=7);
  await sleep(1000);
  stage='校验配置和库存';
  const product=dialog().innerText.replace(/\s/g,'');
  if(!product.includes(((task.variant.model||'iPhone Duo')+' '+task.variant.capacity+' '+task.variant.colour).replace(/\s/g,'')))throw Error('配置校验失败');
  const rows=Array.from(dialog().querySelectorAll('[data-autom^="pickupStore_"]')).map(el=>{
   const option=el.querySelector('input');const message=el.querySelector('.form-selector-right-col')?.textContent.trim()||'';
   let status='unknown';if(/currently unavailable|unavailable for pickup/i.test(message))status='unavailable';
   else if(!option.disabled&&/available|pick.?up|today|tomorrow/i.test(message))status='available';
   return {store_id:option.value,store:stores[option.value],status,message,part:option.getAttribute('data-pl-partnumber')};
  }).filter(r=>r.store);
  if(rows.length!==7||rows.some(r=>r.status==='unknown'))throw Error('库存列表不完整或文案无法识别');
  const response=await chrome.runtime.sendMessage({type:'result',result:{id:task.id,postcode,stores:rows}});
  if(response?.error)throw Error(response.error);
  finished=task.id;
 }catch(e){try{await chrome.runtime.sendMessage({type:'result',result:{id:task.id,postcode,error:stage+'：'+e.message}})}catch{/* Extension may have been reloaded while this page was running. */}}
 finally{active=null}
}
chrome.runtime.onMessage.addListener((msg,sender,respond)=>{
 if(msg.type==='collect'){
  const accepted=location.href.split('?')[0]===msg.task.variant.url;
  respond({accepted});if(accepted)collect(msg.task);
 }
});
chrome.runtime.sendMessage({type:'ready'}).then(r=>{if(r?.task)collect(r.task)}).catch(()=>{});
