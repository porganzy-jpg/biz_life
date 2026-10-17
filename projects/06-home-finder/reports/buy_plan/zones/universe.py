"""세 갈래(① 대출 없이 · ② 세 낀 집 · ③ 바로 입주+대출) 후보 전체 — 네이버 단지 묶음(naver_universe.json) 기반.

1) 300세대 이상 · 2000년 이후 · 평당 호가로 추정한 59㎡ 가격이 13.4억 이하
2) 카카오 좌표→주소로 이름·구를 붙이고 관심 권역 구만 남김
3) 카카오 생활환경(rank_for_me.kakao_living) + 점수
사용: python universe.py <작업폴더>   → <작업폴더>/universe_scored.json
"""
import sys, os, json
from pathlib import Path
WORK = Path(sys.argv[1])
sys.argv = [sys.argv[0], "stage1", "10억"]
ROOT = Path(r"C:\Users\user\Desktop\biz_life\projects\06-home-finder"); sys.path.insert(0, str(ROOT))
import rank_for_me as R
import requests
from dotenv import load_dotenv
sys.stdout.reconfigure(encoding="utf-8")
load_dotenv(ROOT / ".env")
PW = Path(r"C:\Users\user\Desktop\biz_life\.playwright-mcp")
r = json.load(open(PW / "naver_universe.json", encoding="utf-8")); r = json.loads(r) if isinstance(r, str) else r
GU = {"종로구": "중부", "중구": "중부", "용산구": "중부", "마포구": "서부", "서대문구": "서부", "은평구": "서부",
      "성동구": "동부", "광진구": "동부", "동대문구": "동부", "중랑구": "동부", "강동구": "동부",
      "영등포구": "남부", "동작구": "남부", "관악구": "남부", "구로구": "남부", "금천구": "남부", "하남시": "하남"}
MAGOK = {"마곡동", "가양동", "내발산동", "외발산동", "공항동", "방화동", "등촌동"}
s = requests.Session()
s.headers.update({"Authorization": "KakaoAK " + os.environ["KAKAO_REST_API_KEY"],
                  "KA": "sdk/1.0 os/javascript origin/http://localhost:8006", "Origin": "http://localhost:8006"})
kpath = ROOT / "data/cache/kakao_living.json"; kc = json.loads(kpath.read_text(encoding="utf-8"))
out = []
cands = [(cn, v) for cn, v in r["out"].items()
         if (v.get("hh") or 0) >= 300 and v.get("ppy") and v.get("d") and int(v["d"][:4]) >= 2000
         and v["ppy"] * 25 / 1e8 <= 13.4]
print("후보", len(cands))
for i, (cn, v) in enumerate(cands):
    d = s.get("https://dapi.kakao.com/v2/local/geo/coord2address.json", params={"x": v["x"], "y": v["y"]}, timeout=10).json().get("documents", [])
    if not d: continue
    ad = d[0]["address"]; ra = d[0].get("road_address") or {}
    gu = ad["region_2depth_name"].split(" ")[-1] if ad["region_1depth_name"] != "경기" else ad["region_2depth_name"]
    dong = ad["region_3depth_name"]
    zone = "마곡" if gu == "강서구" and dong in MAGOK else GU.get(gu)
    if not zone: continue
    liv = R.kakao_living(v["x"], v["y"], s, kc)
    km = R.haversine_km((v["x"], v["y"]), R.SEOUL_CITY_HALL)
    y = int(v["d"][:4])
    e59, e84 = round(v["ppy"] * 25 / 1e8, 2), round(v["ppy"] * 33.5 / 1e8, 2)
    gap = round(v["med"] / v["real"] - 1, 3) if v.get("med") and v.get("real") else None
    out.append({"cn": int(cn), "name": ra.get("building_name") or "", "addr": ad["address_name"], "gu": gu, "dong": dong, "zone": zone,
                "x": v["x"], "y": v["y"], "built": y, "hh": v["hh"], "far": v.get("far"), "e59": e59, "e84": e84,
                "base_supply": v.get("bs"), "med": (v.get("med") or 0) / 1e8, "real": (v.get("real") or 0) / 1e8, "gap": gap,
                "jeonse_ratio": v.get("wr"), "liv": liv, "km": round(km, 1)})
    if i % 40 == 0:
        print(i, len(out), flush=True); kpath.write_text(json.dumps(kc, ensure_ascii=False), encoding="utf-8")
kpath.write_text(json.dumps(kc, ensure_ascii=False), encoding="utf-8")
json.dump(out, open(WORK / "universe_scored.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("권역 안", len(out))
