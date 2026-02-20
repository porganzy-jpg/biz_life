# -*- coding: utf-8 -*-
"""
BarcodeQuest 업적(Achievement) 시스템

18개의 업적을 6개 카테고리로 분류하여 관리합니다.

카테고리:
  - collection  : 수집 관련
  - battle      : 전투 관련
  - economy     : 경제 관련
  - guild       : 길드 관련
  - exploration : 탐험 관련
  - special     : 특수 달성

각 업적에는 ID, 이름, 설명, 아이콘, 카테고리, 보상(골드/아이템)이 정의되어 있으며,
check_condition 함수를 통해 달성 여부를 판별합니다.

DB 테이블: player_achievements (session_id, achievement_id, unlocked_at)
"""
from datetime import datetime
from typing import List, Dict, Optional, Callable

from sqlalchemy.orm import Session as DBSession
from database import SessionLocal


# =====================================================
#  업적 정의
# =====================================================

ACHIEVEMENTS: List[Dict] = [
    # === 수집 (Collection) ===
    {
        "id": "coll_first_monster",
        "name": "첫 몬스터",
        "description": "처음으로 몬스터를 스캔해서 획득했습니다!",
        "category": "collection",
        "icon": "egg",
        "reward_gold": 100,
        "reward_item": None,
    },
    {
        "id": "coll_10_monsters",
        "name": "10마리 수집",
        "description": "도감에 10마리의 몬스터를 등록했습니다.",
        "category": "collection",
        "icon": "books",
        "reward_gold": 500,
        "reward_item": "exp_candy_m",
    },
    {
        "id": "coll_50_monsters",
        "name": "50마리 수집",
        "description": "도감에 50마리의 몬스터를 등록했습니다!",
        "category": "collection",
        "icon": "star2",
        "reward_gold": 3000,
        "reward_item": "lucky_clover",
    },
    {
        "id": "coll_legendary",
        "name": "전설 획득",
        "description": "전설(Legendary) 등급 몬스터를 획득했습니다!",
        "category": "collection",
        "icon": "crown",
        "reward_gold": 5000,
        "reward_item": "dragon_scale",
    },

    # === 전투 (Battle) ===
    {
        "id": "battle_first_win",
        "name": "첫 승리",
        "description": "첫 번째 배틀에서 승리했습니다!",
        "category": "battle",
        "icon": "crossed_swords",
        "reward_gold": 200,
        "reward_item": None,
    },
    {
        "id": "battle_10_wins",
        "name": "10연승",
        "description": "배틀에서 총 10번 승리했습니다!",
        "category": "battle",
        "icon": "fire",
        "reward_gold": 1000,
        "reward_item": "atk_stone",
    },
    {
        "id": "battle_50_wins",
        "name": "전투의 달인",
        "description": "배틀에서 총 50번 승리했습니다!",
        "category": "battle",
        "icon": "trophy",
        "reward_gold": 5000,
        "reward_item": "exp_candy_l",
    },
    {
        "id": "battle_pvp_1000",
        "name": "PvP 1000점 도달",
        "description": "PvP 아레나 레이팅 1000점을 달성했습니다!",
        "category": "battle",
        "icon": "medal",
        "reward_gold": 3000,
        "reward_item": "star_shard",
    },

    # === 경제 (Economy) ===
    {
        "id": "econ_first_trade",
        "name": "첫 거래",
        "description": "거래소에서 처음으로 거래를 완료했습니다!",
        "category": "economy",
        "icon": "handshake",
        "reward_gold": 300,
        "reward_item": None,
    },
    {
        "id": "econ_rich",
        "name": "부자",
        "description": "골드를 10,000 이상 보유했습니다!",
        "category": "economy",
        "icon": "moneybag",
        "reward_gold": 1000,
        "reward_item": "exp_candy_m",
    },
    {
        "id": "econ_trader",
        "name": "장사꾼",
        "description": "거래소에서 10회 이상 거래를 완료했습니다!",
        "category": "economy",
        "icon": "chart",
        "reward_gold": 2000,
        "reward_item": "lucky_clover",
    },

    # === 길드 (Guild) ===
    {
        "id": "guild_join",
        "name": "길드 가입",
        "description": "길드에 가입했습니다!",
        "category": "guild",
        "icon": "shield",
        "reward_gold": 500,
        "reward_item": None,
    },
    {
        "id": "guild_boss_kill",
        "name": "길드 보스 처치",
        "description": "길드 보스를 처치했습니다!",
        "category": "guild",
        "icon": "dragon",
        "reward_gold": 3000,
        "reward_item": "moon_crystal",
    },

    # === 탐험 (Exploration) ===
    {
        "id": "explore_100",
        "name": "원정 100회",
        "description": "원정대를 총 100회 파견했습니다!",
        "category": "exploration",
        "icon": "compass",
        "reward_gold": 5000,
        "reward_item": "rainbow_dew",
    },
    {
        "id": "explore_all_zones",
        "name": "모든 지역 탐험",
        "description": "모든 탐험 지역을 방문했습니다!",
        "category": "exploration",
        "icon": "globe",
        "reward_gold": 3000,
        "reward_item": "star_shard",
    },

    # === 특수 (Special) ===
    {
        "id": "special_evolution",
        "name": "진화 달성",
        "description": "크리처를 처음으로 진화시켰습니다!",
        "category": "special",
        "icon": "sparkles",
        "reward_gold": 1000,
        "reward_item": "exp_candy_m",
    },
    {
        "id": "special_max_level",
        "name": "만렙 몬스터",
        "description": "몬스터의 레벨을 50 이상으로 키웠습니다!",
        "category": "special",
        "icon": "hundred",
        "reward_gold": 5000,
        "reward_item": "golden_apple",
    },
    {
        "id": "special_daily_7",
        "name": "일일퀘스트 7일 연속",
        "description": "7일 연속으로 일일퀘스트를 완료했습니다!",
        "category": "special",
        "icon": "calendar",
        "reward_gold": 3000,
        "reward_item": "energy_elixir",
    },
]

