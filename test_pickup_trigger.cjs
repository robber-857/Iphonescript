const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const source=fs.readFileSync('collector/content.js','utf8');
function find(candidates){
 const context=vm.createContext({document:{querySelectorAll:()=>candidates},chrome:{runtime:{onMessage:{addListener(){}},sendMessage:()=>Promise.resolve({})}}});
 vm.runInContext(source,context);
 return vm.runInContext('pickupTrigger()',context);
}
function element(text,trigger=false,visible=true,disabled=false){
 return {textContent:text,disabled,matches:()=>trigger,getAttribute:()=>null,getClientRects:()=>visible?[{}]:[]};
}
test('store-name pickup trigger opens even without Check availability text',()=>{
 const store=element('Apple Sydney',true);assert.equal(find([store]),store);
});
test('legacy availability button remains supported',()=>{
 const button=element('Check availability');assert.equal(find([button]),button);
});
test('hidden, disabled and ordinary retail links are not selected',()=>{
 assert.equal(find([element('Apple Sydney'),element('Apple Sydney',true,false),element('Check availability',false,true,true)]),undefined);
});

function openingFixture({opened=false,selected={}}={}){
 const values={...selected},clicks=[],options={tradeupinline:'noTradeIn',purchase_option_group:'fullprice',carrierModel:'UNLOCKED/US'};
 let isOpen=opened;
 const root={querySelector:()=>({}),getClientRects:()=>[{}]};
 const button={click(){clicks.push('pickup');isOpen=true}};
 const document={querySelector(s){
  if(s==='[role="dialog"]')return isOpen?root:null;
  const name=Object.keys(options).find(n=>s.includes('name="'+n+'"'));
  if(!name)return null;
  if(s.endsWith(':checked'))return values[name]?{value:values[name]}:null;
  return {disabled:false,click(){clicks.push(name);values[name]=options[name]}};
 }};
 const context=vm.createContext({document,chrome:{runtime:{onMessage:{addListener(){}},sendMessage:()=>Promise.resolve({})}}});
 vm.runInContext(source,context);context.pickupTrigger=()=>button;
 context.until=async fn=>{for(let i=0;i<6;i++){const v=fn();if(v)return v}throw Error('timeout')};
 return {open:()=>context.openPickup(),clicks,context};
}
test('already open dialog needs no setup clicks',async()=>{const f=openingFixture({opened:true});await f.open();assert.deepEqual(f.clicks,[])});
test('US setup completes trade, full-price and connect-later before pickup',async()=>{
 const f=openingFixture();await f.open();assert.deepEqual(f.clicks,['tradeupinline','purchase_option_group','carrierModel','pickup']);
});
test('existing correct choices are reused',async()=>{
 const f=openingFixture({selected:{tradeupinline:'noTradeIn',purchase_option_group:'fullprice',carrierModel:'UNLOCKED/US'}});await f.open();assert.deepEqual(f.clicks,['pickup']);
});
test('other carrier and finance do not leak into unlocked inventory',async()=>{
 const f=openingFixture({selected:{tradeupinline:'noTradeIn',purchase_option_group:'finance',carrierModel:'ATT'}});await f.open();assert.deepEqual(f.clicks,['purchase_option_group','carrierModel','pickup']);
});
test('missing pickup reports no ZIP submitted',async()=>{
 const f=openingFixture();f.context.pickupTrigger=()=>null;await assert.rejects(f.open(),/尚未提交 ZIP/);
});
