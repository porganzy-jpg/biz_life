"""
BarcodeQuest 던전 캠페인 시스템

5개 챕터, 총 30 스테이지의 스토리 던전 PvE 컨텐츠.

챕터 구조:
  1. 그림자 숲 (Shadow Forest)    - stages 1~6
  2. 얼음 동굴 (Ice Cave)         - stages 7~12
  3. 화염 사원 (Fire Temple)      - stages 13~18
  4. 폭풍 성채 (Storm Fortress)   - stages 19~24
  5. 심연의 왕좌 (Abyss Throne)   - stages 25~30

각 챕터: 5 일반 스테이지 + 1 보스 스테이지
"""
import hashlib
import math
import random
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from database import Base, SessionLocal

# ================================================================
#  DB Models
# ================================================================

class DungeonProgress(Base):
    """플레이어의 던전 스테이지 클리어 기록"""
    __tablename__ = "dungeon_progress"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), nullable=False, index=True)
    stage_id = Column(Integer, nullable=False)
    stars = Column(Integer, default=0)          # 1~3
    best_turns = Column(Integer, default=99)
    completed_at = Column(DateTime, default=datetime.utcnow)


class DungeonBossLog(Base):
    """보스 도전 기록"""
    __tablename__ = "dungeon_boss_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), nullable=False, index=True)
    boss_id = Column(Integer, nullable=False)       # chapter number 1~5
    attempt_count = Column(Integer, default=0)
    best_turns = Column(Integer, default=99)
    defeated = Column(Integer, default=0)           # 0 or 1
    defeated_at = Column(DateTime, nullable=True)


class DungeonEnergyState(Base):
    """던전 에너지 상태"""
    __tablename__ = "dungeon_energy_states"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    energy = Column(Integer, default=50)
    max_energy = Column(Integer, default=50)
    last_recovery_time = Column(Float, default=0.0)


# ================================================================
#  Chapter / Stage Definitions
# ================================================================

CHAPTERS = {
    1: {
        "name": "그림자 숲",
        "name_en": "Shadow Forest",
        "emoji": "\U0001F332",
        "description": "어둠이 드리운 고대의 숲. 그림자 속에서 기이한 존재들이 움직인다.",
        "lore": "오래전 빛의 수호자가 쓰러진 후, 이 숲은 영원한 황혼에 갇혔다. "
                "나무들은 그림자를 먹고 자라며, 숲의 주인인 '그림자 녹대왕'이 모든 것을 지배한다.",
        "theme_types": ["Dark", "Nature", "Spirit"],
        "bg_color": "#2d3436",
        "accent": "#00b894",
    },
    2: {
        "name": "얼음 동굴",
        "name_en": "Ice Cave",
        "emoji": "\u2744\uFE0F",
        "description": "영원히 녹지 않는 얼음으로 뒤덮인 거대한 동굴.",
        "lore": "태초의 겨울이 만든 이 동굴은 시간마저 얼어붙어 있다. "
                "얼음의 심장에는 고대 빙룡 '프로스트 하트'가 잠들어 있다.",
        "theme_types": ["Water", "Wind", "Spirit"],
        "bg_color": "#74b9ff",
        "accent": "#0984e3",
    },
    3: {
        "name": "화염 사원",
        "name_en": "Fire Temple",
        "emoji": "\U0001F525",
        "description": "용암이 흐르는 고대 사원. 불꽃의 시련이 기다린다.",
        "lore": "화염의 신을 모시던 사원은 이제 광기에 빠진 불의 정령들이 점령했다. "
                "사원 최심부에는 '영원불꽃의 수호자'가 침입자를 기다린다.",
        "theme_types": ["Fire", "Earth", "Tech"],
        "bg_color": "#d63031",
        "accent": "#fdcb6e",
    },
    4: {
        "name": "폭풍 성채",
        "name_en": "Storm Fortress",
        "emoji": "\u26A1",
        "description": "하늘 위에 떠 있는 고대 성채. 끊임없는 뇌우가 감싸고 있다.",
        "lore": "천상의 건축가들이 세운 이 성채는 폭풍의 힘으로 하늘에 떠 있다. "
                "지금은 '뇌전의 군주'가 번개의 군단을 이끌며 성채를 지배한다.",
        "theme_types": ["Wind", "Tech", "Light"],
        "bg_color": "#6c5ce7",
        "accent": "#a29bfe",
    },
    5: {
        "name": "심연의 왕좌",
        "name_en": "Abyss Throne",
        "emoji": "\U0001F480",
        "description": "세계의 끝, 심연 속에 존재하는 최후의 왕좌.",
        "lore": "모든 어둠이 태어나는 곳. 심연의 왕은 세계를 삼키려 한다. "
                "'종말의 군주'를 쓰러뜨려야만 세계에 평화가 돌아온다.",
        "theme_types": ["Dark", "Fire", "Spirit"],
        "bg_color": "#2d3436",
        "accent": "#e17055",
    },
}


def _get_chapter_for_stage(stage_id: int) -> int:
    """stage_id (1~30) -> chapter number (1~5)"""
    return (stage_id - 1) // 6 + 1


def _is_boss_stage(stage_id: int) -> bool:
    """6, 12, 18, 24, 30 are boss stages"""
    return stage_id % 6 == 0


def _stage_index_in_chapter(stage_id: int) -> int:
    """Returns 0~5 (position within chapter)"""
    return (stage_id - 1) % 6


# ================================================================
#  Monster Name Pools (Korean themed names)
# ================================================================

