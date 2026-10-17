"""질랜디아 C안 — 마음 쌓기 단계 도달일 · 편한 방 배율 (기획·밸런스 소유)

    python tools/sim_c_plan.py      # 씨앗 30, 30일
마음: sim_core_a 의 A 모드(「어디로」 최선 고르기)를 그대로 돌리며 사람마다 건넨 종류를 점수로 센다.
편한 방: sim_statprod 의 greedy 배치에 '편한 방 배율'을 얹어 생산 변화를 잰다.
"""
from __future__ import annotations

import json
import os
import random
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import sim_core_a as CA   # noqa: E402

C = json.load(open(os.path.join(ROOT, "data", "balance", "c_plan.json"), encoding="utf-8"))
PTS = C["heart"]["points"]
TH = C["heart"]["levels"]


def mean(x):
    x = list(x)
    return sum(x) / len(x) if x else 0.0


def run_hearts(persona, seed, days):
    """sim_core_a.run 을 따라가되, 건넨 순간의 종류로 점수를 쌓는다(가보는 귀함 이상 4% 가정)."""
    rng = random.Random(f"{persona}|{seed}")
    pts = defaultdict(float)
    reach = defaultdict(dict)          # pid -> level -> day
    orig = CA.option_values

    def hooked(people, rooms_decor, item, day, seed_, shelf_has, shelf_free):
        opts = orig(people, rooms_decor, item, day, seed_, shelf_has, shelf_free)
        best = opts[0]
        if best[1].startswith("p:"):
            kind = best[2]
            key = {"chain": "chain", "memory": "memory", "need": "need", "like": "like", "neutral": "warm"}.get(kind, "warm")
            if rng.random() < C["heart"]["_sim_heirloom_share"]:
                key = "heirloom"
            p = best[3]
            pts[p.id] += PTS[key]
            for i, t in enumerate(TH):
                if pts[p.id] >= t and i + 1 not in reach[p.id]:
                    reach[p.id][i + 1] = day
        return opts
    CA.option_values = hooked
    try:
        CA.run(persona, seed, days, "A")
    finally:
        CA.option_values = orig
    return pts, reach


def main():
    seeds = range(30)
    days = 30
    print("질랜디아 C안 — 마음 쌓기 (씨앗 30, 30일)")
    print(f"점수 {PTS} · 단계 문턱 {TH}")
    print(f"{'':<6}" + "".join(f"{'L'+str(i+1)+' 첫 사람':<12}" for i in range(len(TH))) + "   (중앙값 날짜, 31 = 30일 안 못 닿음)")
    for persona in ("A", "B"):
        firsts = defaultdict(list); counts = defaultdict(list)
        for s in seeds:
            pts, reach = run_hearts(persona, s, days)
            for lv in range(1, len(TH) + 1):
                ds = [r[lv] for r in reach.values() if lv in r]
                firsts[lv].append(min(ds) if ds else 31)
                counts[lv].append(len(ds))
        print(f"{persona:<6}" + "".join(f"{statistics.median(firsts[lv]):<12.0f}" for lv in range(1, len(TH) + 1)))
        print(f"{'':<6}" + "".join(f"{mean(counts[lv]):<12.1f}" for lv in range(1, len(TH) + 1)) + "   (30일에 그 단계에 닿은 사람 수, 평균)")
    print("  목표: 첫 사람 L2 2~3일, L3 1주, L4 2주, L5 3~4주(A). B 는 하루 쯤 늦게. 30일에 L5 는 한두 사람 — 드물게.")


if __name__ == "__main__":
    main()
