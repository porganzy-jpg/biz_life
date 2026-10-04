/* 잔해 방주 — 유물 카드 층 (S16-B, 클라이언트만)
 *
 * 근거: 사용자 승인 S16-B 지시(찍기 = 카드 개봉, 희귀도가 보인다) · docs/UI_SIMPLE.md(작고 경쾌하게) ·
 *       static/art/cards/cards_meta.json(S16-A 배경 에셋 — 경로·자리·물들임 색은 전부 이 파일에서 읽는다).
 * 하는 일: ① 카드 앞면 한 장(틀·그림 창·갈래 무늬·이름·설명·박·바다 무늬)을 그린다 — 찍기 카드·선반 카드·도감 카드가 같은 것을 쓴다
 *          ② 찍기 개봉 연출: 뒷면으로 날아옴 → 희귀도만큼 차오름 → 뒤집힘. 눌러서 건너뛰기. 다시 찍기(닦기)는 뒤집지 않고 빛만 지나간다
 *          ③ 선반·도감에서 누르면 그 유물 카드를 작게 띄운다
 * 움직임은 transform·opacity 만 쓴다(60fps). prefers-reduced-motion 이면 뒤집지 않고 바로 앞면.
 * 희귀도 이름(흔함·쓸만함·귀함·진귀함·전설)은 서버가 보내지 않는다 — ROOMS_AND_ITEMS §1 정본을 base.js 와 같이 쓴다.
 * 카드 번호(No.)는 서버에 통번호가 없어 비워 둔다(지어내지 않는다).
 */
