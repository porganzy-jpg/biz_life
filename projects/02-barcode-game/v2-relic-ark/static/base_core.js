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
  const API = { give: '/api/give', ask: '/api/arc/ask', leaving: '/api/leaving', decorRemove: '/api/decor/remove', subtype: '/api/scan/subtype', table: '/api/table', prefs: '/api/prefs' };   // docs/API_S19.md
  // S25 첫 주 해금 달력(/api/ark.unlocked.features). 서버가 그 정보를 안 주면(옛 서버) 다 열린 것으로 본다
  const unlocked = (f) => { const u = (K.ark || {}).unlocked; return !u || !Array.isArray(u.features) || u.features.indexOf(f) >= 0; };
  K.ext.unlocked = unlocked;
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
  const ICON_OF = { chain_beat: 'chain', memory: 'memory', need: 'need', like: 'like', decor: 'decor', warm: 'warm' };
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
               reason: s.known === false ? 'sign' : (s.icon || ICON_OF[s.tier] || s.reason || 'other'), tier: s.tier, known: s.known !== false,
               hint: txt(s.reason_ko || s.hint_ko || ''), sign: s.known === false ? txt(s.hint_ko || '') : '',
               tag: s.tag_ko, target: s.target || (rid ? { resident_id: rid } : { slot }), srv: { role: s.role || null, name: s.name || null } };
    }).filter(s => s.rid || s.slot != null).slice(0, 3);
  }
  function coreOf(p) { const c = (K.ark && K.ark.core && K.ark.core.residents) || {}; return c[p.id] || p.tastes || {}; }
  function normTaste(p) {
    const t = coreOf(p);
    const need = (t.needs_today || [])[0] || t.need_today || null;
    const tw = t.twist || {};
    const likes = (tw.like ? [txt(tw.like)] : []).concat((t.likes || []).map(txt)).filter(Boolean);   // 그 사람만의 좋아함을 맨 앞에(셋까지만 보여서 잘리던 것)
    const keep = t.keepsake || null;
    const arc = t.arc || null, nx = (arc && arc.next) || {};
    const mem = (t.memories_seen || t.memories || []).map(x => (typeof x === 'string' ? (MEMKO[x] || '') : txt(x))).filter(Boolean);
    const nrow = ((K.ark && K.ark.needs_today) || []).find(x => x.resident_id === p.id);
    return { need: need && { ko: txt(need), met: !!(t.given_need_today || (nrow && nrow.met)) }, given: t.given_today | 0, likes, dislike: tw.dislike ? txt(tw.dislike) : '',
             keep: keep && { ko: txt(keep) }, items: (t.items || []).length,
             arc: arc && { step: arc.step | 0, total: arc.steps || arc.total || 0, title: txt(arc.title), next: txt(nx.hint_ko || ''), open: !!nx.open, done: !!arc.done },
             memN: (t.memories_seen || []).length, mem,
             heir: (coreOf(p) || {}).heirloom || null,
             pimps: (p.personal_imprints || []).map(id => { const c = ((K.ark || {}).personal_imprints_catalog || {})[id] || {}; return c.name ? c.name : ''; }).filter(Boolean),
             ask: !!(arc && arc.next && arc.next.ask) };
  }
  const MEMKO = {};                                       // 기억 id → 한 줄(서버가 이름을 안 주면 개수만 보인다)
  // 얼굴: 생활형 도트 시트(셀 256, x4)의 idle 첫 칸에서 머리만 오린다(정수 배율 아님 — 작은 원형 초상은 픽셀화로 맞춘다)
  function face(p, size) {
    if (!p) return '<i class="face blank"></i>';
    size = size || 40;
    const sheet = '/static/art/chars/front/p2/indoor/' + encodeURIComponent(p.role || 'scout') + (p.body === 'b' ? '_b' : '') + '.png';
    const k = size / 104;
    return '<i class="face" data-role="' + esc(p.role || '') + '" style="width:' + size + 'px;height:' + size + 'px;background-image:url(' + sheet + ');background-size:' + (768 * k).toFixed(1) + 'px auto;background-position:-' + (76 * k).toFixed(1) + 'px -' + (28 * k).toFixed(1) + 'px" aria-hidden="true"></i>';
  }
  const WHY = { chain: '매듭', arc: '매듭', need: '오늘 필요', memory: '기억', like: '좋아함', decor: '꾸밈', warm: '반가움', other: '' };   // S21: warm(0.9V) = 반가움
  const why = (r) => '<em class="why why-' + esc(r) + '"><i aria-hidden="true"></i>' + esc(WHY[r] || '') + '</em>';

  // ══════════════════════════════════════════════════════════════
  //  1. 「어디로」 — 카드가 뒤집힌 뒤. 한 번 누르면 끝. 둘째 찍기부터는 작게
  // ══════════════════════════════════════════════════════════════
  let pending = null;
  // S23: 3일째부터(labels:false) 라벨 대신 기색 — 모르는 칸은 얼굴 + 기색 한 줄(접어도 보인다), 아는 칸은 라벨. 순서는 서버(가장 오래 못 받은 사람부터), 첫자리 강조 없음
  function stripHTML(sug, compact, keepLabel, labels) {
    const signMode = labels === false;
    return '<p class="gq">' + esc(T('give.ask', {}, '어디로 둘까요?')) + '</p><div class="gopts' + (signMode ? ' signs' : '') + '">' +
      sug.map((s, i) => '<button class="gopt' + (i === 0 && !signMode ? ' top' : '') + (s.sign ? ' sign' : '') + '" data-i="' + i + '"' + (s.rid ? ' data-rid="' + esc(s.rid) + '" data-srole="' + esc(s.srv.role || '') + '"' : '') + '>' +
        (s.p ? face(s.p, (compact || innerHeight <= 500) ? 28 : 40) : '<i class="roomico" aria-hidden="true"></i>') +
        '<span class="gname"><b>' + esc(s.name) + '</b>' + (s.sign ? '' : why(s.reason)) + '</span>' +
        (s.sign ? '<small class="signline">' + esc(plain(s.sign)) + '</small>' : (!compact && s.hint ? '<small>' + esc(plain(s.hint)) + '</small>' : '')) + '</button>').join('') +
      '<button class="gopt keep" data-i="keep"><i class="shelfico" aria-hidden="true"></i><span class="gname"><b>' + esc(keepLabel) + '</b></span></button></div>';
  }
  // S22 ① 「이게 뭐예요?」 — where.subtype_pick.needed 면 「어디로」 앞에 하위 종류 단추(4~6). 다른 방주의 이름(suggest)은 미리 골라 둔다.
  //  고르면 POST /api/scan/subtype → 응답 card 로 카드를 다시 그리고 where 로 「어디로」를 다시 그린다. 안 골라도 「어디로」는 쓸 수 있다
  function subtypePick(r, sp) {
    const old = $('#subPick'); if (old) old.remove();
    const el = document.createElement('div'); el.id = 'subPick'; el.className = 'subpick';
    const sg = sp.suggest && sp.suggest.id;
    if (!sp.needed) el.classList.add('later');
    el.innerHTML = (!sp.needed ? '<button class="sublater">' + esc(T('subtype.later_label', {}, '나중에 이름 붙이기')) + '</button>' : '') +
      '<p class="gq">' + esc(plain(sp.ask_ko || '이게 뭐예요?')) + '</p>' +
      (sg ? '<p class="subsug">' + esc(plain(sp.suggest_ko || ('다른 방주에서는 「' + sp.suggest.ko + '」(이)라고 부릅니다.'))) + '</p>' : '') +
      '<div class="subopts">' + (sp.options || []).slice(0, 6).map(o => '<button data-sub="' + esc(o.id) + '"' + (o.id === sg ? ' class="on"' : '') + '>' + esc(o.ko) + '</button>').join('') + '</div>';
    const strip = $('#giveStrip'), btn = $('#shelfBtn');
    (strip || btn).parentNode.insertBefore(el, strip || btn);
    el.addEventListener('click', async (e) => {
      if (e.target.closest('.sublater')) { el.classList.toggle('open'); return; }
      const b = e.target.closest('button[data-sub]'); if (!b || el.classList.contains('busy')) return;
      el.classList.add('busy');
      const sid = (r.where || {}).scan_id || (r.card || {}).id;
      let res;
      try { res = await call(API.subtype, { scan_id: sid, subtype: b.dataset.sub }); }
      catch (err) { el.classList.remove('busy'); K.toast(err.message || '적지 못했습니다'); return; }
      if (res.state) K.apply(res.state);
      const nr = Object.assign({}, r, { card: Object.assign({}, r.card, res.card || {}), where: Object.assign({}, res.where || r.where, { subtype_pick: null }) });
      lastPick = nr;
      redrawFront(nr);
      document.querySelectorAll('#rgain .meetline[data-kind="category"]').forEach(x => x.remove());     // S28: 고르기 전 짐작으로 쓴 줄(「민물 냄새 나는 병」)이 남지 않게
      const fm = res.first_meet || null, fmt = fm && (fm.line_short || fm.line_ko);
      if (fm && fm.replaces) document.querySelectorAll('#rgain .meetline[data-kind="' + fm.replaces + '"]').forEach(x => x.remove());
      if (fmt || res.line_ko) { const g = $('#rgain'); if (g) { const sp2 = document.createElement('span'); sp2.className = 'meetline picked'; sp2.dataset.kind = 'subtype'; sp2.textContent = plain(fmt || res.line_ko); g.appendChild(sp2); } }
      el.remove();
      afterReveal(nr);
      if (res.done_ko) K.toast(plain(res.done_ko));
      D.log.push('subtype ' + b.dataset.sub + ' ' + (res.subtype_ko || ''));
    });
    D.log.push('subpick ' + (sp.options || []).length + (sg ? ' suggest' : ''));
  }
  let lastPick = null;
  // S30·S31 해금 방송(unlock_new[]) — 스캔·/api/ark·/api/relic/where 어디로 와도 켠 날 해금과 같은 열쇠(기능|켠 날)로 한 번만
  function sayUnlockNew(list, from) {
    (list || []).forEach(n => {
      const key = (n.feature || '') + '|' + (((K.ark || {}).unlocked || {}).play_day || ''), said = store.get('unlock_said', []);
      if (!n.line || said.indexOf(key) >= 0) return;
      said.push(key); store.set('unlock_said', said.slice(-40)); setTimeout(() => K.say(plain(n.line)), 1200); D.log.push('unlock ' + n.feature + ' ' + from);
    });
  }
  // S31 선반 물건 「가보로 드리기」: GET /api/relic/where → heirloom[] 를 작은 패널에. 건네기는 /api/give {relic_id, target:{resident_id, heirloom:true}}
  async function heirFromShelf(it) {
    const id = it.card_id || it.id; if (!id) return;
    let w;
    try { w = await call('/api/relic/where?uid=' + encodeURIComponent(K.uid) + '&relic_id=' + encodeURIComponent(id)); }
    catch (err) { K.toast(err.message || '지금은 고를 수 없습니다'); return; }
    const wh = w.where || w;
    sayUnlockNew(w.unlock_new || wh.unlock_new, 'shelf');
    if (!(wh.heirloom || []).length) { K.toast('지금은 이 물건을 가보로 드릴 분이 없습니다.'); return; }
    const nm = it.display_name || it.relic_name || it.name || '물건';
    const body = K.panel('<h2>' + esc(plain(w.heirloom_label || wh.heirloom_label || '가보로 드리기')) + '</h2><p class="sub">「' + esc(nm) + '」</p><div id="heirHost"></div>');
    heirloomRow({ relic_id: id, where: { heirloom: wh.heirloom }, onDone: () => K.closePanel() }, body.querySelector('#heirHost'));
    D.log.push('heir shelf ' + wh.heirloom.length);
  }
  // S27 간직 메모: 가보 칸이 열리기 전(3일째 전)에 들어온 귀함 이상 — 단추 없이 한 줄(나중에 가보로)
  const keepSaid = {};
  function keepNote(r) {
    const kk = (r.card || {}).barcode || r.keep_note.name || ''; if (keepSaid[kk]) return; keepSaid[kk] = 1;   // 같은 물건은 세션에 한 번
    const old = $('#keepNote'); if (old) old.remove();
    const el = document.createElement('p'); el.id = 'keepNote'; el.className = 'keepnote';
    el.innerHTML = '<i aria-hidden="true"></i><span>' + esc(plain(r.keep_note.ko)) + '</span>';
    const strip = $('#giveStrip'), btn = $('#shelfBtn');
    (strip || btn).parentNode.insertBefore(el, strip ? strip.nextSibling : btn);
    D.log.push('keep_note ' + (r.keep_note.rarity || ''));
  }
  // S27 이름 다시 붙이기: 이미 이름을 정한 바코드를 다시 찍으면 where.rename. 하루 한 번(can_today), 접힌 한 줄 → 누르면 물음과 이름들
  function renameRow(r) {
    const rn = r.where.rename, old = $('#renameRow'); if (old) old.remove();
    const el = document.createElement('div'); el.id = 'renameRow'; el.className = 'renamerow';
    const draw = (open) => {
      el.innerHTML = '<button class="rnfold"' + (rn.can_today === false ? ' disabled' : '') + '>' + esc(plain(rn.label_ko || T('scan.rename_label', {}, '이름 다시 붙이기'))) +
        (rn.can_today === false ? ' <small>오늘은 한 번 바꾸셨습니다</small>' : ' <b aria-hidden="true">' + (open ? '▾' : '▸') + '</b>') + '</button>' +
        (open ? '<p class="gq">' + esc(plain(rn.confirm_ko || '')) + '</p><div class="subopts">' +
          (rn.options || []).map(o => '<button data-rn="' + esc(o.id) + '"' + (o.current ? ' class="on" disabled' : '') + '>' + esc(o.ko) + '</button>').join('') + '</div>' : '');
    };
    draw(false);
    const strip = $('#giveStrip'), btn = $('#shelfBtn');
    (strip || btn).parentNode.insertBefore(el, strip || btn);
    el.addEventListener('click', async (e) => {
      if (e.target.closest('.rnfold')) { draw(!el.querySelector('.subopts')); return; }
      const b = e.target.closest('button[data-rn]'); if (!b || el.classList.contains('busy')) return;
      el.classList.add('busy');
      let res;
      try { res = await call(API.subtype, { barcode: (r.card || {}).barcode || r.barcode, scan_id: (r.where || {}).scan_id || (r.card || {}).id, subtype: b.dataset.rn, rename: true }); }
      catch (err) { el.classList.remove('busy'); K.toast(err.message || '다시 적지 못했습니다'); return; }
      if (res.state) K.apply(res.state);
      const nr = Object.assign({}, r, { card: Object.assign({}, r.card, res.card || {}), where: Object.assign({}, res.where || r.where, { subtype_pick: null, rename: null }) });
      lastPick = nr; redrawFront(nr); el.remove();
      const fm = res.first_meet || null, fmt = fm && (fm.line_short || fm.line_ko);
      document.querySelectorAll('#rgain .meetline').forEach(x => x.remove());
      if (fmt) { const g = $('#rgain'); if (g) { const sp2 = document.createElement('span'); sp2.className = 'meetline picked'; sp2.textContent = plain(fmt); g.appendChild(sp2); } }
      afterReveal(nr);
      if (res.done_ko) K.toast(plain(res.done_ko));
      D.log.push('rename ' + b.dataset.rn + ' from ' + (res.renamed_from || ''));
    });
    D.log.push('renamerow ' + (rn.options || []).length + (rn.can_today === false ? ' done_today' : ''));
  }
  // S25 가보 칸: 「어디로」 아래 작은 줄 「가보로 · ○○」. 이미 가보가 있으면 서버가 바꿀지 묻는다(기본 그대로)
  function heirloomRow(r, host, first) {
    const hs = (r.where.heirloom || []).slice(0, 4);
    const old = $('#heirRow'); if (old) old.remove();
    const el = document.createElement('div'); el.id = 'heirRow'; el.className = 'heirrow';
    el.classList.add('fold'); if (host) el.classList.add('open');   // S31: 선반·문어 카드 안에서는 펼친 채로
    el.innerHTML = '<button class="hfold" aria-expanded="false"><i aria-hidden="true"></i>' + esc((() => { const v = K.ext.moment && K.ext.moment('heirloom.fold_label'); return plain((Array.isArray(v) ? v[0] : (typeof v === 'string' ? v : '')) || '가보로 둘 수 있습니다'); })()) + ' <b aria-hidden="true">▸</b></button>' +
      '<p class="hq"><i aria-hidden="true"></i>' + esc(T('heirloom.ask', {}, '오래 아낄 물건입니다. 누구의 가보로 둘까요?')) + '</p><div class="hopts">' +
      hs.map((h, i) => '<button data-h="' + i + '"' + (h.second ? ' class="hsecond"' : '') + '>' + face(personById((h.target || {}).resident_id), 22) + '<span class="hl"><b>' + esc(h.label || ('가보로 · ' + h.name)) + (h.swap ? ' <small>바꾸기</small>' : '') + '</b>' +
        (h.hint_ko ? '<small class="hh">' + esc(plain(h.hint_ko)) + '</small>' : '') + '</span></button>').join('') +
      ((hs.find(h => h.second) || {}).more_ko ? '<button class="hmore" data-hmore="1">' + esc(plain(hs.find(h => h.second).more_ko)) + '</button>' : '') + '</div>';   // S27: 후보마다 한 줄 · S29: 덧붙인 둘째 후보는 「다른 분도 보여 드릴까요?」 뒤에
    if (host) { if (first && host.firstChild) host.insertBefore(el, host.firstChild); else host.appendChild(el); const fb = el.querySelector('.hfold b'); if (fb) fb.textContent = '▾'; }
    else { const strip = $('#giveStrip'), btn = $('#shelfBtn'); const after = strip ? strip.nextSibling : btn; (strip || btn).parentNode.insertBefore(el, after); }
    const send = async (target) => {
      el.classList.add('busy');
      let res;
      try { res = await call(API.give, r.relic_id ? { relic_id: r.relic_id, target } : { scan_id: (r.where || {}).scan_id || (r.card || {}).id, target }); }
      catch (err) { el.classList.remove('busy'); K.toast(err.message || '드리지 못했습니다'); return; }
      el.classList.remove('busy');
      if (res && res.ok === false && res.ask_swap) {                 // 바꿀까요? (기본: 그대로)
        const a = res.ask_swap;
        el.innerHTML = '<p class="hq">' + esc(plain(a.line || '')) + '</p><div class="hopts"><button data-swap="1">' + esc(T('heirloom.swap_label', {}, '바꿔 드리기')) + '</button><button class="on" data-keep="1">' + esc(T('heirloom.keep_label', {}, '그대로 두기')) + '</button></div>';
        el.onclick = (e) => {
          if (e.target.closest('[data-swap]')) send(Object.assign({}, target, { swap: true }));
          else if (e.target.closest('[data-keep]')) { el.remove(); D.log.push('heir keep'); }
        };
        D.log.push('heir ask_swap'); return;
      }
      if (res.state) K.apply(res.state);
      r._placed = true;
      const sg = $('#giveStrip'); if (sg) sg.remove();
      el.remove();
      if (r.onDone) r.onDone(res); else K.closeScan();
      react(res, { rid: target.resident_id, reason: 'heir', target });
      if (!res.heirloom_refused) heirLines(res.heirloom, target.resident_id);       // S27: 거절이면 돌려받음 한 줄만
      D.log.push('heir give ' + ((res.heirloom || {}).tier || '') + ((res.heirloom || {}).swapped ? ' swapped' : ''));
    };
    el.onclick = (e) => {
      if (e.target.closest('[data-hmore]')) { el.classList.add('more'); D.log.push('heir more'); return; }
      const f = e.target.closest('.hfold');
      if (f) { const o = el.classList.toggle('open'); f.setAttribute('aria-expanded', String(o)); f.querySelector('b').textContent = o ? '▾' : '▸'; D.log.push('heir fold ' + (o ? 'open' : 'close')); return; }
      const b = e.target.closest('button[data-h]'); if (b && !el.classList.contains('busy')) send(hs[+b.dataset.h].target);
    };
    D.log.push('heirrow ' + hs.length);
  }
  // 등급별 줄: 귀함 = 쓰는 모습(방송), 진귀함 = 대사의 주어(방송), 전설 = 세 번째 기억 장면(작은 카드, 세 줄)
  function heirLines(h, rid) {
    if (!h) return;
    const L = h.lines || {};
    if (L.placed) setTimeout(() => K.say(plain(L.placed)), 400);
    if (L.swapped) setTimeout(() => K.say(plain(L.swapped)), 600);
    if (L.use) setTimeout(() => K.say(plain(L.use)), 1200);
    if (L.speak) setTimeout(() => K.say(plain('「' + L.speak + '」')), 1800);
    const tm = h.third_memory || L.third_memory;
    if (tm && (tm.line || tm.announce)) {
      const p = personById(rid);
      queueBeat({ id: 'third:' + (tm.id || rid), resident_id: rid, title: T('heirloom.third_title', {}, '세 번째 기억'), broadcast: tm.announce, line: tm.line, size: 'big' });
      beatShown = 0; setTimeout(showBeat, 2600); void p;
    }
  }
  function redrawFront(r) {                                  // 카드 앞면만(뒤집기·연출 없이)
    const c = r.card || {}, f = $('#rcFront'); if (!f || !K.ext.cards) return;
    const pid = K.propForItem ? K.propForItem(c.category, c.subtype) : K.propForCategory(c.category);   // S28 고른 이름의 소품
    f.innerHTML = K.ext.cards.face({ rarity: c.rarity, sea: !!(c.sea_variant || (r.variant && r.variant.shiny)), name: c.name, category: c.category,
                                     subtype_ko: c.subtype_ko, flavor: c.flavor, prop_id: pid });
    K.ext.cards.settle($('#rcard'));
    const sh = f.querySelector('.rk-shine i');
    if (sh && sh.animate && !reduced()) sh.animate([{ transform: 'translate3d(-120%,0,0) skewX(-18deg)' }, { transform: 'translate3d(130%,0,0) skewX(-18deg)' }], { duration: 520 });
  }
  function afterReveal(r) {
    const old = $('#giveStrip'); if (old) old.remove();
    if (r !== lastPick) { const op = $('#subPick'); if (op) op.remove(); }     // 다른 카드의 고르기가 남지 않게
    ['#renameRow', '#keepNote'].forEach(q => { const x = $(q); if (x) x.remove(); });
    const sp = r.where && r.where.subtype_pick;
    if (sp && (sp.options || []).length && (sp.needed || sp.later_ok)) setTimeout(() => subtypePick(r, sp), 0);
    sayUnlockNew(r.unlock_new, 'scan');
    if (((r.where || {}).heirloom || []).length) setTimeout(() => heirloomRow(r), 0);
    else if (r.keep_note && r.keep_note.ko) setTimeout(() => keepNote(r), 0);
    if ((r.where || {}).rename && (r.where.rename.options || []).length) setTimeout(() => renameRow(r), 0);
    if (D.mock && !r.suggest) D.mock.suggest(r);
    const sug = normSuggest(r);
    pending = sug.length ? r : null;
    if (!sug.length) return;
    const compact = (r.where && typeof r.where.compact === 'boolean') ? r.where.compact : (r.scans_today || 1) > 1;   // API_S19 §1 where.compact
    const el = document.createElement('div');
    el.id = 'giveStrip'; el.className = 'give' + (compact ? ' compact' : '');
    el.innerHTML = stripHTML(sug, compact, T('give.keep', {}, '선반'), (r.where || {}).labels);
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
  let keepToastSaid = false;
  function keepShelf(r) {
    const sid = (r.where || {}).scan_id || (r.card || {}).id;
    if (!sid || D.mock || r._placed) return; r._placed = true;
    D.log.push('keep ' + sid);                               // S32 길잡이: 「선반에」는 건네기가 아니다
    if (!keepToastSaid) K.ext.keepToastAt = performance.now();
    call(API.give, { scan_id: sid, target: 'shelf' }).then(x => {
      if (x && x.state) K.apply(x.state);
      const an = x && x.reaction && (x.reaction.announce || x.reaction.line);   // 서버 「선반에 올려 두었습니다」를 세션에 한 번
      if (an && !keepToastSaid) { keepToastSaid = true; setTimeout(() => K.toast(plain(txt(an))), 500); }
    }).catch(() => {});
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
    const willCard = !!(ef.arc && !ef.arc.deferred && beatShown < 1 && !beatSeen[(ef.arc.arc_id || '') + ':' + (ef.arc.step || '')]);   // S34: 이 건네기 뒤 장면 카드가 뜬다
    if (willCard) { sceneWait = true; [ef.arc.announce, ef.arc.line, ef.arc.broadcast, rc.line, rc.announce].forEach(x => { const k = normT(x); if (k) cardSaid.add(k); }); }
    let chipsHTML = '';
    if (res.tier !== 'keep') {
      try { if (willCard && K.ext.chipsHTML) chipsHTML = K.ext.chipsHTML(res); else if (K.ext.giftChips) K.ext.giftChips(res); } catch (e) { /* 칩이 실패해도 반응은 그린다 */ }   // S34 결과 칩: 카드가 있으면 카드 안에
    }
    const big = ef.memory || ef.arc;                         // 기억·매듭이면 대사가 그쪽 것
    const line = plain(txt((ef.memory && ef.memory.line) || rc.line || res.line || rc.announce || ''));
    const kind = ef.returned_to_shelf ? 'returned' : (res.tier === 'chain_beat' ? 'chain' : (res.tier || res.kind || s.reason || 'like'));
    const arcTx = ef.arc ? [ef.arc.announce, ef.arc.line, ef.arc.broadcast] : [];
    if (rc.announce && rc.line && !sameT(rc.announce, rc.line) && !arcTx.some(x => sameT(x, rc.announce))) K.say(plain(rc.announce));    // 관리실 방송은 한 줄 뒤에
    if (res.intent) D.log.push('intent');
    if (ef.keepsake && ef.keepsake.line) setTimeout(() => K.say(plain(ef.keepsake.line)), 600);
    const rid = (res.who && res.who.id) || (res.target && res.target.resident_id) || s.rid;
    const slot = (ef.decor && ef.decor.slot != null) ? ef.decor.slot : ((res.target && res.target.slot != null) ? res.target.slot : s.slot);
    if (ef.decor && ef.decor.tag_added) res.decor_tag = ef.decor.tag_added.ko;
    if (!line && ef.decor) {                                // 방에 놓았는데 대사가 없으면 그 방이 무엇에 다가갔는지
      const tg = (ef.decor.tags || []).find(t => !t.on && t.have) || null;
      res._line = (ef.decor.tag_added ? ef.decor.tag_added.announce || '' : '') || ('꾸밈 ' + ef.decor.items + '/' + ef.decor.cap + (tg ? ' · ' + txt(tg) + ' ' + tg.have + '/' + tg.need : ''));
    }
    if (ef.arc && !ef.arc.deferred) res.beat = Object.assign({ resident_id: rid, _chips: chipsHTML }, ef.arc);
    if (ef.heart && ef.heart.level_up && !ef.heart.level_up.deferred) heartScene(rid, ef.heart.level_up);   // S34 마음 한 칸 — 매듭 카드가 있으면 그 뒤에
    void big;
    const p = rid ? personById(rid) : null;
    const st = p ? stationOf(p) : slot;
    if (st != null && K.flyToSlot) K.flyToSlot(st);
    setTimeout(() => {
      let at = null;
      if (p) { const h = (window.ARKBASE.peopleHits() || []).find(x => x.id === p.id); if (h) at = { x: h.cx, y: h.cy - 46 }; }
      if (!at && slot != null) { const b = window.ARKBASE.slotBox(slot); if (b) at = { x: b.x + b.w / 2, y: b.y + b.h * 0.35 }; }
      if (!at) at = { x: K.view.w / 2, y: K.view.h / 2 };
      if (!willCard) pop(at, kind, line || plain(res._line || ''), null, res.repeat && res.repeat.line ? plain(res.repeat.line) : '');   // 장면 카드가 뜨면 머리 위 말풍선은 띄우지 않는다(카드가 대사를 말한다)
      const rv = res.revealed;
      if (rv && rv.line) {
        if (rv.big) bigReveal(rv, p); else setTimeout(() => K.say(plain(rv.line)), 900);
        D.log.push('revealed ' + rv.kind + (rv.big ? ' big' : ''));
      }
      if (res.repeat) D.log.push('repeat ' + (res.repeat.other_name || ''));
      if (res.decor_tag || res.tag_formed) badgePop(slot, txt(res.decor_tag || res.tag_formed));
      if (res.beat) queueBeat(res.beat);
    }, st != null ? 700 : 80);
  }
  function stationOf(p) { const cb = K.cb || {}; const s = (cb.stations || {})[p.id]; return s === undefined ? null : s; }
  // S23 큰 장면: 라벨 없이 처음 맞혔다 — 화면 가운데 「맞히셨습니다」 + 수첩에 이름표가 붙는 한 줄
  function bigReveal(rv, p) {
    const el = document.createElement('div'); el.className = 'revealbig';
    el.innerHTML = '<div class="rb-ring" aria-hidden="true"></div>' + (p ? face(p, 56) : '') + '<b>' + esc(T('reveal.big_title', {}, '맞히셨습니다')) + '</b>' +
      (rv.slot_ko ? '<em>' + esc(rv.slot_ko) + '</em>' : '') + '<p>' + esc(plain(rv.line)) + '</p>';
    document.body.appendChild(el);
    K.play && K.play('cue_spot_found.ogg', 0.45);
    const off = () => { if (!el.parentNode) return; el.classList.add('off'); setTimeout(() => el.remove(), 500); };
    el.addEventListener('click', off); setTimeout(off, 4800);
  }
  function pop(at, kind, line, propId, extra) {
    const el = document.createElement('div');
    el.className = 'givepop gk-' + kind;
    const w = Math.min(260, K.view.w - 24);
    const x = Math.max(12 + w / 2, Math.min(K.view.w - 12 - w / 2, at.x));
    el.style.left = x + 'px'; el.style.top = Math.max(60, at.y) + 'px'; el.style.width = w + 'px';
    el.innerHTML = '<span class="heart" aria-hidden="true"></span>' + (line ? '<p>' + esc(line) + '</p>' : '') + (extra ? '<p class="gp-repeat">' + esc(extra) + '</p>' : '');
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
  const labelsOn = () => { const a = K.ark || {}; return !!((a.prefs || {}).labels_always) || (a.day || 1) < 3; };
  function notebookHTML(p, small) {
    const nb = (coreOf(p) || {}).notebook; if (!nb || !(nb.slots || []).length) return '';
    const sl = nb.slots;
    return '<div class="nbook"><p class="nbhead"><b>수첩</b> ' + (nb.known | 0) + '/' + (nb.total || sl.length) + '</p><div class="nbslots">' +
      sl.map(x => '<span class="nb' + (x.known ? ' on' : '') + ' nb-' + esc(x.kind) + '" title="' + esc(x.kind_ko || '') + '">' + (x.known ? '<i>' + esc(x.kind_ko || '') + '</i>' + esc(x.ko || '') + (x.how === 'gossip' ? ' <small>들은 말</small>' : '') : '<i>' + esc(x.kind_ko || '') + '</i>?') + '</span>')
        .slice(0, small ? 8 : 20).join('') + '</div></div>';
  }
  K.ext.notebookFor = (p) => notebookHTML(p, false);
  function tasteHTML(p, small) {
    const t = normTaste(p);
    if (!labelsOn() && (coreOf(p) || {}).notebook) { t.likes = []; t.dislike = ''; }    // 좋아함은 수첩으로만(알아낸 것만)
    const nbh = labelsOn() ? '' : notebookHTML(p, small);
    if (!t.need && !t.likes.length && !t.keep && !t.arc && !t.memN && !nbh && !t.heir) return '';
    return '<div class="taste' + (small ? ' sm' : '') + '">' +
      (t.need ? '<p class="tneed' + (t.need.met ? ' met' : '') + '"><i aria-hidden="true"></i><b>오늘</b> ' + esc(plain(t.need.ko)) + (t.need.met ? ' <em class="metmark">받음</em>' : '') + '</p>' : '') +
      (t.likes.length ? '<p class="tlike"><i aria-hidden="true"></i><b>좋아함</b> ' + esc(t.likes.slice(0, 3).join(' · ')) + '</p>' : '') +
      (t.keep ? '<p class="tkeep"><i aria-hidden="true"></i><b>머리맡</b> ' + esc(t.keep.ko) + '</p>' : '') +
      (t.arc ? '<p class="tarc"><b>' + esc(t.arc.title || '이야기') + '</b> ' + arcDots(t.arc) + (t.arc.done ? ' <small>다 이뤘습니다</small>' : (t.arc.next ? '<br><small>' + (t.arc.open ? '' : '며칠 뒤 · ') + esc(plain(t.arc.next)) + '</small>' : '')) + '</p>' : '') +
      (t.pimps.length ? '<p class="tpimp"><b>각인</b> ' + esc(t.pimps.join(' · ')) + '</p>' : '') +
      (t.heir ? '<p class="their"><i aria-hidden="true"></i><b>가보</b> 「' + esc(t.heir.name || '') + '」 <em class="hr-' + esc(t.heir.tier || '') + '">' + esc(K.RAR_KO[t.heir.tier] || '') + '</em>' + (t.heir.boxed ? ' <small>상자에</small>' : '') + '</p>' : '') + nbh +
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
    ppop.innerHTML = '<div class="phead">' + face(p, 36) + '<b>' + esc(p.name) + '</b><em>' + esc(p.evolved_ko || p.role_ko || '') + '</em></div>' +
      (K.ext.heartRow ? K.ext.heartRow(p.id, true) : '') + body +
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
      const met = !!(n.met || (p && normTaste(p).need && normTaste(p).need.met));
      return '<span class="needchip' + (met ? ' met' : '') + '">' + face(p, 26) + '<b>' + esc((p && p.name) || n.name || '') + '</b> ' + esc(plain(txt(n.need))) +
        (met ? ' <em class="metmark">받음</em>' : '') + '</span>'; }).join('') + '</div>';
    return h;
  }
  const hasMorning = (st) => !!((st.needs_today && st.needs_today.length) || (st.beat_today && st.beat_today.new && st.beat_today.star));

  // ══════════════════════════════════════════════════════════════
  //  3. 매듭 이야기 카드 — 아침 패널 말고는 세션에 한 번. 작은 카드(큰 창 아님), 고르기(ask) 있으면 단추
  // ══════════════════════════════════════════════════════════════
  // r5-5 같은 문장 겹침: 서버가 역할 없는 대체 줄을 announce·line 양쪽에 실을 때가 있다. 화면에서는 같은 말을 한 번만
  const normT = (x) => String(plain(txt(x || ''))).replace(/[「」『』"'“”‘’\s.,…!?·~]/g, '');
  const sameT = (a, b) => { const x = normT(a), y = normT(b); return !!x && x === y; };
  const saidAt = {};
  const cardSaid = new Set();
  let sceneWait = false;
  const sceneCard = () => document.querySelector('.beatcard:not(.octwhere):not(.off), .revealbig');
  D.sceneHold = () => sceneWait || !!sceneCard();
  new MutationObserver(() => {
    const on = !!sceneCard();
    if (on) sceneWait = false;
    if (on !== document.body.classList.contains('scene-on')) {
      document.body.classList.toggle('scene-on', on);
      if (!on) setTimeout(() => { if (!sceneCard() && K.flushSay) K.flushSay(); }, 500);   // 카드가 닫히면 미룬 방송을 차례로
    }
  }).observe(document.getElementById('base') || document.body, { childList: true, subtree: false });
  setInterval(() => { if (sceneWait && !sceneCard() && !beatQ.length) { sceneWait = false; if (K.flushSay) K.flushSay(); } }, 3000);   // 카드가 끝내 안 뜨면 풀어 준다
  D.dupSkips = 0;
  if (!K.__sayWrapped) {
    const raw = K.say; K.__sayWrapped = true;
    K.say = (m) => {
      const k = normT(m); if (!k) return raw(m);
      const now = Date.now();
      const onCard = [...document.querySelectorAll('.beatcard .bline, .beatcard .bcast, .givepop p')].some(e => normT(e.textContent) === k);
      if (onCard || cardSaid.has(k) || (saidAt[k] && now - saidAt[k] < 60000)) { D.dupSkips++; D.log.push('say dup'); return; }
      saidAt[k] = now; return raw(m);
    };
  }
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
    if (b.broadcast && b.line && sameT(b.broadcast, b.line)) { b.broadcast = ''; D.log.push('beat dedupe'); }
    const el = document.createElement('div'); el.className = 'beatcard' + (b.size === 'big' ? ' big' : '');
    el.innerHTML = '<div class="phead">' + face(p, 40) + '<b>' + esc(txt(b.title) || (p ? p.name : '')) + '</b>' + arcDots(b.arc || (p && normTaste(p).arc)) + '</div>' +
      (b._chips ? '<div class="cardchips">' + b._chips + '</div>' : '') +
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
  const ART = { vis: {}, dec: {}, decCell: [564, 317], floorY: 262, win: {}, knots: {}, traces: null, bySub: null };
  fetch('/static/art/props/props_meta.json').then(r => (r.ok ? r.json() : null)).then(j => {
    if (!j) return; ART.bySub = j.by_subtype || null;
    if (j.seat_stand) { ART.seat = j.seat_stand; loadImg('/' + j.seat_stand.file.replace(/^\//, '')); }
    Object.entries(j.knots || {}).forEach(([k, v]) => { ART.knots[k] = v; loadImg('/' + v.file.replace(/^\//, '')); });
  }).catch(() => {});
  // 머리맡·작업 자리의 받은 물건(core.residents[rid].keepsakes_recent, 최근 셋) — 그 사람 발치 옆에 작은 소품으로
  function propIdOf(k) {
    if (k.prop) return k.prop;
    const b = ART.bySub || {}, c = b[k.category] || {};
    return ((c[k.subtype] || {}).prop) || ((Object.values(c).find(x => x.match === 'good') || {}).prop) || ((b.unknown || {}).any || {}).prop || null;
  }
  const keepLog = {}, rareLog = {}, spotLog = {};
  let spotFrame = -1;
  D.spots = () => JSON.parse(JSON.stringify(spotLog));
  // S25 남은 것: 그 방 사람 수만큼 keepsake_spots(침상·작업대·화단 턱·선반) 앞에서부터 — i 번째 사람의 물건 하나.
  // 끝 매듭(core.residents[rid].seat)을 맺은 사람은 자리 받침(seat_stand) 위에 그 물건. 매듭 소품 넷(own_prop_arcs)은 받침 대신 매듭 소품이 이미 방에 있다
  const SPOT_PLATE = { quarters: 'quarters', storage: 'storage', pantry: 'storage', workshop: 'workshop', infirmary: 'infirmary',
                       generator: 'power', power: 'power', greenhouse: 'greenhouse', decoder: 'quarters', lounge: 'storage', bath: 'infirmary', well: 'greenhouse' };
  function drawSpots(room, slot, ix, iy, iw, ih, t, lit, ppl) {
    spotFrame = t;
    const spots = (ART.kspots || {})[SPOT_PLATE[room.id] || room.id]; if (!spots || K.z < 0.25) return;
    const ctx = K.ctx, kx = iw / ART.decCell[0], ky = ih / ART.decCell[1], cr = ((K.ark || {}).core || {}).residents || {};
    const own = (ART.seat || {}).own_prop_arcs || {};
    ppl = ppl || [];
    // S26: 끝 매듭 자리는 seat.slot(맺은 방)에 고정 — 사람이 옮겨도 남는다. slot 이 없는 옛 값은 그 사람이 선 방
    const seatOf = (c) => (c.seat && c.seat.item && !own[c.seat.arc] ? c.seat : null);
    const seatItem = (c, seat) => (c.items || []).slice().reverse().find(x => x.name === seat.item) || { name: seat.item, category: seat.category, subtype: seat.subtype, prop: seat.prop };
    const rows = [];
    Object.keys(cr).forEach(rid => { const c = cr[rid], st = seatOf(c); if (st && st.slot === slot) rows.push({ rid, c, seat: st, it: seatItem(c, st) }); });
    ppl.forEach(p => {
      if (rows.some(r => r.rid === p.id)) return;                          // 그 사람의 자리가 이 방에 있으면 그것 하나
      const c = cr[p.id] || {}, st = seatOf(c);
      if (st && st.slot == null) { rows.push({ rid: p.id, c, seat: st, it: seatItem(c, st) }); return; }
      let it = null;
      if (c.heirloom && !c.heirloom.boxed) it = c.heirloom;                // 가보가 있으면 머리맡에는 가보
      if (!it) it = (c.keepsakes_recent || [])[0] || null;
      if (it) rows.push({ rid: p.id, c, seat: null, it });
    });
    rows.slice(0, spots.length).forEach((r, i) => {
      const sp = spots[i], it = r.it;
      const pid = it && propIdOf(it); const pi = pid && K.propImg(pid); if (!pi || !pi.ok1) return;
      const sc = 1.6 * kx, cx = ix + sp.x * kx; let bottom = iy + sp.y * ky, stood = false;
      ctx.save(); ctx.imageSmoothingEnabled = false; if (lit === false) ctx.globalAlpha = 0.6;
      if (r.seat && ART.seat) {
        const sim = imgOf['/' + ART.seat.file.replace(/^\//, '')];
        if (sim && sim.ok) { const sw = ART.seat.w * sc, sh = ART.seat.h * sc; ctx.drawImage(sim.img, cx - sw / 2, bottom - sh, sw, sh); bottom = bottom - sh + (ART.seat.item_floor_y || 18) * sc; stood = true; }
      }
      const w = pi.x1.naturalWidth * sc, h = pi.x1.naturalHeight * sc;
      ctx.drawImage(pi.x1, cx - w / 2, bottom - h, w, h);
      ctx.restore();
      spotLog[ppl.some(p => p.id === r.rid) ? r.rid : r.rid + ':seat'] = { at: t, slot, spot: i, kind: sp.kind, prop: pid, seat: stood, heir: it === r.c.heirloom, fixed: !!(r.seat && r.seat.slot != null) };
    });
  }
  D.rare = () => Object.assign({}, rareLog);
  K.ext.drawKeepsakes = (p, px, floorY, box, mirror) => {
    const cr = ((K.ark || {}).core || {}).residents || {}, ks = ((cr[p.id] || {}).keepsakes_recent || []).slice(0, 3);
    if (!ks.length || K.z < 0.3) return;
    if (spotLog[p.id] && spotLog[p.id].at === spotFrame) return;   // S25: 침상·작업대 자리에 놓였으면 발치에는 그리지 않는다
    const ctx = K.ctx, z = K.z, sc = Math.max(1, Math.round(1.5 * z)), side = mirror ? -1 : 1;
    let x = px + side * (box.w / 2 + 4 * z);
    ks.forEach((k, i) => {
      const pi = K.propImg(propIdOf(k)); if (!pi || !pi.ok1) return;
      const w = pi.x1.naturalWidth * sc / 1.0, h = pi.x1.naturalHeight * sc;
      const ww = w * 0.55, hh = h * 0.55;                       // 사람보다 작게(소품 원화 34px → 발치 크기)
      ctx.save(); ctx.imageSmoothingEnabled = false;
      ctx.drawImage(pi.x1, side > 0 ? x : x - ww, floorY - hh, ww, hh);
      ctx.restore();
      x += side * (ww + 2 * z);
    });
    keepLog[p.id] = ks.map(k => propIdOf(k));
  };
  D.keepsakes = () => Object.assign({}, keepLog);
  // ★ S25 자가 검사: 「어디로」 줄의 얼굴·이름·기색이 그 줄 자신의 target.resident_id 에서 왔나(서버 행 role = 얼굴 role = 명부 role)
  D.selfTest = () => {
    const bad = [];
    document.querySelectorAll('button.gopt[data-rid]').forEach(b => {
      const p = personById(b.dataset.rid), fr = (b.querySelector('.face') || {}).dataset || {};
      const nm = (b.querySelector('.gname b') || {}).textContent || '';
      if (!p) { bad.push(b.dataset.rid + ' 명부에 없음'); return; }
      if (fr.role !== p.role) bad.push(p.name + ' 얼굴 ' + fr.role + '≠' + p.role);
      if (b.dataset.srole && b.dataset.srole !== p.role) bad.push(p.name + ' 서버행 ' + b.dataset.srole + '≠' + p.role);
      if (nm && nm !== p.name) bad.push(b.dataset.rid + ' 이름 ' + nm + '≠' + p.name);
    });
    return { ok: !bad.length, rows: document.querySelectorAll('button.gopt[data-rid]').length, bad };
  };
  D.bigReveal = (rv, pid) => bigReveal(rv, personById(pid));   // ★ 검수용
  K.ext.visMeta = (id) => ART.vis[id] || null;
  // 매듭 소품(core.props): 그 매듭이 일어난 방에(식량창고 앞 의자·온실 창가 싹·공방 대야·거주실 이름표). 그림이 없으면 그리지 않는다
  const KNOT_ROOM = { chair_1: 'pantry', sprout_on_sill: 'greenhouse', warm_basin: 'workshop', name_tag_worn: 'quarters' };
  const KNOT_SPOT = { chair_1: [120, 282], sprout_on_sill: [430, 120], warm_basin: [300, 282], name_tag_worn: [455, 150] };
  const knotLog = {};
  const imgOf = {};
  const loadImg = (src) => { let o = imgOf[src]; if (!o) { o = imgOf[src] = { img: new Image(), ok: false }; o.img.onload = () => { o.ok = o.img.naturalWidth > 0; }; o.img.src = src; } return o; };
  fetch('/static/art/visitors/visitors_meta.json').then(r => (r.ok ? r.json() : null)).then(j => {
    (j && j.visitors || []).forEach(v => { ART.vis[v.id] = v; loadImg('/' + v.file.replace(/^\//, '')); });
  }).catch(() => {});
  fetch('/static/art/decor/decor_meta.json').then(r => (r.ok ? r.json() : null)).then(j => {
    if (!j) return; if (j.cell) ART.decCell = j.cell; if (j.clear_zones && j.clear_zones.floor_band_y) ART.floorY = j.clear_zones.floor_band_y;
    (j.tags || []).forEach(t => { ART.dec[t.id] = t; loadImg('/static/art/decor/' + t.file); });
    if (j.keepsake_spots && j.keepsake_spots.by_plate) ART.kspots = j.keepsake_spots.by_plate;
    if (j.slots) { ART.slots = { list: j.slots, pos: j.slot_positions_in_cell || {} }; spotsCache = null; }
    if (j.traces) { ART.traces = j.traces; (j.traces.items || []).forEach(x => loadImg('/static/art/decor/' + x.file)); }
    const wc = (j.window_spot || {}).cells || {}; Object.keys(wc).forEach(k => { if (wc[k] && wc[k].visitor_world) ART.win[k] = wc[k].visitor_world; });
  }).catch(() => {});
  // 흔적 그림 고르기: visitors.json 손님 → 그 손님이 오는 자리(창=물고기 비늘, 방 안=발자국). 표에 없으면 물무늬
  const traceLog = {};
  D.traces = () => Object.assign({}, traceLog); D.knots = () => Object.assign({}, knotLog);
  function traceFor(vid) {
    const items = (ART.traces || {}).items || []; if (!items.length) return null;
    const v = ART.vis[vid] || {}, kind = /octopus/.test(vid || '') ? 'octopus' : /gardener/.test(vid || '') ? 'gardener' : v.indoor ? 'guest' : (v.where === 'window' ? 'small_fish' : 'any');
    return items.find(x => (x.visitors || []).indexOf(kind) >= 0) || items.find(x => (x.visitors || []).indexOf('any') >= 0) || items[0];
  }
  function decorOf(room) {
    const d = ((K.ark && K.ark.room_decor) || {})[String(room.slot)] || room.decor || {};
    const items = (d.items || []).filter(x => !x.boxed);
    const n = d.cap || d.slots || 0;
    const tags = (d.tags || []).filter(t => t.on !== false).map(t => ({ id: t.id || t, ko: txt(t) }));
    return { items, n, tags, raw: d };
  }
  K.ext.decorFor = (slot) => {                             // 방 카드 한 줄: 꾸밈 칸 n/m · 꼬리표 · 다가가는 꼬리표
    const r = roomAt(slot); if (!r) return '';
    const mw = K.ext.wallLine ? K.ext.wallLine(slot) : '';    // S27 기억 벽(식량창고)
    const dc = decorOf(r); if (!dc.n) return mw;
    const near = (dc.raw.tags || []).filter(t => !t.on && t.have).map(t => t.ko + ' ' + t.have + '/' + t.need);
    const trc = ((K.ark || {}).decor_trace || []).find(d => d.slot === slot);
    return mw + (trc && trc.line ? '<p class="rcline traceline">' + esc(plain(trc.line)) + '</p>' : '') + '<p class="rcline decorline">꾸밈 ' + dc.items.length + '/' + dc.n + (dc.tags.length ? ' · <b>' + esc(dc.tags.map(t => t.ko).join(' · ')) + '</b>' : '') + (near.length ? ' · ' + esc(near[0]) : '') + '</p>' +
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
  K.ext.drawRoomExtra = (room, slot, ix, iy, iw, ih, t, lit, ppl) => {
    const ctx = K.ctx, z = K.z, dc = decorOf(room);
    try { drawSpots(room, slot, ix, iy, iw, ih, t, lit, ppl); } catch (e) { /* 자리 소품이 실패해도 방은 그린다 */ }
    try { drawWall(room, slot, ix, iy, iw, ih, lit); } catch (e) { /* 기억 벽이 실패해도 방은 그린다 */ }
    const kx0 = iw / ART.decCell[0], ky0 = ih / ART.decCell[1];
    // S22 흔적(decor_trace — 꼬리표까지 하나 남은 방): 바닥 가운데 기둥 자리에 반투명 그림
    ((K.ark || {}).decor_trace || []).filter(d => d.slot === slot).slice(0, 1).forEach(d => {
      const tr = traceFor(d.visitor_id); if (!tr) return;
      const im = imgOf['/static/art/decor/' + tr.file]; if (!im || !im.ok) return;
      const sp = ((ART.traces || {}).corner_spots_in_cell || [[300, 276]])[0];
      ctx.save(); ctx.globalAlpha = lit === false ? 0.5 : 0.85; ctx.imageSmoothingEnabled = false;
      ctx.drawImage(im.img, ix + (sp[0] - tr.anchor[0]) * kx0, iy + (sp[1] - tr.anchor[1]) * ky0, tr.w * kx0, tr.h * ky0);
      ctx.restore(); traceLog[slot] = tr.id;
    });
    // S22 매듭 소품
    (((K.ark || {}).core || {}).props || []).forEach(pk => {
      if (KNOT_ROOM[pk] !== room.id || knotLog[pk] != null && knotLog[pk] !== slot) return;
      const kv = ART.knots[pk]; if (!kv) return;
      const im = imgOf['/' + kv.file.replace(/^\//, '')]; if (!im || !im.ok) return;
      const [ax, ay] = KNOT_SPOT[pk], sc = 3 * kx0;
      ctx.save(); ctx.imageSmoothingEnabled = false;
      ctx.drawImage(im.img, ix + ax * kx0 - kv.w * sc / 2, iy + ay * ky0 - kv.h * sc, kv.w * sc, kv.h * sc);
      ctx.restore(); knotLog[pk] = slot;
    });
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
      if (v.form === 'rare') { ctx.save(); ctx.filter = 'hue-rotate(160deg) saturate(1.7) brightness(1.15)'; }
      if (!meta || !spriteVisitor(ctx, meta, x, y, z, t, k)) drawVisitor(ctx, v, x, inside ? floor : y, z, t);
      if (v.form === 'rare') { ctx.restore(); rareLog[v.kind] = slot; }
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
  const leaveLog = [];
  D.leaveOrder = () => leaveLog.slice();
  async function leaveCard(manual) {
    if ($('.leavecard')) return;
    const st = K.ark || {};
    let d = null;
    if (!D.mock) { try { d = await call(API.leaving + '?uid=' + encodeURIComponent(K.uid)); } catch (e) { d = null; } }
    if (d && (d.heart_scenes || []).length) d.heart_scenes.forEach(h => heartScene(h.resident_id || h.rid, h.scenes ? Object.assign({}, h, { deferred: false }) : { level: h.level, fill_ko: h.fill_ko, scenes: [h], deferred: false }));   // S34 미룬 마음 장면(떠날 때 카드 뒤에)
    const changed = ((d && (d.changed || d.lines)) || st.session_changes || []).map(txt).filter(Boolean).slice(0, 2);
    const nv = (d && d.next_visit) || st.next_visit || null;
    const nxt = (nv && txt(nv.line || nv)) || T('leave.nothing', {}, '다음에 켜시면 밤사이 일을 한꺼번에 알려 드리겠습니다. 편히 쉬십시오.');
    // S27 r5-3: 보여 줄 순서는 서버 order(=leave_order). next_visit 가 tomorrow_ask 면 내일의 부탁이 합쳐진 것(그 사람 얼굴과 함께)
    const ta = (d && d.tomorrow_ask) || (d ? null : st.tomorrow_ask);
    const mc = (d && d.missed_chain) || st.missed_chain;
    const blocks = {
      next_visit: () => (nv && nv.kind === 'tomorrow_ask'
        ? '<p class="sub">' + esc(nv.title || '다음에 켜시면') + '</p><p class="tomask">' + face(personById(((nv.data || {}).resident_id)), 26) + '<span>' + esc(plain(nxt)) + '</span></p>'
        : '<p class="sub">' + esc((nv && nv.title) || '다음에 켜시면') + '</p><p class="lnext">' + esc(plain(nxt)) + '</p>'),
      missed_chain: () => (mc && txt(mc) ? '<p class="missed">' + esc(plain(txt(mc))) + '</p>' : ''),
      unlock_teaser: () => (((d && d.unlock_teaser) || {}).line ? '<p class="teaser' + (d.unlock_teaser.required ? ' req' : '') + '">' + esc(plain(d.unlock_teaser.line)) + '</p>' : ''),
      tomorrow_ask: () => (ta && !(nv && nv.kind === 'tomorrow_ask') ? '<p class="tomask">' + face(personById(ta.resident_id), 26) + '<span>' + esc(plain(txt(ta.line))) + '</span></p>' : ''),
    };
    const order = ((d && d.order) || st.leave_order || []).filter(k => blocks[k]);
    ['next_visit', 'missed_chain', 'tomorrow_ask', 'unlock_teaser'].forEach(k => { if (order.indexOf(k) < 0) order.push(k); });
    leaveLog.push(order.join(','));
    const el = document.createElement('div'); el.className = 'leavecard';
    el.innerHTML = '<div class="leave-in">' +
      (changed.length ? '<p class="sub">' + esc((d && d.title) || T('leave.changed_title', {}, '이번에 바뀐 것')) + '</p>' + changed.map(c => '<p class="dayline">' + esc(plain(c)) + '</p>').join('') : '') +
      order.map(k => blocks[k]()).join('') +
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
  // 잔치(API_S19 §10, 켠 날 10부터·7일에 한 번·넘치는 식량의 출구): ≡ → 「잔치」 → 마주 앉힐 두 분 고르기.
  //  대가·여는 날은 서버가 정한다. 화면은 숫자를 박지 않고, 한 번 연 뒤 응답의 paid 를 기억해 다음부터 보여 준다(못 열면 서버 문장 그대로)
  const costText = (o) => Object.entries(o || {}).map(([k, v]) => (K.RES_KO[k] || k) + ' ' + v).join(' · ');
  function openFeast() {
    K.closeMenu();
    const ps = people(), pick = [], fc = store.get('feast_cost', null);
    const body = K.panel('<h2>잔치</h2><p class="sub">' + (fc ? esc(K.josa(costText(fc), '이')) + ' 듭니다. ' : '식량과 물을 넉넉히 씁니다. ') + '마주 앉으실 두 분을 골라 주세요.</p><div class="chips">' +
      ps.map(p => '<button class="chip" data-fp="' + esc(p.id) + '">' + esc(p.name) + '</button>').join('') + '</div><div class="rowbtns"><button class="on" id="feastGo" disabled>상 차리기</button></div>');
    body.addEventListener('click', async (e) => {
      const c = e.target.closest('[data-fp]');
      if (c) { const i = pick.indexOf(c.dataset.fp); if (i >= 0) pick.splice(i, 1); else { pick.push(c.dataset.fp); if (pick.length > 2) pick.shift(); }
        body.querySelectorAll('[data-fp]').forEach(x => x.classList.toggle('on', pick.indexOf(x.dataset.fp) >= 0)); body.querySelector('#feastGo').disabled = pick.length !== 2; return; }
      if (e.target.id === 'feastGo') {
        e.target.disabled = true;
        try { const r = await call('/api/feast', { pair: pick.slice() }); if (r.state) K.apply(r.state); K.closePanel();
          const ln = plain(txt(r.ko || r.line || '상을 차렸습니다. 다들 한자리에 앉으셨습니다.'));
          if (r.paid) { store.set('feast_cost', r.paid); K.toast(K.josa(costText(r.paid), '으로') + ' 상을 차렸습니다.'); setTimeout(() => K.say(ln), 2800); }
          else K.say(ln);
          D.log.push('feast ' + costText(r.paid)); }
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
  // 찍기 창이 열리면 매듭 카드를 접어 둔다(겹침 방지) — 닫히면 다시 편다
  new MutationObserver(() => {
    const open = !$('#scan').hidden;
    document.querySelectorAll('.beatcard, .ppop').forEach(el => el.classList.toggle('folded', open));   // .octwhere 도 .beatcard
  }).observe($('#scan'), { attributes: true, attributeFilter: ['hidden'] });
  // S25: 큰 창은 한 번에 하나(UI_SIMPLE) — 패널(도감·장부 등)이 열려 있는 동안 문어의 「어디로」 카드는 잠시 숨긴다
  const octHide = () => { const open = !$('#panel').hidden || !$('#raidbar').hidden || !$('#roomcard').hidden; document.querySelectorAll('.beatcard.octwhere').forEach(e => { e.hidden = open; }); };
  new MutationObserver(octHide).observe($('#panel'), { attributes: true, attributeFilter: ['hidden'] });
  new MutationObserver(octHide).observe($('#raidbar'), { attributes: true, attributeFilter: ['hidden'] });
  new MutationObserver(octHide).observe($('#roomcard'), { attributes: true, attributeFilter: ['hidden'] });   // 방 카드를 열어도(눌러서 연 것이 먼저)   // S27: 습격 카드를 펼치면 문어 카드도 잠시 숨김
  // 선반 물건 다시 주기(API_S19 §2 relic_id): 사람 + 꾸밈 칸이 남은 방 중에서 고른다
  function regift(it) {
    const a = K.ark || {}, rd = a.room_decor || {};
    const rooms = unlocked('decor_place') ? Object.keys(rd).filter(k => (rd[k].items || []).filter(x => !x.boxed).length < (rd[k].cap || 0)).map(k => +k) : [];
    const body = K.panel('<h2>' + esc(it.display_name || it.relic_name || it.name || '물건') + ' 건네기</h2><p class="sub">누구에게, 어디에 둘까요?</p>' +
      '<div class="gopts regift">' + people().map(p => '<button class="gopt" data-rid="' + esc(p.id) + '">' + face(p, 34) + '<span class="gname"><b>' + esc(p.name) + '</b>' +
        (normTaste(p).need ? '<small>오늘 ' + esc(normTaste(p).need.ko) + '</small>' : '') + '</span></button>').join('') +
      rooms.map(s => '<button class="gopt" data-slot="' + s + '"><i class="roomico" aria-hidden="true"></i><span class="gname"><b>' + esc(roomName(s)) + '</b><small>꾸밈 칸</small></span></button>').join('') + '</div>');
    body.addEventListener('click', async (e) => {
      const b = e.target.closest('button.gopt'); if (!b) return;
      const target = b.dataset.rid ? { resident_id: b.dataset.rid } : { slot: +b.dataset.slot };
      b.disabled = true;
      try { const res = await call(API.give, { relic_id: it.card_id || it.id, target }); if (res.state) K.apply(res.state); K.closePanel();
        react(res, { rid: b.dataset.rid || null, slot: b.dataset.slot != null ? +b.dataset.slot : null, reason: res.tier || 'like' }); D.log.push('regift ' + (b.dataset.rid || 'room' + b.dataset.slot)); }
      catch (err) { b.disabled = false; K.toast(err.message || '건네지 못했습니다'); }
    });
  }
  // ── S21 ① 새것 실마리(/api/ark.novelty, 켠 날 4부터 세션에 한 번) — 그사이 패널에 이미 실렸으면 다시 안 하고, 아니면 방송 한 줄
  const novSaid = store.get('nov_said', []);
  function noveltyCheck(st) {
    const n = st.novelty; if (!n || !n.line) return;
    const key = (n.line_key || n.kind || '') + '|' + n.line;
    if (novSaid.indexOf(key) >= 0) return;
    novSaid.push(key); while (novSaid.length > 20) novSaid.shift(); store.set('nov_said', novSaid);
    setTimeout(() => {                                       // 그사이 패널(첫 로드)이 줄을 다 모은 뒤에 견준다
      if ((K.ext.ovShown || []).indexOf(plain(n.line)) >= 0) { D.log.push('novelty in-panel ' + n.kind); return; }
      K.say(plain(n.line)); D.log.push('novelty say ' + n.kind);
    }, 2500);
  }
  // ── S21 ② 5일째 문어 조각의 「어디로」(/api/ark.octopus_gift_where — 스캔과 같은 모양 + relic_id·name). 작은 카드(큰 창 아님)
  let octOpen = null;
  function octWhere(st) {
    const w = st.octopus_gift_where;
    if (!w || !w.relic_id || octOpen === w.relic_id || $('.octwhere')) return;
    const dism = store.get('oct_where_dismissed', {});
    if ((dism[w.relic_id] || 0) >= 2) return;                // 「선반에 그대로」를 두 번 고르면 더 묻지 않는다(물건은 선반에 남는다)
    const sug = normSuggest({ where: w }); if (!sug.length && !(w.heirloom || []).length) return;
    octOpen = w.relic_id;
    const show = () => {
      const q = window.ARKBASE.queue ? window.ARKBASE.queue() : {};
      if (!$('#scan').hidden || !$('#panel').hidden || $('.beatcard') || $('.leavecard') || q.busy || (q.wait || []).length) { setTimeout(show, 1500); return; }
      const nm = w.name || '색 조각';
      const el = document.createElement('div'); el.className = 'beatcard octwhere';
      el.innerHTML = '<div class="phead"><i class="octico" aria-hidden="true"></i><b>' + esc(T('octopus_gift.where_title', {}, '문어가 물어 온 것')) + '</b></div>' +
        '<p class="bline">「' + esc(plain(nm)) + '」</p>' + '<div class="give">' + stripHTML(sug, false, T('octopus_gift.where_keep', {}, '선반에 그대로')) + '</div>';
      $('#base').appendChild(el);
      const close = () => { el.classList.add('off'); setTimeout(() => el.remove(), 400); };
      if ((w.heirloom || []).length) {                       // S31: 가보 후보 — heirloom_first 면 「어디로」 앞에
        const host = document.createElement('div'); host.className = 'octheir';
        const give = el.querySelector('.give'); if (w.heirloom_first) give.before(host); else give.after(host);
        heirloomRow({ relic_id: w.relic_id, where: { heirloom: w.heirloom }, onDone: close }, host);
        D.log.push('octwhere heir ' + w.heirloom.length + (w.heirloom_first ? ' first' : ''));
      }
      el.addEventListener('click', async (e) => {
        const b = e.target.closest('button.gopt'); if (!b || el.classList.contains('busy')) return;
        if (b.dataset.i === 'keep') { dism[w.relic_id] = (dism[w.relic_id] || 0) + 1; store.set('oct_where_dismissed', dism); close(); D.log.push('octwhere keep'); return; }
        const s = sug[+b.dataset.i]; el.classList.add('busy');
        let res;
        try { res = await call(API.give, { relic_id: w.relic_id, target: s.target }); }
        catch (err) { el.classList.remove('busy'); K.toast(err.message || '건네지 못했습니다'); return; }
        if (res.state) K.apply(res.state);
        close(); react(res, s);
        D.log.push('octwhere give ' + (s.rid || 'room' + s.slot) + ' ' + (res.tier || ''));
      });
      D.log.push('octwhere ' + sug.length);
    };
    setTimeout(show, 1200);
  }
  // ── S21 ⑧ 꼬리표가 붙은 방에 배치 안 된 주민이 모인다(visits kind:"residents", CORE_LOOP_A §3 「그 방에 모인다(그림)」).
  //  지금 홀·포드에 있는 사람(일손 아님·바깥 아님)만, 방마다 셋까지. 그림은 base.js(drawGathered)가 그 방 바닥에 그린다
  let gather = { at: {}, by: {} };
  function computeGather(st) {
    const at = {}, by = {}, cbx = st.combat || K.cb || {}, stations = cbx.stations || {}, outside = cbx.outside || [];
    const rows = (st.visits || []).filter(v => v.kind === 'residents' && v.slot != null &&
      (st.rooms || []).some(r => r.slot === v.slot && !r.flooded));
    if (rows.length) {
      let k = 0;
      (st.residents_list || []).filter(p => stations[p.id] === undefined && outside.indexOf(p.id) < 0).forEach(p => {
        const rs = rows.filter(v => (v.resident_ids || []).indexOf(p.id) >= 0 && (by[v.slot] || []).length < 3);
        if (!rs.length) return;
        const v = rs[k++ % rs.length];
        at[p.id] = v.slot; (by[v.slot] = by[v.slot] || []).push(p.id);
      });
    }
    gather = { at, by };
  }
  K.ext.gatheredAt = (id) => (gather.at[id] != null ? gather.at[id] : null);
  K.ext.gatheredIn = (slot) => gather.by[slot] || null;
  D.gather = () => JSON.parse(JSON.stringify(gather));

  // S25 해금: 처음 열린 기능의 방송(unlocked.new, 한 번) · 메뉴 단추 숨김 · 5일째 첫 원정 장면(beat_today.first_session_scene)
  const MENU_GATE = { sendbtn: 'expedition', tablebtn: 'evening_table' };
  function unlockCheck(st) {
    Object.entries(MENU_GATE).forEach(([id, f]) => { const b = document.getElementById(id); if (b) b.hidden = !unlocked(f); });
    const u = st.unlocked; if (!u) return;
    const said = store.get('unlock_said', []);
    (u.new || []).forEach(n => {
      const key = n.feature + '|' + (u.play_day || '');
      if (!n.line || said.indexOf(key) >= 0) return;
      said.push(key); store.set('unlock_said', said.slice(-40));
      setTimeout(() => K.say(plain(n.line)), 1800); D.log.push('unlock ' + n.feature);
    });
    const sc = (st.beat_today || {}).first_session_scene;
    if (sc && (sc.lines || []).length && store.get('scene_day', null) !== (st.beat_today.play_day || st.day)) {
      store.set('scene_day', st.beat_today.play_day || st.day);
      setTimeout(() => firstScene(sc.lines), 2200);
    }
  }
  // ══ S27 기억 벽(7일째 식량창고, 고리 넷) ══════════════════════
  //  /api/ark.memory_wall {open, room, slots[4], filled, total, complete, first_label_ko, hang_prompt_ko, open_ko(처음 한 번), prefilled_ko, story}
  //  방 카드 한 줄 + 「여기 걸기」 → 작은 패널(고리 넷 · 선반/창고 물건) → POST /api/memory_wall/hang. 다 차면 complete_ko + story 세 줄 장면
  const MW_HOOKS = [[150, 128], [200, 128], [250, 128], [300, 128]];   // 식량창고(storage 플레이트) 왼쪽 빈 벽 — 칸 좌표. 선반 줄·꾸밈 받침·탁자와 안 겹치는 자리
  const wallOf = () => { const w = (K.ark || {}).memory_wall; return w && w.open ? w : null; };
  function wallCheck(st) {
    const w = st.memory_wall; if (!w || !w.open || !w.open_ko) return;
    const said = store.get('wall_open_said', false); if (said) return;
    store.set('wall_open_said', true); setTimeout(() => K.say(plain(w.open_ko)), 2000); D.log.push('wall open');
  }
  function wallLine(slot) {
    const w = wallOf(), r = roomAt(slot); if (!w || !r || r.id !== w.room) return '';
    const names = (w.slots || []).filter(Boolean).map(x => x.name).slice(0, 2);
    return '<p class="rcline mwline"><b>' + esc(plain(w.first_label_ko || '기억 벽')) + '</b> ' + (w.filled | 0) + '/' + (w.total || (w.slots || []).length) +
      (names.length ? ' · 「' + esc(names.join('」 「')) + '」' : '') + '</p>' +
      (w.complete ? '' : '<div class="rcbtns"><button data-mw="' + slot + '">' + esc(T('memory_wall.hang_label', {}, '여기 걸기')) + '</button></div>');
  }
  K.ext.wallLine = wallLine;
  function openWall(slot) {
    const w = wallOf(); if (!w) return;
    const ark = K.ark || {};
    const items = (ark.shelf || []).filter(x => x.card_id).map(x => ({ id: x.card_id, name: x.relic_name || x.name || '물건', where: '선반' }))
      .concat((ark.stored || []).map(x => ({ id: x.id || x.card_id, name: x.relic_name || x.name || '물건', where: '창고' })).filter(x => x.id)).slice(0, 12);
    const hooks = (w.slots || []).map((x, i) => '<li class="' + (x ? 'on' : '') + '"><i aria-hidden="true"></i>' + (x ? '「' + esc(x.name || '') + '」' + (x.from === 'first_given' && x.resident_name ? ' <small>' + esc(x.resident_name) + ' 님께 처음 드린 것</small>' : x.from === 'first_scan' ? ' <small>처음 찍은 것</small>' : '') : '<small>빈 고리</small>') + '</li>').join('');
    const body = K.panel('<h2>' + esc(plain(w.first_label_ko || '기억 벽')) + '</h2><p class="sub">' + (w.filled | 0) + '/' + (w.total || 4) + '</p>' +
      (w.prefilled_ko ? '<p class="desc">' + esc(plain(w.prefilled_ko)) + '</p>' : '') +
      '<ol class="mwhooks">' + hooks + '</ol>' +
      (w.complete ? (w.story ? w.story.map(l => '<p class="desc mwstory">' + esc(plain(l)) + '</p>').join('') : '') :
        '<h3>' + esc(plain(w.hang_prompt_ko || '어느 물건을 벽에 걸어 둘까요?')) + '</h3>' +
        (items.length ? '<div class="chips">' + items.map(x => '<button class="chip" data-mwi="' + esc(x.id) + '">' + esc(x.name) + ' <small>' + esc(x.where) + '</small></button>').join('') + '</div>'
                      : '<p class="desc">걸 물건이 선반에 없습니다. 무엇이든 찍어 오시면 됩니다.</p>')));
    body.classList.remove('busy');
    body.onclick = async (e) => {   // #panelBody 는 늘 같은 요소 — 덧붙이지 않고 바꿔 단다
      const b = e.target.closest('[data-mwi]'); if (!b || body.classList.contains('busy')) return;
      body.classList.add('busy');
      let r;
      try { r = await call('/api/memory_wall/hang', { relic_id: b.dataset.mwi }); }
      catch (err) { body.classList.remove('busy'); K.toast(err.message || '걸지 못했습니다'); return; }
      if (r.state) K.apply(r.state);
      if (r.memory_wall && K.ark) { K.ark.memory_wall = r.memory_wall; lastFull.memory_wall = r.memory_wall; }
      K.closePanel();
      if (r.line) K.toast(plain(r.line));
      D.log.push('wall hang ' + ((r.memory_wall || {}).filled || '') + (r.complete ? ' complete' : ''));
      body.classList.remove('busy'); body.onclick = null;
      if (r.complete) wallScene(r.complete_ko, r.story || []);
    };
    D.log.push('wall panel ' + items.length);
  }
  function wallScene(head, story) {
    const q = window.ARKBASE.queue ? window.ARKBASE.queue() : {};
    if (!$('#panel').hidden || $('.beatcard:not(.octwhere)') || q.busy) { setTimeout(() => wallScene(head, story), 1200); return; }   // 문어 카드는 기다리지 않는다
    const el = document.createElement('div'); el.className = 'beatcard scenecard wallscene';
    el.innerHTML = '<div class="phead"><i class="mwico" aria-hidden="true"></i><b>' + esc(plain(((K.ark || {}).memory_wall || {}).first_label_ko || '기억 벽')) + '</b></div>' +
      (head ? '<p class="sl sl-office" style="--i:0">' + esc(plain(head)) + '</p>' : '') +
      story.map((l, i) => '<p class="sl sl-narration" style="--i:' + (i + 1) + '">' + esc(plain(l)) + '</p>').join('') +
      '<div class="rowbtns"><button class="ok">그렇군요</button></div>';
    $('#base').appendChild(el);
    el.addEventListener('click', (e) => { if (e.target.closest('button.ok')) { el.classList.add('off'); setTimeout(() => el.remove(), 400); } });
    D.log.push('wall scene ' + story.length);
  }
  document.addEventListener('click', (e) => {
    const b = e.target.closest('button[data-mw]'); if (!b) return;
    e.stopPropagation(); openWall(+b.dataset.mw);
  }, true);
  const wallLog = {};
  D.wall = () => Object.assign({}, wallLog);
  function drawWall(room, slot, ix, iy, iw, ih, lit) {
    const w = wallOf(); if (!w || room.id !== w.room || K.z < 0.25) return;
    const ctx = K.ctx, kx = iw / ART.decCell[0], ky = ih / ART.decCell[1], drawn = [];
    ctx.save(); ctx.imageSmoothingEnabled = false; if (lit === false) ctx.globalAlpha = 0.6;
    { const [x0, y0] = MW_HOOKS[0], x1 = MW_HOOKS[MW_HOOKS.length - 1][0];                       // 고리를 단 가로 막대 — 선반 줄과 따로 읽히게
      ctx.fillStyle = '#4a3418'; ctx.fillRect(ix + (x0 - 16) * kx, iy + (y0 - 4) * ky, (x1 - x0 + 32) * kx, 3.5 * ky);
      ctx.fillStyle = 'rgba(232,201,138,.35)'; ctx.fillRect(ix + (x0 - 16) * kx, iy + (y0 - 4) * ky, (x1 - x0 + 32) * kx, 1 * ky); }
    (w.slots || []).slice(0, MW_HOOKS.length).forEach((x, i) => {
      const [hx, hy] = MW_HOOKS[i], cx = ix + hx * kx, top = iy + hy * ky;
      ctx.fillStyle = '#3a2a16'; ctx.fillRect(cx - 2.5 * kx, top - 3 * ky, 5 * kx, 4 * ky);          // 고리 못
      if (!x) { ctx.strokeStyle = 'rgba(205,185,138,.55)'; ctx.lineWidth = Math.max(1, 1.5 * kx); ctx.beginPath(); ctx.arc(cx, top + 4 * ky, 3.5 * kx, 0, Math.PI); ctx.stroke(); return; }
      const pid = x.prop || propIdOf(x), pi = pid && K.propImg(pid);
      ctx.strokeStyle = '#2a1e10'; ctx.lineWidth = Math.max(1, 1.2 * kx); ctx.beginPath(); ctx.moveTo(cx, top); ctx.lineTo(cx, top + 6 * ky); ctx.stroke();   // 끈
      if (!pi || !pi.ok1) return;
      const sc = 1.0 * kx, wpx = pi.x1.naturalWidth * sc, hpx = pi.x1.naturalHeight * sc;
      ctx.drawImage(pi.x1, cx - wpx / 2, top + 6 * ky, wpx, hpx);
      drawn.push(pid);
    });
    ctx.restore();
    wallLog[slot] = drawn;
  }
  // ══ S34 마음 단계 장면 · 편한 방 혼잣말 ══════════════════════════
  //  give effects.heart.level_up {level, fill_ko, scenes[{kind, announce, line, scene[]?, keepsake?}], deferred}
  //  deferred 면 /api/ark·/api/leaving 의 heart_scenes[] 로 한 번 온다. 카드는 한 번에 하나(다른 장면 카드가 닫힌 뒤)
  const heartSeen = store.get('heart_seen', []);
  function heartScene(rid, lu) {
    if (!lu || lu.deferred || !(lu.scenes || []).length) return;
    const key = rid + ':' + (lu.level || '');
    if (heartSeen.indexOf(key) >= 0) return;
    heartSeen.push(key); store.set('heart_seen', heartSeen.slice(-60));
    const show = () => {
      const q = window.ARKBASE.queue ? window.ARKBASE.queue() : {};
      if (!$('#scan').hidden || !$('#panel').hidden || $('.beatcard:not(.octwhere)') || $('.leavecard') || q.busy) { setTimeout(show, 1500); return; }
      const p = personById(rid);
      const rows = [];
      if (lu.fill_ko) rows.push({ who: 'office', text: lu.fill_ko });
      lu.scenes.forEach(sc => {
        if (sc.announce) rows.push({ who: 'office', text: sc.announce });
        (sc.scene || []).forEach(t => rows.push({ who: 'narration', text: t }));
        if (sc.line) rows.push({ who: 'line', text: sc.line });
      });
      const el = document.createElement('div'); el.className = 'beatcard scenecard heartscene';
      el.innerHTML = '<div class="phead">' + face(p, 36) + '<b>' + esc((p ? p.name + ' · ' : '') + '마음 ' + (lu.level || '') + '칸') + '</b>' + (K.ext.heartRow ? '' : '') + '</div>' +
        rows.map((r, i) => r.who === 'line' ? '<p class="bline" style="--i:' + i + '">「' + esc(plain(r.text)) + '」</p>' : '<p class="sl sl-' + r.who + '" style="--i:' + i + '">' + esc(plain(r.text)) + '</p>').join('') +
        '<div class="rowbtns"><button class="ok">그렇군요</button></div>';
      rows.forEach(r => { const k = normT(r.text); if (k) cardSaid.add(k); });   // 카드가 말한 것은 방송으로 다시 하지 않는다
      $('#base').appendChild(el);
      el.addEventListener('click', (e) => { if (e.target.closest('button.ok')) { el.classList.add('off'); setTimeout(() => el.remove(), 400); } });
      D.log.push('heart scene ' + key + ' ' + lu.scenes.map(x => x.kind).join(','));
    };
    setTimeout(show, 1600);
  }
  K.ext.heartScene = heartScene;
  // S35 방 소식(room_news[] 한 번만: 방 종류 열림 · 머물 칸 없음) · 살림이 바닥일 때 한 줄(household_note)
  function newsCheck(st) {
    const said = store.get('news_said', []);
    (st.room_news || []).forEach(n => { const k = (n.kind || '') + '|' + (n.room_id || n.guest_id || '') + '|' + (n.resident_id || ''); if (!n.ko || said.indexOf(k) >= 0) return;
      said.push(k); store.set('news_said', said.slice(-60)); setTimeout(() => K.say(plain(n.ko)), 1800); D.log.push('news ' + n.kind); });
    if (st.household_note) { const k = 'hh|' + (st.day || '') + '|' + st.household_note; if (said.indexOf(k) < 0) { said.push(k); store.set('news_said', said.slice(-60)); setTimeout(() => K.say(plain(st.household_note)), 2400); D.log.push('household note'); } }
  }
  function heartCheck(st) {
    (st.heart_scenes || []).forEach(h => heartScene(h.resident_id || h.rid, h.scenes ? Object.assign({}, h, { deferred: false }) : { level: h.level, fill_ko: h.fill_ko, scenes: [h], deferred: false }));
    const ms = st.comfort_mutters || [], said = store.get('mutter_said', []);
    ms.forEach(m => { const k = (m.resident_id || '') + '|' + (st.day || '') + '|' + (m.line || ''); if (!m.line || said.indexOf(k) >= 0) return;
      said.push(k); store.set('mutter_said', said.slice(-40)); setTimeout(() => K.say(plain((m.name ? m.name + ' 님 혼잣말: ' : '') + '「' + m.line + '」')), 2600); D.log.push('mutter ' + m.resident_id); });
  }
  function firstScene(lines) {
    const q = window.ARKBASE.queue ? window.ARKBASE.queue() : {};
    if (!$('#scan').hidden || !$('#panel').hidden || $('.beatcard') || q.busy || (q.wait || []).length) { setTimeout(() => firstScene(lines), 1500); return; }
    const el = document.createElement('div'); el.className = 'beatcard scenecard';
    el.innerHTML = '<div class="phead"><i class="doorico" aria-hidden="true"></i><b>' + esc(T('expedition.first_scene_title', {}, '문간 문')) + '</b></div>' +
      lines.map((l, i) => '<p class="sl sl-' + esc(l.who || 'narration') + '" style="--i:' + i + '">' + esc(plain(l.text || '')) + '</p>').join('') +
      '<div class="rowbtns">' + (K.ext.openSendOff && unlocked('expedition') ? '<button class="on" data-send="1">' + esc(T('expedition.first_scene_go', {}, '내보내기')) + '</button>' : '') + '<button class="ok">그렇군요</button></div>';
    $('#base').appendChild(el);
    const close = () => { el.classList.add('off'); setTimeout(() => el.remove(), 400); };
    el.addEventListener('click', (e) => { if (e.target.closest('[data-send]')) { close(); K.ext.openSendOff(); } else if (e.target.closest('button.ok')) close(); });
    D.log.push('first_scene ' + lines.length);
  }
  // S23 저녁 귀띔(notebook_tip) — 그사이 패널에 실렸으면 건너뛰고, 아니면 방송 한 줄(한 번만)
  function tipCheck(st) {
    const tp = st.notebook_tip; if (!tp || !tp.line) return;
    const key = 'tip|' + tp.day + '|' + tp.resident_id + '|' + tp.slot;
    const said = store.get('tips_said', []); if (said.indexOf(key) >= 0) return;
    said.push(key); while (said.length > 30) said.shift(); store.set('tips_said', said);
    setTimeout(() => { if ((K.ext.ovShown || []).indexOf(plain(tp.line)) >= 0) return; K.say(plain(tp.line)); D.log.push('tip say'); }, 3000);
  }
  // S23 받는 저녁 · 한 상(evening_table) — 저녁 첫 세션에 작은 카드 하나. 상에 올릴 물건 하나 + 마주 앉힐 두 분 → POST /api/table
  let tableShown = false;
  function tableCheck(st) {
    const et = st.evening_table;
    if (!et || !et.open || tableShown || !unlocked('evening_table')) return;
    if (store.get('table_day', null) === st.day) return;          // 오늘 닫았으면 다시 띄우지 않는다(≡ 「한 상」으로는 언제나)
    tableShown = true; setTimeout(() => openTable(et), 2500);
  }
  function openTable(et) {
    et = et || (K.ark || {}).evening_table;
    if (!et || !et.open) { K.toast(et && et.done_today ? '오늘은 이미 한 상을 차렸습니다.' : '지금은 한 상을 차릴 수 없습니다.'); return; }
    const show = () => {
      const q = window.ARKBASE.queue ? window.ARKBASE.queue() : {};
      if (!$('#scan').hidden || !$('#panel').hidden || $('.beatcard') || $('.leavecard') || q.busy || (q.wait || []).length) { setTimeout(show, 1500); return; }
      const items = ((et.candidates || {}).items || []).slice(0, 6), ppl = ((et.candidates || {}).residents || []);
      const ret = (et.returned || []).map(x => x.to_name ? '「' + x.name + '」 → ' + x.to_name + ' 님' : x.name + (x.room ? ' · ' + x.room : '')).slice(0, 4);
      const pick = { item: items[0] ? items[0].relic_id : null, seats: [] };
      const el = document.createElement('div'); el.className = 'beatcard tablecard';
      const draw = () => {
        el.innerHTML = '<div class="phead"><i class="tableico" aria-hidden="true"></i><b>' + esc(et.daytime ? T('daytime_table.title', {}, '낮 상') : T('evening.title', {}, '한 상')) + '</b></div>' +   // S27 낮 세션이면 낮 상
          '<p class="bcast">' + esc(plain(et.open_ko || '')) + '</p>' + (ret.length ? '<p class="tret">' + ret.map(esc).join('<br>') + '</p>' : '') +
          '<p class="bask">' + esc(plain(et.table_prompt || '상에 무엇을 올릴까요?')) + '</p>' +
          (items.length ? '<div class="chips">' + items.map(x => '<button class="chip' + (pick.item === x.relic_id ? ' on' : '') + '" data-ti="' + esc(x.relic_id) + '">' + esc(x.name) + (x.today ? ' <small>오늘</small>' : '') + '</button>').join('') + '</div>'
                        : '<p class="rvhow">올릴 물건이 선반에 없습니다. 상만 차려도 됩니다.</p>') +
          '<p class="bask">' + esc(plain(et.seat_prompt || '누구 옆에 누구를 앉힐까요?')) + '</p>' +
          '<div class="chips">' + ppl.map(x => '<button class="chip' + (pick.seats.indexOf(x.id) >= 0 ? ' on' : '') + '" data-ts="' + esc(x.id) + '">' + face(personById(x.id) || x, 22) + ' ' + esc(x.name) + '</button>').join('') + '</div>' +
          '<div class="rowbtns"><button class="on" data-go="1"' + (pick.seats.length === 2 ? '' : ' disabled') + '>상 차리기</button><button class="ok">오늘은 됐어요</button></div>';
      };
      draw(); $('#base').appendChild(el);
      const close = () => { store.set('table_day', (K.ark || {}).day); el.classList.add('off'); setTimeout(() => el.remove(), 400); };
      el.addEventListener('click', async (e) => {
        const ti = e.target.closest('[data-ti]'), ts = e.target.closest('[data-ts]'), go = e.target.closest('[data-go]');
        if (ti) { pick.item = ti.dataset.ti; draw(); return; }
        if (ts) { const i = pick.seats.indexOf(ts.dataset.ts); if (i >= 0) pick.seats.splice(i, 1); else { pick.seats.push(ts.dataset.ts); if (pick.seats.length > 2) pick.seats.shift(); } draw(); return; }
        if (go) {
          go.disabled = true;
          let r;
          try { r = await call(API.table, Object.assign({ seats: [pick.seats.slice()] }, pick.item ? { relic_id: pick.item } : {})); }
          catch (err) { go.disabled = false; K.toast(err.message || '상을 차리지 못했습니다'); return; }
          if (r.state) K.apply(r.state);
          const talk = (r.talk || []).map(x => '<p class="bline"><b>' + esc(x.name || '') + '</b> 「' + esc(plain(x.line || '')) + '」</p>').join('');
          el.innerHTML = '<div class="phead"><i class="tableico" aria-hidden="true"></i><b>' + esc((r.names || []).join(' · ')) + '</b>' +
            (r.trust_delta ? '<em class="trustup">마음 +' + r.trust_delta + (r.liked_by && r.liked_by.length ? ' · 좋아하는 물건' : '') + '</em>' : '') + '</div>' +
            (r.item ? '<p class="bcast">상에 「' + esc(txt(r.item)) + '」' + (r.food_paid || r.table_store_paid ? ' · 식량 ' + ((r.food_paid || 0) + (r.table_store_paid || 0)) : '') + '</p>' : '') + talk +
            (r.promise ? '<p class="tpromise">' + esc(plain(txt(r.promise))) + '</p>' : '') +
            '<div class="rowbtns"><button class="ok">그렇군요</button></div>';
          D.log.push('table ' + (r.trust_delta || 0) + (r.promise ? ' promise' : '') + (r.daytime || et.daytime ? ' daytime' : ''));
          return;
        }
        if (e.target.closest('button.ok')) close();
      });
      D.log.push('tablecard ' + items.length + '/' + ppl.length);
    };
    show();
  }
  // ≡ 「한 상」 · 「늘 이름표 보기」(prefs.labels_always)
  (() => {
    const mb = $('#menu .mbtns'); if (!mb) return;
    const t = document.createElement('button'); t.className = 'sw'; t.id = 'tablebtn'; t.textContent = '한 상';
    t.addEventListener('click', () => { K.closeMenu(); openTable(); }); mb.appendChild(t);
    const b = document.createElement('button'); b.className = 'sw'; b.id = 'labelsbtn';
    const paint = () => { const on = !!(((K.ark || {}).prefs || {}).labels_always); b.textContent = '늘 이름표 보기 · ' + (on ? '켬' : '끔'); b.classList.toggle('on', on); };
    b.addEventListener('click', async () => {
      const on = !(((K.ark || {}).prefs || {}).labels_always);
      try { const r = await call(API.prefs, { labels_always: on }); if (K.ark) K.ark.prefs = r.prefs || { labels_always: on }; paint(); K.toast(plain(r.label_ko || (on ? '이제 늘 이름표를 붙여 드립니다.' : '이름표를 떼었습니다. 기색으로 읽어 주세요.'))); D.log.push('prefs ' + on); }
      catch (err) { K.toast(err.message || '바꾸지 못했습니다'); }
    });
    mb.appendChild(b); K.onApply(paint);
  })();
  K.ext.core = { afterReveal, morningExtra, hasMorning, queueBeat, leaveCard, regift, heirFromShelf };
  // /api/ark 에만 오는 키(방문·떠날 때 약속·오늘의 비트·세션)는 다른 응답의 state(public_state)에 없다 — 지난 값을 이어 쓴다
  const lastFull = {};
  K.onApply((st) => {
    if (D.mock) D.mock.decorate(st);                        // ★ 시험대: 서버 모양을 먼저 입힌다
    ['visits', 'next_visit', 'beat_today', 'session', 'visitors_book', 'decor_trace', 'missed_chain', 'prefs', 'evening_table', 'tomorrow_ask', 'unlocked', 'memory_wall', 'leave_order'].forEach(k => { if (st[k] === undefined) { if (lastFull[k] !== undefined) st[k] = lastFull[k]; } else lastFull[k] = st[k]; });
    computeGather(st);
    unlockCheck(st);
    sayUnlockNew(st.unlock_new, 'ark');
    noveltyCheck(st);
    tipCheck(st);
    tableCheck(st);
    wallCheck(st);
    heartCheck(st);
    newsCheck(st);
    octWhere(st);
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
  D.heirRow = (r) => heirloomRow(r);   // ★ 검수용
  D.leaveCard = leaveCard; D.react = react; D.pop = pop; D.queueBeat = (b) => { beatShown = 0; queueBeat(b); };   // ★ 검수용
})();
