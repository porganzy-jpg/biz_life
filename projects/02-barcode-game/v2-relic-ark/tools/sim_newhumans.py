"""잔해 방주 — 신인류(공명) 도착 시뮬레이션 (기획·밸런스 소유)

    python tools/sim_newhumans.py            # 씨앗 30
입력: data/balance/newhumans.json. 스캔 흐름은 sim_expedition.KeyedScan(바코드마다 갈래 고정)에
바코드마다 고정 희귀도를 더해 쓴다. 공명 판정은 hash(uid|barcode|day) — 같은 날 재스캔은 굴리지 않는다.

  N1 첫 공명 날짜 · 30/60일 수     N2 주민 곡선(원정 켬, 신인류 켬/끔)     N3 방 곡선·수입 영향
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim_expedition as X   # noqa: E402

NH = json.load(open(os.path.join(os.path.dirname(HERE), "data", "balance", "newhumans.json"), encoding="utf-8"))
R = NH["resonance"]
RAR = X.ECON["scan"]["rarity"]
RN = ["common", "uncommon", "rare", "epic", "legendary"]
RP = [RAR["_distribution"][n] for n in RN]
# 하루 6회는 사용자가 지정한 '보통'. 기존 세 유형도 함께 본다
PROF = [("가벼움 3/일", 3, 55), ("보통 6/일", 6, 80), ("보통 8/일", 8, 90), ("열심 20/일", 20, 160)]


def resonance_days(seed: int, scans: int, pool: int, days: int) -> list[int]:
    """공명이 난 날 목록(그날 스캔에서). 도착은 다음 날."""
    scan = X.KeyedScan(random.Random(seed + 1), pool)
    rr = random.Random(f"rar|{seed}")
    rarity = [rr.choices(RN, weights=RP)[0] for _ in range(pool)]
    got, counter, out = 0, 0, []
    for day in range(1, days + 1):
        _, scans_ = scan.one_day(scans)
        seen = set()
        for bc, cat, m in scans_:
            if bc in seen or m <= 0:
                continue
            seen.add(bc)
            if day < R["not_before_day"] or got >= R["max_per_ark_act1"]:
                continue
            if len(seen) > R["daily_eligible_scans"]:
                continue                    # 하루 처음 N번의 유효 스캔만 굴린다
            counter += 1
            ph = R["first"] if got == 0 else R["after"]
            p = ph["base_rate"] * R["rarity_mult"][rarity[bc]]
            hit = random.Random(f"{seed}|{bc}|{day}").random() < p or counter >= ph["pity_at"]
            if hit:
                got += 1; counter = 0; out.append(day)
                break                       # 하루 하나까지
    return out


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=30)
    a = ap.parse_args()
    seeds = range(a.seeds)
    print("잔해 방주 — 신인류(공명) 시뮬레이션", NH["_version"])
    print(f"first {R['first']} · after {R['after']} · {R['not_before_day']}일부터 · 상한 {R['max_per_ark_act1']}")

    print("\n" + "=" * 100)
    print(f"표 N1. 공명 날짜 — 씨앗 {a.seeds}개 (도착은 공명 다음 날)")
    print("=" * 100)
    print(f"{'유형':<16}{'첫 공명 중앙':<12}{'10~90분위':<14}{'5~10일 안':<11}{'30일 수':<9}{'60일 수':<9}{'둘째까지 간격(중앙)':<16}")
    for name, n, pool in PROF:
        ds = [resonance_days(s, n, pool, 60) for s in seeds]
        first = [d[0] for d in ds if d]
        gaps = [d[1] - d[0] for d in ds if len(d) > 1]
        print(f"{name:<16}{statistics.median(first):<12.0f}{f'{pct(first, .1)}~{pct(first, .9)}':<14}"
              f"{sum(1 for f in first if 5 <= f + 1 <= 10) / len(first):<11.0%}"
              f"{statistics.mean(sum(1 for x in d if x <= 30) for d in ds):<9.1f}{statistics.mean(len(d) for d in ds):<9.1f}"
              f"{(statistics.median(gaps) if gaps else 0):<16.0f}")
    print("  목표: 보통(6/일) 첫 도착 5~10일, 그 뒤 2~3주에 하나.")

    print("\n" + "=" * 100)
    print(f"표 N2·N3. 곡선 — sim_expedition 진행(원정 켬)에 공명 도착을 얹는다. 씨앗 {min(a.seeds, 20)}개")
    print("=" * 100)
    print(f"{'유형':<18}{'':<6}{'주민 7/14/30':<18}{'방 7/14/30':<20}{'주민 6 도달일':<12}{'스캔 비중(건설)':<14}{'손님 대기 30일':<12}")
    if NH["arrival"].get("knock_daily_chance_with_newhumans") is not None:
        X.NEWC["knock"]["daily_chance"] = NH["arrival"]["knock_daily_chance_with_newhumans"]
    base_knock = json.load(open(os.path.join(os.path.dirname(HERE), "data", "balance", "expedition.json"), encoding="utf-8"))["newcomers"]["knock"]["daily_chance"]
    print(f"  두드림 확률: 끔 {base_knock} / 켬 {X.NEWC['knock']['daily_chance']}")
    for prof in X.PROFILES:
        n = prof[1]; pool = prof[2]
        for on in (False, True):
            runs = []
            X.NEWC["knock"]["daily_chance"] = NH["arrival"].get("knock_daily_chance_with_newhumans", base_knock) if on else base_knock
            for s in range(min(a.seeds, 20)):
                bonus = {}
                if on:
                    for d in resonance_days(s, n, pool, 30):
                        bonus[d + 1] = bonus.get(d + 1, 0) + 1
                runs.append(X.run_day_sim(prof, 30, seed=s, bonus_guests=bonus))
            res = [statistics.mean(r["per_day"][d - 1]["res"] for r in runs) for d in (7, 14, 30)]
            rooms = [statistics.mean(r["per_day"][d - 1]["rooms"] for r in runs) for d in (7, 14, 30)]
            six = statistics.mean(next((p["day"] for p in r["per_day"] if p["res"] >= 6), 31) for r in runs)
            share = statistics.mean(r["scan_b"] / max(1e-9, r["scan_b"] + r["box_b"] + r["exp_direct_b"] + r["room_b"] + r["gift_b"]) for r in runs)
            gq = statistics.mean(r["per_day"][29]["guests"] for r in runs)
            print(f"{prof[0]:<18}{'켬' if on else '끔':<6}{'/'.join(f'{x:.1f}' for x in res):<18}{'/'.join(f'{x:.1f}' for x in rooms):<20}"
                  f"{six:<12.1f}{share:<14.0%}{gq:<12.1f}")
    print("  주민 목표 5/7/10, 방 목표 6/9/12(원정 켬 기준 14일은 원래 +1 빠름 — design_expedition §followup).")


if __name__ == "__main__":
    main()
