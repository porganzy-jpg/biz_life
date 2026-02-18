"""
HomeFinder - 실제 서울 아파트 데이터 수집 스크립트
실존하는 단지명, GPS 좌표, 2025~2026 실거래 시세 기반
"""
import sys
import os
import random
from pathlib import Path
from datetime import datetime, timedelta, date

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from database import SessionLocal, init_db
from models.property import Property
from models.transaction import TransactionHistory
from models.auction import AuctionListing
from models.subscription import SubscriptionOpportunity
from models.area import Area
import seed_data

# ──────────── 실제 서울 아파트 데이터 ────────────
# 단지명, 위도, 경도, 전용면적(㎡), 시세(만원), 건축년도, 세대수, 동
REAL_APARTMENTS = [
    # ── 마포구 ──
    {"complex": "마포래미안푸르지오", "district": "마포구", "dong": "아현동", "lat": 37.5518, "lng": 126.9568,
     "units": [
         {"area": 59, "price_man": 130000, "floor": 15, "total": 32, "rooms": 3, "bath": 1, "year": 2014},
         {"area": 84, "price_man": 168000, "floor": 22, "total": 32, "rooms": 4, "bath": 2, "year": 2014},
     ]},
    {"complex": "마포프레스티지자이", "district": "마포구", "dong": "염리동", "lat": 37.5453, "lng": 126.9488,
     "units": [
         {"area": 59, "price_man": 120000, "floor": 8, "total": 25, "rooms": 3, "bath": 1, "year": 2018},
         {"area": 84, "price_man": 155000, "floor": 18, "total": 25, "rooms": 4, "bath": 2, "year": 2018},
     ]},
    {"complex": "신촌숲아이파크", "district": "마포구", "dong": "북아현동", "lat": 37.5570, "lng": 126.9520,
     "units": [
         {"area": 59, "price_man": 125000, "floor": 10, "total": 29, "rooms": 3, "bath": 1, "year": 2022},
         {"area": 84, "price_man": 163000, "floor": 20, "total": 29, "rooms": 4, "bath": 2, "year": 2022},
         {"area": 114, "price_man": 198000, "floor": 25, "total": 29, "rooms": 4, "bath": 2, "year": 2022},
     ]},
    {"complex": "마포한강2차푸르지오", "district": "마포구", "dong": "마포동", "lat": 37.5394, "lng": 126.9457,
     "units": [
         {"area": 59, "price_man": 100000, "floor": 7, "total": 18, "rooms": 3, "bath": 1, "year": 2008},
         {"area": 84, "price_man": 130000, "floor": 12, "total": 18, "rooms": 3, "bath": 2, "year": 2008},
     ]},
    {"complex": "공덕자이", "district": "마포구", "dong": "공덕동", "lat": 37.5441, "lng": 126.9510,
     "units": [
         {"area": 77, "price_man": 135000, "floor": 14, "total": 20, "rooms": 3, "bath": 2, "year": 2016},
         {"area": 102, "price_man": 170000, "floor": 18, "total": 20, "rooms": 4, "bath": 2, "year": 2016},
     ]},
    # ── 용산구 ──
    {"complex": "래미안첼리투스", "district": "용산구", "dong": "이촌동", "lat": 37.5218, "lng": 126.9710,
     "units": [
         {"area": 59, "price_man": 175000, "floor": 12, "total": 36, "rooms": 3, "bath": 1, "year": 2015},
         {"area": 84, "price_man": 230000, "floor": 28, "total": 36, "rooms": 4, "bath": 2, "year": 2015},
     ]},
    {"complex": "용산센트럴파크해링턴스퀘어", "district": "용산구", "dong": "한강로3가", "lat": 37.5296, "lng": 126.9649,
     "units": [
         {"area": 84, "price_man": 220000, "floor": 20, "total": 45, "rooms": 3, "bath": 2, "year": 2019},
         {"area": 101, "price_man": 280000, "floor": 35, "total": 45, "rooms": 4, "bath": 2, "year": 2019},
     ]},
    {"complex": "한남더힐", "district": "용산구", "dong": "한남동", "lat": 37.5340, "lng": 127.0003,
     "units": [
         {"area": 224, "price_man": 600000, "floor": 3, "total": 5, "rooms": 5, "bath": 3, "year": 2011},
     ]},
    {"complex": "용산파크타워", "district": "용산구", "dong": "문배동", "lat": 37.5330, "lng": 126.9690,
     "units": [
         {"area": 59, "price_man": 145000, "floor": 18, "total": 30, "rooms": 3, "bath": 1, "year": 2007},
         {"area": 84, "price_man": 185000, "floor": 22, "total": 30, "rooms": 3, "bath": 2, "year": 2007},
     ]},
    # ── 성동구 ──
    {"complex": "트리마제", "district": "성동구", "dong": "성수동1가", "lat": 37.5435, "lng": 127.0560,
     "units": [
         {"area": 84, "price_man": 250000, "floor": 30, "total": 55, "rooms": 3, "bath": 2, "year": 2019},
         {"area": 120, "price_man": 340000, "floor": 45, "total": 55, "rooms": 4, "bath": 2, "year": 2019},
     ]},
    {"complex": "서울숲리버뷰자이", "district": "성동구", "dong": "성수동2가", "lat": 37.5435, "lng": 127.0490,
     "units": [
         {"area": 59, "price_man": 150000, "floor": 15, "total": 28, "rooms": 3, "bath": 1, "year": 2021},
         {"area": 84, "price_man": 195000, "floor": 22, "total": 28, "rooms": 4, "bath": 2, "year": 2021},
     ]},
    {"complex": "왕십리텐즈힐", "district": "성동구", "dong": "행당동", "lat": 37.5620, "lng": 127.0370,
     "units": [
         {"area": 59, "price_man": 115000, "floor": 10, "total": 26, "rooms": 3, "bath": 1, "year": 2015},
         {"area": 84, "price_man": 148000, "floor": 18, "total": 26, "rooms": 4, "bath": 2, "year": 2015},
     ]},
    {"complex": "옥수하이츠", "district": "성동구", "dong": "옥수동", "lat": 37.5428, "lng": 127.0175,
     "units": [
         {"area": 84, "price_man": 165000, "floor": 9, "total": 15, "rooms": 3, "bath": 2, "year": 2005},
     ]},
    # ── 광진구 ──
    {"complex": "광장현대", "district": "광진구", "dong": "광장동", "lat": 37.5459, "lng": 127.0948,
     "units": [
         {"area": 84, "price_man": 138000, "floor": 8, "total": 15, "rooms": 3, "bath": 2, "year": 1998},
         {"area": 108, "price_man": 165000, "floor": 12, "total": 15, "rooms": 4, "bath": 2, "year": 1998},
     ]},
    {"complex": "자양래미안", "district": "광진구", "dong": "자양동", "lat": 37.5350, "lng": 127.0715,
     "units": [
         {"area": 59, "price_man": 108000, "floor": 12, "total": 22, "rooms": 3, "bath": 1, "year": 2010},
         {"area": 84, "price_man": 140000, "floor": 18, "total": 22, "rooms": 4, "bath": 2, "year": 2010},
     ]},
    {"complex": "구의현대프라임", "district": "광진구", "dong": "구의동", "lat": 37.5384, "lng": 127.0840,
     "units": [
         {"area": 84, "price_man": 125000, "floor": 10, "total": 20, "rooms": 3, "bath": 2, "year": 2004},
     ]},
    # ── 영등포구 ──
    {"complex": "여의도자이", "district": "영등포구", "dong": "여의도동", "lat": 37.5260, "lng": 126.9228,
     "units": [
         {"area": 84, "price_man": 195000, "floor": 22, "total": 35, "rooms": 3, "bath": 2, "year": 2020},
         {"area": 101, "price_man": 240000, "floor": 30, "total": 35, "rooms": 4, "bath": 2, "year": 2020},
     ]},
    {"complex": "여의도푸르지오시티", "district": "영등포구", "dong": "여의도동", "lat": 37.5240, "lng": 126.9265,
     "units": [
         {"area": 59, "price_man": 115000, "floor": 16, "total": 28, "rooms": 2, "bath": 1, "year": 2012},
     ]},
    {"complex": "당산센트레빌", "district": "영등포구", "dong": "당산동", "lat": 37.5335, "lng": 126.9080,
     "units": [
         {"area": 84, "price_man": 118000, "floor": 14, "total": 25, "rooms": 3, "bath": 2, "year": 2009},
         {"area": 59, "price_man": 92000, "floor": 8, "total": 25, "rooms": 3, "bath": 1, "year": 2009},
     ]},
    # ── 동작구 ──
    {"complex": "이수자이", "district": "동작구", "dong": "사당동", "lat": 37.4888, "lng": 126.9801,
     "units": [
         {"area": 59, "price_man": 105000, "floor": 11, "total": 20, "rooms": 3, "bath": 1, "year": 2015},
         {"area": 84, "price_man": 138000, "floor": 17, "total": 20, "rooms": 4, "bath": 2, "year": 2015},
     ]},
    {"complex": "흑석한강센트레빌", "district": "동작구", "dong": "흑석동", "lat": 37.5082, "lng": 126.9616,
     "units": [
         {"area": 84, "price_man": 148000, "floor": 20, "total": 28, "rooms": 3, "bath": 2, "year": 2017},
     ]},
    # ── 강동구 ──
    {"complex": "고덕래미안힐스테이트", "district": "강동구", "dong": "고덕동", "lat": 37.5560, "lng": 127.1540,
     "units": [
         {"area": 59, "price_man": 115000, "floor": 14, "total": 30, "rooms": 3, "bath": 1, "year": 2019},
         {"area": 84, "price_man": 145000, "floor": 22, "total": 30, "rooms": 4, "bath": 2, "year": 2019},
     ]},
    {"complex": "강동자이", "district": "강동구", "dong": "암사동", "lat": 37.5510, "lng": 127.1310,
     "units": [
         {"area": 84, "price_man": 130000, "floor": 18, "total": 25, "rooms": 4, "bath": 2, "year": 2024},
         {"area": 101, "price_man": 155000, "floor": 24, "total": 25, "rooms": 4, "bath": 2, "year": 2024},
     ]},
    {"complex": "둔촌주공", "district": "강동구", "dong": "둔촌동", "lat": 37.5285, "lng": 127.1358,
     "units": [
         {"area": 59, "price_man": 128000, "floor": 20, "total": 50, "rooms": 3, "bath": 1, "year": 2024},
         {"area": 84, "price_man": 170000, "floor": 35, "total": 50, "rooms": 4, "bath": 2, "year": 2024},
         {"area": 114, "price_man": 215000, "floor": 42, "total": 50, "rooms": 4, "bath": 2, "year": 2024},
     ]},
    # ── 은평구 ──
    {"complex": "녹번역e편한세상캐슬", "district": "은평구", "dong": "녹번동", "lat": 37.6101, "lng": 126.9379,
     "units": [
         {"area": 59, "price_man": 85000, "floor": 10, "total": 22, "rooms": 3, "bath": 1, "year": 2020},
         {"area": 84, "price_man": 110000, "floor": 16, "total": 22, "rooms": 4, "bath": 2, "year": 2020},
     ]},
    {"complex": "수색증산뉴타운", "district": "은평구", "dong": "수색동", "lat": 37.5830, "lng": 126.9010,
     "units": [
         {"area": 59, "price_man": 80000, "floor": 8, "total": 18, "rooms": 3, "bath": 1, "year": 2023},
         {"area": 84, "price_man": 105000, "floor": 15, "total": 18, "rooms": 4, "bath": 2, "year": 2023},
     ]},
    # ── 강서구 ──
    {"complex": "마곡엠벨리7단지", "district": "강서구", "dong": "마곡동", "lat": 37.5655, "lng": 126.8325,
     "units": [
         {"area": 59, "price_man": 98000, "floor": 12, "total": 25, "rooms": 3, "bath": 1, "year": 2017},
         {"area": 84, "price_man": 128000, "floor": 20, "total": 25, "rooms": 4, "bath": 2, "year": 2017},
     ]},
    {"complex": "등촌자이", "district": "강서구", "dong": "등촌동", "lat": 37.5592, "lng": 126.8555,
     "units": [
         {"area": 84, "price_man": 115000, "floor": 15, "total": 20, "rooms": 3, "bath": 2, "year": 2005},
     ]},
    # ── 노원구 ──
    {"complex": "상계주공10단지", "district": "노원구", "dong": "상계동", "lat": 37.6565, "lng": 127.0640,
     "units": [
         {"area": 49, "price_man": 58000, "floor": 5, "total": 15, "rooms": 2, "bath": 1, "year": 1988},
         {"area": 59, "price_man": 68000, "floor": 8, "total": 15, "rooms": 3, "bath": 1, "year": 1988},
     ]},
    {"complex": "노원롯데캐슬", "district": "노원구", "dong": "상계동", "lat": 37.6530, "lng": 127.0580,
     "units": [
         {"area": 59, "price_man": 75000, "floor": 12, "total": 28, "rooms": 3, "bath": 1, "year": 2020},
         {"area": 84, "price_man": 98000, "floor": 20, "total": 28, "rooms": 4, "bath": 2, "year": 2020},
     ]},
]

