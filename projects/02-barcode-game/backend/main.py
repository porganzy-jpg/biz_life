"""
BarcodeQuest - FastAPI 게임 서버 v2.3

v2.0 시스템:
  - 방치형 탐험 (ExpeditionSystem)
  - 아이템 인벤토리 (ItemInventory)
  - 크리처 진화 (EvolutionSystem)
  - 일일 퀘스트 (DailyQuestSystem)

v2.1 변경:
  - SQLite-backed persistence (인메모리 dict → DB 저장)
  - 서버 재시작 후에도 플레이어 진행도 유지

v2.2 변경:
  - PvP 아레나 시스템 (ELO 매치메이킹, 글로벌 리더보드)

v2.3 변경:
  - 길드 시스템 (길드 생성/가입/탈퇴, 보스전, 랭킹)
  - 몬스터 거래소 (마켓플레이스 등록/구매/취소, 거래내역)
"""
import sys
import os
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "game-engine"))
MOCKUPS_DIR = os.path.join(os.path.dirname(__file__), "..", "mockups")

from pathlib import Path
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import uvicorn

from database import init_db
from barcode_monster_generator import BarcodeMonsterGenerator
from battle_system import BattleSystem, BattleMonster, BattleAction
from collection import MonsterCollection
from player import Player
from expedition_system import ExpeditionSystem
from item_system import ItemInventory, get_shop_listing, ITEM_DATABASE
from evolution_system import EvolutionSystem
from daily_quest_system import DailyQuestSystem
from bus_system import BusSystem, calculate_affinity, get_room_suggestion, ROOM_DEFINITIONS

import persistence
from pvp_system import ArenaManager
from guild_system import GuildManager
from trading_system import TradeManager

app = FastAPI(title="BarcodeQuest Game Server v2.3")

# 게임 엔진 인스턴스 (stateless singletons)
generator = BarcodeMonsterGenerator()
battle_system = BattleSystem()
evolution_system = EvolutionSystem()

# PvP 아레나 매니저
arena_manager = ArenaManager()

# 길드 & 거래 매니저
guild_manager = GuildManager()
trade_manager = TradeManager()

# Sub-systems that hold per-session state in memory (loaded from DB on access)
expedition_system = ExpeditionSystem()
daily_quest_system = DailyQuestSystem()
bus_system = BusSystem()

# In-memory caches (populated lazily from DB, written back after mutations)
players = {}            # session_id -> Player
collections = {}        # session_id -> MonsterCollection
inventories = {}        # session_id -> ItemInventory
scanned_barcodes = {}   # session_id -> set[str]


# =====================================================
#  Session helpers  (load from DB on first access)
# =====================================================

def get_or_create_player(session_id: str = "default") -> tuple:
    """
    Return (Player, MonsterCollection) for the given session.
    On first access the state is loaded from the database;
    if no saved state exists, fresh objects are created and persisted.
    """
    if session_id not in players:
        # Try loading from DB
        player, collection, inventory, scanned = persistence.load_all_state(
            session_id, expedition_system, daily_quest_system, bus_system
        )
        if player is not None:
            players[session_id] = player
            collections[session_id] = collection
            inventories[session_id] = inventory
            scanned_barcodes[session_id] = scanned
        else:
            # Brand-new session
            players[session_id] = Player(name="Trainer", player_id=session_id)
            collections[session_id] = MonsterCollection()
            inventories[session_id] = ItemInventory()
            scanned_barcodes[session_id] = set()
            # Persist the new state immediately
            persistence.save_player(session_id, players[session_id])
            persistence.save_collection(session_id, collections[session_id])
            persistence.save_inventory(session_id, inventories[session_id])

    return players[session_id], collections[session_id]


def get_inventory(session_id: str = "default") -> ItemInventory:
    if session_id not in inventories:
        inv = persistence.load_inventory(session_id)
        if inv is not None:
            inventories[session_id] = inv
        else:
            inventories[session_id] = ItemInventory()
    return inventories[session_id]


# =====================================================
#  Startup
# =====================================================

@app.on_event("startup")
async def startup():
    import pvp_models  # noqa: F401  (테이블 생성을 위해 모델 import)
    import guild_system  # noqa: F401  (Guild, GuildMember, GuildBossLog 테이블 생성)
    import trading_system  # noqa: F401  (TradeListing, TradeHistory 테이블 생성)
    init_db()


# =====================================================
#  Pages & Health
# =====================================================

@app.get("/", response_class=HTMLResponse)
async def game_client():
    html_path = Path(MOCKUPS_DIR) / "index.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return "<h1>Game file not found</h1>"


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "BarcodeQuest"}


