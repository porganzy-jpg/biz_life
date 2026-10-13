"""질랜디아 — 가보 칸 시뮬레이션 (기획·밸런스 소유)

    python tools/sim_heirloom.py          # 씨앗 40, 30일
입력: data/balance/core_a.json heirloom, 가정 물건 32종 + 장보기(tools/playtest_household.py, sim_s22 와 같은 스캔 흐름).
희귀도는 바코드마다 고정(같은 바코드 = 같은 유물). 분포는 relic_generator 실측(흔함 59.8 / 쓸만함 24.6 / 귀함 10.0 / 진귀함 4.0 / 전설 1.53%).

표
  H1 30일 — 가보 후보(귀함 이상 카드), 채운 가보 칸, 진귀함·전설, 세 번째 기억, 닦아서 오른 등급
  H2 「누구에게?」 — 귀함 이상이 나온 순간 고를 사람이 둘 이상이었나(빈 칸·바꿀 만한 칸), 바꾸기 물음 수
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import sim_core_a as CA     # noqa: E402
import sim_s22 as S2        # noqa: E402

HL = json.load(open(os.path.join(ROOT, "data", "balance", "core_a.json"), encoding="utf-8"))["heirloom"]
RN = ["common", "uncommon", "rare", "epic", "legendary"]
RP = [0.598, 0.246, 0.100, 0.040, 0.0153]
RANK = {r: i for i, r in enumerate(RN)}
POLISH = HL["polish_ascend"]


def mean(x):
    x = list(x)
    return sum(x) / len(x) if x else 0.0


def run(persona, seed, days, ascend_on=True):
    rng = random.Random(f"h|{persona}|{seed}")
    st = S2.scan_stream(rng, persona, days)
    rr = random.Random(f"rar|{seed}")
    rarity = {}
    polish_days = {}
    slots = {}            # pid -> (barcode, effective tier)
    people = []
    third = set()
    used_bc = set()
    out = Counter()
    for day in range(1, days + 1):
        nres = int(round(CA.interp(CA.RES_CURVE[persona], day)))
        while len(people) < nres:
            people.append(len(people))
        for k in st[day]:
            if k not in rarity:
                rarity[k] = rr.choices(RN, weights=RP)[0]
            pd = polish_days.setdefault(k, set())
            pd.add(day)
            base = RANK[rarity[k]]
            eff = base
            if ascend_on and base >= RANK["rare"] and len(pd) >= POLISH["distinct_days"]:
                eff = min(RANK["legendary"], base + 1)
            if eff < RANK["rare"]:
                continue
            if k in used_bc and not (ascend_on and eff > slots_tier_of(slots, k)):
                continue
            out["candidates"] += 1
            # 고를 사람: 빈 칸 또는 지금 가보보다 높은 등급이면 바꿀 만한 사람
            empty = [p for p in people if p not in slots]
            better = [p for p in people if p in slots and slots[p][1] < eff and slots[p][0] != k]
            n_choice = len(empty) + len(better)
            out["choice_2plus"] += n_choice >= 2
            out["choice_1"] += n_choice == 1
            if not n_choice:
                out["no_slot"] += 1
                continue
            # 플레이어: 빈 칸 우선(70%), 아니면 바꾸기
            if empty and (not better or rng.random() < 0.7):
                p = rng.choice(empty)
            else:
                p = rng.choice(better); out["swap"] += 1
                used_bc.discard(slots[p][0])
            if k in used_bc:              # 닦아서 오른 같은 물건: 같은 사람 칸에서 등급만 오른다
                p = next(q for q, v in slots.items() if v[0] == k)
                out["ascended"] += 1
            slots[p] = (k, eff)
            used_bc.add(k)
            if eff == RANK["legendary"] and p not in third:
                third.add(p); out["third_memory"] += 1
                out["third_by_polish"] += base < RANK["legendary"]
    out["filled"] = len(slots)
    out["epic_plus_held"] = sum(1 for v in slots.values() if v[1] >= RANK["epic"])
    out["residents"] = len(people)
    out["legend_seen"] = int(any(r == "legendary" for r in rarity.values()))
    return out


def slots_tier_of(slots, k):
    for v in slots.values():
        if v[0] == k:
            return v[1]
    return 99


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--days", type=int, default=30)
    a = ap.parse_args()
    seeds = range(a.seeds)
    print(f"질랜디아 — 가보 칸 (씨앗 {a.seeds}, {a.days}일) · 닦아 오르기: 서로 다른 날 {POLISH['distinct_days']}번 = 한 등급 위(귀함 이상만)")
    print("\n표 H1·H2")
    print(f"{'':<16}{'후보 카드':<10}{'채운 칸/주민':<14}{'진귀함+ 칸':<11}{'세 번째 기억':<13}{'(닦아서)':<10}{'전설 실물 본 비율':<16}"
          f"{'고를 사람 2+':<13}{'바꾸기':<8}")
    for persona in ("A", "B"):
        for asc in (False, True):
            rs = [run(persona, s, a.days, asc) for s in seeds]
            c = mean(r["candidates"] for r in rs)
            print(f"{persona + (' 닦아 오르기' if asc else ' 실물만'):<16}{c:<10.1f}"
                  f"{mean(r['filled'] for r in rs):.1f}/{mean(r['residents'] for r in rs):<9.1f}"
                  f"{mean(r['epic_plus_held'] for r in rs):<11.1f}{mean(r['third_memory'] for r in rs):<13.2f}"
                  f"{mean(r['third_by_polish'] for r in rs):<10.2f}{mean(r['legend_seen'] for r in rs):<16.0%}"
                  f"{mean(r['choice_2plus'] for r in rs) / max(1e-9, c):<13.0%}{mean(r['swap'] for r in rs):<8.1f}")
    print("  '고를 사람 2+' = 귀함 이상이 나온 순간 빈 칸이거나 더 낮은 가보를 가진 사람이 둘 이상 = 「누구에게?」가 진짜 결정.")


if __name__ == "__main__":
    main()
