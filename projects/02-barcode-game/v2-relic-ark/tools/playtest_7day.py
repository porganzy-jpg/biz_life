"""7일 플레이테스트 세션 도구 (2026-10-04). 프로젝트 파일을 고치지 않는다.

사용: python tools/playtest_7day.py <persona A|B> <uid> <step...>
step 예: open[:shot.png] scan:shin,milk raid:careful|lazy|look event guests build place
         exp:follow|send|none dayend codex wishes boxes adv:<minutes> ui_scan:shin
각 단계의 출력(화면 문장·결정·오류)을 그대로 찍는다. 일지는 사람이(테스터가) 이 출력을 읽고 쓴다.
"""
from __future__ import annotations

import sys
sys.path.insert(0, __file__.rsplit("\\", 1)[0] if "\\" in __file__ else __file__.rsplit("/", 1)[0])
from playtest_lib import *          # noqa
from playtest_household import code, cat, name, H   # noqa
import random
import playtest_core_a as CA

ROOM_PRI = ["quarters", "storage", "greenhouse", "well", "workshop", "airlock", "generator", "library", "infirmary", "pantry"]


def summary(st):
    print(f"== Day {st.get('day')} | {res_line(st)} | 스캔 {st.get('scans_today')}/{st.get('scan_cap')} | 등급 {st.get('grade')}")
    rooms = [(r['slot'], r['id'], r.get('level'), 'FLOOD' if r.get('flooded') else ('금' if r.get('cracked') else '')) for r in st['rooms']]
    print("   방:", rooms)
    stn = (st.get('combat') or {}).get('stations') or {}
    print("   사람:", [(p['name'], p['role_ko'], stn.get(p['id'], '홀'), 'injured' if p.get('injured') else '', [i.get('name') if isinstance(i, dict) else i for i in p.get('imprints') or []]) for p in st['residents_list']])
    prod = st.get('production') or {}
    print("   생산:", {k: (v.get('room_id'), v.get('staff'), round(v.get('mult', 0), 2), v.get('label')) for k, v in prod.items()})
    print("   공기:", st.get('air'), "| 깊이:", (st.get('gauges') or {}).get('depth', {}).get('m'), "m | 울음:", (st.get('gauges') or {}).get('far_call_sec'))
    o = st.get('octopus') or {}
    print("   문어:", {k: o.get(k) for k in ('arrived', 'name')}, (o.get('mood') or {}).get('ko'), "| 선물:", (o.get('gift_today') or {}).get('ko'))
    print("   상자:", [(x.get('cat_ko'), x.get('age_days')) for x in st.get('boxes') or []], "| 손님:", st.get('guests'), "| 잠자리:", st.get('beds'))
    print("   선반:", len(st.get('shelf') or []), "칸", "| 손패:", len(st.get('hand') or []), "| 가문완성:", st.get('families_done'))
    if st.get('expedition'):
        e = st['expedition']; print("   원정 중:", e.get('member_names'), e.get('dest_ko'), e.get('length'), 'progress', round(e.get('progress') or 0, 2))
    if st.get('flooded_cells'):
        print("   물 찬 칸:", st['flooded_cells'])


SES = None


def do_open(b, shot=None):
    seen = b.open(wait=15, shot=shot, shot_at=7 if shot else None)
    b.report(seen, "열자마자")
    st = (b.payloads.get('/api/ark') or [None])[0] or ark(b.uid)
    summary(st)
    if SES is not None:
        SES.on_open(st)
    print("   선반칸:", (st.get('shelf_room') or {}).get('capacity'), "창고상자:", len(st.get('stored') or []), "| 저장:", st.get('storage'), "| 밤사이:", json.dumps(st.get('overnight'), ensure_ascii=False)[:600])
    if st.get('depth_crossed'): print("   [깊이]", st['depth_crossed'])
    for k in ('night_judge', 'knock', 'wishes_new', 'morning_lines', 'produced_while_away', 'expedition_return'):
        v = st.get(k)
        if v and (not isinstance(v, dict) or any(v.values())):
            print(f"   [{k}]", json.dumps(v, ensure_ascii=False)[:700])
    rr = (b.payloads.get('/api/raid/today') or [None])[-1]
    if rr:
        show_raid(rr)
    ev = (b.payloads.get('/api/event/today') or [None])[-1]
    if ev and ev.get('event'):
        print(f"   [쪽지] 「{ev['event']['name']}」 해결={ev['state'].get('resolved')} 맞는카드={len(ev.get('matching_card_ids') or [])}")
    return st