# =====================================================
#  Player info
# =====================================================

@app.get("/api/player")
async def get_player(session: str = "default"):
    player, collection = get_or_create_player(session)
    return {
        "player": player.to_dict(),
        "collection_stats": collection.get_completion_stats(),
    }


# =====================================================
#  Barcode Scan
# =====================================================

@app.post("/api/scan")
async def scan_barcode(
    barcode: str = Query(..., min_length=13, max_length=13),
    lat: float = Query(37.5665),
    lon: float = Query(126.9780),
    hour: int = Query(12),
    session: str = Query("default"),
):
    """바코드 스캔 -> 몬스터 생성"""
    player, collection = get_or_create_player(session)

    # 중복 바코드 체크
    if session not in scanned_barcodes:
        scanned_barcodes[session] = persistence.load_scanned_barcodes(session)
    if barcode in scanned_barcodes[session]:
        return {"error": "duplicate", "message": "이미 스캔한 바코드입니다! 다른 바코드를 스캔해보세요.", "barcode": barcode}

    if not player.use_energy(10):
        return {"error": "에너지 부족! 잠시 후 다시 시도하세요.", "energy": player.energy}

    player.total_scans += 1
    scanned_barcodes[session].add(barcode)

    monster = generator.generate_monster(barcode, lat, lon, hour)
    monster_dict = monster.to_dict()

    # 도감 등록
    coll_result = collection.add_monster(monster_dict)

    # 플레이어 인벤토리에 추가
    add_result = player.add_monster(monster_dict)

    # 일일 퀘스트 진행도 업데이트
    quest_updates = daily_quest_system.update_progress(session, "scan")
    if coll_result.get("is_new"):
        quest_updates += daily_quest_system.update_progress(session, "scan_new")
        quest_updates += daily_quest_system.update_progress(session, "collect")

    # 버스 방 추천
    bus_suggestion = get_room_suggestion(monster_dict)

    # --- DB Persist ---
    persistence.save_player(session, player)
    persistence.save_collection(session, collection)
    persistence.save_scanned_barcode(session, barcode)
    persistence.save_daily_quests(session, daily_quest_system)

    return {
        "monster": monster_dict,
        "collection": coll_result,
        "inventory": add_result,
        "player": player.to_dict(),
        "quest_updates": quest_updates,
        "bus_suggestion": bus_suggestion,
    }


# =====================================================
#  Battle
# =====================================================

@app.post("/api/battle")
async def start_battle(
    monster_idx: int = Query(0, description="파티 몬스터 인덱스"),
    session: str = Query("default"),
):
    """PvE 배틀 시작"""
    player, collection = get_or_create_player(session)

    if not player.party:
        return {"error": "파티에 몬스터가 없습니다! 먼저 바코드를 스캔하세요."}

    if monster_idx >= len(player.party):
        monster_idx = 0

    player_monster_data = player.party[monster_idx]

    # 랜덤 상대 생성 (바코드 랜덤)
    random_barcode = f"880{random.randint(1000, 9999)}{random.randint(10000, 99999)}"
    digits = [int(d) for d in random_barcode]
    check = (10 - sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits)) % 10) % 10
    random_barcode += str(check)
    opponent = generator.generate_monster(random_barcode)
    opponent_dict = opponent.to_dict()

    # 배틀 실행 (자동 최대 10턴)
    p1 = BattleMonster(player_monster_data)
    p2 = BattleMonster(opponent_dict)

    battle_log = []
    for turn in range(10):
        if not p1.is_alive or not p2.is_alive:
            break

        p1_action = BattleAction(p1.id, random.choice(["attack", "special"]))
        p2_action = BattleAction(p2.id, random.choice(["attack", "special", "defend"]))

        results = battle_system.execute_turn(p1, p1_action, p2, p2_action)
        for r in results:
            battle_log.append({
                "attacker": r.attacker_name,
                "defender": r.defender_name,
                "action": r.action,
                "damage": r.damage,
                "is_critical": r.is_critical,
                "effectiveness": r.is_effective,
                "attacker_hp": r.attacker_hp_remaining,
                "defender_hp": r.defender_hp_remaining,
                "message": r.message,
            })

    # 결과
    winner = p1 if p1.is_alive else p2
    is_player_win = p1.is_alive

    player.total_battles += 1
    rewards = {"exp": 0, "gold": 0}

    # 일일 퀘스트: 배틀
    quest_updates = daily_quest_system.update_progress(session, "battle")

    monster_level_result = None
    affinity_result = None
    affinity_heal_result = None
    if is_player_win:
        player.total_wins += 1
        rewards = battle_system.get_battle_reward(p1, p2)
        exp_result = player.gain_exp(rewards["exp"])
        player.gain_gold(rewards["gold"])
        # 참전 몬스터도 경험치 획득
        monster_exp = 10 + p2.level * 3
        monster_level_result = player.gain_monster_exp(player_monster_data, monster_exp)
        rewards["monster_exp"] = monster_exp
        quest_updates += daily_quest_system.update_progress(session, "battle_win")
        # Affinity gain: 3 AP per win
        affinity_result = player.gain_affinity(monster_idx, 3, source="party")
        # Post-battle passive heal (affinity level >= 7)
        affinity_heal_result = player.apply_post_battle_affinity_heal(monster_idx, source="party")
    else:
        player.gain_exp(5)
        player.gain_monster_exp(player_monster_data, 3)
        # Affinity gain: 1 AP per loss
        affinity_result = player.gain_affinity(monster_idx, 1, source="party")

    # --- DB Persist ---
    persistence.save_player(session, player)
    persistence.save_daily_quests(session, daily_quest_system)

    return {
        "result": "WIN" if is_player_win else "LOSE",
        "player_monster": {"name": player_monster_data["name"], "level": player_monster_data.get("level", 1), "final_hp": p1.current_hp, "max_hp": p1.max_hp},
        "opponent": {"name": opponent_dict["name"], "rarity": opponent_dict["rarity"], "final_hp": p2.current_hp, "max_hp": p2.max_hp},
        "battle_log": battle_log,
        "rewards": rewards,
        "monster_level": monster_level_result,
        "affinity": affinity_result,
        "affinity_heal": affinity_heal_result,
        "player": player.to_dict(),
        "quest_updates": quest_updates,
    }


