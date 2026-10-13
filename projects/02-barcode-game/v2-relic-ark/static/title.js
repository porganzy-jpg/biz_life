/* 질랜디아 — 타이틀·불러오기 화면.
 * base.html 에서 <body> 바로 뒤에 한 줄로 불린다(base.js 보다 먼저).
 *  - 키아트: 배경 담당 static/art/title/meta.json(크롭 landscape·phone × 층 far·cliff·tower·near, 로고 자리). 없으면 M5 층
 *  - 로고: static/art/brand/zealandia/lockup_horizontal_dark.png(로고 A 「가라앉은 대륙의 창」 — 새로 만들지 않는다)
 *  - 진행: 이 창이 열려 있는 동안 시작된 그림 요청(Image.src)을 실제로 세고 + 첫 /api/ark. 가짜 막대 없음
 *  - 다 되면 「눌러서 시작」(ui_moments title.start_label[0]). 그 첫 탭에서 소리를 연다(자동 재생 정책)
 *  - 다시 온 사람: 그사이 있었던 일 수 한 줄(title.return.*), 처음: title.tagline[0]
 *  - 줄임 동작(prefers-reduced-motion)이면 시차·흐름·숨쉬기 없음
 * base.js 와의 약속: 첫 로드에서 window.ARKTITLE.arkLoaded(st) / arkFailed(err) 를 부르고, 큰 창 줄(qReady)은 ARKTITLE.gate 뒤에 연다.
 */