def do_scans(uid, keys):
    for k in keys:
        scan(uid, code(k), cat(k))


def do_place(uid):
    st = ark(uid)
    mp = st.get('move_preview') or {}
    stn = (st.get('combat') or {}).get('stations') or {}
    for p in st['residents_list']:
        if p.get('injured') or p['id'] in (st.get('outside') or []):
            continue
        opts = mp.get(p['id']) or {}
        def gain(v):
            return v.get('ark_delta_pct') if v.get('ark_delta_pct') is not None else (v.get('room_delta_pct') or 0) + (v.get('from_delta_pct') or 0)
        best = max(((s, v) for s, v in opts.items() if s != 'hall' and v.get('can')), key=lambda x: gain(x[1]) or -999, default=None)
        cur = stn.get(p['id'])
        if best and (gain(best[1]) or 0) > 1:
            r = post('/api/ark/station', {'uid': uid, 'resident_id': p['id'], 'slot': int(best[0])})
            print(f"  [배치] {p['name']}({p['role_ko']}) {cur}→{best[0]}  미리보기 {best[1]}")
            st = r if '_status' not in r else st
            mp = st.get('move_preview') or {}
            stn = (st.get('combat') or {}).get('stations') or {}
        else:
            print(f"  [배치] {p['name']} 그대로({cur}) — 옮겨서 나아지는 곳 없음: {json.dumps(opts, ensure_ascii=False)[:200]}")


def do_build(uid, max_n=2):
    st = ark(uid)
    used = {r['slot'] for r in st['rooms'] if not r.get('flooded')}
    flooded = [r['slot'] for r in st['rooms'] if r.get('flooded')]
    have = {r['id'] for r in st['rooms'] if not r.get('flooded')}
    bo = st['build_options']
    can = [k for k in ROOM_PRI if bo.get(k, {}).get('can') and (k not in have or k in ('quarters', 'storage'))]
    print("  [짓기] 지을 수 있는 것:", [(k, bo[k]['cost']) for k in bo if bo[k].get('can')])
    n = 0
    for rid in can:
        if n >= max_n:
            break
        free = flooded + [s for s in range(st.get('slots', 10)) if s not in used and s not in flooded]
        if not free:
            print("   빈 칸 없음"); break
        for s in free:
            r = post('/api/ark/build', {'uid': uid, 'room_id': rid, 'slot': s}, quiet=True)
            if '_status' not in r:
                print(f"   지음: {rid} @ {s}" + (f" (되찾기 {r.get('reclaimed')})" if r.get('reclaimed') else ''))
                used.add(s); n += 1; break
        else:
            print(f"   {rid}: 놓을 칸 없음(마지막 오류 {r.get('detail')})")
    st = ark(uid)
    for slot, u in (st.get('upgrades') or {}).items():
        if u and u.get('can'):
            r = post('/api/ark/upgrade', {'uid': uid, 'slot': int(slot)})
            if '_status' not in r:
                print(f"   올림: {r.get('upgraded')}")
        elif u:
            print(f"   올리기 {slot}: {json.dumps(u, ensure_ascii=False)[:250]}")


def do_event(uid):
    ev = get(f'/api/event/today?uid={uid}')
    if not ev.get('event') or ev['state'].get('resolved'):
        print("  [쪽지] 없음/처리됨"); return
    e = ev['event']
    print(f"  [쪽지] 「{e['name']}」 {e['text'][:260]}")
    m = ev.get('matching_card_ids') or []
    r = post('/api/event/resolve', {'uid': uid, 'card_id': m[0] if m else None})
    print(f"   → {'맞는 카드' if m else '카드 없이'}: countered={r.get('countered')} applied={json.dumps(r.get('applied'), ensure_ascii=False)[:200]} voice={(r.get('voice') or {}).get('text')}")
    for n in r.get('new_imprints') or []:
        print(f"   각인: {n.get('resident')} 「{n['imprint'].get('name')}」 {n.get('line')}")