# =====================================================
#  Collection
# =====================================================

@app.get("/api/collection")
async def get_collection(session: str = "default", sort: str = "rarity"):
    player, collection = get_or_create_player(session)
    monsters = collection.get_collection_list(sort)
    return {
        "total": len(monsters),
        "stats": collection.get_completion_stats(),
        "rewards": collection.check_rewards(),
        "monsters": monsters[:50],
    }


# =====================================================
#  Monster Affinity / Bonding
# =====================================================

@app.get("/api/monster/{index}/affinity")
async def get_monster_affinity(
    index: int,
    source: str = Query("party", description="'party' 또는 'inventory'"),
    session: str = Query("default"),
):
    """몬스터 유대(친밀도) 상세 조회"""
    player, _ = get_or_create_player(session)

    monster_list = player.party if source == "party" else player.inventory
    if index < 0 or index >= len(monster_list):
        return {"error": "유효하지 않은 몬스터 인덱스입니다."}

    monster = monster_list[index]
    bonus = player.get_affinity_bonus(monster)

    return {
        "monster_name": monster.get("name", "Unknown"),
        "monster_index": index,
        "source": source,
        "affinity_level": bonus["affinity_level"],
        "affinity_exp": bonus["affinity_exp"],
        "exp_to_next_level": 100 - bonus["affinity_exp"] if bonus["affinity_level"] < 10 else 0,
        "max_level": 10,
        "stat_multiplier": bonus["multiplier"],
        "passive_heal": bonus["passive_heal"],
        "heal_pct": bonus["heal_pct"],
        "bonus_description": bonus["bonus_description"],
    }


# =====================================================
#  Energy Recovery
# =====================================================

@app.post("/api/recover")
async def recover_energy(session: str = "default"):
    player, _ = get_or_create_player(session)
    player.recover_energy(20)

    # --- DB Persist ---
    persistence.save_player(session, player)

    return {"energy": player.energy, "max_energy": player.max_energy}


# =====================================================
#  파티 관리 API
# =====================================================

@app.post("/api/party/swap")
async def swap_party_member(
    party_idx: int = Query(..., description="파티 슬롯 인덱스"),
    inventory_idx: int = Query(..., description="보관함 슬롯 인덱스"),
    session: str = Query("default"),
):
    """파티 <-> 보관함 몬스터 교체"""
    player, _ = get_or_create_player(session)
    result = player.swap_party_member(party_idx, inventory_idx)

    # --- DB Persist ---
    persistence.save_player(session, player)

    return {**result, "party": player.party, "inventory_size": len(player.inventory)}


