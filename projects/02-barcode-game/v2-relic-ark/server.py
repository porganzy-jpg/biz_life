"""
잔해 방주 (RELIC ARK) — Phase 0 서버
FastAPI + SQLite. 단일 테스터 그룹용(uid는 클라이언트가 생성해 보관).

실행:
  python server.py            # http://localhost:8002  (데스크톱 카메라 OK)
  python server.py --https    # https://<LAN IP>:8444 (휴대폰 카메라용, tools/make_cert.py 먼저)
  python server.py --port=9000
"""
from __future__ import annotations

import json
import os
import random
import socket
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "engine"))
from relic_generator import RelicGenerator, Category, rescan_multiplier  # noqa: E402
from storyteller import ArkState, pick_event, resolve, load_events, acts_of, events_for_act  # noqa: E402
import combat  # noqa: E402  — 배치 방어 전투(COMBAT_AND_DEFENSE.md). 순수 함수 모듈

DB = ROOT / "relic_ark.db"
# ★ 개발 전용 훅 스위치. RELIC_DEV=1 일 때만 ?debug_* 질의가 살아난다(02_DEV §4-4 "배포 전 제거 목록").
#   배포 빌드는 환경변수를 주지 않으므로 훅이 존재하지 않는 것과 같다.
DEV_MODE = os.environ.get("RELIC_DEV") == "1"
ROOMS = json.loads((ROOT / "data" / "rooms.json").read_text(encoding="utf-8"))
ROOMS.pop("_comment", None)
# 공방 — 대응 도구 일곱이 나오는 방(COMBAT_AND_DEFENSE §5-1·§6.5). `data/rooms.json` 은 시나리오 소유라
# 고치지 않고 **런타임에 덧붙인다**. 같은 id 가 파일에 생기면 파일이 이긴다(DEEP_IMPRINTS 와 같은 규약).
WORKSHOP_ROOM = {
    "workshop": {
        "name": "공방", "light": "#F2A93B", "tier": 2,
        "cost": {"parts": 4, "scrap": 4},
        "produces": {"parts": 1},
        "counters": ["breach"],
        "desc": "남이 버린 것을 다시 쓸 것으로 바꾸는 방. 막고 가리고 꿰매는 물건이 여기서 나온다.",
    },
}
for _rid, _spec in WORKSHOP_ROOM.items():
    ROOMS.setdefault(_rid, _spec)
EVENTS = {e["id"]: e for e in load_events()}
# 막(acts) — DECISIONS 2026-09-23. 1 심해 / 2 터널 / 3 지상. 방주 상태의 act 가 오늘의 사건 풀을 고른다.
ACTS = (1, 2, 3)
ACT_KO = {1: "심해 유리돔", 2: "침수 터널", 3: "지상 쇼핑몰"}
ACT_POOL_SIZE = {a: len(events_for_act(a, list(EVENTS.values()))) for a in ACTS}
ACT_POOL_TARGET = 24      # 1막 최소 목표(DECISIONS 2026-09-23). 밑돌면 기동 로그에 남긴다
if ACT_POOL_SIZE[1] < ACT_POOL_TARGET:
    print(f"[acts] 1막 풀 {ACT_POOL_SIZE[1]}장 — 목표 {ACT_POOL_TARGET}장에 {ACT_POOL_TARGET - ACT_POOL_SIZE[1]}장 모자란다 "
          f"(2막 {ACT_POOL_SIZE[2]} · 3막 {ACT_POOL_SIZE[3]})")
TEMPLATES = json.loads((ROOT / "data" / "relic_templates.json").read_text(encoding="utf-8"))
ROLES = json.loads((ROOT / "data" / "roles.json").read_text(encoding="utf-8"))
ROLE_IDS = [k for k in ROLES if not k.startswith("_")]
TRAITS = ROLES["_traits"]; NAMES = ROLES["_names"]
GEN = RelicGenerator()

# ── 각인(刻印) · 신뢰 ──────────────────────────────────────────
# docs/GROWTH_AND_MYTH.md §1 (계단식 성장) · docs/TRUST_AND_COMPANIONS.md §3 (신뢰의 역전)
IMPRINT_DATA = json.loads((ROOT / "data" / "imprints.json").read_text(encoding="utf-8"))
IMPRINT_LIST = IMPRINT_DATA["imprints"]

# ── 심해 1막 각인 4종 (런타임 우선 병합) ─────────────────────────
# docs/WORLD_BIBLE_DEEP.md §7 표 + DECISIONS 2026-09-22(「발자국」은 육상 전용, 심해는 「두드림을 들은 자」).
# data/imprints.json 은 시나리오 소유라 고치지 않고 여기서 덧붙인다. 같은 id가 파일에 생기면 **파일이 이긴다**
# (아래 병합 루프가 file-first). 스프린트 2의 roles_evolved/imprint_lines 와 같은 방식.
DEEP_IMPRINTS = [
    {
        "id": "saved_breath",
        "name": "아낀 숨",
        "crisis": "air_out",
        "crisis_ko": "공기 부족 (숨이 바닥난 원정에서 생환)",
        "trigger": {"type": "event_survived", "event_ids": [], "factions": [], "counter_tags": [],
                    "id_prefixes": ["deep_air"], "flags": ["air_survived"]},
        "visual": {"keyword": "short_sentences_quiet", "ko": "짧아진 문장, 줄어든 말수",
                   "line": "{name}의 문장이 짧아졌다. 숨을 아껴 본 사람은 말도 아낀다."},
        "effect": {"air_cap": 0.2},
        "cost": {"ko": "사람들이 그의 말을 놓친다 — 남의 사기를 덜 올린다", "effect": {"morale_heal_others": -1}},
    },
    {
        "id": "crack_seen",
        "name": "금을 본 자",
        "crisis": "hull_breach",
        "crisis_ko": "유리 균열 (방 하나를 닫고 생존)",
        "trigger": {"type": "event_survived", "event_ids": [], "factions": [], "counter_tags": [],
                    "id_prefixes": ["deep_glass"], "flags": ["room_sealed"]},
        "visual": {"keyword": "hand_on_glass", "ko": "늘 창을 만지며 지나간다",
                   "line": "{name}은 이제 창을 만지며 지나간다. 손끝으로 먼저 안다."},
        "effect": {"counter_bonus": {"부품": 0.3, "청사진": 0.2}},
        "cost": {"ko": "닫힌 방 앞을 지나지 못한다 — 동선이 길어져 생산이 조금 준다",
                 "effect": {"production_penalty": 0.05}},
    },
    {
        "id": "depth_mark",
        "name": "깊이의 자국",
        "crisis": "descent",
        "crisis_ko": "해구 하강 (무광층 아래에 처음 닿음)",
        "trigger": {"type": "event_survived", "event_ids": [], "factions": [], "counter_tags": [],
                    "id_prefixes": ["deep_trench", "deep_ballast"], "flags": ["deep_descent"]},
        "visual": {"keyword": "pressed_ears_low_voice", "ko": "귀와 코의 눌린 자국, 낮아진 목소리",
                   "line": "{name}의 귀 뒤에 눌린 자국이 남았다. 목소리가 한 뼘 낮아졌다."},
        "effect": {"depth_cap": 0.2},
        "cost": {"ko": "얕은 곳에서 불안해한다 — 광층 체류 중 사기 −1", "effect": {"morale_daily": -1}},
    },
    {
        # 2026-09-26(S4): 시나리오 S4-C 가 WORLD_BIBLE_DEEP §7 표 1행과 imprint_lines.json 줄을 채웠다 →
        # 자리표시(_pending_text)를 풀고 정식 문구로 바꾼다. 연출문은 imprint_lines.json 이 다시 덮어쓴다(파일 우선).
        "id": "knock_heard",
        "name": "두드림을 들은 자",
        "crisis": "beast",
        "crisis_ko": "대형 생물 조우 (긴목·문지기가 다녀가고 생환)",
        "trigger": {"type": "event_survived", "event_ids": [], "factions": [], "counter_tags": [],
                    "id_prefixes": [], "flags": ["beast_left"]},
        "visual": {"keyword": "knock_twice_and_wait",
                   "ko": "무엇을 만지기 전에 두 번 두드리고 대답을 기다린다. 귀가 소리 쪽으로 먼저 돈다",
                   "line": "{name}의 손끝에 아직 유리의 떨림이 남아 있다. 무엇을 만지기 전에 두 번 두드리고, 대답을 기다린다."},
        "effect": {"counter_bonus": {"야행": 0.2}},
        "cost": {"ko": "두드리는 소리가 나면 하던 일을 멈춘다 — 밤 작업이 느려진다",
                 "effect": {"night_production": -1}},
    },
]
_HAVE_IMPRINTS = {i["id"] for i in IMPRINT_LIST}
IMPRINT_LIST += [i for i in DEEP_IMPRINTS if i["id"] not in _HAVE_IMPRINTS]   # 파일이 먼저, 코드가 나중
IMPRINTS = {i["id"]: i for i in IMPRINT_LIST}

# 심해 카드의 flag 별칭. data/events_deep.json 이 대형 생물 조우에 임시로 육상 flag(dino_escaped)를 쓰고 있다.
# 데이터는 시나리오 소유라 고치지 않고 **읽을 때 옮긴다**(DECISIONS 2026-09-22: 물속엔 발자국이 없다).
DEEP_FLAG_ALIAS = {"dino_escaped": "beast_left"}
DEEP_EVENT_PREFIX = "deep_"
IMPRINT_RULES = IMPRINT_DATA.get("_rules", {})
MAX_IMPRINTS = int(IMPRINT_RULES.get("max_per_resident", 3))
EVOLVE_AT = int(IMPRINT_RULES.get("evolve_at", 3))
MATCH_LEVELS = IMPRINT_DATA.get("_match", {}).get("levels", {})
ROLE_EVOLUTION = {k: v for k, v in IMPRINT_DATA.get("_role_evolution", {}).items() if not k.startswith("_")}


def _load_json(name: str):
    """시나리오가 나중에 내놓는 선택 파일. 없거나 깨져 있으면 None."""
    p = ROOT / "data" / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[data] {name} 무시: {e}")
        return None


# 역할 진화 이름: 부족 신화에서 받은 이름(data/roles_evolved.json)이 개발이 붙인 임시 이름을 이긴다.
# 성경 GROWTH_AND_MYTH §1 "진화는 부족 신화에서 이름을 받는다". 데이터 파일은 시나리오 소유라 고치지 않고 덮어쓴다.
_EVOLVED = _load_json("roles_evolved.json") or {}
ROLE_EVOLUTION.update({k: v for k, v in (_EVOLVED.get("_role_evolution") or {}).items()
                       if not k.startswith("_") and isinstance(v, str)})
# 각인 연출 문장: data/imprint_lines.json 의 line 이 imprints.json 의 개발 초안을 이긴다.
_LINES = _load_json("imprint_lines.json") or {}
for _row in (_LINES.get("lines") or []):
    _imp = IMPRINTS.get(_row.get("imprint_id")) if isinstance(_row, dict) else None
    if _imp and isinstance(_row.get("line"), str):
        _imp["visual"]["line"] = _row["line"]
# 생물·도구의 **문장**은 시나리오가 가진다(data/combat_schema.json 의 계약). 파일이 오면 코드 초안을 덮어쓴다.
# 수치(need·power·cost·gate)는 밸런스라 개발이 들고 있고 파일이 바꾸지 못한다 — DECISIONS 2026-09-20 과 같은 분담.
_CRE_TEXT = ("name", "zone", "how", "sound", "silhouette", "contact")
# 명단의 정본은 `data/creatures.json` 하나다(시나리오 2026-10-01 요청). 옛 이름도 받아 준다.
_CRE_FILES = ("creatures.json", "creatures_deep.json")
_CRE_SEEN: set = set()
for _f in _CRE_FILES:
    for _row in ((_load_json(_f) or {}).get("creatures") or []):
        if not isinstance(_row, dict) or _row.get("id") in _CRE_SEEN:
            continue
        _c = combat.CREATURES.get(_row.get("id"))
        if not _c:
            # 아직 전투 규칙이 없는 생물(거울눈·곧은치 등)은 조용히 건너뛴다.
            # 관문·수치가 정해지면 engine/combat.py 에 한 줄 넣는 것만으로 붙는다.
            continue
        _CRE_SEEN.add(_row["id"])
        _c.update({k: _row[k] for k in _CRE_TEXT if isinstance(_row.get(k), str)})
        if isinstance(_row.get("lines"), dict):
            _c["lines"] = {k: v for k, v in _row["lines"].items() if isinstance(v, str)}
for _row in ((_load_json("tools.json") or {}).get("tools") or []):
    _t = combat.TOOLS.get(_row.get("id")) if isinstance(_row, dict) else None
    if _t:
        _t.update({k: _row[k] for k in ("name", "does", "flavor") if isinstance(_row.get(k), str)})

TRUST_ON_COUNTER = 10        # 함께 위기를 넘겼을 때만 오른다
TRUST_ON_FAIL = -5           # 작은 일로도 급락한다
TRUST_MAX = 100
MAX_PARTICIPANTS = 2         # 사건 하나에 '나선' 사람은 1~2명. 나머지는 방주 안에 있었다

# ── 두 AI의 목소리 ────────────────────────────────────────────
# data/dialogue.json (시나리오 소유, 읽기만). when 태그로 상황에 맞는 한 줄을 고른다.
# 리더 = 과거의 목소리(명령·약속), 정원사 = 현재의 손(질문). 같은 태그에 둘 다 있으면 시드로 고른다.
DIALOGUE = json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))
VOICE_LINES: dict[str, list[dict]] = {}
for _who in ("reader", "gardener"):
    for _line in DIALOGUE.get(_who, []):
        if isinstance(_line, dict) and _line.get("when") and _line.get("text"):
            # 줄마다 acts 배열(없으면 전 막 공용). 1막 사람들은 숲도 일곱도 모른다(DECISIONS 2026-09-22) —
            # 값 기입은 시나리오, 거르는 것은 여기(2026-09-26 PM 요청).
            _raw = _line.get("acts")
            _acts = sorted({int(a) for a in _raw if isinstance(a, (int, float)) and int(a) in (1, 2, 3)})                 if isinstance(_raw, list) else None
            VOICE_LINES.setdefault(_line["when"], []).append(
                {"who": _who, "text": _line["text"], "acts": _acts or [1, 2, 3]})
VOICE_KO = {"reader": "리더", "gardener": "정원사"}
VOICE_WEIGHT = {"reader": 2, "gardener": 1}    # 방주 안에서는 리더가 더 자주 들린다(정원사는 바깥·물가에서)
# 스캔 대사 태그는 카테고리에서 바로 만든다(scan_medical 등을 시나리오가 채우면 코드 수정 없이 붙는다).
# 줄이 없는 태그는 조용히 넘어간다. 음료는 전용 줄이 없으면 식품 줄로 대신한다.
SCAN_VOICE_FALLBACK = {"drink": "scan_food"}
NIGHT_START, NIGHT_END = 21, 5                 # 클라이언트 밤 톤(app.js)과 같은 경계

# ── 소문(힐링 스팟 단서) ───────────────────────────────────────
# docs/WORLD_PRESENTATION.md §1-3 "스캔 카테고리가 지도를 연다".
# 월드 좌표(m)는 지도 표식용 임시값이다. data/spots.json 은 시나리오 소유라 좌표를 넣지 않고 여기 둔다.
# 원점 = 몰 문턱. +x 동(숲·지상 노선), -x 서(강·터널), +y 남(지하 터널 방향), -y 북(언덕·옥상).
# 스팟 파일 목록. 사건 카드 EVENT_FILES 와 같은 패턴 — 시나리오가 새 묶음을 내면 한 줄만 는다.
#   spots.json      — 육상(3막으로 승격 예정)
#   spots_deep.json — 심해 1막 여섯 곳. **아직 없어도 정상 동작한다**(시나리오 대기, DECISIONS 2026-09-22)
SPOT_FILES = ("spots.json", "spots_deep.json")


def load_spots(files: tuple | list = SPOT_FILES) -> list[dict]:
    """스팟 전부를 한 목록으로 병합한다. id 는 파일을 넘어 유일해야 하고, 먼저 읽은 파일이 이긴다.
    파일이 없거나 깨졌거나 id/name 이 없는 줄은 조용히 건너뛴다(게임이 죽지 않게. 이유는 표준출력에)."""
    out: list[dict] = []
    have: set = set()
    for fname in files:
        rows = _load_json(fname)
        if rows is None:
            continue
        if not isinstance(rows, list):
            rows = [v for k, v in rows.items() if not k.startswith("_")] if isinstance(rows, dict) else []
        for s in rows:
            if not isinstance(s, dict) or not s.get("id") or not s.get("name"):
                print(f"[spots] {fname} 줄 건너뜀: id/name 없음 {str(s)[:40]}")
                continue
            if s["id"] in have:
                print(f"[spots] {fname} 중복 id 건너뜀: {s['id']}")
                continue
            out.append({**s, "_src": fname}); have.add(s["id"])
    return out


