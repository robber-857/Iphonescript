const $=id=>document.getElementById(id);
let state,dirty=false,phoneDirty=false,renderedModel=null;
const stamp=t=>t?new Date(t*1000).toLocaleTimeString('zh-CN',{timeZone:'Australia/Sydney',hour12:false}):'尚未检查';
function toast(msg){$('toast').textContent=msg;$('toast').hidden=false;setTimeout(()=>$('toast').hidden=true,4500)}
function element(tag,text,cls){const e=document.createElement(tag);e.textContent=text;if(cls)e.className=cls;return e}
function render(){
 if(!state)return;
 const postcode=state.postcode||'2000';
 const city=postcode==='2000'?'悉尼':postcode==='3000'?'墨尔本':'邮编 '+postcode+' 附近';
 const count=Object.keys(state.stores).length;
 $('location-title').textContent=city+'门店库存';
 document.title='Duo / '+city+'库存监测';
 $('store-scope').textContent=count?'范围：'+Object.values(state.stores).join(' / '):'等待 Apple 返回 '+postcode+' 附近门店';
 $('model-summary').textContent=state.model==='pro-test'?'iPhone 18 Pro · 256GB Black · 真实库存测试（不自动拨号）':'iPhone Duo · 全部颜色和容量 · '+(count?count+' 家门店':'等待门店数据');
 if(renderedModel!==state.model){
  $('colour').replaceChildren(new Option('全部颜色',''),...Array.from(new Set(state.variants.map(v=>v.colour))).map(v=>new Option(v,v)));
  $('capacity').value='';renderedModel=state.model;
 }
 const phone=state.phone||{};
 $('phone-status').textContent=(phone.configured?'已配置 '+phone.destination:'尚未配置')+' · '+(phone.last||'尚未拨号');
 if(!phoneDirty)$('phone-enabled').checked=!!phone.enabled;
 $('phone-test').disabled=!phone.configured;
 $('location').textContent=(postcode==='2000'?'SYDNEY':postcode==='3000'?'MELBOURNE':'POSTCODE')+' · '+postcode;
 const connected=state.collector_seen&&state.server_time-state.collector_seen<130;
 $('status').textContent=!connected?'等待浏览器采集器连接':state.cookie_cleanup?'等待清理 Apple Cookie':state.running?'正在检查':state.enabled?'监测已开启':'监测已暂停';
 $('dot').className='dot'+(connected&&state.enabled?' on':'');
 $('progress').textContent=connected?(state.current||''):'请加载扩展，并在手动打开的 Apple 商品页点击扩展图标指定采集页';
 $('toggle').textContent=state.enabled?'暂停监测':'开始监测';
 $('check').disabled=state.running;
 $('next').textContent=state.next_check?'下次检查 '+stamp(state.next_check):state.running?'按配置依次检查，请稍候':'等待开始';
 const variants=state.variants.filter(v=>(!$('colour').value||v.colour===$('colour').value)&&(!$('capacity').value||v.capacity===$('capacity').value));
 const head=$('head');head.replaceChildren(element('th','门店 / 配置'));
 for(const v of variants){const th=element('th',v.capacity);th.append(element('small',v.colour));head.append(th)}
 const body=$('rows');body.replaceChildren();let available=0,unknown=0;
 const freshness=state.interval+600;
 function cellData(v,sid){const r=state.results[v.id];const row=r?.stores.find(s=>s.store_id===sid);const stale=!r?.checked||state.server_time-r.checked>freshness;return {r,row,status:r?.error||stale?'unknown':row?.status||'unknown'}}
 for(const [sid,name] of Object.entries(state.stores)){
  const cells=variants.map(v=>({v,...cellData(v,sid)}));
  available+=cells.filter(c=>c.status==='available').length;unknown+=cells.filter(c=>c.status==='unknown').length;
  if($('only').checked&&!cells.some(c=>c.status==='available'))continue;
  const tr=element('tr','');tr.append(element('td',name.replace('Apple ','')));
  for(const {v,r,row,status} of cells){const td=element('td','');const a=element('a',status==='available'?'● 可自提':status==='unavailable'?'暂无库存':'待确认','cell '+status);a.href=v.url;a.target='_blank';a.rel='noopener';a.title=(r?.error?'本次查询失败：'+r.error+'\n':'')+'上次成功：'+stamp(r?.checked)+'\n'+(row?.message||'尚无有效数据')+'\n点击打开 Apple 官网';td.append(a);tr.append(td)}
  body.append(tr);
 }
 if(!body.children.length){const td=element('td',count?'当前筛选下没有已确认有货的门店':'等待首次采集 '+postcode+' 附近门店；请确认扩展已更新至 1.3.3');td.colSpan=variants.length+1;const tr=element('tr','');tr.append(td);body.append(tr)}
 $('summary').textContent=`${available} 个有货组合 · ${unknown} 个待确认`;
 if(!dirty){$('model').value=state.model||'duo';$('postcode').value=state.postcode||'2000';$('interval').value=state.interval;$('notifications').checked=state.notifications;$('clear-cookies').checked=!!state.clear_apple_cookies}
 $('events').replaceChildren();$('count').textContent=state.events.length?`/ ${state.events.length}`:'';
 for(const ev of state.events.slice(0,30)){const e=element('div','','event '+ev.kind);e.append(element('time',stamp(ev.time)),element('span',ev.message));$('events').append(e)}
 if(!state.events.length)$('events').append(element('p','开始监测后，这里将记录有货提醒和查询异常。','muted'));
}
async function refresh(){try{const r=await fetch('/api/state');if(!r.ok)throw Error();state=await r.json();render()}catch{$('status').textContent='后台连接已断开';$('dot').className='dot error';$('progress').textContent='请重新运行启动文件';$('next').textContent='当前表格为旧结果';$('rows').replaceChildren();$('summary').textContent='无法确认当前库存'}}
async function action(path,body={}){try{const r=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-Duo-Token':state?.token||''},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(data.error);await refresh();return true}catch(e){toast(e.message);return false}}
$('toggle').onclick=()=>action(state?.enabled?'pause':'start');$('check').onclick=()=>action('check');
$('test').onclick=()=>action('test-notification');
$('save').onclick=async()=>{if(!/^[0-9]{4}$/.test($('postcode').value.trim())){toast('请输入四位澳洲邮编，例如 2000');$('postcode').focus();return}if(await action('settings',{model:$('model').value,postcode:$('postcode').value.trim(),interval:Number($('interval').value),notifications:$('notifications').checked,clear_apple_cookies:$('clear-cookies').checked})){dirty=false;render();toast('设置已保存')}};
for(const id of ['colour','capacity','only'])$(id).onchange=render;
for(const id of ['interval','notifications','postcode','model','clear-cookies'])$(id).oninput=()=>dirty=true;
for(const id of ['phone-enabled','phone-sid','phone-token','phone-from','phone-to'])$(id).oninput=()=>phoneDirty=true;
$('phone-save').onclick=async()=>{
 if(await action('phone/settings',{enabled:$('phone-enabled').checked,sid:$('phone-sid').value,token:$('phone-token').value,from:$('phone-from').value,to:$('phone-to').value})){
  for(const id of ['phone-sid','phone-token','phone-from','phone-to'])$(id).value='';
  phoneDirty=false;render();toast('电话设置已保存');
 }
};
$('phone-test').onclick=async()=>{
 if(!confirm('将拨打已保存的接听号码 '+(state.phone.destination||'')+'，可能产生 Twilio 费用。继续？'))return;
 if(await action('phone/test',{confirm:true}))toast('测试拨号请求已启动，请查看电话状态');
};
refresh();setInterval(refresh,3000);
