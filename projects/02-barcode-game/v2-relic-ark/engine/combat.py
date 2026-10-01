"""배치 방어 전투 — 1막의 핵심 플레이 (COMBAT_AND_DEFENSE.md 구현).

> **돔 바깥에서 물고기들이 들이친다. 플레이어는 안의 사람들을 옮기고 배치해서 막는다.**

이 모듈은 **순수 함수**만 가진다. DB·HTTP·시간을 모른다(시각은 호출자가 넘긴다).
server.py 가 상태를 읽어 넘기고, 돌아온 결과를 상태에 쓴다. 그래야 같은 입력이면
같은 결과가 나오고(02_DEV **D6**), 테스트가 서버 없이 돈다.

설계 근거
  COMBAT_AND_DEFENSE.md §3 흐름(소리→실루엣→접촉→대응→결과→흔적)
                       §4 생물별 대응(같은 습격도 배치에 따라 결과가 다르다)
                       §6 아늑함 안전장치 / §6.5 대응 도구 일곱 / §9 준비 단계 권장안
  WORLD_BIBLE_DEEP.md  §3 큰 것들(긴목·문지기·손톱 무리·동거 문어)
  DECISIONS 2026-10-01 "죽이는 것이 주된 동사가 아니다" — 여기에 공격·피해량·HP 는 없다.
                       동사는 **끄다 · 모이다 · 들이다 · 가리다 · 꿰매다** 다섯뿐이다.
"""
from __future__ import annotations

import random

