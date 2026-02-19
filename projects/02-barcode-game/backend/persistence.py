"""
BarcodeQuest Persistence Layer

Save / load game state objects to/from SQLite via SQLAlchemy.
Game-engine classes (Player, MonsterCollection, ItemInventory, etc.)
are NOT modified.  We serialize their public attributes into JSON-friendly
DB rows and reconstruct them on load.
"""
from datetime import datetime
from typing import Optional, Set

from sqlalchemy.orm import Session as DBSession

from database import SessionLocal
from models import (
    PlayerState,
    MonsterCollectionState,
    InventoryStateModel,
    ScannedBarcode,
    ExpeditionStateModel,
    DailyQuestStateModel,
    BusStateModel,
)

# Re-import game-engine types so callers of this module don't need to
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "game-engine"))

from player import Player
from collection import MonsterCollection
from item_system import ItemInventory
from expedition_system import ExpeditionSystem, ActiveExpedition
from daily_quest_system import DailyQuestSystem, QuestProgress
from bus_system import BusSystem


# =====================================================
#  Helpers
# =====================================================

def _get_db() -> DBSession:
    """Return a new DB session (caller must close)."""
    return SessionLocal()


# =====================================================
#  Player  <-->  DB
# =====================================================

def save_player(session_id: str, player: Player) -> None:
    db = _get_db()
    try:
        row = db.query(PlayerState).filter(PlayerState.session_id == session_id).first()
        if row is None:
            row = PlayerState(session_id=session_id)
            db.add(row)

        row.name = player.name
        row.level = player.level
        row.exp = player.exp
        row.gold = player.gold
        row.energy = player.energy
        row.max_energy = player.max_energy
        row.total_scans = player.total_scans
        row.total_battles = player.total_battles
        row.total_wins = player.total_wins
        row.party_data = player.party          # list[dict] -> JSON
        row.inventory_data = player.inventory  # list[dict] -> JSON
        row.last_active = datetime.utcnow()
        db.commit()
    finally:
        db.close()


def load_player(session_id: str) -> Optional[Player]:
    """Load a Player from DB.  Returns None if not found."""
    db = _get_db()
    try:
        row = db.query(PlayerState).filter(PlayerState.session_id == session_id).first()
        if row is None:
            return None

        player = Player(name=row.name, player_id=session_id)
        player.level = row.level
        player.exp = row.exp
        player.gold = row.gold
        player.energy = row.energy
        player.max_energy = row.max_energy
        player.total_scans = row.total_scans
        player.total_battles = row.total_battles
        player.total_wins = row.total_wins
        player.party = row.party_data if row.party_data else []
        player.inventory = row.inventory_data if row.inventory_data else []
        player.created_at = row.created_at.isoformat() if row.created_at else datetime.utcnow().isoformat()
        return player
    finally:
        db.close()


# =====================================================
#  MonsterCollection  <-->  DB
# =====================================================

def save_collection(session_id: str, collection: MonsterCollection) -> None:
    db = _get_db()
    try:
        row = db.query(MonsterCollectionState).filter(
            MonsterCollectionState.session_id == session_id
        ).first()
        if row is None:
            row = MonsterCollectionState(session_id=session_id)
            db.add(row)

        row.collection_data = collection.collection    # dict[str, dict]
        row.discovery_log = collection.discovery_log   # list[dict]
        db.commit()
    finally:
        db.close()


def load_collection(session_id: str) -> Optional[MonsterCollection]:
    db = _get_db()
    try:
        row = db.query(MonsterCollectionState).filter(
            MonsterCollectionState.session_id == session_id
        ).first()
        if row is None:
            return None

        coll = MonsterCollection()
        coll.collection = row.collection_data if row.collection_data else {}
        coll.discovery_log = row.discovery_log if row.discovery_log else []
        return coll
    finally:
        db.close()


# =====================================================
#  ItemInventory  <-->  DB
# =====================================================

def save_inventory(session_id: str, inventory: ItemInventory) -> None:
    db = _get_db()
    try:
        row = db.query(InventoryStateModel).filter(
            InventoryStateModel.session_id == session_id
        ).first()
        if row is None:
            row = InventoryStateModel(session_id=session_id)
            db.add(row)

        row.items_data = inventory.items  # dict[str, int]
        db.commit()
    finally:
        db.close()


