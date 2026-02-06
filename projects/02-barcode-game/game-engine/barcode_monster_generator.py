"""
BarcodeQuest - 바코드 기반 몬스터 생성 엔진 (특허 핵심 기술)

[특허 출원 대상]
발명의 명칭: "상품 바코드 정보 기반 게임 캐릭터 생성 시스템 및 방법"

핵심 기술:
1. EAN-13 바코드의 구조적 정보(국가코드, 제조사코드, 상품코드)를 분석
2. 각 코드 세그먼트를 게임 캐릭터의 속성(타입, 능력치, 외형)에 매핑
3. GPS 위치 정보와 결합하여 위치 기반 보너스 및 희귀도 차별화
4. 동일 바코드 + 다른 위치 = 다른 변형(Variant) 생성
5. 시간대(아침/낮/밤) 결합으로 추가 차별화

EAN-13 바코드 구조:
┌─────────┬──────────┬───────────┬──────┐
│ 국가코드 │ 제조사코드 │ 상품코드   │ 검증 │
│ (3자리)  │ (4-5자리) │ (4-5자리)  │ (1)  │
└─────────┴──────────┴───────────┴──────┘
예: 880 1062 87124 7
    한국  롯데  초코파이  체크
"""

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Optional
from enum import Enum


# === 몬스터 타입 정의 ===
class MonsterType(Enum):
    FIRE = "Fire"
    WATER = "Water"
    EARTH = "Earth"
    WIND = "Wind"
    FOOD = "Food"
    TECH = "Tech"
    NATURE = "Nature"
    SPIRIT = "Spirit"
    DARK = "Dark"
    LIGHT = "Light"


class Rarity(Enum):
    COMMON = "Common"       # 60%
    UNCOMMON = "Uncommon"   # 25%
    RARE = "Rare"           # 10%
    EPIC = "Epic"           # 4%
    LEGENDARY = "Legendary" # 1%


# === 국가 코드 → 몬스터 원산지/속성 매핑 ===
COUNTRY_CODE_MAP = {
    # 한국
    "880": {"region": "Korea", "primary_type": MonsterType.FOOD, "stat_bonus": "hp"},
    # 일본
    "490": {"region": "Japan", "primary_type": MonsterType.TECH, "stat_bonus": "atk"},
    "491": {"region": "Japan", "primary_type": MonsterType.TECH, "stat_bonus": "atk"},
    # 중국
    "690": {"region": "China", "primary_type": MonsterType.EARTH, "stat_bonus": "def"},
    "691": {"region": "China", "primary_type": MonsterType.EARTH, "stat_bonus": "def"},
    # 미국/캐나다
    "000": {"region": "USA", "primary_type": MonsterType.FIRE, "stat_bonus": "atk"},
    "001": {"region": "USA", "primary_type": MonsterType.FIRE, "stat_bonus": "atk"},
    # 프랑스
    "300": {"region": "France", "primary_type": MonsterType.WIND, "stat_bonus": "spd"},
    # 독일
    "400": {"region": "Germany", "primary_type": MonsterType.TECH, "stat_bonus": "def"},
    # 영국
    "500": {"region": "UK", "primary_type": MonsterType.SPIRIT, "stat_bonus": "hp"},
    # 태국
    "885": {"region": "Thailand", "primary_type": MonsterType.NATURE, "stat_bonus": "spd"},
    # 호주
    "930": {"region": "Australia", "primary_type": MonsterType.NATURE, "stat_bonus": "atk"},
}

