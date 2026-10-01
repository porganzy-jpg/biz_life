"""
최근 12개월 아파트·토지 매매 실거래를 지역×월 단위 CSV로 캐시한다.

- 시군구 코드는 하드코딩하지 않고 PublicDataReader 공식 법정동 코드표에서 이름으로 찾는다
  (collectors/molit_collector.py 의 과천=41150 / 의정부=41820 오기 같은 실수 방지).
- 이미 받은 (유형, 지역, 월) 파일은 건너뛴다 → 재실행은 신규 월만 받는다.
- 출력: data/cache/molit/{아파트|토지}_{코드}_{YYYYMM}.csv

사용: python fetch_recent_trades.py [--months 12] [--end 202609]
"""
import os
import sys
import argparse
import warnings
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings("ignore")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv
import PublicDataReader as pdr
from PublicDataReader import TransactionPrice

ROOT = Path(__file__).parent
CACHE = ROOT / "data" / "cache" / "molit"

SEOUL = [
    "종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구", "강북구",
    "도봉구", "노원구", "은평구", "서대문구", "마포구", "양천구", "강서구", "구로구", "금천구",
    "영등포구", "동작구", "관악구", "서초구", "강남구", "송파구", "강동구",
]
GYEONGGI = [
    "고양시 덕양구", "고양시 일산동구", "고양시 일산서구", "남양주시", "구리시", "의정부시",
    "김포시", "파주시", "하남시", "광명시", "성남시 수정구", "성남시 중원구", "성남시 분당구",
    "안양시 만안구", "안양시 동안구", "군포시", "의왕시", "용인시 기흥구", "용인시 수지구",
    "용인시 처인구", "수원시 영통구", "수원시 장안구", "수원시 권선구", "수원시 팔달구",
    "화성시", "부천시 원미구", "부천시 소사구", "부천시 오정구", "시흥시", "광주시", "양평군",
    "가평군",
]
INCHEON = ["연수구", "부평구", "서구"]


def resolve_codes() -> dict:
    """{'서울 은평구': '11380', ...} — 현행(말소 안 된) 시군구만."""
    df = pdr.code_bdong()
    df = df[df["말소일자"].fillna("") == ""]
    pairs = df[["시도명", "시군구명", "시군구코드"]].drop_duplicates()

    def find(sido, name):
        hit = pairs[(pairs["시도명"] == sido) & (pairs["시군구명"] == name)]
        if hit.empty:
            raise KeyError(f"{sido} {name} 코드 없음")
        return str(hit.iloc[0]["시군구코드"])

    out = {}
    for n in SEOUL:
        out[f"서울 {n}"] = find("서울특별시", n)
    for n in GYEONGGI:
        out[f"경기 {n}"] = find("경기도", n)
    for n in INCHEON:
        out[f"인천 {n}"] = find("인천광역시", n)
    return out


def month_list(end: str, n: int) -> list:
    y, m = int(end[:4]), int(end[4:])
    out = []
    for _ in range(n):
        out.append(f"{y}{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out[::-1]


def fetch_one(api, prop, code, ym):
    path = CACHE / f"{prop}_{code}_{ym}.csv"
    if path.exists():
        return prop, code, ym, "cached", 0
    try:
        df = api.get_data(property_type=prop, trade_type="매매", sigungu_code=code, year_month=ym)
    except Exception as e:  # 개별 실패는 기록만 하고 다음 실행 때 재시도
        return prop, code, ym, f"ERR {e}", 0
    # PublicDataReader는 429/403 등 실패 시 예외 없이 빈 DataFrame을 돌려준다.
    # 진짜 거래 0건인 달과 구별할 수 없으므로 빈 결과는 캐시하지 않는다(다음 실행 때 재시도).
    if df is None or df.empty:
        return prop, code, ym, "empty", 0
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return prop, code, ym, "ok", len(df)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--end", default="202609")
    ap.add_argument("--workers", type=int, default=1)  # 4개 동시 요청에서 429 다발
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    api = TransactionPrice(os.environ["PUBLIC_DATA_API_KEY"])
    CACHE.mkdir(parents=True, exist_ok=True)

    codes = resolve_codes()
    (ROOT / "data" / "cache" / "region_codes.json").write_text(
        __import__("json").dumps(codes, ensure_ascii=False, indent=1), encoding="utf-8")

    jobs = [(p, c, ym) for p in ("아파트", "토지") for c in codes.values()
            for ym in month_list(args.end, args.months)]
    print(f"지역 {len(codes)}곳 × {args.months}개월 × 2유형 = {len(jobs)}건")

    errors = empties = 0
    with ThreadPoolExecutor(args.workers) as ex:
        futs = [ex.submit(fetch_one, api, *j) for j in jobs]
        for i, f in enumerate(as_completed(futs), 1):
            prop, code, ym, status, n = f.result()
            if status.startswith("ERR"):
                errors += 1
                print(f"  ✗ {prop} {code} {ym}: {status[:120]}")
            elif status == "empty":
                empties += 1
            if i % 100 == 0:
                print(f"  {i}/{len(jobs)} 진행 (오류 {errors}, 빈응답 {empties})", flush=True)
    print(f"완료 — 오류 {errors}건, 빈응답 {empties}건 (빈응답은 429 한도초과일 수 있음 → 재실행 시 재시도)")


if __name__ == "__main__":
    main()
