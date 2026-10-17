"""관심 권역 탭 데이터: 권역 후보 점수(zone_scored.json) + 네이버 호가·전세 → ../zone.json

사용: python merge.py <작업폴더>   (작업폴더 = stage1.py·living.py 결과가 있는 곳)
네이버 결과는 브라우저에서 받아 .playwright-mcp/naver_zone_a.json, naver_zone_b.json, naver_1017.json 으로 저장해 둔다.
"""
import json, sys, re
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
SCR = Path(sys.argv[1]); PW = Path(r"C:\Users\user\Desktop\biz_life\.playwright-mcp")
BP = Path(r"C:\Users\user\Desktop\biz_life\projects\06-home-finder\reports\buy_plan")
def lj(p):
    r = json.load(open(p, encoding="utf-8")); return json.loads(r) if isinstance(r, str) else r
nv = {**lj(PW/"naver_zone_a.json"), **lj(PW/"naver_zone_b.json")}
alias = {"방화 e편한세상": "대림e-편한세상", "망우 금호어울림": "금호어울림(580)"}
nv = {alias.get(k, k): v for k, v in nv.items() if isinstance(v, dict)}
# 연 저축 1억 가정에서 열리는 '바로 입주 + 대출 6억' 후보(11~13억대) — naver_ctier.json, 전세 호가는 없음
CTIER_SKIP = {"마곡수명산파크3단지"}                     # 최저 호가 14억으로 상한 밖
for k, v in lj(PW/"naver_ctier.json").items():
    if isinstance(v, dict) and k not in CTIER_SKIP:
        nv[k] = {"cn": v["cn"], "nn": v["nn"], "A1": {"n": len(v["m"]), "m": v["m"]}, "B1": {"n": 0, "m": []}}
scored = {o["name"]: o for o in json.load(open(SCR/"zone_scored.json", encoding="utf-8"))}
TEN = re.compile(r"세\s?안고|세\s?끼고|승계|갭|월세안고|임대")
def tc(p):
    b = 0.01 if p <= 6 else ((p*2/3-3)/100 if p <= 9 else 0.03); return round(p*(1+b*1.1+0.007), 2)
out = []
for name, v in nv.items():
    o = scored.get(name)
    if not o: print("no score", name); continue
    ms = v["A1"]["m"]; mv = [m for m in ms if not TEN.search(m[2])]; tn = [m for m in ms if TEN.search(m[2])]
    bm = min(mv, key=lambda m: m[0]) if mv else None; bt = min(tn, key=lambda m: m[0]) if tn else None
    js = sorted(m[0] for m in v["B1"]["m"] if m[0])
    L = o["liv"]
    best = min([x[0] for x in (bm, bt) if x])
    out.append({"cn": v["cn"], "name": name, "nname": v["nn"], "zone": o["zone"], "region": o["region"], "dong": o["dong"],
        "area": o["area"], "built": o["built"], "x": o["x"], "y": o["y"], "score": o["score"], "ref": o["ref"], "last": o["last"],
        "trades": o["n12"], "mom": o["mom"], "movein": bm[0] if bm else None, "movein_total": tc(bm[0]) if bm else None,
        "movein_floor": bm[1] if bm else None, "movein_note": bm[2] if bm else "",
        "tenant": bt[0] if bt else None, "tenant_total": tc(bt[0]) if bt else None, "note": bt[2] if bt else "",
        "jeonse": js[0] if js else None, "listings": v["A1"]["n"],
        "subway": L["subway_m"], "park_m": L["park_m"], "univ_m": L.get("univ_hospital_m"), "univ": L.get("univ_hospital"),
        "wh_m": L.get("warehouse_m"), "wh": L.get("warehouse"), "seoul_km": o["km"],
        "gap": round(best/o["ref"]-1, 3), "best_total": tc(best)})
# 10/17 기존 후보 재조회(naver_1017)에 있던 권역 안 단지 — 생활환경은 apts.json 값을 쓴다
EXTRA = {119598: "남부", 18689: "마곡", 25872: "마곡", 1024: "마곡"}
old = {a["cn"]: a for a in json.load(open(BP/"apts.json", encoding="utf-8"))}
n17 = lj(PW/"naver_1017.json")
for cn, zone in EXTRA.items():
    a = old[cn]; ms = n17[str(cn)]["m"]
    sc = scored.get(a["name"])
    mv = [m for m in ms if not TEN.search(m[2])]; tn = [m for m in ms if TEN.search(m[2])]
    bm = min(mv, key=lambda m: m[0]) if mv else None; bt = min(tn, key=lambda m: m[0]) if tn else None
    best = min([x[0] for x in (bm, bt) if x])
    out.append({"cn": cn, "name": a["name"], "nname": a["name"], "zone": zone, "region": a["region"], "dong": a["dong"],
        "area": a["area"], "built": a["built"], "x": a["x"], "y": a["y"], "score": sc["score"] if sc else a["score"],
        "ref": a["ref"], "last": a["last"], "trades": a["trades"], "mom": sc["mom"] if sc else None,
        "movein": bm[0] if bm else None, "movein_total": tc(bm[0]) if bm else None, "movein_floor": bm[1] if bm else None,
        "movein_note": bm[2] if bm else "", "tenant": bt[0] if bt else None, "tenant_total": tc(bt[0]) if bt else None,
        "note": bt[2] if bt else "", "jeonse": None, "listings": n17[str(cn)]["n"],
        "subway": a["subway"], "park_m": a["park_m"], "univ_m": a["univ_m"], "univ": a["univ"], "wh_m": a["wh_m"], "wh": a["wh"],
        "seoul_km": a["seoul_km"], "gap": round(best/a["ref"]-1, 3), "best_total": tc(best)})
