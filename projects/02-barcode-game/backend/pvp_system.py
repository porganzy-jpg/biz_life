"""
BarcodeQuest PvP 아레나 시스템

ELO 기반 매치메이킹, 자동 배틀, 리더보드
기존 BattleSystem 엔진을 활용한 PvP 전투
"""
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict

from sqlalchemy.orm import Session as DBSession
from sqlalchemy import desc, func

from database import SessionLocal
from pvp_models import ArenaRegistration, PvPBattleLog

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "game-engine"))

from battle_system import BattleSystem, BattleMonster, BattleAction


# =====================================================
#  데이터 클래스
# =====================================================

@dataclass
class ArenaPlayer:
    """아레나 플레이어 상태"""
    session_id: str
    player_level: int = 1
    rating: float = 1000.0
    wins: int = 0
    losses: int = 0
    win_streak: int = 0


# =====================================================
#  ELO 계산
# =====================================================

ELO_K_FACTOR = 32
ELO_DEFAULT_RATING = 1000.0
STREAK_BONUS_PER_WIN = 5
STREAK_BONUS_MAX = 25


def calculate_expected_score(rating_a: float, rating_b: float) -> float:
    """ELO 기대 승률: 1 / (1 + 10^((Rb - Ra) / 400))"""
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def calculate_elo_change(winner_rating: float, loser_rating: float,
                         winner_streak: int = 0) -> tuple:
    """
    ELO 레이팅 변동 계산

    Returns: (winner_change, loser_change)
    """
    expected_winner = calculate_expected_score(winner_rating, loser_rating)
    expected_loser = 1.0 - expected_winner

    winner_change = ELO_K_FACTOR * (1.0 - expected_winner)
    loser_change = ELO_K_FACTOR * (0.0 - expected_loser)

    # 연승 보너스 (최대 +25)
    streak_bonus = min(winner_streak * STREAK_BONUS_PER_WIN, STREAK_BONUS_MAX)
    winner_change += streak_bonus

    return round(winner_change, 1), round(loser_change, 1)


# =====================================================
#  보상 계산
# =====================================================

def calculate_pvp_reward(winner_rating: float, loser_rating: float,
                         win_streak: int) -> dict:
    """
    PvP 보상 계산

    승리: 50 + (상대 레이팅 - 내 레이팅) * 0.1 골드 (최소 30)
    패배: 10 골드 위로금
    연승 3: 보너스 100 골드
    연승 5: 보너스 진화석
    """
    rating_diff = loser_rating - winner_rating
    gold = max(30, int(50 + rating_diff * 0.1))

    bonus_gold = 0
    bonus_item = None

    if win_streak >= 5:
        bonus_gold = 100
        bonus_item = "evolution_stone"
    elif win_streak >= 3:
        bonus_gold = 100

    return {
        "gold": gold + bonus_gold,
        "base_gold": gold,
        "bonus_gold": bonus_gold,
        "bonus_item": bonus_item,
        "streak": win_streak,
    }


CONSOLATION_GOLD = 10


# =====================================================
#  ArenaManager
# =====================================================

