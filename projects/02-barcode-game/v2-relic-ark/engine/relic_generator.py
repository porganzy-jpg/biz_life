"""
잔해 방주 (RELIC ARK) — 성문 해독 엔진
바코드(EAN-13 / ISBN-13 / UPC-A) → 유물 카드(RelicCard) 결정적 생성

v1 barcode_monster_generator.py(특허 핵심)의 파싱·시드·희귀도 로직을 승계하고,
결과물을 "몬스터"에서 "유물 카드"로 바꿨다.

원칙: 같은 바코드 = 전 세계 누구에게나 같은 유물. (도감·거래·희귀도의 전제)
      시각·위치는 '변조(variant)'에만 쓰고 정체(identity)에는 쓰지 않는다.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ─────────────────────────────────────────────────────────────
# 열거형
# ─────────────────────────────────────────────────────────────
class Category(str, Enum):
    FOOD = "food"                 # 식품
    DRINK = "drink"               # 음료·주류
    MEDICAL = "medical"           # 의약·화장품·세제 (화학)
    ELECTRONICS = "electronics"   # 전자·배터리
    STATIONERY = "stationery"     # 문구·완구
    BOOK = "book"                 # 도서 (ISBN)
    APPAREL = "apparel"           # 의류·잡화
    TOBACCO = "tobacco"           # 담배·주류 (교역 화폐)
    UNKNOWN = "unknown"           # 정체불명 유물


class Rarity(str, Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"


RARITY_ORDER = [Rarity.COMMON, Rarity.UNCOMMON, Rarity.RARE, Rarity.EPIC, Rarity.LEGENDARY]


class CardType(str, Enum):
    SUPPLY = "supply"       # 보급
    COUNTER = "counter"     # 대항
    FACILITY = "facility"   # 시설
    EVENT = "event"         # 이벤트
    BLUEPRINT = "blueprint" # 청사진 (시설 해금)
    GEAR = "gear"           # 장비
    TRADE = "trade"         # 교역


# 카테고리 → (카드 유형, 기본 자원 산출)
CATEGORY_PROFILE = {
    Category.FOOD:        (CardType.SUPPLY,    {"food": 3, "morale": 1}),
    Category.DRINK:       (CardType.SUPPLY,    {"water": 3, "chem": 1}),
    Category.MEDICAL:     (CardType.COUNTER,   {"med": 2, "chem": 2}),
    Category.ELECTRONICS: (CardType.FACILITY,  {"power": 2, "parts": 2}),
    Category.STATIONERY:  (CardType.EVENT,     {"knowledge": 1, "morale": 2}),
    Category.BOOK:        (CardType.BLUEPRINT, {"knowledge": 4}),
    Category.APPAREL:     (CardType.GEAR,      {"cloth": 3}),
    Category.TOBACCO:     (CardType.TRADE,     {"trade": 4}),
    Category.UNKNOWN:     (CardType.SUPPLY,    {"scrap": 2}),
}

RARITY_MULT = {
    Rarity.COMMON: 1.0, Rarity.UNCOMMON: 1.3, Rarity.RARE: 1.7, Rarity.EPIC: 2.2, Rarity.LEGENDARY: 3.0,
}

# GS1 국가 접두어 → 출처 지역 (세계관 명칭). 반도 잔해 = 880
ORIGIN_MAP = {
    "880": "반도 잔해", "490": "동쪽 섬 잔해", "491": "동쪽 섬 잔해", "492": "동쪽 섬 잔해",
    "690": "대륙 잔해", "691": "대륙 잔해", "692": "대륙 잔해", "693": "대륙 잔해",
    "400": "서쪽 대륙 잔해", "401": "서쪽 대륙 잔해", "500": "안개 섬 잔해",
    "978": "잊힌 서고", "979": "잊힌 서고",
}

# 재스캔 감쇠: 개인 기준 n번째 스캔의 보상 배율 (주 1회 리셋은 서버 정책)
RESCAN_DECAY = [1.0, 0.5, 0.1]  # 이후 0


def rescan_multiplier(previous_scans: int) -> float:
    """같은 바코드를 이미 previous_scans번 스캔했을 때 이번 스캔의 보상 배율."""
    if previous_scans < 0:
        previous_scans = 0
    return RESCAN_DECAY[previous_scans] if previous_scans < len(RESCAN_DECAY) else 0.0


# ─────────────────────────────────────────────────────────────
# 데이터 모델
# ─────────────────────────────────────────────────────────────
@dataclass
class RelicCard:
    barcode: str
    name: str                 # 잔존자식 오해 이름 ("붉은 말린 실의 부적")
    flavor: str               # 플레이버 텍스트
    category: Category
    card_type: CardType
    rarity: Rarity
    yields: dict              # 자원 산출 {"food": 4, ...}
    family_code: str          # 제조 가문 (제조사 코드)
    family_name: str
    origin: str               # 출처 지역
    variant: str              # 시각 변조 ("night" 등) — 정체에 영향 없음
    seed: str                 # 결정적 시드 (앞 16자)
    tags: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("category", "card_type", "rarity"):
            d[k] = d[k].value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────
# 생성기
# ─────────────────────────────────────────────────────────────
class RelicGenerator:
    """바코드 → 유물 카드. 외부 상품 DB 없이도 동작한다(Phase 0)."""

    def __init__(self, data_dir: Path = DATA_DIR):
        self.templates = json.loads((data_dir / "relic_templates.json").read_text(encoding="utf-8"))
        self.families = json.loads((data_dir / "known_families.json").read_text(encoding="utf-8"))
        # known_families.json 의 name 은 **실제 상표**다 — 카테고리 판정에만 쓰고 화면에는 내보내지 않는다
        # (DECISIONS 2026-09-20). 표시용 창작 이름은 시나리오가 주는 data/family_names.json 에서 온다.
        self.family_names_path = data_dir / "family_names.json"
        self._fam_names: dict = {}
        self._fam_names_mtime = None

    def display_family(self, fam_key: str, manufacturer: str) -> str:
        """가문의 화면 표시 이름. family_names.json 이 있으면 그 창작 이름, 없으면 '이름 잃은 가문 NNNN'."""
        try:
            mtime = self.family_names_path.stat().st_mtime
        except OSError:
            mtime = None
        if mtime != self._fam_names_mtime:                      # 파일이 나중에 생겨도 재시작 없이 반영
            self._fam_names_mtime = mtime
            self._fam_names = {}
            if mtime is not None:
                try:
                    raw = json.loads(self.family_names_path.read_text(encoding="utf-8"))
                    for k, v in (raw.items() if isinstance(raw, dict) else []):
                        if k.startswith("_"):
                            continue
                        name = v.get("name") if isinstance(v, dict) else v
                        if isinstance(name, str):
                            self._fam_names[k] = name
                except (json.JSONDecodeError, OSError, AttributeError) as e:
                    print(f"[relic] data/family_names.json 무시: {e}")
        return self._fam_names.get(fam_key) or f"이름 잃은 가문 {manufacturer}"

    # ── 1. 파싱 ────────────────────────────────────────────
    @staticmethod
    def normalize(barcode: str) -> str:
        code = "".join(ch for ch in barcode if ch.isdigit())
        if len(code) == 12:          # UPC-A → EAN-13
            code = "0" + code
        if len(code) != 13:
            raise ValueError(f"EAN-13/ISBN-13/UPC-A 13자리가 필요합니다: {barcode!r}")
        if not RelicGenerator.valid_checksum(code):
            raise ValueError(f"체크섬 불일치: {code}")
        return code

    @staticmethod
    def valid_checksum(code: str) -> bool:
        digits = [int(c) for c in code]
        total = sum(d * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits[:12]))
        return (10 - total % 10) % 10 == digits[12]

    @staticmethod
    def parse(code: str) -> dict:
        # 제조사 코드 길이는 실제로 4~7자리로 가변이지만, 결정성만 필요하므로 고정 분할한다.
        return {
            "prefix": code[:3],
            "manufacturer": code[3:7],
            "product": code[7:12],
            "check": code[12],
            "full": code,
        }

    # ── 2. 카테고리 판정 ───────────────────────────────────
    def infer_category(self, parsed: dict, user_pick: Optional[str] = None) -> Category:
        """우선순위: ISBN 접두어 > 알려진 제조 가문 > 유저 선택 > 정체불명."""
        if parsed["prefix"] in ("978", "979"):
            return Category.BOOK
        fam = self.families.get(parsed["prefix"] + parsed["manufacturer"])
        if fam and fam.get("category"):
            return Category(fam["category"])
        if user_pick:
            try:
                return Category(user_pick)
            except ValueError:
                pass
        return Category.UNKNOWN

    # ── 3. 시드 ────────────────────────────────────────────
    @staticmethod
    def identity_seed(code: str) -> str:
        """정체 시드: 바코드만으로 결정. 전 세계 동일."""
        return hashlib.sha256(f"RELIC|{code}".encode()).hexdigest()

    @staticmethod
    def variant_of(hour: int) -> str:
        if 5 <= hour < 10:
            return "dawn"
        if 10 <= hour < 17:
            return "day"
        if 17 <= hour < 21:
            return "dusk"
        return "night"

    # ── 4. 희귀도 (v1 특허 로직 승계) ─────────────────────
    @staticmethod
    def determine_rarity(parsed: dict, seed: str, category: Category) -> Rarity:
        # 기본 점수 0~999 (시드 균등). 목표 분포: 일반 60 / 고급 25 / 희귀 10 / 에픽 4 / 전설 1 (%)
        score = int(seed[:8], 16) % 1000
        # "행운 패턴" 보너스 — v1 특허 포인트 승계. 분포를 크게 흔들지 않도록 소폭으로 재보정.
        check = int(parsed["check"])
        if check == 7:
            score += 15
        if check == 0:
            score += 8
        mfg = parsed["manufacturer"]
        if mfg[0] == mfg[-1]:                 # 팰린드롬 패턴
            score += 20
        if len(set(parsed["product"])) <= 2:  # 반복 숫자 패턴 (예: 00700) — 눈에 띄는 바코드는 실제로 귀하다
            score += 60

        if score >= 990:
            r = Rarity.LEGENDARY
        elif score >= 950:
            r = Rarity.EPIC
        elif score >= 850:
            r = Rarity.RARE
        elif score >= 600:
            r = Rarity.UNCOMMON
        else:
            r = Rarity.COMMON

        # 도서는 "잊힌 지식" → 최소 RARE 보장 (결정 #5)
        if category == Category.BOOK and RARITY_ORDER.index(r) < RARITY_ORDER.index(Rarity.RARE):
            r = Rarity.RARE
        return r

    # ── 5. 이름·플레이버 ───────────────────────────────────
    def name_and_flavor(self, seed: str, category: Category, rarity: Rarity) -> tuple[str, str, list]:
        pool = self.templates[category.value]
        # 희귀도가 높으면 템플릿 풀의 뒤쪽(더 신비로운 이름) 편향
        bias = RARITY_ORDER.index(rarity)
        idx = (int(seed[8:12], 16) + bias * 3) % len(pool)
        t = pool[idx]
        adj = self.templates["_adjectives"][int(seed[12:14], 16) % len(self.templates["_adjectives"])]
        name = t["name"].replace("{adj}", adj)
        return name, t["flavor"], t.get("tags", [])

    # ── 6. 조립 ────────────────────────────────────────────
    def generate(self, barcode: str, hour: int = 12, user_category: Optional[str] = None) -> RelicCard:
        code = self.normalize(barcode)
        parsed = self.parse(code)
        category = self.infer_category(parsed, user_category)
        seed = self.identity_seed(code)
        rarity = self.determine_rarity(parsed, seed, category)
        card_type, base = CATEGORY_PROFILE[category]

        mult = RARITY_MULT[rarity]
        yields = {k: max(1, round(v * mult)) for k, v in base.items()}
        # 시드로 보조 자원 1개 소량 추가 (같은 카테고리 안에서도 카드가 조금씩 다르게)
        extras = ["food", "water", "med", "power", "parts", "morale", "cloth", "trade", "knowledge"]
        bonus = extras[int(seed[14:16], 16) % len(extras)]
        yields[bonus] = yields.get(bonus, 0) + 1

        name, flavor, tags = self.name_and_flavor(seed, category, rarity)
        fam_key = parsed["prefix"] + parsed["manufacturer"]
        origin = ORIGIN_MAP.get(parsed["prefix"], "먼 잔해")

        return RelicCard(
            barcode=code, name=name, flavor=flavor, category=category, card_type=card_type,
            rarity=rarity, yields=yields, family_code=fam_key,
            family_name=self.display_family(fam_key, parsed["manufacturer"]),
            origin=origin, variant=self.variant_of(hour), seed=seed[:16], tags=tags,
        )


if __name__ == "__main__":
    import sys
    gen = RelicGenerator()
    codes = sys.argv[1:] or ["8801043015097", "9791162241905", "8801062636853", "4901234567894"]
    for c in codes:
        try:
            print(gen.generate(c).to_json())
        except ValueError as e:
            print("ERR", e)
