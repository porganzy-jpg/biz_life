"""
BarcodeQuest 턴제 배틀 시스템

속성 상성 테이블:
Fire > Nature > Water > Fire (삼각 상성)
Tech > Spirit > Dark > Tech (삼각 상성)
Earth, Wind: 상성 없음 (중립)
Food, Light: 보너스 없음 (중립)
"""
import random
from dataclasses import dataclass
from typing import Optional
from barcode_monster_generator import Monster, MonsterStats


# === 속성 상성 매트릭스 ===
TYPE_ADVANTAGE = {
    "Fire": ["Nature", "Food"],
    "Water": ["Fire", "Earth"],
    "Nature": ["Water", "Wind"],
    "Tech": ["Spirit", "Wind"],
    "Spirit": ["Dark", "Light"],
    "Dark": ["Tech", "Food"],
    "Earth": ["Fire", "Tech"],
    "Wind": ["Water", "Spirit"],
    "Food": ["Nature", "Light"],
    "Light": ["Dark", "Earth"],
}


@dataclass
class BattleAction:
    """배틀 행동"""
    attacker: str   # 몬스터 ID
    action_type: str  # "attack", "special", "defend", "swap"
    target: str = ""


@dataclass
class TurnResult:
    """턴 결과"""
    attacker_name: str
    defender_name: str
    action: str
    damage: int
    is_critical: bool
    is_effective: str  # "normal", "effective", "not_effective"
    attacker_hp_remaining: int
    defender_hp_remaining: int
    message: str


class BattleMonster:
    """배틀용 몬스터 래퍼"""

    def __init__(self, monster: dict):
        self.id = monster["id"]
        self.name = monster["name"]
        self.primary_type = monster["primary_type"]
        self.secondary_type = monster["secondary_type"]
        self.level = monster.get("level", 1)

        # Apply affinity stat bonus if present
        affinity_level = monster.get("affinity_level", 1)
        affinity_multiplier = self._get_affinity_multiplier(affinity_level)

        self.max_hp = int(monster["stats"]["hp"] * affinity_multiplier)
        self.current_hp = self.max_hp
        self.attack = int(monster["stats"]["attack"] * affinity_multiplier)
        self.defense = int(monster["stats"]["defense"] * affinity_multiplier)
        self.speed = int(monster["stats"]["speed"] * affinity_multiplier)
        self.special = int(monster["stats"]["special"] * affinity_multiplier)
        self.is_defending = False
        self.affinity_level = affinity_level

    @staticmethod
    def _get_affinity_multiplier(affinity_level: int) -> float:
        """Return stat multiplier based on affinity level."""
        bonuses = {
            1: 1.0, 2: 1.0,
            3: 1.03, 4: 1.03,
            5: 1.05, 6: 1.05,
            7: 1.08, 8: 1.08, 9: 1.08,
            10: 1.12,
        }
        return bonuses.get(max(1, min(10, affinity_level)), 1.0)

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0