(() => {
  'use strict';
  const K = window.ARKBASE && window.ARKBASE._k;
  if (!K) return;
  const $ = (s) => document.querySelector(s);
  const esc = K.esc;
  const DIR = '/static/art/cards/';
  const ORDER = ['common', 'uncommon', 'rare', 'epic', 'legendary'];
  const RAR_KO = K.RAR_KO || { common: '흔함', uncommon: '쓸만함', rare: '귀함', epic: '진귀함', legendary: '전설' };
  const CAT_KO = { food: '식품', drink: '음료', medical: '의약·화학', electronics: '전자', stationery: '문구',
                   book: '도서', apparel: '의류', tobacco: '담배·주류', unknown: '정체불명' };
  const reduced = () => !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const rarOf = (r) => (ORDER.indexOf(r) >= 0 ? r : 'common');
  const D = window.ARKCARDS = { log: [], meta: null };        // ★ 검수용 읽기 창

  // ══════════════════════════════════════════════════════════════
  //  0. 메타 — 파일이 없으면 CSS 대체 그림으로 돈다(경로를 코드에 박지 않는다)
  // ══════════════════════════════════════════════════════════════
  // 자리(카드 px, 400×560 설계). 메타가 오면 메타 값이 이긴다
  let L = { W: 400, H: 560,
    art: { x: 36, y: 70, w: 328, h: 264, shelf_y: 291 },
    number: { x: 48, y: 22, w: 270, h: 38 }, cat: { x: 326, y: 24, w: 34, h: 34 },
    name: { x: 48, y: 344, w: 304, h: 48 }, info: { x: 50, y: 408, w: 300, h: 96 } };
  let TINT = { common: '#C8A878', uncommon: '#F0C070', rare: '#FFD27A', epic: '#7FE0D8', legendary: '#F4EEFF' };
  const pct = (r) => 'left:' + (100 * r.x / L.W).toFixed(3) + '%;top:' + (100 * r.y / L.H).toFixed(3) + '%;width:' +
    (100 * r.w / L.W).toFixed(3) + '%;height:' + (100 * r.h / L.H).toFixed(3) + '%';
  function applyMeta(j) {
    if (!j || !j.rarities) return;
    D.meta = j;
    const c = j.card || {}, t = j.text || {}, a = j.art_window || {};
    L = { W: c.w || L.W, H: c.h || L.H,
      art: Object.assign({}, L.art, a), number: t.number || L.number, cat: t.category_slot || L.cat,
      name: t.name || L.name, info: t.info || L.info };
    const f = j.files || {}, root = document.documentElement.style, pre = [];
    const url = (p) => { pre.push(DIR + p); return 'url("' + DIR + p + '")'; };
    if (f.card_back) root.setProperty('--rk-back', url(f.card_back));
    if (f.art_bg) root.setProperty('--rk-artbg', url(f.art_bg));
    if (f.charge_glow) root.setProperty('--rk-glow', url(typeof f.charge_glow === 'string' ? f.charge_glow : f.charge_glow.file));
    if (f.foil && f.foil.sea) root.setProperty('--rk-foil-sea', url(f.foil.sea));
    ORDER.forEach(k => {
      const r = j.rarities[k]; if (!r) return;
      if (r.frame) root.setProperty('--rk-frame-' + k, url(r.frame));
      if (r.foil) root.setProperty('--rk-foil-' + k, url(r.foil));
      if (r.charge_tint) TINT[k] = r.charge_tint;
    });
    pre.forEach(src => { const im = new Image(); im.src = src; });      // 첫 개봉에 빈 틀이 보이지 않게
    document.documentElement.classList.add('rk-art');
    D.log.push('meta ok ' + pre.length);
  }
  fetch(DIR + 'cards_meta.json').then(r => (r.ok ? r.json() : null)).then(applyMeta).catch(() => { D.log.push('meta none'); });

  // 갈래 무늬(봉인 상자 뚜껑과 같은 그림 — base.js drawSealedBox 의 무늬를 작은 캔버스에)
  function glyph(cv, cat) {
    const ctx = cv.getContext('2d'), w = cv.width, cx = w / 2, cy = w / 2, r = w * 0.26;
    ctx.clearRect(0, 0, w, w);
    ctx.strokeStyle = '#e6d7b0'; ctx.lineWidth = Math.max(1.5, w / 14); ctx.lineCap = 'round';
    ctx.beginPath();
    switch (cat) {
      case 'food': for (let k = -1; k <= 1; k++) { ctx.moveTo(cx + k * r * 0.7, cy + r); ctx.lineTo(cx + k * r * 0.7, cy - r); } break;
      case 'drink': ctx.arc(cx, cy + r * 0.2, r * 0.6, 0, Math.PI); ctx.moveTo(cx - r * 0.6, cy + r * 0.2); ctx.lineTo(cx, cy - r); ctx.lineTo(cx + r * 0.6, cy + r * 0.2); break;
      case 'medical': ctx.moveTo(cx - r, cy - r); ctx.lineTo(cx + r, cy + r); ctx.moveTo(cx + r, cy - r); ctx.lineTo(cx - r, cy + r); break;
      case 'electronics': ctx.moveTo(cx - r * 0.3, cy - r); ctx.lineTo(cx + r * 0.2, cy); ctx.lineTo(cx - r * 0.2, cy); ctx.lineTo(cx + r * 0.3, cy + r); break;
      case 'stationery': ctx.moveTo(cx - r, cy + r); ctx.lineTo(cx + r, cy - r); ctx.moveTo(cx, cy); ctx.lineTo(cx + r * 0.5, cy + r * 0.3); break;
      case 'book': for (let k = 0; k < 3; k++) { ctx.moveTo(cx - r, cy - r * 0.6 + k * r * 0.6); ctx.lineTo(cx + r, cy - r * 0.6 + k * r * 0.6); } break;
      case 'apparel': ctx.arc(cx, cy, r * 0.8, 0, 6.2832); ctx.moveTo(cx + r * 0.4, cy); ctx.arc(cx, cy, r * 0.4, 0, 6.2832); break;
      case 'tobacco': for (let k = -1; k <= 1; k++) { ctx.moveTo(cx + k * r * 0.6, cy + r); ctx.quadraticCurveTo(cx + k * r * 0.6 + r * 0.4, cy, cx + k * r * 0.6, cy - r); } break;
      default: ctx.arc(cx, cy, r * 0.8, 0, 6.2832);
    }
    ctx.stroke();
  }

  // ══════════════════════════════════════════════════════════════
  //  1. 카드 앞면 한 장. o = {rarity, sea, name, category, flavor, prop_id, lines[]}
  //     그리는 순서(메타 draw_order): 그림 창 바탕 → 유물 그림 → 틀 → 박 → 글자
  // ══════════════════════════════════════════════════════════════
  function face(o) {
    const r = rarOf(o.rarity), sp = (K.propSpec && o.prop_id) ? K.propSpec(o.prop_id) : null;
    const a = L.art, sh = Math.max(0, (a.y + a.h - (a.shelf_y || a.y + a.h)) / a.h * 100);
    const foil = ['rare', 'epic', 'legendary'].indexOf(r) >= 0;
    const rarLine = (CAT_KO[o.category] || o.category || '') + ' · ' + (RAR_KO[r] || r) + (o.sea ? ' · 바다 무늬' : '');
    const pips = ORDER.indexOf(r) + 1;
    return '<div class="rk ' + r + (o.sea ? ' sea' : '') + '" role="img" aria-label="' + esc((o.name || '') + ', ' + (RAR_KO[r] || r) + (o.sea ? ', 바다 무늬' : '')) + '">' +
      '<div class="rk-win" style="' + pct(a) + '">' +
        (sp ? '<img class="rk-prop" alt="" data-w="' + sp.w + '" data-h="' + sp.h + '" style="bottom:' + sh.toFixed(2) + '%" src="/static/art/props/' + esc(o.prop_id) + '.png">' : '') +
      '</div>' +
      '<div class="rk-frame"><span class="rk-pips" aria-hidden="true">' + '●'.repeat(pips) + '</span></div>' +
      (foil ? '<div class="rk-foil" aria-hidden="true"><i></i><b></b></div>' : '') +
      (o.sea ? '<div class="rk-sea" aria-hidden="true"><i></i><b></b></div>' : '') +
      '<div class="rk-shine" aria-hidden="true"><i></i></div>' +
      '<div class="rk-num" style="' + pct(L.number) + '"></div>' +            // 통번호 없음 — 비워 둔다
      '<canvas class="rk-cat" width="68" height="68" data-cat="' + esc(o.category || '') + '" style="' + pct(L.cat) + '" aria-hidden="true"></canvas>' +
      '<div class="rk-name" style="' + pct(L.name) + '"><span>' + esc(o.name || '이름 없는 것') + '</span></div>' +
      '<div class="rk-info" style="' + pct(L.info) + '"><p class="rk-rar">' + esc(rarLine) + '</p>' +
        (o.flavor ? '<p class="rk-desc">' + esc(o.flavor) + '</p>' : '') +
        (o.lines || []).map(x => '<p class="rk-desc">' + esc(x) + '</p>').join('') + '</div>' +
      '<div class="rk-stamp" hidden></div>' +
    '</div>';
  }
  // 그림은 정수 배율·최근접 보간. 화면 px 기준으로 정수가 되게 실제 카드 폭에서 다시 잰다(offsetWidth 는 transform 을 무시)
  function settle(root) {
    root.querySelectorAll('canvas.rk-cat').forEach(cv => glyph(cv, cv.dataset.cat));
    root.querySelectorAll('.rk').forEach(rk => {
      const cw = rk.offsetWidth; if (!cw) return;
      const img = rk.querySelector('.rk-prop'); if (!img) return;
      const w = +img.dataset.w || 34, h = +img.dataset.h || 30;
      const k = Math.max(1, Math.floor(Math.min(280 / w, 200 / h) * cw / L.W));
      img.style.width = (w * k) + 'px'; img.style.height = (h * k) + 'px';
    });
  }

  // ══════════════════════════════════════════════════════════════
  //  2. 반짝임 — 손가락/마우스 위치나 기울기가 있으면 그쪽으로, 없으면 천천히 저절로
  // ══════════════════════════════════════════════════════════════
  let tiltEl = null, tiltRaf = 0, tiltXY = null;
  function tiltApply() {
    tiltRaf = 0; if (!tiltEl || !tiltXY) return;
    const [x, y] = tiltXY;                                  // -1..1
    const tl = tiltEl.querySelector('.rc-tilt') || tiltEl;
    tl.style.transform = 'rotateX(' + (-y * 7).toFixed(2) + 'deg) rotateY(' + (x * 9).toFixed(2) + 'deg)';
    tiltEl.querySelectorAll('.rk').forEach(rk => {
      rk.classList.add('manual');
      rk.querySelectorAll('.rk-foil i, .rk-sea i').forEach(i => { i.style.transform = 'translate3d(' + (x * -22).toFixed(1) + '%,' + (y * -14).toFixed(1) + '%,0)'; });
    });
  }
  function tiltTo(x, y) { tiltXY = [Math.max(-1, Math.min(1, x)), Math.max(-1, Math.min(1, y))]; if (!tiltRaf) tiltRaf = requestAnimationFrame(tiltApply); }
  function tiltReset(el) {
    const tl = el && (el.querySelector('.rc-tilt') || el); if (tl) tl.style.transform = '';
    if (el) el.querySelectorAll('.rk').forEach(rk => { rk.classList.remove('manual'); rk.querySelectorAll('.rk-foil i, .rk-sea i').forEach(i => { i.style.transform = ''; }); });
    tiltXY = null;
  }
  function bindTilt(el) {
    if (!el || el._tilt) return; el._tilt = true;
    el.addEventListener('pointermove', (e) => {
      if (reduced() || el.classList.contains('revealing')) return;
      tiltEl = el; const b = el.getBoundingClientRect();
      tiltTo(((e.clientX - b.left) / b.width) * 2 - 1, ((e.clientY - b.top) / b.height) * 2 - 1);
    });
    el.addEventListener('pointerleave', () => { if (tiltEl === el) { tiltReset(el); tiltEl = null; } });
  }
  window.addEventListener('deviceorientation', (e) => {     // 안드로이드 등 권한 없이 오는 곳만. iOS 권한 창은 띄우지 않는다
    if (e.gamma == null || reduced()) return;
    const el = !$('#scan').hidden ? $('#rcard') : (peekEl && !peekEl.hidden ? peekEl.querySelector('.pk-card') : null);
    if (!el || el.classList.contains('revealing')) return;
    tiltEl = el; tiltTo(e.gamma / 30, (e.beta - 40) / 30);
  });

  // ══════════════════════════════════════════════════════════════
  //  3. 찍기 개봉 — 뒷면으로 날아옴 → (희귀도만큼) 차오름 → 뒤집힘. 눌러서 건너뛰기
  //     흔함 ≈0.8 s · 쓸만함 ≈1.0 · 귀함 ≈1.25 · 진귀함 ≈1.5 · 전설 ≈2.0(상한 2.2)
  // ══════════════════════════════════════════════════════════════
  const PLAN = {
    common:    { fly: 260, charge: 130, glow: 0,    shake: 0,   rays: 0,    flash: 0, flip: 400 },
    uncommon:  { fly: 260, charge: 320, glow: 0.7,  shake: 0,   rays: 0,    flash: 0, flip: 420 },
    rare:      { fly: 260, charge: 560, glow: 1,    shake: 280, rays: 0,    flash: 0, flip: 440 },
    epic:      { fly: 260, charge: 800, glow: 1,    shake: 320, rays: 0.45, flash: 0, flip: 460 },
    legendary: { fly: 260, charge: 1220, glow: 1,   shake: 360, rays: 1,    flash: 1, flip: 520 },
  };
  let run = null;                                           // 지금 도는 개봉 {anims, timers, finish}
  function anim(el, kf, opt) { if (!el || !el.animate) return null; const a = el.animate(kf, opt); run && run.anims.push(a); return a; }
  function later(ms, f) { const t = setTimeout(f, ms); run && run.timers.push(t); }
  function stop() {
    if (!run) return;
    run.timers.forEach(clearTimeout); run.anims.forEach(a => { try { a.cancel(); } catch (e) { /* 이미 끝남 */ } });
    const r = run; run = null; return r;
  }
  // opts: {rarity, again(닦기), stamp(닦기 도장 글), onFlip, onDone}
  function reveal(opts) {
    stop();
    const card = $('#rcard'), inn = card.querySelector('.rc-in'), tl = card.querySelector('.rc-tilt');
    const glowEl = card.querySelector('.rc-charge'), raysEl = card.querySelector('.rc-rays'), flashEl = $('#rcFlash');
    const r = rarOf(opts.rarity), P = PLAN[r];
    card.style.setProperty('--rk-tint', TINT[r] || '#f0b055');
    card.classList.remove('flip'); tiltReset(card);
    settle(card);
    bindTilt(card);
    const stamp = card.querySelector('.rc-front .rk-stamp');
    const done = (how) => {
      card.classList.remove('revealing'); card.classList.add('flip');
      [glowEl, raysEl, flashEl].forEach(e => e && (e.style.opacity = ''));
      if (opts.again && stamp) { stamp.hidden = false; stamp.textContent = opts.stamp || ''; }
      D.log.push('reveal ' + r + (opts.again ? ' polish' : '') + ' ' + how);
      opts.onDone && opts.onDone(how);
    };
    run = { anims: [], timers: [], finish: null };
    if (reduced()) { run = null; if (opts.onFlip) opts.onFlip(); done('reduced'); return; }

    if (opts.again) {                                       // 닦기 — 뒤집지 않고 이미 있는 카드에 빛이 한 번 지나간다
      card.classList.add('flip', 'revealing');
      anim(card, [{ transform: 'scale(.9)', opacity: 0.4 }, { transform: 'scale(1)', opacity: 1 }], { duration: 180, easing: 'cubic-bezier(.2,.8,.3,1)' });
      const sh = card.querySelector('.rc-front .rk-shine i');
      anim(sh, [{ transform: 'translate3d(-120%,0,0) skewX(-18deg)' }, { transform: 'translate3d(130%,0,0) skewX(-18deg)' }],
           { duration: 520, delay: 120, easing: 'ease-in-out' });
      later(330, () => {
        if (stamp) { stamp.hidden = false; stamp.textContent = opts.stamp || ''; anim(stamp, [{ transform: 'rotate(-8deg) scale(1.6)', opacity: 0 }, { transform: 'rotate(-8deg) scale(1)', opacity: 1 }], { duration: 220, easing: 'cubic-bezier(.3,1.4,.5,1)' }); }
      });
      later(660, () => { stop(); done('end'); });
      run.finish = () => { stop(); done('skip'); };
      return;
    }

    card.classList.add('revealing');
    // ① 날아옴(뒷면)
    anim(card, [{ transform: 'translate3d(0,46vh,0) rotate(-9deg) scale(.72)', opacity: 0 },
                { transform: 'translate3d(0,-2%,0) rotate(1deg) scale(1.02)', opacity: 1, offset: 0.8 },
                { transform: 'none', opacity: 1 }], { duration: P.fly, easing: 'cubic-bezier(.2,.75,.3,1)' });
    const t1 = P.fly, t2 = t1 + P.charge;
    // ② 차오름
    if (P.glow) anim(glowEl, [{ opacity: 0, transform: 'scale(.55)' }, { opacity: P.glow, transform: 'scale(' + (1 + 0.3 * P.glow).toFixed(2) + ')' }],
                     { duration: P.charge, delay: t1, easing: 'linear', fill: 'forwards' });
    if (P.rays) anim(raysEl, [{ opacity: 0, transform: 'scale(.6) rotate(0deg)' }, { opacity: P.rays, transform: 'scale(1.15) rotate(40deg)' }],
                     { duration: P.charge, delay: t1, easing: 'ease-in', fill: 'forwards' });
    if (P.shake) anim(tl, [{ transform: 'translate3d(0,0,0)' }, { transform: 'translate3d(-3px,0,0) rotate(-1.2deg)' }, { transform: 'translate3d(3px,-1px,0) rotate(1.2deg)' },
                           { transform: 'translate3d(-2px,1px,0) rotate(-.8deg)' }, { transform: 'translate3d(2px,0,0) rotate(.8deg)' }, { transform: 'translate3d(0,0,0)' }],
                      { duration: P.shake / 2, delay: t2 - P.shake, iterations: 2 });
    // ③ 뒤집힘 (+ 전설은 등불색 번쩍)
    later(t2, () => {
      if (opts.onFlip) opts.onFlip();
      if (P.glow) anim(glowEl, [{ opacity: P.glow, transform: 'scale(' + (1 + 0.3 * P.glow).toFixed(2) + ')' }, { opacity: 0, transform: 'scale(1.5)' }], { duration: P.flip, easing: 'ease-out', fill: 'forwards' });
      if (P.rays) anim(raysEl, [{ opacity: P.rays, transform: 'scale(1.15) rotate(40deg)' }, { opacity: 0, transform: 'scale(1.6) rotate(70deg)' }], { duration: P.flip + 200, easing: 'ease-out', fill: 'forwards' });
      if (P.flash) {
        anim(flashEl, [{ opacity: 0 }, { opacity: 0.85, offset: 0.25 }, { opacity: 0 }], { duration: 420, easing: 'ease-out' });
        K.play && K.play('sfx_lantern_on.ogg', 0.5);
      }
      anim(inn, [{ transform: 'rotateY(0deg)' }, { transform: 'rotateY(90deg) scale(1.07)', offset: 0.5 }, { transform: 'rotateY(180deg)' }],
           { duration: P.flip, easing: 'cubic-bezier(.35,.1,.25,1)' });
    });
    later(t2 + P.flip, () => { stop(); done('end'); });
    run.finish = () => { const had = stop(); if (had && opts.onFlip && !had.flipped) opts.onFlip(); done('skip'); };
    run.flipped = false;
    later(t2 + 1, () => { if (run) run.flipped = true; });
  }
  function skip() { if (run && run.finish) { const f = run.finish; f(); return true; } return false; }

  // ══════════════════════════════════════════════════════════════
  //  4. 선반·도감에서 누른 유물 — 작은 카드(누르면 닫힘)
  // ══════════════════════════════════════════════════════════════
  let peekEl = null;
  function peek(o, line, act) {
    if (!peekEl) {
      peekEl = document.createElement('div'); peekEl.className = 'relpeek'; peekEl.hidden = true;
      peekEl.addEventListener('click', (e) => {
        const b = e.target.closest('button[data-act]');
        if (b && peekEl._act) { const f = peekEl._act; closePeek(); f(); return; }
        closePeek();
      });
      ($('#app') || document.body).appendChild(peekEl);
    }
    peekEl._act = act ? act.fn : null;
    peekEl.innerHTML = '<div class="pk-card"><div class="rc-tilt">' + face(o) + '</div></div>' +
      (line ? '<p class="pk-line">' + esc(line) + '</p>' : '') +
      (act ? '<button data-act="1">' + esc(act.label) + '</button>' : '') +
      '<p class="pk-hint">아무 데나 누르면 닫힙니다</p>';
    peekEl.hidden = false;
    const c = peekEl.querySelector('.pk-card');
    settle(c); bindTilt(c);
    if (!reduced() && c.animate) c.animate([{ transform: 'translate3d(0,24px,0) scale(.92)', opacity: 0 }, { transform: 'none', opacity: 1 }], { duration: 200, easing: 'cubic-bezier(.2,.8,.3,1)' });
    D.log.push('peek ' + rarOf(o.rarity) + (o.sea ? ' sea' : ''));
  }
  function closePeek() { if (peekEl) { peekEl.hidden = true; peekEl.innerHTML = ''; } }
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closePeek(); });

  K.ext.cards = { face, settle, reveal, skip, stop, peek, closePeek, RAR_KO, CAT_KO, running: () => !!run };
  D.reveal = reveal; D.peek = peek; D.running = () => !!run;

  // ══════════════════════════════════════════════════════════════
  //  ★ 5. 개발 전용 시험대 ?cardtest=1 — 서버가 RELIC_DEV 일 때만 열린다(아니면 아무것도 안 보인다)
  //     확인 방법: /api/ark?debug_act=99 가 개발 서버면 400(없는 막), 배포면 404. 상태를 바꾸지 않는다
  // ══════════════════════════════════════════════════════════════
  const qs = new URLSearchParams(location.search);
  if (qs.get('cardtest') === '1') {
    fetch('/api/ark?uid=' + encodeURIComponent(K.uid) + '&debug_act=99').then(r => {
      if (r.status !== 400) return;                         // 개발 서버가 아니다 — 시험대 없음
      const bar = document.createElement('div'); bar.className = 'cardtest';
      bar.innerHTML = '★ ' + ORDER.map(k => '<button data-r="' + k + '">' + RAR_KO[k] + '</button>').join('') +
        '<button data-r="rare" data-sea="1">귀함+바다</button><button data-r="epic" data-again="1">닦기</button><button data-box="1">상자</button>';
      document.body.appendChild(bar);
      bar.addEventListener('click', (e) => {
        const b = e.target.closest('button'); if (!b || !K.ext.cardTestReveal) return;
        K.ext.cardTestReveal(b.dataset.r || 'common', !!b.dataset.sea, !!b.dataset.again, !!b.dataset.box);
      });
      D.cardtest = true;
    }).catch(() => {});
  }
})();
