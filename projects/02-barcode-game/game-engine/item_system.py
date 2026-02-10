"""
BarcodeQuest 아이템 시스템

바코드 카테고리 기반 아이템 풀 + 인벤토리 관리
"""
from typing import Dict, List, Optional
from enum import Enum


class ItemCategory(Enum):
    GROWTH = "growth"           # 경험치 아이템
    ENHANCE = "enhance"         # 스탯 강화
    EVOLUTION = "evolution"     # 진화 재료
    CONSUMABLE = "consumable"   # 소모품
    COSMETIC = "cosmetic"       # 장식


class ItemRarity(Enum):
    COMMON = "Common"
    UNCOMMON = "Uncommon"
    RARE = "Rare"
    EPIC = "Epic"
    LEGENDARY = "Legendary"


# === 전체 아이템 정의 ===
ITEM_DATABASE = {
    # --- 성장 아이템 ---
    "exp_candy_s": {
        "name": "경험치 사탕 (소)", "emoji": "🍬",
        "category": "growth", "rarity": "Common",
        "effect": {"type": "exp", "value": 20},
        "description": "달콤한 사탕. 크리처에게 20 EXP를 줍니다.",
        "sell_price": 10,
    },
    "exp_candy_m": {
        "name": "경험치 사탕 (중)", "emoji": "🍭",
        "category": "growth", "rarity": "Uncommon",
        "effect": {"type": "exp", "value": 50},
        "description": "큰 사탕. 크리처에게 50 EXP를 줍니다.",
        "sell_price": 30,
    },
    "exp_candy_l": {
        "name": "경험치 사탕 (대)", "emoji": "🎂",
        "category": "growth", "rarity": "Rare",
        "effect": {"type": "exp", "value": 150},
        "description": "특대형 사탕. 크리처에게 150 EXP를 줍니다.",
        "sell_price": 100,
    },
    "golden_apple": {
        "name": "황금 사과", "emoji": "🍎",
        "category": "growth", "rarity": "Epic",
        "effect": {"type": "exp", "value": 500},
        "description": "전설의 과일. 크리처에게 500 EXP를 줍니다.",
        "sell_price": 500,
    },
    # --- 강화 아이템 ---
    "atk_stone": {
        "name": "공격의 돌", "emoji": "⚔️",
        "category": "enhance", "rarity": "Uncommon",
        "effect": {"type": "stat_boost", "stat": "attack", "value": 5},
        "description": "빨간 빛의 돌. 크리처의 공격력을 5 올립니다.",
        "sell_price": 50,
    },
    "def_seed": {
        "name": "방어의 씨앗", "emoji": "🛡️",
        "category": "enhance", "rarity": "Uncommon",
        "effect": {"type": "stat_boost", "stat": "defense", "value": 5},
        "description": "단단한 씨앗. 크리처의 방어력을 5 올립니다.",
        "sell_price": 50,
    },
    "spd_feather": {
        "name": "속도의 깃털", "emoji": "🪶",
        "category": "enhance", "rarity": "Uncommon",
        "effect": {"type": "stat_boost", "stat": "speed", "value": 5},
        "description": "가벼운 깃털. 크리처의 속도를 5 올립니다.",
        "sell_price": 50,
    },
    "hp_fruit": {
        "name": "생명의 열매", "emoji": "🍇",
        "category": "enhance", "rarity": "Uncommon",
        "effect": {"type": "stat_boost", "stat": "hp", "value": 10},
        "description": "싱그러운 열매. 크리처의 HP를 10 올립니다.",
        "sell_price": 50,
    },
    # --- 진화 재료 ---
    "star_shard": {
        "name": "별의 파편", "emoji": "💫",
        "category": "evolution", "rarity": "Rare",
        "effect": {"type": "evolution_material"},
        "description": "하늘에서 떨어진 별 조각. 진화에 필요합니다.",
        "sell_price": 200,
    },
    "rainbow_dew": {
        "name": "무지개 이슬", "emoji": "🌈",
        "category": "evolution", "rarity": "Rare",
        "effect": {"type": "evolution_material"},
        "description": "무지개가 떨어진 자리의 이슬. 진화에 필요합니다.",
        "sell_price": 200,
    },
    "dragon_scale": {
        "name": "용의 비늘", "emoji": "🐲",
        "category": "evolution", "rarity": "Epic",
        "effect": {"type": "evolution_material"},
        "description": "고대 용의 비늘. 고급 진화에 필요합니다.",
        "sell_price": 1000,
    },
    "moon_crystal": {
        "name": "달빛 결정", "emoji": "🌙",
        "category": "evolution", "rarity": "Epic",
        "effect": {"type": "evolution_material"},
        "description": "달빛이 응축된 결정. 고급 진화에 필요합니다.",
        "sell_price": 1000,
    },
    # --- 소모품 ---
    "energy_drink": {
        "name": "에너지 음료", "emoji": "🥤",
        "category": "consumable", "rarity": "Common",
        "effect": {"type": "energy", "value": 30},
        "description": "시원한 음료. 에너지를 30 회복합니다.",
        "sell_price": 20,
    },
    "energy_elixir": {
        "name": "에너지 비약", "emoji": "⚡",
        "category": "consumable", "rarity": "Epic",
        "effect": {"type": "energy_full"},
        "description": "강력한 비약. 에너지를 전량 회복합니다.",
        "sell_price": 300,
    },
    "lucky_clover": {
        "name": "행운의 클로버", "emoji": "🍀",
        "category": "consumable", "rarity": "Rare",
        "effect": {"type": "luck_boost", "duration_scans": 3},
        "description": "다음 3회 스캔의 등급 확률이 상승합니다.",
        "sell_price": 150,
    },
    # --- 장식 ---
    "flower_crown": {
        "name": "꽃 왕관", "emoji": "👑",
        "category": "cosmetic", "rarity": "Rare",
        "effect": {"type": "cosmetic", "slot": "accessory"},
        "description": "아름다운 꽃으로 만든 왕관.",
        "sell_price": 100,
    },
    "star_wings": {
        "name": "별빛 날개", "emoji": "✨",
        "category": "cosmetic", "rarity": "Epic",
        "effect": {"type": "cosmetic", "slot": "accessory"},
        "description": "반짝이는 날개 장식.",
        "sell_price": 500,
    },
}

