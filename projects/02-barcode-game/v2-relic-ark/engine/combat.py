"""배치 방어 전투 — 1막의 핵심 플레이 (COMBAT_AND_DEFENSE.md 구현).

> **돔 바깥에서 물고기들이 들이친다. 플레이어는 안의 사람들을 옮기고 배치해서 막는다.**

이 모듈은 **순수 함수**만 가진다. DB·HTTP·시간을 모른다(시각은 호출자가 넘긴다).
server.py 가 상태를 읽어 넘기고, 돌아온 결과를 상태에 쓴다. 그래야 같은 입력이면
같은 결과가 나오고(02_DEV **D6**), 테스트가 서버 없이 돈다.

수치의 정본은 **`data/balance/defense.json` · `data/balance/threats.json`** 이고(기획·밸런스 소유),
이 모듈은 그 파일을 읽어 쓴다. 코드에 박힌 상수는 파일이 없을 때의 폴백일 뿐이다(02_DEV **D7**).

설계 근거
  docs/BALANCE.md §2  **관문은 점수가 아니라 분기다** (2026-10-01 교정)
  COMBAT_AND_DEFENSE.md §3 흐름(소리→실루엣→접촉→대응→결과→흔적)
                       §4 생물별 대응(같은 습격도 배치에 따라 결과가 다르다)
                       §6 아늑함 안전장치 / §6.5 대응 도구 일곱 / §9 준비 단계 권장안
  WORLD_BIBLE_DEEP.md  §3 큰 것들(긴목·문지기·손톱 무리·동거 문어)
  data/creatures.json  생물 14종 · 막는 법 11종(시나리오 소유. 문장이 이긴다)
  DECISIONS 2026-10-01 "죽이는 것이 주된 동사가 아니다" — 여기에 공격·피해량·HP 는 없다.
                       "관문은 전제 조건이지 점수가 아니다" — W_GATE +3.0 제거(S10-C).
"""
from __future__ import annotations

import json
import random
from pathlib import Path

_BAL_DIR = Path(__file__).resolve().parent.parent / "data" / "balance"


def _balance(name: str) -> dict:
    """밸런스 정본 한 장. 없거나 깨져 있으면 빈 dict — 코드의 폴백 상수로 돈다."""
    p = _BAL_DIR / f"{name}.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:        # 게임이 죽지는 않는다. 이유는 표준출력에
        print(f"[balance] {name}.json 을 읽지 못했다 → 코드 폴백값으로 돈다: {e}")
        return {}


BAL = _balance("defense")
THR = _balance("threats")


def _num(obj, path: str, default: float) -> float:
    cur = obj
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return float(default)
        cur = cur[key]
    return float(cur) if isinstance(cur, (int, float)) else float(default)