SPOTS = load_spots()
# 월드 좌표(m). 2026-09-22 S3-C: dev_world_S2.md §3-3 제안표로 교체했다.
# 기준계 = world.html 지형(400×250m), 원점 = 몰 문턱, +x 바깥(동), +z 남. 여기의 두 번째 값이 월드 Z다
# (/api/rumors·/api/spots 는 pos{x,y} 로 내보내고 클라이언트가 y 를 Z 로 읽는다 — S2 규약 유지).
# 옛 임시값은 6곳 중 3곳이 지형 밖(-170·-120)이거나 강 한가운데였다.
SPOT_POS = {
    "spot_flooded_train":     ( 62,  30),
    "spot_goldfish_canal":    (100, -18),
    "spot_greenhouse_cafe":   ( 30,  92),
    "spot_rooftop_garden":    (-30, 105),
    "spot_lantern_river":     (148,  55),
    "spot_forest_train_door": (178,  70),
}
# spot_id -> 누적 스캔 카테고리 조건. 2026-09-20 PM 요청으로 data/rumors.json 의 단서 카테고리를
# 게이트에 합쳤다(문구·의약·전자로 오는 소문도 실제로 열리게).
RUMOR_RULES = {
    "spot_flooded_train":     {"categories": ["drink", "medical"],   "need": 3},
    "spot_goldfish_canal":    {"categories": ["tobacco"],            "need": 2},
    "spot_greenhouse_cafe":   {"categories": ["food"],               "need": 4},
    "spot_forest_train_door": {"categories": ["electronics", "food"], "need": 2},
    "spot_rooftop_garden":    {"categories": ["apparel", "medical"], "need": 2},
    "spot_lantern_river":     {"categories": ["book", "stationery"], "need": 2},
}

# ── 심해 1막 자리 (data/spots_deep.json 대기) ────────────────────────────────
# 파일이 들어오면 **코드 수정 없이** 여기 두 표만 채우면 붙는다. 지금은 비어 있어도 정상이고,
# 비어 있는 동안에는 파일의 unlock(임시 게이트)과 파일의 pos/depth 가 대신 쓰인다.
# 좌표계(육상과 다르다): x = 척추 기준 좌우(m, +가 오른쪽), y = **깊이(m, 아래가 +)**.
#   무광층 0 ~ 약 400, 해구 400 이상. 화면 위(광층)는 음수. DECISIONS 2026-09-23 '성장 방향은 아래'.
# 깊이는 WORLD_BIBLE_DEEP §4 의 각 스팟 구역 표기를 그대로 옮긴 값이다(광층 < -258 / 박광층 -258~-106 /
# 무광층 -106~180 / 해구 문턱 180~240 / 해구 240~). 같은 경계가 static/base.js 의 ZONES 와 1:1이다.
SPOT_POS_DEEP: dict[str, tuple[int, int]] = {
    "spot_kelp_ceiling":     ( -60, -290),   # 광층 — 위를 보는 숲
    "spot_sunken_courtyard": (-190, -150),   # 박광층 — 침몰선 안뜰
    "spot_jelly_bloom":      (  95,   80),   # 무광층 — 등불 떼
    "spot_vent_garden":      (-140,  120),   # 무광층 — 열수구 정원
    "spot_brine_lake":       ( 170,  175),   # 무광층 바닥 — 물속의 호수
    "spot_whale_fall":       (  60,  230),   # 해구 입구 — 가라앉은 큰 것
}
# 해금 조건의 정본은 서버 표(DECISIONS 2026-09-20). 값은 `data/spots_deep.json` 의 unlock 을 그대로
# 옮겼다 — 시나리오가 정한 숫자를 바꾸지 않고 정본 자리만 서버로 가져온 것이다(밸런스 변경 아님).
RUMOR_RULES_DEEP: dict[str, dict] = {
    "spot_vent_garden":      {"categories": ["electronics"], "need": 2},
    "spot_jelly_bloom":      {"categories": ["stationery"],  "need": 3},
    "spot_sunken_courtyard": {"categories": ["book"],        "need": 3},
    "spot_whale_fall":       {"categories": ["food"],        "need": 3},
    "spot_brine_lake":       {"categories": ["drink"],       "need": 3},
    "spot_kelp_ceiling":     {"categories": ["apparel"],     "need": 4},
}
SPOT_POS.update(SPOT_POS_DEEP)
RUMOR_RULES.update(RUMOR_RULES_DEEP)


def spot_pos_of(sid: str, spot: dict | None = None) -> tuple[int, int] | None:
    """스팟 좌표. 표가 정본이고, 표에 없으면 파일의 pos{x,y} 또는 pos{x,depth} 를 받아 준다
    (심해 6곳이 들어오는 날 화면이 바로 켜지게. 값이 없으면 None → 클라이언트가 안 그린다)."""
    if sid in SPOT_POS:
        return SPOT_POS[sid]
    p = (spot or {}).get("pos")
    if isinstance(p, dict):
        x, y = p.get("x"), (p.get("y") if p.get("y") is not None else p.get("depth"))
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            return (int(x), int(y))
    return None
CAT_KO = {"food": "식품", "drink": "음료", "medical": "의약·화학", "electronics": "전자", "stationery": "문구",
          "book": "도서", "apparel": "의류", "tobacco": "담배·주류", "unknown": "정체불명"}


def spot_gate(sid: str, spot: dict | None = None) -> dict | None:
    """그 스팟을 여는 조건. **정본은 서버의 RUMOR_RULES**(DECISIONS 2026-09-20).
    표에 없는 새 스팟(심해 6곳 등)만 파일의 unlock 을 임시 게이트로 받아 준다 —
    그렇지 않으면 시나리오가 파일을 채워도 영영 안 열린다. 표에 들어오면 표가 이긴다."""
    rule = RUMOR_RULES.get(sid)
    if rule:
        return {"categories": list(rule["categories"]), "need": int(rule["need"]), "source": "rules"}
    unlock = (spot or {}).get("unlock")
    if isinstance(unlock, dict) and isinstance(unlock.get("category"), str):
        return {"categories": [unlock["category"]], "need": int(unlock.get("count") or 1), "source": "file"}
    return None


def scan_counts(uid: str) -> dict:
    with db() as con:
        rows = con.execute("SELECT category, COUNT(*) c FROM scans WHERE uid=? GROUP BY category", (uid,)).fetchall()
    return {r["category"]: r["c"] for r in rows}


def rumor_rule_audit() -> list[dict]:
    """`data/rumors.json` 줄별 `unlock` ↔ 서버 `RUMOR_RULES` 동기화 점검. 정본은 서버 표(DECISIONS 2026-09-20).

    파일의 `unlock` 은 **해금 조건이 아니라 그 한 줄이 읽힐 조건**(사다리)이므로 값이 표와 다른 것 자체는
    결함이 아니다. 실제 결함은 하나뿐이다 — **스팟이 열리는 순간 읽을 수 있는 줄이 한 줄도 없는 경우.**
    그때 서버는 조건을 못 채운 줄로 되돌아가고, 플레이어는 아직 얻지 않은 지식이 적힌 소문을 읽는다.
    최악의 경로(표의 카테고리 하나만으로 need 를 채운 경우)를 전수 검사한다."""
    lines = rumor_lines()
    rows = []
    for sid, rule in RUMOR_RULES.items():
        pool = lines.get(sid) or []
        for cat in rule["categories"]:                       # 한 카테고리만으로 문턱을 넘는 최악의 경로
            counts = {cat: rule["need"]}
            ready = [ln for ln in pool if not ln.get("category") or counts.get(ln["category"], 0) >= (ln.get("count") or 0)]
            if not ready:
                rows.append({
                    "spot": sid, "path": f"{cat}×{rule['need']}",
                    "server": f"{'·'.join(rule['categories'])}×{rule['need']}",
                    "file": ", ".join(f"{ln.get('category')}×{ln.get('count')}" for ln in pool) or "(줄 없음)",
                    "why": "해금 순간 읽을 수 있는 줄 0 → 조건 미달 줄로 폴백",
                })
    return rows
RUMORS_PATH = ROOT / "data" / "rumors.json"    # 시나리오 에이전트가 만드는 중. 있으면 단서 문장을 여기서 가져온다
_RUMORS_CACHE: dict = {"mtime": None, "by_spot": {}}

DAILY_SCAN_CAP = 20
PRODUCTION_TICK_SEC = 8 * 3600      # 방 생산 주기 (8시간 = 하루 3틱)
MAX_OFFLINE_TICKS = 3
SLOTS = 10                          # 지상 0~4, 지하 5~9
HAND_LIMIT = 20

app = FastAPI(title="RELIC ARK Phase 0")