@app.get("/api/party")
async def get_party(session: str = "default"):
    """파티 + 보관함 전체 조회"""
    player, _ = get_or_create_player(session)
    return {
        "party": player.party,
        "inventory": player.inventory,
        "party_max": player.MAX_PARTY_SIZE,
        "inventory_max": player.MAX_INVENTORY_SIZE,
    }


# =====================================================
#  신규 API: 탐험 시스템
# =====================================================

@app.get("/api/expedition/zones")
async def get_expedition_zones(session: str = "default"):
    """탐험 가능 지역 목록"""
    player, _ = get_or_create_player(session)
    zones = expedition_system.get_available_zones(player.level)
    current = expedition_system.check_expedition(session)
    return {"zones": zones, "active_expedition": current}


@app.post("/api/expedition/start")
async def start_expedition(
    zone_id: str = Query(..., description="탐험 지역 ID"),
    session: str = Query("default"),
):
    """탐험 시작"""
    player, _ = get_or_create_player(session)
    if not player.party:
        return {"error": "파티에 크리처가 없습니다!"}

    result = expedition_system.start_expedition(session, zone_id, player.party)

    if "error" not in result:
        daily_quest_system.update_progress(session, "expedition")
        # --- DB Persist ---
        persistence.save_expedition(session, expedition_system)
        persistence.save_daily_quests(session, daily_quest_system)

    return result


@app.get("/api/expedition/status")
async def expedition_status(session: str = "default"):
    """탐험 진행 상태 확인"""
    # Ensure expedition is loaded from DB
    get_or_create_player(session)
    status = expedition_system.check_expedition(session)
    if not status:
        return {"active": False, "message": "진행 중인 탐험이 없습니다."}
    return {"active": True, "expedition": status}


@app.post("/api/expedition/collect")
async def collect_expedition(session: str = "default"):
    """탐험 결과 수령"""
    player, _ = get_or_create_player(session)
    inv = get_inventory(session)

    result = expedition_system.collect_expedition(session)
    if not result:
        status = expedition_system.check_expedition(session)
        if status:
            return {"error": "탐험이 아직 진행 중입니다!", "expedition": status}
        return {"error": "수령할 탐험 결과가 없습니다."}

    # 보상 적용
    player.gain_gold(result.gold_earned)
    player.gain_exp(result.exp_earned)

    items_added = []
    for item in result.items_found:
        add_result = inv.add_item(item["id"])
        items_added.append(add_result)

    # 퀘스트 업데이트
    daily_quest_system.update_progress(session, "expedition_collect")

    # Affinity gain: 2 AP for all party monsters on expedition collect
    affinity_results = []
    for idx in range(len(player.party)):
        aff = player.gain_affinity(idx, 2, source="party")
        affinity_results.append(aff)

    # --- DB Persist ---
    persistence.save_player(session, player)
    persistence.save_inventory(session, inv)
    persistence.save_expedition(session, expedition_system)
    persistence.save_daily_quests(session, daily_quest_system)

    return {
        "result": {
            "zone_name": result.zone_name,
            "zone_emoji": result.zone_emoji,
            "gold_earned": result.gold_earned,
            "exp_earned": result.exp_earned,
            "items_found": result.items_found,
            "bonus_message": result.bonus_message,
            "party_used": result.party_used,
        },
        "items_added": items_added,
        "affinity_updates": affinity_results,
        "player": player.to_dict(),
    }


# =====================================================
#  신규 API: 아이템 시스템
# =====================================================

@app.get("/api/items")
async def get_items(session: str = "default"):
    """아이템 인벤토리 조회"""
    inv = get_inventory(session)
    return inv.to_dict()


@app.post("/api/items/use")
async def use_item(
    item_id: str = Query(...),
    monster_idx: int = Query(-1, description="대상 파티 크리처 인덱스 (-1=자신)"),
    session: str = Query("default"),
):
    """아이템 사용"""
    player, _ = get_or_create_player(session)
    inv = get_inventory(session)

    target_monster = None
    if monster_idx >= 0 and monster_idx < len(player.party):
        target_monster = player.party[monster_idx]

    result = inv.use_item(item_id, target_monster)
    if "error" in result:
        return result

    # 효과 적용
    if result.get("energy_value"):
        player.recover_energy(result["energy_value"])
        result["new_energy"] = player.energy
    elif result.get("energy_full"):
        player.energy = player.max_energy
        result["new_energy"] = player.energy
    elif result.get("exp_value") and target_monster:
        result["applied_to"] = target_monster.get("name", "Unknown")
    elif result.get("stat_value") and target_monster:
        stat = result["stat_name"]
        val = result["stat_value"]
        if isinstance(target_monster.get("stats"), dict):
            target_monster["stats"][stat] = target_monster["stats"].get(stat, 0) + val
        result["applied_to"] = target_monster.get("name", "Unknown")

    result["player"] = player.to_dict()

    # --- DB Persist ---
    persistence.save_player(session, player)
    persistence.save_inventory(session, inv)

    return result


