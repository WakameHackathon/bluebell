/* Independent SVG implementation for this prototype. No third-party expression engine. */
window.AftercareOrb={create(mount,options={}){
 const ns='http://www.w3.org/2000/svg';
 mount.innerHTML=`<svg viewBox="0 0 300 300" role="img" aria-label="售后助手" xmlns="${ns}"><defs><radialGradient id="body-shade" cx="32%" cy="24%" r="85%"><stop stop-color="#8cd6f1"/><stop offset=".55" stop-color="#55b5df"/><stop offset="1" stop-color="#398cbb"/></radialGradient><linearGradient id="work-color"><stop stop-color="#32cfa5"/><stop offset=".55" stop-color="#885de8"/><stop offset="1" stop-color="#ed83bc"/></linearGradient></defs><g data-work-effects="back"></g><g class="character"><path d="M150 27 C219 23 268 76 267 147 C267 216 219 270 148 272 C78 272 30 220 32 150 C32 82 80 30 150 27Z" fill="url(#body-shade)"/><g class="face"><g class="eye-left"><rect x="-13" y="-17" width="26" height="34" rx="12" fill="#214d70"/><circle cx="-4" cy="-8" r="3" fill="#b5e8f6" opacity=".8"/></g><g class="eye-right"><rect x="-13" y="-17" width="26" height="34" rx="12" fill="#214d70"/><circle cx="-4" cy="-8" r="3" fill="#b5e8f6" opacity=".8"/></g></g></g><g data-work-effects="front"></g></svg>`;
 const q=s=>mount.querySelector(s), eyes=[q('.eye-left'),q('.eye-right')], body=q('.character');
 if(options.effectsOnly){body.style.display='none'}
 const layers=[q('[data-work-effects="back"]'),q('[data-work-effects="front"]')];
 const paths=layers.map(layer=>[0,1].map(()=>{const p=document.createElementNS(ns,'path');p.setAttribute('fill','none');p.setAttribute('stroke','url(#work-color)');p.setAttribute('stroke-linecap','round');layer.appendChild(p);return p}));
 let state='idle',active=true,raf=0,gaze=[0,0],target=[0,0];
 const moods={idle:[1,1,0],listening:[1.15,1.15,-7],understanding:[.72,1.05,8],working:[.75,.75,0],speaking:[.85,.95,-3],clarify:[1.2,.6,-10],waiting:[.85,.85,3]};
 function draw(ms){const t=active?ms/1000:0,m=moods[state]||moods.idle;
 gaze=gaze.map((v,i)=>v+(target[i]-v)*.09);
 const blink=active?1-.93*Math.exp(-Math.pow(((t+1.3)%4.9-2.4)/.095,2)):1;
 body.setAttribute('transform',`translate(0 ${Math.sin(t*1.7)*2.2}) rotate(${Math.sin(t*.9)*1.6} 150 150)`);
 eyes.forEach((e,i)=>{const h=m[i]*blink;const x=(i?176:124)+gaze[0]*7+Math.sin(t*.7)*2;const y=143+gaze[1]*5+(state==='understanding'?-6:0)+Math.sin(t*1.4+i*.7)*1.4;e.setAttribute('transform',`translate(${x} ${y}) rotate(${i?-m[2]:m[2]}) scale(${1+(state==='speaking'?Math.sin(t*5+i)*.05:0)} ${h})`)});
 layers.forEach((e,i)=>e.style.display=state==='working'&&active&&(!options.effectsOnly||i===1)?'':'none');
 if(state==='working'&&active){for(let strand=0;strand<2;strand++){
 const segments=['',''];let prev=-1;
 // Independent drifting orbital planes: each arc changes height, tilt and radius.
 const phase=strand*2.3;
 const tilt=(strand?-.32:.32)+Math.sin(t*.43+phase)*.2;
 const centerY=(strand?135:177)+Math.sin(t*.57+phase)*14;
 const radius=132+strand*6+Math.sin(t*.38+phase)*5;
 const depthRadius=38+Math.sin(t*.49+phase)*9;
 for(let n=0;n<=70;n++){const a=t*(strand?-.85:1.05)+strand*2.8+n/70*4.4;const depth=Math.sin(a);const side=depth>0?1:0;const horizontal=Math.cos(a)*radius;const vertical=depth*depthRadius;const x=150+horizontal*Math.cos(tilt)-vertical*Math.sin(tilt);const y=centerY+horizontal*Math.sin(tilt)+vertical*Math.cos(tilt)+Math.sin(a*2+t+phase)*3;segments[side]+=(side!==prev?'M':'L')+x.toFixed(2)+' '+y.toFixed(2)+' ';prev=side;}
 paths.forEach((pair,i)=>{pair[strand].setAttribute('d',segments[i]);pair[strand].setAttribute('stroke-width',strand?5:7);pair[strand].setAttribute('opacity',strand?.88:1)});
 }}
 }
 function loop(t){draw(t);if(active)raf=requestAnimationFrame(loop)}
 raf=requestAnimationFrame(loop);
 return {setState(s){state=s;draw(performance.now())},setActive(v){active=v;cancelAnimationFrame(raf);draw(performance.now());if(v)raf=requestAnimationFrame(loop)},renderStatic(){draw(0)},setGaze(x,y){target=[x,y].map(v=>Math.max(-1,Math.min(1,v)))},clearGaze(){target=[0,0]}};
}};
