"""
가격 적정성 분석 서비스
매물 가격을 실거래 히스토리와 비교하여 적정가 판단
3단계 매칭: 같은 단지 → 같은 동 → 같은 구
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from models.property import Property
from models.transaction import TransactionHistory

logger = logging.getLogger("homefinder.price_analyzer")

# 면적 허용 오차 (㎡)
AREA_TOLERANCE = 10
# 최소 비교 건수 (이 이상이어야 신뢰 가능)
MIN_COMPARABLES = 3
# 비교 기간 (개월)
DEFAULT_MONTHS = 6


def _get_cutoff_date(months: int) -> datetime:
    return datetime.now() - timedelta(days=30 * months)


def _calc_stats(prices: list[int]) -> dict:
    """가격 리스트에서 통계 계산"""
    if not prices:
        return None
    prices_sorted = sorted(prices)
    n = len(prices_sorted)
    return {
        "count": n,
        "avg": int(sum(prices) / n),
        "median": prices_sorted[n // 2],
        "min": prices_sorted[0],
        "max": prices_sorted[-1],
        "p25": prices_sorted[max(0, n // 4)],
        "p75": prices_sorted[min(n - 1, n * 3 // 4)],
    }


def _judge_price(listing_price: int, market_avg: int) -> dict:
    """매물가 vs 시세 판정"""
    if not market_avg or market_avg == 0:
        return {"verdict": "판단불가", "diff_pct": None, "score": 50}

    diff_pct = round((listing_price - market_avg) / market_avg * 100, 1)

    if diff_pct <= -10:
        verdict, score = "급매/저평가", 100
    elif diff_pct <= -5:
        verdict, score = "저렴", 85
    elif diff_pct <= -2:
        verdict, score = "소폭 저렴", 75
    elif diff_pct <= 2:
        verdict, score = "적정가", 65
    elif diff_pct <= 5:
        verdict, score = "소폭 비쌈", 50
    elif diff_pct <= 10:
        verdict, score = "다소 비쌈", 35
    else:
        verdict, score = "고평가", 20

    return {"verdict": verdict, "diff_pct": diff_pct, "score": score}


class PriceAnalyzer:
    def __init__(self, db: Session):
        self.db = db

    def analyze(self, property_id: int, months: int = DEFAULT_MONTHS) -> dict:
        """매물의 가격 적정성 종합 분석"""
        prop = self.db.query(Property).filter(Property.id == property_id).first()
        if not prop:
            return {"error": "매물을 찾을 수 없습니다"}
        if not prop.price_krw:
            return {"error": "매물 가격 정보가 없습니다"}

        cutoff = _get_cutoff_date(months)
        area = prop.area_m2 or 0

        # 3단계 매칭
        result = {
            "property_id": property_id,
            "listing_price": prop.price_krw,
            "listing_area": area,
            "listing_name": prop.complex_name or prop.address,
            "district": prop.district,
            "dong": prop.dong,
            "months": months,
            "levels": {},
            "best_match": None,
            "verdict": None,
        }

        # Level 1: 같은 단지 + 비슷한 면적
        if prop.complex_name:
            level1 = self._find_comparables(
                cutoff, area,
                name=prop.complex_name,
            )
            result["levels"]["단지"] = level1
            if level1 and level1["stats"]["count"] >= MIN_COMPARABLES:
                result["best_match"] = "단지"

        # Level 2: 같은 동 + 비슷한 면적
        if prop.dong:
            level2 = self._find_comparables(
                cutoff, area,
                district=prop.district,
                dong=prop.dong,
            )
            result["levels"]["동"] = level2
            if not result["best_match"] and level2 and level2["stats"]["count"] >= MIN_COMPARABLES:
                result["best_match"] = "동"

        # Level 3: 같은 구 + 비슷한 면적
        if prop.district:
            level3 = self._find_comparables(
                cutoff, area,
                district=prop.district,
            )
            result["levels"]["구"] = level3
            if not result["best_match"] and level3 and level3["stats"]["count"] >= MIN_COMPARABLES:
                result["best_match"] = "구"

        # 최적 매칭 레벨로 판정
        if result["best_match"]:
            best = result["levels"][result["best_match"]]
            judgment = _judge_price(prop.price_krw, best["stats"]["avg"])
            result["verdict"] = {
                "level": result["best_match"],
                "comparable_count": best["stats"]["count"],
                "market_avg": best["stats"]["avg"],
                "market_median": best["stats"]["median"],
                **judgment,
            }
        else:
            result["verdict"] = {
                "level": None,
                "verdict": "비교 데이터 부족",
                "diff_pct": None,
                "score": 50,
                "comparable_count": 0,
            }

        return result

    def _find_comparables(
        self, cutoff, area: float,
        name: str = None, district: str = None, dong: str = None,
    ) -> dict | None:
        """조건에 맞는 실거래 비교군 조회"""
        q = self.db.query(TransactionHistory).filter(
            TransactionHistory.transaction_date >= cutoff.date(),
        )

        if name:
            q = q.filter(TransactionHistory.name == name)
        if district:
            q = q.filter(TransactionHistory.district == district)
        if dong:
            q = q.filter(TransactionHistory.dong == dong)

        # 면적 범위 필터
        if area > 0:
            q = q.filter(
                TransactionHistory.area_exclusive.between(
                    area - AREA_TOLERANCE, area + AREA_TOLERANCE
                )
            )

        txs = q.order_by(TransactionHistory.transaction_date.desc()).limit(200).all()

        if not txs:
            return {"stats": {"count": 0}, "transactions": []}

        prices = [t.price_krw for t in txs if t.price_krw]
        stats = _calc_stats(prices)

        # 최근 거래 5건 반환
        recent = []
        for t in txs[:5]:
            recent.append({
                "date": t.transaction_date.isoformat() if t.transaction_date else None,
                "name": t.name,
                "dong": t.dong,
                "price_krw": t.price_krw,
                "area": t.area_exclusive,
                "floor": t.floor,
            })

        return {"stats": stats, "transactions": recent}
