"""
BarcodeQuest 방치형 탐험 시스템

오프라인 동안 크리처들이 자동으로 탐험하여 자원을 수집합니다.
접속 시 결과를 확인하고 보상을 받습니다.

탐험 지역:
  - 숲의 오솔길 (2시간, 쉬움)
  - 바다 동굴 (4시간, 보통)
  - 용의 둥지 (8시간, 어려움)
  - 별빛 봉우리 (12시간, 전설)
"""
import hashlib
import random
import time
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict
from enum import Enum


class ExpeditionZone(Enum):
    FOREST_PATH = "forest_path"
    OCEAN_CAVE = "ocean_cave"
    DRAGON_NEST = "dragon_nest"
    STARLIGHT_PEAK = "starlight_peak"


ZONE_CONFIG = {
    ExpeditionZone.FOREST_PATH: {
        "name": "숲의 오솔길",
        "name_en": "Forest Path",
        "duration_hours": 2,
        "difficulty": "easy",
        "gold_range": (100, 300),
        "exp_reward": 20,
        "item_slots": 2,
        "rare_item_chance": 0.05,
        "epic_item_chance": 0.0,
        "bonus_type": "Leaf",
        "description": "평화로운 숲길. 약초와 열매를 수집할 수 있습니다.",
        "emoji": "🌲",
    },
    ExpeditionZone.OCEAN_CAVE: {
        "name": "바다 동굴",
        "name_en": "Ocean Cave",
        "duration_hours": 4,
        "difficulty": "normal",
        "gold_range": (300, 800),
        "exp_reward": 50,
        "item_slots": 3,
        "rare_item_chance": 0.15,
        "epic_item_chance": 0.03,
        "bonus_type": "Water",
        "description": "신비로운 해저 동굴. 진주와 산호를 발견할 수 있습니다.",
        "emoji": "🌊",
    },
    ExpeditionZone.DRAGON_NEST: {
        "name": "용의 둥지",
        "name_en": "Dragon Nest",
        "duration_hours": 8,
        "difficulty": "hard",
        "gold_range": (800, 2000),
        "exp_reward": 120,
        "item_slots": 4,
        "rare_item_chance": 0.30,
        "epic_item_chance": 0.08,
        "bonus_type": "Fire",
        "description": "위험한 화산지대. 광석과 용의 비늘을 얻을 수 있습니다.",
        "emoji": "🌋",
    },
    ExpeditionZone.STARLIGHT_PEAK: {
        "name": "별빛 봉우리",
        "name_en": "Starlight Peak",
        "duration_hours": 12,
        "difficulty": "legendary",
        "gold_range": (2000, 5000),
        "exp_reward": 200,
        "item_slots": 5,
        "rare_item_chance": 0.45,
        "epic_item_chance": 0.15,
        "bonus_type": "Light",
        "description": "하늘에 닿을 듯한 봉우리. 전설적인 보물이 잠들어 있습니다.",
        "emoji": "⭐",
    },
}


# === 탐험 아이템 드롭 테이블 ===
EXPEDITION_ITEMS = {
    "common": [
        {"id": "herb", "name": "약초", "emoji": "🌿", "category": "growth", "effect": "+10 EXP"},
        {"id": "berry", "name": "열매", "emoji": "🍇", "category": "growth", "effect": "+15 EXP"},
        {"id": "pebble", "name": "반짝 돌", "emoji": "💎", "category": "material", "effect": "강화 재료"},
        {"id": "feather", "name": "깃털", "emoji": "🪶", "category": "material", "effect": "강화 재료"},
        {"id": "shell", "name": "조개껍질", "emoji": "🐚", "category": "material", "effect": "강화 재료"},
    ],
    "rare": [
        {"id": "star_shard", "name": "별의 파편", "emoji": "💫", "category": "evolution", "effect": "진화 재료"},
        {"id": "rainbow_dew", "name": "무지개 이슬", "emoji": "🌈", "category": "evolution", "effect": "진화 재료"},
        {"id": "atk_stone", "name": "공격의 돌", "emoji": "⚔️", "category": "enhance", "effect": "ATK +5"},
        {"id": "def_seed", "name": "방어의 씨앗", "emoji": "🛡️", "category": "enhance", "effect": "DEF +5"},
        {"id": "lucky_clover", "name": "행운의 클로버", "emoji": "🍀", "category": "consumable", "effect": "다음 스캔 등급 UP"},
    ],
    "epic": [
        {"id": "dragon_scale", "name": "용의 비늘", "emoji": "🐲", "category": "evolution", "effect": "고급 진화 재료"},
        {"id": "moon_crystal", "name": "달빛 결정", "emoji": "🌙", "category": "evolution", "effect": "고급 진화 재료"},
        {"id": "energy_elixir", "name": "에너지 비약", "emoji": "⚡", "category": "consumable", "effect": "에너지 전량 회복"},
        {"id": "golden_apple", "name": "황금 사과", "emoji": "🍎", "category": "growth", "effect": "+100 EXP"},
    ],
}


@dataclass
class ExpeditionResult:
    """탐험 결과"""
    zone_name: str
    zone_emoji: str
    duration_hours: int
    gold_earned: int
    exp_earned: int
    items_found: List[dict]
    bonus_message: str
    completion_time: str
    party_used: List[str]  # 참여 크리처 이름들