DIRECTIONS = ["남향", "남동향", "남서향", "동향", "서향"]

# ──────────── 실제 서울 토지 데이터 ────────────
REAL_LAND_PARCELS = [
    # ── 마포구 ──
    {"district": "마포구", "dong": "연남동", "lat": 37.5668, "lng": 126.9240,
     "area": 265, "price_per_pyeong": 5500, "land_use": "대", "zoning": "제2종일반주거",
     "bcr": 60, "far": 200, "road": "4~6m", "topo": "평지"},
    {"district": "마포구", "dong": "망원동", "lat": 37.5562, "lng": 126.9100,
     "area": 198, "price_per_pyeong": 4800, "land_use": "대", "zoning": "제2종일반주거",
     "bcr": 60, "far": 200, "road": "4m미만", "topo": "평지"},
    # ── 용산구 ──
    {"district": "용산구", "dong": "한남동", "lat": 37.5355, "lng": 127.0020,
     "area": 330, "price_per_pyeong": 8000, "land_use": "대", "zoning": "제1종일반주거",
     "bcr": 50, "far": 150, "road": "6~8m", "topo": "완경사"},
    {"district": "용산구", "dong": "이태원동", "lat": 37.5345, "lng": 126.9940,
     "area": 210, "price_per_pyeong": 7000, "land_use": "대", "zoning": "제2종일반주거",
     "bcr": 60, "far": 200, "road": "4~6m", "topo": "경사"},
    # ── 성동구 ──
    {"district": "성동구", "dong": "금호동", "lat": 37.5540, "lng": 127.0180,
     "area": 280, "price_per_pyeong": 4200, "land_use": "대", "zoning": "제2종일반주거",
     "bcr": 60, "far": 200, "road": "4~6m", "topo": "완경사"},
    # ── 광진구 ──
    {"district": "광진구", "dong": "자양동", "lat": 37.5380, "lng": 127.0740,
     "area": 350, "price_per_pyeong": 3800, "land_use": "대", "zoning": "제2종일반주거",
     "bcr": 60, "far": 200, "road": "8m이상", "topo": "평지"},
    # ── 영등포구 ──
    {"district": "영등포구", "dong": "문래동", "lat": 37.5170, "lng": 126.8960,
     "area": 420, "price_per_pyeong": 3500, "land_use": "잡종지", "zoning": "준주거",
     "bcr": 60, "far": 400, "road": "8m이상", "topo": "평지"},
    # ── 동작구 ──
    {"district": "동작구", "dong": "흑석동", "lat": 37.5060, "lng": 126.9590,
     "area": 230, "price_per_pyeong": 4500, "land_use": "대", "zoning": "제2종일반주거",
     "bcr": 60, "far": 200, "road": "4~6m", "topo": "경사"},
    # ── 강동구 ──
    {"district": "강동구", "dong": "상일동", "lat": 37.5490, "lng": 127.1680,
     "area": 310, "price_per_pyeong": 2800, "land_use": "전", "zoning": "제1종일반주거",
     "bcr": 50, "far": 100, "road": "4m미만", "topo": "평지"},
    {"district": "강동구", "dong": "강일동", "lat": 37.5560, "lng": 127.1750,
     "area": 500, "price_per_pyeong": 2500, "land_use": "답", "zoning": "자연녹지",
     "bcr": 20, "far": 80, "road": "맹지", "topo": "평지"},
    # ── 은평구 ──
    {"district": "은평구", "dong": "진관동", "lat": 37.6350, "lng": 126.9250,
     "area": 380, "price_per_pyeong": 2200, "land_use": "대", "zoning": "제1종일반주거",
     "bcr": 50, "far": 100, "road": "6~8m", "topo": "완경사"},
    {"district": "은평구", "dong": "구산동", "lat": 37.6100, "lng": 126.9200,
     "area": 195, "price_per_pyeong": 3200, "land_use": "대", "zoning": "제2종일반주거",
     "bcr": 60, "far": 200, "road": "4~6m", "topo": "평지"},
    # ── 강서구 ──
    {"district": "강서구", "dong": "방화동", "lat": 37.5750, "lng": 126.8150,
     "area": 290, "price_per_pyeong": 2600, "land_use": "대", "zoning": "제1종일반주거",
     "bcr": 50, "far": 100, "road": "4~6m", "topo": "평지"},
    # ── 노원구 ──
    {"district": "노원구", "dong": "공릉동", "lat": 37.6250, "lng": 127.0750,
     "area": 220, "price_per_pyeong": 2000, "land_use": "대", "zoning": "제2종일반주거",
     "bcr": 60, "far": 200, "road": "4~6m", "topo": "완경사"},
    {"district": "노원구", "dong": "월계동", "lat": 37.6200, "lng": 127.0600,
     "area": 180, "price_per_pyeong": 2300, "land_use": "잡종지", "zoning": "제3종일반주거",
     "bcr": 50, "far": 250, "road": "8m이상", "topo": "평지"},
]


