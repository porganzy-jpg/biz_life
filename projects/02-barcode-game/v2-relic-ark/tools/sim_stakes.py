"""잔해 방주 — 이해관계(stakes)·수집 보강 전/후 비교 (기획·밸런스 소유)

입력: data/balance/stakes.json (+ threats/defense/economy)
감사 스크립트(tools/audit_combat.py·audit_collection.py)의 엔진 호출과 가정을 **그대로 가져와**
stakes.json 규칙을 켠 경우(후)와 끈 경우(전)를 같은 씨앗으로 돌린다. 프로젝트 파일·DB 를 쓰지 않는다.

    python tools/sim_stakes.py           # 전체 (방주 200 × 30일, 가구 120 × 120일)
    python tools/sim_stakes.py --quick   # 방주 60, 가구 40

표
  T1 배치=생산 — 하루 생산과 습격 하나의 값        T2 지배 전략 비율(전원 투입이 최선인 습격)
  T3 성실 vs 게으름 vs 누르지 않기 — 30일          T4 덮개
  T5 값 0 스캔 비율 · 닦기                         T6 도감 50/80% 도달일 · 가문 세트 · 스팟
  T7 세션당 결정 수(추정)
"""
from __future__ import annotations

import io
import itertools
import json
import os
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
with redirect_stdout(io.StringIO()):
    import audit_combat as A          # noqa: E402  (server·combat 를 읽기 전용으로 불러 둔다)
    import audit_collection as AC     # noqa: E402
S, C = A.S, A.C

QUICK = "--quick" in sys.argv
STK = json.load(open(os.path.join(ROOT, "data", "balance", "stakes.json"), encoding="utf-8"))
STAFF = STK["staffing"]["staff_mult"]
CRACK = STK["crack"]
TICKS_PER_DAY = 3
CONTACT_SHARE = 1 / 6        # 접촉 순간의 배치가 그 틱의 남은 시간(평균 반 틱 = 하루의 1/6) 생산을 정한다
ROOM_LOSS_VALUE = 20.0       # 잃은 방 하나의 값(재료 환산): 건설비 ≈8 + 레벨업 일부 + 남은 날의 생산. 효용 비교용 가정
HOME_ORDER = ["pantry", "well", "greenhouse", "decoder"]      # 평소 한 명씩 서는 생산 방(성실)
N_ARK = 60 if QUICK else 200
N_HOUSE = 40 if QUICK else 120


def hr(t):
    print("\n" + "=" * 104 + "\n" + t + "\n" + "=" * 104)


def staff_mult(n: int, on: bool) -> float:
    if not on:
        return 1.0
    return STAFF[min(n, len(STAFF) - 1)]


def daily_base(room: dict) -> float:
    """그 방의 하루 재료 생산(사기·전력 제외)."""
    prod = S.room_produces(room) or {}
    return sum(v for k, v in prod.items() if isinstance(v, (int, float)) and k in ("food", "water", "knowledge", "med", "parts", "cloth")) * TICKS_PER_DAY


def production(st: dict, stations: dict, on: bool) -> float:
    total = 0.0
    cnt = Counter(s for s in stations.values())
    for r in S.live_rooms(st):
        b = daily_base(r)
        if not b:
            continue
        m = staff_mult(cnt.get(r["slot"], 0), on)
        if on and r.get("cracked"):
            m *= CRACK["prod_mult"]
        total += b * m
    return total


def value_of(res: str, sev: int, grade: int, room: dict | None, on: bool) -> float:
    rw = C.reward_for(res, sev, grade)
    v = sum(x for k, x in rw.items() if k != "morale") + 0.5 * rw.get("morale", 0)
    if res == C.SCARRED and on:
        rc = sum(CRACK["repair_cost"].values())
        loss = (1 - CRACK["prod_mult"]) * (daily_base(room) if room else 0) * 0.5      # 다음 접속(반나절)에 고친다
        v -= rc + loss
    if res == C.BREACHED:
        v -= ROOM_LOSS_VALUE
    return v


