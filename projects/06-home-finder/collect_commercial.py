"""
상업업무용 부동산 실거래 수집 실행 스크립트

사용:
    python collect_commercial.py                  # 서울 전체, 6개월
    python collect_commercial.py 12               # 12개월
    python collect_commercial.py 6 강남구 서초구    # 특정 구만
"""
import os
import sys
import logging
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)

from collectors.commercial_collector import CommercialCollector


def main():
    months = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    districts = sys.argv[2:] if len(sys.argv) > 2 else []

    api_key = os.getenv("PUBLIC_DATA_API_KEY")
    if not api_key:
        print("PUBLIC_DATA_API_KEY 가 .env 에 없습니다.")
        sys.exit(1)

    target = ", ".join(districts) if districts else "서울+경기 전체"
    print(f"상업업무용 실거래 수집 시작 — {target}, 최근 {months}개월\n")

    collector = CommercialCollector(api_key, target_districts=districts)
    try:
        result = collector.run(months_back=months)
    except RuntimeError as e:
        print(f"\n[중단] {e}")
        sys.exit(2)

    print(
        f"\n완료 — 조회 {result['fetched']}건 / 신규 저장 {result['new']}건 "
        f"(실패 {result['failures']}, 빈응답 {result['empty']})"
    )


if __name__ == "__main__":
    main()