(() => {
  'use strict';
  const RM = !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
  let firstVisit = true;
  try { firstVisit = !localStorage.getItem('ark_uid'); } catch (e) { /* 저장소가 막히면 처음으로 본다 */ }
  const T0 = performance.now();
  const D = { log: [], t: {} };                       // ★ 검수용

  // ── 1. 진행: 이 창이 열려 있는 동안 시작된 그림 요청을 센다 ─────────────────
  let tracking = true, total = 0, settled = 0, lastStart = performance.now();
  const desc = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src');
  if (desc && desc.set) {
    Object.defineProperty(HTMLImageElement.prototype, 'src', {
      configurable: true, enumerable: desc.enumerable, get: desc.get,
      set(v) {
        if (tracking && v && !this.__ttl && !/^data:/.test(String(v))) {
          this.__ttl = 1; total++; lastStart = performance.now();
          const fin = () => { if (this.__ttl === 1) { this.__ttl = 2; settled++; tick(); } };
          this.addEventListener('load', fin, { once: true }); this.addEventListener('error', fin, { once: true });
        }
        desc.set.call(this, v);
      },
    });
  }
  const untrack = () => { tracking = false; if (desc) Object.defineProperty(HTMLImageElement.prototype, 'src', desc); };

  // ── 2. 화면 ─────────────────────────────────────────────────────────
  const css = `
#ttl{position:fixed; inset:0; z-index:100; overflow:hidden; background:#04141b; color:#e6d7b0; font-family:"Noto Sans KR",sans-serif;
  -webkit-tap-highlight-color:transparent; transition:opacity .7s ease; user-select:none}
#ttl.off{opacity:0; pointer-events:none}
#ttl canvas{position:absolute; inset:0; width:100%; height:100%; display:block}
#ttl .tv{position:absolute; inset:0; background:radial-gradient(ellipse at 50% 45%, rgba(4,20,27,0) 55%, rgba(2,10,14,.55) 100%); pointer-events:none}
#ttl .tlogo{position:absolute; left:0; top:0; height:auto; filter:drop-shadow(0 6px 18px rgba(0,0,0,.55)); opacity:0; transition:opacity .8s ease}
#ttl .tlogo.on{opacity:1}
#ttl .tbox{position:absolute; display:flex; flex-direction:column; align-items:stretch; text-align:right}
#ttl .tline{margin:0; min-height:1.5em; font-size:15px; line-height:1.55; color:#e8d9b4; text-shadow:0 1px 6px rgba(0,0,0,.9), 0 0 12px rgba(0,0,0,.6)}
#ttl .tline.ret{color:#cfe8ec}
#ttl .tslot{display:flex; align-items:center; gap:10px; margin-top:10px; min-height:52px}
#ttl .tlamp{flex:none; width:48px; height:48px; background-repeat:no-repeat; background-size:800% 100%; filter:drop-shadow(0 0 8px rgba(240,176,85,.25))}
#ttl .tlamp.lit{animation:ttlBreath 2s ease-in-out infinite}
@keyframes ttlBreath{50%{opacity:.9}}
#ttl .tprog{flex:1; min-width:0; text-align:left}
#ttl .tbar{position:relative; height:4px; border-radius:2px; background:rgba(207,232,236,.16); overflow:hidden}
#ttl .tbar i{position:absolute; left:0; top:0; bottom:0; width:0; background:linear-gradient(90deg,#6fc9c4,#f0b055); border-radius:2px; transition:width .25s linear}
#ttl .tsub{display:flex; justify-content:space-between; gap:8px; margin-top:6px; font-size:11.5px; color:#a9bcb9; text-shadow:0 1px 4px rgba(0,0,0,.9)}
#ttl .tgo{flex:1; min-height:46px; padding:0 26px; font:inherit; font-size:15px; letter-spacing:.06em; color:#1a150e; background:#f0b055;
  border:0; border-radius:24px; box-shadow:0 0 0 3px rgba(240,176,85,.25), 0 6px 18px rgba(0,0,0,.45); cursor:pointer; animation:ttlPulse 2.4s ease-in-out infinite}
#ttl [hidden]{display:none !important}
@keyframes ttlPulse{50%{box-shadow:0 0 0 7px rgba(240,176,85,.12), 0 6px 18px rgba(0,0,0,.45)}}
@media (prefers-reduced-motion:reduce){ #ttl, #ttl .tlogo{transition:none} #ttl .tgo, #ttl .tlamp.lit{animation:none} }
@media (max-height:500px){
  #ttl .tline{font-size:12px; line-height:1.45}
  #ttl .tslot{margin-top:6px; min-height:44px; gap:8px}
  #ttl .tlamp{width:40px; height:40px}
  #ttl .tgo{min-height:44px; font-size:14px}
  #ttl .tsub{font-size:10.5px; margin-top:4px}
}`;
  const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
  const el = document.createElement('div'); el.id = 'ttl'; el.setAttribute('role', 'dialog'); el.setAttribute('aria-label', '질랜디아');
  // 고정 문자열만(사용자·서버 글은 textContent 로 넣는다)
  el.innerHTML = '<canvas aria-hidden="true"></canvas><div class="tv"></div>' +
    '<img class="tlogo" alt="질랜디아" src="/static/art/brand/zealandia/lockup_horizontal_dark.png"><div class="tbox">' +
    '<p class="tline"></p><div class="tslot"><i class="tlamp" aria-hidden="true" hidden></i>' +
    '<div class="tprog" aria-live="polite"><div class="tbar"><i></i></div><div class="tsub"><span class="tload"></span><span class="tpct">0%</span></div></div>' +
    '<button class="tgo" hidden></button></div></div>';
  document.body.appendChild(el);
  const $ = (s) => el.querySelector(s);
  const logo = $('.tlogo');
  const logoOn = () => { logo.classList.add('on'); if (!D.t.logo) D.t.logo = Math.round(performance.now() - T0); };
  if (logo.complete && logo.naturalWidth) logoOn(); else logo.addEventListener('load', logoOn);

  // 문장(시나리오 ui_moments.title) — 오기 전에는 같은 문장의 기본값
  const TX = { tagline: '내 집의 진짜 물건이, 바다 밑 사람들의 삶이 됩니다.', start: '눌러서 시작',
               ret: { zero: '관리실입니다. 그사이 방주는 조용했습니다. 다들 잘 지내고 있었습니다.', one: '관리실입니다. 그사이 방주에 일이 하나 있었습니다.', many: '관리실입니다. 그사이 방주에 {n}가지 일이 있었습니다.' },
               loading: ['관리실 장부를 펴고 있습니다…'] };
  let arkSt = null, arkErr = null, ready = false;
  fetch('/api/text/moments').then(r => (r.ok ? r.json() : null)).then(j => {
    const t = j && j.title; if (!t) return;
    if ((t.tagline || [])[0]) TX.tagline = t.tagline[0];
    if ((t.start_label || [])[0]) TX.start = t.start_label[0];
    if (t.return) Object.assign(TX.ret, t.return);
    if ((t.loading || []).length) TX.loading = t.loading;
    lineOut(); loadLine(); D.log.push('moments');
  }).catch(() => {});
  function lineOut() {
    const p = $('.tline');
    if (firstVisit) { p.textContent = TX.tagline; p.className = 'tline'; return; }
    if (!arkSt) { p.textContent = ''; return; }
    const ov = arkSt.overnight || {}, items = (ov.items || ov.lines || []).filter(x => x && x.kind !== 'needs');
    const n = items.length;
    p.textContent = n <= 0 ? TX.ret.zero : n === 1 ? TX.ret.one : String(TX.ret.many).replace('{n}', n);
    p.className = 'tline ret'; D.retN = n;
  }
  lineOut();
  let li = 0;
  function loadLine() { const s = $('.tload'); if (s && !ready) s.textContent = TX.loading[li++ % TX.loading.length]; }
  loadLine(); const liT = setInterval(loadLine, 2400);

  // ── 3. 키아트 ─────────────────────────────────────────────────────
  const cv = $('canvas'), ctx = cv.getContext('2d'), TD = '/static/art/title/', M5 = '/static/art/maps/m5/';
  let meta = null, crop = null, layers = [], lamp = null, raf = 0, alive = true;
  const DEF = [['back.jpg', 0, 0, 5600, 3400, 0.15], ['cliff.png', 0, 140, 1277, 2782, 0.45], ['tower_shell.png', 949, 510, 3907, 2890, 0.7],
               ['elevator_shaft.png', 1815, 726, 209, 2277, 0.7], ['entrance.png', 3336, 811, 880, 719, 0.7], ['front.png', 0, 2435, 5600, 965, 1]];
  const mkImg = (src, L) => { const img = new Image(); L.img = img; img.onload = () => { L.ok = img.naturalWidth > 0; L.born = performance.now(); }; img.src = src; return L; };
  function pickCrop() {                                   // 화면 비에 가까운 크롭(폰 가로 844×390 ≈ 2.16, 1280×800 = 1.6)
    const r = innerWidth / innerHeight, cs = (meta && meta.crops) || {};
    return Object.keys(cs).map(k => Object.assign({ name: k }, cs[k]))
      .sort((a, b) => Math.abs(Math.log(a.size[0] / a.size[1] / r)) - Math.abs(Math.log(b.size[0] / b.size[1] / r)))[0] || null;
  }
  function useCrop() {
    const c = pickCrop(); if (!c || (crop && crop.name === c.name)) return; crop = c;
    const par = meta.parallax || {};
    layers = (meta.order || Object.keys(c.files)).filter(n => c.files[n]).map(n => mkImg(TD + c.files[n], { n, par: par[n] == null ? 0.5 : par[n], ok: false }));
    D.art = 'title:' + c.name; layout();
  }
  function fallbackM5() { if (layers.length) return; layers = DEF.map(([f, x, y, w, h, par]) => mkImg(M5 + f, { x, y, w, h, par, ok: false, m5: true })); D.art = 'm5'; layout(); }
  fetch(TD + 'meta.json').then(r => (r.ok ? r.json() : null)).then(j => {
    if (!(j && j.crops && Object.keys(j.crops).length)) { fallbackM5(); return; }
    meta = j; useCrop();
    if (j.loading && j.loading.file) {
      lamp = j.loading; const lp = $('.tlamp'); lp.style.backgroundImage = 'url(' + TD + j.loading.file + ')'; lp.style.backgroundSize = ((lamp.frames || 8) * 100) + '% 100%'; lp.hidden = false;
      lampAt(pct / 100);
    }
  }).catch(fallbackM5);
  // 크롭 좌표 → 화면: 덮기(가운데 정렬)
  function fitOf() {
    const W = innerWidth, H = innerHeight;
    if (crop) { const [cw, ch] = crop.size, s = Math.max(W / cw, H / ch); return { s, ox: (W - cw * s) / 2, oy: (H - ch * s) / 2, cw, ch }; }
    const s = Math.max(W / 5600, H / 3400) * 1.08; return { s, ox: W / 2 - 0.36 * 5600 * s, oy: H / 2 - 0.42 * 3400 * s, cw: 5600, ch: 3400 };
  }
  function layout() {
    const W = innerWidth, H = innerHeight, f = fitOf(), bx = $('.tbox');
    let L;                                                 // 로고 사각형(화면 px)
    if (crop && crop.logo) L = { x: f.ox + crop.logo.x * f.s, y: f.oy + crop.logo.y * f.s, w: crop.logo.w * f.s, h: crop.logo.h * f.s };
    else { const w = Math.min(W * 0.42, 520); L = { x: W - w - W * 0.05, y: H * 0.1, w, h: w * 300 / 860 }; }
    if (L.x + L.w > W - 8) L.x = W - 8 - L.w;
    if (L.y + L.h > H - 8) L.y = H - 8 - L.h;
    if (L.x < 8) L.x = 8;
    logo.style.left = L.x + 'px'; logo.style.top = L.y + 'px'; logo.style.width = L.w + 'px';
    const bw = Math.min(Math.max(L.w, 300), W - 32), below = H - (L.y + L.h);
    bx.style.width = bw + 'px'; bx.style.left = Math.max(16, L.x + L.w - bw) + 'px';
    if (below >= 130) { bx.style.top = (L.y + L.h + 6) + 'px'; bx.style.bottom = ''; bx.dataset.at = 'below'; }
    else { bx.style.top = ''; bx.style.bottom = (H - L.y + 4) + 'px'; bx.dataset.at = 'above'; }   // 폰 가로: 로고 아래가 좁으면 로고 위(물빛 쪽)에
    D.logo = { x: Math.round(L.x), y: Math.round(L.y), w: Math.round(L.w), h: Math.round(L.h) }; D.box = bx.dataset.at;
  }
  addEventListener('resize', () => { if (!alive) return; if (meta) useCrop(); layout(); });
  layout();
  let px = 0, py = 0, tx = 0, ty = 0;
  if (!RM) el.addEventListener('pointermove', (e) => { tx = (e.clientX / innerWidth - 0.5) * 2; ty = (e.clientY / innerHeight - 0.5) * 2; });
  function draw(now) {
    if (!alive) return;
    const dpr = Math.min(2, devicePixelRatio || 1), W = innerWidth, H = innerHeight;
    if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.fillStyle = '#04141b'; ctx.fillRect(0, 0, W, H);
    const f = fitOf(), t = now / 1000;
    px += (tx - px) * 0.04; py += (ty - py) * 0.04;
    // 카메라: 가로 ±1.5%, 세로 ±1%, 주기 8초·10초(meta motion_hint) + 손끝 쪽으로 조금. 오프셋 = 카메라 × parallax
    const camX = RM ? 0 : (Math.sin(t * 2 * Math.PI / 8) * 0.015 + px * 0.008) * f.cw;
    const camY = RM ? 0 : (Math.sin(t * 2 * Math.PI / 10 + 1) * 0.01 + py * 0.006) * f.ch;
    ctx.imageSmoothingEnabled = true;
    layers.forEach(L => {
      if (!L.ok) return;
      ctx.globalAlpha = RM ? 1 : Math.min(1, (now - L.born) / 600);
      if (L.m5) ctx.drawImage(L.img, f.ox + (L.x - camX * L.par) * f.s, f.oy + (L.y - camY * L.par) * f.s, L.w * f.s, L.h * f.s);
      else {
        const [lx, ly] = crop.layer_offset || [0, 0], [lw, lh] = crop.layer_size || [L.img.naturalWidth, L.img.naturalHeight];
        ctx.drawImage(L.img, f.ox + (lx - camX * L.par) * f.s, f.oy + (ly - camY * L.par) * f.s, lw * f.s, lh * f.s);
      }
    });
    ctx.globalAlpha = 1;
    if (!D.t.art && layers.length && layers.every(L => L.ok)) D.t.art = Math.round(now - T0);
    raf = requestAnimationFrame(draw);
  }
  raf = requestAnimationFrame(draw);
  function lampAt(p) {                                   // 손등불 8칸: 진행률 p → 칸 round(p×7)
    if (!lamp) return; const n = lamp.frames || 8, fr = Math.round(Math.max(0, Math.min(1, p)) * (n - 1));
    $('.tlamp').style.backgroundPosition = (fr / (n - 1) * 100) + '% 0'; D.lampFrame = fr;
  }

  // ── 4. 다 됐나 ─────────────────────────────────────────────────────
  let arkDone = false, pct = 0;
  const later = [];                                     // 첫 화면 뒤로 미룬 미리 받기(모든 방 플레이트·카드 틀)
  const HARD = 25000;                                   // 그림 하나가 안 와도 25초 뒤에는 들어갈 수 있다(나머지는 들어가서 마저)
  function tick() {
    if (ready) return;
    const imgP = total ? settled / total : 0;
    const p = Math.round(100 * (0.25 * (arkDone ? 1 : 0) + 0.75 * imgP));
    pct = Math.max(pct, Math.min(arkDone ? 100 : 99, p));
    $('.tbar i').style.width = pct + '%'; $('.tpct').textContent = pct + '%'; lampAt(pct / 100);
    const quiet = performance.now() - lastStart > 500;
    if ((arkDone && settled >= total && quiet) || performance.now() - T0 > HARD) setReady();
  }
  const tickT = setInterval(tick, 150);
  function setReady() {
    if (ready) return; ready = true; clearInterval(tickT); clearInterval(liT); untrack();
    D.t.ready = Math.round(performance.now() - T0); D.total = total; D.settled = settled; D.hard = settled < total;
    const q = later.splice(0); setTimeout(() => q.forEach(f => { try { f(); } catch (e) { /* 미리 받기 실패는 화면을 멈추지 않는다 */ } }), 0);
    pct = 100; lampAt(1); if (!RM) $('.tlamp').classList.add('lit');
    $('.tprog').hidden = true;
    if (arkErr) $('.tline').textContent = '방주를 불러오지 못했습니다. 눌러서 다시 시도해 보세요.';
    const b = $('.tgo'); b.textContent = arkErr ? '다시 시도' : TX.start; b.hidden = false;
    setTimeout(() => { try { b.focus({ preventScroll: true }); } catch (e) { /* */ } }, 0);
    el.style.cursor = 'pointer';
  }

  // ── 5. 첫 탭: 소리를 열고 들어간다 ─────────────────────────────────────
  let resolveGate; const gate = new Promise(r => { resolveGate = r; });
  let amb = null;
  function openSound() {
    try {
      const s = new Audio('/static/audio/sfx_lantern_on.ogg'); s.volume = 0.45; const p = s.play(); if (p && p.catch) p.catch(() => {});
      amb = new Audio('/static/audio/amb_inside.ogg'); amb.loop = true; amb.volume = 0;
      const q = amb.play(); if (q && q.catch) q.catch(() => {});
      let v = 0; const f = setInterval(() => { v += 0.02; amb.volume = Math.min(0.22, v); if (v >= 0.22) clearInterval(f); }, 120);   // 방주 안 공기 소리를 천천히
      D.sound = true;
    } catch (e) { D.sound = false; }
  }
  function enter(e) {
    if (!ready) return;
    if (e && e.type === 'keydown' && !/^(Enter| |Spacebar)$/.test(e.key)) return;
    if (e) e.preventDefault();
    if (arkErr) { location.reload(); return; }
    openSound();
    el.classList.add('off'); D.t.enter = Math.round(performance.now() - T0);
    removeEventListener('keydown', enter, true);
    setTimeout(() => { alive = false; cancelAnimationFrame(raf); el.remove(); st.remove(); }, RM ? 0 : 750);
    resolveGate();
  }
  el.addEventListener('click', enter);
  addEventListener('keydown', enter, true);

  window.ARKTITLE = {
    gate,
    debug: () => Object.assign({ ready, arkDone, total, settled, pct, firstVisit, rm: RM, line: $('.tline') ? $('.tline').textContent : null,
                                 btn: $('.tgo') ? $('.tgo').textContent : null }, JSON.parse(JSON.stringify(D))),
    arkLoaded(s) { arkSt = s || null; arkDone = true; D.t.ark = Math.round(performance.now() - T0); lineOut(); tick(); },
    arkFailed(err) { arkErr = err || true; arkDone = true; D.t.ark = Math.round(performance.now() - T0); tick(); },
    ambience: () => amb,
    afterReady(f) { if (ready) f(); else later.push(f); },
  };
})();
