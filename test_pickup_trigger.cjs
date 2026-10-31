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

function openingFixture({opened=false,tradeSelected=false}={}){
 let clicks=0,tradeClicks=0,isOpen=opened;
 const root={querySelector:()=>({}),getClientRects:()=>[{}]};
 const button={click(){clicks++;isOpen=true}};
 const noTrade={click(){tradeClicks++;tradeSelected=true},disabled:false};
 const context=vm.createContext({document:{querySelector:s=>s==='[role="dialog"]'?(isOpen?root:null):s.includes('choose-noTradeIn')?noTrade:s.includes('tradeupinline')?(tradeSelected?{}:null):null},chrome:{runtime:{onMessage:{addListener(){}},sendMessage:()=>Promise.resolve({})}}});
 vm.runInContext(source,context);
 context.pickupTrigger=()=>tradeSelected?button:null;
 context.until=async fn=>{for(let i=0;i<3;i++){const value=fn();if(value)return value}throw Error('timeout')};
 return {open:()=>context.openPickup(),counts:()=>({clicks,tradeClicks}),context};
}
test('already open pickup dialog skips trigger and trade-in selection',async()=>{
 const f=openingFixture({opened:true});await f.open();assert.deepEqual(f.counts(),{clicks:0,tradeClicks:0});
});
test('missing trade-in selection is completed before looking for pickup',async()=>{
 const f=openingFixture();await f.open();assert.deepEqual(f.counts(),{clicks:1,tradeClicks:1});
});
test('existing trade-in choice is preserved',async()=>{
 const f=openingFixture({tradeSelected:true});await f.open();assert.deepEqual(f.counts(),{clicks:1,tradeClicks:0});
});
test('missing pickup entry reports no postcode submitted',async()=>{
 const f=openingFixture();f.context.pickupTrigger=()=>null;await assert.rejects(f.open(),/尚未提交邮编/);
});
