import sys, os, json
from pathlib import Path
sys.argv = [sys.argv[0], "stage1", "10억"] + sys.argv[1:]
ROOT = Path(r"C:\Users\user\Desktop\biz_life\projects\06-home-finder"); sys.path.insert(0, str(ROOT))
import rank_for_me as R
import requests, pandas as pd
from dotenv import load_dotenv
load_dotenv(ROOT/".env")
SCR = Path(sys.argv[3])
s = requests.Session()
s.headers.update({"Authorization": "KakaoAK "+os.environ["KAKAO_REST_API_KEY"], "KA": "sdk/1.0 os/javascript origin/http://localhost:8006", "Origin": "http://localhost:8006"})
kpath = ROOT/"data/cache/kakao_living.json"; kc = json.loads(kpath.read_text(encoding="utf-8"))
c = pd.read_json(SCR/"zone_pick.json"); c = c[c.zone != "강남3구"]
out = []
for _, r in c.iterrows():
    sido = "서울특별시" if r.region.startswith("서울") else "경기도"
    q = f"{sido} {r.region.split(' ',1)[1]} {r.dong} {r.jibun}"
    d = s.get("https://dapi.kakao.com/v2/local/search/address.json", params={"query": q}, timeout=10).json().get("documents", [])
    if not d: print("no geo", q); continue
    x, y = float(d[0]["x"]), float(d[0]["y"])
    liv = R.kakao_living(x, y, s, kc)
    km = R.haversine_km((x, y), R.SEOUL_CITY_HALL)
    cpl = {"ref_price": int(r.ref*1e8), "built": r.built, "area_m2": r.area, "regulated": True}
    sc = R.score_listing(cpl, liv, int(r.ref*1e8), km)   # 호가 대신 기준가로 → price 항목은 예산 여유만 반영
    out.append({**r.to_dict(), "x": x, "y": y, "liv": liv, "km": round(km,1), "score": sc["score"], "parts": sc["parts"]})
kpath.write_text(json.dumps(kc, ensure_ascii=False), encoding="utf-8")
json.dump(out, open(SCR/"zone_scored.json","w",encoding="utf-8"), ensure_ascii=False, indent=0)
for zone in ["중부","서부","동부","남부","마곡","하남"]:
    print("\n==", zone)
    for o in sorted([o for o in out if o["zone"]==zone], key=lambda o: -o["score"]):
        L=o["liv"]
        print(f'{o["score"]:5.1f} {o["tier"]:8} {o["name"][:13]:13} {o["dong"]:4} {o["area"]}㎡ {o["built"]} 기준{o["ref"]:.2f} 총{o["cost"]} 추세{o["mom"]} 역{L["subway_m"]} 공원{L["park_m"]} 대학병원{L.get("univ_hospital_m")}({(L.get("univ_hospital") or "")[:8]}) 창고{L.get("warehouse_m")} 시청{o["km"]}km')