# ─────────────────────────────────────────────────────────────
# 1. 바깥에서 오는 것들 (COMBAT_AND_DEFENSE §4 표를 그대로 코드로)
#    gate = **그 종을 막는 단 하나의 조건**. 점수로 뭉개지 않는다 —
#    "같은 방식의 반복이 이 장르를 지루하게 만드는 주범"(§4)이라 종마다 동사가 다르다.
# ─────────────────────────────────────────────────────────────
CREATURES = {
    "swarm": {
        "id": "swarm", "name": "작은 떼", "zone": "무광층", "threat": True,
        "gate": "people",                       # 그 방 사람 수
        "gate_need": 2,                         # +severity
        "how": "사람 수로 막는다. 누구든 여럿이면 된다.",
        "sound": "물이 잘게 끓는다. 이음매 쪽에서 긁는 소리가 번진다.",
        "silhouette": "작은 그림자 수십이 창을 따라 흐른다. 하나하나는 손바닥만 하다.",
        "contact": "이음매마다 작은 입이 붙는다. 손이 모자라면 어디부터 막을지 고를 수 없다.",
        "role_tags": ["방어", "부품"],
        "imprints": ["crack_seen"],
        "hold_flags": [], "breach_flags": ["room_sealed"],
        "need": 4.0,
        "audio": {"sound": "sfx_water_splash.ogg", "contact": "sfx_glass_crack.ogg"},
    },
    "longneck": {
        "id": "longneck", "name": "긴목", "zone": "박광층", "threat": True,
        "gate": "lights_off",                   # 그 방의 불을 끈다
        "gate_need": 0,
        "how": "불을 끈다. 끄면 우리도 그 방을 못 본다.",
        "sound": "두드리는 소리. 똑, 똑. 사람이 내는 소리를 흉내 낸 것이다.",
        "silhouette": "목이 먼저 온다. 몸은 아직 어둠 속인데 창 앞에는 목만 와 있다.",
        "contact": "얼굴을 유리에 붙이고 들여다본다. 해치려는 것이 아니라 궁금한 것이다.",
        "role_tags": ["전력"],
        "imprints": ["knock_heard", "crack_seen"],
        "hold_flags": ["beast_left"], "breach_flags": ["room_sealed"],
        "need": 3.0,
        "audio": {"sound": "sfx_knock_glass.ogg", "contact": "sfx_glass_crack.ogg"},
        "avoid_tool": "lure_lamp",              # 유인 등불이 있는 방은 지나친다
    },
    "warden": {
        "id": "warden", "name": "문지기", "zone": "무광층 경계", "threat": True,
        "gate": "quiet",                        # 전원을 내리고 한 방에 모인다
        "gate_need": 0,
        "how": "소리를 죽인다. 전원을 내리고 모두 한 방에 모인다.",
        "sound": "다른 소리가 전부 사라진다. 물이 조용해지면 온 것이다.",
        "silhouette": "그림자가 아니라 압력이 먼저 온다. 유리가 한 번 휜다.",
        "contact": "바다가 숨을 들이켰다. 돔 전체가 한 뼘 눌린다.",
        "role_tags": ["전력", "방어"],
        "imprints": ["knock_heard"],
        "hold_flags": ["beast_left"], "breach_flags": ["room_sealed"],
        "need": 3.0,
        "audio": {"sound": "amb_far_call.ogg", "contact": "sfx_glass_crack.ogg"},
    },
    "claws": {
        "id": "claws", "name": "손톱 무리", "zone": "해구", "threat": True,
        "gate": "all_inside",                   # 밖에 있는 사람을 즉시 들인다
        "gate_need": 0,
        "how": "밖에 나간 사람을 즉시 들인다. 잠수복 이음매를 정확히 찾는다.",
        "sound": "아무 소리도 없다. 그들은 소리를 못 듣고 냄새로 온다.",
        "silhouette": "바닥 쪽에서 모래가 들린다. 느리고 작고 수백이다.",
        "contact": "이음매를 찾는 손톱. 밖에 사람이 있으면 사람부터 찾는다.",
        "role_tags": ["탐사"],
        "imprints": ["saved_breath"],
        "hold_flags": [], "breach_flags": ["room_sealed"],
        "need": 3.0,
        "audio": {"sound": "amb_outside_deep.ogg", "contact": "sfx_air_low.ogg"},
    },
    "octopus": {
        # 위협이 아니라 **식구**다. 공격하지 않는다. 오히려 다음에 오는 것을 미리 알린다.
        # 문어는 어떤 매체에서도 발화하지 않는다(DECISIONS 2026-09-27) — 아래 문장에
        # 따옴표·의성어·생각자막이 없는 이유다. 행동과 자리로만 말한다.
        "id": "octopus", "name": "동거 문어", "zone": "돔 안팎", "threat": False,
        "gate": "none", "gate_need": 0,
        "how": "막을 것이 없다. 식구다.",
        "sound": "에어락 쪽에서 작게 빨판 소리가 난다.",
        "silhouette": "창 밖을 한 바퀴 돌고, 한 방 앞에 멈춰 붙는다.",
        "contact": "붙어 있던 자리에서 떨어져 안으로 들어온다. 무언가를 물고 왔다.",
        "role_tags": [], "imprints": [],
        "hold_flags": [], "breach_flags": [],
        "need": 0.0,
        "audio": {"sound": "sfx_water_splash.ogg", "contact": "sfx_collect.ogg"},
    },
}
# 뽑기 가중치. 문어가 자주 와야 한다(§6-1 "조용한 날이 더 많아야 한다" — 문어의 날은 조용한 날이다).
CREATURE_WEIGHT = {"swarm": 3, "longneck": 3, "warden": 1, "claws": 2, "octopus": 3}

STAGES = ("sound", "silhouette", "contact", "done")
STAGE_KO = {"sound": "소리", "silhouette": "실루엣", "contact": "접촉", "done": "지나갔다"}

