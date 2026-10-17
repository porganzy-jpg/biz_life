"""routes.json · zone.json 보강: 건폐율·주차·전용률·전용 평당가, 세 낀 매물 상세, 주변 정비사업(redev.json).

입력: ../routes.json, ../zone.json, ../redev.json, .playwright-mcp/naver_routes_eff.json(단지 정보·세 낀 매물 상세), naver_eff_*.json
'세 갈래 후보' 점수(100) = 생활환경 28 · 집 20 · 교통 17 · 호가/실거래 13 · 실평수(전용률) 6 · 용적률 6 · 건폐율 3 · 주변 정비사업 7
사용: python enrich.py
"""
import json, math, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
BP = Path(__file__).resolve().parent.parent
PW = Path(r"C:\Users\user\Desktop\biz_life\.playwright-mcp")


def lj(p):
    r = json.load(open(p, encoding="utf-8")); return json.loads(r) if isinstance(r, str) else r


cl = lambda v: max(0.0, min(1.0, v))
RE = lj(BP / "redev.json")
STAGE_W = {"구역지정": .3, "추진위": .3, "조합설립": .5, "건축심의": .6, "사업시행": .7, "관리처분": .85, "착공": 1.0}
RADIUS = 1500


def km(a, b):
    (x1, y1), (x2, y2) = a, b
    p = math.pi / 180
    h = math.sin((y2 - y1) * p / 2) ** 2 + math.cos(y1 * p) * math.cos(y2 * p) * math.sin((x2 - x1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def redev_near(x, y):
    """반경 1.5km 정비구역. 100m 안의 재건축 구역은 단지 자신으로 본다."""
    near, own, s = [], None, 0.0
    for z in RE:
        d = round(km((x, y), (z["x"], z["y"])) * 1000)
        if d > RADIUS: continue
        if d <= 100 and "재건축" in z["kind"]:
            own = {k: z[k] for k in ("name", "kind", "stage", "new_hh")}; continue
        near.append({"name": z["name"], "kind": z["kind"].replace("주택정비형 ", "").replace("도시정비형 ", "도심 ").replace("공동주택", "").replace("아파트지구", "").replace("단독주택", "단독 "),
                     "stage": z["stage"], "new_hh": z["new_hh"], "d": d})
        s += STAGE_W.get(z["stage"], .3) * min(1, (z["new_hh"] or 300) / 1000) * (1 - d / RADIUS)
    near.sort(key=lambda z: z["d"])
    return {"near": near[:6], "n": len(near), "new_hh": sum(z["new_hh"] for z in near),
            "started": sum(z["stage"] in ("착공", "관리처분") for z in near), "own": own, "s": round(min(1, s / 1.5), 3)}


def months_until(d, close=(2026, 12)):
    return max(0, (int(d[:4]) - close[0]) * 12 + int(d[5:7]) - close[1])


# ── 세 갈래 후보 ──
eff = lj(PW / "naver_routes_eff.json")
CX, AR = eff["cx"], eff["ar"]
routes = json.load(open(BP / "routes.json", encoding="utf-8"))
for r in routes:
    c = CX.get(str(r["cn"]), {})
    r["name"] = c.get("name") or r["name"]
    for k in ("bcr", "park", "dongs"):
        r[k] = c.get(k)
    r["far"] = c.get("far") or r["far"]
    r["top_floor"] = c.get("hi")
    r["excl_ratio"] = round(r["excl"] / r["supply"], 3) if r.get("supply") and r.get("excl") else None
    best = min(x for x in (r["movein"], r["tenant"]) if x is not None)
    r["ppy"] = round(best * 1e4 / ((r.get("excl") or r["area"]) / 3.3058))
    t = AR.get(str(r.get("tenant_no")))
    if t:
        mv = t.get("mv")
        r["ten"] = {"dep": t["dep"] or None, "rent": t["rent"] or 0, "mv": mv, "months": months_until(mv) if mv else None,
                    "lease_start": f"{int(mv[:4]) - 2}-{mv[5:7]}" if mv else None,
                    "eligible": None if not mv else f"{int(mv[:4]) - 2}-{mv[5:7]}" <= "2026-05",
                    "old_lease": None if not mv else f"{int(mv[:4]) - 2}-{mv[5:7]}" <= "2025-06",
                    "total": r["tenant_total"], "price": r["tenant"]}
    r["redev"] = redev_near(r["x"], r["y"])
    p = r["parts"]
    extra = {"excl": round(100 * cl(((r["excl_ratio"] or 0.76) - 0.70) / 0.12)),
             "bcr": round(100 * cl((30 - (r["bcr"] or 22)) / 15)),
             "redev": round(100 * r["redev"]["s"])}
    r["parts"] = {**{k: p[k] for k in ("living", "home", "transit", "price", "far")}, **extra}
    W = {"living": 28, "home": 20, "transit": 17, "price": 13, "excl": 6, "far": 6, "bcr": 3, "redev": 7}
    r["score"] = round(sum(W[k] * r["parts"][k] / 100 for k in W), 1)
json.dump(routes, open(BP / "routes.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)

# ── 관심 권역 ──
ze = {**lj(PW / "naver_eff_a.json"), **lj(PW / "naver_eff_b.json"), **lj(PW / "naver_eff_c.json")}
zone = json.load(open(BP / "zone.json", encoding="utf-8"))
for z in zone:
    e = ze.get(str(z["cn"])) or {}
    z["bcr"], z["park"] = e.get("bcr") or None, e.get("park")
    z["redev"] = redev_near(z["x"], z["y"])
json.dump(zone, open(BP / "zone.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)

for r in sorted(routes, key=lambda r: -r["redev"]["s"])[:12]:
    rd = r["redev"]
    print(f"{r['name'][:14]:14} 정비{rd['s']:.2f} {rd['n']}곳 착공·관리처분{rd['started']} 신규{rd['new_hh']} 자체{rd['own']} 가까운:{[(z['name'], z['stage'], z['d']) for z in rd['near'][:2]]}")
print("자체 재건축 구역:", [(r["name"], r["redev"]["own"]) for r in routes if r["redev"]["own"]])
print("세 낀 상세:", [(r["name"], r["ten"]["dep"], r["ten"]["mv"], r["ten"]["eligible"]) for r in routes if r.get("ten")])
