import os, sys, json, time, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
from PublicDataReader import TransactionPrice
ROOT = Path(r"C:\Users\user\Desktop\biz_life\projects\06-home-finder")
OUT = Path(sys.argv[1])
load_dotenv(ROOT / ".env")
api = TransactionPrice(os.environ["PUBLIC_DATA_API_KEY"])
codes = json.loads((ROOT/"data/cache/region_codes.json").read_text(encoding="utf-8"))
apts = json.load(open(ROOT/"reports/buy_plan/apts.json", encoding="utf-8"))
regions = sorted({a["region"] for a in apts})
jobs = [("아파트", codes[r], ym) for r in regions for ym in ("202608", "202609", "202610")]
land_regions = ["경기 의정부시", "경기 고양시 덕양구", "경기 용인시 수지구"]
jobs += [("토지", codes[r], ym) for r in land_regions for ym in ("202609", "202610")]
bad = 0
for prop, code, ym in jobs:
    p = OUT / f"{prop}_{code}_{ym}.csv"
    if p.exists(): continue
    for attempt in range(3):
        try:
            df = api.get_data(property_type=prop, trade_type="매매", sigungu_code=code, year_month=ym)
        except Exception as e:
            df = None
        if df is not None and not df.empty:
            df.to_csv(p, index=False, encoding="utf-8-sig"); break
        time.sleep(2)
    else:
        bad += 1; print("empty", prop, code, ym)
print("done, empty:", bad, "of", len(jobs))
