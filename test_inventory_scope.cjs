const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync('collector/content.js','utf8');
const ids=['R238','R523','R254','R253','R606','R344','R440'];
const variant={model:'iPhone Duo',capacity:'1TB',colour:'Star White'};
function row(id,message='Currently unavailableIn-Store Pickup',part='WHITE',disabled=true){
 const option={value:id,disabled,getAttribute:()=>part};
 return {querySelector:s=>s==='input'?option:{textContent:message}};
}
function fixture(){
 const f={rows:ids.map(id=>row(id)),recommendations:[row('R238','Available TodayIn-Store Pickup','BLUE',false)],title:'iPhone\u00a0Duo 1TB Star White',capacity:'1tb',colour:'starwhite',postcode:'2000'};
 const list={querySelectorAll:()=>f.rows};
 const main={querySelector:s=>({'.rf-productlocator-productinfo .typography-body-tight':{textContent:f.title},'.rf-productlocator-pickuploctionheader':{textContent:'Pick it up at an Apple Store near: '+f.postcode},'.rf-productlocator-pickupstoreslist':list,'input[name="delivery"]':{value:'WHITE'}}[s])};
 f.root={querySelector:s=>s==='.rf-productlocator-main'?main:s.includes('pl_dimensionCapacity')?{value:f.capacity}:s.includes('pl_dimensionColor')?{value:f.colour}:null,querySelectorAll:()=>[...f.rows,...f.recommendations]};
 const context=vm.createContext({document:{querySelector:()=>f.root},chrome:{runtime:{onMessage:{addListener(){}},sendMessage:()=>Promise.resolve({})}},setTimeout,Date});
 vm.runInContext(source,context);
 f.read=(postcode='2000')=>context.readInventory(f.root,variant,postcode);
 f.wait=timeout=>context.waitInventory(variant,'2000',timeout);
 return f;
}
test('white unavailable + blue available recommendations yields only seven white unavailable stores',()=>{
 const f=fixture();f.rows.push(row('R385'),row('R483'));
 const rows=f.read();assert.equal(rows.length,7);assert.ok(rows.every(r=>r.status==='unavailable'&&r.part==='WHITE'));
});
test('current configuration available store is preserved',()=>{
 const f=fixture();f.rows[0]=row('R238','Available TomorrowIn-Store Pickup','WHITE',false);assert.equal(f.read()[0].status,'available');
});
test('recommendation cannot fill a missing current-model store',()=>{
 const f=fixture();f.rows.shift();assert.throws(f.read,/缺少门店：Apple Sydney/);
});
test('duplicate store is rejected with its name',()=>{
 const f=fixture();f.rows.push(row('R238'));assert.throws(f.read,/重复门店：Apple Sydney/);
});
test('matching recommendation title cannot mask wrong main title or selection',()=>{
 const f=fixture();f.title='iPhone Duo 1TB Night Sky';assert.throws(f.read,/配置校验失败/);
 f.title='iPhone Duo 1TB Star White';f.capacity='512gb';assert.throws(f.read,/配置选项不匹配/);
});
test('foreign SKU inside main list is rejected',()=>{
 const f=fixture();f.rows[0]=row('R238','Available Today','BLUE',false);assert.throws(f.read,/多个商品编号/);
});
test('generic Pickup and unknown wording do not mean available; error contains store and text',()=>{
 const f=fixture();f.rows[0]=row('R238','In-Store Pickup','WHITE',false);assert.throws(f.read,/Apple Sydney 文案无法识别：In-Store Pickup/);
});
test('wrong postcode is rejected',()=>{const f=fixture();f.postcode='2150';assert.throws(f.read,/邮编未确认/)});
test('incomplete render is retried until all stores arrive',async()=>{
 const f=fixture();f.rows.shift();setTimeout(()=>f.rows.unshift(row('R238')),20);assert.equal((await f.wait(1000)).length,7);
});
test('retry timeout retains specific diagnostics',async()=>{
 const f=fixture();f.rows.shift();await assert.rejects(f.wait(1),/缺少门店：Apple Sydney/);
});

test('Melbourne uses returned current-product stores instead of Sydney allowlist',()=>{
 const f=fixture();f.postcode='3000';f.rows=[row('R999')];
 const rows=f.read('3000');assert.equal(rows.length,1);assert.equal(rows[0].store_id,'R999');
 f.rows=[];assert.throws(()=>f.read('3000'),/没有可确认的门店/);
});
