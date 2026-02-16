"""단지 서비스 - 아파트 단지 조회 및 시세"""
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models.complex import Complex
from models.transaction import TransactionHistory
from repositories.complex_repo import ComplexRepository
from repositories.transaction_repo import TransactionRepository
from exceptions import NotFoundException


class ComplexService:
    def __init__(self, db: Session):
        self.db = db
        self.complex_repo = ComplexRepository(db)
        self.tx_repo = TransactionRepository(db)

    def get_complex(self, id: int) -> Complex:
        """단지 상세 조회"""
        cpx = self.complex_repo.get_by_id(id)
        if not cpx:
            raise NotFoundException(f"단지 ID {id}을(를) 찾을 수 없습니다")
        return cpx

    def search_complexes(self, keyword: str, district: str = None) -> list:
        """단지 검색 (이름 키워드 + 선택적 지역 필터)"""
        if district:
            # Filter by both keyword and district
            query = (
                self.db.query(Complex)
                .filter(Complex.name.contains(keyword))
                .filter(Complex.district == district)
                .limit(50)
            )
            return query.all()
        else:
            return self.complex_repo.search_by_name(keyword, limit=50)

    def get_price_history(self, complex_id: int) -> list:
        """단지 실거래가 이력 조회"""
        cpx = self.complex_repo.get_by_id(complex_id)
        if not cpx:
            raise NotFoundException(f"단지 ID {complex_id}을(를) 찾을 수 없습니다")

        # Get transactions by complex name
        transactions = self.tx_repo.get_by_name(cpx.name, months_back=36)

        result = []
        for tx in transactions:
            result.append({
                "date": tx.transaction_date.isoformat() if tx.transaction_date else None,
                "price_krw": tx.price_krw,
                "price_per_m2": tx.price_per_m2,
                "area_m2": tx.area_exclusive,
                "floor": tx.floor,
                "built_year": tx.built_year,
            })
        return result
