"""
BarcodeQuest 플레이어 모델
"""
from datetime import datetime
from typing import List, Optional


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

        # 레벨업 체크 (100 * 레벨 EXP 필요)
        needed = self.level * 100
        while self.exp >= needed:
            self.exp -= needed
            self.level += 1
            self.max_energy += 5
            self.energy = self.max_energy
            leveled_up = True
            needed = self.level * 100

        return {
            "exp_gained": amount,
            "leveled_up": leveled_up,
            "current_level": self.level,
            "current_exp": self.exp,
            "next_level_exp": needed,
        }

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
        return {
            "id": self.id,
            "name": self.name,
            "level": self.level,
            "exp": self.exp,
            "gold": self.gold,
            "energy": self.energy,
            "max_energy": self.max_energy,
            "party_size": len(self.party),
            "inventory_size": len(self.inventory),
            "total_scans": self.total_scans,
            "total_battles": self.total_battles,
            "total_wins": self.total_wins,
        }
