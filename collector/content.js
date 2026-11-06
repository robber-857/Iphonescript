const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let active=null,finished=null;
function until(fn,timeout=40000){return new Promise((resolve,reject)=>{
 const check=()=>{const value=fn();if(value){observer.disconnect();clearTimeout(timer);resolve(value)}};
 const observer=new MutationObserver(check);
 const timer=setTimeout(()=>{observer.disconnect();reject(Error('Apple 页面未返回库存，请打开采集标签页检查；本次无法确认'))},timeout);
 observer.observe(document.documentElement,{subtree:true,childList:true,attributes:true,characterData:true});check();
})}
function dialog(){return document.querySelector('[role="dialog"]')}
const compact=value=>String(value||'').replace(/\s/g,'').toLowerCase();
function parseDistance(text){
 const match=String(text||'').trim().match(/^([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*(mi|miles?|km|kilomet(?:er|re)s?)$/i);
 if(!match)return null;
 const value=Number(match[1].replace(/,/g,''));
 return value*(/^mi/i.test(match[2])?1.609344:1);
}
function pageProductPart(variant){
 if(location.href.split('?')[0]!==variant.url)return null;
 for(const [name,value] of [['dimensionCapacity',variant.capacity],['dimensionColor',variant.colour],['carrierModel','UNLOCKED/US']]){
  if(compact(document.querySelector('input[name="'+name+'"]:checked')?.value)!==compact(value))return null;
 }
 const expected=compact(variant.model+' '+variant.capacity+' '+variant.colour);
 const trigger=Array.from(document.querySelectorAll('[data-autom^="productLocatorTriggerLink_"]')).find(e=>compact(e.textContent).endsWith(expected));
 return trigger?.getAttribute('data-autom').slice('productLocatorTriggerLink_'.length)||null;
}
function readInventory(root,variant,postcode){
 const main=root?.querySelector('.rf-productlocator-main');
 if(!main)throw Error('未找到当前配置的主库存区域');
 const expected=(variant.model||'iPhone Duo')+' '+variant.capacity+' '+variant.colour;
 const title=main.querySelector('.rf-productlocator-productinfo .typography-body-tight')?.textContent;
 // Some US dialogs omit the title and checked dimension radios. In that
 // case require independent product-page URL, dimensions, carrier and SKU.
 const pagePart=!compact(title)?pageProductPart(variant):null;
 if(compact(title)!==compact(expected)&&!(!compact(title)&&pagePart))throw Error('配置校验失败：当前 '+(title||'标题未加载')+'；预期 '+expected);
 for(const [name,value] of [['pl_dimensionCapacity',variant.capacity],['pl_dimensionColor',variant.colour]]){
  const selected=root.querySelector('input[name="'+name+'"]:checked');
  if(selected?compact(selected.value)!==compact(value):!pagePart)throw Error('配置选项不匹配：'+name+'='+ (selected?.value||'未选中'));
 }
 const heading=main.querySelector('.rf-productlocator-pickuploctionheader')?.textContent||'';
 if(!new RegExp('near:\\s*'+postcode+'\\b').test(heading))throw Error('当前配置邮编未确认：'+postcode);
 const list=main.querySelector('.rf-productlocator-pickupstoreslist');
 if(!list)throw Error('当前配置门店列表尚未加载');
 const expectedPart=main.querySelector('input[name="delivery"]')?.value;
 if(!expectedPart||(pagePart&&pagePart!==expectedPart))throw Error('主库存商品编号与当前商品页不匹配');
 const rows=[],issues=[],seen=new Set(),parts=new Set();
 for(const el of list.querySelectorAll('[data-autom^="pickupStore_"]')){
  const option=el.querySelector('input');
  if(!option){issues.push('门店行缺少选项');continue}
  if(!/^R[0-9]+$/.test(option.value)){issues.push('门店编号无效');continue}
  const store=(el.querySelector('.form-selector-title')?.textContent||'').replace(/\s+/g,' ').trim();
  if(!store){issues.push('门店名称尚未加载');continue}
  if(seen.has(option.value)){issues.push('重复门店：'+store);continue}
  seen.add(option.value);
  const part=option.getAttribute('data-pl-partnumber');
  if(!part||(expectedPart&&part!==expectedPart))issues.push(store+' 商品编号不匹配');
  if(part)parts.add(part);
  const message=(el.querySelector('.form-selector-right-col')?.textContent||'').replace(/\s+/g,' ').trim();
  let status='unknown';
  if(/currently unavailable|unavailable for pickup|not available(?: today)?/i.test(message))status='unavailable';
  else if(!option.disabled&&/^available\b/i.test(message))status='available';
  if(status==='unknown')issues.push(store+' 文案无法识别：'+(message.slice(0,90)||'空白')+(option.disabled?'（选项禁用）':''));
  const distanceLabel=Array.from(el.querySelectorAll('.form-selector-left-col .form-label-small')).map(e=>e.textContent.trim()).find(text=>parseDistance(text)!==null)||'';
  if(parseDistance(distanceLabel)===null)issues.push(store+' 距离未确认，无法判断是否在 50 km 内');
  rows.push({store_id:option.value,store,status,message,part,distance_km:parseDistance(distanceLabel),distance_label:distanceLabel});
 }
 const declared=list.querySelector('button')?.textContent.match(/at\s+(\d+)\s+nearest stores/i);
 if(declared&&rows.length!==Number(declared[1]))issues.unshift('门店列表尚未完整加载：预期 '+declared[1]+'，当前 '+rows.length);
 if(!rows.length)issues.unshift('当前邮编没有可确认的门店数据');
 if(parts.size>1)issues.unshift('当前列表混入多个商品编号');
 if(issues.length)throw Error(issues.join('；').slice(0,460));
 return rows;
}
async function waitInventory(variant,postcode,timeout=15000){
 const deadline=Date.now()+timeout;
 let detail='库存尚未加载';
 do{
  try{return readInventory(dialog(),variant,postcode)}catch(e){detail=e.message}
  await sleep(250);
 }while(Date.now()<deadline);
 throw Error(detail);
}
function pickupTrigger(){
 const candidates=document.querySelectorAll('[data-autom^="productLocatorTriggerLink_"], [data-autom="pickUpDetails"] .rf-pickup-quote-overlay-trigger, button');
 return Array.from(candidates).find(el=>
  !el.disabled&&el.getAttribute('aria-disabled')!=='true'&&el.getClientRects().length&&
  (el.matches('[data-autom^="productLocatorTriggerLink_"], [data-autom="pickUpDetails"] .rf-pickup-quote-overlay-trigger')||/^Check availability/i.test(el.textContent.trim())));
}
function pickupDialog(){
 const root=dialog();
 return root?.querySelector('input[data-autom="zipCode"]')&&root.getClientRects().length?root:null;
}
async function openPickup(){
 const attempted=new Set();
 try{
  const entry=await until(()=>{
   const opened=pickupDialog();
   if(opened)return {opened};
   // US pickup is gated on payment and carrier. Always query the same
   // full-price / connect-later configuration across the entire round.
   for(const [name,value] of [['tradeupinline','noTradeIn'],['purchase_option_group','fullprice'],['carrierModel','UNLOCKED/US']]){
    const option=document.querySelector('input[name="'+name+'"][value="'+value+'"]');
    const selected=document.querySelector('input[name="'+name+'"]:checked');
    if(option&&selected?.value!==value){
     if(!option.disabled&&!attempted.has(name)){attempted.add(name);option.scrollIntoView?.({block:'center'});option.click()}
     return null;
    }
   }
   const button=pickupTrigger();
   if(button)return {button};
   return null;
  });
  if(entry.button)entry.button.click();
  await until(pickupDialog);
 }catch{
  throw Error('美国站自提入口未出现；尚未提交 ZIP，无法确认库存。请检查 Buy / Connect to any carrier later 选项，或页面是否遇到访问限制（如 HTTP 541）');
 }
}
async function collect(task){
 if(active===task.id||finished===task.id)return;
 if(location.href.split('?')[0]!==task.variant.url)return;
 active=task.id;
 const postcode=task.postcode||'10001';
 let stage='等待库存查询按钮';
 try{
  await openPickup();
  stage='填写邮编';
  await until(()=>dialog()?.querySelector('input[data-autom="zipCode"]'));
  stage='提交邮编并等待门店结果';
  await new Promise((resolve,reject)=>{
   const id=task.id;
   const timer=setTimeout(()=>{document.removeEventListener('duo-postcode-response',receive);reject(Error('页面输入模块未响应，请重新加载美国版扩展并刷新商品页'))},10000);
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
  await until(()=>dialog()?.querySelector('.rf-productlocator-main .rf-productlocator-pickupstoreslist'));
  stage='展开门店列表';
  const expand=Array.from(dialog().querySelectorAll('.rf-productlocator-main .rf-productlocator-pickupstoreslist button')).find(b=>/nearest stores/.test(b.textContent));
  if(expand&&expand.getAttribute('aria-expanded')!=='true')expand.click();
  stage='校验配置和库存';
  const rows=await waitInventory(task.variant,postcode);
  const response=await chrome.runtime.sendMessage({type:'result',result:{id:task.id,postcode,scope_version:3,stores:rows}});
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