MONSTER_NAMES = {
    "Dark": [
        "그림자 늑대", "암흑 박쥐", "유령 거미", "밤의 까마귀",
        "저주받은 나무", "어둠 슬라임", "망령 기사", "혼돈의 눈",
        "그림자 뱀", "흑염 정령", "어둠의 사냥꾼", "몽환의 나비",
    ],
    "Nature": [
        "독버섯 전사", "가시 덩굴", "숲의 골렘", "맹독 꽃",
        "야생 멧돼지", "고대 나무 정령", "이끼 거인", "포자 요정",
        "뿌리 마녀", "숲의 파수꾼", "덩굴 사냥꾼", "꽃잎 무사",
    ],
    "Spirit": [
        "방황하는 혼백", "빛나는 위스프", "은빛 요정", "환영 기사",
        "꿈의 수호자", "영혼의 불꽃", "안개 정령", "달빛 유령",
        "수정 요정", "영혼 포식자", "고요의 정령", "별빛 환영",
    ],
    "Water": [
        "얼음 정령", "서리 늑대", "빙결 골렘", "눈보라 매",
        "냉기 슬라임", "빙하 거북", "서리 요정", "얼음 뱀",
        "동결 전사", "눈의 정령", "빙수 곰", "한파 마법사",
    ],
    "Wind": [
        "돌풍 독수리", "회오리 정령", "바람 요정", "폭풍 늑대",
        "천공 기사", "기류 슬라임", "선풍 뱀", "질풍 기수",
        "태풍 골렘", "하늘 사냥꾼", "진공 마법사", "소용돌이 박쥐",
    ],
    "Fire": [
        "화염 도마뱀", "불꽃 정령", "용암 골렘", "적염 전사",
        "화산 뱀", "불의 요정", "폭염 늑대", "잿빛 악마",
        "흑염 기사", "마그마 슬라임", "불사조 유령", "화염의 눈",
    ],
    "Earth": [
        "바위 골렘", "모래 전갈", "대지의 전사", "지진 두더지",
        "암석 거인", "모래폭풍 뱀", "수정 갑충", "지하 마법사",
        "바위 거북", "흙의 정령", "사막 기수", "석화 가고일",
    ],
    "Tech": [
        "기계 파수꾼", "전기 드론", "강철 골렘", "레이저 기사",
        "회로 정령", "자동 포탑", "전자 뱀", "사이버 늑대",
        "나노 슬라임", "전파 요정", "기어 거인", "플라즈마 전사",
    ],
    "Light": [
        "빛의 기사", "성스러운 정령", "광선 요정", "태양 늑대",
        "빛나는 골렘", "홀리 뱀", "프리즘 전사", "오로라 마법사",
        "광명의 수호자", "별빛 기사", "성광 슬라임", "신성 불꽃",
    ],
    "Food": [
        "떡 전사", "김치 요정", "라면 골렘", "치킨 기사",
        "케이크 슬라임", "소세지 뱀", "피자 마법사", "초코 정령",
        "빵 거인", "아이스크림 요정", "과일 사냥꾼", "사탕 늑대",
    ],
}


# ================================================================
#  Boss Definitions
# ================================================================

BOSSES = {
    1: {
        "name": "그림자 녹대왕",
        "title": "숲의 지배자",
        "emoji": "\U0001F43A",
        "type": "Dark",
        "lore": "오래전 숲의 수호자였으나 어둠에 타락한 고대의 늑대왕. "
                "그의 포효 한 번에 숲 전체가 떨린다.",
        "abilities": [
            {"name": "그림자 포효", "type": "aoe", "description": "전체 대상에게 공격력 120%의 피해",
             "multiplier": 1.2},
            {"name": "어둠의 치유", "type": "heal", "description": "최대 HP의 15% 회복",
             "heal_pct": 15},
            {"name": "공포의 눈빛", "type": "debuff", "description": "상대 공격력 20% 감소 (3턴)",
             "debuff_stat": "attack", "debuff_pct": 20, "duration": 3},
        ],
        "drops": [
            {"item_id": "star_shard", "chance": 1.0, "count": 2},
            {"item_id": "rainbow_dew", "chance": 0.5, "count": 1},
            {"item_id": "shadow_essence", "chance": 0.3, "count": 1},
        ],
    },
    2: {
        "name": "프로스트 하트",
        "title": "얼음의 심장",
        "emoji": "\U0001F409",
        "type": "Water",
        "lore": "태초의 겨울이 낳은 빙룡. 그의 숨결은 모든 것을 영원히 얼려버린다. "
                "심장에서 뿜어져 나오는 한기는 시간마저 멈추게 한다.",
        "abilities": [
            {"name": "절대영도", "type": "aoe", "description": "전체 대상에게 공격력 130%의 피해",
             "multiplier": 1.3},
            {"name": "빙결 갑옷", "type": "buff", "description": "방어력 30% 증가 (3턴)",
             "buff_stat": "defense", "buff_pct": 30, "duration": 3},
            {"name": "동결 숨결", "type": "debuff", "description": "상대 속도 25% 감소 (3턴)",
             "debuff_stat": "speed", "debuff_pct": 25, "duration": 3},
        ],
        "drops": [
            {"item_id": "star_shard", "chance": 1.0, "count": 3},
            {"item_id": "rainbow_dew", "chance": 0.7, "count": 2},
            {"item_id": "frost_crystal", "chance": 0.3, "count": 1},
        ],
    },
    3: {
        "name": "영원불꽃의 수호자",
        "title": "화염 사원의 주인",
        "emoji": "\U0001F525",
        "type": "Fire",
        "lore": "화염의 신이 남긴 마지막 수호자. 꺼지지 않는 불꽃으로 사원을 지킨다. "
                "분노에 빠지면 사원 전체가 용암으로 뒤덮인다.",
        "abilities": [
            {"name": "화염 폭풍", "type": "aoe", "description": "전체 대상에게 공격력 140%의 피해",
             "multiplier": 1.4},
            {"name": "불사의 화염", "type": "heal", "description": "최대 HP의 20% 회복",
             "heal_pct": 20},
            {"name": "용암 분출", "type": "aoe", "description": "전체 대상에게 공격력 100%의 피해 + 방어력 15% 감소",
             "multiplier": 1.0, "debuff_stat": "defense", "debuff_pct": 15, "duration": 2},
        ],
        "drops": [
            {"item_id": "dragon_scale", "chance": 0.8, "count": 1},
            {"item_id": "moon_crystal", "chance": 0.5, "count": 1},
            {"item_id": "fire_heart", "chance": 0.25, "count": 1},
        ],
    },
    4: {
        "name": "뇌전의 군주",
        "title": "폭풍 성채의 지배자",
        "emoji": "\u26A1",
        "type": "Tech",
        "lore": "번개를 조종하는 고대 병기. 의식을 가진 최초의 기계 생명체이며 "
                "성채의 모든 에너지를 자신의 것으로 만들었다.",
        "abilities": [
            {"name": "천둥 심판", "type": "aoe", "description": "전체 대상에게 공격력 150%의 피해",
             "multiplier": 1.5},
            {"name": "전자기 방벽", "type": "buff", "description": "방어력 40% 증가 (2턴)",
             "buff_stat": "defense", "buff_pct": 40, "duration": 2},
            {"name": "과부하", "type": "debuff", "description": "상대 전체 스탯 10% 감소 (2턴)",
             "debuff_stat": "all", "debuff_pct": 10, "duration": 2},
        ],
        "drops": [
            {"item_id": "dragon_scale", "chance": 1.0, "count": 2},
            {"item_id": "moon_crystal", "chance": 0.8, "count": 2},
            {"item_id": "storm_core", "chance": 0.2, "count": 1},
        ],
    },
    5: {
        "name": "종말의 군주",
        "title": "심연의 왕",
        "emoji": "\U0001F451",
        "type": "Dark",
        "lore": "모든 어둠의 근원이자 심연의 절대 지배자. "
                "세계를 종말로 이끌려는 그를 막는 것이 모든 모험의 최종 목표다.",
        "abilities": [
            {"name": "심연의 일격", "type": "aoe", "description": "전체 대상에게 공격력 180%의 피해",
             "multiplier": 1.8},
            {"name": "어둠 재생", "type": "heal", "description": "최대 HP의 25% 회복",
             "heal_pct": 25},
            {"name": "종말의 선언", "type": "debuff", "description": "상대 전체 스탯 20% 감소 (3턴)",
             "debuff_stat": "all", "debuff_pct": 20, "duration": 3},
        ],
        "drops": [
            {"item_id": "dragon_scale", "chance": 1.0, "count": 3},
            {"item_id": "moon_crystal", "chance": 1.0, "count": 3},
            {"item_id": "abyss_crown", "chance": 0.15, "count": 1},
        ],
    },
}