# === 제조사 카테고리 → 서브타입 매핑 ===
# 실제 서비스에서는 바코드 DB(GS1)를 참조
MANUFACTURER_CATEGORY = {
    # 식품
    "food": {"sub_type": MonsterType.FOOD, "name_prefix": ["Choco", "Noodle", "Rice", "Honey", "Spice"]},
    # 음료
    "beverage": {"sub_type": MonsterType.WATER, "name_prefix": ["Aqua", "Fizz", "Milk", "Juice", "Tea"]},
    # 과자/스낵
    "snack": {"sub_type": MonsterType.FIRE, "name_prefix": ["Crunch", "Crispy", "Sweet", "Crunchy", "Puff"]},
    # 생활용품
    "household": {"sub_type": MonsterType.EARTH, "name_prefix": ["Clean", "Fresh", "Pure", "Soft", "Bright"]},
    # 전자제품
    "electronics": {"sub_type": MonsterType.TECH, "name_prefix": ["Volt", "Pixel", "Nano", "Cyber", "Robo"]},
    # 화장품
    "cosmetics": {"sub_type": MonsterType.LIGHT, "name_prefix": ["Glow", "Bloom", "Shine", "Silk", "Pearl"]},
}

# === 몬스터 외형 요소 ===
BODY_SHAPES = ["Dragon", "Fox", "Bear", "Bird", "Slime", "Golem", "Ghost", "Cat", "Wolf", "Turtle"]
COLORS = ["Crimson", "Azure", "Emerald", "Golden", "Violet", "Obsidian", "Crystal", "Amber", "Silver", "Rose"]
ACCESSORIES = ["Crown", "Scarf", "Shield", "Wings", "Horns", "Tail Ring", "Amulet", "Cape", "Goggles", "Bell"]


@dataclass
class MonsterStats:
    hp: int
    attack: int
    defense: int
    speed: int
    special: int