# ─────────────────────────────────────────────────────────────
# DB
# ─────────────────────────────────────────────────────────────
def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS arks (uid TEXT PRIMARY KEY, state TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS scans (id INTEGER PRIMARY KEY, uid TEXT, barcode TEXT, category TEXT,
            rarity TEXT, mult REAL, ts REAL, day INTEGER);
        CREATE TABLE IF NOT EXISTS family_votes (uid TEXT, family_code TEXT, category TEXT, ts REAL);
        CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, uid TEXT, kind TEXT, payload TEXT, ts REAL);
        CREATE TABLE IF NOT EXISTS codes (code TEXT PRIMARY KEY, uid TEXT NOT NULL, created REAL, used REAL);
        CREATE INDEX IF NOT EXISTS codes_uid ON codes(uid);
        """)


def log(uid: str, kind: str, payload: dict | None = None):
    with db() as con:
        con.execute("INSERT INTO logs(uid,kind,payload,ts) VALUES(?,?,?,?)",
                    (uid, kind, json.dumps(payload or {}, ensure_ascii=False), time.time()))


# ─────────────────────────────────────────────────────────────
# 이어하기 — **여섯 자리 복구 코드** (DECISIONS D5 추천안, S10-C)
#   폰으로 하는 게임인데 지금까지는 localStorage 의 uid 하나뿐이라, 기기를 바꾸거나 브라우저
#   데이터를 지우면 방주가 통째로 사라졌다. 계정도 비밀번호도 만들지 않는다 —
#   **보여 주고 적어 두라고 말하는 여섯 글자**가 전부다(첫 3분 루프에 탭을 한 번도 더하지 않는다, D5).
#   기존 uid 사용자는 처음 열 때 코드가 하나 발급되고 방주는 그대로다(마이그레이션 = 없음).
# ─────────────────────────────────────────────────────────────
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # 0·O·1·I·L 제외. 손으로 적고 다시 치는 글자다
CODE_LEN = 6                                          # 32^6 ≈ 10.7억. 한 사람이 찍어 맞힐 수는 없다
CODE_GROUP = 3                                        # 화면에는 ABC-DEF 로 끊어 보여 준다


def normalize_code(raw: str) -> str:
    """사람이 적은 것을 받아 준다 — 소문자·공백·하이픈·헷갈리는 글자(O→0 아님, 0→O)를 되돌린다."""
    up = "".join(ch for ch in str(raw or "").upper() if ch.isalnum())
    fix = {"0": "O", "O": "O", "1": "I", "I": "I", "L": "I"}     # 적힌 모양 기준으로 되돌린다
    out = []
    for ch in up:
        if ch in CODE_ALPHABET:
            out.append(ch)
        elif ch in ("0", "O"):
            out.append("Q")      # O 계열은 알파벳에 없다 → 가장 가까운 Q 로 본다
        elif ch in ("1", "I", "L"):
            out.append("J")
        else:
            out.append(ch)
    return "".join(out)[:CODE_LEN]


def code_pretty(code: str) -> str:
    return "-".join(code[i:i + CODE_GROUP] for i in range(0, len(code), CODE_GROUP))


def issue_code(uid: str) -> str:
    """그 방주의 복구 코드. 이미 있으면 그대로 돌려준다(코드는 하나뿐이고 바뀌지 않는다)."""
    with db() as con:
        row = con.execute("SELECT code FROM codes WHERE uid=? ORDER BY created LIMIT 1", (uid,)).fetchone()
        if row:
            return row["code"]
        rng = random.SystemRandom()
        for _ in range(40):
            code = "".join(rng.choice(CODE_ALPHABET) for _ in range(CODE_LEN))
            try:
                con.execute("INSERT INTO codes(code,uid,created,used) VALUES(?,?,?,NULL)",
                            (code, uid, time.time()))
                return code
            except sqlite3.IntegrityError:
                continue            # 충돌. 다시 뽑는다
    raise HTTPException(500, "코드를 만들지 못했습니다. 잠시 뒤 다시 시도해 주세요")


def uid_for_code(code: str) -> str | None:
    with db() as con:
        row = con.execute("SELECT uid FROM codes WHERE code=?", (code,)).fetchone()
        if row:
            con.execute("UPDATE codes SET used=? WHERE code=?", (time.time(), code))
        return row["uid"] if row else None


# ─────────────────────────────────────────────────────────────
# 주민 스탯 넷 (docs/RESIDENT_STATS.md)
#   손 만들고 · 눈 찾고 · 숨 버티고 · 담 맞선다. 게임 안의 동사 하나씩이다.
#   **스탯은 시작의 차이고, 각인은 얻어 낸 변화다**(§3-3). 스탯은 거의 변하지 않는다 —
#   사람이 바뀌는 일은 계단식 성장(각인)이 맡는다.
#   시드는 `uid|resident_id|stats`. 같은 방주의 같은 사람은 언제 읽어도 같은 사람이다(D6).
# ─────────────────────────────────────────────────────────────
RES_KO_SRV = {"food": "식량", "water": "물", "med": "의약", "power": "전력", "parts": "부품",
              "morale": "사기", "cloth": "직물", "trade": "교역", "knowledge": "지식",
              "scrap": "잔해", "chem": "화학"}
STAT_KEYS = ("hand", "eye", "breath", "nerve")
STAT_KO = {"hand": "손", "eye": "눈", "breath": "숨", "nerve": "담"}
STAT_USE = {"hand": "제작·수리", "eye": "탐사·예고", "breath": "버팀·회복", "nerve": "방어 판정"}
STAT_BASE = {                      # §3-1 역할 기본값: 둘이 높고 하나가 낮다
    "scout":    {"hand": 4, "eye": 7, "breath": 7, "nerve": 5},
    "cook":     {"hand": 7, "eye": 4, "breath": 5, "nerve": 5},
    "medic":    {"hand": 7, "eye": 6, "breath": 4, "nerve": 5},
    "engineer": {"hand": 8, "eye": 5, "breath": 5, "nerve": 4},
    "farmer":   {"hand": 6, "eye": 5, "breath": 7, "nerve": 4},
    "scholar":  {"hand": 5, "eye": 8, "breath": 4, "nerve": 4},
    "trader":   {"hand": 4, "eye": 6, "breath": 5, "nerve": 7},
    "kid":      {"hand": 3, "eye": 6, "breath": 4, "nerve": 3},
}
STAT_BASE_DEFAULT = {"hand": 5, "eye": 5, "breath": 5, "nerve": 5}
# §3-2 특이점 — 사람을 기억하게 만드는 한 줄. **마이너스를 반드시 섞는다**(약점이 없으면 배치에 고민이 없다)
QUIRK_KO = {
    ("hand", 1): "손이 유난히 좋다", ("hand", -1): "손이 서툴다",
    ("eye", 1): "눈이 밝다",       ("eye", -1): "밤눈이 어둡다",
    ("breath", 1): "숨이 길다",     ("breath", -1): "숨이 짧다",
    ("nerve", 1): "겁이 없다",      ("nerve", -1): "큰 것 앞에서는 못 선다",
}
QUIRK_BONUS = 2


def roll_stats(uid: str, rid: str, role: str) -> tuple[dict, dict]:
    """역할 기본값 + 무작위(−2~+2) + 특이점(한 스탯에 ±2). 범위 1~10."""
    rng = random.Random(f"{uid}|{rid}|stats")
    base = STAT_BASE.get(role, STAT_BASE_DEFAULT)
    stats = {k: base[k] + rng.randint(-2, 2) for k in STAT_KEYS}
    qk = rng.choice(list(STAT_KEYS))
    qs = 1 if rng.random() < 0.5 else -1          # 절반은 약점이다
    stats[qk] += QUIRK_BONUS * qs
    stats = {k: max(1, min(10, v)) for k, v in stats.items()}
    quirk = {"stat": qk, "stat_ko": STAT_KO[qk], "sign": qs, "ko": QUIRK_KO[(qk, qs)]}
    return stats, quirk


def ensure_stats(uid: str, r: dict) -> bool:
    """스탯이 없는 (구버전) 주민에게 같은 규칙으로 채운다. 기존 저장은 깨지지 않는다."""
    ok = isinstance(r.get("stats"), dict) and all(k in r["stats"] for k in STAT_KEYS)
    if ok and isinstance(r.get("quirk"), dict):
        return False
    stats, quirk = roll_stats(uid, r.get("id") or r.get("name") or "?", r.get("role") or "")
    r["stats"] = stats; r["quirk"] = quirk
    return True


def best_stat(people: list, key: str) -> tuple[int, dict | None]:
    """그 무리에서 가장 좋은 값과 그 사람. 없으면 (0, None)."""
    best, who = 0, None
    for p in people:
        v = int((p.get("stats") or {}).get(key, 0))
        if v > best:
            best, who = v, p
    return best, who


EYE_EARLY = 8        # 「눈」이 이만큼이면 예고를 한 단계 먼저 읽는다(§4) — 소리 단계에서 이미 어느 창인지 안다
HAND_GOOD, HAND_POOR = 8, 3    # 제작: 손이 좋으면 재료 하나를 아끼고, 서툴면 하나 더 든다


def make_resident(role: str, rng: random.Random, taken: set, uid: str = "") -> dict:
    name = next((n for n in rng.sample(NAMES, len(NAMES)) if n not in taken), f"주민{len(taken) + 1}")
    taken.add(name)
    trait = rng.choice(list(TRAITS.keys())) if rng.random() < 0.7 else None
    r = ROLES[role]
    return {"id": f"{role}-{int(rng.random() * 1e6)}", "name": name, "role": role, "role_ko": r["ko"], "ability": r["ability"],
            "trait": trait, "injured": False, "joined": time.time(),
            "imprints": [],     # 받은 각인 id (최대 3)
            "crises": [],       # 겪어 본 위기 종류. 여기 있는 종류는 다시 겪어도 사람을 바꾸지 않는다
            "trust": {},        # 다른 주민 id -> 0~100. 시작은 0 (사람 간 신뢰의 역전)
            "stats": {}, "quirk": {}}   # ensure_stats 가 uid 를 알고 채운다(시드가 uid 를 쓴다)


def new_state(uid: str = "") -> dict:
    now = time.time()
    rng = random.Random(now)
    taken: set = set()
    residents = [make_resident(role, rng, taken, uid) for role in ("cook", "engineer", "scout")]   # 시작 3인: 먹이고, 고치고, 살핀다
    for _r in residents:
        ensure_stats(uid, _r)
    return {
        "residents_list": residents,
        "created": now, "last_tick": now,
        "resources": {"food": 4, "water": 4, "med": 0, "power": 0, "parts": 1, "morale": 5,
                      "cloth": 0, "trade": 0, "knowledge": 0, "scrap": 2, "chem": 0},
        "rooms": [{"id": "pantry", "slot": 2, "built": now}],   # 시작 방주: 지하 1층 식량창고 1칸 (첫 화면이 비지 않게)
        "residents": 3, "injured": 0,
        "hand": [],             # 유물 카드 (대항용)
        "codex": {},            # category -> {template_name: count}
        "recent_events": [],
        "today_event": None,    # {"day":n, "event_id":..., "resolved":bool, "countered":bool}
        "hardcore": False,
        # 지금 있는 막. 1 심해 유리돔(1막) / 2 침수 터널 / 3 지상. DECISIONS 2026-09-23 — 오늘의 사건 풀을 이 값이 고른다
        "act": 1,
        "blueprint_progress": 0,
        "seen_events": [],      # 이미 한 번 나온 사건 id. 부족 첫 접촉(tribe_*)은 여기 있으면 다시 뽑지 않는다
        "rumors_seen": [],      # 이미 해금한 힐링 스팟 단서 id
        "morning_pending": [],  # 각인 받은 '다음 날 아침'에 한 번 보여 줄 연출 문장
        "greeted": False,       # 첫 화면에서 리더의 첫 말(game_start)을 들었는가
        # ── 배치 방어(COMBAT_AND_DEFENSE.md) ──────────────────────────
        "stations": {},         # resident_id -> slot. 없는 사람은 홀에 모인다
        "lights": {},           # str(slot) -> bool. 없으면 켜져 있다(기본 True)
        "power_on": True,       # 전원. 내리면 조용해지지만 모든 방이 어두워진다
        "tools": {},            # tool_id -> 보유 수(아직 설치하지 않은 것)
        "room_tools": {},       # str(slot) -> [{"id":..., "uses":n}]  설치된 것
        "outside": [],          # 지금 밖에 나가 있는 주민 id
        "raid": None,           # 오늘의 습격(없으면 None)
        "raid_log": [],         # 지나간 습격들. 흔적은 지워지지 않는다
        "next_raid_hint": None, # 문어가 미리 알려 준 다음 습격
    }


def load_state(uid: str) -> dict:
    with db() as con:
        row = con.execute("SELECT state FROM arks WHERE uid=?", (uid,)).fetchone()
    if row:
        st = json.loads(row["state"])
        if "residents_list" not in st:            # 구버전 방주 마이그레이션
            rng = random.Random(st.get("created", 0)); taken: set = set()
            st["residents_list"] = [make_resident(role, rng, taken, uid) for role in ("cook", "engineer", "scout")][: max(1, st.get("residents", 3))]
            for r in st["residents_list"][: st.get("injured", 0)]:
                r["injured"] = True
            save_state(uid, st)
        changed = migrate_residents(st, uid)      # 각인·신뢰·스탯이 없는 구버전 주민 보강
        changed = migrate_state(st) or changed    # 소문·사건 이력 필드 보강
        if changed:
            save_state(uid, st)
        return st
    st = new_state(uid)
    save_state(uid, st)
    log(uid, "ark_created")
    return st


def save_state(uid: str, st: dict):
    with db() as con:
        con.execute("INSERT OR REPLACE INTO arks(uid,state) VALUES(?,?)",
                    (uid, json.dumps(st, ensure_ascii=False)))


def migrate_residents(st: dict, uid: str = "") -> bool:
    """구버전 방주의 주민에 각인·신뢰·**스탯** 필드를 채운다. 변경이 있으면 True.
    스탯 시드는 `uid|id|stats` 라 구버전 주민도 **언제 읽어도 같은 사람**이 된다(D6)."""
    changed = False
    res = st.get("residents_list", [])
    ids = {r.get("id") for r in res}
    for i, r in enumerate(res):
        if not r.get("id"):
            r["id"] = f"{r.get('role', 'res')}-{i}"; ids.add(r["id"]); changed = True
        for key, default in (("imprints", []), ("crises", []), ("trust", {})):
            if not isinstance(r.get(key), type(default)):
                r[key] = type(default)(); changed = True
        changed = ensure_stats(uid, r) or changed
        drop = [k for k in r["trust"] if k not in ids or k == r["id"]]
        for k in drop:
            r["trust"].pop(k); changed = True
    return changed


def migrate_state(st: dict) -> bool:
    """스프린트 2에서 추가된 방주 필드(사건 이력·소문 이력)를 구버전 방주에 채운다."""
    changed = False
    for key in ("seen_events", "rumors_seen", "morning_pending"):
        if not isinstance(st.get(key), list):
            st[key] = []; changed = True
    if st.get("act") not in ACTS:        # 구버전 방주는 전부 1막(심해)에서 시작한다
        st["act"] = 1; changed = True
    te = st.get("today_event")
    if te and te.get("event_id") and te["event_id"] not in st["seen_events"]:
        st["seen_events"].append(te["event_id"]); changed = True     # 이미 겪은 오늘의 사건은 겪은 것으로
    # 배치 방어(S8). 구버전 방주는 "아무도 배치되지 않았고 불은 켜져 있고 습격은 없었다"로 시작한다
    for key, default in (("stations", {}), ("lights", {}), ("tools", {}), ("room_tools", {}),
                         ("outside", []), ("raid_log", [])):
        if not isinstance(st.get(key), type(default)):
            st[key] = type(default)(); changed = True
    if not isinstance(st.get("power_on"), bool):
        st["power_on"] = True; changed = True
    for key in ("raid", "next_raid_hint"):
        if key not in st:
            st[key] = None; changed = True
    ids = {r.get("id") for r in st.get("residents_list", [])}
    for gone in [k for k in st["stations"] if k not in ids]:
        st["stations"].pop(gone); changed = True                     # 떠난 사람의 자리는 비운다
    st["outside"] = [i for i in st["outside"] if i in ids]
    return changed


# ─────────────────────────────────────────────────────────────
# 두 AI의 목소리 (data/dialogue.json 의 when 태그)
# ─────────────────────────────────────────────────────────────
def voice_for(tag: str, seed: str, who: str | None = None, act: int | None = None) -> dict | None:
    """상황 태그에 맞는 한 줄. 같은 입력이면 같은 줄(D6: 시드 결정성).
    act 를 주면 그 막에서 할 수 있는 말만 남긴다. acts 가 없는 줄은 전 막 공용이므로
    시나리오가 값을 채우기 전에도 지금과 똑같이 동작한다(줄이 갑자기 사라지지 않는다)."""
    pool = [ln for ln in VOICE_LINES.get(tag, []) if who is None or ln["who"] == who]
    if act in (1, 2, 3):
        in_act = [ln for ln in pool if act in ln.get("acts", [1, 2, 3])]
        pool = in_act or []        # 그 막에서 할 말이 없으면 **말하지 않는다**(엉뚱한 막의 대사보다 침묵이 낫다)
    if not pool:
        return None
    rng = random.Random(f"voice|{seed}|{tag}")
    line = rng.choices(pool, weights=[VOICE_WEIGHT.get(ln["who"], 1) for ln in pool], k=1)[0]
    return {"who": line["who"], "who_ko": VOICE_KO[line["who"]], "text": line["text"], "when": tag}


def is_night(hour: int | None = None) -> bool:
    h = datetime.now().hour if hour is None else hour
    return h >= NIGHT_START or h < NIGHT_END


# ─────────────────────────────────────────────────────────────
# 소문: 스캔 카테고리 누적이 힐링 스팟 단서를 연다
# ─────────────────────────────────────────────────────────────
def rumor_lines() -> dict[str, list[dict]]:
    """data/rumors.json 이 있으면 spot_id -> [{text, who}] 로 읽는다(없으면 빈 dict).
    시나리오 에이전트가 쓰는 중이라 필드명을 넓게 받는다. 깨져 있으면 조용히 무시하고 spots.clue_text 로 되돌아간다."""
    try:
        mtime = RUMORS_PATH.stat().st_mtime
    except OSError:
        _RUMORS_CACHE.update({"mtime": None, "by_spot": {}})
        return {}
    if _RUMORS_CACHE["mtime"] == mtime:
        return _RUMORS_CACHE["by_spot"]
    by_spot: dict[str, list[dict]] = {}
    try:
        raw = json.loads(RUMORS_PATH.read_text(encoding="utf-8"))
        rows = raw if isinstance(raw, list) else [v for k, v in raw.items() if not k.startswith("_")]
        flat: list = []
        for row in rows:                                   # {"spot_id":[...]} 같은 중첩도 받아 준다
            flat.extend(row) if isinstance(row, list) else flat.append(row)
        for row in flat:
            if not isinstance(row, dict):
                continue
            sid = next((row[k] for k in ("spot_id", "spot") if isinstance(row.get(k), str)), None)
            text = next((row[k] for k in ("clue_text", "text", "clue", "line", "sentence") if isinstance(row.get(k), str)), None)
            who = next((row[k] for k in ("who", "carrier", "source", "from") if isinstance(row.get(k), str)), None)
            unlock = row.get("unlock") if isinstance(row.get("unlock"), dict) else {}
            cat = unlock.get("category") if isinstance(unlock.get("category"), str) else None
            cnt = unlock.get("count") if isinstance(unlock.get("count"), int) else 0
            if sid and text:
                by_spot.setdefault(sid, []).append({"text": text, "who": who, "category": cat, "count": cnt})
    except (json.JSONDecodeError, OSError, AttributeError) as e:
        print(f"[rumors] data/rumors.json 무시: {e}")
        by_spot = {}
    _RUMORS_CACHE.update({"mtime": mtime, "by_spot": by_spot})
    return by_spot


# ─────────────────────────────────────────────────────────────
# 각인(刻印): 처음 겪는 종류의 위기를 살아서 넘긴 사람만 변한다
# ─────────────────────────────────────────────────────────────
def imprint_for(ev: dict | None, flags: list[str] | None = None) -> dict | None:
    """사건 카드(+해결 중 생긴 flag)를 위기 종류로 판정해 각인 하나를 고른다.
    맞춤 단계: flag(4) > event_ids·id_prefixes(3) > factions·tribes(2) > counter_tags(1).
    같은 단계에서 여러 개가 맞으면 data/imprints.json 의 앞선 것이 이긴다."""
    flags = list(flags or [])
    best, best_level = None, 0
    for imp in IMPRINT_LIST:
        t = imp.get("trigger", {})
        level = 0
        if flags and set(t.get("flags", [])) & set(flags):
            level = 4
        elif ev:
            if ev.get("positive") and not IMPRINT_RULES.get("positive_event_grants", False):
                continue                               # 긍정 사건(표류자·유물 창고)은 사람을 바꾸지 않는다
            eid = ev.get("id", "")
            if eid in t.get("event_ids", []) or any(eid.startswith(p) for p in t.get("id_prefixes", [])):
                level = MATCH_LEVELS.get("event_ids", 3)
            elif ev.get("faction") in t.get("factions", []) or (ev.get("tribe") and ev["tribe"] in t.get("tribes", [])):
                level = MATCH_LEVELS.get("factions", 2)
            elif set(ev.get("counter_tags", [])) & set(t.get("counter_tags", [])):
                level = MATCH_LEVELS.get("counter_tags", 1)
        if level > best_level:
            best, best_level = imp, level
    return best


def grant_imprints(st: dict, ev: dict | None, flags: list[str], targets: list[dict]) -> list[dict]:
    """살아남은 주민 중 그 위기 종류가 '처음'인 사람에게 각인을 준다.
    반환: [{resident, imprint, line, evolved}] — /api/event/resolve 의 new_imprints."""
    imp = imprint_for(ev, flags)
    if not imp:
        return []
    out = []
    for r in targets:
        r.setdefault("crises", []); r.setdefault("imprints", [])
        if imp["crisis"] in r["crises"]:
            continue                                   # 두 번째부터는 성장이 없다
        r["crises"].append(imp["crisis"])
        if imp["id"] in r["imprints"] or len(r["imprints"]) >= MAX_IMPRINTS:
            continue                                   # 같은 각인은 한 번, 최대 3개
        r["imprints"].append(imp["id"])
        evolved = False
        if len(r["imprints"]) >= EVOLVE_AT and not r.get("role_evolved"):
            r["role_evolved"] = True
            r["evolved_ko"] = ROLE_EVOLUTION.get(r["role"], r.get("role_ko"))
            evolved = True
        line = imp["visual"]["line"].replace("{name}", r["name"])
        out.append({
            "resident": r["name"], "resident_id": r["id"], "role_ko": r.get("role_ko"),
            "imprint": {"id": imp["id"], "name": imp["name"], "crisis_ko": imp.get("crisis_ko"),
                        "visual": imp["visual"]["ko"], "effect": imp["effect"], "cost": imp["cost"].get("ko"),
                        "pending": bool(imp.get("_pending_text"))},
            "line": line,
            "evolved": evolved, "evolved_ko": r.get("evolved_ko") if evolved else None,
        })
        # 변화는 계단이다 — "그 다음 날 아침"에 한 번 더 보인다 (GROWTH_AND_MYTH §1).
        st.setdefault("morning_pending", []).append({
            "day": day_of(st) + 1, "resident": r["name"], "resident_id": r["id"],
            "imprint_id": imp["id"], "imprint_name": imp["name"], "visual": imp["visual"]["ko"],
            "line": line, "evolved": evolved, "evolved_ko": r.get("evolved_ko") if evolved else None,
        })
    return out


def event_participants(roster: list[dict], ev: dict, seed: str, how: str, used_card: dict | None,
                       hero: dict | None, pre_injured: set, station_rooms: dict | None = None) -> list[dict]:
    """이 사건에 **나선** 주민 1~2명. 나머지는 방주 안에 있었으므로 각인을 받지 않는다.
    (docs/GROWTH_AND_MYTH.md §1 "겪어본 적 없는 위험을 넘긴 자만 변한다" — 겪은 사람이 누구인지부터 정한다)

    우선순위
      ① 역할 자동 대항으로 실제로 나선 사람(hero) — 무조건 첫 번째
      ② 사건의 counter_room 에 **배치**된 주민(`station` 필드). 자리 배치는 스프린트 3 태스크라 지금은 비어 있고,
         필드가 생기면 규칙을 고치지 않아도 1순위가 된다
      ③ 역할 counter_tags ∩ 사건 counter_tags — 그 일에 나설 이유가 있는 사람
      ④ 대항 카드로 막았으면, 그 카드의 태그와 맞는 역할 1명(카드를 건넨 손). 카드는 물건이지만 쓴 것은 사람이다
      ⑤ 그래도 아무도 없으면 시드 난수 1명 (uid|day|who_imprint)

    이미 누워 있던 부상자는 후보에서 뺀다(그 밤에 나서지 못했다). 전원이 부상이면 전원이 후보.
    roster 는 **사건 전**의 명단이다 — 사건 결과로 합류한 표류자는 그 밤을 겪지 않았으므로 후보가 아니다.
    상한 2명 — 시작 3인 방주에서 사건 세 번이면 전원이 역할 진화하던 S1 결함(review_sprint1 §S1-B 1번)의 교정.
    """
    res = list(roster)
    if not res:
        return []
    pool = [r for r in res if r["id"] not in pre_injured] or res
    tags = set(ev.get("counter_tags", [])) if ev else set()
    room = (ev or {}).get("counter_room")

    def by_tags(want: set) -> list[dict]:
        return [r for r in pool if want and set(ROLES.get(r["role"], {}).get("counter_tags", [])) & want]

    ranked: list[dict] = []
    if hero:
        ranked.append(hero)
    # ② 사건의 counter_room 에 **배치**된 주민. 2026-10-01(S8) 배치 시스템이 생기면서 이 줄이 실제로 산다.
    #    자리는 slot 으로 저장되므로 slot -> 방 id 로 풀어서 비교한다(station_room_ids).
    sr = station_rooms or {}
    ranked += [r for r in pool if room and sr.get(r["id"]) == room]
    ranked += by_tags(tags)
    if how == "card" and used_card:
        ranked += by_tags(set(used_card.get("tags", [])))
    picked: list[dict] = []
    for r in ranked:
        if r["id"] not in {p["id"] for p in picked}:
            picked.append(r)
        if len(picked) >= MAX_PARTICIPANTS:
            break
    if not picked:
        picked = [random.Random(f"{seed}|who_imprint").choice(pool)]     # 아무 이유도 없으면 그날 당번 한 사람
    return picked


def bump_trust(st: dict, delta: int):
    """사람 간 신뢰(docs/TRUST_AND_COMPANIONS.md §3): 함께 위기를 넘겼을 때만 오르고, 실패하면 급락한다."""
    res = st.get("residents_list", [])
    ids = [r["id"] for r in res]
    for a in res:
        t = a.setdefault("trust", {})
        for b in ids:
            if b == a["id"]:
                continue
            t[b] = max(0, min(TRUST_MAX, t.get(b, 0) + delta))
        for gone in [k for k in t if k not in ids]:
            t.pop(gone)


def trust_avg(r: dict) -> int:
    vals = list((r.get("trust") or {}).values())
    return int(round(sum(vals) / len(vals))) if vals else 0


def role_effects(st: dict) -> dict:
    """주민 역할·특성·각인의 누적 효과."""
    eff = {"room_bonus": {}, "build_discount": 0.0, "morale_daily": 0, "auto_counter": {}, "blueprint_rate": 1, "book_bonus": 0, "heal_rate": 1, "positive_event_weight": 1.0,
           "counter_bonus": {}, "food_daily": 0.0, "morale_cap": 0, "imprint_count": 0}
    for r in st.get("residents_list", []):
        if r.get("injured"):
            continue
        e = ROLES[r["role"]].get("effects", {})
        for room, bonus in e.get("room_bonus", {}).items():
            for k, v in bonus.items():
                eff["room_bonus"].setdefault(room, {}); eff["room_bonus"][room][k] = eff["room_bonus"][room].get(k, 0) + v
        eff["build_discount"] += e.get("build_discount", 0.0)
        eff["morale_daily"] += e.get("morale_daily", 0)
        eff["blueprint_rate"] = max(eff["blueprint_rate"], e.get("blueprint_rate", 1))
        eff["book_bonus"] += e.get("book_bonus", 0)
        eff["heal_rate"] = max(eff["heal_rate"], e.get("heal_rate", 1))
        eff["positive_event_weight"] *= e.get("positive_event_weight", 1.0)
        ac = ROLES[r["role"]].get("auto_counter", 0)
        for t in ROLES[r["role"]].get("counter_tags", []):
            eff["auto_counter"][t] = max(eff["auto_counter"].get(t, 0), ac)
        tr = TRAITS.get(r.get("trait") or "", {})
        eff["build_discount"] += tr.get("build_discount", 0.0); eff["morale_daily"] += tr.get("morale_daily", 0)
        # 각인: 능력과 대가를 함께 합산한다 (성장은 대가와 함께 온다)
        for imp_id in r.get("imprints", []):
            imp = IMPRINTS.get(imp_id)
            if not imp:
                continue
            eff["imprint_count"] += 1
            for src in (imp.get("effect", {}), imp.get("cost", {}).get("effect", {})):
                for k, v in src.items():
                    if k == "room_bonus" and isinstance(v, dict):
                        for room, bonus in v.items():
                            eff["room_bonus"].setdefault(room, {})
                            for kk, vv in bonus.items():
                                eff["room_bonus"][room][kk] = eff["room_bonus"][room].get(kk, 0) + vv
                    elif isinstance(v, dict):
                        dst = eff.setdefault(k, {})
                        for kk, vv in v.items():
                            dst[kk] = round(dst.get(kk, 0) + vv, 3)
                    elif isinstance(v, bool):
                        eff[k] = eff.get(k, False) or v
                    elif isinstance(v, (int, float)):
                        eff[k] = round(eff.get(k, 0) + v, 3)
    for tag, bonus in eff["counter_bonus"].items():          # 각인의 자동 대항 보너스를 역할 위에 얹는다
        eff["auto_counter"][tag] = round(min(0.95, eff["auto_counter"].get(tag, 0) + bonus), 3)
    eff["build_discount"] = min(0.5, eff["build_discount"])
    return eff


def day_of(st: dict) -> int:
    return int((time.time() - st["created"]) // 86400) + 1


# ── 생산물의 길 (S10-C 버그 셋 중 둘) ────────────────────────────
# `data/rooms.json` 의 produces 에는 **자원이 아닌 것이 둘** 있다. 시나리오 소유 파일이라 고치지 않고
# 읽을 때 올바른 자리로 보낸다(DEEP_IMPRINTS 와 같은 규약).
#   library.blueprint_progress → st["blueprint_progress"] (전에는 resources 에 유령 키를 만들어
#                                 화면에도 안 보이고 건설에도 안 쓰였다 = 서고 생산 사망)
#   infirmary.counter_card     → 손패의 **대항 카드** (값이 문자열이라 isinstance(v,int) 에서 걸러져
#                                 생산이 0 이었다)
NON_RESOURCE_PRODUCE = ("blueprint_progress", "counter_card")
COUNTER_CARD_SPECS = {
    # 유물 카드와 같은 모양이라야 손패 UI(app.js cardEl)가 그대로 그린다.
    "heal": {"name": "처치 꾸러미", "tags": ["치료"], "category": "medical", "rarity": "common",
             "card_type": "tool", "family_name": "의무실", "barcode": "8800000000013",
             "flavor": "끓인 천과 하얀 가루. 누가 언제 감았는지는 아무도 모른다.",
             "yields": {"med": 1}},
}


def make_counter_card(kind: str, st: dict) -> dict | None:
    """방이 만들어 내는 대항 카드 한 장. 스캔 카드와 같은 계약(id·barcode·tags)을 지킨다."""
    spec = COUNTER_CARD_SPECS.get(kind)
    if not spec or len(st.get("hand") or []) >= HAND_LIMIT:
        return None
    card = dict(spec)
    card["id"] = f"made-{kind}-{int(time.time() * 1000)}-{len(st['hand'])}"
    card["seed"] = card["id"]
    card["made_by_room"] = True
    st["hand"].append(card)
    return card


def tick_production(st: dict) -> dict:
    """오프라인 생산 정산. 반환: 이번에 생산된 자원 요약.

    관문의 **대가**가 여기서 돈을 낸다(defense.json gates.gate_cost):
      전원 차단(문지기의 정답) → 그 기간 전 방 생산 0 — 이 게임에서 가장 비싼 올바른 행동
      불 끄기(긴목의 정답)     → 그 방 생산 ×0.5 — 끄면 우리도 그 방을 못 본다
    """
    elapsed = time.time() - st["last_tick"]
    ticks = min(int(elapsed // PRODUCTION_TICK_SEC), MAX_OFFLINE_TICKS)
    produced: dict = {}
    if ticks <= 0:
        return produced
    if not st.get("power_on", True):
        # 전원을 내려 둔 채로 시간이 흘렀다. 조용한 대신 아무것도 만들지 못한다
        st["last_tick"] += ticks * PRODUCTION_TICK_SEC
        st["dark_note"] = {"kind": "blackout", "ticks": ticks,
                           "ko": "전원이 내려가 있는 동안 아무 방도 일하지 않았다."}
        return produced
    st.pop("dark_note", None)
    # 물 찬 방은 생산하지 않는다. 인접 보너스도 주지 않는다 — 그 방은 더 이상 방이 아니다
    live = [r for r in st["rooms"] if not r.get("flooded")]
    room_ids = [r["id"] for r in live]
    eff = role_effects(st)
    dark_rooms = []
    for r in live:
        spec = ROOMS[r["id"]]
        bonus = eff["room_bonus"].get(r["id"], {})
        mul = 1.0
        if not light_on(st, r["slot"]):
            mul = 0.5
            dark_rooms.append(ROOMS[r["id"]]["name"])
        for k, v in spec["produces"].items():
            if k in NON_RESOURCE_PRODUCE:
                if k == "blueprint_progress" and isinstance(v, (int, float)):
                    amt = int(round(v * ticks * mul))
                    st["blueprint_progress"] = int(st.get("blueprint_progress", 0)) + amt
                    if amt:
                        produced[k] = produced.get(k, 0) + amt
                elif k == "counter_card" and isinstance(v, str):
                    made = sum(1 for _ in range(int(max(1, round(ticks * mul))))
                               if make_counter_card(v, st))
                    if made:
                        produced[k] = produced.get(k, 0) + made
                continue
            if isinstance(v, (int, float)):
                amt = int(round((v + bonus.get(k, 0)) * ticks * mul))
                if not amt:
                    continue
                st["resources"][k] = st["resources"].get(k, 0) + amt
                produced[k] = produced.get(k, 0) + amt
        for nb, bonus in spec.get("adjacency_bonus", {}).items():
            if nb in room_ids:
                for k, v in bonus.items():
                    amt = int(round(v * ticks * mul))
                    if not amt:
                        continue
                    st["resources"][k] = st["resources"].get(k, 0) + amt
                    produced[k] = produced.get(k, 0) + amt
    if dark_rooms:
        st["dark_note"] = {"kind": "dark", "rooms": sorted(set(dark_rooms)),
                           "ko": "불을 꺼 둔 방은 절반만 일했다 — " + " · ".join(sorted(set(dark_rooms)))}
    # 부상 회복: 틱마다 1명 (의무병 있으면 2명)
    heal = eff["heal_rate"] * ticks
    # 숨이 긴 사람이 먼저 일어난다(RESIDENT_STATS §4 "부상 회복 = 숨 + 의무실 등급")
    for res in sorted(st.get("residents_list", []),
                      key=lambda r: -int((r.get("stats") or {}).get("breath", 5))):
        if res.get("injured") and heal > 0:
            res["injured"] = False; heal -= 1
    st["injured"] = sum(1 for x in st.get("residents_list", []) if x.get("injured"))
    st["last_tick"] += ticks * PRODUCTION_TICK_SEC
    return produced


def ark_state_obj(st: dict) -> ArkState:
    return ArkState(day=day_of(st), act=int(st.get("act") or 1),
                    resources=dict(st["resources"]), rooms=[r["id"] for r in st["rooms"]],
                    residents=st["residents"], injured=st["injured"], recent_events=list(st["recent_events"]),
                    hardcore=st["hardcore"])


# ── 공기·깊이 게이지 ─────────────────────────────────────────
# SCRIPT_first_10min_deep.md 3:00 비트와 시나리오 요청: **숫자가 아니라 줄어드는 띠**.
# 원정 시스템이 아직 없으므로 공기는 고정값이고(fixed=true), 깊이는 이미 존재하는 것
# (가장 깊은 방의 층)에서 나온다 — 고정값을 띄우면 아래로 증축했는데 깊이가 그대로인
# 거짓말이 화면에 남는다(D2: 모든 숫자는 화면의 무엇으로 보인다).
FLOOR_SLOTS = 2             # 한 층에 방 2칸. index.html·base.js 와 같은 규약(slot // 2 = 층)
DOME_FLOOR = 1              # 깊이 0 m 의 층 = 시작 방(slot 2)이 있는 층. 그 위 슬롯 0·1 은 돔 상부다
DEPTH_PER_FLOOR = 60        # 층 하나 = 60 m. static/base.js 의 같은 상수와 맞춘다
# 깊이 구역 경계(m). **해구 문턱은 180 m 다** — 밸런스 threats.json grade_source.map 의 등급 4 깊이와
# 같은 값이어야 한다(등급을 깊이로 판정하므로). S10-C 에서 150 → 180 으로 통일했다.
DEPTH_ZONES = ((0, "무광층"), (180, "해구 문턱"), (210, "해구"))   # static/base.js ZONES 와 같은 경계(m)
AIR_FIXED = 0.82            # ★ 원정(공기 소모)이 생기면 실제 값으로 바뀐다. 지금은 UI 자리만


def depth_zone(m: int) -> str:
    name = DEPTH_ZONES[0][1]
    for edge, ko in DEPTH_ZONES:
        if m >= edge:
            name = ko
    return name


def gauges_of(st: dict) -> dict:
    deepest = max([r["slot"] // FLOOR_SLOTS for r in st["rooms"]] or [DOME_FLOOR])
    floors = deepest + 1
    depth_m = max(0, deepest - DOME_FLOOR) * DEPTH_PER_FLOOR
    depth_max = (SLOTS // FLOOR_SLOTS - 1 - DOME_FLOOR) * DEPTH_PER_FLOOR
    return {
        # value 는 0~1. 클라이언트는 이 값을 **띠의 길이**로만 쓴다(숫자로 찍지 않는다)
        "air":   {"ko": "공기", "value": AIR_FIXED, "fixed": True,
                  "note": "원정 시스템 전까지 고정 — UI 자리만"},
        "depth": {"ko": "깊이", "value": (depth_m / depth_max) if depth_max else 0.0, "fixed": False,
                  "m": depth_m, "max_m": depth_max, "floors": floors, "zone": depth_zone(depth_m)},
        # 「먼 울음」 간격(초). PM 2026-09-26 커브: 90초에서 시작해 한 층 내려갈 때마다 5초씩, 하한 40초.
        # 내려갈수록 가까워진다 = 성장 방향이 아래라는 결정과 같은 말이다. **정체는 1막에서 밝히지 않는다** —
        # 서버는 간격만 내려보내고 이름도 설명도 붙이지 않는다. 사운드 층이 붙는 날 이 값을 그대로 쓰면 된다.
        "far_call_sec": max(40, 90 - 5 * max(0, deepest - DOME_FLOOR)),
    }


# ─────────────────────────────────────────────────────────────
# 배치 방어 (COMBAT_AND_DEFENSE.md) — 서버 쪽 배선
# 판정 공식과 생물·도구 표는 engine/combat.py 에 있다. 여기서는 **상태를 읽어 ctx 를 만들고**
# 돌아온 판정을 상태에 쓰기만 한다. 난수는 전부 `uid|day|raid|목적` 시드다(02_DEV D6).
# ─────────────────────────────────────────────────────────────

# 위협 등급 — **깊이로만 정해진다. 날짜가 아니다**(threats.json grade_source, BALANCE §3).
# 띄엄띄엄 하는 사람은 얕은 곳에 오래 머물고, 그에게는 센 것이 오지 않는다. 난이도를 시간이
# 밀면 조급해지고 플레이어가 당기면 아늑함이 남는다(B4).
THREAT_GRADES = sorted(
    [{"grade": int(r["grade"]), "depth_m": int(r.get("depth_m") or 0), "rooms_min": int(r.get("rooms_min") or 0)}
     for r in (((combat.THR.get("grade_source") or {}).get("map")) or []) if isinstance(r, dict) and r.get("grade")],
    key=lambda r: r["grade"]) or [{"grade": 1, "depth_m": 0, "rooms_min": 0}]


def depth_of(st: dict) -> int:
    """거점 최심부 깊이(m). 등급도 화면의 깊이 띠도 이 한 값에서 나온다."""
    deepest = max([r["slot"] // FLOOR_SLOTS for r in st.get("rooms", [])] or [DOME_FLOOR])
    return max(0, deepest - DOME_FLOOR) * DEPTH_PER_FLOOR


def grade_of(st: dict) -> int:
    """오늘 올 수 있는 위협의 등급 1~5. 깊이 + (등급 5 만) 방 칸 수."""
    depth_m, rooms = depth_of(st), len(live_rooms(st))
    g = THREAT_GRADES[0]["grade"]
    for row in THREAT_GRADES:
        if depth_m >= row["depth_m"] and rooms >= row["rooms_min"]:
            g = row["grade"]
    return int(g)

def live_rooms(st: dict) -> list[dict]:
    """아직 방인 것들. 물 찬 방은 빠진다."""
    return [r for r in st.get("rooms", []) if not r.get("flooded")]


def room_at(st: dict, slot) -> dict | None:
    try:
        slot = int(slot)
    except (TypeError, ValueError):
        return None
    return next((r for r in st.get("rooms", []) if r.get("slot") == slot), None)


def station_slot(st: dict, rid: str):
    v = (st.get("stations") or {}).get(rid)
    return int(v) if isinstance(v, (int, float)) else None


def stations_map(st: dict) -> dict:
    """slot -> 거기 배치된 주민들. 밖에 나간 사람은 방에 없다."""
    out: dict = {}
    outside = set(st.get("outside") or [])
    for r in st.get("residents_list", []):
        s = station_slot(st, r.get("id"))
        if s is None or r["id"] in outside:
            continue
        out.setdefault(s, []).append(r)
    return out


def hall_of(st: dict) -> list[dict]:
    """배치되지 않은 사람은 홀에 모인다(돔 상부의 공용 공간)."""
    outside = set(st.get("outside") or [])
    return [r for r in st.get("residents_list", [])
            if station_slot(st, r.get("id")) is None and r["id"] not in outside]


def installed_at(st: dict, slot) -> list:
    rows = (st.get("room_tools") or {}).get(str(int(slot))) or []
    return [t["id"] for t in rows if isinstance(t, dict) and t.get("id") in combat.TOOLS]


def light_on(st: dict, slot) -> bool:
    """방의 불. 전원이 내려가 있으면 전부 꺼져 있고, 차광 덧문이 있으면 역시 어둡다."""
    if not st.get("power_on", True):
        return False
    if any(combat.TOOLS.get(t, {}).get("forces_dark") for t in installed_at(st, slot)):
        return False
    v = (st.get("lights") or {}).get(str(int(slot)))
    return True if v is None else bool(v)


def set_station(st: dict, rid: str, slot) -> None:
    stations = st.setdefault("stations", {})
    if slot is None:
        stations.pop(rid, None)
    else:
        stations[rid] = int(slot)


def station_room_ids(st: dict) -> dict:
    """resident_id -> 그 사람이 서 있는 방의 id. 사건 참여자 규칙 ②(배치된 사람 1순위)가 이걸 쓴다."""
    out = {}
    for rid, slot in (st.get("stations") or {}).items():
        r = room_at(st, slot)
        if r and not r.get("flooded"):
            out[rid] = r["id"]
    return out


def gathered_one_room(st: dict):
    """모두 한 방에 모였는가. 밖에 한 사람이라도 있거나 홀에 남아 있으면 아니다."""
    if st.get("outside"):
        return False, None
    if hall_of(st):
        return False, None
    slots = {station_slot(st, r["id"]) for r in st.get("residents_list", [])}
    if len(slots) == 1 and None not in slots:
        s = slots.pop()
        return (room_at(st, s) is not None), s
    return False, None


def lure_elsewhere(st: dict, slot) -> bool:
    """**다른 방**에 유인 등불이 켜져 있는가. 거울눈의 관문(반대쪽이 더 밝다)이 이것을 본다."""
    for r in live_rooms(st):
        if slot is not None and int(r["slot"]) == int(slot):
            continue
        if any(combat.TOOLS.get(t, {}).get("lures_elsewhere") for t in installed_at(st, r["slot"])):
            return True
    return False


def raid_ctx(st: dict, raid: dict, consumables: list | None = None) -> dict:
    """판정에 들어가는 '그 순간의 사실들'. 화면이 보여 주는 것과 한 글자도 달라서는 안 된다(D2)."""
    slot = raid.get("target_slot")
    r = room_at(st, slot)
    people = [{"id": p["id"], "name": p["name"], "injured": bool(p.get("injured")),
               "role": p.get("role"),
               "nerve": int((p.get("stats") or {}).get("nerve", 5)),
               "imprints": list(p.get("imprints") or [])}
              for p in stations_map(st).get(int(slot), [])] if slot is not None else []
    gathered, gslot = gathered_one_room(st)
    inst = installed_at(st, slot) if slot is not None else []
    return {
        "room_id": (r or {}).get("id") if r and not r.get("flooded") else None,
        "room_name": (ROOMS.get((r or {}).get("id"), {}).get("name") if r else None) or "빈 자리",
        "room_level": int((r or {}).get("level") or 1),
        "people": people,
        "light_on": light_on(st, slot) if slot is not None else True,
        "forced_dark": any(combat.TOOLS.get(t, {}).get("forces_dark") for t in inst),
        "power_on": bool(st.get("power_on", True)),
        "gathered_one_room": gathered,
        "hushed": bool(gathered and gslot is not None and any(
            combat.TOOLS.get(t, {}).get("silences") for t in installed_at(st, gslot))),
        "outside": list(st.get("outside") or []),
        "installed": inst,
        "consumables": list(consumables or []),
        # 도구가 대신 드는 손. 작은 떼의 관문(사람 수)에만 쓰인다
        "hands": sum(int((combat.TOOLS.get(t) or {}).get("hands", 0))
                     for t in list(inst) + list(consumables or [])),
        "severity": int(raid.get("severity", 0)),
        # ── S10-C 신규 관문 일곱이 읽는 사실 셋 ─────────────────────
        "grade": int(raid.get("grade") or grade_of(st)),      # need 가 등급에서 나온다
        "acts": list(raid.get("acts") or []),                 # 이번 습격에 치른 행동(대가를 이미 냈다)
        "moves": int(raid.get("moves") or 0),                 # 습격이 시작된 뒤 사람을 옮긴 횟수(덮개)
        "lure_elsewhere": lure_elsewhere(st, slot),           # 반대쪽이 더 밝은가(거울눈)
    }


def send_outside(st: dict, uid: str, day: int) -> list:
    """손톱 무리가 오는 날, 하필 밖에 나가 있던 사람. 홀에 있던 사람부터(일하러 나간 것이다).
    원정 시스템이 생기면 이 함수만 '진짜 나가 있는 사람'으로 바뀐다 — 호출부는 그대로다."""
    pool = [r["id"] for r in hall_of(st)] or [r["id"] for r in st.get("residents_list", [])]
    if not pool:
        return []
    n = 1 if len(pool) < 3 else 2
    rng = combat.raid_rng(uid, day, "outside")
    return sorted(rng.sample(sorted(pool), min(n, len(pool))))


def archive_raid(st: dict, raid: dict) -> None:
    rows = st.setdefault("raid_log", [])
    rows.append({k: raid.get(k) for k in
                 ("id", "day", "creature", "target_slot", "severity", "result", "line", "score",
                  "need", "grade", "gate_ok", "shielded")})
    del rows[:-60]


def ensure_raid(st: dict, uid: str, force: str | None = None, reset: bool = False,
                grade_force: int | None = None) -> dict | None:
    """오늘의 습격. **하루 1회 이하**(§6-1) — 이미 오늘 것이 있으면 새로 뽑지 않는다."""
    day = day_of(st)
    cur = st.get("raid")
    if cur and cur.get("day") == day and not (reset or force or grade_force):
        return None if cur.get("none") else cur
    st["outside"] = []                   # 어제 밖에 있던 사람은 밤새 들어왔다. 밖은 하루를 넘기지 않는다
    grade = int(grade_force) if grade_force else grade_of(st)
    cre = combat.pick_creature(uid, day, grade, force=force)
    if not cre:
        st["raid"] = {"day": day, "none": True, "grade": grade}
        return None
    slot = combat.pick_target(uid, day, cre, live_rooms(st), st.get("room_tools") or {})
    if slot is None:
        # 갈 방이 없다(전부 침수거나 전부 유인 등불). 긴목은 다른 불빛을 따라 간다
        st["raid"] = {"day": day, "none": True, "diverted": cre["id"], "grade": grade}
        return None
    sev = combat.severity(uid, day, grade)
    sev += int(st.pop("severity_debt", 0) or 0)      # 윗물 아이를 올려 보낸 값(금기를 어겼다)
    raid = {
        "id": f"raid-{day}-{cre['id']}", "day": day, "creature": cre["id"], "grade": grade,
        "target_slot": int(slot), "severity": max(0, min(4, sev)),
        "stage": "sound", "started": time.time(), "resolved": False, "result": None,
        "outside_sent": [], "acts": [], "moves": 0,
    }
    if cre["gate"] == "all_inside":
        raid["outside_sent"] = send_outside(st, uid, day)
        st["outside"] = list(raid["outside_sent"])      # 그 사람들은 지금 밖에 있다
    st["raid"] = raid
    return raid


def raid_public(st: dict, raid: dict | None) -> dict | None:
    """화면이 읽는 습격. **정보를 숨기지 않는다**(02_DEV §3 Slay the Spire) —
    지금 배치로 막을 수 있는지(`ready.gate`)를 접촉 전에 그대로 보여 준다. 그래야 계획이 가능하다."""
    if not raid or raid.get("none"):
        return None
    cre = combat.CREATURES.get(raid.get("creature"))
    if not cre:
        return None
    ctx = raid_ctx(st, raid)
    preview = combat.evaluate(cre, ctx)
    r = room_at(st, raid["target_slot"])
    room_name = (ROOMS.get((r or {}).get("id"), {}) or {}).get("name") if r else "빈 자리"
    # 「눈」이 밝은 사람이 안에 있으면 **소리만 듣고도 어느 창인지 안다**(RESIDENT_STATS §4).
    # 예고가 한 단계 앞당겨지는 것이지 접촉이 빨라지는 것이 아니다 — 아늑함은 그대로다.
    inside = [p for p in st.get("residents_list", []) if p["id"] not in (st.get("outside") or [])]
    eye, eye_who = best_stat(inside, "eye")
    early = bool(eye >= EYE_EARLY and eye_who)
    quiet = raid["stage"] == "sound" and not early    # 보통은 소리 단계에서 어느 방인지 모른다(§3-1·3-2)
    return {
        "id": raid["id"], "day": raid["day"], "stage": raid["stage"],
        "stage_ko": combat.STAGE_KO.get(raid["stage"], raid["stage"]),
        "stage_no": list(combat.STAGES).index(raid["stage"]) if raid["stage"] in combat.STAGES else 0,
        "creature": {"id": cre["id"], "name": cre["name"], "zone": cre["zone"], "threat": cre["threat"],
                     "how": cre["how"], "sound": cre["sound"], "silhouette": cre["silhouette"],
                     "contact": cre["contact"], "audio": cre.get("audio", {})},
        "target_slot": None if quiet else raid["target_slot"],
        "target_room": None if quiet else room_name,
        "severity": raid["severity"], "resolved": bool(raid.get("resolved")),
        "result": raid.get("result"), "result_ko": combat.RESULT_KO.get(raid.get("result") or ""),
        "line": raid.get("line"),
        "outside": list(st.get("outside") or []),
        "grade": int(raid.get("grade") or grade_of(st)),
        "moves": int(raid.get("moves") or 0),
        "acts": list(raid.get("acts") or []),
        # 그 생물을 막는 **행동 버튼**(관문이 토글로 안 되는 일곱). 대가와 낼 수 있는지까지 서버가 판단한다
        "action": None if quiet else gate_action_public(st, raid, cre),
        # 접촉 전 미리보기(실루엣 단계부터). 숫자보다 "무엇이 모자란지"를 먼저 말한다
        "eye_early": ({"name": eye_who["name"], "eye": eye,
                       "ko": eye_who["name"] + "의 눈이 밝다 — 소리만 듣고 어느 창인지 안다."} if early else None),
        "ready": None if quiet else {
            "gate": preview["gate"], "score": preview["score"], "need": preview["need"],
            "would": preview["result"], "would_ko": combat.RESULT_KO[preview["result"]],
            "parts": preview["parts"], "shielded": preview.get("shielded"),
        },
    }


def gate_action_public(st: dict, raid: dict, cre: dict) -> dict | None:
    """관문 행동 한 개(있는 생물만). 대가·충족 여부·이미 했는지를 전부 서버가 말한다 —
    화면은 계산하지 않는다(정보를 숨기지 않는다, 02_DEV §3 Slay the Spire)."""
    spec = combat.action_for_gate(cre.get("gate") or "none")
    if not spec:
        return None
    sev = int(raid.get("severity", 0))
    cost = combat.action_cost(spec["id"], sev)
    have = st.get("resources") or {}
    lack = {k: v - int(have.get(k, 0)) for k, v in cost.items() if int(have.get(k, 0)) < v}
    why = []
    if spec.get("needs_room") and not any(r["id"] == spec["needs_room"] for r in live_rooms(st)):
        why.append(f"{ROOMS.get(spec['needs_room'], {}).get('name', spec['needs_room'])}이(가) 없다")
    if spec.get("needs_hall") and not hall_of(st):
        why.append("홀에 사람이 없다 — 등을 순서대로 켤 사람이 필요하다")
    if spec.get("needs_power_on") and not st.get("power_on", True):
        why.append("전원이 내려가 있다")
    if spec.get("needs_light_on") and not light_on(st, raid.get("target_slot")):
        why.append("이 방의 불이 꺼져 있다 — 끄면 비침이 사라진다")
    if spec.get("spends_relic") and not (st.get("hand") or []):
        why.append("돌려보낼 유물이 창고에 없다")
    inst_now = installed_at(st, raid.get("target_slot"))
    cost_ko = spec["cost_ko"]
    if spec.get("strips_tools"):
        # 걷을 것이 없으면 공짜다. 대신 그 방은 지금 맨몸이라는 뜻이기도 하다
        cost_ko = ("걷어 낼 것: " + " · ".join(combat.TOOLS[t]["name"] for t in inst_now) +
                   " — 영영 잃는다") if inst_now else "그 방에는 걷어 낼 것이 없다. 비키기만 하면 된다"
    return {
        "id": spec["id"], "ko": spec["ko"], "why": spec["why"], "cost_ko": cost_ko,
        "cost": cost, "lacking": lack,
        "done": spec["id"] in (raid.get("acts") or []),
        "blocked": why,
        "can": not lack and not why and spec["id"] not in (raid.get("acts") or []),
    }


def workshop_hands(st: dict):
    """공방에 **서 있는 사람** 중 가장 좋은 손. 아무도 없으면 (0, None) — 도구는 손이 만든다."""
    slots = [r["slot"] for r in live_rooms(st) if r["id"] == "workshop"]
    smap = stations_map(st)
    who = []
    for sl in slots:
        who += smap.get(int(sl), [])
    return best_stat(who, "hand")


def craft_cost(st: dict, tool_id: str):
    """제작 재료. **손**이 좋으면 하나를 아끼고 서툴면 하나가 더 든다(RESIDENT_STATS §4).
    난수가 아니라 사람이 바꾸는 값이다 — 같은 사람이 만들면 늘 같은 값(D6)."""
    cost = dict(combat.TOOLS[tool_id]["cost"])
    hand, who = workshop_hands(st)
    note = None
    if who:
        big = max(cost, key=lambda k: cost[k])
        ko = RES_KO_SRV.get(big, big)
        if hand >= HAND_GOOD:
            cost[big] = max(1, cost[big] - 1)
            note = {"name": who["name"], "hand": hand, "ko": who["name"] + "의 손이 " + ko + " 하나를 아꼈다"}
        elif hand <= HAND_POOR:
            cost[big] = cost[big] + 1
            note = {"name": who["name"], "hand": hand, "ko": who["name"] + "의 손이 서툴러 " + ko + " 하나가 더 든다"}
        else:
            note = {"name": who["name"], "hand": hand, "ko": who["name"] + "이(가) 공방에 있다"}
    return cost, note


def tool_public(st: dict) -> dict:
    """공방·도구 상태. 제작 가능 여부와 **손 보정까지** 서버가 판단해 내려 준다(화면은 계산하지 않는다)."""
    have = st.get("resources", {})
    has_workshop = any(r["id"] == "workshop" for r in live_rooms(st))
    hand, who = workshop_hands(st)
    rows = []
    for tid, t in combat.TOOLS.items():
        cost, note = craft_cost(st, tid)
        lack = {k: v - have.get(k, 0) for k, v in cost.items() if have.get(k, 0) < v}
        rows.append({"id": tid, "name": t["name"], "kind": t["kind"], "does": t["does"],
                     "against": [combat.CREATURES[c]["name"] for c in t["against"]],
                     "cost": cost, "base_cost": t["cost"], "lacking": lack, "hands": note,
                     "can_craft": bool(has_workshop and not lack),
                     "owned": int((st.get("tools") or {}).get(tid, 0))})
    return {"has_workshop": has_workshop, "tools": rows,
            "hand": {"value": hand, "name": who["name"] if who else None},
            "installed": {k: v for k, v in (st.get("room_tools") or {}).items() if v}}


def combat_public(st: dict) -> dict:
    caps = {}
    for r in st.get("rooms", []):
        caps[str(r["slot"])] = 0 if r.get("flooded") else combat.room_cap(r["id"])
    return {
        "stations": {k: int(v) for k, v in (st.get("stations") or {}).items()},
        "hall": [r["id"] for r in hall_of(st)],
        "outside": list(st.get("outside") or []),
        "caps": caps,
        "lights": {str(r["slot"]): light_on(st, r["slot"]) for r in st.get("rooms", [])},
        "power_on": bool(st.get("power_on", True)),
        "raid": raid_public(st, st.get("raid")),
        "raid_log": list(st.get("raid_log") or [])[-8:],
        "next_raid_hint": st.get("next_raid_hint"),
        "workshop": tool_public(st),
        "grade": grade_of(st),
        "creatures": {c["id"]: {"name": c["name"], "how": c["how"], "threat": c["threat"],
                                "gate": c.get("gate", "none"),
                                "gate_ko": combat.GATE_KO.get(c.get("gate", "none"), "")}
                      for c in combat.CREATURES.values()},
    }


def public_state(st: dict, uid: str) -> dict:
    with db() as con:
        today = con.execute("SELECT COUNT(*) c FROM scans WHERE uid=? AND day=?", (uid, day_of(st))).fetchone()["c"]
    return {
        "day": day_of(st), "resources": st["resources"], "rooms": st["rooms"], "residents": st["residents"],
        "injured": st["injured"], "hand": st["hand"], "hardcore": st["hardcore"],
        "scans_today": today, "scan_cap": DAILY_SCAN_CAP, "blueprint_progress": st["blueprint_progress"],
        "today_event": st["today_event"], "slots": SLOTS, "floor_slots": FLOOR_SLOTS, "dome_floor": DOME_FLOOR,
        # 막: 오늘의 사건이 어느 풀에서 나왔는지와 같은 값이다(DECISIONS 2026-09-23)
        "act": int(st.get("act") or 1), "act_ko": ACT_KO.get(int(st.get("act") or 1), ""),
        "gauges": gauges_of(st),
        # 위협 등급 1~5. **깊이로만 올라간다**(threats.json). 화면은 이것을 숫자로 찍지 않고
        # 「해구 문턱」 같은 구역 이름과 깊이 띠로 보여 준다(D2)
        "grade": grade_of(st),
        "dark_note": st.get("dark_note"),
        "residents_list": st.get("residents_list", []), "effects": role_effects(st),
        # 각인·신뢰 (residents_list[].imprints / .crises / .trust 와 함께 읽는다)
        "imprints_catalog": {i["id"]: {"name": i["name"], "crisis_ko": i.get("crisis_ko"), "visual": i["visual"]["ko"],
                                       "line": i["visual"]["line"], "effect": i["effect"], "cost": i["cost"].get("ko"),
                                       "pending": bool(i.get("_pending_text"))}
                             for i in IMPRINT_LIST},
        "trust": {r["id"]: {"avg": trust_avg(r), "to": r.get("trust", {})} for r in st.get("residents_list", [])},
        # 배치 방어(COMBAT_AND_DEFENSE.md). 배치·조명·전원·습격·공방이 전부 여기 한 덩이로 온다
        "combat": combat_public(st),
        "room_caps": {rid: combat.room_cap(rid) for rid in ROOMS},
        # 스탯 사전. 화면은 숫자를 크게 쓰지 않고 점 네 줄로 그린다(RESIDENT_STATS §5)
        "stats_meta": {"keys": list(STAT_KEYS), "ko": STAT_KO, "use": STAT_USE, "max": 10},
    }


# ─────────────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────────────
class ScanIn(BaseModel):
    uid: str
    barcode: str
    user_category: str | None = None


@app.get("/api/peek")
def peek(barcode: str):
    """스캔 직전: 카테고리를 유저에게 물어야 하는지 알려준다."""
    try:
        code = GEN.normalize(barcode)
    except ValueError as e:
        raise HTTPException(400, str(e))
    parsed = GEN.parse(code)
    cat = GEN.infer_category(parsed)
    return {"barcode": code, "known_category": None if cat == Category.UNKNOWN else cat.value,
            "needs_category": cat == Category.UNKNOWN,
            "categories": [c.value for c in Category if c != Category.UNKNOWN and c != Category.BOOK]}


@app.post("/api/scan")
def scan(inp: ScanIn):
    st = load_state(inp.uid)
    tick_production(st)
    day = day_of(st)
    try:
        code = GEN.normalize(inp.barcode)
    except ValueError as e:
        raise HTTPException(400, str(e))

    with db() as con:
        today = con.execute("SELECT COUNT(*) c FROM scans WHERE uid=? AND day=?", (inp.uid, day)).fetchone()["c"]
        prev = con.execute("SELECT COUNT(*) c FROM scans WHERE uid=? AND barcode=? AND ts>?",
                           (inp.uid, code, time.time() - 7 * 86400)).fetchone()["c"]
    if today >= DAILY_SCAN_CAP:
        raise HTTPException(429, "오늘의 성문 해독 상한에 도달했습니다 (20회).")

    card = GEN.generate(code, hour=datetime.now().hour, user_category=inp.user_category)
    mult = rescan_multiplier(prev)
    gained = {k: int(round(v * mult)) for k, v in card.yields.items() if round(v * mult) >= 1}
    for k, v in gained.items():
        st["resources"][k] = st["resources"].get(k, 0) + v
    if card.category == Category.BOOK:
        eff = role_effects(st)
        st["blueprint_progress"] += eff["blueprint_rate"]
        if eff["book_bonus"]:
            gained["knowledge"] = gained.get("knowledge", 0) + eff["book_bonus"]; st["resources"]["knowledge"] += eff["book_bonus"]

    # 도감
    cx = st["codex"].setdefault(card.category.value, {})
    first_time = card.name not in cx
    cx[card.name] = cx.get(card.name, 0) + 1

    # 손패 (대항용). 정체불명은 대항 태그가 없으므로 손패에 넣지 않음
    card_d = card.to_dict()
    card_d["id"] = f"{code}-{int(time.time()*1000)}"
    usable_tags = [t for t in card.tags if t != "미확인"]
    if mult > 0 and usable_tags and len(st["hand"]) < HAND_LIMIT:
        if True:
            st["hand"].append(card_d)

    # 가문 크라우드소싱
    if inp.user_category and card.family_code not in GEN.families:
        with db() as con:
            con.execute("INSERT INTO family_votes VALUES(?,?,?,?)", (inp.uid, card.family_code, inp.user_category, time.time()))

    with db() as con:
        con.execute("INSERT INTO scans(uid,barcode,category,rarity,mult,ts,day) VALUES(?,?,?,?,?,?,?)",
                    (inp.uid, code, card.category.value, card.rarity.value, mult, time.time(), day))
    save_state(inp.uid, st)
    log(inp.uid, "scan", {"barcode": code, "rarity": card.rarity.value, "category": card.category.value, "mult": mult})
    # 스캔은 버튼이 아니라 세계에 물자가 도착하는 장면이다(WORLD_PRESENTATION §1-3) → 두 AI 중 하나가 한 줄 읊는다
    vseed = f"{inp.uid}|{code}|{today}"
    cat = card.category.value
    _act = int(st.get("act") or 1)
    voice = voice_for(f"scan_{cat}", vseed, act=_act) or voice_for(SCAN_VOICE_FALLBACK.get(cat, ""), vseed, act=_act)
    return {"card": card_d, "gained": gained, "rescan_multiplier": mult, "first_time": first_time,
            "scans_today": today + 1, "scan_cap": DAILY_SCAN_CAP, "resources": st["resources"], "voice": voice}


# ── 이어하기 API ──────────────────────────────────────────────
@app.get("/api/account")
def account(uid: str):
    """이 방주의 복구 코드. 처음 물으면 그 자리에서 발급된다(기존 uid 사용자 포함)."""
    st = load_state(uid)                      # 없는 방주면 여기서 생긴다 = 코드가 빈 방주를 가리키지 않는다
    code = issue_code(uid)
    return {"uid": uid, "code": code, "pretty": code_pretty(code),
            "day": day_of(st), "rooms": len(st.get("rooms") or []),
            "residents": len(st.get("residents_list") or []),
            "ko": "이 여섯 글자가 방주의 열쇠다. 적어 두면 다른 기계에서도 이어서 할 수 있다."}


class RestoreIn(BaseModel):
    code: str


@app.post("/api/account/restore")
def account_restore(inp: RestoreIn):
    """코드로 다른 기기에서 이어하기. 계정도 비밀번호도 없다 — 코드가 곧 방주다."""
    code = normalize_code(inp.code)
    if len(code) != CODE_LEN:
        raise HTTPException(400, f"{CODE_LEN}글자를 적어 주세요")
    uid = uid_for_code(code)
    if not uid:
        raise HTTPException(404, "그런 코드는 없습니다. 적어 둔 것을 다시 봐 주세요")
    st = load_state(uid)
    log(uid, "restore", {"code": code})
    return {"uid": uid, "code": code, "pretty": code_pretty(code), "day": day_of(st),
            "rooms": len(st.get("rooms") or []), "residents": len(st.get("residents_list") or []),
            "ko": f"{day_of(st)}일째 방주로 돌아왔다."}


@app.get("/api/ark")
def get_ark(uid: str, debug_act: int | None = Query(None, description="★ 개발 전용(DEV ONLY): 이 방주의 막(1 심해/2 터널/3 지상)을 바꾼다. 막별 사건 풀 검증용. RELIC_DEV=1 에서만 동작한다.")):
    st = load_state(uid)
    if debug_act is not None:
        if not DEV_MODE:
            raise HTTPException(404, "없는 질의입니다")     # 존재를 알리지 않는다(DECISIONS 2026-09-23)
        if debug_act not in ACTS:
            raise HTTPException(400, f"없는 막입니다: {debug_act}")
        st["act"] = debug_act
        st["today_event"] = None      # 막이 바뀌면 오늘의 사건도 그 막에서 다시 뽑는다
        save_state(uid, st)
    produced = tick_production(st)
    day = day_of(st)
    # 각인의 다음 날 아침: 밀린 연출 문장을 한 번만 내려보내고 큐에서 뺀다
    pending = st.get("morning_pending") or []
    morning = [p for p in pending if p.get("day", 0) <= day]
    if morning:
        st["morning_pending"] = [p for p in pending if p.get("day", 0) > day]
    first_light = not st.get("greeted")            # 이 방주의 첫 화면 — 리더의 첫 말
    if first_light:
        st["greeted"] = True
    save_state(uid, st)
    out = public_state(st, uid)
    out["produced_while_away"] = produced
    out["rooms_catalog"] = ROOMS
    out["morning_lines"] = morning
    # 목소리: 첫 화면(game_start) > 야간 진입(night). 하루 안에서는 같은 줄(D6)
    out["is_night"] = is_night()
    _act = int(st.get("act") or 1)
    out["voice"] = (first_light and voice_for("game_start", f"{uid}|start", act=_act)) \
        or (voice_for("night", f"{uid}|{day}", act=_act) if out["is_night"] else None)
    return out


class BuildIn(BaseModel):
    uid: str
    room_id: str
    slot: int


@app.post("/api/ark/build")
def build(inp: BuildIn):
    st = load_state(inp.uid)
    tick_production(st)
    if inp.room_id not in ROOMS:
        raise HTTPException(400, "없는 방입니다")
    if not (0 <= inp.slot < SLOTS) or any(r["slot"] == inp.slot for r in st["rooms"]):
        raise HTTPException(400, "그 자리는 비어 있지 않습니다")
    disc = role_effects(st)["build_discount"]
    cost = {k: max(1, int(round(v * (1 - disc)))) for k, v in ROOMS[inp.room_id]["cost"].items()}
    lacking = {k: v - st["resources"].get(k, 0) for k, v in cost.items() if st["resources"].get(k, 0) < v}
    if lacking:
        raise HTTPException(400, f"자원이 부족합니다: {lacking}")
    for k, v in cost.items():
        st["resources"][k] -= v
    st["rooms"].append({"id": inp.room_id, "slot": inp.slot, "built": time.time()})
    save_state(inp.uid, st)
    log(inp.uid, "build", {"room": inp.room_id, "slot": inp.slot})
    return public_state(st, inp.uid)


# ─────────────────────────────────────────────────────────────
# 배치 방어 API — 사람을 옮겨 습격을 막는 한 바퀴
#   배치  POST /api/ark/station     사람을 방에 둔다(또는 홀로 되돌린다)
#   조명  POST /api/ark/light       그 방의 불을 끈다/켠다      ← 긴목
#   전원  POST /api/ark/power       전원을 내린다/올린다        ← 문지기
#   귀환  POST /api/ark/recall      밖에 있는 사람을 들인다     ← 손톱 무리
#   제작  POST /api/ark/craft       공방에서 대응 도구를 만든다
#   설치  POST /api/ark/install     설치형 도구를 방에 붙인다
#   습격  GET  /api/raid/today      오늘 오는 것(소리→실루엣→접촉)
#         POST /api/raid/advance    한 단계 넘긴다. 접촉에서 판정이 난다
# ─────────────────────────────────────────────────────────────
class StationIn(BaseModel):
    uid: str
    resident_id: str
    slot: int | None = None       # None = 홀로 되돌린다


@app.post("/api/ark/station")
def station(inp: StationIn):
    st = load_state(inp.uid)
    tick_production(st)
    res = next((r for r in st.get("residents_list", []) if r["id"] == inp.resident_id), None)
    if not res:
        raise HTTPException(400, "없는 사람입니다")
    if inp.resident_id in (st.get("outside") or []):
        raise HTTPException(400, f"{res['name']}{combat.josa(res['name'], ('은', '는'))} 아직 밖에 있습니다")
    if inp.slot is not None:
        room = room_at(st, inp.slot)
        if not room:
            raise HTTPException(400, "그 자리에는 방이 없습니다")
        if room.get("flooded"):
            raise HTTPException(400, "물이 찬 방입니다. 격벽은 다시 열리지 않습니다")
        cap = combat.room_cap(room["id"])
        here = [p for p in stations_map(st).get(int(inp.slot), []) if p["id"] != inp.resident_id]
        if len(here) >= cap:
            raise HTTPException(400, f"{ROOMS[room['id']]['name']}{combat.josa(ROOMS[room['id']]['name'], ('은', '는'))} {cap}명까지입니다")
    before = station_slot(st, inp.resident_id)
    set_station(st, inp.resident_id, inp.slot)
    # 「덮개」의 관문은 **아무도 움직이지 않는 것**이다. 습격이 시작된 뒤의 이동을 센다 —
    # 이 게임의 주된 동사(사람을 옮긴다)가 최악수가 되는 유일한 생물이라 세는 자리가 필요하다.
    raid = st.get("raid")
    if (raid and not raid.get("none") and not raid.get("resolved")
            and raid.get("day") == day_of(st) and before != (int(inp.slot) if inp.slot is not None else None)):
        raid["moves"] = int(raid.get("moves") or 0) + 1
    save_state(inp.uid, st)
    log(inp.uid, "station", {"resident": inp.resident_id, "slot": inp.slot})
    return public_state(st, inp.uid)


class LightIn(BaseModel):
    uid: str
    slot: int
    on: bool


@app.post("/api/ark/light")
def set_light(inp: LightIn):
    """불을 끄면 긴목이 떠나고, 우리도 그 방을 못 본다(§4 — 끄면 우리도 못 본다)."""
    st = load_state(inp.uid)
    if not room_at(st, inp.slot):
        raise HTTPException(400, "그 자리에는 방이 없습니다")
    st.setdefault("lights", {})[str(int(inp.slot))] = bool(inp.on)
    save_state(inp.uid, st)
    log(inp.uid, "light", {"slot": inp.slot, "on": inp.on})
    return public_state(st, inp.uid)


class PowerIn(BaseModel):
    uid: str
    on: bool


@app.post("/api/ark/power")
def set_power(inp: PowerIn):
    """전원을 내리면 돔 전체가 조용해지고 전부 어두워진다. 문지기를 보내는 유일한 방법."""
    st = load_state(inp.uid)
    st["power_on"] = bool(inp.on)
    save_state(inp.uid, st)
    log(inp.uid, "power", {"on": inp.on})
    return public_state(st, inp.uid)


class UidIn(BaseModel):
    uid: str


@app.post("/api/ark/recall")
def recall(inp: UidIn):
    """밖에 있는 사람을 들인다. 에어락은 한 번에 한 사람이지만, 급할 때는 한 번에 센다."""
    st = load_state(inp.uid)
    had = list(st.get("outside") or [])
    st["outside"] = []
    save_state(inp.uid, st)
    log(inp.uid, "recall", {"count": len(had)})
    return {"recalled": had, "state": public_state(st, inp.uid)}


class CraftIn(BaseModel):
    uid: str
    tool_id: str


@app.post("/api/ark/craft")
def craft(inp: CraftIn):
    """공방에서 대응 도구를 만든다. 재료는 전부 유물 — 멸망한 문명의 쓰레기다(§5-3)."""
    st = load_state(inp.uid)
    tick_production(st)
    tool = combat.TOOLS.get(inp.tool_id)
    if not tool:
        raise HTTPException(400, "없는 도구입니다")
    if not any(r["id"] == "workshop" for r in live_rooms(st)):
        raise HTTPException(400, "공방이 없습니다. 먼저 공방을 지으세요")
    cost, hands = craft_cost(st, inp.tool_id)
    lack = {k: v - st["resources"].get(k, 0) for k, v in cost.items() if st["resources"].get(k, 0) < v}
    if lack:
        raise HTTPException(400, f"재료가 부족합니다: {lack}")
    for k, v in cost.items():
        st["resources"][k] -= v
    st.setdefault("tools", {})[inp.tool_id] = int(st.get("tools", {}).get(inp.tool_id, 0)) + 1
    save_state(inp.uid, st)
    log(inp.uid, "craft", {"tool": inp.tool_id, "hands": (hands or {}).get("hand")})
    return {"made": {"id": inp.tool_id, "name": tool["name"], "kind": tool["kind"]},
            "hands": hands, "cost": cost,
            "state": public_state(st, inp.uid)}


class InstallIn(BaseModel):
    uid: str
    tool_id: str
    slot: int


@app.post("/api/ark/install")
def install(inp: InstallIn):
    """설치·내구·영구 도구를 방에 붙인다. 소모품은 접촉 순간에 쓰는 것이라 설치하지 않는다."""
    st = load_state(inp.uid)
    tool = combat.TOOLS.get(inp.tool_id)
    if not tool:
        raise HTTPException(400, "없는 도구입니다")
    if tool["kind"] not in combat.INSTALLED_KINDS:
        raise HTTPException(400, f"{tool['name']}{combat.josa(tool['name'], ('은', '는'))} 설치하는 물건이 아닙니다")
    if int(st.get("tools", {}).get(inp.tool_id, 0)) <= 0:
        raise HTTPException(400, f"{tool['name']}{combat.josa(tool['name'])} 없습니다")
    room = room_at(st, inp.slot)
    if not room or room.get("flooded"):
        raise HTTPException(400, "그 자리에는 붙일 방이 없습니다")
    rows = st.setdefault("room_tools", {}).setdefault(str(int(inp.slot)), [])
    if any(t.get("id") == inp.tool_id for t in rows):
        raise HTTPException(400, f"{ROOMS[room['id']]['name']}에 이미 붙어 있습니다")
    st["tools"][inp.tool_id] -= 1
    rows.append({"id": inp.tool_id, "uses": tool.get("uses")})
    save_state(inp.uid, st)
    log(inp.uid, "install", {"tool": inp.tool_id, "slot": inp.slot})
    return public_state(st, inp.uid)


class ActIn(BaseModel):
    uid: str
    action: str


@app.post("/api/ark/act")
def gate_act(inp: ActIn):
    """관문 행동 하나. **대가를 그 자리에서 낸다**(defense.json gates.gate_cost).

    토글(불·전원·귀환)로 표현되지 않는 일곱 — 반대쪽에 불 켜기 / 물 흐리기 / 길 비키기 /
    먹이 내주기 / 돌려주기 / 올려 보내기 — 이 여기로 온다. 「가만히 서기」는 행동이 아니라
    **하지 않는 것**이라 버튼이 없다(세는 것은 /api/ark/station 쪽이다).
    되돌릴 수 없다. 대가 없는 관문은 그냥 누르는 버튼이 되어 선택이 사라진다(B3).
    """
    st = load_state(inp.uid)
    tick_production(st)
    spec = combat.GATE_ACTIONS.get(inp.action)
    if not spec:
        raise HTTPException(400, "없는 대응입니다")
    raid = st.get("raid")
    if not raid or raid.get("none") or raid.get("day") != day_of(st) or raid.get("resolved"):
        raise HTTPException(400, "지금 맞설 것이 없습니다")
    cre = combat.CREATURES.get(raid.get("creature")) or {}
    if cre.get("gate") != spec["gate"]:
        raise HTTPException(400, f"{cre.get('name', '그것')}에게는 통하지 않습니다")
    pub = gate_action_public(st, raid, cre)
    if pub["done"]:
        raise HTTPException(400, "이미 했습니다")
    if pub["blocked"]:
        raise HTTPException(400, " · ".join(pub["blocked"]))
    if pub["lacking"]:
        raise HTTPException(400, "모자랍니다: " +
                            " · ".join(f"{RES_KO_SRV.get(k, k)} {v}" for k, v in pub["lacking"].items()))

    paid: dict = {}
    for k, v in pub["cost"].items():
        st["resources"][k] = max(0, int(st["resources"].get(k, 0)) - int(v))
        paid[k] = int(v)
    lost = []
    if spec.get("strips_tools"):                       # 걷어 낸 것은 돌아오지 않는다
        rows = (st.get("room_tools") or {}).pop(str(int(raid["target_slot"])), []) or []
        lost = [combat.TOOLS[r["id"]]["name"] for r in rows if r.get("id") in combat.TOOLS]
    gone_card = None
    if spec.get("spends_relic"):                       # 수집을 깎는 유일한 대가라 가장 아프다
        card = (st.get("hand") or [])[0]
        st["hand"] = st["hand"][1:]
        gone_card = card.get("name")
    if spec.get("next_severity"):                      # 금기를 어긴 값은 **다음**에 치른다
        st["severity_debt"] = int(st.get("severity_debt", 0)) + int(spec["next_severity"])

    raid.setdefault("acts", []).append(spec["id"])
    save_state(inp.uid, st)
    log(inp.uid, "gate_act", {"action": spec["id"], "raid": raid["id"], "paid": paid,
                              "lost_tools": lost, "lost_card": gone_card})
    bits = [spec["ko"] + "."]
    if paid:
        bits.append("치른 것 — " + " · ".join(f"{RES_KO_SRV.get(k, k)} {v}" for k, v in paid.items()))
    if lost:
        bits.append("걷어 낸 것 — " + " · ".join(lost) + " (영영)")
    if gone_card:
        bits.append(f"「{gone_card}」을(를) 내려보냈다. 도감의 그 칸은 비어 있는 채로 남는다")
    if spec.get("next_severity"):
        bits.append("위로 빛을 비췄다. 다음에 오는 것이 한 단계 세진다")
    return {"ok": True, "action": spec["id"], "paid": paid, "lost_tools": lost,
            "lost_card": gone_card, "ko": " ".join(bits),
            "raid": raid_public(st, raid), "state": public_state(st, inp.uid)}


def resolve_raid(st: dict, uid: str, raid: dict, consumables: list) -> dict:
    """접촉. **방어 판정 공식은 engine/combat.evaluate 하나뿐이고 난수가 없다**(D6).
    같은 배치 = 같은 결과, 다른 배치 = 다른 결과. 이것이 이 시스템의 합격 기준이다."""
    cre = combat.CREATURES[raid["creature"]]
    day = raid["day"]
    owned = st.setdefault("tools", {})
    use = [t for t in (consumables or []) if combat.TOOLS.get(t, {}).get("kind") in combat.CARRY_KINDS
           and int(owned.get(t, 0)) > 0]
    # ① 소모품의 '쓰는 즉시' 효과를 **판정 전에** 적용한다. 귀환 신호기는 부르는 물건이지 점수가 아니다
    for t in use:
        if combat.TOOLS[t].get("recalls") and st.get("outside"):
            st["outside"] = []
    ctx = raid_ctx(st, raid, use)
    ev = combat.evaluate(cre, ctx)
    result = ev["result"]
    for t in use:                                   # ② 쓴 것은 없어진다
        owned[t] = max(0, int(owned.get(t, 0)) - 1)
    # ③ 내구 도구(긴 장대 그물)는 이번 접촉에 기여했으면 한 번 닳는다
    rows = (st.get("room_tools") or {}).get(str(raid["target_slot"])) or []
    worn = []
    for row in list(rows):
        spec = combat.TOOLS.get(row.get("id")) or {}
        if spec.get("kind") == "durable" and combat.tool_power(row["id"], cre["id"]) > 0:
            row["uses"] = int(row.get("uses") or 1) - 1
            if row["uses"] <= 0:
                rows.remove(row); worn.append(spec["name"])

    room = room_at(st, raid["target_slot"])
    room_name = ctx["room_name"]
    line = combat.outcome_line(cre, result, room_name)
    gained = combat.reward_for(result, raid["severity"], int(raid.get("grade") or 1))
    for k, v in gained.items():
        st["resources"][k] = max(0, st["resources"].get(k, 0) + v)

    flags, hurt, lost_room = [], None, None
    if result == combat.HELD:
        flags = list(cre.get("hold_flags") or [])
    elif result == combat.SCARRED and room:
        room["cracked"] = True
        if any(combat.TOOLS[t].get("heals_crack") for t in use):   # 봉합 패치로 그 자리에서 꿰맨다
            room["cracked"] = False
            line += " 봉합 패치가 그 자리를 덮었다."
    elif result == combat.BREACHED and room:
        # 격벽이 닫힌다. 그 방은 **사라지지 않고 물이 찬 채로 영구히 남는다**(§3-6 흔적)
        room["flooded"] = True
        room["cracked"] = False
        room["flooded_day"] = day
        room["flooded_by"] = cre["id"]
        lost_room = ROOMS.get(room["id"], {}).get("name", room["id"])
        for p in list(stations_map(st).get(int(raid["target_slot"]), [])):
            set_station(st, p["id"], None)          # 살아 나온 사람은 홀로 모인다
        (st.get("lights") or {}).pop(str(raid["target_slot"]), None)
        (st.get("room_tools") or {}).pop(str(raid["target_slot"]), None)   # 붙어 있던 것도 함께 잠긴다
        flags = list(cre.get("breach_flags") or [])
        pool = [p for p in st.get("residents_list", []) if not p.get("injured")]
        if pool:
            pool.sort(key=lambda p: 0 if p["role"] == "kid" else 1)
            pool[0]["injured"] = True; hurt = pool[0]["name"]
            st["injured"] = sum(1 for x in st.get("residents_list", []) if x.get("injured"))

    # ④ 각인: 그 방에서 **겪은 사람**만 변한다(GROWTH_AND_MYTH §1). 배치가 곧 참여자다
    here = [p for p in stations_map(st).get(int(raid["target_slot"]), [])][:MAX_PARTICIPANTS] \
        or hall_of(st)[:1]
    new_imprints = grant_imprints(st, None, flags, here) if flags else []

    hint = None
    if cre.get("foretells"):
        # 문어는 위협이 아니라 **다음을 미리 알린다**(§4). 말은 하지 않는다 — 알리는 것은 행동이다
        nxt = combat.pick_creature(uid, day + 1, int(raid.get("grade") or grade_of(st)))
        hint = {"day": day + 1, "creature": nxt["id"] if nxt else None,
                "name": nxt["name"] if nxt else None,
                "how": nxt["how"] if nxt else None,
                "ko": (f"문어가 창 쪽에 붙어 떨어지지 않는다. 내일 {nxt['name']}{combat.josa(nxt['name'])} 온다."
                       if nxt else "문어가 창 쪽을 보다가 자리로 돌아간다. 내일은 조용하다.")}
        st["next_raid_hint"] = hint
    elif st.get("next_raid_hint", {}) and (st.get("next_raid_hint") or {}).get("day") == day:
        st["next_raid_hint"] = None                 # 예고한 날이 지나갔다

    bump_trust(st, TRUST_ON_COUNTER if result in (combat.HELD, combat.PASSED) else TRUST_ON_FAIL)
    raid.update({"stage": "done", "resolved": True, "result": result, "line": line,
                 "score": ev["score"], "need": ev["need"], "margin": ev["margin"],
                 "gate_ok": ev["gate"]["ok"], "used": use, "ended": time.time(),
                 "shielded": ev.get("shielded")})
    archive_raid(st, raid)
    log(uid, "raid_resolved", {"raid": raid["id"], "creature": cre["id"], "result": result,
                               "slot": raid["target_slot"], "score": ev["score"], "need": ev["need"],
                               "gate": ev["gate"]["ok"], "used": use, "grade": raid.get("grade"),
                               "severity": raid.get("severity"), "acts": list(raid.get("acts") or []),
                               "moves": raid.get("moves"), "shielded": ev.get("shielded")})
    return {"result": result, "result_ko": combat.RESULT_KO[result], "line": line,
            "score": ev["score"], "need": ev["need"], "margin": ev["margin"],
            "gate": ev["gate"], "parts": ev["parts"], "used": use, "worn_out": worn,
            "shielded": ev.get("shielded"), "grade": int(raid.get("grade") or 1),
            "gained": gained, "injured": hurt, "lost_room": lost_room,
            "new_imprints": new_imprints, "next_raid_hint": hint,
            "voice": voice_for("event_counter" if result in (combat.HELD, combat.PASSED) else "event_fail",
                               f"{uid}|{day}|raid", act=int(st.get("act") or 1))}


@app.get("/api/raid/today")
def raid_today(uid: str,
               debug_raid: str | None = Query(None, description="★ 개발 전용(DEV ONLY): 오늘의 습격을 이 생물로 강제한다(swarm/longneck/warden/claws/mirror_eye/straight_one/lid/needle/big_maw/follower/upper_child/octopus/shade/far_cry). RELIC_DEV=1 에서만."),
               debug_reset: int | None = Query(None, description="★ 개발 전용(DEV ONLY): 오늘의 습격을 처음 단계로 되돌린다. 같은 습격을 다른 배치로 다시 돌려 보기 위한 훅. RELIC_DEV=1 에서만."),
               debug_grade: int | None = Query(None, description="★ 개발 전용(DEV ONLY): 위협 등급 1~5 를 강제한다. 깊이를 파지 않고 need 곡선을 확인하는 훅. RELIC_DEV=1 에서만.")):
    st = load_state(uid)
    tick_production(st)
    if (debug_raid or debug_reset or debug_grade) and not DEV_MODE:
        raise HTTPException(404, "없는 질의입니다")       # 존재를 알리지 않는다(DECISIONS 2026-09-23)
    if debug_raid and debug_raid not in combat.CREATURES:
        raise HTTPException(400, f"없는 생물입니다: {debug_raid}")
    if debug_grade is not None and not (1 <= debug_grade <= 5):
        raise HTTPException(400, f"없는 등급입니다: {debug_grade}")
    ensure_raid(st, uid, force=debug_raid, reset=bool(debug_reset), grade_force=debug_grade)
    save_state(uid, st)
    out = combat_public(st)
    return {"raid": out["raid"], "day": day_of(st), "outside": out["outside"],
            "next_raid_hint": out["next_raid_hint"], "state": public_state(st, uid)}


class RaidStepIn(BaseModel):
    uid: str
    use: list[str] | None = None          # 접촉 순간에 쓸 소모품


@app.post("/api/raid/advance")
def raid_advance(inp: RaidStepIn):
    """한 단계 넘긴다. **시계는 없다**(§6-2·§9 준비 단계 권장안) — 플레이어가 누를 때만 다가온다.
    실루엣 단계에서 배치를 얼마든지 바꿔도 되고, 바꾸는 동안 아무 일도 일어나지 않는다."""
    st = load_state(inp.uid)
    raid = st.get("raid")
    if not raid or raid.get("none") or raid.get("day") != day_of(st):
        raise HTTPException(400, "오늘 오는 것이 없습니다")
    if raid.get("resolved"):
        raise HTTPException(400, "오늘의 습격은 이미 지나갔습니다")
    if raid["stage"] == "sound":
        raid["stage"] = "silhouette"
        save_state(inp.uid, st)
        return {"stage": "silhouette", "raid": raid_public(st, raid), "state": public_state(st, inp.uid)}
    out = resolve_raid(st, inp.uid, raid, inp.use or [])
    save_state(inp.uid, st)
    out["raid"] = raid_public(st, raid)
    out["state"] = public_state(st, inp.uid)
    return out


ONCE_PREFIXES = ("tribe_",)      # 한 방주에서 한 번만 나오는 카드 (부족 첫 접촉)


def mark_seen(st: dict, event_id: str):
    seen = st.setdefault("seen_events", [])
    if event_id not in seen:
        seen.append(event_id)
    del seen[:-200]


def seen_once(st: dict) -> set:
    """이미 소모된 1회성 카드 id 집합."""
    return {e for e in st.get("seen_events", []) if e.startswith(ONCE_PREFIXES)}


@app.get("/api/event/today")
def event_today(uid: str, debug_force_event: str | None = Query(None, description="★ 개발 전용(DEV ONLY): 오늘의 사건을 이 id로 덮어쓰고 미해결 상태로 되돌린다. 각인·신뢰 테스트용. RELIC_DEV=1 환경변수에서만 동작한다.")):
    st = load_state(uid)
    tick_production(st)
    day = day_of(st)
    te = st["today_event"]
    if debug_force_event and not DEV_MODE:
        # 배포 환경에는 이 훅이 없는 것과 같다. 존재를 알리지 않기 위해 404.
        raise HTTPException(404, "없는 질의입니다")
    if debug_force_event:
        # ★ 개발 전용 — 사건은 하루 1회라 테스트가 불가능하므로 강제 주입한다. 정식 플레이 경로 아님.
        if debug_force_event not in EVENTS:
            raise HTTPException(400, f"없는 사건입니다: {debug_force_event}")
        te = {"day": day, "event_id": debug_force_event, "resolved": False, "countered": None,
              "shown_at": time.time(), "debug": True}
        st["today_event"] = te
        mark_seen(st, debug_force_event)
        save_state(uid, st)
        log(uid, "event_shown", {"event": debug_force_event, "day": day, "debug": True})
    elif not te or te["day"] != day:
        # 부족 첫 접촉은 1회 소모: 이미 나온 tribe_* 카드는 후보에서 뺀다(첫 대면의 연출은 한 번뿐이다)
        ev = pick_event(ark_state_obj(st), rng=random.Random(f"{uid}|{day}"), exclude=seen_once(st))
        te = {"day": day, "event_id": ev["id"], "resolved": False, "countered": None, "shown_at": time.time()}
        st["today_event"] = te
        mark_seen(st, ev["id"])
        save_state(uid, st)
        log(uid, "event_shown", {"event": ev["id"], "day": day})
    ev = EVENTS[te["event_id"]]
    room_ids = [r["id"] for r in st["rooms"] if not r.get("flooded")]   # 잃은 방은 사건도 못 막는다
    matching = [c["id"] for c in st["hand"] if set(c.get("tags", [])) & set(ev["counter_tags"])]
    return {"event": ev, "state": te, "matching_card_ids": matching,
            "act": int(st.get("act") or 1), "event_acts": acts_of(ev),
            "room_backup": bool(ev.get("counter_room") and ev["counter_room"] in room_ids)}


class ResolveIn(BaseModel):
    uid: str
    card_id: str | None = None


@app.post("/api/event/resolve")
def event_resolve(inp: ResolveIn):
    st = load_state(inp.uid)
    te = st["today_event"]
    if not te or te["resolved"]:
        raise HTTPException(400, "처리할 사건이 없습니다")
    ev = EVENTS[te["event_id"]]
    room_ids = [r["id"] for r in st["rooms"] if not r.get("flooded")]   # 잃은 방은 사건도 못 막는다
    countered = False
    how = "none"
    used = None
    if inp.card_id:
        used = next((c for c in st["hand"] if c["id"] == inp.card_id), None)
        if used and set(used.get("tags", [])) & set(ev["counter_tags"]):
            countered, how = True, "card"
        if used:
            st["hand"] = [c for c in st["hand"] if c["id"] != inp.card_id]
    if not countered and ev.get("counter_room") and ev["counter_room"] in room_ids:
        if random.Random(f"{inp.uid}|{te['day']}|room").random() < 0.5:
            countered, how = True, "room"
    eff = role_effects(st); hero = None
    if not countered:
        # 역할 자동 대항: 사건 태그와 맞는 주민이 스스로 막는다
        chance = max([eff["auto_counter"].get(t, 0) for t in ev["counter_tags"]] + [0])
        if chance and random.Random(f"{inp.uid}|{te['day']}|role").random() < chance:
            countered, how = True, "role"
            hero = next((r for r in st.get("residents_list", []) if not r.get("injured") and set(ROLES[r["role"]]["counter_tags"]) & set(ev["counter_tags"])), None)
    ark = ark_state_obj(st)
    applied = resolve(ev, ark, countered)
    st["resources"] = ark.resources
    st["recent_events"] = ark.recent_events
    rng = random.Random(f"{inp.uid}|{te['day']}|who")
    roster = list(st.get("residents_list", []))     # 이 사건을 겪은 명단 (뒤에 합류하는 표류자는 제외)
    pre_injured = {r["id"] for r in roster if r.get("injured")}                         # 그 밤에 이미 누워 있던 사람
    if applied.get("injured"):
        healthy = [r for r in st.get("residents_list", []) if not r.get("injured")]
        kids_first = sorted(healthy, key=lambda r: 0 if r["role"] == "kid" else 1)   # 아이는 보호받지 못하면 먼저 다친다
        for r in kids_first[: int(applied["injured"])]:
            r["injured"] = True
    if applied.get("resident"):
        taken = {r["name"] for r in st.get("residents_list", [])}
        have = {r["role"] for r in st.get("residents_list", [])}
        pool = [r for r in ROLE_IDS if r not in have] or ROLE_IDS
        newcomer = make_resident(rng.choice(pool), rng, taken, inp.uid)
        ensure_stats(inp.uid, newcomer)
        st.setdefault("residents_list", []).append(newcomer); applied["newcomer"] = newcomer
    st["residents"] = len(st.get("residents_list", [])) or ark.residents
    st["injured"] = sum(1 for x in st.get("residents_list", []) if x.get("injured"))
    if hero:
        applied["hero"] = hero["name"]

    # ── 계단식 성장: 처음 겪는 종류의 위기를 **나가서** 넘긴 사람만 변한다 ──
    ev_flags = [f for f in [applied.get("flag")] if f] + list(applied.get("flags") or [])
    if ev["id"].startswith(DEEP_EVENT_PREFIX):
        # 심해 카드가 쓰는 육상 flag 를 심해 것으로 옮겨 읽는다(물속엔 발자국이 없다 — DECISIONS 2026-09-22).
        # 데이터 파일(events_deep.json, 시나리오 소유)은 손대지 않는다.
        ev_flags = [DEEP_FLAG_ALIAS.get(f, f) for f in ev_flags]
    if applied.get("spot_clue"):
        ev_flags.append("healing_spot_found")     # 힐링 스팟 단서를 얻은 날 → 「물의 기억」
    seed = f"{inp.uid}|{te['day']}"
    participants = event_participants(roster, ev, seed, how, used, hero, pre_injured, station_room_ids(st))
    new_imprints = grant_imprints(st, ev, ev_flags, participants)
    if applied.get("injured"):
        # 상실: 곁의 누군가가 다치는 것을 처음 본 사람에게 「빈 자리」 — 목격자는 한 명
        witnesses = [r for r in participants if not r.get("injured")] \
            or [r for r in roster if not r.get("injured")]
        if witnesses:
            new_imprints += grant_imprints(st, None, ["ally_crisis"], witnesses[:1])
    # ── 신뢰: 함께 넘기면 오르고, 실패하면 급락한다 ──
    bump_trust(st, TRUST_ON_COUNTER if countered else TRUST_ON_FAIL)

    te.update({"resolved": True, "countered": countered, "how": how})
    save_state(inp.uid, st)
    log(inp.uid, "event_resolved", {"event": ev["id"], "countered": countered, "how": how, "card": bool(inp.card_id),
                                    "imprints": [n["imprint"]["id"] for n in new_imprints]})
    return {"countered": countered, "how": how, "applied": applied, "used_card": used, "hero": hero,
            "new_imprints": new_imprints, "trust_delta": TRUST_ON_COUNTER if countered else TRUST_ON_FAIL,
            "participants": [{"id": r["id"], "name": r["name"], "role_ko": r.get("evolved_ko") or r.get("role_ko")}
                             for r in participants],
            "voice": voice_for("event_counter" if countered else "event_fail", f"{seed}|{ev['id']}",
                               act=int(st.get("act") or 1)),
            # 스팟 단서를 얻은 날에는 물에 비친 문장이 한 줄 더 온다 (WORLD_PRESENTATION §2-8)
            "spot_voice": (voice_for("spot_water_reflection", f"{seed}|spot", act=int(st.get("act") or 1))
                           or voice_for("spot_found", f"{seed}|spot", act=int(st.get("act") or 1)))
                          if applied.get("spot_clue") else None,
            "state": public_state(st, inp.uid)}


@app.get("/api/rumors")
def rumors(uid: str):
    """소문 = 힐링 스팟 단서. 현실의 스캔 카테고리 누적이 지도를 연다(WORLD_PRESENTATION §1-3).
    도서를 읽던 사람에게는 강의 등불이, 음료·의약을 모으던 사람에게는 물에 잠긴 전철이 먼저 들린다."""
    st = load_state(uid)
    counts = scan_counts(uid)
    lines = rumor_lines()
    seen = st.setdefault("rumors_seen", [])
    out, changed = [], False
    for spot in SPOTS:
        sid = spot.get("id")
        rule = spot_gate(sid, spot)
        if not rule:
            continue
        have = sum(counts.get(c, 0) for c in rule["categories"])
        need = rule["need"]
        unlocked = have >= need
        is_new = False
        if unlocked and sid not in seen:
            seen.append(sid); changed = is_new = True
            log(uid, "rumor_unlocked", {"spot": sid, "have": have, "categories": rule["categories"]})
        pick = None
        if unlocked:
            # data/rumors.json 이 있으면 그 문장이 우선. 줄마다 자기 해금 조건(unlock)이 붙어 있으면
            # 조건을 이미 채운 줄을 먼저 쓴다(해금 여부 자체는 위의 RUMOR_RULES 가 정한다).
            pool = lines.get(sid) or []
            ready = [ln for ln in pool if not ln.get("category") or counts.get(ln["category"], 0) >= ln.get("count", 0)]
            # S3 동기화 점검(rumor_rule_audit)에서 나온 결함: 서버 표가 파일의 가장 싼 줄보다 먼저 열리는
            # 스팟이 4곳 있다. 예전에는 조건을 못 채운 줄로 되돌아가 **아직 얻지 않은 지식이 적힌 소문**을
            # 읽혔다. 이제는 조건 없는 spots.json 의 clue_text 로 물러난다(수치는 시나리오 확인 대기).
            pick = random.Random(f"{uid}|{sid}|rumor").choice(ready) if ready else None
        x, y = spot_pos_of(sid, spot) or (0, 0)
        out.append({
            "spot_id": sid, "name": spot.get("name"),
            "clue_text": (pick or {}).get("text") or (spot.get("clue_text") if unlocked else None),
            "who": (pick or {}).get("who"),
            "unlocked": unlocked, "is_new": is_new,
            "progress": {"have": min(have, need), "need": need},
            "categories": rule["categories"],
            "categories_ko": "·".join(CAT_KO.get(c, c) for c in rule["categories"]),
            "pos": {"x": x, "y": y},
        })
    if changed:
        save_state(uid, st)
    return out


@app.get("/api/spots")
def spots(uid: str | None = None):
    """힐링 스팟 정본. 발견문·좌표·자원·위험·무리 힌트는 **여기가 유일한 출처**다(02_DEV D7).
    `data/spots.json` 은 /static 에 없어 브라우저가 못 읽으므로 발견 텍스트가 world3d.js 상수로
    박혀 있었다 — 그 상수를 대신한다. `spots_deep.json` 이 생기면 자동으로 함께 나온다.

    /api/rumors 와의 역할 분담(필드가 겹쳐서 정한다)
      · **/api/spots = 스팟 그 자체**(name·discovery_text·resource·danger_note·tribe_hint·pos·gate). 정적.
      · **/api/rumors = 소문 한 줄의 상태**(clue_text 문장 고르기·is_new·who). 동적.
      · 겹치는 `unlocked`·`progress`·`pos` 는 두 API 가 같은 함수(spot_gate·SPOT_POS)를 부르므로 값이 갈라지지 않는다.
      · `clue_text` 는 /api/spots 가 내지 않는다 — 같은 문장을 두 곳에서 고르면 시드가 갈라진다(D6).
    uid 를 주면 그 방주 기준 해금 여부·진행도가 함께 온다. 없으면 잠긴 상태로 본다."""
    counts = scan_counts(uid) if uid else {}
    seen = set(load_state(uid).get("rumors_seen") or []) if uid else set()
    out = []
    for spot in SPOTS:
        sid = spot["id"]
        gate = spot_gate(sid, spot)
        have = sum(counts.get(c, 0) for c in gate["categories"]) if gate else 0
        unlocked = bool(uid) and bool(gate) and have >= gate["need"]
        pos = spot_pos_of(sid, spot)
        x, y = pos or (0, 0)
        out.append({
            "id": sid, "name": spot.get("name"),
            "discovery_text": spot.get("discovery_text"),
            "resource": spot.get("resource"), "danger_note": spot.get("danger_note"),
            "tribe_hint": spot.get("tribe_hint"),
            "pos": {"x": x, "y": y}, "has_pos": pos is not None,
            "act": 1 if spot.get("_src") == "spots_deep.json" else 3,
            "unlocked": unlocked, "rumor_seen": sid in seen,
            "progress": ({"have": min(have, gate["need"]), "need": gate["need"]} if gate else None),
            "gate": ({"categories": gate["categories"],
                      "categories_ko": "·".join(CAT_KO.get(c, c) for c in gate["categories"]),
                      "need": gate["need"], "source": gate["source"]} if gate else None),
            "source_file": spot.get("_src"),
        })
    return out


@app.get("/api/codex")
def codex(uid: str):
    st = load_state(uid)
    out = []
    for cat, pool in TEMPLATES.items():
        if cat.startswith("_"):
            continue
        found = st["codex"].get(cat, {})
        # 템플릿 이름은 {adj}가 치환되므로 접미 부분으로 매칭
        stems = [t["name"].replace("{adj} ", "") for t in pool]
        got = [s for s in stems if any(n.endswith(s) for n in found)]
        out.append({"category": cat, "total": len(stems), "found": len(got), "names": got})
    return out


# 에이전트·PM이 만든 테스트 방주. 지표(H1~H5)에서 뺀다. ?all=1 로 전부 볼 수 있다.
TEST_UIDS = {"smoke", "uakdrgvja", "scn_s2_check", "log_demo"}
TEST_UID_PREFIXES = ("pmcheck", "scn_", "s2b_", "imp_", "test", "dev_")


def is_test_uid(uid: str) -> bool:
    return uid in TEST_UIDS or uid.startswith(TEST_UID_PREFIXES)


@app.get("/api/stats")
def stats(all: bool = False):
    """테스트 지표 (H1~H5 원자료). 기본은 에이전트 테스트 uid 제외."""
    with db() as con:
        rows = con.execute("SELECT uid, kind, COUNT(*) c FROM logs GROUP BY uid, kind").fetchall()
        per_user = con.execute("SELECT uid, COUNT(*) scans, COUNT(DISTINCT category) cats, COUNT(DISTINCT day) days FROM scans GROUP BY uid").fetchall()
    keep = (lambda u: True) if all else (lambda u: not is_test_uid(u or ""))
    events: dict = {}
    for r in rows:
        if keep(r["uid"]):
            events[r["kind"]] = events.get(r["kind"], 0) + r["c"]
    users = [dict(r) for r in per_user if keep(r["uid"])]
    return {"events": events, "users": users,
            "excluded_uids": 0 if all else len({r["uid"] for r in per_user if not keep(r["uid"])})}


# ─────────────────────────────────────────────────────────────
# 정적 파일
# ─────────────────────────────────────────────────────────────
@app.middleware("http")
async def no_cache(request, call_next):
    """Phase 0: 정적 파일 캐시 금지 (테스터 브라우저가 옛 JS/CSS/타일을 붙잡는 문제 방지)."""
    resp = await call_next(request)
    if request.url.path in ("/", "/base", "/journey") or request.url.path.startswith("/static"):
        resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


@app.get("/")
def index():
    """index.html의 정적 링크에 파일 수정시각을 버전으로 붙여 준다."""
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    for name in ("style.css", "rooms.js", "app.js", "life.js"):
        p = ROOT / "static" / name
        if p.exists():
            html = html.replace(f"/static/{name}\"", f"/static/{name}?v={int(p.stat().st_mtime)}\"")
    from fastapi.responses import HTMLResponse
    return HTMLResponse(html)


@app.get("/base")
def base_screen():
    """1막 거점 화면 — 정면 평면 단면(DECISIONS 2026-09-23). index 와 같은 방식으로 정적 링크에 버전을 붙인다."""
    from fastapi.responses import HTMLResponse
    html = (ROOT / "static" / "base.html").read_text(encoding="utf-8")
    for name in ("base.css", "base.js"):
        p = ROOT / "static" / name
        if p.exists():
            html = html.replace(f"/static/{name}\"", f"/static/{name}?v={int(p.stat().st_mtime)}\"")
    return HTMLResponse(html)


@app.get("/journey")
def journey_page():
    """사용자 여정 14단계 화면 시안(기획안 부록). 정적 페이지이고 게임 상태를 읽지 않는다."""
    from fastapi.responses import HTMLResponse
    html = (ROOT / "static" / "journey.html").read_text(encoding="utf-8")
    p = ROOT / "static" / "journey.css"
    if p.exists():
        html = html.replace('/static/journey.css"', f'/static/journey.css?v={int(p.stat().st_mtime)}"')
    return HTMLResponse(html)


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


def lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


if __name__ == "__main__":
    import uvicorn
    init_db()
    https = "--https" in sys.argv
    port = 8444 if https else 8002
    for a in sys.argv:
        if a.startswith("--port="):
            port = int(a.split("=")[1])
    kw = {}
    if https:
        cert, key = ROOT / "certs" / "cert.pem", ROOT / "certs" / "key.pem"
        if not cert.exists():
            print("인증서가 없습니다. 먼저: python tools/make_cert.py")
            sys.exit(1)
        kw = {"ssl_certfile": str(cert), "ssl_keyfile": str(key)}
    scheme = "https" if https else "http"
    print(f"\n  잔해 방주 Phase 0\n  데스크톱: {scheme}://localhost:{port}\n  휴대폰:   {scheme}://{lan_ip()}:{port}\n")
    uvicorn.run(app, host="0.0.0.0", port=port, **kw)
