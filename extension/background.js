chrome.runtime.onInstalled.addListener(async () => {
  await chrome.sidePanel.setPanelBehavior({openPanelOnActionClick:true});
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async()=>{
    if(message?.type==='orb-open-panel'){
      if(!sender.tab?.id) throw new Error('无法确定当前网页。');
      await chrome.sidePanel.open({tabId:sender.tab.id});
      return {ok:true};
    }
    if(message?.type==='orb-show'){
      const [tab]=await chrome.tabs.query({active:true,lastFocusedWindow:true});
      if(!tab?.id) throw new Error('当前没有可用网页。');
      await chrome.tabs.sendMessage(tab.id,{type:'orb-show'});
      return {ok:true};
    }
    if(message?.type==='capture-active-tab'){
      const prefs=await chrome.storage.local.get('pagePermission');
      if(prefs.pagePermission!=='read-visible-text') throw new Error('请先通过悬浮球左侧小椭圆开启“允许手动读取当前页文字”。');
      const [tab]=await chrome.tabs.query({active:true,lastFocusedWindow:true});
      if(!tab?.id || !tab.url || !/^https?:/.test(tab.url)) throw new Error('当前标签页不是普通网页，无法读取。');
      const [{result}]=await chrome.scripting.executeScript({target:{tabId:tab.id},func:()=>({
        title:document.title,
        url:location.origin,
        text:(document.body?.innerText||'').slice(0,12000),
        capturedAt:new Date().toISOString()
      })});
      return {ok:true,data:{page:result}};
    }
    if(message?.type==='agent-turn'){
      const response=await fetch('http://127.0.0.1:8766/api/agent/turn',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(message.payload)});
      const data=await response.json(); if(!response.ok) throw new Error(data.detail||'本地 Agent 暂不可用。'); return {ok:true,data};
    }
    if(message?.type==='load-task'){
      const response=await fetch('http://127.0.0.1:8766/api/tasks/'+encodeURIComponent(message.taskId));
      if(response.status===404)return {ok:true,data:null};
      const data=await response.json();if(!response.ok)throw new Error(data.detail||'任务读取失败。');return {ok:true,data};
    }
    if(message?.type==='agent-status'){
      const response=await fetch('http://127.0.0.1:8766/api/status');return {ok:true,data:await response.json()};
    }
    throw new Error('未知的插件请求。');
  })().then(sendResponse).catch(error=>sendResponse({ok:false,error:error.message}));
  return true;
});