def home_stations(st: dict) -> dict:
    slots = {r["id"]: r["slot"] for r in S.live_rooms(st)}
    homes = [slots[h] for h in HOME_ORDER if h in slots] or [r["slot"] for r in S.live_rooms(st)][:1]
    return {p["id"]: homes[i % len(homes)] for i, p in enumerate(st["residents_list"])} if homes else {}


def apply_gate_actions(st, cre, slot, sev, spent):
    g = cre["gate"]; acts = []
    if g == "all_inside":
        st["outside"] = []
    if g == "lights_off":
        st["lights"][str(slot)] = False
    if g == "quiet":
        st["power_on"] = False
    if g in ("light_elsewhere", "cloud_water", "make_way", "feed", "return_it", "guide_up"):
        a = C.action_for_gate(g)["id"]; acts = [a]
        for k, v in C.action_cost(a, sev).items():
            spent[k] += v
    return acts


def judge(st, cre, slot, sev, grade, acts, moves, cons=()):
    raid = {"target_slot": slot, "severity": sev, "grade": grade, "acts": acts, "moves": moves}
    return C.evaluate(cre, S.raid_ctx(st, raid, list(cons)))


def sim_ark(uid: str, policy: str, on: bool, days: int = 30):
    """policy: diligent(접촉 누름, 필요한 만큼 옮김) / allin(감사의 greedy: 전원 투입) /
    lazy_spread(한 명씩 세 방, 누르고 아무것도 안 함) / ignore(한 명씩, 접촉을 누르지 않음)."""
    ppl = []
    for i, r in enumerate(A.ACT1):
        stats, _ = S.roll_stats(uid, f"{r}-{i}", r)
        p = A.person(f"{r}-{i}", r, stats["nerve"], eye=stats["eye"], name=r); p["stats"] = stats
        ppl.append(p)
    st = A.make_state([], ppl)
    st["created"] = time.time() - 86400 * days
    out = Counter(); prod_total = 0.0; spent = Counter(); dom = Counter(); lid = Counter()
    for day in range(1, days + 1):
        for d, rid, slot in A.BUILD_PLAN:
            if d == day and not S.room_at(st, slot):
                st["rooms"].append({"id": rid, "slot": slot, "level": 1})
        for d, rid, lv in A.LEVEL_PLAN:
            if d == day:
                for r in st["rooms"]:
                    if r["id"] == rid and not r.get("flooded"):
                        r["level"] = lv
        for d, t in A.TOOL_PLAN:
            if d == day:
                s0 = next((r["slot"] for r in S.live_rooms(st) if r["id"] == "pantry"), None)
                if s0 is not None:
                    st["room_tools"].setdefault(str(s0), []).append({"id": t, "uses": C.TOOLS[t].get("uses")})
        # 평소 자리. 감사의 greedy 는 '전원 식량창고'였다 — 배치=생산이 켜지면 성실한 사람은 한 명씩 선다
        if policy == "allin" and not on:
            pan = next((r["slot"] for r in S.live_rooms(st) if r["id"] == "pantry"), None)
            st["stations"] = {p["id"]: pan for p in st["residents_list"]} if pan is not None else {}
        else:
            st["stations"] = home_stations(st)
        home = dict(st["stations"])
        # 수리(성실은 다음 날 고친다)
        if policy in ("diligent", "allin", "smart") and on:
            for r in S.live_rooms(st):
                if r.get("cracked"):
                    r["cracked"] = False
                    for k, v in CRACK["repair_cost"].items():
                        spent["repair_" + k] += v
        st["lights"] = {}; st["power_on"] = True; st["outside"] = []
        grade = S.grade_of(st)
        cre = C.pick_creature(uid, day, grade)
        day_prod = production(st, home, on)
        if not cre or not cre["threat"]:
            prod_total += day_prod; continue
        slot = C.pick_target(uid, day, cre, S.live_rooms(st), st.get("room_tools") or {})
        if slot is None:
            prod_total += day_prod; continue
        sev = max(0, min(4, C.severity(uid, day, grade)))
        g = cre["gate"]
        target_room = S.room_at(st, slot)
        cap = S.room_cap_of(target_room)

        if policy == "ignore":
            if not on:
                out["무판정"] += 1; prod_total += day_prod; continue
            ev = judge(st, cre, slot, sev, grade, [], 0)          # 21시, 서 있는 배치 그대로, 관문 행동 없음
            res = ev["result"]
            if res == C.BREACHED and STK["night_judge"]["worst_result"] == "scarred":
                res = C.SCARRED
        elif policy == "lazy_spread":
            if g == "all_inside":
                st["outside"] = []        # S15: 무작위 차출 폐지 — 밖에 있는 사람은 원정대뿐(이 sim 에는 원정이 없다)
            res = judge(st, cre, slot, sev, grade, [], 0)["result"]
        else:
            # 성실: 관문 행동을 하고, 옮길 사람의 부분집합을 고른다
            acts = apply_gate_actions(st, cre, slot, sev, spent)
            people = st["residents_list"]
            if g == "quiet":
                big = max(S.live_rooms(st), key=lambda r: S.room_cap_of(r))
                st["stations"] = {p["id"]: big["slot"] for p in people}
                ev = judge(st, cre, slot, sev, grade, acts, 0); res = ev["result"]
                chosen = people
            elif g == "stand_still" and not (on and STK["lid"]["reveal_target"]):
                ev = judge(st, cre, slot, sev, grade, acts, 0); res = ev["result"]     # 공개 전: 서 있는 대로
                chosen = []
            else:
                keep_hall = 1 if g == "guide_up" else 0
                best = None; cands = []
                for k in range(0, len(people) + 1):
                    for sub in itertools.combinations(people, k):
                        if len(sub) > cap or len(people) - len(sub) < keep_hall:
                            continue
                        stn = dict(home)
                        for p in sub:
                            stn[p["id"]] = slot
                        if keep_hall:
                            stn.pop(next(p for p in people if p not in sub)["id"], None)
                        st["stations"] = stn
                        r_ = judge(st, cre, slot, sev, grade, acts, 0)["result"]
                        cost = (production(st, home, on) - production(st, stn, on)) * CONTACT_SHARE
                        u = value_of(r_, sev, grade, target_room, on) - cost
                        cands.append((u, k, sub, r_, stn))
                umax = max(c[0] for c in cands)
                kmax = max(c[1] for c in cands)
                opt = [c for c in cands if c[0] >= umax - 1e-9]
                allin_opt = any(c[1] == kmax for c in opt)
                dom["raids"] += 1
                dom["allin_optimal"] += allin_opt
                dom["allin_unique"] += allin_opt and all(c[1] == kmax for c in opt)
                dom["fewer_is_best"] += min(c[1] for c in opt) < kmax
                if policy == "allin":
                    pick = max((c for c in cands if c[1] == kmax), key=lambda c: c[0])
                else:
                    pick = max(opt, key=lambda c: -c[1])      # 같은 값이면 적게 옮긴다
                res, stn = pick[3], pick[4]
                st["stations"] = stn
                chosen = pick[2]
                if g == "stand_still":
                    lid["revealed_moves_before"] += 1
            if policy == "smart" and on and res == C.BREACHED and STK["night_judge"]["worst_result"] == "scarred":
                res = C.SCARRED          # 미리보기가 '상실'이면 누르지 않고 21시 판정(최악 금)에 맡긴다
                out["미룸"] += 1
            if on:
                day_prod = day_prod * (1 - CONTACT_SHARE) + production(st, st["stations"], on) * CONTACT_SHARE
        if g == "stand_still":
            lid[res] += 1
        out[res] += 1
        if res == C.SCARRED and on and target_room:
            target_room["cracked"] = True
        if res == C.BREACHED and target_room:
            target_room["flooded"] = True
            st["room_tools"].pop(str(slot), None)
        rw = C.reward_for(res, sev, grade)
        prod_total += day_prod + sum(v for k, v in rw.items() if k != "morale")
    lost = sum(1 for r in st["rooms"] if r.get("flooded"))
    cracked = sum(1 for r in st["rooms"] if r.get("cracked") and not r.get("flooded"))
    return {"out": out, "prod": prod_total, "lost": lost, "cracked": cracked, "spent": spent, "dom": dom, "lid": lid}