def load_inventory(session_id: str) -> Optional[ItemInventory]:
    db = _get_db()
    try:
        row = db.query(InventoryStateModel).filter(
            InventoryStateModel.session_id == session_id
        ).first()
        if row is None:
            return None

        inv = ItemInventory()
        inv.items = row.items_data if row.items_data else {}
        return inv
    finally:
        db.close()


# =====================================================
#  Scanned Barcodes  <-->  DB
# =====================================================

def save_scanned_barcode(session_id: str, barcode: str) -> None:
    """Insert one scanned barcode record."""
    db = _get_db()
    try:
        row = ScannedBarcode(session_id=session_id, barcode=barcode)
        db.add(row)
        db.commit()
    finally:
        db.close()


def load_scanned_barcodes(session_id: str) -> Set[str]:
    """Load the set of barcodes already scanned by this session."""
    db = _get_db()
    try:
        rows = db.query(ScannedBarcode.barcode).filter(
            ScannedBarcode.session_id == session_id
        ).all()
        return {r[0] for r in rows}
    finally:
        db.close()


# =====================================================
#  Expedition System  <-->  DB
# =====================================================

def save_expedition(session_id: str, expedition_system: ExpeditionSystem) -> None:
    """Persist the active expedition for a session (if any)."""
    db = _get_db()
    try:
        row = db.query(ExpeditionStateModel).filter(
            ExpeditionStateModel.session_id == session_id
        ).first()

        active = expedition_system.active_expeditions.get(session_id)

        if active is None:
            # No active expedition - remove DB row if exists
            if row is not None:
                db.delete(row)
        else:
            if row is None:
                row = ExpeditionStateModel(session_id=session_id)
                db.add(row)
            row.expedition_data = {
                "zone": active.zone,
                "zone_name": active.zone_name,
                "zone_emoji": active.zone_emoji,
                "start_time": active.start_time,
                "duration_seconds": active.duration_seconds,
                "party_ids": active.party_ids,
                "party_names": active.party_names,
                "party_types": active.party_types,
            }
        db.commit()
    finally:
        db.close()


def load_expedition_into(session_id: str, expedition_system: ExpeditionSystem) -> None:
    """Load a persisted expedition into the in-memory ExpeditionSystem."""
    db = _get_db()
    try:
        row = db.query(ExpeditionStateModel).filter(
            ExpeditionStateModel.session_id == session_id
        ).first()
        if row is None or row.expedition_data is None:
            return

        d = row.expedition_data
        active = ActiveExpedition(
            zone=d["zone"],
            zone_name=d["zone_name"],
            zone_emoji=d["zone_emoji"],
            start_time=d["start_time"],
            duration_seconds=d["duration_seconds"],
            party_ids=d.get("party_ids", []),
            party_names=d.get("party_names", []),
            party_types=d.get("party_types", []),
        )
        expedition_system.active_expeditions[session_id] = active
    finally:
        db.close()


# =====================================================
#  Daily Quest System  <-->  DB
# =====================================================

def save_daily_quests(session_id: str, quest_system: DailyQuestSystem) -> None:
    """Persist daily quest progress."""
    db = _get_db()
    try:
        row = db.query(DailyQuestStateModel).filter(
            DailyQuestStateModel.session_id == session_id
        ).first()

        pq = quest_system.player_quests.get(session_id)
        if pq is None:
            return

        if row is None:
            row = DailyQuestStateModel(session_id=session_id)
            db.add(row)

        # Serialize QuestProgress objects into plain dicts
        serialized_quests = {}
        for qid, qp in pq.get("quests", {}).items():
            serialized_quests[qid] = {
                "quest_id": qp.quest_id,
                "title": qp.title,
                "description": qp.description,
                "emoji": qp.emoji,
                "category": qp.category,
                "current": qp.current,
                "target": qp.target,
                "completed": qp.completed,
                "claimed": qp.claimed,
                "reward_gold": qp.reward_gold,
                "reward_exp": qp.reward_exp,
                "reward_item": qp.reward_item,
            }

        row.quest_data = {
            "date": pq.get("date", ""),
            "quests": serialized_quests,
        }
        db.commit()
    finally:
        db.close()


