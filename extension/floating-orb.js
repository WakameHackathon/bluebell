(() => {
  if (window.top !== window || document.getElementById('aftercare-assistant-orb-host')) return;

  const host = document.createElement('div');
  host.id = 'aftercare-assistant-orb-host';
  host.style.cssText = 'all:initial;position:fixed;z-index:2147483647;width:190px;height:174px;right:18px;bottom:18px;pointer-events:none;';
  const shadow = host.attachShadow({ mode: 'closed' });
  const style = document.createElement('style');
  style.textContent = `
    :host{all:initial}*{box-sizing:border-box} .root{position:relative;width:100%;height:100%;pointer-events:none;font:13px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif;color:#24384c;user-select:none}
    .orb{position:absolute;left:42px;top:14px;width:124px;height:124px;pointer-events:auto;cursor:grab;touch-action:none;filter:drop-shadow(0 8px 12px #255c7540);transition:filter .2s}.face{position:absolute;inset:0}
    .orb:active{cursor:grabbing}.orb svg{width:100%;height:100%;overflow:visible!important}.arcs{position:absolute;inset:-13px;pointer-events:none}.arcs svg{width:100%;height:100%;overflow:visible!important}
    .hand{position:absolute;z-index:4;width:39px;height:31px;padding:0;border:1.5px solid #326c8d;border-radius:50%;background:radial-gradient(ellipse at 32% 21%,#e1f6ff 0,#9ad8f2 32%,#58acd4 76%,#357ca6 100%);box-shadow:inset 0 1px 3px #fff9,inset 0 -2px 3px #1e587766,0 3px 8px #1c577333;color:#174c69;cursor:pointer;pointer-events:auto;animation:handfloat 3.3s ease-in-out infinite;transition:filter .18s,scale .18s}.hand svg{width:14px;height:14px;display:block;margin:auto;fill:none;stroke:#174c69;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;filter:drop-shadow(0 1px 1px #fff9)}
    .hand:hover,.hand[aria-expanded=true]{filter:brightness(1.13);scale:1.09}.permission{left:12px;top:111px;rotate:-24deg}.mode{left:64px;top:130px;rotate:-9deg;animation-delay:-1.65s}
    @keyframes handfloat{0%,100%{translate:-1px 1px;scale:1 1}35%{translate:-4px -4px;scale:.97 1.04}70%{translate:2px -2px;scale:1.03 .97}}
    .menu{position:absolute;z-index:8;left:8px;top:8px;min-width:156px;padding:9px;background:#ffffffef;border:1px solid #dce9ef;border-radius:14px;box-shadow:0 8px 28px #193b4d30;backdrop-filter:blur(14px);pointer-events:auto;display:none}
    .menu.open{display:grid;gap:5px}.menu strong{font-size:12px;padding:2px 4px 4px}.choice{border:0;border-radius:9px;background:transparent;padding:8px;text-align:left;color:inherit;font:inherit;cursor:pointer}.choice:hover{background:#eaf5fa}.choice.selected{background:#dff1f9;color:#185b7b;font-weight:600}.note{font-size:10px;color:#6c8291;padding:2px 4px}
    .hide{position:absolute;right:20px;top:0;width:25px;height:25px;border:1px solid #d8e5ec;border-radius:50%;background:#fff;color:#486174;font-size:17px;line-height:20px;cursor:pointer;pointer-events:auto;opacity:0;transition:opacity .15s}.root:hover .hide,.hide:focus-visible{opacity:.94}
    .voice{position:absolute;left:23px;top:0;width:164px;height:26px;border-radius:99px;background:#eef9ff;border:1px solid #84c6e3;display:none;align-items:center;justify-content:center;gap:4px;pointer-events:none}.voice[data-active=true]{display:flex}.voice i{width:3px;height:var(--h);max-height:16px;border-radius:8px;background:linear-gradient(#55c9bf,#548fdf);animation:wave .55s ease-in-out infinite alternate}.voice i:nth-child(2n){animation-delay:-.2s}@keyframes wave{to{transform:scaleY(.25)}}
    .root[data-working=true] .orb{filter:drop-shadow(0 8px 13px #255c7550)}
    @media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}
  `;
  shadow.append(style);
  const root = document.createElement('div');
  root.className = 'root';
  root.innerHTML = `<button class="hand permission" aria-label="页面权限选项" title="页面权限" aria-expanded="false"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 19 6v5c0 4.6-2.8 7.8-7 10-4.2-2.2-7-5.4-7-10V6l7-3Z"/><path d="m9 12 2 2 4-4"/></svg></button><button class="hand mode" aria-label="协助模式选项" title="协助模式" aria-expanded="false"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14M5 17h14"/><circle cx="9" cy="7" r="2" fill="#d9f3fc"/><circle cx="15" cy="17" r="2" fill="#d9f3fc"/></svg></button><div class="orb" role="button" tabindex="0" aria-label="打开售后助手侧边栏"><div class="arcs" aria-hidden="true"></div><div class="face"></div></div><div class="voice" aria-hidden="true"><i style="--h:7px"></i><i style="--h:13px"></i><i style="--h:10px"></i><i style="--h:16px"></i><i style="--h:9px"></i><i style="--h:14px"></i><i style="--h:6px"></i></div><button class="hide" aria-label="隐藏悬浮球" title="隐藏">×</button><div class="menu" role="dialog" aria-label="设置"></div>`;
  shadow.append(root);
  document.documentElement.append(host);

  const $ = (selector) => shadow.querySelector(selector);
  const orb = $('.orb'), permissionButton = $('.permission'), modeButton = $('.mode'), menu = $('.menu');
  const originKey = (() => { try { return new URL(location.href).origin; } catch { return 'unknown'; } })();
  let ball, arcs, prefs = {}, dragging = false, moved = false, start = null, originPos = null, closeMenuTimer;
  const defaults = { mode: 'self', pagePermission: 'none', orbPositions: {}, hiddenOrbs: {}, orbState: 'idle' };

  function applyPosition(pos) {
    const maxLeft = Math.max(0, innerWidth - host.offsetWidth);
    const maxTop = Math.max(0, innerHeight - host.offsetHeight);
    const left = Math.min(maxLeft, Math.max(0, pos?.left == null ? maxLeft : Number(pos.left)));
    const top = Math.min(maxTop, Math.max(0, pos?.top == null ? maxTop : Number(pos.top)));
    host.style.left = `${left}px`; host.style.top = `${top}px`; host.style.right = 'auto'; host.style.bottom = 'auto';
    return { left, top };
  }
  function savePosition() {
    const pos = { left: host.offsetLeft, top: host.offsetTop };
    prefs.orbPositions = { ...(prefs.orbPositions || {}), [originKey]: pos };
    chrome.storage.local.set({ orbPositions: prefs.orbPositions });
  }
  function closeMenu() { menu.classList.remove('open'); permissionButton.setAttribute('aria-expanded', 'false'); modeButton.setAttribute('aria-expanded', 'false'); }
  function openMenu(kind) {
    clearTimeout(closeMenuTimer); closeMenu();
    permissionButton.setAttribute('aria-expanded', String(kind === 'permission'));
    modeButton.setAttribute('aria-expanded', String(kind === 'mode'));
    const isPermission = kind === 'permission';
    menu.innerHTML = isPermission
      ? `<strong>页面权限</strong><button class="choice ${prefs.pagePermission === 'none' ? 'selected' : ''}" data-permission="none">仅对话</button><button class="choice ${prefs.pagePermission === 'read-visible-text' ? 'selected' : ''}" data-permission="read-visible-text">允许手动读取当前页文字</button><span class="note">读取还需在侧栏中主动点击</span>`
      : `<strong>协助模式</strong><button class="choice ${prefs.mode === 'self' ? 'selected' : ''}" data-mode="self">我自己操作</button><button class="choice ${prefs.mode === 'guided' ? 'selected' : ''}" data-mode="guided">陪我操作</button><button class="choice ${prefs.mode === 'auto' ? 'selected' : ''}" data-mode="auto">帮我准备</button><span class="note">网页自动操作尚未开放</span>`;
    menu.classList.add('open');
    menu.querySelectorAll('[data-permission]').forEach(button => button.addEventListener('click', async () => {
      prefs.pagePermission = button.dataset.permission; await chrome.storage.local.set({ pagePermission: prefs.pagePermission }); render(); closeMenu();
    }));
    menu.querySelectorAll('[data-mode]').forEach(button => button.addEventListener('click', async () => {
      prefs.mode = button.dataset.mode; await chrome.storage.local.set({ mode: prefs.mode }); render(); closeMenu();
    }));
  }
  function render() {
    permissionButton.title = prefs.pagePermission === 'read-visible-text' ? '页面权限：允许手动读取当前页文字' : '页面权限：仅对话';
    modeButton.title = `协助模式：${({ self: '我自己操作', guided: '陪我操作', auto: '帮我准备' })[prefs.mode] || '我自己操作'}`;
    root.dataset.working = String(prefs.orbState === 'working');
    $('.voice').dataset.active = String(prefs.orbState === 'speaking');
    if (ball) ball.setEmotion(prefs.orbState === 'understanding' || prefs.orbState === 'working' ? '30' : '02');
    if (arcs) arcs.setState(prefs.orbState === 'working' ? 'working' : 'idle');
  }

  try {
    ball = GrokBall.create($('.face'), { emotion: '02', color: '#51b4ef', eyeColor: '#214d70', shape: 'blob', lite: true, label: '售后助手' });
    arcs = AftercareOrb.create($('.arcs'), { effectsOnly: true });
    const apply = ball.ball.applyPose.bind(ball.ball);
    const adapt = (pose, side) => ({ ...pose, scaleX: pose.scaleX * 1.1, scaleY: pose.scaleY * .94, x: pose.x + side * 2.5 });
    ball.ball.applyPose = pose => apply({ ...pose, left: adapt(pose.left, -1), right: adapt(pose.right, 1) });
  } catch (error) { console.warn('售后助手悬浮球初始化失败', error); }

  permissionButton.addEventListener('click', event => { event.stopPropagation(); menu.classList.contains('open') && permissionButton.getAttribute('aria-expanded') === 'true' ? closeMenu() : openMenu('permission'); });
  modeButton.addEventListener('click', event => { event.stopPropagation(); menu.classList.contains('open') && modeButton.getAttribute('aria-expanded') === 'true' ? closeMenu() : openMenu('mode'); });
  menu.addEventListener('click', event => event.stopPropagation());
  document.addEventListener('pointerdown', event => { if (!host.contains(event.target)) closeMenu(); }, true);
  document.addEventListener('keydown', event => { if (event.key === 'Escape') closeMenu(); });

  function openPanel() { chrome.runtime.sendMessage({ type: 'orb-open-panel' }).catch(() => {}); }
  orb.addEventListener('pointerdown', event => {
    if (event.button !== 0) return;
    dragging = true; moved = false; start = { x: event.clientX, y: event.clientY }; originPos = { x: host.offsetLeft, y: host.offsetTop };
    orb.setPointerCapture(event.pointerId); event.preventDefault();
  });
  orb.addEventListener('pointermove', event => {
    if (!dragging || !start || !originPos) return;
    const dx = event.clientX - start.x, dy = event.clientY - start.y;
    if (Math.abs(dx) + Math.abs(dy) > 5) moved = true;
    if (moved) applyPosition({ left: originPos.x + dx, top: originPos.y + dy });
  });
  orb.addEventListener('pointerup', event => {
    if (!dragging) return;
    dragging = false; orb.releasePointerCapture(event.pointerId);
    if (moved) savePosition(); else openPanel();
    start = originPos = null;
  });
  orb.addEventListener('pointercancel', () => { dragging = false; start = originPos = null; });
  orb.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); openPanel(); } });
  $('.hide').addEventListener('click', async event => {
    event.stopPropagation(); prefs.hiddenOrbs = { ...(prefs.hiddenOrbs || {}), [originKey]: true };
    await chrome.storage.local.set({ hiddenOrbs: prefs.hiddenOrbs }); host.style.display = 'none';
  });
  chrome.runtime.onMessage.addListener(message => {
    if (message?.type === 'orb-show') { prefs.hiddenOrbs = { ...(prefs.hiddenOrbs || {}), [originKey]: false }; host.style.display = ''; }
    if (message?.type === 'orb-state' && ['idle', 'understanding', 'working', 'speaking'].includes(message.state)) { prefs.orbState = message.state; render(); }
  });
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== 'local') return;
    for (const key of ['mode', 'pagePermission', 'orbState']) if (changes[key]) prefs[key] = changes[key].newValue;
    if (changes.hiddenOrbs) prefs.hiddenOrbs = changes.hiddenOrbs.newValue || {};
    if (changes.orbPositions) prefs.orbPositions = changes.orbPositions.newValue || {};
    render();
    if (changes.hiddenOrbs) host.style.display = prefs.hiddenOrbs[originKey] ? 'none' : '';
  });

  chrome.storage.local.get(defaults).then(stored => {
    prefs = { ...defaults, ...stored };
    applyPosition(prefs.orbPositions?.[originKey]);
    host.style.display = prefs.hiddenOrbs?.[originKey] ? 'none' : '';
    render();
  }).catch(() => applyPosition(null));
  window.addEventListener('resize', () => applyPosition({ left: host.offsetLeft, top: host.offsetTop }));
})();