# ─────────────────────────────────────────────────────────────
# 1. 바깥에서 오는 것들 (data/creatures.json 14종을 코드로)
#    gate = **그 종을 막는 단 하나의 조건**. 점수로 뭉개지 않는다 —
#    "같은 방식의 반복이 이 장르를 지루하게 만드는 주범"(§4)이라 종마다 동사가 다르다.
#    여기 문장은 **초안**이고, server.py 가 data/creatures.json 으로 덮어쓴다(파일이 이긴다).
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
        "hold_flags": [], "breach_flags": ["room_sealed"],
        "audio": {"sound": "sfx_water_splash.ogg", "contact": "sfx_glass_crack.ogg"},
    },
    "longneck": {
        "id": "longneck", "name": "긴목", "zone": "박광층", "threat": True,
        "gate": "lights_off",                   # 그 방의 불을 끈다
        "how": "불을 끈다. 끄면 우리도 그 방을 못 본다.",
        "sound": "두드리는 소리. 똑, 똑. 사람이 내는 소리를 흉내 낸 것이다.",
        "silhouette": "목이 먼저 온다. 몸은 아직 어둠 속인데 창 앞에는 목만 와 있다.",
        "contact": "얼굴을 유리에 붙이고 들여다본다. 해치려는 것이 아니라 궁금한 것이다.",
        "hold_flags": ["beast_left"], "breach_flags": ["room_sealed"],
        "audio": {"sound": "sfx_knock_glass.ogg", "contact": "sfx_glass_crack.ogg"},
        "avoid_tool": "lure_lamp",              # 유인 등불이 있는 방은 지나친다
    },
    "warden": {
        "id": "warden", "name": "문지기", "zone": "무광층 경계", "threat": True,
        "gate": "quiet",                        # 전원을 내리고 한 방에 모인다
        "how": "소리를 죽인다. 전원을 내리고 모두 한 방에 모인다.",
        "sound": "다른 소리가 전부 사라진다. 물이 조용해지면 온 것이다.",
        "silhouette": "그림자가 아니라 압력이 먼저 온다. 유리가 한 번 휜다.",
        "contact": "바다가 숨을 들이켰다. 돔 전체가 한 뼘 눌린다.",
        "hold_flags": ["beast_left"], "breach_flags": ["room_sealed"],
        "audio": {"sound": "amb_far_call.ogg", "contact": "sfx_glass_crack.ogg"},
    },
    "claws": {
        "id": "claws", "name": "손톱 무리", "zone": "해구", "threat": True,
        "gate": "all_inside",                   # 밖에 있는 사람을 즉시 들인다
        "how": "밖에 나간 사람을 즉시 들인다. 잠수복 이음매를 정확히 찾는다.",
        "sound": "아무 소리도 없다. 그들은 소리를 못 듣고 냄새로 온다.",
        "silhouette": "바닥 쪽에서 모래가 들린다. 느리고 작고 수백이다.",
        "contact": "이음매를 찾는 손톱. 밖에 사람이 있으면 사람부터 찾는다.",
        "hold_flags": [], "breach_flags": ["room_sealed"],
        "audio": {"sound": "amb_outside_deep.ogg", "contact": "sfx_air_low.ogg"},
    },
    # ── 신규 일곱 (S10-C). 막는 법 일곱이 서로 겹치지 않는다 ─────────────
    "mirror_eye": {
        # **먼저 배운 정답이 오답이 되는 설계 ①.** 긴목에게 통한 '불을 끈다'가 여기서는 최악수다.
        "id": "mirror_eye", "name": "거울눈", "zone": "박광층", "threat": True,
        "gate": "light_elsewhere",
        "how": "반대쪽에 더 밝은 불을 켠다. **끄면 안 된다** — 비침이 사라지면 유리를 민다.",
        "sound": "유리에 무엇이 비친다. 그쪽에서도 같은 것이 비쳤을 것이다.",
        "silhouette": "제 모습을 따라 움직인다. 가까워질수록 느려진다.",
        "contact": "창에 눈이 닿는다. 저쪽 눈도 같은 자리에 닿아 있다.",
        "hold_flags": ["beast_left"], "breach_flags": ["room_sealed"],
        "audio": {"sound": "sfx_knock_glass.ogg", "contact": "sfx_glass_crack.ogg"},
    },
    "straight_one": {
        "id": "straight_one", "name": "곧은치", "zone": "박광층", "threat": True,
        "gate": "cloud_water",
        "how": "물을 흐린다. 곧게만 오는 것은 흐린 물에서 겨누지 못한다.",
        "sound": "먼 데서 한 번. 짧고 곧다.",
        "silhouette": "직선 하나가 창 쪽으로 자란다.",
        "contact": "같은 자리를 다시 겨눈다.",
        "hold_flags": [], "breach_flags": ["room_sealed"],
        "audio": {"sound": "amb_outside_deep.ogg", "contact": "sfx_glass_crack.ogg"},
    },
    "lid": {
        # **먼저 배운 정답이 오답이 되는 설계 ②.** 이 게임의 주된 동사(사람을 옮긴다)가 최악수다.
        "id": "lid", "name": "덮개", "zone": "무광층", "threat": True,
        "gate": "stand_still",
        "how": "아무도 움직이지 않는다. **사람을 옮기면 최악수다** — 움직이는 것 위에는 앉지 않는다.",
        "sound": "소리가 아니라 무게가 먼저 온다. 천장 쪽이 어두워진다.",
        "silhouette": "넓고 평평한 것이 방 위를 덮는다.",
        "contact": "내려앉는다. 유리가 한 번 삐걱인다.",
        "hold_flags": ["beast_left"], "breach_flags": ["room_sealed"],
        "audio": {"sound": "amb_far_call.ogg", "contact": "sfx_air_low.ogg"},
    },
    "needle": {
        "id": "needle", "name": "바늘", "zone": "무광층", "threat": True,
        "gate": "make_way",
        "how": "길을 비킨다. 그 면의 설치 도구를 걷어 내면 그냥 지나간다.",
        "sound": "가느다란 것이 길게 스친다.",
        "silhouette": "길이를 가늠할 수 없는 선 하나가 옆면을 따라 흐른다.",
        "contact": "걸릴 것을 찾는다. 걸린 것은 끌려간다.",
        "hold_flags": [], "breach_flags": ["room_sealed"],
        "audio": {"sound": "amb_outside_deep.ogg", "contact": "sfx_glass_crack.ogg"},
    },
    "big_maw": {
        "id": "big_maw", "name": "큰 입", "zone": "해구", "threat": True,
        "gate": "feed",
        "how": "먹이를 내준다. 받은 것을 먹는 동안 천천히 내려간다.",
        "sound": "물이 한꺼번에 밀린다. 아래쪽에서 올라오는 소리다.",
        "silhouette": "창 하나를 전부 가린다. 그것이 아직 입이 아니다.",
        "contact": "벌어진다. 온실 창이 통째로 그 안에 들어간다.",
        "hold_flags": ["beast_left"], "breach_flags": ["room_sealed"],
        "audio": {"sound": "amb_far_call.ogg", "contact": "sfx_air_low.ogg"},
    },
    "follower": {
        "id": "follower", "name": "따라온 것", "zone": "해구", "threat": True,
        "gate": "return_it",
        "how": "가져온 것을 돌려보낸다. 유물 하나를 영영 잃는다.",
        "sound": "창고 쪽에서 무언가 자리를 바꾼다.",
        "silhouette": "형태가 자꾸 바뀐다. 보는 사람마다 다르게 말한다.",
        "contact": "제 것을 찾으러 왔다. 어디 있는지 이미 안다.",
        "hold_flags": ["beast_left"], "breach_flags": ["room_sealed"],
        "audio": {"sound": "amb_far_call.ogg", "contact": "sfx_glass_crack.ogg"},
    },
    "upper_child": {
        "id": "upper_child", "name": "윗물 아이", "zone": "광층", "threat": True,
        "gate": "guide_up",
        "how": "위로 빛의 길을 내서 올려 보낸다. 금기를 어기는 일이다.",
        "sound": "작은 것이 유리를 더듬는다. 내려가는 법을 모르는 소리다.",
        "silhouette": "위쪽 창에 붙어 떨어지지 않는다.",
        "contact": "붙은 채로 미끄러진다. 아래로는 가고 싶어 하지 않는다.",
        "hold_flags": ["beast_left"], "breach_flags": ["room_sealed"],
        "audio": {"sound": "sfx_water_splash.ogg", "contact": "sfx_air_low.ogg"},
    },
    # ── 위협이 아닌 셋 ────────────────────────────────────────
    "octopus": {
        # 위협이 아니라 **식구**다. 공격하지 않는다. 오히려 다음에 오는 것을 미리 알린다.
        # 문어는 어떤 매체에서도 발화하지 않는다(DECISIONS 2026-09-27) — 아래 문장에
        # 따옴표·의성어·생각자막이 없는 이유다. 행동과 자리로만 말한다.
        "id": "octopus", "name": "동거 문어", "zone": "돔 안팎", "threat": False,
        "gate": "none",
        "how": "막을 것이 없다. 식구다.",
        "sound": "에어락 쪽에서 작게 빨판 소리가 난다.",
        "silhouette": "창 밖을 한 바퀴 돌고, 한 방 앞에 멈춰 붙는다.",
        "contact": "붙어 있던 자리에서 떨어져 안으로 들어온다. 무언가를 물고 왔다.",
        "hold_flags": [], "breach_flags": [],
        "foretells": True,                      # 다음에 오는 것을 미리 알린다. 문어만
        "audio": {"sound": "sfx_water_splash.ogg", "contact": "sfx_collect.ogg"},
    },
    "shade": {
        "id": "shade", "name": "그늘", "zone": "광층", "threat": False,
        "gate": "none",
        "how": "판정이 없다. 지나가는 동안 작은 것들이 전부 숨는다 — 가장 조용한 시간이다.",
        "sound": "위쪽이 한 번에 어두워진다.",
        "silhouette": "광층 전체가 천천히 지나간다. 끝이 보이지 않는다.",
        "contact": "지나간다. 그뿐이다.",
        "hold_flags": [], "breach_flags": [],
        "audio": {"sound": "amb_far_call.ogg", "contact": "amb_far_call.ogg"},
    },
    "far_cry": {
        "id": "far_cry", "name": "먼 울음", "zone": "해구", "threat": False,
        "gate": "none",
        "how": "판정이 없다. 세는 것이 돔의 일과다.",
        "sound": "아주 멀리서. 간격을 세면 지난번보다 짧다.",
        "silhouette": "아무것도 보이지 않는다.",
        "contact": "오지 않는다. 다만 일지에 한 줄이 는다.",
        "hold_flags": [], "breach_flags": [],
        "audio": {"sound": "amb_far_call.ogg", "contact": "amb_far_call.ogg"},
    },
}
# 그 생물을 넘겨 본 사람의 각인(시나리오 2026-10-03 등재). 넘긴 생물에 강해지는 것이 계단식 성장의 핵심이다
CREATURES["needle"]["imprints"] = ["made_way"]
CREATURES["big_maw"]["imprints"] = ["fed_it"]
CREATURES["upper_child"]["imprints"] = ["sent_up"]
for _cid, _c in CREATURES.items():                      # 공통 기본값
    _c.setdefault("gate_need", 0)
    _c["imprints"] = sorted(set(_c.get("imprints") or []) | set((BAL.get("imprint_match") or {}).get(_cid) or []))
    _c.setdefault("need", 3.0)                          # 폴백. 실제 need 는 등급에서 나온다

