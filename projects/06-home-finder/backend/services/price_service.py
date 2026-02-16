"""가격 서비스 - 시세 분석 및 적정가 추정"""
from datetime import datetime, date

from sqlalchemy.orm import Session
from sqlalchemy import func

from models.transaction import TransactionHistory
from models.price_index import PriceIndex
from repositories.transaction_repo import TransactionRepository
from repositories.price_index_repo import PriceIndexRepository
from repositories.area_repo import AreaRepository


class PriceService:
    def __init__(self, db: Session):
        self.db = db
        self.tx_repo = TransactionRepository(db)
        self.price_idx_repo = PriceIndexRepository(db)
        self.area_repo = AreaRepository(db)

    def get_price_trend(
        self,
        district: str,
        dong: str = None,
        name: str = None,
        months: int = 12,
    ) -> list:
        """실거래가 추이 조회"""
        transactions = self.tx_repo.get_price_trend(
            district=district,
            dong=dong,
            name=name,
            months=months,
        )
        result = []
        for tx in transactions:
            result.append({
                "date": tx.transaction_date.isoformat() if tx.transaction_date else None,
                "name": tx.name,
                "dong": tx.dong,
                "price_krw": tx.price_krw,
                "price_per_m2": tx.price_per_m2,
                "area_m2": tx.area_exclusive,
                "floor": tx.floor,
            })
        return result

    def get_area_average(self, district: str) -> dict:
        """지역 평균 m2당 가격 조회"""
        # From area table
        areas = self.area_repo.get_by_district(district)
        area_avg = None
        if areas:
            area_avg = areas[0].avg_price_per_m2

        # From recent transactions (last 6 months)
        recent_txs = self.tx_repo.get_by_district(district, months_back=6)
        tx_avg = None
        tx_count = 0
        if recent_txs:
            prices = [
                tx.price_per_m2
                for tx in recent_txs
                if tx.price_per_m2 is not None
            ]
            if prices:
                tx_avg = int(sum(prices) / len(prices))
                tx_count = len(prices)

        return {
            "district": district,
            "area_table_avg_per_m2": area_avg,
            "transaction_avg_per_m2": tx_avg,
            "transaction_count": tx_count,
        }

    def get_price_indices(self, region: str = "서울", months: int = 12) -> list:
        """가격 지수 추이 조회"""
        indices = self.price_idx_repo.get_trend(
            source="kb", region=region, months_back=months
        )
        result = []
        for idx in indices:
            result.append({
                "date": idx.date.isoformat() if idx.date else None,
                "source": idx.source,
                "index_type": idx.index_type,
                "region": idx.region,
                "value": idx.value,
                "change_pct": idx.change_pct,
            })
        return result

    def estimate_fair_price(
        self,
        district: str,
        area_m2: float,
        floor: int,
        built_year: int,
    ) -> dict:
        """적정 가격 추정 (유사 거래 기반)"""
        # Find similar recent transactions
        # Same district, similar area (+-10m2), similar age (+-5yr)
        area_min = area_m2 - 10
        area_max = area_m2 + 10
        year_min = built_year - 5
        year_max = built_year + 5

        query = (
            self.db.query(TransactionHistory)
            .filter(TransactionHistory.district == district)
            .filter(TransactionHistory.area_exclusive.between(area_min, area_max))
            .filter(TransactionHistory.built_year.between(year_min, year_max))
        )

        # Use last 12 months of data
        from datetime import timedelta
        cutoff = date.today() - timedelta(days=365)
        query = query.filter(TransactionHistory.transaction_date >= cutoff)

        similar_txs = query.order_by(
            TransactionHistory.transaction_date.desc()
        ).all()

        if not similar_txs:
            return {
                "district": district,
                "area_m2": area_m2,
                "floor": floor,
                "built_year": built_year,
                "estimated_price": None,
                "estimated_price_per_m2": None,
                "confidence": "low",
                "comparable_count": 0,
                "comparables": [],
                "message": "유사 거래 데이터가 부족합니다",
            }

        # Calculate stats
        prices = [tx.price_krw for tx in similar_txs if tx.price_krw]
        prices_per_m2 = [tx.price_per_m2 for tx in similar_txs if tx.price_per_m2]

        avg_price = int(sum(prices) / len(prices)) if prices else None
        avg_per_m2 = int(sum(prices_per_m2) / len(prices_per_m2)) if prices_per_m2 else None
        min_price = min(prices) if prices else None
        max_price = max(prices) if prices else None

        # Estimate based on avg price per m2
        estimated_price = int(avg_per_m2 * area_m2) if avg_per_m2 else None

        # Floor adjustment: higher floors get a small premium
        if estimated_price and floor:
            if floor >= 15:
                estimated_price = int(estimated_price * 1.03)
            elif floor >= 10:
                estimated_price = int(estimated_price * 1.01)
            elif floor <= 3:
                estimated_price = int(estimated_price * 0.97)

        # Confidence based on sample size
        count = len(similar_txs)
        if count >= 20:
            confidence = "high"
        elif count >= 10:
            confidence = "medium"
        else:
            confidence = "low"

        # Top 5 comparables
        comparables = []
        for tx in similar_txs[:5]:
            comparables.append({
                "name": tx.name,
                "date": tx.transaction_date.isoformat() if tx.transaction_date else None,
                "price_krw": tx.price_krw,
                "area_m2": tx.area_exclusive,
                "floor": tx.floor,
                "built_year": tx.built_year,
            })

        return {
            "district": district,
            "area_m2": area_m2,
            "floor": floor,
            "built_year": built_year,
            "estimated_price": estimated_price,
            "estimated_price_per_m2": avg_per_m2,
            "min_price": min_price,
            "max_price": max_price,
            "confidence": confidence,
            "comparable_count": count,
            "comparables": comparables,
        }
