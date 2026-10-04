"""잔해 방주 — 7일 플레이테스트(2026-10-04) 고칠 것 검증 (기획·밸런스 소유)

    python tools/sim_playtest_fixes.py            # 씨앗 30
표
  P1 선반 칸 vs 서로 다른 물건 — 2주차까지 자라는가
  P2 첫 주 위협 — 보장 없을 때 7일 안에 위협 0회인 비율
  P3 재료 막힘 — 공방 바꾸기(나쁜 비율) 켬/끔: 곡선·식량 재고·막힌 날
  P4 값 0 재스캔 — 닦기 [3,5] vs [2,4], 작은 반응
입력은 data/balance/*.json 의 **제안값**(economy.shelf·workshop_trade, threats.first_week_guarantee, stakes.polish).
"""
from __future__ import annotations

import argparse
import io
import json
import os
import random
import statistics
import sys
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import sim_economy as E   # noqa: E402

with redirect_stdout(io.StringIO()):
    import sim_stakes as K     # noqa: E402   (audit_collection 가구 모델 + 닦기)
    import audit_collection as AC   # noqa: E402

ECON, THR = E.ECON, E.THREAT
SHELF = ECON["shelf"]
TRADE = ECON["workshop_trade"]
FWG = THR["first_week_guarantee"]
STK = K.STK


def mean(x):
    x = list(x)
    return sum(x) / len(x) if x else 0.0


class ArkT(E.Ark):
    """방 상태를 날마다 기록하고, 공방 바꾸기(켬일 때)를 짓기 전에 한다."""

    trade_on = False

    def __init__(self, rng):
        super().__init__(rng)
        self.log = []
        self.traded = 0.0
        self.blocked = 0

    def _next_need(self):
        for rid in E.BUILD_ORDER:
            if rid not in self.rooms:
                if rid == "lounge" and self.rooms.get("quarters", 0) < 2:
                    continue
                if rid == "bath" and self.rooms.get("generator", 0) < 2:
                    continue
                return self._cost_of(rid, 1)
        for rid in E.UPGRADE_ORDER:
            lv = self.rooms.get(rid, 0)
            if 0 < lv < 2:
                return self._cost_of(rid, 2)
        return {}

    def spend(self, day):
        need = self._next_need()
        short = {k: v - self.res.get(k, 0) for k, v in need.items() if self.res.get(k, 0) < v}
        if short:
            self.blocked += 1
        if self.trade_on and short and "workshop" in self.rooms:
            out_left = TRADE["daily_out_cap"]
            for k in sorted(short, key=lambda x: -short[x]):
                if k not in TRADE["to"]:
                    continue
                while out_left > 0 and short[k] > 0:
                    src = max(TRADE["from"], key=lambda s: self.res.get(s, 0))
                    if self.res.get(src, 0) - TRADE["rate"] < TRADE["keep_reserve"]:
                        break
                    self.res[src] -= TRADE["rate"]; self.res[k] = self.res.get(k, 0) + 1
                    short[k] -= 1; out_left -= 1; self.traded += 1
        super().spend(day)
        self.log.append(dict(self.rooms, _floor=self.depth_floor))


def run(trade: bool, seed: int, scans=8, pool=90, days=30):
    ArkT.trade_on = trade
    orig = E.Ark
    E.Ark = ArkT
    try:
        return E.run_economy(scans, days, seed, pool)
    finally:
        E.Ark = orig