def gate_fix(uid, raid):
    g = ((raid.get('ready') or {}).get('gate') or {})
    kind = g.get('kind'); tslot = raid.get('target_slot')
    act = raid.get('action') or {}
    print(f"   관문: {kind} — {g.get('ko')} | 행동: {json.dumps(act, ensure_ascii=False)[:300] if act else '-'}")
    if g.get('ok'):
        return
    if kind == 'lights_off':
        post('/api/ark/light', {'uid': uid, 'slot': tslot, 'on': False})
    elif kind == 'quiet':
        post('/api/ark/power', {'uid': uid, 'on': False})
    elif kind == 'all_inside':
        post('/api/ark/recall', {'uid': uid})
    elif act and act.get('id') and not act.get('done'):
        r = post('/api/ark/act', {'uid': uid, 'action': act['id']})
        print("   행동 결과:", json.dumps({k: r.get(k) for k in ('ok', 'paid', 'ko', 'detail')}, ensure_ascii=False)[:300])


def do_raid(uid, policy):
    r = get(f'/api/raid/today?uid={uid}')
    raid = show_raid(r)
    if not raid or raid.get('none') or raid.get('resolved'):
        return
    if policy == 'look':
        return
    if raid.get('stage') == 'sound':
        a = post('/api/raid/advance', {'uid': uid})
        raid = a.get('raid') or raid
        print("  [실루엣]", (raid.get('creature') or {}).get('silhouette'), "| 노리는 방:", raid.get('target_room'))
        print("   미리보기:", json.dumps(raid.get('ready'), ensure_ascii=False)[:600])
    if raid.get('card_mode') == 'clue':
        print("  [단서 모드] 버릇:", raid.get('habit'), "| 동사:", json.dumps(raid.get('verbs'), ensure_ascii=False)[:900], "| 만남:", ((ark(uid).get('combat') or {}).get('encounters')))
        if policy == 'careful':
            print("   (단서 모드 — 사람이 판단해서 verb/act 단계로 이어 간다)"); return
    if policy == 'careful':
        gate_fix(uid, raid)
        st = ark(uid)
        tslot = raid.get('target_slot'); cap = (st.get('room_caps') or {}).get(str(tslot)) or 4
        n = 0
        for p in st['residents_list']:
            if p.get('injured') or p['id'] in (st.get('outside') or []):
                continue
            if n >= cap:
                break
            rr = post('/api/ark/station', {'uid': uid, 'resident_id': p['id'], 'slot': tslot}, quiet=True)
            if '_status' not in rr:
                n += 1
        raid = get(f'/api/raid/today?uid={uid}')['raid']
        gate_fix(uid, raid)
        raid = get(f'/api/raid/today?uid={uid}')['raid']
        print("   옮긴 뒤 미리보기:", json.dumps(raid.get('ready'), ensure_ascii=False)[:600])
    if policy in ('careful', 'lazy'):
        a = post('/api/raid/advance', {'uid': uid})
        print("  [접촉 결과]", json.dumps({k: a.get(k) for k in ('result', 'result_ko', 'line', 'gained', 'lost_room', 'room_name', 'imprints', 'new_imprints')}, ensure_ascii=False)[:900])
        # 불·전원 되돌리기
        st = ark(uid)
        if not st.get('power_on', True) or (st.get('combat') or {}).get('power_on') is False:
            post('/api/ark/power', {'uid': uid, 'on': True})
        post('/api/ark/light', {'uid': uid, 'slot': raid.get('target_slot'), 'on': True}, quiet=True)


