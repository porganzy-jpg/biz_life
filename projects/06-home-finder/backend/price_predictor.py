"""
HomeFinder - 가격 예측 & 기회 매물 스코어링
순수 Python 구현 (sklearn 미사용) - 최소제곱법 선형회귀
"""
import logging
import math
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from models.property import Property
from models.area import Area
from models.transaction import TransactionHistory

logger = logging.getLogger("homefinder.price_predictor")


class PricePredictor:
    """
    부동산 가격 예측 및 기회 매물 분석기.
    - 구별 가격 추세를 선형회귀로 분석
    - 매물별 기회 점수(0-100) 산출
    """

    # ──────────────────────────────────────────────
    # 선형회귀 (최소제곱법, pure Python)
    # ──────────────────────────────────────────────

    @staticmethod
    def _linear_regression(x_vals: list[float], y_vals: list[float]) -> dict:
        """
        단순 선형회귀: y = slope * x + intercept
        Returns: slope, intercept, r_squared, std_error
        """
        n = len(x_vals)
        if n < 2:
            return {"slope": 0.0, "intercept": y_vals[0] if y_vals else 0.0,
                    "r_squared": 0.0, "std_error": 0.0}

        sum_x = sum(x_vals)
        sum_y = sum(y_vals)
        sum_xy = sum(x * y for x, y in zip(x_vals, y_vals))
        sum_x2 = sum(x * x for x in x_vals)

        mean_x = sum_x / n
        mean_y = sum_y / n

        denom = sum_x2 - (sum_x * sum_x) / n
        if abs(denom) < 1e-10:
            return {"slope": 0.0, "intercept": mean_y,
                    "r_squared": 0.0, "std_error": 0.0}

        slope = (sum_xy - (sum_x * sum_y) / n) / denom
        intercept = mean_y - slope * mean_x

        # R-squared
        ss_res = sum((y - (slope * x + intercept)) ** 2
                     for x, y in zip(x_vals, y_vals))
        ss_tot = sum((y - mean_y) ** 2 for y in y_vals)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-10 else 0.0
        r_squared = max(0.0, min(1.0, r_squared))

        # Standard error of the estimate
        std_error = math.sqrt(ss_res / (n - 2)) if n > 2 else 0.0

        return {
            "slope": slope,
            "intercept": intercept,
            "r_squared": r_squared,
            "std_error": std_error,
        }

    # ──────────────────────────────────────────────
    # 구별 가격 추세 예측
    # ──────────────────────────────────────────────

    def predict_district_trend(
        self,
        district: str,
        db: Session,
        months: int = 6,
    ) -> dict:
        """
        특정 구의 가격 추세를 분석하고 향후 N개월 가격을 예측.

        데이터 소스 우선순위:
        1. transaction_history (실거래가) - 월별 평균
        2. properties (현재 매물) - 현재 시점 가격

        Returns:
            current_avg: 현재 평균 가격 (원)
            predicted_avg: N개월 후 예측 평균 가격 (원)
            change_pct: 변동률 (%)
            trend_direction: "up" | "down" | "flat"
            confidence: 0.0 ~ 1.0 (R-squared 기반)
            data_points: 분석에 사용된 데이터 포인트 수
            monthly_prices: [{month, avg_price}] 시계열 데이터
        """
        # 1) 실거래가 월별 평균 수집 (최근 24개월)
        cutoff_date = datetime.utcnow() - timedelta(days=730)
        monthly_data = self._get_monthly_transaction_prices(
            db, district, cutoff_date
        )

        # 2) 현재 매물 평균 가격도 참조
        current_listing_avg = self._get_current_listing_avg(db, district)

        # 3) 데이터가 충분하지 않으면 매물 데이터만으로 반환
        if len(monthly_data) < 2:
            avg = current_listing_avg or 0
            return {
                "district": district,
                "current_avg": avg,
                "predicted_avg": avg,
                "change_pct": 0.0,
                "trend_direction": "flat",
                "confidence": 0.0,
                "data_points": len(monthly_data),
                "monthly_prices": monthly_data,
            }

        # 4) 선형회귀 수행: x = 월 인덱스 (0, 1, 2, ...), y = 평균 가격
        x_vals = [float(i) for i in range(len(monthly_data))]
        y_vals = [d["avg_price"] for d in monthly_data]

        reg = self._linear_regression(x_vals, y_vals)

        # 현재 가격 = 회귀선의 마지막 값 or 실제 최근 값
        current_idx = len(monthly_data) - 1
        current_avg_regressed = reg["slope"] * current_idx + reg["intercept"]
        # 실제 현재 값은 매물 평균 또는 최근 실거래 평균
        current_avg = current_listing_avg or y_vals[-1]

        # 예측: N개월 후
        future_idx = current_idx + months
        predicted_avg = reg["slope"] * future_idx + reg["intercept"]
        # 예측값이 음수가 되지 않도록
        predicted_avg = max(predicted_avg, 0)

        # 변동률 계산
        if current_avg and current_avg > 0:
            change_pct = ((predicted_avg - current_avg) / current_avg) * 100
        else:
            change_pct = 0.0

        # 추세 방향 결정
        if change_pct > 1.0:
            trend_direction = "up"
        elif change_pct < -1.0:
            trend_direction = "down"
        else:
            trend_direction = "flat"

        # 신뢰도 = R-squared (데이터 포인트 수에 따라 보정)
        data_penalty = min(1.0, len(monthly_data) / 6.0)
        confidence = reg["r_squared"] * data_penalty

        return {
            "district": district,
            "current_avg": int(current_avg),
            "predicted_avg": int(predicted_avg),
            "change_pct": round(change_pct, 2),
            "trend_direction": trend_direction,
            "confidence": round(confidence, 3),
            "data_points": len(monthly_data),
            "monthly_prices": monthly_data,
            "regression": {
                "slope": round(reg["slope"], 2),
                "intercept": round(reg["intercept"], 2),
                "r_squared": round(reg["r_squared"], 4),
            },
        }

    def _get_monthly_transaction_prices(
        self, db: Session, district: str, cutoff_date: datetime
    ) -> list[dict]:
        """실거래가를 월별로 집계하여 시계열 데이터 반환."""
        rows = (
            db.query(
                func.strftime("%Y-%m", TransactionHistory.transaction_date).label("month"),
                func.avg(TransactionHistory.price_krw).label("avg_price"),
                func.count(TransactionHistory.id).label("count"),
            )
            .filter(TransactionHistory.district == district)
            .filter(TransactionHistory.transaction_date >= cutoff_date.date())
            .filter(TransactionHistory.price_krw.isnot(None))
            .group_by(func.strftime("%Y-%m", TransactionHistory.transaction_date))
            .order_by(func.strftime("%Y-%m", TransactionHistory.transaction_date))
            .all()
        )

        return [
            {
                "month": row.month,
                "avg_price": int(row.avg_price),
                "count": row.count,
            }
            for row in rows
        ]

    def _get_current_listing_avg(
        self, db: Session, district: str
    ) -> Optional[int]:
        """현재 활성 매물의 평균 가격 조회."""
        result = (
            db.query(func.avg(Property.price_krw))
            .filter(Property.district == district)
            .filter(Property.is_active == 1)
            .filter(Property.price_krw.isnot(None))
            .scalar()
        )
        return int(result) if result else None

    # ──────────────────────────────────────────────
    # 기회 점수 (Opportunity Score) 산출
    # ──────────────────────────────────────────────

    def calculate_opportunity_score(
        self,
        prop: Property,
        district_avg: Optional[int],
    ) -> dict:
        """
        매물의 기회 점수를 0~100 으로 산출.

        구성 요소:
        - 가격 할인율 (district 평균 대비): 0~40점
        - 종합 점수 보너스 (score_composite): 0~30점
        - 신규 매물 보너스 (등록 최근): 0~15점
        - 지역 개발 점수 보너스: 0~15점

        Returns:
            score: 총점 (0~100)
            breakdown: {discount, composite, recency, development}
            discount_pct: 할인율 (%)
        """
        breakdown = {
            "discount": 0.0,
            "composite": 0.0,
            "recency": 0.0,
            "development": 0.0,
        }
        discount_pct = 0.0

        # 1) 가격 할인율 점수 (0~40)
        if (
            district_avg
            and district_avg > 0
            and prop.price_krw
            and prop.price_krw > 0
        ):
            discount_pct = (
                (district_avg - prop.price_krw) / district_avg
            ) * 100
            # 할인율이 양수면 시세보다 저렴 -> 높은 점수
            if discount_pct > 0:
                # 최대 40%할인 -> 40점
                breakdown["discount"] = min(40.0, discount_pct * (40.0 / 40.0))
            else:
                # 시세보다 비싼 경우에도 약간의 점수 (프리미엄이 낮으면)
                # -10% 이하 프리미엄 -> 0점
                breakdown["discount"] = max(
                    0.0, 10.0 + discount_pct * (10.0 / 10.0)
                )

        # 2) 종합 점수 보너스 (0~30)
        if prop.score_composite and prop.score_composite > 0:
            # score_composite는 0~100 범위
            # 50 이상부터 보너스 시작, 100에서 30점 만점
            if prop.score_composite >= 50:
                ratio = (prop.score_composite - 50) / 50.0
                breakdown["composite"] = ratio * 30.0
            else:
                # 50 미만이어도 약간의 점수
                breakdown["composite"] = (prop.score_composite / 50.0) * 10.0

        # 3) 신규 매물 보너스 (0~15)
        if prop.created_at:
            now = datetime.utcnow()
            days_since = (now - prop.created_at).days
            if days_since <= 3:
                breakdown["recency"] = 15.0
            elif days_since <= 7:
                breakdown["recency"] = 12.0
            elif days_since <= 14:
                breakdown["recency"] = 8.0
            elif days_since <= 30:
                breakdown["recency"] = 4.0
            else:
                breakdown["recency"] = 0.0

        # 4) 지역 개발 점수 보너스 (0~15)
        if prop.score_area and prop.score_area > 0:
            # score_area는 0~100 범위 -> 0~15 매핑
            breakdown["development"] = (prop.score_area / 100.0) * 15.0

        # 합산
        total = sum(breakdown.values())
        total = round(min(100.0, max(0.0, total)), 1)

        # 소수점 정리
        for k in breakdown:
            breakdown[k] = round(breakdown[k], 1)

        return {
            "score": total,
            "breakdown": breakdown,
            "discount_pct": round(discount_pct, 2),
        }

    # ──────────────────────────────────────────────
    # 전체 구 예측 조회
    # ──────────────────────────────────────────────

    def get_district_forecasts(self, db: Session) -> list[dict]:
        """
        모든 구에 대한 가격 예측 데이터를 반환.
        활성 매물이 존재하는 구만 대상으로 함.
        """
        # 활성 매물이 있는 구 목록 조회
        districts = (
            db.query(Property.district)
            .filter(Property.is_active == 1)
            .filter(Property.district.isnot(None))
            .filter(Property.price_krw.isnot(None))
            .group_by(Property.district)
            .having(func.count(Property.id) >= 1)
            .all()
        )

        forecasts = []
        for (district,) in districts:
            try:
                forecast = self.predict_district_trend(district, db)
                # 매물 수 추가
                prop_count = (
                    db.query(func.count(Property.id))
                    .filter(Property.district == district)
                    .filter(Property.is_active == 1)
                    .scalar()
                )
                forecast["property_count"] = prop_count or 0
                forecasts.append(forecast)
            except Exception as e:
                logger.error(f"District forecast error for {district}: {e}")

        # 변동률 절대값 기준으로 정렬 (변동이 큰 구 먼저)
        forecasts.sort(key=lambda f: abs(f["change_pct"]), reverse=True)

        return forecasts

    # ──────────────────────────────────────────────
    # 기회 매물 상위 조회
    # ──────────────────────────────────────────────

    def get_hot_opportunities(
        self, db: Session, limit: int = 10
    ) -> list[dict]:
        """
        기회 점수가 높은 상위 매물 목록을 반환.
        """
        # 활성 매물 + 가격 있는 것만
        properties = (
            db.query(Property)
            .filter(Property.is_active == 1)
            .filter(Property.price_krw.isnot(None))
            .all()
        )

        if not properties:
            return []

        # 구별 평균 가격 계산
        district_avgs = self._calculate_district_averages(db)

        # 각 매물의 기회 점수 산출
        scored = []
        for prop in properties:
            district_avg = district_avgs.get(prop.district)
            opp = self.calculate_opportunity_score(prop, district_avg)
            scored.append({
                "property": prop,
                "opportunity": opp,
            })

        # 기회 점수 기준 내림차순 정렬
        scored.sort(key=lambda x: x["opportunity"]["score"], reverse=True)

        # 상위 N건 반환
        results = []
        for item in scored[:limit]:
            p = item["property"]
            opp = item["opportunity"]
            results.append({
                "id": p.id,
                "complex_name": p.complex_name,
                "address": p.address,
                "district": p.district,
                "dong": p.dong,
                "property_type": p.property_type,
                "price_krw": p.price_krw,
                "area_m2": p.area_m2,
                "score_composite": p.score_composite,
                "opportunity_score": opp["score"],
                "opportunity_breakdown": opp["breakdown"],
                "discount_pct": opp["discount_pct"],
                "created_at": (
                    p.created_at.isoformat() if p.created_at else None
                ),
            })

        return results

    # ──────────────────────────────────────────────
    # 단일 매물 분석
    # ──────────────────────────────────────────────

    def get_property_analysis(
        self, property_id: int, db: Session
    ) -> Optional[dict]:
        """
        특정 매물에 대한 가격 예측 및 기회 분석 컨텍스트를 반환.
        """
        prop = (
            db.query(Property)
            .filter(Property.id == property_id)
            .first()
        )
        if not prop:
            return None

        # 구별 평균 가격
        district_avg = self._get_current_listing_avg(db, prop.district) if prop.district else None

        # 기회 점수
        opp = self.calculate_opportunity_score(prop, district_avg)

        # 구 가격 추세
        district_trend = None
        if prop.district:
            try:
                district_trend = self.predict_district_trend(
                    prop.district, db, months=6
                )
                # monthly_prices는 API 응답 크기를 줄이기 위해 요약만
                if district_trend.get("monthly_prices"):
                    district_trend["monthly_prices"] = district_trend[
                        "monthly_prices"
                    ][-6:]  # 최근 6개월만
            except Exception as e:
                logger.error(
                    f"Property analysis trend error for {prop.district}: {e}"
                )

        # 같은 구 유사 매물 비교
        similar = self._get_similar_properties_stats(db, prop)

        return {
            "property_id": prop.id,
            "complex_name": prop.complex_name,
            "address": prop.address,
            "district": prop.district,
            "dong": prop.dong,
            "price_krw": prop.price_krw,
            "area_m2": prop.area_m2,
            "score_composite": prop.score_composite,
            "district_avg_price": district_avg,
            "opportunity": opp,
            "district_trend": district_trend,
            "similar_properties": similar,
        }

    # ──────────────────────────────────────────────
    # 내부 헬퍼 메서드
    # ──────────────────────────────────────────────

    def _calculate_district_averages(self, db: Session) -> dict[str, int]:
        """모든 구의 활성 매물 평균 가격을 dict로 반환."""
        rows = (
            db.query(
                Property.district,
                func.avg(Property.price_krw).label("avg_price"),
            )
            .filter(Property.is_active == 1)
            .filter(Property.price_krw.isnot(None))
            .filter(Property.district.isnot(None))
            .group_by(Property.district)
            .all()
        )
        return {
            row.district: int(row.avg_price) for row in rows if row.avg_price
        }

    def _get_similar_properties_stats(
        self, db: Session, prop: Property
    ) -> dict:
        """같은 구/유형의 유사 매물 통계 반환."""
        query = (
            db.query(Property)
            .filter(Property.is_active == 1)
            .filter(Property.price_krw.isnot(None))
            .filter(Property.id != prop.id)
        )

        if prop.district:
            query = query.filter(Property.district == prop.district)
        if prop.property_type:
            query = query.filter(Property.property_type == prop.property_type)

        similar = query.all()

        if not similar:
            return {
                "count": 0,
                "avg_price": None,
                "min_price": None,
                "max_price": None,
                "price_rank": None,
                "price_percentile": None,
            }

        prices = [s.price_krw for s in similar if s.price_krw]
        if not prices:
            return {
                "count": len(similar),
                "avg_price": None,
                "min_price": None,
                "max_price": None,
                "price_rank": None,
                "price_percentile": None,
            }

        prices.sort()
        avg_price = int(sum(prices) / len(prices))

        # 해당 매물의 가격 순위 (저렴한 순)
        price_rank = None
        price_percentile = None
        if prop.price_krw:
            lower_count = sum(1 for p in prices if p < prop.price_krw)
            price_rank = lower_count + 1
            price_percentile = round(
                (lower_count / len(prices)) * 100, 1
            )

        return {
            "count": len(prices),
            "avg_price": avg_price,
            "min_price": prices[0],
            "max_price": prices[-1],
            "price_rank": price_rank,
            "price_percentile": price_percentile,
        }
