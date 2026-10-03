"""감사(audit) — 수집 요소의 재고·결정성·완성 곡선.

읽기 전용. 프로젝트 파일·DB 를 건드리지 않는다.
  - engine/relic_generator.RelicGenerator.generate 를 **직접** 불러 실제 유물을 만든다(규칙 마).
  - server.py 는 import 만 하고 상수·순수 함수(rescan_multiplier, RUMOR_RULES 등)를 읽는다.
  - 가정(가구 바코드 분포 등)은 전부 ASSUME 표에 모았다. 결과 표에 '가정'이라고 함께 적는다.

실행: python tools/audit_collection.py          (약 30~90초)
      python tools/audit_collection.py --quick  (가구 수를 줄인다)
"""
from __future__ import annotations

import io
import json
import os
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "engine"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
with redirect_stdout(io.StringIO()):
    import server as S                                  # noqa: E402
from relic_generator import RelicGenerator, Category, rescan_multiplier, RARITY_ORDER  # noqa: E402

QUICK = "--quick" in sys.argv
GEN = RelicGenerator()
DATA = os.path.join(ROOT, "data")


def L(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def hr(t):
    print("\n" + "=" * 100 + "\n" + t + "\n" + "=" * 100)


def grep_code(pattern, files=("server.py", "static/base.js", "static/app.js", "static/m5map.js", "static/life.js")):
    hits = {}
    for f in files:
        p = os.path.join(ROOT, f)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as fh:
            n = len(re.findall(pattern, fh.read()))
        if n:
            hits[f] = n
    return hits


# ─────────────────────────────────────────────────────────────
# B1. 재고 — 데이터 파일에서 센 정확한 수 + 코드에 연결돼 있는가
# ─────────────────────────────────────────────────────────────
def inventory():
    hr("B1. 수집 재고 — 데이터 파일 실측 + '게임 코드가 그 파일을 읽는가'")
    t = L("relic_templates.json")
    cats = [k for k in t if not k.startswith("_")]
    stems = {c: [x["name"].replace("{adj} ", "") for x in t[c]] for c in cats}
    n_stem = sum(len(v) for v in stems.values())
    adj = t["_adjectives"]
    print(f"유물 템플릿(도감 칸 = 이름 줄기): {n_stem}  (카테고리 {len(cats)}: " +
          ", ".join(f"{c} {len(v)}" for c, v in stems.items()) + ")")
    print(f"형용사 {len(adj)} → 화면 이름 조합 {n_stem * len(adj)}  | 도감 화면(/api/codex)은 줄기 {n_stem}칸만 센다;"
          f" 스캔 응답의 first_time 은 형용사 포함 전체 이름 기준(server.scan: card.name not in cx)")
    fam = {k: v for k, v in L("known_families.json").items() if not k.startswith("_")}
    print(f"알려진 제조 가문(7자리 접두): {len(fam)}  카테고리별 {dict(Counter(v['category'] for v in fam.values()))}")
    lore = L("family_lore.json")["families"]
    print(f"가문 세트(family_lore): {len(lore)}  set_count 분포 {dict(Counter(v['set_count'] for v in lore.values()))}"
          f"  장식(decor) {sum(1 for v in lore.values() if v.get('decor'))}")
    print("희귀도 5단(흔함/쓸만함/귀함/진귀함/전설), 문턱 990/950/850/600, 도서는 귀함 이상 보장")
    props = L("relic_props.json")["props"]
    print(f"선반 소품(relic_props): {sum(len(v) for v in props.values())}  카테고리별 {dict((k, len(v)) for k, v in props.items())}")
    imps = L("imprints.json")["imprints"]
    print(f"각인: {len(imps)}  ({', '.join(i['id'] for i in imps)})  | 역할 진화 이름 {len(L('roles_evolved.json')['roles'])}")
    print(f"주민 바람(wishes): {len(L('wishes.json')['wishes'])}")
    sp = L("spots.json"); spd = L("spots_deep.json")
    print(f"힐링 스팟: 육상 {len(sp)} + 심해 {len(spd)} = {len(sp) + len(spd)} (1막은 심해 {len(spd)})  | 소문 {len(L('rumors.json'))}줄")
    cr = L("creatures.json")["creatures"]
    print(f"생물: {len(cr)} (위협 {sum(1 for c in cr if S.combat.CREATURES.get(c['id'], {}).get('threat'))}, "
          f"위협 아님 {sum(1 for c in cr if not S.combat.CREATURES.get(c['id'], {}).get('threat'))})")
    oc = L("companion_octopus.json")
    print(f"문어 선물(finds): {len(oc['finds'])}  기분 {len(oc['moods'])}")
    fm = L("first_meet.json")
    print(f"첫 만남 연출: 카테고리 {len(fm['categories'])} + 가문 {len(fm['families'])}")
    print(f"하루 마감 장면: {len(L('day_end.json')['situations'])}")
    roles = L("roles.json")
    print(f"역할 {len([k for k in roles if not k.startswith('_')])}  이름 풀 {len(roles['_names'])}  특성(trait) {len(roles['_traits'])}"
          f"  특이점 {len(S.QUIRK_KO)}")
    meta = json.load(open(os.path.join(ROOT, "static/art/chars/front/p2/meta.json"), encoding="utf-8"))
    print(f"외형: 머리 {len(meta.get('hair') or [])} × 얼굴 {len(meta.get('faces') or [])} × 체형 {len(meta.get('bodies') or {})}(+아이)")
    rooms = [k for k, v in S.ROOMS.items()]
    print(f"방 종류(코드 카탈로그): {len(rooms)} {rooms}  레벨 1~3")
    print(f"대응 도구: {len(S.combat.TOOLS)}  | 장비 슬롯(equipment.json): {len(L('balance/equipment.json')['slots'])} 슬롯")
    ev = [e for e in S.EVENTS.values() if 1 in (e.get("acts") or [])]
    print(f"1막 사건 카드: {len(ev)}장")

    print("\n연결 여부 — 이 데이터 파일/필드를 게임 코드(server.py·static/*.js)가 읽는가 (문자열 검색 실측):")
    checks = {
        "family_lore.json (가문 세트 보상)": r"family_lore|set_count",
        "first_meet.json (첫 만남 연출)": r"first_meet",
        "wishes.json (주민 바람)": r"wishes\.json|wish_",
        "companion_octopus.json (문어 이름·선물)": r"companion_octopus|octopus_gift",
        "day_end.json (하루 마감)": r"day_end",
        "/api/codex (도감 화면)": r"/api/codex",
        "/api/rumors (소문)": r"/api/rumors",
        "머리·얼굴·체형B 패치(hair/ faces/)": r"hair/|faces/",
        "equipment.json (장비)": r"equipment",
        "relic_props.json → 선반(props_meta)": r"relic_props|props_meta",
        "spots (스팟)": r"/api/spots",
    }
    for name, pat in checks.items():
        h = grep_code(pat)
        srv = h.get("server.py", 0); base = h.get("static/base.js", 0) + h.get("static/m5map.js", 0) + h.get("static/life.js", 0)
        old = h.get("static/app.js", 0)
        state = "연결됨(본 화면)" if base else ("옛 화면(/)만" if old else ("서버만" if srv else "미연결"))
        print(f"  {name:38s} server.py {srv:2d} | /base 화면 {base:2d} | 옛 화면 {old:2d} → {state}")
    return stems


# ─────────────────────────────────────────────────────────────
# B1-2. 바코드 → 유물: 결정성·중복·재스캔
# ─────────────────────────────────────────────────────────────
def ean13(body12: str) -> str:
    d = [int(c) for c in body12]
    s = sum(x * (1 if i % 2 == 0 else 3) for i, x in enumerate(d))
    return body12 + str((10 - s % 10) % 10)


def mapping():
    hr("B1-2. 바코드 → 유물 매핑 (RelicGenerator.generate 직접 호출)")
    rng = random.Random(7)
    fams = [k for k in GEN.families if not k.startswith("_")]
    # 결정성
    code = ean13(fams[0] + "12345")
    a = GEN.generate(code, hour=9).to_dict(); b = GEN.generate(code, hour=23).to_dict()
    diff = [k for k in a if a[k] != b[k]]
    print(f"같은 바코드, 다른 시각(9시 vs 23시): 달라지는 필드 = {diff}  → 정체는 같고 variant(시간대 4종)만 바뀐다."
          " variant 는 화면·도감에서 쓰이지 않는다:", grep_code(r"\.variant|variant\b", ("static/base.js",)) or "base.js 0회")
    # 사용자 카테고리
    unk = [ean13("880" + f"{rng.randint(0, 9999):04d}" + f"{rng.randint(0, 99999):05d}") for _ in range(3000)]
    unk = [c for c in unk if c[:7] not in GEN.families]
    picks = [c.value for c in Category if c not in (Category.UNKNOWN, Category.BOOK)]
    n_names = []
    for c in unk[:1000]:
        names = {GEN.generate(c, user_category=p).name for p in picks}
        n_names.append(len(names))
    print(f"모르는 가문 바코드 1개를 고를 수 있는 카테고리 {len(picks)}개로 각각 찍으면 → 서로 다른 유물 이름 평균 {statistics.mean(n_names):.2f}개"
          f" (도감 줄기는 카테고리마다 다른 칸). 즉 '같은 바코드 = 같은 유물'은 **알려진 가문 18곳과 도서(978/979)에서만** 성립한다.")
    # 희귀도 분포
    sample = [ean13("880" + f"{rng.randint(0, 9999):04d}" + f"{rng.randint(0, 99999):05d}") for _ in range(100000)]
    rar = Counter(GEN.generate(c, user_category="food").rarity.value for c in sample)
    print("희귀도 실측(무작위 EAN 10만):", {r.value: f"{rar[r.value] / len(sample):.2%}" for r in RARITY_ORDER})
    # 이름 줄기 편향 — '희귀할수록 뒤쪽(신비로운) 이름' 주석이 실제로 작동하는가
    by_r = defaultdict(Counter)
    pool = GEN.templates["food"]
    for c in sample:
        card = GEN.generate(c, user_category="food")
        if card.category.value != "food":
            continue
        stem = next(i for i, t in enumerate(pool) if card.name.endswith(t["name"].replace("{adj} ", "")))
        by_r[card.rarity.value][stem] += 1
    print("식품 이름 줄기 0~3 의 비율(희귀도별) — 주석은 '희귀하면 뒤쪽 편향':")
    for r in RARITY_ORDER:
        c = by_r[r.value]; tot = sum(c.values())
        print(f"  {r.value:9s} " + " ".join(f"{c[i] / tot:5.0%}" for i in range(len(pool))))
    print("  → bias*3 를 더한 뒤 %4 는 회전일 뿐이라 균등 시드에서 분포가 바뀌지 않는다. 희귀도와 이름은 독립이다.")
    # 재스캔
    print("\n재스캔(server.scan): 같은 바코드의 최근 7일 스캔 수 prev → 배율", [rescan_multiplier(i) for i in range(5)])
    print("  배율 0 이어도: 도감 카운트 +1, scans 테이블 +1(→ 스팟 해금 카운트에 들어간다), 하루 20회 상한 1회 소모.")
    print("  배율 0 이면: 자원 0, 손패 안 들어감, 선반에 안 놓임. 합치기·강화·교환·선물 기능 없음(server.py 에 해당 API 없음).")
    print("  스팟 해금 = scans 테이블의 카테고리별 **행 수**(server.scan_counts, 중복 바코드 구분 없음):",
          {k: f"{v['categories'][0]}×{v['need']}" for k, v in S.RUMOR_RULES_DEEP.items()})


# ─────────────────────────────────────────────────────────────
# B2. 완성 곡선 시뮬레이션
# ─────────────────────────────────────────────────────────────
ASSUME = {
    "household_items": 120,          # 집 안에서 손에 닿는 서로 다른 바코드(가정)
    "new_items_per_week": 6,         # 장보기로 새로 들어오는 서로 다른 바코드/주(가정)
    "zipf_s": 1.1,                   # 손에 잡히는 빈도: 소수 일상품이 대부분(가정)
    "novelty_reject": 0.7,           # 최근 7일에 찍은 물건이면 70% 확률로 다른 걸 찾는다(가정)
    "known_family_share": 0.25,      # 18개 알려진 가문에 속하는 비율(식품·음료·의약·전자·문구·담배 안에서, 가정)
    "skip_picker": 0.10,             # 모르는 가문에서 카테고리 고르기를 건너뛰는 비율 → unknown(가정)
    # 카테고리 분포 — economy.json scan.assumed_category_mix 그대로(그 파일도 '가장 약한 숫자'라고 적었다)
}


def make_household(rng, size, mix):
    fams_by_cat = defaultdict(list)
    for k, v in GEN.families.items():
        if not k.startswith("_"):
            fams_by_cat[v["category"]].append(k)
    cats = [c for c in mix if c != "unknown" and not c.startswith("_")]
    w = [mix[c] for c in cats]
    items = []
    for _ in range(size):
        cat = rng.choices(cats, weights=w)[0]
        if cat == "book":
            code = ean13("978" + f"{rng.randint(0, 999999999):09d}")
        elif fams_by_cat.get(cat) and rng.random() < ASSUME["known_family_share"]:
            code = ean13(rng.choice(fams_by_cat[cat]) + f"{rng.randint(0, 99999):05d}")
        else:
            while True:
                m = f"{rng.randint(0, 9999):04d}"
                if "880" + m not in GEN.families:
                    break
            code = ean13("880" + m + f"{rng.randint(0, 99999):05d}")
        pick = None if (code[:7] in GEN.families or cat == "book") else (None if rng.random() < ASSUME["skip_picker"] else cat)
        card = GEN.generate(code, user_category=pick)
        items.append({"code": code, "cat": card.category.value, "name": card.name, "rarity": card.rarity.value,
                      "fam": code[:7] if code[:7] in GEN.families else None})
    return items


def simulate(scans_per_day, days, n_house, seed=0):
    mix = {k: v for k, v in S.combat._balance("economy")["scan"]["assumed_category_mix"].items()
           if not k.startswith("_")}
    tpl = GEN.templates
    stems_all = {(c, x["name"].replace("{adj} ", "")) for c in tpl if not c.startswith("_") for x in tpl[c]}
    lore = L("family_lore.json")["families"]
    deep_rules = S.RUMOR_RULES_DEEP
    curves = defaultdict(lambda: defaultdict(list))   # metric -> day -> [values]
    for h in range(n_house):
        rng = random.Random(f"{seed}|{h}")
        items = make_household(rng, ASSUME["household_items"], mix)
        order = list(range(len(items))); rng.shuffle(order)
        weights = [1.0 / (r + 1) ** ASSUME["zipf_s"] for r in range(len(items))]
        rank = {i: order[i] for i in range(len(items))}
        seen_codes = set(); stems = set(); names = set(); rar = set(); fams_seen = set()
        fam_distinct = defaultdict(set); sets_done = set(); cat_rows = Counter(); spots = set()
        recent = []          # (day, code)
        wasted = 0; total = 0; first_cats = set()
        for day in range(1, days + 1):
            if day > 1 and (day - 1) % 7 == 0:
                items += make_household(rng, ASSUME["new_items_per_week"], mix)
                weights += [1.0 / (len(weights) // 4 + 1) ** ASSUME["zipf_s"]] * ASSUME["new_items_per_week"]
            w = [1.0 / (rank.get(i, i) + 1) ** ASSUME["zipf_s"] if i in rank else weights[i] for i in range(len(items))]
            new_today = 0
            for _ in range(scans_per_day):
                recent = [(d, c) for d, c in recent if d > day - 7]
                rc = Counter(c for _, c in recent)
                for _try in range(6):
                    i = rng.choices(range(len(items)), weights=w)[0]
                    if rc[items[i]["code"]] == 0 or rng.random() > ASSUME["novelty_reject"]:
                        break
                it = items[i]
                prev = rc[it["code"]]
                mult = rescan_multiplier(prev)
                total += 1; wasted += mult == 0
                recent.append((day, it["code"]))
                if it["code"] not in seen_codes:
                    new_today += 1
                seen_codes.add(it["code"])
                stem = next(s for (c, s) in stems_all if c == it["cat"] and it["name"].endswith(s))
                stems.add((it["cat"], stem)); names.add(it["name"]); rar.add(it["rarity"]); first_cats.add(it["cat"])
                cat_rows[it["cat"]] += 1
                if it["fam"]:
                    fams_seen.add(it["fam"]); fam_distinct[it["fam"]].add(it["code"])
                    if len(fam_distinct[it["fam"]]) >= lore[it["fam"]]["set_count"]:
                        sets_done.add(it["fam"])
            for sid, rule in deep_rules.items():
                if sum(cat_rows[c] for c in rule["categories"]) >= rule["need"]:
                    spots.add(sid)
            m = curves
            m["distinct_barcodes"][day].append(len(seen_codes))
            m["new_barcodes_today"][day].append(new_today)
            m["codex_stems"][day].append(len(stems))
            m["display_names"][day].append(len(names))
            m["rarity_tiers"][day].append(len(rar))
            m["legendary_seen"][day].append(int("legendary" in rar))
            m["families_seen"][day].append(len(fams_seen))
            m["family_sets"][day].append(len(sets_done))
            m["deep_spots"][day].append(len(spots))
            m["categories"][day].append(len(first_cats))
            m["wasted_share"][day].append(wasted / max(1, total))
            m["shelf_lv1_full"][day].append(int(min(6, len(seen_codes)) >= 6))
    return curves, len(stems_all)


def completion():
    hr("B2. 완성 곡선 — 하루 3 / 6 / 10 스캔, 가구 바코드 분포(가정) 시뮬레이션")
    print("가정(ASSUME):", ASSUME)
    print("카테고리 분포: data/balance/economy.json scan.assumed_category_mix (그 파일 스스로 '근거가 가장 약한 숫자'로 표시)")
    print("도감 = /api/codex 와 같은 '이름 줄기' 기준. 스팟 = server.RUMOR_RULES_DEEP(중복 스캔도 센다). 가문 세트 = family_lore set_count(서로 다른 바코드 수, 미구현 기능을 구현됐다고 치고 계산)")
    days = 120
    n = 60 if QUICK else 200
    totals = {"codex_stems": 33, "display_names": 330, "rarity_tiers": 5, "families_seen": 18, "family_sets": 18,
              "deep_spots": 6, "categories": 9}
    for spd in (3, 6, 10):
        curves, n_stems = simulate(spd, days, n, seed=spd)
        print(f"\n── 하루 {spd}회 (가구 {n}개 평균) ──")
        cols = [1, 3, 7, 14, 30, 60, 90, 120]
        print("지표                 | " + " ".join(f"{d:>6d}일" for d in cols) + " | 50%  80%  100% 도달일(중앙값)")
        for key in ("distinct_barcodes", "new_barcodes_today", "codex_stems", "display_names", "rarity_tiers",
                    "legendary_seen", "families_seen", "family_sets", "deep_spots", "categories", "wasted_share"):
            vals = [statistics.mean(curves[key][d]) for d in cols]
            fmt = (lambda v: f"{v:7.0%}") if key in ("wasted_share", "legendary_seen") else (lambda v: f"{v:7.1f}")
            reach = ""
            if key in totals:
                tot = totals[key]
                out = []
                for frac in (0.5, 0.8, 1.0):
                    per = []
                    for hidx in range(n):
                        dd = next((d for d in range(1, days + 1) if curves[key][d][hidx] >= frac * tot - 1e-9), None)
                        per.append(dd if dd is not None else 10 ** 6)
                    med = statistics.median(per)
                    out.append(f"{int(med):>4d}" if med < 10 ** 6 else " >120")
                reach = " ".join(out) + f"   (전체 {tot})"
            print(f"  {key:19s}| " + " ".join(fmt(v) for v in vals) + " | " + reach)
        # 새로움이 끝나는 날
        nb = [statistics.mean(curves["new_barcodes_today"][d]) for d in range(1, days + 1)]
        roll = [statistics.mean(nb[max(0, i - 6):i + 1]) for i in range(len(nb))]
        d_lt1 = next((i + 1 for i, v in enumerate(roll) if v < 1.0), None)
        cs = [statistics.mean(curves["codex_stems"][d]) for d in range(1, days + 1)]
        d_codex = next((i + 1 for i in range(7, len(cs)) if cs[i] - cs[i - 7] < 0.5), None)
        print(f"  → 새 바코드가 하루 1개 아래로 떨어지는 날(7일 평균): {d_lt1}일 | 도감 줄기가 일주일에 0.5칸도 안 느는 첫 날: {d_codex}일")


def api_diff():
    hr("검수 규칙 (사) — 서버 API − 본 화면(/base: base.js·m5map.js·life.js·movement.js·rooms.js)이 부르는 API")
    with open(os.path.join(ROOT, "server.py"), encoding="utf-8") as f:
        srv = set(re.findall(r'@app\.(?:get|post)\("(/api/[^"]*)"', f.read()))
    cli = set()
    for fn in ("base.js", "m5map.js", "life.js", "movement.js", "rooms.js"):
        p = os.path.join(ROOT, "static", fn)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                cli |= set(re.findall(r"/api/[a-z/_]+", f.read()))
    old = set()
    with open(os.path.join(ROOT, "static", "app.js"), encoding="utf-8") as f:
        old |= set(re.findall(r"/api/[a-z/_]+", f.read()))
    for a in sorted(srv - cli):
        print(f"  {a:22s} 본 화면 미호출" + ("  (옛 화면 / 에서만 호출)" if a in old else ""))


def main():
    api_diff()
    inventory()
    mapping()
    completion()


if __name__ == "__main__":
    main()
