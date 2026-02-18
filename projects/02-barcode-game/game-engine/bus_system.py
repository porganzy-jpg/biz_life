"""
BarcodeQuest 여행 버스 시스템 (Fallout Shelter Style)

1~3층 버스에 9종의 방을 건설하고, 수집한 몬스터를 배치하여
자원을 생산하는 방치형 시스템.

층 구조:
  - 1F: 무료 해금, 3슬롯
  - 2F: 3,000G + Lv.5
  - 3F: 10,000G + Lv.10

어피니티 공식:
  affinity = 1.0 + type_bonus + stat_bonus
  S(1.75+), A(1.5+), B(1.25+), C(1.0+)

생산 공식:
  production/h = base * affinity * room_level_mult
  축적 상한: 24시간, 몬스터 미배치 시 생산 0
"""
import time
from typing import Dict, List, Optional


# === 방 정의 ===
ROOM_DEFINITIONS = {
    "gold_mine": {
        "name": "골드 광산",
        "emoji": "\u26cf",
        "category": "resource",
        "preferred_types": ["Earth", "Dark"],
        "preferred_stat": "defense",
        "base_production": {"gold": 10},
        "build_cost": 500,
        "description": "골드를 채굴합니다",
    },
    "energy_gen": {
        "name": "에너지 발전소",
        "emoji": "\u26a1",
        "category": "resource",
        "preferred_types": ["Tech", "Fire"],
        "preferred_stat": "speed",
        "base_production": {"energy": 3},
        "build_cost": 800,
        "description": "에너지를 생산합니다",
    },
    "exp_library": {
        "name": "경험의 도서관",
        "emoji": "\U0001F4DA",
        "category": "resource",
        "preferred_types": ["Spirit", "Light"],
        "preferred_stat": "special",
        "base_production": {"exp": 5},
        "build_cost": 600,
        "description": "경험치를 생산합니다",
    },
    "training": {
        "name": "훈련소",
        "emoji": "\U0001F94A",
        "category": "combat",
        "preferred_types": ["Fire", "Wind"],
        "preferred_stat": "attack",
        "base_production": {"stat_point": 1},
        "build_cost": 1000,
        "description": "배치된 몬스터의 스탯을 강화합니다",
    },
    "arena": {
        "name": "배틀 아레나",
        "emoji": "\u2694",
        "category": "combat",
        "preferred_types": ["Dark", "Fire"],
        "preferred_stat": "attack",
        "base_production": {"gold": 15, "exp": 8},
        "build_cost": 1500,
        "description": "골드와 경험치를 동시에 생산합니다",
    },
    "evo_lab": {
        "name": "진화 연구소",
        "emoji": "\u2697",
        "category": "combat",
        "preferred_types": ["Nature", "Spirit"],
        "preferred_stat": "special",
        "base_production": {"evo_material": 1},
        "build_cost": 2000,
        "description": "12시간마다 진화 재료를 생산합니다",
    },
    "radar": {
        "name": "레이더실",
        "emoji": "\U0001F4E1",
        "category": "explore",
        "preferred_types": ["Tech", "Light"],
        "preferred_stat": "speed",
        "base_production": {"hint": 1},
        "build_cost": 1200,
        "description": "6시간마다 스캔 힌트를 제공합니다",
    },
    "expedition_base": {
        "name": "탐험 기지",
        "emoji": "\U0001F9ED",
        "category": "explore",
        "preferred_types": ["Nature", "Water"],
        "preferred_stat": "hp",
        "base_production": {"expedition_bonus": 15},
        "build_cost": 1000,
        "description": "탐험 보상 +15%",
    },
    "warehouse": {
        "name": "창고",
        "emoji": "\U0001F4E6",
        "category": "explore",
        "preferred_types": ["Earth", "Food"],
        "preferred_stat": "hp",
        "base_production": {"inventory_slot": 5},
        "build_cost": 800,
        "description": "인벤토리 슬롯 +5",
    },
}

