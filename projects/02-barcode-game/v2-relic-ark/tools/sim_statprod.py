"""잔해 방주 — 스탯이 생산을 바꿀 때 (stakes.json stat_production) 검증 (기획·밸런스 소유)

    python tools/sim_statprod.py           # 씨앗 30 × 30일
    python tools/sim_statprod.py --seeds 10

경제·스캔 모델은 tools/sim_economy.py 를 그대로 쓰고, 생산(produce)만 바꾼다:
  방 생산 = 기본[레벨] × staff_mult[n] × stat_factor(사람들, room_stat) (+ 역할 보너스는 그 방에 있을 때만)
주민은 이름 있는 사람이다(역할 기본값 + 무작위 + 특이점 — server.py roll_stats 와 같은 규칙).

배치 정책 넷
  before     : 지금 서버(스탯 무시, 역할 보너스는 어디 있든). sim_economy 와 같은 '한 명씩 먼저' 배치
  random     : 생산 방에 무작위로(정원 안)
  greedy     : 한 사람씩 '가장 많이 늘리는 방'에 넣는다(플레이어가 강조된 스탯을 보고 놓는 경우)
  one_room   : 전원을 한 방(온실)에 몰고 남는 사람은 홀
표
  S1 정책별 30일 생산·곡선      S2 한 방의 최선 vs 최악 배치 격차(B6)
  S3 손 좋은 사람의 기회비용(B3) S4 세션당 배치 결정(추정)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim_economy as E                       # noqa: E402
from sim_expedition import make_person, ROLES  # noqa: E402

ROOT = os.path.dirname(HERE)
STK = json.load(open(os.path.join(ROOT, "data", "balance", "stakes.json"), encoding="utf-8"))
SP = STK["stat_production"]
STAFF = STK["staffing"]["staff_mult"]
ROLE_BONUS = {"cook": ("pantry", "food"), "engineer": ("well", "water")}   # roles.json effects.room_bonus (+1/틱 = 기본의 1/3 꼴)
MATS = ("food", "water", "knowledge")
# 식량창고(server 시작 방, 손 방)는 economy.json 목록에 없다. S3 에서만 서버 카탈로그 값으로 넣는다
PANTRY = {"cap": 3, "produces": {"food": 2}}


def person_mult(p, stat, on=True):
    if not on:
        return 1.0
    v = p["stats"][stat]
    return max(SP["min_mult"], min(SP["max_mult"], 1 + SP["per_point"] * (v - SP["center"])))


def room_output(spec, lv, people, room_id, stat_on=True, role_in_room=True):
    base = spec["produces"] if lv < 2 else spec.get(f"lv{lv}", {}).get("produces_after", spec["produces"])
    n = len(people)
    if n == 0:
        sm = STAFF[0]
    else:
        sm = STAFF[min(n, len(STAFF) - 1)]
    stat = SP["room_stat"].get(room_id)
    if stat_on and people and stat:
        f = statistics.mean(person_mult(p, stat) for p in people)
    else:
        f = 1.0
    out = {}
    for k, v in base.items():
        if k in MATS:
            out[k] = v * sm * f
    if role_in_room:
        for p in people:
            rb = ROLE_BONUS.get(p["role"])
            if rb and rb[0] == room_id and rb[1] in base:
                out[rb[1]] = out.get(rb[1], 0) + base[rb[1]] / 3
    return out


class ArkS(E.Ark):
    """생산만 바꾼 Ark. 주민은 이름 있는 사람."""

    def __init__(self, rng, policy):
        super().__init__(rng)
        self.policy = policy
        self.roster = [make_person(rng, r, i) for i, r in enumerate(("cook", "engineer", "scout"))]
        self.layout_log = []

    def residents(self, day):
        return len(self.roster)

    def grow(self, day):
        want = max(3, min(self.resident_cap, 10, 3 + int(day / 3.5)))
        while len(self.roster) < want:
            have = {p["role"] for p in self.roster}
            pool = [r for r in ROLES if r not in have] or ROLES
            self.roster.append(make_person(self.rng, self.rng.choice(pool), len(self.roster)))

    def prod_rooms(self):
        return [r for r in ("greenhouse", "well", "decoder") if r in self.rooms]

    def total(self, assign, stat_on=True, role_in_room=True):
        out = {}
        for r in self.prod_rooms():
            o = room_output(self.spec[r], self.rooms[r], assign.get(r, []), r, stat_on, role_in_room)
            for k, v in o.items():
                out[k] = out.get(k, 0) + v
        return out

    def layout(self, policy=None):
        policy = policy or self.policy
        rooms = self.prod_rooms()
        assign = {r: [] for r in rooms}
        cap = {r: self.spec[r]["cap"] for r in rooms}
        ppl = list(self.roster)
        if not rooms:
            return assign
        if policy == "before":
            for i, p in enumerate(ppl):                         # 한 명씩 먼저, 그다음 고루(sim_economy 와 같다)
                order = sorted(rooms, key=lambda r: len(assign[r]))
                r = next((x for x in order if len(assign[x]) < cap[x]), None)
                if r:
                    assign[r].append(p)
        elif policy == "random":
            self.rng.shuffle(ppl)
            for p in ppl:
                free = [r for r in rooms if len(assign[r]) < cap[r]]
                if not free:
                    break
                assign[self.rng.choice(free)].append(p)
        elif policy == "one_room":
            r = rooms[0]
            assign[r] = ppl[:cap[r]]
        else:                                                   # greedy
            left = list(ppl)
            while left:
                best = None
                cur = sum(self.total(assign).values())
                for p in left:
                    for r in rooms:
                        if len(assign[r]) >= cap[r]:
                            continue
                        assign[r].append(p)
                        g = sum(self.total(assign).values()) - cur
                        assign[r].pop()
                        if best is None or g > best[0]:
                            best = (g, p, r)
                if best is None or best[0] <= 1e-9:
                    break
                assign[best[2]].append(best[1]); left.remove(best[1])
        return assign

    def produce(self, day):
        self.grow(day)
        self.morale_from_rooms = sum(
            (self.spec[r]["produces"].get("morale", 0) if self.rooms[r] < 2 else
             self.spec[r].get(f"lv{self.rooms[r]}", {}).get("produces_after", self.spec[r]["produces"]).get("morale", 0))
            for r in ("quarters", "lounge", "bath") if r in self.rooms)
        a = self.layout()
        self.layout_log.append({r: tuple(sorted(p["id"] for p in ps)) for r, ps in a.items()})
        if self.policy == "before":
            out = self.total(a, stat_on=False, role_in_room=False)
            # 지금 서버: 역할 보너스는 어디 있든 들어온다
            for p in self.roster:
                rb = ROLE_BONUS.get(p["role"])
                if rb and rb[0] in self.rooms and rb[1] in self.spec[rb[0]]["produces"]:
                    out[rb[1]] = out.get(rb[1], 0) + self.spec[rb[0]]["produces"][rb[1]] / 3
            return out
        return self.total(a)


def run(policy, seed, days=30, scans=8, pool=90):
    rng = random.Random(seed)
    E_Ark = E.Ark
    E.Ark = lambda r: ArkS(r, policy)
    try:
        res = E.run_economy(scans, days, seed, pool)
    finally:
        E.Ark = E_Ark
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=30)
    a = ap.parse_args()
    seeds = range(a.seeds)
    print("잔해 방주 — 스탯이 생산을 바꿀 때 (stakes.json stat_production)")
    print(f"room_stat {dict((k, v) for k, v in SP['room_stat'].items() if not k.startswith('_'))}")
    print(f"center {SP['center']} · per_point {SP['per_point']} · clamp {SP['min_mult']}~{SP['max_mult']} · aggregate {SP['aggregate']}")

    print("\n" + "=" * 100)
    print(f"표 S1. 정책별 — 보통 플레이어(스캔 8/일) 30일, 씨앗 {a.seeds}개 평균")
    print("=" * 100)
    print(f"{'정책':<12}{'방생산(30일, 식량·물·기록)':<26}{'before 대비':<12}{'기록(건설)':<12}{'방 7/14/30일':<20}{'Lv2 14일':<10}")
    base_prod = None
    rows = {}
    for pol in ("before", "random", "greedy", "one_room"):
        rs = [run(pol, s) for s in seeds]
        prod = statistics.mean(r["ark"].income_room for r in rs)
        kn = statistics.mean(sum(1 for _ in []) for r in rs)
        rooms = [statistics.mean(r["hist"][d - 1]["rooms"] for r in rs) for d in (7, 14, 30)]
        lv2 = statistics.mean(r["hist"][13]["lv2"] for r in rs)
        if base_prod is None:
            base_prod = prod
        rows[pol] = (prod, rooms)
        print(f"{pol:<12}{prod:<26.1f}{prod / base_prod - 1:<+12.0%}{statistics.mean(r['ark'].b_room for r in rs):<12.1f}"
              f"{'/'.join(f'{x:.1f}' for x in rooms):<20}{lv2:<10.1f}")
    print("  방 생산은 식량·물·기록뿐이다(sim_economy 모델). 식량·물은 보관 상한과 소비가 있어 곡선(방 수)에는 기록만 닿는다.")
    print("  곡선 기준(10-03 재조정, 씨앗 30): 6.5 / 9.3 / 11.4 ±1.")

    print("\n" + "=" * 100)
    print("표 S2. 한 방의 최선 vs 최악 배치 격차 — 그 날 명단에서 '한 사람'을 그 방에 넣을 때 (B6 목표 20~35%)")
    print("=" * 100)
    print(f"{'방':<12}{'스탯':<8}{'최선/최악 평균 격차':<20}{'90분위':<10}{'역할 보너스 포함 격차':<20}")
    for room in ("greenhouse", "well", "decoder"):
        gaps, gaps_role = [], []
        for s in seeds:
            rng = random.Random(1000 + s)
            roster = [make_person(rng, r, i) for i, r in enumerate(("cook", "engineer", "scout"))]
            for i in range(3, 3 + rng.randint(2, 5)):
                roster.append(make_person(rng, rng.choice(ROLES), i))
            spec = E.ECON["rooms"]["list"][room]
            outs = [sum(room_output(spec, 1, [p], room, True, False).values()) for p in roster]
            outs_r = [sum(room_output(spec, 1, [p], room, True, True).values()) for p in roster]
            gaps.append(max(outs) / min(outs) - 1)
            gaps_role.append(max(outs_r) / min(outs_r) - 1)
        st = SP["room_stat"][room]
        print(f"{room:<12}{st:<8}{statistics.mean(gaps):<20.0%}{sorted(gaps)[int(len(gaps) * .9)]:<10.0%}{statistics.mean(gaps_role):<20.0%}")
    print("  스탯만의 격차가 각인 하나의 전형적 효과(+20~30%)를 넘지 않아야 한다. 역할 보너스(기술자→정수실 +1/틱)는 스탯보다 크다 —")
    print("  그것은 '시작의 차이'가 아니라 역할의 정체성이라 그대로 둔다(그 방에 있을 때만).")

    print("\n" + "=" * 100)
    print("표 S3. 손 좋은 사람의 기회비용 — greedy 배치에서 손이 가장 좋은 사람을 하루 빼면 (B3)")
    print("=" * 100)
    loss_prod, where = [], {}
    for s in seeds:
        rng = random.Random(s)
        ark = ArkS(rng, "greedy")
        ark.rooms = {"pantry": 1, "greenhouse": 1, "well": 1, "decoder": 1, "workshop": 1, "quarters": 1}
        ark.spec = dict(ark.spec, pantry=PANTRY)
        ark.prod_rooms = lambda: [r for r in ("pantry", "greenhouse", "well", "decoder") if r in ark.rooms]
        for i in range(3, 7):
            ark.roster.append(make_person(rng, rng.choice(ROLES), i))
        a_full = ark.layout()
        full = sum(ark.total(a_full).values())
        hp = max(ark.roster, key=lambda p: p["stats"]["hand"])
        ark.roster.remove(hp)
        less = sum(ark.total(ark.layout()).values())
        loss_prod.append(1 - less / full)
        r_in = next((r for r, ps in a_full.items() if hp in ps), "홀(생산 방 정원 밖)")
        where[r_in] = where.get(r_in, 0) + 1
    print("  (S3 는 서버 시작 방 '식량창고'(손 방, 식량 2)를 넣은 방주. sim_economy 의 목록에는 손을 쓰는 '재료 생산 방'이 없다)")
    print(f"  그 사람을 원정·방어로 빼면 하루 방 생산 −{statistics.mean(loss_prod):.0%} (씨앗 {a.seeds}개 평균, 주민 7명)")
    print(f"  greedy 가 그 사람을 둔 곳: {where}")
    print("  같은 사람이 방어(담·역할 친화)와 원정(손 = 들고 오는 칸, expedition.json)에서도 쓸모가 있다 — 셋 중 하나를 고른다.")

    print("\n" + "=" * 100)
    print("표 S4. 배치 결정 — greedy 의 최적 배치가 전날과 달라진 날(= 다시 볼 이유가 생긴 날)")
    print("=" * 100)
    ch = []
    for s in seeds:
        rng = random.Random(s)
        ark = ArkS(rng, "greedy")
        r = run("greedy", s)
        log = r["ark"].layout_log
        ch.append(sum(1 for i in range(1, len(log)) if log[i] != log[i - 1]) / len(log))
    print(f"  최적 배치가 바뀌는 날의 비율: {statistics.mean(ch):.0%} (새 주민·새 방·레벨업이 생길 때)")
    print("  → 하루 2~3세션이면 세션당 배치 결정 약 +{:.1f}개(전에는 생산에 대해 0 — 배치가 생산을 바꾸지 않았다).".format(statistics.mean(ch) / 2.5 * 2))


if __name__ == "__main__":
    main()
