"""
서울 · 경기 · 송도(인천 연수구) '직접 집을 지을 수 있는 땅' 실거래 수집 실행 스크립트

사용:
    python collect_land.py                # 전체 지역, 최근 6개월
    python collect_land.py 12             # 최근 12개월
    python collect_land.py 6 강남구 인천\\ 연수구   # 특정 지역만

수집 데이터: 국토교통부 토지 실거래가 (건축 가능 필지만 필터링)
  - 지분거래 / 도로·하천 등 건축 불가 지목 / 개발제한·보전·농림 용도 → 제외
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from database import init_db, SessionLocal
from models.property import Property
from backend.config import settings
from collectors.land_collector import LandCollector, DISTRICT_CODES


def main():
    months_back = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    target = sys.argv[2:] if len(sys.argv) > 2 else []

    print("=" * 56)
    print(" HomeFinder · 건축 가능 토지 실거래 수집")
    print("=" * 56)
    print(f" 대상 지역: {len(target) if target else len(DISTRICT_CODES)}개 "
          f"({'지정' if target else '서울+경기+송도 전체'})")
    print(f" 수집 기간: 최근 {months_back}개월")
    if not settings.PUBLIC_DATA_API_KEY:
        print(" [오류] .env의 PUBLIC_DATA_API_KEY가 비어 있습니다.")
        sys.exit(1)
    print(f" 카카오 지오코딩: {'ON' if settings.KAKAO_REST_API_KEY else 'OFF (좌표 없음)'}")
    print("-" * 56)

    init_db()

    collector = LandCollector(
        api_key=settings.PUBLIC_DATA_API_KEY,
        target_districts=target,
        kakao_key=settings.KAKAO_REST_API_KEY,
    )
    result = collector.run(months_back=months_back)

    print("-" * 56)
    print(f" 원본 수집:   {result['fetched']}건")
    print(f" 건축가능 신규: {result['new']}건")
    print(f" 제외:        {result.get('skipped', 0)}건 (지분/불가지목/제약용도)")
    print(f" 실패 호출:   {result['failures']}건")

    # 요약 통계
    db = SessionLocal()
    try:
        q = db.query(Property).filter(
            Property.source == "molit_land", Property.is_active == 1)
        total = q.count()
        print("-" * 56)
        print(f" DB 내 실거래 기반 토지 매물: {total}건")

        # 도시별
        from sqlalchemy import func
        by_city = (db.query(Property.city, func.count(Property.id))
                   .filter(Property.source == "molit_land")
                   .group_by(Property.city).all())
        for city, cnt in by_city:
            print(f"   · {city}: {cnt}건")

        # 최저가 TOP 8 (평당가 기준)
        cheap = (q.filter(Property.price_per_m2 > 0)
                 .order_by(Property.price_per_m2.asc()).limit(8).all())
        if cheap:
            print("\n 평당가 저렴한 순 TOP 8:")
            for p in cheap:
                pyeong_price = int(p.price_per_m2 * 3.3058 / 10000)  # 만원/평
                eok = p.price_krw / 100000000
                print(f"   {p.district} {p.dong} | {p.area_m2:.0f}㎡ | "
                      f"{eok:.2f}억 | 평당 {pyeong_price:,}만 | {p.land_use}/{p.zoning_type}")
    finally:
        db.close()

    print("\n 서버: http://localhost:8006 · 토지 필터로 확인하세요.")


if __name__ == "__main__":
    main()