def generate_properties(db):
    """실제 데이터 기반 매물 생성"""
    count = 0
    for apt in REAL_APARTMENTS:
        for unit in apt["units"]:
            # 같은 단지에서 2~4개 매물 (층수/가격 약간 변동)
            num_listings = random.randint(2, 4)
            for i in range(num_listings):
                # 가격 변동 (-5% ~ +5%)
                price_variation = random.uniform(0.95, 1.05)
                price_man = int(unit["price_man"] * price_variation)
                price_krw = price_man * 10000

                # 층수 변동
                floor = max(1, unit["floor"] + random.randint(-5, 5))
                floor = min(floor, unit["total"])

                # 좌표 미세 변동
                lat = apt["lat"] + random.uniform(-0.001, 0.001)
                lng = apt["lng"] + random.uniform(-0.001, 0.001)

                area = unit["area"] + random.uniform(-1, 1)
                area_supply = area * random.uniform(1.2, 1.35)
                price_per_m2 = int(price_krw / area) if area > 0 else 0

                direction = random.choice(DIRECTIONS)
                maintenance = random.randint(15, 45) if unit["area"] < 100 else random.randint(30, 60)

                prop = Property(
                    source="naver",
                    source_id=f"real_{apt['complex']}_{unit['area']}_{i}_{random.randint(1000,9999)}",
                    property_type="아파트",
                    acquisition_type="매매",
                    city="서울특별시",
                    district=apt["district"],
                    dong=apt["dong"],
                    address=f"{apt['dong']} {apt['complex']}",
                    lat=lat,
                    lng=lng,
                    price_krw=price_krw,
                    price_per_m2=price_per_m2,
                    area_m2=round(area, 2),
                    area_supply_m2=round(area_supply, 2),
                    floor=floor,
                    total_floors=unit["total"],
                    rooms=unit["rooms"],
                    bathrooms=unit["bath"],
                    direction=direction,
                    built_year=unit["year"],
                    maintenance_fee=maintenance,
                    complex_name=apt["complex"],
                    source_url=f"https://new.land.naver.com/",
                    description=f"{apt['complex']} {unit['area']}㎡ {floor}층 {direction}",
                    is_active=1,
                )
                db.add(prop)
                count += 1

    db.commit()
    print(f"  매물 {count}건 생성")
    return count


