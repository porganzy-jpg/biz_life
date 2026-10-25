/* 질랜디아 — S34 「사람이 주인공」(C안). base_guide.js 다음에 불린다.
 *  1) 첫 화면 얼굴 띠: 위 줄 바로 아래, 식구마다 얼굴 + 이름 + 기색 한 줄 + 오늘 필요 표시 + 열린 이야기 표시. 누르면 그 사람 카드
 *  2) 건네기 결과 칩: 건넨 직후 「사기 +2 · 식량창고 생산 +10%(오늘) · 수첩 +1 · 이야기 2/4」(서버 effects 에 있는 것만. 마음은 S34 서버 뒤)
 *  3) 「어디로」 이유 표시(필요·좋아함·반가움·매듭·기억·꾸밈)를 누르면 무엇에 좋은지 한 줄
 */
(() => {
  'use strict';
  const K = window.ARKBASE && window.ARKBASE._k; if (!K) return;
  const $ = (s) => document.querySelector(s);
  const esc = K.esc, plain = K.plain;
  const D = window.ARKPEOPLE = { log: [] };              // ★ 검수용
  const T = (k, fb) => (K.ext.T ? K.ext.T(k, {}, '') : '') || fb;
  const txt = (x) => (x == null ? '' : typeof x === 'string' ? x : (x.ko || x.line || x.text || x.name || ''));

  // 얼굴: base_core 와 같은 시트 자르기(생활형 도트 idle 첫 칸의 머리)
  function face(p, size) {
    const sheet = '/static/art/chars/front/p2/indoor/' + encodeURIComponent(p.role || 'scout') + (p.body === 'b' ? '_b' : '') + '.png', k = size / 104;
    return '<i class="face" data-role="' + esc(p.role || '') + '" style="width:' + size + 'px;height:' + size + 'px;background-image:url(' + sheet + ');background-size:' + (768 * k).toFixed(1) + 'px auto;background-position:-' + (76 * k).toFixed(1) + 'px -' + (28 * k).toFixed(1) + 'px" aria-hidden="true"></i>';
  }

  // ══ 0. S34 마음 다섯 칸 · 편한 방 ═══════════════════════════════════
  const HEART_N = 5;
  function heartOf(rid) { const c = (((K.ark || {}).core || {}).residents || {})[rid] || {}; return c.heart || null; }
  function heartPips(h, big) {
    const lv = Math.max(0, Math.min(HEART_N, (h && h.level) | 0));
    // 다음 칸까지 얼마나 찼나(문턱 levels[lv-1] → levels[lv])
    const L = (h && h.levels) || [], lo = lv > 0 ? (L[lv - 1] || 0) : 0, hi = L[lv] != null ? L[lv] : null;
    const part = hi != null && hi > lo ? Math.max(0, Math.min(1, ((h.points || 0) - lo) / (hi - lo))) : 0;
    let out = '';
    for (let i = 0; i < HEART_N; i++) out += '<i class="hp' + (i < lv ? ' on' : '') + '"' + (i === lv && part > 0 ? ' style="--f:' + Math.round(part * 100) + '%"' : '') + '></i>';
    return '<span class="hpips' + (big ? ' big' : '') + '" aria-label="마음 ' + lv + '/' + HEART_N + '">' + out + '</span>';
  }
  K.ext.heartRow = (rid, withComfort) => {
    const h = heartOf(rid), c = (((K.ark || {}).core || {}).residents || {})[rid] || {};
    if (!h && !c.comfort_room) return '';
    const rc = (K.ark || {}).rooms_catalog || K.catalog || {};
    const cname = c.comfort_room ? ((rc[c.comfort_room] || {}).name || c.comfort_room) : '';
    const left = h && h.next != null ? Math.max(0, Math.round((h.next - (h.points || 0)) * 10) / 10) : null;
    return '<p class="pheart">' + (h ? '<b>마음</b> ' + heartPips(h, true) + (left ? ' <small>다음 칸까지 ' + left + '</small>' : '') : '') + '</p>' +
      (withComfort && cname ? '<p class="pcomfort"><i class="houseico" aria-hidden="true"></i>편한 방 <b>' + esc(cname) + '</b>' +
        (c.comfort_now ? ' <small>지금 여기 계십니다</small>' : (c.comfort_built === false ? ' <small>아직 없는 방입니다</small>' : '')) + '</p>' : '');
  };

  // ══ 1. 얼굴 띠 ════════════════════════════════════════════════
  const strip = document.createElement('div'); strip.id = 'faces'; strip.className = 'faces'; strip.hidden = true;
  strip.setAttribute('role', 'list'); strip.setAttribute('aria-label', '식구');
  ($('#base') || document.body).appendChild(strip);
  function moodOf(p, c) {
    // 기색 한 줄: 열린 이야기 > 오늘 필요(받았으면 받음) > 반가운 물건이 있으면 그것 > 조용함
    const arc = c.arc || {}, nx = arc.next || {};
    if (c.third_memory_open) return { line: T('faces.third_memory', '세 번째 기억을 꺼낼 듯합니다'), story: true };
    if (nx.open && !arc.done) return { line: plain(c.arc_line || T('faces.story_open', '할 이야기가 있는 눈치입니다')), story: true };
    if (document.body.classList.contains('hh-dim') || ((K.ark || {}).household_dim)) return { line: T('faces.household_dim', '살림이 비어 다들 기운이 없습니다') };   // S35 오늘 필요가 쉰다
    const nd = (c.needs_today || [])[0];
    if (nd && c.given_need_today) return { line: T('faces.need_met', '오늘 바라던 것을 받으셨습니다'), need: 'met' };
    if (nd && K.ext.unlocked && K.ext.unlocked('mood_hints')) return { line: T('faces.need_hint', '뭔가 찾는 눈치입니다'), need: 'want' };   // 기색 날(4일째~)에는 무엇인지 말하지 않는다 — 수첩·기색으로 맞힌다
    if (nd) return { line: plain(nd.announce ? nd.announce.replace(/^.*?님이\s*/, '') : (txt(nd) + ' 쪽을 찾으십니다')), need: 'want' };
    return { line: T('faces.quiet', '오늘은 조용히 지내십니다') };
  }
  let lastKey = '';
  function drawFaces() {
    const a = K.ark || {}, ppl = a.residents_list || [], cr = (a.core || {}).residents || {};
    if (!ppl.length) { strip.hidden = true; return; }
    const outside = ((a.combat || {}).outside) || [];
    const rows = ppl.map(p => ({ p, m: moodOf(p, cr[p.id] || {}), out: outside.indexOf(p.id) >= 0, h: (cr[p.id] || {}).heart || null, home: !!(cr[p.id] || {}).comfort_now }));
    const key = JSON.stringify(rows.map(r => [r.p.id, r.m.line, r.m.need, r.m.story, r.out, r.h && r.h.level, r.h && r.h.points, r.home]));
    if (key === lastKey && !strip.hidden) return; lastKey = key;
    strip.innerHTML = rows.map(r => '<button class="fchip' + (r.out ? ' out' : '') + '" role="listitem" data-pid="' + esc(r.p.id) + '" title="' + esc(r.p.name + ' · ' + r.m.line) + '">' +
      face(r.p, innerHeight <= 500 ? 28 : 34) +
      '<span class="fname"><b>' + esc(r.p.name) + '</b>' +
        (r.m.need ? '<i class="fneed ' + r.m.need + '" aria-label="' + (r.m.need === 'met' ? '받음' : '오늘 필요') + '"></i>' : '') +
        (r.m.story ? '<i class="fstory" aria-label="이야기"></i>' : '') + (r.home ? '<i class="houseico sm" aria-label="편한 방에 계심"></i>' : '') + (r.h ? heartPips(r.h) : '') + '</span>' +
      '<small class="fline">' + esc(r.out ? T('faces.outside', '바깥에 나가 계십니다') : r.m.line) + '</small></button>').join('');
    strip.hidden = false;
    D.faces = rows.map(r => ({ id: r.p.id, name: r.p.name, line: r.m.line, need: r.m.need || null, story: !!r.m.story }));
    layoutTop();
  }
  strip.addEventListener('click', (e) => {
    const b = e.target.closest('[data-pid]'); if (!b) return;
    e.stopPropagation();
    const p = ((K.ark || {}).residents_list || []).find(x => x.id === b.dataset.pid); if (!p) return;
    if (K.ext.onPersonTap) K.ext.onPersonTap({ id: p.id, name: p.name, role: p.role }, '');
    D.log.push('face ' + p.id);
  });
  // 띠가 맨 위(위 줄 바로 아래), 그 아래 「다음 할 일」, 그 아래 목표 판
  function layoutTop() {
    const tb = $('#topbar'), top0 = tb ? tb.getBoundingClientRect().bottom : 44;
    strip.style.top = (top0 + 4) + 'px';
    const sb = strip.hidden ? top0 : strip.getBoundingClientRect().bottom;
    const ns = $('#nextstep'); if (ns) ns.style.top = (sb + 6) + 'px';
  }
  K.onApply(() => setTimeout(drawFaces, 0));
  // 패널(짓기·도감 등)이 열리면 얼굴 띠는 잠시 숨는다 — 큰 창은 하나(패널 위로 띠가 겹치던 것)
  const pn = document.getElementById('panel');
  if (pn) new MutationObserver(() => { strip.style.visibility = pn.hidden ? '' : 'hidden'; }).observe(pn, { attributes: true, attributeFilter: ['hidden'] });
  addEventListener('resize', () => { lastKey = ''; drawFaces(); });
  setInterval(layoutTop, 600);

  // ══ 2. 건네기 결과 칩 ═══════════════════════════════════════════
  const RES_KO = K.RES_KO || {};
  const SV_KIND = { morale: 'morale', room_bonus: 'room', notebook: 'note', heart: 'heart', heart_level: 'heart', returned: 'returned' };
  function chipsOf(res) {
    const ef = (res && res.effects) || {}, out = [];
    if (Array.isArray(ef.chips) && ef.chips.length) {       // S34 서버 effects.chips [{kind, ko}]
      ef.chips.filter(c => c && c.ko && c.kind !== 'keepsake').forEach(c => out.push({ k: SV_KIND[c.kind] || c.kind, t: plain(c.ko) }));
      if (ef.arc && ef.arc.step) out.push({ k: 'story', t: '이야기 ' + ef.arc.step + '/' + (ef.arc.steps || '') });
      return out.slice(0, 5);
    }
    if (ef.morale) out.push({ k: 'morale', t: '사기 ' + (ef.morale > 0 ? '+' : '') + ef.morale });
    if (ef.room_bonus && ef.room_bonus.pct) {
      const rm = ((K.ark || {}).rooms || []).find(r => r.slot === ef.room_bonus.slot), nm = rm ? ((K.catalog[rm.id] || {}).name || rm.id) : '방';
      out.push({ k: 'room', t: nm + ' 생산 +' + ef.room_bonus.pct + '%(오늘)' });
    }
    const rv = res.revealed; if (rv && (rv.new || rv.kind)) out.push({ k: 'note', t: '수첩 +1' });
    const hv = ef.heart;                                     // S34 서버: effects.heart {gain, total, level, ko}
    if (hv && typeof hv === 'object' && (hv.ko || hv.gain)) out.push({ k: 'heart', t: plain(hv.ko || ('마음 +' + hv.gain)) });
    else if (typeof hv === 'number' && hv) out.push({ k: 'heart', t: '마음 ' + (hv > 0 ? '+' : '') + hv });
    if (ef.arc && ef.arc.step) out.push({ k: 'story', t: '이야기 ' + ef.arc.step + '/' + (ef.arc.steps || '') });
    if (ef.memory) out.push({ k: 'memory', t: '기억 하나' });
    if (ef.decor && ef.decor.items != null) out.push({ k: 'decor', t: '꾸밈 ' + ef.decor.items + '/' + (ef.decor.cap || '') });
    // 머리맡 물건은 관리실 한 줄(keepsake.line)이 따로 말하므로 칩에는 넣지 않는다(같은 말 두 번 없이)
    return out.slice(0, 5);
  }
  const chipBox = document.createElement('div'); chipBox.className = 'giftchips'; chipBox.hidden = true; chipBox.setAttribute('aria-live', 'polite');
  ($('#base') || document.body).appendChild(chipBox);
  let chipT = 0;
  function showChips(res) {
    const cs = chipsOf(res); D.lastChips = cs.map(c => c.t); D.chipsIn = 'float';
    if (!cs.length) return;
    chipBox.innerHTML = cs.map((c, i) => '<span class="gchip gc-' + c.k + '" style="--i:' + i + '">' + esc(c.t) + '</span>').join('');
    chipBox.hidden = false; chipBox.classList.remove('off'); void chipBox.offsetWidth; chipBox.classList.add('in');
    clearTimeout(chipT); chipT = setTimeout(() => { chipBox.classList.remove('in'); chipBox.classList.add('off'); setTimeout(() => { chipBox.hidden = true; }, 500); }, 4200);
    D.log.push('chips ' + cs.length);
  }
  K.ext.giftChips = showChips;
  K.ext.chipsHTML = (res) => { const cs = chipsOf(res); D.lastChips = cs.map(c => c.t); D.chipsIn = 'card'; return cs.map(c => '<span class="gchip gc-' + c.k + '">' + esc(c.t) + '</span>').join(''); };

  // ══ 3. 「어디로」 이유 표시를 누르면 한 줄 ═══════════════════════════
  const WHY_HELP = {
    need: '오늘 그분께 꼭 필요한 것입니다. 건네면 그 방 일이 오늘 더 잘 돌아갑니다.',
    like: '그분이 좋아하는 쪽입니다. 사기가 오르고, 머리맡에 남기도 합니다.',
    warm: '딱 맞진 않아도 반가워하십니다. 사기가 조금 오릅니다.',
    chain: '그분 이야기의 다음 매듭입니다. 건네면 이야기가 한 걸음 움직입니다.',
    arc: '그분 이야기의 다음 매듭입니다. 건네면 이야기가 한 걸음 움직입니다.',
    memory: '그분의 옛 기억을 건드리는 물건입니다. 수첩에 기억이 하나 열립니다.',
    decor: '방에 두는 물건입니다. 모이면 그 방 분위기(꼬리표)가 생기고 손님이 찾아옵니다.',
  };
  const pop = document.createElement('div'); pop.className = 'whypop'; pop.hidden = true; document.body.appendChild(pop);
  let popT = 0;
  document.addEventListener('click', (e) => {
    const w = e.target.closest && e.target.closest('.gopt .why'); if (!w) { if (!pop.hidden && !(e.target.closest && e.target.closest('.whypop'))) pop.hidden = true; return; }
    e.preventDefault(); e.stopPropagation();                // 이유 표시를 누른 것은 건네기가 아니다
    const k = ((w.className.match(/why-(\w+)/) || [])[1]) || '';
    const line = T('why_help.' + k, WHY_HELP[k] || '');
    if (!line) return;
    pop.textContent = plain(line);
    const r = w.getBoundingClientRect(), wd = Math.min(260, innerWidth - 16);
    pop.style.width = wd + 'px'; pop.style.left = Math.max(8, Math.min(innerWidth - wd - 8, r.left)) + 'px';
    pop.hidden = false; const h = pop.offsetHeight;
    pop.style.top = (r.top - h - 8 > 8 ? r.top - h - 8 : r.bottom + 8) + 'px';
    clearTimeout(popT); popT = setTimeout(() => { pop.hidden = true; }, 5000);
    D.log.push('why ' + k);
  }, true);

  D.state = () => ({ faces: D.faces || null, chips: D.lastChips || null, chipsIn: D.chipsIn || null, why: pop.hidden ? null : pop.textContent });
  if (K.ark) drawFaces();
})();
