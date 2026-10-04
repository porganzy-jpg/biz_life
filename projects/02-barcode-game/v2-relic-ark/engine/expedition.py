"""
잔해 방주 — 원정 엔진 (docs/EXPEDITION.md · data/balance/expedition.json)

순수 함수 모듈. 상태(dict)를 읽지 않고, server.py 가 모아 주는 값만 받는다.
결과는 **출발 때 한 번** 시드(`uid|exp_id`)로 굴려 둔 균등난수 목록이다(D6). 따라 나가기·갈림길·위험 앞의 선택은
그 난수를 **다시 굴리지 않고** 같은 난수에 다른 문턱을 대는 것뿐이다(공통 난수). 그래서
  · 따라 나가서 자동 규칙과 같은 것을 고르면 결과가 **바이트까지 같다**
  · 갈림길을 바꾸면 내용물(재료↔상자)만 바뀌고 기댓값은 기획이 맞춘 만큼 같다.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

_BAL = Path(__file__).resolve().parent.parent / "data" / "balance" / "expedition.json"
_CACHE: dict = {"mtime": "unset", "data": {}}


def X() -> dict:
    """expedition.json(기획 소유). 바뀌면 재시작 없이 다시 읽는다. 깨져 있으면 직전 값을 지킨다."""
    try:
        mt = _BAL.stat().st_mtime
    except OSError:
        mt = None
    if mt != _CACHE["mtime"]:
        data = _CACHE.get("data") or {}
        if mt is not None:
            try:
                data = json.loads(_BAL.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                print(f"[expedition] expedition.json 을 읽지 못했다 → 직전 값: {e}")
        _CACHE.update({"mtime": mt, "data": _clean(data)})
    return _CACHE["data"]


def _clean(o):
    """'_' 로 시작하는 키는 기획의 주석이다 — 규칙을 읽을 때 섞이지 않게 걷어 낸다."""
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, list):
        return [_clean(x) for x in o]
    return o


def g(path: str, default=None):
    cur = X()
    for k in path.split("."):
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur


HEAD = 3                                   # 따라 나가기 구간의 줍기 수(scene.follow_picks_max)
KINDS = ("material", "box", "relic", "empty")
KEEP_RANK = {"box": 0, "relic": 1, "material": 2, "empty": 3}
RARITY_EDGES = ((0.598, "common"), (0.844, "uncommon"), (0.944, "rare"), (0.984, "epic"), (1.01, "legendary"))
RARITY_UP = {"common": "uncommon", "uncommon": "rare", "rare": "epic", "epic": "legendary", "legendary": "legendary"}
CATS = ("food", "drink", "medical", "electronics", "stationery", "book", "apparel", "tobacco")


def head_n() -> int:
    return int(g("scene.follow_picks_max", HEAD) or HEAD)


def check_p(stat: float, pair: bool = False) -> float:
    p = 0.55 + 0.07 * (float(stat) - 5)
    if pair:
        p += float(g("stats.check.pair_bonus", 0.05))
    return max(0.20, min(0.95, p))


def carry_slots(hand: int) -> int:
    t = g("stats.hand.table") or {}
    v = t.get(str(int(hand)))
    return int(v) if isinstance(v, (int, float)) else 2 + math.ceil(int(hand) / 2)


def main_material(cat: str) -> str:
    return (g("boxes.category_main_material") or {}).get(cat, "scrap")


def eight_materials() -> list:
    vals = []
    for v in (g("boxes.category_main_material") or {}).values():
        if v not in vals:
            vals.append(v)
    return vals or ["scrap"]


def find_probs(eye: int, branch: str | None = None) -> dict:
    p = dict(g("finds.per_action") or {"material": 0.36, "box": 0.08, "relic": 0.07, "empty": 0.49})
    sh = g("stats.eye.find_shift_per_point") or {}
    d = int(eye) - 5
    for k in ("box", "relic"):
        p[k] = p.get(k, 0) + float(sh.get(k, 0)) * d
    if branch in ("lit", "dark"):
        for k, v in (g(f"scene.fork.{branch}") or {}).items():
            if k in p and isinstance(v, (int, float)):
                p[k] += v
    for k in ("material", "box", "relic"):
        p[k] = max(0.0, p.get(k, 0))
    p["empty"] = max(0.0, 1.0 - p["material"] - p["box"] - p["relic"])
    return p


def kind_of(u: float, probs: dict) -> str:
    acc = 0.0
    for k in ("material", "box", "relic"):
        acc += probs[k]
        if u < acc:
            return k
    return "empty"


def rarity_of(u: float, up_u: float, deep: bool) -> str:
    r = next(name for edge, name in RARITY_EDGES if u < edge)
    if deep and up_u < 0.2:
        r = RARITY_UP[r]
    return r


# ─────────────────────────────────────────────────────────────
# 출발 때 한 번 굴리기
# ─────────────────────────────────────────────────────────────
def roll(seed: str, *, members: list[dict], dest: dict, dest_cat: str, length: str,
         danger_mul: float, lingering: str | None, learning: bool, recent_cats: list[str],
         kinds_weights: dict | None, rescue_p: float, clue_p: float, discover_p: float,
         tutorial: bool = False, deep: bool = False) -> dict:
    """members = [{"id","stats":{hand,eye,breath,nerve}}]. 반환 = 저장할 결과(균등난수와 그 해석에 필요한 값)."""
    rng = random.Random(f"exp|{seed}")
    L = (g("lengths") or {}).get(length) or {}
    tank = int(L.get("tank", 2))
    breath = min(int(m["stats"].get("breath", 5)) for m in members)
    eye = max(int(m["stats"].get("eye", 5)) for m in members)
    x = tank * (1 + float(g("stats.breath.per_point", 0.1)) * (breath - 5))
    n = int(x)
    if rng.random() < x - n:
        n += 1
    n = max(int(g("stats.breath.min_actions", 1)), n)
    if tutorial:
        n = head_n()
    acts = [{"u": rng.random(), "u2": rng.random(), "u3": rng.random()} for _ in range(n)]
    carry = sum(carry_slots(int(m["stats"].get("hand", 5))) for m in members)
    # 위험 한 번까지
    p = 0.0 if (learning or tutorial) else float(L.get("danger", 0)) * float(danger_mul) + \
        float((g("raid_link.lingering_add") or {}).get(lingering or "", 0))
    p = max(0.0, min(0.95, p))
    u_dz, u_at, u_kind, u_chk, u_ling = (rng.random() for _ in range(5))
    danger = None
    if u_dz < p:
        w = dict(kinds_weights or g("danger.default_kind_weights") or {"air": 1})
        lk = (g("raid_link.lingering_kind") or {}).get(lingering or "")
        if lk and u_ling < 0.6:
            kind = lk
        else:
            tot = sum(w.values()) or 1
            acc, kind = 0.0, next(iter(w))
            for k, v in w.items():
                acc += v / tot
                if u_kind < acc:
                    kind = k
                    break
        stat = ((g("danger.kinds") or {}).get(kind) or {}).get("check", "breath")
        best = max(int(m["stats"].get(stat, 5)) for m in members)
        danger = {"kind": kind, "at": int(u_at * n), "stat": stat,
                  "p_pass": round(check_p(best, len(members) > 1), 4), "u": u_chk}
    out = {"actions": n, "acts": acts, "carry": carry, "eye": eye, "breath": breath,
           "dest_cat": dest_cat, "recent_cats": list(recent_cats or []), "deep": bool(deep),
           "danger_p": round(p, 4), "danger": danger,
           "u_rescue": rng.random(), "rescue_p": rescue_p, "u_clue": rng.random(), "clue_p": clue_p,
           "u_clue_pick": rng.random(), "u_discover": rng.random(), "discover_p": discover_p,
           "u_role": rng.random(), "tutorial": bool(tutorial)}
    if tutorial and n >= 3:
        out["tutorial_box_at"] = 2
    return out


def danger_auto(danger: dict | None) -> str | None:
    if not danger:
        return None
    return "hide" if danger["p_pass"] >= 0.55 else "turn_back"


def item_at(res: dict, i: int, branch: str | None) -> dict:
    """i 번째 행동이 줍는 것. 갈림길(branch)은 HEAD 번째 행동부터 문턱만 옮긴다(난수는 그대로)."""
    a = res["acts"][i]
    if res.get("tutorial_box_at") == i:
        return {"kind": "box", "cat": "blank", "i": i}         # 튜토리얼 빈 원 상자(아무 성문이나 맞는다)
    probs = find_probs(res["eye"], branch if i >= head_n() else None)
    kind = kind_of(a["u"], probs)
    if kind == "material":
        if a["u2"] < float(g("finds.material_bias.destination", 0.6)) and res["dest_cat"] != "*":
            mat = main_material(res["dest_cat"])
        else:
            eight = eight_materials()
            mat = eight[int(a["u3"] * len(eight)) % len(eight)]
        return {"kind": "material", "res": mat, "i": i}
    if kind == "box":
        pick = g("boxes.category_pick") or {"destination": 0.5}
        recent = res.get("recent_cats") or []
        dest_known = res["dest_cat"] in CATS
        if dest_known and (a["u2"] < float(pick.get("destination", 0.5)) or not recent):
            cat = res["dest_cat"]
        elif recent:
            cat = recent[int(a["u3"] * len(recent)) % len(recent)]
        else:
            cat = CATS[int(a["u3"] * len(CATS)) % len(CATS)]
        # 갈래를 모르는 목적지(문 앞·모르는 쪽)는 최근 찍은 갈래, 그것도 없으면 여덟 중 하나 — 상자에는 늘 정본 갈래가 찍힌다
        return {"kind": "box", "cat": cat, "i": i}
    if kind == "relic":
        return {"kind": "relic", "rarity": rarity_of(a["u2"], a["u3"], res.get("deep")), "i": i}
    return {"kind": "empty", "i": i}


def slots_of(item: dict) -> int:
    return int((g("stats.hand.slots") or {}).get(item["kind"], 1)) if item["kind"] != "empty" else 0


def value_of(item: dict) -> float:
    """비교용 가치 단위(재료 1). 상자 = 주 재료 4 + 유물 25%, 유물 = 2(재료 둘 몫으로 본다)."""
    k = item["kind"]
    if k == "material":
        return 1.0
    if k == "relic":
        return 2.0
    if k == "box":
        return float(g("boxes.value.units", 4)) + float(g("boxes.value.relic_chance", 0.25)) * 2.0
    return 0.0


def settle(res: dict, *, fork: str, danger_choice: str | None, dropped: list | None = None,
           recall_keep: int | None = None) -> dict:
    """굴려 둔 결과를 선택과 함께 펼친다. 반환: 들고 온 것·두고 온 것·위험 결과·시간 비율."""
    n = res["actions"]
    d = res.get("danger")
    keep_n = n
    early = None
    late_min = 0
    danger_out = None
    haul_cut = False
    injure = False
    wear_extra = 0
    flags: list = []
    if d and recall_keep is not None and recall_keep <= d["at"]:
        d = None                                   # 그 자리에 닿기 전에 불러들였다 — 위험을 만나지 않았다
    if d:
        choice = danger_choice or danger_auto(d)
        if choice == "turn_back":
            keep_n = min(keep_n, d["at"])
            early = keep_n / n if n else 0.0
            danger_out = {"kind": d["kind"], "ok": None, "choice": "turn_back"}
        else:
            ok = d["u"] < d["p_pass"]
            spec = (g("danger.kinds") or {}).get(d["kind"]) or {}
            danger_out = {"kind": d["kind"], "ok": ok, "choice": choice or "hide"}
            if spec.get("imprint_on_any") == "knock_heard" or d["kind"] == "beast":
                flags.append("beast_left")
            if not ok:
                f = spec.get("fail") or {}
                if f.get("actions_lost_frac"):
                    keep_n = min(keep_n, max(d["at"], n - int(round(n * float(f["actions_lost_frac"])))))
                if f.get("actions_lost"):
                    keep_n = min(keep_n, max(0, n - int(f["actions_lost"])))
                if f.get("early_return"):
                    early = keep_n / n if n else 0.0
                if f.get("late_minutes"):
                    late_min = int(f["late_minutes"])
                if f.get("haul_lost_frac"):
                    haul_cut = float(f["haul_lost_frac"])
                if f.get("injury"):
                    injure = True
                if f.get("suit_wear"):
                    wear_extra = int(f["suit_wear"])
                if d["kind"] == "air":
                    flags.append("air_survived")
    if recall_keep is not None:
        keep_n = min(keep_n, recall_keep)
    items = [item_at(res, i, fork) for i in range(keep_n)]
    got = [it for it in items if it["kind"] != "empty"]
    left: list = []
    if haul_cut and d:
        before = [it for it in got if it["i"] < d["at"]]
        before.sort(key=lambda it: (-KEEP_RANK[it["kind"]], -it["i"]))      # 가치 낮은 것부터 놓는다
        drop_n = int(len(before) * haul_cut)
        dropped_ids = {it["i"] for it in before[:drop_n]}
        left += [it for it in got if it["i"] in dropped_ids]
        got = [it for it in got if it["i"] not in dropped_ids]
    if dropped:
        ds = set(int(x) for x in dropped)
        left += [it for it in got if it["i"] in ds]
        got = [it for it in got if it["i"] not in ds]
    # 손 칸 — 상자 > 유물 > 재료, 같으면 먼저 주운 것
    got.sort(key=lambda it: (KEEP_RANK[it["kind"]], it["i"]))
    kept, used = [], 0
    for it in got:
        s = slots_of(it)
        if used + s <= res["carry"]:
            kept.append(it)
            used += s
        else:
            left.append(it)
    kept.sort(key=lambda it: it["i"])
    return {"kept": kept, "left": left, "keep_n": keep_n, "danger": danger_out, "early": early,
            "late_min": late_min, "injure": injure, "wear_extra": wear_extra, "flags": flags,
            "turned_back": bool(danger_out and danger_out.get("choice") == "turn_back"),
            "value": round(sum(value_of(it) for it in kept), 4)}