# =====================================================
#  신규 API: 상점
# =====================================================

@app.get("/api/shop")
async def get_shop():
    """상점 아이템 목록"""
    return {"items": get_shop_listing()}


@app.post("/api/shop/buy")
async def buy_item(
    item_id: str = Query(...),
    count: int = Query(1, ge=1, le=10),
    session: str = Query("default"),
):
    """상점에서 아이템 구매"""
    player, _ = get_or_create_player(session)
    inv = get_inventory(session)

    # 가격 확인
    shop_listing = get_shop_listing()
    shop_item = next((s for s in shop_listing if s["item_id"] == item_id), None)
    if not shop_item:
        return {"error": "상점에 없는 아이템입니다."}

    total_price = shop_item["price"] * count
    if not player.spend_gold(total_price):
        return {"error": f"골드가 부족합니다! (필요: {total_price:,}G, 보유: {player.gold:,}G)"}

    add_result = inv.add_item(item_id, count)
    if "error" in add_result:
        player.gain_gold(total_price)  # 환불
        return add_result

    # --- DB Persist ---
    persistence.save_player(session, player)
    persistence.save_inventory(session, inv)

    return {
        "purchased": add_result,
        "spent_gold": total_price,
        "player": player.to_dict(),
    }


# =====================================================
#  신규 API: 진화 시스템
# =====================================================

@app.get("/api/evolve/preview")
async def evolve_preview(
    monster_idx: int = Query(0, description="파티 크리처 인덱스"),
    session: str = Query("default"),
):
    """진화 미리보기"""
    player, _ = get_or_create_player(session)
    if monster_idx >= len(player.party):
        return {"error": "유효하지 않은 크리처 인덱스입니다."}

    monster = player.party[monster_idx]
    inv = get_inventory(session)

    preview = evolution_system.get_evolution_preview(monster)
    requirements = evolution_system.check_evolution_requirements(
        monster, player.gold, inv
    )

    return {
        "preview": preview,
        "requirements": requirements,
    }


@app.post("/api/evolve")
async def evolve_monster(
    monster_idx: int = Query(0, description="파티 크리처 인덱스"),
    session: str = Query("default"),
):
    """크리처 진화 실행"""
    player, collection = get_or_create_player(session)
    inv = get_inventory(session)

    if monster_idx >= len(player.party):
        return {"error": "유효하지 않은 크리처 인덱스입니다."}

    monster = player.party[monster_idx]

    # 요구사항 확인
    check = evolution_system.check_evolution_requirements(monster, player.gold, inv)
    if not check["can_evolve"]:
        return {"error": "진화 조건을 충족하지 못했습니다.", "missing": check.get("missing", [])}

    # 비용 차감
    from evolution_system import EVOLUTION_COSTS
    costs = EVOLUTION_COSTS.get(monster.get("rarity", "Common"))
    player.spend_gold(costs["gold"])
    for mat_id, mat_count in costs["materials"]:
        inv.remove_item(mat_id, mat_count)

    # 진화 실행
    evolved = evolution_system.evolve_monster(monster, session)
    player.party[monster_idx] = evolved

    # 도감 업데이트
    collection.add_monster(evolved)

    # --- DB Persist ---
    persistence.save_player(session, player)
    persistence.save_collection(session, collection)
    persistence.save_inventory(session, inv)

    return {
        "evolved_monster": evolved,
        "cost_paid": {"gold": costs["gold"], "materials": costs["materials"]},
        "player": player.to_dict(),
        "message": f"축하합니다! {monster.get('name')}이(가) {evolved['name']}(으)로 진화했습니다!",
    }


# =====================================================
#  신규 API: 일일 퀘스트
# =====================================================

@app.get("/api/daily-quest")
async def get_daily_quests(session: str = "default"):
    """오늘의 일일 퀘스트 목록"""
    # Ensure session state is loaded
    get_or_create_player(session)
    quests = daily_quest_system.get_quests(session)
    summary = daily_quest_system.get_summary(session)

    # Persist (get_quests may have created new daily quests)
    persistence.save_daily_quests(session, daily_quest_system)

    return {"quests": quests, "summary": summary}