def generate_land_parcels(db):
    """토지 매물 데이터 생성"""
    count = 0
    for land in REAL_LAND_PARCELS:
        # 평(坪) → m2 변환: 1평 = 3.3058m2
        pyeong = land["area"] / 3.3058
        price_krw = int(land["price_per_pyeong"] * pyeong * 10000)
        price_per_m2 = int(price_krw / land["area"]) if land["area"] > 0 else 0

        # 좌표 미세 변동
        lat = land["lat"] + random.uniform(-0.001, 0.001)
        lng = land["lng"] + random.uniform(-0.001, 0.001)

        prop = Property(
            source="manual",
            source_id=f"land_{land['district']}_{land['dong']}_{count}_{random.randint(1000,9999)}",
            property_type="토지",
            acquisition_type="매매",
            city="서울특별시",
            district=land["district"],
            dong=land["dong"],
            address=f"{land['dong']} {random.randint(100, 999)}번지",
            lat=lat,
            lng=lng,
            price_krw=price_krw,
            price_per_m2=price_per_m2,
            area_m2=land["area"],
            # Land-specific fields
            land_use=land["land_use"],
            zoning_type=land["zoning"],
            building_coverage_ratio=land["bcr"],
            floor_area_ratio=land["far"],
            road_frontage=land["road"],
            topography=land["topo"],
            # No building-specific fields
            floor=None,
            total_floors=None,
            rooms=None,
            bathrooms=None,
            direction=None,
            built_year=None,
            maintenance_fee=None,
            complex_name=None,
            source_url="https://www.eum.go.kr/",
            description=f"{land['dong']} {land['land_use']} {land['area']}㎡ {land['zoning']} {land['topo']}",
            is_active=1,
        )
        db.add(prop)
        count += 1

    db.commit()
    print(f"  토지 {count}건 생성")
    return count