# Quick lookup by ID
ACHIEVEMENTS_BY_ID: Dict[str, Dict] = {a["id"]: a for a in ACHIEVEMENTS}

# Category display names (Korean)
CATEGORY_NAMES = {
    "collection": "수집",
    "battle": "전투",
    "economy": "경제",
    "guild": "길드",
    "exploration": "탐험",
    "special": "특수",
}

# Category display icons
CATEGORY_ICONS = {
    "collection": "books",
    "battle": "crossed_swords",
    "economy": "moneybag",
    "guild": "shield",
    "exploration": "compass",
    "special": "sparkles",
}


# =====================================================
#  Progress Calculation Helpers
# =====================================================

def _count_collection(player, collection) -> int:
    """Total distinct monsters in collection."""
    if collection:
        return collection.get_completion_stats().get("total_collected", 0)
    return 0


def _has_legendary(player, collection) -> bool:
    """Whether collection contains a Legendary monster."""
    if collection:
        stats = collection.get_completion_stats()
        return stats.get("by_rarity", {}).get("Legendary", 0) > 0
    return False


def _has_evolved_monster(player) -> bool:
    """Whether any monster in party/inventory has been evolved."""
    for m in player.party + player.inventory:
        if m.get("evolved", False):
            return True
    return False


def _max_monster_level(player) -> int:
    """Highest monster level across party and inventory."""
    max_lv = 0
    for m in player.party + player.inventory:
        lv = m.get("level", 1)
        if lv > max_lv:
            max_lv = lv
    return max_lv


# =====================================================
#  Achievement Condition & Progress Functions
#
#  Each returns (is_met: bool, current: int, target: int)
#  so we can show progress bars for countable achievements.
# =====================================================

def _check_coll_first(player, collection, extra) -> tuple:
    c = _count_collection(player, collection)
    return c >= 1, min(c, 1), 1

def _check_coll_10(player, collection, extra) -> tuple:
    c = _count_collection(player, collection)
    return c >= 10, min(c, 10), 10

def _check_coll_50(player, collection, extra) -> tuple:
    c = _count_collection(player, collection)
    return c >= 50, min(c, 50), 50

def _check_coll_legendary(player, collection, extra) -> tuple:
    has = _has_legendary(player, collection)
    return has, 1 if has else 0, 1

def _check_battle_first(player, collection, extra) -> tuple:
    w = player.total_wins
    return w >= 1, min(w, 1), 1

def _check_battle_10(player, collection, extra) -> tuple:
    w = player.total_wins
    return w >= 10, min(w, 10), 10

def _check_battle_50(player, collection, extra) -> tuple:
    w = player.total_wins
    return w >= 50, min(w, 50), 50

def _check_pvp_1000(player, collection, extra) -> tuple:
    rating = extra.get("pvp_rating", 0)
    return rating >= 1000, min(rating, 1000), 1000

def _check_econ_first_trade(player, collection, extra) -> tuple:
    trades = extra.get("total_trades", 0)
    return trades >= 1, min(trades, 1), 1

