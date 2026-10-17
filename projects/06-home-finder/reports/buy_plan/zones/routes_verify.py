"""routes.json(추정) + 네이버 실제 매물(naver_routes_*.json) → 실제 호가로 세 갈래 재배정 → <작업폴더>/routes_verified.json"""
import sys, json
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
WORK = Path(sys.argv[1]); PW = Path(r"C:\Users\user\Desktop\biz_life\.playwright-mcp")
def lj(p):
    r = json.load(open(p, encoding="utf-8")); return json.loads(r) if isinstance(r, str) else r
nv = {**lj(PW / "naver_routes_a.json"), **lj(PW / "naver_routes_b.json")}
R = {r["cn"]: r for r in json.load(open(WORK / "routes.json", encoding="utf-8"))}
def tc(p):
    b = 0.01 if p <= 6 else ((p*2/3-3)/100 if p <= 9 else 0.03); return round(p*(1+b*1.1+0.007), 2)
out = []
for cn, v in nv.items():
    if not isinstance(v, dict) or not v["m"]: continue
    r = R[int(cn)]
    low = lambda f: str(f).split("/")[0] in ("1", "2", "저")
    mv = [m for m in v["m"] if m[3] == "M"]; tn = [m for m in v["m"] if m[3] == "T"]
    mv_mid = [m for m in mv if not low(m[1])] or mv
    bm = min(mv_mid, key=lambda m: m[0]) if mv_mid else None
    bt = min(tn, key=lambda m: m[0]) if tn else None
    routes = []
    if bm and tc(bm[0]) <= 8.0: routes.append("①")
    if bt and tc(bt[0]) <= 10.4: routes.append("②")
    if bm and 8.0 < tc(bm[0]) <= 14.0: routes.append("③")
    out.append({**{k: r[k] for k in ("cn", "zone", "gu", "dong", "x", "y", "built", "hh", "far", "gap", "jeonse_ratio", "liv", "km", "score", "parts", "area")},
                "name": v["name"] or r["name"], "listings": v["n"], "supply": v["sup"], "excl": v["ex"],
                "movein": bm[0] if bm else None, "movein_floor": bm[1] if bm else None, "movein_note": bm[2] if bm else "",
                "movein_total": tc(bm[0]) if bm else None, "tenant": bt[0] if bt else None, "tenant_floor": bt[1] if bt else None,
                "tenant_note": bt[2] if bt else "", "tenant_no": bt[4] if bt else None, "tenant_total": tc(bt[0]) if bt else None,
                "est_route": r["route"], "routes": routes})
json.dump(out, open(WORK / "routes_verified.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
for b in ("①", "②", "③"):
    rs = sorted([o for o in out if b in o["routes"]], key=lambda o: -o["score"])
    print(f"== {b} {len(rs)}곳")
    for o in rs:
        L = o["liv"]
        print(f"  {o['score']:5.1f} {o['zone']} {o['gu'][:3]} {o['name'][:16]:16} {o['area']}㎡ {o['built']} {o['hh']}세대 입주{o['movein']}({o['movein_floor']}) 세낀{o['tenant']} 총{o['movein_total'] if b!='②' else o['tenant_total']} 매물{o['listings']} 역{L['subway_m']} 대병{L.get('univ_hospital_m')} 용적{o['far']} 갭{o['gap']}")
print("no route:", [(o["name"], o["movein"], o["tenant"]) for o in out if not o["routes"]])
