"""
BarcodeQuest - FastAPI 게임 서버 v2.0

신규 시스템:
  - 방치형 탐험 (ExpeditionSystem)
  - 아이템 인벤토리 (ItemInventory)
  - 크리처 진화 (EvolutionSystem)
  - 일일 퀘스트 (DailyQuestSystem)
"""
import sys
import os
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "game-engine"))

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

app = FastAPI(title="BarcodeQuest Game Server v2.0")

# 게임 엔진 인스턴스
generator = BarcodeMonsterGenerator()
battle_system = BattleSystem()
expedition_system = ExpeditionSystem()
evolution_system = EvolutionSystem()
daily_quest_system = DailyQuestSystem()
bus_system = BusSystem()

# 플레이어 상태 (인메모리 - 실제 프로덕션에서는 DB 사용)
players = {}       # session_id → Player
collections = {}   # session_id → MonsterCollection
inventories = {}   # session_id → ItemInventory
scanned_barcodes = {}  # session_id → set of barcodes already scanned


def get_or_create_player(session_id: str = "default") -> tuple:
    if session_id not in players:
        players[session_id] = Player(name="Trainer", player_id=session_id)
        collections[session_id] = MonsterCollection()
        inventories[session_id] = ItemInventory()
        scanned_barcodes[session_id] = set()
    return players[session_id], collections[session_id]


def get_inventory(session_id: str = "default") -> ItemInventory:
    if session_id not in inventories:
        inventories[session_id] = ItemInventory()
    return inventories[session_id]


@app.on_event("startup")
async def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
async def game_client():
    return GAME_HTML


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "BarcodeQuest"}


@app.get("/api/player")
async def get_player(session: str = "default"):
    player, collection = get_or_create_player(session)
    return {
        "player": player.to_dict(),
        "collection_stats": collection.get_completion_stats(),
    }


@app.post("/api/scan")
async def scan_barcode(
    barcode: str = Query(..., min_length=13, max_length=13),
    lat: float = Query(37.5665),
    lon: float = Query(126.9780),
    hour: int = Query(12),
    session: str = Query("default"),
):
    """바코드 스캔 → 몬스터 생성"""
    player, collection = get_or_create_player(session)

    # 중복 바코드 체크 — 동일 바코드는 한 번만 크리처 획득 가능
    if session not in scanned_barcodes:
        scanned_barcodes[session] = set()
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

    return {
        "monster": monster_dict,
        "collection": coll_result,
        "inventory": add_result,
        "player": player.to_dict(),
        "quest_updates": quest_updates,
        "bus_suggestion": bus_suggestion,
    }


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
    # 체크디짓 계산
    digits = [int(d) for d in random_barcode]
    check = (10 - sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits)) % 10) % 10
    random_barcode += str(check)
    opponent = generator.generate_monster(random_barcode)
    opponent_dict = opponent.to_dict()

    # 배틀 실행 (자동 5턴)
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
    else:
        player.gain_exp(5)  # 패배해도 소량 경험치
        player.gain_monster_exp(player_monster_data, 3)  # 몬스터도 소량

    return {
        "result": "WIN" if is_player_win else "LOSE",
        "player_monster": {"name": player_monster_data["name"], "level": player_monster_data.get("level", 1), "final_hp": p1.current_hp, "max_hp": p1.max_hp},
        "opponent": {"name": opponent_dict["name"], "rarity": opponent_dict["rarity"], "final_hp": p2.current_hp, "max_hp": p2.max_hp},
        "battle_log": battle_log,
        "rewards": rewards,
        "monster_level": monster_level_result,
        "player": player.to_dict(),
        "quest_updates": quest_updates,
    }


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


@app.post("/api/recover")
async def recover_energy(session: str = "default"):
    player, _ = get_or_create_player(session)
    player.recover_energy(20)
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
    """파티 ↔ 보관함 몬스터 교체"""
    player, _ = get_or_create_player(session)
    result = player.swap_party_member(party_idx, inventory_idx)
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

    return result


@app.get("/api/expedition/status")
async def expedition_status(session: str = "default"):
    """탐험 진행 상태 확인"""
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
        # 크리처 EXP는 향후 크리처 레벨업 시스템 연동
        result["applied_to"] = target_monster.get("name", "Unknown")
    elif result.get("stat_value") and target_monster:
        stat = result["stat_name"]
        val = result["stat_value"]
        if isinstance(target_monster.get("stats"), dict):
            target_monster["stats"][stat] = target_monster["stats"].get(stat, 0) + val
        result["applied_to"] = target_monster.get("name", "Unknown")

    result["player"] = player.to_dict()
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
    quests = daily_quest_system.get_quests(session)
    summary = daily_quest_system.get_summary(session)
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
    return result


@app.post("/api/bus/unassign")
async def unassign_bus_monster(
    floor: int = Query(...),
    slot: int = Query(...),
    session: str = Query("default"),
):
    """버스 방에서 몬스터 회수"""
    return bus_system.unassign_monster(session, floor, slot)


@app.post("/api/bus/upgrade-floor")
async def upgrade_bus_floor(session: str = Query("default")):
    """버스 층 해금"""
    player, _ = get_or_create_player(session)
    result = bus_system.upgrade_floor(session, player.gold, player.level)
    if "error" in result:
        return result
    player.spend_gold(result["cost"])
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
    return result