def _check_econ_rich(player, collection, extra) -> tuple:
    g = player.gold
    return g >= 10000, min(g, 10000), 10000

def _check_econ_trader(player, collection, extra) -> tuple:
    trades = extra.get("total_trades", 0)
    return trades >= 10, min(trades, 10), 10

def _check_guild_join(player, collection, extra) -> tuple:
    joined = extra.get("in_guild", False)
    return joined, 1 if joined else 0, 1

def _check_guild_boss(player, collection, extra) -> tuple:
    kills = extra.get("guild_boss_kills", 0)
    return kills >= 1, min(kills, 1), 1

def _check_explore_100(player, collection, extra) -> tuple:
    exp_count = extra.get("total_expeditions", 0)
    return exp_count >= 100, min(exp_count, 100), 100

def _check_explore_all(player, collection, extra) -> tuple:
    explored = extra.get("zones_explored", set())
    total_zones = 4  # forest_path, ocean_cave, dragon_nest, starlight_peak
    count = len(explored)
    return count >= total_zones, min(count, total_zones), total_zones

def _check_evolution(player, collection, extra) -> tuple:
    has = _has_evolved_monster(player)
    return has, 1 if has else 0, 1

def _check_max_level(player, collection, extra) -> tuple:
    lv = _max_monster_level(player)
    return lv >= 50, min(lv, 50), 50

def _check_daily_7(player, collection, extra) -> tuple:
    streak = extra.get("daily_quest_streak", 0)
    return streak >= 7, min(streak, 7), 7


# Map achievement_id -> check function
ACHIEVEMENT_CHECKS: Dict[str, Callable] = {
    "coll_first_monster": _check_coll_first,
    "coll_10_monsters": _check_coll_10,
    "coll_50_monsters": _check_coll_50,
    "coll_legendary": _check_coll_legendary,
    "battle_first_win": _check_battle_first,
    "battle_10_wins": _check_battle_10,
    "battle_50_wins": _check_battle_50,
    "battle_pvp_1000": _check_pvp_1000,
    "econ_first_trade": _check_econ_first_trade,
    "econ_rich": _check_econ_rich,
    "econ_trader": _check_econ_trader,
    "guild_join": _check_guild_join,
    "guild_boss_kill": _check_guild_boss,
    "explore_100": _check_explore_100,
    "explore_all_zones": _check_explore_all,
    "special_evolution": _check_evolution,
    "special_max_level": _check_max_level,
    "special_daily_7": _check_daily_7,
}


# =====================================================
#  AchievementManager
# =====================================================

