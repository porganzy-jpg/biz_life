"""
'내가 살 집' 랭킹 — 재택근무 · 총예산 5~8억 · 6개월 내 매수 프로필.

단계
  stage1  실거래 캐시(data/cache/molit) → 단지×평형별 '적정가' 기준선 + 1차 후보
          → data/cache/apt_shortlist.json  (브라우저 단계에서 네이버 현재 호가 조회)
  stage2  네이버 호가(data/cache/naver_listings.json) + 카카오 생활환경 → 최종 점수
          → data/cache/final_apartments.json

기준선은 '최근 6개월 중개거래의 중앙값'이 아니라 '최근 거래 3건 중앙값'을 쓴다.
2026년 서울은 월 단위로 오르는 중이라 6개월 중앙값은 현재가를 체계적으로 낮게 잡는다.

사용: python rank_for_me.py stage1|stage2 [8억|10억]
  8억   총 8억 · 6개월 내 입주 가능 매물만 대표가로
  10억  총 10억 · 생애최초(규제지역도 LTV 70%) · 세입자 낀 매물도 허용
        (2026.10.1 시행: 토허구역 세 낀 주택 실거주 유예 — 무주택자, 최장 2029년 말 입주)
"""
import sys
import json
import math
import statistics
from pathlib import Path
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd

ROOT = Path(__file__).parent
CACHE = ROOT / "data" / "cache"
MOLIT = CACHE / "molit"

# ── 프로필 ─────────────────────────────────────────────
PROFILES = {
    "8억": {"budget_max": 8_0000_0000, "budget_min": 4_0000_0000,
            "first_time": False, "allow_tenant": False, "cash": None, "per_region": 4},
    "10억": {"budget_max": 10_0000_0000, "budget_min": 6_0000_0000,
             "first_time": True, "allow_tenant": True, "cash": 8_0000_0000, "per_region": 3},
}
PROFILE_NAME = sys.argv[2] if len(sys.argv) > 2 else "8억"
P = PROFILES[PROFILE_NAME]
TAG = "" if PROFILE_NAME == "8억" else "_10억"      # 8억은 기존 파일명 유지

BUDGET_MAX = P["budget_max"]      # 부대비용 포함 총액 상한
BUDGET_MIN = P["budget_min"]      # 너무 싼 물건(입지·노후 문제 가능성)은 제외
MIN_EXCLUSIVE_M2 = 55             # 재택 작업공간 확보 — 59㎡형부터
RECENT_FROM = (2026, 4)           # '최근 6개월' 시작

# 2025.10.15 대책 규제지역(서울 전역 + 경기 12곳): LTV 40%(생애최초 70%), 토허·2년 실거주
REGULATED_GG = {
    "과천시", "광명시", "성남시 분당구", "성남시 수정구", "성남시 중원구",
    "수원시 영통구", "수원시 장안구", "수원시 팔달구", "안양시 동안구",
    "용인시 수지구", "의왕시", "하남시",
}


def is_regulated(region: str) -> bool:
    sido, name = region.split(" ", 1)
    return sido == "서울" or (sido == "경기" and name in REGULATED_GG)


def acquisition_tax_rate(price: int) -> float:
    """1주택(무주택자 취득) 취득세+지방교육세 근사. 85㎡ 이하 농특세 없음."""
    eok = price / 1_0000_0000
    if eok <= 6:
        base = 0.01
    elif eok <= 9:
        base = (eok * 2 / 3 - 3) / 100   # 6~9억 구간 선형(1%→3%)
    else:
        base = 0.03
    return base * 1.1                     # 지방교육세 ≒ 취득세의 10%


def total_cost(price: int) -> int:
    """매수가 + 취득세 + 중개보수(0.4%) + 법무·채권 등(0.3%)."""
    return int(price * (1 + acquisition_tax_rate(price) + 0.004 + 0.003))


# ── stage1 ────────────────────────────────────────────
def load_apartments() -> pd.DataFrame:
    codes = json.loads((CACHE / "region_codes.json").read_text(encoding="utf-8"))
    code2region = {v: k for k, v in codes.items()}
    frames = []
    for p in MOLIT.glob("아파트_*.csv"):
        code = p.stem.split("_")[1]
        df = pd.read_csv(p, encoding="utf-8-sig", dtype=str)
        df["region"] = code2region.get(code, code)
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df = df[df["해제여부"].fillna("None").isin(["None", "", "nan"])]       # 취소된 거래 제외
    df = df[df["거래유형"].fillna("") != "직거래"]                           # 가족간 증여성 직거래 제외
    df["price"] = df["거래금액"].str.replace(",", "").astype(int) * 10000
    df["area"] = df["전용면적"].astype(float)
    df["ym"] = df["계약년도"].astype(int) * 100 + df["계약월"].astype(int)
    df["day"] = df["계약일"].astype(int)
    df["built"] = pd.to_numeric(df["건축년도"], errors="coerce")
    df["floor"] = pd.to_numeric(df["층"], errors="coerce")
    df["area_key"] = df["area"].round(0).astype(int)
    return df