# === 층 해금 비용 ===
FLOOR_UNLOCK = [
    {"floor": 1, "cost": 0, "required_level": 1},
    {"floor": 2, "cost": 3000, "required_level": 5},
    {"floor": 3, "cost": 10000, "required_level": 10},
]

# 방 레벨 배수
ROOM_LEVEL_MULT = {1: 1.0, 2: 1.5, 3: 2.0}

# 축적 상한 (시간)
MAX_ACCUMULATE_HOURS = 24


def calculate_affinity(monster: dict, room_type: str) -> dict:
    """몬스터-방 궁합 계산

    Returns:
        dict with affinity(float), grade(str), type_bonus, stat_bonus
    """
    room = ROOM_DEFINITIONS.get(room_type)
    if not room:
        return {"affinity": 1.0, "grade": "C", "type_bonus": 0, "stat_bonus": 0}

    type_bonus = 0.0
    m_primary = monster.get("primary_type", "")
    m_secondary = monster.get("secondary_type", "")
    pref_types = room["preferred_types"]

    # primary_type 매치
    if m_primary in pref_types:
        type_bonus += 0.5 if m_primary == pref_types[0] else 0.25
    # secondary_type 매치
    if m_secondary in pref_types:
        type_bonus += 0.25

    # 스탯 보너스
    stat_bonus = 0.0
    stats = monster.get("stats", {})
    pref_stat = room["preferred_stat"]

    if stats:
        # hp -> hp, attack -> attack 등 매핑
        stat_values = [
            ("hp", stats.get("hp", 0)),
            ("attack", stats.get("attack", 0)),
            ("defense", stats.get("defense", 0)),
            ("speed", stats.get("speed", 0)),
            ("special", stats.get("special", 0)),
        ]
        sorted_stats = sorted(stat_values, key=lambda x: x[1], reverse=True)

        if sorted_stats[0][0] == pref_stat:
            stat_bonus += 0.5
        elif len(sorted_stats) > 1 and sorted_stats[1][0] == pref_stat:
            stat_bonus += 0.25

    affinity = min(2.0, 1.0 + type_bonus + stat_bonus)

    # 등급
    if affinity >= 1.75:
        grade = "S"
    elif affinity >= 1.5:
        grade = "A"
    elif affinity >= 1.25:
        grade = "B"
    else:
        grade = "C"

    return {
        "affinity": round(affinity, 2),
        "grade": grade,
        "type_bonus": round(type_bonus, 2),
        "stat_bonus": round(stat_bonus, 2),
    }


def get_room_suggestion(monster: dict) -> dict:
    """몬스터에 가장 적합한 방 추천 (스캔 시 사용)"""
    best_room = None
    best_affinity = 0
    best_grade = "C"

    for room_id, room_def in ROOM_DEFINITIONS.items():
        result = calculate_affinity(monster, room_id)
        if result["affinity"] > best_affinity:
            best_affinity = result["affinity"]
            best_room = room_id
            best_grade = result["grade"]

    if best_room:
        room_def = ROOM_DEFINITIONS[best_room]
        return {
            "room_id": best_room,
            "room_name": room_def["name"],
            "room_emoji": room_def["emoji"],
            "affinity": best_affinity,
            "grade": best_grade,
        }
    return None