class AchievementManager:
    """
    업적 관리 매니저

    DB 테이블 player_achievements 에 해금된 업적을 기록하고,
    check_achievements() 호출 시 새로 달성된 업적을 감지합니다.
    """

    def __init__(self):
        pass

    # --------------------------------------------------
    #  DB helpers
    # --------------------------------------------------

    @staticmethod
    def _get_db() -> DBSession:
        return SessionLocal()

    def _load_unlocked(self, session_id: str) -> Dict[str, str]:
        """
        Load unlocked achievements from DB.
        Returns dict: { achievement_id: unlocked_at_isoformat }
        """
        from models import PlayerAchievement
        db = self._get_db()
        try:
            rows = db.query(PlayerAchievement).filter(
                PlayerAchievement.session_id == session_id
            ).all()
            return {r.achievement_id: r.unlocked_at.isoformat() if r.unlocked_at else "" for r in rows}
        finally:
            db.close()

    def _unlock(self, session_id: str, achievement_id: str) -> None:
        """Write a new unlock record to DB."""
        from models import PlayerAchievement
        db = self._get_db()
        try:
            existing = db.query(PlayerAchievement).filter(
                PlayerAchievement.session_id == session_id,
                PlayerAchievement.achievement_id == achievement_id,
            ).first()
            if existing is None:
                row = PlayerAchievement(
                    session_id=session_id,
                    achievement_id=achievement_id,
                    unlocked_at=datetime.utcnow(),
                )
                db.add(row)
                db.commit()
        finally:
            db.close()

    # --------------------------------------------------
    #  Public API
    # --------------------------------------------------

    def check_achievements(
        self,
        session_id: str,
        player,
        collection,
        extra: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        Check all achievements and unlock any newly met conditions.

        Args:
            session_id: Player session ID
            player: Player object
            collection: MonsterCollection object
            extra: Additional context dict with keys like:
                   pvp_rating, total_trades, in_guild, guild_boss_kills,
                   total_expeditions, zones_explored, daily_quest_streak

        Returns:
            List of newly unlocked achievement dicts (with reward info)
        """
        if extra is None:
            extra = {}

        unlocked = self._load_unlocked(session_id)
        newly_unlocked = []

        for ach in ACHIEVEMENTS:
            aid = ach["id"]

            # Already unlocked -> skip
            if aid in unlocked:
                continue

            # Check condition
            check_fn = ACHIEVEMENT_CHECKS.get(aid)
            if check_fn is None:
                continue

            is_met, current, target = check_fn(player, collection, extra)

            if is_met:
                self._unlock(session_id, aid)
                newly_unlocked.append({
                    "id": aid,
                    "name": ach["name"],
                    "description": ach["description"],
                    "category": ach["category"],
                    "icon": ach["icon"],
                    "reward_gold": ach["reward_gold"],
                    "reward_item": ach["reward_item"],
                })

        return newly_unlocked

    def get_player_achievements(
        self,
        session_id: str,
        player,
        collection,
        extra: Optional[Dict] = None,
    ) -> Dict:
        """
        Get full achievement list with unlock status and progress.

        Returns dict:
        {
            "total": int,
            "unlocked_count": int,
            "categories": { cat_id: { "name": str, "icon": str } },
            "achievements": [
                {
                    "id", "name", "description", "category", "icon",
                    "reward_gold", "reward_item",
                    "unlocked": bool, "unlocked_at": str or null,
                    "progress_current": int, "progress_target": int,
                },
                ...
            ]
        }
        """
        if extra is None:
            extra = {}

        unlocked = self._load_unlocked(session_id)
        result_list = []

        for ach in ACHIEVEMENTS:
            aid = ach["id"]
            is_unlocked = aid in unlocked

            # Calculate progress
            check_fn = ACHIEVEMENT_CHECKS.get(aid)
            if check_fn:
                _, current, target = check_fn(player, collection, extra)
            else:
                current, target = (1 if is_unlocked else 0), 1

            result_list.append({
                "id": aid,
                "name": ach["name"],
                "description": ach["description"],
                "category": ach["category"],
                "category_name": CATEGORY_NAMES.get(ach["category"], ach["category"]),
                "icon": ach["icon"],
                "reward_gold": ach["reward_gold"],
                "reward_item": ach["reward_item"],
                "unlocked": is_unlocked,
                "unlocked_at": unlocked.get(aid),
                "progress_current": current,
                "progress_target": target,
            })

        categories = {}
        for cat_id, cat_name in CATEGORY_NAMES.items():
            categories[cat_id] = {
                "name": cat_name,
                "icon": CATEGORY_ICONS.get(cat_id, "star"),
            }

        return {
            "total": len(ACHIEVEMENTS),
            "unlocked_count": len(unlocked),
            "categories": categories,
            "achievements": result_list,
        }

    def get_extra_context(
        self,
        session_id: str,
        arena_manager=None,
        trade_manager=None,
        guild_manager=None,
        expedition_system=None,
        daily_quest_system=None,
    ) -> Dict:
        """
        Build the 'extra' context dict needed for achievement checks
        by querying the various subsystems.
        """
        extra = {}

        # PvP rating
        if arena_manager is not None:
            stats = arena_manager.get_player_arena_stats(session_id)
            if stats:
                extra["pvp_rating"] = stats.get("rating", 0)
            else:
                extra["pvp_rating"] = 0

        # Trade count
        if trade_manager is not None:
            history = trade_manager.get_trade_history(session_id, limit=1000)
            extra["total_trades"] = len(history)

        # Guild membership
        if guild_manager is not None:
            guild_info = guild_manager.get_guild_info(session_id)
            extra["in_guild"] = guild_info.get("guild") is not None if isinstance(guild_info, dict) else False
            # Guild boss kills
            extra["guild_boss_kills"] = guild_info.get("boss_kills", 0) if isinstance(guild_info, dict) else 0

        # Expeditions
        if expedition_system is not None:
            # We track total expeditions from player.total_scans as proxy,
            # but ideally we'd store expedition count separately.
            # For now, use a simple heuristic from DB.
            extra["total_expeditions"] = extra.get("total_expeditions", 0)
            extra["zones_explored"] = extra.get("zones_explored", set())

        # Daily quest streak
        if daily_quest_system is not None:
            pq = daily_quest_system.player_quests.get(session_id)
            if pq:
                extra["daily_quest_streak"] = pq.get("streak", 0)
            else:
                extra["daily_quest_streak"] = 0

        return extra