# ─────────────────────────────────────────────────────────────
# 2. 대응 도구 일곱 (COMBAT_AND_DEFENSE §6.5 — 확정표 그대로)
#    무기가 아니다. 막고 가리고 꿰매고 부르는 물건이다.
#    kind: consumable 소모 / install 설치 / durable 내구 / permanent 영구
# ─────────────────────────────────────────────────────────────
TOOLS = {
    "patch": {
        "id": "patch", "name": "봉합 패치", "kind": "consumable",
        "does": "유리 균열과 잠수복 이음매를 막는다", "against": ["swarm"],
        "cost": {"cloth": 2, "med": 1},
        "power": {"swarm": 1.5, "_any": 0.5}, "hands": 1,
        "heals_crack": True,
    },
    "shutter": {
        "id": "shutter", "name": "차광 덧문", "kind": "install",
        "does": "방을 즉시 어둡게 한다", "against": ["longneck"],
        "cost": {"cloth": 2, "parts": 2},
        "power": {"longneck": 1.0},
        "forces_dark": True,                    # 설치된 방은 조명 상태와 무관하게 어둡다
    },
    "lure_lamp": {
        "id": "lure_lamp", "name": "유인 등불", "kind": "install",
        "does": "돔에서 떨어진 곳에 불을 켜 둔다", "against": ["longneck"],
        "cost": {"parts": 2, "power": 2},
        "power": {"longneck": 1.0},
        "diverts": "longneck",                  # 이 방은 긴목의 목표가 되지 않는다
    },
    "hush": {
        "id": "hush", "name": "소리 가리개", "kind": "install",
        "does": "방의 소리를 먹는다", "against": ["warden"],
        "cost": {"cloth": 3, "parts": 1},
        "power": {"warden": 1.0},
        "silences": True,                       # 여기 모이면 전원을 내리지 않아도 조용하다
    },
    "beacon": {
        "id": "beacon", "name": "귀환 신호기", "kind": "consumable",
        "does": "밖에 있는 사람을 즉시 부른다", "against": ["claws"],
        "cost": {"parts": 1, "knowledge": 1},
        "power": {"claws": 1.0},
        "recalls": True,                        # 쓰면 밖의 사람이 전부 들어온다
    },
    "long_net": {
        "id": "long_net", "name": "긴 장대 그물", "kind": "durable",
        "does": "밀어내고 떼어 낸다. 다치게 하지 않는다", "against": ["swarm", "longneck", "warden", "claws"],
        "cost": {"cloth": 2, "parts": 3},
        "power": {"_any": 2.0}, "hands": 1,
        "uses": 3,                              # 세 번 쓰면 해진다
    },
    "brace": {
        "id": "brace", "name": "이음매 보강대", "kind": "permanent",
        "does": "그 방의 기본 방어를 올린다", "against": ["swarm", "longneck", "warden", "claws"],
        "cost": {"parts": 3, "knowledge": 2},
        "power": {"_any": 2.0}, "hands": 1,
    },
}
INSTALLED_KINDS = ("install", "durable", "permanent")      # 방에 붙는 것
CARRY_KINDS = ("consumable",)                              # 접촉 순간에 쓰는 것

# 방 정원 — 방 크기별 2~4명 (COMBAT_AND_DEFENSE §9 "방 정원은 몇 명인가"에 대한 답).
# 좁은 방(정수·서고)은 2, 보통 3, 넓은 방(창고·공방)은 4.
ROOM_CAP = {"pantry": 4, "well": 2, "infirmary": 3, "library": 2, "workshop": 4}
ROOM_CAP_DEFAULT = 3
HALL_KO = "홀"           # 배치되지 않은 사람이 모이는 곳 = 돔 상부의 공용 공간

# 결과 등급. 실패가 즉사가 아니다(§6-3) — 최악이 방 하나이고 그조차 화면에 남아 이야기가 된다.
HELD, SCARRED, BREACHED, PASSED = "held", "scarred", "breached", "passed"
RESULT_KO = {HELD: "막았다", SCARRED: "유리에 금이 갔다", BREACHED: "방을 잃었다", PASSED: "지나갔다"}


def room_cap(room_id: str) -> int:
    return ROOM_CAP.get(room_id, ROOM_CAP_DEFAULT)


def josa(word: str, pair: tuple = ("이", "가")) -> str:
    """받침에 맞는 조사. 「식량창고이 어두워지자」 같은 문장을 막는다 — 화면에 보이는 한국어는 사람이 쓴 것처럼."""
    if not word:
        return pair[1]
    code = ord(word[-1])
    if 0xAC00 <= code <= 0xD7A3:
        return pair[0] if (code - 0xAC00) % 28 else pair[1]
    return pair[1]


# ─────────────────────────────────────────────────────────────
# 3. 습격 뽑기 — 하루 1회 이하, 조용한 날이 더 많다 (§6-1)
# ─────────────────────────────────────────────────────────────
RAID_CHANCE = 0.45           # 그날 무언가 오기는 할 확률. 그중 1/3 가까이가 문어(= 조용한 날)
RAID_FIRST_DAY = 2           # 첫날은 아무것도 오지 않는다. 처음 하루는 들여다보기만 한다


