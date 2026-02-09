"""
BarcodeQuest DB 모델
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON
from database import Base


class PlayerModel(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    gold = Column(Integer, default=1000)
    energy = Column(Integer, default=100)
    max_energy = Column(Integer, default=100)
    total_scans = Column(Integer, default=0)
    total_battles = Column(Integer, default=0)
    total_wins = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class MonsterModel(Base):
    __tablename__ = "monsters"

    id = Column(Integer, primary_key=True, index=True)
    monster_id = Column(String(50), unique=True, index=True)
    player_id = Column(Integer, nullable=False)
    name = Column(String(100))
    barcode = Column(String(13))
    primary_type = Column(String(20))
    secondary_type = Column(String(20))
    rarity = Column(String(20))
    level = Column(Integer, default=1)
    stats = Column(JSON)
    body_shape = Column(String(20))
    color = Column(String(20))
    accessory = Column(String(20))
    special_trait = Column(String(50))
    location = Column(String(10), default="party")  # party / inventory
    discovered_at = Column(DateTime, default=datetime.utcnow)


class BattleLog(Base):
    __tablename__ = "battle_logs"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, nullable=False)
    player_monster_id = Column(String(50))
    opponent_monster_id = Column(String(50))
    result = Column(String(10))  # win / lose
    exp_gained = Column(Integer, default=0)
    gold_gained = Column(Integer, default=0)
    battle_at = Column(DateTime, default=datetime.utcnow)
