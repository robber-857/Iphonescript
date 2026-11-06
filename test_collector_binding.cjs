const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const url='https://www.apple.com/shop/buy-iphone/iphone-duo/7.6-inch-display-256gb-night-sky-unlocked';
function fixture(saved={},present=true,selectedUrl=url){
 const state={...saved},calls=[],listeners={};
 const event=name=>({addListener:fn=>listeners[name]=fn});
 const chrome={storage:{local:{get:async()=>({...state}),set:async v=>Object.assign(state,v),remove:async keys=>{for(const k of [].concat(keys))delete state[k]}}},
 action:{setBadgeText:async v=>calls.push(['badge',v.text]),setTitle:async()=>{},onClicked:event('click')},
 tabs:{get:async id=>{if(!present)throw Error('closed');return {id,url:selectedUrl,windowId:7}},update:async(id,v)=>calls.push(['update',id,v]),reload:async id=>calls.push(['reload',id]),sendMessage:async()=>({accepted:true}),onRemoved:event('removed')},
 windows:{update:async(id,v)=>calls.push(['focus',id,v])},alarms:{create(){},onAlarm:event('alarm')},runtime:{onInstalled:event('install'),onStartup:event('startup'),onMessage:event('message')}};
 const ctx=vm.createContext({chrome,console,setTimeout,fetch:async path=>{calls.push(['fetch',path]);return {ok:true,json:async()=>path.endsWith('/api/state')?{token:'test'}:{task:{id:'new',variant:{url}}}}}});
 vm.runInContext(fs.readFileSync('collector/background.js','utf8'),ctx);
 return {state,calls,listeners,poll:()=>vm.runInContext('poll()',ctx)};
}
test('unbound collector does not request a task or open a tab',async()=>{const f=fixture();await f.poll();assert.equal(f.calls.some(c=>c[0]==='fetch'),false)});
test('closed selected tab clears binding without creating a replacement',async()=>{const f=fixture({tabId:42,manualBinding:true},false);await f.poll();assert.equal(f.state.tabId,undefined);assert.equal(f.calls.some(c=>c[0]==='fetch'),false)});
test('bound tab is reused, refreshed and focused in its own window',async()=>{const f=fixture({tabId:42,manualBinding:true});await f.poll();assert.ok(f.calls.some(c=>c[0]==='reload'&&c[1]===42));assert.ok(f.calls.some(c=>c[0]==='focus'&&c[1]===7));assert.equal(f.state.tabId,42)});
test('upgrade discards old automatically created tab binding',async()=>{const f=fixture({tabId:42,task:{id:'old'}});await f.listeners.install();assert.equal(f.state.tabId,undefined)});
test('click outside supported product page does not bind or open anything',async()=>{const f=fixture();await f.listeners.click({id:99,url:'https://example.com'});assert.equal(f.state.tabId,undefined)});

for(const selectedUrl of [url.replace('/shop/','/us/shop/'),url.replace('www.','').replace('/shop/','/us/shop/').replace('-unlocked','-att')]){
 test('US alias page binds and remains selected: '+selectedUrl,async()=>{
  const f=fixture({},true,selectedUrl);
  await f.listeners.click({id:42,url:selectedUrl});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(f.state.tabId,42);assert.equal(f.state.manualBinding,true);
  assert.ok(f.calls.some(c=>c[0]==='badge'&&c[1]==='已选'));
  assert.ok(f.calls.some(c=>c[0]==='update'&&c[2].url===url));
 });
}
for(const unsupported of [url.replace('/shop/','/au/shop/'),url.replace('apple.com','apple.com.evil.test'),url.replace('/iphone-duo/','/iphone-unknown/'),url.slice(0,url.lastIndexOf('/')+1)]){
 test('reject unsupported binding: '+unsupported,async()=>{
  const f=fixture();await f.listeners.click({id:42,url:unsupported});assert.equal(f.state.tabId,undefined);
 });
}
