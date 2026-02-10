"""
BarcodeQuest 일일 퀘스트 시스템

매일 리셋되는 퀘스트로 유저의 일일 루틴을 만들고
보상으로 도파민을 제공합니다.

퀘스트 카테고리:
  - 스캔 퀘스트: 바코드 스캔 관련
  - 배틀 퀘스트: 전투 관련
  - 수집 퀘스트: 도감 관련
  - 탐험 퀘스트: 탐험 관련
"""
import time
import hashlib
from typing import Dict, List, Optional
from dataclasses import dataclass, field


# === 퀘스트 풀 정의 ===
QUEST_POOL = [
    # --- 스캔 퀘스트 ---
    {
        "id": "scan_3",
        "title": "바코드 탐험가",
        "description": "바코드를 3번 스캔하세요",
        "emoji": "📷",
        "category": "scan",
        "target": 3,
        "reward_gold": 100,
        "reward_exp": 30,
        "reward_item": None,
    },
    {
        "id": "scan_5",
        "title": "열정 스캐너",
        "description": "바코드를 5번 스캔하세요",
        "emoji": "📱",
        "category": "scan",
        "target": 5,
        "reward_gold": 200,
        "reward_exp": 50,
        "reward_item": "exp_candy_s",
    },
    {
        "id": "scan_new",
        "title": "미지의 발견",
        "description": "새로운 크리처를 1마리 발견하세요",
        "emoji": "🔍",
        "category": "scan",
        "target": 1,
        "reward_gold": 150,
        "reward_exp": 40,
        "reward_item": None,
    },
    # --- 배틀 퀘스트 ---
    {
        "id": "battle_2",
        "title": "도전자",
        "description": "배틀을 2번 하세요",
        "emoji": "⚔️",
        "category": "battle",
        "target": 2,
        "reward_gold": 150,
        "reward_exp": 40,
        "reward_item": None,
    },
    {
        "id": "battle_win",
        "title": "승리의 전사",
        "description": "배틀에서 1번 승리하세요",
        "emoji": "🏆",
        "category": "battle",
        "target": 1,
        "reward_gold": 200,
        "reward_exp": 50,
        "reward_item": "atk_stone",
    },
    {
        "id": "battle_3_wins",
        "title": "연승 행진",
        "description": "배틀에서 3번 승리하세요",
        "emoji": "🔥",
        "category": "battle",
        "target": 3,
        "reward_gold": 500,
        "reward_exp": 100,
        "reward_item": "exp_candy_m",
    },
    # --- 수집 퀘스트 ---
    {
        "id": "collect_variety",
        "title": "다양한 수집",
        "description": "서로 다른 타입의 크리처를 2마리 수집하세요",
        "emoji": "📖",
        "category": "collect",
        "target": 2,
        "reward_gold": 200,
        "reward_exp": 60,
        "reward_item": None,
    },
    # --- 탐험 퀘스트 ---
    {
        "id": "expedition_start",
        "title": "탐험 출발",
        "description": "탐험을 1번 보내세요",
        "emoji": "🗺️",
        "category": "expedition",
        "target": 1,
        "reward_gold": 100,
        "reward_exp": 30,
        "reward_item": None,
    },
    {
        "id": "expedition_collect",
        "title": "보물 수령",
        "description": "탐험 결과를 1번 수령하세요",
        "emoji": "🎁",
        "category": "expedition",
        "target": 1,
        "reward_gold": 200,
        "reward_exp": 50,
        "reward_item": "lucky_clover",
    },
    # --- 일일 특별 ---
    {
        "id": "daily_login",
        "title": "출석 체크",
        "description": "오늘 처음 접속하세요",
        "emoji": "📅",
        "category": "login",
        "target": 1,
        "reward_gold": 50,
        "reward_exp": 20,
        "reward_item": None,
    },
]

# 매일 이 풀에서 4개를 뽑음 (출석 체크 1 + 랜덤 3)
DAILY_QUEST_COUNT = 4


@dataclass
class QuestProgress:
    quest_id: str
    title: str
    description: str
    emoji: str
    category: str
    current: int = 0
    target: int = 1
    completed: bool = False
    claimed: bool = False
    reward_gold: int = 0
    reward_exp: int = 0
    reward_item: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "quest_id": self.quest_id,
            "title": self.title,
            "description": self.description,
            "emoji": self.emoji,
            "category": self.category,
            "current": self.current,
            "target": self.target,
            "completed": self.completed,
            "claimed": self.claimed,
            "progress_pct": min(100, int((self.current / self.target) * 100)),
            "reward_gold": self.reward_gold,
            "reward_exp": self.reward_exp,
            "reward_item": self.reward_item,
        }


