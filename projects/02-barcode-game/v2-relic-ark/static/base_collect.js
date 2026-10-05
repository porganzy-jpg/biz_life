/* 잔해 방주 — 거점 화면의 수집·사건 층 (S13-B, 클라이언트만)
 *
 * 근거: docs/reports/review_fun_collection_20261003.md 추천 1~4(사용자 승인) · docs/UI_SIMPLE.md(눌렀을 때만) ·
 *       docs/TEXT_VOICE.md(관리실 방송).
 * 하는 일: ≡ 메뉴의 도감·소문, 오늘의 쪽지(사건) 카드, 아침 방송.
 *          S13 서버 계약(docs/API_S13.md)으로 들어오는 것(가문 세트·바람·문어 선물·첫 만남·하루 마감)도 여기서 그린다.
 * base.js 의 안쪽 손잡이(ARKBASE._k)만 쓴다. 서버 상태를 바꾸는 길은 api → apply 하나다.
 */
(() => {
  'use strict';
  const K = window.ARKBASE && window.ARKBASE._k;
  if (!K) return;
  const $ = (s) => document.querySelector(s);
  const esc = K.esc;
  const CAT_KO = { food: '식품', drink: '음료', medical: '의약·화학', electronics: '전자', stationery: '문구',
                   book: '도서', apparel: '의류', tobacco: '담배·주류', unknown: '정체불명' };
  const RAR_KO = { common: '흔함', uncommon: '쓸만함', rare: '귀함', epic: '진귀함', legendary: '전설' };
  const store = {
    get(k, d) { try { const v = localStorage.getItem('ark_' + K.uid + '_' + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem('ark_' + K.uid + '_' + k, JSON.stringify(v)); } catch (e) { /* 이 기계에 못 적어도 화면은 돈다 */ } },
  };
  const announce = (line) => (K.say ? K.say(line) : K.toast(line));   // S18: 큰 창이 떠 있으면 닫힌 뒤에
  const C = window.ARKCOLLECT = { log: [] };          // ★ 검수용 읽기 창

  // ══════════════════════════════════════════════════════════════
  //  0. 화면 문장(API_S13 §1 GET /api/text/moments = data/ui_moments.json). 키로 꺼내 쓴다.
  //     서버가 *_ko 로 치환을 끝낸 한 줄을 주는 곳은 그것이 이긴다. 서버가 아직 없으면(404) 짧은 대체 문장
  // ══════════════════════════════════════════════════════════════
  let MOM = {};
  K.api('/api/text/moments').then(j => { MOM = j || {}; }).catch(() => { MOM = {}; });
  function T(key, vars, fallback) {
    let o = MOM;
    const parts = key.split('.');
    for (let i = 0; i < parts.length && o != null; i++) {
      if (o[parts[i]] !== undefined) { o = o[parts[i]]; continue; }
      const rest = parts.slice(i).join('.');                 // "complete.8801043" 처럼 점이 든 키
      o = o[rest]; break;
    }
    return K.fill(typeof o === 'string' ? o : (fallback || ''), vars);   // 모르는 자리표시는 빈칸(base.js fillText)
  }
  K.ext.T = T;
  C.T = T;
  // 배열 문장(시나리오가 여러 줄을 주면 하나를 고른다)
  K.ext.Tarr = (key) => { let o = MOM; key.split('.').forEach(k => { o = o == null ? o : o[k]; }); return Array.isArray(o) ? o.filter(x => typeof x === 'string') : null; };

  // ══════════════════════════════════════════════════════════════
  //  1. 도감 — 물건 · 가문 · 손님(생물) · 문어 선물. 못 본 칸은 실루엣(눌러 보면 그림자 한 줄)
  //     API_S13 §7 /api/codex(entries) · §8 /api/collection. 서버가 옛 꼴이면 names 로 그린다
  // ══════════════════════════════════════════════════════════════
  let cxTab = 'items';
  async function openCodex(tab) {
    K.closeMenu();
    cxTab = tab || cxTab;
    const body = K.panel('<h2>도감</h2><p class="sub">불러오는 중입니다</p>');
    let cats = [], col = null;
    try { cats = await K.api('/api/codex?uid=' + encodeURIComponent(K.uid)); }
    catch (e) { body.innerHTML = '<h2>도감</h2><p class="lost">도감을 펼치지 못했습니다: ' + esc(e.message || '') + '</p>'; return; }
    try { col = await K.api('/api/collection?uid=' + encodeURIComponent(K.uid)); } catch (e) { col = null; }   // S13 이전 서버면 없다
    cats = Array.isArray(cats) ? cats : (cats.categories || []);
    const tot = cats.reduce((a, x) => a + (x.total || 0), 0), got = cats.reduce((a, x) => a + (x.found || 0), 0);
    const tabs = [['items', '물건 ' + got + '/' + tot]];
    if (col) {
      tabs.push(['families', '가문 ' + (col.families_done || 0) + '/' + (col.families_total || (col.families || []).length)]);
      tabs.push(['creatures', '손님 ' + (col.creatures || []).filter(c => c.known).length + '/' + (col.creatures || []).length]);
      if ((col.octopus_finds || []).length || (K.ark && K.ark.octopus && K.ark.octopus.arrived)) tabs.push(['octopus', '문어']);
    }
    let h = '<h2>도감</h2><div class="cxtabs">' + tabs.map(([k, l]) => '<button data-tab="' + k + '"' + (k === cxTab ? ' class="on"' : '') + '>' + esc(l) + '</button>').join('') + '</div>';
    if (cxTab === 'items' || !col) h += itemsTab(cats, col);
    else if (cxTab === 'families') h += familiesTab(col);
    else if (cxTab === 'creatures') h += creaturesTab(col);
    else h += octopusTab(col);
    body.innerHTML = h;
    body.querySelectorAll('button[data-tab]').forEach(b => b.addEventListener('click', () => openCodex(b.dataset.tab)));
    body.querySelectorAll('.cx.off[data-hint]').forEach(el => el.addEventListener('click', () => announce(el.dataset.hint)));
    body.querySelectorAll('.cx.on[data-card]').forEach(el => {
      const open = () => {
        const CR = K.ext.cards; if (!CR) return;
        let o = {}; try { o = JSON.parse(el.dataset.card); } catch (e) { return; }
        o.prop_id = K.propForCategory ? K.propForCategory(o.category) : null;
        CR.peek(o, o.count ? '도감 · ' + o.count + '번 찍음' : '도감');
      };
      el.addEventListener('click', open);
      el.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
    });
    const nb = body.querySelector('#octname');
    if (nb) nb.addEventListener('click', nameOctopus);
    // 다 모은 갈래·가문이 새로 생겼으면 한 번만 축하(완성의 순간)
    const seen = store.get('cx_done', []);
    const now = cats.filter(x => x.total && x.found >= x.total).map(x => 'cat:' + x.category)
      .concat(((col && col.families) || []).filter(f => f.completed).map(f => 'fam:' + f.code));
    const fresh = now.filter(k => seen.indexOf(k) < 0);
    store.set('cx_done', seen.concat(fresh));
    const fc = fresh.find(k => k.startsWith('cat:'));
    if (fc) celebrate('관리실에서 알려 드립니다. ' + (CAT_KO[fc.slice(4)] || fc.slice(4)) + ' 칸을 다 채웠습니다. 주민 여러분, 축하드립니다.');
    C.log.push('codex ' + got + '/' + tot + ' tab=' + cxTab);
  }
  function itemsTab(cats, col) {
    let h = '<p class="sub">찍은 물건의 이름이 여기 적힙니다. 못 본 칸은 그림자만 보이고, 누르면 어떤 모양인지 들려 드립니다.</p>';
    if (col && col.rarity) h += '<div class="kv rarsum">' + Object.keys(RAR_KO).map(k => '<span class="r-' + k + '">' + RAR_KO[k] + ' <b>' + (col.rarity[k] || 0) + '</b></span>').join('') +
      ((col.variants && col.variants.seen) ? '<span class="r-sea">바다 무늬 <b>' + col.variants.seen + '</b></span>' : '') + '</div>';
    cats.forEach(x => {
      const items = x.entries || (x.names || []).map(n => ({ known: true, name: n }));
      const done = x.total && x.found >= x.total;
      h += '<h3>' + esc(x.category_ko || CAT_KO[x.category] || x.category) + ' · ' + (x.found || 0) + '/' + (x.total || 0) + (done ? ' <b class="cxdone">다 모음</b>' : '') + '</h3><div class="cxgrid">';
      const img = K.propImgSrc(x.category);
      for (let i = 0; i < (x.total || 0); i++) {
        const it = items[i] || { known: false };
        if (it.known) {
          const r = it.rarity_best || it.rarity || '';
          // S16: 아는 칸은 희귀도 틀 색 + (귀함 이상) 박이 천천히 지나간다. 누르면 그 유물 카드
          h += '<div class="cx on ' + esc(r) + (it.variant_seen ? ' sea' : '') + '" role="button" tabindex="0" data-card="' + esc(JSON.stringify({ rarity: r, sea: !!it.variant_seen, name: it.name || it.stem || '', category: x.category, count: it.count || 0 })) + '" title="' + esc(it.name || it.stem) + (RAR_KO[r] ? ' · ' + RAR_KO[r] : '') + (it.count ? ' · ' + it.count + '번' : '') + '">' +
               (img ? '<img alt="" src="' + img + '">' : '') + '<span>' + esc(it.stem || it.name) + '</span>' +
               (['rare', 'epic', 'legendary'].indexOf(r) >= 0 ? '<i class="cxfoil" aria-hidden="true"></i>' : '') +
               (RAR_KO[r] ? '<i class="rmk">' + esc(RAR_KO[r]) + '</i>' : '') + (it.count > 1 ? '<i class="cnt">×' + it.count + '</i>' : '') + '</div>';
        } else {
          const hint = it.hint_ko || T('codex.unknown', { hint: T('codex.category_hints.' + x.category, {}, '') }, '') || T('codex.unknown_no_hint', {}, '');
          h += '<div class="cx off" data-hint="' + esc(hint) + '" title="' + esc(hint) + '">' + (img ? '<img alt="" src="' + img + '">' : '') + '<span>?</span></div>';
        }
      }
      h += '</div>';
    });
    return h;
  }
  function familiesTab(col) {
    const fams = col.families || [];
    return '<p class="sub">같은 가문 물건을 ' + ((fams[0] && fams[0].total) || 3) + '가지 모으면 한 벌입니다. 다 모으면 이야기와 장식이 열립니다.</p><div class="famlist">' + fams.map(f => {
      const need = f.total || 3, have = Math.min(need, f.have || 0), done = !!f.completed;
      return '<div class="fam' + (done ? ' done' : '') + (f.known ? '' : ' off') + '"><b>' + esc(f.known ? f.name : '이름 모를 가문') + '</b>' +
        '<span>' + esc(f.category_ko || '') + ' · ' + have + '/' + need + '</span>' +
        '<div class="fbar"><i style="width:' + Math.round(100 * have / need) + '%"></i></div>' +
        (f.known ? (done ? (f.story ? '<p class="desc">' + esc(f.story) + '</p>' : '') + (f.decor ? '<p class="decor">장식 · ' + esc(f.decor) + '</p>' : '')
                         : (have === need - 1 ? '<p class="desc">' + esc(T('family_set.one_left', { family: f.name }, '')) + '</p>' : (f.flavor ? '<p class="desc">' + esc(f.flavor) + '</p>' : '')))
                 : (f.silhouette ? '<p class="desc dim">' + esc(f.silhouette) + '</p>' : '')) + '</div>';
    }).join('') + '</div>';
  }
  function creaturesTab(col) {
    const RES = { held: '막았습니다', scarred: '금이 갔습니다', breached: '잃었습니다', passed: '지나갔습니다' };
    return '<p class="sub">다녀간 손님들입니다. 아직 못 본 손님은 그림자만 적어 둡니다.</p><div class="famlist">' + (col.creatures || []).map(c =>
      '<div class="fam' + (c.known ? '' : ' off') + '"><b>' + esc(c.known ? c.name : '아직 못 본 손님') + '</b>' +
      (c.known ? '<span>' + (c.times || 0) + '번' + (c.last_result ? ' · ' + (RES[c.last_result] || c.last_result) : '') + '</span>' +
                 (c.how ? '<p class="desc">' + esc(K.plain(c.how)) + '</p>' : '')
               : (c.silhouette ? '<p class="desc dim">' + esc(c.silhouette) + '</p>' : '')) + '</div>').join('') + '</div>';
  }
  function octopusTab(col) {
    const o = (K.ark && K.ark.octopus) || {};
    let h = '<p class="sub">' + (o.name ? '「' + esc(o.name) + '」' : '문어') + (o.mood && o.mood.ko ? ' · ' + esc(o.mood.ko) : '') + '</p>' +
      (o.mood && o.mood.line ? '<p class="desc">' + esc(K.plain(o.mood.line)) + '</p>' : '');
    if (o.arrived) h += '<div class="keyrow"><input id="octin" maxlength="12" placeholder="문어 이름" value="' + esc(o.name || '') + '"><button id="octname">이름 짓기</button></div>';
    h += '<h3>' + esc(T('octopus_gift.label', {}, '문어 선물')) + '</h3><div class="famlist">' + (col.octopus_finds || []).map(f =>
      '<div class="fam' + (f.known ? '' : ' off') + '"><b>' + esc(f.known ? f.name : '아직 못 받은 선물') + '</b>' + (f.count ? '<span>' + f.count + '번</span>' : '') +
      (f.known && f.line ? '<p class="desc">' + esc(K.plain(f.line)) + '</p>' : '') + '</div>').join('') + '</div>';
    return h;
  }
  async function nameOctopus() {
    const v = ($('#octin').value || '').trim();
    if (!v) return;
    try { const r = await K.api('/api/octopus/name', { name: v }); announce(K.plain(r.ko || '')); await K.reload(); openCodex('octopus'); }
    catch (e) { K.toast(e.message || '이름을 짓지 못했습니다'); }
  }
  function celebrate(line) {
    const el = document.createElement('div'); el.className = 'celebrate'; el.textContent = '다 모았습니다';
    document.body.appendChild(el); setTimeout(() => el.remove(), 2400);
    K.play('sfx_scan_ok.ogg', 0.6); if (line) announce(line);
  }
  K.ext.celebrate = celebrate;
  $('#codexbtn').addEventListener('click', () => openCodex());


  // ══════════════════════════════════════════════════════════════
  //  2. 오늘의 쪽지(사건) — 위 한 줄의 작은 단추 → 카드 → 고르기 → /api/event/resolve → 방송 한 줄
  // ══════════════════════════════════════════════════════════════
  let ev = null;
  async function loadEvent() {
    try { ev = await K.api('/api/event/today?uid=' + encodeURIComponent(K.uid)); }
    catch (e) { ev = null; }
    renderEvBtn();
    return ev;
  }
  function renderEvBtn() {
    const b = $('#evbtn');
    const live = ev && ev.event && ev.state && !ev.state.resolved;
    b.hidden = !live;
    if (live) { $('#evline').textContent = T('event_strip.label', {}, '관리실 쪽지'); b.title = T('event_strip.line', {}, ev.event.name || ''); }
  }
  function openEvent() {
    if (!ev || !ev.event) return;
    const e = ev.event, st = ev.state || {}, ark = K.ark || {};
    const hand = ark.hand || [], match = ev.matching_card_ids || [];
    const roomName = e.counter_room ? ((K.catalog[e.counter_room] || {}).name || e.counter_room) : '';
    let h = '<h2>' + esc(e.name) + '</h2><p class="sub">오늘의 쪽지 · ' + esc(st.day || ark.day || '') + '일째</p>' +
      '<p class="desc">' + esc(K.plain(e.text)) + '</p>';
    if (st.resolved) {
      h += '<p class="reclaim">오늘 쪽지는 이미 처리했습니다.</p>';
      K.panel(h); return;
    }
    if (roomName) h += '<p class="evhint">' + esc(roomName) + (ev.room_backup ? '이 있어서, 카드가 없어도 반쯤은 막을 수 있습니다.' : '이 있으면 카드 없이도 반쯤 막을 수 있습니다.') + '</p>';
    h += '<h3>어떻게 할까요</h3><div class="blist">';
    const sorted = hand.slice().sort((a, b) => (match.indexOf(b.id) >= 0) - (match.indexOf(a.id) >= 0));
    sorted.forEach(c => {
      const ok = match.indexOf(c.id) >= 0;
      h += '<button class="bopt' + (ok ? ' good' : '') + '" data-card="' + esc(c.id) + '"><b>' + esc(c.name || c.id) + (ok ? ' · 맞는 카드' : '') + '</b>' +
           '<small>' + esc((c.tags || []).map(t => '#' + t).join(' ')) + '</small></button>';
    });
    h += '<button class="bopt" data-card=""><b>카드 없이 넘기기</b><small>' + (hand.length ? '카드를 아껴 둡니다' : '손에 든 카드가 없습니다') + '</small></button></div>';
    const body = K.panel(h);
    body.querySelectorAll('button[data-card]').forEach(b => b.addEventListener('click', () => resolveEvent(b.dataset.card || null)));
  }
  async function resolveEvent(cardId) {
    const e = ev && ev.event; if (!e) return;
    let r;
    try { r = await K.api('/api/event/resolve', { card_id: cardId }); }
    catch (er) { K.toast(er.message || '쪽지를 처리하지 못했습니다'); return; }
    const ok = !!r.countered;
    const ap = r.applied || {};
    const delta = Object.entries(ap).filter(([k, v]) => K.RES_KO[k] && typeof v === 'number' && v)
      .map(([k, v]) => K.RES_KO[k] + ' ' + (v > 0 ? '+' : '') + v);
    const line = (r.voice && r.voice.text) ? (r.voice.who_ko ? r.voice.who_ko + ': ' : '') + K.plain(r.voice.text)
      : (ok ? '관리실에서 알려 드립니다. 「' + e.name + '」, 잘 넘겼습니다. 수고 많으셨습니다.'
            : '관리실에서 알려 드립니다. 「' + e.name + '」는 막지 못했습니다. 다치신 분이 있는지 살펴 주세요.');
    announce(line);
    K.play(ok ? 'sfx_card_place.ogg' : 'sfx_water_splash.ogg', 0.5);
    let h = '<h2>' + (ok ? '잘 넘겼습니다' : '막지 못했습니다') + '</h2><p class="sub">' + esc(e.name) + '</p>' +
      '<p class="desc">' + esc(line) + '</p>';
    if (r.hero) h += '<p class="reclaim">' + esc(r.hero) + ' 님이 나서서 막았습니다.</p>';
    if (delta.length) h += '<h3>달라진 것</h3><div class="kv">' + delta.map(d => '<span>' + esc(d) + '</span>').join('') + '</div>';
    if (ap.newcomer) h += '<h3>새 식구</h3><p class="desc">' + esc(ap.newcomer.name) + ' 님이 합류했습니다.</p>';
    (r.new_imprints || []).forEach(n => { h += '<div class="who"><b>' + esc(n.resident) + ' 님</b><em>' + esc(n.imprint.name) + '</em></div><p class="desc">' + esc(n.line || '') + '</p>'; });
    (r.imprint_credit || []).forEach(c => { h += '<p class="credit">' + esc(K.plain(c.ko || '')) + '</p>'; });   // S19: 각인 덕분 한 줄
    K.panel(h);
    if (ap.newcomer) setTimeout(() => firstMeet({ resident: ap.newcomer }), 1200);
    C.log.push('event ' + e.id + ' ' + (ok ? 'countered' : 'failed'));
    await K.reload();
    await loadEvent();
  }
  $('#evbtn').addEventListener('click', openEvent);

  // ══════════════════════════════════════════════════════════════
  //  3. 소문 — ≡ 메뉴 + 새로 열린 소문은 가끔(하루 한 번) 방송으로
  // ══════════════════════════════════════════════════════════════
  async function openRumors() {
    K.closeMenu();
    const body = K.panel('<h2>소문</h2><p class="sub">불러오는 중입니다</p>');
    let rs;
    try { rs = await K.api('/api/rumors?uid=' + encodeURIComponent(K.uid)); }
    catch (e) { body.innerHTML = '<h2>소문</h2><p class="lost">소문을 듣지 못했습니다: ' + esc(e.message || '') + '</p>'; return; }
    rs = (rs || []).filter(r => !r.act || r.act === (K.ark && K.ark.act || 1));
    const got = rs.filter(r => r.unlocked).length;
    body.innerHTML = '<h2>소문<span class="cap">' + got + ' / ' + rs.length + '</span></h2>' +
      '<p class="sub">찍은 물건의 갈래에 따라, 바깥 이야기가 하나씩 들어옵니다.</p>' +
      rs.map(r => {
        const p = r.progress || { have: 0, need: 1 };
        return '<div class="rumor' + (r.unlocked ? ' on' : '') + '"><b>' + (r.unlocked ? esc(r.name) : '아직 들은 이야기가 없습니다') + '</b>' +
          '<small>' + esc(r.categories_ko || '') + ' ' + p.have + '/' + p.need + '</small>' +
          '<div class="fbar"><i style="width:' + Math.round(100 * Math.min(1, p.have / Math.max(1, p.need))) + '%"></i></div>' +
          (r.unlocked && r.clue_text ? '<p class="desc">' + esc(K.plain(r.clue_text)) + (r.who ? ' <em>· ' + esc(r.who) + '</em>' : '') + '</p>' : '') + '</div>';
      }).join('');
    C.log.push('rumors ' + got + '/' + rs.length);
  }
  async function rumorAnnounce() {
    const day = K.ark && K.ark.day;
    if (store.get('rumor_day', null) === day) return;
    try {
      const rs = await K.api('/api/rumors?uid=' + encodeURIComponent(K.uid));
      const fresh = (rs || []).find(r => r.unlocked && r.is_new);
      if (fresh) { store.set('rumor_day', day); setTimeout(() => announce('관리실에서 알려 드립니다. 새 소문이 들어왔습니다. 「' + fresh.name + '」, 메뉴의 소문에서 들어 보세요.'), 6000); }
    } catch (e) { /* 소문이 없어도 화면은 돈다 */ }
  }
  $('#rumorbtn').addEventListener('click', openRumors);

  // ══════════════════════════════════════════════════════════════
  //  아침 방송 — 밤사이 들어온 것 · 밀린 각인 연출 · (S13) 밤사이 판정
  // ══════════════════════════════════════════════════════════════
  // S18: 아침은 「밤사이」 **한 장**(플레이테스트 최악 2·명확성 3 — 마감·만남·귀환·방송 넷이 한꺼번에 겹쳤다).
  //      서버 요약(st.overnight: {day, lines:[{kind, ko}]})이 오면 그것을, 아직 없으면 지금 있는 조각
  //      (밤사이 생산·밀린 각인 연출·밤 판정·귀환 한 줄·문어)을 모아 한 장으로. 같은 종류의 같은 문장은 한 번만.
  //      이 창이 닫힌 뒤에 귀환 카드·만남 카드·방송이 차례로 나온다(base.js enqueue)
  let morningShown = null;
  function overnightLines(st) {
    const ov = st.overnight;
    const out = [];
    const prS = st.produced_while_away || {};
    const gotS = Object.entries(prS).filter(([, v]) => v > 0).map(([k, v]) => (K.RES_KO[k] || k) + ' ' + v);
    if (ov && (ov.items || ov.lines)) {                      // 서버 S18 요약: {items:[{kind, data}]}
      if (gotS.length) out.push({ kind: 'production', text: '밤사이 ' + gotS.join(', ') + ' 들어왔습니다.' });
      (ov.items || ov.lines).forEach(x => { const t = overnightText(x); if (t) out.push({ kind: x.kind || '', text: t }); });
      const seen = new Set();
      return out.filter(x => (seen.has(x.text) ? false : (seen.add(x.text), true)));
    }
    const pr = st.produced_while_away || {};
    const got = Object.entries(pr).filter(([, v]) => v > 0).map(([k, v]) => (K.RES_KO[k] || k) + ' ' + v);
    if (got.length) out.push({ kind: 'production', text: '밤사이 ' + got.join(', ') + ' 들어왔습니다.' });
    const nr = st.night_judge && st.night_judge.report;      // S13: 밤사이 자동 판정(한 번만 온다)
    if (nr && nr.ko) out.push({ kind: 'night_judge', text: K.plain(nr.ko) });
    const ret = st.expedition_return;
    if (ret && !ret.seen) {
      const nm = (ret.member_names || []).join(' 님과 ');
      if (nm) out.push({ kind: 'return', text: nm + ' 님이 밤사이 돌아오셨습니다.' + (ret.discovered ? ' 찾은 곳이 있습니다.' : '') });
    }
    (st.morning_lines || []).forEach(m => { const t = m.line || m.ko || m.text; if (t) out.push({ kind: m.kind || 'imprint', text: K.plain(t) }); });
    const o = st.octopus || {};
    if (o.gift_today && store.get('gift_day', null) !== st.day) out.push({ kind: 'octopus', text: K.josa(o.name || '문어', '가') + ' 입구에 무언가를 두고 갔습니다.' });
    const seen = new Set();
    return out.filter(x => { const k = x.text.replace(/\S+ 님/g, '님'); if (seen.has(x.kind + k)) return false; seen.add(x.kind + k); return true; });
  }
  function overnightText(x) {
    const d = x.data || x, k = x.kind;
    const s = (v) => (v ? K.plain(String(v)) : '');
    if (x.ko || x.line || x.text) return s(x.ko || x.line || x.text);
    if (k === 'night_judge') return s(d.ko || (d.report && d.report.ko));
    if (k === 'expedition_return') { const nm = (d.member_names || []).join(' 님과 ');
      return s(d.line) || (nm ? nm + ' 님이 돌아오셨습니다.' + (d.discovered ? ' 찾은 곳이 있습니다.' : '') : ''); }
    if (k === 'depth') return s(d.ko) || (d.m ? '이 집이 ' + d.m + 'm까지 내려왔습니다.' : '');
    if (k === 'imprint') return s(d.line) || (d.imprint_name ? (d.residents || []).join(', ') + ' 님에게 ' + K.josa('「' + d.imprint_name + '」', '이') + ' 남았습니다.' : '');
    if (k === 'octopus') { const l = s(d.line); const on = ((K.ark || {}).octopus || {}).name || '문어'; return l ? ((l.indexOf('문어') >= 0 || l.indexOf(on) >= 0) ? l : '문어가 물어 온 것: ' + l) : (d.name ? '문어가 ' + K.josa('「' + d.name + '」', '을') + ' 두고 갔습니다.' : ''); }
    if (k === 'knock') return d.name ? '밤사이 문간 유리를 누가 두드렸습니다. ' + d.name + ' 님이 문간에서 기다리십니다.' : '';
    if (k === 'wish') return s(d.line || d.ko);
    if (k === 'needs') return '';                                  // S19: 오늘 필요는 아래 얼굴 줄(needs_today)로
    if (k === 'visit') return s(d.line || d.ko);
    if (k === 'overflow') return s(d.ko);
    if (k === 'keepsake' && d.name && d.item) {                  // ui_moments keepsake.by_time — 저녁에 열어도 「오늘 아침에도」라 하던 것
      const hr = new Date().getHours(), band = hr >= 5 && hr < 11 ? 'morning' : hr < 17 ? 'day' : hr < 21 ? 'evening' : 'night';
      return s(T('keepsake.by_time.' + band, { name: d.name, item: d.item }, '') || d.line);
    }
    if (k === 'arc' || k === 'beat') return s(d.announce || d.line || d.ko);
    return s(d.ko || d.line);
  }
  function morning(st) {
    const day = st.day;
    const ov = st.overnight;
    if (ov && ov.items && ov.items.length) { if (morningShown === ov.items.length) return; }       // 서버 요약은 seen 할 때까지 남는다 — 이 세션에서 한 번
    else if (store.get('morning_day', null) === day && !(st.morning_lines || []).length && !(st.night_judge && st.night_judge.report)) return;
    if (ov && ov.items) morningShown = ov.items.length;
    const lines = overnightLines(st);
    store.set('morning_day', day);
    const core = K.ext.core;
    if (!lines.length && !(core && core.hasMorning && core.hasMorning(st))) return;
    K.enqueue('overnight', (done) => {
      const hr = new Date().getHours(), when = hr >= 5 && hr < 11 ? '아침' : hr < 17 ? '낮' : hr < 21 ? '저녁' : '밤';
      const tk = hr >= 5 && hr < 11 ? 'morning' : hr < 17 ? 'day' : hr < 21 ? 'evening' : 'night';                       // S19: 저녁에 열어도 「아침」이라 하던 것
      const title = T('morning.by_time.' + tk + '.title', {}, '') || (tk === 'morning' ? ((ov && ov.title) || T('morning.title', {}, '밤사이')) : '그사이');
      const open0 = T('morning.by_time.' + tk + '.open', {}, '');
      const body = K.panel('<h2>' + esc(title) + '</h2><p class="sub">' + esc(day) + '일째 ' + when + '</p>' +
        '<p class="desc">' + esc(K.plain(open0 || (ov && ov.open) || T('morning.open', {}, '좋은 아침입니다, 관리실입니다.'))) + '</p>' +
        (K.ext.core && K.ext.core.morningExtra ? K.ext.core.morningExtra(st) : '') +   // S19: 오늘 바라는 것·찾아온 이·오늘의 일
        lines.map(l => '<p class="dayline ov-' + esc(l.kind) + '">' + esc(l.text) + '</p>').join('') +
        '<p class="desc">' + esc(K.plain((ov && ov.close) || T('morning.close', {}, ''))) + '</p>' +
        '<div class="rowbtns"><button class="ovok">' + esc(T('overnight.ok', {}, '확인')) + '</button></div>');
      body.querySelector('.ovok').addEventListener('click', () => K.closePanel());
      K.whenPanelGone(() => { if (ov && ov.items) K.api('/api/overnight/seen', {}).catch(() => {}); done(); });
    }, true);
    C.log.push('overnight ' + lines.length);
  }

  // ══════════════════════════════════════════════════════════════
  //  4. (S13 계약) 첫 만남 · 문어 선물 · 바람 · 하루 마감 — 서버가 주면 그린다
  // ══════════════════════════════════════════════════════════════
  function firstMeet(m) { K.enqueue('meet:' + ((m.resident || {}).name || ''), (done) => showMeet(m, done)); }
  function showMeet(m, done) {
    const p = m.resident || {}, line = m.line || m.ko || '';
    const el = document.createElement('div'); el.className = 'meet';
    el.innerHTML = '<div class="meet-in"><p class="sub">' + esc(m.title || '새 식구') + '</p><h2>' + esc(p.name || '') + '</h2>' +
      '<p class="desc">' + esc(K.plain(line || (p.name ? p.name + ' 님이 해치로 들어왔습니다. 자리는 입구 의자에 마련해 두었습니다.' : ''))) + '</p>' +
      '<button>반갑습니다</button></div>';
    document.body.appendChild(el);
    el.querySelector('button').addEventListener('click', () => { el.remove(); done && done(); });
    if (window.ARKBASE.hatchCycle) window.ARKBASE.hatchCycle(2000);
    C.log.push('first_meet ' + (p.name || ''));
  }
  // 바람(API_S13 §9): 주민 카드(방 카드 「자세히」)에 한 줄. 이뤄지면 line 이 바뀐다 — 그것이 보상
  let wishes = [], wishAt = 0;
  async function loadWishes(force) {
    if (!force && performance.now() - wishAt < 20000) return;
    wishAt = performance.now();
    try { wishes = await K.api('/api/wishes?uid=' + encodeURIComponent(K.uid)) || []; } catch (e) { wishes = []; }
  }
  K.ext.wishFor = (p) => {
    const w = wishes.find(x => x.resident_id === p.id);
    if (!w) return '';
    const pr = w.progress || {};
    return '<div class="wish' + (w.done ? ' done' : '') + '"><b>' + (w.done ? '이룬 바람' : '바람') + '</b> ' + esc(K.plain(w.wish || '')) +
      (w.line ? '<br><em>「' + esc(K.plain(w.line)) + '」</em>' : '') +
      (!w.done && pr.need ? '<br><small>' + esc(K.plain(w.condition || '')) + ' (' + (pr.have || 0) + '/' + pr.need + ')</small>' : '') + '</div>';
  };
  // 문어 선물(API_S13 §4 octopus.gift_today): 하루 한 번 입구에 작은 방울이 톡. 누르면 방송
  function giftCheck(st) {
    const o = st.octopus || {};
    if (o.arrival && !store.get('oct_arrival', false)) {
      store.set('oct_arrival', true);
      const beats = (o.arrival.beats || []).map(b => (typeof b === 'string' ? b : (b.line || b.beat || ''))).filter(Boolean);
      firstMeet({ resident: { name: o.name || '문어' }, line: beats.concat(o.arrival.closing ? [o.arrival.closing] : []).join(' '), title: '처음 온 손님' });
    }
    const g = o.gift_today;
    K.ext.gift = (g && store.get('gift_day', null) !== st.day) ? g : null;
  }
  K.ext.onGift = () => {
    const g = K.ext.gift; if (!g) return;
    store.set('gift_day', K.ark && K.ark.day); K.ext.gift = null;
    K.play('sfx_card_place.ogg', 0.5);
    const gl = K.plain(g.ko || T('octopus_gift.pop', { item: g.name }, ''));
    const on = ((K.ark || {}).octopus || {}).name || '문어';
    announce((gl.indexOf('문어') >= 0 || gl.indexOf(on) >= 0) ? gl : '문어가 물어 온 것: ' + gl);
    C.log.push('gift ' + g.id);
  };
  // 덮개가 노리는 방이 드러나면 한 번 방송(API_S13 §6 raid.reveal_ko)
  let lidSaid = null;
  function lidCheck(st) {
    const r = st.combat && st.combat.raid;
    if (r && r.lid_revealed && r.reveal_ko && lidSaid !== r.id) { lidSaid = r.id; announce(K.plain(r.reveal_ko)); }
  }
  // 하루 마감(API_S13 §11): 밤에 처음 들어올 때 한 번 + ≡ 메뉴 「오늘 마감」
  async function openDayEnd(auto) {
    K.closeMenu();
    let d;
    try { d = await K.api('/api/day_end?uid=' + encodeURIComponent(K.uid)); }
    catch (e) { if (!auto) K.toast('마감 말씀을 아직 준비하지 못했습니다'); return; }
    const lines = (d.lines || []).map(l => l.text || '').concat(d.facts_ko || []).filter(Boolean);
    K.panel('<h2>' + esc(d.title || '오늘 바뀐 것') + '</h2><p class="sub">' + esc(d.day || '') + '일째 마감</p>' +
      '<p class="desc">' + esc(K.plain(d.open || T('day_end.open', {}, ''))) + '</p>' +
      (lines.length ? lines.map(l => '<p class="dayline">' + esc(K.plain(l)) + '</p>').join('') : '<p class="dayline">' + esc(T('day_end.nothing', {}, '')) + '</p>') +
      (d.closing ? '<p class="desc">' + esc(K.plain(d.closing)) + '</p>' : '') +
      '<p class="desc">' + esc(K.plain(d.close || T('day_end.close', {}, ''))) + '</p>');
    store.set('dayend_day', d.day);
    C.log.push('day_end ' + lines.length + (auto ? ' auto' : ''));
  }
  const deb = $('#dayendbtn'); if (deb) deb.addEventListener('click', () => openDayEnd(false));
  // S18: 하루 마감은 **그 사람의 하루가 끝날 때만** 저절로 연다(플레이테스트 버그 1 — 게임 날은 방주를 만든 시각에 바뀌는데
  //      실제 밤 21시로 열어서, 저녁에 시작한 사람은 매일 아침(방금 시작한 날)에 「N일째 마감」을 봤다).
  //      서버가 날이 끝나는 시각(day_ends_at, 초)을 주면 끝나기 3시간 안쪽의 세션에서 한 번. 그 값이 없으면 저절로 열지 않는다
  //      (≡ 메뉴 「오늘 마감」은 언제나). 첫 세션에는 열지 않는다
  const DAYEND_WINDOW_S = 3 * 3600;
  const sessionStart = !store.get('seen_before', false);
  store.set('seen_before', true);
  function dayEndsAt(st) {
    const v = st.day_ends_at != null ? st.day_ends_at : (st.clock && st.clock.day_ends_at != null ? st.clock.day_ends_at : (st.day_end && st.day_end.ends_at));
    return typeof v === 'number' ? v : null;
  }
  async function nightCheck(st) {
    if (store.get('dayend_day', null) === st.day || sessionStart) return;
    if (st.session && st.session.big_left === 0) return;            // S19: 큰 창은 세션에 둘까지(API_S19 §6)
    const end = dayEndsAt(st);
    if (end == null) return;
    const left = end - Date.now() / 1000;
    if (!(left > 0 && left <= DAYEND_WINDOW_S)) return;
    let d;
    try { d = await K.api('/api/day_end?uid=' + encodeURIComponent(K.uid)); } catch (e) { return; }
    if (!(d.lines || []).length) return;                      // 적을 것이 없으면 조용히
    K.enqueue('day_end', (done) => { openDayEnd(true).then(() => K.whenPanelGone(done)).catch(done); });
  }
  C.dayEndsAt = dayEndsAt;
  C.morningTest = () => { morningShown = null; store.set('morning_day', null); morning(K.ark); };   // ★ 검수용
  // 이뤄진 바람(한 번만 온다)
  function wishNews(st) { (st.wishes_new || []).forEach(w => announce(K.plain(w.line || ''))); if ((st.wishes_new || []).length) loadWishes(true); }

  C.firstMeet = firstMeet; C.openCodex = openCodex; C.openRumors = openRumors; C.openEvent = openEvent;

  // ── 연결 ──
  // 첫날 살짝 찌르기: 세 분 모두 자리를 안 정해 생산 방이 반만 돈다. 방송 한 줄 + 그 방 테두리(누가 들어가면 끝)
  function firstDayNudge(st) {
    if ((st.day || 1) > 1) return;
    const prod = st.production || {}, cb = st.combat || {};
    const placed = Object.keys(cb.stations || {}).length;
    const idle = Object.entries(prod).find(([, p]) => (p.staff || 0) === 0);
    if (!idle || placed > 0) return;
    const slot = +idle[0];
    K.ext.nudgeSlot = slot;
    if (store.get('nudge_day', null) === st.day) return;
    store.set('nudge_day', st.day);
    const nm = (K.catalog[idle[1].room_id] || {}).name || '식량창고';
    setTimeout(() => announce('관리실에서 알려 드립니다. ' + nm + '에 일하시는 분이 안 계셔서 반만 돌아가고 있습니다. 입구에 계신 분 한 분만 ' + K.josa(nm, '으로') + ' 모셔 주세요.'), 2500);
    C.log.push('nudge ' + slot);
  }
  // S18: 깊이 문턱(60·120·180 m)을 처음 넘으면 화면 가운데 큰 표시 + 방송 한 줄(플레이테스트 명확성 4 — 4일째 180 m 에 닿았는데 아무 연출이 없었다).
  //      서버가 depth_threshold({m, ko, title}) 를 주면 그것을, 없으면 깊이 띠(gauges.depth.m)가 문턱을 처음 넘는 순간을 이 기기에서 잰다.
  //      문장은 시나리오(ui_moments depth_threshold.<m>.{title,line}); 아직 없으면 짧은 대체 문장
  const DEPTH_MARKS = [60, 120, 180];
  function depthCheck(st, first) {
    const g = (st.gauges || {}).depth || {};
    const m = typeof g.m === 'number' ? g.m : null;
    if (m == null) return;
    const seenMax = store.get('depth_max', null);
    store.set('depth_max', Math.max(m, seenMax == null ? 0 : seenMax));
    let hit = (st.depth_crossed && st.depth_crossed.length) ? st.depth_crossed[st.depth_crossed.length - 1]
      : (st.depth_threshold && st.depth_threshold.m ? st.depth_threshold : null);
    if (!hit) {
      if (seenMax == null) return;                            // 이 기기에서 처음 보는 방주 — 지난 문턱을 소급해 울리지 않는다
      const crossed = DEPTH_MARKS.filter(x => seenMax < x && m >= x);
      if (!crossed.length) return;
      hit = { m: crossed[crossed.length - 1] };
    }
    if (store.get('depth_said_' + hit.m, false)) return;
    store.set('depth_said_' + hit.m, true);
    const zone = g.zone || '';
    const title = K.plain(hit.title || T('depth.cross_title.' + hit.m, { m: hit.m, zone }, '깊이 ' + hit.m + 'm'));
    const line = K.plain(hit.ko || T('depth.first_' + hit.m, { m: hit.m, zone }, '') || T('depth.cross.' + hit.m, { m: hit.m, zone }, '관리실에서 알려 드립니다. 이 집이 이제 ' + hit.m + 'm까지 내려왔습니다.' + (zone ? ' 여기부터는 ' + zone + '입니다.' : '')));
    K.enqueue('depth:' + hit.m, (done) => {
      const el = document.createElement('div'); el.className = 'depthmark' + (hit.m >= 180 ? ' trench' : '');
      el.innerHTML = '<b>' + esc(title) + '</b><span>' + esc(line) + '</span>';
      document.body.appendChild(el);
      K.play(hit.m >= 180 ? 'cue_spot_found.ogg' : 'sfx_note_arrive.ogg', 0.5);
      const off = () => { if (!el.parentNode) return; el.remove(); done(); };
      el.addEventListener('click', off); setTimeout(off, 5200);
    });
    C.log.push('depth ' + hit.m);
  }
  C.depthCheck = depthCheck;
  K.onLoad((st) => { morning(st); loadEvent(); rumorAnnounce(); loadWishes(true); nightCheck(st); firstDayNudge(st); depthCheck(st, true); });
  let lastDay = null;
  K.onApply((st) => {
    const first = lastDay === null;
    if (!first && st.day !== lastDay) loadEvent();
    lastDay = st.day;
    giftCheck(st); lidCheck(st); wishNews(st); loadWishes(false); if (!first) { depthCheck(st, false); nightCheck(st); }
    if (!first && st.night_judge && st.night_judge.report) morning(st);   // 첫 로드의 아침은 onLoad 가 한다
  });
})();
