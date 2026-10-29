const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const source=fs.readFileSync('collector/page-input.js','utf8');
function fixture(reset=false){
 let submitted=0,accepted='',tracked='';const listeners=new Map(),responses=[];
 class Input {
  get value(){return accepted}
  set value(v){accepted=v}
  focus(){}
  select(){}
  dispatchEvent(e){if(e.type==='input'&&accepted!==tracked)tracked=accepted;if(reset)accepted=''}
  closest(){return {requestSubmit(){assert.equal(tracked,'2150');submitted++}}}
 }
 const input=new Input();
 // Model a controlled input's own setter, bypassed by the prototype setter.
 Object.defineProperty(input,'value',{get(){return accepted},set(v){accepted=v;tracked=v}});
 class Event{constructor(type,options={}){this.type=type;Object.assign(this,options)}}
 const document={execCommand(command,showUI,value){assert.equal(command,'insertText');accepted=value;input.dispatchEvent({type:'input'});return true},querySelector:()=>input,addEventListener:(name,fn)=>listeners.set(name,fn),dispatchEvent:e=>responses.push(e)};
 vm.runInNewContext(source,{document,HTMLInputElement:Input,InputEvent:Event,Event,CustomEvent:Event,setTimeout,Promise,JSON,Error});
 return {async run(postcode){await listeners.get('duo-postcode-request')({detail:JSON.stringify({id:'test',postcode})});return {submitted,responses:responses.map(r=>JSON.parse(r.detail))}}};
}
test('controlled input receives postcode before native form submission',async()=>{
 const result=await fixture().run('2150');assert.equal(result.submitted,1);assert.equal(result.responses[0].error,'');assert.equal(result.responses[0].value,'2150');
});
test('page resetting the input is reported instead of submitting empty postcode',async()=>{
 const result=await fixture(true).run('2150');assert.equal(result.submitted,0);assert.match(result.responses[0].error,/页面未接受邮编/);
});
test('invalid postcode never reaches the form',async()=>{
 const result=await fixture().run('abc');assert.equal(result.submitted,0);assert.equal(result.responses.length,0);
});