STAGES = ("sound", "silhouette", "contact", "done")
STAGE_KO = {"sound": "소리", "silhouette": "실루엣", "contact": "접촉", "done": "지나갔다"}

# ─────────────────────────────────────────────────────────────
# 2. 대응 도구 일곱 (COMBAT_AND_DEFENSE §6.5 — 확정표 그대로)
#    무기가 아니다. 막고 가리고 꿰매고 부르는 물건이다.
#    kind: consumable 소모 / install 설치 / durable 내구 / permanent 영구
#    세기(power)의 정본은 defense.json tool_power — 아래 값은 폴백이다.
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
        "does": "돔에서 떨어진 곳에 불을 켜 둔다", "against": ["longneck", "mirror_eye"],
        "cost": {"parts": 2, "power": 2},
        "power": {"longneck": 1.0, "mirror_eye": 1.0},
        "diverts": "longneck",                  # 이 방은 긴목의 목표가 되지 않는다
        "lures_elsewhere": True,                # **다른 방**에 붙어 있으면 거울눈의 관문을 연다
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
        "power": {"_any": 1.5}, "hands": 1,     # 2.0 → 1.5 (BALANCE §2-2 도구가 사람을 이기면 배치가 죽는다)
        "uses": 3,                              # 세 번 쓰면 해진다
    },
    "brace": {
        "id": "brace", "name": "이음매 보강대", "kind": "permanent",
        "does": "그 방의 기본 방어를 올린다", "against": ["swarm", "longneck", "warden", "claws"],
        "cost": {"parts": 3, "knowledge": 2},
        "power": {"_any": 1.5}, "hands": 1,     # 2.0 → 1.5
    },
}
# 도구 세기의 정본은 defense.json. 파일이 있으면 코드값을 덮는다(밸런스가 코드를 안 고치고 바꾼다).
for _tid, _row in (BAL.get("tool_power") or {}).items():
    if _tid.startswith("_") or _tid not in TOOLS or not isinstance(_row, dict):
        continue
    # `_any` 는 '그 밖의 생물 전부'라는 뜻의 정식 키다 — 주석(_basis·_comment)과 구분해 남긴다.
    TOOLS[_tid]["power"] = {k: float(v) for k, v in _row.items()
                            if k != "uses" and isinstance(v, (int, float))}
    if isinstance(_row.get("uses"), int):
        TOOLS[_tid]["uses"] = _row["uses"]

INSTALLED_KINDS = ("install", "durable", "permanent")      # 방에 붙는 것
MAX_TOOL_HANDS = sum(1 for t in TOOLS.values() if t.get("hands"))   # 한 방에서 도구가 대신 들 수 있는 손의 최대
CARRY_KINDS = ("consumable",)                              # 접촉 순간에 쓰는 것