def do_guests(uid, accept=True):
    en = get(f'/api/entrance?uid={uid}')
    print("  [문간]", [(p.get('name'), p.get('activity_ko')) for p in en.get('people') or []], "잠자리", en.get('beds'))
    for g in en.get('guests') or []:
        print(f"   손님: {g.get('name')} {g.get('role_ko')} {g.get('stats')} {g.get('quirk', {}).get('ko') if isinstance(g.get('quirk'), dict) else ''} src={g.get('src')}")
        if accept:
            r = post('/api/entrance/guest', {'uid': uid, 'guest_id': g['id'], 'accept': True})
            print("   → 들임:", r.get('ko') or r.get('detail') or 'ok')


def pick_members(st, opts, n=1):
    cands = [r for r in opts.get('residents') or [] if r.get('can')]
    cands.sort(key=lambda r: -(r['stats'].get('breath', 0) + r['stats'].get('nerve', 0)))
    return [r['id'] for r in cands[:n]]


def do_exp(uid, mode, b=None, prefer=None, n=1, shot_mid=None, shot_ret=None):
    o = get(f'/api/expedition/options?uid={uid}')
    if o.get('out'):
        print("  [원정] 이미 나가 있음", o['out']); return
    print("  [원정 선택지]", [(d['ko'], d['lengths'], d['can'], d.get('why')) for d in o.get('dests') or []], "| 공기", o.get('air'), "| 잠수복", o.get('suits'))
    dests = [d for d in o['dests'] if d['can']]
    order = prefer or ['clue', 'spot', 'unknown', 'door']
    dsel = None
    for kind in order:
        dsel = next((d for d in dests if d['dest']['kind'] == kind), None)
        if dsel:
            break
    if not dsel:
        print("   갈 곳 없음"); return
    L = next((l for l in (['half', 'long', 'short'] if mode != 'quick' else ['short', 'half']) if l in dsel['lengths'] and o['lengths'][l]['can']), None)
    mem = pick_members(None, o, n)
    pv = post('/api/expedition/preview', {'uid': uid, 'members': mem, 'dest': dsel['dest'], 'length': L})
    print(f"   미리보기 {dsel['ko']} {L} {mem}: {json.dumps({k: pv.get(k) for k in ('actions', 'carry', 'air_cost', 'air_after', 'danger', 'discover_p', 'rescue_p', 'warnings', 'errors')}, ensure_ascii=False)[:700]}")
    if pv.get('errors'):
        if n == 2:
            return do_exp(uid, mode, b, prefer, 1, shot_mid, shot_ret)
        if L == 'half' and 'short' in dsel['lengths']:
            L = 'short'
        else:
            return
    s = post('/api/expedition/start', {'uid': uid, 'members': mem, 'dest': dsel['dest'], 'length': L})
    if '_status' in s:
        return
    e = s['expedition']; print(f"   출발: {e.get('member_names')} → {e.get('dest_ko')} ({L}) 귀환 {time.strftime('%H:%M', time.localtime(e.get('returns_at')))}")
    if mode == 'follow' and b:
        def chooser(txt, labels):
            # 위험: 숨기 확률이 표시되면 숨는다. 갈림길: 상자·유물 쪽(어둠)
            if any('숨' in l for l in labels):
                return next(i for i, l in enumerate(labels) if '숨' in l)
            if any('어둠' in l for l in labels):
                return next(i for i, l in enumerate(labels) if '어둠' in l)
            return 0
        follow_expedition(b, e['id'], pick_choice=chooser, shot_mid=shot_mid, shot_ret=None, max_s=60)
        sc = get(f'/api/expedition/scene?uid={uid}', quiet=True)
        print("   장면 후 상태:", sc.get('next'), sc.get('committed'), json.dumps((sc.get('carry') or {}).get('items'), ensure_ascii=False)[:300])


def do_return_view(b, uid, shot=None):
    """돌아온 원정을 3D 귀환 장면으로 본다(따라간 원정만)."""
    x = get(f'/api/expedition?uid={uid}')
    ret = x.get('expedition_return')
    if not ret:
        print("  [귀환] 아직/없음", (x.get('expedition') or {}).get('progress')); return
    print("  [귀환 데이터]", json.dumps(ret, ensure_ascii=False)[:1200])
    if b:
        seen, btns = follow_expedition(b, ret['id'], shot_ret=shot, max_s=70)
        if btns:
            btns[-1].click(); time.sleep(2)
    post('/api/expedition/seen', {'uid': uid})


