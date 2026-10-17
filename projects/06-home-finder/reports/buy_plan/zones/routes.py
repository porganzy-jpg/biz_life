"""universe_scored.json → 세 갈래별 후보 순위 (호가 확인 전 추정 단계).

가격대(평당 호가 × 공급평으로 추정한 매매가):
  ① 대출 없이 바로 입주   ≤ 7.8억  (총비용 8억 이하)
  ② 세 낀 집              7.8~10억 (연 1억 저축 · 실거주 유예 조건에서의 상한)
  ③ 바로 입주 + 대출 6억  10~13.4억 (총비용 14억 이하)
84㎡가 들어가는 가장 높은 가격대를 우선, 84㎡가 13.4억을 넘으면 59㎡로 본다.
사용: python routes.py <작업폴더>  → <작업폴더>/routes.json
"""
import sys, json
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
WORK = Path(sys.argv[1])
U = json.load(open(WORK / "universe_scored.json", encoding="utf-8"))
cl = lambda v: max(0.0, min(1.0, v))
BANDS = [("①", 0, 7.8), ("②", 7.8, 10.0), ("③", 10.0, 13.4)]


def band(p):
    return next((b for b, lo, hi in BANDS if lo < p <= hi), None)


def score(u, area):
    L = u["liv"]
    pk = cl(1 - ((L["park_m"] or 2000) - 200) / 1000)
    hp = cl(L["hospitals_1km"] / 10)
    mt = cl(1 - ((L["mart_m"] or 3000) - 300) / 1700)
    ce = cl(L["cafes_500m"] / 15)
    bh = 0.6 * cl(1 - ((L.get("univ_hospital_m") or 10000) - 2000) / 6000) + 0.4 * cl(1 - ((L.get("gen_hospital_m") or 5000) - 1500) / 3500)
    wh = cl(1 - ((L.get("warehouse_m") or 10000) - 2000) / 6000)
    living = 0.25 * pk + 0.15 * hp + 0.20 * bh + 0.15 * mt + 0.10 * wh + 0.15 * ce
    home = 0.6 * cl((u["built"] - 1995) / 27) + 0.25 * cl((area - 55) / 30) + 0.15 * cl((u["hh"] - 300) / 1200)
    transit = 0.65 * cl(1 - ((L["subway_m"] or 2500) - 300) / 1500) + 0.35 * cl(1 - (u["km"] - 5) / 20)
    gap = u["gap"] if u["gap"] is not None else 0.05
    price = cl((0.12 - gap) / 0.17)                       # 호가가 최근 실거래보다 덜 높을수록
    far = cl((300 - (u["far"] or 250)) / 120)             # 용적률 낮을수록 쾌적
    parts = {"living": living, "home": home, "transit": transit, "price": price, "far": far}
    W = {"living": 32, "home": 25, "transit": 20, "price": 15, "far": 8}
    return round(sum(W[k] * v for k, v in parts.items()), 1), {k: round(v * 100) for k, v in parts.items()}


out = []
for u in U:
    for area, est in ((84, u["e84"]), (59, u["e59"])):
        b = band(est)
        if b:
            sc, parts = score(u, area)
            out.append({**u, "route": b, "area": area, "est": est, "score": sc, "parts": parts})
            break
out.sort(key=lambda r: (r["route"], -r["score"]))
json.dump(out, open(WORK / "routes.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
for b, _, _ in BANDS:
    rs = [r for r in out if r["route"] == b]
    print(f"== {b} {len(rs)}곳 (84㎡ {sum(r['area']==84 for r in rs)} · 59㎡ {sum(r['area']==59 for r in rs)})")
    for r in rs[:22]:
        L = r["liv"]
        print(f"  {r['score']:5.1f} {r['zone']} {r['gu'][:3]} {r['dong'][:4]:4} {r['name'][:14]:14} {r['area']}㎡ 추정{r['est']:5.2f} {r['built']} {r['hh']}세대 용적{r['far']} 갭{r['gap']} 역{L['subway_m']} 대병{L.get('univ_hospital_m')} cn{r['cn']}")