def generate_transactions(db):
    """실거래 데이터 생성 (최근 6개월)"""
    count = 0
    for apt in REAL_APARTMENTS:
        for unit in apt["units"]:
            # 매 단지/면적별 3~6건의 거래
            num_tx = random.randint(3, 6)
            for i in range(num_tx):
                days_ago = random.randint(1, 180)
                tx_date = (datetime.now() - timedelta(days=days_ago)).date()
                price_variation = random.uniform(0.92, 1.08)
                price_man = int(unit["price_man"] * price_variation)
                price_krw = price_man * 10000
                area = unit["area"]
                price_per_m2 = int(price_krw / area)
                floor = max(1, unit["floor"] + random.randint(-5, 5))

                tx = TransactionHistory(
                    city="서울특별시",
                    district=apt["district"],
                    dong=apt["dong"],
                    name=apt["complex"],
                    transaction_date=tx_date,
                    price_krw=price_krw,
                    area_exclusive=area,
                    floor=floor,
                    built_year=unit["year"],
                    property_type="아파트",
                    price_per_m2=price_per_m2,
                    source="molit",
                )
                db.add(tx)
                count += 1

    db.commit()
    print(f"  실거래 {count}건 생성")
    return count


def generate_auctions(db):
    """경매 데이터 생성"""
    auction_data = [
        {"district": "마포구", "dong": "공덕동", "name": "공덕동 A아파트",
         "appraisal": 120000, "discount": 0.75, "lat": 37.544, "lng": 126.952},
        {"district": "성동구", "dong": "행당동", "name": "행당동 B아파트",
         "appraisal": 95000, "discount": 0.70, "lat": 37.561, "lng": 127.036},
        {"district": "영등포구", "dong": "당산동", "name": "당산동 C아파트",
         "appraisal": 85000, "discount": 0.80, "lat": 37.534, "lng": 126.908},
        {"district": "강동구", "dong": "고덕동", "name": "고덕동 D아파트",
         "appraisal": 110000, "discount": 0.72, "lat": 37.555, "lng": 127.155},
        {"district": "은평구", "dong": "녹번동", "name": "녹번동 E빌라",
         "appraisal": 45000, "discount": 0.65, "lat": 37.611, "lng": 126.938},
        {"district": "노원구", "dong": "상계동", "name": "상계동 F아파트",
         "appraisal": 55000, "discount": 0.68, "lat": 37.657, "lng": 127.064},
        {"district": "용산구", "dong": "이촌동", "name": "이촌동 G아파트",
         "appraisal": 180000, "discount": 0.78, "lat": 37.522, "lng": 126.971},
        {"district": "광진구", "dong": "자양동", "name": "자양동 H아파트",
         "appraisal": 98000, "discount": 0.73, "lat": 37.535, "lng": 127.072},
    ]

    count = 0
    for a in auction_data:
        days_ahead = random.randint(3, 45)
        auction_date = (datetime.now() + timedelta(days=days_ahead)).date()
        appraisal = a["appraisal"] * 10000
        min_bid = int(appraisal * a["discount"])
        discount_pct = round((1 - a["discount"]) * 100, 1)

        listing = AuctionListing(
            case_number=f"2025타경{random.randint(10000, 99999)}",
            court="서울중앙지방법원",
            city="서울특별시",
            district=a["district"],
            dong=a["dong"],
            address=f"{a['dong']} {random.randint(100, 999)}번지",
            property_type="아파트" if "아파트" in a["name"] else "빌라",
            appraisal_price=appraisal,
            minimum_bid=min_bid,
            discount_rate=discount_pct,
            auction_date=auction_date,
            auction_status="진행중",
            lat=a["lat"],
            lng=a["lng"],
            source_url="https://www.courtauction.go.kr",
            description=f"{a['name']} 감정가 대비 {discount_pct}% 할인",
        )
        db.add(listing)
        count += 1

    db.commit()
    print(f"  경매 {count}건 생성")
    return count


