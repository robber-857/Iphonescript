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