def capacity(rooms: dict, rule: str) -> int:
    """rule: before(지금 서버: 선반 가장 많은 방 하나) / after(제안: 식량창고 바탕 + 창고 칸 합, 창고 둘까지)."""
    st_lv = rooms.get("storage", 0)
    if rule == "before":
        return {0: 6, 1: 6, 2: 12, 3: 20}[st_lv]
    return (SHELF["base_pantry"] + (SHELF["per_storage_level"][str(st_lv)] if st_lv else 0)
            + SHELF["per_floor_reclaimed"] * rooms.get("_floor", 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=30)
    a = ap.parse_args()
    seeds = range(a.seeds)
    print("잔해 방주 — 7일 플레이테스트 고칠 것 검증 (씨앗", a.seeds, ")")

    # ── P1 선반
    print("\n" + "=" * 100)
    print("표 P1. 선반 칸 vs 서로 다른 물건(유물을 선반에 둘 후보) — 보통 플레이어(스캔 8/일)")
    print("=" * 100)
    runs = [run(False, s) for s in seeds]
    with redirect_stdout(io.StringIO()):
        saved = dict(AC.ASSUME)
        AC.ASSUME.update({"household_items": 32, "new_items_per_week": 4})
        cur_small, _ = AC.simulate(6, 30, 40, seed=1)
        AC.ASSUME.clear(); AC.ASSUME.update(saved)
        cur_big, _ = AC.simulate(6, 30, 40, seed=1)
    print(f"{'일':<5}{'칸(지금)':<10}{'칸(제안)':<10}{'창고 레벨 평균':<14}{'서로 다른 물건(가구 32, 플레이테스트)':<36}{'(가구 120, 감사)':<16}")
    for d in (1, 3, 5, 7, 10, 14, 21, 30):
        b = mean(capacity(r["ark"].log[d - 1], "before") for r in runs)
        f = mean(capacity(r["ark"].log[d - 1], "after") for r in runs)
        lv = mean(r["ark"].log[d - 1].get("storage", 0) for r in runs)
        print(f"{d:<5}{b:<10.1f}{f:<10.1f}{lv:<14.1f}{mean(cur_small['distinct_barcodes'][d]):<36.1f}{mean(cur_big['distinct_barcodes'][d]):<16.1f}")
    print("  '서로 다른 물건'이 칸보다 많으면 선반은 차 있다. 닦기(같은 물건 다시 찍기)는 칸을 먹지 않는다.")
    print("  넘친 유물은 사라지지 않고 '창고 상자'(도감에서 보임)로 간다 — economy.json shelf.overflow.")

    # ── P2 위협 보장
    print("\n" + "=" * 100)
    print("표 P2. 첫 주에 위협이 한 번도 안 오는 비율 (등급 1, 2일째부터)")
    print("=" * 100)
    fq = THR["frequency"]["by_grade"]["1"]
    p_threat = fq["threat_day_rate"]
    none7 = (1 - p_threat) ** 6
    by4 = 1 - (1 - p_threat) ** 3
    print(f"  위협 오는 날 {p_threat:.1%}/일 → 2~7일째에 0회일 확률 {none7:.0%}, 4일째까지 1회 이상 {by4:.0%}")
    print(f"  제안: {FWG['by_day']}일째까지 위협이 없었으면 그날 '{FWG['creature']}' 세기 {FWG['severity']}, 대상 = 사람이 있는 방 → 첫 주 위협 0회 비율 0%")

    # ── P3 재료 막힘
    print("\n" + "=" * 100)
    print(f"표 P3. 공방 바꾸기 — {TRADE['rate']}:1, 하루 {TRADE['daily_out_cap']}개까지, 재고 {TRADE['keep_reserve']} 남김 (보통 8/일, 씨앗 {a.seeds})")
    print("=" * 100)
    print(f"{'':<8}{'방 7/14/30':<20}{'Lv2 14일':<10}{'식량 7일':<10}{'직물 7일':<10}{'부품 7일':<10}{'막힌 날(30일)':<14}{'바꾼 수(30일)':<12}")
    for tr in (False, True):
        rs = [run(tr, s) for s in seeds]
        rooms = "/".join(f"{mean(r['hist'][d - 1]['rooms'] for r in rs):.1f}" for d in (7, 14, 30))
        print(f"{'켬' if tr else '끔':<8}{rooms:<20}{mean(r['hist'][13]['lv2'] for r in rs):<10.1f}"
              f"{mean(r['hist'][6]['food'] for r in rs):<10.1f}{mean(r['hist'][6]['cloth'] for r in rs):<10.1f}"
              f"{mean(r['hist'][6]['parts'] for r in rs):<10.1f}{mean(r['ark'].blocked for r in rs):<14.1f}{mean(r['ark'].traded for r in rs):<12.1f}")
    print("  sim 은 보관 상한(창고 칸 × 6)을 지킨다 — 플레이테스트의 식량 112 는 서버에 상한이 없어서다(요청).")

    # ── P4 값 0
    print("\n" + "=" * 100)
    print("표 P4. 값 0 재스캔 — 닦기 단계 전/후 (가구 32 + 새 물건 4/주 = 플레이테스트 가정, 하루 6회)")
    print("=" * 100)
    print(f"{'닦기':<10}{'값0(감쇠, 7일)':<16}{'값0(감쇠, 30일)':<16}{'아무것도 없음 7일':<18}{'아무것도 없음 30일':<18}{'3단계 30일':<10}")
    with redirect_stdout(io.StringIO()):
        saved = dict(AC.ASSUME)
        AC.ASSUME.update({"household_items": 32, "new_items_per_week": 4})
    dec_new = ECON["scan"]["rescan_decay"]["values"]
    orig_mult = AC.rescan_multiplier
    for spl, dec in (([3, 5], None), (list(STK["polish"]["scans_per_level"]), None), (list(STK["polish"]["scans_per_level"]), dec_new)):
        K.POL["scans_per_level"] = spl
        AC.rescan_multiplier = (lambda i, d=dec: d[min(i, len(d) - 1)]) if dec else orig_mult
        cur, _ = K.collect_sim(6, 30, True, 60, seed=3)
        AC.rescan_multiplier = orig_mult
        spl = f"{spl}" + (" +바닥" if dec else "")
        print(f"{str(spl):<10}{mean(cur['zero_raw'][7]):<16.0%}{mean(cur['zero_raw'][30]):<16.0%}"
              f"{mean(cur['zero'][7]):<18.0%}{mean(cur['zero'][30]):<18.0%}{mean(cur['lv3'][30]):<10.1f}")
    AC.ASSUME.clear(); AC.ASSUME.update(saved)
    print("  '아무것도 없음' = 감쇠 0 이면서 닦기 진척·새 물빛도 없는 스캔. 여기에 '작은 반응'(stakes.polish.zero_reaction)이")
    print("  붙으면 화면에서 아무 일도 없는 스캔은 0 이 된다 — 남는 것은 재료 값 0 뿐이고 그것은 감쇠의 의도다.")


if __name__ == "__main__":
    main()
