"""마포·하남 네이버 조회 결과를 apts.json에 같은 형식으로 추가한다."""
import json, math, os, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HF = Path(r"C:\Users\user\Desktop\biz_life\projects\06-home-finder")
sys.path.insert(0, str(HF))
sys.argv = ["x", "stage2", "10억"]
os.chdir(HF)
import requests
from dotenv import load_dotenv
load_dotenv(HF / ".env")
import rank_for_me as R

SP = Path(__file__).parent
A = json.loads((SP / "apts.json").read_text(encoding="utf-8"))
H = json.loads((SP / "hojae.json").read_text(encoding="utf-8"))
MOLIT = {r["cid"] + f"/{r['ak']}": r for r in json.loads((HF / "data/cache/mapo_hanam.json").read_text(encoding="utf-8"))}
NV = json.loads((HF.parent.parent / ".playwright-mcp/naver_mapo_hanam.json").read_text(encoding="utf-8"))
AREA = {"11440-4801": 60, "11440-4772": 60, "11440-107": 60, "11440-69": 85, "11440-67": 85, "11440-125": 78,
        "11440-4503": 85, "11440-5919": 60, "41450-382": 85, "41450-426": 60, "41450-304": 60, "41450-206": 85,
        "41450-184": 85, "41450-8": 85, "41450-187": 85, "41450-185": 85, "41450-200": 85}

s = requests.Session()
s.headers.update({"Authorization": "KakaoAK " + os.environ["KAKAO_REST_API_KEY"],
                  "KA": "sdk/1.0 os/javascript origin/http://localhost:8006", "Origin": "http://localhost:8006"})
kc_path = R.CACHE / "kakao_living.json"
kc = json.loads(kc_path.read_text(encoding="utf-8"))


def m(a, b):
    p = math.pi / 180
    (x1, y1), (x2, y2) = a, b
    h = math.sin((y2 - y1) * p / 2) ** 2 + math.cos(y1 * p) * math.cos(y2 * p) * math.sin((x2 - x1) * p / 2) ** 2
    return 12742000 * math.asin(math.sqrt(h))


W = {"높음": 1.0, "중간": 0.6, "낮음": 0.25}
have = {a["cn"] for a in A}
added = []
for cid, v in NV.items():
    if cid.startswith("_") or "cn" not in v or v["cn"] in have or not v["n"]:
        print("skip", cid, v.get("nn"), v.get("err"), v.get("n"))
        continue
    mo = MOLIT[f"{cid}/{AREA[cid]}"]
    asks = [a for a in v["a"] if a[0]]

    def not_low(a):
        f = str(a[1]).split("/")[0]
        return f in ("중", "고") or (f.isdigit() and int(f) >= 3)

    pool = [a for a in asks if not_low(a)] or asks
    mv = [a for a in pool if R.tenancy(a[3]) != "tenant"]
    tn = [a for a in pool if R.tenancy(a[3]) == "tenant"]
    best_mv = min(mv, key=lambda a: a[0]) if mv else None
    best_tn = min(tn, key=lambda a: a[0]) if tn else None
    rep = min(pool, key=lambda a: a[0])
    region = "서울 마포구" if cid.startswith("11440") else "경기 하남시"
    c = {"region": region, "regulated": True, "complex": mo["cx"], "dong": mo["dong"], "area_m2": AREA[cid],
         "built": mo["built"], "trades_12m": mo["n"], "ref_price": int(mo["ref"] * 1e8),
         "last_prices": [int(p * 1e8) for p in mo["last"]]}
    liv = R.kakao_living(v["x"], v["y"], s, kc)
    km = R.haversine_km((v["x"], v["y"]), R.SEOUL_CITY_HALL)
    sc = R.score_listing(c, liv, rep[0], km)
    sw = s.get("https://dapi.kakao.com/v2/local/search/category.json", params={
        "category_group_code": "SW8", "x": v["x"], "y": v["y"], "radius": 2000, "sort": "distance"}).json().get("documents", [])
    own = next((cl for cl in v["cl"] if cl[0] == v["cn"]), None)
    near = [cl for cl in v["cl"] if m((v["x"], v["y"]), (cl[1], cl[2])) <= 500 and (cl[3] or 0) >= 100]
    hh = own[3] if own else None
    hh500 = sum(cl[3] for cl in near)
    scale = "대단지" if (hh or 0) >= 1000 else "대단지권" if hh500 >= 5000 else "중형 밀집" if hh500 >= 2500 else "소규모" if (hh or 0) < 300 else "보통"
    mvp, tp = (best_mv[0] if best_mv else None), (best_tn[0] if best_tn else None)
    tot = min(R.total_cost(p) for p in (mvp, tp) if p)
    if tot > 10e8:
        print("over budget", v["nn"], round(tot / 1e8, 2))
        continue
    o = dict(cn=v["cn"], name=v["nn"], region=region, dong=mo["dong"], area=AREA[cid], built=mo["built"],
             x=v["x"], y=v["y"], tier="8억" if tot <= 8e8 else "10억", score=sc["score"], ref=mo["ref"], last=mo["last"],
             movein=round(mvp / 1e8, 2) if mvp else None, tenant=round(tp / 1e8, 2) if tp else None,
             movein_total=round(R.total_cost(mvp) / 1e8, 2) if mvp else None,
             tenant_total=round(R.total_cost(tp) / 1e8, 2) if tp else None,
             note=rep[3], movein_note=best_mv[3] if best_mv else "",
             station=sw[0]["place_name"] if sw else None, subway=int(sw[0]["distance"]) if sw else None,
             univ=liv.get("univ_hospital"), univ_m=liv.get("univ_hospital_m"), park_m=liv.get("park_m"),
             wh=liv.get("warehouse"), wh_m=liv.get("warehouse_m"), seoul_km=round(km, 1),
             hh=hh, hh500=hh500, scale=scale, trades=mo["n"], extra_region=True)
    hits, bonus = [], 0
    for h in H:
        d, lab = min((m((o["x"], o["y"]), (p["x"], p["y"])), p["label"]) for p in h["pts"])
        if d <= h["radius"]:
            e = h["mag"] * W[h["cert"]] * (1 - 0.5 * d / h["radius"]); bonus += e
            hits.append(dict(id=h["id"], name=h["name"], stop=lab, d=int(d), year=h["year"], cert=h["cert"],
                             kind=h["kind"], closer=bool(h["line"] and o["subway"] and d < o["subway"] - 150), e=round(e, 1)))
    o["hj"], o["hj_bonus"] = sorted(hits, key=lambda x: -x["e"]), round(min(15, bonus), 1)
    o["score_dev"] = round(o["score"] + o["hj_bonus"], 1)
    A.append(o); added.append(o)

kc_path.write_text(json.dumps(kc, ensure_ascii=False), encoding="utf-8")
(SP / "apts.json").write_text(json.dumps(A, ensure_ascii=False), encoding="utf-8")
print("added", len(added))
for o in sorted(added, key=lambda o: -o["score"]):
    print(f"{o['score']:5.1f} {o['tier']} {o['region']} {o['name']} {o['area']}㎡ {o['built']} | 입주 {o['movein']} 세낀 {o['tenant']} 실거래 {o['ref']} {o['last']} | "
          f"역 {o['station']} {o['subway']} 대학병원 {o['univ']} {o['univ_m']} 공원 {o['park_m']} 창고 {o['wh']} {o['wh_m']} | "
          f"{o['hh']}세대 500m {o['hh500']} {o['scale']} | 호재 {[(h['name'], h['d']) for h in o['hj']]} | {o['movein_note'] or o['note']}")