def raid_rng(uid: str, day: int, purpose: str = "") -> random.Random:
    """습격에 쓰는 난수는 전부 `uid|day|목적` 시드다(D6). 같은 방주의 같은 날은 늘 같은 습격."""
    return random.Random(f"{uid}|{day}|raid{('|' + purpose) if purpose else ''}")


def pick_creature(uid: str, day: int, force: str | None = None) -> dict | None:
    if force:
        return CREATURES.get(force)
    if day < RAID_FIRST_DAY:
        return None
    if raid_rng(uid, day, "roll").random() >= RAID_CHANCE:
        return None
    ids = sorted(CREATURE_WEIGHT)
    pick = raid_rng(uid, day, "who").choices(ids, weights=[CREATURE_WEIGHT[i] for i in ids], k=1)[0]
    return CREATURES[pick]


def pick_target(uid: str, day: int, creature: dict, rooms: list[dict], room_tools: dict) -> int | None:
    """어느 방으로 오는가. 침수된 방에는 오지 않고(이미 물이다), 유인 등불이 있는 방은 긴목이 지나친다."""
    live = [r for r in rooms if not r.get("flooded")]
    if not live:
        return None
    divert = creature.get("avoid_tool")
    cand = live
    if divert:
        safe = [r for r in live if divert not in [t.get("id") for t in room_tools.get(str(r["slot"]), [])]]
        cand = safe          # 전부 보호돼 있으면 빈 목록 → 호출자가 '방향을 틀어 떠났다'로 읽는다
    if not cand:
        return None
    slots = sorted(r["slot"] for r in cand)
    return raid_rng(uid, day, "where").choice(slots)


def severity(uid: str, day: int) -> int:
    """0·1·2. 세기도 시드에서 나온다 — 같은 날은 늘 같은 세기."""
    return raid_rng(uid, day, "sev").choices([0, 1, 2], weights=[5, 3, 2], k=1)[0]


# ─────────────────────────────────────────────────────────────
# 4. 방어 판정 — **공식 하나**. 난수가 한 톨도 들어가지 않는다 (D6)
#
#   score = 방 1.0
#         + Σ 사람          (성함 1.0 / 부상 0.5)
#         + Σ 역할 태그 일치 1.5
#         + Σ 각인 일치      1.5
#         + Σ 설치 도구 세기 (그 생물 전용 값, 없으면 _any)
#         + Σ 소모품 세기    (이번 접촉에 쓴 것)
#         + 관문 통과         3.0
#   need  = 생물 기본값 + severity(0~2)
#
#   관문(gate)이 **먼저**다. 관문을 못 넘기면 점수가 아무리 높아도 막을 수 없다.
#     swarm       people      그 방 사람 수 ≥ 2 + severity
#     longneck    lights_off  그 방의 불이 꺼져 있다(차광 덧문도 같은 효과)
#     warden      quiet       전원이 내려가 있고 모두 한 방에 있다(소리 가리개 방이면 전원 무관)
#     claws       all_inside  밖에 있는 사람이 0명
#     octopus     none        관문도 판정도 없다. 식구다
#
#   판정
#     관문 통과 & score ≥ need            → 막았다
#     관문 통과 & need-2 ≤ score < need   → 유리에 금
#     관문 실패 & score ≥ need-2          → 유리에 금
#     그 밖                                 → 방을 잃는다
# ─────────────────────────────────────────────────────────────
W_ROOM, W_TAG, W_IMPRINT, W_GATE = 1.0, 1.5, 1.5, 3.0
# 사람 한 명의 무게는 **담**이 정한다(RESIDENT_STATS §4 "방어 판정 = 역할 태그 + 담 + 각인 + 도구").
# 담 5(보통) = 1.0 으로 옛 값과 같고, 담 1 = 0.6, 담 10 = 1.5. 부상이면 절반.
W_NERVE_BASE, W_NERVE_STEP, HURT_MUL = 0.5, 0.1, 0.5
SCAR_BAND = 2.0          # need 아래 이만큼까지는 '금'에서 멈춘다. 그 아래가 상실