class ArenaManager:
    """PvP 아레나 매니저"""

    def __init__(self):
        self.battle_system = BattleSystem()
        # 직전 대전 상대 기록 (같은 상대 연속 매칭 방지)
        self.last_opponent: Dict[str, str] = {}

    def _get_db(self) -> DBSession:
        return SessionLocal()

    # ----- 아레나 등록 -----

    def register_for_arena(self, session_id: str, party: list) -> dict:
        """
        방어 파티 등록 (몬스터 3마리)

        Args:
            session_id: 세션 ID
            party: 방어 파티 몬스터 dict 리스트 (최대 3)

        Returns:
            dict: 등록 결과
        """
        if not party or len(party) == 0:
            return {"error": "방어 파티에 최소 1마리 이상 등록해야 합니다."}

        if len(party) > 3:
            party = party[:3]

        # 몬스터 유효성 검사
        for m in party:
            if not isinstance(m, dict) or "id" not in m or "stats" not in m:
                return {"error": "유효하지 않은 몬스터 데이터입니다."}

        db = self._get_db()
        try:
            row = db.query(ArenaRegistration).filter(
                ArenaRegistration.session_id == session_id
            ).first()

            if row is None:
                row = ArenaRegistration(
                    session_id=session_id,
                    defense_party_json=party,
                    rating=ELO_DEFAULT_RATING,
                    wins=0,
                    losses=0,
                    win_streak=0,
                    registered_at=datetime.utcnow(),
                )
                db.add(row)
            else:
                row.defense_party_json = party

            db.commit()

            return {
                "ok": True,
                "message": f"방어 파티 등록 완료! ({len(party)}마리)",
                "party_size": len(party),
                "rating": row.rating,
                "wins": row.wins,
                "losses": row.losses,
            }
        finally:
            db.close()

    # ----- 매치메이킹 -----

    def find_opponent(self, session_id: str, player_rating: float) -> Optional[dict]:
        """
        상대 찾기 (ELO 기반 매치메이킹)

        1차: +-100 범위
        2차: +-200 범위
        3차: 전체 (fallback)
        같은 상대 연속 매칭 방지
        """
        db = self._get_db()
        try:
            last_opp = self.last_opponent.get(session_id)

            for rating_range in [100, 200, None]:
                query = db.query(ArenaRegistration).filter(
                    ArenaRegistration.session_id != session_id
                )

                if rating_range is not None:
                    query = query.filter(
                        ArenaRegistration.rating >= player_rating - rating_range,
                        ArenaRegistration.rating <= player_rating + rating_range,
                    )

                # 직전 상대 제외
                if last_opp:
                    query = query.filter(
                        ArenaRegistration.session_id != last_opp
                    )

                candidates = query.all()
                if candidates:
                    # 레이팅 차이가 가장 작은 상대 우선 (약간의 랜덤성 추가)
                    candidates.sort(key=lambda c: abs(c.rating - player_rating))
                    # 상위 5명 중 랜덤 선택
                    pool = candidates[:min(5, len(candidates))]
                    chosen = random.choice(pool)
                    return {
                        "session_id": chosen.session_id,
                        "defense_party": chosen.defense_party_json,
                        "rating": chosen.rating,
                        "wins": chosen.wins,
                        "losses": chosen.losses,
                        "win_streak": chosen.win_streak,
                    }

            # 직전 상대 제외 없이 재시도
            if last_opp:
                fallback = db.query(ArenaRegistration).filter(
                    ArenaRegistration.session_id != session_id
                ).all()
                if fallback:
                    chosen = random.choice(fallback)
                    return {
                        "session_id": chosen.session_id,
                        "defense_party": chosen.defense_party_json,
                        "rating": chosen.rating,
                        "wins": chosen.wins,
                        "losses": chosen.losses,
                        "win_streak": chosen.win_streak,
                    }

            return None
        finally:
            db.close()

    # ----- PvP 배틀 실행 -----

    def execute_pvp_battle(self, attacker_party: list,
                           defender_party: list) -> dict:
        """
        자동 PvP 배틀 실행 (기존 BattleSystem 활용)

        각 파티의 몬스터가 1:1로 순차 대전
        모든 몬스터가 쓰러진 쪽이 패배

        Returns:
            dict: {winner: "attacker"|"defender", battle_log: [...], rounds: [...]}
        """
        atk_monsters = [BattleMonster(m) for m in attacker_party if m]
        def_monsters = [BattleMonster(m) for m in defender_party if m]

        if not atk_monsters:
            return {"winner": "defender", "battle_log": [], "rounds": []}
        if not def_monsters:
            return {"winner": "attacker", "battle_log": [], "rounds": []}

        full_log = []
        rounds = []
        atk_idx = 0
        def_idx = 0

        while atk_idx < len(atk_monsters) and def_idx < len(def_monsters):
            p1 = atk_monsters[atk_idx]
            p2 = def_monsters[def_idx]
            round_log = []

            for turn in range(15):  # 최대 15턴
                if not p1.is_alive or not p2.is_alive:
                    break

                # AI 행동 선택
                p1_action = BattleAction(
                    p1.id,
                    random.choice(["attack", "attack", "special"])
                )
                p2_action = BattleAction(
                    p2.id,
                    random.choice(["attack", "attack", "special", "defend"])
                )

                results = self.battle_system.execute_turn(p1, p1_action, p2, p2_action)
                for r in results:
                    entry = {
                        "attacker": r.attacker_name,
                        "defender": r.defender_name,
                        "action": r.action,
                        "damage": r.damage,
                        "is_critical": r.is_critical,
                        "effectiveness": r.is_effective,
                        "attacker_hp": r.attacker_hp_remaining,
                        "defender_hp": r.defender_hp_remaining,
                        "message": r.message,
                    }
                    round_log.append(entry)
                    full_log.append(entry)

            # 턴 제한 도달 시 남은 HP 비율로 승패 결정
            if p1.is_alive and p2.is_alive:
                p1_ratio = p1.current_hp / p1.max_hp
                p2_ratio = p2.current_hp / p2.max_hp
                if p1_ratio >= p2_ratio:
                    p2.current_hp = 0
                else:
                    p1.current_hp = 0

            round_winner = "attacker" if p1.is_alive else "defender"
            rounds.append({
                "attacker_monster": attacker_party[atk_idx].get("name", "???"),
                "defender_monster": defender_party[def_idx].get("name", "???"),
                "winner": round_winner,
                "log": round_log,
            })

            if not p1.is_alive:
                atk_idx += 1
            if not p2.is_alive:
                def_idx += 1

        overall_winner = "attacker" if def_idx >= len(def_monsters) else "defender"

        return {
            "winner": overall_winner,
            "battle_log": full_log,
            "rounds": rounds,
            "attacker_remaining": len(atk_monsters) - atk_idx,
            "defender_remaining": len(def_monsters) - def_idx,
        }

    # ----- 레이팅 업데이트 -----

    def update_ratings(self, winner_id: str, loser_id: str) -> dict:
        """
        ELO 레이팅 업데이트

        Returns:
            dict: {winner_change, loser_change, winner_new_rating, loser_new_rating, ...}
        """
        db = self._get_db()
        try:
            winner_row = db.query(ArenaRegistration).filter(
                ArenaRegistration.session_id == winner_id
            ).first()
            loser_row = db.query(ArenaRegistration).filter(
                ArenaRegistration.session_id == loser_id
            ).first()

            if not winner_row or not loser_row:
                return {"error": "플레이어를 찾을 수 없습니다."}

            # ELO 변동 계산
            new_streak = winner_row.win_streak + 1
            winner_change, loser_change = calculate_elo_change(
                winner_row.rating, loser_row.rating, new_streak
            )

            # 승자 업데이트
            winner_row.rating = max(100, winner_row.rating + winner_change)
            winner_row.wins += 1
            winner_row.win_streak = new_streak
            winner_row.last_battle_at = datetime.utcnow()

            # 패자 업데이트
            loser_row.rating = max(100, loser_row.rating + loser_change)
            loser_row.losses += 1
            loser_row.win_streak = 0
            loser_row.last_battle_at = datetime.utcnow()

            db.commit()

            return {
                "winner_change": winner_change,
                "loser_change": loser_change,
                "winner_new_rating": winner_row.rating,
                "loser_new_rating": loser_row.rating,
                "winner_streak": new_streak,
            }
        finally:
            db.close()

    # ----- 배틀 로그 저장 -----

    def save_battle_log(self, attacker_id: str, defender_id: str,
                        winner_id: str, atk_rating_change: float,
                        def_rating_change: float, battle_log: list,
                        gold_reward: int = 0,
                        bonus_reward: str = None) -> None:
        """PvP 배틀 로그 DB 저장"""
        db = self._get_db()
        try:
            row = PvPBattleLog(
                attacker_id=attacker_id,
                defender_id=defender_id,
                winner_id=winner_id,
                attacker_rating_change=atk_rating_change,
                defender_rating_change=def_rating_change,
                battle_log_json=battle_log,
                gold_reward=gold_reward,
                bonus_reward=bonus_reward,
                created_at=datetime.utcnow(),
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

    # ----- 리더보드 -----

    def get_leaderboard(self, limit: int = 50) -> list:
        """
        글로벌 리더보드 (레이팅 상위 순)

        Returns:
            list: [{rank, session_id, rating, wins, losses, win_rate, win_streak}, ...]
        """
        db = self._get_db()
        try:
            rows = db.query(ArenaRegistration).order_by(
                desc(ArenaRegistration.rating)
            ).limit(limit).all()

            leaderboard = []
            for i, row in enumerate(rows):
                total = row.wins + row.losses
                win_rate = round(row.wins / total * 100, 1) if total > 0 else 0.0
                leaderboard.append({
                    "rank": i + 1,
                    "session_id": row.session_id,
                    "rating": round(row.rating, 1),
                    "wins": row.wins,
                    "losses": row.losses,
                    "win_rate": win_rate,
                    "win_streak": row.win_streak,
                })

            return leaderboard
        finally:
            db.close()

    # ----- 플레이어 아레나 통계 -----

    def get_player_arena_stats(self, session_id: str) -> Optional[dict]:
        """
        플레이어 아레나 통계 + 순위

        Returns:
            dict: {rating, wins, losses, win_rate, win_streak, rank, total_players}
        """
        db = self._get_db()
        try:
            row = db.query(ArenaRegistration).filter(
                ArenaRegistration.session_id == session_id
            ).first()

            if row is None:
                return None

            # 순위 계산 (자기보다 레이팅 높은 사람 수 + 1)
            rank = db.query(func.count(ArenaRegistration.id)).filter(
                ArenaRegistration.rating > row.rating
            ).scalar() + 1

            total_players = db.query(func.count(ArenaRegistration.id)).scalar()

            total = row.wins + row.losses
            win_rate = round(row.wins / total * 100, 1) if total > 0 else 0.0

            return {
                "session_id": session_id,
                "rating": round(row.rating, 1),
                "wins": row.wins,
                "losses": row.losses,
                "win_rate": win_rate,
                "win_streak": row.win_streak,
                "rank": rank,
                "total_players": total_players,
                "defense_party": row.defense_party_json,
            }
        finally:
            db.close()

    # ----- 최근 배틀 기록 -----

    def get_recent_battles(self, session_id: str, limit: int = 10) -> list:
        """
        최근 PvP 배틀 기록

        Returns:
            list: [{id, opponent_id, result, rating_change, gold_reward, bonus_reward, created_at}, ...]
        """
        db = self._get_db()
        try:
            rows = db.query(PvPBattleLog).filter(
                (PvPBattleLog.attacker_id == session_id) |
                (PvPBattleLog.defender_id == session_id)
            ).order_by(desc(PvPBattleLog.created_at)).limit(limit).all()

            history = []
            for row in rows:
                is_attacker = row.attacker_id == session_id
                opponent_id = row.defender_id if is_attacker else row.attacker_id
                won = row.winner_id == session_id
                rating_change = row.attacker_rating_change if is_attacker else row.defender_rating_change

                history.append({
                    "id": row.id,
                    "opponent_id": opponent_id,
                    "result": "WIN" if won else "LOSE",
                    "rating_change": rating_change,
                    "gold_reward": row.gold_reward if won else CONSOLATION_GOLD,
                    "bonus_reward": row.bonus_reward if won else None,
                    "created_at": row.created_at.isoformat() if row.created_at else "",
                })

            return history
        finally:
            db.close()

    # ----- 전체 PvP 배틀 플로우 -----

    def do_pvp_battle(self, session_id: str, attacker_party: list,
                      player_gold_callback=None) -> dict:
        """
        PvP 배틀 전체 플로우:
        1. 매치메이킹
        2. 배틀 실행
        3. 레이팅 업데이트
        4. 보상 계산
        5. 로그 저장

        Args:
            session_id: 공격자 세션 ID
            attacker_party: 공격 파티 몬스터 dict 리스트
            player_gold_callback: 골드 지급 콜백 (session_id, gold) -> None

        Returns:
            dict: 전체 배틀 결과
        """
        if not attacker_party:
            return {"error": "공격 파티가 비어있습니다."}

        # 아레나 등록 여부 확인
        stats = self.get_player_arena_stats(session_id)
        if stats is None:
            return {"error": "아레나에 등록되지 않았습니다. 먼저 방어 파티를 등록해주세요."}

        player_rating = stats["rating"]

        # 매치메이킹
        opponent = self.find_opponent(session_id, player_rating)
        if opponent is None:
            return {"error": "대전 상대를 찾을 수 없습니다. 다른 플레이어가 아레나에 등록할 때까지 기다려주세요."}

        defender_party = opponent["defense_party"]
        defender_id = opponent["session_id"]

        # 배틀 실행
        battle_result = self.execute_pvp_battle(attacker_party, defender_party)

        is_attacker_win = battle_result["winner"] == "attacker"
        winner_id = session_id if is_attacker_win else defender_id
        loser_id = defender_id if is_attacker_win else session_id

        # 레이팅 업데이트
        rating_result = self.update_ratings(winner_id, loser_id)

        # 직전 상대 기록
        self.last_opponent[session_id] = defender_id

        # 보상 계산
        if is_attacker_win:
            reward = calculate_pvp_reward(
                player_rating, opponent["rating"],
                rating_result.get("winner_streak", 1)
            )
            gold_earned = reward["gold"]
            bonus_item = reward.get("bonus_item")
        else:
            reward = {"gold": CONSOLATION_GOLD, "base_gold": CONSOLATION_GOLD,
                      "bonus_gold": 0, "bonus_item": None, "streak": 0}
            gold_earned = CONSOLATION_GOLD
            bonus_item = None

        # 배틀 로그 저장
        atk_change = rating_result.get("winner_change", 0) if is_attacker_win else rating_result.get("loser_change", 0)
        def_change = rating_result.get("loser_change", 0) if is_attacker_win else rating_result.get("winner_change", 0)

        self.save_battle_log(
            attacker_id=session_id,
            defender_id=defender_id,
            winner_id=winner_id,
            atk_rating_change=atk_change,
            def_rating_change=def_change,
            battle_log=battle_result.get("rounds", []),
            gold_reward=gold_earned,
            bonus_reward=bonus_item,
        )

        # 업데이트된 통계 가져오기
        updated_stats = self.get_player_arena_stats(session_id)

        return {
            "result": "WIN" if is_attacker_win else "LOSE",
            "opponent": {
                "session_id": defender_id,
                "rating": opponent["rating"],
                "party": defender_party,
            },
            "battle": {
                "rounds": battle_result.get("rounds", []),
                "attacker_remaining": battle_result.get("attacker_remaining", 0),
                "defender_remaining": battle_result.get("defender_remaining", 0),
            },
            "rating_change": atk_change,
            "reward": reward,
            "gold_earned": gold_earned,
            "bonus_item": bonus_item,
            "stats": updated_stats,
        }