def stage1():
    df = load_apartments()
    print(f"아파트 실거래 {len(df):,}건 · 지역 {df['region'].nunique()}곳 · 기간 {df['ym'].min()}~{df['ym'].max()}")
    recent_ym = RECENT_FROM[0] * 100 + RECENT_FROM[1]

    # 지역 × 연식대 평당가 중앙값 (가성비 기준)
    df["age_band"] = (df["built"] // 10 * 10).fillna(0).astype(int)
    df["ppm2"] = df["price"] / df["area"]
    band_med = df[df["ym"] >= recent_ym].groupby(["region", "age_band"])["ppm2"].median().to_dict()

    rows = []
    for (region, cid, akey), g in df.groupby(["region", "단지일련번호", "area_key"]):
        if akey < MIN_EXCLUSIVE_M2 or len(g) < 3:
            continue
        g = g.sort_values(["ym", "day"])
        recent = g[g["ym"] >= recent_ym]
        if len(recent) < 2:
            continue
        last3 = g.tail(3)
        ref = int(statistics.median(last3["price"]))
        cost = total_cost(ref)
        # 호가는 보통 실거래보다 높게 나와 있으므로 기준선이 상한에 붙은 단지는 미리 제외
        if not (BUDGET_MIN <= ref and cost <= BUDGET_MAX * 1.03):
            continue
        older = g[g["ym"] < recent_ym]
        trend = (recent["price"].median() / older["price"].median() - 1) if len(older) >= 2 else None
        built = int(g["built"].max()) if g["built"].notna().any() else None
        age_band = (built // 10 * 10) if built else 0
        bm = band_med.get((region, age_band))
        rows.append({
            "region": region,
            "regulated": is_regulated(region),
            "complex_id": cid,
            "complex": g["단지명"].iloc[-1],
            "dong": g["법정동"].iloc[-1],
            "jibun": g["지번"].iloc[-1],
            "area_m2": akey,
            "built": built,
            "trades_12m": len(g),
            "trades_6m": len(recent),
            "ref_price": ref,
            "ref_total_cost": cost,
            "last_trade": f"{int(g['ym'].iloc[-1])}{int(g['day'].iloc[-1]):02d}",
            "last_prices": [int(x) for x in last3["price"]],
            "trend_6m": round(trend, 4) if trend is not None else None,
            "value_vs_band": round(ref / akey / bm - 1, 4) if bm else None,
        })

    cand = pd.DataFrame(rows)
    print(f"예산·평형·거래량 통과 단지×평형: {len(cand):,}")

    # 1차 점수 — 네이버 조회 대상을 줄이기 위한 거친 필터(최종 점수 아님)
    def pre_score(r):
        s = 0.0
        s += 30 * min(1, max(0, (r.built or 1985) - 1985) / 35)                 # 연식
        s += 20 * min(1, max(0, r.area_m2 - 55) / 30)                           # 평형(85㎡ 만점)
        s += 15 * min(1, r.trades_12m / 15)                                     # 환금성
        if r.value_vs_band is not None:
            s += 20 * min(1, max(0, 0.15 - r.value_vs_band) / 0.30)             # 같은 지역·연식 대비 싸면 가점
        if r.trend_6m is not None:
            s += 15 * min(1, max(0, r.trend_6m + 0.05) / 0.15)                  # 하락 중인 단지는 감점
        return round(s, 1)

    cand["pre_score"] = cand.apply(pre_score, axis=1)
    # 한 단지에서 평형은 최고점 1개만, 지역별 상위 4단지 → 지역 다양성 확보
    cand = cand.sort_values("pre_score", ascending=False).drop_duplicates(["region", "complex_id"])
    short = cand.groupby("region").head(P["per_region"]).sort_values("pre_score", ascending=False)
    out = short.to_dict("records")
    (CACHE / f"apt_shortlist{TAG}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"네이버 호가 조회 대상: {len(out)}개 단지 (지역 {short['region'].nunique()}곳)")
    for r in out[:15]:
        print(f"  {r['pre_score']:5.1f} {r['region']:12s} {r['complex'][:14]:14s} {r['area_m2']}㎡ "
              f"{r['built']} 기준 {r['ref_price']/1e8:.2f}억 거래{r['trades_12m']} 추세{r['trend_6m']}")


# ── stage2 ────────────────────────────────────────────
# 재택근무자 기준 가중치(합 100). 출퇴근이 없으니 교통 비중을 낮추고 생활환경·가격을 올렸다.
WEIGHTS = {
    "price": 30,     # 호가 vs 실거래 기준선, 예산 여유
    "living": 25,    # 공원·종합병원·창고형마트·마트·카페 접근성
    "home": 20,      # 연식·평형
    "transit": 15,   # 지하철·서울 도심 거리(가끔 외출용)
    "cash": 10,      # 필요 자기자본(규제지역 LTV 40% vs 비규제 70%) — 10억 프로필은 남는 현금
}
LOAN_CAP = 6_0000_0000            # 6.27 대책: 수도권 주담대 최대 6억
SEOUL_CITY_HALL = (126.9779, 37.5663)


def loan_limit(price: int, regulated: bool, first_time: bool = False) -> int:
    ltv = 0.70 if (not regulated or first_time) else 0.40
    return min(int(price * ltv), LOAN_CAP)


def kakao_living(x: float, y: float, session, cache: dict) -> dict:
    """카카오 로컬로 반경 내 생활시설을 센다. 키는 JS 키라 등록 도메인 헤더가 필요."""
    key = f"{x:.5f},{y:.5f}"
    if key in cache and "univ_hospital_m" in cache[key]:
        return cache[key]
    base = "https://dapi.kakao.com/v2/local/search"

    def nearest(queries, radius, cats):
        """카카오 업종(category_name)이 cats 중 하나로 끝나는 가장 가까운 곳.
        이름 매칭은 '동물종합병원', '페인트트레이더스' 같은 오탐이 많아 업종으로만 판정한다."""
        best = None
        for q in queries:
            for page in (1, 2, 3):
                r = session.get(f"{base}/keyword.json", params={
                    "query": q, "x": x, "y": y, "radius": radius, "sort": "distance", "page": page}, timeout=10).json()
                hit = next((d for d in r.get("documents", [])
                            if d.get("category_name", "").endswith(cats) and "예정" not in d["place_name"]), None)
                if hit:
                    if not best or int(hit["distance"]) < best[0]:
                        best = (int(hit["distance"]), hit["place_name"])
                    break
                if r.get("meta", {}).get("is_end", True):
                    break
        return best or (None, None)

    if key in cache:                                   # 예전 캐시: 추가 항목만 채운다
        out = cache[key]
    else:
        out = None

    def cat(code, radius):
        r = session.get(f"{base}/category.json", params={
            "category_group_code": code, "x": x, "y": y, "radius": radius, "sort": "distance"}, timeout=10).json()
        docs = r.get("documents", [])
        return r.get("meta", {}).get("total_count", 0), (int(docs[0]["distance"]) if docs else None)

    def kw(q, radius):
        r = session.get(f"{base}/keyword.json", params={
            "query": q, "x": x, "y": y, "radius": radius, "sort": "distance"}, timeout=10).json()
        docs = [d for d in r.get("documents", []) if q in d.get("category_name", "")]
        return len(docs), (int(docs[0]["distance"]) if docs else None), (docs[0]["place_name"] if docs else None)

    if out is None:
        sw_n, sw_d = cat("SW8", 2000)
        hp_n, _ = cat("HP8", 1000)
        mt_n, mt_d = cat("MT1", 2000)
        ce_n, _ = cat("CE7", 500)
        pk_n, pk_d, pk_name = kw("공원", 1000)
        out = {"subway_m": sw_d, "hospitals_1km": hp_n, "mart_m": mt_d, "cafes_500m": ce_n,
               "parks_1km": pk_n, "park_m": pk_d, "park_name": pk_name}
    # 사용자 요청(2026-10-01): 대학·종합병원, 창고형 마트 접근성
    out["univ_hospital_m"], out["univ_hospital"] = nearest(["대학병원", "대학교병원"], 10000, ("병원 > 대학병원",))
    out["gen_hospital_m"], out["gen_hospital"] = nearest(["종합병원"], 5000, ("병원 > 종합병원", "병원 > 대학병원"))
    out["warehouse_m"], out["warehouse"] = nearest(
        ["트레이더스", "코스트코"], 10000, ("대형마트 > 트레이더스 홀세일 클럽", "대형마트 > 코스트코코리아"))
    cache[key] = out
    return out


TENANT_WORDS = ("전세안고", "세안고", "세끼고", "전세끼고", "갭투", "갭으로", "GAP", "임대중", "만기")
VACANT_WORDS = ("즉시입주", "입주가능", "빠른입주", "빠른이사", "이사협의", "공실", "주인거주", "실입주")


MOVE_IN_DEADLINE = (2027, 3)      # 오늘(2026-10) + 6개월


def tenancy(note: str) -> str:
    """매물 설명으로 입주 가능 여부 추정: vacant / tenant / unknown.

    '세안고 … 27년 8월 입주가능'처럼 두 신호가 같이 있으면 세입자 쪽을 믿는다.
    설명에 적힌 입주 시점이 기한(6개월)보다 늦으면 세입자 있는 것으로 본다.
    """
    import re
    n = (note or "").replace(" ", "")
    for yy, mm in re.findall(r"(2[6-9])[년.](1[0-2]|0?[1-9])월?", n):
        if (2000 + int(yy), int(mm)) > MOVE_IN_DEADLINE:
            return "tenant"
    if any(w in n for w in TENANT_WORDS):
        return "tenant"
    if any(w in n for w in VACANT_WORDS):
        return "vacant"
    return "unknown"


def haversine_km(a, b):
    (x1, y1), (x2, y2) = a, b
    p = math.pi / 180
    h = math.sin((y2 - y1) * p / 2) ** 2 + math.cos(y1 * p) * math.cos(y2 * p) * math.sin((x2 - x1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def clamp01(v):
    return max(0.0, min(1.0, v))


def score_listing(c: dict, liv: dict, best_ask: int, seoul_km: float) -> dict:
    # 가격: 호가가 기준선보다 낮을수록, 총비용이 상한보다 여유 있을수록
    gap = best_ask / c["ref_price"] - 1                       # +면 실거래보다 비싸게 나옴
    cost = total_cost(best_ask)
    p = 0.7 * clamp01((0.10 - gap) / 0.15) + 0.3 * clamp01((BUDGET_MAX - cost) / 2_0000_0000)
    # 생활: 공원 200m·의원 10곳·마트 300m·카페 15곳·종합병원 1.5km·창고형 2km를 만점 기준으로
    pk = clamp01(1 - ((liv["park_m"] or 2000) - 200) / 1000)
    hp = clamp01(liv["hospitals_1km"] / 10)
    mt = clamp01(1 - ((liv["mart_m"] or 3000) - 300) / 1700)
    ce = clamp01(liv["cafes_500m"] / 15)
    # 대학병원 2km 이내 만점·8km 0점 60% + 종합병원 1.5km 이내 만점·5km 0점 40%
    bh = 0.6 * clamp01(1 - ((liv.get("univ_hospital_m") or 10000) - 2000) / 6000) \
        + 0.4 * clamp01(1 - ((liv.get("gen_hospital_m") or 5000) - 1500) / 3500)
    wh = clamp01(1 - ((liv.get("warehouse_m") or 10000) - 2000) / 6000)
    lv = 0.25 * pk + 0.15 * hp + 0.20 * bh + 0.15 * mt + 0.10 * wh + 0.15 * ce
    # 집: 2010년 이후·85㎡ 근접
    hm = 0.6 * clamp01(((c["built"] or 1985) - 1990) / 30) + 0.4 * clamp01((c["area_m2"] - 55) / 30)
    # 교통: 역 800m 이내·서울시청 30km 이내면 만점 쪽
    tr = 0.6 * clamp01(1 - ((liv["subway_m"] or 2500) - 300) / 1500) + 0.4 * clamp01(1 - (seoul_km - 10) / 30)
    need = cost - loan_limit(best_ask, c["regulated"], P["first_time"])
    if P["cash"]:   # 현금이 정해진 프로필: 쓰고 남는 현금(비상금)이 많을수록
        ca = clamp01((P["cash"] - need) / P["cash"])
    else:           # 필요 현금 2억 이하 만점, 5억 이상 0
        ca = clamp01((5_0000_0000 - need) / 3_0000_0000)
    parts = {"price": p, "living": lv, "home": hm, "transit": tr, "cash": ca}
    total = sum(WEIGHTS[k] * v for k, v in parts.items())
    return {"score": round(total, 1), "parts": {k: round(v * 100) for k, v in parts.items()},
            "ask_gap": round(gap, 4), "ask_total_cost": cost, "cash_needed": need}


def stage2():
    import os
    import requests
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    short = {r["complex_id"]: r for r in json.loads((CACHE / f"apt_shortlist{TAG}.json").read_text(encoding="utf-8"))}
    naver = {}   # 국토부 단지ID → 네이버 조회결과. 프로필과 무관하게 모든 배치를 합친다.
    pw = ROOT.parent.parent / ".playwright-mcp"
    for p in sorted(pw.glob("naver_batch*.json")) + sorted(pw.glob("naver_p10_*.json")):
        naver.update({k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items() if not k.startswith("_")})

    s = requests.Session()
    s.headers.update({"Authorization": "KakaoAK " + os.environ["KAKAO_REST_API_KEY"],
                      "KA": "sdk/1.0 os/javascript origin/http://localhost:8006",
                      "Origin": "http://localhost:8006"})
    kcache_path = CACHE / "kakao_living.json"
    kcache = json.loads(kcache_path.read_text(encoding="utf-8")) if kcache_path.exists() else {}

    final, unchecked = [], []
    for cid, c in short.items():
        nv = naver.get(cid)
        if not nv or "cn" not in nv:
            unchecked.append(c)
            continue
        if not nv["n"]:
            continue                                   # 해당 평형 매물 없음
        # 1층·저층 할인 매물은 최저가를 왜곡하므로 '3층 이상' 최저가를 대표 호가로
        asks = [a for a in nv["a"] if a[0]]
        def not_low(a):
            f = str(a[1]).split("/")[0]                # '8', '중', '고', '저', 'B1'
            return f in ("중", "고") or (f.isdigit() and int(f) >= 3)
        mid = [a for a in asks if not_low(a)]
        pool = mid or asks                             # 중층 이상이 없으면 저층이라도 쓰되 표시
        low_only = not mid
        # 6개월 내 실거주가 목표 → 세입자 낀 매물보다 입주 가능한 매물을 대표가로.
        # (규제지역은 2년 실거주 의무라 세 낀 매물은 사실상 매수 불가)
        movein = [a for a in pool if tenancy(a[3]) != "tenant"]
        best_movein = min(movein, key=lambda a: a[0]) if movein else None
        if P["allow_tenant"]:                          # 세 낀 매물도 후보 — 가장 싼 것이 대표가
            rep = min(pool, key=lambda a: a[0])
        else:
            rep = best_movein or min(pool, key=lambda a: a[0])
        rep_tenancy = tenancy(rep[3])
        if total_cost(rep[0]) > BUDGET_MAX:
            continue
        liv = kakao_living(nv["x"], nv["y"], s, kcache)
        km = haversine_km((nv["x"], nv["y"]), SEOUL_CITY_HALL)
        sc = score_listing(c, liv, rep[0], km)
        if rep_tenancy == "tenant" and not P["allow_tenant"]:   # 입주 가능한 매물이 하나도 없는 단지
            sc["score"] = round(sc["score"] - 10, 1)
        final.append({**c, **sc, "naver_complex": nv["cn"], "naver_name": nv.get("nn"),
                      "listings_same_area": nv["n"], "listings_total": nv["total"],
                      "best_ask": rep[0], "best_ask_floor": rep[1], "best_ask_dir": rep[2],
                      "best_ask_note": rep[3], "best_ask_date": rep[4], "article_no": rep[5],
                      "low_floor_only": low_only, "tenancy": rep_tenancy,
                      "movein_listings": len([a for a in asks if tenancy(a[3]) != "tenant"]),
                      "best_movein": best_movein[:6] if best_movein else None,
                      "all_asks": [[a[0], a[1]] for a in asks], "living": liv, "seoul_km": round(km, 1),
                      "url": f"https://fin.land.naver.com/complexes/{nv['cn']}?tab=article&tradeTypes=A1"})
    kcache_path.write_text(json.dumps(kcache, ensure_ascii=False), encoding="utf-8")

    final.sort(key=lambda r: r["score"], reverse=True)
    (CACHE / f"final_apartments{TAG}.json").write_text(json.dumps(final, ensure_ascii=False, indent=1), encoding="utf-8")
    (CACHE / f"unchecked_apartments{TAG}.json").write_text(json.dumps(unchecked, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"호가 확인·예산 내: {len(final)}개 / 호가 미확인: {len(unchecked)}개")
    for r in final[:20]:
        print(f"{r['score']:5.1f} {r['region']:12s} {r['complex'][:13]:13s} {r['area_m2']}㎡ {r['built']} "
              f"호가 {r['best_ask']/1e8:.2f}억({r['best_ask_floor']}) 기준 {r['ref_price']/1e8:.2f}억 "
              f"갭{r['ask_gap']*100:+.1f}% 현금{r['cash_needed']/1e8:.2f}억 {r['parts']}")


if __name__ == "__main__":
    {"stage1": stage1, "stage2": stage2}[sys.argv[1] if len(sys.argv) > 1 else "stage1"]()