# === 바코드 카테고리별 드롭 가중치 ===
# 국가코드 접두사로 바코드 카테고리 추정
BARCODE_ITEM_AFFINITY = {
    # 한국 식품류 → 성장 아이템 확률 UP
    "880_food": ["exp_candy_s", "exp_candy_m", "hp_fruit", "energy_drink"],
    # 일본 전자제품류 → 강화 아이템 확률 UP
    "490_tech": ["atk_stone", "def_seed", "spd_feather"],
    # 음료류 → 에너지 아이템 확률 UP
    "beverage": ["energy_drink", "energy_elixir", "exp_candy_s"],
    # 기본
    "default": ["exp_candy_s", "energy_drink", "hp_fruit", "atk_stone"],
}

# === 상점 아이템 ===
SHOP_ITEMS = [
    {"item_id": "exp_candy_s", "price": 50, "stock": -1},      # 무제한
    {"item_id": "exp_candy_m", "price": 150, "stock": -1},
    {"item_id": "energy_drink", "price": 100, "stock": 5},      # 일일 5개
    {"item_id": "atk_stone", "price": 300, "stock": 3},
    {"item_id": "def_seed", "price": 300, "stock": 3},
    {"item_id": "spd_feather", "price": 300, "stock": 3},
    {"item_id": "hp_fruit", "price": 300, "stock": 3},
    {"item_id": "lucky_clover", "price": 800, "stock": 1},
    {"item_id": "star_shard", "price": 1500, "stock": 2},
    {"item_id": "rainbow_dew", "price": 1500, "stock": 2},
]


