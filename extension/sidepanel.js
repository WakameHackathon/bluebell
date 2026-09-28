(() => {
 const $=s=>document.querySelector(s),thread=$('#thread');
 let taskId=null,mode='self',pagePermission='none';
 function bubble(role,text){const e=document.createElement('div');e.className='bubble '+role;e.textContent=text;thread.append(e);thread.scrollTop=thread.scrollHeight}
 function call(message){return new Promise((resolve,reject)=>chrome.runtime.sendMessage(message,r=>{if(chrome.runtime.lastError)return reject(new Error(chrome.runtime.lastError.message));if(!r?.ok)return reject(new Error(r?.error||'插件暂时无法完成'));resolve(r.data)}))}
 function selectMode(value){mode=value;document.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('selected',b.dataset.mode===value));}
 function setPermission(value){pagePermission=value;$('#capture').disabled=value!=='read-visible-text';$('#orb-status').textContent=value==='read-visible-text'?'当前页文字读取已授权，仍需手动点击':'悬浮球已在网页显示 · 页面文字读取关闭';if(value!=='read-visible-text'){$('#page-text').value='';$('#page-title').textContent='尚未读取';delete $('#page-text').dataset.url;}}
 async function init(){
  $('#service-status').textContent='正在检查本地 Agent…';
  const saved=await chrome.storage.local.get(['taskId','mode','pagePermission']);taskId=saved.taskId||null;selectMode(saved.mode||'self');setPermission(saved.pagePermission||'none');
  try{const s=await call({type:'agent-status'});$('#service-status').textContent=s.model_configured?'Agent 已连接 · '+s.model:'本机服务已连接 · 本地模式';if(taskId){try{const t=await call({type:'load-task',taskId});t?.turns?.forEach(x=>bubble(x.role==='user'?'user':'',x.content))}catch{}}}
  catch{$('#service-status').textContent='请先启动售后助手本地服务';}
 }
 document.querySelectorAll('[data-mode]').forEach(b=>b.addEventListener('click',()=>{selectMode(b.dataset.mode);chrome.storage.local.set({mode})}));
 chrome.storage.onChanged.addListener((changes,area)=>{if(area!=='local')return;if(changes.mode)selectMode(changes.mode.newValue||'self');if(changes.pagePermission)setPermission(changes.pagePermission.newValue||'none');});
 $('#show-orb').addEventListener('click',async()=>{try{await call({type:'orb-show'});$('#orb-status').textContent='悬浮球已显示';}catch(e){$('#orb-status').textContent=e.message;}});
 $('#capture').addEventListener('click',async()=>{if(pagePermission!=='read-visible-text')return;const b=$('#capture');b.disabled=true;b.textContent='读取中…';try{const r=await call({type:'capture-active-tab'});$('#page-title').textContent=r.page.title+' · '+new URL(r.page.url).host;$('#page-text').value=`网页标题：${r.page.title}\n页面地址：${r.page.url}\n\n${r.page.text}`;$('#page-text').dataset.url=r.page.url;$('#page-title').title=r.page.url}catch(e){$('#page-title').textContent=e.message}finally{b.textContent='重新读取页面';b.disabled=pagePermission!=='read-visible-text';}});
 async function send(){const text=$('#message').value.trim();if(!text)return;bubble('user',text);$('#message').value='';$('#send').disabled=true;chrome.storage.local.set({orbState:'understanding'});try{const data=await call({type:'agent-turn',payload:{task_id:taskId,text,mode,page_evidence:$('#page-text').value,allow_model:$('#remote-consent').checked}});taskId=data.task_id;await chrome.storage.local.set({taskId});bubble('',data.reply);for(const x of data.skill_results||[])bubble('',`能力：${x.skill_id} · ${x.status}\n${x.user_message}`)}catch(e){bubble('',e.message)}finally{$('#remote-consent').checked=false;chrome.storage.local.set({orbState:'idle'});$('#send').disabled=false;$('#message').focus();}}
 $('#send').addEventListener('click',send);$('#message').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}});
 $('#new-task').addEventListener('click',async()=>{taskId=null;await chrome.storage.local.remove('taskId');thread.replaceChildren();bubble('','新任务已开始。请说说要处理哪件商品和你想达到的结果。')});
 init();
})();
