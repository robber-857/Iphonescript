const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync('collector/content.js','utf8');
const variant={model:'iPhone Duo',capacity:'256GB',colour:'Night Sky',url:'https://www.apple.com/shop/buy-iphone/iphone-duo/7.6-inch-display-256gb-night-sky-unlocked'};
function row(id='R250',message='Currently unavailableIn-Store Pickup',part='SKU-US',disabled=true){
 return {querySelectorAll:()=>[{textContent:'0.31 mi'}],querySelector:s=>s==='input'?{value:id,disabled,getAttribute:()=>part}:{textContent:s==='.form-selector-title'?'Fixture '+id:message}};
}
function fixture(){
 const f={rows:[row()],title:'iPhone Duo 256GB Night Sky',capacity:'256gb',colour:'nightsky',postcode:'10001',declared:1,pagePart:'SKU-US',deliveryPart:'SKU-US',url:variant.url,carrier:'UNLOCKED/US',pageCapacity:'256gb'};
 const list={querySelectorAll:()=>f.rows,querySelector:()=>({textContent:`Not available today at ${f.declared} nearest stores.`})};
 const main={querySelector:s=>({'.rf-productlocator-productinfo .typography-body-tight':{textContent:f.title},'.rf-productlocator-pickuploctionheader':{textContent:'Pick it up at an Apple Store near: '+f.postcode},'.rf-productlocator-pickupstoreslist':list,'input[name="delivery"]':{value:f.deliveryPart}}[s])};
 f.root={querySelector:s=>s==='.rf-productlocator-main'?main:s.includes('pl_dimensionCapacity')?(f.capacity?{value:f.capacity}:null):s.includes('pl_dimensionColor')?(f.colour?{value:f.colour}:null):null};
 const document={querySelector:s=>s==='[role="dialog"]'?f.root:s.includes('dimensionCapacity')?{value:f.pageCapacity}:s.includes('dimensionColor')?{value:'nightsky'}:s.includes('carrierModel')?{value:f.carrier}:null,querySelectorAll:()=>[{textContent:'Check availability iPhone Duo 256GB Night Sky',getAttribute:()=> 'productLocatorTriggerLink_'+f.pagePart}]};
 const context=vm.createContext({document,location:{get href(){return f.url}},chrome:{runtime:{onMessage:{addListener(){}},sendMessage:()=>Promise.resolve({})}},setTimeout,Date});
 vm.runInContext(source,context);
 f.read=()=>context.readInventory(f.root,variant,f.postcode);
 f.wait=timeout=>context.waitInventory(variant,f.postcode,timeout);
 return f;
}
test('only main product rows are parsed; recommendations cannot fill an empty list',()=>{
 const f=fixture();assert.equal(f.read()[0].status,'unavailable');f.rows=[];assert.throws(f.read,/没有可确认|尚未完整/);
});
test('available needs explicit wording and enabled current SKU',()=>{
 const f=fixture();f.rows=[row('R250','Available TomorrowIn-Store Pickup','SKU-US',false)];assert.equal(f.read()[0].status,'available');
 f.rows=[row('R250','In-Store Pickup','SKU-US',false)];assert.throws(f.read,/文案无法识别/);
 f.rows=[row('R250','Available Today','SKU-US',true)];assert.throws(f.read,/文案无法识别/);
});
test('main title, options, ZIP and SKU mismatches fail closed',()=>{
 const f=fixture();f.title='iPhone Duo 256GB Star White';assert.throws(f.read,/配置校验失败/);
 f.title='iPhone Duo 256GB Night Sky';f.capacity='512gb';assert.throws(f.read,/配置选项不匹配/);
 f.capacity='256gb';f.rows=[row('R250','Available Today','OTHER',false)];assert.throws(f.read,/商品编号不匹配/);
});
test('duplicate stores and incomplete declared store count are rejected',()=>{
 const f=fixture();f.rows.push(row());assert.throws(f.read,/重复门店/);f.rows=[row()];f.declared=12;assert.throws(f.read,/预期 12/);
});
test('US empty dialog title uses independent page identity and matching SKU',()=>{
 const f=fixture();f.title='';f.capacity=null;f.colour=null;assert.equal(f.read().length,1);
 f.pagePart='WRONG';assert.throws(f.read,/商品编号/);f.pagePart='SKU-US';f.carrier='ATT';assert.throws(f.read,/配置校验失败/);
 f.carrier='UNLOCKED/US';f.url='https://www.apple.com/au/shop/';assert.throws(f.read,/配置校验失败/);
 f.url=variant.url;f.pageCapacity='512gb';assert.throws(f.read,/配置校验失败/);
});
test('fallback never hides explicitly mismatched dialog selections',()=>{
 const f=fixture();f.title='';f.capacity='512gb';assert.throws(f.read,/配置选项不匹配/);
});
test('incomplete render retries until declared store count arrives',async()=>{
 const f=fixture();f.rows=[];setTimeout(()=>f.rows.push(row()),20);assert.equal((await f.wait(1000)).length,1);
});
test('retry timeout retains diagnostics',async()=>{
 const f=fixture();f.rows=[];await assert.rejects(f.wait(1),/尚未完整|没有可确认/);
});
test('leading-zero ZIP uses returned stores dynamically',()=>{
 const f=fixture();f.postcode='02108';f.rows=[row('R999')];assert.equal(f.read()[0].store_id,'R999');
});

test('distance parses miles and km without confusing addresses or unknown values',()=>{
 const ctx=vm.createContext({chrome:{runtime:{onMessage:{addListener(){}},sendMessage:()=>Promise.resolve({})}}});vm.runInContext(source,ctx);
 assert.equal(ctx.parseDistance('50 km'),50);assert.equal(ctx.parseDistance('0.31 mi'),0.31*1.609344);
 assert.ok(ctx.parseDistance('31.07 mi')>50);assert.ok(ctx.parseDistance('31.06 mi')<50);
 assert.equal(ctx.parseDistance('1,234.56 miles'),1234.56*1.609344);
 for(const value of ['Portland, OR','','unknown','-1 mi','97204'])assert.equal(ctx.parseDistance(value),null);
 assert.equal(fixture().read()[0].distance_km,0.31*1.609344);
});