# 방 정원 — 방 크기별 2~4명 (COMBAT_AND_DEFENSE §9 "방 정원은 몇 명인가"에 대한 답).
# 좁은 방(정수·서고)은 2, 보통 3, 넓은 방(창고·공방)은 4.
ROOM_CAP = {"pantry": 4, "well": 2, "infirmary": 3, "library": 2, "workshop": 4}
ROOM_CAP_DEFAULT = 3
HALL_KO = "홀"           # 배치되지 않은 사람이 모이는 곳 = 돔 상부의 공용 공간

# 결과 등급. 실패가 즉사가 아니다(§6-3) — 최악이 방 하나이고 그조차 화면에 남아 이야기가 된다.
HELD, SCARRED, BREACHED, PASSED = "held", "scarred", "breached", "passed"
RESULT_KO = {HELD: "막았습니다", SCARRED: "유리에 금이 갔습니다", BREACHED: "방을 잃었습니다", PASSED: "지나갔습니다"}


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
# 3. 관문 행동 — 토글이 아니라 **그 자리에서 치르는 대가**
#    defense.json gates.gate_cost 가 정본이다(대가의 글은 거기, 숫자는 여기).
#    "대가가 없는 관문은 그냥 누르는 버튼이 되어 선택이 사라진다"(B3).
# ─────────────────────────────────────────────────────────────
GATE_ACTIONS = {
    "light_elsewhere": {
        "id": "light_elsewhere", "ko": "반대쪽에 불을 켠다", "gate": "light_elsewhere",
        "cost": {"power": 2},
        "needs_light_on": True,
        "why": "더 밝은 비침이 그쪽에 생긴다. 이 방의 불은 **켜 둔 채**여야 한다.",
        "cost_ko": "전력 2. 그 밤 바깥에 우리 자리를 하나 더 켜 둔다",
    },
    "cloud_water": {
        "id": "cloud_water", "ko": "물을 흐린다", "gate": "cloud_water",
        "cost": {"water": 2},
        "needs_room": "well",
        "why": "정수실의 침전물을 그 창 앞으로 흘려보낸다. 곧게만 오는 것은 겨누지 못한다.",
        "cost_ko": "물 2. 흐려진 창으로는 우리도 바깥을 못 본다",
    },
    "make_way": {
        "id": "make_way", "ko": "길을 비킨다", "gate": "make_way",
        "cost": {},
        "strips_tools": True,
        "why": "그 면의 설치 도구를 전부 걷는다. 걸릴 것이 없으면 그냥 지나간다.",
        "cost_ko": "그 방의 설치 도구를 **영영 잃는다**",
    },
    "feed": {
        "id": "feed", "ko": "먹이를 내준다", "gate": "feed",
        "cost": {"food": 2}, "cost_per_severity": {"food": 1},
        "why": "수확분을 에어락으로 내보낸다. 받은 것을 먹는 동안 천천히 내려간다.",
        "cost_ko": "식량 2 + 세기만큼 더",
    },
    "return_it": {
        "id": "return_it", "ko": "돌려보낸다", "gate": "return_it",
        "cost": {}, "spends_relic": True,
        "why": "가장 깊은 데서 온 유물 하나를 에어락으로 내려보낸다.",
        "cost_ko": "창고의 유물 **한 장을 영영 잃는다**",
    },
    "guide_up": {
        "id": "guide_up", "ko": "위로 올려 보낸다", "gate": "guide_up",
        "cost": {"power": 2},
        "needs_hall": True, "needs_power_on": True,
        "next_severity": 1,
        "why": "돔 윗층 등을 아래에서 위로 차례로 켠다. 순서를 맞출 사람이 홀에 있어야 한다.",
        "cost_ko": "전력 2. 그리고 **다음에 오는 것이 한 단계 세진다** — 금기를 어긴 값",
    },
}
# 행동이 필요 없는 관문. 이미 있는 토글·배치·가만히 있기로 충족된다
PASSIVE_GATES = ("people", "lights_off", "quiet", "all_inside", "stand_still", "none")
GATE_KO = {
    "people": "사람 수", "lights_off": "불을 끈다", "quiet": "소리를 죽인다",
    "all_inside": "밖의 사람을 들인다", "light_elsewhere": "반대쪽에 불을 켠다",
    "cloud_water": "물을 흐린다", "stand_still": "아무도 움직이지 않는다",
    "make_way": "길을 비킨다", "feed": "먹이를 내준다", "return_it": "돌려보낸다",
    "guide_up": "위로 올려 보낸다", "none": "막을 것이 없다",
}


def action_for_gate(gate: str) -> dict | None:
    return next((a for a in GATE_ACTIONS.values() if a["gate"] == gate), None)


def action_cost(action_id: str, severity_: int = 0) -> dict:
    a = GATE_ACTIONS.get(action_id) or {}
    cost = dict(a.get("cost") or {})
    for k, v in (a.get("cost_per_severity") or {}).items():
        cost[k] = cost.get(k, 0) + v * max(0, int(severity_))
    return cost


# ─────────────────────────────────────────────────────────────
# 4. 습격 뽑기 — 하루 1회 이하, 조용한 날이 과반 (§6-1 · threats.json frequency)
#    **등급은 깊이로만 정해진다**(threats.json grade_source). 날짜가 아니다.
# ─────────────────────────────────────────────────────────────
RAID_CHANCE_FALLBACK = 0.45
RAID_FIRST_DAY = 2           # 첫날은 아무것도 오지 않는다. 처음 하루는 들여다보기만 한다
NEW_CREATURE_WEIGHT = 2      # 신규 일곱의 기본 가중치. 기존 중위권(문지기 2·손톱 2)과 같은 자리
QUIET_SPLIT = {"octopus": 0.7, "shade": 0.2, "far_cry": 0.1}   # 조용한 날 안에서의 비율


def grade_conf(grade: int) -> dict:
    return ((THR.get("frequency") or {}).get("by_grade") or {}).get(str(int(grade))) or {}