# ================================================================
#  Stage Names
# ================================================================

STAGE_NAMES = {
    # Chapter 1
    1: "그늘진 입구", 2: "이끼낀 오솔길", 3: "버섯 군락지",
    4: "고목의 심장부", 5: "어둠의 샘", 6: "녹대왕의 영역",
    # Chapter 2
    7: "동굴 입구", 8: "빙하 통로", 9: "수정 광장",
    10: "얼어붙은 호수", 11: "서리 미궁", 12: "빙룡의 둥지",
    # Chapter 3
    13: "사원 외벽", 14: "용암 회랑", 15: "화염 제단",
    16: "재의 정원", 17: "불꽃 탑", 18: "수호자의 방",
    # Chapter 4
    19: "하늘 다리", 20: "폭풍의 문", 21: "번개 탑",
    22: "기계 공방", 23: "전기 미로", 24: "군주의 왕좌",
    # Chapter 5
    25: "심연의 문", 26: "절망의 계단", 27: "망자의 전당",
    28: "혼돈의 회랑", 29: "종말의 광장", 30: "왕좌의 방",
}


# ================================================================
#  Energy System Constants
# ================================================================

DUNGEON_MAX_ENERGY = 50
DUNGEON_ENERGY_REGEN_INTERVAL = 360  # 6 minutes per 1 energy
NORMAL_STAGE_COST = 5
BOSS_STAGE_COST = 10


# ================================================================
#  DungeonManager
# ================================================================