def person_weight(p: dict) -> float:
    nv = p.get("nerve")
    nv = 5 if not isinstance(nv, (int, float)) else max(1, min(10, int(nv)))
    w = W_NERVE_BASE + W_NERVE_STEP * nv
    return round(w * (HURT_MUL if p.get("injured") else 1.0), 2)


def gate_state(creature: dict, ctx: dict) -> dict:
    """관문 한 줄. ctx 는 server.py 가 모아 주는 그 순간의 사실들."""
    g = creature.get("gate", "none")
    sev = int(ctx.get("severity", 0))
    if g == "people":
        # 사람 수가 관문이다. 다만 손이 모자랄 때 **도구가 한 사람 몫을 한다**(봉합 패치·긴 장대 그물·
        # 이음매 보강대). 좁은 방(정원 2)이 센 떼를 영영 못 막는 막다른 골목을 피하려는 장치다.
        need = creature.get("gate_need", 2) + sev
        hands = int(ctx.get("hands", 0))
        have = len(ctx.get("people", [])) + hands
        extra = f" + 도구 {hands}" if hands else ""
        return {"kind": g, "ok": have >= need, "have": have, "need": need,
                "ko": f"그 방에 {need}명 이상 (지금 {len(ctx.get('people', []))}명{extra})"}
    if g == "lights_off":
        ok = (not ctx.get("light_on", True)) or ctx.get("forced_dark", False)
        return {"kind": g, "ok": ok, "have": 0 if ok else 1, "need": 0,
                "ko": "그 방의 불을 끈다" + ("" if ok else " — 지금 켜져 있다")}
    if g == "quiet":
        gathered = ctx.get("gathered_one_room", False)
        quiet = (not ctx.get("power_on", True)) or ctx.get("hushed", False)
        ok = gathered and quiet
        return {"kind": g, "ok": ok, "have": int(gathered) + int(quiet), "need": 2,
                "ko": "전원을 내리고 모두 한 방에" +
                      ("" if ok else f" — {'모이지 않았다' if not gathered else '소리가 남아 있다'}")}
    if g == "all_inside":
        out = len(ctx.get("outside", []))
        return {"kind": g, "ok": out == 0, "have": out, "need": 0,
                "ko": "밖에 있는 사람을 들인다" + ("" if out == 0 else f" — 아직 {out}명 밖에 있다")}
    return {"kind": "none", "ok": True, "have": 0, "need": 0, "ko": "막을 것이 없다"}


def tool_power(tool_id: str, creature_id: str) -> float:
    p = (TOOLS.get(tool_id) or {}).get("power") or {}
    return float(p.get(creature_id, p.get("_any", 0.0)))


def evaluate(creature: dict, ctx: dict) -> dict:
    """방어 판정. 같은 ctx 면 늘 같은 dict 를 돌려준다(난수 없음)."""
    if not creature.get("threat"):
        return {"result": PASSED, "result_ko": RESULT_KO[PASSED], "score": 0.0, "need": 0.0,
                "margin": 0.0, "gate": gate_state(creature, ctx), "parts": [], "used": []}

    people = ctx.get("people", [])
    tags = set(creature.get("role_tags", []))
    imps = set(creature.get("imprints", []))
    parts: list[dict] = []
    score = 0.0

    if ctx.get("room_id"):
        score += W_ROOM
        parts.append({"ko": "방이 있다", "v": W_ROOM})
    for p in people:
        w = person_weight(p)
        score += w
        parts.append({"ko": f"{p.get('name')} · 담 {p.get('nerve', 5)}" + (" (부상)" if p.get("injured") else ""), "v": w})
        hit = sorted(set(p.get("counter_tags") or []) & tags)
        if hit:
            score += W_TAG
            parts.append({"ko": f"{p.get('name')} · #{'·'.join(hit)}", "v": W_TAG})
        for iid in (p.get("imprints") or []):
            if iid in imps:
                score += W_IMPRINT
                parts.append({"ko": f"{p.get('name')} · 刻 {iid}", "v": W_IMPRINT})
    for t in ctx.get("installed", []):
        v = tool_power(t, creature["id"])
        if v:
            score += v
            parts.append({"ko": TOOLS[t]["name"], "v": v})
    used: list[str] = []
    for t in ctx.get("consumables", []):
        v = tool_power(t, creature["id"])
        used.append(t)
        if v:
            score += v
            parts.append({"ko": TOOLS[t]["name"] + " (씀)", "v": v})

    gate = gate_state(creature, ctx)
    if gate["ok"]:
        score += W_GATE
        parts.append({"ko": "대응이 맞았다", "v": W_GATE})

    need = float(creature.get("need", 3.0)) + int(ctx.get("severity", 0))
    margin = round(score - need, 2)
    if gate["ok"]:
        result = HELD if margin >= 0 else (SCARRED if margin >= -SCAR_BAND else BREACHED)
    else:
        result = SCARRED if margin >= -SCAR_BAND else BREACHED
    return {"result": result, "result_ko": RESULT_KO[result], "score": round(score, 2),
            "need": round(need, 2), "margin": margin, "gate": gate, "parts": parts, "used": used}