def combat_tables():
    hr(f"T1. 배치 = 생산 — 방주 하나의 하루 (staff_mult {STAFF}, 접촉 배치는 하루의 {CONTACT_SHARE:.2f} 만큼 생산을 정한다)")
    rooms = [{"id": "pantry", "slot": 2, "level": 1}, {"id": "well", "slot": 1, "level": 1}, {"id": "greenhouse", "slot": 4, "level": 1}]
    st = A.make_state(rooms, [A.person(x, r, 5) for x, r in (("a", "cook"), ("b", "engineer"), ("c", "scout"))])
    cases = {"한 명씩 생산 방": {"a": 2, "b": 1, "c": 4}, "전원 홀(아무도 안 섬)": {}, "전원 식량창고": {"a": 2, "b": 2, "c": 2},
             "둘 식량창고 + 하나 정수실": {"a": 2, "b": 2, "c": 1}}
    print(f"{'배치':<28}{'전(하루)':<10}{'후(하루)':<10}{'후/한 명씩':<12}")
    ref = production(st, cases["한 명씩 생산 방"], True)
    for k, stn in cases.items():
        b, a = production(st, stn, False), production(st, stn, True)
        print(f"{k:<28}{b:<10.1f}{a:<10.1f}{a / ref:<12.0%}")
    allin = production(st, cases["전원 식량창고"], True)
    print(f"  습격 하나에 전원을 식량창고로 몰면, 그날 생산 손실 = ({ref:.1f} − {allin:.1f}) × {CONTACT_SHARE:.2f} = "
          f"{(ref - allin) * CONTACT_SHARE:.2f} (하루의 {(ref - allin) * CONTACT_SHARE / ref:.0%}). 전에는 0.")
    print("  빈 방은 0.5 로 돈다 — 사람이 없어도 굶지 않는다. 전원 홀(감사의 게으름)도 하루 생산의 절반은 들어온다.")

    res = {}
    for pol in ("allin", "diligent", "smart", "lazy_spread", "ignore"):
        for on in (False, True):
            if pol == "smart" and not on:
                continue
            runs = [sim_ark(f"stk{i}", pol, on) for i in range(N_ARK)]
            res[(pol, on)] = runs

    hr(f"T2. 지배 전략 — '관문 + 대상 방 꽉 채우기'가 최선인 습격 비율 (방주 {N_ARK} × 30일, 성실 정책이 받은 습격, 문지기 제외)")
    print(f"{'':<10}{'습격 수':<10}{'전원 투입이 최선(동률 포함)':<26}{'전원 투입만 최선':<18}{'더 적게 옮기는 게 최선':<20}")
    for on in (False, True):
        d = Counter()
        for r in res[("diligent", on)]:
            d.update(r["dom"])
        n = d["raids"]
        print(f"{'후' if on else '전':<10}{n:<10}{d['allin_optimal'] / n:<26.0%}{d['allin_unique'] / n:<18.0%}{d['fewer_is_best'] / n:<20.0%}")
    print("  '전'에서는 점수가 더하기뿐이고 옮기는 비용이 0 이라 전원 투입이 언제나 최선(동률 포함)이다 — 감사 A1(a)와 같다.")
    print("  '후'에서는 옮긴 만큼 생산이 줄어, 덜 옮겨도 막히는 습격에서는 '몇 명을 뺄까'가 실제 답이 된다.")

    hr("T3. 성실 vs 게으름 vs 누르지 않기 — 30일 (같은 uid = 같은 생물·대상·세기)")
    print(f"{'정책':<34}{'':<4}{'막음':<7}{'넘김':<7}{'금':<7}{'상실':<7}{'무판정':<8}{'잃은 방':<9}{'금 남은 방':<11}{'생산+보상':<11}{'수리비':<8}")
    names = {"allin": "전원 투입(감사 greedy)", "diligent": "성실(필요한 만큼)", "lazy_spread": "게으름(한 명씩, 누르기만)",
             "ignore": "누르지 않기", "smart": "성실 + 상실 미리보기면 미룸"}
    for pol in ("allin", "diligent", "smart", "lazy_spread", "ignore"):
        for on in (False, True):
            if (pol, on) not in res:
                continue
            rs = res[(pol, on)]
            o = Counter()
            for r in rs:
                o.update(r["out"])
            tot = sum(o.values()) or 1
            rep = statistics.mean(sum(v for k, v in r["spent"].items() if k.startswith("repair_")) for r in rs)
            print(f"{names[pol]:<34}{'후' if on else '전':<4}" + "".join(f"{o[k] / tot:<7.0%}" for k in (C.HELD, C.PASSED, C.SCARRED, C.BREACHED))
                  + f"{o['무판정'] / tot:<8.0%}{statistics.mean(r['lost'] for r in rs):<9.2f}{statistics.mean(r['cracked'] for r in rs):<11.2f}"
                  f"{statistics.mean(r['prod'] for r in rs):<11.0f}{rep:<8.1f}")
    print(f"  '누르지 않기'는 전에는 아무 일도 없었다(무판정 100%). 후에는 21시에 서 있는 배치로 판정된다(최악 = {STK['night_judge']['worst_result']}).")
    print("  2026-10-03 사용자 결정: 밤 판정은 누른 것과 같다(상한 없음). 대신 잃은 방은 물 찬 칸으로 남아 다시 되찾는다.")
    print("  '성실 + 미룸': 상한이 있을 때만 의미가 있다(상한 없음 결정 뒤에는 성실과 같은 줄이 나와야 맞다).")
    print("  게으름(누르기만)의 방 상실은 이 묶음이 고치지 않는다 — 접촉을 직접 누른 판정에는 상한이 없다(§6 질문).")

    hr("T4. 덮개 — 대상 방 공개 전/후 (성실 정책)")
    for on in (False, True):
        lid = Counter()
        for r in res[("diligent", on)]:
            lid.update(r["lid"])
        n = sum(lid[k] for k in (C.HELD, C.PASSED, C.SCARRED, C.BREACHED))
        if n:
            print(f"  {'후' if on else '전'}: 덮개 {n}회 — 막음 {lid[C.HELD] / n:.0%} · 금 {lid[C.SCARRED] / n:.0%} · 상실 {lid[C.BREACHED] / n:.0%}")
        else:
            print(f"  {'후' if on else '전'}: 덮개가 30일 안에 오지 않았다")
    return res