def raid_chance(grade: int) -> float:
    return _num(grade_conf(grade), "raid_chance", RAID_CHANCE_FALLBACK)


def min_grade(cid: str, residents: int | None = None) -> int:
    """그 생물이 처음 나올 수 있는 등급. S15: threats.json `min_grade_override` 가 있으면
    주민 수(residents)가 문턱을 넘을 때 다른 등급을 쓴다(예: 덮개 — 손님으로 주민이 늘면 보류를 푼다).
    residents 를 주지 않으면 예전과 같다."""
    v = (THR.get("min_grade") or {}).get(cid)
    base = int(v) if isinstance(v, (int, float)) else 1
    ov = (THR.get("min_grade_override") or {}).get(cid)
    if residents is not None and isinstance(ov, dict) and isinstance(ov.get("min_grade"), (int, float))             and int(residents) >= int(ov.get("residents_at_least") or 0):
        return int(ov["min_grade"])
    return base


def creature_weights(grade: int, residents: int | None = None) -> dict:
    """그 등급에서 각 생물이 뽑힐 가중치.

    기존 넷·문어의 값은 threats.json 의 표 그대로 쓰고, **신규 일곱은 min_grade 가 열린 등급부터
    기본 가중치로 들어간다.** 그다음 조용한 쪽(문어·그늘·먼 울음)의 합을 다시 맞춰,
    threats.json 이 보증한 `quiet_day_rate` 가 생물이 늘어도 **변하지 않게** 한다 —
    "모든 등급에서 조용한 날이 과반"은 넘지 말라고 적힌 선이다(§3 guardrail).
    """
    conf = grade_conf(grade)
    base = {k: v for k, v in (conf.get("weights") or {}).items() if isinstance(v, (int, float))}
    threat: dict[str, float] = {}
    for cid, c in CREATURES.items():
        if not c["threat"] or min_grade(cid, residents) > grade:
            continue
        w = base.get(cid)
        threat[cid] = float(w) if isinstance(w, (int, float)) else float(NEW_CREATURE_WEIGHT)
    threat = {k: v for k, v in threat.items() if v > 0}
    if not threat:
        threat = {"swarm": 1.0}
    t_sum = sum(threat.values())

    quiet_rate = _num(conf, "quiet_day_rate", 0.0)
    chance = raid_chance(grade)
    # 위협이 차지해야 할 비율. threats.json 이 값을 안 주면 문어 가중치를 그대로 쓴다
    share = ((1.0 - quiet_rate) / chance) if (quiet_rate and chance) else 0.0
    if not (0.05 < share < 0.95):
        q_total = float(base.get("octopus") or 3)
    else:
        q_total = t_sum * (1.0 - share) / share
    avail = {k: v for k, v in QUIET_SPLIT.items() if min_grade(k, residents) <= grade}
    a_sum = sum(avail.values()) or 1.0
    out = dict(threat)
    for cid, frac in avail.items():
        out[cid] = round(q_total * frac / a_sum, 4)
    return out


def quiet_day_rate(grade: int) -> float:
    """실제로 계산되는 조용한 날 비율. 0.5 를 넘는지 검증에 쓴다(§3 guardrail)."""
    w = creature_weights(grade)
    tot = sum(w.values()) or 1.0
    threat = sum(v for k, v in w.items() if CREATURES[k]["threat"])
    return round(1.0 - raid_chance(grade) * threat / tot, 3)


def raid_rng(uid: str, day: int, purpose: str = "") -> random.Random:
    """습격에 쓰는 난수는 전부 `uid|day|목적` 시드다(D6). 같은 방주의 같은 날은 늘 같은 습격."""
    return random.Random(f"{uid}|{day}|raid{('|' + purpose) if purpose else ''}")


def pick_creature(uid: str, day: int, grade: int = 1, force: str | None = None,
                  residents: int | None = None, mult: dict | None = None) -> dict | None:
    """mult(S19): 생물별 가중 배율(꾸밈의 대가 — 트인 쪽 반짝이는 것에 긴목 ×1.3). None 이면 예전과 바이트까지 같다."""
    if force:
        return CREATURES.get(force)
    if day < RAID_FIRST_DAY:
        return None
    if raid_rng(uid, day, "roll").random() >= raid_chance(grade):
        return None
    w = creature_weights(grade, residents)
    if mult:
        w = {k: (v * float(mult.get(k, 1.0))) for k, v in w.items()}
    ids = sorted(w)
    pick = raid_rng(uid, day, f"who|g{grade}").choices(ids, weights=[w[i] for i in ids], k=1)[0]
    return CREATURES[pick]


def pick_target(uid: str, day: int, creature: dict, rooms: list[dict], room_tools: dict,
                weights: dict | None = None) -> int | None:
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
    if weights and any(float(weights.get(s_, 1.0)) != 1.0 for s_ in slots):
        # S19: 아끼는 것(꾸밈·사슬 물건)이 있는 방 가중. 가중이 없으면 아래 옛 추첨 그대로(바이트 동일)
        return raid_rng(uid, day, "where").choices(slots, weights=[float(weights.get(s_, 1.0)) for s_ in slots], k=1)[0]
    return raid_rng(uid, day, "where").choice(slots)


def severity(uid: str, day: int, grade: int = 1) -> int:
    """0·1·2. 세기도 시드에서 나온다 — 같은 날은 늘 같은 세기. 가중치는 등급별(threats.json)."""
    w = (((THR.get("severity") or {}).get("weights_by_grade") or {}).get(str(int(grade))))
    if not (isinstance(w, list) and len(w) == 3 and sum(w) > 0):
        w = [5, 3, 2]
    return raid_rng(uid, day, "sev").choices([0, 1, 2], weights=list(w), k=1)[0]