def do_dayend(uid):
    d = get(f'/api/day_end?uid={uid}')
    print("  [하루 마감]", d.get('open'))
    for l in d.get('lines') or []:
        print("    -", l.get('text'))
    for l in d.get('facts_ko') or []:
        print("    ·", l)
    print("    ", d.get('closing'), d.get('close'))


def do_codex(uid):
    c = get(f'/api/collection?uid={uid}')
    fams = [(f['name'], f['have'], f['total']) for f in c.get('families') or [] if f.get('known')]
    print("  [도감] 가문:", fams, f"완성 {c.get('families_done')}/{c.get('families_total')}")
    print("   생물:", [(x.get('name'), x.get('times'), x.get('last_result')) for x in c.get('creatures') or [] if x.get('known')])
    print("   문어선물:", [x.get('name') for x in c.get('octopus_finds') or [] if x.get('known')], "| 희귀도", c.get('rarity'), "| 스팟", c.get('spots'))
    cx = get(f'/api/codex?uid={uid}')
    print("   물건 칸:", [(x['category_ko'], x['found'], x['total']) for x in cx])


def do_wishes(uid):
    for w in get(f'/api/wishes?uid={uid}'):
        print(f"  [바람] {w.get('name')}: {w.get('wish')} | {w.get('condition')} {w.get('progress')} done={w.get('done')} 「{w.get('line')}」")


def do_boxes(uid):
    for x in get(f'/api/boxes?uid={uid}'):
        print(f"  [상자] {x.get('pattern')} {x.get('cat_ko')} {x.get('age_days')}일 pry_ok={x.get('pry_ok')}")


