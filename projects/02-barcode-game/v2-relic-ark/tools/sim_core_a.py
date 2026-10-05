"""잔해 방주 — 핵심 루프 A 시뮬레이션: 지금(CURRENT) vs A (기획·밸런스 소유)

    python tools/sim_core_a.py              # 씨앗 24, 14일 + 30일
    python tools/sim_core_a.py --seeds 40

입력: data/draft/core_a.json(A 규칙), tools/playtest_household.py(플레이테스트 가정 물건 32종).
페르소나: A 「보통」 하루 2.5세션·찍기 6 / B 「띄엄띄엄」 하루 1세션·찍기 3 (플레이테스트와 같다).
주민 수·방 수는 sim_expedition·sim_economy 곡선을 따른다(원정 켬, 씨앗 평균).

지표(세션·하루 단위)
  real decisions / same-answer rate : 고를 때 정답(가치 최고)이 그 갈래의 '늘 같은 답'과 다르거나, 1·2위가 0.1V 안이면 진짜.
  new things / people beats / 세션 계약(도착 선물·새것·진짜 결정·모르는 결과·다시 올 이유) / 값 0 / 생산 덤
'재미 추정' = 1 + 4 × 계약 충족률 — **추정**이다. 지금(CURRENT) 모델은 플레이테스트 일지로 보정했다.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import playtest_household as PH   # noqa: E402

CA = json.load(open(os.path.join(ROOT, "data", "draft", "core_a.json"), encoding="utf-8"))
try:   # 시나리오 초안(S19-S): 사슬 매듭 수는 arcs.json 을 따른다(없는 역할은 3)
    ARC_BEATS = {a["role"]: len(a["beats"]) for a in json.load(open(os.path.join(ROOT, "data", "draft", "arcs.json"), encoding="utf-8"))["arcs"]}
except Exception:
    ARC_BEATS = {}
MEMORIES_PER_PERSON = 2   # resident_tastes.json: 역할마다 기억 둘
OV = CA["give_place"]["outcome_V"]
PROF = CA["profiles"]
CH = CA["chains"]
DEC = CA["decor"]
DECAY = [1.0, 0.5, 0.1, 0.0]          # 지금 서버 감쇠(7일 창)

INITIAL = ["shin", "chapa", "saewoo", "jin", "rice", "pepero", "chocopie", "tofu", "gim", "milk", "coke", "samdasoo",
           "maxim", "shampoo", "toothpaste", "tylenol", "tissue", "battery", "cable", "monami", "postit", "book1",
           "book2", "soju", "cass"]
SHOPPING = {4: ["granola", "vitamin"], 6: ["socks", "book3"], 9: ["lightbulb", "kimchi"], 12: ["tea"]}


def cat_of(k):
    c = PH.cat(k)
    if c:
        return c
    return "book" if k.startswith("book") else "unknown"


def family_of(k):
    return PH.code(k)[:7]


# 주민·방 곡선(원정 켬, 씨앗 평균) — sim_expedition X3 / sim_economy E2
RES_CURVE = {"A": [(1, 3), (3, 4), (7, 5.8), (14, 7.1), (30, 10.3)], "B": [(1, 3), (3, 4), (7, 5.3), (14, 6.3), (30, 8.4)]}
ROOM_CURVE = {"A": [(1, 3), (7, 6.5), (14, 9.3), (30, 11.4)], "B": [(1, 2), (7, 3.5), (14, 5.0), (30, 8.9)]}
ROLE_ORDER = ["cook", "engineer", "scout", "farmer", "scholar", "medic", "trader", "kid", "farmer", "medic", "scout", "cook"]
ROOM_ORDER = ["pantry", "quarters", "well", "storage", "generator", "workshop", "greenhouse", "decoder", "infirmary",
              "airlock", "lounge", "bath"]
PERSONA = {"A": {"sessions": 2.5, "scans": 6, "expedition_daily": True},
           "B": {"sessions": 1, "scans": 3, "expedition_daily": False}}


def interp(curve, d):
    for (d0, v0), (d1, v1) in zip(curve, curve[1:]):
        if d0 <= d <= d1:
            return v0 + (v1 - v0) * (d - d0) / (d1 - d0)
    return curve[-1][1]


class Person:
    def __init__(self, rng, pid, role):
        self.id, self.role = pid, role
        likes = list(PROF["role_likes"][role])
        if rng.random() < 0.3:
            cats = ["food", "drink", "medical", "electronics", "stationery", "book", "apparel", "tobacco"]
            likes[rng.randrange(2)] = rng.choice([c for c in cats if c not in likes])
        self.likes = likes
        self.needs = PROF["role_needs"][role]
        allk = INITIAL + [x for v in SHOPPING.values() for x in v]
        self.memories = []
        for _ in range(MEMORIES_PER_PERSON):
            k = rng.choice(allk)
            self.memories.append(("family", family_of(k)) if rng.random() < 0.5 else ("cat", cat_of(k)))
        self.memory = self.memories[0]
        self.memory_done = False
        pool = list(dict.fromkeys(self.needs + self.likes))
        nb = ARC_BEATS.get(role, 3)
        self.chain = [rng.choice(pool) for _ in range(nb - 1)] + ["memory_or_decor"]
        self.nbeats = nb
        self.beat = 0
        self.beat_open_day = 1
        self.given_today = 0
        self.recent = {}           # item -> day

    def need_today(self, seed, day):
        return random.Random(f"{seed}|{self.id}|{day}").choice(self.needs)


def option_values(people, rooms_decor, item, day, seed, shelf_has, shelf_free):
    c = cat_of(item); fam = family_of(item)
    opts = []
    for p in people:
        v, kind = OV["neutral_person"], "neutral"
        if p.beat < p.nbeats and day >= p.beat_open_day:
            req = p.chain[p.beat]
            hit = (req == c) or (req == "memory_or_decor" and ((p.memory[0] == "family" and p.memory[1] == fam) or
                                                               (p.memory[0] == "cat" and p.memory[1] == c)))
            if hit:
                v, kind = OV["chain_beat"], "chain"
        if kind == "neutral" and not p.memory_done and ((p.memory[0] == "family" and p.memory[1] == fam) or
                                                        (p.memory[0] == "cat" and p.memory[1] == c)):
            v, kind = OV["memory"], "memory"
        if kind == "neutral" and p.need_today(seed, day) == c:
            v, kind = OV["need"], "need"
        if kind == "neutral" and c in p.likes:
            v, kind = OV["like"], "like"
        if p.given_today:
            v *= 0.5
        if item in p.recent and day - p.recent[item] < 3:
            v *= 0.3
        opts.append((v, f"p:{p.id}", kind, p))
    for room, tags in rooms_decor.items():
        if len(tags["items"]) >= DEC["slots_by_level"]["1"]:
            continue
        prog = any(v["room"] == room and c in v["need"] and tags["cats"].get(c, 0) < v["need"][c] and not tags["seen"].get(v["id"])
                   for v in DEC["visitors"])
        opts.append((OV["decor"] if prog else 0.6, f"r:{room}", "decor" if prog else "decor_plain", room))
    opts.append(((OV["keep"] if (not shelf_has and shelf_free) else 0.3), "keep", "keep", None))
    opts.sort(key=lambda o: -o[0])
    return opts


def run(persona, seed, days, mode):
    rng = random.Random(f"{persona}|{seed}")
    P = PERSONA[persona]
    people, rooms_decor = [], {}
    items = list(INITIAL)
    weights = {k: 1.0 / (i + 1) ** 1.1 for i, k in enumerate(rng.sample(INITIAL, len(INITIAL)))}
    scanlog = defaultdict(list)      # item -> days scanned
    seen_items, shelf = set(), set()
    out = defaultdict(lambda: defaultdict(float))
    choice_log = []                  # (category, best target, near_tie)
    visitors_seen = set()
    sessions_total = 0
    for day in range(1, days + 1):
        for d_, ks in SHOPPING.items():
            if d_ == day:
                items += ks
                for k in ks:
                    weights[k] = 0.4
        nres = int(round(interp(RES_CURVE[persona], day)))
        while len(people) < nres:
            r = ROLE_ORDER[len(people) % len(ROLE_ORDER)]
            people.append(Person(random.Random(f"{seed}|p{len(people)}"), len(people), r))
            if day > 1:
                out[day]["people_beats"] += 1; out[day]["new"] += 1
        nrooms = int(round(interp(ROOM_CURVE[persona], day)))
        for rid in ROOM_ORDER[:nrooms]:
            rooms_decor.setdefault(rid, {"items": [], "cats": Counter(), "seen": {}})
        shelf_cap = 6 + 8 * ("storage" in rooms_decor) + 4 * max(0, (nrooms - 3) // 3)
        for p in people:
            p.given_today = 0
        n_sess = int(P["sessions"]) + (1 if rng.random() < P["sessions"] - int(P["sessions"]) else 0)
        scans_per = [P["scans"] // n_sess + (1 if i < P["scans"] % n_sess else 0) for i in range(n_sess)]
        pending_visitors = [v for v in list(visitors_seen) if isinstance(v, tuple) and v[1] == day]
        for si in range(n_sess):
            sessions_total += 1
            sess = Counter()
            # 도착 선물: 첫 세션 = 문어 선물(지금도 있다) / A 는 찾아온 손님도
            if si == 0:
                sess["gift"] = 1
            if mode == "A" and si == 0 and pending_visitors:
                sess["gift"] = 1; sess["new"] += len(pending_visitors); sess["unknown"] = 1
            if P["expedition_daily"] and si == 0 and day >= 2:
                sess["gift"] = 1; sess["unknown"] = 1
            for _ in range(scans_per[si]):
                # 고르기: 최근 7일 많이 찍은 것은 70% 피한다(감사 가정)
                for _t in range(6):
                    k = rng.choices(items, weights=[weights[x] for x in items])[0]
                    n7 = sum(1 for d in scanlog[k] if d > day - 7)
                    if n7 == 0 or rng.random() > 0.7:
                        break
                n7 = sum(1 for d in scanlog[k] if d > day - 7)
                mult = DECAY[min(n7, 3)]
                scanlog[k].append(day)
                if k not in seen_items:
                    seen_items.add(k); sess["new"] += 1; sess["unknown"] = 1
                out[day]["scans"] += 1
                if mode == "current":
                    out[day]["value0"] += mult == 0
                    if mult > 0 and k not in shelf and len(shelf) < shelf_cap:
                        shelf.add(k)
                    continue
                opts = option_values(people, rooms_decor, k, day, seed, k in shelf, len(shelf) < shelf_cap)
                best = opts[0]
                near = len(opts) > 1 and opts[0][0] - opts[1][0] <= 0.1 * 1.0 and opts[1][1] != opts[0][1]
                choice_log.append((cat_of(k), best[1], near, day, si))
                out[day]["value0"] += (mult == 0 and best[0] < 0.5)
                if mult < 1.0:
                    out[day]["rescans"] += 1
                    out[day]["rescan_meaningful"] += best[0] >= 0.8
                v, tgt, kind, obj = best
                if tgt.startswith("p:"):
                    p = obj; p.given_today += 1; p.recent[k] = day
                    if kind == "chain":
                        p.beat += 1; p.beat_open_day = day + CH["cooldown_days"]
                        out[day]["people_beats"] += 1; sess["new"] += 1
                    elif kind == "memory":
                        p.memories.pop(0)
                        if p.memories:
                            p.memory = p.memories[0]
                        else:
                            p.memory_done = True
                        out[day]["people_beats"] += 1; sess["new"] += 1
                    if kind == "need":
                        out[day]["need_bonus"] += 0.1
                elif tgt.startswith("r:"):
                    r = rooms_decor[obj]; c = cat_of(k)
                    r["items"].append(k); r["cats"][c] += 1
                    for vis in DEC["visitors"]:
                        if vis["room"] == obj and not r["seen"].get(vis["id"]) and all(
                                r["cats"].get(cc, 0) >= n for cc, n in vis["need"].items() if not cc.startswith("_")):
                            r["seen"][vis["id"]] = True
                            visitors_seen.add((vis["id"], day + 1))
                            out[day + 1]["new"] += 1
                            if vis["brings"] in ("guest_weight", "newhuman_weight"):
                                out[day + 1]["people_beats"] += 1
                else:
                    shelf.add(k)
            # 진짜 결정(세션)
            if mode == "A":
                cl = [c for c in choice_log if c[3] == day and c[4] == si]
                sess["choices"] = len(cl)
            out[day]["sessions"] += 1
            out[day]["new_sess"] += sess["new"] > 0
            out[day]["gift_sess"] += sess["gift"] > 0
            out[day]["unknown_sess"] += sess["unknown"] > 0
            # 다시 올 이유: A — 열린 매듭(요구 갈래가 보인다)·찾아올 손님·원정 / 지금 — 원정이 나가 있을 때만
            open_beats = sum(1 for p in people if p.beat < p.nbeats and p.beat_open_day <= day + 1)
            if mode == "A":
                out[day]["return_sess"] += (open_beats > 0 or P["expedition_daily"])
            else:
                out[day]["return_sess"] += P["expedition_daily"] and si == n_sess - 1
            out[day]["_sess_ids"] += 0
        out[day]["people_beats"] += 1 if day == 2 else 0          # 문어 도착
        if mode == "current":
            # 지금 모델(플레이테스트 보정): 바람 8개가 1~3일째 저절로, 원정 귀환 구조, 쪽지·배치는 같은 답
            if day <= 3:
                out[day]["people_beats"] += 1.3
            out[day]["real_dec"] += (0.5 if day <= 6 else 0.2) + (0.3 if P["expedition_daily"] else 0.1)
    # A 진짜 결정: 갈래별 '늘 같은 답'(최빈 대상)과 다르거나 근소
    if mode == "A":
        modal = {}
        bycat = defaultdict(Counter)
        for c, tgt, near, d, si in choice_log:
            bycat[c][tgt] += 1
        for c, cnt in bycat.items():
            modal[c] = cnt.most_common(1)[0][0]
        same = sum(1 for c, tgt, near, d, si in choice_log if tgt == modal[c] and not near)
        for c, tgt, near, d, si in choice_log:
            if tgt != modal[c] or near:
                out[d]["real_dec"] += 1
        same_rate = same / max(1, len(choice_log))
    else:
        same_rate = 0.9
    return out, same_rate


def summarize(persona, mode, days, seeds):
    agg = defaultdict(list); sr = []
    for s in seeds:
        out, same = run(persona, s, days, mode)
        sr.append(same)
        for d in range(1, days + 1):
            o = out[d]
            n = max(1, o["sessions"])
            dec_sess = min(1.0, o["real_dec"] / n)       # 세션당 진짜 결정 하나 이상일 확률(근사)
            cover = (o["gift_sess"] / n + o["new_sess"] / n + dec_sess + o["unknown_sess"] / n + o["return_sess"] / n) / 5
            agg[d].append({"dec_per_sess": o["real_dec"] / n, "new": o["new"], "people": o["people_beats"],
                           "cover": cover, "value0": o["value0"] / max(1, o["scans"]), "need_bonus": o["need_bonus"],
                           "rs": o["rescans"], "rsm": o["rescan_meaningful"]})
    return agg, statistics.mean(sr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=24)
    a = ap.parse_args()
    seeds = range(a.seeds)
    print("잔해 방주 — 핵심 루프 A vs 지금 (씨앗", a.seeds, ")  입력 data/draft/core_a.json", CA["_version"])
    for days in (14, 30):
        print("\n" + "=" * 110)
        print(f"표 C1. {days}일 — 페르소나 × 지금/A (하루 평균)")
        print("=" * 110)
        print(f"{'':<14}{'세션당 진짜 결정':<16}{'같은 답 비율':<12}{'새것/일':<10}{'사람 비트/일':<12}{'계약 충족':<10}{'재미(추정)':<11}{'값0':<8}{'1~7일 재미':<12}{'8~14일 재미':<12}{'재스캔 중 0.8V+':<14}")
        for persona in ("A", "B"):
            for mode in ("current", "A"):
                agg, same = summarize(persona, mode, days, seeds)
                m = lambda key, d0=1, d1=days: statistics.mean(x[key] for d in range(d0, d1 + 1) for x in agg[d])
                fun = lambda d0, d1: 1 + 4 * m("cover", d0, d1)
                print(f"{persona + ' ' + ('지금' if mode == 'current' else 'A'):<14}{m('dec_per_sess'):<16.2f}"
                      f"{(same if mode == 'A' else float('nan')):<12.0%}{m('new'):<10.2f}{m('people'):<12.2f}"
                      f"{m('cover'):<10.0%}{fun(1, days):<11.1f}{m('value0'):<8.0%}{fun(1, 7):<12.1f}{fun(8, 14):<12.1f}"
                      f"{(sum(x['rsm'] for d in agg for x in agg[d]) / max(1, sum(x['rs'] for d in agg for x in agg[d]))) if mode == 'A' else 0:<14.0%}")
        if days == 14:
            print("  '같은 답 비율' = 고른 대상이 그 갈래의 최빈 대상과 같고 근소하지도 않은 비율(목표 < 30%). 지금 모델은 쪽지 금색 카드·")
            print("  배치·원정 목적지가 거의 늘 같은 답이라 90% 로 두었다(시스템 패널 감사).")
            print("  재미(추정) = 1 + 4 × 계약 충족률. 지금 모델 1~7일 값이 플레이테스트 A 일지(3.7→2, 평균 ≈ 2.8)와 같은지가 보정 확인이다.")
    # 하루별(14일, A 페르소나)
    print("\n" + "=" * 110)
    print("표 C2. 날마다 — A 「보통」, 지금 vs A (재미 추정 / 사람 비트)")
    print("=" * 110)
    cur, _ = summarize("A", "current", 14, seeds)
    new, _ = summarize("A", "A", 14, seeds)
    print("일   " + " ".join(f"{d:>5d}" for d in range(1, 15)))
    for name, agg in (("지금", cur), ("A", new)):
        print(f"{name:<5}" + " ".join(f"{1 + 4 * statistics.mean(x['cover'] for x in agg[d]):>5.1f}" for d in range(1, 15)) + "  (재미 추정)")
        print(f"{'':<5}" + " ".join(f"{statistics.mean(x['people'] for x in agg[d]):>5.1f}" for d in range(1, 15)) + "  (사람 비트)")
    nb = statistics.mean(x["need_bonus"] for d in range(1, 15) for x in new[d])
    print(f"\n  생산 덤(필요 +10% × 그날): 하루 평균 {nb:.2f} 방-일 → 방 생산의 약 {nb * 0.1 / 6:.1%} — 건설 재료 곡선 영향 없음(방 생산은 대부분 식량·물).")


if __name__ == "__main__":
    main()