def need_for(creature: dict, grade: int, severity_: int) -> float:
    """need = 등급 기본값 + 생물 보정 + severity (BALANCE §2-1)."""
    base = _num(THR.get("need_by_grade") or {}, str(int(grade)), float(creature.get("need", 3.0)))
    off = _num(THR.get("creature_offset") or {}, creature["id"], 0.0)
    step = _num(THR.get("severity") or {}, "add_per_step", 1.0)
    return round(base + off + step * max(0, int(severity_)), 2)


# ─────────────────────────────────────────────────────────────
# 5. 방어 판정 — **공식 하나**. 난수가 한 톨도 들어가지 않는다 (D6)
#
#   관문(gate) = 올바른 행동.   점수(score) = 배치의 두께.
#   단위가 다르므로 **더하지 않는다.** 관문은 어느 판정표를 쓸지 고를 뿐이다.
#   (2026-10-01 교정: 전에는 관문 통과에 +3.0 을 주어, 관문만 넘기면 사람·각인·도구·방 레벨이
#    결과를 전혀 바꾸지 못했다. 담력 3 한 명이든 담력 9 네 명이든 전부 '막았다'였다.)
#
#   score = 방 바탕[레벨] + Σ사람(0.5+0.1×담, 부상 ×0.5) + Σ역할 친화(강 1.5/약 0.75)
#         + Σ각인 일치(1.5) + min(Σ도구, 3.0)
#   need  = 등급 기본값 + 생물 보정 + severity
#
#   관문 통과:  margin ≥ 0     막았다 / ≥ −4.5  유리에 금 / 그 밖  방을 잃는다
#   관문 실패:  막는 것은 불가능. margin ≥ −1.0  유리에 금 / 그 밖  방을 잃는다
#   상실 보호:  등급 1 전면 / 등급 2 는 방에 사람이 있을 때
# ─────────────────────────────────────────────────────────────
W_ROOM = _num(BAL, "score.room_base.1", 1.0)        # 레벨 1 방 바탕(폴백)
ROOM_BASE = {int(k): float(v) for k, v in ((BAL.get("score") or {}).get("room_base") or {}).items()
             if not str(k).startswith("_") and isinstance(v, (int, float))} or {1: 1.0, 2: 1.5, 3: 2.0}
W_NERVE_BASE = _num(BAL, "score.person.base", 0.5)
W_NERVE_STEP = _num(BAL, "score.person.per_nerve", 0.1)
HURT_MUL = _num(BAL, "score.person.injured_mul", 0.5)
W_AFF_STRONG = _num(BAL, "score.affinity_strong", 1.5)
W_AFF_WEAK = _num(BAL, "score.affinity_weak", 0.75)
W_IMPRINT = _num(BAL, "score.imprint_match", 1.5)
TOOL_CAP = _num(BAL, "score.tool_total_cap", 3.0)
SCAR_BAND = _num(BAL, "verdict.scar_band", 4.5)     # 2.0 → 4.5 (시뮬로 두 번 조정한 값)
GATE_FAIL_BAND = 1.0                                # 관문 실패 시 금으로 멈추는 폭(verdict.gate_fail)

ROLE_AFFINITY = {k: v for k, v in (BAL.get("role_affinity") or {}).items()
                 if not k.startswith("_") and isinstance(v, dict)}
IMPRINT_MATCH = {k: list(v) for k, v in (BAL.get("imprint_match") or {}).items()
                 if not k.startswith("_") and isinstance(v, list)}


def _verdict_table(key: str) -> list[tuple[float, str]]:
    rows = ((BAL.get("verdict") or {}).get(key) or [])
    out = [(float(r["min_margin"]), str(r["result"])) for r in rows
           if isinstance(r, dict) and isinstance(r.get("min_margin"), (int, float)) and r.get("result")]
    if out:
        return sorted(out, key=lambda x: -x[0])
    if key == "gate_pass":
        return [(0.0, HELD), (-SCAR_BAND, SCARRED), (-99.0, BREACHED)]
    return [(-GATE_FAIL_BAND, SCARRED), (-99.0, BREACHED)]


VERDICT_PASS = _verdict_table("gate_pass")
VERDICT_FAIL = _verdict_table("gate_fail")
LOSS_SHIELD = bool(((BAL.get("verdict") or {}).get("loss_shield") or {}).get("enabled", True))


def person_weight(p: dict) -> float:
    nv = p.get("nerve")
    nv = 5 if not isinstance(nv, (int, float)) else max(1, min(10, int(nv)))
    w = W_NERVE_BASE + W_NERVE_STEP * nv
    return round(w * (HURT_MUL if p.get("injured") else 1.0), 2)


def affinity(creature_id: str, role: str) -> tuple[float, str]:
    """생물 × 역할 친화. **roles.json 의 counter_tags 를 쓰지 않는다** — 그러면 여덟 역할 중 둘만
    전투에서 점수를 받아 최적 배치가 하나로 수렴한다(defense.json role_affinity._why)."""
    row = ROLE_AFFINITY.get(creature_id) or {}
    for key, w in (("strong", W_AFF_STRONG), ("weak", W_AFF_WEAK)):
        tbl = row.get(key) or {}
        if role in tbl:
            return w, str(tbl[role])
    return 0.0, ""


