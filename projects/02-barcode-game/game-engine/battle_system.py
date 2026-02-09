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
        self.max_hp = monster["stats"]["hp"]
        self.current_hp = self.max_hp
        self.attack = monster["stats"]["attack"]
        self.defense = monster["stats"]["defense"]
        self.speed = monster["stats"]["speed"]
        self.special = monster["stats"]["special"]
        self.is_defending = False

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

        기본 데미지 = (공격력 * 레벨보정) / (방어력 * 0.5) * 상성 * 크리티컬 * 랜덤
        """
        base_stat = attacker.special if is_special else attacker.attack
        level_mod = 1 + (attacker.level * 0.1)

        # 방어 중이면 방어력 2배
        def_stat = defender.defense * (2 if defender.is_defending else 1)

        # 기본 데미지
        raw_damage = (base_stat * level_mod * 2) / max(def_stat * 0.5, 1)

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

        # 랜덤 변동 (85~100%)
        raw_damage *= random.uniform(0.85, 1.0)

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
