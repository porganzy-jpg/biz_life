"""
BarcodeQuest DB 모델

v2.1 - SQLite persistence for full game state
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, Text
from database import Base


# === Legacy models (kept for backwards compatibility) ===

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


# ==========================================================
#  v2.1 Game State Persistence Models
#
#  These models store the full in-memory game state so that
#  player progress survives server restarts.  Complex nested
#  data (party monsters, items, bus layout ...) is kept as
#  JSON columns for simplicity.
# ==========================================================

class PlayerState(Base):
    """
    Persisted Player object state.
    One row per session_id.
    """
    __tablename__ = "player_states"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False, default="Trainer")
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    gold = Column(Integer, default=1000)
    energy = Column(Integer, default=100)
    max_energy = Column(Integer, default=100)
    total_scans = Column(Integer, default=0)
    total_battles = Column(Integer, default=0)
    total_wins = Column(Integer, default=0)
    # party and inventory are lists of monster dicts
    party_data = Column(JSON, default=list)
    inventory_data = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MonsterCollectionState(Base):
    """
    Persisted MonsterCollection state.
    collection_data = { monster_id: monster_dict, ... }
    discovery_log   = [ {monster_id, name, rarity, timestamp}, ... ]
    """
    __tablename__ = "monster_collections"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    collection_data = Column(JSON, default=dict)
    discovery_log = Column(JSON, default=list)


class InventoryStateModel(Base):
    """
    Persisted ItemInventory state.
    items_data = { item_id: count, ... }
    """
    __tablename__ = "inventory_states"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    items_data = Column(JSON, default=dict)


class ScannedBarcode(Base):
    """
    Individual scanned barcodes per player.
    Stored as individual rows for easy querying.
    """
    __tablename__ = "scanned_barcodes"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), nullable=False, index=True)
    barcode = Column(String(13), nullable=False)
    scanned_at = Column(DateTime, default=datetime.utcnow)


class ExpeditionStateModel(Base):
    """
    Persisted active expedition (one per session).
    expedition_data stores the ActiveExpedition fields as JSON.
    """
    __tablename__ = "expedition_states"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    expedition_data = Column(JSON, nullable=True)


class DailyQuestStateModel(Base):
    """
    Persisted daily quest progress for a player.
    quest_data = { "date": "YYYY-MM-DD", "quests": { qid: {...}, ... } }
    """
    __tablename__ = "daily_quest_states"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    quest_data = Column(JSON, default=dict)


class BusStateModel(Base):
    """
    Persisted bus system state.
    bus_data stores the full bus dict (floors, slots, monsters, timers).
    """
    __tablename__ = "bus_states"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    bus_data = Column(JSON, default=dict)