# ─────────────────────────────────────────────────────────────
# 5. 결과의 말 — 숫자가 아니라 장면으로 (D2)
# ─────────────────────────────────────────────────────────────
def outcome_line(creature: dict, result: str, room_name: str) -> str:
    cid = creature["id"]
    # 시나리오가 data/creatures_deep.json 으로 문장을 내놓으면 그것이 이긴다(server.py 가 병합해 둔다)
    override = (creature.get("lines") or {}).get(result)
    if isinstance(override, str) and override:
        return override.replace("{room}", room_name)
    if result == PASSED:
        return "문어가 들어왔다. 무언가를 물고 왔고, 창 쪽을 한 번 더 본다."
    if result == HELD:
        return {
            "swarm": f"{room_name}의 이음매마다 손이 닿았다. 떼는 먹을 것을 못 찾고 흩어진다.",
            "longneck": f"{room_name}{josa(room_name)} 어두워지자 목이 천천히 물러난다. 유리에 콧김 자국만 남았다.",
            "warden": "돔이 숨을 멈춘 동안 아무도 움직이지 않았다. 압력이 지나가고, 물이 다시 소리를 낸다.",
            "claws": "마지막 한 사람이 에어락을 넘어오고 문이 닫힌다. 바깥 바닥에서 모래가 가라앉는다.",
        }.get(cid, f"{room_name}은 무사하다.")
    if result == SCARRED:
        return {
            "swarm": f"{room_name}의 이음매 한 곳이 벌어졌다. 물이 한 줄기 들어왔다가 멎는다.",
            "longneck": f"불을 끄지 않았다. 얼굴이 유리에 눌리고, {room_name}의 창에 금이 간다.",
            "warden": f"압력이 지나가며 {room_name}의 창이 휘었다. 금 하나가 길게 남았다.",
            "claws": f"잠수복 이음매가 뜯겼다. {room_name}으로 사람을 끌고 들어오는 동안 손톱이 따라 들어왔다.",
        }.get(cid, f"{room_name}의 유리에 금이 갔다.")
    return {
        "swarm": f"{room_name}의 이음매가 한꺼번에 터졌다. 격벽이 닫힌다.",
        "longneck": f"유리가 무게를 못 견뎠다. {room_name}의 격벽이 닫히고, 그 안은 물이다.",
        "warden": f"{room_name}이 접혔다. 격벽이 닫힌 뒤에도 한참 소리가 났다.",
        "claws": f"{room_name}까지 따라 들어왔다. 문을 닫는 데 그 방을 내줬다.",
    }.get(cid, f"{room_name}을 잃었다.")


def reward_for(result: str, severity_: int) -> dict:
    """막아 낸 뒤 보상은 자원·유물·이야기를 섞되 이야기가 가장 크다(§9). 자원은 일부러 적다."""
    if result == HELD:
        return {"scrap": 1 + severity_, "parts": 1, "morale": 1}
    if result == PASSED:
        return {"scrap": 1, "morale": 1}
    if result == SCARRED:
        return {"morale": -1}
    return {"morale": -3}