def gate_state(creature: dict, ctx: dict) -> dict:
    """관문 한 줄. ctx 는 server.py 가 모아 주는 그 순간의 사실들."""
    g = creature.get("gate", "none")
    sev = int(ctx.get("severity", 0))
    acts = set(ctx.get("acts") or [])

    def done(kind: str, ok: bool, ko: str, have=0, need=0) -> dict:
        return {"kind": kind, "ok": bool(ok), "have": have, "need": need, "ko": ko,
                "action": (action_for_gate(kind) or {}).get("id")}

    if g == "people":
        # 사람 수가 관문이다. 다만 손이 모자랄 때 **도구가 한 사람 몫을 한다**(봉합 패치·긴 장대 그물·
        # 이음매 보강대). 좁은 방(정원 2)이 센 떼를 영영 못 막는 막다른 골목을 피하려는 장치다.
        need = creature.get("gate_need", 2) + sev
        # 필요 인원은 **그 방이 채울 수 있는 최대(정원 + 도구 칸)** 를 넘지 않는다. 정원 2 인 좁은 방이
        # 세기 4 의 떼를 영영 못 막는 막다른 길을 없앤다(defense.json gates.swarm._basis, 리뷰 2026-10-03)
        reach = int(ctx.get("room_cap") or 0) + MAX_TOOL_HANDS
        if reach > 0:
            need = min(need, reach)
        hands = int(ctx.get("hands", 0))
        n = len(ctx.get("people", []))
        have = n + hands
        extra = f", 도구 {hands}개" if hands else ""
        return done(g, have >= need, f"그 방에 {need}분 이상 모여 주세요. 지금은 {n}분{extra}입니다.", have, need)
    if g == "lights_off":
        ok = (not ctx.get("light_on", True)) or ctx.get("forced_dark", False)
        return done(g, ok, "그 방 불을 꺼 주세요." + ("" if ok else " 지금은 켜져 있습니다."), 0 if ok else 1, 0)
    if g == "quiet":
        gathered = ctx.get("gathered_one_room", False)
        quiet = (not ctx.get("power_on", True)) or ctx.get("hushed", False)
        ok = gathered and quiet
        return done(g, ok, "전원을 내리시고, 모두 한 방에 모여 주세요." +
                    ("" if ok else f" {'아직 다 모이지 않으셨습니다.' if not gathered else '아직 소리가 남아 있습니다.'}"),
                    int(gathered) + int(quiet), 2)
    if g == "all_inside":
        out = len(ctx.get("outside", []))
        return done(g, out == 0, "밖에 계신 분을 들여 주세요." + ("" if out == 0 else f" 아직 {out}분이 밖에 계십니다."), out, 0)
    if g == "light_elsewhere":
        # **긴목의 정답이 여기서는 최악수다.** 불을 끄면 통과할 수 없다.
        lit = bool(ctx.get("light_on", True)) and not ctx.get("forced_dark", False)
        lure = bool(ctx.get("lure_elsewhere")) or ("light_elsewhere" in acts)
        ok = lit and lure
        why = ("" if ok else
               (" 지금 이 방 불이 꺼져 있습니다. 끄시면 비침이 사라집니다." if not lit
                else " 아직 다른 쪽에 더 밝은 곳이 없습니다."))
        return done(g, ok, "이 방 불은 켜 두시고, 다른 방에 더 밝은 불을 켜 주세요." + why, int(lit) + int(lure), 2)
    if g == "cloud_water":
        ok = "cloud_water" in acts
        return done(g, ok, "창 앞 물을 흐려 주세요." + ("" if ok else " 아직 창 앞이 맑습니다."))
    if g == "stand_still":
        # **이 게임의 주된 동사가 최악수다.** 습격이 시작된 뒤로 사람을 한 번도 안 옮겼어야 한다.
        moves = int(ctx.get("moves", 0))
        return done(g, moves == 0,
                    "아무도 움직이지 말아 주세요." + ("" if moves == 0 else f" 벌써 {moves}번 옮기셨습니다."), moves, 0)
    if g == "make_way":
        ok = "make_way" in acts
        return done(g, ok, "길을 비켜 주세요." + ("" if ok else " 아직 걸릴 것이 남아 있습니다."))
    if g == "feed":
        ok = "feed" in acts
        return done(g, ok, "먹이를 내어 주세요." + ("" if ok else " 아직 아무것도 내보내지 않았습니다."))
    if g == "return_it":
        ok = "return_it" in acts
        return done(g, ok, "가져온 것을 돌려보내 주세요." + ("" if ok else " 아직 창고에 있습니다."))
    if g == "guide_up":
        ok = "guide_up" in acts
        return done(g, ok, "위쪽으로 빛의 길을 내 주세요." + ("" if ok else " 아직 위쪽이 어둡습니다."))
    return done("none", True, "막을 것이 없습니다.")


def tool_power(tool_id: str, creature_id: str) -> float:
    p = (TOOLS.get(tool_id) or {}).get("power") or {}
    return float(p.get(creature_id, p.get("_any", 0.0)))


def _verdict(gate_ok: bool, margin: float) -> str:
    for edge, res in (VERDICT_PASS if gate_ok else VERDICT_FAIL):
        if margin >= edge:
            return res
    return BREACHED