class BattleSystem:
    """턴제 배틀 엔진"""

    def __init__(self):
        self.turn_count = 0

    def calculate_type_effectiveness(self, atk_type: str, def_type: str) -> tuple:
        """속성 상성 계산"""
        advantages = TYPE_ADVANTAGE.get(atk_type, [])
        if def_type in advantages:
            return 1.5, "effective"

        # 역상성 체크
        def_advantages = TYPE_ADVANTAGE.get(def_type, [])
        if atk_type in def_advantages:
            return 0.7, "not_effective"

        return 1.0, "normal"

    def calculate_damage(self, attacker: BattleMonster, defender: BattleMonster,
                         is_special: bool = False) -> tuple:
        """
        데미지 계산

        기본 데미지 = (공격력 * 레벨보정) * (1 - 방어 감소율) * 상성 * 크리티컬 * 랜덤
        방어 감소율 = defense / (defense + 100) (스케일링 방어 공식)
        """
        base_stat = attacker.special if is_special else attacker.attack
        level_mod = 1 + (attacker.level * 0.1)

        # 방어 중이면 방어력 2배
        def_stat = defender.defense * (2 if defender.is_defending else 1)

        # 기본 공격력 (레벨 보정 적용)
        raw_damage = base_stat * level_mod * 2

        # 방어력 스케일링: defense / (defense + 100) 비율만큼 데미지 감소
        # 방어력 100 → 50% 감소, 200 → 66% 감소, 50 → 33% 감소
        defense_reduction = def_stat / (def_stat + 100)
        raw_damage *= (1 - defense_reduction)

        # 속성 상성
        effectiveness, eff_label = self.calculate_type_effectiveness(
            attacker.primary_type, defender.primary_type
        )
        raw_damage *= effectiveness

        # 크리티컬 (속도 비례 확률)
        crit_chance = min(0.25, attacker.speed / 500)
        is_critical = random.random() < crit_chance
        if is_critical:
            raw_damage *= 1.5

        # 랜덤 변동 (80~110%) - 더 넓은 범위로 전투를 흥미롭게
        raw_damage *= random.uniform(0.80, 1.10)

        final_damage = max(1, int(raw_damage))
        return final_damage, is_critical, eff_label

    def execute_turn(self, p1_monster: BattleMonster, p1_action: BattleAction,
                     p2_monster: BattleMonster, p2_action: BattleAction) -> list:
        """
        1턴 실행 (양쪽 동시)
        속도가 높은 쪽이 먼저 행동
        """
        self.turn_count += 1
        results = []

        # 방어 리셋
        p1_monster.is_defending = False
        p2_monster.is_defending = False

        # 순서 결정 (속도)
        if p1_monster.speed >= p2_monster.speed:
            first, f_action = p1_monster, p1_action
            second, s_action = p2_monster, p2_action
        else:
            first, f_action = p2_monster, p2_action
            second, s_action = p1_monster, p1_action

        # 선공
        result = self._execute_action(first, f_action, second)
        results.append(result)

        # 후공 (살아있으면)
        if second.is_alive:
            result = self._execute_action(second, s_action, first)
            results.append(result)

        return results

    def _execute_action(self, attacker: BattleMonster, action: BattleAction,
                        defender: BattleMonster) -> TurnResult:
        if action.action_type == "defend":
            attacker.is_defending = True
            return TurnResult(
                attacker_name=attacker.name, defender_name=defender.name,
                action="defend", damage=0, is_critical=False, is_effective="normal",
                attacker_hp_remaining=attacker.current_hp,
                defender_hp_remaining=defender.current_hp,
                message=f"{attacker.name}이(가) 방어 태세를 취했다!",
            )

        is_special = action.action_type == "special"
        damage, is_crit, effectiveness = self.calculate_damage(attacker, defender, is_special)
        defender.current_hp = max(0, defender.current_hp - damage)

        eff_msg = ""
        if effectiveness == "effective":
            eff_msg = " 효과가 좋다!"
        elif effectiveness == "not_effective":
            eff_msg = " 효과가 별로..."

        crit_msg = " 크리티컬!" if is_crit else ""
        action_name = "특수 공격" if is_special else "공격"

        return TurnResult(
            attacker_name=attacker.name, defender_name=defender.name,
            action=action_name, damage=damage, is_critical=is_crit,
            is_effective=effectiveness,
            attacker_hp_remaining=attacker.current_hp,
            defender_hp_remaining=defender.current_hp,
            message=f"{attacker.name}의 {action_name}! {damage} 데미지!{crit_msg}{eff_msg}",
        )

    @staticmethod
    def clamp_opponent_level(player_monster_level: int, opponent: dict) -> dict:
        """
        상대 몬스터 레벨을 플레이어 몬스터 레벨 ± 3 범위로 제한

        밸런스를 위해 상대가 너무 강하거나 너무 약하지 않도록 조정합니다.
        레벨에 맞게 스탯도 비례 보정합니다.
        """
        opp_level = opponent.get("level", 1)
        min_level = max(1, player_monster_level - 3)
        max_level = player_monster_level + 3
        clamped_level = max(min_level, min(max_level, opp_level))

        if clamped_level != opp_level and opp_level > 0:
            # 레벨 변경 시 스탯 비례 보정
            scale = clamped_level / opp_level
            opponent = opponent.copy()
            opponent["level"] = clamped_level
            if "stats" in opponent and isinstance(opponent["stats"], dict):
                opponent["stats"] = {
                    k: max(1, int(v * scale))
                    for k, v in opponent["stats"].items()
                }

        return opponent

    def get_battle_reward(self, winner: BattleMonster, loser: BattleMonster) -> dict:
        """배틀 보상 계산"""
        exp = 10 + loser.level * 5
        gold = 50 + loser.level * 10
        # 상위 희귀도 상대 격파 시 보너스
        bonus = max(0, loser.level - winner.level) * 2

        return {
            "exp": exp + bonus,
            "gold": gold + bonus * 5,
            "bonus_message": f"레벨 차 보너스! +{bonus}" if bonus > 0 else "",
        }
