/* 질랜디아 — S32 안내 두 가지(base_core.js 다음에 불린다)
 *  1) 「다음 할 일」 한 줄: /api/ark.next_step {id, line_ko, target{kind, resident_id?, slot?}, hint_mode:"always"|"idle", idle_sec?}
 *     위 줄 바로 아래 한 줄(폰 가로 한 줄·말줄임). 누르면 대상(찍기·사람·방·≡·선반·홀·내보내기·한 상)을 부드럽게 빛내고 화살표.
 *     hint_mode "idle"(켠 날 4부터)이면 30초 동안 손을 안 댔을 때만 스며 나온다. 매 행동 뒤(찍기·건네기·자리·짓기) 새로 받는다.
 *  2) 첫 찍기 길잡이: /api/ark.tutorial {next_step_id, done}. 문장은 ui_moments.tutorial.<id>.text(시나리오).
 *     말풍선 하나 + 대상 빛(누를 단추는 가리지 않고 화살표로). 그 단계의 일을 하면(또는 말풍선을 누르면) POST /api/tutorial {uid, step} → 다음.
 *     「건너뛰기」 = step:"skip".
 *  필드가 없으면 아무것도 하지 않는다.
 */
(() => {
  'use strict';
  const K = window.ARKBASE && window.ARKBASE._k; if (!K) return;
  const $ = (s) => document.querySelector(s);
  const esc = K.esc, plain = K.plain;
  const RM = !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
  const D = window.ARKGUIDE = { log: [] };                 // ★ 검수용
  const T = (k, fb) => (K.ext.T ? K.ext.T(k, {}, '') : '') || fb;

  // ── 대상 찾기: 화면 사각형(뷰포트 px) ─────────────────────────────
  const cvRect = () => { const c = $('#cv'); return c ? c.getBoundingClientRect() : { left: 0, top: 0 }; };
  const elRect = (sel) => { const e = typeof sel === 'string' ? $(sel) : sel; if (!e || e.hidden || !e.offsetParent) return null; const r = e.getBoundingClientRect(); return r.width ? { x: r.left, y: r.top, w: r.width, h: r.height } : null; };
  const canvasRect = (b) => { if (!b) return null; const c = cvRect(); return { x: c.left + b.x, y: c.top + b.y, w: b.w, h: b.h }; };
  const slotOfT = (t) => { if (t.slot != null) return t.slot; if (t.room_id) { const r = ((K.ark || {}).rooms || []).find(x => x.id === t.room_id); return r ? r.slot : null; } return null; };
  function targetRect(t) {
    if (!t) return null;
    const A = window.ARKBASE;
    switch (t.kind) {
      case 'scan': return elRect('#scanbtn');
      case 'menu': return elRect('#menubtn');
      case 'expedition': return elRect('#sendbtn') || elRect('#menubtn');
      case 'table': return elRect('#tablebtn') || elRect('#menubtn');
      case 'room': { const sl = slotOfT(t); return sl != null ? canvasRect(A.slotBox(sl)) : null; }
      case 'hall': {                                       // 자리를 정할 사람이 있으면 그 사람(홀·문간 어디에 서 있든), 없으면 홀
        const h = t.resident_id && (A.peopleHits() || []).find(p => p.id === t.resident_id);
        return h ? canvasRect({ x: h.cx - 22, y: h.cy - 34, w: 44, h: 68 }) : canvasRect(A.hallBox && A.hallBox()); }
      case 'shelf': { const h = (A.shelfHits() || [])[0]; return h ? canvasRect(h) : (A.shelfRoomSlot ? canvasRect(A.slotBox(A.shelfRoomSlot())) : null); }
      case 'person': { const h = (A.peopleHits() || []).find(p => p.id === t.resident_id); return h ? canvasRect({ x: h.cx - 22, y: h.cy - 34, w: 44, h: 68 }) : null; }
      // 첫 찍기 길잡이 대상
      case 'scan_input': { const m = $('#manual'); const row = m && (m.closest('.manualrow, .mrow, .manual') || m.parentElement); return elRect(row) || elRect('#scanCam'); }   // 숫자 칸 줄(입력·읽기) — 창 전체를 빛내지 않는다
      case 'card': return elRect('#rcard');
      case 'subtype': return elRect('#subPick') || elRect('#picker');
      case 'where': return elRect('#giveStrip');
      default: return t.selector ? elRect(t.selector) : null;
    }
  }
  function focusCanvas(t) {                                // 캔버스 대상은 먼저 그쪽으로 카메라를 옮긴다
    if (!t) return;
    if (t.kind === 'room' && slotOfT(t) != null) K.flyToSlot(slotOfT(t));
    else if (t.kind === 'shelf' && window.ARKBASE.focusShelf) window.ARKBASE.focusShelf();
    else if (t.kind === 'person') { const h = (window.ARKBASE.peopleHits() || []).find(p => p.id === t.resident_id); if (h && h.from != null) K.flyToSlot(h.from); }
  }

  // ── 빛과 화살표(누를 것을 가리지 않는다 — 고리는 대상 바깥, 화살표는 옆) ─────────
  const glow = document.createElement('div'); glow.className = 'gdglow'; glow.hidden = true; glow.setAttribute('aria-hidden', 'true');
  const arrow = document.createElement('div'); arrow.className = 'gdarrow'; arrow.hidden = true; arrow.setAttribute('aria-hidden', 'true');
  document.body.appendChild(glow); document.body.appendChild(arrow);
  let lit = null, litUntil = 0, litRaf = 0;
  function light(t, ms) {
    lit = t; litUntil = performance.now() + (ms || 4000);
    cancelAnimationFrame(litRaf);
    const step = () => {
      const r = lit && performance.now() < litUntil ? targetRect(lit) : null;
      if (!r) { glow.hidden = true; arrow.hidden = true; if (lit && performance.now() < litUntil) { litRaf = requestAnimationFrame(step); } else lit = null; return; }
      const pad = 6;
      { const x0 = Math.max(4, r.x), y0 = Math.max(4, r.y), x1 = Math.min(innerWidth - 4, r.x + r.w), y1 = Math.min(innerHeight - 4, r.y + r.h); r.x = x0; r.y = y0; r.w = Math.max(10, x1 - x0); r.h = Math.max(10, y1 - y0); }   // 화면 안으로
      Object.assign(glow.style, { left: (r.x - pad) + 'px', top: (r.y - pad) + 'px', width: (r.w + pad * 2) + 'px', height: (r.h + pad * 2) + 'px' });
      glow.hidden = false;
      // 화살표: 대상 위쪽에 자리가 있으면 위에서 아래로, 아니면 왼쪽에서
      const up = r.y > 70;
      arrow.className = 'gdarrow ' + (up ? 'down' : 'right');
      Object.assign(arrow.style, up ? { left: (r.x + r.w / 2 - 12) + 'px', top: (r.y - pad - 30) + 'px' } : { left: (r.x - pad - 30) + 'px', top: (r.y + r.h / 2 - 12) + 'px' });
      arrow.hidden = false;
      D.lit = { kind: lit.kind, x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.w), h: Math.round(r.h) };
      litRaf = requestAnimationFrame(step);
    };
    litRaf = requestAnimationFrame(step);
  }
  function unlight() { lit = null; D.lit = null; glow.hidden = true; arrow.hidden = true; cancelAnimationFrame(litRaf); }

  // ══ 1. 「다음 할 일」 한 줄 ═══════════════════════════════════════
  const bar = document.createElement('button'); bar.id = 'nextstep'; bar.className = 'nextstep'; bar.hidden = true;
  bar.innerHTML = '<i aria-hidden="true"></i><span></span>';
  ($('#base') || document.body).appendChild(bar);
  let ns = null, lastInput = Date.now(), idleT = 0;
  function showStep(st) {
    const n = st && st.next_step;
    if (n !== undefined) ns = n && n.line_ko ? n : null;
    if (!ns || tut.active) { bar.hidden = true; bar.classList.remove('in'); return; }
    bar.querySelector('span').textContent = plain(ns.line_ko);
    bar.title = plain(ns.line_ko);
    const idle = ns.hint_mode === 'idle';
    if (!idle) { bar.hidden = false; bar.classList.add('in'); }
    else { const wait = (ns.idle_sec || 30) * 1000 - (Date.now() - lastInput); bar.hidden = true; bar.classList.remove('in'); clearTimeout(idleT); idleT = setTimeout(idleShow, Math.max(200, wait)); }
    D.step = { id: ns.id, mode: ns.hint_mode || 'always', line: ns.line_ko, shown: !bar.hidden };
  }
  function idleShow() {
    if (!ns || ns.hint_mode !== 'idle' || tut.active) return;
    const left = (ns.idle_sec || 30) * 1000 - (Date.now() - lastInput);
    if (left > 50) { idleT = setTimeout(idleShow, left); return; }
    bar.hidden = false; requestAnimationFrame(() => bar.classList.add('in')); D.log.push('idle show ' + ns.id); D.step.shown = true;
  }
  const touched = () => {
    lastInput = Date.now();
    if (ns && ns.hint_mode === 'idle' && !bar.hidden) { bar.classList.remove('in'); bar.hidden = true; D.step.shown = false; }
    if (ns && ns.hint_mode === 'idle') { clearTimeout(idleT); idleT = setTimeout(idleShow, (ns.idle_sec || 30) * 1000); }
  };
  ['pointerdown', 'keydown', 'wheel'].forEach(ev => addEventListener(ev, (e) => { if (e.target && e.target.closest && e.target.closest('#nextstep')) return; touched(); }, { capture: true, passive: true }));
  bar.addEventListener('click', (e) => {
    e.stopPropagation();
    if (!ns) return;
    focusCanvas(ns.target);
    setTimeout(() => light(ns.target, 4500), ns.target && ['room', 'shelf', 'person'].indexOf(ns.target.kind) >= 0 ? 700 : 0);
    D.log.push('step tap ' + ns.id + ' ' + ((ns.target || {}).kind || ''));
  });
  // 매 행동 뒤 새로: next_step 은 /api/ark 에 온다. 다른 응답의 state 에 없으면 잠시 뒤 /api/ark 를 한 번 다시 받는다
  let refreshT = 0, sawStep = false;
  K.onApply((st) => {
    if (st.next_step !== undefined) { sawStep = true; showStep(st); }
    else if (sawStep) { clearTimeout(refreshT); refreshT = setTimeout(() => { D.log.push('refresh'); window.ARKBASE.reload(); }, 900); }
    tutCheck(st);
  });

  // ══ 2. 첫 찍기 길잡이 ═════════════════════════════════════════════
  const TUT_DEF = {
    scan_button: { title: '찍기', text: '집에 있는 물건 하나를 들고, 여기 「찍기」를 눌러 보세요.', target: { kind: 'scan' } },
    scan_input: { title: '바코드', text: '줄무늬를 카메라에 비추거나, 아래 칸에 숫자를 적어 주세요.', target: { kind: 'scan_input' } },
    card: { title: '카드', text: '물건이 카드가 되었습니다. 이름과 귀한 정도가 적혀 있습니다.', target: { kind: 'card' }, tap: true },
    subtype: { title: '이게 뭐예요?', text: '이 물건이 정확히 무엇인지 골라 주세요. 그 이름으로 그림이 바뀝니다.', target: { kind: 'subtype' } },
    where: { title: '어디로', text: '누구에게 건넬지 골라 주세요. 반가워하실 분이 앞에 있습니다.', target: { kind: 'where' } },
    after_give: { title: '건넸습니다', text: '잘 하셨습니다. 내일 또 하나 찍어 오시면 이 방주가 조금씩 살아납니다.', target: null, tap: true },
  };
  // 시나리오 단계 이름(ui_moments.tutorial.<id>.lines[]) ↔ 화면 단계
  const ALIAS = { scan_window: 'scan_input', card_flip: 'card', subtype_pick: 'subtype', after_first_give: 'after_give' };
  Object.keys(ALIAS).forEach(k => { TUT_DEF[k] = TUT_DEF[ALIAS[k]]; });
  const tut = { active: false, id: null, sending: false, el: null, poll: 0, saw: {} };
  function tutText(id) {
    const d = TUT_DEF[id] || { text: '' };
    const rev = Object.keys(ALIAS).find(k => ALIAS[k] === id);
    const m = (K.ext.moment && (K.ext.moment('tutorial.' + id) || (rev && K.ext.moment('tutorial.' + rev)))) || null;
    const lines = m ? (Array.isArray(m) ? m : (Array.isArray(m.lines) ? m.lines : [m.text || (typeof m === 'string' ? m : '')])) : [d.text];
    const title = (m && typeof m === 'object' && !Array.isArray(m) && m.title) || d.title;
    return { title: plain(title || ''), lines: lines.filter(Boolean).map(plain) };
  }
  function tutCheck(st) {
    const tu = st && st.tutorial; if (tu === undefined) return;
    const id = tu && !tu.done ? tu.next_step_id : null;
    if (!id) { if (tut.active) tutEnd(); return; }
    if (tut.id === id && tut.active) return;
    tutShow(id);
  }
  function tutShow(id) {
    tut.active = true; tut.id = id; tut.saw = {}; bar.hidden = true;
    if (!tut.el) {
      tut.el = document.createElement('div'); tut.el.className = 'coach'; tut.el.setAttribute('role', 'note');
      document.body.appendChild(tut.el);
      tut.el.addEventListener('click', (e) => {
        if (e.target.closest('[data-skip]')) { tutSend('skip'); return; }
        if ((TUT_DEF[tut.id] || {}).tap || e.target.closest('[data-next]')) tutSend(tut.id);
      });
    }
    const tx = tutText(id), d = TUT_DEF[id] || {};
    tut.el.innerHTML = (tx.title ? '<b>' + esc(tx.title) + '</b>' : '') + tx.lines.map(l => '<p>' + esc(l) + '</p>').join('') +
      '<div class="cbtns">' + (d.tap ? '<button class="on" data-next="1">' + esc(T('tutorial.ok', '알겠습니다')) + '</button>' : '') +
      '<button class="skip" data-skip="1">' + esc(T('tutorial.skip', '건너뛰기')) + '</button></div>';
    tut.el.hidden = false;
    placeCoach();
    if (d.target) light(d.target, 600000); else unlight();
    clearInterval(tut.poll); tut.poll = setInterval(tutTick, 350);
    D.log.push('tut ' + id);
  }
  // 말풍선 자리: 대상 사각형과 겹치지 않는 쪽(위·아래·왼쪽), 대상이 없으면 가운데
  function placeCoach() {
    const el = tut.el; if (!el || el.hidden) return;
    const d = TUT_DEF[tut.id] || {}, r = d.target ? targetRect(d.target) : null;
    const W = innerWidth, H = innerHeight, w = Math.min(300, W - 24); el.style.width = w + 'px';
    const h = el.offsetHeight || 110;
    let x, y;
    if (!r) { x = (W - w) / 2; y = Math.max(12, (H - h) / 2); }
    else if (r.y - h - 40 > 8) { x = r.x + r.w / 2 - w / 2; y = r.y - h - 40; }                // 위(화살표 자리 비우고)
    else if (r.y + r.h + h + 16 < H) { x = r.x + r.w / 2 - w / 2; y = r.y + r.h + 16; }           // 아래
    else { x = r.x - w - 44; y = r.y + r.h / 2 - h / 2; if (x < 8) x = r.x + r.w + 16; }           // 옆
    x = Math.max(8, Math.min(W - w - 8, x)); y = Math.max(8, Math.min(H - h - 8, y));
    // 마지막 확인: 대상과 겹치면 대상 반대편 구석으로
    if (r && !(x + w < r.x || x > r.x + r.w || y + h < r.y || y > r.y + r.h)) { x = r.x > W / 2 ? 8 : W - w - 8; y = r.y > H / 2 ? 8 : H - h - 8; }
    el.style.left = x + 'px'; el.style.top = y + 'px';
    D.coach = { id: tut.id, x: Math.round(x), y: Math.round(y), w: Math.round(w), h: Math.round(h), overlap: !!(r && !(x + w < r.x || x > r.x + r.w || y + h < r.y || y > r.y + r.h)) };
  }
  addEventListener('resize', () => { if (tut.active) placeCoach(); });
  // 단계가 끝났나: 화면 상태로 본다(찍기 창이 열렸다 → 카드가 보인다 → 고르기가 끝났다 → 건넸다)
  function tutTick() {
    if (!tut.active || tut.sending) return;
    const id = tut.id, vis = (s) => !!elRect(s);
    placeCoach();
    const k = ALIAS[id] || id;
    if (k === 'scan_button' && !$('#scan').hidden) return tutSend(id);
    if (k === 'scan_input' && vis('#scanCard')) return tutSend(id);
    if (k === 'card') { tut.saw.t0 = tut.saw.t0 || Date.now(); if (Date.now() - tut.saw.t0 > 6000 && !$('#scan').hidden) return tutSend(id); }   // 말풍선을 안 눌러도 6초 뒤 다음
    if (k === 'subtype') { if (vis('#subPick')) tut.saw.pick = true; else if (tut.saw.pick || vis('#giveStrip')) return tutSend(id); }
    if (k === 'where') {
      if (vis('#giveStrip')) { tut.saw.strip = true; if (tut.el.hidden) { tut.el.hidden = false; placeCoach(); light(TUT_DEF[id].target, 600000); } }
      else if (tut.saw.strip) {
        // 버그 수정: 「선반에」를 골라 줄이 사라진 것은 건넨 것이 아니다 — 다음 「어디로」까지 기다린다(말풍선은 접는다)
        const last = ((window.ARKCORE || {}).log || []).slice().reverse().find(x => /^(give|keep|heir give|octwhere give|regift) /.test(x)) || '';
        if (/^keep /.test(last)) { tut.saw.strip = false; tut.el.hidden = true; unlight(); D.log.push('tut where kept'); return; }
        return tutSend(id);
      }
    }
    // 찍기 창을 닫아 버렸으면 다시 찍기 단추 쪽을 가리킨다(단계는 서버가 정한다 — 화면은 빛만 옮긴다)
    const d = TUT_DEF[id] || {};
    if (d.target && !targetRect(d.target) && ['scan_input', 'card', 'subtype', 'where'].indexOf(k) >= 0 && $('#scan').hidden) light({ kind: 'scan' }, 600000);
    else if (d.target && lit && lit.kind !== d.target.kind && targetRect(d.target)) light(d.target, 600000);
  }
  async function tutSend(step) {
    if (tut.sending) return; tut.sending = true;
    let r = null;
    try { r = await K.api('/api/tutorial', { step }); } catch (e) { r = null; D.log.push('tut err ' + (e.message || '')); }
    tut.sending = false;
    D.log.push('tut done ' + step);
    const tu = r && (r.tutorial || (r.state && r.state.tutorial));
    if (tu && !tu.done && tu.next_step_id) { if (K.ark) K.ark.tutorial = tu; tutShow(tu.next_step_id); }
    else { if (K.ark && tu) K.ark.tutorial = tu; tutEnd(); }
  }
  function tutEnd() {
    tut.active = false; tut.id = null; clearInterval(tut.poll);
    if (tut.el) tut.el.hidden = true; unlight();
    showStep({});
    setTimeout(() => { if (K.flushSay) K.flushSay(); }, 600);   // 길잡이 동안 미룬 방송을 이제
    D.log.push('tut end');
  }
  // ══ 3. S33 오늘의 목표 셋(관리·핵심·새것) ═══════════════════════════
  //  /api/ark.goals [{id, kind, text_key, done, progress:[cur,n]}] — 모든 응답 state 에도. 문장 ui_moments goal.<key>.title/.done
  //  끝낸 것: 체크 + 관리실 한 줄(goals_done_now[].line_ko → goal.<key>.done) + 그 줄이 한 번 반짝. 셋 다: 「내일 부탁이 또렷해집니다」
  //  폰 가로(높이 500 이하)는 「목표 1/3」 한 줄로 접고, 누르면 편다
  const gp = document.createElement('div'); gp.className = 'goals'; gp.hidden = true; gp.id = 'goals';
  ($('#base') || document.body).appendChild(gp);
  let goalsPrev = null, goalsOpen = null; const goalSaid = {};   // 서버 goals_done_now 가 여러 응답에 겹쳐 와도 한 번만
  // PM 결정: 목표 문장은 서버 응답(goals[].title_ko·done_ko, all_done_ko)에서. ui_moments.goal.* 는 서버 문장이 없을 때만
  const gText = (g, part) => { const sv = part === 'title' ? g.title_ko : g.done_ko; if (sv) return plain(sv);
    const k = String(g.text_key || g.id).replace(/^goal[.]/, ''); const m = K.ext.moment && K.ext.moment('goal.' + k + '.' + part);
    return plain((Array.isArray(m) ? m[0] : m) || ''); };
  function drawGoals(st) {
    const gs = st && st.goals; if (gs === undefined) return;
    if (!Array.isArray(gs) || !gs.length) { gp.hidden = true; return; }
    if (!gs.every(g => gText(g, 'title'))) { gp.hidden = true; D.goals = { waiting_text: true }; return; }   // 문장이 없으면 id 를 보이지 않는다
    const n = gs.filter(g => g.done).length, phone = innerHeight <= 500;
    if (goalsOpen === null) goalsOpen = !phone;
    const just = goalsPrev ? gs.filter(g => g.done && !(goalsPrev[g.id] || {}).done).map(g => g.id) : [];
    gp.innerHTML = '<button class="ghead" aria-expanded="' + goalsOpen + '"><span>' + esc(T('goal.panel_title', '오늘의 목표')) + ' ' + n + '/' + gs.length + '</span><b aria-hidden="true">' + (goalsOpen ? '▾' : '▸') + '</b></button>' +
      '<ul>' + gs.map(g => '<li class="' + (g.done ? 'done' : '') + (just.indexOf(g.id) >= 0 ? ' just' : '') + '" data-kind="' + esc(g.kind || '') + '"><i aria-hidden="true"></i><span>' + esc(gText(g, 'title')) + '</span>' +
        (!g.done && Array.isArray(g.progress) && g.progress[1] > 1 ? '<small>' + (g.progress[0] | 0) + '/' + g.progress[1] + '</small>' : '') + '</li>').join('') + '</ul>';
    gp.classList.toggle('fold', !goalsOpen); gp.classList.toggle('alldone', n === gs.length);
    gp.hidden = false;
    // 끝낸 것 방송(서버 goals_done_now 가 오면 그 문장, 아니면 goal.<key>.done)
    // 끝낸 것 방송: 서버 goals_done_now(서버가 한 번만 싣는다) — 문장이 없으면 goal.<key>.done
    const now = (st.goals_done_now || []);
    now.forEach(sv => { if (goalSaid[sv.id]) return; goalSaid[sv.id] = 1; const g = gs.find(x => x.id === sv.id) || { id: sv.id }; const ln = sv.line_ko || gText(g, 'done'); if (ln) setTimeout(() => K.say(plain(ln)), 1200);   /* 건네기 반응·장면 카드 판단이 먼저 서도록 */ D.log.push('goal done ' + sv.id); });
    if (now.some(sv => goalSaid[sv.id] === 1 && (goalSaid[sv.id] = 2)) && n === gs.length && !goalSaid._all && (goalSaid._all = 1)) setTimeout(() => { const m = K.ext.moment && K.ext.moment('goal.all_done');
      K.say(plain(st.all_done_ko || st.goals_all_done_ko || (Array.isArray(m) ? m[0] : m) || '관리실입니다. 오늘 할 일을 다 해 주셨습니다. 내일 부탁이 또렷해집니다.')); D.log.push('goal all done'); }, 1600);
    goalsPrev = Object.fromEntries(gs.map(g => [g.id, { done: !!g.done }]));
    D.goals = { n, total: gs.length, open: goalsOpen, just };
  }
  document.addEventListener('pointerdown', (e) => {
    if (innerHeight > 500 || !goalsOpen || gp.hidden) return;
    if (e.target.closest && e.target.closest('#goals')) return;
    goalsOpen = false; gp.classList.add('fold'); const ar = gp.querySelector('.ghead b'); if (ar) ar.textContent = '▸'; D.log.push('goals auto-fold');
  }, true);
  gp.addEventListener('click', (e) => { if (!e.target.closest('.ghead')) return; if (zoomFold) { zoomFold = false; zoomUserOpen = true; gp.classList.remove('fold'); return; } goalsOpen = !goalsOpen; drawGoals({ goals: Object.keys(goalsPrev || {}).length ? lastGoals : [] }); });
  let lastGoals = [];
  K.onApply((st) => { if (st.goals !== undefined) { lastGoals = st.goals || []; drawGoals(st); } });
  // 「다음 할 일」 줄 아래에 붙인다(줄이 숨으면 그 자리로)
  function placeGoals() {                               // 「다음 할 일」 줄 아래, 그 줄이 숨으면 얼굴 띠 아래
    const b = $('#nextstep'), f = $('#faces'); let top = innerHeight <= 500 ? 44 : 52;
    if (f && !f.hidden && f.style.visibility !== 'hidden') top = Math.max(top, f.getBoundingClientRect().bottom + 6);
    if (b && !b.hidden) top = Math.max(top, b.getBoundingClientRect().bottom + 6);
    gp.style.top = top + 'px';
  }
  setInterval(placeGoals, 500);
  // 가까이 볼 때(배율 1.1 이상) 펼친 목표 판이 방 이름표를 가린다 — 그동안만 한 줄로 접는다(누가 직접 펴면 그대로)
  let zoomFold = false, zoomUserOpen = false;
  setInterval(() => {
    if (gp.hidden || !goalsOpen) { if (zoomFold) { zoomFold = false; gp.classList.toggle('fold', !goalsOpen); } return; }
    const want = (K.z || 1) >= 1.1 && !zoomUserOpen;
    if ((K.z || 1) < 1.1) zoomUserOpen = false;
    if (want !== zoomFold || (want && !gp.classList.contains('fold'))) { zoomFold = want; gp.classList.toggle('fold', want || !goalsOpen); D.goalsZoomFold = want;
      const ar = gp.querySelector('.ghead b'); if (ar) ar.textContent = gp.classList.contains('fold') ? '▸' : '▾'; }
  }, 400);
  D.holding = () => tut.active && !!tut.el && !tut.el.hidden;
  D.state = () => ({ step: D.step || null, tut: { active: tut.active, id: tut.id }, coach: D.coach || null, lit: D.lit || null, barShown: !bar.hidden });
  D.light = (t) => light(t, 3000);
  if (K.ark) { showStep(K.ark); tutCheck(K.ark); if (K.ark.goals !== undefined) { lastGoals = K.ark.goals || []; drawGoals(K.ark); } }
})();
