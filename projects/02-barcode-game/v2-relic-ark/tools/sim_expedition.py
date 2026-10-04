"""잔해 방주 — 원정·문간 시뮬레이션 (기획·밸런스 소유)

입력: data/balance/expedition.json (+ economy / threats / defense / equipment)
경제·스캔·방어 모델은 tools/sim_economy.py 를 그대로 가져다 쓴다(같은 가정에서 비교하려고).

    python tools/sim_expedition.py            # 전체 표 (30일·60일)
    python tools/sim_expedition.py --trip     # 한 번의 원정 표만 (X1·X2)
    python tools/sim_expedition.py --days 30  # 진행 표를 30일로만

표 목록
  X1 누구를 보내나 — 조 구성 × 길이        X2 어디로 가나 — 목적지 × 길이 (공기당 가치)
  X3 30/60일 진행 — 플레이 유형 셋          X4 목표 곡선 — 주민·방 (원정 켬/끔)
  X5 수입 출처 — 스캔이 주 수입인가          X6 재스캔이 열쇠가 되는가 (PM 요구 b)
  X7 습격과의 거래 — 빠진 사람의 값, 물 먼저/길 먼저   X8 결석률
  X9 대가의 크기 — 부상·각인·늦은 귀환
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sim_economy as E  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EXP = json.loads((ROOT / "data" / "balance" / "expedition.json").read_text(encoding="utf-8"))
ECON, THREAT = E.ECON, E.THREAT

LEN = {k: EXP["lengths"][k] for k in ("short", "half", "long")}
FIND = EXP["finds"]["per_action"]
BOX = EXP["boxes"]
DEST = EXP["destinations"]
SPOTS = {k: v for k, v in DEST["spots"].items() if not k.startswith("_")}
DANGER = EXP["danger"]
NEWC = EXP["newcomers"]
AIR = EXP["air"]
LINK = EXP["raid_link"]
CAT_MAT = BOX["category_main_material"]
CATS = list(CAT_MAT)
MAT8 = ["food", "water", "med", "parts", "knowledge", "cloth", "trade", "scrap"]
BUILD = set(E.BUILD_KEYS)

# server.py RUMOR_RULES_DEEP — 단서가 열리는 스캔 누적(서버가 정본, 여기는 사본)
CLUE_RULES = {"spot_vent_garden": ("electronics", 2), "spot_jelly_bloom": ("stationery", 3),
              "spot_sunken_courtyard": ("book", 3), "spot_whale_fall": ("food", 3),
              "spot_brine_lake": ("drink", 3), "spot_kelp_ceiling": ("apparel", 4)}

# server.py STAT_BASE — 역할 기본값
STAT_BASE = {
    "scout": (4, 7, 7, 5), "cook": (7, 4, 5, 5), "medic": (7, 6, 4, 5), "engineer": (8, 5, 5, 4),
    "farmer": (6, 5, 7, 4), "scholar": (5, 8, 4, 4), "trader": (4, 6, 5, 7), "kid": (3, 6, 4, 3),
}
ROLES = list(STAT_BASE)
SK = ("hand", "eye", "breath", "nerve")


def make_person(rng: random.Random, role: str, pid: int) -> dict:
    """server.py roll_stats 와 같은 규칙: 기본값 + (−2..+2) + 특이점 ±2, 1~10."""
    st = {k: STAT_BASE[role][i] + rng.randint(-2, 2) for i, k in enumerate(SK)}
    q = rng.choice(SK)
    st[q] += 2 if rng.random() < 0.5 else -2
    st = {k: max(1, min(10, v)) for k, v in st.items()}
    return {"id": pid, "role": role, "stats": st, "born_breath": st["breath"], "crises": set(),
            "imprints": 0, "trip_pts": 0.0, "injured_until": -1.0, "trips": 0}


# ─────────────────────────────────────────────────────────────
# 스탯 → 원정 수치 (expedition.json stats)
# ─────────────────────────────────────────────────────────────
def breath_mul(b: int) -> float:
    """숨 1 = 공기 10%. 숨 5 = ×1.0, 숨 9 = ×1.4, 숨 3 = ×0.8 (expedition.json stats.breath)."""
    return 1.0 + EXP["stats"]["breath"]["per_point"] * (b - 5)


def stoch_round(rng: random.Random, x: float) -> int:
    """소수 부분을 확률로 올린다. 서버는 원정 id 시드로 같은 일을 한다(결정적)."""
    base = int(math.floor(x))
    return base + (1 if rng.random() < x - base else 0)


def carry_of(hand: int) -> int:
    return 2 + math.ceil(hand / 2)


def check_p(stat: int, pair: bool) -> float:
    p = 0.55 + 0.07 * (stat - 5)
    if pair:
        p += EXP["stats"]["check"]["pair_bonus"]
    return max(0.20, min(0.95, p))


def find_probs(eye: int) -> dict:
    d = eye - 5
    sh = EXP["stats"]["eye"]["find_shift_per_point"]
    p = {"material": FIND["material"], "box": FIND["box"] + sh["box"] * d,
         "relic": FIND["relic"] + sh["relic"] * d, "empty": FIND["empty"] + sh["empty"] * d}
    p = {k: max(0.0, v) for k, v in p.items()}
    s = sum(p.values())
    return {k: v / s for k, v in p.items()}


def dest_category(dest: tuple) -> str | None:
    kind, sid = dest
    if kind == "door":
        return "unknown"
    if kind in ("spot", "clue"):
        return SPOTS[sid]["category"]
    return None                              # 모르는 쪽: find 마다 무작위


# ─────────────────────────────────────────────────────────────
# 한 번의 원정
# ─────────────────────────────────────────────────────────────
def run_trip(rng: random.Random, party: list[dict], length: str, dest: tuple, recent_cats: list[str],
             lingering: str | None = None, learning: bool = False, gear_actions: int = 0) -> dict:
    pair = len(party) == 2
    tank = LEN[length]["tank"]
    bmin = min(p["stats"]["breath"] for p in party)
    actions = sum(max(EXP["stats"]["breath"]["min_actions"], stoch_round(rng, tank * breath_mul(bmin)) + gear_actions)
                  for _ in party)
    eye = max(p["stats"]["eye"] for p in party)
    carry = sum(carry_of(p["stats"]["hand"]) for p in party)
    kind, sid = dest
    cat = dest_category(dest)
    probs = find_probs(eye)

    # 위험
    out = {"danger": None, "ok": None, "injured": None, "imprint": [], "late": 0, "newcomer": False,
           "discovered": False, "clue": False, "left": 0, "air": tank * len(party), "actions": actions}
    p_d = 0.0
    if not learning:
        p_d = LEN[length]["danger"]
        if kind == "door":
            p_d *= DEST["door"]["danger_mul"]
        elif kind == "unknown":
            p_d *= DEST["unknown"]["danger_mul"]
        else:
            p_d *= SPOTS[sid]["danger_mul"]
        if lingering:
            p_d += LINK["lingering_add"].get(lingering, LINK["lingering_add"]["_other"])
        p_d = max(0.0, p_d)
    lost_actions = 0
    haul_lost = 0.0
    if rng.random() < p_d:
        weights = dict(DANGER["default_kind_weights"])
        if kind in ("spot", "clue"):
            weights = dict(SPOTS[sid]["kinds"])
        forced = LINK["lingering_kind"].get(lingering or "")
        dk = forced if (forced and rng.random() < 0.6) else rng.choices(list(weights), weights=list(weights.values()))[0]
        stat = {"air": "breath", "beast": "nerve", "seam": "hand", "lost": "eye"}[dk]
        ok = rng.random() < check_p(max(p["stats"][stat] for p in party), pair)
        out["danger"], out["ok"] = dk, ok
        spec = DANGER["kinds"][dk]
        if dk == "beast":
            out["imprint"].append("beast")
        if not ok:
            f = spec["fail"]
            if "actions_lost_frac" in f:
                lost_actions = int(actions * f["actions_lost_frac"])
            if "actions_lost" in f:
                lost_actions = f["actions_lost"]
            haul_lost = f.get("haul_lost_frac", 0.0)
            if f.get("injury"):
                out["injured"] = min(party, key=lambda p: p["stats"]["hand"])["id"]
            out["late"] = f.get("late_minutes", 0)
            if dk == "air":
                out["imprint"].append("air")
    real = max(0, actions - lost_actions)
    out["actions"] = real

    mats: dict[str, float] = {}
    boxes: list[str] = []
    relics = 0
    for _ in range(real):
        r = rng.random()
        if r < probs["material"]:
            if cat and rng.random() < EXP["finds"]["material_bias"]["destination"]:
                m = CAT_MAT[cat]
            elif cat is None:
                m = CAT_MAT[rng.choice(CATS)]
            else:
                m = rng.choice(MAT8)
            mats[m] = mats.get(m, 0) + 1
        elif r < probs["material"] + probs["box"]:
            if cat and (not recent_cats or rng.random() < BOX["category_pick"]["destination"]):
                boxes.append(cat)
            elif recent_cats:
                boxes.append(rng.choice(recent_cats))
            else:
                boxes.append(rng.choice(CATS))
        elif r < probs["material"] + probs["box"] + probs["relic"]:
            relics += 1
    # 손: 들고 오는 양 (상자 > 유물 > 재료)
    slots = carry
    kept_boxes = []
    for b in boxes:
        if slots >= 2:
            kept_boxes.append(b)
            slots -= 2
        else:
            out["left"] += 1
    kept_relics = min(relics, slots)
    slots -= kept_relics
    out["left"] += relics - kept_relics
    kept_mats: dict[str, float] = {}
    for m, n in sorted(mats.items(), key=lambda kv: -kv[1]):
        take = min(n, slots)
        if take:
            kept_mats[m] = take
            slots -= take
        out["left"] += n - take
    if haul_lost:
        kept_mats = {m: n * (1 - haul_lost) for m, n in kept_mats.items()}
        kept_boxes = kept_boxes[: int(len(kept_boxes) * (1 - haul_lost))]
        kept_relics = int(kept_relics * (1 - haul_lost))
    out.update(mats=kept_mats, boxes=kept_boxes, relics=kept_relics)

    # 사람·단서·발견
    eye_d = max(0, eye - 5)
    if kind == "unknown":
        key = "unknown_" + length
        pc = NEWC["rescue"]["chance"].get(key, 0) + NEWC["rescue"]["per_eye_above_5"] * eye_d
        out["newcomer"] = rng.random() < pc
        st = DEST["unknown"]["clue_stumble"]
        out["clue"] = rng.random() < st.get(length, 0) + st["per_eye_above_5"] * eye_d
    elif kind in ("spot", "clue"):
        out["newcomer"] = rng.random() < NEWC["rescue"]["chance"]["spot"]
    if kind == "clue":
        dsc = EXP["stats"]["eye"]["discovery"]
        out["discover_p"] = max(dsc["min"], min(dsc["max"], dsc["base"] + dsc["per_point"] * (eye - 5)))
    return out


def value_of(t: dict, box_open_rate: float = 1.0) -> float:
    """재료 환산 가치. 재료 1 / 상자 4(열리는 비율 곱) / 유물 1.5."""
    return (sum(t["mats"].values()) + len(t["boxes"]) * BOX["value"]["units"] * box_open_rate
            + t["relics"] * 1.5)


# ─────────────────────────────────────────────────────────────
# X1·X2 — 한 번의 원정
# ─────────────────────────────────────────────────────────────
def P(role, **over):
    st = dict(zip(SK, STAT_BASE[role]))
    st.update(over)
    return {"id": role, "role": role, "stats": st}


def trip_table(n: int = 6000):
    rng = random.Random(11)
    recent = ["food", "drink", "electronics"]
    print("\n" + "=" * 110)
    print("표 X1. 누구를 보내나 — 조 구성 × 길이 (모르는 쪽, 위험 켬, 바깥에 생물 없음). 6000회 평균")
    print("=" * 110)
    parties = [
        ("정찰병 혼자 (손4 눈7 숨7 담5)", [P("scout")]),
        ("기술자 혼자 (손8 눈5 숨5 담4)", [P("engineer")]),
        ("학자 혼자 (손5 눈8 숨4 담4)", [P("scholar")]),
        ("농부 혼자 (손6 눈5 숨7 담4)", [P("farmer")]),
        ("정찰병+기술자", [P("scout"), P("engineer")]),
        ("정찰병+학자", [P("scout"), P("scholar")]),
        ("정찰병+아이 (숨4)", [P("scout"), P("kid")]),
    ]
    print(f"{'조':<30}{'길이':<8}{'공기':<6}{'행동':<7}{'주움':<7}{'두고옴':<8}{'상자':<7}{'가치':<7}"
          f"{'공기당':<8}{'위험넘김':<9}{'부상':<7}{'사람':<6}")
    for name, party in parties:
        for length in ("half", "long"):
            agg = {"act": 0, "got": 0, "left": 0, "box": 0, "val": 0, "dang": 0, "ok": 0, "inj": 0, "new": 0}
            for _ in range(n):
                t = run_trip(rng, party, length, ("unknown", None), recent)
                agg["act"] += t["actions"]
                agg["got"] += sum(t["mats"].values()) + len(t["boxes"]) + t["relics"]
                agg["left"] += t["left"]
                agg["box"] += len(t["boxes"])
                agg["val"] += value_of(t, 0.85)
                agg["dang"] += t["danger"] is not None
                agg["ok"] += bool(t["ok"])
                agg["inj"] += t["injured"] is not None
                agg["new"] += t["newcomer"]
            air = LEN[length]["tank"] * len(party)
            okr = agg["ok"] / agg["dang"] if agg["dang"] else 0
            print(f"{name:<30}{LEN[length]['ko']:<8}{air:<6}{agg['act']/n:<7.1f}{agg['got']/n:<7.1f}"
                  f"{agg['left']/n:<8.2f}{agg['box']/n:<7.2f}{agg['val']/n:<7.1f}{agg['val']/n/air:<8.2f}"
                  f"{okr:<9.0%}{agg['inj']/n:<7.1%}{agg['new']/n:<6.0%}")
        print("-" * 110)
    print("  읽는 법: '공기당'이 조 사이에서 크게 벌어지지 않아야 한다(B3). 둘이 가면 공기당은 비슷하고")
    print("  두고 오는 것·위험·부상이 줄어든다(질을 산다). 숨 짧은 짝(아이)은 둘 다를 끌어내린다.")
    print("  상자 가치는 '85%가 열쇠로 열리고 나머지는 7일 뒤 억지로'를 가정한 4 × 0.85 로 셌다.")

    print("\n" + "=" * 110)
    print("표 X2. 어디로 가나 — 목적지 × 길이 (정찰병 혼자, 위험 켬). 6000회 평균")
    print("=" * 110)
    print(f"{'목적지':<26}{'길이':<8}{'공기':<6}{'재료':<7}{'건설재료':<9}{'상자':<7}{'유물':<7}{'덤':<6}"
          f"{'가치':<7}{'공기당':<8}{'위험':<7}{'사람':<7}{'단서/발견':<10}")
    party = [P("scout")]
    dests = [("문 앞 바닥", ("door", None), ("short", "half")),
             ("등불 떼(아는 곳)", ("spot", "spot_jelly_bloom"), ("half",)),
             ("열수구 정원(아는 곳)", ("spot", "spot_vent_garden"), ("half",)),
             ("위를 보는 숲(아는 곳)", ("spot", "spot_kelp_ceiling"), ("long",)),
             ("열수구 정원(단서)", ("clue", "spot_vent_garden"), ("half",)),
             ("모르는 쪽", ("unknown", None), ("half", "long"))]
    bonus = {"spot_jelly_bloom": 0, "spot_vent_garden": 0, "spot_kelp_ceiling": 4}   # spots_deep gain 중 재료(사기·전력 제외)
    CD = DEST["spot"]["visit_bonus_cooldown_days"]                                   # 3일에 한 번 → 평균 1/3
    for name, dest, lens in dests:
        for length in lens:
            agg = {k: 0.0 for k in ("m", "b", "box", "rel", "val", "d", "new", "clue")}
            for _ in range(n):
                t = run_trip(rng, party, length, dest, recent)
                agg["m"] += sum(t["mats"].values())
                agg["b"] += sum(v for k, v in t["mats"].items() if k in BUILD)
                agg["box"] += len(t["boxes"])
                agg["rel"] += t["relics"]
                vb = bonus.get(dest[1], 0) / CD if dest[0] == "spot" else 0
                agg["val"] += value_of(t, 0.85) + vb
                agg["d"] += t["danger"] is not None
                agg["new"] += t["newcomer"]
                agg["clue"] += t.get("discover_p", 0) if dest[0] == "clue" else t["clue"]
            air = LEN[length]["tank"]
            vb = bonus.get(dest[1], 0) / CD if dest[0] == "spot" else 0
            print(f"{name:<26}{LEN[length]['ko']:<8}{air:<6}{agg['m']/n:<7.1f}{agg['b']/n:<9.1f}{agg['box']/n:<7.2f}"
                  f"{agg['rel']/n:<7.2f}{vb:<6.1f}{agg['val']/n:<7.1f}{agg['val']/n/air:<8.2f}{agg['d']/n:<7.0%}"
                  f"{agg['new']/n:<7.0%}{agg['clue']/n:<10.0%}")
    print("  '덤' = 스팟 방문 덤 중 재료(spots_deep resource.gain, 사기·전력 제외)를 3일 쿨다운으로 나눈 평균. '단서/발견' = 모르는 쪽은")
    print("  스캔 없이 단서를 주울 확률, 단서 원정은 그 자리에서 스팟을 찾아낼 확률(눈 7 기준).")
    print("  목표: 공기당 가치가 목적지·길이 사이 ±25% 안 — 차이는 '얼마나'가 아니라 '무엇을'에 있어야 한다(B3).")


# ─────────────────────────────────────────────────────────────
# X3~ — 하루 단위 진행 (경제 + 원정 + 문간)
# ─────────────────────────────────────────────────────────────
class KeyedScan(E.ScanModel):
    """바코드마다 갈래가 정해져 있는 스캔 모델(상자 열쇠 판정에 필요). 산출 규칙은 원본과 같다."""

    def __init__(self, rng, pool_size):
        super().__init__(rng, pool_size)
        self.bc_cat = [rng.choices(self.cats, weights=self.weights, k=1)[0] for _ in range(pool_size)]

    def one_day(self, n_scans: int):
        gained: dict[str, float] = {}
        cats_today: set[str] = set()
        picked_today: list[int] = []
        scans = []
        for i in range(n_scans):
            bc = self.rng.randrange(self.pool_size)
            times = self.pool[bc]
            m_re = self.decay[times] if times < len(self.decay) else 0.0
            picked_today.append(bc)
            self.pool[bc] = times + 1
            cat = self.bc_cat[bc]
            scans.append((bc, cat, m_re))
            if m_re <= 0:
                continue
            cats_today.add(cat)
            rar = self.rng.choices(self.rar_names, weights=self.rar_p, k=1)[0]
            mul = self.rar_mul[rar] * m_re * self.fatigue(i)
            for k, v in self.base[cat].items():
                gained[k] = gained.get(k, 0.0) + v * mul
            bonus = self.rng.choice(["food", "water", "med", "power", "parts", "morale", "cloth", "trade", "knowledge"])
            gained[bonus] = gained.get(bonus, 0.0) + mul
        div = min(self.div_cap, 1 + 0.08 * (len(cats_today) - 1)) if cats_today else 1.0
        for k in gained:
            gained[k] *= div
        self.day_seen.append(picked_today)
        if len(self.day_seen) > 7:
            for bc in self.day_seen.pop(0):
                self.pool[bc] = max(0, self.pool[bc] - 1)
        return gained, scans


# 원정이 있으면 에어락을 일찍 짓는다(긴 원정·둘이 가기의 전제). 순서 외 정책은 sim_economy 그대로
BUILD_ORDER_EXP = ["quarters", "storage", "well", "greenhouse", "airlock", "generator",
                   "workshop", "infirmary", "hall", "decoder", "lounge", "bath"]


class ArkX(E.Ark):
    def __init__(self, rng):
        super().__init__(rng)
        self.n_res = 3

    def residents(self, day: int) -> int:
        return self.n_res


PROFILES = [
    # 이름, 스캔/일, 바코드 풀, 접속 시각(시)
    ("열심 20회/일", 20, 160, (8, 13, 21)),
    ("보통 8회/일", 8, 90, (8, 21)),
    ("띄엄띄엄 3회/일", 3, 55, (21,)),
]


def threat_today(rng: random.Random, grade: int) -> str | None:
    fq = THREAT["frequency"]["by_grade"][str(grade)]
    if rng.random() >= fq["raid_chance"]:
        return None
    w = {k: v for k, v in fq["weights"].items() if v > 0}
    return rng.choices(list(w), weights=list(w.values()))[0]


def run_day_sim(profile, days: int, seed: int, expedition: bool = True, raid_policy: str = "water_first",
                dest_policy: str = "mixed", skip_rate: float = 0.0) -> dict:
    name, scans_per_day, pool, sessions = profile
    rng = random.Random(seed)
    ark = ArkX(rng)
    scan = KeyedScan(random.Random(seed + 1), pool)
    saved_order = list(E.BUILD_ORDER)
    if expedition:
        E.BUILD_ORDER[:] = BUILD_ORDER_EXP
    roster = [make_person(rng, r, i) for i, r in enumerate(("cook", "engineer", "scout"))]
    next_id = 3
    guests: list[dict] = []
    boxes: list[dict] = []          # {"cat", "day"}
    cat_counts: dict[str, int] = {}
    recent_cat_days: list[set] = []
    known: set = set()
    clues: set = set()
    clue_fail: dict = {}
    air = AIR["daily_supply_base"]
    out_party = None                # {"t_back", "trip", "party", "dest", "length"}
    trips_done = 0
    first_unknown_done = False
    stats = {"exp_direct_b": 0.0, "box_b": 0.0, "scan_b": 0.0, "room_b": 0.0, "gift_b": 0.0,
             "exp_direct_all": 0.0, "box_all": 0.0,
             "trips": 0, "air_used": 0, "boxes_found": 0, "boxes_opened": 0, "boxes_opened_decayed": 0,
             "boxes_pried": 0, "relics": 0, "injuries": 0, "imprints": 0, "imprints_30": 0, "late": 0,
             "dangers": 0, "danger_fail": 0, "newcomers_knock": 0, "newcomers_rescue": 0, "rescue_turned": 0,
             "discoveries": 0, "out_at_raid": 0, "raid_days": 0, "lingering_trips": 0, "left": 0,
             "recalled": 0, "fork_lit": 0, "fork_n": 0, "per_day": []}
    skipped = 0

    def beds():
        return int(NEWC["beds_by_quarters_level"][str(ark.rooms.get("quarters", 0))])

    def suits():
        return EXP["entrance"]["shared_suits"] + (1 if ark.rooms.get("airlock", 0) >= 1 else 0)

    def air_supply():
        gl = ark.rooms.get("greenhouse", 0)
        base = AIR["daily_supply_base"] + (AIR["greenhouse_bonus"].get(str(gl), 0) if gl >= 2 else 0)
        if ark.rooms.get("airlock", 0) >= 2:
            base *= AIR["airlock_mul"]["2"]
        return base

    def recent_cats():
        s = set()
        for d in recent_cat_days[-7:]:
            s |= d
        return sorted(s)

    def add_mat(k, v, bucket_b, bucket_all):
        if k == "morale":
            return
        ark.res[k] = ark.res.get(k, 0) + v
        stats[bucket_all] = stats.get(bucket_all, 0) + v
        if k in BUILD:
            stats[bucket_b] += v

    def grant_imprint(p, crisis, day):
        if crisis in p["crises"] or p["imprints"] >= 3:
            return
        p["crises"].add(crisis)
        p["imprints"] += 1
        stats["imprints"] += 1
        if day <= 30:
            stats["imprints_30"] += 1

    def settle(now_h, day):
        nonlocal out_party, trips_done
        if not out_party or out_party["t_back"] > now_h:
            return
        t = out_party["trip"]
        for k, v in t["mats"].items():
            add_mat(k, v, "exp_direct_b", "exp_direct_all")
        for c in t["boxes"]:
            boxes.append({"cat": c, "day": day})
        stats["boxes_found"] += len(t["boxes"])
        stats["relics"] += t["relics"]
        stats["left"] += t["left"]
        party = out_party["party"]
        for p in party:
            p["trips"] += 1
            p["trip_pts"] += EXP["stats"]["growth"]["trip_points"][out_party["length"]]
            if p["trip_pts"] >= 8 and p["stats"]["breath"] < min(10, p["born_breath"] + 2):
                p["trip_pts"] -= 8
                p["stats"]["breath"] += 1
        if t["danger"]:
            stats["dangers"] += 1
            stats["danger_fail"] += not t["ok"]
        if t["injured"] is not None:
            stats["injuries"] += 1
            for p in party:
                if p["id"] == t["injured"]:
                    p["injured_until"] = now_h + 16         # 틱 두 번 남짓 — 의무실이 있으면 더 빨리
        stats["late"] += bool(t["late"])
        for p in party:
            if "air" in t["imprint"]:
                grant_imprint(p, "air_out", day)
            if "beast" in t["imprint"]:
                grant_imprint(p, "beast", day)
        kind, sid = out_party["dest"]
        if kind == "clue":
            p_ok = t["discover_p"] + clue_fail.get(sid, 0)
            if rng.random() < p_ok:
                known.add(sid)
                clues.discard(sid)
                stats["discoveries"] += 1
                for p in party:
                    grant_imprint(p, "spot_found", day)
            else:
                clue_fail[sid] = clue_fail.get(sid, 0) + DEST["clue"]["fail_memory"]
        if kind == "spot" and sid == "spot_whale_fall":
            for p in party:
                grant_imprint(p, "descent", day)
        if kind == "spot" and sid == "spot_kelp_ceiling" and day - last_visit.get(sid, -99) >= DEST["spot"]["visit_bonus_cooldown_days"]:
            last_visit[sid] = day
            add_mat("food", 2, "exp_direct_b", "exp_direct_all")
            add_mat("cloth", 2, "exp_direct_b", "exp_direct_all")
        if t["clue"]:
            locked = [s for s in SPOTS if s not in known and s not in clues]
            if locked:
                clues.add(rng.choice(locked))
        if t["newcomer"] or (kind == "unknown" and not first_unknown_done_flag[0]):
            if kind == "unknown":
                first_unknown_done_flag[0] = True
            if len(guests) < EXP["entrance"]["guest_spots"]:
                guests.append({"day": day, "src": "rescue"})
                stats["newcomers_rescue"] += 1
            else:
                stats["rescue_turned"] += 1
        trips_done += 1
        out_party = None

    first_unknown_done_flag = [False]
    last_visit: dict = {}

    def pick_dest(length, eye_best):
        if dest_policy == "known_only":
            pool_k = [s for s in known if LEN_ORDER[SPOTS[s]["min_length"]] <= LEN_ORDER[length]
                      and SPOTS[s]["min_base_depth_m"] <= ark.depth_m]
            c = [s for s in clues if LEN_ORDER[SPOTS[s]["min_length"]] <= LEN_ORDER[length]
                 and SPOTS[s]["min_base_depth_m"] <= ark.depth_m]
            if c:
                return ("clue", c[0])
            if pool_k:
                return ("spot", min(pool_k, key=lambda s: ark.res.get(CAT_MAT[SPOTS[s]["category"]], 0)))
            return ("door", None) if length != "long" else ("unknown", None)
        if dest_policy == "unknown_only":
            return ("unknown", None) if length != "short" else ("door", None)
        # mixed: 단서가 있으면 따라간다 → 아니면 40% 모르는 쪽 → 아는 곳 → 문 앞
        c = [s for s in clues if LEN_ORDER[SPOTS[s]["min_length"]] <= LEN_ORDER[length]
             and SPOTS[s]["min_base_depth_m"] <= ark.depth_m]
        if c:
            return ("clue", c[0])
        if length != "short" and rng.random() < 0.4:
            return ("unknown", None)
        pool_k = [s for s in known if LEN_ORDER[SPOTS[s]["min_length"]] <= LEN_ORDER[length]
                  and SPOTS[s]["min_base_depth_m"] <= ark.depth_m]
        if pool_k:
            return ("spot", min(pool_k, key=lambda s: ark.res.get(CAT_MAT[SPOTS[s]["category"]], 0)))
        return ("door", None) if length != "long" else ("unknown", None)

    for day in range(1, days + 1):
        played = rng.random() >= skip_rate or day == 1
        day_h0 = (day - 1) * 24
        creature = threat_today(rng, ark.grade) if day >= THREAT["frequency"].get("_first_day_n", 2) else None
        raid_pending = creature is not None and creature != "octopus"
        if raid_pending:
            stats["raid_days"] += 1

        # 문 두드림 (아침)
        if len(guests) < EXP["entrance"]["guest_spots"]:
            if day == NEWC["knock"]["first_knock_day"] or (day > NEWC["knock"]["first_knock_day"]
                                                           and rng.random() < NEWC["knock"]["daily_chance"]):
                guests.append({"day": day, "src": "knock"})
                stats["newcomers_knock"] += 1

        # 스캔 (첫 접속 때 몰아서) + 상자 열기
        if played:
            g, scans = scan.one_day(scans_per_day)
            for k, v in g.items():
                if k == "morale":
                    ark.morale = min(10.0, ark.morale + v * 0.1)
                elif k in ark.res:
                    add_mat(k, v, "scan_b", "_scan_all")
            used_bc = set()
            for bc, cat, m_re in scans:
                cat_counts[cat] = cat_counts.get(cat, 0) + (1 if m_re > 0 else 0)
                if bc in used_bc:
                    continue
                hit = next((b for b in boxes if b["cat"] == cat), None)
                if expedition and hit:
                    boxes.remove(hit)
                    used_bc.add(bc)
                    stats["boxes_opened"] += 1
                    stats["boxes_opened_decayed"] += m_re < 1.0
                    add_mat(CAT_MAT[cat], BOX["value"]["units"], "box_b", "box_all")
            recent_cat_days.append({c for _, c, m in scans})
            # 단서 (스캔 누적)
            for sid, (c, need) in CLUE_RULES.items():
                if sid not in known and cat_counts.get(c, 0) >= need:
                    clues.add(sid)
            # 손님 들이기 (잠자리가 있으면 언제나 들인다 — 시뮬레이션 정책)
            while guests and ark.n_res < beds():
                guests.pop(0)
                role_have = {p["role"] for p in roster}
                pool_r = [r for r in ROLES if r not in role_have] or ROLES
                roster.append(make_person(rng, rng.choice(pool_r), next_id))
                next_id += 1
                ark.n_res += 1
        else:
            recent_cat_days.append(set())

        # 억지로 열기 (7일)
        if expedition:
            for b in [b for b in boxes if day - b["day"] >= BOX["pry"]["after_days"]]:
                boxes.remove(b)
                stats["boxes_pried"] += 1
                add_mat(CAT_MAT[b["cat"]], BOX["value"]["units"] * BOX["pry"]["value_mul"], "box_b", "box_all")

        # 원정 — 접속마다
        if expedition and played:
            for si, h in enumerate(sessions):
                now = day_h0 + h
                # 공기 채움(마지막 이후 시간만큼)
                air = min(air_supply(), air + air_supply() / 24 * (h - (sessions[si - 1] if si else (sessions[-1] - 24))))
                settle(now, day)
                # 습격 정책
                if raid_pending and raid_policy == "water_first":
                    if out_party:
                        stats["out_at_raid"] += 1          # 이미 나가 있는 동안 받았다(밤 넘기기 귀환 전)
                    raid_pending = False
                if out_party:
                    continue
                gap = (sessions[si + 1] - h) if si + 1 < len(sessions) else (sessions[0] + 24 - h)
                can_long = ark.rooms.get("airlock", 0) >= 1
                order = ["long", "half", "short"] if can_long else ["half", "short"]
                length = next((L for L in order if LEN[L]["minutes"] / 60 <= gap and air >= LEN[L]["tank"]), None)
                if not length:
                    length = next((L for L in reversed(order) if air >= LEN[L]["tank"]), None)
                if not length:
                    continue
                avail = [p for p in roster if p["injured_until"] <= now]
                if not avail:
                    continue
                lead = max(avail, key=lambda p: p["stats"]["eye"] + p["stats"]["breath"])
                party = [lead]
                if suits() >= 2 and length != "short" and air >= 2 * LEN[length]["tank"] and len(avail) > 1:
                    mate = max((p for p in avail if p is not lead),
                               key=lambda p: p["stats"]["hand"] + p["stats"]["breath"])
                    party.append(mate)
                dest = pick_dest(length, lead["stats"]["eye"])
                linger = None
                if raid_pending and raid_policy == "road_first":
                    linger = creature
                    stats["lingering_trips"] += 1
                fk = EXP["scene"]["fork"]
                low = min(ark.res.get(k, 0) for k in fk["auto_low_materials"])
                stats["fork_lit"] += (len(boxes) >= fk["auto_box_backlog"] or low < fk["auto_low_stock"])
                stats["fork_n"] += 1
                trip = run_trip(rng, party, length, dest, recent_cats(), lingering=linger,
                                learning=trips_done < DANGER["learning_trips_without_danger"])
                if raid_pending and raid_policy == "road_first" and creature == "claws":
                    stats["recalled"] += 1             # 손톱 무리 접촉 때 불러들인다 → 절반만
                    trip["mats"] = {k: v * 0.5 for k, v in trip["mats"].items()}
                    trip["boxes"] = trip["boxes"][: len(trip["boxes"]) // 2]
                air -= trip["air"]
                stats["air_used"] += trip["air"]
                stats["trips"] += 1
                t_back = now + LEN[length]["minutes"] / 60 + trip["late"] / 60
                out_party = {"t_back": t_back, "trip": trip, "party": party, "dest": dest, "length": length}
            if raid_pending:
                # 길 먼저: 마지막 접속에서 받는다. 그때 원정대가 밖에 있으면 '빠진 채로' 받는다
                if out_party:
                    stats["out_at_raid"] += 1
                raid_pending = False
        # 하루 끝 정산(밤 넘기기는 다음 날 아침 접속에서)
        if expedition and out_party and out_party["t_back"] <= day_h0 + 24 and not played:
            settle(day_h0 + 24, day)

        # 방 생산·소비·문어 (sim_economy 와 같은 순서)
        p = ark.produce(day)
        for k, v in p.items():
            add_mat(k, v, "room_b", "_room_all")
        for k, v in ark.consume(day).items():
            if ark.res[k] < v:
                ark.morale = max(0.0, ark.morale + ECON["consumption"]["starvation"]["morale_per_day"])
            ark.res[k] = max(0.0, ark.res[k] - v)
        if played:
            n = 1 + min(2, skipped)
            skipped = 0
            for _ in range(n):
                k = min(E.BUILD_KEYS, key=lambda x: ark.res.get(x, 0)) if rng.random() < 0.6 else rng.choice(E.BUILD_KEYS)
                add_mat(k, rng.choice([1, 2]), "gift_b", "_gift_all")
        else:
            skipped += 1
        ark.morale = max(0.0, min(10.0, ark.morale + ECON["consumption"]["morale"]["drift_per_day"]
                                   + ark.morale_from_rooms * 0.5))
        ark.clamp()
        if played:
            ark.spend(day)
        stats["per_day"].append({"day": day, "rooms": len(ark.rooms), "res": ark.n_res, "guests": len(guests),
                                 "boxes": len(boxes), "known": len(known), "lv2": ark.lv_count(2),
                                 "lv3": ark.lv_count(3), "depth": ark.depth_m, "imprints": stats["imprints"],
                                 "airlock": ark.rooms.get("airlock", 0), "parts": round(ark.res["parts"], 1)})
    E.BUILD_ORDER[:] = saved_order
    stats["roster"] = roster
    return stats


LEN_ORDER = {"short": 0, "half": 1, "long": 2}
SEEDS = list(range(20))


def avg_runs(profile, days, **kw):
    runs = [run_day_sim(profile, days, seed=s, **kw) for s in SEEDS]
    return runs


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def progress_tables(days: int):
    print("\n" + "=" * 110)
    print(f"표 X3. {days}일 진행 — 원정 켬, 습격 정책 '물 먼저', 목적지 '섞어서'. 씨앗 20개 평균")
    print("=" * 110)
    marks = [d for d in (1, 3, 7, 14, 21, 30, 45, 60) if d <= days]
    print(f"{'유형':<18}{'일':<5}{'방':<6}{'Lv2':<6}{'Lv3':<6}{'주민':<6}{'손님':<6}{'에어락':<7}{'아는곳':<7}"
          f"{'상자대기':<9}{'각인(원정)':<11}{'깊이':<6}")
    allruns = {}
    for prof in PROFILES:
        runs = avg_runs(prof, days)
        allruns[prof[0]] = runs
        for d in marks:
            rows = [r["per_day"][d - 1] for r in runs]
            print(f"{prof[0]:<18}{d:<5}{mean(x['rooms'] for x in rows):<6.1f}{mean(x['lv2'] for x in rows):<6.1f}"
                  f"{mean(x['lv3'] for x in rows):<6.1f}{mean(x['res'] for x in rows):<6.1f}"
                  f"{mean(x['guests'] for x in rows):<6.1f}{mean(x['airlock'] >= 1 for x in rows):<7.0%}"
                  f"{mean(x['known'] for x in rows):<7.1f}{mean(x['boxes'] for x in rows):<9.1f}"
                  f"{mean(x['imprints'] for x in rows):<11.1f}{mean(x['depth'] for x in rows):<6.0f}")
        print("-" * 110)
    return allruns


def curve_table(days: int, allruns: dict):
    print("\n" + "=" * 110)
    print("표 X4. 목표 곡선 — 주민(새 규칙)과 방(원정 켬/끔). 보통 플레이어 기준. 씨앗 20개 평균")
    print("=" * 110)
    off = {p[0]: avg_runs(p, days, expedition=False) for p in PROFILES}
    tgt = EXP["targets"]["residents_curve"]
    print(f"{'일':<5}{'목표 주민':<10}{'열심':<8}{'보통':<8}{'띄엄':<8}{'판정':<8}"
          f"{'목표 방':<9}{'보통(켬)':<10}{'보통(끔)':<10}{'열심(켬)':<10}{'띄엄(켬)':<10}{'판정':<8}")
    for cp in ECON["target_curve"]["checkpoints"]:
        d = cp["day"]
        if d > days:
            continue
        rr = {k: mean(r["per_day"][d - 1]["res"] for r in v) for k, v in allruns.items()}
        rm = {k: mean(r["per_day"][d - 1]["rooms"] for r in v) for k, v in allruns.items()}
        rm_off = mean(r["per_day"][d - 1]["rooms"] for r in off["보통 8회/일"])
        tr = int(tgt.get(str(d), cp["residents"]))
        n = rr["보통 8회/일"]
        j1 = "맞음" if abs(n - tr) <= 1 else ("빠름" if n > tr else "느림")
        nm = rm["보통 8회/일"]
        j2 = "맞음" if abs(nm - cp["rooms"]) <= 1 else ("빠름" if nm > cp["rooms"] else "느림")
        print(f"{d:<5}{tr:<10}{rr['열심 20회/일']:<8.1f}{n:<8.1f}{rr['띄엄띄엄 3회/일']:<8.1f}{j1:<8}"
              f"{cp['rooms']:<9}{nm:<10.1f}{rm_off:<10.1f}{rm['열심 20회/일']:<10.1f}{rm['띄엄띄엄 3회/일']:<10.1f}{j2:<8}")
    print("  주민 '끔' 칸이 없는 이유: 원정을 끄면 1막에는 사람이 늘어나는 길이 두드림 하나뿐이다(지금 서버는 0).")
    return off


def income_table(days: int, allruns: dict, off: dict):
    print("\n" + "=" * 110)
    print(f"표 X5. 수입 출처 (건설 재료, {days}일 합) — 스캔이 주 수입으로 남는가")
    print("=" * 110)
    print(f"{'유형':<18}{'스캔':<8}{'상자(열쇠=스캔)':<17}{'원정 직접':<11}{'방 생산':<9}{'문어':<7}{'총량':<8}"
          f"{'끔일때 총량':<12}{'판정':<10}")
    for name, runs in allruns.items():
        def share(key):
            return mean(r[key] / max(1e-9, r["scan_b"] + r["box_b"] + r["exp_direct_b"] + r["room_b"] + r["gift_b"]) for r in runs)
        tot = mean(r["scan_b"] + r["box_b"] + r["exp_direct_b"] + r["room_b"] + r["gift_b"] for r in runs)
        tot_off = mean(r["scan_b"] + r["room_b"] + r["gift_b"] for r in off[name])
        s = share("scan_b")
        ok = "통과" if s >= EXP["targets"]["scan_share_build_min"] and share("exp_direct_b") <= EXP["targets"]["expedition_direct_share_build_max"] else "미달"
        print(f"{name:<18}{s:<8.0%}{share('box_b'):<17.0%}{share('exp_direct_b'):<11.0%}{share('room_b'):<9.0%}"
              f"{share('gift_b'):<7.0%}{tot:<8.0f}{tot_off:<12.0f}{ok:<10}")
    print(f"  기준: 스캔 ≥ {EXP['targets']['scan_share_build_min']:.0%}, 원정 직접 ≤ {EXP['targets']['expedition_direct_share_build_max']:.0%}.")
    print("  상자는 원정이 가져오지만 **스캔으로만 열린다**(7일 뒤 억지로 열기 제외). 그래서 따로 셌다.")


def rescan_table(days: int, allruns: dict):
    print("\n" + "=" * 110)
    print(f"표 X6. 재스캔이 열쇠가 되는가 (PM 요구 b) — {days}일 합")
    print("=" * 110)
    print(f"{'유형':<18}{'상자 발견':<10}{'열쇠로 엶':<10}{'그중 재스캔':<12}{'억지로 엶':<10}{'열쇠 비율':<10}{'재스캔 1회당 덤':<14}")
    for name, runs in allruns.items():
        f = mean(r["boxes_found"] for r in runs)
        o = mean(r["boxes_opened"] for r in runs)
        dcy = mean(r["boxes_opened_decayed"] for r in runs)
        pr = mean(r["boxes_pried"] for r in runs)
        print(f"{name:<18}{f:<10.1f}{o:<10.1f}{(dcy / o if o else 0):<12.0%}{pr:<10.1f}{(o / max(1e-9, o + pr)):<10.0%}"
              f"{'4.0 (원래 0~2)':<14}")
    print("  '그중 재스캔' = 감쇠가 걸린(이미 찍어 본) 바코드로 연 비율. 목표 30% 이상 — 그만큼 '헌 물건'이 쓸모를 되찾았다.")
    print("  '열쇠 비율'이 낮으면 상자 갈래가 플레이어의 바코드 현실과 안 맞는 것이다(억지로 열기가 바닥을 받친다).")


def raid_tables(days: int):
    print("\n" + "=" * 110)
    print("표 X7-1. 빠진 사람의 값 — 맞는 사람이 원정을 나가 있으면 (관문 했을 때, severity 가중 평균)")
    print("=" * 110)
    print(f"{'등급':<6}{'배치 / 빠진 사람':<34}{'막음(다 있음)':<15}{'막음(빠짐)':<12}{'금(빠짐)':<10}{'상실(빠짐)':<11}{'차이':<8}")
    cases = (("맞는 사람 2 + 나머지", "하나 빠짐", lambda p: p[1:]),
             ("맞는 사람 2 + 나머지", "둘 다 빠짐", lambda p: p[2:]),
             ("총력", "하나 빠짐", lambda p: p[1:]))
    for grade in (1, 2, 3, 4, 5):
        for arch_name, ko, cut in cases:
            tot = {"full": {}, "out": {}}
            w_all = 0.0
            for c in E.creatures_at(grade):
                for sev in (0, 1, 2):
                    w = THREAT["severity"]["weights_by_grade"][str(grade)][sev]
                    if not w:
                        continue
                    need = E.need_of(c, grade, sev)
                    arch = E.archetypes(c, grade)[arch_name]
                    for key, people in (("full", arch["people"]), ("out", cut(arch["people"]))):
                        a = dict(arch, people=people)
                        sc = E.score_of(c, a["people"], a["lv"], a["tools"], a["imp"])
                        ok = E.gate_ok_for(c, a, sev, True)
                        v = E.verdict(sc, need, ok, grade, len(a["people"]))
                        tot[key][v] = tot[key].get(v, 0) + w
                    w_all += w
            f = tot["full"].get("held", 0) / w_all
            o = tot["out"].get("held", 0) / w_all
            print(f"{grade:<6}{arch_name + ' / ' + ko:<34}{f:<15.0%}{o:<12.0%}{tot['out'].get('scarred', 0) / w_all:<10.0%}"
                  f"{tot['out'].get('breached', 0) / w_all:<11.0%}{(o - f) * 100:+.0f}%p")
        print("-" * 100)
    print("  밖에 나간 사람은 지키지 못한다. 정원이 찬 방(총력)은 한 사람 빠져도 버티지만, 보통 배치에서")
    print("  맞는 사람이 빠지면 '막음'이 줄어 '금'으로 간다. 방 상실은 등급 1·2 보호 덕에 낮게 머문다.")

    print("\n" + "=" * 110)
    print(f"표 X7-2. 물 먼저 / 길 먼저 — 보통 플레이어 {days}일, 씨앗 20개 평균")
    print("=" * 110)
    print(f"{'정책':<34}{'원정':<7}{'생물 지나간 원정':<16}{'위험 만남':<10}{'못 넘김':<9}{'부상':<7}{'불러들임':<9}"
          f"{'빠진 채 받은 습격':<17}{'건설재료(원정+상자)':<18}")
    prof = PROFILES[1]
    for pol, ko in (("water_first", "물 먼저 (먼저 받고 내보낸다)"), ("road_first", "길 먼저 (내보내고 저녁에 받는다)")):
        runs = avg_runs(prof, days, raid_policy=pol)
        print(f"{ko:<34}{mean(r['trips'] for r in runs):<7.1f}{mean(r['lingering_trips'] for r in runs):<16.1f}"
              f"{mean(r['dangers'] for r in runs):<10.1f}{mean(r['danger_fail'] for r in runs):<9.1f}"
              f"{mean(r['injuries'] for r in runs):<7.1f}{mean(r['recalled'] for r in runs):<9.1f}"
              f"{mean(r['out_at_raid'] for r in runs):<17.1f}{mean(r['exp_direct_b'] + r['box_b'] for r in runs):<18.0f}")
    print("  '물 먼저'는 원정이 안전하지만 집에 있는 사람으로만 받는다. '길 먼저'는 원정을 위험한 물로 보내는 대신")
    print("  준비(도구 제작·사람 귀환)를 기다렸다가 받을 수 있다. 어느 쪽도 전부를 이기지 않는다(B3).")


def skip_table(days: int):
    print("\n" + "=" * 110)
    print(f"표 X8. 결석률 — 보통 플레이어 {days}일 (원정 켬). 씨앗 20개 평균")
    print("=" * 110)
    print(f"{'결석률':<9}{'방':<7}{'주민':<7}{'손님':<7}{'원정':<7}{'상자 억지로':<12}{'아는 곳':<9}")
    for rate in (0.0, 0.3, 0.5):
        runs = avg_runs(PROFILES[1], days, skip_rate=rate)
        last = [r["per_day"][days - 1] for r in runs]
        print(f"{rate:<9.0%}{mean(x['rooms'] for x in last):<7.1f}{mean(x['res'] for x in last):<7.1f}"
              f"{mean(x['guests'] for x in last):<7.1f}{mean(r['trips'] for r in runs):<7.1f}"
              f"{mean(r['boxes_pried'] for r in runs):<12.1f}{mean(x['known'] for x in last):<9.1f}")
    print("  안 켠 날에는 원정을 보내지 않는다. 손님은 떠나지 않고 기다리며, 상자는 7일 뒤 절반으로라도 열린다.")


def cost_table(days: int, allruns: dict):
    print("\n" + "=" * 110)
    print(f"표 X9. 대가의 크기 ({days}일 합) — 처벌이 아니라 이야기인가")
    print("=" * 110)
    weeks = days / 7
    print(f"{'유형':<18}{'원정':<7}{'공기/일':<9}{'위험 만남':<10}{'못 넘김':<9}{'부상':<7}{'부상/주':<9}{'늦은 귀환':<10}"
          f"{'두고 온 것':<11}{'각인(원정)':<11}{'각인/주(30일)':<14}{'사람(두드림/구조)':<16}")
    for name, runs in allruns.items():
        print(f"{name:<18}{mean(r['trips'] for r in runs):<7.1f}{mean(r['air_used'] for r in runs) / days:<9.1f}"
              f"{mean(r['dangers'] for r in runs):<10.1f}{mean(r['danger_fail'] for r in runs):<9.1f}"
              f"{mean(r['injuries'] for r in runs):<7.1f}{mean(r['injuries'] for r in runs) / weeks:<9.2f}"
              f"{mean(r['late'] for r in runs):<10.1f}{mean(r['left'] for r in runs):<11.1f}"
              f"{mean(r['imprints'] for r in runs):<11.1f}{mean(r['imprints_30'] for r in runs) / (min(days, 30) / 7):<14.2f}"
              f"{mean(r['newcomers_knock'] for r in runs):.1f}/{mean(r['newcomers_rescue'] for r in runs):.1f}")
    print("  죽음 0, 돌아오지 못함 0, 장비 소멸 0 — 규칙상 0 이라 칸이 없다.")
    print("  X10 갈림길 자동 규칙(expedition.json scene.fork.auto)이 불빛을 고른 비율: " + " · ".join(
        f"{name} {mean(r['fork_lit'] / max(1, r['fork_n']) for r in runs):.0%}" for name, runs in allruns.items()))
    print(f"  기준: 부상 ≤ 1.0/주, 원정 각인 ≤ 1.0/주(첫 30일).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=0)
    ap.add_argument("--trip", action="store_true")
    a = ap.parse_args()
    print("잔해 방주 — 원정·문간 시뮬레이션")
    print(f"입력: data/balance/expedition.json ({EXP['_version']}) + economy/threats/defense")
    trip_table()
    if a.trip:
        return
    for d in ([a.days] if a.days else [30, 60]):
        allruns = progress_tables(d)
        off = curve_table(d, allruns)
        income_table(d, allruns, off)
        rescan_table(d, allruns)
        cost_table(d, allruns)
        if d == (a.days or 30):
            raid_tables(d)
            skip_table(d)


if __name__ == "__main__":
    main()