class DailyQuestSystem:
    """일일 퀘스트 관리"""

    def __init__(self):
        # session_id → {date_key, quests}
        self.player_quests: Dict[str, dict] = {}

    def _get_date_key(self) -> str:
        """오늘 날짜 키"""
        return time.strftime("%Y-%m-%d")

    def _select_daily_quests(self, date_key: str, session_id: str) -> List[dict]:
        """날짜+세션 기반 오늘의 퀘스트 선택 (결정론적)"""
        seed = hashlib.sha256(f"{date_key}|{session_id}".encode()).hexdigest()
        import random as _rng
        rng = _rng.Random(int(seed[:8], 16))

        # 출석 체크는 항상 포함
        login_quest = next(q for q in QUEST_POOL if q["id"] == "daily_login")
        others = [q for q in QUEST_POOL if q["id"] != "daily_login"]

        selected = rng.sample(others, min(DAILY_QUEST_COUNT - 1, len(others)))
        return [login_quest] + selected

    def get_quests(self, session_id: str) -> List[dict]:
        """오늘의 퀘스트 목록 (없으면 생성)"""
        date_key = self._get_date_key()

        if session_id not in self.player_quests or \
           self.player_quests[session_id].get("date") != date_key:
            # 새 날짜 → 퀘스트 리셋
            quest_defs = self._select_daily_quests(date_key, session_id)
            quests = {}
            for q in quest_defs:
                qp = QuestProgress(
                    quest_id=q["id"],
                    title=q["title"],
                    description=q["description"],
                    emoji=q["emoji"],
                    category=q["category"],
                    target=q["target"],
                    reward_gold=q["reward_gold"],
                    reward_exp=q["reward_exp"],
                    reward_item=q.get("reward_item"),
                )
                # 출석 체크는 자동 완료
                if q["id"] == "daily_login":
                    qp.current = 1
                    qp.completed = True
                quests[q["id"]] = qp

            self.player_quests[session_id] = {
                "date": date_key,
                "quests": quests,
            }

        quests = self.player_quests[session_id]["quests"]
        return [q.to_dict() for q in quests.values()]

    def update_progress(self, session_id: str, category: str,
                        amount: int = 1) -> List[dict]:
        """퀘스트 진행도 업데이트

        Args:
            session_id: 플레이어 세션
            category: "scan", "battle", "battle_win", "collect",
                      "expedition", "expedition_collect"
            amount: 증가량

        Returns:
            list: 새로 완료된 퀘스트 목록
        """
        # 퀘스트 초기화 (아직 안 했으면)
        self.get_quests(session_id)

        quests = self.player_quests[session_id]["quests"]
        newly_completed = []

        for qid, quest in quests.items():
            if quest.completed:
                continue

            match = False
            if quest.category == "scan" and category == "scan":
                match = quest.quest_id in ("scan_3", "scan_5")
            elif quest.category == "scan" and category == "scan_new":
                match = quest.quest_id == "scan_new"
            elif quest.category == "battle" and category == "battle":
                match = quest.quest_id == "battle_2"
            elif quest.category == "battle" and category == "battle_win":
                match = quest.quest_id in ("battle_win", "battle_3_wins", "battle_2")
            elif quest.category == "collect" and category == "collect":
                match = True
            elif quest.category == "expedition" and category == "expedition":
                match = quest.quest_id == "expedition_start"
            elif quest.category == "expedition" and category == "expedition_collect":
                match = quest.quest_id == "expedition_collect"

            if match:
                quest.current = min(quest.current + amount, quest.target)
                if quest.current >= quest.target:
                    quest.completed = True
                    newly_completed.append(quest.to_dict())

        return newly_completed

    def claim_reward(self, session_id: str, quest_id: str) -> Optional[dict]:
        """완료된 퀘스트 보상 수령"""
        if session_id not in self.player_quests:
            return None

        quests = self.player_quests[session_id]["quests"]
        quest = quests.get(quest_id)

        if not quest or not quest.completed or quest.claimed:
            return None

        quest.claimed = True

        return {
            "quest_id": quest_id,
            "title": quest.title,
            "gold": quest.reward_gold,
            "exp": quest.reward_exp,
            "item": quest.reward_item,
            "message": f"퀘스트 '{quest.title}' 보상 수령!",
        }

    def get_summary(self, session_id: str) -> dict:
        """퀘스트 요약"""
        quests_list = self.get_quests(session_id)
        total = len(quests_list)
        completed = sum(1 for q in quests_list if q["completed"])
        claimed = sum(1 for q in quests_list if q["claimed"])
        unclaimed = completed - claimed

        return {
            "total": total,
            "completed": completed,
            "claimed": claimed,
            "unclaimed_rewards": unclaimed,
            "all_completed": completed == total,
        }