for r in out:
    r["mom"] = None if r["mom"] is None or r["mom"] != r["mom"] else r["mom"]     # NaN → null

# ── 효율 지표(용적률·전용률·전용 평당가)와 세 낀 매물 계산 ──
# naver_eff_*.json: 단지 정보(용적률·세대수) + 세 낀 매물 상세(기존 보증금·입주가능일). 브라우저에서 받는다.
eff = {**lj(PW/"naver_eff_a.json"), **lj(PW/"naver_eff_b.json"), **lj(PW/"naver_eff_c.json")}
CASH, EXIT_LOAN, RATE = 8.0, 1.0, 0.03 * (1 - 0.154)     # 현금 8억, 퇴거자금 대출 1억, 예금 3% 세후
CLOSE = (2026, 12)                                        # 계약·잔금을 12월로 가정


def months_until(d):
    y, m = int(d[:4]), int(d[5:7])
    return max(0, (y - CLOSE[0]) * 12 + m - CLOSE[1])


for r in out:
    e = eff.get(str(r["cn"])) or {}
    r["far"] = e.get("far") or None
    r["hh"] = e.get("hh")
    r["top_floor"] = e.get("hi")
    if e.get("supply"):
        r["excl_ratio"] = round(e["excl"] / e["supply"], 3)
        r["supply"] = e["supply"]
    best = min(x for x in (r["movein"], r["tenant"]) if x is not None)
    r["ppy"] = round(best * 1e4 / (r["area"] / 3.3058))     # 전용 평당가(만원)
    tens = []
    for t in e.get("ten", []):
        dep = t["dep"] or None
        dep_src = "매물 정보" if dep else None
        if not dep and r.get("jeonse"):
            dep, dep_src = r["jeonse"], "전세 호가로 추정"
        total = tc(t["price"])
        mv = t.get("mv")
        if not mv:                                            # 설명의 '27년7월입주' 같은 문구로 보완
            m = re.search(r"(2[6-9])\s*[년.]\s*(1[0-2]|0?[1-9])\s*월", t["desc"])
            mv = f"20{m.group(1)}-{int(m.group(2)):02d}-15" if m else None
        mon = months_until(mv) if mv else None
        start = f"{int(mv[:4]) - 2}-{mv[5:7]}" if mv else None    # 2년 계약 가정
        x = {"price": t["price"], "floor": t["floor"], "desc": t["desc"], "no": t["no"], "dep": dep, "dep_src": dep_src,
             "rent": t["rent"] or 0, "mv": mv, "months": mon, "lease_start": start, "total": total,
             "eligible": None if not start else start <= "2026-05",            # 실거주 유예: 2026.5.12 당시 임대 중
             "old_lease": None if not start else start <= "2025-06"}           # 퇴거자금 대출 종전 기준
        if dep:
            cash_now = round(total - dep, 2)
            x["cash_now"] = cash_now
            x["return_ok"] = CASH - cash_now + EXIT_LOAN >= dep
            if mon is not None:
                # 바로 입주와 비교한 이득 = 보증금만큼 돈을 늦게 내는 효과(무이자 차입)
                x["interest"] = round(dep * RATE * mon / 12, 2)
                x["rent_income"] = round(x["rent"] * mon / 1e4, 2)
        x["discount"] = round(r["movein"] - t["price"], 2) if r["movein"] is not None else None
        x["benefit"] = round((x["discount"] or 0) + x.get("interest", 0) + x.get("rent_income", 0), 2) if dep else None
        tens.append(x)
    r["ten"] = tens
json.dump(out, open(BP/"zone.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
for z in ["중부","서부","동부","남부","마곡","하남"]:
    print("==", z)
    for r in sorted([r for r in out if r["zone"]==z], key=lambda r: r["gap"]):
        print(f'  {r["name"][:12]:12}({r["nname"][:10]}) {r["area"]}㎡ {r["built"]} 기준{r["ref"]:.2f} {r["last"]} 추세{r["mom"]} | 입주{r["movein"]}({r["movein_floor"]}) 세낀{r["tenant"]} 전세{r["jeonse"]} 매물{r["listings"]} | 호가갭{r["gap"]:+.0%} 총{r["best_total"]} 점수{r["score"]}')
