/* 잔해 방주 — 핵심 루프 A 화면 층 (S19-B, 클라이언트만)
 *
 * 근거: docs/CORE_LOOP_A.md(찍은 물건이 이 사람들의 삶이 된다) · docs/UI_SIMPLE.md(큰 창은 세션에 둘까지, 나머지는 작은 방울) ·
 *       재미 패널(떠날 때 카드·오늘의 필요·매듭) · 서버 계약 docs/API_S19.md.
 * 하는 일: ① 카드가 뒤집힌 뒤 「어디로」 줄(제안 셋 + 선반) → 주기 → 그 사람/그 방의 반응
 *          ② 주민 작은 카드·패널 줄(오늘 바라는 것·좋아함·머리맡 물건·사슬 점·열린 기억)
 *          ③ 매듭 이야기 카드(세션에 한 번, 아침 패널 말고) + 고르기(ask)
 *          ④ 방 꾸밈 칸·꼬리표 배지·방문자(방 안·창밖)
 *          ⑤ 떠날 때 카드 + 위 줄 「다음에 켜시면」 한 줄
 * 필드 이름이 바뀌어도 화면이 깨지지 않게 읽는 곳(norm*)을 한데 모았다. 서버가 아직 안 보내는 것은 그리지 않는다.
 */
(() => {
  'use strict';
  const K = window.ARKBASE && window.ARKBASE._k;
  if (!K) return;
  const $ = (s) => document.querySelector(s);
  const esc = K.esc, plain = K.plain;
  const T = (k, v, fb) => (K.ext.T ? K.ext.T(k, v || {}, '') : '') || fb || '';
  const D = window.ARKCORE = { log: [] };                  // ★ 검수용 읽기 창
  // 서버 경로(API_S19 이 확정되면 여기만 고친다)
  const API = { give: '/api/give', ask: '/api/arc/ask', leaving: '/api/leaving', decorRemove: '/api/decor/remove' };   // docs/API_S19.md
  const has404 = {};                                      // 서버가 아직 그 경로를 안 열었으면(404) 이 세션에서는 다시 안 부른다
  async function call(path, body) {
    if (has404[path]) throw Object.assign(new Error('아직 준비되지 않았습니다'), { status: 404 });
    try { return await K.api(path, body); } catch (e) { if (e.status === 404) has404[path] = true; throw e; }
  }
  const reduced = () => !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
  const store = {
    get(k, d) { try { const v = localStorage.getItem('ark_' + K.uid + '_' + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem('ark_' + K.uid + '_' + k, JSON.stringify(v)); } catch (e) { /* 못 적어도 돈다 */ } },
  };

  // ══════════════════════════════════════════════════════════════
  //  0. 읽기 — 서버 필드를 한 모양으로
  // ══════════════════════════════════════════════════════════════
  const people = () => (K.ark && K.ark.residents_list) || [];
  const personById = (id) => people().find(p => p.id === id) || null;
  const roomAt = (slot) => ((K.ark && K.ark.rooms) || []).find(r => r.slot === slot) || null;
  const roomName = (slot) => { const r = roomAt(slot); return r ? ((K.catalog[r.id] || {}).name || r.id) : ''; };
  const txt = (x) => (x == null ? '' : typeof x === 'string' ? x : (x.ko || x.line || x.text || x.name || ''));
  const ICON_OF = { chain_beat: 'chain', memory: 'memory', need: 'need', like: 'like', decor: 'decor' };
  function normSuggest(r) {
    const w = r.where || {};
    const raw = w.suggest || r.suggest || [];
    return raw.map(s => {
      const tg = s.target || {};
      const rid = tg.resident_id || s.resident_id || null;
      const slot = tg.slot != null ? tg.slot : (s.slot != null ? s.slot : null);
      const p = rid ? personById(rid) : null;
      return { rid, slot: rid ? null : slot, p: p || (rid ? { id: rid, name: s.name, role: s.role } : null),
               name: s.name || (p && p.name) || (slot != null ? roomName(slot) : ''),
               reason: s.icon || ICON_OF[s.tier] || s.reason || 'other', tier: s.tier,
               hint: txt(s.reason_ko || s.hint_ko || ''), tag: s.tag_ko, target: s.target || (rid ? { resident_id: rid } : { slot }) };
    }).filter(s => s.rid || s.slot != null).slice(0, 3);
  }
  function coreOf(p) { const c = (K.ark && K.ark.core && K.ark.core.residents) || {}; return c[p.id] || p.tastes || {}; }
  function normTaste(p) {
    const t = coreOf(p);
    const need = (t.needs_today || [])[0] || t.need_today || null;
    const tw = t.twist || {};
    const likes = (t.likes || []).map(txt).concat(tw.like ? [txt(tw.like)] : []).filter(Boolean);
    const keep = t.keepsake || null;
    const arc = t.arc || null, nx = (arc && arc.next) || {};
    const mem = (t.memories_seen || t.memories || []).map(x => (typeof x === 'string' ? (MEMKO[x] || '') : txt(x))).filter(Boolean);
    return { need: need && { ko: txt(need), met: (t.given_need_today || false) }, given: t.given_today | 0, likes, dislike: tw.dislike ? txt(tw.dislike) : '',
             keep: keep && { ko: txt(keep) }, items: (t.items || []).length,
             arc: arc && { step: arc.step | 0, total: arc.steps || arc.total || 0, title: txt(arc.title), next: txt(nx.hint_ko || ''), open: !!nx.open, done: !!arc.done },
             memN: (t.memories_seen || []).length, mem,
             pimps: (p.personal_imprints || []).map(id => { const c = ((K.ark || {}).personal_imprints_catalog || {})[id] || {}; return c.name ? c.name : ''; }).filter(Boolean),
             ask: !!(arc && arc.next && arc.next.ask) };
  }
  const MEMKO = {};                                       // 기억 id → 한 줄(서버가 이름을 안 주면 개수만 보인다)
  // 얼굴: 생활형 도트 시트(셀 256, x4)의 idle 첫 칸에서 머리만 오린다(정수 배율 아님 — 작은 원형 초상은 픽셀화로 맞춘다)
  function face(p, size) {
    if (!p) return '<i class="face blank"></i>';
    size = size || 40;
    const sheet = '/static/art/chars/front/p2/' + encodeURIComponent(p.role || 'scout') + (p.body === 'b' ? '_b' : '') + '.png';
    const k = size / 104;
    return '<i class="face" style="width:' + size + 'px;height:' + size + 'px;background-image:url(' + sheet + ');background-size:' + (768 * k).toFixed(1) + 'px auto;background-position:-' + (76 * k).toFixed(1) + 'px -' + (28 * k).toFixed(1) + 'px" aria-hidden="true"></i>';
  }
  const WHY = { chain: '매듭', arc: '매듭', need: '오늘 필요', memory: '기억', like: '좋아함', decor: '꾸밈', other: '' };
  const why = (r) => '<em class="why why-' + esc(r) + '"><i aria-hidden="true"></i>' + esc(WHY[r] || '') + '</em>';

  // ══════════════════════════════════════════════════════════════
  //  1. 「어디로」 — 카드가 뒤집힌 뒤. 한 번 누르면 끝. 둘째 찍기부터는 작게
  // ══════════════════════════════════════════════════════════════
  let pending = null;
  function afterReveal(r) {
    const old = $('#giveStrip'); if (old) old.remove();
    if (D.mock && !r.suggest) D.mock.suggest(r);
    const sug = normSuggest(r);
    pending = sug.length ? r : null;
    if (!sug.length) return;
    const compact = (r.where && typeof r.where.compact === 'boolean') ? r.where.compact : (r.scans_today || 1) > 1;   // API_S19 §1 where.compact
    const el = document.createElement('div');
    el.id = 'giveStrip'; el.className = 'give' + (compact ? ' compact' : '');
    el.innerHTML = '<p class="gq">' + esc(T('give.ask', {}, '어디로 둘까요?')) + '</p><div class="gopts">' +
      sug.map((s, i) => '<button class="gopt' + (i === 0 ? ' top' : '') + '" data-i="' + i + '">' +
        (s.p ? face(s.p, compact ? 30 : 40) : '<i class="roomico" aria-hidden="true"></i>') +
        '<span class="gname"><b>' + esc(s.name) + '</b>' + why(s.reason) + '</span>' +
        (!compact && s.hint ? '<small>' + esc(plain(s.hint)) + '</small>' : '') + '</button>').join('') +
      '<button class="gopt keep" data-i="keep"><i class="shelfico" aria-hidden="true"></i><span class="gname"><b>' + esc(T('give.keep', {}, '선반')) + '</b></span></button></div>';
    const btn = $('#shelfBtn'); btn.parentNode.insertBefore(el, btn);
    btn.hidden = true;                                       // 선반은 줄 안의 「선반」이 대신한다(닫아도 선반으로 간다)
    el.addEventListener('click', (e) => {
      const b = e.target.closest('button.gopt'); if (!b || el.classList.contains('busy')) return;
      if (b.dataset.i === 'keep') { keepShelf(r); done(el); $('#shelfBtn').click(); return; }
      give(r, sug[+b.dataset.i], el);
    });
    D.log.push('strip ' + sug.length + (compact ? ' compact' : ''));
  }
  // 선반(= 닫기)도 서버에 자리를 정해 준다(API §0 「닫기(=선반)」). 실패해도 물건은 이미 선반에 있다
  function keepShelf(r) {
    const sid = (r.where || {}).scan_id || (r.card || {}).id;
    if (!sid || D.mock || r._placed) return; r._placed = true;
    call(API.give, { scan_id: sid, target: 'shelf' }).then(x => { if (x && x.state) K.apply(x.state); }).catch(() => {});
  }
  K.ext.coreKeep = () => { if (pending) { keepShelf(pending); const el = $('#giveStrip'); done(el); } };
  function done(el) { if (el) el.remove(); const b = $('#shelfBtn'); if (b) b.hidden = false; pending = null; }
  async function give(r, s, el) {
    el.classList.add('busy');
    const sid = (r.where || {}).scan_id || (r.card || {}).id;
    let res;
    if (D.mock) res = D.mock.give(s);
    else {
      try { res = await call(API.give, { scan_id: sid, target: s.target }); r._placed = true; }
      catch (e) { el.classList.remove('busy'); K.toast(e.message || '건네지 못했습니다'); return; }
    }
    if (res.state) K.apply(res.state);
    done(el); K.closeScan();
    react(res, s);
    D.log.push('give ' + (s.rid || 'room' + s.slot) + ' ' + (res.tier || res.kind || ''));
  }
  // 반응: 사람이면 그 사람 위에 물건 + 마음 + 한 줄, 방이면 방이 한 번 밝아지고 한 줄
  function react(res, s) {
    const rc = res.reaction || {}, ef = res.effects || {};
    const big = ef.memory || ef.arc;                         // 기억·매듭이면 대사가 그쪽 것
    const line = plain(txt((ef.memory && ef.memory.line) || rc.line || res.line || rc.announce || ''));
    const kind = ef.returned_to_shelf ? 'returned' : (res.tier === 'chain_beat' ? 'chain' : (res.tier || res.kind || s.reason || 'like'));
    if (rc.announce && rc.line) K.say(plain(rc.announce));    // 관리실 방송은 한 줄 뒤에
    if (ef.keepsake && ef.keepsake.line) setTimeout(() => K.say(plain(ef.keepsake.line)), 600);
    const rid = (res.who && res.who.id) || (res.target && res.target.resident_id) || s.rid;
    const slot = (ef.decor && ef.decor.slot != null) ? ef.decor.slot : ((res.target && res.target.slot != null) ? res.target.slot : s.slot);
    if (ef.decor && ef.decor.tag_added) res.decor_tag = ef.decor.tag_added.ko;
    if (!line && ef.decor) {                                // 방에 놓았는데 대사가 없으면 그 방이 무엇에 다가갔는지
      const tg = (ef.decor.tags || []).find(t => !t.on && t.have) || null;
      res._line = (ef.decor.tag_added ? ef.decor.tag_added.announce || '' : '') || ('꾸밈 ' + ef.decor.items + '/' + ef.decor.cap + (tg ? ' · ' + txt(tg) + ' ' + tg.have + '/' + tg.need : ''));
    }
    if (ef.arc && !ef.arc.deferred) res.beat = Object.assign({ resident_id: rid }, ef.arc);
    void big;
    const p = rid ? personById(rid) : null;
    const st = p ? stationOf(p) : slot;
    if (st != null && K.flyToSlot) K.flyToSlot(st);
    setTimeout(() => {
      let at = null;
      if (p) { const h = (window.ARKBASE.peopleHits() || []).find(x => x.id === p.id); if (h) at = { x: h.cx, y: h.cy - 46 }; }
      if (!at && slot != null) { const b = window.ARKBASE.slotBox(slot); if (b) at = { x: b.x + b.w / 2, y: b.y + b.h * 0.35 }; }
      if (!at) at = { x: K.view.w / 2, y: K.view.h / 2 };
      pop(at, kind, line || plain(res._line || ''), null);
      if (res.decor_tag || res.tag_formed) badgePop(slot, txt(res.decor_tag || res.tag_formed));
      if (res.beat) queueBeat(res.beat);
    }, st != null ? 700 : 80);
  }
  function stationOf(p) { const cb = K.cb || {}; const s = (cb.stations || {})[p.id]; return s === undefined ? null : s; }
  function pop(at, kind, line, propId) {
    const el = document.createElement('div');
    el.className = 'givepop gk-' + kind;
    const w = Math.min(260, K.view.w - 24);
    const x = Math.max(12 + w / 2, Math.min(K.view.w - 12 - w / 2, at.x));
    el.style.left = x + 'px'; el.style.top = Math.max(60, at.y) + 'px'; el.style.width = w + 'px';
    el.innerHTML = '<span class="heart" aria-hidden="true"></span>' + (line ? '<p>' + esc(line) + '</p>' : '');
    $('#base').appendChild(el);
    const off = () => { el.classList.add('off'); setTimeout(() => el.remove(), 500); };
    el.addEventListener('click', off); setTimeout(off, reduced() ? 4500 : 4200);
  }
  function badgePop(slot, tag) {
    if (!tag || slot == null) return;
    const b = window.ARKBASE.slotBox(slot); if (!b) return;
    const el = document.createElement('div'); el.className = 'tagpop';
    el.style.left = (b.x + b.w / 2) + 'px'; el.style.top = (b.y + 10) + 'px';
    el.innerHTML = '<b>' + esc(tag) + '</b>';
    $('#base').appendChild(el); setTimeout(() => el.remove(), 3800);
  }

  // ══════════════════════════════════════════════════════════════
  //  2. 주민 — 누르면 작은 카드(옮기기는 그대로), 패널 줄
  // ══════════════════════════════════════════════════════════════
  function arcDots(a) {
    if (!a || !a.total) return '';
    let h = '<span class="arcdots" title="' + esc(a.title || '사슬') + '">';
    for (let i = 0; i < a.total; i++) h += '<i class="' + (i < a.step ? 'on' : '') + '"></i>';
    return h + '</span>';
  }
  function tasteHTML(p, small) {
    const t = normTaste(p);
    if (!t.need && !t.likes.length && !t.keep && !t.arc && !t.memN) return '';
    return '<div class="taste' + (small ? ' sm' : '') + '">' +
      (t.need ? '<p class="tneed' + (t.need.met ? ' met' : '') + '"><i aria-hidden="true"></i><b>오늘</b> ' + esc(plain(t.need.ko)) + (t.need.met ? ' · 받음' : '') + '</p>' : '') +
      (t.likes.length ? '<p class="tlike"><i aria-hidden="true"></i><b>좋아함</b> ' + esc(t.likes.slice(0, 3).join(' · ')) + '</p>' : '') +
      (t.keep ? '<p class="tkeep"><i aria-hidden="true"></i><b>머리맡</b> ' + esc(t.keep.ko) + '</p>' : '') +
      (t.arc ? '<p class="tarc"><b>' + esc(t.arc.title || '이야기') + '</b> ' + arcDots(t.arc) + (t.arc.done ? ' <small>다 이뤘습니다</small>' : (t.arc.next ? '<br><small>' + (t.arc.open ? '' : '며칠 뒤 · ') + esc(plain(t.arc.next)) + '</small>' : '')) + '</p>' : '') +
      (t.pimps.length ? '<p class="tpimp"><b>각인</b> ' + esc(t.pimps.join(' · ')) + '</p>' : '') +
      (t.memN && !small ? '<p class="tmem"><b>열린 기억</b> ' + (t.mem.length ? esc(t.mem.slice(-1)[0]) + (t.memN > 1 ? ' 외 ' + (t.memN - 1) : '') : t.memN + '개') + '</p>' : '') +
      '</div>';
  }
  K.ext.tasteFor = (p) => tasteHTML(p, false);
  let ppop = null;
  K.ext.onPersonTap = (hit, cap) => {
    const p = personById(hit.id); if (!p) return false;
    const body = tasteHTML(p, true);
    if (!body) return false;                                // 서버가 아직 취향을 안 보내면 예전 토스트
    if (ppop) ppop.remove();
    ppop = document.createElement('div'); ppop.className = 'ppop';
    ppop.innerHTML = '<div class="phead">' + face(p, 36) + '<b>' + esc(p.name) + '</b><em>' + esc(p.role_ko || '') + '</em></div>' + body +
      (normTaste(p).ask ? '<div class="rowbtns"><button class="on" data-ask="' + esc(p.id) + '">' + esc(T('arc.ask_label', {}, '물어보실 게 있답니다')) + '</button></div>' : '') +
      '<p class="phint">' + esc((cap ? cap + ' ' : '') + '옮길 방을 누르시면 자리를 옮깁니다') + '</p>';
    $('#base').appendChild(ppop);
    const h = (window.ARKBASE.peopleHits() || []).find(x => x.id === p.id);
    const w = Math.min(250, K.view.w - 24), x = h ? h.cx : K.view.w / 2, y = h ? h.cy - 70 : 90;
    ppop.style.width = w + 'px';
    ppop.style.left = Math.max(12, Math.min(K.view.w - w - 12, x - w / 2)) + 'px';
    ppop.style.top = Math.max(52, y - ppop.offsetHeight) + 'px';
    const me = ppop; setTimeout(() => { if (ppop === me) { me.remove(); ppop = null; } }, 6000);
    ppop.addEventListener('click', (e) => { const b = e.target.closest('button[data-ask]'); if (b) { me.remove(); ppop = null; openAsk(p); } });
    D.log.push('person ' + p.id);
    return true;
  };
  document.addEventListener('pointerdown', (e) => { if (ppop && !ppop.contains(e.target)) { ppop.remove(); ppop = null; } }, true);

  // 아침 패널에 덧붙임: 오늘 바라는 것(얼굴 + 한 줄) · 찾아온 이 · 오늘의 일 한 줄
  function morningExtra(st) {
    const needs = st.needs_today || [];
    const beat = st.beat_today || null;
    let h = '';
    if (beat && beat.star) h += '<p class="dayline ov-beat">' + esc(plain(beat.star)) + '</p>';
    if (needs.length) h += '<h3>오늘 바라는 것</h3><div class="needrow">' + needs.slice(0, 6).map(n => { const p = personById(n.resident_id);
      return '<span class="needchip">' + face(p, 26) + '<b>' + esc((p && p.name) || n.name || '') + '</b> ' + esc(plain(txt(n.need))) + '</span>'; }).join('') + '</div>';
    return h;
  }
  const hasMorning = (st) => !!((st.needs_today && st.needs_today.length) || (st.beat_today && st.beat_today.new && st.beat_today.star));

  // ══════════════════════════════════════════════════════════════
  //  3. 매듭 이야기 카드 — 아침 패널 말고는 세션에 한 번. 작은 카드(큰 창 아님), 고르기(ask) 있으면 단추
  // ══════════════════════════════════════════════════════════════
  let beatShown = 0, beatQ = [];
  const beatSeen = {};
  function queueBeat(b) { if (!b) return; b.id = b.id || ((b.arc_id || '') + ':' + (b.step || '')); if (beatSeen[b.id] || beatQ.some(x => x.id === b.id)) return; beatSeen[b.id] = 1; beatQ.push(b); setTimeout(showBeat, 900); }
  function showBeat() {
    if ($('.beatcard') || !beatQ.length) return;
    if (beatShown >= 1) return;                            // 세션에 한 번(나머지는 아침 패널·다음 세션)
    if (!$('#scan').hidden || !$('#panel').hidden) { setTimeout(showBeat, 1500); return; }
    const b = beatQ.shift(); beatShown++;
    const p = personById(b.resident_id || b.who || b.rid);
    const ask = b.ask || null;
    b.title = b.title ? b.title + (b.step ? ' · ' + b.step + '/' + (b.steps || '') : '') : ''; b.broadcast = b.broadcast || b.announce; b.arc = b.arc || { step: b.step, total: b.steps };
    const el = document.createElement('div'); el.className = 'beatcard' + (b.size === 'big' ? ' big' : '');
    el.innerHTML = '<div class="phead">' + face(p, 40) + '<b>' + esc(txt(b.title) || (p ? p.name : '')) + '</b>' + arcDots(b.arc || (p && normTaste(p).arc)) + '</div>' +
      (b.broadcast ? '<p class="bcast">' + esc(plain(txt(b.broadcast))) + '</p>' : '') +
      (b.line ? '<p class="bline">「' + esc(plain(txt(b.line))) + '」</p>' : '') +
      (ask ? askHTML(ask, p) : '<div class="rowbtns"><button class="ok">' + esc(T('beat.ok', {}, '그렇군요')) + '</button></div>');
    $('#base').appendChild(el);
    const close = () => { el.classList.add('off'); setTimeout(() => el.remove(), 400); };
    if (ask) bindAsk(el, ask, Object.assign({ arc_id: b.arc_id, step: (ask.step || b.step) }, {}), close);
    else el.addEventListener('click', (e) => { if (e.target.closest('button.ok')) close(); });
    D.log.push('beat ' + (b.id || ''));
  }

  // ── 매듭이 묻는 것(ask) — 버튼 / 유물 고르기(place·give) / 두 사람 고르기(pick_residents). 안 고르면 default(타이머 없음)
  function relicChoices(ask) {
    const a = K.ark || {}, subs = ask.subtype == null ? null : [].concat(ask.subtype);
    const ok = (x) => (!ask.category || x.category === ask.category) && (!subs || subs.indexOf(x.subtype) >= 0 || !x.subtype);
    const sh = (a.shelf || []).map(x => ({ id: x.card_id || x.id, name: x.relic_name || x.name, category: x.category, subtype: x.subtype, polish: x.polish || 1, where: '선반' }));
    const st = (a.stored || []).map(x => ({ id: x.id, name: x.relic_name || x.name, category: x.category, subtype: x.subtype, polish: x.polish || 1, where: '창고 안쪽' }));
    return sh.concat(st).filter(x => x.id && ok(x)).sort((m, n) => n.polish - m.polish).slice(0, 8);
  }
  function askHTML(ask, p) {
    const kind = ask.kind || (ask.options ? 'choice' : '');
    let h = '<p class="bask">' + esc(plain(txt(ask.label || ask.ko))) + '</p>';
    if (kind === 'choice') {
      const opts = (ask.options || ask.choices || []).map(o => (typeof o === 'string' ? { id: o, ko: o } : o));
      h += '<div class="rowbtns">' + opts.map(o => '<button data-ans="' + esc(o.id) + '"' + (o.id === ask.default ? ' class="on"' : '') + '>' + esc(plain(txt(o))) + '</button>').join('') + '</div>';
    } else if (kind === 'place' || kind === 'give') {
      const rs = relicChoices(ask);
      h += rs.length ? '<div class="askrelics">' + rs.map((x, i) => '<button data-relic="' + esc(x.id) + '"' + (i === 0 && ask.default === 'most_polished' ? ' class="on"' : '') + '><b>' + esc(x.name || '') + '</b><small>' + esc(x.where) + '</small></button>').join('') + '</div>'
                     : '<p class="rvhow">지금 맞는 물건이 선반에 없습니다. 찍어 오시면 그때 다시 물어보겠습니다.</p>';
      h += '<div class="rowbtns"><button class="ok">나중에</button></div>';
    } else if (kind === 'pick_residents') {
      const n = ask.n || 2;
      h += '<div class="chips askpeople" data-n="' + n + '">' + people().map(q => '<button class="chip" data-who="' + esc(q.id) + '">' + face(q, 22) + ' ' + esc(q.name) + '</button>').join('') + '</div>' +
           '<div class="rowbtns"><button class="on" data-go="1" disabled>마주 앉히기</button><button class="ok">나중에</button></div>';
    } else h += '<div class="rowbtns"><button class="ok">그렇군요</button></div>';
    return h;
  }
  function bindAsk(el, ask, ref, close) {
    const pick = [];
    const send = async (body) => {
      if (D.mock) { close(); return; }
      try { const r = await call(API.ask, Object.assign({ arc_id: ref.arc_id, step: ref.step }, body)); if (r.state) K.apply(r.state);
        const ap = r.applied || {};
        if (ap.reaction && (ap.reaction.line || ap.reaction.announce)) K.say(plain(txt(ap.reaction.line || ap.reaction.announce)));
        if (r.after_ask_ko) K.say(plain(r.after_ask_ko));
        D.log.push('ask ' + ref.arc_id + ':' + ref.step + ' ok');
        close();
      } catch (err) { if (err.status !== 404) K.toast(err.message || '전하지 못했습니다'); el.querySelectorAll('button').forEach(b => { b.disabled = false; }); }
    };
    el.addEventListener('click', (e) => {
      const a = e.target.closest('button[data-ans]'), rl = e.target.closest('button[data-relic]'), w = e.target.closest('button[data-who]'), go = e.target.closest('button[data-go]');
      if (a) { a.disabled = true; send({ choice: a.dataset.ans }); return; }
      if (rl) { rl.disabled = true; send({ relic_id: rl.dataset.relic }); return; }
      if (w) { const n = +(el.querySelector('.askpeople').dataset.n || 2), i = pick.indexOf(w.dataset.who);
        if (i >= 0) pick.splice(i, 1); else { pick.push(w.dataset.who); if (pick.length > n) pick.shift(); }
        el.querySelectorAll('[data-who]').forEach(x => x.classList.toggle('on', pick.indexOf(x.dataset.who) >= 0));
        el.querySelector('[data-go]').disabled = pick.length !== n; return; }
      if (go) { go.disabled = true; send({ resident_ids: pick.slice() }); return; }
      if (e.target.closest('button.ok')) close();
    });
  }
  // 사람 카드에서 답하지 않은 ask 를 다시 연다(core.residents[rid].arc.next.ask)
  function openAsk(p) {
    const c = coreOf(p), arc = c.arc || {}, ask = arc.next && arc.next.ask; if (!ask) return;
    beatQ.unshift({ id: 'ask:' + arc.id + ':' + (ask.step || ''), resident_id: p.id, arc_id: arc.id, step: ask.step, steps: arc.steps, title: arc.title, ask });
    beatShown = 0; showBeat();
  }

  // ══════════════════════════════════════════════════════════════
  //  4. 꾸밈·방문자 — 캔버스에 작게(배경 그림은 그대로, 덧그림만)
  // ══════════════════════════════════════════════════════════════
  // 그림: 손님 도트(static/art/visitors/visitors_meta.json)·꼬리표 덧씌움(static/art/decor/decor_meta.json). 없으면 도형으로
  const ART = { vis: {}, dec: {}, decCell: [564, 317], floorY: 262, win: {} };
  const imgOf = {};
  const loadImg = (src) => { let o = imgOf[src]; if (!o) { o = imgOf[src] = { img: new Image(), ok: false }; o.img.onload = () => { o.ok = o.img.naturalWidth > 0; }; o.img.src = src; } return o; };
  fetch('/static/art/visitors/visitors_meta.json').then(r => (r.ok ? r.json() : null)).then(j => {
    (j && j.visitors || []).forEach(v => { ART.vis[v.id] = v; loadImg('/' + v.file.replace(/^\//, '')); });
  }).catch(() => {});
  fetch('/static/art/decor/decor_meta.json').then(r => (r.ok ? r.json() : null)).then(j => {
    if (!j) return; if (j.cell) ART.decCell = j.cell; if (j.clear_zones && j.clear_zones.floor_band_y) ART.floorY = j.clear_zones.floor_band_y;
    (j.tags || []).forEach(t => { ART.dec[t.id] = t; loadImg('/static/art/decor/' + t.file); });
    if (j.slots) { ART.slots = { list: j.slots, pos: j.slot_positions_in_cell || {} }; spotsCache = null; }
    const wc = (j.window_spot || {}).cells || {}; Object.keys(wc).forEach(k => { if (wc[k] && wc[k].visitor_world) ART.win[k] = wc[k].visitor_world; });
  }).catch(() => {});
  function decorOf(room) {
    const d = ((K.ark && K.ark.room_decor) || {})[String(room.slot)] || room.decor || {};
    const items = (d.items || []).filter(x => !x.boxed);
    const n = d.cap || d.slots || 0;
    const tags = (d.tags || []).filter(t => t.on !== false).map(t => ({ id: t.id || t, ko: txt(t) }));
    return { items, n, tags, raw: d };
  }
  K.ext.decorFor = (slot) => {                             // 방 카드 한 줄: 꾸밈 칸 n/m · 꼬리표 · 다가가는 꼬리표
    const r = roomAt(slot); if (!r) return '';
    const dc = decorOf(r); if (!dc.n) return '';
    const near = (dc.raw.tags || []).filter(t => !t.on && t.have).map(t => t.ko + ' ' + t.have + '/' + t.need);
    return '<p class="rcline decorline">꾸밈 ' + dc.items.length + '/' + dc.n + (dc.tags.length ? ' · <b>' + esc(dc.tags.map(t => t.ko).join(' · ')) + '</b>' : '') + (near.length ? ' · ' + esc(near[0]) : '') + '</p>' +
      (dc.items.length ? '<div class="decorlist">' + dc.items.map(it => '<button data-decrm="' + esc(it.id) + '" data-slot="' + slot + '" title="선반으로">' + esc(it.name || '') + ' ×</button>').join('') + '</div>' : '');
  };
  document.addEventListener('click', async (e) => {
    const b = e.target.closest('button[data-decrm]'); if (!b) return;
    e.stopPropagation(); b.disabled = true;
    try { const r = await call(API.decorRemove, { slot: +b.dataset.slot, item_id: b.dataset.decrm }); if (r.state) K.apply(r.state); K.toast(r.back_to === 'stored' ? '창고 안쪽에 넣어 두었습니다.' : '선반에 올려 두었습니다.'); K.openCard({ slot: +b.dataset.slot }); }
    catch (err) { K.toast(err.message || '옮기지 못했습니다'); }
  }, true);
  // 칸 순서: 벽 선반 → 받침대 → 둘째 선반 → 고리 둘(머리 위 벽·가운데 기둥만 — 사람 서는 자리는 비운다)
  let spotsCache = null;
  function slotSpots() {
    if (spotsCache) return spotsCache;
    const m = ART.slots; if (!m) return DEFAULT_SPOTS;
    const pos = m.pos || {}, by = {}; (m.list || []).forEach(x => { by[x.id] = x; loadImg('/static/art/decor/' + x.file); });
    const order = [['slot_shelf_bracket', 0], ['slot_stand', 0], ['slot_shelf_bracket', 1], ['slot_hook', 0], ['slot_hook', 1]];
    spotsCache = order.map(([id, i]) => { const d = by[id], xy = (pos[id] || [])[i]; if (!d || !xy) return null;
      return { file: d.file, x: xy[0], y: xy[1], w: d.size[0], h: d.size[1], ax: d.anchor[0], ay: d.anchor[1], hang: id === 'slot_hook' }; }).filter(Boolean);
    return spotsCache;
  }
  const DEFAULT_SPOTS = [{ file: '', x: 150, y: 60, w: 130, h: 56, ax: 65, ay: 10 }, { file: '', x: 240, y: 192, w: 84, h: 70, ax: 42, ay: 10 }, { file: '', x: 280, y: 160, w: 130, h: 56, ax: 65, ay: 10 }, { file: '', x: 100, y: 40, w: 40, h: 60, ax: 20, ay: 40, hang: true }];
  K.ext.drawRoomExtra = (room, slot, ix, iy, iw, ih, t, lit) => {
    const ctx = K.ctx, z = K.z, dc = decorOf(room);
    // 꼬리표가 붙은 방은 덧씌움 한 장(칸 564×317 에 1:1, 플레이트 위·사람 아래). 방이 달라 보이는 것이 보상이다
    dc.tags.forEach(tg => {
      const d = ART.dec[tg.id]; if (!d) return;
      const im = imgOf['/static/art/decor/' + d.file]; if (!im || !im.ok) return;
      ctx.save(); if (lit === false) ctx.globalAlpha = 0.55; ctx.drawImage(im.img, ix, iy, iw, ih); ctx.restore();
    });
    // 꾸밈 칸: 받침 소품(벽 선반·받침대·고리, decor_meta slots) 위에 놓인 유물. 칸 좌표 564×317 → 방 사각형
    if (dc.n || dc.items.length) {
      const kx = iw / ART.decCell[0], ky = ih / ART.decCell[1];
      const n = Math.max(dc.n, dc.items.length);
      slotSpots().slice(0, n).forEach((sp, i) => {
        const pim = imgOf['/static/art/decor/' + sp.file];
        const px = ix + sp.x * kx, py = iy + sp.y * ky, pw = sp.w * kx, ph = sp.h * ky;
        if (pim && pim.ok) { ctx.save(); ctx.imageSmoothingEnabled = false; ctx.drawImage(pim.img, px, py, pw, ph); ctx.restore(); }
        else if (z > 0.35) { ctx.strokeStyle = 'rgba(240,176,85,0.35)'; ctx.setLineDash([3, 3]); ctx.strokeRect(px, py, pw, ph); ctx.setLineDash([]); }
        const it = dc.items[i]; if (!it) return;
        const pi = K.propImg(it.prop_id || K.propForCategory2(it.category)); if (!pi || !(pi.ok1 || pi.ok4)) return;
        const im = pi.ok1 ? pi.x1 : pi.x4, w0 = pi.ok1 ? im.naturalWidth : im.naturalWidth / 4, h0 = pi.ok1 ? im.naturalHeight : im.naturalHeight / 4;
        const sc = Math.min(3 * kx * 1.0, (pw * 0.8) / Math.max(1, w0)), rw = w0 * sc, rh = h0 * sc;
        const ax = px + sp.ax * kx, ay = py + sp.ay * ky;
        const top = sp.hang ? ay : ay - rh;                  // 고리는 윗가운데를 매달고, 선반·받침은 바닥을 얹는다
        ctx.save(); ctx.imageSmoothingEnabled = false; ctx.drawImage(im, ax - rw / 2, top, rw, rh); ctx.restore();
      });
    }
    if (dc.tags.length && z > 0.22) {                       // 꼬리표 배지 — 방 오른쪽 위
      ctx.font = 'bold ' + Math.max(10, 13 * Math.min(1.2, z * 1.3)) + 'px "Noto Sans KR",sans-serif';
      let x = ix + iw - 8, y = iy + 8;
      dc.tags.slice(0, 2).forEach(tg => {
        const label = tg.ko || tg.id, w = ctx.measureText(label).width + 14, h = 20;
        ctx.fillStyle = 'rgba(232,201,138,0.95)'; ctx.fillRect(x - w, y, w, h);
        ctx.strokeStyle = '#5a4320'; ctx.lineWidth = 1.5; ctx.strokeRect(x - w, y, w, h);
        ctx.fillStyle = '#1a150e'; ctx.textBaseline = 'middle'; ctx.fillText(label, x - w + 7, y + h / 2 + 1); ctx.textBaseline = 'alphabetic';
        y += h + 4;
      });
    }
    // 방문자: 방 안(발을 바닥 줄에) · 창(몸 가운데를 방 위쪽 유리 자리에). 가끔 시그니처 동작
    const floor = iy + ih * (ART.floorY / ART.decCell[1]);
    visitors().filter(v => v.slot === slot).forEach((v, k) => {
      const meta = ART.vis[v.kind];
      const inside = meta ? !!meta.indoor : v.where === 'inside';
      const ws = !inside && ART.win[String(slot)];
      const x = inside ? ix + iw * (0.30 + 0.16 * k) : (ws ? K.sx(ws[0]) + k * 26 * z : ix + iw * (0.62 + 0.14 * (k % 2))), y = inside ? floor : (ws ? K.sy(ws[1]) : iy + ih * 0.30);
      if (!meta || !spriteVisitor(ctx, meta, x, y, z, t, k)) drawVisitor(ctx, v, x, inside ? floor : y, z, t);
    });
  };
  function visitors() { const a = K.ark || {}; return (a.visits || a.visitors || []).filter(v => v.kind !== 'guest_tilt' && v.kind !== 'newhuman_tilt' && v.kind !== 'residents')
      .map(v => Object.assign({}, v, { kind: v.visitor_id || v.kind, where: v.where || (v.kind === 'octopus' ? 'inside' : 'window') })); }
  function visitorsIn(slot) { return visitors().filter(v => v.slot === slot && v.where === 'inside'); }
  function spriteVisitor(ctx, m, x, y, z, t, k) {
    const im = imgOf['/' + m.file.replace(/^\//, '')]; if (!im || !im.ok) return false;
    const [w, h] = m.size, clips = m.clips || {}, names = Object.keys(clips);
    const sig = names.find(n => n !== 'idle'), cyc = 9000 + k * 1700;
    const useSig = sig && ((t + k * 3100) % cyc) < 2200;          // 9초쯤에 한 번 2초 남짓 시그니처
    const c = clips[useSig ? sig : 'idle'] || clips[names[0]];
    const f = Math.floor(t / 1000 * (c.fps || 2)) % (c.frames || 1);
    const sc = 3 * z >= 1 ? Math.max(1, Math.round(3 * z)) : 3 * z;   // 방 ×3 과 같은 배율(정수로 맞춘다)
    const [ax, ay] = m.anchor || [w / 2, h];
    ctx.save(); ctx.imageSmoothingEnabled = false;
    if (!m.indoor) ctx.globalAlpha = 0.92;
    ctx.drawImage(im.img, f * w, (c.row || 0) * h, w, h, Math.round(x - ax * sc), Math.round(y - ay * sc), w * sc, h * sc);
    ctx.restore();
    return true;
  }
  function drawVisitor(ctx, v, x, y, z, t) {
    const id = v.kind || v.id || '';
    const s = Math.max(6, 18 * z), bob = Math.sin(t / 600 + x) * 2 * z;
    ctx.save();
    if (/octopus/.test(id)) {
      ctx.fillStyle = '#d08a72'; ctx.beginPath(); ctx.ellipse(x, y - s * 0.7 + bob, s * 0.7, s * 0.6, 0, 0, 6.2832); ctx.fill();
      for (let i = -2; i <= 2; i++) { ctx.fillRect(x + i * s * 0.25 - 1, y - s * 0.3 + bob, Math.max(1.5, 2 * z), s * 0.45); }
    } else if (/crab/.test(id)) {
      ctx.fillStyle = '#c8784e'; ctx.beginPath(); ctx.ellipse(x, y - s * 0.3, s * 0.6, s * 0.35, 0, 0, 6.2832); ctx.fill();
    } else {
      ctx.fillStyle = 'rgba(200,236,232,0.85)'; ctx.beginPath(); ctx.arc(x, y - s * 0.5 + bob, s * 0.4, 0, 6.2832); ctx.fill();
    }
    ctx.restore();
  }
  // 창밖 방문자: 작은 물고기 떼·등불고기·정원사(은빛 떼) — 그 방 바깥벽 옆을 천천히 돈다
  K.ext.drawOutsideExtra = (t) => {
    const vs = visitors().filter(v => !ART.vis[v.kind] && /small_fish|gardener|school/.test(v.kind || ''));
    if (!vs.length) return;
    const ctx = K.ctx, z = K.z;
    vs.forEach((v, k) => {
      const slot = v.slot != null ? v.slot : v.room_slot;
      const b = slot != null ? window.ARKBASE.slotBox(slot) : null; if (!b) return;
      const silver = /gardener/.test(v.kind || v.id || ''), ws = ART.win[String(slot)];
      const cx = ws ? K.sx(ws[0]) : b.x + b.w + 60 * z, cy = ws ? K.sy(ws[1]) : b.y + b.h * 0.45, n = silver ? 14 : 7;
      for (let i = 0; i < n; i++) {
        const a = t / (silver ? 2600 : 1700) + i * (6.2832 / n) + k;
        const fx = cx + Math.cos(a) * 46 * z * (1 + (i % 3) * 0.18), fy = cy + Math.sin(a * 1.3) * 22 * z;
        ctx.fillStyle = silver ? 'rgba(220,230,240,0.75)' : (/lantern/.test(v.kind || v.id || '') && i < 2 ? '#ffe2a8' : 'rgba(143,216,210,0.8)');
        ctx.beginPath(); ctx.ellipse(fx, fy, 5 * z + 1, 2.2 * z + 0.6, Math.cos(a) > 0 ? 0.3 : -0.3, 0, 6.2832); ctx.fill();
      }
    });
  };

  // ══════════════════════════════════════════════════════════════
  //  5. 떠날 때 카드 + 위 줄 「다음에 켜시면」
  // ══════════════════════════════════════════════════════════════
  function nextLine(st) { const n = st.next_visit || null; return n && n.kind !== 'nothing' ? plain(txt(n.line || n.ko || '')) : ''; }
  function renderNext(st) {
    let el = $('#nextline');
    const l = nextLine(st);
    if (!l) { if (el) el.hidden = true; return; }
    if (!el) { el = document.createElement('button'); el.id = 'nextline'; el.className = 'nextline'; el.title = '다음에 켜시면'; $('#topbar').appendChild(el);
      el.addEventListener('click', () => leaveCard(true)); }
    el.hidden = false; el.innerHTML = '<i aria-hidden="true"></i><span>' + esc(l) + '</span>';
  }
  async function leaveCard(manual) {
    if ($('.leavecard')) return;
    const st = K.ark || {};
    let d = null;
    if (!D.mock) { try { d = await call(API.leaving + '?uid=' + encodeURIComponent(K.uid)); } catch (e) { d = null; } }
    const changed = ((d && (d.changed || d.lines)) || st.session_changes || []).map(txt).filter(Boolean).slice(0, 2);
    const nv = (d && d.next_visit) || st.next_visit || null;
    const nxt = (nv && txt(nv.line || nv)) || T('leave.nothing', {}, '다음에 켜시면 밤사이 일을 한꺼번에 알려 드리겠습니다. 편히 쉬십시오.');
    const el = document.createElement('div'); el.className = 'leavecard';
    el.innerHTML = '<div class="leave-in">' +
      (changed.length ? '<p class="sub">' + esc((d && d.title) || T('leave.changed_title', {}, '이번에 바뀐 것')) + '</p>' + changed.map(c => '<p class="dayline">' + esc(plain(c)) + '</p>').join('') : '') +
      '<p class="sub">' + esc((nv && nv.title) || '다음에 켜시면') + '</p><p class="lnext">' + esc(plain(nxt)) + '</p>' +
      '<div class="rowbtns"><button class="ok">' + esc((d && d.close_label) || '잠깐 쉬기') + '</button></div></div>';
    document.body.appendChild(el);
    el.addEventListener('click', (e) => { if (e.target.closest('button.ok') || e.target === el) el.remove(); });
    D.log.push('leave ' + (manual ? 'menu' : 'auto'));
  }
  // ≡ 메뉴 「오늘은 여기까지」
  (() => {
    const mb = $('#menu .mbtns'); if (!mb) return;
    const b = document.createElement('button'); b.className = 'sw'; b.id = 'leavebtn'; b.textContent = '오늘은 여기까지';
    b.addEventListener('click', () => { K.closeMenu(); leaveCard(true); });
    mb.appendChild(b);
  })();
  // 잔치(API_S19 §8, 비트 10일째·넘치는 식량의 출구): ≡ → 「잔치」 → 마주 앉힐 두 분 고르기. 판정·대가는 서버(식량 30·물 20, 하루 한 번)
  function openFeast() {
    K.closeMenu();
    const ps = people(), pick = [];
    const body = K.panel('<h2>잔치</h2><p class="sub">식량 30 · 물 20 · 하루 한 번. 마주 앉으실 두 분을 골라 주세요.</p><div class="chips">' +
      ps.map(p => '<button class="chip" data-fp="' + esc(p.id) + '">' + esc(p.name) + '</button>').join('') + '</div><div class="rowbtns"><button class="on" id="feastGo" disabled>상 차리기</button></div>');
    body.addEventListener('click', async (e) => {
      const c = e.target.closest('[data-fp]');
      if (c) { const i = pick.indexOf(c.dataset.fp); if (i >= 0) pick.splice(i, 1); else { pick.push(c.dataset.fp); if (pick.length > 2) pick.shift(); }
        body.querySelectorAll('[data-fp]').forEach(x => x.classList.toggle('on', pick.indexOf(x.dataset.fp) >= 0)); body.querySelector('#feastGo').disabled = pick.length !== 2; return; }
      if (e.target.id === 'feastGo') {
        e.target.disabled = true;
        try { const r = await call('/api/feast', { pair: pick.slice() }); if (r.state) K.apply(r.state); K.closePanel(); K.say(plain(txt(r.ko || r.line || '상을 차렸습니다. 다들 한자리에 앉으셨습니다.'))); }
        catch (err) { K.toast(err.message || '잔치를 열지 못했습니다'); e.target.disabled = false; }
      }
    });
  }
  (() => {
    const mb = $('#menu .mbtns'); if (!mb) return;
    const b = document.createElement('button'); b.className = 'sw'; b.id = 'feastbtn'; b.textContent = '잔치';
    b.addEventListener('click', openFeast); mb.appendChild(b);
  })();
  // 탭을 떠나면 카드를 깔아 둔다(돌아왔을 때 첫 화면이 「다음에 켜시면」) — 세션당 한 번, 3분 넘게 머문 세션만
  const t0 = Date.now();
  document.addEventListener('visibilitychange', () => { if (document.hidden && Date.now() - t0 > 180000 && !D.leftOnce) { D.leftOnce = true; leaveCard(false); } });

  // ══════════════════════════════════════════════════════════════
  //  연결
  // ══════════════════════════════════════════════════════════════
  K.ext.core = { afterReveal, morningExtra, hasMorning, queueBeat, leaveCard };
  K.onApply((st) => {
    if (D.mock) D.mock.decorate(st);                        // ★ 시험대: 서버 모양을 먼저 입힌다
    renderNext(st);
    (st.arc_events || []).filter(Boolean).forEach(e => queueBeat(Object.assign({ id: (e.arc_id || '') + ':' + (e.step || '') }, e)));
  });
  // ★ 개발 전용 ?coretest=1 (RELIC_DEV 서버에서만): 서버 S19 가 오기 전에 화면 틀을 본다. 서버를 부르지 않는다
  if (new URLSearchParams(location.search).get('coretest') === '1') {
    fetch('/api/ark?uid=' + encodeURIComponent(K.uid) + '&debug_act=99').then(r => {
      if (r.status !== 400) return;
      const ps = () => people();
      const NEED = ['따뜻한 것', '종이 한 장', '반짝이는 것'], LIKE = [['국물', '마른 잎'], ['전선', '작은 등'], ['지도', '연필']];
      D.mock = {                                        // API_S19 모양 그대로(§1~§7)
        decorate(st) {
          const rs = st.residents_list || [], R = {};
          rs.forEach((p, i) => { R[p.id] = { needs_today: [{ ko: NEED[i % 3] }], likes: LIKE[i % 3].map(k => ({ ko: k })), keepsake: i === 0 ? { name: '찌그러진 국자' } : null,
            memories_seen: i === 0 ? ['m1'] : [], given_today: 0,
            arc: { title: ['앉아서 먹는 저녁', '창 쪽으로 돌아눕기', '등불 하나'][i % 3], step: 1 + (i % 2), steps: 4, next: { open: i !== 2, hint_ko: '식품 서로 다른 것 2개' }, done: false } }; });
          st.core = { residents: R };
          const r0 = (st.rooms || [])[0];
          if (r0) {
            st.room_decor = { [r0.slot]: { cap: 3, items: [{ id: 'dec-1', name: '면 상자', category: 'food' }, { id: 'dec-2', name: '말린 잎', category: 'drink' }], tags: [{ id: 'warm_kitchen', ko: '따뜻한 부엌', have: 2, need: 2, on: true }] } };
            st.visits = [{ kind: 'visitor', visitor_id: 'blanket_crab', slot: r0.slot }, { kind: 'visitor', visitor_id: 'lantern_fish_pair', slot: r0.slot, where: 'window' }, { kind: 'octopus', slot: r0.slot, line: '문어가 그 방에서 한참 놀다 갔습니다.' }];
          }
          st.next_visit = { kind: 'arc_beat_ready', title: '다음에 켜시면', line: ((rs[0] || {}).name || '') + ' 님이 뭔가 하실 말씀이 있는 눈치입니다. 다음에 켜시면 들어 보세요.' };
          st.needs_today = rs.slice(0, 3).map((p, i) => ({ resident_id: p.id, name: p.name, need: { ko: NEED[i % 3] } }));
          st.beat_today = { star: '관리실에서 알려 드립니다. 오늘은 문간 쪽이 조금 시끄러울 것 같습니다.', new: true, big: false };
          return st;
        },
        suggest(r) { const p = ps(); const slot = ((K.ark.rooms || [])[0] || {}).slot;
          r.where = { scan_id: (r.card || {}).id || 'mock', compact: (D.mock._n = (D.mock._n || 0) + 1) > 1, suggest: [
            p[0] && { kind: 'resident', target: { resident_id: p[0].id }, name: p[0].name, role: p[0].role, tier: 'need', icon: 'need', reason_ko: '오늘 필요하신 물건' },
            p[1] && { kind: 'resident', target: { resident_id: p[1].id }, name: p[1].name, role: p[1].role, tier: 'chain_beat', icon: 'chain', reason_ko: '이야기가 움직입니다' },
            slot != null && { kind: 'room', target: { slot }, name: '식량창고', tier: 'decor', icon: 'decor', reason_ko: '따뜻한 부엌까지 하나' }].filter(Boolean), shelf: { label: '선반에' } };
          return r; },
        give(s) { return s.rid ? { ok: true, tier: s.tier, who: { id: s.rid }, target: { resident_id: s.rid },
            reaction: { announce: '「면 상자」, 드렸습니다.', line: s.tier === 'chain_beat' ? '그건… 앉을 자리에 두면 좋겠네요.' : '이거면 오늘은 됐어요.' },
            effects: { morale: 2, arc: s.tier === 'chain_beat' ? { arc_id: 'arc_cook_seat', title: '앉아서 먹는 저녁', step: 2, steps: 4, size: 'small', announce: '관리실에서 알려 드립니다. 식량창고 앞 의자에 누가 앉아 있었다는 소문입니다.', line: '앉아 보니까, 생각보다 낮네요.',
              ask: { label: '상에 무엇을 올릴까요?', options: [{ id: 'a', ko: '면 상자', reply: '면 상자를 올렸습니다. 김이 납니다.' }, { id: 'b', ko: '말린 잎', reply: '말린 잎을 올렸습니다. 냄새가 납니다.' }] } } : null } }
          : { ok: true, tier: 'decor', target: { slot: s.slot }, reaction: { line: '식량창고에서 냄새가 나기 시작했습니다.' },
              effects: { decor: { slot: s.slot, items: 2, cap: 2, tag_added: { id: 'warm_kitchen', ko: '따뜻한 부엌' } } } }; },
      };
      if (K.ark) { D.mock.decorate(K.ark); K.apply(K.ark); }
      const bar = document.createElement('div'); bar.className = 'cardtest coretest';
      bar.innerHTML = '★ <button data-k="scan">어디로</button><button data-k="beat">매듭</button><button data-k="leave">떠날 때</button><button data-k="morning">아침</button>';
      document.body.appendChild(bar);
      bar.addEventListener('click', (e) => { const k = (e.target.closest('button') || {}).dataset; if (!k) return;
        if (k.k === 'scan' && K.ext.cardTestReveal) { K.ext.cardTestReveal('rare', false, false, false); setTimeout(() => {}, 0); }
        if (k.k === 'beat') { beatShown = 0; const g = D.mock.give({ rid: ps()[1].id, tier: 'chain_beat' }); queueBeat(Object.assign({ resident_id: ps()[1].id, id: 'mock' + Date.now() }, g.effects.arc)); }
        if (k.k === 'leave') leaveCard(true);
        if (k.k === 'morning' && window.ARKCOLLECT && ARKCOLLECT.morningTest) ARKCOLLECT.morningTest();
      });
      D.mockOn = true;
    }).catch(() => {});
  }
  D.state = () => ({ pending: !!pending, beatShown, beatQ: beatQ.length });
  D.leaveCard = leaveCard; D.react = react; D.pop = pop;
})();