@app.post("/api/daily-quest/claim")
async def claim_quest_reward(
    quest_id: str = Query(...),
    session: str = Query("default"),
):
    """퀘스트 보상 수령"""
    player, _ = get_or_create_player(session)
    inv = get_inventory(session)

    reward = daily_quest_system.claim_reward(session, quest_id)
    if not reward:
        return {"error": "수령할 보상이 없습니다."}

    # 보상 적용
    if reward["gold"]:
        player.gain_gold(reward["gold"])
    if reward["exp"]:
        player.gain_exp(reward["exp"])
    if reward["item"]:
        inv.add_item(reward["item"])

    # --- DB Persist ---
    persistence.save_player(session, player)
    persistence.save_inventory(session, inv)
    persistence.save_daily_quests(session, daily_quest_system)

    return {
        "reward": reward,
        "player": player.to_dict(),
    }


# =====================================================
#  신규 API: 버스 시스템
# =====================================================

@app.get("/api/bus")
async def get_bus_state(session: str = "default"):
    """버스 전체 상태 조회"""
    # Ensure session state (including bus) is loaded from DB
    get_or_create_player(session)
    state = bus_system.get_bus_state(session)
    return state


@app.post("/api/bus/build")
async def build_bus_room(
    floor: int = Query(..., description="층 (1~3)"),
    slot: int = Query(..., description="슬롯 (0~2)"),
    room_type: str = Query(..., description="방 타입 ID"),
    session: str = Query("default"),
):
    """버스에 방 건설"""
    player, _ = get_or_create_player(session)
    result = bus_system.build_room(session, floor, slot, room_type, player.gold)
    if "error" in result:
        return result
    player.spend_gold(result["cost"])
    daily_quest_system.update_progress(session, "bus_build")

    # --- DB Persist ---
    persistence.save_player(session, player)
    persistence.save_bus(session, bus_system)
    persistence.save_daily_quests(session, daily_quest_system)

    return {**result, "player": player.to_dict()}


@app.post("/api/bus/assign")
async def assign_bus_monster(
    floor: int = Query(...),
    slot: int = Query(...),
    monster_source: str = Query(..., description="party 또는 inventory"),
    monster_idx: int = Query(..., description="몬스터 인덱스"),
    session: str = Query("default"),
):
    """버스 방에 몬스터 배치"""
    player, _ = get_or_create_player(session)

    if monster_source == "party":
        if monster_idx < 0 or monster_idx >= len(player.party):
            return {"error": "잘못된 파티 인덱스입니다."}
        monster = player.party[monster_idx]
    elif monster_source == "inventory":
        if monster_idx < 0 or monster_idx >= len(player.inventory):
            return {"error": "잘못된 보관함 인덱스입니다."}
        monster = player.inventory[monster_idx]
    else:
        return {"error": "monster_source는 'party' 또는 'inventory'여야 합니다."}

    result = bus_system.assign_monster(session, floor, slot, monster)
    if result.get("ok"):
        daily_quest_system.update_progress(session, "bus_assign")
        # --- DB Persist ---
        persistence.save_bus(session, bus_system)
        persistence.save_daily_quests(session, daily_quest_system)

    return result


@app.post("/api/bus/unassign")
async def unassign_bus_monster(
    floor: int = Query(...),
    slot: int = Query(...),
    session: str = Query("default"),
):
    """버스 방에서 몬스터 회수"""
    # Ensure bus is loaded
    get_or_create_player(session)
    result = bus_system.unassign_monster(session, floor, slot)

    if result.get("ok"):
        # --- DB Persist ---
        persistence.save_bus(session, bus_system)

    return result


@app.post("/api/bus/upgrade-floor")
async def upgrade_bus_floor(session: str = Query("default")):
    """버스 층 해금"""
    player, _ = get_or_create_player(session)
    result = bus_system.upgrade_floor(session, player.gold, player.level)
    if "error" in result:
        return result
    player.spend_gold(result["cost"])

    # --- DB Persist ---
    persistence.save_player(session, player)
    persistence.save_bus(session, bus_system)

    return {**result, "player": player.to_dict()}


@app.post("/api/bus/upgrade-room")
async def upgrade_bus_room(
    floor: int = Query(...),
    slot: int = Query(...),
    session: str = Query("default"),
):
    """버스 방 업그레이드"""
    player, _ = get_or_create_player(session)
    result = bus_system.upgrade_room(session, floor, slot, player.gold)
    if "error" in result:
        return result
    player.spend_gold(result["cost"])

    # --- DB Persist ---
    persistence.save_player(session, player)
    persistence.save_bus(session, bus_system)

    return {**result, "player": player.to_dict()}


