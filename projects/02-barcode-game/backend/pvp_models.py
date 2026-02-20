"""
BarcodeQuest PvP Arena DB 모델

아레나 등록, PvP 배틀 로그를 위한 SQLAlchemy 모델
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Text
from database import Base


class ArenaRegistration(Base):
    """
    아레나 등록 정보 (세션당 1행)
    defense_party_json: 방어 파티 몬스터 3마리 dict 리스트
    """
    __tablename__ = "arena_registrations"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    defense_party_json = Column(JSON, default=list)
    rating = Column(Float, default=1000.0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    win_streak = Column(Integer, default=0)
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_battle_at = Column(DateTime, nullable=True)


class PvPBattleLog(Base):
    """
    PvP 배틀 기록
    """
    __tablename__ = "pvp_battle_logs"

    id = Column(Integer, primary_key=True, index=True)
    attacker_id = Column(String(100), nullable=False, index=True)
    defender_id = Column(String(100), nullable=False, index=True)
    winner_id = Column(String(100), nullable=False)
    attacker_rating_change = Column(Float, default=0.0)
    defender_rating_change = Column(Float, default=0.0)
    battle_log_json = Column(JSON, default=list)
    gold_reward = Column(Integer, default=0)
    bonus_reward = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
