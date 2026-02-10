"""
BarcodeQuest 진화 시스템

크리처를 진화시켜 더 강한 형태로 변화시킵니다.

진화 조건:
  1. 크리처 레벨 10 이상
  2. 진화 재료 보유 (등급별 다름)
  3. 골드 비용
"""
from typing import Dict, List, Optional


# === 진화 접두어 (등급별) ===
EVOLUTION_PREFIXES = {
    "Common": ["빛나는", "강인한", "민첩한", "총명한", "용감한"],
    "Uncommon": ["찬란한", "위엄있는", "신비로운", "폭풍의", "대지의"],
    "Rare": ["전설의", "고대의", "천상의", "황금의", "불멸의"],
    "Epic": ["신성한", "초월의", "차원의", "태초의", "영겁의"],
    "Legendary": ["창세의", "우주의", "절대의", "무한의", "운명의"],
}

# === 진화 비용 테이블 ===
EVOLUTION_COSTS = {
    "Common": {
        "gold": 1000,
        "materials": [("star_shard", 1)],
        "min_level": 10,
    },
    "Uncommon": {
        "gold": 3000,
        "materials": [("star_shard", 2), ("rainbow_dew", 1)],
        "min_level": 10,
    },
    "Rare": {
        "gold": 8000,
        "materials": [("star_shard", 3), ("rainbow_dew", 2)],
        "min_level": 10,
    },
    "Epic": {
        "gold": 20000,
        "materials": [("dragon_scale", 2), ("moon_crystal", 2)],
        "min_level": 15,
    },
    "Legendary": {
        "gold": 50000,
        "materials": [("dragon_scale", 5), ("moon_crystal", 5)],
        "min_level": 20,
    },
}

# === 진화 시 스탯 증가율 ===
EVOLUTION_STAT_MULTIPLIER = 1.5

# === 진화 후 추가 특성 ===
EVOLUTION_TRAITS = {
    "Common": [
        "회복의 숨결: 매 턴 HP 3% 회복",
        "강철 의지: 방어 시 피해 70% 감소",
        "질풍: 선제공격 확률 +15%",
    ],
    "Uncommon": [
        "폭풍의 눈: 크리티컬 확률 +10%",
        "대지의 축복: 최대 HP +20%",
        "화염 갑옷: 공격자에게 반사 피해 10%",
    ],
    "Rare": [
        "용의 숨결: 특수 공격 데미지 +30%",
        "그림자 회피: 피격 시 20% 확률로 회피",
        "번개 연쇄: 공격 시 추가 피해 15%",
    ],
    "Epic": [
        "차원 분열: 2회 연속 공격 (데미지 70%씩)",
        "시간 왜곡: 3턴마다 추가 행동",
        "영혼 흡수: 공격 데미지의 20%를 HP로 회복",
    ],
    "Legendary": [
        "창세의 힘: 모든 스탯 +15%",
        "운명 거부: 치명적 피해 시 1회 부활 (HP 30%)",
        "절대 영역: 3턴간 받는 피해 50% 감소 (배틀 시작 시)",
    ],
}