@dataclass
class Monster:
    """생성된 몬스터"""
    id: str                      # 고유 ID (바코드 + 위치 해시)
    name: str                    # 몬스터 이름
    barcode: str                 # 원본 바코드
    primary_type: str            # 주 타입
    secondary_type: str          # 부 타입
    rarity: str                  # 희귀도
    level: int                   # 초기 레벨
    stats: MonsterStats          # 능력치
    origin_country: str          # 원산지
    body_shape: str              # 외형
    color: str                   # 색상
    accessory: str               # 장식
    location_name: str           # 발견 위치
    location_bonus: float        # 위치 보너스 배율
    time_variant: str            # 시간대 변형 (Dawn/Day/Dusk/Night)
    special_trait: str           # 특수 특성
    discovery_timestamp: str     # 발견 시각

    def to_dict(self):
        return asdict(self)

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class BarcodeMonsterGenerator:
    """
    바코드 → 몬스터 변환 엔진

    [특허 핵심 알고리즘]
    1. 바코드 파싱: EAN-13 구조 분석
    2. 시드 생성: 바코드 + GPS + 시간 → 결정적 해시
    3. 속성 매핑: 해시값을 각 속성 범위에 분배
    4. 희귀도 결정: 바코드 체크섬 + 위치 특수성으로 결정
    5. 몬스터 조립: 이름, 외형, 능력치, 특성 조합
    """

    def __init__(self):
        self.generated_count = 0

    def parse_barcode(self, barcode: str) -> dict:
        """
        EAN-13 바코드 파싱

        Args:
            barcode: 13자리 바코드 문자열

        Returns:
            dict: {country_code, manufacturer_code, product_code, check_digit}
        """
        barcode = barcode.replace("-", "").replace(" ", "")

        if len(barcode) != 13 or not barcode.isdigit():
            raise ValueError(f"Invalid EAN-13 barcode: {barcode}")

        return {
            "country_code": barcode[:3],
            "manufacturer_code": barcode[3:7],
            "product_code": barcode[7:12],
            "check_digit": barcode[12],
            "full": barcode,
        }

    def generate_seed(self, barcode: str, latitude: float = 0, longitude: float = 0,
                      hour: int = 12) -> str:
        """
        결정적 시드 생성

        같은 바코드 + 같은 위치 + 같은 시간대 = 항상 같은 몬스터
        다른 위치나 시간대 = 다른 변형(Variant)

        [특허 포인트] 바코드의 고유 정보와 컨텍스트(위치, 시간)의 결합
        """
        # 위치를 격자 단위로 양자화 (약 1km 단위)
        lat_grid = round(latitude * 100) / 100
        lon_grid = round(longitude * 100) / 100

        # 시간대 분류
        if 5 <= hour < 10:
            time_period = "dawn"
        elif 10 <= hour < 17:
            time_period = "day"
        elif 17 <= hour < 21:
            time_period = "dusk"
        else:
            time_period = "night"

        # 시드 문자열
        seed_str = f"{barcode}|{lat_grid}|{lon_grid}|{time_period}"
        return hashlib.sha256(seed_str.encode()).hexdigest()

    def determine_rarity(self, barcode_data: dict, seed: str) -> Rarity:
        """
        희귀도 결정

        [특허 포인트] 바코드의 체크디짓과 시드 해시의 조합으로 결정적 희귀도 산출
        """
        check = int(barcode_data["check_digit"])
        seed_val = int(seed[:8], 16) % 1000

        # 체크디짓이 7인 바코드는 기본 희귀도 상승
        rarity_score = seed_val
        if check == 7:
            rarity_score += 100
        if check == 0:
            rarity_score += 50

        # 제조사 코드의 특수 패턴
        mfg = barcode_data["manufacturer_code"]
        if mfg[0] == mfg[-1]:  # 팰린드롬 패턴
            rarity_score += 150

        # 상품 코드의 반복 패턴
        prod = barcode_data["product_code"]
        if len(set(prod)) <= 2:  # 2종류 이하의 숫자
            rarity_score += 200

        if rarity_score >= 900:
            return Rarity.LEGENDARY
        elif rarity_score >= 800:
            return Rarity.EPIC
        elif rarity_score >= 650:
            return Rarity.RARE
        elif rarity_score >= 400:
            return Rarity.UNCOMMON
        else:
            return Rarity.COMMON

    def generate_stats(self, seed: str, rarity: Rarity, country_info: dict) -> MonsterStats:
        """능력치 생성"""
        # 시드에서 각 능력치 추출
        base_multiplier = {
            Rarity.COMMON: 1.0,
            Rarity.UNCOMMON: 1.2,
            Rarity.RARE: 1.5,
            Rarity.EPIC: 1.8,
            Rarity.LEGENDARY: 2.2,
        }[rarity]

        s = seed
        hp = int(int(s[0:4], 16) % 100 + 50) * base_multiplier
        atk = int(int(s[4:8], 16) % 80 + 30) * base_multiplier
        defense = int(int(s[8:12], 16) % 70 + 25) * base_multiplier
        spd = int(int(s[12:16], 16) % 60 + 20) * base_multiplier
        spc = int(int(s[16:20], 16) % 50 + 15) * base_multiplier

        # 국가별 보너스
        bonus_stat = country_info.get("stat_bonus", "hp")
        if bonus_stat == "hp":
            hp *= 1.15
        elif bonus_stat == "atk":
            atk *= 1.15
        elif bonus_stat == "def":
            defense *= 1.15
        elif bonus_stat == "spd":
            spd *= 1.15

        return MonsterStats(
            hp=int(hp),
            attack=int(atk),
            defense=int(defense),
            speed=int(spd),
            special=int(spc),
        )

    def generate_name(self, seed: str, country_info: dict, barcode_data: dict) -> str:
        """몬스터 이름 생성"""
        s = seed
        prefix_idx = int(s[20:24], 16) % len(COLORS)
        body_idx = int(s[24:28], 16) % len(BODY_SHAPES)

        color = COLORS[prefix_idx]
        body = BODY_SHAPES[body_idx]

        return f"{color} {body}"

    def generate_appearance(self, seed: str) -> dict:
        """외형 결정"""
        s = seed
        return {
            "body_shape": BODY_SHAPES[int(s[28:32], 16) % len(BODY_SHAPES)],
            "color": COLORS[int(s[32:36], 16) % len(COLORS)],
            "accessory": ACCESSORIES[int(s[36:40], 16) % len(ACCESSORIES)],
        }

    def get_time_variant(self, hour: int) -> str:
        """시간대 변형"""
        if 5 <= hour < 10:
            return "Dawn"
        elif 10 <= hour < 17:
            return "Day"
        elif 17 <= hour < 21:
            return "Dusk"
        else:
            return "Night"

    def get_special_trait(self, rarity: Rarity, seed: str) -> str:
        """특수 특성 결정"""
        traits = {
            Rarity.COMMON: ["Quick Learner", "Hardy", "Friendly", "Curious", "Calm"],
            Rarity.UNCOMMON: ["Eagle Eye", "Iron Will", "Swift Strike", "Healer", "Lucky"],
            Rarity.RARE: ["Dragon Heart", "Shadow Step", "Thunder Call", "Ice Shield", "Fire Soul"],
            Rarity.EPIC: ["Dimension Rift", "Time Warp", "Star Fall", "Void Walker", "Soul Bind"],
            Rarity.LEGENDARY: ["Genesis Force", "Cosmic Ray", "Eternal Flame", "World Breaker", "Divine Light"],
        }
        idx = int(seed[40:44], 16) % 5
        return traits[rarity][idx]

    def calculate_location_bonus(self, latitude: float, longitude: float) -> tuple:
        """
        위치 기반 보너스 계산

        [특허 포인트] GPS 좌표를 기반으로 특수 위치 보너스 부여
        - 대형마트: +20% 능력치
        - 편의점: +10% ATK
        - 학교 근처: +15% EXP
        - 공원: +10% HP
        - 기본: +5%
        """
        # 실제 구현에서는 Google Places API나 Kakao Map API를 사용
        # 프로토타입에서는 좌표 해시로 시뮬레이션
        loc_hash = hashlib.md5(f"{latitude},{longitude}".encode()).hexdigest()
        loc_val = int(loc_hash[:4], 16) % 100

        if loc_val < 10:
            return 1.20, "Supermarket Zone"
        elif loc_val < 25:
            return 1.10, "Convenience Store"
        elif loc_val < 40:
            return 1.15, "School Area"
        elif loc_val < 55:
            return 1.10, "Park Area"
        else:
            return 1.05, "Standard Zone"

    def generate_monster(
        self,
        barcode: str,
        latitude: float = 37.5665,    # 기본: 서울 시청
        longitude: float = 126.9780,
        hour: int = 12,
        location_name: str = "Seoul",
    ) -> Monster:
        """
        메인 함수: 바코드 → 몬스터 생성

        [특허 핵심 프로세스]
        1. 바코드 파싱 → 국가/제조사/상품 정보 추출
        2. 컨텍스트(GPS + 시간) 결합 → 고유 시드 생성
        3. 시드 기반 결정적 속성 생성 (같은 입력 = 같은 출력)
        4. 위치 보너스 적용
        5. 최종 몬스터 객체 조립

        Args:
            barcode: EAN-13 바코드 (13자리)
            latitude: GPS 위도
            longitude: GPS 경도
            hour: 발견 시각 (0-23)
            location_name: 위치 이름

        Returns:
            Monster: 생성된 몬스터 객체
        """
        # Step 1: 바코드 파싱
        barcode_data = self.parse_barcode(barcode)

        # Step 2: 국가 정보 조회
        country_code = barcode_data["country_code"]
        country_info = COUNTRY_CODE_MAP.get(
            country_code,
            {"region": "Unknown", "primary_type": MonsterType.SPIRIT, "stat_bonus": "hp"}
        )

        # Step 3: 시드 생성
        seed = self.generate_seed(barcode, latitude, longitude, hour)

        # Step 4: 각 속성 결정
        rarity = self.determine_rarity(barcode_data, seed)
        stats = self.generate_stats(seed, rarity, country_info)
        name = self.generate_name(seed, country_info, barcode_data)
        appearance = self.generate_appearance(seed)
        time_variant = self.get_time_variant(hour)
        special_trait = self.get_special_trait(rarity, seed)
        location_bonus, location_zone = self.calculate_location_bonus(latitude, longitude)

        # Step 5: 위치 보너스 적용
        if location_bonus > 1.0:
            stats.hp = int(stats.hp * location_bonus)
            stats.attack = int(stats.attack * location_bonus)
            stats.defense = int(stats.defense * location_bonus)

        # 서브타입 결정 (제조사 코드 기반)
        mfg_hash = int(hashlib.md5(barcode_data["manufacturer_code"].encode()).hexdigest()[:4], 16)
        secondary_types = list(MonsterType)
        secondary_type = secondary_types[mfg_hash % len(secondary_types)]

        # 몬스터 ID 생성
        monster_id = seed[:16]

        self.generated_count += 1

        from datetime import datetime
        return Monster(
            id=monster_id,
            name=name,
            barcode=barcode,
            primary_type=country_info["primary_type"].value,
            secondary_type=secondary_type.value,
            rarity=rarity.value,
            level=max(1, int(int(seed[44:48], 16) % 5 + 1)),
            stats=stats,
            origin_country=country_info["region"],
            body_shape=appearance["body_shape"],
            color=appearance["color"],
            accessory=appearance["accessory"],
            location_name=location_name,
            location_bonus=location_bonus,
            time_variant=time_variant,
            special_trait=special_trait,
            discovery_timestamp=datetime.now().isoformat(),
        )


