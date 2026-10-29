// Run only on the public product page, in the same JS world as its form.
// No extension APIs, cookies, credentials or arbitrary code are exposed.
document.addEventListener('duo-postcode-request', async event => {
 let request;
 try {request=JSON.parse(event.detail)} catch {return}
 if(!/^[0-9]{4}$/.test(request.postcode)||typeof request.id!=='string')return;
 const input=document.querySelector('[role="dialog"] input[data-autom="zipCode"]');
 let error='';
 try {
  if(!input)throw Error('找不到邮编输入框');
  // Let the focus render finish before using the browser's editing pipeline.
  // A synthetic input/change pair can leave the controlled field empty.
  input.focus();
  await new Promise(resolve=>setTimeout(resolve,300));
  input.select();
  if(!document.execCommand('insertText',false,request.postcode))
   throw Error('浏览器未执行邮编文本输入');
  await new Promise(resolve=>setTimeout(resolve,500));
  if(input.value!==request.postcode)throw Error('页面未接受邮编，当前输入值：'+input.value);
  const form=input.closest('form');
  if(!form)throw Error('找不到查询表单');
  form.requestSubmit();
 } catch(e){error=e.message}
 document.dispatchEvent(new CustomEvent('duo-postcode-response',{detail:JSON.stringify({id:request.id,error,value:input?.value||''})}));
});