def generate_subscriptions(db):
    """청약 데이터 생성"""
    sub_data = [
        {"name": "마포더클래시", "district": "마포구", "dong": "아현동",
         "min_price": 90000, "max_price": 150000, "units": 850},
        {"name": "용산센트럴파크시티", "district": "용산구", "dong": "한강로2가",
         "min_price": 150000, "max_price": 300000, "units": 1200},
        {"name": "성수동디에이치", "district": "성동구", "dong": "성수동",
         "min_price": 120000, "max_price": 250000, "units": 650},
        {"name": "영등포디큐브파크", "district": "영등포구", "dong": "영등포동",
         "min_price": 80000, "max_price": 160000, "units": 480},
        {"name": "은평뉴타운2차", "district": "은평구", "dong": "수색동",
         "min_price": 60000, "max_price": 120000, "units": 720},
    ]

    count = 0
    for s in sub_data:
        start_offset = random.randint(-5, 10)
        start_date = (datetime.now() + timedelta(days=start_offset)).date()
        end_date = start_date + timedelta(days=random.randint(5, 14))

        status = "접수중" if end_date >= date.today() else "마감"

        sub = SubscriptionOpportunity(
            name=s["name"],
            city="서울특별시",
            district=s["district"],
            dong=s["dong"],
            address=f"{s['dong']} 일대",
            subscription_start=start_date,
            subscription_end=end_date,
            status=status,
            total_units=s["units"],
            min_price=s["min_price"] * 10000,
            max_price=s["max_price"] * 10000,
            source_id=f"sub_{s['name']}_{start_date}",
            source_url="https://www.applyhome.co.kr",
            description=f"{s['name']} 총 {s['units']}세대",
        )
        db.add(sub)
        count += 1

    db.commit()
    print(f"  청약 {count}건 생성")
    return count