def load_daily_quests_into(session_id: str, quest_system: DailyQuestSystem) -> None:
    """Load persisted daily quest state into the in-memory DailyQuestSystem."""
    db = _get_db()
    try:
        row = db.query(DailyQuestStateModel).filter(
            DailyQuestStateModel.session_id == session_id
        ).first()
        if row is None or row.quest_data is None:
            return

        data = row.quest_data
        date_key = data.get("date", "")
        quests_raw = data.get("quests", {})

        # Reconstruct QuestProgress objects
        quests = {}
        for qid, qd in quests_raw.items():
            qp = QuestProgress(
                quest_id=qd["quest_id"],
                title=qd["title"],
                description=qd["description"],
                emoji=qd["emoji"],
                category=qd["category"],
                current=qd.get("current", 0),
                target=qd.get("target", 1),
                completed=qd.get("completed", False),
                claimed=qd.get("claimed", False),
                reward_gold=qd.get("reward_gold", 0),
                reward_exp=qd.get("reward_exp", 0),
                reward_item=qd.get("reward_item"),
            )
            quests[qid] = qp

        quest_system.player_quests[session_id] = {
            "date": date_key,
            "quests": quests,
        }
    finally:
        db.close()


# =====================================================
#  Bus System  <-->  DB
# =====================================================

def save_bus(session_id: str, bus_system: BusSystem) -> None:
    """Persist bus state for a session."""
    db = _get_db()
    try:
        row = db.query(BusStateModel).filter(
            BusStateModel.session_id == session_id
        ).first()

        bus_data = bus_system.buses.get(session_id)
        if bus_data is None:
            return

        if row is None:
            row = BusStateModel(session_id=session_id)
            db.add(row)

        # The bus dict contains int keys for floors. JSON requires string keys.
        # Convert floor int keys to strings for safe serialization.
        serializable = {
            "max_floor": bus_data["max_floor"],
            "last_collect_time": bus_data["last_collect_time"],
            "created_at": bus_data.get("created_at", 0),
            "floors": {},
        }
        for floor_num, floor_data in bus_data["floors"].items():
            serializable["floors"][str(floor_num)] = floor_data

        row.bus_data = serializable
        db.commit()
    finally:
        db.close()


def load_bus_into(session_id: str, bus_system: BusSystem) -> None:
    """Load persisted bus state into the in-memory BusSystem."""
    db = _get_db()
    try:
        row = db.query(BusStateModel).filter(
            BusStateModel.session_id == session_id
        ).first()
        if row is None or row.bus_data is None:
            return

        data = row.bus_data

        # Reconstruct with int keys for floors
        floors = {}
        for floor_key, floor_data in data.get("floors", {}).items():
            floors[int(floor_key)] = floor_data

        bus_system.buses[session_id] = {
            "max_floor": data.get("max_floor", 1),
            "floors": floors,
            "last_collect_time": data.get("last_collect_time", 0),
            "created_at": data.get("created_at", 0),
        }
    finally:
        db.close()


# =====================================================
#  Convenience: load ALL state for a session at once
# =====================================================

def load_all_state(session_id: str, expedition_system: ExpeditionSystem,
                   daily_quest_system: DailyQuestSystem,
                   bus_system: BusSystem):
    """
    Load everything for a session.  Returns (player, collection, inventory, scanned_set)
    or (None, None, None, None) if the session has no saved state.

    Side-effects: populates expedition_system, daily_quest_system, bus_system
    in-memory dicts for this session.
    """
    player = load_player(session_id)
    if player is None:
        return None, None, None, None

    collection = load_collection(session_id) or MonsterCollection()
    inventory = load_inventory(session_id) or ItemInventory()
    scanned = load_scanned_barcodes(session_id)

    # Load sub-system states if not already in memory
    if session_id not in expedition_system.active_expeditions:
        load_expedition_into(session_id, expedition_system)

    if session_id not in daily_quest_system.player_quests:
        load_daily_quests_into(session_id, daily_quest_system)

    if session_id not in bus_system.buses:
        load_bus_into(session_id, bus_system)

    return player, collection, inventory, scanned


def save_all_state(session_id: str, player: Player, collection: MonsterCollection,
                   inventory: ItemInventory,
                   expedition_system: ExpeditionSystem,
                   daily_quest_system: DailyQuestSystem,
                   bus_system: BusSystem) -> None:
    """Save everything for a session in one call."""
    save_player(session_id, player)
    save_collection(session_id, collection)
    save_inventory(session_id, inventory)
    save_expedition(session_id, expedition_system)
    save_daily_quests(session_id, daily_quest_system)
    save_bus(session_id, bus_system)