GAME_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BarcodeQuest v2</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap" rel="stylesheet">
    <script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Poppins', 'Segoe UI', sans-serif; background: linear-gradient(160deg, #1a1432, #1e1a3a, #1a2038, #1a1432); background-size: 400% 400%; animation: gradientBG 20s ease infinite; color: #e8e8f0; min-height: 100vh; }
        @keyframes gradientBG { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
        .header { background: rgba(20,18,40,0.85); backdrop-filter: blur(12px); padding: 14px 16px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 100; border-bottom: 1px solid rgba(255,255,255,0.05); }
        .header::after { content: ''; position: absolute; top: 0; left: -100%; width: 50%; height: 100%; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.03), transparent); animation: headerShimmer 5s linear infinite; }
        @keyframes headerShimmer { 0% { left: -100%; } 100% { left: 200%; } }
        .header h1 { font-size: 1.2rem; background: linear-gradient(135deg, #ff6b8a, #c084fc, #67e8f9); background-size: 200% 200%; animation: titleGradient 4s ease infinite; -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800; letter-spacing: -0.5px; }
        @keyframes titleGradient { 0%,100% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } }
        .player-info { display: flex; gap: 6px; font-size: 0.72rem; }
        .player-info span { background: rgba(255,255,255,0.06); padding: 4px 10px; border-radius: 20px; color: #b0b0cc; }
        .container { max-width: 600px; margin: 0 auto; padding: 12px; }
        .tabs { display: flex; gap: 4px; margin-bottom: 14px; background: rgba(255,255,255,0.03); border-radius: 12px; padding: 3px; }
        .tab { flex: 1; padding: 8px 4px; text-align: center; background: transparent; border-radius: 10px; cursor: pointer; font-weight: 600; font-size: 0.72rem; transition: all 0.25s ease; color: #888; }
        .tab.active { background: linear-gradient(135deg, #ff6b8a, #e05577); color: #fff; box-shadow: 0 4px 15px rgba(255,107,138,0.3); }
        .tab:hover:not(.active) { background: rgba(255,255,255,0.05); color: #bbb; }
        .panel { display: none; }
        .panel.active { display: block; animation: panelFadeIn 0.35s ease-out; }
        @keyframes panelFadeIn { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
        /* Scan Panel */
        .scan-area { text-align: center; padding: 20px 0; }
        .barcode-input { width: 100%; padding: 14px; border: 1.5px solid rgba(255,107,138,0.3); border-radius: 14px; background: rgba(255,255,255,0.05); color: #e8e8f0; font-size: 1.1rem; text-align: center; letter-spacing: 3px; margin-bottom: 12px; outline: none; transition: all 0.3s; }
        .barcode-input:focus { border-color: #c084fc; box-shadow: 0 0 20px rgba(192,132,252,0.15); background: rgba(255,255,255,0.07); }
        .barcode-input::placeholder { color: #555; }
        .scan-btn { width: 100%; padding: 14px; background: linear-gradient(135deg, #ff6b8a, #e05577); color: white; border: none; border-radius: 14px; font-size: 1.1rem; font-weight: 700; cursor: pointer; transition: all 0.25s; position: relative; overflow: hidden; letter-spacing: 1px; }
        .scan-btn::before { content: ''; position: absolute; top: 0; left: -100%; width: 100%; height: 100%; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent); transition: left 0.5s ease; }
        .scan-btn:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(255,107,138,0.35); }
        .scan-btn:hover::before { left: 100%; }
        .scan-btn:active { transform: scale(0.98); }
        .scan-btn:disabled { background: #333; cursor: not-allowed; transform: none; box-shadow: none; }
        /* Monster Card with animation */
        .monster-card { background: linear-gradient(145deg, #16213e, #1a1a2e); border: 2px solid #333; border-radius: 16px; padding: 20px; margin: 16px 0; text-align: center; position: relative; overflow: hidden; }
        .monster-card.rarity-Common { border-color: #555; background: linear-gradient(145deg, #2a2a3e, #1e1e30); }
        .monster-card.rarity-Uncommon { border-color: #4ecdc4; background: linear-gradient(145deg, #1a2e2a, #162824); box-shadow: 0 0 8px rgba(78,205,196,0.15); }
        .monster-card.rarity-Rare { border-color: #3b82f6; background: linear-gradient(145deg, #1a2440, #162040); box-shadow: 0 0 15px rgba(59,130,246,0.3); }
        .monster-card.rarity-Epic { border-color: #a855f7; background: linear-gradient(145deg, #2a1a3e, #221638); box-shadow: 0 0 15px rgba(168,85,247,0.3); animation: epicGlow 2s ease-in-out infinite; }
        @keyframes epicGlow { 0%,100% { box-shadow: 0 0 15px rgba(168,85,247,0.3); } 50% { box-shadow: 0 0 30px rgba(168,85,247,0.6); } }
        .monster-card.rarity-Epic::before { content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%; background: radial-gradient(circle, rgba(168,85,247,0.08) 0%, transparent 70%); animation: epicPulse 3s ease-in-out infinite; pointer-events: none; }
        @keyframes epicPulse { 0%,100% { transform: scale(0.8); opacity: 0.5; } 50% { transform: scale(1.2); opacity: 1; } }
        .monster-card.rarity-Legendary { border-color: #f59e0b; background: linear-gradient(145deg, #3a2a10, #2e2208); box-shadow: 0 0 25px rgba(245,158,11,0.4); animation: legendGlow 1.5s ease-in-out infinite; }
        @keyframes legendGlow { 0%,100% { box-shadow: 0 0 25px rgba(245,158,11,0.4); } 50% { box-shadow: 0 0 45px rgba(245,158,11,0.7); } }
        .monster-card.rarity-Legendary::before { content: ''; position: absolute; top: 0; left: -100%; width: 50%; height: 100%; background: linear-gradient(90deg, transparent, rgba(255,204,2,0.12), rgba(255,255,255,0.08), rgba(255,204,2,0.12), transparent); animation: holoShine 3s linear infinite; pointer-events: none; z-index: 1; }
        @keyframes holoShine { 0% { left: -100%; } 100% { left: 200%; } }
        .monster-card.rarity-Legendary::after { content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: linear-gradient(135deg, rgba(255,0,0,0.03), rgba(255,165,0,0.03), rgba(255,255,0,0.03), rgba(0,128,0,0.03), rgba(0,0,255,0.03), rgba(128,0,128,0.03)); background-size: 300% 300%; animation: rainbowSheen 4s ease infinite; border-radius: 14px; pointer-events: none; }
        @keyframes rainbowSheen { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
        .rarity-sparkles { font-size: 0.75rem; letter-spacing: 2px; display: inline-block; margin-left: 4px; animation: sparkleAnim 1.5s ease-in-out infinite; }
        @keyframes sparkleAnim { 0%,100% { opacity: 0.5; transform: scale(0.9); } 50% { opacity: 1; transform: scale(1.1); } }
        .legend-particle { position: absolute; width: 3px; height: 3px; background: #ffcc02; border-radius: 50%; pointer-events: none; z-index: 2; }
        @keyframes particleFloat { 0% { transform: translateY(0) scale(1); opacity: 0.8; } 100% { transform: translateY(-80px) scale(0); opacity: 0; } }
        .monster-name { font-size: 1.3rem; font-weight: 700; margin: 10px 0 5px; }
        .monster-type { font-size: 0.85rem; color: #aaa; }
        .rarity-badge { display: inline-block; padding: 3px 12px; border-radius: 12px; font-size: 0.8rem; font-weight: 700; margin: 8px 0; }
        .rarity-Common { background: #444; }
        .rarity-Uncommon { background: #0f766e; }
        .rarity-Rare { background: #1d4ed8; }
        .rarity-Epic { background: #7c3aed; }
        .rarity-Legendary { background: linear-gradient(135deg, #d97706, #f59e0b); }
        .stats-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin: 12px 0; }
        .stat { text-align: center; }
        .stat .label { font-size: 0.65rem; color: #888; }
        .stat .val { font-size: 1rem; font-weight: 700; }
        .monster-visual { font-size: 3rem; margin: 10px; animation: float 3s ease-in-out infinite; position: relative; z-index: 2; }
        .monster-svg-wrap { display: inline-block; animation: float 3s ease-in-out infinite; position: relative; z-index: 2; }
        .monster-svg-wrap svg { filter: drop-shadow(0 4px 8px rgba(0,0,0,0.4)); }
        @keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
        .trait { font-size: 0.8rem; color: #e94560; font-style: italic; margin-top: 8px; }
        /* Battle */
        .battle-arena { text-align: center; }
        .battle-btn { padding: 14px 40px; background: linear-gradient(135deg, #e94560, #c23152); color: white; border: none; border-radius: 12px; font-size: 1rem; font-weight: 700; cursor: pointer; margin: 16px 0; transition: all 0.2s; position: relative; overflow: hidden; }
        .battle-btn::before { content: ''; position: absolute; top: 0; left: -100%; width: 100%; height: 100%; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent); transition: left 0.5s ease; }
        .battle-btn:hover { transform: scale(1.03); box-shadow: 0 6px 20px rgba(233,69,96,0.4); }
        .battle-btn:hover::before { left: 100%; }
        .battle-log { background: #0f0f23; border-radius: 12px; padding: 12px; max-height: 300px; overflow-y: auto; font-size: 0.82rem; line-height: 1.8; }
        .log-win { color: #4ecdc4; }
        .log-lose { color: #e94560; }
        .log-crit { color: #f59e0b; font-weight: 700; }
        .battle-result { font-size: 2rem; font-weight: 800; margin: 16px 0; }
        .battle-result.win { color: #4ecdc4; }
        .battle-result.lose { color: #e94560; }
        /* Collection */
        .coll-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 16px; }
        .coll-stat { background: #16213e; border-radius: 10px; padding: 12px; text-align: center; }
        .coll-stat .num { font-size: 1.5rem; font-weight: 700; color: #e94560; }
        .coll-stat .lbl { font-size: 0.75rem; color: #888; }
        .mini-card { background: #16213e; border-radius: 10px; padding: 10px; margin: 6px 0; display: flex; align-items: center; gap: 12px; }
        .mini-card .mc-icon { font-size: 1.5rem; }
        .mini-card .mc-info { flex: 1; }
        .mini-card .mc-name { font-weight: 600; font-size: 0.9rem; }
        .mini-card .mc-sub { font-size: 0.75rem; color: #888; }
        .energy-bar { width: 100%; height: 6px; background: #333; border-radius: 3px; margin: 4px 0; box-shadow: 0 0 8px rgba(78,205,196,0.15); }
        .energy-fill { height: 100%; background: linear-gradient(90deg, #4ecdc4, #7ee8fa); border-radius: 3px; transition: width 0.3s; position: relative; overflow: hidden; }
        .energy-fill::after { content: ''; position: absolute; top: 0; left: -100%; width: 100%; height: 100%; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent); animation: energyShimmer 2s linear infinite; }
        @keyframes energyShimmer { 0% { left: -100%; } 100% { left: 100%; } }
        .sample-codes { margin-top: 12px; }
        .sample-codes button { background: #16213e; border: 1px solid #333; color: #aaa; padding: 6px 10px; border-radius: 8px; margin: 3px; cursor: pointer; font-size: 0.75rem; transition: all 0.15s; }
        .sample-codes button:hover { border-color: #e94560; color: white; background: #1a1a3e; }
        /* Expedition */
        .zone-card { background: #16213e; border-radius: 12px; padding: 14px; margin: 8px 0; cursor: pointer; transition: all 0.2s; border: 1px solid #333; }
        .zone-card:hover { border-color: #e94560; transform: translateY(-2px); }
        .zone-card.locked { opacity: 0.5; cursor: not-allowed; }
        .zone-header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
        .zone-emoji { font-size: 1.5rem; }
        .zone-name { font-weight: 700; font-size: 0.95rem; }
        .zone-diff { font-size: 0.7rem; padding: 2px 8px; border-radius: 6px; }
        .diff-easy { background: #2e7d32; }
        .diff-normal { background: #1565c0; }
        .diff-hard { background: #7c3aed; }
        .diff-legendary { background: #d97706; }
        .zone-desc { font-size: 0.8rem; color: #888; }
        .zone-rewards { font-size: 0.75rem; color: #4ecdc4; margin-top: 4px; }
        .progress-bar { width: 100%; height: 8px; background: #333; border-radius: 4px; margin: 8px 0; overflow: hidden; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #e94560, #f093fb); border-radius: 4px; transition: width 0.5s; }
        /* Quest */
        .quest-card { background: #16213e; border-radius: 10px; padding: 12px; margin: 6px 0; display: flex; align-items: center; gap: 10px; border: 1px solid #333; }
        .quest-card.completed { border-color: #4ecdc4; }
        .quest-card.claimed { opacity: 0.6; }
        .quest-emoji { font-size: 1.3rem; }
        .quest-info { flex: 1; }
        .quest-title { font-weight: 600; font-size: 0.85rem; }
        .quest-desc { font-size: 0.73rem; color: #888; }
        .quest-progress { font-size: 0.7rem; color: #4ecdc4; margin-top: 2px; }
        .quest-reward { font-size: 0.7rem; color: #f59e0b; }
        .claim-btn { padding: 6px 12px; background: #4ecdc4; color: #1a1a2e; border: none; border-radius: 6px; font-size: 0.75rem; font-weight: 700; cursor: pointer; }
        .claim-btn:hover { background: #7ee8fa; }
        /* Toast notification */
        .toast { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: linear-gradient(135deg, #4ecdc4, #7ee8fa); color: #1a1a2e; padding: 10px 20px; border-radius: 10px; font-weight: 700; font-size: 0.85rem; z-index: 1000; animation: toastIn 0.3s ease-out; pointer-events: none; }
        @keyframes toastIn { from { opacity:0; transform: translateX(-50%) translateY(-20px); } to { opacity:1; transform: translateX(-50%) translateY(0); } }
        /* Bus System */
        .bus-collect-btn { padding: 8px 16px; background: linear-gradient(135deg, #4ecdc4, #2ab7a9); color: #1a1a2e; border: none; border-radius: 8px; font-size: 0.8rem; font-weight: 700; cursor: pointer; position: relative; overflow: hidden; transition: all 0.2s; }
        .bus-collect-btn::before { content: ''; position: absolute; top: 0; left: -100%; width: 100%; height: 100%; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.25), transparent); transition: left 0.5s ease; }
        .bus-collect-btn:hover { transform: scale(1.03); box-shadow: 0 4px 12px rgba(78,205,196,0.3); }
        .bus-collect-btn:hover::before { left: 100%; }
        .bus-floor { background: #16213e; border-radius: 12px; padding: 12px; margin-bottom: 10px; border: 1px solid #333; }
        .bus-floor-header { font-weight: 700; font-size: 0.9rem; margin-bottom: 8px; color: #f093fb; }
        .bus-slots { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
        .bus-slot { background: #1a1a2e; border: 2px dashed #444; border-radius: 10px; padding: 10px; text-align: center; min-height: 110px; cursor: pointer; transition: all 0.3s ease; display: flex; flex-direction: column; justify-content: center; align-items: center; }
        .bus-slot:hover { border-color: #e94560; transform: translateY(-4px); box-shadow: 0 8px 20px rgba(0,0,0,0.3); background: rgba(233,69,96,0.05); }
        .bus-slot.has-room { border-style: solid; border-color: #2a8a8a; background: linear-gradient(180deg, #1a2a3e, #1a1a2e); }
        .bus-slot.has-room:hover { border-color: #4ecdc4; box-shadow: 0 8px 20px rgba(78,205,196,0.15); }
        .bus-slot .slot-emoji { font-size: 1.5rem; animation: float 3s ease-in-out infinite; }
        .bus-slot .slot-name { font-size: 0.72rem; font-weight: 600; margin-top: 4px; }
        .bus-slot .slot-level { font-size: 0.65rem; color: #888; }
        .bus-slot .slot-monster { font-size: 0.68rem; color: #4ecdc4; margin-top: 3px; }
        .bus-slot .slot-prod { font-size: 0.62rem; color: #f59e0b; margin-top: 2px; }
        .bus-slot .slot-empty { font-size: 0.75rem; color: #555; }
        .bus-slot .slot-affinity { font-size: 0.6rem; padding: 1px 6px; border-radius: 4px; display: inline-block; margin-top: 2px; }
        .bus-slot .slot-affinity.grade-S { background: linear-gradient(135deg, #d97706, #fbbf24); color: #fff; box-shadow: 0 0 10px rgba(251,191,36,0.4); animation: sGradeGlow 1.5s ease-in-out infinite; }
        @keyframes sGradeGlow { 0%,100% { box-shadow: 0 0 8px rgba(251,191,36,0.3); } 50% { box-shadow: 0 0 16px rgba(251,191,36,0.7); } }
        .bus-slot .slot-affinity.grade-A { background: #7c3aed; color: #fff; }
        .bus-slot .slot-affinity.grade-B { background: #1d4ed8; color: #fff; }
        .bus-slot .slot-affinity.grade-C { background: #444; color: #aaa; }
        .bus-accumulated { background: #0f0f23; border-radius: 8px; padding: 8px 12px; font-size: 0.8rem; display: flex; gap: 12px; flex-wrap: wrap; }
        .bus-accumulated .res-item { color: #f59e0b; }
        .bus-modal { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); z-index: 999; display: flex; align-items: center; justify-content: center; }
        .bus-modal-content { background: #16213e; border-radius: 14px; padding: 20px; max-width: 400px; width: 90%; max-height: 80vh; overflow-y: auto; }
        .bus-modal-close { width: 100%; padding: 10px; margin-top: 12px; background: #333; color: #aaa; border: none; border-radius: 8px; cursor: pointer; }
        .bus-room-option { background: #1a1a2e; border: 1px solid #333; border-radius: 10px; padding: 10px; margin: 6px 0; cursor: pointer; transition: all 0.15s; }
        .bus-room-option:hover { border-color: #e94560; }
        .bus-room-option .ro-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
        .bus-room-option .ro-emoji { font-size: 1.2rem; }
        .bus-room-option .ro-name { font-weight: 600; font-size: 0.85rem; }
        .bus-room-option .ro-cost { font-size: 0.75rem; color: #f59e0b; }
        .bus-room-option .ro-desc { font-size: 0.72rem; color: #888; }
        .bus-room-option .ro-types { font-size: 0.68rem; color: #4ecdc4; margin-top: 2px; }
        .bus-monster-option { background: #1a1a2e; border: 1px solid #333; border-radius: 10px; padding: 10px; margin: 6px 0; cursor: pointer; display: flex; align-items: center; gap: 10px; transition: all 0.15s; }
        .bus-monster-option:hover { border-color: #4ecdc4; }
        .bus-monster-option .bmo-info { flex: 1; }
        .bus-monster-option .bmo-name { font-weight: 600; font-size: 0.85rem; }
        .bus-monster-option .bmo-sub { font-size: 0.72rem; color: #888; }
        .bus-upgrade-btn { padding: 8px 16px; background: linear-gradient(135deg, #f093fb, #e94560); color: white; border: none; border-radius: 8px; font-size: 0.8rem; font-weight: 700; cursor: pointer; margin-top: 6px; position: relative; overflow: hidden; transition: all 0.2s; }
        .bus-upgrade-btn::before { content: ''; position: absolute; top: 0; left: -100%; width: 100%; height: 100%; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent); transition: left 0.5s ease; }
        .bus-upgrade-btn:hover { transform: scale(1.03); box-shadow: 0 4px 12px rgba(240,147,251,0.3); }
        .bus-upgrade-btn:hover::before { left: 100%; }
        .bus-suggestion { background: #16213e; border: 1px solid #4ecdc4; border-radius: 8px; padding: 8px 12px; margin-top: 8px; font-size: 0.78rem; }
        .bus-suggestion .bs-label { color: #4ecdc4; font-weight: 600; }
        /* Camera Scanner */
        .camera-toggle { width: 100%; padding: 12px; background: rgba(103,232,249,0.06); color: #67e8f9; border: 1.5px solid rgba(103,232,249,0.25); border-radius: 14px; font-size: 0.95rem; font-weight: 700; cursor: pointer; margin-bottom: 12px; transition: all 0.25s; }
        .camera-toggle:hover { background: rgba(103,232,249,0.12); border-color: rgba(103,232,249,0.5); transform: translateY(-1px); }
        .camera-toggle.active { background: #67e8f9; color: #1a1a2e; border-color: #67e8f9; }
        #cameraPreview { width: 100%; border-radius: 12px; overflow: hidden; margin-bottom: 12px; display: none; }
        #cameraPreview video { border-radius: 12px; }
        .camera-status { font-size: 0.8rem; color: #4ecdc4; margin-bottom: 8px; animation: pulse 1.5s ease-in-out infinite; }
        .scan-divider { display: flex; align-items: center; gap: 10px; margin: 12px 0; }
        .scan-divider hr { flex: 1; border: none; border-top: 1px solid #333; }
        .scan-divider span { font-size: 0.75rem; color: #555; }
        /* === HERO WELCOME SECTION === */
        .hero-section { position: relative; text-align: center; padding: 30px 16px 22px; overflow: hidden; border-radius: 20px; margin-bottom: 16px; background: linear-gradient(180deg, rgba(255,107,138,0.06) 0%, rgba(192,132,252,0.04) 50%, transparent 100%); border: 1px solid rgba(255,255,255,0.05); }
        /* Ambient floating particles */
        .hero-particles { position: absolute; top: 0; left: 0; right: 0; bottom: 0; pointer-events: none; z-index: 0; overflow: hidden; }
        .hero-particle { position: absolute; border-radius: 50%; opacity: 0; animation: ambientParticle linear infinite; }
        @keyframes ambientParticle { 0% { opacity: 0; transform: translateY(100%) scale(0); } 20% { opacity: 0.5; } 80% { opacity: 0.2; } 100% { opacity: 0; transform: translateY(-100vh) scale(1); } }
        /* Animated SVG creatures */
        .hero-creature-stage { position: relative; z-index: 2; height: 80px; margin-bottom: 8px; display: flex; justify-content: center; align-items: flex-end; gap: 0; }
        .hero-creature-slot { display: inline-block; opacity: 0.85; }
        .hero-creature-slot:nth-child(1) { animation: creatureBob1 3s ease-in-out infinite; }
        .hero-creature-slot:nth-child(2) { animation: creatureBob2 3.5s ease-in-out infinite; }
        .hero-creature-slot:nth-child(3) { animation: creatureBob3 2.8s ease-in-out infinite; margin: 0 -4px; transform-origin: bottom center; }
        .hero-creature-slot:nth-child(4) { animation: creatureBob2 3.2s ease-in-out infinite reverse; }
        .hero-creature-slot:nth-child(5) { animation: creatureBob1 3.7s ease-in-out infinite reverse; }
        @keyframes creatureBob1 { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
        @keyframes creatureBob2 { 0%,100% { transform: translateY(0) rotate(0deg); } 50% { transform: translateY(-12px) rotate(3deg); } }
        @keyframes creatureBob3 { 0%,100% { transform: translateY(0) scale(1); } 50% { transform: translateY(-14px) scale(1.04); } }
        .hero-creature-shadow { width: 30px; height: 6px; background: radial-gradient(ellipse, rgba(0,0,0,0.2) 0%, transparent 70%); border-radius: 50%; margin: 2px auto 0; animation: shadowPulse 3s ease-in-out infinite; }
        @keyframes shadowPulse { 0%,100% { transform: scaleX(1); opacity: 0.3; } 50% { transform: scaleX(0.7); opacity: 0.15; } }
        /* Logo */
        .hero-logo-wrap { position: relative; z-index: 2; margin-bottom: 4px; }
        .hero-logo { font-size: 2.4rem; font-weight: 800; background: linear-gradient(135deg, #ff6b8a, #c084fc, #67e8f9, #c084fc, #ff6b8a); background-size: 300% 300%; animation: heroGrad 6s ease infinite; -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: -0.5px; }
        .hero-logo-sub { font-size: 0.6rem; color: #666; letter-spacing: 5px; text-transform: uppercase; margin-top: 0; }
        @keyframes heroGrad { 0%,100% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } }
        /* Lore tagline */
        .hero-lore { position: relative; z-index: 2; margin-bottom: 18px; }
        .hero-tagline { font-size: 0.85rem; color: #a0a0c0; font-weight: 400; letter-spacing: 0.3px; line-height: 1.7; }
        .hero-tagline em { color: #c084fc; font-style: normal; font-weight: 600; }
        .hero-tagline .lore-glow { color: #ff6b8a; font-weight: 700; }
        .hero-lore-divider { width: 50px; height: 1px; background: linear-gradient(90deg, transparent, rgba(192,132,252,0.4), transparent); margin: 12px auto 0; }
        /* Legacy creature silhouettes hidden */
        .hero-creatures { display: none; }
        /* Quick stats row */
        .hero-stats { display: flex; gap: 6px; justify-content: center; margin-bottom: 16px; position: relative; z-index: 2; }
        .hero-stat { background: rgba(255,255,255,0.04); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.06); border-radius: 14px; padding: 8px 0; text-align: center; flex: 1; max-width: 85px; transition: all 0.3s; }
        .hero-stat:hover { background: rgba(255,255,255,0.07); transform: translateY(-2px); }
        .hero-stat .hs-icon { font-size: 0.85rem; display: block; margin-bottom: 1px; }
        .hero-stat .hs-num { font-size: 1.1rem; font-weight: 800; display: block; line-height: 1.2; }
        .hero-stat .hs-num.gold { color: #fbbf24; }
        .hero-stat .hs-num.energy { color: #67e8f9; }
        .hero-stat .hs-num.collection { color: #c084fc; }
        .hero-stat .hs-num.level { color: #ff6b8a; }
        .hero-stat .hs-label { font-size: 0.52rem; color: #666; text-transform: uppercase; letter-spacing: 1px; }
        /* Recent catches carousel */
        .recent-catches { position: relative; z-index: 2; }
        .recent-catches-title { font-size: 0.62rem; color: #555; text-transform: uppercase; letter-spacing: 3px; margin-bottom: 8px; text-align: center; }
        .recent-row { display: flex; gap: 7px; overflow-x: auto; padding: 4px 2px; scrollbar-width: none; }
        .recent-row::-webkit-scrollbar { display: none; }
        .recent-mini { flex-shrink: 0; width: 68px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 8px 4px 6px; text-align: center; cursor: pointer; transition: all 0.3s; }
        .recent-mini:hover { border-color: rgba(255,107,138,0.4); transform: translateY(-4px); box-shadow: 0 8px 20px rgba(0,0,0,0.3); }
        .recent-mini.r-Legendary { border-color: rgba(251,191,36,0.35); background: rgba(251,191,36,0.05); }
        .recent-mini.r-Epic { border-color: rgba(192,132,252,0.3); background: rgba(192,132,252,0.04); }
        .recent-mini.r-Rare { border-color: rgba(96,165,250,0.25); background: rgba(96,165,250,0.03); }
        .recent-mini .rm-svg { margin-bottom: 3px; }
        .recent-mini .rm-name { font-size: 0.52rem; font-weight: 600; color: #bbb; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .recent-mini .rm-rarity { font-size: 0.45rem; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 700; }
        .recent-empty { color: #555; font-size: 0.78rem; padding: 18px 16px; background: rgba(255,255,255,0.02); border: 1px dashed rgba(255,255,255,0.08); border-radius: 14px; line-height: 1.6; }
        .recent-empty .re-icon { font-size: 1.6rem; display: block; margin-bottom: 6px; opacity: 0.6; animation: reEmptyPulse 3s ease-in-out infinite; }
        @keyframes reEmptyPulse { 0%,100% { transform: scale(1); opacity: 0.5; } 50% { transform: scale(1.08); opacity: 0.8; } }
        .recent-empty .re-hint { font-size: 0.68rem; color: #555; }
        /* === SCAN PORTAL === */
        .summon-section { position: relative; text-align: center; padding: 0 0 4px; }
        .summon-label { font-size: 0.6rem; color: #555; text-transform: uppercase; letter-spacing: 4px; margin-bottom: 8px; position: relative; z-index: 2; }
        .scan-portal { position: relative; margin: 0 auto 8px; width: 180px; height: 180px; display: flex; align-items: center; justify-content: center; }
        .scan-portal-bg { position: absolute; width: 150px; height: 150px; border-radius: 50%; background: radial-gradient(circle, rgba(192,132,252,0.08) 0%, rgba(255,107,138,0.04) 50%, transparent 70%); animation: portalBgPulse 4s ease-in-out infinite; }
        @keyframes portalBgPulse { 0%,100% { transform: scale(1); opacity: 0.6; } 50% { transform: scale(1.12); opacity: 1; } }
        .scan-portal-ring { position: absolute; border: 2px solid rgba(233,69,96,0.15); border-radius: 50%; }
        .scan-portal-ring:nth-child(2) { width: 170px; height: 170px; border-color: rgba(255,107,138,0.08); animation: portalSpin 20s linear infinite; border-width: 1px; border-style: dotted; }
        .scan-portal-ring:nth-child(3) { width: 140px; height: 140px; border-color: rgba(192,132,252,0.1); animation: portalSpin 12s linear infinite reverse; }
        .scan-portal-ring:nth-child(4) { width: 110px; height: 110px; border-color: rgba(103,232,249,0.12); animation: portalSpin 8s linear infinite; border-style: dashed; }
        .scan-portal-ring:nth-child(5) { width: 80px; height: 80px; border-color: rgba(251,191,36,0.08); animation: portalSpin 5s linear infinite reverse; border-width: 1px; }
        @keyframes portalSpin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .scan-portal-runes { position: absolute; width: 160px; height: 160px; animation: portalSpin 30s linear infinite; }
        .scan-portal-rune { position: absolute; font-size: 0.6rem; opacity: 0.12; color: #c084fc; }
        .scan-portal-rune:nth-child(1) { top: 0; left: 50%; transform: translateX(-50%); }
        .scan-portal-rune:nth-child(2) { top: 25%; right: 2%; }
        .scan-portal-rune:nth-child(3) { bottom: 25%; right: 2%; }
        .scan-portal-rune:nth-child(4) { bottom: 0; left: 50%; transform: translateX(-50%); }
        .scan-portal-rune:nth-child(5) { bottom: 25%; left: 2%; }
        .scan-portal-rune:nth-child(6) { top: 25%; left: 2%; }
        .scan-portal-center { position: relative; z-index: 2; display: flex; flex-direction: column; align-items: center; }
        .scan-portal-orb { font-size: 2.8rem; animation: orbFloat 4s ease-in-out infinite; filter: drop-shadow(0 0 20px rgba(192,132,252,0.35)); }
        @keyframes orbFloat { 0%,100% { transform: translateY(0) scale(1); filter: drop-shadow(0 0 20px rgba(192,132,252,0.3)); } 50% { transform: translateY(-6px) scale(1.05); filter: drop-shadow(0 0 30px rgba(255,107,138,0.4)); } }
        .scan-portal-text { font-size: 0.55rem; color: #666; letter-spacing: 3px; text-transform: uppercase; margin-top: 2px; }
        .scan-portal-dots { position: absolute; width: 100%; height: 100%; }
        .scan-portal-dot { position: absolute; width: 3px; height: 3px; background: #ff6b8a; border-radius: 50%; opacity: 0; animation: portalDot 5s ease-in-out infinite; }
        .scan-portal-dot:nth-child(1) { top: 5%; left: 50%; animation-delay: 0s; }
        .scan-portal-dot:nth-child(2) { top: 50%; right: 2%; animation-delay: -1s; background: #c084fc; }
        .scan-portal-dot:nth-child(3) { bottom: 5%; left: 50%; animation-delay: -2s; }
        .scan-portal-dot:nth-child(4) { top: 50%; left: 2%; animation-delay: -3s; background: #67e8f9; }
        .scan-portal-dot:nth-child(5) { top: 15%; right: 12%; animation-delay: -0.7s; background: #c084fc; width: 2px; height: 2px; }
        .scan-portal-dot:nth-child(6) { bottom: 15%; left: 12%; animation-delay: -2.7s; background: #67e8f9; width: 2px; height: 2px; }
        .scan-portal-dot:nth-child(7) { top: 30%; left: 8%; animation-delay: -4s; background: #fbbf24; width: 2px; height: 2px; }
        .scan-portal-dot:nth-child(8) { bottom: 30%; right: 8%; animation-delay: -1.5s; width: 2px; height: 2px; }
        @keyframes portalDot { 0%,100% { opacity: 0; transform: scale(0); } 50% { opacity: 0.7; transform: scale(2); } }
        /* Energy bar compact */
        .energy-compact { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; padding: 0 10px; }
        .energy-compact .energy-bar { flex: 1; height: 4px; background: rgba(255,255,255,0.06); }
        .energy-compact .ec-text { font-size: 0.65rem; color: #666; white-space: nowrap; min-width: 65px; text-align: right; }
        /* Scan action area */
        .scan-actions { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); border-radius: 16px; padding: 16px; margin-bottom: 14px; }
        .scan-actions-title { font-size: 0.6rem; color: #555; text-transform: uppercase; letter-spacing: 3px; margin-bottom: 12px; text-align: center; }
        /* Improved sample buttons */
        .sample-section { margin-top: 6px; }
        .sample-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; position: relative; z-index: 2; }
        .sample-item { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 10px 4px 8px; text-align: center; cursor: pointer; transition: all 0.3s; }
        .sample-item:hover { border-color: rgba(255,107,138,0.3); transform: translateY(-3px); box-shadow: 0 6px 16px rgba(255,107,138,0.1); background: rgba(255,107,138,0.04); }
        .sample-item .si-flag { font-size: 1.2rem; display: block; margin-bottom: 3px; }
        .sample-item .si-name { font-size: 0.58rem; color: #999; font-weight: 600; display: block; line-height: 1.2; }
        .sample-item .si-code { font-size: 0.45rem; color: #555; display: block; margin-top: 3px; font-family: monospace; letter-spacing: 0.5px; }
        /* Scan section improvements */
        .scan-section-title { font-size: 0.65rem; color: #444; text-transform: uppercase; letter-spacing: 3px; margin-bottom: 10px; text-align: center; }
        .scan-input-group { position: relative; margin-bottom: 12px; }
        .scan-input-group .barcode-input { padding-right: 50px; }
        .scan-input-icon { position: absolute; right: 14px; top: 50%; transform: translateY(-50%); font-size: 1.2rem; opacity: 0.3; pointer-events: none; }
        /* Welcome tip */
        .welcome-tip { background: rgba(255,255,255,0.03); border: 1px solid rgba(192,132,252,0.1); border-radius: 14px; padding: 14px 16px; margin-bottom: 16px; font-size: 0.76rem; color: #888; line-height: 1.7; position: relative; z-index: 2; }
        .welcome-tip strong { color: #c084fc; }
        .welcome-tip .tip-dismiss { position: absolute; top: 8px; right: 10px; background: none; border: none; color: #555; cursor: pointer; font-size: 0.85rem; transition: color 0.2s; }
        .welcome-tip .tip-dismiss:hover { color: #aaa; }
        .welcome-tip .tip-flavor { color: #777; font-style: italic; font-size: 0.7rem; display: block; margin-top: 6px; }
        /* NEW discovery effect */
        .new-discovery { color: #f59e0b; font-size: 1.2rem; font-weight: 700; margin: 8px; animation: pulse 1s ease-in-out infinite; }
        @keyframes pulse { 0%,100% { transform: scale(1); } 50% { transform: scale(1.05); } }
        /* === GACHA SCAN OVERLAY === */
        .scan-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(5,5,15,0.95); z-index: 1000; display: flex; align-items: center; justify-content: center; flex-direction: column; }
        .scan-stage { text-align: center; animation: stageAppear 0.3s ease-out; }
        @keyframes stageAppear { from { opacity: 0; transform: scale(0.8); } to { opacity: 1; transform: scale(1); } }
        .scan-particles-box { width: 120px; height: 120px; position: relative; margin: 0 auto 20px; animation: scanVibrate 0.08s linear infinite; }
        @keyframes scanVibrate { 0%,100% { transform: translate(0,0); } 25% { transform: translate(-3px,1px); } 50% { transform: translate(2px,-2px); } 75% { transform: translate(-1px,3px); } }
        .scan-p { position: absolute; width: 8px; height: 8px; border-radius: 50%; background: #e94560; top: 50%; left: 50%; }
        .scan-p:nth-child(1) { animation: sp1 0.8s ease-out infinite; }
        .scan-p:nth-child(2) { animation: sp2 0.8s ease-out 0.15s infinite; }
        .scan-p:nth-child(3) { animation: sp3 0.8s ease-out 0.3s infinite; }
        .scan-p:nth-child(4) { animation: sp4 0.8s ease-out 0.45s infinite; }
        @keyframes sp1 { 0% { transform: translate(0,0) scale(1); opacity:1; } 100% { transform: translate(-40px,-40px) scale(0); opacity:0; } }
        @keyframes sp2 { 0% { transform: translate(0,0) scale(1); opacity:1; } 100% { transform: translate(40px,-40px) scale(0); opacity:0; } }
        @keyframes sp3 { 0% { transform: translate(0,0) scale(1); opacity:1; } 100% { transform: translate(-40px,40px) scale(0); opacity:0; } }
        @keyframes sp4 { 0% { transform: translate(0,0) scale(1); opacity:1; } 100% { transform: translate(40px,40px) scale(0); opacity:0; } }
        .scan-text-anim { font-size: 1.3rem; font-weight: 700; color: #e94560; animation: scanTextPulse 0.5s ease-in-out infinite alternate; }
        @keyframes scanTextPulse { from { opacity: 0.5; text-shadow: 0 0 5px rgba(233,69,96,0.3); } to { opacity: 1; text-shadow: 0 0 20px rgba(233,69,96,0.6); } }
        .energy-orbs-box { width: 150px; height: 150px; position: relative; margin: 0 auto 20px; }
        .energy-orb { position: absolute; width: 12px; height: 12px; border-radius: 50%; top: 50%; left: 50%; }
        .energy-orb:nth-child(1) { animation: eorb 1.8s ease-in forwards; --sx: -60px; --sy: -50px; }
        .energy-orb:nth-child(2) { animation: eorb 1.8s ease-in 0.1s forwards; --sx: 60px; --sy: -50px; }
        .energy-orb:nth-child(3) { animation: eorb 1.8s ease-in 0.2s forwards; --sx: -70px; --sy: 20px; }
        .energy-orb:nth-child(4) { animation: eorb 1.8s ease-in 0.3s forwards; --sx: 70px; --sy: 20px; }
        .energy-orb:nth-child(5) { animation: eorb 1.8s ease-in 0.15s forwards; --sx: 0px; --sy: -70px; }
        .energy-orb:nth-child(6) { animation: eorb 1.8s ease-in 0.25s forwards; --sx: 0px; --sy: 70px; }
        @keyframes eorb { 0% { transform: translate(var(--sx), var(--sy)) scale(1.5); opacity: 0.2; } 70% { opacity: 1; } 100% { transform: translate(0, 0) scale(0.3); opacity: 0; } }
        .rarity-hint-text { font-size: 1rem; font-weight: 600; color: #f093fb; opacity: 0; animation: hintAppear 0.5s ease-out 0.8s forwards; }
        @keyframes hintAppear { to { opacity: 1; } }
        .card-reveal-wrap { perspective: 800px; }
        .card-flip-anim { transform: rotateY(180deg); animation: cardFlipReveal 0.8s ease-out forwards; }
        @keyframes cardFlipReveal { 0% { transform: rotateY(180deg) scale(0.5); opacity: 0; } 50% { transform: rotateY(0deg) scale(1.1); opacity: 1; } 100% { transform: rotateY(0deg) scale(1); } }
        .star-burst-box { position: absolute; width: 300px; height: 300px; top: 50%; left: 50%; transform: translate(-50%, -50%); pointer-events: none; z-index: 0; }
        .star-ray { position: absolute; width: 2px; top: 50%; left: 50%; transform-origin: center top; background: linear-gradient(to bottom, rgba(255,255,255,0.7), transparent); opacity: 0; animation: rayBurst 1.2s ease-out forwards; }
        @keyframes rayBurst { 0% { opacity: 0; height: 0; } 20% { opacity: 1; } 100% { opacity: 0; height: 120px; } }
        .scan-overlay .skip-btn { position: absolute; bottom: 30px; padding: 8px 24px; background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); color: #666; border-radius: 8px; cursor: pointer; font-size: 0.8rem; transition: all 0.2s; }
        .scan-overlay .skip-btn:hover { background: rgba(255,255,255,0.15); color: #aaa; }
        .rarity-bg-common { background: radial-gradient(circle, rgba(200,200,200,0.1) 0%, transparent 70%); }
        .rarity-bg-uncommon { background: radial-gradient(circle, rgba(78,205,196,0.15) 0%, transparent 70%); }
        .rarity-bg-rare { background: radial-gradient(circle, rgba(59,130,246,0.2) 0%, transparent 70%); }
        .rarity-bg-epic { background: radial-gradient(circle, rgba(168,85,247,0.25) 0%, transparent 70%); }
        .rarity-bg-legendary { background: radial-gradient(circle, rgba(245,158,11,0.3) 0%, transparent 70%); }
        /* === MONSTER DETAIL MODAL === */
        .detail-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(5,5,15,0.92); z-index: 1001; display: flex; align-items: flex-start; justify-content: center; overflow-y: auto; padding: 20px 12px; animation: panelFadeIn 0.25s ease-out; }
        .detail-panel { background: linear-gradient(160deg, #16213e, #0f0f23); border: 1px solid #333; border-radius: 20px; max-width: 500px; width: 100%; padding: 0; overflow: hidden; position: relative; }
        .detail-header { padding: 16px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #222; }
        .detail-close { background: none; border: 1px solid #444; color: #888; width: 32px; height: 32px; border-radius: 50%; cursor: pointer; font-size: 1.1rem; display: flex; align-items: center; justify-content: center; transition: all 0.2s; }
        .detail-close:hover { border-color: #e94560; color: #e94560; }
        .detail-visual { text-align: center; padding: 20px 20px 10px; position: relative; }
        .detail-visual .monster-svg-wrap { animation: float 3s ease-in-out infinite; }
        .detail-visual .monster-svg-wrap svg { width: 120px; height: 120px; filter: drop-shadow(0 6px 16px rgba(0,0,0,0.5)); }
        .detail-body { padding: 0 20px 20px; }
        .detail-name { font-size: 1.4rem; font-weight: 800; text-align: center; margin-bottom: 2px; }
        .detail-types { text-align: center; font-size: 0.8rem; color: #aaa; margin-bottom: 8px; }
        .detail-rarity-row { text-align: center; margin-bottom: 12px; }
        .detail-story { background: linear-gradient(135deg, rgba(233,69,96,0.08), rgba(240,147,251,0.06)); border: 1px solid rgba(233,69,96,0.15); border-radius: 12px; padding: 14px; margin-bottom: 14px; font-size: 0.8rem; line-height: 1.7; color: #ccc; font-style: italic; position: relative; }
        .detail-story::before { content: '"'; position: absolute; top: 4px; left: 10px; font-size: 2rem; color: rgba(233,69,96,0.3); font-family: Georgia, serif; }
        .detail-stat-bars { margin-bottom: 14px; }
        .stat-bar-row { display: flex; align-items: center; gap: 8px; margin: 6px 0; }
        .stat-bar-label { font-size: 0.7rem; color: #888; width: 32px; text-align: right; font-weight: 600; }
        .stat-bar-val { font-size: 0.75rem; font-weight: 700; width: 30px; text-align: right; }
        .stat-bar-track { flex: 1; height: 8px; background: #1a1a2e; border-radius: 4px; overflow: hidden; }
        .stat-bar-fill { height: 100%; border-radius: 4px; transition: width 0.6s ease-out; }
        .stat-bar-fill.hp { background: linear-gradient(90deg, #4ecdc4, #7ee8fa); }
        .stat-bar-fill.atk { background: linear-gradient(90deg, #e94560, #f093fb); }
        .stat-bar-fill.def { background: linear-gradient(90deg, #3b82f6, #60a5fa); }
        .stat-bar-fill.spd { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
        .stat-bar-fill.spc { background: linear-gradient(90deg, #a855f7, #c084fc); }
        .detail-info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 14px; }
        .detail-info-item { background: #1a1a2e; border-radius: 8px; padding: 8px 10px; }
        .detail-info-item .dii-label { font-size: 0.62rem; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }
        .detail-info-item .dii-val { font-size: 0.82rem; font-weight: 600; margin-top: 2px; }
        .detail-trait { text-align: center; padding: 8px; background: rgba(233,69,96,0.08); border-radius: 8px; margin-bottom: 14px; }
        .detail-trait .dt-label { font-size: 0.65rem; color: #888; text-transform: uppercase; }
        .detail-trait .dt-val { font-size: 0.9rem; color: #e94560; font-weight: 600; font-style: italic; }
        /* Barcode Product Info */
        .barcode-info { background: linear-gradient(135deg, rgba(78,205,196,0.08), rgba(126,232,250,0.04)); border: 1px solid rgba(78,205,196,0.15); border-radius: 12px; padding: 14px; margin-bottom: 14px; }
        .barcode-info-title { font-size: 0.72rem; color: #4ecdc4; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
        .barcode-info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
        .barcode-info-item { font-size: 0.78rem; }
        .barcode-info-item .bil { color: #666; font-size: 0.65rem; }
        .barcode-info-item .biv { color: #ddd; font-weight: 500; }
        .barcode-product-name { font-size: 0.95rem; font-weight: 700; color: #fff; margin-bottom: 8px; grid-column: 1 / -1; }
        /* Enhanced Collection/Dex */
        .dex-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .dex-filters { display: flex; gap: 4px; flex-wrap: wrap; }
        .dex-filter { padding: 4px 10px; border-radius: 6px; font-size: 0.68rem; font-weight: 600; cursor: pointer; border: 1px solid #333; background: #16213e; color: #888; transition: all 0.2s; }
        .dex-filter.active { border-color: #e94560; color: #e94560; background: rgba(233,69,96,0.1); }
        .dex-filter:hover { border-color: #555; color: #aaa; }
        .dex-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
        .dex-card { background: #16213e; border-radius: 12px; padding: 12px; text-align: center; cursor: pointer; transition: all 0.25s; border: 1px solid #222; position: relative; overflow: hidden; }
        .dex-card:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(0,0,0,0.3); border-color: #444; }
        .dex-card.r-Common { border-left: 3px solid #555; }
        .dex-card.r-Uncommon { border-left: 3px solid #4ecdc4; }
        .dex-card.r-Rare { border-left: 3px solid #3b82f6; }
        .dex-card.r-Epic { border-left: 3px solid #a855f7; }
        .dex-card.r-Legendary { border-left: 3px solid #f59e0b; background: linear-gradient(135deg, #16213e, #1f1a10); }
        .dex-card .dex-icon { margin-bottom: 4px; }
        .dex-card .dex-icon .monster-svg-wrap { animation: none; }
        .dex-card .dex-icon .monster-svg-wrap svg { width: 48px; height: 48px; }
        .dex-card .dex-name { font-size: 0.8rem; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .dex-card .dex-sub { font-size: 0.65rem; color: #888; }
        .dex-card .dex-rarity { font-size: 0.6rem; }
        .dex-empty { grid-column: 1 / -1; text-align: center; padding: 40px 20px; color: #555; }
        /* Scan barcode info section */
        .scan-barcode-info { background: #16213e; border-radius: 12px; padding: 12px; margin-top: 8px; }
        .monster-card { cursor: pointer; }
        .monster-card:hover { filter: brightness(1.05); }

        /* === NEW UI FLAG === */
        .old-tabs-hidden .tabs { display: none !important; }
        .old-tabs-hidden .header { display: none !important; }

        /* === LANDSCAPE VIEW === */
        #landscape-view {
            position: fixed; top: 0; left: 0; right: 0; bottom: 0; z-index: 200;
            overflow: hidden; transition: opacity 0.6s ease, transform 0.6s ease;
        }
        #landscape-view.hidden { opacity: 0; pointer-events: none; transform: scale(1.1); }
        .sky-layer {
            position: absolute; top: 0; left: 0; right: 0; bottom: 0;
            background: linear-gradient(180deg, #87CEEB 0%, #B0E0F0 40%, #E8F4E8 70%, #C8E6C8 100%);
            animation: dayCycle 120s ease-in-out infinite;
        }
        @keyframes dayCycle {
            0%,100% { background: linear-gradient(180deg, #87CEEB 0%, #B0E0F0 40%, #E8F4E8 70%, #C8E6C8 100%); }
            25% { background: linear-gradient(180deg, #FFB347 0%, #FF8C5A 30%, #FFD194 55%, #E8DCC8 100%); }
            40% { background: linear-gradient(180deg, #1a1a3e 0%, #2C3E6B 35%, #0A1428 70%, #0A1020 100%); }
            60% { background: linear-gradient(180deg, #1a1a3e 0%, #2C3E6B 35%, #0A1428 70%, #0A1020 100%); }
            75% { background: linear-gradient(180deg, #FFB5C2 0%, #FFD194 35%, #B0E0F0 70%, #E8F4E8 100%); }
        }
        /* Sun/Moon */
        .celestial-body {
            position: absolute; width: 60px; height: 60px; border-radius: 50%;
            top: 12%; left: 15%; z-index: 1;
            background: radial-gradient(circle, #FFFDE7 30%, #FFD54F 70%, transparent 100%);
            box-shadow: 0 0 40px rgba(255,213,79,0.5), 0 0 80px rgba(255,213,79,0.2);
            animation: celestialFloat 8s ease-in-out infinite;
        }
        @keyframes celestialFloat { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
        /* Clouds */
        .cloud {
            position: absolute; z-index: 2;
            background: rgba(255,255,255,0.85);
            border-radius: 50px;
        }
        .cloud::before, .cloud::after {
            content: ''; position: absolute; background: inherit; border-radius: 50%;
        }
        .cloud-1 { width: 80px; height: 28px; top: 8%; animation: cloudDrift 60s linear infinite; }
        .cloud-1::before { width: 40px; height: 40px; top: -20px; left: 12px; }
        .cloud-1::after { width: 30px; height: 30px; top: -12px; right: 10px; }
        .cloud-2 { width: 60px; height: 22px; top: 14%; animation: cloudDrift 45s linear infinite; animation-delay: -15s; }
        .cloud-2::before { width: 32px; height: 32px; top: -16px; left: 8px; }
        .cloud-2::after { width: 22px; height: 22px; top: -8px; right: 6px; }
        .cloud-3 { width: 90px; height: 30px; top: 6%; animation: cloudDrift 80s linear infinite; animation-delay: -30s; }
        .cloud-3::before { width: 46px; height: 46px; top: -24px; left: 16px; }
        .cloud-3::after { width: 34px; height: 34px; top: -14px; right: 12px; }
        @keyframes cloudDrift { 0% { left: -20%; } 100% { left: 110%; } }
        /* Mountains */
        .mountain-layer { position: absolute; bottom: 30%; left: 0; right: 0; height: 35%; z-index: 3; }
        .mountain-far { position: absolute; bottom: 0; width: 100%; }
        .mountain-near { position: absolute; bottom: -5%; width: 100%; }
        /* Midground trees */
        .midground { position: absolute; bottom: 22%; left: 0; right: 0; height: 20%; z-index: 4; }
        /* Road */
        .road-layer {
            position: absolute; bottom: 8%; left: 0; right: 0; height: 22%; z-index: 5;
            background: linear-gradient(180deg, #7BC67E 0%, #6ab86a 30%, #8B7355 40%, #9A8866 45%, #8B7355 50%, #7BC67E 52%, #5da55d 100%);
        }
        .road-line {
            position: absolute; top: 44%; left: 0; right: 0; height: 3px;
            background: repeating-linear-gradient(90deg, #FFD54F 0, #FFD54F 20px, transparent 20px, transparent 40px);
            opacity: 0.6;
        }
        /* Bus Exterior */
        .bus-exterior {
            position: absolute; bottom: 14%; left: 50%; transform: translateX(-50%);
            z-index: 10; cursor: pointer; transition: transform 0.3s ease;
            animation: busIdle 4s ease-in-out infinite;
        }
        .bus-exterior:hover { transform: translateX(-50%) scale(1.03); }
        .bus-exterior:active { transform: translateX(-50%) scale(0.98); }
        @keyframes busIdle { 0%,100% { transform: translateX(-50%) translateY(0); } 50% { transform: translateX(-50%) translateY(-4px); } }
        .bus-exterior svg { filter: drop-shadow(0 8px 20px rgba(0,0,0,0.3)); }
        /* Bus entrance animation */
        @keyframes busEnter { 0% { left: -30%; opacity: 0; } 60% { opacity: 1; } 100% { left: 50%; } }
        .bus-entering { animation: busEnter 1.5s ease-out forwards !important; }
        /* Foreground */
        .foreground { position: absolute; bottom: 0; left: 0; right: 0; height: 12%; z-index: 11; pointer-events: none; }
        /* Landscape creatures */
        .landscape-creatures { position: absolute; bottom: 20%; left: 0; right: 0; height: 10%; z-index: 9; pointer-events: none; }
        .landscape-creature {
            position: absolute; animation: creatureWander 6s ease-in-out infinite alternate;
            filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
        }
        @keyframes creatureWander { 0% { transform: translateY(0) translateX(0); } 100% { transform: translateY(-6px) translateX(10px); } }
        /* Landscape UI overlay */
        .landscape-ui {
            position: absolute; top: 0; left: 0; right: 0; z-index: 20;
            padding: 16px; display: flex; flex-direction: column; align-items: center;
        }
        .ls-title {
            font-size: 2rem; font-weight: 800;
            background: linear-gradient(135deg, #fff, #FFD194, #fff);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            text-shadow: none; letter-spacing: -0.5px; margin-bottom: 4px;
            filter: drop-shadow(0 2px 6px rgba(0,0,0,0.3));
        }
        .ls-subtitle { font-size: 0.65rem; color: rgba(255,255,255,0.7); letter-spacing: 4px; text-transform: uppercase; }
        .ls-stats {
            display: flex; gap: 8px; margin-top: 12px;
        }
        .ls-stat {
            background: rgba(0,0,0,0.25); backdrop-filter: blur(8px);
            padding: 6px 14px; border-radius: 20px; font-size: 0.75rem; color: #fff;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .ls-stat .stat-val { font-weight: 700; }
        .ls-bottom-hint {
            position: absolute; bottom: 3%; left: 50%; transform: translateX(-50%);
            z-index: 20; text-align: center;
        }
        .ls-tap-hint {
            font-size: 0.7rem; color: rgba(255,255,255,0.6);
            animation: hintPulse 2s ease-in-out infinite;
            background: rgba(0,0,0,0.2); padding: 6px 16px; border-radius: 20px;
            backdrop-filter: blur(4px);
        }
        @keyframes hintPulse { 0%,100% { opacity: 0.6; } 50% { opacity: 1; } }
        /* Smoke particles */
        .smoke-particle {
            position: absolute; width: 8px; height: 8px; border-radius: 50%;
            background: rgba(200,200,200,0.5); animation: smokeRise 3s ease-out infinite;
        }
        @keyframes smokeRise {
            0% { transform: translateY(0) scale(1); opacity: 0.5; }
            100% { transform: translateY(-40px) translateX(10px) scale(2.5); opacity: 0; }
        }
        /* Wheel animation */
        @keyframes wheelSpin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        /* Stars (night) */
        .stars-layer { position: absolute; top: 0; left: 0; right: 0; bottom: 50%; z-index: 1; pointer-events: none; }
        .star {
            position: absolute; width: 2px; height: 2px; background: #fff; border-radius: 50%;
            animation: starTwinkle 3s ease-in-out infinite;
        }
        @keyframes starTwinkle { 0%,100% { opacity: 0.2; } 50% { opacity: 0.8; } }

        /* === BUS INTERIOR VIEW === */
        #bus-interior-view {
            position: fixed; top: 0; left: 0; right: 0; bottom: 0; z-index: 200;
            background: linear-gradient(180deg, #87CEEB 0%, #B0D8F0 30%, #DDD0B8 50%, #D4C4A8 100%);
            display: none; flex-direction: column; overflow: hidden;
        }
        #bus-interior-view.active { display: flex; animation: viewFadeIn 0.5s ease-out; }
        @keyframes viewFadeIn { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
        .bi-header {
            display: flex; align-items: center; justify-content: space-between;
            padding: 12px 16px; background: rgba(20,18,40,0.85);
            backdrop-filter: blur(12px); z-index: 10;
        }
        .bi-back-btn {
            background: none; border: 1px solid rgba(255,255,255,0.2);
            color: #ccc; padding: 6px 12px; border-radius: 8px; font-size: 0.8rem;
            cursor: pointer; transition: all 0.2s;
        }
        .bi-back-btn:hover { border-color: #fff; color: #fff; }
        .bi-title { font-size: 1rem; font-weight: 700; color: #e8e8f0; }
        .bi-collect-btn {
            padding: 6px 14px; background: linear-gradient(135deg, #4ecdc4, #2ab7a9);
            color: #1a1a2e; border: none; border-radius: 8px; font-size: 0.75rem;
            font-weight: 700; cursor: pointer; transition: all 0.2s;
        }
        .bi-collect-btn:hover { transform: scale(1.05); box-shadow: 0 2px 10px rgba(78,205,196,0.3); }
        /* Cross Section Container */
        .bus-cross-section {
            flex: 1; display: flex; flex-direction: column; align-items: center;
            justify-content: center; padding: 10px 16px; overflow-y: auto;
        }
        .cs-bus-body {
            width: 100%; max-width: 380px; position: relative;
        }
        /* Roof */
        .cs-roof {
            background: linear-gradient(180deg, #C0704A, #E8734A);
            height: 20px; border-radius: 30px 30px 0 0; position: relative;
            border: 2px solid #9A5A3A; border-bottom: none;
        }
        .cs-chimney {
            position: absolute; top: -16px; right: 25%; width: 14px; height: 16px;
            background: #666; border-radius: 2px 2px 0 0;
        }
        /* Floor containers */
        .cs-floor {
            background: linear-gradient(180deg, #E8DCC8, #DDD0B8);
            border-left: 3px solid #9A7A50; border-right: 3px solid #9A7A50;
            padding: 6px 8px; position: relative;
        }
        .cs-floor:last-of-type { border-bottom: 3px solid #9A7A50; }
        .cs-floor-label {
            position: absolute; left: -28px; top: 50%; transform: translateY(-50%);
            font-size: 0.65rem; font-weight: 700; color: #9A7A50;
            background: rgba(255,255,255,0.7); padding: 2px 4px; border-radius: 4px;
        }
        .cs-floor-divider {
            height: 2px; background: linear-gradient(90deg, #9A7A50, #C4A878, #9A7A50);
        }
        .cs-slots { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
        /* Individual slot */
        .cs-slot {
            background: rgba(255,255,255,0.4); border: 2px dashed rgba(154,122,80,0.4);
            border-radius: 8px; padding: 8px 4px; text-align: center; min-height: 90px;
            cursor: pointer; transition: all 0.25s; display: flex; flex-direction: column;
            justify-content: center; align-items: center; position: relative;
        }
        .cs-slot:hover { background: rgba(255,255,255,0.6); border-color: #E8734A; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
        .cs-slot.has-room {
            border-style: solid; border-color: rgba(154,122,80,0.6);
            background: rgba(255,255,255,0.5);
        }
        .cs-slot .cs-room-emoji { font-size: 1.3rem; }
        .cs-slot .cs-room-name { font-size: 0.65rem; font-weight: 600; color: #5A4A30; margin-top: 2px; }
        .cs-slot .cs-room-level { font-size: 0.55rem; color: #9A7A50; }
        .cs-slot .cs-creature-mini { margin-top: 3px; }
        .cs-slot .cs-creature-mini svg { filter: drop-shadow(0 1px 2px rgba(0,0,0,0.2)); }
        .cs-slot .cs-affinity {
            font-size: 0.5rem; padding: 1px 5px; border-radius: 3px;
            display: inline-block; margin-top: 2px;
        }
        .cs-slot .cs-affinity.grade-S { background: linear-gradient(135deg, #d97706, #fbbf24); color: #fff; }
        .cs-slot .cs-affinity.grade-A { background: #7c3aed; color: #fff; }
        .cs-slot .cs-affinity.grade-B { background: #1d4ed8; color: #fff; }
        .cs-slot .cs-affinity.grade-C { background: #888; color: #fff; }
        .cs-slot .cs-prod { font-size: 0.5rem; color: #B8860B; margin-top: 1px; }
        .cs-slot .cs-empty { font-size: 0.7rem; color: #9A7A50; }
        .cs-slot .cs-empty-plus { font-size: 1.5rem; color: #C4A878; line-height: 1; }
        /* Room type backgrounds */
        .cs-slot.room-gold_mine { background: linear-gradient(180deg, rgba(255,215,0,0.15), rgba(255,255,255,0.4)); }
        .cs-slot.room-energy_gen { background: linear-gradient(180deg, rgba(0,206,209,0.15), rgba(255,255,255,0.4)); }
        .cs-slot.room-exp_library { background: linear-gradient(180deg, rgba(168,85,247,0.1), rgba(255,255,255,0.4)); }
        .cs-slot.room-training { background: linear-gradient(180deg, rgba(233,69,96,0.1), rgba(255,255,255,0.4)); }
        .cs-slot.room-arena { background: linear-gradient(180deg, rgba(255,107,138,0.12), rgba(255,255,255,0.4)); }
        .cs-slot.room-evo_lab { background: linear-gradient(180deg, rgba(126,232,250,0.12), rgba(255,255,255,0.4)); }
        .cs-slot.room-radar { background: linear-gradient(180deg, rgba(59,130,246,0.1), rgba(255,255,255,0.4)); }
        .cs-slot.room-expedition_base { background: linear-gradient(180deg, rgba(123,198,126,0.15), rgba(255,255,255,0.4)); }
        .cs-slot.room-warehouse { background: linear-gradient(180deg, rgba(205,127,50,0.1), rgba(255,255,255,0.4)); }
        /* Locked floor */
        .cs-floor.locked {
            opacity: 0.5; position: relative;
        }
        .cs-floor.locked::after {
            content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.3); border-radius: 4px; z-index: 1;
        }
        .cs-lock-overlay {
            position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%);
            z-index: 2; text-align: center; color: #fff;
        }
        .cs-lock-overlay .lock-icon { font-size: 1.5rem; }
        .cs-lock-overlay .lock-text { font-size: 0.65rem; }
        /* Wheels */
        .cs-wheels {
            display: flex; justify-content: space-around; padding: 0 20%;
            margin-top: -2px; position: relative; z-index: 2;
        }
        .cs-wheel {
            width: 28px; height: 28px; background: #333;
            border: 3px solid #555; border-radius: 50%;
            position: relative;
        }
        .cs-wheel::after {
            content: '+'; position: absolute; top: 50%; left: 50%;
            transform: translate(-50%,-50%); color: #888; font-size: 0.7rem; font-weight: 700;
        }
        /* Resource bar */
        .bi-resource-bar {
            display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;
            padding: 8px 16px; background: rgba(0,0,0,0.15);
            font-size: 0.75rem;
        }
        .bi-res-item { color: #FFD54F; font-weight: 600; }
        .bi-res-time { color: rgba(255,255,255,0.5); font-size: 0.65rem; }

        /* === BOTTOM NAV === */
        .bottom-nav {
            display: flex; background: rgba(20,18,40,0.92);
            backdrop-filter: blur(12px); border-top: 1px solid rgba(255,255,255,0.05);
            z-index: 10; padding: 4px 0;
        }
        .bottom-nav .bn-item {
            flex: 1; text-align: center; padding: 8px 4px; cursor: pointer;
            transition: all 0.2s; color: #888;
        }
        .bottom-nav .bn-item:hover { color: #ccc; }
        .bottom-nav .bn-item.active { color: #ff6b8a; }
        .bottom-nav .bn-icon { font-size: 1.1rem; display: block; }
        .bottom-nav .bn-label { font-size: 0.55rem; display: block; margin-top: 2px; letter-spacing: 0.5px; }

        /* === FEATURE OVERLAY === */
        .feature-overlay {
            position: fixed; top: 0; left: 0; right: 0; bottom: 0; z-index: 300;
            background: rgba(26,20,50,0.97); display: none;
            flex-direction: column; overflow: hidden;
            transform: translateY(100%); transition: transform 0.35s ease-out;
        }
        .feature-overlay.active { display: flex; transform: translateY(0); animation: featureSlideUp 0.35s ease-out; }
        @keyframes featureSlideUp { from { transform: translateY(100%); } to { transform: translateY(0); } }
        .fo-header {
            display: flex; align-items: center; justify-content: space-between;
            padding: 12px 16px; border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .fo-close {
            background: none; border: 1px solid rgba(255,255,255,0.2);
            color: #ccc; padding: 6px 12px; border-radius: 8px; font-size: 0.8rem;
            cursor: pointer; transition: all 0.2s;
        }
        .fo-close:hover { border-color: #fff; color: #fff; }
        .fo-title { font-size: 1rem; font-weight: 700; color: #e8e8f0; }
        .fo-body { flex: 1; overflow-y: auto; padding: 12px; }

        /* Upgrade floor button in cross section */
        .cs-upgrade-floor {
            text-align: center; margin-top: 8px;
        }
        .cs-upgrade-floor button {
            padding: 8px 20px; background: linear-gradient(135deg, #f093fb, #e94560);
            color: white; border: none; border-radius: 8px; font-size: 0.78rem;
            font-weight: 700; cursor: pointer; transition: all 0.2s;
        }
        .cs-upgrade-floor button:hover { transform: scale(1.05); box-shadow: 0 4px 14px rgba(240,147,251,0.3); }
    </style>
</head>
<body class="old-tabs-hidden">
    <!-- === LANDSCAPE VIEW === -->
    <div id="landscape-view">
        <div class="sky-layer">
            <div class="celestial-body"></div>
            <div class="stars-layer" id="starsLayer"></div>
        </div>
        <div class="cloud cloud-1"></div>
        <div class="cloud cloud-2"></div>
        <div class="cloud cloud-3"></div>
        <div class="mountain-layer">
            <svg class="mountain-far" viewBox="0 0 800 200" preserveAspectRatio="none" style="height:100%;opacity:0.7">
                <polygon points="0,200 100,60 200,140 300,30 450,120 550,50 700,130 800,70 800,200" fill="#4A5868"/>
                <polygon points="0,200 50,100 180,160 280,80 400,150 520,70 650,140 750,90 800,200" fill="#5A6878" opacity="0.7"/>
            </svg>
            <svg class="mountain-near" viewBox="0 0 800 180" preserveAspectRatio="none" style="height:90%">
                <polygon points="0,180 80,50 160,110 260,20 380,90 480,40 600,100 700,30 800,80 800,180" fill="#5A7A5A"/>
                <polygon points="0,180 120,70 220,130 340,50 460,110 580,60 680,120 800,50 800,180" fill="#6A8A6A" opacity="0.8"/>
            </svg>
        </div>
        <div class="midground" id="midgroundTrees"></div>
        <div class="road-layer"><div class="road-line"></div></div>
        <div class="bus-exterior" id="busExterior" onclick="enterBus()">
            <svg viewBox="0 0 240 160" width="200" height="133" xmlns="http://www.w3.org/2000/svg">
                <!-- Bus body -->
                <rect x="20" y="20" width="200" height="120" rx="12" fill="#E8734A"/>
                <rect x="20" y="20" width="200" height="120" rx="12" fill="url(#busShine)" opacity="0.3"/>
                <defs>
                    <linearGradient id="busShine" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="#fff" stop-opacity="0.3"/>
                        <stop offset="100%" stop-color="#000" stop-opacity="0.1"/>
                    </linearGradient>
                </defs>
                <!-- Floor lines -->
                <line x1="25" y1="62" x2="215" y2="62" stroke="#C0604A" stroke-width="1.5"/>
                <line x1="25" y1="98" x2="215" y2="98" stroke="#C0604A" stroke-width="1.5"/>
                <!-- 3F windows -->
                <rect x="35" y="28" width="28" height="26" rx="4" fill="#87CEEB" opacity="0.7"/>
                <rect x="70" y="28" width="28" height="26" rx="4" fill="#87CEEB" opacity="0.7"/>
                <rect x="105" y="28" width="28" height="26" rx="4" fill="#87CEEB" opacity="0.7"/>
                <rect x="145" y="28" width="50" height="26" rx="4" fill="#87CEEB" opacity="0.6"/>
                <!-- 2F windows -->
                <rect x="35" y="68" width="28" height="24" rx="4" fill="#87CEEB" opacity="0.65"/>
                <rect x="70" y="68" width="28" height="24" rx="4" fill="#87CEEB" opacity="0.65"/>
                <rect x="105" y="68" width="28" height="24" rx="4" fill="#87CEEB" opacity="0.65"/>
                <rect x="145" y="68" width="50" height="24" rx="4" fill="#87CEEB" opacity="0.55"/>
                <!-- 1F windows -->
                <rect x="35" y="104" width="28" height="24" rx="4" fill="#87CEEB" opacity="0.6"/>
                <rect x="70" y="104" width="28" height="24" rx="4" fill="#87CEEB" opacity="0.6"/>
                <rect x="105" y="104" width="28" height="24" rx="4" fill="#87CEEB" opacity="0.6"/>
                <!-- Door -->
                <rect x="150" y="100" width="40" height="36" rx="4" fill="#C0604A"/>
                <rect x="154" y="104" width="32" height="28" rx="3" fill="#A0D8EF" opacity="0.5"/>
                <!-- Roof details -->
                <rect x="18" y="16" width="204" height="8" rx="4" fill="#C0604A"/>
                <!-- Chimney -->
                <rect x="175" y="2" width="12" height="18" rx="2" fill="#666"/>
                <g id="busSmoke"></g>
                <!-- Wheels -->
                <circle cx="60" cy="142" r="14" fill="#333" stroke="#555" stroke-width="3"/>
                <circle cx="60" cy="142" r="4" fill="#888"/>
                <circle cx="180" cy="142" r="14" fill="#333" stroke="#555" stroke-width="3"/>
                <circle cx="180" cy="142" r="4" fill="#888"/>
                <!-- Headlight -->
                <ellipse cx="222" cy="118" rx="5" ry="8" fill="#FFD54F" opacity="0.8"/>
                <!-- BarcodeQuest sign -->
                <rect x="55" y="5" width="80" height="14" rx="3" fill="rgba(0,0,0,0.3)"/>
                <text x="95" y="15" text-anchor="middle" fill="#FFD194" font-size="8" font-weight="700" font-family="Poppins,sans-serif">TRAVEL BUS</text>
            </svg>
        </div>
        <div class="landscape-creatures" id="landscapeCreatures"></div>
        <div class="foreground" id="foregroundLayer"></div>
        <!-- UI Overlay -->
        <div class="landscape-ui">
            <div class="ls-title">BarcodeQuest</div>
            <div class="ls-subtitle">Travel Bus Adventure</div>
            <div class="ls-stats">
                <div class="ls-stat"><span class="stat-val" id="lsLevel">Lv.1</span></div>
                <div class="ls-stat"><span class="stat-val" id="lsGold">1,000G</span></div>
                <div class="ls-stat"><span class="stat-val" id="lsEnergy">100E</span></div>
            </div>
        </div>
        <div class="ls-bottom-hint">
            <div class="ls-tap-hint">Tap the bus to board</div>
        </div>
    </div>

    <!-- === BUS INTERIOR VIEW === -->
    <div id="bus-interior-view">
        <div class="bi-header">
            <button class="bi-back-btn" onclick="exitBus()">&#8592; Exit</button>
            <span class="bi-title">Travel Bus</span>
            <button class="bi-collect-btn" onclick="busCollect()">Collect</button>
        </div>
        <div class="bi-resource-bar" id="biResourceBar">
            <span class="bi-res-item">Loading...</span>
        </div>
        <div class="bus-cross-section">
            <div class="cs-bus-body">
                <div class="cs-roof"><div class="cs-chimney"></div></div>
                <div class="cs-floor" id="csFloor3" style="display:none">
                    <span class="cs-floor-label">3F</span>
                    <div class="cs-slots" id="csSlots3"></div>
                </div>
                <div class="cs-floor-divider" id="csDivider23" style="display:none"></div>
                <div class="cs-floor" id="csFloor2" style="display:none">
                    <span class="cs-floor-label">2F</span>
                    <div class="cs-slots" id="csSlots2"></div>
                </div>
                <div class="cs-floor-divider" id="csDivider12" style="display:none"></div>
                <div class="cs-floor" id="csFloor1">
                    <span class="cs-floor-label">1F</span>
                    <div class="cs-slots" id="csSlots1"></div>
                </div>
                <div class="cs-wheels">
                    <div class="cs-wheel"></div>
                    <div class="cs-wheel"></div>
                    <div class="cs-wheel"></div>
                    <div class="cs-wheel"></div>
                </div>
                <div class="cs-upgrade-floor" id="csUpgradeFloor"></div>
            </div>
        </div>
        <div class="bottom-nav">
            <div class="bn-item" onclick="openFeature('scan')"><span class="bn-icon">&#x1F4F7;</span><span class="bn-label">Scan</span></div>
            <div class="bn-item" onclick="openFeature('battle')"><span class="bn-icon">&#x2694;</span><span class="bn-label">Battle</span></div>
            <div class="bn-item" onclick="openFeature('expedition')"><span class="bn-icon">&#x1F30D;</span><span class="bn-label">Explore</span></div>
            <div class="bn-item" onclick="openFeature('collection')"><span class="bn-icon">&#x1F4D6;</span><span class="bn-label">Dex</span></div>
            <div class="bn-item" onclick="openFeature('quest')"><span class="bn-icon">&#x1F4DC;</span><span class="bn-label">Quest</span></div>
        </div>
    </div>

    <!-- === FEATURE OVERLAY === -->
    <div id="featureOverlay" class="feature-overlay">
        <div class="fo-header">
            <button class="fo-close" onclick="closeFeature()">&#8592; Back</button>
            <span class="fo-title" id="foTitle">Feature</span>
            <div style="width:60px"></div>
        </div>
        <div class="fo-body" id="foBody"></div>
    </div>

    <div class="header">
        <h1>BarcodeQuest</h1>
        <div class="player-info">
            <span id="pLevel">Lv.1</span>
            <span id="pGold">1000G</span>
            <span id="pEnergy">100E</span>
        </div>
    </div>
    <div class="container">
        <div class="tabs">
            <div class="tab active" onclick="showTab('scan')">Scan</div>
            <div class="tab" onclick="showTab('battle')">Battle</div>
            <div class="tab" onclick="showTab('expedition')">Explore</div>
            <div class="tab" onclick="showTab('collection')">Dex</div>
            <div class="tab" onclick="showTab('quest')">Quest</div>
            <div class="tab" onclick="showTab('bus')">Bus</div>
        </div>

        <!-- SCAN TAB -->
        <div class="panel active" id="panel-scan">
            <!-- Hero Welcome Section -->
            <div class="hero-section" id="heroSection">
                <div class="hero-particles" id="heroParticles"></div>
                <!-- Animated SVG creatures -->
                <div class="hero-creature-stage" id="heroCreatureStage"></div>

                <div class="hero-logo-wrap">
                    <div class="hero-logo">BarcodeQuest</div>
                    <div class="hero-logo-sub">Creature Collection RPG</div>
                </div>

                <div class="hero-lore">
                    <div class="hero-tagline">모든 상품에는 잠든 <em>크리처</em>가 숨어있습니다<br><span class="lore-glow">바코드를 스캔</span>하여 그들을 깨워주세요</div>
                    <div class="hero-lore-divider"></div>
                </div>

                <!-- Quick Stats -->
                <div class="hero-stats">
                    <div class="hero-stat">
                        <span class="hs-icon">⚔️</span>
                        <span class="hs-num level" id="hsLevel">1</span>
                        <span class="hs-label">Level</span>
                    </div>
                    <div class="hero-stat">
                        <span class="hs-icon">📖</span>
                        <span class="hs-num collection" id="hsCollection">0</span>
                        <span class="hs-label">Dex</span>
                    </div>
                    <div class="hero-stat">
                        <span class="hs-icon">💰</span>
                        <span class="hs-num gold" id="hsGold">1,000</span>
                        <span class="hs-label">Gold</span>
                    </div>
                    <div class="hero-stat">
                        <span class="hs-icon">⚡</span>
                        <span class="hs-num energy" id="hsEnergy">100</span>
                        <span class="hs-label">Energy</span>
                    </div>
                </div>

                <!-- Recent Catches -->
                <div class="recent-catches" id="recentCatches">
                    <div class="recent-catches-title">Recent Catches</div>
                    <div class="recent-row" id="recentRow">
                        <div class="recent-empty"><span class="re-icon">🥚</span>아직 깨어난 크리처가 없습니다<div class="re-hint">아래 포탈에서 첫 바코드를 스캔해보세요</div></div>
                    </div>
                </div>
            </div>

            <!-- Summoning Portal -->
            <div class="summon-section">
                <div class="summon-label">Summoning Portal</div>
                <div class="scan-portal">
                    <div class="scan-portal-bg"></div>
                    <div class="scan-portal-ring"></div>
                    <div class="scan-portal-ring"></div>
                    <div class="scan-portal-ring"></div>
                    <div class="scan-portal-ring"></div>
                    <div class="scan-portal-runes">
                        <div class="scan-portal-rune">◆</div>
                        <div class="scan-portal-rune">✦</div>
                        <div class="scan-portal-rune">◇</div>
                        <div class="scan-portal-rune">✧</div>
                        <div class="scan-portal-rune">◈</div>
                        <div class="scan-portal-rune">✦</div>
                    </div>
                    <div class="scan-portal-dots">
                        <div class="scan-portal-dot"></div>
                        <div class="scan-portal-dot"></div>
                        <div class="scan-portal-dot"></div>
                        <div class="scan-portal-dot"></div>
                        <div class="scan-portal-dot"></div>
                        <div class="scan-portal-dot"></div>
                        <div class="scan-portal-dot"></div>
                        <div class="scan-portal-dot"></div>
                    </div>
                    <div class="scan-portal-center">
                        <div class="scan-portal-orb">🔮</div>
                        <div class="scan-portal-text">Touch to Scan</div>
                    </div>
                </div>

                <div class="energy-compact">
                    <div class="energy-bar"><div class="energy-fill" id="energyBar" style="width:100%"></div></div>
                    <span class="ec-text" id="energyText">⚡ 100/100</span>
                </div>
            </div>

            <!-- Scan Actions -->
            <div class="scan-actions">
                <div class="scan-actions-title">Barcode Scan</div>
                <button class="camera-toggle" id="cameraToggle" onclick="toggleCamera()">📸 카메라로 바코드 스캔</button>
                <div id="cameraPreview"></div>
                <div id="cameraStatus"></div>
                <div class="scan-divider"><hr><span>또는 직접 입력</span><hr></div>
                <div class="scan-input-group">
                    <input class="barcode-input" id="barcodeInput" placeholder="바코드 13자리 입력" maxlength="13" />
                    <span class="scan-input-icon">📦</span>
                </div>
                <button class="scan-btn" id="scanBtn" onclick="scanBarcode()">✨ SUMMON !</button>
            </div>

            <!-- Sample Barcodes -->
            <div class="sample-section">
                <div class="scan-section-title">샘플 바코드</div>
                <div class="sample-grid">
                    <div class="sample-item" onclick="fillBarcode('8801062871247')">
                        <span class="si-flag">🇰🇷</span>
                        <span class="si-name">초코파이</span>
                        <span class="si-code">880...1247</span>
                    </div>
                    <div class="sample-item" onclick="fillBarcode('8801043150842')">
                        <span class="si-flag">🇰🇷</span>
                        <span class="si-name">신라면</span>
                        <span class="si-code">880...0842</span>
                    </div>
                    <div class="sample-item" onclick="fillBarcode('4902105231456')">
                        <span class="si-flag">🇯🇵</span>
                        <span class="si-name">Pocky</span>
                        <span class="si-code">490...1456</span>
                    </div>
                    <div class="sample-item" onclick="fillBarcode('0012345678905')">
                        <span class="si-flag">🇺🇸</span>
                        <span class="si-name">US Snack</span>
                        <span class="si-code">001...8905</span>
                    </div>
                    <div class="sample-item" onclick="fillBarcode('8801115114505')">
                        <span class="si-flag">🇰🇷</span>
                        <span class="si-name">서울우유</span>
                        <span class="si-code">880...4505</span>
                    </div>
                </div>
            </div>

            <!-- Welcome Tip (dismissible) -->
            <div class="welcome-tip" id="welcomeTip">
                <button class="tip-dismiss" onclick="document.getElementById('welcomeTip').style.display='none'">✕</button>
                <strong>모든 바코드에는 고유한 크리처가 잠들어 있습니다.</strong> 같은 바코드는 항상 같은 크리처를 깨웁니다. 카메라로 스캔하거나, 바코드 번호를 직접 입력하세요.
                <span class="tip-flavor">"수천 개의 상품 속에, 수천 개의 생명이 당신을 기다립니다."</span>
            </div>

            <div id="scanResult"></div>
            <!-- Gacha Scan Overlay -->
            <div id="scanOverlay" class="scan-overlay" style="display:none">
                <div id="scanStageContent"></div>
                <button class="skip-btn" onclick="skipScanAnimation()">SKIP</button>
            </div>
        </div>

        <!-- BATTLE TAB -->
        <div class="panel" id="panel-battle">
            <div class="battle-arena">
                <p style="margin-bottom:12px;color:#888">파티의 첫 번째 크리처로 배틀!</p>
                <button class="battle-btn" onclick="startBattle()">BATTLE START!</button>
                <div id="battleResult"></div>
                <div class="battle-log" id="battleLog" style="display:none"></div>
            </div>
        </div>

        <!-- EXPEDITION TAB -->
        <div class="panel" id="panel-expedition">
            <h3 style="margin-bottom:12px;font-size:1rem">탐험 보내기</h3>
            <div id="expeditionStatus"></div>
            <div id="expeditionZones"></div>
        </div>

        <!-- COLLECTION TAB -->
        <div class="panel" id="panel-collection">
            <div class="coll-stats" id="collStats"></div>
            <div class="dex-header">
                <div class="dex-filters" id="dexFilters">
                    <div class="dex-filter active" onclick="setDexFilter('all')">All</div>
                    <div class="dex-filter" onclick="setDexFilter('Legendary')">Legendary</div>
                    <div class="dex-filter" onclick="setDexFilter('Epic')">Epic</div>
                    <div class="dex-filter" onclick="setDexFilter('Rare')">Rare</div>
                    <div class="dex-filter" onclick="setDexFilter('Uncommon')">Uncommon</div>
                    <div class="dex-filter" onclick="setDexFilter('Common')">Common</div>
                </div>
            </div>
            <div id="collList" class="dex-grid"></div>
        </div>

        <!-- BUS TAB -->
        <div class="panel" id="panel-bus">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                <h3 style="font-size:1rem">🚌 여행 버스</h3>
                <button class="bus-collect-btn" onclick="busCollect()">자원 수령</button>
            </div>
            <div id="busAccumulated" style="margin-bottom:10px"></div>
            <div id="busFloors"></div>
            <div id="busUpgradeFloor" style="margin-top:12px"></div>
        </div>

        <!-- QUEST TAB -->
        <div class="panel" id="panel-quest">
            <h3 style="margin-bottom:8px;font-size:1rem">일일 퀘스트</h3>
            <div id="questSummary" style="margin-bottom:12px"></div>
            <div id="questList"></div>
        </div>
    </div>
    <!-- Bus Build Modal (global) -->
    <div id="busBuildModal" class="bus-modal" style="display:none;z-index:1000">
        <div class="bus-modal-content">
            <h4 style="margin-bottom:10px">방 건설</h4>
            <div id="busBuildList"></div>
            <button class="bus-modal-close" onclick="closeBusModal()">닫기</button>
        </div>
    </div>
    <!-- Bus Assign Modal (global) -->
    <div id="busAssignModal" class="bus-modal" style="display:none;z-index:1000">
        <div class="bus-modal-content">
            <h4 style="margin-bottom:10px">몬스터 배치</h4>
            <div id="busAssignList"></div>
            <button class="bus-modal-close" onclick="closeBusAssignModal()">닫기</button>
        </div>
    </div>
    <!-- Monster Detail Modal -->
    <div id="monsterDetailOverlay" class="detail-overlay" style="display:none" onclick="if(event.target===this)closeMonsterDetail()">
        <div class="detail-panel" id="monsterDetailPanel"></div>
    </div>

    <script>
        const USE_NEW_UI = true;
        const TABS = ['scan','battle','expedition','collection','quest','bus'];
        const shapes = {Dragon:'&#x1F432;',Fox:'&#x1F98A;',Bear:'&#x1F43B;',Bird:'&#x1F426;',Slime:'&#x1F47E;',Golem:'&#x1F5FF;',Ghost:'&#x1F47B;',Cat:'&#x1F431;',Wolf:'&#x1F43A;',Turtle:'&#x1F422;'};

        // === VIEW STATE SYSTEM ===
        let currentView = 'LANDSCAPE'; // LANDSCAPE | BUS_INTERIOR | FEATURE

        function switchView(view) {
            const landscape = document.getElementById('landscape-view');
            const busInterior = document.getElementById('bus-interior-view');
            const featureOverlay = document.getElementById('featureOverlay');

            landscape.classList.add('hidden');
            busInterior.classList.remove('active');
            featureOverlay.classList.remove('active');

            if (view === 'LANDSCAPE') {
                landscape.classList.remove('hidden');
            } else if (view === 'BUS_INTERIOR') {
                busInterior.classList.add('active');
            }
            currentView = view;
        }

        function enterBus() {
            const busEl = document.getElementById('busExterior');
            busEl.style.transition = 'transform 0.6s ease-in';
            busEl.style.transform = 'translateX(-50%) scale(3)';
            busEl.style.opacity = '0';
            setTimeout(() => {
                switchView('BUS_INTERIOR');
                loadBus();
                // Reset bus exterior for when we return
                busEl.style.transition = 'none';
                busEl.style.transform = '';
                busEl.style.opacity = '';
                setTimeout(() => { busEl.style.transition = ''; }, 50);
            }, 500);
        }

        function exitBus() {
            switchView('LANDSCAPE');
        }

        let activeFeatureTab = null;
        function openFeature(tab) {
            const overlay = document.getElementById('featureOverlay');
            const foBody = document.getElementById('foBody');
            const foTitle = document.getElementById('foTitle');
            const titles = {scan:'Scan',battle:'Battle',expedition:'Explore',collection:'Dex',quest:'Quest'};
            foTitle.textContent = titles[tab] || tab;

            // Return any previously moved panel
            if (activeFeatureTab) {
                const prevPanel = document.getElementById('panel-' + activeFeatureTab);
                if (prevPanel && prevPanel.parentNode === foBody) {
                    document.querySelector('.container').appendChild(prevPanel);
                }
            }

            // Move the actual panel DOM node into the overlay (preserves event handlers)
            const panel = document.getElementById('panel-' + tab);
            if (panel) {
                foBody.innerHTML = '';
                foBody.appendChild(panel);
                panel.classList.add('active');
                panel.style.display = 'block';
            }
            activeFeatureTab = tab;
            overlay.classList.add('active');
            overlay.style.display = 'flex';

            // Trigger data loading
            if (tab === 'collection') loadCollection();
            if (tab === 'expedition') loadExpedition();
            if (tab === 'quest') loadQuests();

            // Highlight bottom nav
            document.querySelectorAll('.bn-item').forEach(item => {
                const onclick = item.getAttribute('onclick') || '';
                item.classList.toggle('active', onclick.includes(tab));
            });
            currentView = 'FEATURE';
        }

        function closeFeature() {
            const overlay = document.getElementById('featureOverlay');
            overlay.classList.remove('active');
            overlay.style.display = 'none';
            // Return panel back to container
            if (activeFeatureTab) {
                const panel = document.getElementById('panel-' + activeFeatureTab);
                if (panel) {
                    panel.classList.remove('active');
                    panel.style.display = '';
                    document.querySelector('.container').appendChild(panel);
                }
                activeFeatureTab = null;
            }
            document.querySelectorAll('.bn-item').forEach(item => item.classList.remove('active'));
            currentView = 'BUS_INTERIOR';
        }

        function showTab(name) {
            document.querySelectorAll('.tab').forEach((t,i) => t.classList.toggle('active', TABS[i]===name));
            document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
            document.getElementById('panel-'+name).classList.add('active');
            if (name==='collection') loadCollection();
            if (name==='expedition') loadExpedition();
            if (name==='quest') loadQuests();
            if (name==='bus') loadBus();
        }

        // === LANDSCAPE INITIALIZATION ===
        function initLandscape() {
            initLandscapeTrees();
            initLandscapeFlowers();
            initLandscapeCreatures();
            initLandscapeStars();
            initParallax();
            // Bus entrance animation on load
            const busEl = document.getElementById('busExterior');
            busEl.classList.add('bus-entering');
            setTimeout(() => busEl.classList.remove('bus-entering'), 1600);
        }

        function initLandscapeTrees() {
            const container = document.getElementById('midgroundTrees');
            if (!container) return;
            const treeColors = ['#5A8A5A','#4A7A4A','#6B9B6B','#3A6A3A','#7BC67E'];
            let treesHtml = '<svg viewBox="0 0 800 160" preserveAspectRatio="none" style="width:100%;height:100%">';
            for (let i = 0; i < 12; i++) {
                const x = 30 + Math.random() * 740;
                const h = 40 + Math.random() * 80;
                const w = 15 + Math.random() * 25;
                const color = treeColors[Math.floor(Math.random() * treeColors.length)];
                const ty = 160 - h;
                treesHtml += '<rect x="' + (x-2) + '" y="' + (ty+h*0.6) + '" width="4" height="' + (h*0.4) + '" fill="#8B6B4A"/>';
                treesHtml += '<ellipse cx="' + x + '" cy="' + (ty+h*0.35) + '" rx="' + w + '" ry="' + (h*0.45) + '" fill="' + color + '"/>';
                treesHtml += '<ellipse cx="' + (x-w*0.3) + '" cy="' + (ty+h*0.25) + '" rx="' + (w*0.6) + '" ry="' + (h*0.3) + '" fill="' + color + '" opacity="0.7"/>';
            }
            treesHtml += '</svg>';
            container.innerHTML = treesHtml;
        }

        function initLandscapeFlowers() {
            const fg = document.getElementById('foregroundLayer');
            if (!fg) return;
            let html = '<svg viewBox="0 0 800 80" preserveAspectRatio="none" style="width:100%;height:100%">';
            // Grass base
            html += '<rect x="0" y="20" width="800" height="60" fill="#7BC67E"/>';
            html += '<rect x="0" y="15" width="800" height="15" fill="#8BD68D"/>';
            // Flowers
            const flowerColors = ['#FF6B8A','#FFD54F','#FF8C5A','#C084FC','#67E8F9','#FFFFFF'];
            for (let i = 0; i < 25; i++) {
                const x = Math.random() * 800;
                const y = 12 + Math.random() * 20;
                const color = flowerColors[Math.floor(Math.random() * flowerColors.length)];
                const size = 2 + Math.random() * 3;
                html += '<line x1="' + x + '" y1="' + (y+8) + '" x2="' + x + '" y2="' + (y+size+8) + '" stroke="#5A9A5A" stroke-width="1"/>';
                html += '<circle cx="' + x + '" cy="' + y + '" r="' + size + '" fill="' + color + '" opacity="0.8"/>';
            }
            html += '</svg>';
            fg.innerHTML = html;
        }

        function initLandscapeCreatures() {
            const container = document.getElementById('landscapeCreatures');
            if (!container) return;
            // Show 2-3 creatures from party if available
            fetch('/api/party?session=default').then(r => r.json()).then(d => {
                const party = d.party || [];
                const count = Math.min(3, party.length);
                if (count === 0) {
                    // Show default creatures
                    const defaults = [
                        {shape:'Fox', color:'#ff6b8a', x:15},
                        {shape:'Bird', color:'#67e8f9', x:75}
                    ];
                    defaults.forEach(c => {
                        const svg = generateMonsterSVG(c.shape, c.color, 'Rare');
                        const el = document.createElement('div');
                        el.className = 'landscape-creature';
                        el.style.left = c.x + '%';
                        el.style.bottom = Math.random() * 40 + '%';
                        el.innerHTML = svg.replace(/width="\\d+"/g, 'width="32"').replace(/height="\\d+"/g, 'height="32"');
                        el.style.animationDelay = (Math.random() * 3) + 's';
                        container.appendChild(el);
                    });
                } else {
                    for (let i = 0; i < count; i++) {
                        const m = party[i];
                        const colorHex = getMonsterColorHex(m.color);
                        const svg = generateMonsterSVG(m.body_shape, colorHex, m.rarity);
                        const el = document.createElement('div');
                        el.className = 'landscape-creature';
                        el.style.left = (15 + i * 30) + '%';
                        el.style.bottom = (10 + Math.random() * 50) + '%';
                        el.innerHTML = svg.replace(/width="\\d+"/g, 'width="32"').replace(/height="\\d+"/g, 'height="32"');
                        el.style.animationDelay = (i * 1.2) + 's';
                        container.appendChild(el);
                    }
                }
            }).catch(() => {});
        }

        function initLandscapeStars() {
            const container = document.getElementById('starsLayer');
            if (!container) return;
            for (let i = 0; i < 30; i++) {
                const star = document.createElement('div');
                star.className = 'star';
                star.style.left = Math.random() * 100 + '%';
                star.style.top = Math.random() * 100 + '%';
                star.style.animationDelay = (Math.random() * 5) + 's';
                star.style.animationDuration = (2 + Math.random() * 3) + 's';
                const size = 1 + Math.random() * 2;
                star.style.width = size + 'px';
                star.style.height = size + 'px';
                container.appendChild(star);
            }
        }

        function initParallax() {
            const landscape = document.getElementById('landscape-view');
            if (!landscape) return;
            let ticking = false;
            landscape.addEventListener('mousemove', (e) => {
                if (ticking) return;
                ticking = true;
                requestAnimationFrame(() => {
                    const x = (e.clientX / window.innerWidth - 0.5) * 2;
                    const y = (e.clientY / window.innerHeight - 0.5) * 2;
                    const mountains = document.querySelector('.mountain-layer');
                    const midground = document.getElementById('midgroundTrees');
                    const bus = document.getElementById('busExterior');
                    const clouds = document.querySelectorAll('.cloud');
                    if (mountains) mountains.style.transform = 'translateX(' + (x * -3) + 'px)';
                    if (midground) midground.style.transform = 'translateX(' + (x * -6) + 'px)';
                    clouds.forEach((c, i) => { c.style.marginTop = (y * (2 + i)) + 'px'; });
                    ticking = false;
                });
            });
            // Device orientation for mobile
            if (window.DeviceOrientationEvent) {
                window.addEventListener('deviceorientation', (e) => {
                    if (!e.gamma || !e.beta) return;
                    const x = e.gamma / 45;
                    const y = (e.beta - 45) / 45;
                    const mountains = document.querySelector('.mountain-layer');
                    const midground = document.getElementById('midgroundTrees');
                    if (mountains) mountains.style.transform = 'translateX(' + (x * -5) + 'px)';
                    if (midground) midground.style.transform = 'translateX(' + (x * -10) + 'px)';
                });
            }
        }

        // === BUS CROSS-SECTION RENDERER ===
        function renderBusCrossSection() {
            if (!busState) return;
            const d = busState;

            // Resource bar
            const resBar = document.getElementById('biResourceBar');
            const accItems = [];
            if (d.total_accumulated.gold) accItems.push('<span class="bi-res-item">+' + Math.floor(d.total_accumulated.gold) + 'G</span>');
            if (d.total_accumulated.exp) accItems.push('<span class="bi-res-item">+' + Math.floor(d.total_accumulated.exp) + 'EXP</span>');
            if (d.total_accumulated.energy) accItems.push('<span class="bi-res-item">+' + Math.floor(d.total_accumulated.energy) + 'E</span>');
            if (accItems.length > 0) {
                resBar.innerHTML = accItems.join(' ') + ' <span class="bi-res-time">(' + d.elapsed_hours.toFixed(1) + 'h)</span>';
            } else {
                resBar.innerHTML = '<span style="color:rgba(255,255,255,0.4)">No production yet</span>';
            }

            // Render each floor
            for (let floorNum = 1; floorNum <= 3; floorNum++) {
                const floorEl = document.getElementById('csFloor' + floorNum);
                const slotsEl = document.getElementById('csSlots' + floorNum);
                const divAbove = document.getElementById('csDivider' + (floorNum-1) + '' + floorNum) || document.getElementById('csDivider' + floorNum + '' + (floorNum+1));

                if (floorNum > d.max_floor) {
                    floorEl.style.display = 'none';
                    if (floorNum === 2) { document.getElementById('csDivider12').style.display = 'none'; }
                    if (floorNum === 3) { document.getElementById('csDivider23').style.display = 'none'; }
                    continue;
                }

                floorEl.style.display = '';
                if (floorNum === 2) document.getElementById('csDivider12').style.display = '';
                if (floorNum === 3) document.getElementById('csDivider23').style.display = '';

                const floorData = d.floors.find(f => f.floor === floorNum);
                if (!floorData) continue;

                slotsEl.innerHTML = floorData.slots.map((s, si) => {
                    if (!s.room_type) {
                        return '<div class="cs-slot" onclick="openBuildModal(' + floorNum + ',' + si + ')">' +
                            '<div class="cs-empty-plus">+</div>' +
                            '<div class="cs-empty">Build</div>' +
                            '</div>';
                    }
                    let creatureHtml = '';
                    let affHtml = '';
                    let prodHtml = '';
                    const roomClass = 'room-' + s.room_type;
                    if (s.monster) {
                        const typeColorMap = {Fire:'#DC143C',Water:'#007FFF',Nature:'#50C878',Earth:'#CD7F32',Wind:'#67E8F9',Tech:'#C0C0C0',Dark:'#36454F',Light:'#FFD700',Spirit:'#8B5CF6',Food:'#FF7F50'};
                        const colorHex = typeColorMap[s.monster.primary_type] || '#e94560';
                        const shapeKeys = Object.keys(shapes);
                        const nameHash = (s.monster.name || '').split('').reduce(function(a,c){ return a + c.charCodeAt(0); }, 0);
                        const bodyShape = shapeKeys[nameHash % shapeKeys.length];
                        const svg = generateMonsterSVG(bodyShape, colorHex, s.monster.rarity || 'Common');
                        creatureHtml = '<div class="cs-creature-mini">' + svg.replace(/width="\\d+"/g, 'width="28"').replace(/height="\\d+"/g, 'height="28"') + '</div>';
                        if (s.affinity) {
                            affHtml = '<span class="cs-affinity grade-' + s.affinity.grade + '">' + s.affinity.grade + '</span>';
                        }
                        const prods = Object.entries(s.production_per_hour || {}).map(function(e) { return e[1] + e[0].substring(0,3) + '/h'; }).join(' ');
                        if (prods) prodHtml = '<div class="cs-prod">' + prods + '</div>';
                    } else {
                        creatureHtml = '<div style="font-size:0.55rem;color:#9A7A50;cursor:pointer;margin-top:3px" onclick="event.stopPropagation();openAssignModal(' + floorNum + ',' + si + ')">+ Assign</div>';
                    }
                    return '<div class="cs-slot has-room ' + roomClass + '" onclick="busSlotAction(' + floorNum + ',' + si + ')">' +
                        '<div class="cs-room-emoji">' + (s.room_emoji || '') + '</div>' +
                        '<div class="cs-room-name">' + (s.room_name || '') + '</div>' +
                        '<div class="cs-room-level">Lv.' + s.room_level + '</div>' +
                        creatureHtml + affHtml + prodHtml +
                        '</div>';
                }).join('');
            }

            // Next floor unlock
            const ufEl = document.getElementById('csUpgradeFloor');
            if (d.next_floor_unlock) {
                const nf = d.next_floor_unlock;
                ufEl.innerHTML = '<button onclick="busUpgradeFloor()">' + nf.floor + 'F Unlock (' + nf.cost.toLocaleString() + 'G / Lv.' + nf.required_level + ')</button>';
            } else {
                ufEl.innerHTML = '<div style="font-size:0.7rem;color:#4A7A4A;padding:4px">All floors unlocked!</div>';
            }
        }

        // Update landscape stats
        function updateLandscapeUI(p) {
            const lsLevel = document.getElementById('lsLevel');
            const lsGold = document.getElementById('lsGold');
            const lsEnergy = document.getElementById('lsEnergy');
            if (lsLevel) lsLevel.textContent = 'Lv.' + p.level;
            if (lsGold) lsGold.textContent = p.gold.toLocaleString() + 'G';
            if (lsEnergy) lsEnergy.textContent = p.energy + 'E';
        }

        function fillBarcode(code) { document.getElementById('barcodeInput').value = code; }

        // === CAMERA BARCODE SCANNER ===
        let html5QrCode = null;
        let cameraActive = false;

        async function toggleCamera() {
            const btn = document.getElementById('cameraToggle');
            const preview = document.getElementById('cameraPreview');
            const status = document.getElementById('cameraStatus');

            if (cameraActive) {
                stopCamera();
                return;
            }

            // Start camera
            preview.style.display = 'block';
            btn.textContent = '⏹ 카메라 끄기';
            btn.classList.add('active');
            status.innerHTML = '<div class="camera-status">바코드를 카메라에 비춰주세요...</div>';

            try {
                html5QrCode = new Html5Qrcode("cameraPreview");
                const cameras = await Html5Qrcode.getCameras();
                if (!cameras || cameras.length === 0) {
                    status.innerHTML = '<div style="color:#e94560;font-size:0.8rem">카메라를 찾을 수 없습니다.</div>';
                    stopCamera();
                    return;
                }
                // Prefer back camera on mobile
                const backCam = cameras.find(c => c.label.toLowerCase().includes('back') || c.label.toLowerCase().includes('rear'));
                const camId = backCam ? backCam.id : cameras[cameras.length - 1].id;

                await html5QrCode.start(
                    camId,
                    {
                        fps: 10,
                        qrbox: { width: 280, height: 120 },
                        aspectRatio: 1.5,
                        formatsToSupport: [
                            Html5QrcodeSupportedFormats.EAN_13,
                            Html5QrcodeSupportedFormats.EAN_8,
                            Html5QrcodeSupportedFormats.UPC_A,
                            Html5QrcodeSupportedFormats.UPC_E,
                            Html5QrcodeSupportedFormats.CODE_128,
                        ]
                    },
                    onBarcodeDetected,
                    () => {} // ignore scan failures
                );
                cameraActive = true;
            } catch (err) {
                console.error('Camera error:', err);
                let msg = '카메라 접근에 실패했습니다.';
                if (String(err).includes('NotAllowed') || String(err).includes('Permission')) {
                    msg = '카메라 권한을 허용해주세요! (설정 > 사이트 권한)';
                }
                status.innerHTML = `<div style="color:#e94560;font-size:0.8rem">${msg}</div>`;
                stopCamera();
            }
        }

        function onBarcodeDetected(decodedText) {
            // Normalize to 13-digit EAN
            let code = decodedText.replace(/[^0-9]/g, '');
            if (code.length === 12) code = '0' + code; // UPC-A → EAN-13
            if (code.length !== 13) {
                showToast('13자리 바코드가 아닙니다: ' + code);
                return;
            }

            // Auto-fill and scan
            document.getElementById('barcodeInput').value = code;
            stopCamera();
            showToast('바코드 인식! ' + code);
            scanBarcode();
        }

        function stopCamera() {
            const btn = document.getElementById('cameraToggle');
            const preview = document.getElementById('cameraPreview');
            const status = document.getElementById('cameraStatus');

            if (html5QrCode) {
                html5QrCode.stop().catch(() => {});
                html5QrCode.clear();
                html5QrCode = null;
            }
            cameraActive = false;
            preview.style.display = 'none';
            btn.textContent = '📸 카메라로 바코드 스캔';
            btn.classList.remove('active');
            status.innerHTML = '';
        }

        function showToast(msg) {
            const t = document.createElement('div');
            t.className = 'toast';
            t.textContent = msg;
            document.body.appendChild(t);
            setTimeout(() => t.remove(), 2500);
        }

        function updatePlayerUI(p) {
            document.getElementById('pLevel').textContent = `Lv.${p.level}`;
            document.getElementById('pGold').textContent = `${p.gold.toLocaleString()}G`;
            document.getElementById('pEnergy').textContent = `${p.energy}E`;
            const pct = (p.energy/p.max_energy*100);
            document.getElementById('energyBar').style.width = pct+'%';
            document.getElementById('energyText').textContent = `⚡ ${p.energy}/${p.max_energy}`;
            // Hero stats
            const hsL = document.getElementById('hsLevel');
            if (hsL) { hsL.textContent = p.level; }
            const hsG = document.getElementById('hsGold');
            if (hsG) { hsG.textContent = p.gold.toLocaleString(); }
            const hsE = document.getElementById('hsEnergy');
            if (hsE) { hsE.textContent = p.energy; }
            const hsC = document.getElementById('hsCollection');
            if (hsC) { hsC.textContent = p.total_scans || 0; }
            // Landscape stats
            if (USE_NEW_UI) updateLandscapeUI(p);
        }

        // Recent catches list (kept in memory)
        let recentCatchesList = [];

        function addRecentCatch(monster) {
            recentCatchesList.unshift(monster);
            if (recentCatchesList.length > 10) recentCatchesList.pop();
            renderRecentCatches();
        }

        function renderRecentCatches() {
            const row = document.getElementById('recentRow');
            if (!row) return;
            if (recentCatchesList.length === 0) {
                row.innerHTML = '<div class="recent-empty"><span class="re-icon">🥚</span>아직 깨어난 크리처가 없습니다<div class="re-hint">아래 포탈에서 첫 바코드를 스캔해보세요</div></div>';
                return;
            }
            row.innerHTML = recentCatchesList.map(m => {
                const colorHex = getMonsterColorHex(m.color);
                const svg = generateMonsterSVG(m.body_shape, colorHex, m.rarity);
                const rarClass = `r-${m.rarity}`;
                return `<div class="recent-mini ${rarClass}" onclick="showMonsterDetail(${JSON.stringify(m).replace(/"/g,'&quot;')})">
                    <div class="rm-svg">${svg.replace(/width="\d+"/, 'width="36"').replace(/height="\d+"/, 'height="36"')}</div>
                    <div class="rm-name">${m.name}</div>
                    <div class="rm-rarity" style="color:${getRarityColor(m.rarity)}">${m.rarity}</div>
                </div>`;
            }).join('');
        }

        function getRarityColor(r) {
            return { Common:'#888', Uncommon:'#4ecdc4', Rare:'#3b82f6', Epic:'#a855f7', Legendary:'#f59e0b' }[r] || '#888';
        }

        function loadRecentFromCollection() {
            fetch('/api/collection?session=default').then(r=>r.json()).then(d => {
                if (d.monsters && d.monsters.length > 0) {
                    recentCatchesList = d.monsters.slice(-10).reverse();
                    renderRecentCatches();
                    const hsC = document.getElementById('hsCollection');
                    if (hsC) hsC.textContent = d.total || d.monsters.length;
                }
            }).catch(()=>{});
        }

        // Ambient particles for hero section
        function initHeroParticles() {
            const container = document.getElementById('heroParticles');
            if (!container) return;
            const colors = ['#ff6b8a','#c084fc','#67e8f9','#fbbf24','#60a5fa','#a78bfa'];
            for (let i = 0; i < 15; i++) {
                const p = document.createElement('div');
                p.className = 'hero-particle';
                const size = 2 + Math.random() * 2;
                p.style.width = size + 'px';
                p.style.height = size + 'px';
                p.style.left = Math.random() * 100 + '%';
                p.style.bottom = '-5%';
                p.style.background = colors[Math.floor(Math.random() * colors.length)];
                p.style.animationDuration = (10 + Math.random() * 15) + 's';
                p.style.animationDelay = -(Math.random() * 25) + 's';
                container.appendChild(p);
            }
        }

        // Animated SVG creatures on hero
        function initHeroCreatures() {
            const stage = document.getElementById('heroCreatureStage');
            if (!stage) return;
            const creatures = [
                { shape: 'Fox', color: '#ff6b8a', size: 38 },
                { shape: 'Bird', color: '#67e8f9', size: 34 },
                { shape: 'Dragon', color: '#c084fc', size: 48 },
                { shape: 'Cat', color: '#fbbf24', size: 34 },
                { shape: 'Wolf', color: '#60a5fa', size: 38 },
            ];
            creatures.forEach(c => {
                const slot = document.createElement('div');
                slot.className = 'hero-creature-slot';
                const svg = generateMonsterSVG(c.shape, c.color, 'Rare');
                const sized = svg.replace(/width="\d+"/, `width="${c.size}"`).replace(/height="\d+"/, `height="${c.size}"`);
                slot.innerHTML = sized + '<div class="hero-creature-shadow" style="width:'+Math.round(c.size*0.6)+'px"></div>';
                stage.appendChild(slot);
            });
        }

        function renderMonsterCard(m, opts) {
            const colorHex = getMonsterColorHex(m.color);
            const svgVisual = generateMonsterSVG(m.body_shape, colorHex, m.rarity);
            const evolved = m.evolved ? '<span style="color:#f093fb;font-size:0.7rem"> EVOLVED</span>' : '';
            let sparkles = '';
            if (m.rarity === 'Rare') sparkles = '<span class="rarity-sparkles">&#10022;</span>';
            else if (m.rarity === 'Epic') sparkles = '<span class="rarity-sparkles">&#10022;&#10022;</span>';
            else if (m.rarity === 'Legendary') sparkles = '<span class="rarity-sparkles">&#10022;&#10022;&#10022;</span>';
            const story = generateMonsterStory(m);
            const storyPreview = story.length > 80 ? story.substring(0, 80) + '...' : story;
            const clickable = !(opts && opts.noClick);
            return `<div class="monster-card rarity-${m.rarity}" ${clickable ? 'onclick="openLastScannedDetail()"' : ''} title="Tap for details">
                ${svgVisual}
                <div class="monster-name">${m.name}${evolved}${sparkles}</div>
                <div class="monster-type">${m.primary_type} / ${m.secondary_type}</div>
                <span class="rarity-badge rarity-${m.rarity}">${m.rarity}</span>
                <div class="stats-grid">
                    <div class="stat"><div class="val">${m.stats.hp}</div><div class="label">HP</div></div>
                    <div class="stat"><div class="val">${m.stats.attack}</div><div class="label">ATK</div></div>
                    <div class="stat"><div class="val">${m.stats.defense}</div><div class="label">DEF</div></div>
                    <div class="stat"><div class="val">${m.stats.speed}</div><div class="label">SPD</div></div>
                    <div class="stat"><div class="val">${m.stats.special}</div><div class="label">SPC</div></div>
                </div>
                <div class="detail-story" style="margin:10px 0 6px;padding:10px;font-size:0.72rem;line-height:1.6">${storyPreview}</div>
                <div class="trait">"${m.special_trait}"</div>
                <div style="font-size:0.65rem;color:#555;margin-top:6px">${m.origin_country || parseBarcodeCountry(m.barcode)} | ${m.body_shape} | ${m.color} | ${m.accessory}</div>
                <div style="font-size:0.6rem;color:#444;margin-top:4px">Tap for full details</div>
            </div>`;
        }

        // === SCAN ===
        let lastScannedMonster = null;
        let lastBarcodeInfo = null;

        function openLastScannedDetail() {
            if (lastScannedMonster) showMonsterDetail(lastScannedMonster, lastBarcodeInfo);
        }

        async function scanBarcode() {
            const code = document.getElementById('barcodeInput').value.trim();
            if (code.length !== 13) { alert('13자리 바코드를 입력하세요!'); return; }
            document.getElementById('scanBtn').disabled = true;
            try {
                // Start all fetches in parallel
                const fetchPromise = fetch(`/api/scan?barcode=${code}&session=default`, {method:'POST'}).then(r=>r.json());
                const barcodeInfoPromise = fetchBarcodeInfo(code);

                const [d, bcInfo] = await Promise.all([fetchPromise, barcodeInfoPromise]);
                if (d.error) {
                    if (d.error === 'duplicate') {
                        document.getElementById('scanResult').innerHTML = `<div style="text-align:center;padding:24px 16px;background:rgba(22,33,62,0.6);border:1px solid #e94560;border-radius:14px;margin:16px 0">
                            <div style="font-size:2.5rem;margin-bottom:8px">🚫</div>
                            <div style="font-size:1.1rem;font-weight:700;color:#e94560;margin-bottom:6px">이미 스캔한 바코드!</div>
                            <div style="font-size:0.82rem;color:#888;line-height:1.5">${d.message}</div>
                            <div style="font-size:0.72rem;color:#555;margin-top:10px;font-family:monospace;letter-spacing:2px">${d.barcode}</div>
                        </div>`;
                    } else { alert(d.error); }
                    return;
                }
                updatePlayerUI(d.player);
                lastScannedMonster = d.monster;
                lastBarcodeInfo = bcInfo;

                // Run the 3-stage gacha animation
                await showScanAnimation(d.monster, d.collection, d.bus_suggestion, d.quest_updates, bcInfo);
            } catch(e) { console.error(e); }
            finally { document.getElementById('scanBtn').disabled = false; }
        }

        // === BATTLE ===
        async function startBattle() {
            const r = await fetch('/api/battle?session=default', {method:'POST'});
            const d = await r.json();
            if (d.error) { alert(d.error); return; }
            updatePlayerUI(d.player);
            const resEl = document.getElementById('battleResult');
            const logEl = document.getElementById('battleLog');
            resEl.innerHTML = `<div class="battle-result ${d.result==='WIN'?'win':'lose'}">${d.result==='WIN'?'VICTORY!':'DEFEAT...'}</div>
                <div style="margin:8px 0">${d.player_monster.name} vs ${d.opponent.name} (${d.opponent.rarity})</div>
                ${d.result==='WIN'?`<div style="color:#4ecdc4">+${d.rewards.exp} EXP | +${d.rewards.gold} Gold</div>`:''}`;
            logEl.style.display = 'block';
            logEl.innerHTML = d.battle_log.map(l => {
                let cls = '';
                if (l.is_critical) cls = 'log-crit';
                else if (l.effectiveness==='effective') cls = 'log-win';
                else if (l.effectiveness==='not_effective') cls = 'log-lose';
                return `<div class="${cls}">${l.message}</div>`;
            }).join('');
            if (d.quest_updates && d.quest_updates.length > 0) {
                d.quest_updates.forEach(q => showToast(`Quest Complete: ${q.title}`));
            }
        }

        // === COLLECTION ===
        async function loadCollection() {
            const r = await fetch('/api/collection?session=default');
            const d = await r.json();
            const rare = (d.stats.by_rarity?.Rare||0) + (d.stats.by_rarity?.Epic||0) + (d.stats.by_rarity?.Legendary||0);
            const types = Object.keys(d.stats.by_type||{}).length;
            document.getElementById('collStats').innerHTML = `
                <div class="coll-stat"><div class="num">${d.total}</div><div class="lbl">Total</div></div>
                <div class="coll-stat"><div class="num">${rare}</div><div class="lbl">Rare+</div></div>
                <div class="coll-stat"><div class="num">${types}/10</div><div class="lbl">Types</div></div>`;
            dexMonsters = d.monsters || [];
            renderDexList();
        }

        // === EXPEDITION ===
        async function loadExpedition() {
            const r = await fetch('/api/expedition/zones?session=default');
            const d = await r.json();
            const statusEl = document.getElementById('expeditionStatus');
            const zonesEl = document.getElementById('expeditionZones');

            if (d.active_expedition) {
                const e = d.active_expedition;
                statusEl.innerHTML = `
                    <div style="background:#16213e;border:1px solid #e94560;border-radius:12px;padding:14px;margin-bottom:12px">
                        <div style="font-weight:700;margin-bottom:6px">${e.zone_emoji} ${e.zone_name} 탐험 중...</div>
                        <div class="progress-bar"><div class="progress-fill" style="width:${e.progress_pct}%"></div></div>
                        <div style="font-size:0.8rem;color:#888">${e.party_names.join(', ')} | ${e.is_complete ? '완료!' : Math.ceil(e.remaining_seconds/60)+'분 남음'}</div>
                        ${e.is_complete ? '<button class="battle-btn" style="margin-top:8px;padding:10px 24px" onclick="collectExpedition()">보상 수령!</button>' : ''}
                    </div>`;
                zonesEl.innerHTML = '';
            } else {
                statusEl.innerHTML = '<p style="color:#888;font-size:0.85rem;margin-bottom:12px">파티 크리처를 탐험에 보내세요! (오프라인에서도 진행)</p>';
                zonesEl.innerHTML = d.zones.map(z => `
                    <div class="zone-card ${z.unlocked?'':'locked'}" onclick="${z.unlocked?`startExpedition('${z.zone_id}')`:''}">
                        <div class="zone-header">
                            <span class="zone-emoji">${z.emoji}</span>
                            <span class="zone-name">${z.name}</span>
                            <span class="zone-diff diff-${z.difficulty}">${z.difficulty}</span>
                        </div>
                        <div class="zone-desc">${z.description}</div>
                        <div class="zone-rewards">${z.duration_hours}시간 | ${z.gold_range[0]}~${z.gold_range[1]}G | ${z.exp_reward} EXP</div>
                        ${z.unlocked?'':'<div style="font-size:0.7rem;color:#e94560;margin-top:4px">Lv.'+z.required_level+' 필요</div>'}
                    </div>
                `).join('');
            }
        }

        async function startExpedition(zoneId) {
            const r = await fetch(`/api/expedition/start?zone_id=${zoneId}&session=default`, {method:'POST'});
            const d = await r.json();
            if (d.error) { alert(d.error); return; }
            showToast(d.message);
            loadExpedition();
        }

        async function collectExpedition() {
            const r = await fetch('/api/expedition/collect?session=default', {method:'POST'});
            const d = await r.json();
            if (d.error) { alert(d.error); return; }
            updatePlayerUI(d.player);
            const res = d.result;
            showToast(`${res.zone_emoji} 탐험 완료! +${res.gold_earned}G +${res.exp_earned}EXP`);
            loadExpedition();
        }

        // === QUESTS ===
        async function loadQuests() {
            const r = await fetch('/api/daily-quest?session=default');
            const d = await r.json();
            const s = d.summary;
            document.getElementById('questSummary').innerHTML = `
                <div style="display:flex;gap:8px;font-size:0.8rem">
                    <span style="color:#4ecdc4">${s.completed}/${s.total} 완료</span>
                    ${s.unclaimed_rewards>0?`<span style="color:#f59e0b">${s.unclaimed_rewards}개 보상 수령 가능!</span>`:''}
                </div>`;
            document.getElementById('questList').innerHTML = d.quests.map(q => {
                const cls = q.claimed ? 'quest-card claimed' : q.completed ? 'quest-card completed' : 'quest-card';
                const btn = q.completed && !q.claimed ? `<button class="claim-btn" onclick="claimQuest('${q.quest_id}')">수령</button>` : q.claimed ? '<span style="font-size:0.7rem;color:#4ecdc4">완료</span>' : '';
                return `<div class="${cls}">
                    <span class="quest-emoji">${q.emoji}</span>
                    <div class="quest-info">
                        <div class="quest-title">${q.title}</div>
                        <div class="quest-desc">${q.description}</div>
                        <div class="quest-progress">${q.current}/${q.target} (${q.progress_pct}%)</div>
                        <div class="quest-reward">${q.reward_gold}G + ${q.reward_exp}EXP${q.reward_item?' + Item':''}</div>
                    </div>
                    ${btn}
                </div>`;
            }).join('');
        }

        async function claimQuest(questId) {
            const r = await fetch(`/api/daily-quest/claim?quest_id=${questId}&session=default`, {method:'POST'});
            const d = await r.json();
            if (d.error) { alert(d.error); return; }
            updatePlayerUI(d.player);
            showToast(`${d.reward.message} +${d.reward.gold}G +${d.reward.exp}EXP`);
            loadQuests();
        }

        // === BUS ===
        let busState = null;
        let pendingBusSlot = null; // {floor, slot} for build/assign

        async function loadBus() {
            const r = await fetch('/api/bus?session=default');
            busState = await r.json();
            renderBus();
        }

        function renderBus() {
            if (!busState) return;
            // Also render cross-section in new UI
            if (USE_NEW_UI) renderBusCrossSection();
            const d = busState;

            // Accumulated resources
            const accEl = document.getElementById('busAccumulated');
            const accItems = [];
            if (d.total_accumulated.gold) accItems.push(`<span class="res-item">+${Math.floor(d.total_accumulated.gold)}G</span>`);
            if (d.total_accumulated.exp) accItems.push(`<span class="res-item">+${Math.floor(d.total_accumulated.exp)}EXP</span>`);
            if (d.total_accumulated.energy) accItems.push(`<span class="res-item">+${Math.floor(d.total_accumulated.energy)}E</span>`);
            if (d.total_accumulated.stat_point) accItems.push(`<span class="res-item">+${Math.floor(d.total_accumulated.stat_point)} stat</span>`);
            if (accItems.length > 0) {
                accEl.innerHTML = `<div class="bus-accumulated">${accItems.join(' | ')} <span style="color:#888">(${d.elapsed_hours.toFixed(1)}h)</span></div>`;
            } else {
                accEl.innerHTML = `<div class="bus-accumulated"><span style="color:#666">생산 중인 자원이 없습니다</span></div>`;
            }

            // Floors
            const floorsEl = document.getElementById('busFloors');
            floorsEl.innerHTML = d.floors.map(f => {
                const slotsHtml = f.slots.map((s, si) => {
                    if (!s.room_type) {
                        return `<div class="bus-slot" onclick="openBuildModal(${f.floor},${si})">
                            <div class="slot-empty">+ 건설</div>
                        </div>`;
                    }
                    let monsterHtml = '';
                    let affHtml = '';
                    let prodHtml = '';
                    if (s.monster) {
                        monsterHtml = `<div class="slot-monster">${s.monster.name}</div>`;
                        if (s.affinity) {
                            affHtml = `<span class="slot-affinity grade-${s.affinity.grade}">${s.affinity.grade} ${s.affinity.affinity}x</span>`;
                        }
                        const prods = Object.entries(s.production_per_hour).map(([k,v]) => `${v}${k}/h`).join(' ');
                        prodHtml = `<div class="slot-prod">${prods}</div>`;
                    } else {
                        monsterHtml = `<div class="slot-monster" style="color:#555;cursor:pointer" onclick="openAssignModal(${f.floor},${si})">배치하기</div>`;
                    }
                    return `<div class="bus-slot has-room" onclick="busSlotAction(${f.floor},${si})">
                        <div class="slot-emoji">${s.room_emoji}</div>
                        <div class="slot-name">${s.room_name}</div>
                        <div class="slot-level">Lv.${s.room_level}</div>
                        ${monsterHtml}${affHtml}${prodHtml}
                    </div>`;
                }).join('');
                return `<div class="bus-floor">
                    <div class="bus-floor-header">${f.floor}F</div>
                    <div class="bus-slots">${slotsHtml}</div>
                </div>`;
            }).join('');

            // Next floor unlock
            const ufEl = document.getElementById('busUpgradeFloor');
            if (d.next_floor_unlock) {
                const nf = d.next_floor_unlock;
                ufEl.innerHTML = `<button class="bus-upgrade-btn" onclick="busUpgradeFloor()">${nf.floor}층 해금 (${nf.cost.toLocaleString()}G / Lv.${nf.required_level})</button>`;
            } else {
                ufEl.innerHTML = '<div style="font-size:0.75rem;color:#4ecdc4;text-align:center">모든 층이 해금되었습니다!</div>';
            }
        }

        function busSlotAction(floor, slot) {
            if (!busState) return;
            const f = busState.floors.find(fl => fl.floor === floor);
            if (!f) return;
            const s = f.slots[slot];
            if (!s.room_type) { openBuildModal(floor, slot); return; }
            if (!s.monster) { openAssignModal(floor, slot); return; }
            // Has monster - show actions
            const action = confirm(`${s.room_name} (Lv.${s.room_level})\n${s.monster.name} 배치 중\n\n[확인] 몬스터 회수\n[취소] 방 업그레이드`);
            if (action) { busUnassign(floor, slot); }
            else { busUpgradeRoom(floor, slot); }
        }

        function openBuildModal(floor, slot) {
            pendingBusSlot = {floor, slot};
            const rooms = busState.available_rooms || [];
            if (rooms.length === 0) {
                alert('건설 가능한 방이 없습니다!');
                return;
            }
            document.getElementById('busBuildList').innerHTML = rooms.map(r =>
                `<div class="bus-room-option" onclick="busBuild('${r.room_id}')">
                    <div class="ro-header">
                        <span class="ro-emoji">${r.emoji}</span>
                        <span class="ro-name">${r.name}</span>
                        <span class="ro-cost">${r.build_cost.toLocaleString()}G</span>
                    </div>
                    <div class="ro-desc">${r.description}</div>
                    <div class="ro-types">선호: ${r.preferred_types.join(', ')} / ${r.preferred_stat}</div>
                </div>`
            ).join('');
            document.getElementById('busBuildModal').style.display = 'flex';
        }

        function closeBusModal() {
            document.getElementById('busBuildModal').style.display = 'none';
            pendingBusSlot = null;
        }

        async function busBuild(roomType) {
            if (!pendingBusSlot) return;
            const {floor, slot} = pendingBusSlot;
            closeBusModal();
            const r = await fetch(`/api/bus/build?floor=${floor}&slot=${slot}&room_type=${roomType}&session=default`, {method:'POST'});
            const d = await r.json();
            if (d.error) { alert(d.error); return; }
            if (d.player) updatePlayerUI(d.player);
            showToast(d.message);
            loadBus();
        }

        function openAssignModal(floor, slot) {
            pendingBusSlot = {floor, slot};
            // Fetch party + inventory for assignment
            fetch('/api/party?session=default').then(r=>r.json()).then(d => {
                const assignedIds = new Set(busState.assigned_monster_ids || []);
                let html = '';
                // Party monsters
                d.party.forEach((m, i) => {
                    if (assignedIds.has(m.id)) return;
                    const icon = shapes[m.body_shape] || '&#x1F47E;';
                    html += `<div class="bus-monster-option" onclick="busAssign('party',${i})">
                        <span style="font-size:1.2rem">${icon}</span>
                        <div class="bmo-info"><div class="bmo-name">${m.name}</div><div class="bmo-sub">${m.primary_type} | ${m.rarity} | Lv.${m.level||1} [파티]</div></div>
                    </div>`;
                });
                // Inventory monsters
                d.inventory.forEach((m, i) => {
                    if (assignedIds.has(m.id)) return;
                    const icon = shapes[m.body_shape] || '&#x1F47E;';
                    html += `<div class="bus-monster-option" onclick="busAssign('inventory',${i})">
                        <span style="font-size:1.2rem">${icon}</span>
                        <div class="bmo-info"><div class="bmo-name">${m.name}</div><div class="bmo-sub">${m.primary_type} | ${m.rarity} | Lv.${m.level||1} [보관함]</div></div>
                    </div>`;
                });
                if (!html) html = '<p style="color:#888;text-align:center;padding:12px">배치 가능한 몬스터가 없습니다.</p>';
                document.getElementById('busAssignList').innerHTML = html;
                document.getElementById('busAssignModal').style.display = 'flex';
            });
        }

        function closeBusAssignModal() {
            document.getElementById('busAssignModal').style.display = 'none';
            pendingBusSlot = null;
        }

        async function busAssign(source, idx) {
            if (!pendingBusSlot) return;
            const {floor, slot} = pendingBusSlot;
            closeBusAssignModal();
            const r = await fetch(`/api/bus/assign?floor=${floor}&slot=${slot}&monster_source=${source}&monster_idx=${idx}&session=default`, {method:'POST'});
            const d = await r.json();
            if (d.error) { alert(d.error); return; }
            showToast(d.message);
            loadBus();
        }

        async function busUnassign(floor, slot) {
            const r = await fetch(`/api/bus/unassign?floor=${floor}&slot=${slot}&session=default`, {method:'POST'});
            const d = await r.json();
            if (d.error) { alert(d.error); return; }
            showToast(d.message);
            loadBus();
        }

        async function busUpgradeFloor() {
            const r = await fetch('/api/bus/upgrade-floor?session=default', {method:'POST'});
            const d = await r.json();
            if (d.error) { alert(d.error); return; }
            if (d.player) updatePlayerUI(d.player);
            showToast(d.message);
            loadBus();
        }

        async function busUpgradeRoom(floor, slot) {
            const r = await fetch(`/api/bus/upgrade-room?floor=${floor}&slot=${slot}&session=default`, {method:'POST'});
            const d = await r.json();
            if (d.error) { alert(d.error); return; }
            if (d.player) updatePlayerUI(d.player);
            showToast(d.message);
            loadBus();
        }

        async function busCollect() {
            const r = await fetch('/api/bus/collect?session=default', {method:'POST'});
            const d = await r.json();
            if (d.error) { alert(d.error); return; }
            if (d.player) updatePlayerUI(d.player);
            showToast(d.message);
            loadBus();
        }

        // === BARCODE COUNTRY MAP ===
        const BARCODE_COUNTRIES = {
            '000':'USA','001':'USA','002':'USA','003':'USA','004':'USA','005':'USA','006':'USA','007':'USA','008':'USA','009':'USA',
            '01':'USA','02':'USA','03':'USA','04':'USA','05':'USA','06':'USA','07':'USA','08':'USA','09':'USA',
            '30':'France','31':'France','32':'France','33':'France','34':'France','35':'France','36':'France','37':'France',
            '380':'Bulgaria','383':'Slovenia','385':'Croatia','387':'Bosnia','389':'Montenegro',
            '400':'Germany','41':'Germany','42':'Germany','43':'Germany','44':'Germany',
            '45':'Japan','46':'Russia','470':'Kyrgyzstan','471':'Taiwan','474':'Estonia','475':'Latvia',
            '476':'Azerbaijan','477':'Lithuania','478':'Uzbekistan','479':'Sri Lanka',
            '480':'Philippines','481':'Belarus','482':'Ukraine','484':'Moldova','485':'Armenia','486':'Georgia',
            '487':'Kazakhstan','488':'Tajikistan','489':'Hong Kong',
            '49':'Japan',
            '50':'UK','520':'Greece','528':'Lebanon','529':'Cyprus','530':'Albania','531':'North Macedonia',
            '535':'Malta','539':'Ireland','54':'Belgium','560':'Portugal','569':'Iceland',
            '57':'Denmark','590':'Poland','594':'Romania','599':'Hungary',
            '600':'South Africa','601':'South Africa','608':'Bahrain','609':'Mauritius',
            '611':'Morocco','613':'Algeria','615':'Nigeria','616':'Kenya','618':'Ivory Coast','619':'Tunisia',
            '621':'Syria','622':'Egypt','624':'Libya','625':'Jordan','626':'Iran','627':'Kuwait','628':'Saudi Arabia','629':'UAE',
            '64':'Finland','690':'China','691':'China','692':'China','693':'China','694':'China','695':'China','699':'China',
            '70':'Norway','729':'Israel','73':'Sweden','740':'Guatemala','741':'El Salvador','742':'Honduras',
            '743':'Nicaragua','744':'Costa Rica','745':'Panama','746':'Dominican Republic',
            '750':'Mexico','754':'Canada','755':'Canada','759':'Venezuela',
            '76':'Switzerland','770':'Colombia','773':'Uruguay','775':'Peru','777':'Bolivia','779':'Argentina',
            '780':'Chile','784':'Paraguay','786':'Ecuador','789':'Brazil','790':'Brazil',
            '80':'Italy','81':'Italy','82':'Italy','83':'Italy','84':'Spain',
            '858':'Slovakia','859':'Czech Republic','860':'Serbia','865':'Mongolia','867':'North Korea',
            '868':'Turkey','869':'Turkey','87':'Netherlands',
            '880':'South Korea','884':'Cambodia','885':'Thailand','888':'Singapore',
            '890':'India','893':'Vietnam','896':'Pakistan','899':'Indonesia',
            '90':'Austria','91':'Austria','93':'Australia','94':'New Zealand','955':'Malaysia','958':'Macau'
        };

        function parseBarcodeCountry(barcode) {
            if (!barcode || barcode.length < 3) return 'Unknown';
            if (BARCODE_COUNTRIES[barcode.substring(0,3)]) return BARCODE_COUNTRIES[barcode.substring(0,3)];
            if (BARCODE_COUNTRIES[barcode.substring(0,2)]) return BARCODE_COUNTRIES[barcode.substring(0,2)];
            return 'Unknown';
        }

        function parseBarcodeComponents(barcode) {
            if (!barcode || barcode.length !== 13) return null;
            const country = parseBarcodeCountry(barcode);
            const countryLen = barcode.startsWith('0') ? 3 : (BARCODE_COUNTRIES[barcode.substring(0,3)] ? 3 : 2);
            const mfr = barcode.substring(countryLen, countryLen + (countryLen === 3 ? 4 : 5));
            const prod = barcode.substring(countryLen + mfr.length, 12);
            return { country, countryCode: barcode.substring(0, countryLen), manufacturer: mfr, product: prod, checkDigit: barcode[12], full: barcode };
        }

        // === BARCODE PRODUCT INFO (Open Food Facts API) ===
        const productCache = {};
        async function fetchBarcodeInfo(barcode) {
            if (productCache[barcode]) return productCache[barcode];
            try {
                const r = await fetch(`https://world.openfoodfacts.org/api/v2/product/${barcode}?fields=product_name,brands,categories,countries,origins,labels,quantity,image_front_small_url,nutriscore_grade,nova_group`);
                const d = await r.json();
                if (d.status === 1 && d.product) {
                    const p = d.product;
                    const info = {
                        found: true,
                        name: p.product_name || '',
                        brand: p.brands || '',
                        categories: p.categories || '',
                        countries: p.countries || '',
                        origins: p.origins || '',
                        labels: p.labels || '',
                        quantity: p.quantity || '',
                        image: p.image_front_small_url || '',
                        nutriscore: p.nutriscore_grade || '',
                        nova: p.nova_group || ''
                    };
                    productCache[barcode] = info;
                    return info;
                }
            } catch(e) { console.log('OpenFoodFacts fetch failed:', e); }
            const info = { found: false };
            productCache[barcode] = info;
            return info;
        }

        // === MONSTER STORY GENERATOR ===
        function generateMonsterStory(m) {
            const seed = hashStr(m.id || m.name + m.barcode);
            const bodyStories = {
                Dragon: [
                    "Once the smallest guardian of a mountain village, this little dragon was left behind when its family migrated south. It still lights a tiny flame every evening, hoping they'll see it from afar and find their way back.",
                    "Born from the last ember of a dying hearth, this dragon carries warmth for others but can never quite warm its own heart. It smiles anyway, because someone once told it that fire is for sharing.",
                    "It was once a proud protector, but the village it guarded faded away long ago. Now it wanders with a {accessory}, the only gift from a child who once called it friend."
                ],
                Fox: [
                    "Found shivering under a convenience store awning on a rainy night, this little fox still brings small gifts to the doorstep of the shop that once sheltered it, even though the shop has long since closed.",
                    "They say this fox learned to smile by watching humans. But sometimes, when no one is looking, the smile fades and it gazes at the moon, remembering a forest that no longer exists.",
                    "This fox once had a twin sibling, but they were separated during a storm. It carries a {accessory} that matches one its sibling wore, hoping someday they'll recognize each other."
                ],
                Bear: [
                    "Too gentle to be fierce, this bear was always the one left behind by its pack. But it discovered that being soft in a hard world isn't weakness. Every creature it meets ends up wanting to stay.",
                    "It collects small, broken things: chipped seashells, torn leaves, mismatched buttons. It believes everything deserves to be treasured, even the things others throw away.",
                    "This bear once guarded a honey tree for a family of bees. When the tree fell in a storm, it carried each bee to safety on its back, one trip at a time."
                ],
                Bird: [
                    "It has a beautiful voice but chooses to sing only at dawn, when no one is listening. Not because it's shy, but because it sings for a friend who left with the morning mist and never came back.",
                    "Born with one wing slightly shorter than the other, this bird can't fly as high as the rest. But it found that walking the earth means discovering treasures the sky-dwellers never see.",
                    "Every night, this bird folds a paper crane from a fallen leaf and places it by the window. 'One more day of wishing,' it whispers, 'one day closer to finding you.'"
                ],
                Slime: [
                    "Born from a child's spilled juice box and a whispered wish, this slime absorbs the sadness of those around it, always wobbling cheerfully despite carrying everyone's tears inside.",
                    "Nobody wanted to be friends with a slime. But this one learned to change its color to match others' moods, just so they'd feel a little less alone. It has long forgotten its own original color.",
                    "This slime lives in the corner of an old library. It can't read, but it loves the sound of pages turning. On quiet nights, it gently holds open the books that are too heavy for the old librarian."
                ],
                Golem: [
                    "Built by a lonely inventor who passed away before giving it a name, this golem still follows the last instruction it received: 'Take care of things while I'm gone.' It's been waiting ever since.",
                    "There are scratch marks on its stone body. Not from battles, but from all the kittens that climbed on it thinking it was a warm rock. It never moved, not once, until each one was safely asleep.",
                    "This golem was carved from the cornerstone of a demolished school. Inside its chest, you can still hear the faint echo of children laughing, a sound it protects above all else."
                ],
                Ghost: [
                    "It isn't scary at all. In fact, it's the one that gets scared. Thunder, loud noises, sudden movements. But it stays close to sleeping children, because it remembers what it was like to need someone nearby in the dark.",
                    "This ghost forgot how it came to be. All it remembers is the scent of a certain flower and a lullaby it can't quite finish. It searches everywhere for the missing notes.",
                    "It could pass through any wall, but it always knocks first. 'Manners matter,' it says, repeating the last words someone kind once told it, even though it can't remember who."
                ],
                Cat: [
                    "Found curled up inside an empty shoebox at a bus stop, this little one still waits at the same corner every evening, purring softly for a companion who promised to come back but never did.",
                    "It pretends not to care. It grooms itself, looks away, flicks its tail. But late at night, it sneaks onto your pillow and presses its tiny nose against your cheek, just to make sure you're still there.",
                    "This cat has a bell that doesn't ring anymore. It refuses to take it off because it was the first gift it ever received, from hands that were gentle when the world was not."
                ],
                Wolf: [
                    "The runt of a pack that vanished in the winter, this wolf howls every full moon. Not out of sadness, but hope, because somewhere far away, it believes a howl will answer back one day.",
                    "It guards the entrance to an abandoned den, keeping it clean and warm. 'Just in case,' it says. Just in case they come home. Just in case someone needs a safe place tonight.",
                    "Fierce on the outside, this wolf secretly leaves food at the doorsteps of weaker creatures. It learned from its mother that true strength is making sure no one goes hungry."
                ],
                Turtle: [
                    "It carries its home on its back, not because it wants to, but because it promised a friend it would keep their shared memories safe. Every scratch on its shell is a story it refuses to forget.",
                    "The slowest one in every race, but it never stops. 'I'll get there,' it says, 'and when I do, I'll have seen every flower along the way.' Its shell is covered in tiny pressed petals.",
                    "This turtle has been walking for a very long time. It's looking for an ocean it saw in a dream. Some say the ocean doesn't exist, but the turtle just smiles and takes another step."
                ]
            };
            const stories = bodyStories[m.body_shape] || bodyStories['Slime'];
            let story = stories[seed % stories.length];
            story = story.replace('{accessory}', (m.accessory || 'small charm').toLowerCase());
            return story;
        }

        function hashStr(s) {
            let h = 0;
            for (let i = 0; i < s.length; i++) { h = ((h << 5) - h + s.charCodeAt(i)) | 0; }
            return Math.abs(h);
        }

        // === MONSTER DETAIL MODAL ===
        let lastDetailMonster = null;

        function showMonsterDetail(m, barcodeInfo) {
            lastDetailMonster = m;
            const colorHex = getMonsterColorHex(m.color);
            const svg = generateMonsterSVG(m.body_shape, colorHex, m.rarity);
            const story = generateMonsterStory(m);
            const bc = parseBarcodeComponents(m.barcode);
            let sparkles = '';
            if (m.rarity === 'Rare') sparkles = ' <span class="rarity-sparkles">&#10022;</span>';
            else if (m.rarity === 'Epic') sparkles = ' <span class="rarity-sparkles">&#10022;&#10022;</span>';
            else if (m.rarity === 'Legendary') sparkles = ' <span class="rarity-sparkles">&#10022;&#10022;&#10022;</span>';
            const maxStat = 300;
            const statBar = (label, val, cls) =>
                `<div class="stat-bar-row"><div class="stat-bar-label">${label}</div><div class="stat-bar-track"><div class="stat-bar-fill ${cls}" style="width:${Math.min(100,val/maxStat*100)}%"></div></div><div class="stat-bar-val">${val}</div></div>`;

            let barcodeHtml = '';
            if (bc) {
                barcodeHtml = `<div class="barcode-info"><div class="barcode-info-title">Barcode Data</div><div class="barcode-info-grid">`;
                barcodeHtml += `<div class="barcode-info-item" style="grid-column:1/-1"><div class="bil">Barcode</div><div class="biv" style="font-family:monospace;letter-spacing:2px">${bc.full}</div></div>`;
                barcodeHtml += `<div class="barcode-info-item"><div class="bil">Country</div><div class="biv">${bc.country} (${bc.countryCode})</div></div>`;
                barcodeHtml += `<div class="barcode-info-item"><div class="bil">Manufacturer</div><div class="biv">${bc.manufacturer}</div></div>`;
                barcodeHtml += `<div class="barcode-info-item"><div class="bil">Product Code</div><div class="biv">${bc.product}</div></div>`;
                barcodeHtml += `<div class="barcode-info-item"><div class="bil">Check Digit</div><div class="biv">${bc.checkDigit}</div></div>`;
                if (barcodeInfo && barcodeInfo.found) {
                    const bi = barcodeInfo;
                    if (bi.name) barcodeHtml += `<div class="barcode-product-name">${bi.name}</div>`;
                    if (bi.brand) barcodeHtml += `<div class="barcode-info-item"><div class="bil">Brand</div><div class="biv">${bi.brand}</div></div>`;
                    if (bi.categories) barcodeHtml += `<div class="barcode-info-item"><div class="bil">Category</div><div class="biv">${bi.categories.split(',')[0]}</div></div>`;
                    if (bi.countries) barcodeHtml += `<div class="barcode-info-item"><div class="bil">Sold In</div><div class="biv">${bi.countries.split(',').slice(0,2).join(', ')}</div></div>`;
                    if (bi.quantity) barcodeHtml += `<div class="barcode-info-item"><div class="bil">Quantity</div><div class="biv">${bi.quantity}</div></div>`;
                    if (bi.origins) barcodeHtml += `<div class="barcode-info-item"><div class="bil">Origin</div><div class="biv">${bi.origins}</div></div>`;
                    if (bi.nutriscore) barcodeHtml += `<div class="barcode-info-item"><div class="bil">Nutri-Score</div><div class="biv" style="text-transform:uppercase">${bi.nutriscore}</div></div>`;
                    if (bi.labels) barcodeHtml += `<div class="barcode-info-item" style="grid-column:1/-1"><div class="bil">Labels</div><div class="biv" style="font-size:0.72rem">${bi.labels.split(',').slice(0,3).join(', ')}</div></div>`;
                }
                barcodeHtml += '</div></div>';
            }

            const html = `
                <div class="detail-header">
                    <span style="font-size:0.75rem;color:#666">Lv.${m.level || 1}</span>
                    <button class="detail-close" onclick="closeMonsterDetail()">&#x2715;</button>
                </div>
                <div class="detail-visual rarity-bg-${m.rarity.toLowerCase()}" style="border-radius:0">
                    <div style="display:inline-block">${svg.replace(/width="\d+"/g,'width="120"').replace(/height="\d+"/g,'height="120"')}</div>
                </div>
                <div class="detail-body">
                    <div class="detail-name">${m.name}${sparkles}</div>
                    <div class="detail-types">${m.primary_type} / ${m.secondary_type}</div>
                    <div class="detail-rarity-row"><span class="rarity-badge rarity-${m.rarity}">${m.rarity}</span></div>
                    <div class="detail-story">${story}</div>
                    <div class="detail-stat-bars">
                        ${statBar('HP', m.stats.hp, 'hp')}
                        ${statBar('ATK', m.stats.attack, 'atk')}
                        ${statBar('DEF', m.stats.defense, 'def')}
                        ${statBar('SPD', m.stats.speed, 'spd')}
                        ${statBar('SPC', m.stats.special, 'spc')}
                    </div>
                    <div class="detail-trait"><div class="dt-label">Special Trait</div><div class="dt-val">${m.special_trait}</div></div>
                    <div class="detail-info-grid">
                        <div class="detail-info-item"><div class="dii-label">Body</div><div class="dii-val">${m.body_shape}</div></div>
                        <div class="detail-info-item"><div class="dii-label">Color</div><div class="dii-val">${m.color}</div></div>
                        <div class="detail-info-item"><div class="dii-label">Accessory</div><div class="dii-val">${m.accessory}</div></div>
                        <div class="detail-info-item"><div class="dii-label">Time</div><div class="dii-val">${m.time_variant}</div></div>
                        <div class="detail-info-item"><div class="dii-label">Origin</div><div class="dii-val">${m.origin_country || parseBarcodeCountry(m.barcode)}</div></div>
                        <div class="detail-info-item"><div class="dii-label">Location</div><div class="dii-val">${m.location_name || 'Unknown'}</div></div>
                    </div>
                    ${barcodeHtml}
                </div>`;

            document.getElementById('monsterDetailPanel').innerHTML = html;
            document.getElementById('monsterDetailOverlay').style.display = 'flex';
            // Add legendary particles
            if (m.rarity === 'Legendary') {
                const vis = document.querySelector('.detail-visual');
                if (vis) { vis.style.position = 'relative'; vis.style.overflow = 'hidden'; createLegendaryParticles(vis); }
            }
        }

        function closeMonsterDetail() {
            document.getElementById('monsterDetailOverlay').style.display = 'none';
        }

        // === DEX FILTER STATE ===
        let dexFilter = 'all';
        let dexMonsters = [];

        function setDexFilter(filter) {
            dexFilter = filter;
            document.querySelectorAll('.dex-filter').forEach(f => f.classList.toggle('active', f.textContent === filter || (filter === 'all' && f.textContent === 'All')));
            renderDexList();
        }

        function renderDexList() {
            const filtered = dexFilter === 'all' ? dexMonsters : dexMonsters.filter(m => m.rarity === dexFilter);
            const el = document.getElementById('collList');
            if (filtered.length === 0) {
                el.innerHTML = '<div class="dex-empty">' + (dexMonsters.length === 0 ? 'No creatures collected yet. Scan barcodes to discover!' : 'No ' + dexFilter + ' creatures found.') + '</div>';
                return;
            }
            el.innerHTML = filtered.map((m, i) => {
                const colorHex = getMonsterColorHex(m.color);
                const svg = generateMonsterSVG(m.body_shape, colorHex, m.rarity);
                return `<div class="dex-card r-${m.rarity}" onclick='showMonsterDetail(dexMonsters[${dexMonsters.indexOf(m)}])'>
                    <div class="dex-icon">${svg}</div>
                    <div class="dex-name">${m.name}</div>
                    <div class="dex-sub">${m.primary_type} | Lv.${m.level || 1}</div>
                    <div class="dex-rarity"><span class="rarity-badge rarity-${m.rarity}" style="font-size:0.6rem;padding:2px 8px">${m.rarity}</span></div>
                </div>`;
            }).join('');
        }

        // === SVG MONSTER GENERATOR ===
        function generateMonsterSVG(bodyShape, color, rarity) {
            const sizes = {Common: 60, Uncommon: 60, Rare: 65, Epic: 70, Legendary: 80};
            const sz = sizes[rarity] || 60;
            const c = color || '#e94560';
            const hi = lightenColor(c, 40);
            const lo = darkenColor(c, 30);
            const svgs = {
                Dragon: `<circle cx="50" cy="52" r="22" fill="${c}"/><polygon points="36,36 29,16 43,32" fill="${lo}"/><polygon points="64,36 71,16 57,32" fill="${lo}"/><polygon points="72,46 94,34 90,52" fill="${c}" opacity=".7"/><polygon points="72,54 94,62 88,50" fill="${c}" opacity=".7"/><path d="M28,54 Q16,68 22,80" stroke="${lo}" stroke-width="4" fill="none" stroke-linecap="round"/><circle cx="42" cy="46" r="4" fill="white"/><circle cx="58" cy="46" r="4" fill="white"/><circle cx="42" cy="46" r="2" fill="#1a1a2e"/><circle cx="58" cy="46" r="2" fill="#1a1a2e"/><path d="M44,60 Q50,65 56,60" stroke="#1a1a2e" stroke-width="1.5" fill="none"/>`,
                Fox: `<ellipse cx="50" cy="55" rx="20" ry="18" fill="${c}"/><polygon points="32,42 25,16 44,36" fill="${c}"/><polygon points="68,42 75,16 56,36" fill="${c}"/><polygon points="34,40 29,22 40,36" fill="${hi}" opacity=".4"/><polygon points="66,40 71,22 60,36" fill="${hi}" opacity=".4"/><ellipse cx="50" cy="66" rx="9" ry="5" fill="${hi}" opacity=".3"/><circle cx="43" cy="49" r="3" fill="white"/><circle cx="57" cy="49" r="3" fill="white"/><circle cx="43" cy="49" r="1.5" fill="#1a1a2e"/><circle cx="57" cy="49" r="1.5" fill="#1a1a2e"/><circle cx="50" cy="56" r="2" fill="#1a1a2e"/><path d="M14,58 Q24,52 32,58" stroke="${c}" stroke-width="5" fill="none" stroke-linecap="round"/><path d="M68,58 Q76,52 86,58" stroke="${c}" stroke-width="5" fill="none" stroke-linecap="round"/>`,
                Bear: `<circle cx="50" cy="55" r="24" fill="${c}"/><circle cx="34" cy="32" r="10" fill="${c}"/><circle cx="66" cy="32" r="10" fill="${c}"/><circle cx="34" cy="32" r="6" fill="${lo}" opacity=".5"/><circle cx="66" cy="32" r="6" fill="${lo}" opacity=".5"/><ellipse cx="50" cy="64" rx="12" ry="7" fill="${hi}" opacity=".25"/><circle cx="42" cy="50" r="4" fill="white"/><circle cx="58" cy="50" r="4" fill="white"/><circle cx="42" cy="50" r="2" fill="#1a1a2e"/><circle cx="58" cy="50" r="2" fill="#1a1a2e"/><ellipse cx="50" cy="58" rx="4" ry="2.5" fill="#1a1a2e"/>`,
                Bird: `<ellipse cx="50" cy="50" rx="18" ry="22" fill="${c}"/><polygon points="28,40 8,28 26,50" fill="${c}" opacity=".8"/><polygon points="72,40 92,28 74,50" fill="${c}" opacity=".8"/><ellipse cx="50" cy="60" rx="10" ry="6" fill="${hi}" opacity=".2"/><circle cx="43" cy="42" r="4" fill="white"/><circle cx="57" cy="42" r="4" fill="white"/><circle cx="43" cy="42" r="2" fill="#1a1a2e"/><circle cx="57" cy="42" r="2" fill="#1a1a2e"/><polygon points="50,48 44,56 56,56" fill="#f59e0b"/><polygon points="42,74 50,84 58,74" fill="${lo}" opacity=".6"/>`,
                Slime: `<ellipse cx="50" cy="62" rx="30" ry="20" fill="${c}" opacity=".8"/><ellipse cx="50" cy="52" rx="26" ry="26" fill="${c}"/><ellipse cx="40" cy="34" rx="6" ry="10" fill="${c}"/><ellipse cx="62" cy="32" rx="4" ry="7" fill="${c}"/><circle cx="42" cy="50" r="5" fill="white"/><circle cx="58" cy="50" r="5" fill="white"/><circle cx="42" cy="50" r="2.5" fill="#1a1a2e"/><circle cx="58" cy="50" r="2.5" fill="#1a1a2e"/><path d="M44,62 Q50,68 56,62" stroke="#1a1a2e" stroke-width="1.5" fill="none"/><ellipse cx="36" cy="44" rx="5" ry="3" fill="${hi}" opacity=".3"/>`,
                Golem: `<rect x="32" y="35" width="36" height="38" rx="4" fill="${c}"/><rect x="26" y="40" width="10" height="24" rx="3" fill="${lo}"/><rect x="64" y="40" width="10" height="24" rx="3" fill="${lo}"/><rect x="32" y="26" width="36" height="14" rx="4" fill="${c}"/><rect x="36" y="73" width="11" height="10" rx="2" fill="${lo}"/><rect x="53" y="73" width="11" height="10" rx="2" fill="${lo}"/><rect x="38" y="30" width="8" height="5" rx="1" fill="#4ecdc4"/><rect x="54" y="30" width="8" height="5" rx="1" fill="#4ecdc4"/><line x1="40" y1="54" x2="60" y2="54" stroke="#1a1a2e" stroke-width="2" stroke-linecap="round"/>`,
                Ghost: `<ellipse cx="50" cy="42" rx="22" ry="24" fill="${c}" opacity=".85"/><path d="M28,42 Q28,82 36,72 Q40,78 46,72 Q50,80 54,72 Q58,78 64,72 Q72,82 72,42" fill="${c}" opacity=".85"/><circle cx="42" cy="38" r="5" fill="white"/><circle cx="58" cy="38" r="5" fill="white"/><circle cx="42" cy="38" r="2.5" fill="#1a1a2e"/><circle cx="58" cy="38" r="2.5" fill="#1a1a2e"/><ellipse cx="50" cy="50" rx="4" ry="5" fill="#1a1a2e" opacity=".6"/><ellipse cx="38" cy="32" rx="4" ry="2" fill="${hi}" opacity=".3"/>`,
                Cat: `<ellipse cx="50" cy="55" rx="20" ry="18" fill="${c}"/><polygon points="32,42 28,18 44,36" fill="${c}"/><polygon points="68,42 72,18 56,36" fill="${c}"/><polygon points="34,38 31,24 40,36" fill="${hi}" opacity=".3"/><polygon points="66,38 69,24 60,36" fill="${hi}" opacity=".3"/><circle cx="42" cy="48" r="4" fill="#7ee8fa"/><circle cx="58" cy="48" r="4" fill="#7ee8fa"/><circle cx="42" cy="48" r="2" fill="#1a1a2e"/><circle cx="58" cy="48" r="2" fill="#1a1a2e"/><ellipse cx="50" cy="56" rx="2" ry="1.5" fill="#f093fb"/><line x1="25" y1="50" x2="38" y2="52" stroke="${hi}" stroke-width="0.8" opacity=".5"/><line x1="25" y1="56" x2="38" y2="55" stroke="${hi}" stroke-width="0.8" opacity=".5"/><line x1="62" y1="52" x2="75" y2="50" stroke="${hi}" stroke-width="0.8" opacity=".5"/><line x1="62" y1="55" x2="75" y2="56" stroke="${hi}" stroke-width="0.8" opacity=".5"/>`,
                Wolf: `<ellipse cx="50" cy="52" rx="20" ry="20" fill="${c}"/><polygon points="30,38 22,12 44,34" fill="${c}"/><polygon points="70,38 78,12 56,34" fill="${c}"/><polygon points="34,34 28,18 40,34" fill="${lo}" opacity=".5"/><polygon points="66,34 72,18 60,34" fill="${lo}" opacity=".5"/><ellipse cx="50" cy="60" rx="10" ry="6" fill="${lo}" opacity=".3"/><circle cx="40" cy="46" r="4" fill="#f59e0b" opacity=".9"/><circle cx="60" cy="46" r="4" fill="#f59e0b" opacity=".9"/><circle cx="40" cy="46" r="2" fill="#1a1a2e"/><circle cx="60" cy="46" r="2" fill="#1a1a2e"/><polygon points="50,54 46,60 54,60" fill="#1a1a2e"/><path d="M44,64 Q50,68 56,64" stroke="#1a1a2e" stroke-width="1.2" fill="none"/>`,
                Turtle: `<ellipse cx="50" cy="58" rx="28" ry="20" fill="${lo}"/><ellipse cx="50" cy="56" rx="26" ry="18" fill="${c}"/><path d="M30,48 Q38,38 50,36 Q62,38 70,48" stroke="${lo}" stroke-width="2" fill="none"/><line x1="50" y1="38" x2="50" y2="72" stroke="${lo}" stroke-width="1.5"/><line x1="32" y1="56" x2="68" y2="56" stroke="${lo}" stroke-width="1.5"/><circle cx="50" cy="32" r="10" fill="${hi}"/><circle cx="46" cy="30" r="2.5" fill="white"/><circle cx="54" cy="30" r="2.5" fill="white"/><circle cx="46" cy="30" r="1.2" fill="#1a1a2e"/><circle cx="54" cy="30" r="1.2" fill="#1a1a2e"/><path d="M48,35 Q50,37 52,35" stroke="#1a1a2e" stroke-width="1" fill="none"/><ellipse cx="26" cy="64" rx="6" ry="4" fill="${hi}"/><ellipse cx="74" cy="64" rx="6" ry="4" fill="${hi}"/><ellipse cx="36" cy="76" rx="5" ry="4" fill="${hi}"/><ellipse cx="64" cy="76" rx="5" ry="4" fill="${hi}"/>`
            };
            const inner = svgs[bodyShape] || svgs['Slime'];
            return `<div class="monster-svg-wrap" style="width:${sz}px;height:${sz}px"><svg viewBox="0 0 100 100" width="${sz}" height="${sz}" xmlns="http://www.w3.org/2000/svg">${inner}</svg></div>`;
        }

        function lightenColor(hex, pct) {
            let r=parseInt(hex.slice(1,3),16), g=parseInt(hex.slice(3,5),16), b=parseInt(hex.slice(5,7),16);
            r=Math.min(255,r+Math.round((255-r)*pct/100)); g=Math.min(255,g+Math.round((255-g)*pct/100)); b=Math.min(255,b+Math.round((255-b)*pct/100));
            return '#'+[r,g,b].map(x=>x.toString(16).padStart(2,'0')).join('');
        }
        function darkenColor(hex, pct) {
            let r=parseInt(hex.slice(1,3),16), g=parseInt(hex.slice(3,5),16), b=parseInt(hex.slice(5,7),16);
            r=Math.max(0,Math.round(r*(1-pct/100))); g=Math.max(0,Math.round(g*(1-pct/100))); b=Math.max(0,Math.round(b*(1-pct/100)));
            return '#'+[r,g,b].map(x=>x.toString(16).padStart(2,'0')).join('');
        }

        // Color name to hex mapping for monster colors
        const COLOR_MAP = {
            'Crimson':'#DC143C','Azure':'#007FFF','Emerald':'#50C878','Golden':'#FFD700',
            'Violet':'#8B5CF6','Obsidian':'#2D2D2D','Silver':'#C0C0C0','Coral':'#FF7F50',
            'Cyan':'#00CED1','Amber':'#FFBF00','Ivory':'#FFFFF0','Jade':'#00A86B',
            'Ruby':'#E0115F','Sapphire':'#0F52BA','Pearl':'#F0EAD6','Bronze':'#CD7F32',
            'Frost':'#A5F2F3','Shadow':'#36454F','Sunset':'#FAD6A5','Forest':'#228B22'
        };
        function getMonsterColorHex(colorName) {
            return COLOR_MAP[colorName] || '#e94560';
        }

        // === PARTICLE EFFECTS ===
        function createLegendaryParticles(container) {
            for (let i = 0; i < 12; i++) {
                const p = document.createElement('div');
                p.className = 'legend-particle';
                p.style.left = Math.random()*90+5 + '%';
                p.style.bottom = '10%';
                p.style.animationDuration = (2+Math.random()*2) + 's';
                p.style.animationDelay = Math.random()*2 + 's';
                p.style.animation = `particleFloat ${2+Math.random()*2}s ease-in-out ${Math.random()*2}s infinite`;
                p.style.background = Math.random()>0.5 ? '#ffcc02' : '#fff';
                container.appendChild(p);
            }
        }

        // === GACHA SCAN ANIMATION ===
        let scanAnimSkipped = false;
        let scanAnimResolve = null;

        function skipScanAnimation() {
            scanAnimSkipped = true;
            if (scanAnimResolve) scanAnimResolve();
        }

        function waitMs(ms) {
            return new Promise(resolve => {
                scanAnimResolve = resolve;
                const timer = setTimeout(resolve, ms);
                const check = setInterval(() => {
                    if (scanAnimSkipped) { clearTimeout(timer); clearInterval(check); resolve(); }
                }, 50);
            });
        }

        async function showScanAnimation(monsterData, collResult, busSuggestion, questUpdates, barcodeInfo) {
            scanAnimSkipped = false;
            const overlay = document.getElementById('scanOverlay');
            const content = document.getElementById('scanStageContent');
            overlay.style.display = 'flex';

            // STAGE 1: Scan particles + vibrate (1s)
            content.innerHTML = `<div class="scan-stage">
                <div class="scan-particles-box">
                    <div class="scan-p"></div><div class="scan-p"></div><div class="scan-p"></div><div class="scan-p"></div>
                    <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:2.5rem">
                        ${shapes[monsterData.body_shape]||'&#x1F47E;'}
                    </div>
                </div>
                <div class="scan-text-anim">Scanning barcode...</div>
            </div>`;
            await waitMs(1000);
            if (scanAnimSkipped) { finishScanAnimation(monsterData, collResult, busSuggestion, questUpdates, barcodeInfo); return; }

            // STAGE 2: Energy convergence + rarity hint (2s)
            const rarityColors = {Common:'#888',Uncommon:'#4ecdc4',Rare:'#3b82f6',Epic:'#a855f7',Legendary:'#f59e0b'};
            const orbColor = rarityColors[monsterData.rarity] || '#e94560';
            const hints = {Common:'A creature stirs...',Uncommon:'An uncommon presence...',Rare:'A rare aura detected...!',Epic:'Incredible energy surges...!!',Legendary:'LEGENDARY POWER AWAKENS...!!!'};
            content.innerHTML = `<div class="scan-stage">
                <div class="energy-orbs-box">
                    <div class="energy-orb" style="background:${orbColor}"></div>
                    <div class="energy-orb" style="background:${orbColor}"></div>
                    <div class="energy-orb" style="background:${orbColor}"></div>
                    <div class="energy-orb" style="background:${orbColor}"></div>
                    <div class="energy-orb" style="background:${orbColor}"></div>
                    <div class="energy-orb" style="background:${orbColor}"></div>
                </div>
                <div class="rarity-hint-text" style="color:${orbColor}">${hints[monsterData.rarity]}</div>
            </div>`;
            await waitMs(2000);
            if (scanAnimSkipped) { finishScanAnimation(monsterData, collResult, busSuggestion, questUpdates, barcodeInfo); return; }

            // STAGE 3: Card flip reveal + star burst (1.5s)
            const bgClass = 'rarity-bg-' + monsterData.rarity.toLowerCase();
            const starRays = Array.from({length:12}, (_,i) =>
                `<div class="star-ray" style="transform:rotate(${i*30}deg);background:linear-gradient(to bottom,${orbColor}88,transparent);animation-delay:${i*0.03}s"></div>`
            ).join('');
            content.innerHTML = `<div class="scan-stage ${bgClass}" style="padding:20px;border-radius:16px;position:relative;min-width:300px">
                <div class="star-burst-box">${starRays}</div>
                <div class="card-reveal-wrap">
                    <div class="card-flip-anim">${renderMonsterCard(monsterData)}</div>
                </div>
            </div>`;
            // Add legendary particles to the revealed card
            if (monsterData.rarity === 'Legendary') {
                const card = content.querySelector('.monster-card');
                if (card) createLegendaryParticles(card);
            }
            await waitMs(1500);

            finishScanAnimation(monsterData, collResult, busSuggestion, questUpdates, barcodeInfo);
        }

        function finishScanAnimation(monsterData, collResult, busSuggestion, questUpdates, barcodeInfo) {
            const overlay = document.getElementById('scanOverlay');
            overlay.style.display = 'none';

            const newLabel = collResult.is_new ? '<div class="new-discovery">NEW DISCOVERY!</div>' : '';
            let busSug = '';
            if (busSuggestion) {
                busSug = `<div class="bus-suggestion"><span class="bs-label">Bus:</span> ${busSuggestion.room_emoji} ${busSuggestion.room_name} (${busSuggestion.grade} - ${busSuggestion.affinity}x)</div>`;
            }
            // Barcode product info
            let bcHtml = '';
            const bc = parseBarcodeComponents(monsterData.barcode);
            if (bc) {
                bcHtml = `<div class="scan-barcode-info"><div style="font-size:0.7rem;color:#4ecdc4;font-weight:600;margin-bottom:6px">BARCODE INFO</div>`;
                bcHtml += `<div style="font-family:monospace;font-size:0.85rem;letter-spacing:2px;color:#aaa;margin-bottom:4px">${bc.full}</div>`;
                bcHtml += `<div style="display:flex;gap:8px;flex-wrap:wrap;font-size:0.72rem;color:#888">`;
                bcHtml += `<span>Country: <b style="color:#ddd">${bc.country}</b></span>`;
                if (barcodeInfo && barcodeInfo.found) {
                    if (barcodeInfo.name) bcHtml += `<span>Product: <b style="color:#fff">${barcodeInfo.name}</b></span>`;
                    if (barcodeInfo.brand) bcHtml += `<span>Brand: <b style="color:#ddd">${barcodeInfo.brand}</b></span>`;
                    if (barcodeInfo.categories) bcHtml += `<span>Category: <b style="color:#ddd">${barcodeInfo.categories.split(',')[0]}</b></span>`;
                }
                bcHtml += '</div></div>';
            }
            const cardHtml = renderMonsterCard(monsterData);
            document.getElementById('scanResult').innerHTML = newLabel + cardHtml + bcHtml + busSug;
            if (monsterData.rarity === 'Legendary') {
                const card = document.getElementById('scanResult').querySelector('.monster-card');
                if (card) createLegendaryParticles(card);
            }
            if (questUpdates && questUpdates.length > 0) {
                questUpdates.forEach(q => showToast('Quest: ' + q.title));
            }
            // Add to recent catches
            addRecentCatch(monsterData);
        }

        // 초기 로드
        fetch('/api/player?session=default').then(r=>r.json()).then(d=>updatePlayerUI(d.player));
        loadRecentFromCollection();
        initHeroParticles();
        initHeroCreatures();

        // New UI initialization
        if (USE_NEW_UI) {
            initLandscape();
            switchView('LANDSCAPE');
        } else {
            document.body.classList.remove('old-tabs-hidden');
            const lv = document.getElementById('landscape-view');
            if (lv) lv.style.display = 'none';
        }
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    print("=" * 50)
    print("  BarcodeQuest Game Server - http://localhost:8001")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8001)
