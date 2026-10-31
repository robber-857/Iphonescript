function compileFilter(input, mode = 'subject_phrase') {
  let value = input.trim();
  if (!value) throw new Error('请输入搜索关键词。');
  if (mode === 'advanced') return value;
  if (!['subject_phrase', 'all_phrase', 'sender'].includes(mode)) throw new Error('无效的匹配模式。');
  if (value.startsWith('"') && value.endsWith('"')) value = value.slice(1, -1).trim();
  if (!value || /["\\\r\n]/.test(value)) throw new Error('完整短语中不能包含双引号、反斜杠或换行；复杂条件请使用高级搜索。');
  if (mode === 'sender' || (mode === 'subject_phrase' && /^[^\s<>:@]+@[^\s<>:@]+\.[^\s<>:@]+$/.test(value))) return 'from:"' + value + '"';
  return (mode === 'subject_phrase' ? 'subject:' : '') + '"' + value + '"';
}
if (typeof module !== 'undefined') module.exports = {compileFilter};
if (typeof document !== 'undefined') {
const $ = id => document.getElementById(id);
let restoredSearch = false;
let state = {rows: []}, token = '', page = 1, filter = 'all', pending = false, lastRows = '', localError = '';
let accounts = [], rememberedConnection = '';
try {accounts = JSON.parse(localStorage.getItem('cardbox-accounts') || '[]').filter(x=>typeof x==='string'&&x.includes('@'));} catch {}
const manager=document.createElement('div');manager.className='account-manager';
const accountLabel=document.createElement('label');accountLabel.htmlFor='saved-accounts';accountLabel.textContent='邮箱列表';
const selector=document.createElement('select');selector.id='saved-accounts';selector.setAttribute('aria-label','选择已保存邮箱');
const remove=document.createElement('button');remove.type='button';remove.textContent='移除此地址';remove.className='quiet';
const add=document.createElement('button');add.type='button';add.textContent='保存下方填写的邮箱';add.className='quiet';
manager.append(accountLabel,selector,add,remove);$('connect-form').before(manager);
function renderAccounts(){selector.replaceChildren();const blank=document.createElement('option');blank.value='';blank.textContent='＋ 添加另一个邮箱';selector.append(blank);accounts.forEach(email=>{const o=document.createElement('option');o.value=email;o.textContent=email;selector.append(o);});selector.value=accounts.includes($('account').value)?$('account').value:'';remove.disabled=!selector.value;}
function saveAccounts(){try{localStorage.setItem('cardbox-accounts',JSON.stringify(accounts));}catch{}renderAccounts();}
selector.onchange=()=>{$('account').value=selector.value;remove.disabled=!selector.value;if(!selector.value)$('account').focus();};
remove.onclick=()=>{accounts=accounts.filter(x=>x!==selector.value);saveAccounts();};
add.onclick=()=>{const email=$('account').value.trim();if(!email||!$('account').reportValidity())return;if(!accounts.includes(email))accounts.push(email);saveAccounts();};
renderAccounts();
function notice(message) { $('notice').textContent = message; $('notice').hidden = !message; }
async function request(path, body = {}) {
  const response = await fetch('/api/' + path, {method:'POST',headers:{'Content-Type':'application/json','X-Token':token},body:JSON.stringify(body)});
  if (!response.ok) {const data = await response.json(); throw new Error(data.error || '请求失败，请刷新页面重试。');}
  return response;
}
async function action(path, body) {
  pending = true; localError = ''; render();
  try { await request(path, body); await refresh(); }
  catch (error) { localError = error.message; }
  finally { pending = false; render(); }
}
function cell(row, text, tag = 'td') {const el=document.createElement(tag);el.textContent=text;row.append(el);return el;}
function renderTable() {
  let rows = state.rows.filter(r => filter === 'all' || (filter === 'pin' ? !!r.pin : !r.pin));
  const size = Number($('page-size').value), pages = Math.max(1, Math.ceil(rows.length / size));
  page = Math.min(page, pages);
  const start = (page - 1) * size;
  $('rows').replaceChildren();
  rows.slice(start, start+size).forEach((r,i)=>{
    const tr = document.createElement('tr');
    cell(tr,start+i+1);
    const pinCell = cell(tr,'');cell(pinCell,r.pin ? ($('show-pins').checked ? r.pin : '•••• •••• '+r.pin.slice(-4)) : '—','code');
    const mail = cell(tr,r.subject || '邮件读取失败');cell(mail,r.sender || r.error || '', 'small');
    const date = new Date(r.date);cell(tr,r.date && !isNaN(date) ? date.toLocaleString('zh-CN') : '—');
    const status=cell(tr,'');const badge=cell(status,r.status,'span');badge.className='status'+(r.pin?'':' review');
    if(r.error) badge.title=r.error;
    const operation=cell(tr,'');
    if(r.pin){const copy=cell(operation,'复制','button');copy.type='button';copy.setAttribute('aria-label','复制第 '+(start+i+1)+' 条 PIN');copy.onclick=async()=>{try{await navigator.clipboard.writeText(r.pin);copy.textContent='已复制';setTimeout(()=>copy.textContent='复制',1600);}catch{localError='无法访问剪贴板，请显示完整 PIN 后手动复制。';notice(localError);}};}
    $('rows').append(tr);
  });
  $('empty').hidden=rows.length>0;
  $('empty').querySelector('h3').textContent=state.rows.length?'此分类暂无结果':state.searched?'尚无提取结果':'等待提取邮件';
  $('empty').querySelector('p').textContent=state.searched?(state.total?'点击“提取下一批”开始处理。':'没有匹配邮件，请调整 Filter 后重新搜索。'):'连接 Gmail，输入 Filter，然后提取第一批邮件。';
  $('range').textContent=rows.length?`${start+1}–${Math.min(start+size,rows.length)} / 共 ${rows.length} 条`:'共 0 条结果';
  $('page-label').textContent=`${page} / ${pages}`;$('prev').disabled=page<=1;$('next').disabled=page>=pages;
}
function render() {
  const busy=state.busy||pending, connected=state.connected;
  $('connection-status').textContent=connected?'已连接 · '+state.account:'尚未连接 Gmail';
  $('connect-form').hidden=false;$('disconnect').hidden=!connected;
  $('connect').textContent=connected?'用 Google 切换邮箱':'使用 Google 登录';
  selector.disabled=!!busy;
  $('oauth-config-status').textContent=state.oauth_configured?'已配置，可使用 Google 登录。':'尚未配置：请完成以下一次性设置。';
  $('oauth-file').disabled=!!busy;
  if(!state.oauth_configured)$('oauth-setup').open=true;
  if(connected&&rememberedConnection!==state.account){rememberedConnection=state.account;if(!accounts.includes(state.account)){accounts.push(state.account);saveAccounts();}}
  if(!connected)rememberedConnection='';
  for(const id of ['connect','disconnect','query','match-mode','batch-size']) $(id).disabled=!!busy;
  $('connect').disabled=busy||!state.oauth_configured;
  $('search').disabled=busy||!connected;
  $('search').textContent=busy?'处理中…':'搜索邮件 →';
  let effectiveQuery = '';
  try {effectiveQuery = compileFilter($('query').value, $('match-mode').value);} catch {}
  $('query-preview').textContent = effectiveQuery ? '将搜索：' + effectiveQuery : '输入完整短语或发件邮箱地址。';
  $('active-query').textContent = state.searched ? '当前结果对应：' + state.query : '';
  const changed=state.searched && effectiveQuery!==state.query;
  $('batch').disabled=busy||!connected||!state.searched||state.cursor>=state.total||changed;
  $('retry').hidden=!state.rows.some(r=>r.status==='读取失败');$('retry').disabled=busy||!connected||changed;
  $('export').disabled=!state.rows.length||(busy&&!state.paused);
  $('pause').hidden=!state.batch_running;
  $('pause').disabled=pending||(state.pause_requested&&!state.paused);
  $('pause').textContent=state.paused?'继续提取':state.pause_requested?'正在暂停…':'暂停';
  $('total').textContent=state.searched?state.total:'—';
  $('processed').textContent=state.searched?state.cursor:new Set(state.rows.map(r=>r.uid)).size;
  $('pins').textContent=state.rows.filter(r=>r.pin).length;
  $('review').textContent=state.rows.filter(r=>!r.pin).length;
  $('row-count').textContent=state.rows.length;
  $('source').textContent=state.source||'每个 PIN 一行，保留来源邮件供核对。';
  $('batch-info').textContent=state.paused?`已暂停 · 本批 ${state.progress} / ${state.batch_total} 封，结果已保留`:state.pause_requested?'正在暂停，等待当前邮件读取完成…':busy?'正在处理，请稍候…':changed?'Filter 已修改，请重新搜索':state.searched?`已处理 ${state.cursor} / ${state.total} 封${state.cursor===state.total?' · 本轮处理完成':''}`:'先连接邮箱并搜索';
  $('progress').hidden=!state.busy||!state.batch_total;$('progress').max=state.batch_total||1;$('progress').value=state.progress||0;
  notice(localError||state.error||'');
  const rowKey=JSON.stringify([state.rows,state.searched,state.total]);
  if(lastRows!==rowKey){lastRows=rowKey;renderTable();}
}
async function refresh(){const res=await fetch('/api/state');if(!res.ok)throw new Error('后台连接失败');state=await res.json();token=state.token;if(!restoredSearch){restoredSearch=true;if(state.searched&&state.query){$('match-mode').value=/[:"{}()]/.test(state.query)?'advanced':'subject_phrase';$('query').value=state.query;}}render();}
$('connect-form').onsubmit=async e=>{e.preventDefault();pending=true;localError='';render();try{const response=await request('oauth/start',{account:$('account').value});const data=await response.json();window.location.assign(data.url);}catch(error){localError=error.message;pending=false;render();}};
$('oauth-file').onchange=async()=>{const file=$('oauth-file').files[0];if(!file)return;try{if(file.size>16000)throw Error('客户端 JSON 文件过大。');const config=JSON.parse(await file.text());await action('oauth/config',{config});if(state.oauth_configured)$('oauth-setup').open=false;}catch(error){localError=error.message;notice(localError);}finally{$('oauth-file').value='';}};
$('disconnect').onclick=()=>action('disconnect');
$('search-form').onsubmit=e=>{e.preventDefault();try{const query=compileFilter($('query').value,$('match-mode').value);page=1;action('search',{query});}catch(error){localError=error.message;notice(localError);}};
$('match-mode').onchange=()=>{localError='';$('query').placeholder=$('match-mode').value==='advanced'?'例如 from:someone@gmail.com subject:"Gift Card"':$('match-mode').value==='sender'?'例如 sender@example.com':'例如 Chen sent you 或 sender@example.com';render();};
$('query').oninput=render;
$('batch').onclick=()=>action('batch',{count:Number($('batch-size').value)});
$('pause').onclick=()=>action(state.paused?'resume':'pause');
$('retry').onclick=()=>action('retry',{count:100});
$('export').onclick=async()=>{try{const response=await request('export');const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download='gift-card-pins.xlsx';a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);}catch(e){localError=e.message;notice(localError);}};
$('prev').onclick=()=>{page--;renderTable();};$('next').onclick=()=>{page++;renderTable();};
$('page-size').onchange=()=>{page=1;renderTable();};$('show-pins').onchange=renderTable;
document.querySelectorAll('[data-filter]').forEach(button=>button.onclick=()=>{filter=button.dataset.filter;page=1;document.querySelectorAll('[data-filter]').forEach(b=>b.classList.toggle('selected',b===button));renderTable();});
async function poll(){try{await refresh();}catch{notice('本地后台未连接，请启动 start.cmd 后刷新页面。');}setTimeout(poll,1500);}
renderTable();poll();

}