# === 데모 실행 ===
if __name__ == "__main__":
    generator = BarcodeMonsterGenerator()

    print("=" * 60)
    print("  BarcodeQuest - Monster Generator v1.0")
    print("  [Patent Core Technology Demo]")
    print("=" * 60)

    # 테스트 바코드들
    test_barcodes = [
        ("8801062871247", "Lotte Choco Pie", 37.5665, 126.9780, 14, "Seoul Gangnam"),
        ("8801043150842", "Nongshim Shin Ramyun", 37.5172, 127.0473, 12, "Seoul Songpa"),
        ("4902105231456", "Glico Pocky", 35.6762, 139.6503, 20, "Tokyo Shibuya"),
        ("0012345678905", "American Snack", 40.7128, -74.0060, 9, "New York"),
        ("8801115114505", "Seoul Milk", 37.5665, 126.9780, 3, "Seoul Gangnam (Night)"),
    ]

    for barcode, desc, lat, lon, hour, loc in test_barcodes:
        print(f"\n{'─' * 50}")
        print(f"Scanning: {desc} ({barcode})")
        print(f"Location: {loc} | Time: {hour}:00")

        monster = generator.generate_monster(barcode, lat, lon, hour, loc)

        print(f"\n  Name: {monster.name}")
        print(f"  Type: {monster.primary_type} / {monster.secondary_type}")
        print(f"  Rarity: {monster.rarity}")
        print(f"  Level: {monster.level}")
        print(f"  Stats: HP={monster.stats.hp} ATK={monster.stats.attack} "
              f"DEF={monster.stats.defense} SPD={monster.stats.speed} SPC={monster.stats.special}")
        print(f"  Appearance: {monster.color} {monster.body_shape} with {monster.accessory}")
        print(f"  Origin: {monster.origin_country}")
        print(f"  Time: {monster.time_variant}")
        print(f"  Location Bonus: x{monster.location_bonus}")
        print(f"  Special Trait: {monster.special_trait}")

    # 같은 바코드, 다른 위치 → 다른 몬스터 시연
    print(f"\n\n{'=' * 60}")
    print("  [Same Barcode, Different Location = Different Variant]")
    print(f"{'=' * 60}")

    barcode = "8801062871247"
    locations = [
        (37.5665, 126.9780, "Seoul"),
        (35.1796, 129.0756, "Busan"),
        (33.4996, 126.5312, "Jeju"),
    ]
    for lat, lon, city in locations:
        m = generator.generate_monster(barcode, lat, lon, 12, city)
        print(f"\n  {city}: {m.name} ({m.rarity}) - "
              f"HP:{m.stats.hp} ATK:{m.stats.attack} - {m.special_trait}")
