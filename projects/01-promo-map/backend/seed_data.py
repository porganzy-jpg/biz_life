"""
PromoMap 초기 데모 데이터
서울 주요 지역 매장 및 할인 정보 + 관리자 계정
"""
import sys
import os

_shared_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared")
if _shared_path not in sys.path:
    sys.path.append(_shared_path)

from database import SessionLocal, init_db
from models import User, Company, Store, Discount
from auth.password import hash_password


def seed():
    """데모 데이터 삽입"""
    init_db()
    db = SessionLocal()

    if db.query(Company).count() > 0:
        print("데이터 이미 존재합니다.")
        db.close()
        return

    # === 관리자 계정 ===
    admin = User(
        email="admin@promomap.com",
        hashed_password=hash_password("admin1234"),
        name="관리자",
        phone="010-0000-0000",
        is_admin=True,
    )
    db.add(admin)
    db.flush()

    # === 회사 ===
    companies = [
        Company(name="CJ그룹", code="CJ001", industry="식품/미디어", employee_count=50000),
        Company(name="삼성", code="SS001", industry="전자/반도체", employee_count=120000),
        Company(name="LG", code="LG001", industry="전자/화학", employee_count=80000),
        Company(name="현대", code="HD001", industry="자동차/건설", employee_count=100000),
        Company(name="SK", code="SK001", industry="에너지/통신", employee_count=70000),
    ]
    db.add_all(companies)
    db.flush()

    # === 테스트 사용자 ===
    test_user = User(
        email="test@cj.com",
        hashed_password=hash_password("test1234"),
        name="테스트유저",
        phone="010-1234-5678",
        company_id=companies[0].id,
    )
    db.add(test_user)
    db.flush()

    # === 매장 (강남/역삼 중심) ===
    stores = [
        Store(name="VIPS 역삼점", brand="VIPS", category="food",
              address="서울 강남구 역삼동 123", latitude=37.5012, longitude=127.0396,
              icon_color="#E4002B", icon_letter="V"),
        Store(name="올리브영 강남역점", brand="Olive Young", category="shopping",
              address="서울 강남구 역삼동 456", latitude=37.4980, longitude=127.0276,
              icon_color="#9ACD32", icon_letter="O"),
        Store(name="투썸플레이스 선릉점", brand="TWOSOME", category="cafe",
              address="서울 강남구 선릉로 789", latitude=37.5045, longitude=127.0488,
              icon_color="#1E90FF", icon_letter="T"),
        Store(name="제일제면소 역삼점", brand="제일제면소", category="food",
              address="서울 강남구 역삼동 111", latitude=37.5001, longitude=127.0365,
              icon_color="#FF8C00", icon_letter="J"),
        Store(name="백설기 강남점", brand="백설기", category="food",
              address="서울 강남구 강남대로 222", latitude=37.4955, longitude=127.0300,
              icon_color="#8B4513", icon_letter="B"),
        Store(name="CGV 강남", brand="CGV", category="entertainment",
              address="서울 강남구 강남대로 333", latitude=37.5018, longitude=127.0260,
              icon_color="#C62828", icon_letter="C"),
        Store(name="빕스버거 삼성점", brand="VIPS Burger", category="food",
              address="서울 강남구 삼성동 444", latitude=37.5088, longitude=127.0632,
              icon_color="#E4002B", icon_letter="V"),
        Store(name="올리브영 삼성역점", brand="Olive Young", category="shopping",
              address="서울 강남구 삼성동 555", latitude=37.5094, longitude=127.0601,
              icon_color="#9ACD32", icon_letter="O"),
        Store(name="스타벅스 역삼역점", brand="Starbucks", category="cafe",
              address="서울 강남구 역삼동 666", latitude=37.4998, longitude=127.0365,
              icon_color="#00704A", icon_letter="S"),
        Store(name="이마트24 선릉역점", brand="이마트24", category="convenience",
              address="서울 강남구 선릉로 777", latitude=37.5048, longitude=127.0492,
              icon_color="#F5A623", icon_letter="E"),
    ]
    db.add_all(stores)
    db.flush()

    # === 할인 정보 ===
    cj = companies[0]
    samsung = companies[1]

    discounts = [
        Discount(store_id=stores[0].id, company_id=cj.id, discount_type="percent",
                 discount_value=20, description="CJ 임직원 VIPS 20% 할인"),
        Discount(store_id=stores[1].id, company_id=cj.id, discount_type="percent",
                 discount_value=15, description="CJ 임직원 올리브영 15% 할인"),
        Discount(store_id=stores[2].id, company_id=cj.id, discount_type="percent",
                 discount_value=30, description="CJ 임직원 투썸 30% 할인"),
        Discount(store_id=stores[3].id, company_id=cj.id, discount_type="percent",
                 discount_value=10, description="CJ 임직원 제일제면소 10% 할인"),
        Discount(store_id=stores[4].id, company_id=cj.id, discount_type="percent",
                 discount_value=25, description="CJ 임직원 백설기 25% 할인"),
        Discount(store_id=stores[5].id, company_id=cj.id, discount_type="percent",
                 discount_value=50, description="CJ 임직원 CGV 50% 할인"),
        Discount(store_id=stores[6].id, company_id=cj.id, discount_type="percent",
                 discount_value=20, description="CJ 임직원 빕스버거 20% 할인"),
        Discount(store_id=stores[7].id, company_id=cj.id, discount_type="percent",
                 discount_value=15, description="CJ 임직원 올리브영 15% 할인"),
        Discount(store_id=stores[8].id, company_id=samsung.id, discount_type="percent",
                 discount_value=10, description="삼성 임직원 스타벅스 10% 할인"),
        Discount(store_id=stores[5].id, company_id=samsung.id, discount_type="percent",
                 discount_value=30, description="삼성 임직원 CGV 30% 할인"),
    ]
    db.add_all(discounts)
    db.commit()
    db.close()
    print(f"시드 데이터 삽입 완료: 관리자 1명, 회사 {len(companies)}개, 매장 {len(stores)}개, 할인 {len(discounts)}건")


if __name__ == "__main__":
    seed()
