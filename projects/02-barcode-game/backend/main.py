"""
BarcodeQuest - FastAPI 게임 서버
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

app = FastAPI(title="BarcodeQuest Game Server")

# 게임 상태 (인메모리 - 실제 프로덕션에서는 DB 사용)
generator = BarcodeMonsterGenerator()
battle_system = BattleSystem()
players = {}  # session_id → Player
collections = {}  # session_id → MonsterCollection


def get_or_create_player(session_id: str = "default") -> tuple:
    if session_id not in players:
        players[session_id] = Player(name="Trainer", player_id=session_id)
        collections[session_id] = MonsterCollection()
    return players[session_id], collections[session_id]


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

    return {
        "monster": monster_dict,
        "collection": coll_result,
        "inventory": add_result,
        "player": player.to_dict(),
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

    if is_player_win:
        player.total_wins += 1
        rewards = battle_system.get_battle_reward(p1, p2)
        exp_result = player.gain_exp(rewards["exp"])
        player.gain_gold(rewards["gold"])
    else:
        player.gain_exp(5)  # 패배해도 소량 경험치

    return {
        "result": "WIN" if is_player_win else "LOSE",
        "player_monster": {"name": player_monster_data["name"], "final_hp": p1.current_hp, "max_hp": p1.max_hp},
        "opponent": {"name": opponent_dict["name"], "rarity": opponent_dict["rarity"], "final_hp": p2.current_hp, "max_hp": p2.max_hp},
        "battle_log": battle_log,
        "rewards": rewards,
        "player": player.to_dict(),
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


GAME_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BarcodeQuest</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: #1a1a2e; color: #eee; min-height: 100vh; }
        .header { background: linear-gradient(135deg, #16213e, #0f3460); padding: 16px; display: flex; justify-content: space-between; align-items: center; }
        .header h1 { font-size: 1.3rem; color: #e94560; }
        .player-info { display: flex; gap: 12px; font-size: 0.8rem; }
        .player-info span { background: #16213e; padding: 4px 10px; border-radius: 8px; }
        .container { max-width: 600px; margin: 0 auto; padding: 16px; }
        .tabs { display: flex; gap: 4px; margin-bottom: 16px; }
        .tab { flex: 1; padding: 10px; text-align: center; background: #16213e; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 0.85rem; transition: all 0.2s; }
        .tab.active { background: #e94560; }
        .tab:hover { opacity: 0.8; }
        .panel { display: none; }
        .panel.active { display: block; }
        /* Scan Panel */
        .scan-area { text-align: center; padding: 30px 0; }
        .barcode-input { width: 100%; padding: 14px; border: 2px solid #e94560; border-radius: 12px; background: #16213e; color: white; font-size: 1.1rem; text-align: center; letter-spacing: 3px; margin-bottom: 12px; }
        .scan-btn { width: 100%; padding: 14px; background: linear-gradient(135deg, #e94560, #c23152); color: white; border: none; border-radius: 12px; font-size: 1.1rem; font-weight: 700; cursor: pointer; }
        .scan-btn:hover { transform: scale(1.02); }
        .scan-btn:disabled { background: #333; cursor: not-allowed; }
        /* Monster Card */
        .monster-card { background: linear-gradient(145deg, #16213e, #1a1a2e); border: 2px solid #333; border-radius: 16px; padding: 20px; margin: 16px 0; text-align: center; }
        .monster-card.rarity-Common { border-color: #666; }
        .monster-card.rarity-Uncommon { border-color: #4ecdc4; }
        .monster-card.rarity-Rare { border-color: #3b82f6; }
        .monster-card.rarity-Epic { border-color: #a855f7; }
        .monster-card.rarity-Legendary { border-color: #f59e0b; box-shadow: 0 0 20px rgba(245,158,11,0.3); }
        .monster-name { font-size: 1.3rem; font-weight: 700; margin: 10px 0 5px; }
        .monster-type { font-size: 0.85rem; color: #aaa; }
        .rarity-badge { display: inline-block; padding: 3px 12px; border-radius: 12px; font-size: 0.8rem; font-weight: 700; margin: 8px 0; }
        .rarity-Common { background: #444; }
        .rarity-Uncommon { background: #0f766e; }
        .rarity-Rare { background: #1d4ed8; }
        .rarity-Epic { background: #7c3aed; }
        .rarity-Legendary { background: #d97706; }
        .stats-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin: 12px 0; }
        .stat { text-align: center; }
        .stat .label { font-size: 0.65rem; color: #888; }
        .stat .val { font-size: 1rem; font-weight: 700; }
        .monster-visual { font-size: 3rem; margin: 10px; }
        .trait { font-size: 0.8rem; color: #e94560; font-style: italic; margin-top: 8px; }
        /* Battle */
        .battle-arena { text-align: center; }
        .battle-btn { padding: 14px 40px; background: #e94560; color: white; border: none; border-radius: 12px; font-size: 1rem; font-weight: 700; cursor: pointer; margin: 16px 0; }
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
        .energy-fill { height: 100%; background: #4ecdc4; border-radius: 3px; transition: width 0.3s; }
        .sample-codes { margin-top: 12px; }
        .sample-codes button { background: #16213e; border: 1px solid #333; color: #aaa; padding: 6px 10px; border-radius: 8px; margin: 3px; cursor: pointer; font-size: 0.75rem; }
        .sample-codes button:hover { border-color: #e94560; color: white; }
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
            <div class="tab" onclick="showTab('collection')">Collection</div>
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
                <p style="margin-bottom:12px;color:#888">파티의 첫 번째 몬스터로 배틀!</p>
                <button class="battle-btn" onclick="startBattle()">BATTLE START!</button>
                <div id="battleResult"></div>
                <div class="battle-log" id="battleLog" style="display:none"></div>
            </div>
        </div>

        <!-- COLLECTION TAB -->
        <div class="panel" id="panel-collection">
            <div class="coll-stats" id="collStats"></div>
            <div id="collList"></div>
        </div>
    </div>

    <script>
        function showTab(name) {
            document.querySelectorAll('.tab').forEach((t,i) => t.classList.toggle('active', ['scan','battle','collection'][i]===name));
            document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
            document.getElementById('panel-'+name).classList.add('active');
            if (name==='collection') loadCollection();
        }

        function fillBarcode(code) { document.getElementById('barcodeInput').value = code; }

        function updatePlayerUI(p) {
            document.getElementById('pLevel').textContent = `Lv.${p.level}`;
            document.getElementById('pGold').textContent = `${p.gold}G`;
            document.getElementById('pEnergy').textContent = `${p.energy}E`;
            const pct = (p.energy/p.max_energy*100);
            document.getElementById('energyBar').style.width = pct+'%';
            document.getElementById('energyText').textContent = `Energy: ${p.energy}/${p.max_energy}`;
        }

        function renderMonsterCard(m) {
            const shapes = {Dragon:'&#x1F432;',Fox:'&#x1F98A;',Bear:'&#x1F43B;',Bird:'&#x1F426;',Slime:'&#x1F47E;',Golem:'&#x1F5FF;',Ghost:'&#x1F47B;',Cat:'&#x1F431;',Wolf:'&#x1F43A;',Turtle:'&#x1F422;'};
            const icon = shapes[m.body_shape] || '&#x1F47E;';
            return `<div class="monster-card rarity-${m.rarity}">
                <div class="monster-visual">${icon}</div>
                <div class="monster-name">${m.name}</div>
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

        async function scanBarcode() {
            const code = document.getElementById('barcodeInput').value.trim();
            if (code.length !== 13) { alert('13자리 바코드를 입력하세요!'); return; }
            document.getElementById('scanBtn').disabled = true;
            try {
                const r = await fetch(`/api/scan?barcode=${code}&session=default`, {method:'POST'});
                const d = await r.json();
                if (d.error) { alert(d.error); return; }
                updatePlayerUI(d.player);
                const newLabel = d.collection.is_new ? '<div style="color:#f59e0b;font-size:1.2rem;font-weight:700;margin:8px">NEW DISCOVERY!</div>' : '';
                document.getElementById('scanResult').innerHTML = newLabel + renderMonsterCard(d.monster);
            } catch(e) { console.error(e); }
            finally { document.getElementById('scanBtn').disabled = false; }
        }

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
        }

        async function loadCollection() {
            const r = await fetch('/api/collection?session=default');
            const d = await r.json();
            document.getElementById('collStats').innerHTML = `
                <div class="coll-stat"><div class="num">${d.total}</div><div class="lbl">Total</div></div>
                <div class="coll-stat"><div class="num">${d.stats.by_rarity?.Rare||0}</div><div class="lbl">Rare+</div></div>
                <div class="coll-stat"><div class="num">${d.rewards.length}</div><div class="lbl">Rewards</div></div>`;
            const shapes = {Dragon:'&#x1F432;',Fox:'&#x1F98A;',Bear:'&#x1F43B;',Bird:'&#x1F426;',Slime:'&#x1F47E;',Golem:'&#x1F5FF;',Ghost:'&#x1F47B;',Cat:'&#x1F431;',Wolf:'&#x1F43A;',Turtle:'&#x1F422;'};
            document.getElementById('collList').innerHTML = (d.monsters||[]).map(m => {
                const icon = shapes[m.body_shape]||'&#x1F47E;';
                return `<div class="mini-card"><div class="mc-icon">${icon}</div><div class="mc-info"><div class="mc-name">${m.name}</div><div class="mc-sub">${m.primary_type} | ${m.rarity} | Lv.${m.level}</div></div><span class="rarity-badge rarity-${m.rarity}" style="font-size:0.7rem">${m.rarity}</span></div>`;
            }).join('') || '<p style="color:#888;text-align:center;padding:20px">도감이 비어있습니다. 바코드를 스캔하세요!</p>';
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
