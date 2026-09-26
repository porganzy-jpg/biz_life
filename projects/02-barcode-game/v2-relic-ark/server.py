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

DB = ROOT / "relic_ark.db"
# ★ 개발 전용 훅 스위치. RELIC_DEV=1 일 때만 ?debug_* 질의가 살아난다(02_DEV §4-4 "배포 전 제거 목록").
#   배포 빌드는 환경변수를 주지 않으므로 훅이 존재하지 않는 것과 같다.
DEV_MODE = os.environ.get("RELIC_DEV") == "1"
ROOMS = json.loads((ROOT / "data" / "rooms.json").read_text(encoding="utf-8"))
ROOMS.pop("_comment", None)
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
        """)


def log(uid: str, kind: str, payload: dict | None = None):
    with db() as con:
        con.execute("INSERT INTO logs(uid,kind,payload,ts) VALUES(?,?,?,?)",
                    (uid, kind, json.dumps(payload or {}, ensure_ascii=False), time.time()))


def make_resident(role: str, rng: random.Random, taken: set) -> dict:
    name = next((n for n in rng.sample(NAMES, len(NAMES)) if n not in taken), f"주민{len(taken) + 1}")
    taken.add(name)
    trait = rng.choice(list(TRAITS.keys())) if rng.random() < 0.7 else None
    r = ROLES[role]
    return {"id": f"{role}-{int(rng.random() * 1e6)}", "name": name, "role": role, "role_ko": r["ko"], "ability": r["ability"],
            "trait": trait, "injured": False, "joined": time.time(),
            "imprints": [],     # 받은 각인 id (최대 3)
            "crises": [],       # 겪어 본 위기 종류. 여기 있는 종류는 다시 겪어도 사람을 바꾸지 않는다
            "trust": {}}        # 다른 주민 id -> 0~100. 시작은 0 (사람 간 신뢰의 역전)


def new_state() -> dict:
    now = time.time()
    rng = random.Random(now)
    taken: set = set()
    residents = [make_resident(role, rng, taken) for role in ("cook", "engineer", "scout")]   # 시작 3인: 먹이고, 고치고, 살핀다
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
    }


def load_state(uid: str) -> dict:
    with db() as con:
        row = con.execute("SELECT state FROM arks WHERE uid=?", (uid,)).fetchone()
    if row:
        st = json.loads(row["state"])
        if "residents_list" not in st:            # 구버전 방주 마이그레이션
            rng = random.Random(st.get("created", 0)); taken: set = set()
            st["residents_list"] = [make_resident(role, rng, taken) for role in ("cook", "engineer", "scout")][: max(1, st.get("residents", 3))]
            for r in st["residents_list"][: st.get("injured", 0)]:
                r["injured"] = True
            save_state(uid, st)
        changed = migrate_residents(st)           # 각인·신뢰 필드가 없는 구버전 주민 보강
        changed = migrate_state(st) or changed    # 소문·사건 이력 필드 보강
        if changed:
            save_state(uid, st)
        return st
    st = new_state()
    save_state(uid, st)
    log(uid, "ark_created")
    return st


def save_state(uid: str, st: dict):
    with db() as con:
        con.execute("INSERT OR REPLACE INTO arks(uid,state) VALUES(?,?)",
                    (uid, json.dumps(st, ensure_ascii=False)))


def migrate_residents(st: dict) -> bool:
    """구버전 방주의 주민에 각인·신뢰 필드를 채운다. 변경이 있으면 True."""
    changed = False
    res = st.get("residents_list", [])
    ids = {r.get("id") for r in res}
    for i, r in enumerate(res):
        if not r.get("id"):
            r["id"] = f"{r.get('role', 'res')}-{i}"; ids.add(r["id"]); changed = True
        for key, default in (("imprints", []), ("crises", []), ("trust", {})):
            if not isinstance(r.get(key), type(default)):
                r[key] = type(default)(); changed = True
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
                       hero: dict | None, pre_injured: set) -> list[dict]:
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
    ranked += [r for r in pool if room and r.get("station") == room]
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


def tick_production(st: dict) -> dict:
    """오프라인 생산 정산. 반환: 이번에 생산된 자원 요약."""
    elapsed = time.time() - st["last_tick"]
    ticks = min(int(elapsed // PRODUCTION_TICK_SEC), MAX_OFFLINE_TICKS)
    produced: dict = {}
    if ticks <= 0:
        return produced
    room_ids = [r["id"] for r in st["rooms"]]
    eff = role_effects(st)
    for r in st["rooms"]:
        spec = ROOMS[r["id"]]
        bonus = eff["room_bonus"].get(r["id"], {})
        for k, v in spec["produces"].items():
            if isinstance(v, int):
                amt = (v + bonus.get(k, 0)) * ticks
                st["resources"][k] = st["resources"].get(k, 0) + amt
                produced[k] = produced.get(k, 0) + amt
        for nb, bonus in spec.get("adjacency_bonus", {}).items():
            if nb in room_ids:
                for k, v in bonus.items():
                    st["resources"][k] = st["resources"].get(k, 0) + v * ticks
                    produced[k] = produced.get(k, 0) + v * ticks
    # 부상 회복: 틱마다 1명 (의무병 있으면 2명)
    heal = eff["heal_rate"] * ticks
    for res in st.get("residents_list", []):
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
DEPTH_ZONES = ((0, "무광층"), (150, "해구 문턱"), (210, "해구"))   # static/base.js ZONES 와 같은 경계(m)
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
        "residents_list": st.get("residents_list", []), "effects": role_effects(st),
        # 각인·신뢰 (residents_list[].imprints / .crises / .trust 와 함께 읽는다)
        "imprints_catalog": {i["id"]: {"name": i["name"], "crisis_ko": i.get("crisis_ko"), "visual": i["visual"]["ko"],
                                       "line": i["visual"]["line"], "effect": i["effect"], "cost": i["cost"].get("ko"),
                                       "pending": bool(i.get("_pending_text"))}
                             for i in IMPRINT_LIST},
        "trust": {r["id"]: {"avg": trust_avg(r), "to": r.get("trust", {})} for r in st.get("residents_list", [])},
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
    room_ids = [r["id"] for r in st["rooms"]]
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
    room_ids = [r["id"] for r in st["rooms"]]
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
        newcomer = make_resident(rng.choice(pool), rng, taken)
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
    participants = event_participants(roster, ev, seed, how, used, hero, pre_injured)
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
    if request.url.path in ("/", "/base") or request.url.path.startswith("/static"):
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
