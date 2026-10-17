"""서울시 정비사업 추진현황(열린데이터광장 OA-22856, 분기 갱신 엑셀) → 구역 좌표 → ../redev.json

엑셀은 data.seoul.go.kr 데이터셋 페이지의 '파일내려받기'(nio_download.do POST, infId=OA-22856, seq=파일번호)로 받는다.
사용: python redev.py <엑셀 경로>
"""
import sys, os, json
from pathlib import Path
import pandas as pd, requests
from dotenv import load_dotenv
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\Users\user\Desktop\biz_life\projects\06-home-finder"); BP = ROOT / "reports/buy_plan"
load_dotenv(ROOT / ".env")
d = pd.read_excel(sys.argv[1], header=None).iloc[4:]
COLS = {2: "gu", 3: "name", 4: "jibun", 5: "road", 6: "pub", 7: "jaechok", 8: "kind", 9: "stage", 10: "old_hh",
        11: "designated", 13: "committee", 14: "union", 15: "review", 16: "approval", 18: "mgmt", 20: "move_start", 22: "start", 23: "new_hh"}
d = d[list(COLS)].rename(columns=COLS).dropna(subset=["gu", "name"])
s = requests.Session()
s.headers.update({"Authorization": "KakaoAK " + os.environ["KAKAO_REST_API_KEY"],
                  "KA": "sdk/1.0 os/javascript origin/http://localhost:8006", "Origin": "http://localhost:8006"})
import re


def norm(a):
    """'갈현동300' → '갈현동 300', '서계동33번지일대' → '서계동 33', '대조동88,89' → '대조동 88'."""
    if not isinstance(a, str): return None
    a = re.sub(r"(번지)?\s*일대.*$", "", a).replace("번지", "")
    a = re.split(r"[,~외(]", a)[0].strip()
    return re.sub(r"([동가])(\d)", r"\1 \2", a, count=1)


out, miss = [], []
for _, r in d.iterrows():
    hit = None
    for q in (f"서울 {r.gu} {norm(r.jibun)}", f"서울 {r.gu} {norm(r.road)}"):
        if q.endswith("None"): continue
        docs = s.get("https://dapi.kakao.com/v2/local/search/address.json", params={"query": q}, timeout=10).json().get("documents", [])
        if docs: hit = docs[0]; break
    if not hit:                       # 착공 후 철거로 지번이 사라진 구역 — 장소 이름으로 찾되 같은 구만
        for q in (f"{r['name']}구역", f"{r.gu} {r['name']} 재개발", f"{r.gu} {r['name']} 재건축"):
            docs = s.get("https://dapi.kakao.com/v2/local/search/keyword.json", params={"query": q}, timeout=10).json().get("documents", [])
            docs = [x for x in docs if r.gu in x.get("address_name", "")]
            if docs: hit = docs[0]; break
    if not hit: miss.append(f"{r.gu} {r['name']}"); continue
    dt = lambda v: None if pd.isna(v) else str(v)[:10]
    out.append({"gu": r.gu, "name": str(r["name"]), "kind": str(r.kind), "stage": str(r.stage), "pub": str(r.pub),
                "x": float(hit["x"]), "y": float(hit["y"]),
                "new_hh": int(r.new_hh) if not pd.isna(r.new_hh) else 0, "old_hh": int(r.old_hh) if not pd.isna(r.old_hh) else 0,
                "designated": dt(r.designated), "union": dt(r.union), "approval": dt(r.approval), "mgmt": dt(r.mgmt), "start": dt(r.start)})
json.dump(out, open(BP / "redev.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("구역", len(out), "좌표 못 찾음", len(miss), miss[:10])
import collections
print(collections.Counter(o["stage"] for o in out)); print(collections.Counter(o["kind"] for o in out))