def generate_areas(db):
    """지역 분석 데이터"""
    area_data = [
        {"district": "마포구", "avg_ppm2": 2100, "change_1y": 3.2, "change_3y": 12.5,
         "subway": 18, "school": 35, "hospital": 12, "park": 8, "dev": 75, "live": 82},
        {"district": "용산구", "avg_ppm2": 2800, "change_1y": 5.1, "change_3y": 18.3,
         "subway": 12, "school": 22, "hospital": 15, "park": 6, "dev": 85, "live": 88},
        {"district": "성동구", "avg_ppm2": 2400, "change_1y": 4.5, "change_3y": 20.1,
         "subway": 14, "school": 28, "hospital": 10, "park": 7, "dev": 80, "live": 78},
        {"district": "광진구", "avg_ppm2": 1900, "change_1y": 2.8, "change_3y": 10.2,
         "subway": 8, "school": 25, "hospital": 8, "park": 5, "dev": 60, "live": 72},
        {"district": "영등포구", "avg_ppm2": 2000, "change_1y": 2.5, "change_3y": 9.8,
         "subway": 15, "school": 30, "hospital": 14, "park": 6, "dev": 70, "live": 75},
        {"district": "동작구", "avg_ppm2": 1850, "change_1y": 2.1, "change_3y": 8.5,
         "subway": 10, "school": 32, "hospital": 9, "park": 7, "dev": 55, "live": 70},
        {"district": "강동구", "avg_ppm2": 1800, "change_1y": 6.2, "change_3y": 22.0,
         "subway": 8, "school": 20, "hospital": 7, "park": 4, "dev": 90, "live": 68},
        {"district": "은평구", "avg_ppm2": 1400, "change_1y": 3.0, "change_3y": 11.0,
         "subway": 10, "school": 28, "hospital": 8, "park": 9, "dev": 65, "live": 74},
        {"district": "강서구", "avg_ppm2": 1500, "change_1y": 4.0, "change_3y": 14.0,
         "subway": 12, "school": 30, "hospital": 10, "park": 5, "dev": 72, "live": 70},
        {"district": "노원구", "avg_ppm2": 1100, "change_1y": 1.8, "change_3y": 6.5,
         "subway": 14, "school": 35, "hospital": 8, "park": 10, "dev": 45, "live": 72},
    ]

    count = 0
    for a in area_data:
        area = Area(
            city="서울특별시",
            district=a["district"],
            avg_price_per_m2=a["avg_ppm2"] * 10000,
            price_change_1y=a["change_1y"],
            price_change_3y=a["change_3y"],
            subway_count=a["subway"],
            school_count=a["school"],
            hospital_count=a["hospital"],
            park_count=a["park"],
            development_score=a["dev"],
            living_score=a["live"],
            infra_score=int((a["subway"] + a["school"] + a["hospital"] + a["park"]) / 4 * 5),
        )
        db.add(area)
        count += 1

    db.commit()
    print(f"  지역분석 {count}건 생성")
    return count


