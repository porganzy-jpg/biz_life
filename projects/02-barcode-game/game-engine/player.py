"""
BarcodeQuest 플레이어 모델
"""
import time
from datetime import datetime
from typing import List, Optional

# 패시브 에너지 회복: 3분(180초)마다 1 에너지
PASSIVE_ENERGY_RECOVERY_INTERVAL = 180  # seconds


class Player:
    """플레이어"""

    MAX_PARTY_SIZE = 3
    MAX_INVENTORY_SIZE = 50

    def __init__(self, name: str, player_id: str = "player1"):
        self.id = player_id
        self.name = name
        self.level = 1
        self.exp = 0
        self.gold = 1000  # 시작 골드
        self.energy = 100  # 스캔 에너지
        self.max_energy = 100

        # 패시브 에너지 회복 타임스탬프
        self.last_energy_recovery_time = time.time()

        # 파티 (배틀에 사용할 몬스터 최대 3)
        self.party: List[dict] = []
        # 보관함
        self.inventory: List[dict] = []

        # 통계
        self.total_scans = 0
        self.total_battles = 0
        self.total_wins = 0
        self.created_at = datetime.now().isoformat()

    def add_monster(self, monster: dict) -> dict:
        """몬스터 획득"""
        # Ensure affinity tracking fields exist on the monster
        monster.setdefault("affinity_level", 1)
        monster.setdefault("affinity_exp", 0)

        if len(self.party) < self.MAX_PARTY_SIZE:
            self.party.append(monster)
            return {"location": "party", "slot": len(self.party) - 1}
        elif len(self.inventory) < self.MAX_INVENTORY_SIZE:
            self.inventory.append(monster)
            return {"location": "inventory", "slot": len(self.inventory) - 1}
        else:
            return {"location": "full", "message": "파티와 보관함이 가득 찼습니다!"}

    def swap_party_member(self, party_idx: int, inventory_idx: int) -> dict:
        """파티 ↔ 보관함 교체"""
        if not (0 <= party_idx < len(self.party)):
            return {"ok": False, "msg": f"잘못된 파티 인덱스: {party_idx}"}
        if not (0 <= inventory_idx < len(self.inventory)):
            return {"ok": False, "msg": f"잘못된 보관함 인덱스: {inventory_idx}"}
        self.party[party_idx], self.inventory[inventory_idx] = (
            self.inventory[inventory_idx], self.party[party_idx]
        )
        return {"ok": True, "msg": f"교체 완료: 파티[{party_idx}] ↔ 보관함[{inventory_idx}]"}

    @staticmethod
    def gain_monster_exp(monster: dict, exp: int) -> dict:
        """몬스터 경험치 획득 + 레벨업"""
        monster.setdefault("exp", 0)
        monster.setdefault("level", 1)
        monster["exp"] += exp
        leveled_up = False
        needed = monster["level"] * 50
        while monster["exp"] >= needed:
            monster["exp"] -= needed
            monster["level"] += 1
            # 레벨업 시 스탯 성장 (+2~3%)
            for stat in ("hp", "attack", "defense", "speed", "special"):
                if stat in monster.get("stats", {}):
                    monster["stats"][stat] = int(monster["stats"][stat] * 1.03)
            leveled_up = True
            needed = monster["level"] * 50
        return {"leveled_up": leveled_up, "monster_level": monster["level"], "monster_exp": monster["exp"]}

    # === Affinity / Bonding System ===

    # Affinity level thresholds: each level requires 100 affinity EXP
    AFFINITY_MAX_LEVEL = 10
    AFFINITY_EXP_PER_LEVEL = 100

    # Stat multiplier bonuses by affinity level
    # Level 3 → +3%, Level 5 → +5%, Level 7 → +8%, Level 10 → +12%
    AFFINITY_BONUSES = {
        1: 1.0, 2: 1.0,
        3: 1.03, 4: 1.03,
        5: 1.05, 6: 1.05,
        7: 1.08, 8: 1.08, 9: 1.08,
        10: 1.12,
    }

    def gain_affinity(self, monster_index: int, amount: int, source: str = "party") -> dict:
        """
        Add affinity EXP to a monster and handle level-ups.

        Args:
            monster_index: Index into party or inventory list.
            amount: Amount of affinity EXP to grant.
            source: "party" or "inventory" to pick the correct list.

        Returns:
            dict with affinity state and whether a level-up occurred.
        """
        monster_list = self.party if source == "party" else self.inventory
        if monster_index < 0 or monster_index >= len(monster_list):
            return {"ok": False, "msg": "잘못된 몬스터 인덱스"}

        monster = monster_list[monster_index]
        monster.setdefault("affinity_level", 1)
        monster.setdefault("affinity_exp", 0)

        old_level = monster["affinity_level"]
        if old_level >= self.AFFINITY_MAX_LEVEL:
            return {
                "ok": True,
                "leveled_up": False,
                "affinity_level": old_level,
                "affinity_exp": monster["affinity_exp"],
                "monster_name": monster.get("name", "Unknown"),
            }

        monster["affinity_exp"] += amount
        leveled_up = False

        while (monster["affinity_exp"] >= self.AFFINITY_EXP_PER_LEVEL
               and monster["affinity_level"] < self.AFFINITY_MAX_LEVEL):
            monster["affinity_exp"] -= self.AFFINITY_EXP_PER_LEVEL
            monster["affinity_level"] += 1
            leveled_up = True

        # Cap EXP at 0 if max level reached
        if monster["affinity_level"] >= self.AFFINITY_MAX_LEVEL:
            monster["affinity_exp"] = 0

        return {
            "ok": True,
            "leveled_up": leveled_up,
            "old_level": old_level,
            "affinity_level": monster["affinity_level"],
            "affinity_exp": monster["affinity_exp"],
            "monster_name": monster.get("name", "Unknown"),
        }

    @staticmethod
    def get_affinity_bonus(monster: dict) -> dict:
        """
        Return the stat multiplier and bonus description for a monster's affinity level.

        Returns:
            dict with 'multiplier' (float), 'passive_heal' (bool), 'heal_pct' (int),
            'bonus_description' (str), 'affinity_level' (int), 'affinity_exp' (int).
        """
        level = monster.get("affinity_level", 1)
        level = max(1, min(10, level))

        bonuses = {
            1: 1.0, 2: 1.0,
            3: 1.03, 4: 1.03,
            5: 1.05, 6: 1.05,
            7: 1.08, 8: 1.08, 9: 1.08,
            10: 1.12,
        }
        multiplier = bonuses.get(level, 1.0)
        passive_heal = level >= 7
        heal_pct = 5 if passive_heal else 0

        # Build description
        if level >= 10:
            desc = "최대 유대! 스탯 +12%"
        elif level >= 7:
            desc = f"스탯 +{int((multiplier - 1) * 100)}%, 전투 후 HP 5% 회복"
        elif level >= 3:
            desc = f"스탯 +{int((multiplier - 1) * 100)}%"
        else:
            desc = "보너스 없음"

        return {
            "multiplier": multiplier,
            "passive_heal": passive_heal,
            "heal_pct": heal_pct,
            "bonus_description": desc,
            "affinity_level": level,
            "affinity_exp": monster.get("affinity_exp", 0),
        }

    def apply_post_battle_affinity_heal(self, monster_index: int, source: str = "party"):
        """
        If monster has affinity level >= 7, heal 5% of max HP after battle.
        This modifies the monster's current HP in place (for display purposes).
        """
        monster_list = self.party if source == "party" else self.inventory
        if monster_index < 0 or monster_index >= len(monster_list):
            return None

        monster = monster_list[monster_index]
        bonus = self.get_affinity_bonus(monster)
        if bonus["passive_heal"] and "stats" in monster:
            max_hp = monster["stats"].get("hp", 0)
            heal_amount = int(max_hp * bonus["heal_pct"] / 100)
            return {"healed": True, "heal_amount": heal_amount, "monster_name": monster.get("name")}
        return {"healed": False}

    def check_passive_recovery(self):
        """
        패시브 에너지 회복 계산 및 적용

        경과 시간을 기반으로 3분당 1 에너지를 회복합니다.
        max_energy를 초과하지 않습니다.
        API 호출 시점에서 호출하세요.
        """
        if self.energy >= self.max_energy:
            # 이미 최대이면 타임스탬프만 갱신
            self.last_energy_recovery_time = time.time()
            return

        now = time.time()
        elapsed = now - self.last_energy_recovery_time
        ticks = int(elapsed // PASSIVE_ENERGY_RECOVERY_INTERVAL)

        if ticks > 0:
            recovered = ticks
            self.energy = min(self.max_energy, self.energy + recovered)
            # 소비된 틱 수만큼만 시간을 전진 (나머지는 보존)
            self.last_energy_recovery_time += ticks * PASSIVE_ENERGY_RECOVERY_INTERVAL

    def use_energy(self, amount: int = 10) -> bool:
        """에너지 소비 (스캔 시)"""
        if self.energy >= amount:
            self.energy -= amount
            return True
        return False

    def recover_energy(self, amount: int = 10):
        """에너지 회복"""
        self.energy = min(self.max_energy, self.energy + amount)

    def gain_exp(self, amount: int) -> dict:
        """경험치 획득"""
        self.exp += amount
        leveled_up = False
        gold_bonus = 0

        # 레벨업 체크 (100 * 레벨 EXP 필요)
        needed = self.level * 100
        while self.exp >= needed:
            self.exp -= needed
            self.level += 1
            self.max_energy += 5
            # 레벨업 보상: 에너지 전량 회복
            self.energy = self.max_energy
            # 레벨업 보상: 보너스 골드 (100 * 새 레벨)
            level_gold = 100 * self.level
            self.gold += level_gold
            gold_bonus += level_gold
            leveled_up = True
            needed = self.level * 100

        result = {
            "exp_gained": amount,
            "leveled_up": leveled_up,
            "current_level": self.level,
            "current_exp": self.exp,
            "next_level_exp": needed,
        }
        if gold_bonus > 0:
            result["level_up_gold_bonus"] = gold_bonus
        return result

    def gain_gold(self, amount: int):
        """골드 획득"""
        self.gold += amount

    def spend_gold(self, amount: int) -> bool:
        """골드 소비"""
        if self.gold >= amount:
            self.gold -= amount
            return True
        return False

    def to_dict(self) -> dict:
        # Build affinity summary for each party monster
        party_affinity = []
        for m in self.party:
            party_affinity.append({
                "name": m.get("name", "Unknown"),
                "affinity_level": m.get("affinity_level", 1),
                "affinity_exp": m.get("affinity_exp", 0),
                "bonus": self.get_affinity_bonus(m)["bonus_description"],
            })

        return {
            "id": self.id,
            "name": self.name,
            "level": self.level,
            "exp": self.exp,
            "gold": self.gold,
            "energy": self.energy,
            "max_energy": self.max_energy,
            "last_energy_recovery_time": self.last_energy_recovery_time,
            "party_size": len(self.party),
            "inventory_size": len(self.inventory),
            "total_scans": self.total_scans,
            "total_battles": self.total_battles,
            "total_wins": self.total_wins,
            "party_affinity": party_affinity,
        }