@app.post("/api/bus/collect")
async def collect_bus_resources(session: str = Query("default")):
    """버스 자원 수령"""
    player, _ = get_or_create_player(session)
    result = bus_system.collect_all(session)
    if result.get("ok"):
        collected = result.get("collected", {})
        if collected.get("gold"):
            player.gain_gold(collected["gold"])
        if collected.get("exp"):
            player.gain_exp(collected["exp"])
        if collected.get("energy"):
            player.recover_energy(collected["energy"])
        if collected:
            daily_quest_system.update_progress(session, "bus_collect")
        result["player"] = player.to_dict()

        # --- DB Persist ---
        persistence.save_player(session, player)
        persistence.save_bus(session, bus_system)
        persistence.save_daily_quests(session, daily_quest_system)

    return result


# =====================================================
#  신규 API: PvP 아레나 시스템
# =====================================================

@app.post("/api/pvp/register")
async def pvp_register(
    session: str = Query("default"),
):
    """아레나 방어 파티 등록 (현재 파티 그대로 등록)"""
    player, _ = get_or_create_player(session)
    if not player.party:
        return {"error": "파티에 몬스터가 없습니다! 먼저 바코드를 스캔하세요."}
    result = arena_manager.register_for_arena(session, player.party[:3])
    return result


@app.post("/api/pvp/battle")
async def pvp_battle(
    session: str = Query("default"),
):
    """PvP 배틀 (매치메이킹 → 배틀 → 레이팅 업데이트)"""
    player, _ = get_or_create_player(session)
    if not player.party:
        return {"error": "파티에 몬스터가 없습니다!"}

    result = arena_manager.do_pvp_battle(session, player.party[:3])
    if "error" in result:
        return result

    # 골드 보상 지급
    gold = result.get("gold_earned", 0)
    player.gain_gold(gold)

    # 보너스 아이템 지급
    bonus_item = result.get("bonus_item")
    if bonus_item:
        inv = get_inventory(session)
        inv.add_item(bonus_item)
        persistence.save_inventory(session, inv)

    # --- DB Persist ---
    persistence.save_player(session, player)

    result["player"] = player.to_dict()
    return result


@app.get("/api/pvp/leaderboard")
async def pvp_leaderboard(
    limit: int = Query(50, ge=1, le=100),
):
    """글로벌 PvP 리더보드 (상위 N명)"""
    leaderboard = arena_manager.get_leaderboard(limit)
    return {"leaderboard": leaderboard, "total": len(leaderboard)}


@app.get("/api/pvp/stats")
async def pvp_stats(
    session: str = Query("default"),
):
    """내 아레나 통계"""
    stats = arena_manager.get_player_arena_stats(session)
    if stats is None:
        return {"registered": False, "message": "아레나에 등록되지 않았습니다."}
    return {"registered": True, "stats": stats}


@app.get("/api/pvp/history")
async def pvp_history(
    session: str = Query("default"),
    limit: int = Query(10, ge=1, le=50),
):
    """내 최근 PvP 배틀 기록"""
    history = arena_manager.get_recent_battles(session, limit)
    return {"history": history, "total": len(history)}


# =====================================================
#  신규 API: 길드 시스템
# =====================================================

@app.post("/api/guild/create")
async def guild_create(
    name: str = Query(..., min_length=2, max_length=20, description="길드 이름"),
    session: str = Query("default"),
):
    """길드 생성 (5000 골드)"""
    player, _ = get_or_create_player(session)
    result = guild_manager.create_guild(session, name, player.gold)
    if result.get("ok"):
        player.spend_gold(result["cost"])
        persistence.save_player(session, player)
        result["player"] = player.to_dict()
    return result


@app.post("/api/guild/join/{guild_id}")
async def guild_join(
    guild_id: int,
    session: str = Query("default"),
):
    """길드 가입"""
    get_or_create_player(session)
    result = guild_manager.join_guild(session, guild_id)
    return result


@app.post("/api/guild/leave")
async def guild_leave(
    session: str = Query("default"),
):
    """길드 탈퇴"""
    get_or_create_player(session)
    result = guild_manager.leave_guild(session)
    return result


@app.get("/api/guild/info")
async def guild_info(
    session: str = Query("default"),
):
    """내 길드 정보 조회"""
    get_or_create_player(session)
    result = guild_manager.get_guild_info(session)
    return result


@app.get("/api/guild/ranking")
async def guild_ranking(
    limit: int = Query(20, ge=1, le=50),
):
    """길드 랭킹"""
    ranking = guild_manager.guild_ranking(limit)
    return {"ranking": ranking, "total": len(ranking)}