class BusSystem:
    """여행 버스 관리 시스템"""

    def __init__(self):
        # session_id -> bus_state
        self.buses: Dict[str, dict] = {}

    def get_or_create_bus(self, session_id: str) -> dict:
        """버스 초기화 (1층 3슬롯 빈 상태)"""
        if session_id not in self.buses:
            self.buses[session_id] = {
                "max_floor": 1,
                "floors": {
                    1: {
                        "slots": [
                            {"room_type": None, "room_level": 0, "monster": None},
                            {"room_type": None, "room_level": 0, "monster": None},
                            {"room_type": None, "room_level": 0, "monster": None},
                        ]
                    }
                },
                "last_collect_time": time.time(),
                "created_at": time.time(),
            }
        return self.buses[session_id]

    def get_bus_state(self, session_id: str) -> dict:
        """전체 버스 상태 + 생산량 계산"""
        bus = self.get_or_create_bus(session_id)
        now = time.time()
        elapsed_hours = min(
            (now - bus["last_collect_time"]) / 3600,
            MAX_ACCUMULATE_HOURS,
        )

        floors_info = []
        total_production = {}
        assigned_monster_ids = set()

        for floor_num in range(1, bus["max_floor"] + 1):
            floor_data = bus["floors"][floor_num]
            slots_info = []

            for slot_idx, slot in enumerate(floor_data["slots"]):
                slot_info = {
                    "slot": slot_idx,
                    "room_type": slot["room_type"],
                    "room_level": slot["room_level"],
                    "monster": None,
                    "production_per_hour": {},
                    "accumulated": {},
                    "affinity": None,
                }

                if slot["room_type"]:
                    room_def = ROOM_DEFINITIONS[slot["room_type"]]
                    slot_info["room_name"] = room_def["name"]
                    slot_info["room_emoji"] = room_def["emoji"]
                    slot_info["room_category"] = room_def["category"]

                    if slot["monster"]:
                        monster = slot["monster"]
                        slot_info["monster"] = {
                            "id": monster.get("id"),
                            "name": monster.get("name"),
                            "primary_type": monster.get("primary_type"),
                            "secondary_type": monster.get("secondary_type"),
                            "rarity": monster.get("rarity"),
                            "level": monster.get("level", 1),
                        }
                        assigned_monster_ids.add(monster.get("id"))

                        aff = calculate_affinity(monster, slot["room_type"])
                        slot_info["affinity"] = aff
                        level_mult = ROOM_LEVEL_MULT.get(slot["room_level"], 1.0)

                        for res, base_val in room_def["base_production"].items():
                            prod = round(base_val * aff["affinity"] * level_mult, 2)
                            slot_info["production_per_hour"][res] = prod
                            slot_info["accumulated"][res] = round(
                                prod * elapsed_hours, 1
                            )
                            total_production[res] = round(
                                total_production.get(res, 0) + prod * elapsed_hours, 1
                            )

                slots_info.append(slot_info)

            floors_info.append({
                "floor": floor_num,
                "slots": slots_info,
            })

        # 다음 층 해금 정보
        next_floor = None
        if bus["max_floor"] < 3:
            nf = FLOOR_UNLOCK[bus["max_floor"]]
            next_floor = {
                "floor": nf["floor"],
                "cost": nf["cost"],
                "required_level": nf["required_level"],
            }

        return {
            "max_floor": bus["max_floor"],
            "floors": floors_info,
            "total_accumulated": total_production,
            "elapsed_hours": round(elapsed_hours, 2),
            "next_floor_unlock": next_floor,
            "assigned_monster_ids": list(assigned_monster_ids),
            "available_rooms": self._get_available_rooms(session_id),
        }

    def _get_available_rooms(self, session_id: str) -> list:
        """건설 가능한 방 목록 (이미 건설된 방 제외)"""
        bus = self.get_or_create_bus(session_id)
        built = set()
        for floor_data in bus["floors"].values():
            for slot in floor_data["slots"]:
                if slot["room_type"]:
                    built.add(slot["room_type"])

        available = []
        for room_id, room_def in ROOM_DEFINITIONS.items():
            if room_id not in built:
                available.append({
                    "room_id": room_id,
                    "name": room_def["name"],
                    "emoji": room_def["emoji"],
                    "category": room_def["category"],
                    "build_cost": room_def["build_cost"],
                    "description": room_def["description"],
                    "preferred_types": room_def["preferred_types"],
                    "preferred_stat": room_def["preferred_stat"],
                })
        return available

    def build_room(
        self, session_id: str, floor: int, slot: int, room_type: str, player_gold: int
    ) -> dict:
        """방 건설"""
        bus = self.get_or_create_bus(session_id)

        # 검증
        if room_type not in ROOM_DEFINITIONS:
            return {"error": f"알 수 없는 방 타입: {room_type}"}

        if floor < 1 or floor > bus["max_floor"]:
            return {"error": f"{floor}층은 아직 해금되지 않았습니다!"}

        floor_data = bus["floors"].get(floor)
        if not floor_data or slot < 0 or slot >= len(floor_data["slots"]):
            return {"error": f"잘못된 슬롯 위치입니다."}

        if floor_data["slots"][slot]["room_type"] is not None:
            return {"error": "이미 방이 건설된 슬롯입니다!"}

        # 중복 건설 검사
        for fd in bus["floors"].values():
            for s in fd["slots"]:
                if s["room_type"] == room_type:
                    room_name = ROOM_DEFINITIONS[room_type]["name"]
                    return {"error": f"{room_name}은(는) 이미 건설되어 있습니다!"}

        # 비용 확인
        cost = ROOM_DEFINITIONS[room_type]["build_cost"]
        if player_gold < cost:
            return {
                "error": f"골드가 부족합니다! (필요: {cost:,}G, 보유: {player_gold:,}G)"
            }

        # 건설
        floor_data["slots"][slot] = {
            "room_type": room_type,
            "room_level": 1,
            "monster": None,
        }

        room_def = ROOM_DEFINITIONS[room_type]
        return {
            "ok": True,
            "cost": cost,
            "room_name": room_def["name"],
            "room_emoji": room_def["emoji"],
            "message": f"{room_def['emoji']} {room_def['name']}을(를) {floor}층 슬롯{slot+1}에 건설했습니다!",
        }

    def assign_monster(
        self, session_id: str, floor: int, slot: int, monster: dict
    ) -> dict:
        """몬스터 배치"""
        bus = self.get_or_create_bus(session_id)

        if floor < 1 or floor > bus["max_floor"]:
            return {"error": f"{floor}층은 해금되지 않았습니다!"}

        floor_data = bus["floors"].get(floor)
        if not floor_data or slot < 0 or slot >= len(floor_data["slots"]):
            return {"error": "잘못된 슬롯 위치입니다."}

        target_slot = floor_data["slots"][slot]
        if target_slot["room_type"] is None:
            return {"error": "먼저 방을 건설하세요!"}

        if target_slot["monster"] is not None:
            return {"error": "이미 몬스터가 배치되어 있습니다! 먼저 회수하세요."}

        # 다른 슬롯에 이미 배치된 몬스터인지 확인
        monster_id = monster.get("id")
        for fd in bus["floors"].values():
            for s in fd["slots"]:
                if s["monster"] and s["monster"].get("id") == monster_id:
                    return {"error": "이 몬스터는 이미 다른 방에 배치되어 있습니다!"}

        target_slot["monster"] = monster
        aff = calculate_affinity(monster, target_slot["room_type"])
        room_def = ROOM_DEFINITIONS[target_slot["room_type"]]

        return {
            "ok": True,
            "affinity": aff,
            "message": f"{monster.get('name')}을(를) {room_def['emoji']} {room_def['name']}에 배치했습니다! (궁합: {aff['grade']})",
        }

    def unassign_monster(self, session_id: str, floor: int, slot: int) -> dict:
        """몬스터 회수"""
        bus = self.get_or_create_bus(session_id)

        if floor < 1 or floor > bus["max_floor"]:
            return {"error": f"{floor}층은 해금되지 않았습니다!"}

        floor_data = bus["floors"].get(floor)
        if not floor_data or slot < 0 or slot >= len(floor_data["slots"]):
            return {"error": "잘못된 슬롯 위치입니다."}

        target_slot = floor_data["slots"][slot]
        if target_slot["monster"] is None:
            return {"error": "배치된 몬스터가 없습니다."}

        monster = target_slot["monster"]
        target_slot["monster"] = None

        return {
            "ok": True,
            "monster_name": monster.get("name"),
            "message": f"{monster.get('name')}을(를) 회수했습니다.",
        }

    def upgrade_floor(self, session_id: str, player_gold: int, player_level: int) -> dict:
        """다음 층 해금"""
        bus = self.get_or_create_bus(session_id)

        if bus["max_floor"] >= 3:
            return {"error": "이미 최대 층(3층)입니다!"}

        next_idx = bus["max_floor"]  # 0-indexed: floor 2 is index 1
        unlock_info = FLOOR_UNLOCK[next_idx]
        new_floor = unlock_info["floor"]

        if player_level < unlock_info["required_level"]:
            return {
                "error": f"레벨이 부족합니다! (필요: Lv.{unlock_info['required_level']}, 현재: Lv.{player_level})"
            }

        if player_gold < unlock_info["cost"]:
            return {
                "error": f"골드가 부족합니다! (필요: {unlock_info['cost']:,}G, 보유: {player_gold:,}G)"
            }

        # 해금
        bus["max_floor"] = new_floor
        bus["floors"][new_floor] = {
            "slots": [
                {"room_type": None, "room_level": 0, "monster": None},
                {"room_type": None, "room_level": 0, "monster": None},
                {"room_type": None, "room_level": 0, "monster": None},
            ]
        }

        return {
            "ok": True,
            "cost": unlock_info["cost"],
            "new_floor": new_floor,
            "message": f"{new_floor}층이 해금되었습니다! 새로운 방 3개를 건설할 수 있습니다.",
        }

    def upgrade_room(
        self, session_id: str, floor: int, slot: int, player_gold: int
    ) -> dict:
        """방 레벨업"""
        bus = self.get_or_create_bus(session_id)

        if floor < 1 or floor > bus["max_floor"]:
            return {"error": f"{floor}층은 해금되지 않았습니다!"}

        floor_data = bus["floors"].get(floor)
        if not floor_data or slot < 0 or slot >= len(floor_data["slots"]):
            return {"error": "잘못된 슬롯 위치입니다."}

        target_slot = floor_data["slots"][slot]
        if target_slot["room_type"] is None:
            return {"error": "방이 없습니다!"}

        current_level = target_slot["room_level"]
        if current_level >= 3:
            return {"error": "이미 최대 레벨(Lv.3)입니다!"}

        room_def = ROOM_DEFINITIONS[target_slot["room_type"]]
        base_cost = room_def["build_cost"]

        # Lv1→2: x2, Lv2→3: x5
        if current_level == 1:
            cost = base_cost * 2
        else:
            cost = base_cost * 5

        if player_gold < cost:
            return {
                "error": f"골드가 부족합니다! (필요: {cost:,}G, 보유: {player_gold:,}G)"
            }

        target_slot["room_level"] = current_level + 1

        return {
            "ok": True,
            "cost": cost,
            "new_level": current_level + 1,
            "room_name": room_def["name"],
            "message": f"{room_def['emoji']} {room_def['name']}이(가) Lv.{current_level + 1}로 업그레이드되었습니다!",
        }

    def collect_all(self, session_id: str) -> dict:
        """전체 자원 수령"""
        state = self.get_bus_state(session_id)
        bus = self.get_or_create_bus(session_id)

        accumulated = state["total_accumulated"]
        if not accumulated:
            return {"ok": True, "collected": {}, "message": "수령할 자원이 없습니다."}

        bus["last_collect_time"] = time.time()

        # 정수로 변환 (소수점 버림)
        collected = {}
        for res, val in accumulated.items():
            int_val = int(val)
            if int_val > 0:
                collected[res] = int_val

        parts = []
        if collected.get("gold"):
            parts.append(f"+{collected['gold']}G")
        if collected.get("exp"):
            parts.append(f"+{collected['exp']}EXP")
        if collected.get("energy"):
            parts.append(f"+{collected['energy']}E")
        if collected.get("stat_point"):
            parts.append(f"+{collected['stat_point']} 스탯포인트")
        if collected.get("evo_material"):
            parts.append(f"+{collected['evo_material']} 진화재료")
        if collected.get("hint"):
            parts.append(f"+{collected['hint']} 힌트")

        msg = " ".join(parts) if parts else "수령할 자원이 없습니다."

        return {
            "ok": True,
            "collected": collected,
            "elapsed_hours": state["elapsed_hours"],
            "message": f"버스 자원 수령! {msg}",
        }