class EvolutionSystem:
    """크리처 진화 시스템"""

    def check_evolution_requirements(self, monster: dict, player_gold: int,
                                      item_inventory) -> dict:
        """
        진화 가능 여부 확인

        Returns:
            dict: {can_evolve, requirements, missing}
        """
        rarity = monster.get("rarity", "Common")
        level = monster.get("level", 1)
        already_evolved = monster.get("evolved", False)

        if already_evolved:
            return {
                "can_evolve": False,
                "reason": "이미 진화한 크리처입니다!",
                "requirements": None,
            }

        costs = EVOLUTION_COSTS.get(rarity)
        if not costs:
            return {
                "can_evolve": False,
                "reason": "진화 정보가 없습니다.",
                "requirements": None,
            }

        missing = []

        # 레벨 확인
        if level < costs["min_level"]:
            missing.append(f"레벨 {costs['min_level']} 필요 (현재 Lv.{level})")

        # 골드 확인
        if player_gold < costs["gold"]:
            missing.append(f"골드 {costs['gold']:,} 필요 (보유 {player_gold:,})")

        # 재료 확인
        for mat_id, mat_count in costs["materials"]:
            owned = item_inventory.get_item_count(mat_id) if item_inventory else 0
            if owned < mat_count:
                from item_system import ITEM_DATABASE
                mat_name = ITEM_DATABASE.get(mat_id, {}).get("name", mat_id)
                missing.append(f"{mat_name} x{mat_count} 필요 (보유 {owned})")

        requirements = {
            "level": costs["min_level"],
            "gold": costs["gold"],
            "materials": [
                {"id": mid, "count": mc}
                for mid, mc in costs["materials"]
            ],
        }

        return {
            "can_evolve": len(missing) == 0,
            "requirements": requirements,
            "missing": missing,
        }

    def evolve_monster(self, monster: dict, seed_offset: str = "") -> dict:
        """
        크리처 진화 실행

        Args:
            monster: 원본 크리처 데이터
            seed_offset: 진화 결과 다양성을 위한 시드

        Returns:
            dict: 진화된 크리처 데이터
        """
        import hashlib
        rarity = monster.get("rarity", "Common")

        # 진화 시드 생성
        evo_seed = hashlib.sha256(
            f"{monster['id']}|evolution|{seed_offset}".encode()
        ).hexdigest()
        evo_idx = int(evo_seed[:4], 16)

        # 접두어 선택
        prefixes = EVOLUTION_PREFIXES.get(rarity, EVOLUTION_PREFIXES["Common"])
        prefix = prefixes[evo_idx % len(prefixes)]

        # 새 이름
        original_name = monster.get("name", "Unknown")
        evolved_name = f"{prefix} {original_name}"

        # 스탯 강화
        old_stats = monster.get("stats", {})
        if isinstance(old_stats, dict):
            new_stats = {
                "hp": int(old_stats.get("hp", 50) * EVOLUTION_STAT_MULTIPLIER),
                "attack": int(old_stats.get("attack", 30) * EVOLUTION_STAT_MULTIPLIER),
                "defense": int(old_stats.get("defense", 25) * EVOLUTION_STAT_MULTIPLIER),
                "speed": int(old_stats.get("speed", 20) * EVOLUTION_STAT_MULTIPLIER),
                "special": int(old_stats.get("special", 15) * EVOLUTION_STAT_MULTIPLIER),
            }
        else:
            new_stats = old_stats

        # 추가 특성
        traits = EVOLUTION_TRAITS.get(rarity, EVOLUTION_TRAITS["Common"])
        new_trait = traits[evo_idx % len(traits)]

        # 진화된 크리처 생성 (원본 복사 + 변경)
        evolved = monster.copy()
        evolved["name"] = evolved_name
        evolved["stats"] = new_stats
        evolved["evolved"] = True
        evolved["evolution_trait"] = new_trait
        evolved["original_name"] = original_name
        evolved["original_trait"] = monster.get("special_trait", "")
        evolved["special_trait"] = f"{monster.get('special_trait', '')} + {new_trait}"

        return evolved

    def get_evolution_preview(self, monster: dict) -> dict:
        """진화 미리보기 (진화하면 어떻게 되는지)"""
        rarity = monster.get("rarity", "Common")
        costs = EVOLUTION_COSTS.get(rarity, EVOLUTION_COSTS["Common"])

        import hashlib
        evo_seed = hashlib.sha256(
            f"{monster['id']}|evolution|preview".encode()
        ).hexdigest()
        evo_idx = int(evo_seed[:4], 16)

        prefixes = EVOLUTION_PREFIXES.get(rarity, EVOLUTION_PREFIXES["Common"])
        prefix = prefixes[evo_idx % len(prefixes)]
        traits = EVOLUTION_TRAITS.get(rarity, EVOLUTION_TRAITS["Common"])
        new_trait = traits[evo_idx % len(traits)]

        old_stats = monster.get("stats", {})

        return {
            "current_name": monster.get("name", "Unknown"),
            "evolved_name": f"{prefix} {monster.get('name', 'Unknown')}",
            "stat_increase": "x1.5 (모든 스탯)",
            "new_trait": new_trait,
            "preview_stats": {
                k: int(v * EVOLUTION_STAT_MULTIPLIER)
                for k, v in old_stats.items()
            } if isinstance(old_stats, dict) else {},
            "cost": {
                "gold": costs["gold"],
                "materials": costs["materials"],
                "min_level": costs["min_level"],
            },
        }