@app.get("/api/guild/available")
async def guild_available(
    limit: int = Query(20, ge=1, le=50),
):
    """가입 가능한 길드 목록"""
    guilds = guild_manager.get_available_guilds(limit)
    return {"guilds": guilds}


@app.post("/api/guild/boss")
async def guild_boss(
    session: str = Query("default"),
):
    """길드 보스전"""
    player, _ = get_or_create_player(session)
    if not player.party:
        return {"error": "파티에 몬스터가 없습니다!"}

    result = guild_manager.guild_boss_battle(session, player.party[:3])
    if result.get("ok"):
        # Apply rewards to player
        rewards = result.get("rewards", {})
        if rewards.get("gold"):
            player.gain_gold(rewards["gold"])
        if rewards.get("exp"):
            player.gain_exp(rewards["exp"])
        persistence.save_player(session, player)
        result["player"] = player.to_dict()
    return result


# =====================================================
#  신규 API: 몬스터 거래소
# =====================================================

@app.post("/api/trade/list")
async def trade_list(
    monster_index: int = Query(..., description="몬스터 인덱스"),
    price: int = Query(..., ge=10, le=999999, description="판매 가격"),
    source: str = Query("inventory", description="'party' 또는 'inventory'"),
    session: str = Query("default"),
):
    """몬스터를 거래소에 등록"""
    player, _ = get_or_create_player(session)

    monster_list = player.party if source == "party" else player.inventory
    if monster_index < 0 or monster_index >= len(monster_list):
        return {"error": "유효하지 않은 몬스터 인덱스입니다."}

    # Prevent listing the last party monster
    if source == "party" and len(player.party) <= 1:
        return {"error": "파티에 최소 1마리는 남겨야 합니다."}

    monster_data = monster_list[monster_index]

    result = trade_manager.list_monster(session, monster_data, monster_index, price, source)
    if result.get("ok"):
        # Remove monster from player
        monster_list.pop(monster_index)
        persistence.save_player(session, player)
        result["player"] = player.to_dict()
    return result


@app.post("/api/trade/buy/{listing_id}")
async def trade_buy(
    listing_id: int,
    session: str = Query("default"),
):
    """거래소에서 몬스터 구매"""
    player, _ = get_or_create_player(session)

    result = trade_manager.buy_monster(session, listing_id, player.gold)
    if result.get("ok"):
        # Deduct gold from buyer
        player.spend_gold(result["price"])
        # Add monster to buyer
        monster = result["monster"]
        add_result = player.add_monster(monster)
        result["add_result"] = add_result

        # Give gold to seller (minus fee)
        seller_id = result["seller_id"]
        seller_receives = result["seller_receives"]
        seller_player, _ = get_or_create_player(seller_id)
        seller_player.gain_gold(seller_receives)
        persistence.save_player(seller_id, seller_player)

        # Save buyer
        persistence.save_player(session, player)
        result["player"] = player.to_dict()
    return result


@app.post("/api/trade/cancel/{listing_id}")
async def trade_cancel(
    listing_id: int,
    session: str = Query("default"),
):
    """거래소 등록 취소 (몬스터 복구)"""
    player, _ = get_or_create_player(session)

    result = trade_manager.cancel_listing(session, listing_id)
    if result.get("ok"):
        # Restore monster to player
        monster = result["monster"]
        add_result = player.add_monster(monster)
        result["add_result"] = add_result
        persistence.save_player(session, player)
        result["player"] = player.to_dict()
    return result


@app.get("/api/trade/marketplace")
async def trade_marketplace(
    sort: str = Query("newest", description="newest, price_low, price_high, level_high, rarity"),
    filter_type: str = Query("", description="몬스터 타입 필터"),
    filter_rarity: str = Query("", description="등급 필터"),
    session: str = Query("default"),
):
    """거래소 목록 조회"""
    listings = trade_manager.get_marketplace(sort, filter_type, filter_rarity)
    my_listings = trade_manager.get_my_listings(session)
    return {"listings": listings, "my_listings": my_listings}


@app.get("/api/trade/history")
async def trade_history(
    session: str = Query("default"),
    limit: int = Query(20, ge=1, le=50),
):
    """거래 내역 조회"""
    history = trade_manager.get_trade_history(session, limit)
    return {"history": history, "total": len(history)}


if __name__ == "__main__":
    print("=" * 50)
    print("  BarcodeQuest Game Server - http://localhost:8001")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8001)