def main():
    global SES
    persona, uid = sys.argv[1], sys.argv[2]
    SES = CA.Session(persona, uid)
    rng = random.Random(f"{uid}|{len(sys.argv)}|{time.time()//60}")
    b = None
    def B():
        nonlocal b
        if b is None:
            b = Base(persona, uid)
        return b
    for step in sys.argv[3:]:
        k, _, arg = step.partition(':')
        print(f"\n### {k} {arg}")
        if k == 'open':
            do_open(B(), arg or None)
        elif k == 'scan':
            do_scans(uid, [x for x in arg.split(',') if x])
        elif k == 'ui_scan':
            bb = B()
            if not bb.page.url.endswith('/base'):
                bb.open(wait=4)
            for x in arg.split(','):
                ui_scan(bb, code(x), cat(x))
        elif k == 'raid':
            do_raid(uid, arg or 'careful')
        elif k == 'event':
            do_event(uid)
        elif k == 'guests':
            do_guests(uid, arg != 'no')
        elif k == 'build':
            do_build(uid, int(arg or 2))
        elif k == 'place':
            do_place(uid)
        elif k == 'exp':
            parts = (arg or 'send').split(',')
            do_exp(uid, parts[0], B() if parts[0] == 'follow' else None,
                   prefer=parts[1].split('/') if len(parts) > 1 and parts[1] else None,
                   n=int(parts[2]) if len(parts) > 2 else 1,
                   shot_mid=parts[3] if len(parts) > 3 else None)
        elif k == 'ret':
            do_return_view(B() if arg and arg != 'api' else None, uid, shot=arg if arg and arg.endswith('.png') else None)
        elif k == 'seen':
            post('/api/expedition/seen', {'uid': uid})
        elif k == 'dayend':
            do_dayend(uid)
        elif k == 'codex':
            do_codex(uid)
        elif k == 'wishes':
            do_wishes(uid)
        elif k == 'boxes':
            do_boxes(uid)
        elif k == 'pry':
            for x in get(f'/api/boxes?uid={uid}'):
                if x.get('pry_ok'):
                    print('  [억지로 열기]', post('/api/box/pry', {'uid': uid, 'box_id': x['id']}))
        elif k == 'name':
            print('  [문어 이름]', post('/api/octopus/name', {'uid': uid, 'name': arg}))
        elif k == 'repair':
            st = ark(uid)
            for r in st['rooms']:
                if r.get('cracked'):
                    print('  [수리]', json.dumps(post('/api/ark/repair', {'uid': uid, 'slot': r['slot']}), ensure_ascii=False)[:300])
        elif k == 'loop':
            if SES.d['day'] is None:
                SES.on_open(ark(uid))
            CA.do_loop(persona, uid, [x for x in arg.split(',') if x], SES, rng)
        elif k == 'arcs':
            CA.do_arcs(persona, uid, SES)
        elif k == 'decor':
            CA.do_decor(persona, uid, SES, int(arg or 2))
        elif k == 'feast':
            st = ark(uid); ids = [p['id'] for p in st['residents_list']][:2]
            r = post('/api/feast', {'uid': uid, 'pair': ids}); print('  [잔치]', r.get('ko') or r.get('detail') or json.dumps(r, ensure_ascii=False)[:300])
            if '_status' not in r: SES.d['decisions'].append('잔치')
        elif k == 'leave':
            CA.do_leave(uid, SES)
        elif k == 'contract':
            CA.do_contract(SES)
        elif k == 'report':
            CA.same_answer_report(uid)
        elif k == 'verb':
            r = post('/api/raid/verb', {'uid': uid, 'verb': arg or None}); rd = r.get('raid') or r
            print('  [동사]', arg, json.dumps(rd.get('ready') if isinstance(rd, dict) else r, ensure_ascii=False)[:700])
        elif k == 'act':
            r = post('/api/ark/act', {'uid': uid, 'action': arg}); print('  [행동]', json.dumps({x: r.get(x) for x in ('ok', 'paid', 'ko', 'detail')}, ensure_ascii=False)[:300])
        elif k == 'light':
            sl, on = arg.split(','); post('/api/ark/light', {'uid': uid, 'slot': int(sl), 'on': on == 'on'}); print('  [불]', arg)
        elif k == 'power':
            post('/api/ark/power', {'uid': uid, 'on': arg == 'on'}); print('  [전원]', arg)
        elif k == 'gather':
            st = ark(uid); sl = int(arg); n = 0
            for p in st['residents_list']:
                rr = post('/api/ark/station', {'uid': uid, 'resident_id': p['id'], 'slot': sl}, quiet=True)
                n += '_status' not in rr
            print('  [모이기]', sl, n, '명')
        elif k == 'peek':
            rr = get(f'/api/raid/today?uid={uid}'); show_raid(rr); print('   card_mode', (rr.get('raid') or {}).get('card_mode'), 'verb', (rr.get('raid') or {}).get('verb'))
        elif k == 'contact':
            a = post('/api/raid/advance', {'uid': uid}); print("  [접촉]", json.dumps({x: a.get(x) for x in ('stage', 'result', 'result_ko', 'line', 'gained', 'lost_room', 'room_name')}, ensure_ascii=False)[:700])
        elif k == 'trade':
            g, t, n = arg.split(','); r = post('/api/workshop/trade', {'uid': uid, 'give': g, 'get': t, 'n': int(n)}); print('  [바꾸기]', json.dumps({x: r.get(x) for x in ('ok', 'ko', 'detail', 'paid', 'got')}, ensure_ascii=False)[:300])
        elif k == 'swap':
            st = ark(uid)
            for it in (st.get('stored') or [])[:int(arg or 1)]:
                r = post('/api/shelf/swap', {'uid': uid, 'stored_id': it['id']}); print('  [선반올리기]', it.get('relic_name') or it.get('name'), r.get('ko') or r.get('detail'))
        elif k == 'adv':
            print('  [시간]', advance(uid, float(arg)))
        elif k == 'sum':
            summary(ark(uid))
        elif k == 'shot':
            B().shot(arg)
    if b:
        b.close()


if __name__ == '__main__':
    main()