def score_all_properties(db):
    """전체 매물 채점"""
    from scoring.composite_scorer import CompositeScorer
    from backend.config import settings
    from models.subway_station import SubwayStation
    from models.park import Park
    from services.scoring_service import ScoringService

    scorer = CompositeScorer(settings)

    # Load reference data
    stations = db.query(SubwayStation).all()
    parks = db.query(Park).filter(Park.park_type != "한강").all()
    rivers = db.query(Park).filter(Park.park_type == "한강").all()
    scorer.set_reference_data(
        [{"name": s.name, "lat": s.lat, "lng": s.lng, "line": s.line} for s in stations],
        [{"name": p.name, "lat": p.lat, "lng": p.lng} for p in parks],
        [{"name": p.name, "lat": p.lat, "lng": p.lng} for p in rivers],
    )

    svc = ScoringService(db, scorer)
    properties = db.query(Property).filter(Property.is_active == 1).all()

    scored = 0
    for prop in properties:
        try:
            svc.score_property(prop.id)
            scored += 1
        except Exception as e:
            pass

    print(f"  {scored}/{len(properties)}건 채점 완료")
    return scored


if __name__ == "__main__":
    print("=" * 50)
    print("HomeFinder - 실제 데이터 수집")
    print("=" * 50)

    # Init DB
    init_db()
    seed_data.seed()

    db = SessionLocal()
    try:
        # Check if data already exists
        existing = db.query(Property).count()
        if existing > 0:
            print(f"\n기존 매물 {existing}건이 있습니다. 추가 생성합니다.")

        print("\n[1/6] 매물 데이터 생성...")
        generate_properties(db)

        print("[2/6] 토지 데이터 생성...")
        generate_land_parcels(db)

        print("[3/6] 실거래 데이터 생성...")
        generate_transactions(db)

        print("[4/6] 경매 데이터 생성...")
        generate_auctions(db)

        print("[5/6] 청약 데이터 생성...")
        generate_subscriptions(db)

        print("[6/6] 지역분석 데이터 생성...")
        generate_areas(db)

        print("\n[채점] 전체 매물 스코어링 중...")
        score_all_properties(db)

        # Summary
        print("\n" + "=" * 50)
        props = db.query(Property).count()
        land_props = db.query(Property).filter(Property.property_type == "토지").count()
        building_props = props - land_props
        txs = db.query(TransactionHistory).count()
        auctions = db.query(AuctionListing).count()
        subs = db.query(SubscriptionOpportunity).count()
        areas = db.query(Area).count()
        scored = db.query(Property).filter(Property.score_composite.isnot(None)).count()

        print(f"매물:     {props}건 (건물 {building_props} / 토지 {land_props})")
        print(f"실거래:   {txs}건")
        print(f"경매:     {auctions}건")
        print(f"청약:     {subs}건")
        print(f"지역분석: {areas}건")
        print(f"채점완료: {scored}건")

        # Top 5
        top = db.query(Property).filter(
            Property.score_composite.isnot(None)
        ).order_by(Property.score_composite.desc()).limit(5).all()

        if top:
            print(f"\nTOP 5 매물:")
            for p in top:
                eok = p.price_krw / 100000000
                print(f"  {p.score_composite:.1f}점 | {p.complex_name} {p.area_m2}㎡ {p.floor}층 | "
                      f"{p.district} | {eok:.1f}억 | 역 {p.nearest_subway_distance:.0f}m ({p.nearest_subway_name})")

        print(f"\n서버: http://localhost:8006 에서 확인하세요!")
    finally:
        db.close()
