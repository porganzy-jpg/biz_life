"""지역 서비스 - 지역 프로필 및 비교"""
from datetime import datetime, date, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func

from models.area import Area
from models.transaction import TransactionHistory
from models.property import Property
from repositories.area_repo import AreaRepository
from repositories.transaction_repo import TransactionRepository
from exceptions import NotFoundException


class AreaService:
    def __init__(self, db: Session):
        self.db = db
        self.area_repo = AreaRepository(db)
        self.tx_repo = TransactionRepository(db)

    def get_area_profile(self, district: str) -> dict:
        """지역 프로필 조회"""
        areas = self.area_repo.get_by_district(district)
        if not areas:
            raise NotFoundException(f"지역 '{district}'을(를) 찾을 수 없습니다")

        area = areas[0]

        # Count active properties in this district
        property_count = (
            self.db.query(Property)
            .filter(Property.is_active == 1)
            .filter(Property.district == district)
            .count()
        )

        # Recent transaction count
        recent_txs = self.tx_repo.get_by_district(district, months_back=6)

        return {
            "district": area.district,
            "city": area.city,
            "population": area.population,
            "households": area.households,
            "subway_count": area.subway_count,
            "park_count": area.park_count,
            "school_count": area.school_count,
            "hospital_count": area.hospital_count,
            "avg_price_per_m2": area.avg_price_per_m2,
            "price_change_1y": area.price_change_1y,
            "price_change_3y": area.price_change_3y,
            "development_plan": area.development_plan,
            "development_score": area.development_score,
            "living_score": area.living_score,
            "infra_score": area.infra_score,
            "area_composite_score": area.area_composite_score,
            "active_properties": property_count,
            "recent_transactions": len(recent_txs),
            "description": area.description,
        }

    def compare_areas(self, district1: str, district2: str) -> dict:
        """두 지역 비교"""
        profile1 = self.get_area_profile(district1)
        profile2 = self.get_area_profile(district2)

        # Build comparison highlights
        highlights = []

        # Price comparison
        p1 = profile1.get("avg_price_per_m2") or 0
        p2 = profile2.get("avg_price_per_m2") or 0
        if p1 and p2:
            cheaper = district1 if p1 < p2 else district2
            diff_pct = abs(p1 - p2) / max(p1, p2) * 100
            highlights.append(
                f"{cheaper}이(가) m2당 {diff_pct:.1f}% 저렴"
            )

        # Infrastructure comparison
        infra1 = (profile1.get("subway_count") or 0) + (profile1.get("school_count") or 0)
        infra2 = (profile2.get("subway_count") or 0) + (profile2.get("school_count") or 0)
        if infra1 != infra2:
            better_infra = district1 if infra1 > infra2 else district2
            highlights.append(f"{better_infra}이(가) 인프라 더 우수")

        # Price trend comparison
        trend1 = profile1.get("price_change_1y") or 0
        trend2 = profile2.get("price_change_1y") or 0
        if trend1 != trend2:
            rising = district1 if trend1 > trend2 else district2
            highlights.append(f"{rising}이(가) 최근 상승세 더 강함")

        return {
            "area_1": profile1,
            "area_2": profile2,
            "highlights": highlights,
        }

    def get_all_districts(self) -> list:
        """모든 구 목록 조회"""
        return self.area_repo.get_all_districts()

    def update_area_stats(self, district: str) -> Area:
        """지역 통계 재계산 (실거래가 기반)"""
        areas = self.area_repo.get_by_district(district)
        if not areas:
            raise NotFoundException(f"지역 '{district}'을(를) 찾을 수 없습니다")

        area = areas[0]

        # Recalculate avg_price_per_m2 from recent transactions
        recent_txs = self.tx_repo.get_by_district(district, months_back=6)
        if recent_txs:
            prices_per_m2 = [
                tx.price_per_m2
                for tx in recent_txs
                if tx.price_per_m2 is not None
            ]
            if prices_per_m2:
                area.avg_price_per_m2 = int(sum(prices_per_m2) / len(prices_per_m2))

        # Calculate 1-year price change
        txs_recent = self.tx_repo.get_by_district(district, months_back=3)
        txs_old = self.tx_repo.get_price_trend(district, months=15)

        if txs_recent and txs_old:
            cutoff_old = date.today() - timedelta(days=450)
            cutoff_old_end = date.today() - timedelta(days=270)

            recent_prices = [
                tx.price_per_m2
                for tx in txs_recent
                if tx.price_per_m2 is not None
            ]
            old_prices = [
                tx.price_per_m2
                for tx in txs_old
                if tx.price_per_m2 is not None
                and tx.transaction_date
                and cutoff_old <= tx.transaction_date <= cutoff_old_end
            ]

            if recent_prices and old_prices:
                avg_recent = sum(recent_prices) / len(recent_prices)
                avg_old = sum(old_prices) / len(old_prices)
                if avg_old > 0:
                    area.price_change_1y = round(
                        (avg_recent - avg_old) / avg_old * 100, 2
                    )

        area.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(area)
        return area