class DungeonManager:
    """던전 캠페인 관리자"""

    # Active battle sessions (in-memory, keyed by session_id)
    active_battles: Dict[str, dict] = {}

    def __init__(self):
        self.active_battles = {}

    # --------------------------------------------------------
    #  Energy Management
    # --------------------------------------------------------

    def _get_energy_state(self, session_id: str) -> dict:
        """Load or create energy state from DB"""
        db = SessionLocal()
        try:
            row = db.query(DungeonEnergyState).filter(
                DungeonEnergyState.session_id == session_id
            ).first()
            if row is None:
                row = DungeonEnergyState(
                    session_id=session_id,
                    energy=DUNGEON_MAX_ENERGY,
                    max_energy=DUNGEON_MAX_ENERGY,
                    last_recovery_time=time.time(),
                )
                db.add(row)
                db.commit()
                db.refresh(row)
            return {
                "energy": row.energy,
                "max_energy": row.max_energy,
                "last_recovery_time": row.last_recovery_time,
            }
        finally:
            db.close()

    def _save_energy_state(self, session_id: str, energy: int,
                           max_energy: int, last_recovery_time: float):
        db = SessionLocal()
        try:
            row = db.query(DungeonEnergyState).filter(
                DungeonEnergyState.session_id == session_id
            ).first()
            if row is None:
                row = DungeonEnergyState(session_id=session_id)
                db.add(row)
            row.energy = energy
            row.max_energy = max_energy
            row.last_recovery_time = last_recovery_time
            db.commit()
        finally:
            db.close()

    def get_energy(self, session_id: str) -> dict:
        """Get current energy with passive regen applied"""
        state = self._get_energy_state(session_id)
        energy = state["energy"]
        max_energy = state["max_energy"]
        last_time = state["last_recovery_time"]

        now = time.time()
        if energy < max_energy:
            elapsed = now - last_time
            ticks = int(elapsed // DUNGEON_ENERGY_REGEN_INTERVAL)
            if ticks > 0:
                energy = min(max_energy, energy + ticks)
                last_time += ticks * DUNGEON_ENERGY_REGEN_INTERVAL
                self._save_energy_state(session_id, energy, max_energy, last_time)
        else:
            last_time = now
            self._save_energy_state(session_id, energy, max_energy, last_time)

        # Time until next regen
        if energy < max_energy:
            elapsed_since = now - last_time
            seconds_to_next = max(0, DUNGEON_ENERGY_REGEN_INTERVAL - elapsed_since)
        else:
            seconds_to_next = 0

        return {
            "energy": energy,
            "max_energy": max_energy,
            "seconds_to_next_regen": int(seconds_to_next),
        }

    def _spend_energy(self, session_id: str, cost: int) -> bool:
        """Attempt to spend energy; returns True on success"""
        e = self.get_energy(session_id)
        if e["energy"] < cost:
            return False
        state = self._get_energy_state(session_id)
        new_energy = e["energy"] - cost
        self._save_energy_state(
            session_id, new_energy, state["max_energy"], state["last_recovery_time"]
        )
        return True

    def restore_energy(self, session_id: str, amount: int) -> dict:
        """Restore energy (from items)"""
        state = self._get_energy_state(session_id)
        # Apply regen first
        e = self.get_energy(session_id)
        new_energy = min(state["max_energy"], e["energy"] + amount)
        self._save_energy_state(
            session_id, new_energy, state["max_energy"],
            self._get_energy_state(session_id)["last_recovery_time"]
        )
        return self.get_energy(session_id)

    # --------------------------------------------------------
    #  Progress Queries
    # --------------------------------------------------------

    def _get_all_progress(self, session_id: str) -> List[dict]:
        """Load all cleared stages for a player"""
        db = SessionLocal()
        try:
            rows = db.query(DungeonProgress).filter(
                DungeonProgress.session_id == session_id
            ).all()
            return [
                {
                    "stage_id": r.stage_id,
                    "stars": r.stars,
                    "best_turns": r.best_turns,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                }
                for r in rows
            ]
        finally:
            db.close()

    def _get_stage_progress(self, session_id: str, stage_id: int) -> Optional[dict]:
        db = SessionLocal()
        try:
            row = db.query(DungeonProgress).filter(
                DungeonProgress.session_id == session_id,
                DungeonProgress.stage_id == stage_id,
            ).first()
            if row is None:
                return None
            return {
                "stage_id": row.stage_id,
                "stars": row.stars,
                "best_turns": row.best_turns,
            }
        finally:
            db.close()

    def _save_stage_progress(self, session_id: str, stage_id: int,
                             stars: int, turns: int):
        db = SessionLocal()
        try:
            row = db.query(DungeonProgress).filter(
                DungeonProgress.session_id == session_id,
                DungeonProgress.stage_id == stage_id,
            ).first()
            if row is None:
                row = DungeonProgress(
                    session_id=session_id,
                    stage_id=stage_id,
                    stars=stars,
                    best_turns=turns,
                    completed_at=datetime.utcnow(),
                )
                db.add(row)
            else:
                if stars > row.stars:
                    row.stars = stars
                if turns < row.best_turns:
                    row.best_turns = turns
                row.completed_at = datetime.utcnow()
            db.commit()
        finally:
            db.close()

    def _save_boss_log(self, session_id: str, boss_id: int,
                       defeated: bool, turns: int):
        db = SessionLocal()
        try:
            row = db.query(DungeonBossLog).filter(
                DungeonBossLog.session_id == session_id,
                DungeonBossLog.boss_id == boss_id,
            ).first()
            if row is None:
                row = DungeonBossLog(
                    session_id=session_id,
                    boss_id=boss_id,
                    attempt_count=1,
                    best_turns=turns if defeated else 99,
                    defeated=1 if defeated else 0,
                    defeated_at=datetime.utcnow() if defeated else None,
                )
                db.add(row)
            else:
                row.attempt_count += 1
                if defeated:
                    row.defeated = 1
                    row.defeated_at = datetime.utcnow()
                    if turns < row.best_turns:
                        row.best_turns = turns
            db.commit()
        finally:
            db.close()

    # --------------------------------------------------------
    #  Campaign Status
    # --------------------------------------------------------

    def get_campaign_status(self, session_id: str) -> dict:
        """Full campaign overview for a player"""
        progress = self._get_all_progress(session_id)
        energy = self.get_energy(session_id)

        cleared_map = {p["stage_id"]: p for p in progress}

        # Determine highest cleared stage
        max_cleared = max(cleared_map.keys()) if cleared_map else 0

        chapters = []
        total_stars = 0

        for ch_num in range(1, 6):
            ch = CHAPTERS[ch_num]
            start_stage = (ch_num - 1) * 6 + 1
            end_stage = ch_num * 6

            ch_stages = []
            ch_stars = 0
            ch_unlocked = (start_stage <= max_cleared + 1) or start_stage == 1

            for sid in range(start_stage, end_stage + 1):
                is_boss = _is_boss_stage(sid)
                cleared_data = cleared_map.get(sid)
                stars = cleared_data["stars"] if cleared_data else 0
                ch_stars += stars
                total_stars += stars

                # A stage is unlocked if:
                #  - It's stage 1 (always unlocked)
                #  - The previous stage is cleared
                stage_unlocked = (sid == 1) or (sid - 1 in cleared_map)

                ch_stages.append({
                    "stage_id": sid,
                    "name": STAGE_NAMES.get(sid, f"스테이지 {sid}"),
                    "is_boss": is_boss,
                    "unlocked": stage_unlocked,
                    "cleared": sid in cleared_map,
                    "stars": stars,
                    "max_stars": 3,
                    "best_turns": cleared_data["best_turns"] if cleared_data else None,
                    "energy_cost": BOSS_STAGE_COST if is_boss else NORMAL_STAGE_COST,
                })

            chapters.append({
                "chapter": ch_num,
                "name": ch["name"],
                "emoji": ch["emoji"],
                "description": ch["description"],
                "bg_color": ch["bg_color"],
                "accent": ch["accent"],
                "unlocked": ch_unlocked,
                "stages": ch_stages,
                "stars": ch_stars,
                "max_stars": 18,  # 6 stages * 3 stars
                "boss_name": BOSSES[ch_num]["name"],
                "boss_defeated": end_stage in cleared_map,
            })

        return {
            "chapters": chapters,
            "total_stars": total_stars,
            "max_stars": 90,
            "highest_cleared": max_cleared,
            "energy": energy,
        }

    # --------------------------------------------------------
    #  Stage Enemies (Procedural Generation)
    # --------------------------------------------------------

    def get_stage_enemies(self, stage_id: int) -> List[dict]:
        """Generate enemies for a given stage. Deterministic via seed."""
        chapter = _get_chapter_for_stage(stage_id)
        ch = CHAPTERS[chapter]
        is_boss = _is_boss_stage(stage_id)

        if is_boss:
            return self._generate_boss_enemies(chapter, stage_id)

        # Seed for consistency
        seed = hashlib.md5(f"dungeon_stage_{stage_id}".encode()).hexdigest()
        rng = random.Random(seed)

        stage_in_ch = _stage_index_in_chapter(stage_id)
        num_enemies = 2 + min(stage_in_ch, 2)  # 2~4 enemies

        enemies = []
        for i in range(num_enemies):
            enemy_type = rng.choice(ch["theme_types"])
            name_pool = MONSTER_NAMES.get(enemy_type, MONSTER_NAMES["Dark"])
            name = rng.choice(name_pool)

            # Stat scaling: base * (1 + stage * 0.15)
            scale = 1 + stage_id * 0.15
            base_hp = int(rng.randint(60, 100) * scale)
            base_atk = int(rng.randint(15, 30) * scale)
            base_def = int(rng.randint(10, 25) * scale)
            base_spd = int(rng.randint(10, 25) * scale)
            base_spc = int(rng.randint(12, 28) * scale)

            level = max(1, stage_id + rng.randint(-1, 2))

            enemy = {
                "id": f"dungeon_s{stage_id}_e{i}",
                "name": name,
                "primary_type": enemy_type,
                "secondary_type": rng.choice(ch["theme_types"]),
                "level": level,
                "rarity": self._stage_rarity(stage_id, rng),
                "stats": {
                    "hp": base_hp,
                    "attack": base_atk,
                    "defense": base_def,
                    "speed": base_spd,
                    "special": base_spc,
                },
                "is_boss": False,
            }
            enemies.append(enemy)

        return enemies

    def _generate_boss_enemies(self, chapter: int, stage_id: int) -> List[dict]:
        """Generate a single powerful boss monster"""
        boss = BOSSES[chapter]
        scale = 1 + stage_id * 0.15

        # Boss base stats are significantly higher
        seed = hashlib.md5(f"boss_{chapter}".encode()).hexdigest()
        rng = random.Random(seed)

        boss_hp = int(300 * scale)
        boss_atk = int(50 * scale)
        boss_def = int(40 * scale)
        boss_spd = int(35 * scale)
        boss_spc = int(45 * scale)

        return [{
            "id": f"boss_{chapter}",
            "name": boss["name"],
            "title": boss["title"],
            "primary_type": boss["type"],
            "secondary_type": boss["type"],
            "level": stage_id + 5,
            "rarity": "Legendary",
            "stats": {
                "hp": boss_hp,
                "attack": boss_atk,
                "defense": boss_def,
                "speed": boss_spd,
                "special": boss_spc,
            },
            "is_boss": True,
            "emoji": boss["emoji"],
            "abilities": boss["abilities"],
            "enrage_threshold": 0.3,
        }]

    @staticmethod
    def _stage_rarity(stage_id: int, rng: random.Random) -> str:
        """Determine enemy rarity based on stage"""
        r = rng.random()
        if stage_id >= 25:
            if r < 0.1:
                return "Legendary"
            elif r < 0.3:
                return "Epic"
            elif r < 0.6:
                return "Rare"
            return "Uncommon"
        elif stage_id >= 13:
            if r < 0.05:
                return "Epic"
            elif r < 0.25:
                return "Rare"
            elif r < 0.6:
                return "Uncommon"
            return "Common"
        else:
            if r < 0.1:
                return "Rare"
            elif r < 0.35:
                return "Uncommon"
            return "Common"

    # --------------------------------------------------------
    #  Enter Stage
    # --------------------------------------------------------

    def enter_stage(self, session_id: str, stage_id: int,
                    party: List[dict]) -> dict:
        """Validate and enter a dungeon stage"""
        if stage_id < 1 or stage_id > 30:
            return {"error": "유효하지 않은 스테이지입니다."}

        if not party:
            return {"error": "파티에 몬스터가 없습니다!"}

        # Check if stage is unlocked
        if stage_id > 1:
            prev = self._get_stage_progress(session_id, stage_id - 1)
            if prev is None:
                return {"error": "이전 스테이지를 먼저 클리어해야 합니다!"}

        # Check energy
        is_boss = _is_boss_stage(stage_id)
        cost = BOSS_STAGE_COST if is_boss else NORMAL_STAGE_COST
        if not self._spend_energy(session_id, cost):
            energy = self.get_energy(session_id)
            return {
                "error": f"던전 에너지가 부족합니다! (필요: {cost}, 보유: {energy['energy']})",
                "energy": energy,
            }

        # Generate enemies
        enemies = self.get_stage_enemies(stage_id)
        chapter = _get_chapter_for_stage(stage_id)

        # Initialize battle state
        battle_state = {
            "session_id": session_id,
            "stage_id": stage_id,
            "chapter": chapter,
            "is_boss": is_boss,
            "turn": 0,
            "party": [],
            "enemies": [],
            "battle_log": [],
            "status": "active",
            "boss_enraged": False,
            "boss_debuffs": {},    # stat -> {pct, turns_left}
            "boss_buffs": {},      # stat -> {pct, turns_left}
        }

        # Initialize party monsters for battle
        for i, m in enumerate(party[:3]):
            battle_state["party"].append({
                "index": i,
                "id": m.get("id", f"party_{i}"),
                "name": m.get("name", "Unknown"),
                "primary_type": m.get("primary_type", "Dark"),
                "secondary_type": m.get("secondary_type", "Dark"),
                "level": m.get("level", 1),
                "max_hp": m.get("stats", {}).get("hp", 50),
                "current_hp": m.get("stats", {}).get("hp", 50),
                "attack": m.get("stats", {}).get("attack", 15),
                "defense": m.get("stats", {}).get("defense", 10),
                "speed": m.get("stats", {}).get("speed", 10),
                "special": m.get("stats", {}).get("special", 12),
                "is_alive": True,
            })

        # Initialize enemies for battle
        for e in enemies:
            battle_state["enemies"].append({
                "id": e["id"],
                "name": e["name"],
                "primary_type": e["primary_type"],
                "secondary_type": e.get("secondary_type", e["primary_type"]),
                "level": e["level"],
                "max_hp": e["stats"]["hp"],
                "current_hp": e["stats"]["hp"],
                "attack": e["stats"]["attack"],
                "defense": e["stats"]["defense"],
                "speed": e["stats"]["speed"],
                "special": e["stats"]["special"],
                "is_alive": True,
                "is_boss": e.get("is_boss", False),
                "abilities": e.get("abilities", []),
                "enrage_threshold": e.get("enrage_threshold", 0.0),
            })

        self.active_battles[session_id] = battle_state

        ch = CHAPTERS[chapter]
        boss_info = BOSSES.get(chapter) if is_boss else None

        return {
            "ok": True,
            "stage_id": stage_id,
            "stage_name": STAGE_NAMES.get(stage_id, f"스테이지 {stage_id}"),
            "chapter": chapter,
            "chapter_name": ch["name"],
            "chapter_emoji": ch["emoji"],
            "is_boss": is_boss,
            "party": battle_state["party"],
            "enemies": [
                {
                    "id": e["id"],
                    "name": e["name"],
                    "primary_type": e["primary_type"],
                    "level": e["level"],
                    "max_hp": e["max_hp"],
                    "current_hp": e["current_hp"],
                    "is_boss": e["is_boss"],
                }
                for e in battle_state["enemies"]
            ],
            "boss_info": {
                "name": boss_info["name"],
                "title": boss_info["title"],
                "emoji": boss_info["emoji"],
                "lore": boss_info["lore"],
                "abilities": [
                    {"name": a["name"], "description": a["description"]}
                    for a in boss_info["abilities"]
                ],
            } if boss_info else None,
            "energy": self.get_energy(session_id),
        }

    # --------------------------------------------------------
    #  Battle Turn
    # --------------------------------------------------------

    def battle_turn(self, session_id: str, action: str = "attack",
                    target_idx: int = 0) -> dict:
        """Execute one battle turn"""
        battle = self.active_battles.get(session_id)
        if battle is None:
            return {"error": "진행 중인 던전 전투가 없습니다."}

        if battle["status"] != "active":
            return {"error": "전투가 이미 종료되었습니다."}

        battle["turn"] += 1
        turn_log = []

        # --- Tick debuffs/buffs ---
        self._tick_effects(battle)

        # --- Player Phase ---
        alive_party = [p for p in battle["party"] if p["is_alive"]]
        alive_enemies = [e for e in battle["enemies"] if e["is_alive"]]

        if not alive_party:
            battle["status"] = "defeat"
            return self._build_battle_result(battle)

        if not alive_enemies:
            battle["status"] = "victory"
            return self._build_battle_result(battle)

        # Each alive party monster attacks
        for pm in alive_party:
            alive_enemies = [e for e in battle["enemies"] if e["is_alive"]]
            if not alive_enemies:
                break

            # Pick target: lowest HP enemy or specified
            if target_idx < len(alive_enemies):
                target = alive_enemies[target_idx]
            else:
                target = min(alive_enemies, key=lambda e: e["current_hp"])

            is_special = (action == "special")
            dmg, crit, eff = self._calc_damage(pm, target, is_special, battle)

            target["current_hp"] = max(0, target["current_hp"] - dmg)
            if target["current_hp"] <= 0:
                target["is_alive"] = False

            eff_msg = ""
            if eff == "effective":
                eff_msg = " 효과가 좋다!"
            elif eff == "not_effective":
                eff_msg = " 효과가 별로..."
            crit_msg = " 크리티컬!" if crit else ""
            act_name = "특수 공격" if is_special else "공격"

            log_entry = {
                "phase": "player",
                "attacker": pm["name"],
                "target": target["name"],
                "action": act_name,
                "damage": dmg,
                "is_critical": crit,
                "effectiveness": eff,
                "target_hp": target["current_hp"],
                "target_max_hp": target["max_hp"],
                "target_alive": target["is_alive"],
                "message": f"{pm['name']}의 {act_name}! {target['name']}에게 {dmg} 데미지!{crit_msg}{eff_msg}",
            }
            turn_log.append(log_entry)

        # --- Enemy Phase ---
        alive_enemies = [e for e in battle["enemies"] if e["is_alive"]]
        alive_party = [p for p in battle["party"] if p["is_alive"]]

        for enemy in alive_enemies:
            if not alive_party:
                break

            # Boss enrage check
            if enemy["is_boss"] and not battle.get("boss_enraged"):
                hp_pct = enemy["current_hp"] / max(1, enemy["max_hp"])
                if hp_pct <= enemy.get("enrage_threshold", 0.3):
                    battle["boss_enraged"] = True
                    turn_log.append({
                        "phase": "boss_enrage",
                        "attacker": enemy["name"],
                        "message": f"\u26A0\uFE0F {enemy['name']}이(가) 분노했다! 공격력 50% 증가!",
                        "damage": 0,
                    })

            # Boss ability usage
            if enemy["is_boss"] and enemy.get("abilities") and battle["turn"] % 3 == 0:
                ability_log = self._execute_boss_ability(enemy, battle, alive_party)
                turn_log.extend(ability_log)
                alive_party = [p for p in battle["party"] if p["is_alive"]]
                continue

            # Normal attack on random party member
            target_pm = random.choice(alive_party)
            atk_stat = enemy["attack"]
            if battle.get("boss_enraged") and enemy["is_boss"]:
                atk_stat = int(atk_stat * 1.5)

            # Apply debuffs to enemy attack
            debuff_mult = 1.0
            for stat_key, deb in battle.get("boss_debuffs", {}).items():
                if stat_key == "attack" and deb["turns_left"] > 0:
                    debuff_mult *= (1 - deb["pct"] / 100)

            atk_stat = int(atk_stat * debuff_mult)

            # Damage calc
            raw = atk_stat * (1 + enemy["level"] * 0.1) * 2
            def_stat = target_pm["defense"]

            # Apply boss buffs to defense if applicable
            buff_mult = 1.0
            for stat_key, bf in battle.get("boss_buffs", {}).items():
                if stat_key == "defense" and bf["turns_left"] > 0 and enemy["is_boss"]:
                    buff_mult *= (1 + bf["pct"] / 100)

            def_stat_enemy = def_stat  # target defense
            reduction = def_stat_enemy / (def_stat_enemy + 100)
            raw *= (1 - reduction)

            crit = random.random() < 0.1
            if crit:
                raw *= 1.5
            raw *= random.uniform(0.85, 1.1)
            dmg = max(1, int(raw))

            target_pm["current_hp"] = max(0, target_pm["current_hp"] - dmg)
            if target_pm["current_hp"] <= 0:
                target_pm["is_alive"] = False

            crit_msg = " 크리티컬!" if crit else ""
            log_entry = {
                "phase": "enemy",
                "attacker": enemy["name"],
                "target": target_pm["name"],
                "action": "공격",
                "damage": dmg,
                "is_critical": crit,
                "target_hp": target_pm["current_hp"],
                "target_max_hp": target_pm["max_hp"],
                "target_alive": target_pm["is_alive"],
                "message": f"{enemy['name']}의 공격! {target_pm['name']}에게 {dmg} 데미지!{crit_msg}",
            }
            turn_log.append(log_entry)
            alive_party = [p for p in battle["party"] if p["is_alive"]]

        battle["battle_log"].extend(turn_log)

        # Check win/loss
        alive_party = [p for p in battle["party"] if p["is_alive"]]
        alive_enemies = [e for e in battle["enemies"] if e["is_alive"]]

        if not alive_enemies:
            battle["status"] = "victory"
        elif not alive_party:
            battle["status"] = "defeat"
        elif battle["turn"] >= 30:
            battle["status"] = "defeat"  # Timeout = loss

        return self._build_battle_result(battle, turn_log)

    def _execute_boss_ability(self, boss: dict, battle: dict,
                              alive_party: List[dict]) -> List[dict]:
        """Execute a random boss ability"""
        abilities = boss.get("abilities", [])
        if not abilities:
            return []

        ability = random.choice(abilities)
        logs = []

        if ability["type"] == "aoe":
            mult = ability.get("multiplier", 1.0)
            base_atk = boss["attack"]
            if battle.get("boss_enraged"):
                base_atk = int(base_atk * 1.5)

            for pm in alive_party:
                raw = base_atk * mult * (1 + boss["level"] * 0.1)
                reduction = pm["defense"] / (pm["defense"] + 100)
                raw *= (1 - reduction)
                raw *= random.uniform(0.85, 1.1)
                dmg = max(1, int(raw))
                pm["current_hp"] = max(0, pm["current_hp"] - dmg)
                if pm["current_hp"] <= 0:
                    pm["is_alive"] = False

                logs.append({
                    "phase": "boss_ability",
                    "attacker": boss["name"],
                    "target": pm["name"],
                    "action": ability["name"],
                    "damage": dmg,
                    "target_hp": pm["current_hp"],
                    "target_max_hp": pm["max_hp"],
                    "target_alive": pm["is_alive"],
                    "message": f"\U0001F4A5 {boss['name']}의 {ability['name']}! {pm['name']}에게 {dmg} 데미지!",
                })

            # AOE with debuff
            if ability.get("debuff_stat"):
                battle["boss_debuffs"][ability["debuff_stat"]] = {
                    "pct": ability["debuff_pct"],
                    "turns_left": ability.get("duration", 2),
                }

        elif ability["type"] == "heal":
            heal_pct = ability.get("heal_pct", 15)
            heal_amount = int(boss["max_hp"] * heal_pct / 100)
            boss["current_hp"] = min(boss["max_hp"], boss["current_hp"] + heal_amount)
            logs.append({
                "phase": "boss_ability",
                "attacker": boss["name"],
                "target": boss["name"],
                "action": ability["name"],
                "damage": -heal_amount,
                "target_hp": boss["current_hp"],
                "target_max_hp": boss["max_hp"],
                "target_alive": True,
                "message": f"\U0001F49A {boss['name']}의 {ability['name']}! HP {heal_amount} 회복!",
            })

        elif ability["type"] == "buff":
            stat = ability.get("buff_stat", "defense")
            battle["boss_buffs"][stat] = {
                "pct": ability["buff_pct"],
                "turns_left": ability.get("duration", 2),
            }
            logs.append({
                "phase": "boss_ability",
                "attacker": boss["name"],
                "target": boss["name"],
                "action": ability["name"],
                "damage": 0,
                "target_hp": boss["current_hp"],
                "target_max_hp": boss["max_hp"],
                "target_alive": True,
                "message": f"\U0001F6E1\uFE0F {boss['name']}의 {ability['name']}! {stat} {ability['buff_pct']}% 증가!",
            })

        elif ability["type"] == "debuff":
            stat = ability.get("debuff_stat", "attack")
            battle["boss_debuffs"][stat] = {
                "pct": ability["debuff_pct"],
                "turns_left": ability.get("duration", 2),
            }
            logs.append({
                "phase": "boss_ability",
                "attacker": boss["name"],
                "target": "전체",
                "action": ability["name"],
                "damage": 0,
                "target_hp": 0,
                "target_max_hp": 0,
                "target_alive": True,
                "message": f"\U0001F608 {boss['name']}의 {ability['name']}! {stat} {ability['debuff_pct']}% 감소!",
            })

        return logs

    def _tick_effects(self, battle: dict):
        """Reduce duration of buffs/debuffs each turn"""
        for key in list(battle.get("boss_debuffs", {}).keys()):
            battle["boss_debuffs"][key]["turns_left"] -= 1
            if battle["boss_debuffs"][key]["turns_left"] <= 0:
                del battle["boss_debuffs"][key]
        for key in list(battle.get("boss_buffs", {}).keys()):
            battle["boss_buffs"][key]["turns_left"] -= 1
            if battle["boss_buffs"][key]["turns_left"] <= 0:
                del battle["boss_buffs"][key]

    def _calc_damage(self, attacker: dict, defender: dict,
                     is_special: bool, battle: dict) -> Tuple[int, bool, str]:
        """Calculate player -> enemy damage"""
        base = attacker["special"] if is_special else attacker["attack"]

        # Apply party debuffs (from boss debuff abilities)
        debuff_mult = 1.0
        for stat_key, deb in battle.get("boss_debuffs", {}).items():
            if stat_key in ("attack", "all") and deb["turns_left"] > 0:
                debuff_mult *= (1 - deb["pct"] / 100)
        base = int(base * debuff_mult)

        level_mod = 1 + attacker["level"] * 0.1
        raw = base * level_mod * 2

        def_stat = defender["defense"]
        # Apply boss buffs to defense
        for stat_key, bf in battle.get("boss_buffs", {}).items():
            if stat_key == "defense" and bf["turns_left"] > 0 and defender.get("is_boss"):
                def_stat = int(def_stat * (1 + bf["pct"] / 100))

        reduction = def_stat / (def_stat + 100)
        raw *= (1 - reduction)

        # Type effectiveness
        TYPE_ADVANTAGE = {
            "Fire": ["Nature", "Food"], "Water": ["Fire", "Earth"],
            "Nature": ["Water", "Wind"], "Tech": ["Spirit", "Wind"],
            "Spirit": ["Dark", "Light"], "Dark": ["Tech", "Food"],
            "Earth": ["Fire", "Tech"], "Wind": ["Water", "Spirit"],
            "Food": ["Nature", "Light"], "Light": ["Dark", "Earth"],
        }
        atk_type = attacker.get("primary_type", "")
        def_type = defender.get("primary_type", "")
        eff = "normal"
        if def_type in TYPE_ADVANTAGE.get(atk_type, []):
            raw *= 1.5
            eff = "effective"
        elif atk_type in TYPE_ADVANTAGE.get(def_type, []):
            raw *= 0.7
            eff = "not_effective"

        crit = random.random() < min(0.25, attacker.get("speed", 10) / 500)
        if crit:
            raw *= 1.5

        raw *= random.uniform(0.80, 1.10)
        return max(1, int(raw)), crit, eff

    def _build_battle_result(self, battle: dict,
                             turn_log: List[dict] = None) -> dict:
        """Build response dict for a battle turn or completion"""
        result = {
            "status": battle["status"],
            "turn": battle["turn"],
            "is_boss": battle["is_boss"],
            "boss_enraged": battle.get("boss_enraged", False),
            "party": [
                {
                    "name": p["name"],
                    "current_hp": p["current_hp"],
                    "max_hp": p["max_hp"],
                    "is_alive": p["is_alive"],
                }
                for p in battle["party"]
            ],
            "enemies": [
                {
                    "id": e["id"],
                    "name": e["name"],
                    "current_hp": e["current_hp"],
                    "max_hp": e["max_hp"],
                    "is_alive": e["is_alive"],
                    "is_boss": e.get("is_boss", False),
                }
                for e in battle["enemies"]
            ],
            "turn_log": turn_log or [],
        }

        if battle["status"] in ("victory", "defeat"):
            result["completion"] = self._calculate_completion(battle)

        return result

    def _calculate_completion(self, battle: dict) -> dict:
        """Calculate stars, rewards on completion"""
        stage_id = battle["stage_id"]
        chapter = battle["chapter"]
        is_boss = battle["is_boss"]
        is_victory = battle["status"] == "victory"
        turns = battle["turn"]

        if not is_victory:
            return {
                "victory": False,
                "stars": 0,
                "rewards": {"gold": 0, "exp": 0, "items": []},
                "message": "패배했습니다... 다시 도전하세요!",
            }

        # Star calculation
        alive_count = sum(1 for p in battle["party"] if p["is_alive"])
        total_party = len(battle["party"])
        hp_ratio = sum(
            p["current_hp"] / max(1, p["max_hp"])
            for p in battle["party"] if p["is_alive"]
        ) / max(1, total_party)

        stars = 1
        if is_boss:
            if turns <= 15 and hp_ratio > 0.3:
                stars = 3
            elif turns <= 25 and alive_count >= 2:
                stars = 2
        else:
            if turns <= 6 and hp_ratio > 0.5:
                stars = 3
            elif turns <= 10 and alive_count >= 2:
                stars = 2

        # Rewards
        base_gold = 50 + stage_id * 20
        base_exp = 20 + stage_id * 10
        if is_boss:
            base_gold *= 3
            base_exp *= 3

        # Star bonus
        gold = int(base_gold * (1 + (stars - 1) * 0.25))
        exp = int(base_exp * (1 + (stars - 1) * 0.25))

        items = []
        rng = random.Random()

        # Normal stage item drops
        if not is_boss:
            if rng.random() < 0.3 + stage_id * 0.01:
                item_pool = ["exp_candy_s", "exp_candy_m", "atk_stone",
                             "def_seed", "spd_feather", "hp_fruit"]
                if stage_id >= 13:
                    item_pool.append("star_shard")
                if stage_id >= 19:
                    item_pool.extend(["rainbow_dew", "exp_candy_l"])
                items.append(rng.choice(item_pool))
        else:
            # Boss drops
            boss_drops = BOSSES[chapter]["drops"]
            for drop in boss_drops:
                if rng.random() < drop["chance"]:
                    for _ in range(drop["count"]):
                        items.append(drop["item_id"])

        # Save progress
        session_id = battle["session_id"]
        self._save_stage_progress(session_id, stage_id, stars, turns)
        if is_boss:
            self._save_boss_log(session_id, chapter, True, turns)

        # Clean up battle
        if session_id in self.active_battles:
            del self.active_battles[session_id]

        return {
            "victory": True,
            "stars": stars,
            "best_turns": turns,
            "rewards": {
                "gold": gold,
                "exp": exp,
                "items": items,
            },
            "message": self._victory_message(stage_id, stars, is_boss, chapter),
        }

    @staticmethod
    def _victory_message(stage_id: int, stars: int, is_boss: bool,
                         chapter: int) -> str:
        star_text = "\u2B50" * stars
        if is_boss:
            boss = BOSSES[chapter]
            return f"{boss['name']}을(를) 처치했습니다! {star_text}"
        return f"스테이지 {stage_id} 클리어! {star_text}"

    # --------------------------------------------------------
    #  Boss Info
    # --------------------------------------------------------

    def get_boss_info(self, chapter: int) -> dict:
        """Get boss details and lore"""
        if chapter not in BOSSES:
            return {"error": "유효하지 않은 챕터입니다."}

        boss = BOSSES[chapter]
        ch = CHAPTERS[chapter]
        return {
            "chapter": chapter,
            "chapter_name": ch["name"],
            "chapter_emoji": ch["emoji"],
            "boss": {
                "name": boss["name"],
                "title": boss["title"],
                "emoji": boss["emoji"],
                "type": boss["type"],
                "lore": boss["lore"],
                "abilities": [
                    {"name": a["name"], "type": a["type"],
                     "description": a["description"]}
                    for a in boss["abilities"]
                ],
                "drops": [
                    {"item_id": d["item_id"], "chance_pct": int(d["chance"] * 100)}
                    for d in boss["drops"]
                ],
            },
            "chapter_lore": ch["lore"],
        }

    # --------------------------------------------------------
    #  Reward Preview
    # --------------------------------------------------------

    def get_reward_preview(self, stage_id: int) -> dict:
        """Preview rewards for a stage"""
        if stage_id < 1 or stage_id > 30:
            return {"error": "유효하지 않은 스테이지입니다."}

        chapter = _get_chapter_for_stage(stage_id)
        is_boss = _is_boss_stage(stage_id)

        base_gold = 50 + stage_id * 20
        base_exp = 20 + stage_id * 10
        if is_boss:
            base_gold *= 3
            base_exp *= 3

        drops = []
        if is_boss:
            for d in BOSSES[chapter]["drops"]:
                drops.append({
                    "item_id": d["item_id"],
                    "chance_pct": int(d["chance"] * 100),
                    "count": d["count"],
                })
        else:
            possible = ["exp_candy_s", "exp_candy_m"]
            if stage_id >= 7:
                possible.extend(["atk_stone", "def_seed", "spd_feather", "hp_fruit"])
            if stage_id >= 13:
                possible.append("star_shard")
            if stage_id >= 19:
                possible.extend(["rainbow_dew", "exp_candy_l"])
            drops = [{"item_id": item, "chance_pct": 30} for item in possible]

        return {
            "stage_id": stage_id,
            "stage_name": STAGE_NAMES.get(stage_id, f"스테이지 {stage_id}"),
            "chapter": chapter,
            "is_boss": is_boss,
            "energy_cost": BOSS_STAGE_COST if is_boss else NORMAL_STAGE_COST,
            "rewards": {
                "gold_range": f"{base_gold}~{int(base_gold * 1.5)}",
                "exp_range": f"{base_exp}~{int(base_exp * 1.5)}",
                "possible_drops": drops,
            },
        }

    # --------------------------------------------------------
    #  Leaderboard
    # --------------------------------------------------------

    def get_leaderboard(self, limit: int = 20) -> List[dict]:
        """Boss clear time leaderboard"""
        db = SessionLocal()
        try:
            rows = db.query(DungeonBossLog).filter(
                DungeonBossLog.defeated == 1
            ).order_by(
                DungeonBossLog.boss_id.desc(),
                DungeonBossLog.best_turns.asc(),
            ).limit(limit).all()

            results = []
            for r in rows:
                boss = BOSSES.get(r.boss_id, {})
                results.append({
                    "session_id": r.session_id,
                    "boss_id": r.boss_id,
                    "boss_name": boss.get("name", f"보스 {r.boss_id}"),
                    "best_turns": r.best_turns,
                    "attempt_count": r.attempt_count,
                    "defeated_at": r.defeated_at.isoformat() if r.defeated_at else None,
                })
            return results
        finally:
            db.close()

    # --------------------------------------------------------
    #  Abandon Battle
    # --------------------------------------------------------

    def abandon_battle(self, session_id: str) -> dict:
        """Abandon current dungeon battle"""
        if session_id in self.active_battles:
            del self.active_battles[session_id]
            return {"ok": True, "message": "전투를 포기했습니다."}
        return {"error": "진행 중인 전투가 없습니다."}

    # --------------------------------------------------------
    #  Auto Battle
    # --------------------------------------------------------

    def auto_battle(self, session_id: str) -> dict:
        """Run the full battle automatically and return the result"""
        battle = self.active_battles.get(session_id)
        if battle is None:
            return {"error": "진행 중인 던전 전투가 없습니다."}

        all_logs = []
        result = None
        max_turns = 30
        for _ in range(max_turns):
            if battle["status"] != "active":
                break
            # Alternate between attack and special
            action = "attack" if battle["turn"] % 2 == 0 else "special"
            result = self.battle_turn(session_id, action, 0)
            all_logs.extend(result.get("turn_log", []))
            if result["status"] != "active":
                break

        if result:
            result["full_log"] = all_logs
        return result
