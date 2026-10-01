"""잔해 방주 — 경제·방어 시뮬레이터 (기획·밸런스 소유).

돌려 보지 않은 밸런스는 없는 것이다(B2). 이 스크립트가 data/balance/*.json 의
숫자를 그대로 읽어 30일·60일을 돌리고, 결과를 표로 stdout 에 낸다.

    python tools/sim_economy.py            # 30일·60일 전부
    python tools/sim_economy.py --days 30  # 30일만
    python tools/sim_economy.py --defense  # 방어 판정표만

값을 고칠 때는 이 파일이 아니라 data/balance/*.json 을 고치고 다시 돌린다.
난수는 전부 시드 고정이라 같은 입력이면 같은 표가 나온다(D6).

전제 (PM 확정 2026-10-01)
  - 게임 하루 = 실제 24시간. 접속 시간이 아니라 달력으로 흐른다.
  - 오프라인 생산은 최대 24시간치까지만 쌓인다(server.py MAX_OFFLINE_TICKS=3 × 8h).
  - 하루 스캔 상한 20, 이월 없음.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
BAL = ROOT / "data" / "balance"


def load(name: str) -> dict:
    return json.loads((BAL / f"{name}.json").read_text(encoding="utf-8"))


ECON = load("economy")
THREAT = load("threats")
DEFENSE = load("defense")
EQUIP = load("equipment")

MATERIAL_KEYS = ["food", "water", "med", "parts", "cloth", "trade", "knowledge", "scrap", "chem"]
BUILD_KEYS = ["parts", "cloth", "knowledge", "med", "trade", "scrap"]   # 방을 짓고 올리는 데 쓰는 것


# ─────────────────────────────────────────────────────────────
# 1. 스캔 수입
# ─────────────────────────────────────────────────────────────
class ScanModel:
    """하루치 스캔 수입. 체감 곡선·다양성 보너스·재스캔 감쇠를 전부 적용한다."""

    def __init__(self, rng: random.Random, pool_size: int):
        self.rng = rng
        self.mix = {k: v for k, v in ECON["scan"]["assumed_category_mix"].items() if not k.startswith("_")}
        self.cats = sorted(self.mix)
        self.weights = [self.mix[c] for c in self.cats]
        rar = ECON["scan"]["rarity"]
        self.rar_names = ["common", "uncommon", "rare", "epic", "legendary"]
        self.rar_p = [rar["_distribution"][n] for n in self.rar_names]
        self.rar_mul = rar["multiplier"]
        self.base = {k: v for k, v in ECON["scan"]["category_base_yield"].items() if not k.startswith("_")}
        self.tiers = ECON["scan"]["daily_fatigue"]["tiers"]
        self.div_cap = ECON["scan"]["diversity_bonus"]["cap"]
        self.decay = ECON["scan"]["rescan_decay"]["values"]
        # 플레이어가 손 닿는 서로 다른 바코드의 수. 재스캔 감쇠를 현실적으로 만드는 유일한 가정.
        self.pool = [0] * pool_size          # 최근 7일간 그 바코드를 몇 번 찍었나
        self.pool_size = pool_size
        self.day_seen: list[list[int]] = []

    def fatigue(self, idx: int) -> float:
        for t in self.tiers:
            if idx < t["upto"]:
                return t["mul"]
        return self.tiers[-1]["mul"]

    def one_day(self, n_scans: int) -> dict:
        """하루 스캔 결과. 재료 dict 를 돌려준다."""
        gained: dict[str, float] = {}
        cats_today: set[str] = set()
        picked_today: list[int] = []
        for i in range(n_scans):
            bc = self.rng.randrange(self.pool_size)
            times = self.pool[bc]
            mult_rescan = self.decay[times] if times < len(self.decay) else 0.0
            picked_today.append(bc)
            self.pool[bc] = times + 1
            if mult_rescan <= 0:
                continue                      # 네 번째부터는 아무것도 안 나온다
            cat = self.rng.choices(self.cats, weights=self.weights, k=1)[0]
            cats_today.add(cat)
            rar = self.rng.choices(self.rar_names, weights=self.rar_p, k=1)[0]
            mul = self.rar_mul[rar] * mult_rescan * self.fatigue(i)
            for k, v in self.base[cat].items():
                gained[k] = gained.get(k, 0.0) + v * mul
            bonus = self.rng.choice(["food", "water", "med", "power", "parts", "morale", "cloth", "trade", "knowledge"])
            gained[bonus] = gained.get(bonus, 0.0) + mul
        # 다양성 보너스
        div = min(self.div_cap, 1 + 0.08 * (len(cats_today) - 1)) if cats_today else 1.0
        for k in gained:
            gained[k] *= div
        # 7일 창 관리
        self.day_seen.append(picked_today)
        if len(self.day_seen) > 7:
            for bc in self.day_seen.pop(0):
                self.pool[bc] = max(0, self.pool[bc] - 1)
        return gained


# ─────────────────────────────────────────────────────────────
# 2. 거점 — 방·주민·생산·소비
# ─────────────────────────────────────────────────────────────
BUILD_ORDER = [
    "quarters", "storage", "well",            # 1일: 3칸
    "greenhouse", "generator", "workshop",    # 1주: 6칸
    "infirmary", "hall", "airlock",           # 2주: 9칸
    "decoder", "lounge", "bath",              # 1개월: 12칸
]
UPGRADE_ORDER = ["greenhouse", "well", "quarters", "generator", "workshop", "storage",
                 "infirmary", "decoder", "hall", "airlock"]


class Ark:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.res = {k: 0.0 for k in MATERIAL_KEYS}
        self.res.update({"food": 4, "water": 4, "parts": 1, "scrap": 2})
        self.morale = 5.0
        self.rooms: dict[str, int] = {}       # id -> level
        self.spec = ECON["rooms"]["list"]
        self.depth_floor = 0                  # 0..3 → 0/60/120/180 m
        self.income_scan = 0.0
        self.income_room = 0.0
        self.income_gift = 0.0
        self.morale_from_rooms = 0.0
        # 건설 재료만 따로 — 식량·물은 상한에 걸려 남아돌기 때문에 총량으로 세면 그림이 왜곡된다
        self.b_scan = self.b_room = self.b_gift = 0.0

    # ── 주민
    @property
    def resident_cap(self) -> int:
        q = self.rooms.get("quarters", 0)
        return {0: 3, 1: 4, 2: 6, 3: 8}[q] + (2 if "hall" in self.rooms else 0)

    def residents(self, day: int) -> int:
        return max(3, min(self.resident_cap, 10, 3 + int(day / 3.5)))

    # ── 보관 상한 (창고 선반). 넘치는 것은 버려진다.
    @property
    def cap_per_material(self) -> float:
        shelves = {0: 4, 1: 6, 2: 12, 3: 20}[self.rooms.get("storage", 0)]
        return shelves * 6

    def clamp(self):
        c = self.cap_per_material
        for k in MATERIAL_KEYS:
            if self.res[k] > c:
                self.res[k] = c

    # ── 생산
    def produce(self, day: int) -> dict:
        """방 생산. 배치 인원에 따라 달라진다. 오프라인으로도 들어오는 수입이 이것이다."""
        people = self.residents(day)
        prod_rooms = [r for r in ("greenhouse", "well", "decoder") if r in self.rooms]
        self.morale_from_rooms = sum(
            (self.spec[r]["produces"].get("morale", 0)
             if self.rooms[r] < 2 else
             self.spec[r].get(f"lv{self.rooms[r]}", {}).get("produces_after", self.spec[r]["produces"]).get("morale", 0))
            for r in ("quarters", "lounge", "bath") if r in self.rooms)
        out: dict[str, float] = {}
        # 생산 방에 한 명씩 먼저, 남으면 고루 더 배치(정원까지)
        assign = {r: 1 for r in prod_rooms}
        left = people - len(prod_rooms)
        i = 0
        while left > 0 and prod_rooms:
            r = prod_rooms[i % len(prod_rooms)]
            if assign[r] < self.spec[r]["cap"]:
                assign[r] += 1
                left -= 1
            elif all(assign[x] >= self.spec[x]["cap"] for x in prod_rooms):
                break
            i += 1
        for r in prod_rooms:
            lv = self.rooms[r]
            base = self.spec[r]["produces"]
            if lv >= 2:
                base = self.spec[r].get(f"lv{lv}", {}).get("produces_after", base)
            n = assign[r]
            scale = 0.6 + 0.4 * n
            for k, v in base.items():
                if k in MATERIAL_KEYS:
                    out[k] = out.get(k, 0.0) + v * scale
        return out

    def consume(self, day: int) -> dict:
        people = self.residents(day)
        c = ECON["consumption"]
        return {"food": c["food_per_resident_day"] * people,
                "water": c["water_per_resident_day"] * people}

    # ── 건설·레벨업
    def _cost_of(self, rid: str, to_level: int) -> dict:
        s = self.spec[rid]
        if to_level == 1:
            return {k: v for k, v in s["build"].items()}
        return {k: v for k, v in s.get(f"lv{to_level}", {}).get("cost", {}).items()}

    def _afford(self, cost: dict, reserve: float = 0.0) -> bool:
        return all(self.res.get(k, 0) >= v + reserve for k, v in cost.items())

    def _pay(self, cost: dict):
        for k, v in cost.items():
            self.res[k] = self.res.get(k, 0) - v

    def spend(self, day: int):
        """건설 우선, 그다음 레벨업. 목표 곡선 순서를 따르는 단순 정책."""
        # 1) 아직 안 지은 방을 순서대로
        for rid in BUILD_ORDER:
            if rid in self.rooms:
                continue
            if rid == "lounge" and self.rooms.get("quarters", 0) < 2:
                continue
            if rid == "bath" and self.rooms.get("generator", 0) < 2:
                continue
            cost = self._cost_of(rid, 1)
            if self._afford(cost):
                self._pay(cost)
                self.rooms[rid] = 1
            else:
                break                        # 순서를 지킨다. 뛰어넘지 않는다
        # 2) 레벨업. 주민 수용이 막히면 거주실을 먼저
        order = list(UPGRADE_ORDER)
        if self.residents(day) >= self.resident_cap:
            order.remove("quarters")
            order.insert(0, "quarters")
        for rid in order:
            lv = self.rooms.get(rid, 0)
            if lv == 0 or lv >= 3:
                continue
            if lv == 2:
                # Lv3 는 재료가 아니라 **조건**이 병목이다(각인 3개 보유자·특정 스팟 발견·해구 문턱).
                # 조건은 돈으로 못 사므로 시뮬레이션에서는 '9일에 하나씩 열린다'로 모델링한다.
                if day < 18 or self.lv_count(3) >= 1 + max(0, (day - 18)) // 9:
                    continue
            cost = self._cost_of(rid, lv + 1)
            if cost and self._afford(cost, reserve=2.0):
                self._pay(cost)
                self.rooms[rid] = lv + 1
        # 3) 깊이 — 처음 3칸은 돔(0m), 그 뒤 3칸마다 한 층씩 내려간다
        self.depth_floor = max(0, min(3, (len(self.rooms) - 3) // 3))

    @property
    def depth_m(self) -> int:
        return self.depth_floor * 60

    @property
    def grade(self) -> int:
        for g in (5, 4, 3, 2, 1):
            row = next(r for r in THREAT["grade_source"]["map"] if r["grade"] == g)
            if self.depth_m >= row["depth_m"] and len(self.rooms) >= row["rooms_min"]:
                return g
        return 1

    def lv_count(self, n: int) -> int:
        return sum(1 for v in self.rooms.values() if v >= n)


def run_economy(scans_per_day: int, days: int, seed: int, pool_size: int, skip_rate: float = 0.0) -> dict:
    rng = random.Random(seed)
    ark = Ark(rng)
    scan = ScanModel(random.Random(seed + 1), pool_size)
    hist = []
    skipped = 0
    for day in range(1, days + 1):
        played = rng.random() >= skip_rate
        if not played:
            skipped += 1
        # 스캔 (안 켠 날은 0, 이월 없음)
        g = scan.one_day(scans_per_day if played else 0)
        for k, v in g.items():
            if k == "morale":
                ark.morale = min(10.0, ark.morale + v * 0.1)
            elif k in ark.res:
                ark.res[k] += v
                ark.income_scan += v
                if k in BUILD_KEYS:
                    ark.b_scan += v
        # 방 생산 (오프라인으로도 들어온다. 안 켠 날도 24시간치까지)
        p = ark.produce(day)
        for k, v in p.items():
            ark.res[k] += v
            ark.income_room += v
            if k in BUILD_KEYS:
                ark.b_room += v
        # 소비
        for k, v in ark.consume(day).items():
            if ark.res[k] < v:
                ark.morale = max(0.0, ark.morale + ECON["consumption"]["starvation"]["morale_per_day"])
            ark.res[k] = max(0.0, ark.res[k] - v)
        # 문어 (안 켠 날은 누적되어 다음에)
        if played:
            gift = ECON["octopus_gift"]
            n = 1 + min(2, skipped)
            skipped = 0
            for _ in range(n):
                if rng.random() < 0.6:
                    k = min(BUILD_KEYS, key=lambda x: ark.res.get(x, 0))
                else:
                    k = rng.choice(BUILD_KEYS)
                amt = rng.choice([1, 2])
                ark.res[k] += amt
                ark.income_gift += amt
                if k in BUILD_KEYS:
                    ark.b_gift += amt
        # 사기 자연 하강
        ark.morale = max(0.0, min(10.0, ark.morale + ECON["consumption"]["morale"]["drift_per_day"]
                                   + ark.morale_from_rooms * 0.5))
        ark.clamp()
        # 짓기
        if played:
            ark.spend(day)
        hist.append({"day": day, "rooms": len(ark.rooms), "lv2": ark.lv_count(2), "lv3": ark.lv_count(3),
                     "residents": ark.residents(day), "depth": ark.depth_m, "grade": ark.grade,
                     "morale": round(ark.morale, 1),
                     **{k: round(ark.res[k], 1) for k in ("food", "water", "parts", "cloth", "knowledge", "med")}})
    total = ark.income_scan + ark.income_room + ark.income_gift
    return {"hist": hist, "ark": ark,
            "share_scan": ark.income_scan / total, "share_room": ark.income_room / total,
            "share_gift": ark.income_gift / total,
            "total_in": total,
            "b_total": (bt := ark.b_scan + ark.b_room + ark.b_gift),
            "b_scan": ark.b_scan / bt, "b_room": ark.b_room / bt, "b_gift": ark.b_gift / bt}


# ─────────────────────────────────────────────────────────────
# 3. 방어 판정 — defense.json 의 공식을 그대로 구현
# ─────────────────────────────────────────────────────────────
S = DEFENSE["score"]
# 위협 열하나 (data/creatures.json). min_grade 아래에서는 나타나지 않는다.
THREATS_ALL = [k for k in DEFENSE["role_affinity"] if not k.startswith("_")]
MIN_GRADE = {k: v for k, v in THREAT["min_grade"].items() if not k.startswith("_")}


def creatures_at(grade: int) -> list:
    return [c for c in THREATS_ALL if MIN_GRADE.get(c, 1) <= grade]


ROLES = ["scout", "cook", "medic", "engineer", "farmer", "scholar", "trader", "kid"]


def affinity(creature: str, role: str) -> float:
    t = DEFENSE["role_affinity"].get(creature, {})
    if role in t.get("strong", {}):
        return S["affinity_strong"]
    if role in t.get("weak", {}):
        return S["affinity_weak"]
    return 0.0


def person_w(nerve: int, injured: bool = False) -> float:
    w = S["person"]["base"] + S["person"]["per_nerve"] * nerve
    return w * (S["person"]["injured_mul"] if injured else 1.0)


def score_of(creature: str, people: list[dict], room_lv: int, tools: list[float], imprints: int) -> float:
    sc = S["room_base"][str(room_lv)]
    for p in people:
        sc += person_w(p["nerve"], p.get("injured", False))
        sc += affinity(creature, p["role"])
    sc += min(sum(tools), S["tool_total_cap"])
    sc += imprints * S["imprint_match"]
    return sc


def verdict(score: float, need: float, gate_ok: bool, grade: int, n_people: int = 1) -> str:
    margin = score - need
    table = DEFENSE["verdict"]["gate_pass" if gate_ok else "gate_fail"]
    out = "breached"
    for row in table:
        if margin >= row["min_margin"]:
            out = row["result"]
            break
    # 상실 보호 두 단계 (defense.json verdict.loss_shield)
    if out == "breached" and DEFENSE["verdict"]["loss_shield"]["enabled"]:
        if grade == 1 or (grade == 2 and n_people > 0):
            out = "scarred"
    return out


def need_of(creature: str, grade: int, sev: int) -> float:
    return (THREAT["need_by_grade"][str(grade)]
            + THREAT["creature_offset"][creature]
            + THREAT["severity"]["add_per_step"] * sev)


# 배치 원형 여섯 — 같은 습격을 이 여섯으로 받아 본다
def archetypes(creature: str, grade: int) -> dict:
    """등급대에 맞는 **현실적인** 자원(방 레벨·정원·도구·각인·담)을 쥐고 배치만 바꾼다.

    여기서 등급별로 자원을 올려 주는 것은 밸런스가 아니라 **모델의 정확도**다.
    등급은 깊이로 정해지고, 깊이가 깊다는 것은 그만큼 오래 키웠다는 뜻이기 때문이다
    (threats.json grade_source). 등급 5 를 1일차 자원으로 받는 플레이어는 존재하지 않는다.
    """
    lv = 1 if grade <= 2 else (2 if grade <= 4 else 3)
    cap = 3 if grade <= 3 else 4                 # 거주실·창고 레벨업으로 정원이 는다
    nerve = 5 if grade <= 2 else 6               # 특이점·장비(구식 헬멧 담+1)로 조금 오른다
    tool_kit = [] if grade <= 1 else ([1.5] if grade == 2 else [1.5, 1.5])
    imp = 0 if grade <= 1 else (1 if grade <= 3 else 2)
    strong = list(DEFENSE["role_affinity"][creature]["strong"])
    weak = list(DEFENSE["role_affinity"][creature]["weak"])
    other = [r for r in ROLES if r not in strong and r not in weak]

    def fill(role_list, n, nv=None):
        return [{"role": role_list[i % len(role_list)], "nerve": nv or nerve} for i in range(n)]

    return {
        "빈 방":            {"people": [], "lv": lv, "tools": [], "imp": 0},
        "아무나 2명":        {"people": fill(other, 2), "lv": lv, "tools": [], "imp": 0},
        "아무나 정원껏":      {"people": fill(other, cap), "lv": lv, "tools": [], "imp": 0},
        "맞는 사람 2 + 나머지": {"people": [{"role": strong[0], "nerve": nerve + 1},
                                        {"role": strong[1], "nerve": nerve}] + fill(other, cap - 2),
                             "lv": lv, "tools": [], "imp": 0},
        "평범 + 도구":       {"people": fill(other, cap), "lv": lv, "tools": tool_kit, "imp": 0},
        "겪어 본 사람":      {"people": [{"role": weak[0], "nerve": nerve}] + fill(other, cap - 1),
                           "lv": lv, "tools": [], "imp": imp},
        "총력":             {"people": [{"role": strong[0], "nerve": nerve + 1},
                                      {"role": strong[1], "nerve": nerve}] + fill(other, cap - 2),
                           "lv": lv, "tools": tool_kit, "imp": imp},
    }


def gate_ok_for(creature: str, arch: dict, sev: int, correct_action: bool) -> bool:
    if creature == "swarm":
        hands = len(arch["tools"])
        return len(arch["people"]) + hands >= 2 + sev
    return correct_action and len(arch["people"]) > 0


def defense_table():
    print("\n" + "=" * 100)
    print("표 D1. 같은 습격을 배치만 바꿔 받아 본다 — 올바른 행동(관문)을 **했을 때**")
    print("=" * 100)
    hdr = f"{'등급':<5}{'생물':<10}{'sev':<5}{'need':<7}"
    arch_names = list(archetypes("swarm", 1))
    for a in arch_names:
        hdr += f"{a:<16}"
    print(hdr)
    rows_differ = 0
    rows_total = 0
    tally = {}
    for grade in (1, 2, 3, 4, 5):
        for creature in creatures_at(grade):
            for sev in (0, 1, 2):
                if THREAT["severity"]["weights_by_grade"][str(grade)][sev] == 0:
                    continue
                need = need_of(creature, grade, sev)
                line = f"{grade:<5}{creature:<10}{sev:<5}{need:<7.1f}"
                results = []
                for a in arch_names:
                    arch = archetypes(creature, grade)[a]
                    sc = score_of(creature, arch["people"], arch["lv"], arch["tools"], arch["imp"])
                    ok = gate_ok_for(creature, arch, sev, True)
                    v = verdict(sc, need, ok, grade, len(arch["people"]))
                    results.append(v)
                    ko = {"held": "막음", "scarred": "금", "breached": "상실"}[v]
                    line += f"{ko + f'({sc:.1f})':<16}"
                    tally[(grade, v)] = tally.get((grade, v), 0) + 1
                rows_total += 1
                if len(set(results)) > 1:
                    rows_differ += 1
                print(line)
    print(f"\n배치에 따라 결과가 갈린 경우: {rows_differ}/{rows_total} = {rows_differ / rows_total:.0%}"
          f"   (목표 40% 이상 — defense.json _what_measurement_would_settle_this)")

    print("\n" + "=" * 100)
    print("표 D2. 올바른 행동을 **안 했을 때**(관문 실패) — 불을 안 껐다 / 전원을 안 내렸다")
    print("=" * 100)
    print(f"{'등급':<5}{'생물':<10}{'sev':<5}{'need':<7}{'최선의 배치로도':<20}{'점수':<8}")
    for grade in (1, 2, 3, 4, 5):
        for creature in [c for c in ("longneck", "warden", "mirror_eye", "lid", "big_maw", "follower") if MIN_GRADE.get(c,1) <= grade]:
            sev = 0
            need = need_of(creature, grade, sev)
            arch = archetypes(creature, grade)["맞는 사람 2 + 나머지"]
            sc = score_of(creature, arch["people"], arch["lv"], arch["tools"], arch["imp"])
            v = verdict(sc, need, False, grade, len(arch["people"]))
            ko = {"held": "막음", "scarred": "금", "breached": "상실"}[v]
            print(f"{grade:<5}{creature:<10}{sev:<5}{need:<7.1f}{ko:<20}{sc:<8.1f}")
    print("→ 관문을 놓치면 **아무리 좋은 배치여도 막을 수 없다.** 이것이 '종마다 막는 법이 다르다'를 강제한다.")

    print("\n" + "=" * 100)
    print("표 D3. 등급별 결과 분포 (여섯 배치 원형 × 전 생물 × 전 severity, 관문 통과 가정)")
    print("=" * 100)
    print(f"{'등급':<6}{'막음':<10}{'금':<10}{'상실':<10}")
    for grade in (1, 2, 3, 4, 5):
        tot = sum(tally.get((grade, v), 0) for v in ("held", "scarred", "breached"))
        if not tot:
            continue
        print(f"{grade:<6}" + "".join(f"{tally.get((grade, v), 0) / tot:<10.0%}"
                                      for v in ("held", "scarred", "breached")))
    print("주: 이 표는 '빈 방'까지 포함한 여섯 배치를 **같은 비중**으로 센 것이라 실제 플레이보다 나쁘게 나온다.")
    print("    실제 플레이어는 빈 방·아무나 2명을 거의 고르지 않는다. 목표 분포(held 60~75%)는 표 D4 로 본다.")

    # 플레이어가 실제로 그 배치를 고를 법한 비중. 깊이는 스스로 당긴 것이라
    # 깊은 곳에 있는 사람일수록 더 잘 배치하고 더 많이 갖추고 있다(threats.json grade_source).
    PLAY_W = {
        1: {"빈 방": 0.08, "아무나 2명": 0.20, "아무나 정원껏": 0.37, "맞는 사람 2 + 나머지": 0.15,
            "평범 + 도구": 0.05, "겪어 본 사람": 0.10, "총력": 0.05},
        2: {"빈 방": 0.04, "아무나 2명": 0.12, "아무나 정원껏": 0.30, "맞는 사람 2 + 나머지": 0.22,
            "평범 + 도구": 0.12, "겪어 본 사람": 0.12, "총력": 0.08},
        3: {"빈 방": 0.02, "아무나 2명": 0.07, "아무나 정원껏": 0.20, "맞는 사람 2 + 나머지": 0.25,
            "평범 + 도구": 0.16, "겪어 본 사람": 0.15, "총력": 0.15},
        4: {"빈 방": 0.01, "아무나 2명": 0.04, "아무나 정원껏": 0.12, "맞는 사람 2 + 나머지": 0.25,
            "평범 + 도구": 0.17, "겪어 본 사람": 0.16, "총력": 0.25},
        5: {"빈 방": 0.00, "아무나 2명": 0.02, "아무나 정원껏": 0.08, "맞는 사람 2 + 나머지": 0.24,
            "평범 + 도구": 0.16, "겪어 본 사람": 0.15, "총력": 0.35},
    }
    # 관문(올바른 행동)을 해내는 비율도 배우면서 오른다. 긴목·문지기는 처음엔 자주 놓친다.
    GATE_OK_RATE = {1: 0.60, 2: 0.72, 3: 0.82, 4: 0.88, 5: 0.92}

    print("\n" + "=" * 100)
    print("표 D4. 실제 플레이에 가까운 분포 — 배치 선택 확률·관문 성공률·생물 빈도를 모두 반영")
    print("=" * 100)
    print(f"{'등급':<6}{'막음':<10}{'금':<10}{'상실':<10}{'관문 성공률':<12}")
    for grade in (1, 2, 3, 4, 5):
        cnt = {"held": 0.0, "scarred": 0.0, "breached": 0.0}
        gr = GATE_OK_RATE[grade]
        for creature in creatures_at(grade):
            w = THREAT["frequency"]["by_grade"][str(grade)]["weights"].get(creature, 2)
            if w == 0:
                continue
            for sev in (0, 1, 2):
                sw = THREAT["severity"]["weights_by_grade"][str(grade)][sev]
                if sw == 0:
                    continue
                need = need_of(creature, grade, sev)
                for a in arch_names:
                    aw = PLAY_W[grade][a]
                    if aw == 0:
                        continue
                    arch = archetypes(creature, grade)[a]
                    sc = score_of(creature, arch["people"], arch["lv"], arch["tools"], arch["imp"])
                    # 작은 떼는 관문이 사람 수라 행동 성공률과 무관하다
                    if creature == "swarm":
                        branches = [(gate_ok_for(creature, arch, sev, True), 1.0)]
                    else:
                        branches = [(gate_ok_for(creature, arch, sev, True), gr),
                                    (False, 1 - gr)]
                    for ok, p in branches:
                        cnt[verdict(sc, need, ok, grade, len(arch["people"]))] += w * sw * aw * p
        tot = sum(cnt.values())
        print(f"{grade:<6}" + "".join(f"{cnt[v] / tot:<10.0%}" for v in ("held", "scarred", "breached"))
              + f"{gr:<12.0%}")
    t = THREAT["_target_outcome_distribution"]
    print(f"\n  목표: 막음 {t['held']} / 금 {t['scarred']} / 상실 {t['breached']}")

    print("\n" + "=" * 100)
    print("표 D5. 두 번째 정답이 있는가 — 같은 점수에 이르는 서로 다른 길 (등급 4, 작은 떼, sev1)")
    print("=" * 100)
    need = need_of("swarm", 4, 1)
    paths = {
        "맞는 사람 둘 + 평범 하나": score_of("swarm", [{"role": "engineer", "nerve": 6}, {"role": "cook", "nerve": 5},
                                                 {"role": "scout", "nerve": 5}], 2, [], 0),
        "평범 셋 + 보강대 + 그물":   score_of("swarm", [{"role": "scout", "nerve": 5}] * 3, 2, [1.5, 1.5], 0),
        "겪어 본 사람 둘 + 하나":    score_of("swarm", [{"role": "scout", "nerve": 5}] * 3, 2, [], 2),
        "정원 4 방에 평범 넷(Lv3)":  score_of("swarm", [{"role": "medic", "nerve": 5}] * 4, 3, [], 0),
    }
    for k, v in paths.items():
        print(f"  {k:<28} {v:>5.2f}   need {need:.1f} → "
              f"{ {'held': '막음', 'scarred': '금', 'breached': '상실'}[verdict(v, need, True, 4, 3)] }")
    spread = max(paths.values()) - min(paths.values())
    print(f"\n  최고−최저 = {spread:.2f}. 네 길이 {spread:.1f} 안에 모여 있으면 최적해가 하나로 수렴하지 않는다(B3).")


# ─────────────────────────────────────────────────────────────
# 4. 출력
# ─────────────────────────────────────────────────────────────
PROFILES = [("열심 20회/일", 20, 160), ("보통 8회/일", 8, 90), ("띄엄띄엄 3회/일", 3, 55)]
# pool_size = 그 사람이 손 닿는 서로 다른 바코드 수. 많이 찍는 사람일수록 더 넓게 돌아다닌다는 가정.


def economy_tables(days: int):
    print("\n" + "=" * 100)
    print(f"표 E1. {days}일 진행 — 플레이 유형 셋")
    print("=" * 100)
    runs = {}
    for name, n, pool in PROFILES:
        runs[name] = run_economy(n, days, seed=7, pool_size=pool)
    marks = [d for d in (1, 3, 7, 14, 21, 30, 45, 60) if d <= days]
    print(f"{'유형':<18}{'일':<5}{'방':<5}{'Lv2':<5}{'Lv3':<5}{'주민':<6}{'깊이':<7}{'등급':<5}"
          f"{'식량':<7}{'물':<7}{'부품':<7}{'직물':<7}{'기록':<7}{'사기':<5}")
    for name, _, _ in PROFILES:
        for d in marks:
            h = runs[name]["hist"][d - 1]
            print(f"{name:<18}{h['day']:<5}{h['rooms']:<5}{h['lv2']:<5}{h['lv3']:<5}{h['residents']:<6}"
                  f"{h['depth']:<7}{h['grade']:<5}{h['food']:<7}{h['water']:<7}{h['parts']:<7}"
                  f"{h['cloth']:<7}{h['knowledge']:<7}{h['morale']:<5}")
        print("-" * 100)
    return runs


def curve_check(runs: dict, days: int):
    print("\n" + "=" * 100)
    print("표 E2. 목표 곡선 대조 (ROOMS_AND_ITEMS §4) — 보통 플레이어 기준으로 맞췄다")
    print("=" * 100)
    print(f"{'시점':<8}{'목표 방':<10}{'열심':<10}{'보통':<10}{'띄엄띄엄':<10}{'판정':<12}")
    for cp in ECON["target_curve"]["checkpoints"]:
        d = cp["day"]
        if d > days:
            continue
        got = {name: runs[name]["hist"][d - 1]["rooms"] for name, _, _ in PROFILES}
        normal = got["보통 8회/일"]
        ok = "맞음" if abs(normal - cp["rooms"]) <= 1 else ("빠름" if normal > cp["rooms"] else "느림")
        print(f"{d}일{'':<5}{cp['rooms']:<10}{got['열심 20회/일']:<10}{normal:<10}{got['띄엄띄엄 3회/일']:<10}{ok:<12}")


def income_share(runs: dict, days: int):
    print("\n" + "=" * 100)
    print("표 E3. 수입 출처 — 스캔이 주 수입인가, 오프라인이 바닥을 받치는가 (PM 요구 ①)")
    print("=" * 100)
    print("【전 자원 기준】 — 식량·물을 포함한 총량. 보관 상한에 걸려 남아도는 분까지 세므로 참고용이다.")
    print(f"{'유형':<18}{'스캔':<10}{'방 생산(오프라인)':<22}{'문어':<10}{'총 수입':<10}")
    for name, _, _ in PROFILES:
        r = runs[name]
        print(f"{name:<18}{r['share_scan']:<10.0%}{r['share_room']:<22.0%}{r['share_gift']:<10.0%}{r['total_in']:<10.0f}")
    print("\n【건설 재료만】 — 부품·직물·기록·약재·교역품·잔해. **방을 짓고 올리는 데 실제로 쓰이는 것.**")
    print(f"{'유형':<18}{'스캔':<10}{'방 생산(오프라인)':<22}{'문어':<10}{'총량':<10}")
    for name, _, _ in PROFILES:
        r = runs[name]
        print(f"{name:<18}{r['b_scan']:<10.0%}{r['b_room']:<22.0%}{r['b_gift']:<10.0%}{r['b_total']:<10.0f}")
    print("\n  판정 기준: 스캔 비중이 모든 유형에서 과반이면 '스캔이 주 수입'이 성립한다.")
    print("  방 생산(오프라인)은 식량·물만 낸다 — 건설 재료는 한 톨도 안 나온다. 그래서 하루 안 켜면")
    print("  굶지는 않지만 자라지도 않는다. 이것이 압박 없이 접속 동기를 만드는 자리다(B4).")


def gap_check(runs: dict, days: int):
    print("\n" + "=" * 100)
    print(f"표 E4. 열심 ↔ 띄엄띄엄 격차 ({days}일차) (PM 요구 ②)")
    print("=" * 100)
    h = runs["열심 20회/일"]["hist"][days - 1]
    n = runs["보통 8회/일"]["hist"][days - 1]
    l = runs["띄엄띄엄 3회/일"]["hist"][days - 1]
    print(f"{'지표':<14}{'열심':<10}{'보통':<10}{'띄엄띄엄':<10}{'열심÷띄엄':<10}")
    for key, ko in (("rooms", "방"), ("lv2", "Lv2"), ("residents", "주민"), ("depth", "깊이")):
        hv, lv = h[key], l[key]
        ratio = f"{hv / lv:.1f}배" if lv else "—"
        print(f"{ko:<14}{hv:<10}{n[key]:<10}{lv:<10}{ratio:<10}")
    print(f"\n  스캔 횟수 자체의 격차는 20÷3 = 6.7배다. 체감 곡선(daily_fatigue)과 문어 바닥 보정이")
    print(f"  이것을 방 수 기준 {h['rooms'] / max(1, l['rooms']):.1f}배까지 눌렀다.")


def skipped_days(days: int):
    print("\n" + "=" * 100)
    print("표 E5. 하루를 건너뛰면 (PM 요구 ③) — 보통 플레이어, 결석률별")
    print("=" * 100)
    print(f"{'결석률':<10}{'방':<8}{'Lv2':<8}{'식량':<8}{'물':<8}{'사기':<8}")
    for rate in (0.0, 0.15, 0.30, 0.50):
        r = run_economy(8, days, seed=7, pool_size=90, skip_rate=rate)
        h = r["hist"][days - 1]
        print(f"{rate:<10.0%}{h['rooms']:<8}{h['lv2']:<8}{h['food']:<8}{h['water']:<8}{h['morale']:<8}")
    print("\n  식량·물이 결석률과 거의 무관하게 유지되는 것이 핵심이다 — **비워도 재고가 줄지 않는다.**")
    print("  줄어드는 것은 방 수(= 성장)뿐이고, 그것은 벌이 아니라 '안 한 만큼 안 자란 것'이다.")
    print("  오프라인 생산 상한 24시간(server.py MAX_OFFLINE_TICKS=3)이라 사흘 비워도 하루치만 받는다.")
    print("  건너뛴 날의 습격은 판정하지 않고 지나간다 — 없는 사이에 방을 잃지 않는다(economy.json skipped_day).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=0)
    ap.add_argument("--defense", action="store_true")
    ap.add_argument("--economy", action="store_true")
    a = ap.parse_args()
    do_all = not (a.defense or a.economy)

    print("잔해 방주 — 밸런스 시뮬레이션")
    print(f"입력: data/balance/*.json ({ECON['_version']})")

    if a.defense or do_all:
        defense_table()
    if a.economy or do_all:
        for d in ([a.days] if a.days else [30, 60]):
            runs = economy_tables(d)
            curve_check(runs, d)
            income_share(runs, d)
            gap_check(runs, d)
            skipped_days(d)


if __name__ == "__main__":
    main()