@dataclass
class ActiveExpedition:
    """진행 중인 탐험"""
    zone: str
    zone_name: str
    zone_emoji: str
    start_time: float  # unix timestamp
    duration_seconds: int
    party_ids: List[str]
    party_names: List[str]
    party_types: List[str]

    @property
    def end_time(self) -> float:
        return self.start_time + self.duration_seconds

    @property
    def is_complete(self) -> bool:
        return time.time() >= self.end_time

    @property
    def remaining_seconds(self) -> int:
        return max(0, int(self.end_time - time.time()))

    @property
    def progress_pct(self) -> float:
        elapsed = time.time() - self.start_time
        return min(100.0, (elapsed / self.duration_seconds) * 100)

    def to_dict(self) -> dict:
        return {
            "zone": self.zone,
            "zone_name": self.zone_name,
            "zone_emoji": self.zone_emoji,
            "start_time": self.start_time,
            "duration_seconds": self.duration_seconds,
            "remaining_seconds": self.remaining_seconds,
            "progress_pct": round(self.progress_pct, 1),
            "is_complete": self.is_complete,
            "party_names": self.party_names,
        }


class ExpeditionSystem:
    """방치형 탐험 시스템"""

    def __init__(self):
        # session_id → ActiveExpedition
        self.active_expeditions: Dict[str, ActiveExpedition] = {}

    def get_available_zones(self, player_level: int = 1) -> List[dict]:
        """사용 가능한 탐험 지역 목록"""
        zones = []
        for zone_enum, config in ZONE_CONFIG.items():
            # 레벨 제한
            min_level = {"easy": 1, "normal": 3, "hard": 5, "legendary": 10}
            required = min_level.get(config["difficulty"], 1)

            zones.append({
                "zone_id": zone_enum.value,
                "name": config["name"],
                "name_en": config["name_en"],
                "emoji": config["emoji"],
                "duration_hours": config["duration_hours"],
                "difficulty": config["difficulty"],
                "description": config["description"],
                "gold_range": config["gold_range"],
                "exp_reward": config["exp_reward"],
                "unlocked": player_level >= required,
                "required_level": required,
            })
        return zones

    def start_expedition(self, session_id: str, zone_id: str,
                         party: List[dict]) -> dict:
        """탐험 시작"""
        if session_id in self.active_expeditions:
            exp = self.active_expeditions[session_id]
            if not exp.is_complete:
                return {
                    "error": "이미 탐험이 진행 중입니다!",
                    "expedition": exp.to_dict(),
                }

        try:
            zone_enum = ExpeditionZone(zone_id)
        except ValueError:
            return {"error": f"잘못된 탐험 지역: {zone_id}"}

        if not party:
            return {"error": "파티에 크리처가 없습니다!"}

        config = ZONE_CONFIG[zone_enum]
        duration = config["duration_hours"] * 3600

        expedition = ActiveExpedition(
            zone=zone_id,
            zone_name=config["name"],
            zone_emoji=config["emoji"],
            start_time=time.time(),
            duration_seconds=duration,
            party_ids=[m.get("id", "") for m in party[:3]],
            party_names=[m.get("name", "Unknown") for m in party[:3]],
            party_types=[m.get("primary_type", "") for m in party[:3]],
        )

        self.active_expeditions[session_id] = expedition

        return {
            "status": "started",
            "expedition": expedition.to_dict(),
            "message": f"{config['emoji']} {config['name']}(으)로 탐험을 떠났습니다! "
                       f"({config['duration_hours']}시간 후 돌아옵니다)",
        }

    def check_expedition(self, session_id: str) -> Optional[dict]:
        """탐험 상태 확인"""
        if session_id not in self.active_expeditions:
            return None
        return self.active_expeditions[session_id].to_dict()

    def collect_expedition(self, session_id: str) -> Optional[ExpeditionResult]:
        """탐험 결과 수령 (완료 시)"""
        if session_id not in self.active_expeditions:
            return None

        expedition = self.active_expeditions[session_id]
        if not expedition.is_complete:
            return None

        zone_enum = ExpeditionZone(expedition.zone)
        config = ZONE_CONFIG[zone_enum]

        # 보상 계산 (시드 기반 for 재현성)
        seed_str = f"{session_id}|{expedition.start_time}|{expedition.zone}"
        seed = hashlib.sha256(seed_str.encode()).hexdigest()
        rng = random.Random(int(seed[:8], 16))

        # 골드
        gold = rng.randint(*config["gold_range"])

        # 파티 타입 보너스 (탐험 지역과 같은 타입이면 +30%)
        type_bonus = 1.0
        bonus_msg = ""
        for ptype in expedition.party_types:
            if ptype == config["bonus_type"]:
                type_bonus = 1.3
                bonus_msg = f"타입 보너스! ({config['bonus_type']} 크리처 참여 +30%)"
                break

        gold = int(gold * type_bonus)
        exp = int(config["exp_reward"] * type_bonus)

        # 아이템 드롭
        items = []
        for slot in range(config["item_slots"]):
            roll = rng.random()
            if roll < config["epic_item_chance"]:
                item = rng.choice(EXPEDITION_ITEMS["epic"]).copy()
                item["rarity"] = "Epic"
            elif roll < config["rare_item_chance"]:
                item = rng.choice(EXPEDITION_ITEMS["rare"]).copy()
                item["rarity"] = "Rare"
            else:
                item = rng.choice(EXPEDITION_ITEMS["common"]).copy()
                item["rarity"] = "Common"
            items.append(item)

        result = ExpeditionResult(
            zone_name=config["name"],
            zone_emoji=config["emoji"],
            duration_hours=config["duration_hours"],
            gold_earned=gold,
            exp_earned=exp,
            items_found=items,
            bonus_message=bonus_msg,
            completion_time=time.strftime("%Y-%m-%d %H:%M:%S"),
            party_used=expedition.party_names,
        )

        # 탐험 완료 - 삭제
        del self.active_expeditions[session_id]

        return result
