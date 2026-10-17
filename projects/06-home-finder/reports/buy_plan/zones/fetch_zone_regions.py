import os, sys, json, time, warnings
from pathlib import Path
warnings.filterwarnings("ignore"); sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
from PublicDataReader import TransactionPrice
ROOT = Path(r"C:\Users\user\Desktop\biz_life\projects\06-home-finder"); OUT = Path(sys.argv[1])
load_dotenv(ROOT/".env"); api = TransactionPrice(os.environ["PUBLIC_DATA_API_KEY"])
codes = json.loads((ROOT/"data/cache/region_codes.json").read_text(encoding="utf-8"))
need = ["서울 종로구","서울 중구","서울 용산구","서울 마포구","서울 광진구","서울 동대문구","서울 강동구","서울 서초구","서울 강남구","서울 송파구","서울 성동구","서울 강서구","서울 동작구"]
jobs = [(codes[r], ym) for r in need for ym in ("202608","202609","202610")]
gw = ["2025"+f"{m:02d}" for m in (10,11,12)] + ["2026"+f"{m:02d}" for m in range(1,11)]
jobs += [("41290", ym) for ym in gw]
bad = 0
for code, ym in jobs:
    p = OUT/f"아파트_{code}_{ym}.csv"
    if p.exists(): continue
    for _ in range(3):
        try: df = api.get_data(property_type="아파트", trade_type="매매", sigungu_code=code, year_month=ym)
        except Exception: df = None
        if df is not None and not df.empty: df.to_csv(p, index=False, encoding="utf-8-sig"); break
        time.sleep(2)
    else: bad += 1; print("empty", code, ym)
print("done", len(jobs), "empty", bad)
