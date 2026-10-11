"""잔해 방주(질랜디아) — S22 수치 + 2단계 「기억 벽」 시뮬레이션 (기획·밸런스 소유)

    python tools/sim_s22.py            # 씨앗 30
표
  V1 전역 이름 투표 — 문턱(최소 방주 수·동의 비율)별 정확도·적용률
  F1 사슬 매듭 대체(소프트 폴백) — 하위 종류 하나를 기다릴 때 며칠이면 찍히나
  N1 사람 수첩 — 3일째부터 기색, 라벨이 돌아오는 속도(A·B)
  B1 기억 벽 꾸러미 — 7/14/30일 채움(A·B, 기억 속 물건 켬/끔)
가정 물건은 tools/playtest_household.py 32종 + 장보기(sim_core_a 와 같다). 하위 종류는 이제 플레이어가 고르므로
'그 물건이 실제로 무엇인지'를 그대로 쓴다(DECISIONS 2026-10-11 ①).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import playtest_household as PH   # noqa: E402
import sim_core_a as CA           # noqa: E402

DRAFT = json.load(open(os.path.join(ROOT, "data", "draft", "bundles_memory_wall.json"), encoding="utf-8"))
CORE = json.load(open(os.path.join(ROOT, "data", "balance", "core_a.json"), encoding="utf-8"))
S22 = CORE["s22"]

SUBTYPE = {  # 가정 물건 → 플레이어가 고를 하위 종류(실제 물건 그대로)
    "shin": "noodle", "chapa": "noodle", "saewoo": "snack", "jin": "noodle", "rice": "grain", "pepero": "sweet",
    "chocopie": "sweet", "tofu": "canned", "gim": "snack", "milk": "milk", "coke": "soda", "samdasoo": "water",
    "maxim": "coffee", "shampoo": "hygiene", "toothpaste": "hygiene", "tylenol": "pill", "tissue": "hygiene",
    "battery": "battery", "cable": "cable", "monami": "pen", "postit": "sticky", "book1": "story", "book2": "story",
    "soju": "liquor", "cass": "beer", "granola": "grain", "vitamin": "tonic", "socks": "small", "book3": "story",
    "lightbulb": "light", "kimchi": "canned", "tea": "tea",
}
_TPL = json.load(open(os.path.join(ROOT, "data", "relic_templates.json"), encoding="utf-8"))["_subtypes"]
SUB_CAT = {sub: cat for cat, d in _TPL.items() for sub in d}
PERSONA = {"A": {"scans": 6, "sessions": 2.5, "place_bundle": 0.8, "memory_obj_use": 0.3},
           "B": {"scans": 3, "sessions": 1, "place_bundle": 0.6, "memory_obj_use": 0.7}}


def mean(x):
    x = list(x)
    return sum(x) / len(x) if x else 0.0


def scan_stream(rng, persona, days):
    """하루마다 찍은 물건 목록(sim_core_a 와 같은 고르기: Zipf + 최근 7일 회피)."""
    items = list(CA.INITIAL)
    weights = {k: 1.0 / (i + 1) ** 1.1 for i, k in enumerate(rng.sample(CA.INITIAL, len(CA.INITIAL)))}
    log = defaultdict(list)
    out = {}
    for day in range(1, days + 1):
        for d_, ks in CA.SHOPPING.items():
            if d_ == day:
                items += ks
                for k in ks:
                    weights[k] = 0.4
        today = []
        for _ in range(PERSONA[persona]["scans"]):
            for _t in range(6):
                k = rng.choices(items, weights=[weights[x] for x in items])[0]
                if sum(1 for d in log[k] if d > day - 7) == 0 or rng.random() > 0.7:
                    break
            log[k].append(day)
            today.append(k)
        out[day] = today
    return out


# ─── V1 전역 이름 투표
def vote_table(seeds):
    print("\n" + "=" * 100)
    print("표 V1. 전역 이름 투표 — 한 바코드에 방주들이 붙인 하위 종류를 모아 다음 사람에게 미리 골라 줄 때")
    print("=" * 100)
    print("가정: 맞게 고르는 사람 비율 p(그 물건의 실제 하위 종류), 틀린 표는 나머지 4~6개에 고르게(장난 포함). 바코드마다 찍은 방주 수는 기하분포(인기 차이).")
    print(f"{'최소 방주':<10}{'동의 비율':<10}{'p=0.6 정확도':<14}{'p=0.8 정확도':<14}{'적용률(p=0.8, 평균 표 5)':<24}")
    rng = random.Random(1)
    for nmin, share in ((2, 0.5), (3, 0.6), (3, 0.67), (5, 0.6), (5, 0.7)):
        accs = {}
        cover = 0; tot = 0
        for p in (0.6, 0.8):
            ok = 0; app = 0
            for _ in range(20000):
                n = 1 + int(rng.expovariate(1 / 4.0))       # 평균 약 5표
                opts = 5
                votes = Counter()
                for _v in range(n):
                    votes[0 if rng.random() < p else rng.randrange(1, opts)] += 1
                top, c = votes.most_common(1)[0]
                if n >= nmin and c / n >= share:
                    app += 1; ok += top == 0
            accs[p] = ok / max(1, app)
            if p == 0.8:
                cover = app / 20000
        print(f"{nmin:<10}{share:<10.2f}{accs[0.6]:<14.1%}{accs[0.8]:<14.1%}{cover:<24.0%}")
    print(f"  채택: 최소 방주 {S22['name_vote']['min_distinct_arks']} · 동의 {S22['name_vote']['min_share']:.0%} (core_a.s22.name_vote)")


# ─── F1 매듭 대체
def fallback_table(seeds):
    print("\n" + "=" * 100)
    print("표 F1. 매듭이 하위 종류 하나를 기다릴 때 — 그 하위 종류가 며칠 안에 찍힐 확률(가정 물건 32종)")
    print("=" * 100)
    subs = sorted(set(SUBTYPE.values()))
    want = ["milk", "noodle", "battery", "small", "story", "pill", "tea", "canned"]
    print(f"{'하위 종류':<10}" + "".join(f"{'A '+str(d)+'일':<9}" for d in (1, 2, 3, 5)) + "".join(f"{'B '+str(d)+'일':<9}" for d in (1, 2, 3, 5)))
    rows = {}
    for w in want:
        line = f"{w:<10}"
        for persona in ("A", "B"):
            for D in (1, 2, 3, 5):
                hit = 0
                for s in seeds:
                    rng = random.Random(f"f|{persona}|{s}")
                    st = scan_stream(rng, persona, 14)
                    start = 3 + (s % 7)          # 매듭이 열린 날을 3~9일째로 흩는다
                    hit += any(SUBTYPE[k] == w for d in range(start, start + D) for k in st[d])
                line += f"{hit / len(seeds):<9.0%}"
                rows[(w, persona, D)] = hit / len(seeds)
        print(line)
    a2 = mean(rows[(w, "A", 2)] for w in want); b2 = mean(rows[(w, "B", 2)] for w in want)
    b3 = mean(rows[(w, "B", 3)] for w in want)
    print(f"  평균: A 2일 {a2:.0%} · B 2일 {b2:.0%} · B 3일 {b3:.0%}. 집에 없는 하위 종류(예: 신발·지도)는 영영 0% 다.")
    print(f"  채택: 매듭 대체 {S22['chain_soft_fallback']['days']}일 (core_a.s22.chain_soft_fallback)")


# ─── N1 사람 수첩
def notebook_run(persona, seeds, days, gossip, record12, hint_p):
    curves = defaultdict(list); reach = []; fills = defaultdict(list)
    for s in seeds:
        rng = random.Random(f"n|{persona}|{s}")
        st = scan_stream(rng, persona, days)
        people = []
        known = defaultdict(set)          # pid -> {(kind, cat)}
        gifts = Counter()
        reached = None
        for day in range(1, days + 1):
            nres = int(round(CA.interp(CA.RES_CURVE[persona], day)))
            while len(people) < nres:
                people.append(CA.Person(random.Random(f"{s}|p{len(people)}"), len(people), CA.ROLE_ORDER[len(people)]))
            cand_pairs = 0; labeled = 0
            for k in st[day]:
                c = CA.cat_of(k)
                cands = []
                for p in people:
                    kinds = [kd for kd, ok in (("like", c in p.likes), ("need", c == p.need_today(s, day))) if ok]
                    if kinds:
                        cands.append((p, kinds))
                        cand_pairs += 1
                        if day <= 2 or any((kd, c) in known[p.id] for kd in ("like", "need")):
                            labeled += 1
                if not cands:
                    continue
                lab = [x for x in cands if day <= 2 or any((kd, c) in known[x[0].id] for kd in x[1])]
                if lab:
                    p, kinds = rng.choice(lab)
                elif rng.random() < hint_p:
                    p, kinds = rng.choice(cands)
                else:
                    p = rng.choice(people); kinds = next((x[1] for x in cands if x[0] is p), [])
                gifts[p.id] += 1
                if day > 2 or record12:
                    for kd in kinds:
                        known[p.id].add((kd, c))
            # 저녁 귀띔: 가장 많이 받은 사람의 모르는 칸 하나를 다른 주민·관리실이 흘린다
            for _ in range(gossip if day >= 3 else 0):
                for pid, _n in gifts.most_common():
                    p = people[pid]
                    slots = [("like", c) for c in p.likes] + [("need", c) for c in p.needs]
                    unk = [x for x in slots if x not in known[pid]]
                    if unk:
                        known[pid].add(rng.choice(unk)); break
            curves[day].append(labeled / max(1, cand_pairs))
            top = [pid for pid, _ in gifts.most_common(3)]
            if top:
                f = []
                for pid in top:
                    p = people[pid]
                    slots = {("like", c) for c in p.likes} | {("need", c) for c in p.needs}
                    f.append(len(slots & known[pid]) / len(slots))
                fills[day].append(mean(f))
                if reached is None and day >= 3 and mean(f) >= S22["notebook"]["target_fill"]:
                    reached = day
        reach.append(reached or days + 1)
    return curves, fills, reach


def notebook_table(seeds, days=14):
    print("\n" + "=" * 100)
    print("표 N1. 사람 수첩 — 3일째부터 라벨 대신 기색. 건넨 뒤 결과가 수첩에 적히고, 아는 칸은 다시 라벨로 보인다")
    print("=" * 100)
    nb = S22["notebook"]
    print("칸 = 좋아함(역할 2 + 덧붙임) + 필요 갈래 3. '라벨 비율' = 「어디로」 후보(그 갈래에 칸이 있는 사람) 중 라벨이 보이는 비율.")
    print("'수첩' = 가장 많이 준 세 사람의 칸이 찬 비율. 70% 도달일은 중앙값(15 = 14일 안에 못 닿음).")
    print(f"{'':<34}{'라벨 3/7/10/14일':<26}{'수첩 7/10/14일':<22}{'70% 도달':<10}")
    variants = [("1~2일 기록 없음 · 귀띔 0", 0, False), ("1~2일 기록 · 귀띔 0", 0, True),
                (f"1~2일 기록 · 귀띔 {nb['gossip_per_evening']}/저녁 (채택)", nb["gossip_per_evening"], True)]
    for persona in ("A", "B"):
        for name, g, r12 in variants:
            cv, fl, rc = notebook_run(persona, seeds, days, g, r12, nb["hint_read_prob"])
            lab = "/".join(f"{mean(cv[d]):.0%}" for d in (3, 7, 10, 14))
            fil = "/".join(f"{mean(fl[d]):.0%}" for d in (7, 10, 14))
            print(f"{persona + ' ' + name:<34}{lab:<26}{fil:<22}{statistics.median(rc):<10.0f}")
    print("  목표: B 가 자주 주는 사람의 수첩 대부분(70%)이 기색 시작 1주 안(10일째)에 찬다.")


# ─── B1 기억 벽
def bundle_table(seeds, days=30):
    print("\n" + "=" * 100)
    print(f"표 B1. 기억 벽 꾸러미 — {days}일 (data/draft/bundles_memory_wall.json)")
    print("=" * 100)
    walls = DRAFT["walls"]; sched = DRAFT["schedule"]
    print(f"{'':<16}{'7일 완성':<10}{'14일':<8}{'30일':<8}{'열린 벽(30일)':<14}{'완성 사이 최대 공백(일)':<22}{'기억 물건으로 채운 칸':<18}")
    for persona in ("A", "B"):
        for memory_on in (False, True):
            done7 = []; done14 = []; done30 = []; opened = []; gaps = []; mem_slots = []
            for s in seeds:
                rng = random.Random(f"b|{persona}|{s}")
                st = scan_stream(rng, persona, days)
                filled = {}
                mem_by_wall = Counter()
                opened_on = {}
                open_walls = []
                completed = {}
                mem_used = 0
                for day in range(1, days + 1):
                    nrooms = int(round(CA.interp(CA.ROOM_CURVE[persona], day)))
                    built = CA.ROOM_ORDER[:nrooms]
                    # 열기: 지어진 방의 벽 중 일정이 허락한 수까지, 동시에 열린 것은 max_open 까지
                    allowed = max(n for d, n in sched["walls_unlocked_by_day"].items() if int(d) <= day)
                    cands = [w for w in walls if w["room"] in built and w["id"] not in completed and w["id"] not in open_walls]
                    while cands and len(open_walls) < sched["max_open"] and len(completed) + len(open_walls) < allowed:
                        w = cands.pop(0)
                        open_walls.append(w["id"])
                        filled[w["id"]] = set(w["prefill"] if isinstance(w["prefill"], list) else [w["prefill"]])
                        opened_on[w["id"]] = day
                    byid = {w["id"]: w for w in walls}
                    for k in st[day]:
                        sub = SUBTYPE[k]
                        relax = DRAFT["rules"].get("slot_relax_days")
                        for wid in list(open_walls):
                            w = byid[wid]
                            slot = sub if (sub in w["slots"] and sub not in filled[wid]) else None
                            if slot is None and relax and day - opened_on[wid] >= relax:
                                same = [x for x in w["slots"] if x not in filled[wid] and SUB_CAT.get(x) == SUB_CAT.get(sub)]
                                slot = same[0] if same else None
                            if slot and rng.random() < PERSONA[persona]["place_bundle"]:
                                filled[wid].add(slot)
                                break
                    # 기억 속 물건: 하루 하나, 마지막 칸은 못 채운다
                    if memory_on and rng.random() < PERSONA[persona]["memory_obj_use"]:
                        for wid in open_walls:
                            w = byid[wid]
                            left = [x for x in w["slots"] if x not in filled[wid]]
                            cap = DRAFT["memory_object"].get("max_per_wall", 99)
                            if len(left) >= 2 and mem_by_wall[wid] < cap:
                                filled[wid].add(left[0]); mem_used += 1; mem_by_wall[wid] += 1
                                break
                    for wid in list(open_walls):
                        if set(byid[wid]["slots"]) <= filled[wid]:
                            completed[wid] = day; open_walls.remove(wid)
                cd = sorted(completed.values())
                done7.append(sum(1 for d in cd if d <= 7)); done14.append(sum(1 for d in cd if d <= 14)); done30.append(len(cd))
                opened.append(len(completed) + len(open_walls))
                marks = [0] + cd + [days]
                gaps.append(max(b - a for a, b in zip(marks, marks[1:])))
                mem_slots.append(mem_used)
            print(f"{persona + (' 기억 켬' if memory_on else ' 기억 끔'):<16}{mean(done7):<10.1f}{mean(done14):<8.1f}{mean(done30):<8.1f}"
                  f"{mean(opened):<14.1f}{mean(gaps):<22.1f}{mean(mem_slots):<18.1f}")
    print("  목표: 주에 하나 안팎(A 30일 4~6, B 3~4), 완성 사이 공백 10일 이하 — 2주 넘게 아무것도 안 끝나면 30일 등뼈가 아니다.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=30)
    a = ap.parse_args()
    seeds = range(a.seeds)
    print("질랜디아 — S22 수치·기억 벽 시뮬레이션 (씨앗", a.seeds, ")")
    vote_table(seeds)
    fallback_table(seeds)
    notebook_table(seeds)
    bundle_table(seeds)


if __name__ == "__main__":
    main()
