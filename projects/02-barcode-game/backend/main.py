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

app = FastAPI(title="BarcodeQuest Game Server v2.0")

# 게임 엔진 인스턴스
generator = BarcodeMonsterGenerator()
battle_system = BattleSystem()
expedition_system = ExpeditionSystem()
evolution_system = EvolutionSystem()
daily_quest_system = DailyQuestSystem()

# 플레이어 상태 (인메모리 - 실제 프로덕션에서는 DB 사용)
players = {}       # session_id → Player
collections = {}   # session_id → MonsterCollection
inventories = {}   # session_id → ItemInventory


def get_or_create_player(session_id: str = "default") -> tuple:
    if session_id not in players:
        players[session_id] = Player(name="Trainer", player_id=session_id)
        collections[session_id] = MonsterCollection()
        inventories[session_id] = ItemInventory()
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

    if not player.use_energy(10):
        return {"error": "에너지 부족! 잠시 후 다시 시도하세요.", "energy": player.energy}

    player.total_scans += 1

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

    return {
        "monster": monster_dict,
        "collection": coll_result,
        "inventory": add_result,
        "player": player.to_dict(),
        "quest_updates": quest_updates,
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


GAME_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BarcodeQuest v2</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: #1a1a2e; color: #eee; min-height: 100vh; }
        .header { background: linear-gradient(135deg, #16213e, #0f3460); padding: 16px; display: flex; justify-content: space-between; align-items: center; }
        .header h1 { font-size: 1.3rem; background: linear-gradient(135deg, #e94560, #f093fb); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .player-info { display: flex; gap: 8px; font-size: 0.75rem; }
        .player-info span { background: #16213e; padding: 4px 8px; border-radius: 8px; }
        .container { max-width: 600px; margin: 0 auto; padding: 12px; }
        .tabs { display: flex; gap: 3px; margin-bottom: 12px; }
        .tab { flex: 1; padding: 8px 4px; text-align: center; background: #16213e; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 0.72rem; transition: all 0.2s; }
        .tab.active { background: linear-gradient(135deg, #e94560, #c23152); }
        .tab:hover { opacity: 0.8; }
        .panel { display: none; }
        .panel.active { display: block; }
        /* Scan Panel */
        .scan-area { text-align: center; padding: 20px 0; }
        .barcode-input { width: 100%; padding: 14px; border: 2px solid #e94560; border-radius: 12px; background: #16213e; color: white; font-size: 1.1rem; text-align: center; letter-spacing: 3px; margin-bottom: 12px; outline: none; }
        .barcode-input:focus { border-color: #f093fb; box-shadow: 0 0 12px rgba(233,69,96,0.3); }
        .scan-btn { width: 100%; padding: 14px; background: linear-gradient(135deg, #e94560, #c23152); color: white; border: none; border-radius: 12px; font-size: 1.1rem; font-weight: 700; cursor: pointer; transition: transform 0.1s; }
        .scan-btn:hover { transform: scale(1.02); }
        .scan-btn:active { transform: scale(0.98); }
        .scan-btn:disabled { background: #333; cursor: not-allowed; transform: none; }
        /* Monster Card with animation */
        .monster-card { background: linear-gradient(145deg, #16213e, #1a1a2e); border: 2px solid #333; border-radius: 16px; padding: 20px; margin: 16px 0; text-align: center; animation: cardAppear 0.5s ease-out; }
        @keyframes cardAppear { from { opacity:0; transform: scale(0.8) rotateY(90deg); } to { opacity:1; transform: scale(1) rotateY(0); } }
        .monster-card.rarity-Common { border-color: #666; }
        .monster-card.rarity-Uncommon { border-color: #4ecdc4; }
        .monster-card.rarity-Rare { border-color: #3b82f6; box-shadow: 0 0 10px rgba(59,130,246,0.2); }
        .monster-card.rarity-Epic { border-color: #a855f7; box-shadow: 0 0 15px rgba(168,85,247,0.3); animation: cardAppear 0.5s ease-out, epicGlow 2s ease-in-out infinite; }
        @keyframes epicGlow { 0%,100% { box-shadow: 0 0 15px rgba(168,85,247,0.3); } 50% { box-shadow: 0 0 25px rgba(168,85,247,0.5); } }
        .monster-card.rarity-Legendary { border-color: #f59e0b; box-shadow: 0 0 25px rgba(245,158,11,0.4); animation: cardAppear 0.5s ease-out, legendGlow 1.5s ease-in-out infinite; }
        @keyframes legendGlow { 0%,100% { box-shadow: 0 0 25px rgba(245,158,11,0.4); } 50% { box-shadow: 0 0 40px rgba(245,158,11,0.7); } }
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
        .monster-visual { font-size: 3rem; margin: 10px; animation: float 3s ease-in-out infinite; }
        @keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
        .trait { font-size: 0.8rem; color: #e94560; font-style: italic; margin-top: 8px; }
        /* Battle */
        .battle-arena { text-align: center; }
        .battle-btn { padding: 14px 40px; background: linear-gradient(135deg, #e94560, #c23152); color: white; border: none; border-radius: 12px; font-size: 1rem; font-weight: 700; cursor: pointer; margin: 16px 0; transition: transform 0.1s; }
        .battle-btn:hover { transform: scale(1.02); }
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
        .energy-bar { width: 100%; height: 6px; background: #333; border-radius: 3px; margin: 4px 0; }
        .energy-fill { height: 100%; background: linear-gradient(90deg, #4ecdc4, #7ee8fa); border-radius: 3px; transition: width 0.3s; }
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
        /* NEW discovery effect */
        .new-discovery { color: #f59e0b; font-size: 1.2rem; font-weight: 700; margin: 8px; animation: pulse 1s ease-in-out infinite; }
        @keyframes pulse { 0%,100% { transform: scale(1); } 50% { transform: scale(1.05); } }
    </style>
</head>
<body>
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
        </div>

        <!-- SCAN TAB -->
        <div class="panel active" id="panel-scan">
            <div class="scan-area">
                <div style="margin-bottom:8px">
                    <div class="energy-bar"><div class="energy-fill" id="energyBar" style="width:100%"></div></div>
                    <span style="font-size:0.75rem;color:#888" id="energyText">Energy: 100/100</span>
                </div>
                <input class="barcode-input" id="barcodeInput" placeholder="바코드 13자리 입력" maxlength="13" />
                <button class="scan-btn" id="scanBtn" onclick="scanBarcode()">SCAN!</button>
                <div class="sample-codes">
                    <span style="font-size:0.75rem;color:#666">샘플:</span>
                    <button onclick="fillBarcode('8801062871247')">초코파이</button>
                    <button onclick="fillBarcode('8801043150842')">신라면</button>
                    <button onclick="fillBarcode('4902105231456')">Pocky</button>
                    <button onclick="fillBarcode('0012345678905')">US Snack</button>
                    <button onclick="fillBarcode('8801115114505')">서울우유</button>
                </div>
            </div>
            <div id="scanResult"></div>
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
            <div id="collList"></div>
        </div>

        <!-- QUEST TAB -->
        <div class="panel" id="panel-quest">
            <h3 style="margin-bottom:8px;font-size:1rem">일일 퀘스트</h3>
            <div id="questSummary" style="margin-bottom:12px"></div>
            <div id="questList"></div>
        </div>
    </div>

    <script>
        const TABS = ['scan','battle','expedition','collection','quest'];
        const shapes = {Dragon:'&#x1F432;',Fox:'&#x1F98A;',Bear:'&#x1F43B;',Bird:'&#x1F426;',Slime:'&#x1F47E;',Golem:'&#x1F5FF;',Ghost:'&#x1F47B;',Cat:'&#x1F431;',Wolf:'&#x1F43A;',Turtle:'&#x1F422;'};

        function showTab(name) {
            document.querySelectorAll('.tab').forEach((t,i) => t.classList.toggle('active', TABS[i]===name));
            document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
            document.getElementById('panel-'+name).classList.add('active');
            if (name==='collection') loadCollection();
            if (name==='expedition') loadExpedition();
            if (name==='quest') loadQuests();
        }

        function fillBarcode(code) { document.getElementById('barcodeInput').value = code; }

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
            document.getElementById('energyText').textContent = `Energy: ${p.energy}/${p.max_energy}`;
        }

        function renderMonsterCard(m) {
            const icon = shapes[m.body_shape] || '&#x1F47E;';
            const evolved = m.evolved ? '<span style="color:#f093fb;font-size:0.7rem"> EVOLVED</span>' : '';
            return `<div class="monster-card rarity-${m.rarity}">
                <div class="monster-visual">${icon}</div>
                <div class="monster-name">${m.name}${evolved}</div>
                <div class="monster-type">${m.primary_type} / ${m.secondary_type}</div>
                <span class="rarity-badge rarity-${m.rarity}">${m.rarity}</span>
                <div class="stats-grid">
                    <div class="stat"><div class="val">${m.stats.hp}</div><div class="label">HP</div></div>
                    <div class="stat"><div class="val">${m.stats.attack}</div><div class="label">ATK</div></div>
                    <div class="stat"><div class="val">${m.stats.defense}</div><div class="label">DEF</div></div>
                    <div class="stat"><div class="val">${m.stats.speed}</div><div class="label">SPD</div></div>
                    <div class="stat"><div class="val">${m.stats.special}</div><div class="label">SPC</div></div>
                </div>
                <div class="trait">"${m.special_trait}"</div>
                <div style="font-size:0.7rem;color:#666;margin-top:8px">${m.body_shape} | ${m.color} | ${m.accessory} | ${m.time_variant}</div>
            </div>`;
        }

        // === SCAN ===
        async function scanBarcode() {
            const code = document.getElementById('barcodeInput').value.trim();
            if (code.length !== 13) { alert('13자리 바코드를 입력하세요!'); return; }
            document.getElementById('scanBtn').disabled = true;
            try {
                const r = await fetch(`/api/scan?barcode=${code}&session=default`, {method:'POST'});
                const d = await r.json();
                if (d.error) { alert(d.error); return; }
                updatePlayerUI(d.player);
                const newLabel = d.collection.is_new ? '<div class="new-discovery">NEW DISCOVERY!</div>' : '';
                document.getElementById('scanResult').innerHTML = newLabel + renderMonsterCard(d.monster);
                if (d.quest_updates && d.quest_updates.length > 0) {
                    d.quest_updates.forEach(q => showToast(`Quest Complete: ${q.title}`));
                }
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
            document.getElementById('collStats').innerHTML = `
                <div class="coll-stat"><div class="num">${d.total}</div><div class="lbl">Total</div></div>
                <div class="coll-stat"><div class="num">${rare}</div><div class="lbl">Rare+</div></div>
                <div class="coll-stat"><div class="num">${d.rewards.length}</div><div class="lbl">Rewards</div></div>`;
            document.getElementById('collList').innerHTML = (d.monsters||[]).map(m => {
                const icon = shapes[m.body_shape]||'&#x1F47E;';
                return `<div class="mini-card"><div class="mc-icon">${icon}</div><div class="mc-info"><div class="mc-name">${m.name}</div><div class="mc-sub">${m.primary_type} | ${m.rarity} | Lv.${m.level}</div></div><span class="rarity-badge rarity-${m.rarity}" style="font-size:0.7rem">${m.rarity}</span></div>`;
            }).join('') || '<p style="color:#888;text-align:center;padding:20px">도감이 비어있습니다. 바코드를 스캔하세요!</p>';
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

        // 초기 로드
        fetch('/api/player?session=default').then(r=>r.json()).then(d=>updatePlayerUI(d.player));
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    print("=" * 50)
    print("  BarcodeQuest Game Server - http://localhost:8001")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8001)
