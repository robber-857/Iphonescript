const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync('collector/background.js','utf8');
function setup(leftover=false){
 const removed=[],queries=[];let count=0;const event={addListener(){}};
 const cookies={getAllCookieStores:async()=>[{id:'other',tabIds:[9]},{id:'selected',tabIds:[42]}],getAll:async q=>{queries.push(q);return count++===0?[{domain:'.apple.com',path:'/',name:'session',storeId:'selected'},{domain:'.example.com',path:'/',name:'keep'},{domain:'www.apple.com',path:'/au',name:'partition',partitionKey:{topLevelSite:'https://apple.com'}}]:leftover?[{name:'remaining'}]:[]},remove:async q=>removed.push(q)};
 const chrome={cookies,runtime:{onInstalled:event,onStartup:event,onMessage:event},alarms:{onAlarm:event},action:{onClicked:event},tabs:{onRemoved:event}};
 const ctx=vm.createContext({chrome,console});vm.runInContext(source,ctx);
 return {removed,queries,run:()=>vm.runInContext('clearAppleCookies(42)',ctx)};
}
test('only Apple cookies in selected tab store are removed, partition key retained',async()=>{const f=setup();await f.run();assert.equal(f.removed.length,2);assert.ok(f.removed.every(c=>c.storeId==='selected'&&c.url.includes('apple.com')));assert.equal(f.removed[1].partitionKey.topLevelSite,'https://apple.com');assert.ok(f.queries.every(q=>q.domain==='apple.com'&&q.storeId==='selected'))});
test('remaining cookies report failure rather than claiming success',async()=>{await assert.rejects(setup(true).run())});
