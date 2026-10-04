/* 잔해 방주 — 거점 화면의 원정·문간 층 (S15-B, 클라이언트만)
 *
 * 계약: docs/API_EXPEDITION.md(S15-A). 사양: docs/EXPEDITION.md. 문장: data/expedition_text.json(키 고정).
 * 하는 일: 문간 활동(이름표·눌러서 설명), 손님(두드림·의자·손님 카드), 원정 보내기(사람 1~2·길이·목적지·미리 보기·공기),
 *          나가 있는 동안 위 한 줄 표시, 귀환(해치·방송·가져온 것 카드), 봉인 상자(문간 바닥·카드·억지로 열기·찍기로 열림).
 * 화면은 숫자를 계산하지 않는다(D2) — 미리 보기·확률·시각은 전부 서버 값.
 * 서버가 아직 이 계약을 다 올리지 않았으면 각 기능이 조용히 꺼진다(404 를 부르지 않도록 /api/ark 의 필드로 먼저 판단).
 */
(() => {
  'use strict';
  const K = window.ARKBASE && window.ARKBASE._k;
  if (!K) return;
  const $ = (s) => document.querySelector(s);
  const esc = K.esc;
  const X = window.ARKEXP = { log: [] };              // ★ 검수용 읽기 창
  const store = {
    get(k, d) { try { const v = localStorage.getItem('ark_' + K.uid + '_' + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem('ark_' + K.uid + '_' + k, JSON.stringify(v)); } catch (e) { /* 화면은 돈다 */ } },
  };
  const announce = (l) => { if (l) K.toast(l); };
  const pick = (arr, seed) => (Array.isArray(arr) ? arr[Math.abs(hash(String(seed))) % arr.length] : arr) || '';
  function hash(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h | 0; }

  // ── 문장: 서버가 expedition_text.json 을 내주는 길(계약 미정 — 보고서 참고). /api/text/moments 에 묶여 오면 그것을 쓴다 ──
  let TX = {};
  function TT(key, vars, fb) {
    let o = TX;
    for (const k of key.split('.')) { if (o == null) break; o = o[k]; }
    if (Array.isArray(o)) o = pick(o, key + '|' + (K.ark && K.ark.day) + '|' + JSON.stringify(vars || {}));
    return K.fill(typeof o === 'string' ? o : (fb || ''), vars);
  }
  function loadText() {
    K.api('/api/text/moments').then(j => {
      // 시나리오 S15 문장이 같은 묶음에 들어 있으면(entrance·guest·expedition·sealed_box·spot) 쓴다
      if (j && (j.expedition || j.entrance || j.sealed_box)) TX = j;
      else if (j && j.expedition_text) TX = j.expedition_text;
    }).catch(() => {});
  }
  X.textReady = () => !!(TX.expedition || TX.entrance);

  const ACT_KEY = { hand: 'repair', eye: 'lookout', breath: 'pump', nerve: 'welcome' };
  const ACT_FB = { hand: '수선', eye: '망보기', breath: '공기 펌프', nerve: '마중', waiting: '기다림' };
  const CAT_KO = { food: '식품', drink: '음료', medical: '의약', electronics: '전자', stationery: '문구', book: '도서', apparel: '의류', tobacco: '담배·주류' };
  const RES_KO = K.RES_KO;
  const has = () => !!(K.ark && (K.ark.entrance || K.ark.expedition !== undefined || K.ark.boxes || K.ark.air));

  // ══════════════════════════════════════════════════════════════
  //  1. 문간 — /api/entrance (사람·활동·기다리는 친구·손님·잠자리·잠수복·공기)
  // ══════════════════════════════════════════════════════════════
  let ent = null, entAt = 0;
  async function loadEntrance(force) {
    if (!has()) return;
    if (!force && performance.now() - entAt < 15000) return;
    entAt = performance.now();
    const prevGuests = (ent && ent.guests || []).map(g => g.id);
    try { ent = await K.api('/api/entrance?uid=' + encodeURIComponent(K.uid)); } catch (e) { ent = null; return; }
    // 새 손님: 두드림이면 해치·방송(3일째 첫 두드림은 특별 문장), 구조면 귀환 쪽에서 이미 말했다
    const fresh = (ent.guests || []).filter(g => prevGuests.indexOf(g.id) < 0 && !store.get('guest_seen_' + g.id, false));
    fresh.forEach(g => {
      store.set('guest_seen_' + g.id, true);
      if (g.src === 'knock') {
        if (window.ARKBASE.hatchCycle) window.ARKBASE.hatchCycle(1800);
        const first = !store.get('knock_first_done', false);
        store.set('knock_first_done', true);
        announce(first ? TT('guest.knock_first', {}, '관리실에서 알려 드립니다. 문간 유리를 누가 두 번 두드렸습니다. 바깥에서 온 손님입니다.')
                       : TT('guest.knock', {}, '문간 유리에서 똑똑 소리가 났습니다. 손님이 오셨습니다.'));
        X.log.push('knock ' + g.id);
      }
    });
  }
  const personById = (id) => (K.ark.residents_list || []).find(r => r.id === id);
  K.ext.podAct = (id) => {
    const p = ent && (ent.people || []).find(x => x.id === id);
    return p ? (p.waiting_for ? 'waiting' : p.activity) : null;
  };
  K.ext.podLabel = (act) => (ACT_KEY[act] ? TT('entrance.activities.' + ACT_KEY[act] + '.label', {}, ACT_FB[act]) : (act === 'waiting' ? ACT_FB.waiting : ''));
  K.ext.podCaption = (id) => {
    const act = K.ext.podAct(id); if (!act) return '';
    if (act === 'waiting') {
      const p = (ent.people || []).find(x => x.id === id), f = personById(p.waiting_for);
      const late = expedition && expedition.returns_at && expedition.now > expedition.returns_at;
      return TT(late ? 'entrance.waiting_friend.late' : 'entrance.waiting_friend.lines', { friend: (personById(id) || {}).name, name: f && f.name },
                TT('entrance.waiting_friend.caption', {}, ''));
    }
    return ACT_KEY[act] ? TT('entrance.activities.' + ACT_KEY[act] + '.caption', {}, '') : '';
  };
  K.ext.guests = () => (ent && ent.guests) || [];

  // ── 손님 카드: 들이기 / 다른 돔 안내. 잠자리가 없으면 그 말만(재촉 없음) ──
  K.ext.onGuest = (gid) => {
    const g = (ent && ent.guests || []).find(x => x.id === gid); if (!g) return;
    const beds = ent.beds || {}, ko = (K.ark.stats_meta || {}).ko || { hand: '손', eye: '눈', breath: '숨', nerve: '담' };
    const by = (g.rescued_by || []).map(id => (personById(id) || {}).name).filter(Boolean).join(', ');
    const body = K.panel('<h2>' + esc(TT('guest.card.title', {}, '문간의 손님')) + '</h2>' +
      '<p class="sub">' + esc(g.name) + ' · ' + esc(g.role_ko || g.role || '') + '</p>' +
      '<p class="desc">' + esc(TT('entrance.guest_bench', {}, '')) + '</p>' +
      (by ? '<p class="reclaim">' + esc(TT('guest.card.brought_by', { name: by }, '데려온 사람: ' + by + ' 님')) + '</p>' : '') +
      '<div class="snum">' + Object.keys(ko).map(k => '<span class="sn"><i>' + esc(ko[k]) + '</i><b>' + esc((g.stats || {})[k] || 0) + '</b></span>').join('') + '</div>' +
      (g.quirk && g.quirk.ko ? '<em class="quirk">' + esc(g.quirk.ko) + '</em>' : '') +
      (beds.free > 0 ? '<p class="evhint">빈 잠자리 ' + beds.free + ' / ' + beds.total + '</p>'
                     : '<p class="lost">' + esc(TT('guest.no_bed', {}, '지금은 잠자리가 다 차 있습니다. 거주실을 넓히시면 그때 모시면 됩니다.')) + '</p>') +
      '<div class="rowbtns"><button id="gAccept" class="on"' + (beds.free > 0 ? '' : ' disabled') + '>' + esc(TT('guest.card.accept_label', {}, '들이기')) + '</button>' +
      '<button id="gGuide">' + esc(TT('guest.card.guide_label', {}, '다른 돔 안내')) + '</button></div>');
    body.querySelector('#gAccept').addEventListener('click', () => guestDecide(g, true));
    body.querySelector('#gGuide').addEventListener('click', () => guestDecide(g, false));
  };
  async function guestDecide(g, accept) {
    try {
      const r = await K.api('/api/entrance/guest', { guest_id: g.id, accept });
      if (r.state) K.apply(r.state);
      announce(accept ? TT('guest.accept', { guest: g.name, role: g.role_ko || '' }, g.name + ' 님이 오늘부터 이 집 주민이 되셨습니다.')
                      : TT('guest.card.guide_line', {}, '가까운 돔 쪽 길을 알려 드렸습니다.'));
      K.closePanel(); await K.reload(); await loadEntrance(true);
      X.log.push('guest ' + (accept ? 'accepted ' : 'guided ') + g.id);
    } catch (e) { K.toast(e.message || '정하지 못했습니다'); }
  }

  // ══════════════════════════════════════════════════════════════
  //  2. 원정 보내기 — /api/expedition/options → preview → start
  // ══════════════════════════════════════════════════════════════
  let opts = null, sel = { members: [], dest: null, length: null }, preview = null;
  const LEN_KEY = { short: 'short', half: 'half', long: 'overnight' };
  async function openSendOff(preset) {
    K.closeMenu();
    const body = K.panel('<h2>' + esc(TT('expedition.send_title', {}, '내보내기')) + '</h2><p class="sub">불러오는 중입니다</p>');
    try { opts = await K.api('/api/expedition/options?uid=' + encodeURIComponent(K.uid)); }
    catch (e) { body.innerHTML = '<h2>내보내기</h2><p class="lost">' + esc(e.message || '지금은 내보낼 수 없습니다') + '</p>'; return; }
    if (opts.out) { openStatus(); return; }
    const okDest = (opts.dests || []).filter(d => d.can);
    sel = { members: preset ? [preset] : [], dest: (okDest[0] || {}).dest || null, length: null };
    const d0 = okDest[0]; if (d0) sel.length = d0.lengths.find(l => (opts.lengths[l] || {}).can) || d0.lengths[0];
    preview = null;
    renderSendOff();
    refreshPreview();
  }
  function stationOf(id) {                             // 그 사람이 지금 지키는 방(방어 대가)
    const s = K.cb && K.cb.stations && K.cb.stations[id];
    if (s === undefined) return null;
    const room = (K.ark.rooms || []).find(r => r.slot === s);
    return room ? ((K.catalog[room.id] || {}).name || room.id) : null;
  }
  function renderSendOff() {
    const ko = (K.ark.stats_meta || {}).ko || { hand: '손', eye: '눈', breath: '숨', nerve: '담' };
    const air = opts.air || {}, raid = K.cb && K.cb.raid && !K.cb.raid.resolved && K.cb.raid.stage !== 'done' ? K.cb.raid : null;
    let h = '<h2>내보내기</h2>' +
      '<p class="sub">공기 ' + esc(air.value) + ' / ' + esc(air.supply) + ' · 잠수복 ' + esc((opts.suits || {}).usable) + '벌' + (opts.tutorial ? ' · 첫 원정은 문 앞만' : '') + '</p>' +
      '<div class="airbar"><i style="width:' + Math.round(100 * Math.min(1, air.band || 0)) + '%"></i>' +
      (preview && preview.air_after != null ? '<b style="left:' + Math.round(100 * Math.max(0, preview.air_after) / Math.max(1, air.supply || 1)) + '%"></b>' : '') + '</div>';
    const su = opts.suits || {};
    if ((su.wear || []).some(w => w >= (su.wear_limit || 5)))          // 마모가 한계인 공용 잠수복 — 고쳐야 나간다
      h += '<p class="rno">잠수복 하나가 많이 닳았습니다.' + (su.repair_cost ? ' 고치는 데 ' + Object.entries(su.repair_cost).map(([k, v]) => (RES_KO[k] || k) + ' ' + v).join(', ') + '이 듭니다.' : '') +
           ' <button id="xpSuit" class="chip">잠수복 고치기</button></p>';
    h += '<h3>누가 (1~2분)</h3><div class="blist">' + (opts.residents || []).map(r => {
      const on = sel.members.indexOf(r.id) >= 0, st = r.stats || {}, def = stationOf(r.id);
      return '<button class="bopt pick' + (on ? ' on' : '') + (r.can ? '' : ' lack') + '" data-mem="' + esc(r.id) + '"' + (r.can ? '' : ' disabled') + '><b>' + esc(r.name) + ' 님' +
        '<span class="bstat">' + ['breath', 'eye', 'nerve', 'hand'].map(k => esc(ko[k]) + ' ' + (st[k] || 0)).join(' · ') + '</span></b>' +
        '<small>' + esc(r.can ? (def ? def + '을 지키고 계십니다' + (raid ? ' — 나가면 이 방은 그만큼 약해집니다' : '') : '자리 없음 · 문간') : (r.why || '나갈 수 없습니다')) + '</small></button>';
    }).join('') + '</div>';
    h += '<h3>어디로</h3><div class="chips">' + (opts.dests || []).map((d, i) =>
      '<button class="chip' + (JSON.stringify(d.dest) === JSON.stringify(sel.dest) ? ' on' : '') + '" data-dest="' + i + '"' + (d.can ? '' : ' disabled title="' + esc(d.why || '') + '"') + '>' + esc(d.ko) + '</button>').join('') + '</div>';
    const dsel = (opts.dests || []).find(d => JSON.stringify(d.dest) === JSON.stringify(sel.dest));
    h += '<h3>얼마나</h3><div class="chips">' + Object.keys(opts.lengths || {}).map(l => {
      const L = opts.lengths[l], allowed = L.can && (!dsel || dsel.lengths.indexOf(l) >= 0);
      return '<button class="chip' + (sel.length === l ? ' on' : '') + '" data-len="' + l + '"' + (allowed ? '' : ' disabled title="' + esc(L.why || '이 목적지에는 안 됩니다') + '"') + '>' +
        esc(TT('expedition.lengths.' + LEN_KEY[l] + '.label', {}, L.ko)) + ' <small>' + esc(TT('expedition.lengths.' + LEN_KEY[l] + '.time', {}, L.minutes >= 60 ? (L.minutes / 60) + '시간' : L.minutes + '분')) + '</small></button>';
    }).join('') + '</div>';
    if (sel.length) h += '<p class="desc">' + esc(TT('expedition.lengths.' + LEN_KEY[sel.length] + '.desc', {}, '')) + '</p>';
    h += '<div id="xpPrev">' + previewHtml() + '</div>';
    const errs = (preview && preview.errors) || [];
    h += '<div class="rowbtns"><button id="xpGo" class="on"' + (sel.members.length && sel.dest && sel.length && preview && !errs.length ? '' : ' disabled') + '>내보내기</button></div>';
    const body = K.panel(h);
    body.querySelectorAll('button[data-mem]').forEach(b => b.addEventListener('click', () => {
      const id = b.dataset.mem, i = sel.members.indexOf(id);
      if (i >= 0) sel.members.splice(i, 1); else { sel.members.push(id); if (sel.members.length > 2) sel.members.shift(); }
      renderSendOff(); refreshPreview();
    }));
    body.querySelectorAll('button[data-dest]').forEach(b => b.addEventListener('click', () => {
      const d = opts.dests[+b.dataset.dest]; sel.dest = d.dest;
      if (d.lengths.indexOf(sel.length) < 0) sel.length = d.lengths.find(l => (opts.lengths[l] || {}).can) || d.lengths[0];
      renderSendOff(); refreshPreview();
    }));
    body.querySelectorAll('button[data-len]').forEach(b => b.addEventListener('click', () => { sel.length = b.dataset.len; renderSendOff(); refreshPreview(); }));
    body.querySelector('#xpGo').addEventListener('click', startExpedition);
    const sb2 = body.querySelector('#xpSuit');
    if (sb2) sb2.addEventListener('click', async () => {
      try { const r = await K.api('/api/entrance/suit_repair', {}); if (r.state) K.apply(r.state); announce(K.plain(r.ko || '잠수복을 고쳤습니다.')); openSendOff(); }
      catch (e) { K.toast(e.message || '고치지 못했습니다'); }
    });
  }
  function previewHtml() {
    if (!preview) return '<p class="sub">' + (sel.members.length ? '미리 보는 중입니다' : '나갈 분을 골라 주세요') + '</p>';
    const pl = (k, fb) => esc(TT('expedition.preview_labels.' + k, {}, fb));
    const pct = (v) => Math.round((v || 0) * 100) + '%';
    const d = preview.danger || {};
    return '<div class="kv xpkv"><span>' + pl('actions', '줍는 횟수') + ' <b>' + esc(preview.actions) + '</b></span>' +
      '<span>' + pl('carry', '들고 올 양') + ' <b>' + esc(preview.carry) + '</b></span>' +
      '<span>공기 <b>−' + esc(preview.air_cost) + '</b> → ' + esc(preview.air_after) + '</span>' +
      '<span>' + pl('risk', '위험') + ' <b>' + pct(d.p) + '</b></span>' +
      (preview.discover_p ? '<span>찾을 확률 <b>' + pct(preview.discover_p) + '</b></span>' : '') +
      (preview.rescue_p ? '<span>사람을 만날 확률 <b>' + pct(preview.rescue_p) + '</b></span>' : '') +
      '<span>돌아오는 시각 <b>' + esc(clock(preview.returns_at)) + '</b></span></div>' +
      (d.kinds || []).slice(0, 4).map(k => '<p class="xpdanger">' + esc(k.ko) + ' · ' + esc(((K.ark.stats_meta || {}).ko || {})[k.stat] || k.stat) + '으로 넘길 확률 ' + pct(k.p_pass) + '</p>').join('') +
      (preview.warnings || []).map(w => '<p class="rno">' + esc(K.plain(w)) + '</p>').join('') +
      (preview.errors || []).map(w => '<p class="lost">' + esc(K.plain(w)) + '</p>').join('');
  }
  let pvSeq = 0;
  async function refreshPreview() {
    if (!sel.members.length || !sel.dest || !sel.length) { preview = null; const el = $('#xpPrev'); if (el) el.innerHTML = previewHtml(); return; }
    const my = ++pvSeq;
    try { const r = await K.api('/api/expedition/preview', { members: sel.members, dest: sel.dest, length: sel.length }); if (my !== pvSeq) return; preview = r; }
    catch (e) { if (my !== pvSeq) return; preview = { errors: [e.message || '미리 볼 수 없습니다'] }; }
    renderSendOff();
  }
  function clock(ts) { if (!ts) return '—'; const d = new Date(ts * 1000); return d.getHours() + '시 ' + String(d.getMinutes()).padStart(2, '0') + '분'; }
  async function startExpedition() {
    let r;
    try { r = await K.api('/api/expedition/start', { members: sel.members, dest: sel.dest, length: sel.length }); }
    catch (e) { K.toast(e.message || '내보내지 못했습니다'); return; }
    if (r.state) K.apply(r.state);
    expedition = r.expedition || null;
    const names = namesOf(expedition);
    if (window.ARKBASE.hatchCycle) window.ARKBASE.hatchCycle(2200);
    K.play('sfx_airlock_cycle.ogg', 0.5);
    announce(TT('expedition.send_off', { name: names, dest: expedition && expedition.dest_ko, return_at: clock(expedition && expedition.returns_at) },
                '관리실에서 알려 드립니다. ' + names + ' 님이 나가십니다.'));
    X.log.push('start ' + (expedition && expedition.id));
    // 따라 나가기 / 보내 두기
    const body = K.panel('<h2>' + esc(names) + ' 님이 나가십니다</h2><p class="sub">' + esc(expedition && expedition.dest_ko) + ' · ' + esc(clock(expedition && expedition.returns_at)) + ' 귀환</p>' +
      '<p class="desc">' + esc(TT('expedition.follow.start', {}, '')) + '</p>' +
      '<div class="rowbtns"><button id="xpFollow" class="on">' + esc(TT('expedition.follow.label', {}, '따라 나가기')) + '</button>' +
      '<button id="xpLeave">' + esc(TT('expedition.leave_it_label', {}, '보내 두기')) + '</button></div>');
    body.querySelector('#xpFollow').addEventListener('click', followOut);
    body.querySelector('#xpLeave').addEventListener('click', () => { K.closePanel(); announce(TT('expedition.leave_it_line', { name: names }, names + ' 님께 맡겨 두겠습니다.')); });
    renderChip();
  }
  function followOut() {
    if (!expedition) return;
    location.href = '/static/expedition.html?uid=' + encodeURIComponent(K.uid) + '&exp=' + encodeURIComponent(expedition.id);
  }
  const namesOf = (e) => ((e && e.member_names) || []).join(' 님과 ');
  K.ext.openSendOff = openSendOff;
  const sb = $('#sendbtn'); if (sb) sb.addEventListener('click', () => openSendOff());
  X.openSendOff = openSendOff;

  // ══════════════════════════════════════════════════════════════
  //  3. 나가 있는 동안 — 위 한 줄의 작은 표시(누가·몇 시 귀환). 누르면 상태 카드(불러들이기)
  // ══════════════════════════════════════════════════════════════
  let expedition = null;
  K.ext.expMembers = () => (expedition && expedition.members) || [];
  function renderChip() {
    const b = $('#xpbtn'); if (!b) return;
    b.hidden = !expedition;
    if (!expedition) return;
    const late = expedition.now && expedition.returns_at && expedition.now > expedition.returns_at;
    $('#xpline').textContent = K.fill(namesOf(expedition) + ' 님 · ' + (late ? '늦어짐' : clock(expedition.returns_at)));
    b.style.setProperty('--p', Math.round(100 * Math.min(1, expedition.progress || 0)) + '%');
  }
  function openStatus() {
    const e = expedition; if (!e) return;
    const body = K.panel('<h2>' + esc(namesOf(e)) + ' 님 · 바깥</h2><p class="sub">' + esc(e.dest_ko || '') + ' · ' + esc(clock(e.returns_at)) + ' 귀환' + (e.recalled ? ' · 불러들이는 중' : '') + '</p>' +
      '<div class="airbar"><i style="width:' + Math.round(100 * Math.min(1, e.progress || 0)) + '%"></i></div>' +
      '<div class="rowbtns">' + (e.scene && e.scene.open ? '<button id="xpFollow" class="on">' + esc(TT('expedition.follow.label', {}, '따라 나가기')) + '</button>' : '<button id="xpFollow">들여다보기</button>') +
      (e.recalled ? '' : '<button id="xpRecall">불러들이기</button>') + '</div>');
    body.querySelector('#xpFollow').addEventListener('click', followOut);
    const rb = body.querySelector('#xpRecall');
    if (rb) rb.addEventListener('click', async () => {
      try { const r = await K.api('/api/expedition/recall', {}); if (r.state) K.apply(r.state); expedition = r.expedition || expedition;
            announce('관리실에서 알려 드립니다. ' + namesOf(expedition) + ' 님을 불러들이고 있습니다. ' + clock(r.arrives_at) + '쯤 도착하십니다.'); openStatus(); }
      catch (er) { K.toast(er.message || '불러들이지 못했습니다'); }
    });
  }
  $('#xpbtn') && $('#xpbtn').addEventListener('click', openStatus);

  // ══════════════════════════════════════════════════════════════
  //  4. 귀환 — 해치 → 방송 → 가져온 것 카드 → seen
  // ══════════════════════════════════════════════════════════════
  let shownReturn = null;
  function showReturn(ret) {
    if (!ret || shownReturn === ret.id) return;
    shownReturn = ret.id;
    const names = (ret.member_names || ret.members || []).map(m => (typeof m === 'string' ? ((personById(m) || {}).name || m) : m.name)).join(' 님과 ');
    if (window.ARKBASE.hatchCycle) window.ARKBASE.hatchCycle(2200);
    K.play('sfx_airlock_cycle.ogg', 0.5);
    const key = ret.recalled ? 'expedition.return.recalled' : ret.injured ? 'expedition.return.injured'
      : ret.discovered ? 'expedition.return.found_spot' : (ret.danger && ret.danger.ok === false && ret.danger.choice === 'turn_back') ? 'expedition.return.early' : 'expedition.return.normal';
    const line = TT(key, { name: names, spot: ret.discovered && ret.discovered.name }, '관리실에서 알려 드립니다. ' + names + ' 님 돌아오셨습니다.');
    setTimeout(() => announce(line), 900);
    const hv = ret.haul || {}, mats = hv.materials || {}, nMat = Object.values(mats).reduce((a, b) => a + b, 0);
    const lb = ret.left_behind || {}, nLeft = Object.values(lb.materials || {}).reduce((a, b) => a + b, 0) + (lb.boxes || 0) + (lb.relics || 0);
    let h = '<h2>' + esc(TT('expedition.summary.title', {}, '가져온 것')) + '</h2><p class="sub">' + esc(TT('expedition.summary.log', { name: names, dest: ret.dest_ko }, names + ' 님, ' + (ret.dest_ko || '') + '에 다녀옴.')) + '</p>' +
      '<p class="desc">' + esc(line) + '</p>';
    const rows = [];
    if (nMat) rows.push('<span>' + esc(TT('expedition.summary.materials', { n: nMat }, '재료 ' + nMat + '개')) + ': ' + Object.entries(mats).map(([k, v]) => esc(RES_KO[k] || k) + ' ' + v).join(', ') + '</span>');
    if ((hv.boxes || []).length) rows.push('<span>' + esc(TT('expedition.summary.boxes', { n: hv.boxes.length }, '봉인 상자 ' + hv.boxes.length + '개')) + '</span>');
    if ((hv.relics || []).length) rows.push('<span>' + esc(TT('expedition.summary.shards', { n: hv.relics.length }, '유물 조각 ' + hv.relics.length + '개')) + '</span>');
    if (nLeft) rows.push('<span class="dim">' + esc(TT('expedition.summary.left_behind', { n: nLeft }, '두고 온 것 ' + nLeft + '개')) + '</span>');
    h += rows.length ? '<div class="kv">' + rows.join('') + '</div>' : '<p class="desc">' + esc(TT('expedition.summary.empty', {}, '이번에는 빈손입니다.')) + '</p>';
    (hv.boxes || []).forEach(b => { h += '<p class="boxline">' + esc(TT('sealed_box.on_shelf', { pattern: boxName(b) }, '「' + boxName(b) + '」 상자를 문간에 두었습니다. 같은 갈래 물건을 찍으시면 열립니다.')) + '</p>'; });
    if (ret.danger) {
      const dk = { air: 'air_leak', beast: 'big_one', seam: 'seam', lost: 'lost' }[ret.danger.kind] || ret.danger.kind;
      h += '<h3>바깥에서</h3><p class="desc">' + esc(TT('expedition.danger.kinds.' + dk + '.prompt', {}, ret.danger.ko || '')) + ' ' +
        esc(TT('expedition.danger.kinds.' + dk + '.' + (ret.danger.ok ? 'pass' : 'fail'), {}, '')) + '</p>';
    }
    if (ret.discovered) h += '<h3>찾은 곳</h3><p class="desc">' + esc(TT('spot.discovery_lead', { name: names }, '')) + '</p>' +
      (ret.discovered.discovery_text ? '<p class="desc">' + esc(K.plain(ret.discovered.discovery_text)) + '</p>' : '') +
      '<p class="desc">' + esc(TT('spot.discovery_after', { name: names }, '')) + '</p>';
    else if (ret.clue) h += '<p class="reclaim">' + esc(TT('spot.clue_from_expedition', { name: names, spot: ret.clue.name }, '')) + '</p>';
    if (ret.newcomer) h += '<p class="reclaim">' + esc(TT('expedition.return.rescued', { name: names }, '')) + '</p><p class="desc"><em>' + esc(TT('guest.rescued_first_words', {}, '')) + '</em></p>';
    if (ret.rescued_but_no_room) h += '<p class="desc">' + esc(TT('guest.rescued_no_room', {}, '')) + '</p>';
    if (ret.injured) h += '<p class="lost">' + esc(ret.injured) + ' 님이 다치셨습니다.</p>';
    (ret.imprints || []).forEach(n => { h += '<div class="who"><b>' + esc(n.resident) + ' 님</b><em>' + esc((n.imprint || {}).name || '') + '</em></div><p class="desc">' + esc(n.line || '') + '</p>'; });
    if (ret.line) h += '<p class="dayline">' + esc(K.plain(ret.line)) + '</p>';
    setTimeout(() => {
      K.panel(h);
      K.api('/api/expedition/seen', {}).catch(() => {});
      if (ret.newcomer) loadEntrance(true);
    }, 2400);
    X.log.push('return ' + ret.id);
  }

  // ══════════════════════════════════════════════════════════════
  //  5. 봉인 상자 — 문간 바닥(선반 밖) · 상자 카드 · 7일 뒤 억지로 열기 · 찍기로 열림 문장
  // ══════════════════════════════════════════════════════════════
  let boxes = [], boxAt = 0;
  async function loadBoxes(force) {
    if (!has()) return;
    if (!force && performance.now() - boxAt < 20000) return;
    boxAt = performance.now();
    try { boxes = await K.api('/api/boxes?uid=' + encodeURIComponent(K.uid)) || []; } catch (e) { boxes = []; }
  }
  const boxName = (b) => (b.any || b.cat === 'any') ? TT('sealed_box.blank.name', {}, '빈 원')
    : TT('sealed_box.patterns.' + b.cat + '.name', {}, PAT_FB[b.cat] || '알 수 없는 무늬');
  // 문장 묶음이 아직 안 올 때의 무늬 이름(시나리오 expedition_text.json 과 같은 이름)
  const PAT_FB = { food: '이삭 무늬', drink: '물방울 무늬', medical: '엇갈린 띠 무늬', electronics: '번개 무늬', stationery: '깃 무늬',
                   book: '겹친 장 무늬', apparel: '실타래 무늬', tobacco: '연기 무늬' };
  K.ext.floorBoxes = () => boxes.slice(0, 6);
  K.ext.onBox = (id) => {
    const b = boxes.find(x => x.id === id); if (!b) return;
    const pn = boxName(b);
    const body = K.panel('<h2>' + esc(pn) + ' 상자</h2><p class="sub">' + esc(b.cat_ko || CAT_KO[b.cat] || '') + ' · ' + esc(b.found_day) + '일째에 가져옴 · ' + esc(b.age_days) + '일 지남</p>' +
      '<p class="desc">' + esc(b.any ? TT('sealed_box.blank.desc', {}, '') : TT('sealed_box.patterns.' + b.cat + '.desc', {}, '')) + '</p>' +
      '<p class="reclaim">' + esc(TT('sealed_box.on_shelf', { pattern: pn }, '같은 갈래 물건을 찍으시면 열립니다.')) + '</p>' +
      '<div class="rowbtns"><button id="bxPry"' + (b.pry_ok ? ' class="on"' : ' disabled') + '>억지로 열기' + (b.pry_ok ? '' : ' · ' + b.pry_in_days + '일 뒤') + '</button></div>');
    body.querySelector('#bxPry').addEventListener('click', async () => {
      try {
        const r = await K.api('/api/box/pry', { box_id: b.id });
        if (r.state) K.apply(r.state);
        announce(TT('sealed_box.forced_open', { pattern: pn, name: r.by_name || (r.by && (personById(r.by) || {}).name) || '' }, pn + ' 상자를 억지로 열었습니다.'));
        K.closePanel(); await loadBoxes(true);
      } catch (e) { K.toast(e.message || '열지 못했습니다'); }
    });
  };
  K.ext.boxOpenedLine = (r) => {
    const bo = r.box_opened; if (!bo) return '';
    const pn = boxName(bo), old = !!(r.rescan_multiplier != null && r.rescan_multiplier < 1) || !(r.first_time);
    const g = Object.entries(bo.gained || {}).map(([k, v]) => (RES_KO[k] || k) + ' +' + v).join(', ');
    setTimeout(() => loadBoxes(true), 500);
    return (bo.any && TX.sealed_box ? TT('sealed_box.tutorial_open', {}, '') : TT(old ? 'sealed_box.opened_by_old' : 'sealed_box.opened_new', { pattern: pn }, pn + ' 상자가 열렸습니다.')) + (g ? ' ' + g : '');
  };

  // ══════════════════════════════════════════════════════════════
  //  연결: 상태가 올 때마다(문간·상자는 조금씩 늦춰서) — 원정 표시는 /api/ark 의 expedition 필드로
  // ══════════════════════════════════════════════════════════════
  let lastDayE = null;
  K.onApply((st) => {
    if (st.expedition !== undefined) { expedition = st.expedition || null; renderChip(); }
    if (st.expedition_return) showReturn(st.expedition_return);
    if (has()) {
      // 손님 수(/api/ark guests)나 날이 바뀌면 문간을 바로 다시 읽는다(두드림을 놓치지 않게)
      const gN = typeof st.guests === 'number' ? st.guests : (Array.isArray(st.guests) ? st.guests.length : null);
      const changed = (gN != null && ent && (ent.guests || []).length !== gN) || (lastDayE != null && st.day !== lastDayE);
      lastDayE = st.day;
      loadEntrance(changed); loadBoxes(changed || (st.boxes && st.boxes.length !== boxes.length));
    }
  });
  K.onLoad(() => { loadText(); loadEntrance(true); loadBoxes(true); });
  // 나가 있는 동안만 1분마다 가볍게 물어본다(귀환 정산은 서버가 멱등으로)
  setInterval(async () => {
    if (!expedition || document.hidden) return;
    try {
      const r = await K.api('/api/expedition?uid=' + encodeURIComponent(K.uid));
      expedition = r.expedition || null; renderChip();
      if (r.expedition_return) { await K.reload(); showReturn(r.expedition_return); }
    } catch (e) { /* 다음에 */ }
  }, 60000);
  X.state = () => ({ expedition, ent, boxes, text: X.textReady() });
  X.poll = async () => { const r = await K.api('/api/expedition?uid=' + encodeURIComponent(K.uid)); expedition = r.expedition || null; renderChip(); if (r.expedition_return) { await K.reload(); showReturn(r.expedition_return); } return r; };
})();
