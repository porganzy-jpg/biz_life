"""
기존 토지 매물(source=molit_land)에 좌표를 채우는 backfill 스크립트.

지오코딩 소스: OpenStreetMap Nominatim (무료·키 불필요).
  - 카카오 REST 키가 없어도 동작한다. (기존 .env의 KAKAO_REST_API_KEY는 JavaScript 키라 서버 지오코딩 불가)
  - ToS 준수: User-Agent 필수, 1req/1.1s, 결과 캐싱.
지번이 마스킹되어 있으므로 동(洞)/읍면 단위 근사 좌표를 사용한다.

사용: python backfill_land_coords.py
"""
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

import requests
from database import SessionLocal
from models.property import Property

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "HomeFinder-land/1.0 (personal real-estate research)"}

# sggCd 앞 2자리 → 시/도 (질의 정확도 향상용)
CITY_PREFIX = {"서울특별시": "서울", "경기도": "경기도", "인천광역시": "인천"}


def admin_levels(dong):
    """dong 문자열에서 질의 후보를 정밀→근사 순으로 만든다.
    시골: '옥천면 신복리' → ['옥천면 신복리', '옥천면']  (리 실패 시 읍/면 폴백)
    도심: '신림동'         → ['신림동']                  (이미 최소 단위, 폴백 없음)
    """
    dong = (dong or "").strip()
    if not dong:
        return []
    parts = dong.split()
    if len(parts) >= 2:          # '읍면 리' 형태 → 리 제거한 읍/면을 폴백으로
        return [dong, parts[0]]
    return [dong]                # 단일 토큰(동)이면 폴백 없음


def _query_nominatim(query, max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(
                NOMINATIM_URL,
                params={"q": query, "format": "json", "limit": 1, "countrycodes": "kr"},
                headers=HEADERS, timeout=15,
            )
            if r.status_code == 200:
                j = r.json()
                if j:
                    return float(j[0]["lat"]), float(j[0]["lon"])
                return None, None      # 200이지만 결과 없음 → 폴백으로
            time.sleep(attempt * 1.5)
        except Exception:
            time.sleep(attempt * 1.5)
    return None, None


def geocode(city, district, dong, cache):
    """캐시 히트면 즉시 반환(무통신). 미스면 리→읍/면 폴백 사다리로 Nominatim 호출.
    반환: ((lat,lng), api_calls)  — api_calls는 실제 통신 횟수(ToS 딜레이 계산용)."""
    key = (city, district, dong)
    if key in cache:
        return cache[key], 0
    sido = CITY_PREFIX.get(city, "")
    api_calls = 0
    lat = lng = None
    for level in admin_levels(dong):
        sub_key = (city, district, level)      # 읍/면 폴백은 별도 캐시 키로 공유
        if sub_key in cache:
            lat, lng = cache[sub_key]
        else:
            query = f"{sido} {district} {level}".strip()
            lat, lng = _query_nominatim(query)
            cache[sub_key] = (lat, lng)
            api_calls += 1
        if lat is not None:
            break                               # 정밀 단위에서 찾으면 폴백 중단
    cache[key] = (lat, lng)
    return (lat, lng), api_calls


def main():
    db = SessionLocal()
    cache = {}
    try:
        rows = (db.query(Property)
                .filter(Property.source == "molit_land", Property.lat.is_(None))
                .all())
        print(f"좌표 없는 토지 매물: {len(rows)}건")
        filled = 0
        for i, p in enumerate(rows, 1):
            (lat, lng), api_calls = geocode(p.city, p.district, p.dong, cache)
            if lat is not None:
                p.lat, p.lng = lat, lng
                filled += 1
            if i % 100 == 0:
                db.commit()
                print(f"  {i}/{len(rows)} 처리 · 좌표 {filled}건 · 고유지역 {len(cache)}개")
            if api_calls:  # 실제 호출 횟수만큼 ToS 딜레이 (캐시 히트는 즉시)
                time.sleep(1.1 * api_calls)
        db.commit()
        print(f"완료: {filled}/{len(rows)}건 좌표 채움 (고유 읍면동 {len(cache)}개)")
        miss = [k for k, v in cache.items() if v[0] is None]
        if miss:
            print(f"실패 지역 {len(miss)}개(예): {miss[:8]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
