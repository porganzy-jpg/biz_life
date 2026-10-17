import sys, json, statistics
from pathlib import Path
import pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\Users\user\Desktop\biz_life\projects\06-home-finder"); NEW = Path(sys.argv[1])
codes = json.loads((ROOT/"data/cache/region_codes.json").read_text(encoding="utf-8")); codes["경기 과천시"] = "41290"
ZONES = {"중부": ["종로구","중구","용산구"], "서부": ["마포구","서대문구","은평구"],
         "동부": ["성동구","광진구","동대문구","중랑구","강동구"], "남부": ["영등포구","동작구","관악구","구로구","금천구"],
         "강남3구": ["서초구","강남구","송파구"]}
MAGOK_DONGS = {"마곡동","가양동","내발산동","외발산동","공항동","방화동","등촌동"}
reg2zone = {f"서울 {g}": z for z, gs in ZONES.items() for g in gs}
reg2zone["경기 과천시"] = "과천"; reg2zone["경기 하남시"] = "하남"; reg2zone["서울 강서구"] = "마곡"
files = {}
for p in (ROOT/"data/cache/molit").glob("아파트_*.csv"): files[p.name] = p
for p in NEW.glob("아파트_*.csv"): files[p.name] = p
c2r = {v: k for k, v in codes.items()}
fr = []
for name, p in files.items():
    code = name.split("_")[1]; r = c2r.get(code)
    if r not in reg2zone: continue
    d = pd.read_csv(p, encoding="utf-8-sig", dtype=str); d["region"] = r; fr.append(d)
df = pd.concat(fr, ignore_index=True)
df = df[df["해제여부"].fillna("None").isin(["None","","nan"]) & (df["거래유형"].fillna("") != "직거래")]
df = df[~((df.region == "서울 강서구") & ~df["법정동"].str.strip().isin(MAGOK_DONGS))]
df["price"] = df["거래금액"].str.replace(",","").astype(int)*10000
df["area"] = df["전용면적"].astype(float); df["akey"] = df["area"].round(0).astype(int)
df["ym"] = df["계약년도"].astype(int)*100 + df["계약월"].astype(int); df["day"] = df["계약일"].astype(int)
df["built"] = pd.to_numeric(df["건축년도"], errors="coerce")
df = df[df.ym >= 202510]
df = df.drop_duplicates(["단지일련번호","akey","ym","day","층","price"])
df["zone"] = df.region.map(reg2zone)
print("실거래", len(df), "건", df.groupby("zone").size().to_dict())
def tc(p):
    e = p/1e8; b = 0.01 if e <= 6 else ((e*2/3-3)/100 if e <= 9 else 0.03); return p*(1+b*1.1+0.007)
rows = []
for (region, cid, ak), g in df.groupby(["region","단지일련번호","akey"]):
    if ak < 55 or ak > 100 or len(g) < 3: continue
    g = g.sort_values(["ym","day"])
    rec = g[g.ym >= 202606]
    if len(rec) < 1 or len(g[g.ym >= 202604]) < 2: continue
    ref = int(statistics.median(g.tail(3).price)); cost = tc(ref)
    if cost > 14.2e8 or ref < 5e8: continue
    old = g[g.ym <= 202603]; new = g[g.ym >= 202607]
    mom = new.price.median()/old.price.median()-1 if len(old) >= 2 and len(new) >= 1 else None
    built = int(g.built.max()) if g.built.notna().any() else None
    rows.append(dict(zone=reg2zone[region], region=region, cid=cid, name=g["단지명"].iloc[-1], jibun=str(g["지번"].iloc[-1]), dong=g["법정동"].iloc[-1].strip(),
        area=ak, built=built, n12=len(g), ref=ref/1e8, cost=round(cost/1e8,2), last=[round(x/1e8,2) for x in g.tail(3).price],
        lastd=int(g.ym.iloc[-1]), mom=round(mom,3) if mom is not None else None))
c = pd.DataFrame(rows)
def tier(cost): return "A ≤9억" if cost <= 9.0 else ("B 9~11억" if cost <= 11.2 else "C 11~14억")
c["tier"] = c.cost.map(tier)
def pre(r):
    s = 35*min(1, max(0, (r.built or 1985)-1990)/30) + 15*min(1, max(0, r.area-55)/30) + 20*min(1, r.n12/15)
    if r.mom is not None: s += 15*min(1, max(0, 0.10 - r.mom)/0.20)   # 덜 오른 곳 가점(추격 매수 회피)
    s += 15*(1 if r.cost <= 9 else 0.6 if r.cost <= 11.2 else 0.3)
    return round(s,1)
c["pre"] = c.apply(pre, axis=1)
c = c.sort_values("pre", ascending=False).drop_duplicates(["cid"])
print(c.groupby(["zone","tier"]).size().unstack(fill_value=0))
# 구역 × 등급별 상위 → 네이버 조회 대상
pick = c.groupby(["zone","tier"]).head(4)
pick = pick[pick.zone != "강남3구"]
pick.to_json(NEW.parent/"zone_pick.json", orient="records", force_ascii=False, indent=0)
c.to_json(NEW.parent/"zone_all.json", orient="records", force_ascii=False, indent=0)
print(len(pick))
for _, r in pick.sort_values(["zone","tier","pre"], ascending=[True,True,False]).iterrows():
    print(f"{r.zone:4} {r.tier:8} {r['name'][:14]:14} {r.dong:5} {r.area}㎡ {r.built} 기준{r.ref:.2f} 총{r.cost} 거래{r.n12} 추세{r.mom} {r['pre']}")