# ─────────────────────────────────────────────────────────────
# 수집
# ─────────────────────────────────────────────────────────────
POL = STK["polish"]
VAR = STK["variant"]


def variant_hit(code: str, week: int) -> bool:
    return random.Random(f"{code}:{week}").random() < VAR["rate"]


def collect_sim(spd: int, days: int, on: bool, n_house: int, seed: int = 0):
    mix = {k: v for k, v in S.combat._balance("economy")["scan"]["assumed_category_mix"].items() if not k.startswith("_")}
    tpl = AC.GEN.templates
    stems_all = {(c, x["name"].replace("{adj} ", "")) for c in tpl if not c.startswith("_") for x in tpl[c]}
    lore = AC.L("family_lore.json")["families"]
    rules = S.RUMOR_RULES_DEEP
    need_set = (lambda fam: STK["family_sets"]["pieces_required"]) if on else (lambda fam: lore[fam]["set_count"])
    cur = defaultdict(lambda: defaultdict(list))
    for h in range(n_house):
        rng = random.Random(f"{seed}|{h}")
        items = AC.make_household(rng, AC.ASSUME["household_items"], mix)
        order = list(range(len(items))); rng.shuffle(order)
        weights = [1.0 / (r + 1) ** AC.ASSUME["zipf_s"] for r in range(len(items))]
        rank = {i: order[i] for i in range(len(items))}
        stems = set(); var_slots = set(); fam_distinct = defaultdict(set); sets = set()
        rows = Counter(); distinct_rows = defaultdict(set); spots = set()
        recent = []; zero = 0; zero_raw = 0; total = 0; zero_same = 0
        polish = Counter(); polish_days = defaultdict(set); lvl = Counter(); seen = set()
        for day in range(1, days + 1):
            week = (day - 1) // 7
            if day > 1 and (day - 1) % 7 == 0:
                items += AC.make_household(rng, AC.ASSUME["new_items_per_week"], mix)
                weights += [1.0 / (len(weights) // 4 + 1) ** AC.ASSUME["zipf_s"]] * AC.ASSUME["new_items_per_week"]
            w = [1.0 / (rank.get(i, i) + 1) ** AC.ASSUME["zipf_s"] if i in rank else weights[i] for i in range(len(items))]
            for _ in range(spd):
                recent = [(d, c) for d, c in recent if d > day - 7]
                rc = Counter(c for _, c in recent)
                for _t in range(6):
                    i = rng.choices(range(len(items)), weights=w)[0]
                    if rc[items[i]["code"]] == 0 or rng.random() > AC.ASSUME["novelty_reject"]:
                        break
                it = items[i]; code = it["code"]
                mult = AC.rescan_multiplier(rc[code])
                recent.append((day, code)); total += 1
                stem = next(s for (c, s) in stems_all if c == it["cat"] and it["name"].endswith(s))
                stems.add((it["cat"], stem))
                got = mult > 0
                if on:
                    if code in seen and day not in polish_days[code] and lvl[code] < POL["max_level"] - 1:
                        polish_days[code].add(day)
                        polish[code] += 1
                        got = True
                        need = POL["scans_per_level"][lvl[code]]
                        if polish[code] >= need:
                            lvl[code] += 1; polish[code] = 0
                    if variant_hit(code, week) and (it["cat"], stem) not in var_slots:
                        var_slots.add((it["cat"], stem)); got = True
                zero += not got; zero_raw += mult == 0
                zero_same += (not got) and on and (day in polish_days[code] or lvl[code] >= POL["max_level"] - 1)
                seen.add(code)
                rows[it["cat"]] += 1; distinct_rows[it["cat"]].add(code)
                if it["fam"]:
                    fam_distinct[it["fam"]].add(code)
                    if len(fam_distinct[it["fam"]]) >= need_set(it["fam"]):
                        sets.add(it["fam"])
            for sid, rule in rules.items():
                cnt = (sum(len(distinct_rows[c]) for c in rule["categories"]) if (on and STK["spot_unlock"]["count_distinct_barcodes"])
                       else sum(rows[c] for c in rule["categories"]))
                if cnt >= rule["need"]:
                    spots.add(sid)
            cur["stems"][day].append(len(stems))
            cur["codex_ext"][day].append(len(stems) + len(var_slots))
            cur["sets"][day].append(len(sets))
            cur["spots"][day].append(len(spots))
            cur["zero"][day].append(zero / max(1, total))
            cur["zero_raw"][day].append(zero_raw / max(1, total))
            cur["zero_same"][day].append(zero_same / max(1, zero))
            cur["lv3"][day].append(sum(1 for c in lvl if lvl[c] >= POL["max_level"] - 1))
    return cur, len(stems_all)


def reach_day(curve, total, frac, days, n):
    per = []
    for h in range(n):
        d = next((d for d in range(1, days + 1) if curve[d][h] >= frac * total - 1e-9), None)
        per.append(d if d is not None else 10 ** 6)
    m = statistics.median(per)
    return f"{int(m)}" if m < 10 ** 6 else f">{days}"


def collection_tables():
    days = 120
    hr(f"T5·T6. 수집 — 전/후 (가구 {N_HOUSE} × {days}일, 감사 audit_collection 의 가구 가정 그대로)")
    print(f"{'하루':<6}{'':<4}{'값0 스캔(감쇠만)':<16}{'값0 스캔(아무 쓸모 없음)':<22}{'도감 줄기 50/80%':<17}{'도감+변형(66) 50/80%':<20}"
          f"{'가문세트 30일':<13}{'세트 120일':<11}{'스팟 6 다 열림':<14}{'3단계 닦인 물건(30일)':<18}{'남은 값0 중 오늘 이미 닦음/3단계':<20}")
    for spd in (3, 6, 10):
        for on in (False, True):
            cur, n_st = collect_sim(spd, days, on, N_HOUSE, seed=spd)
            m = lambda k, d: statistics.mean(cur[k][d])
            print(f"{spd:<6}{'후' if on else '전':<4}{m('zero_raw', 30):<16.0%}{m('zero', 30):<22.0%}"
                  f"{reach_day(cur['stems'], n_st, .5, days, N_HOUSE) + '/' + reach_day(cur['stems'], n_st, .8, days, N_HOUSE):<17}"
                  f"{reach_day(cur['codex_ext'], 2 * n_st, .5, days, N_HOUSE) + '/' + reach_day(cur['codex_ext'], 2 * n_st, .8, days, N_HOUSE):<20}"
                  f"{m('sets', 30):<13.1f}{m('sets', 120):<11.1f}{reach_day(cur['spots'], 6, 1.0, days, N_HOUSE):<14}{m('lv3', 30):<18.1f}{(m('zero_same', 30) if on else 0):<20.0%}")
    print("  값0(감사만) = 재스캔 감쇠 배율 0 인 스캔 비율(감사 B2 지표). 값0(아무 쓸모 없음) = 배율 0 이면서 닦기 진척도 새 변형도 없는 스캔.")
    print("  도감+변형 = 줄기 33 + 줄기마다 '물빛' 변형 칸 33. 줄기 곡선 자체는 이 묶음이 바꾸지 않는다(줄기 수는 그대로).")
    print("  원정의 봉인 상자(재스캔이 열쇠)는 여기 넣지 않았다 — 넣으면 값0 은 더 준다(sim_expedition X6).")
    print("  카테고리 고정: 감사 B1-2 의 '바코드 하나로 서로 다른 유물 평균 7.00개'가 규칙상 1 이 된다(도감·스팟 부풀리기 차단).")


def decisions_table(res):
    hr("T7. 세션당 결정 수 — 추정(코드의 선택 지점 × 시뮬 빈도)")
    d = {on: Counter() for on in (False, True)}
    for on in (False, True):
        for r in res[("diligent", on)]:
            d[on].update(r["dom"])
    raid_days = d[True]["raids"] / N_ARK / 30
    real_choice = d[True]["fewer_is_best"] / max(1, d[True]["raids"])
    rows = [
        ("습격 '몇 명을 옮길까'(정답이 전원이 아닌 날)", 0.0, raid_days * real_choice),
        ("습격 '지금 누를까, 21시에 맡길까'", 0.0, raid_days),
        ("금 간 방 고칠까(재료 2)", 0.0, None),
        ("덮개: 공개된 방에 미리 설까", 0.0, None),
        ("무엇을 찍을까 — 닦기·물빛·세트 조각", 1.0, 2.0),
        ("원정 누구·어디·얼마나(EXPEDITION §9)", 0.0, 3.0),
    ]
    crack_rate = 0
    for r in res[("diligent", True)]:
        crack_rate += r["out"][C.SCARRED]
    crack_rate /= (N_ARK * 30)
    lid_rate = sum(r["lid"].get("revealed_moves_before", 0) for r in res[("diligent", True)]) / (N_ARK * 30)
    tot_b = tot_a = 0.0
    print(f"{'결정':<44}{'전(하루)':<10}{'후(하루)':<10}")
    for name, b, a in rows:
        if a is None:
            a = crack_rate if "금" in name else lid_rate
        tot_b += b; tot_a += a
        print(f"{name:<44}{b:<10.2f}{a:<10.2f}")
    print(f"{'(기존) 증축·레벨업·카테고리 고르기 등 — 감사 C-1':<44}{'1~4':<10}{'1~4':<10}")
    print(f"{'합(기존 제외)':<44}{tot_b:<10.2f}{tot_a:<10.2f}")
    print("  하루 2~3세션이면 세션당 약 +{:.1f}~{:.1f}개. 원정 3개는 원정이 구현될 때만 들어온다.".format(tot_a / 3, tot_a / 2))


def main():
    t0 = time.time()
    print("잔해 방주 — 이해관계·수집 보강 전/후 (data/balance/stakes.json", STK["_version"] + ")")
    res = combat_tables()
    collection_tables()
    decisions_table(res)
    print(f"\n(완료 {time.time() - t0:.0f}초)")


if __name__ == "__main__":
    main()