def evaluate(creature: dict, ctx: dict) -> dict:
    """방어 판정. 같은 ctx 면 늘 같은 dict 를 돌려준다(난수 없음)."""
    if not creature.get("threat"):
        return {"result": PASSED, "result_ko": RESULT_KO[PASSED], "score": 0.0, "need": 0.0,
                "margin": 0.0, "gate": gate_state(creature, ctx), "parts": [], "used": [],
                "shielded": None}

    cid = creature["id"]
    people = ctx.get("people", [])
    # 밸런스 표(defense.json imprint_match)와 생물 자신의 목록을 **합친다** — 한쪽에만 있는 각인이 0점이 되지 않게
    imps = set(IMPRINT_MATCH.get(cid) or []) | set(creature.get("imprints") or [])
    parts: list[dict] = []
    score = 0.0

    if ctx.get("room_id"):
        lvl = int(ctx.get("room_level") or 1)
        base = ROOM_BASE.get(lvl, ROOM_BASE.get(1, 1.0))
        score += base
        parts.append({"ko": f"방이 있다 (Lv{lvl})", "v": base})
        # S13: 금 간 방은 바탕이 낮다(stakes.json crack.room_base_penalty). server 가 그 방이 금 갔을 때만
        # 이 키를 넣는다 — 키가 없으면 이 줄은 아무 일도 하지 않아 예전 판정과 바이트까지 같다.
        adj = float(ctx.get("room_base_adj") or 0.0)
        if adj:
            score += adj
            parts.append({"ko": str(ctx.get("room_base_adj_ko") or "금 간 유리"), "v": adj})
    for p in people:
        w = person_weight(p)
        score += w
        parts.append({"ko": f"{p.get('name')} · 담 {p.get('nerve', 5)}" + (" (부상)" if p.get("injured") else ""),
                      "v": w})
        aw, why = affinity(cid, p.get("role") or "")
        if aw:
            score += aw
            parts.append({"ko": f"{p.get('name')} · {why}", "v": aw})
        for iid in (p.get("imprints") or []):
            if iid in imps:
                score += W_IMPRINT
                parts.append({"ko": f"{p.get('name')} · 刻 {iid}", "v": W_IMPRINT})

    # 도구는 **합계에 상한**이 있다. 없으면 도구만 깔고 사람을 안 옮기는 것이 최적해가 된다(B3)
    tool_sum, tool_parts = 0.0, []
    for t in ctx.get("installed", []):
        v = tool_power(t, cid)
        if v:
            tool_sum += v
            tool_parts.append({"ko": TOOLS[t]["name"], "v": v})
    used: list[str] = []
    for t in ctx.get("consumables", []):
        v = tool_power(t, cid)
        used.append(t)
        if v:
            tool_sum += v
            tool_parts.append({"ko": TOOLS[t]["name"] + " (씀)", "v": v})
    if tool_sum > TOOL_CAP:
        capped = round(TOOL_CAP, 2)
        parts += tool_parts
        parts.append({"ko": f"도구 상한 {TOOL_CAP:g}", "v": round(capped - tool_sum, 2)})
        tool_sum = capped
    else:
        parts += tool_parts
    score += tool_sum

    gate = gate_state(creature, ctx)
    grade = int(ctx.get("grade") or 1)
    if gate["ok"] and gate["kind"] == "quiet":
        # 문지기는 **소리를 듣고 오는** 생물이다. 들키지 않았으면 맞설 일 자체가 없다 — 못 찾고 지나간다.
        # 그래서 점수 판정을 하지 않는다. 노리는 방이 소리 단계에서 숨겨져 있어도 "전부 숨죽인다"가
        # 정답으로 성립한다(PM 결정 2026-10-03). 관문을 놓치면 아래의 점수 판정으로 간다.
        return {"result": PASSED, "result_ko": "들키지 않았습니다", "score": round(score, 2),
                "need": need_for(creature, grade, int(ctx.get("severity", 0))), "margin": 0.0,
                "gate": gate, "parts": parts, "used": used, "grade": grade, "shielded": None,
                "unheard": True}
    need = need_for(creature, grade, int(ctx.get("severity", 0)))
    score = round(score, 2)
    margin = round(score - need, 2)
    result = _verdict(gate["ok"], margin)

    # 상실 보호 2단 — 1구역은 완전 보호, 2구역은 '사람을 넣었는가'만 묻는다(defense.json loss_shield)
    shielded = None
    if LOSS_SHIELD and result == BREACHED:
        if grade <= 1:
            result, shielded = SCARRED, "등급 1 — 이 구역에서 방을 잃는 일은 없다"
        elif grade == 2 and people:
            result, shielded = SCARRED, "등급 2 — 방에 사람이 있었다. 빈 방만 잃는다"
    return {"result": result, "result_ko": RESULT_KO[result], "score": score,
            "need": round(need, 2), "margin": margin, "gate": gate, "parts": parts,
            "used": used, "grade": grade, "shielded": shielded}


# ─────────────────────────────────────────────────────────────
# 6. 결과의 말 — 숫자가 아니라 장면으로 (D2)
# ─────────────────────────────────────────────────────────────
def outcome_line(creature: dict, result: str, room_name: str) -> str:
    cid = creature["id"]
    # 시나리오가 data/creatures.json 으로 문장을 내놓으면 그것이 이긴다(server.py 가 병합해 둔다)
    override = (creature.get("lines") or {}).get(result)
    if isinstance(override, str) and override:
        return override.replace("{room}", room_name)
    if result == PASSED:
        if cid == "octopus":
            return "문어가 들어왔다. 무언가를 물고 왔고, 창 쪽을 한 번 더 본다."
        if cid == "shade":
            return "위쪽이 한참 어두웠다가 다시 밝아졌다. 그동안 아무것도 오지 않았다."
        if cid == "far_cry":
            return "아주 멀리서 한 번. 일지에 간격을 적는다. 지난번보다 짧다."
        return "지나갔다."
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


def reward_for(result: str, severity_: int, grade: int = 1) -> dict:
    """막아 낸 뒤 보상은 자원·유물·이야기를 섞되 이야기가 가장 크다(§9). 자원은 일부러 적다.
    등급별 표의 정본은 threats.json rewards."""
    table = (THR.get("rewards") or {})
    if result == HELD:
        row = (table.get("held") or {}).get(str(int(grade)))
        if isinstance(row, dict):
            out = {k: int(v) for k, v in row.items() if not k.startswith("_") and isinstance(v, int)}
            if out and severity_ > 0:                       # severity 만큼 가장 큰 항목에 더한다
                big = max(out, key=lambda k: out[k])
                out[big] += int(severity_)
            return out or {"parts": 1, "morale": 1}
        return {"scrap": 1 + severity_, "parts": 1, "morale": 1}
    if result == PASSED:
        return {"scrap": 1, "morale": 1}
    if result == SCARRED:
        return {"morale": -1}
    return {"morale": -3}