class ItemInventory:
    """플레이어 아이템 인벤토리"""

    MAX_UNIQUE_ITEMS = 100  # 최대 100종류 보관

    def __init__(self):
        # item_id → count
        self.items: Dict[str, int] = {}

    def add_item(self, item_id: str, count: int = 1) -> dict:
        """아이템 추가"""
        if item_id not in ITEM_DATABASE:
            return {"error": f"존재하지 않는 아이템: {item_id}"}

        if item_id not in self.items and len(self.items) >= self.MAX_UNIQUE_ITEMS:
            return {"error": "아이템 인벤토리가 가득 찼습니다!"}

        self.items[item_id] = self.items.get(item_id, 0) + count
        item_data = ITEM_DATABASE[item_id]

        return {
            "item_id": item_id,
            "name": item_data["name"],
            "emoji": item_data["emoji"],
            "count": self.items[item_id],
            "added": count,
        }

    def remove_item(self, item_id: str, count: int = 1) -> bool:
        """아이템 사용/제거"""
        if self.items.get(item_id, 0) < count:
            return False
        self.items[item_id] -= count
        if self.items[item_id] <= 0:
            del self.items[item_id]
        return True

    def has_item(self, item_id: str, count: int = 1) -> bool:
        """아이템 보유 확인"""
        return self.items.get(item_id, 0) >= count

    def get_item_count(self, item_id: str) -> int:
        return self.items.get(item_id, 0)

    def get_inventory_list(self) -> List[dict]:
        """전체 인벤토리 목록"""
        result = []
        for item_id, count in self.items.items():
            if item_id in ITEM_DATABASE:
                data = ITEM_DATABASE[item_id].copy()
                data["item_id"] = item_id
                data["count"] = count
                result.append(data)
        # 등급 순 정렬
        rarity_order = ["Legendary", "Epic", "Rare", "Uncommon", "Common"]
        result.sort(key=lambda x: rarity_order.index(x.get("rarity", "Common")))
        return result

    def use_item(self, item_id: str, target_monster: dict = None) -> dict:
        """아이템 사용"""
        if not self.has_item(item_id):
            return {"error": "아이템이 부족합니다!"}

        item_data = ITEM_DATABASE.get(item_id)
        if not item_data:
            return {"error": "잘못된 아이템입니다."}

        effect = item_data["effect"]
        result = {"item_used": item_data["name"], "emoji": item_data["emoji"]}

        if effect["type"] == "exp" and target_monster:
            result["effect"] = f"크리처에게 {effect['value']} EXP 부여"
            result["exp_value"] = effect["value"]
        elif effect["type"] == "stat_boost" and target_monster:
            stat = effect["stat"]
            value = effect["value"]
            result["effect"] = f"크리처의 {stat} +{value}"
            result["stat_name"] = stat
            result["stat_value"] = value
        elif effect["type"] == "energy":
            result["effect"] = f"에너지 {effect['value']} 회복"
            result["energy_value"] = effect["value"]
        elif effect["type"] == "energy_full":
            result["effect"] = "에너지 전량 회복"
            result["energy_full"] = True
        elif effect["type"] == "luck_boost":
            result["effect"] = f"다음 {effect['duration_scans']}회 스캔 등급 확률 UP"
            result["luck_scans"] = effect["duration_scans"]
        else:
            result["effect"] = "사용됨"

        self.remove_item(item_id)
        return result

    def to_dict(self) -> dict:
        return {
            "total_types": len(self.items),
            "total_count": sum(self.items.values()),
            "items": self.get_inventory_list(),
        }


def get_shop_listing() -> List[dict]:
    """상점 아이템 목록"""
    listing = []
    for shop_item in SHOP_ITEMS:
        item_id = shop_item["item_id"]
        if item_id in ITEM_DATABASE:
            data = ITEM_DATABASE[item_id].copy()
            data["item_id"] = item_id
            data["price"] = shop_item["price"]
            data["stock"] = shop_item["stock"]
            listing.append(data)
    return listing
