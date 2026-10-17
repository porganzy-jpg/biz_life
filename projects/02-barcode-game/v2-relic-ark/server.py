"""
잔해 방주 (RELIC ARK) — Phase 0 서버
FastAPI + SQLite. 단일 테스터 그룹용(uid는 클라이언트가 생성해 보관).

실행:
  python server.py            # http://localhost:8002  (데스크톱 카메라 OK)
  python server.py --https    # https://<LAN IP>:8444 (휴대폰 카메라용, tools/make_cert.py 먼저)
  python server.py --port=9000
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import socket
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
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
# ── 방 열두 종 (ROOMS_AND_ITEMS §2 · 수치 정본 data/balance/economy.json rooms.list) ──────────
# S10-C: 코드에 다섯 종(pantry·well·infirmary·library·workshop)뿐이라 기획서의 12종 중 7종이 "없는 방"이었다.
# 정본 셋을 이 순서로 겹친다 — 아래로 갈수록 이긴다.
#   ① ROOM_TEXT_DEFAULT (개발 초안: 이름·한 줄 설명·등불색)
#   ② data/balance/economy.json rooms.list (**수치**: 건설비·정원·생산·레벨업 재료와 조건)
#   ③ data/rooms.json (시나리오 소유: **이름·설명·등불색**과 숫자가 아닌 생산물 counter_card·blueprint_progress)
# 기존 다섯 id 는 그대로 남는다(저장 호환). pantry·library 는 economy 표에 없어서 rooms.json 값으로 돈다.
_ECON_ALL = combat._balance("economy")
_ECON = (_ECON_ALL.get("rooms") or {})
ECON_ROOMS = {k: v for k, v in (_ECON.get("list") or {}).items() if isinstance(v, dict)}
ROOM_TEXT_DEFAULT = {
    "hall":       ("홀", "#E6D7B0", "층을 잇는 척추. 배치되지 않은 사람이 여기 모인다."),
    "quarters":   ("거주실", "#F2C27B", "잠자리 넷. 사람들이 서로 얼굴을 보고 잠드는 곳이라 사기가 돌아온다."),
    "storage":    ("창고", "#C08A33", "선반 여섯 칸. 찍어 온 물건이 하나씩 놓인다."),
    "greenhouse": ("온실", "#9FBF6A", "흙 상자와 등불. 먹을 것이 자라고, 언젠가 숨도 자란다."),
    "generator":  ("발전실", "#E4B453", "돔의 심장 소리. 어디를 밝힐지는 여기서 정해진다."),
    "airlock":    ("에어락", "#A2B3A0", "바깥으로 나가는 유일한 문. 한 번에 한 사람."),
    "workshop":   ("공방", "#F2A93B", "남이 버린 것을 다시 쓸 것으로 바꾸는 방. 막고 가리고 꿰매는 물건이 여기서 나온다."),
    "decoder":    ("해독실", "#D4AF37", "성문(바코드)을 읽는 책상. 가문 도감이 여기 있다."),
    "lounge":     ("전망 라운지", "#E8C9A0", "아무것도 만들지 않는다. 창이 크고, 바깥이 보인다."),
    "bath":       ("물 끓이는 방", "#E9B98A", "아무것도 만들지 않는다. 200년 만에 처음 더운물에 몸을 담근다."),
}
# 생산물 중 **자원 재고가 아닌 것**. resources 에 넣으면 유령 키가 된다(S10-C 버그 셋 참조)
ROOM_META_PRODUCE = ("power_supply", "heal", "craft_slots", "blueprint_progress", "counter_card")
# 짓는 조건(특수 방). economy.json 의 cond 글을 코드가 판정하는 형태로 옮긴 것
BUILD_COND = {
    "workshop": {"role": "engineer", "ko": "기술자 1명"},
    "decoder":  {"role": "scholar", "ko": "학자 1명"},
    "lounge":   {"room_level": ("quarters", 2), "ko": "거주실 Lv2"},
    "bath":     {"room_level": ("generator", 2), "ko": "발전실 Lv2"},
}
# 레벨업 조건(돈으로 못 사는 것). economy.json lvN.cond 글 → 판정식
UPGRADE_COND = {
    ("hall", 3):       {"depth_m": 180, "ko": "해구 문턱 도달(깊이 180m)"},
    ("quarters", 3):   {"imprints_on_one": 3, "ko": "각인 3개 보유자 1명"},
    ("greenhouse", 3): {"spot": "spot_kelp_ceiling", "ko": "스팟 「위를 보는 숲」 발견"},
    ("generator", 3):  {"spot": "spot_vent_garden", "ko": "스팟 「열수구 정원」 발견"},
    # 「숨의 손」 각인은 아직 imprints.json 에 없다 → 가장 가까운 「아낀 숨」으로 임시 판정(B7, TASKS 요청함)
    ("infirmary", 3):  {"imprint": "saved_breath", "ko": "「숨의 손」 각인 보유자 (임시: 「아낀 숨」)"},
}
HALL_ID = "hall"     # 홀은 칸에 짓는 방이 아니라 **처음부터 있는 척추**다. 레벨만 오른다


def _build_room_catalog() -> dict:
    out: dict = {}
    for rid, (ko, light, desc) in ROOM_TEXT_DEFAULT.items():
        out[rid] = {"name": ko, "light": light, "desc": desc, "tier": 1, "counters": [],
                    "cost": {}, "produces": {}}
    for rid, e in ECON_ROOMS.items():
        spec = out.setdefault(rid, {"name": e.get("ko", rid), "light": "#F2A93B", "desc": "", "tier": 1,
                                    "counters": [], "cost": {}, "produces": {}})
        spec["name"] = spec.get("name") or e.get("ko", rid)
        spec["cost"] = dict(e.get("build") or {})
        # S20: 공방 잔해는 economy.json 값 그대로(기획이 6 → 3 으로 고쳤다 — 서버 배율 1.0, 이중 할인 금지)
        spec["produces"] = dict(e.get("produces") or {})
        spec["cap"] = int(e.get("cap") or combat.ROOM_CAP_DEFAULT)
        if e.get("shelves"):
            spec["shelves"] = int(e["shelves"])
        if e.get("cond"):
            spec["cond_ko"] = str(e["cond"])
        lv = {}
        for n in (2, 3):
            row = e.get(f"lv{n}")
            if isinstance(row, dict):
                lv[str(n)] = {"cost": dict(row.get("cost") or {}), "opens": row.get("opens"),
                              "cond_ko": (UPGRADE_COND.get((rid, n)) or {}).get("ko") or row.get("cond"),
                              "cap": row.get("cap_after"), "produces": row.get("produces_after"),
                              "shelves": row.get("shelves_after")}
        spec["levels"] = lv
    for rid, f in ROOMS.items():                      # 시나리오 파일: 글은 이기고, 숫자는 표가 없을 때만
        spec = out.setdefault(rid, {"counters": [], "produces": {}, "cost": {}})
        for k in ("name", "light", "desc", "counters", "unlocks", "adjacency_bonus", "tier"):
            if k in f:
                spec[k] = f[k]
        if rid not in ECON_ROOMS:
            spec["cost"] = dict(f.get("cost") or {})
            spec["produces"] = dict(f.get("produces") or {})
        else:                                         # 숫자 아닌 생산물(counter_card 등)은 파일 것을 덧붙인다
            for k, v in (f.get("produces") or {}).items():
                if k in ROOM_META_PRODUCE and k not in spec["produces"]:
                    spec["produces"][k] = v
    for rid, spec in out.items():
        spec.setdefault("cap", combat.ROOM_CAP.get(rid, combat.ROOM_CAP_DEFAULT))
        spec.setdefault("levels", {})
        if rid == "pantry":                           # 시작 방 = 식량창고. 선반이 있는 창고 구실도 한다(E1)
            spec.setdefault("shelves", 6)
        spec["fixed"] = (rid == HALL_ID)
        spec["special"] = rid in BUILD_COND
    return out


ROOMS = _build_room_catalog()
combat.ROOM_CAP.update({rid: int(spec["cap"]) for rid, spec in ROOMS.items()})
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

# 심해 각인 4종(saved_breath·crack_seen·depth_mark·knock_heard)과 신규 셋(made_way·fed_it·sent_up)은
# 이제 전부 data/imprints.json 에 있다. 예전의 코드 사본 DEEP_IMPRINTS 는 S10-C 에서 지웠다 —
# 파일과 코드가 갈라질 위험만 남았기 때문이다(PM 2026-10-03). 각인의 정본은 그 파일 하나다.
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
_CRE_TEXT = ("name", "zone", "how", "sound", "silhouette", "contact", "habit", "hint_action_ko")
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
                {"who": _who, "text": _line["text"], "acts": _acts or [1, 2, 3], "req": _line.get("requires"),
                 "text_short": _line.get("text_short")})
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
    """스팟 문턱이 읽는 카테고리별 수. S13: stakes spot_unlock.count_distinct_barcodes 면 **서로 다른 바코드**만 센다
    (중복 스캔·값 0 재스캔이 단서를 열던 구멍)."""
    distinct = bool(stk("spot_unlock.count_distinct_barcodes"))
    q = ("SELECT category, COUNT(DISTINCT barcode) c FROM scans WHERE uid=? GROUP BY category" if distinct
         else "SELECT category, COUNT(*) c FROM scans WHERE uid=? GROUP BY category")
    with db() as con:
        rows = con.execute(q, (uid,)).fetchall()
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
        CREATE TABLE IF NOT EXISTS subtype_votes (uid TEXT, barcode TEXT, category TEXT, subtype TEXT, ts REAL,
                                                  PRIMARY KEY (uid, barcode));
        CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, uid TEXT, kind TEXT, payload TEXT, ts REAL);
        CREATE TABLE IF NOT EXISTS codes (code TEXT PRIMARY KEY, uid TEXT NOT NULL, created REAL, used REAL);
        CREATE INDEX IF NOT EXISTS codes_uid ON codes(uid);
        """)
        try:   # S24: 스캔 출처(camera|manual). 손으로 친 스캔은 전역 집계에서 뺀다
            con.execute("ALTER TABLE scans ADD COLUMN source TEXT")
        except sqlite3.OperationalError:
            pass
        try:   # 한 방주에 코드는 하나 — 동시 발급 경합을 DB 가 막는다(리뷰 2026-10-03)
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS codes_uid_unique ON codes(uid)")
        except sqlite3.IntegrityError as e:
            print(f"[codes] 유일 인덱스를 만들지 못했다(이미 중복 있음): {e}")


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


def normalize_code(raw: str) -> str | None:
    """사람이 적은 것을 받아 준다 — 소문자·공백·하이픈은 지운다. 알파벳에 없는 글자(0·O·1·I)가 섞였거나
    길이가 여섯이 아니면 None(→ 400). 조용히 잘라서 다른 코드를 시도하지 않는다(리뷰 2026-10-03)."""
    code = "".join(ch for ch in str(raw or "").upper() if ch.isalnum())
    if len(code) != CODE_LEN or any(ch not in CODE_ALPHABET for ch in code):
        return None
    return code


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
                row = con.execute("SELECT code FROM codes WHERE uid=?", (uid,)).fetchone()
                if row:              # 같은 방주에 다른 요청이 먼저 발급했다 → 그 코드를 쓴다
                    return row["code"]
                continue            # 코드 충돌. 다시 뽑는다
    raise HTTPException(500, "코드를 만들지 못했습니다. 잠시 뒤 다시 시도해 주세요")


def uid_for_code(code: str) -> str | None:
    with db() as con:
        row = con.execute("SELECT uid FROM codes WHERE code=?", (code,)).fetchone()
        return row["uid"] if row else None


# 불러오기 시도 제한 — 코드가 곧 방주의 열쇠라 무차별 대입을 막는다(리뷰 2026-10-03).
#   IP 마다: 1분에 실패 5회까지. 넘으면 잠금, 잠길 때마다 대기가 두 배(30초 → 60 → … 최대 1시간).
#   전역: 1분에 실패 120회가 넘으면 모든 불러오기를 1분 쉰다(여러 IP 로 나눠 찍는 것을 막는다).
#   성공은 세지 않는다. 메모리에만 둔다 — 서버를 다시 켜면 풀리지만, 그 정도는 공격 속도를 바꾸지 못한다.
RESTORE_WINDOW, RESTORE_MAX_FAILS = 60.0, 5
RESTORE_GLOBAL_MAX = 120
_RESTORE_FAILS: dict[str, list] = {}          # ip -> [실패 시각...]
_RESTORE_LOCK: dict[str, tuple] = {}          # ip -> (풀리는 시각, 잠긴 횟수)
_RESTORE_GLOBAL: list = []


def restore_gate(ip: str) -> float:
    """지금 막혀 있으면 남은 초, 아니면 0."""
    now = time.time()
    until, _n = _RESTORE_LOCK.get(ip, (0.0, 0))
    if until > now:
        return until - now
    _RESTORE_GLOBAL[:] = [t for t in _RESTORE_GLOBAL if now - t < RESTORE_WINDOW]
    if len(_RESTORE_GLOBAL) >= RESTORE_GLOBAL_MAX:
        return RESTORE_WINDOW - (now - _RESTORE_GLOBAL[0])
    return 0.0


def restore_failed(ip: str) -> None:
    now = time.time()
    _RESTORE_GLOBAL.append(now)
    rows = [t for t in _RESTORE_FAILS.get(ip, []) if now - t < RESTORE_WINDOW] + [now]
    _RESTORE_FAILS[ip] = rows
    if len(rows) >= RESTORE_MAX_FAILS:
        _until, n = _RESTORE_LOCK.get(ip, (0.0, 0))
        _RESTORE_LOCK[ip] = (now + min(3600.0, 30.0 * (2 ** n)), n + 1)
        _RESTORE_FAILS[ip] = []


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


NEW_STATE_SEED: str | None = None   # 테스트 전용: 주어지면 시작 주민(이름·id·성향)을 uid 로 고정한다(평소엔 시각 시드)


def new_state(uid: str = "") -> dict:
    now = time.time()
    rng = random.Random(f"{NEW_STATE_SEED}|{uid}") if NEW_STATE_SEED is not None else random.Random(now)
    taken: set = set()
    residents = [make_resident(role, rng, taken, uid) for role in ("cook", "engineer", "scout")]   # 시작 3인: 먹이고, 고치고, 살핀다
    for _r in residents:
        ensure_stats(uid, _r)
    return {
        "residents_list": residents,
        "created": now, "last_tick": now,
        "resources": {"food": 4, "water": 4, "med": 0, "power": 0, "parts": 1, "morale": 5,
                      "cloth": 0, "trade": 0, "knowledge": 0, "scrap": 2, "chem": 0},
        "rooms": [{"id": "pantry", "slot": 2, "built": now, "level": 1}],   # 시작 방주: 지하 1층 식량창고 1칸 (첫 화면이 비지 않게)
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
        changed = migrate_s13(st, uid) or changed  # S13 선반 바코드·닦기·중복 칸 정리·카테고리 고정
        changed = migrate_s15(st) or changed       # S15 원정·상자·손님·스팟 발견 분리
        changed = migrate_s19(st, uid) or changed  # S19 옛 바람 → 사슬, free_pack → 상자
        if changed:
            save_state(uid, st)
        st["_loaded_res"] = dict(st.get("resources") or {})   # S18-D 저장 상한: 이번 요청에서 늘어난 분만 자른다
        _DEV_HOUR.set(st.get("dev_clock_hour") if DEV_MODE else None)   # ★ 개발 시계
        return st
    st = new_state(uid)
    if DEV_MODE:
        st["test_ark"] = True                         # S25 후속: 개발 서버(RELIC_DEV)에서 만든 방주는 전역 집계에서 뺀다
    migrate_s13(st, uid)
    migrate_s15(st)
    migrate_s19(st, uid)
    save_state(uid, st)
    log(uid, "ark_created")
    return st


def save_state(uid: str, st: dict):
    before = st.pop("_loaded_res", None)
    if before is not None:
        apply_storage_cap(st, before)
    _rest = dict(st.get("resources") or {})
    with db() as con:
        con.execute("INSERT OR REPLACE INTO arks(uid,state) VALUES(?,?)",
                    (uid, json.dumps(st, ensure_ascii=False)))
    if before is not None:
        st["_loaded_res"] = _rest                    # 같은 요청 안의 다음 저장도 '늘어난 분만' 자르게


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
    for r in st.get("rooms", []):           # S10-C 방 레벨. 구버전 방은 전부 Lv1
        if not isinstance(r.get("level"), int):
            r["level"] = 1; changed = True
    if not isinstance(st.get("shelf"), list):
        st["shelf"] = []; changed = True
    if not isinstance(st.get("hall_level"), int):
        st["hall_level"] = 1; changed = True
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
def voice_for(tag: str, seed: str, who: str | None = None, act: int | None = None,
              facts: set | None = None) -> dict | None:
    """상황 태그에 맞는 한 줄. 같은 입력이면 같은 줄(D6: 시드 결정성).
    act 를 주면 그 막에서 할 수 있는 말만 남긴다. acts 가 없는 줄은 전 막 공용이므로
    시나리오가 값을 채우기 전에도 지금과 똑같이 동작한다(줄이 갑자기 사라지지 않는다)."""
    pool = [ln for ln in VOICE_LINES.get(tag, []) if who is None or ln["who"] == who]
    # S18: 줄이 전제하는 사실(예: 「상자 하나 열어 두었습니다」→ 상자를 실제로 열었다)이 없으면 그 줄은 쓰지 않는다
    fx = set(facts or ())
    pool = [ln for ln in pool
            if line_requires({"requires": ln["req"]} if ln.get("req") else ln["text"]) <= fx]
    if act in (1, 2, 3):
        in_act = [ln for ln in pool if act in ln.get("acts", [1, 2, 3])]
        pool = in_act or []        # 그 막에서 할 말이 없으면 **말하지 않는다**(엉뚱한 막의 대사보다 침묵이 낫다)
    if not pool:
        return None
    rng = random.Random(f"voice|{seed}|{tag}")
    line = rng.choices(pool, weights=[VOICE_WEIGHT.get(ln["who"], 1) for ln in pool], k=1)[0]
    return {"who": line["who"], "who_ko": VOICE_KO[line["who"]], "text": line["text"], "when": tag,
            "text_short": line.get("text_short") or None}          # S20: 2줄 스캔 카드용 짧은 줄(없으면 null)


def is_night(hour: int | None = None) -> bool:
    h = now_hour() if hour is None else hour
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


def grant_imprints(st: dict, ev: dict | None, flags: list[str], targets: list[dict],
                   src: str | None = None) -> list[dict]:
    """살아남은 주민 중 그 위기 종류가 '처음'인 사람에게 각인을 준다.
    반환: [{resident, imprint, line, evolved}] — /api/event/resolve 의 new_imprints."""
    imp = imprint_for(ev, flags)
    if not imp:
        return []
    out = []
    given_today = st.setdefault("imprint_days", {})
    for r in targets:
        r.setdefault("crises", []); r.setdefault("imprints", [])
        if imp["crisis"] in r["crises"]:
            continue                                   # 두 번째부터는 성장이 없다
        gd = given_today.get(imp["id"])
        if gd and int(gd.get("day") or 0) == day_of(st) and gd.get("rid") != r["id"]:
            continue                                   # S19: 같은 각인은 같은 날 두 사람에게 주지 않는다(PM)
        r["crises"].append(imp["crisis"])
        if imp["id"] in r["imprints"] or len(r["imprints"]) >= MAX_IMPRINTS:
            continue                                   # 같은 각인은 한 번, 최대 3개
        r["imprints"].append(imp["id"])
        given_today[imp["id"]] = {"day": day_of(st), "rid": r["id"]}
        # 하루 마감이 사실만 말하게 — 어디서 생긴 각인인지 함께 적는다(event·raid·expedition)
        day_note(st, "imprint", {"name": r["name"], "src": src or ("event" if ev else "raid"), "imprint": imp["id"]})
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
           "counter_bonus": {}, "food_daily": 0.0, "food_daily_all": 0.0, "morale_cap": 0, "imprint_count": 0}
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
        for imp_id in list(r.get("imprints", [])) + list(r.get("personal_imprints") or []):
            imp = IMPRINTS.get(imp_id) or ARC_IMPRINTS.get(imp_id)
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
    S13: 방마다 × staff_mult[그 방에 서 있는 사람 수] × (금 갔으면 crack.prod_mult) — data/balance/stakes.json
    """
    elapsed = time.time() - st["last_tick"]
    ticks = min(int(elapsed // PRODUCTION_TICK_SEC), MAX_OFFLINE_TICKS)
    produced: dict = {}
    if ticks <= 0:
        return produced
    if not st.get("power_on", True):
        # 전원을 내려 둔 채로 시간이 흘렀다. 조용한 대신 아무것도 만들지 못한다
        st["last_tick"] += ticks * PRODUCTION_TICK_SEC
        consume_tick(st, ticks)                      # S26 사람은 전원과 무관하게 먹는다
        air_refill(st, ticks)                        # S15 공기는 전원과 무관하게 찬다(손 펌프·바깥 물)
        if not staff_snapshot_active(st):
            st.pop("staff_snapshot", None)
        st["dark_note"] = {"kind": "blackout", "ticks": ticks,
                           "ko": "전원이 내려가 있는 동안 아무 방도 일하지 않았다."}
        return produced
    st.pop("dark_note", None)
    snap = staff_snapshot_active(st)
    if snap and float(snap["tick_start"]) >= st["last_tick"] + ticks * PRODUCTION_TICK_SEC:
        snap = None                                   # 접촉한 틱은 아직 정산 범위 밖이다(다음 정산에서 쓴다)
    # 물 찬 방은 생산하지 않는다. 인접 보너스도 주지 않는다 — 그 방은 더 이상 방이 아니다
    live = [r for r in st["rooms"] if not r.get("flooded")]
    room_ids = [r["id"] for r in live]
    eff = role_effects(st)
    dark_rooms = []
    heal_extra = 0.0
    for r in live:
        spec = ROOMS.get(r["id"]) or {"name": r["id"], "produces": {}}
        light = 1.0
        if not light_on(st, r["slot"]):
            light = 0.5
            dark_rooms.append(spec["name"])
        # S13 배치 = 생산(staffing) × 금(crack). S14 × 능력치(stat_production), 역할 보정은 그 방에 선 사람 것만.
        # 서 있는 사람은 **정산 순간**의 배치이고, 접촉이 있었던 틱 하나만은 접촉 순간 배치(스냅숏의 id)로 센다
        segs = [(w, m * light, bn) for w, m, bn in room_segments(st, r, snap, ticks, eff)]
        mul = sum(w * m for w, m, _ in segs) / ticks if ticks else 0.0
        for k, v in room_produces(r).items():
            if k == "heal" and isinstance(v, (int, float)):
                heal_extra += v * mul          # 의무실·물 끓이는 방 = 회복 속도(재고가 아니다)
                continue
            if k in ("power_supply", "craft_slots"):
                continue                       # 공급량·동시 제작 수. 쌓이는 재고가 아니다(economy power._rule)
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
                amt = int(round(sum(w * (v + bn.get(k, 0)) * m for w, m, bn in segs)))
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
                           "ko": moment("raid_card.dark_rooms", rooms=" · ".join(sorted(set(dark_rooms))))
                                 or ("불을 꺼 둔 방은 절반만 일했다 — " + " · ".join(sorted(set(dark_rooms))))}
    # 부상 회복: 틱마다 1명 (의무병 있으면 2명) + 의무실·물 끓이는 방의 회복(heal) 값
    heal = int(round((eff["heal_rate"] + heal_extra) * ticks))
    # 숨이 긴 사람이 먼저 일어난다(RESIDENT_STATS §4 "부상 회복 = 숨 + 의무실 등급")
    for res in sorted(st.get("residents_list", []),
                      key=lambda r: -int((r.get("stats") or {}).get("breath", 5))):
        if res.get("injured") and heal > 0:
            res["injured"] = False; heal -= 1
    st["injured"] = sum(1 for x in st.get("residents_list", []) if x.get("injured"))
    st["last_tick"] += ticks * PRODUCTION_TICK_SEC
    consume_tick(st, ticks)                      # S26 하루 소비(economy.json daily_consumption_server)
    air_refill(st, ticks)                        # S15 하루 공기: 틱마다 공급의 1/3, 상한 = 하루 공급
    if not staff_snapshot_active(st):
        st.pop("staff_snapshot", None)           # 접촉한 틱이 정산됐다(또는 지난 것이다)
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
        "air":   {"ko": "공기", "value": air_state(st)["band"], "fixed": False,
                  "note": "남은 공기 / 하루 공급(S15). 숫자가 아니라 띠"},
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


def room_level(room: dict | None) -> int:
    try:
        return max(1, min(3, int((room or {}).get("level") or 1)))
    except (TypeError, ValueError):
        return 1


def _level_val(room: dict, key: str):
    """레벨에 따라 바뀌는 값(cap·produces·shelves). 그 레벨에 값이 없으면 아래 레벨 값을 물려받는다."""
    spec = ROOMS.get(room.get("id"), {})
    val = spec.get(key)
    for n in range(2, room_level(room) + 1):
        v = ((spec.get("levels") or {}).get(str(n)) or {}).get(key)
        if v is not None:
            val = v
    return val


def room_cap_of(room: dict | None) -> int:
    if not room:
        return combat.ROOM_CAP_DEFAULT
    if room.get("flooded"):
        return 0
    return int(_level_val(room, "cap") or combat.room_cap(room["id"]))


def room_produces(room: dict) -> dict:
    return dict(_level_val(room, "produces") or {})


def shelves_of(room: dict) -> int:
    return int(_level_val(room, "shelves") or 0)


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
        "room_cap": room_cap_of(r) if r else 0,
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
        # S13 금 간 방은 바탕이 낮다(stakes crack.room_base_penalty). 금 가지 않은 방에는 키 자체가 없다
        **({"room_base_adj": float(stk("crack.room_base_penalty") or 0),
            "room_base_adj_ko": moment("crack.label_cracked") or "금 간 유리"}
           if r and not r.get("flooded") and r.get("cracked") else {}),
    }


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
    # S15: outside 는 이제 **원정대**다. 하루를 넘겨도 비우지 않는다(밤 넘기기가 날을 넘긴다).
    grade = int(grade_force) if grade_force else grade_of(st)
    # 덮개 보류 해제 문턱(threats.json min_grade_override)의 주민 수 = residents_list 전원.
    # 들이지 않은 손님(st["guests"])은 빠지고, 원정 나간 사람은 주민이라 센다(PM 2026-10-04)
    cre = combat.pick_creature(uid, day, grade, force=force,
                               residents=len(st.get("residents_list") or []),
                               **({"mult": creature_mult(st)} if creature_mult(st) else {}))
    # S19 비트 캘린더: 그날 비트의 생물을 운 대신 차례로(처음 만나는 것만, 세기 0)
    beat_cre = BEAT_FORCE_CREATURE.get(beat_today_id(st) or "")
    beat_forced = False
    if (not force and not grade_force and beat_cre in combat.CREATURES and beat_cre not in encounters_of(st)
            and not (beat_cre == "shade" and cre and cre.get("threat"))):
        cre = combat.CREATURES[beat_cre]
        beat_forced = True
    # S18 첫 주 위협 보장(threats.json first_week_guarantee): by_day 까지 위협이 한 번도 안 왔으면 그날(을 넘겼으면
    # until_day 안의 첫 방문 날) 하나를 보낸다. 무엇이 오는지는 그 등급 가중치대로(시드 uid|day|guarantee)
    fg = first_week_guarantee()
    guaranteed = False
    if (not force and not grade_force and not int(st.get("threat_raids") or 0)
            and fg["by_day"] <= day <= fg["until_day"] and not (cre and cre.get("threat"))):
        if fg.get("creature") in combat.CREATURES:
            cre = combat.CREATURES[fg["creature"]]
        else:
            w = {k: v for k, v in combat.creature_weights(grade, len(st.get("residents_list") or [])).items()
                 if combat.CREATURES[k]["threat"]}
            if w:
                ids = sorted(w)
                cre = combat.CREATURES[combat.raid_rng(uid, day, "guarantee").choices(ids, weights=[w[i] for i in ids], k=1)[0]]
        guaranteed = bool(cre)
    if not cre:
        st["raid"] = {"day": day, "none": True, "grade": grade}
        return None
    slot = combat.pick_target(uid, day, cre, live_rooms(st), st.get("room_tools") or {},
                              weights=raid_target_weights(st))
    if (guaranteed or (beat_forced and cre.get("threat"))) and fg.get("target") == "occupied_room":
        occ = sorted(int(k) for k, v in stations_map(st).items() if v and room_at(st, k) and not room_at(st, k).get("flooded"))
        if occ:
            slot = combat.raid_rng(uid, day, "guarantee_target").choice(occ)
    if slot is None:
        # 갈 방이 없다(전부 침수거나 전부 유인 등불). 긴목은 다른 불빛을 따라 간다
        st["raid"] = {"day": day, "none": True, "diverted": cre["id"], "grade": grade}
        return None
    sev = combat.severity(uid, day, grade)
    if guaranteed and isinstance(fg.get("severity"), (int, float)):
        sev = int(fg["severity"])
    if beat_forced:
        sev = 0
    sev += int(st.pop("severity_debt", 0) or 0)      # 윗물 아이를 올려 보낸 값(금기를 어겼다)
    raid = {
        "id": f"raid-{day}-{cre['id']}", "day": day, "creature": cre["id"], "grade": grade,
        "target_slot": int(slot), "severity": max(0, min(4, sev)),
        "stage": "sound", "started": time.time(), "resolved": False, "result": None,
        "outside_sent": [], "acts": [], "moves": 0, "guaranteed": guaranteed,
    }
    if beat_forced:
        raid["beat"] = beat_today_id(st)
    if cre.get("threat"):
        st["threat_raids"] = int(st.get("threat_raids") or 0) + 1
    if cre["gate"] == "all_inside":
        raid["outside_sent"] = list(st.get("outside") or [])   # S15: 무작위 차출 폐지 — 원정 나간 사람만 밖에 있다
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
    out_ = None
    revealed = lid_revealed(raid, cre)                # S13 덮개: stakes lid.reveal_from_stage 부터 대상 방을 연다
    if revealed:
        quiet = False
    out_ = {
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
        "lid_revealed": revealed,
        # S18: raid_card(단서 먼저 — 사용자 승인 대기) 대비 버릇 한 줄 자리. 생물 문장(creatures.json)의 habit, 없으면 null
        "habit": (cre.get("lines") or {}).get("habit") or cre.get("habit"),
        "reveal_ko": moment("lid.target_revealed", room=room_name or "") if revealed else None,
        "auto": bool(raid.get("auto")), "capped": bool(raid.get("capped")),
        "office": office_offer(st, raid),             # S27 ⑧ 「관리실이 대신 막을까요?」(낮 세션)
        # 그 생물을 막는 **행동 버튼**(관문이 토글로 안 되는 일곱). 대가와 낼 수 있는지까지 서버가 판단한다
        "action": None if quiet else gate_action_public(st, raid, cre),
        # 접촉 전 미리보기(실루엣 단계부터). 숫자보다 "무엇이 모자란지"를 먼저 말한다
        "eye_early": ({"name": eye_who["name"], "eye": eye,
                       "ko": moment("raid_card.eye_early", name=eye_who["name"])
                             or (eye_who["name"] + "의 눈이 밝다 — 소리만 듣고 어느 창인지 안다.")} if early else None),
        "ready": None if quiet else {
            "gate": preview["gate"], "score": preview["score"], "need": preview["need"],
            # 미리보기는 미래형(ui_moments raid_preview) — 결과용 과거형(RESULT_KO)을 쓰지 않는다(플레이테스트 버그 10)
            "would": preview["result"],
            "would_ko": moment(f"raid_preview.{preview['result']}") or combat.RESULT_KO[preview["result"]],
            "parts": parts_display(preview["parts"]), "shielded": preview.get("shielded"),
        },
    }
    out_ = raid_card_apply(st, raid, cre, out_)
    rd = out_.get("ready")
    if rd and week1_cap(st) and _RESULT_RANK.get(rd.get("would"), 0) > _RESULT_RANK[combat.SCARRED]:
        out_["ready"] = dict(rd, would=combat.SCARRED, would_ko=moment("raid_preview.scarred") or combat.RESULT_KO[combat.SCARRED],
                             capped_week1=True)          # S30: 첫 주는 방을 잃지 않는다(미리보기도 그대로 말한다)
        rd = out_["ready"]
    out_["hint_action_ko"] = (cre.get("hint_action_ko") or None) if rd and rd.get("would") in (combat.SCARRED, combat.BREACHED) else None
    return out_


def encounters_of(st: dict) -> dict:
    """생물별로 '만나 본' 횟수(접촉까지 간 습격 — 누름·밤 판정 모두). raid_log 에서 센다."""
    out: dict = {}
    for r in st.get("raid_log") or []:
        c = r.get("creature")
        if c and r.get("result"):
            out[c] = out.get(c, 0) + 1
    return out


def raid_card_mode(st: dict, cre: dict) -> str:
    """stakes raid_card(사용자 승인 2026-10-04): clue_first 면, 같은 생물을 answer_after_encounters 번 만나기 전까지
    답(관문 문장·맞는 행동) 대신 버릇 한 줄과 동사 목록만 보여 준다. 그 뒤는 예전처럼 답을 보여 준다."""
    rc = stk("raid_card") or {}
    if not isinstance(rc, dict) or rc.get("mode") != "clue_first" or not cre.get("threat"):
        return "answer"
    n = encounters_of(st).get(cre["id"], 0)
    return "clue" if n < int(rc.get("answer_after_encounters", 2)) else "answer"


VERBS = ("light", "power", "station", "tool", "act")


def raid_verbs(st: dict, raid: dict) -> list:
    """고를 수 있는 동사(불·전원·자리·도구·행동). 행동은 **모든** 관문 행동을 대가와 함께 늘어놓는다 — 답을 가리지 않게."""
    sev = int(raid.get("severity", 0))
    acts = []
    for aid, spec in combat.GATE_ACTIONS.items():
        acts.append({"id": aid, "ko": spec.get("ko"), "cost": combat.action_cost(aid, sev), "cost_ko": spec.get("cost_ko")})
    return [{"id": "light", "ko": "불"}, {"id": "power", "ko": "전원"}, {"id": "station", "ko": "자리"},
            {"id": "tool", "ko": "도구"}, {"id": "act", "ko": "행동", "options": acts}]


def raid_card_apply(st: dict, raid: dict, cre: dict, out: dict) -> dict:
    mode = raid_card_mode(st, cre)
    enc = encounters_of(st).get(cre["id"], 0)
    out["card_mode"] = mode
    out["encounters"] = enc
    out["verb"] = raid.get("verb")
    if mode != "clue":
        return out
    out["verbs"] = raid_verbs(st, raid)
    out["action"] = None                         # 그 생물의 맞는 행동 하나를 콕 집어 보이지 않는다
    if isinstance(out.get("creature"), dict):
        out["creature"] = dict(out["creature"], how=None)   # how = 「불을 꺼 주세요」 — 답이다
    # eye_early(「눈이 밝다 — 어느 창인지 안다」)는 **어느 방**을 알려 주는 단서라 남긴다(막는 법은 말하지 않는다)
    if out.get("ready"):
        if not raid.get("verb"):
            out["ready"] = None                  # 동사를 고르기 전에는 미리보기가 닫혀 있다
        else:
            g = out["ready"].get("gate") or {}
            # 관문의 종류·행동 id·필요 수는 곧 답이다 — 단서 모드에서는 '통했나(ok)'와 결과·대가만
            out["ready"] = dict(out["ready"], gate={"ok": bool(g.get("ok")), "ko": None},
                                short_of=short_of_word(st, raid, cre, out["ready"]))
    return out


def lid_revealed(raid: dict, cre: dict) -> bool:
    """덮개(관문 = 움직이지 않기)의 대상 방 공개. stakes lid.reveal_target 이 참이고 reveal_from_stage 이후면 True.
    이 단계부터의 이동은 덮개의 moves 에 세지 않는다(stakes lid._note — 공개가 의미를 갖게)."""
    if (cre or {}).get("gate") != "stand_still" or not stk("lid.reveal_target"):
        return False
    stages = list(combat.STAGES)
    rv = str(stk("lid.reveal_from_stage") or "silhouette")
    if raid.get("stage") not in stages or rv not in stages:
        return False
    return stages.index(raid["stage"]) >= stages.index(rv)


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
        caps[str(r["slot"])] = room_cap_of(r)
    return {
        "stations": {k: int(v) for k, v in (st.get("stations") or {}).items()},
        "hall": [r["id"] for r in hall_of(st)],
        "outside": list(st.get("outside") or []),
        "caps": caps,
        "lights": {str(r["slot"]): light_on(st, r["slot"]) for r in st.get("rooms", [])},
        "power_on": bool(st.get("power_on", True)),
        "raid": raid_public(st, st.get("raid")),
        "raid_log": list(st.get("raid_log") or [])[-8:],
        "encounters": encounters_of(st),                    # S18 생물별 만난 횟수(raid_card 답 공개 기준)
        "next_raid_hint": st.get("next_raid_hint"),
        "workshop": tool_public(st),
        "grade": grade_of(st),
        # 단서 모드인 생물(아직 두 번 못 만난 위협)은 막는 법(how·관문)을 이 사전에서도 숨긴다 — 답이 새지 않게
        "creatures": {c["id"]: ({"name": c["name"], "how": c["how"], "threat": c["threat"],
                                 "gate": c.get("gate", "none"),
                                 "gate_ko": combat.GATE_KO.get(c.get("gate", "none"), ""), "card_mode": "answer"}
                                if raid_card_mode(st, c) == "answer" else
                                {"name": c["name"], "how": None, "threat": c["threat"], "gate": None, "gate_ko": None,
                                 "habit": c.get("habit"), "card_mode": "clue"})
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
        # E1 선반(계약 형식 고정). shelf_room 은 어느 방의 선반인지 알려 주는 덧붙임
        "shelf": shelf_public(st),
        "shelf_room": ({"slot": shelf_room(st)["slot"], "room_id": shelf_room(st)["id"],
                        "level": room_level(shelf_room(st)), "capacity": shelf_capacity(st)}
                       if shelf_room(st) else ({"slot": None, "room_id": None, "level": 1, "capacity": shelf_capacity(st),
                                                "fallback": True} if shelf_capacity(st) else None)),
        # 짓기·레벨업 가능 여부(서버가 판단한다. 화면은 그리기만)
        "build_options": build_options(st, uid),
        "upgrades": {str(r["slot"]): upgrade_option(st, uid, r["id"], room_level(r))
                     for r in live_rooms(st)},
        "hall_level": int(st.get("hall_level") or 1),
        "hall_upgrade": upgrade_option(st, uid, HALL_ID, int(st.get("hall_level") or 1)),
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
        "stats_meta": {"keys": list(STAT_KEYS), "ko": STAT_KO, "use": STAT_USE, "max": 10,
                       # S14 정본 방→능력치 표(stakes stat_production.room_stat). 화면 ROOM_STAT 사본을 대신한다
                       "room_stat": {rid: room_stat_of(rid) for rid in ROOMS if room_stat_of(rid)},
                       "stat_production": stat_production_params()},
        # S18-A2 게임 하루가 끝나는 시각(방주 생성 기준 날 경계). 화면은 이 시각 3시간 안에 하루 마감을 연다
        "day_ends_at": float(st["created"]) + day_of(st) * 86400,
        # S15 원정·문간(docs/API_EXPEDITION.md)
        "expedition": exp_public(st, st.get("expedition")),
        "expedition_return": st.get("exp_unseen"),
        "air": air_state(st),
        "guests": len(st.get("guests") or []),
        "boxes": boxes_public(st),
        "beds": beds_state(st),
        "entrance": entrance_public(st),                    # /api/entrance 와 같은 모양(S15-A2)
        "stored": stored_public(st),                        # S18: 선반에 못 놓인 유물(창고 상자)
        "storage": storage_public(st),                      # S18-D 재료당 저장 상한·가득 찬 것
        "material_sources": MATERIAL_SOURCES,               # S18-D 「모자랍니다」 옆 출처 한 줄(economy.json)
        "spots_found": list(st.get("spots_found") or []),
        # S14 드래그 미리보기 — 서버가 미리 계산한다(화면은 게임 숫자를 계산하지 않는다, D2)
        "move_preview": move_preview(st),
        # ── S13 이해관계·수집 (docs/API_S13.md) ─────────────────────
        "production": production_public(st),
        # 물 찬 칸(사용자 결정 2026-10-03): 다시 지을 수 있다. was_* 는 잃기 전 방(화면이 같은 방을 먼저 권할 수 있게)
        "flooded_cells": [{"slot": r["slot"], "was_id": (r.get("flooded_from") or {}).get("id", r.get("id")),
                           "was_name": (ROOMS.get((r.get("flooded_from") or {}).get("id", r.get("id"))) or {}).get("name"),
                           "was_level": (r.get("flooded_from") or {}).get("level", room_level(r)),
                           "flooded_day": r.get("flooded_day"), "by": r.get("flooded_by"),
                           "reclaim": "build"}
                          for r in st.get("rooms", []) if r.get("flooded")],
        "repair": {"cost": dict(stk("crack.repair_cost") or {}), "patch_tool": REPAIR_PATCH_TOOL,
                   "have_patch": int((st.get("tools") or {}).get(REPAIR_PATCH_TOOL, 0)) if REPAIR_PATCH_TOOL else 0,
                   "label": moment("crack.label_repair")},
        "night_judge": {"hour": int(stk("night_judge.hour")), "worst": stk("night_judge.worst_result"), "report": None},
        "octopus": octopus_public(st),
        "wishes_new": [],
        "families_done": sorted((st.get("family_sets") or {}).keys()),
        "decor": [{"code": k, "name": (v or {}).get("decor")} for k, v in (st.get("family_sets") or {}).items()
                  if (v or {}).get("decor")],
        # ── S19 핵심 루프 A (docs/API_S19.md) ──
        "core": core_public(st, uid),
        "needs_today": needs_today_public(st, uid),
        "room_decor": room_decor_public(st),
        "entrance_airlock": {"level": int((st.get("entrance_airlock") or {}).get("level") or 0)},
        "drain_cells": drain_cells(st),                      # S26 빈 칸·물 찬 칸마다 물 빼기 비용
        "consumption": consumption_public(st),
        "prefs": {"labels_always": bool((st.get("prefs") or {}).get("labels_always"))},
        "personal_imprints_catalog": {k: {"name": v.get("name"), "visual": (v.get("visual") or {}).get("ko"),
                                          "line": (v.get("visual") or {}).get("line"), "ability_ko": v.get("ability_ko"),
                                          "cost": (v.get("cost") or {}).get("ko"), "effect": v.get("effect")}
                                      for k, v in ARC_IMPRINTS.items()},
    }


# ─────────────────────────────────────────────────────────────
# E1 선반 — 찍은 물건이 창고 선반에 **실물로** 쌓인다 (PLAYER_JOURNEY E1, 이 게임의 정체성)
#   소품 이름표: data/relic_props.json (시나리오) · 그림·폭: static/art/props/props_meta.json (배경)
#   계약(화면 담당과 합의, 형식을 바꾸지 않는다):
#     GET /api/ark → shelf: [{slot, prop_id, name, category, rarity, family, scanned_at}]
#     POST /api/scan → shelf_slot: int | null (선반이 차면 null)
#   slot 은 선반 **칸** 번호다. 폭 2 소품(68px)은 slot 과 slot+1 두 칸을 차지한다(폭은 props_meta 의 slots).
#   선반 방 = 창고(storage). 없으면 시작 방 식량창고(pantry)가 그 구실을 한다 — 첫 스캔부터 선반에
#   물건이 놓여야 E1 이 첫 3분 안에 보인다(D5). 둘 다 없으면 빈 배열.
# ─────────────────────────────────────────────────────────────
_PROPS = (_load_json("relic_props.json") or {}).get("props") or {}
try:
    _PROPS_META = json.loads((ROOT / "static" / "art" / "props" / "props_meta.json").read_text(encoding="utf-8")).get("props") or {}
except (OSError, json.JSONDecodeError):
    _PROPS_META = {}
SHELF_ROOMS = ("storage", "pantry")       # 앞이 우선


def prop_width(pid: str) -> int:
    m = _PROPS_META.get(pid) or {}
    if isinstance(m.get("slots"), int):
        return max(1, min(2, m["slots"]))
    for rows in _PROPS.values():
        for r in rows:
            if r.get("id") == pid:
                return max(1, min(2, int(r.get("slots") or 1)))
    return 1


def shelf_room(st: dict) -> dict | None:
    """선반이 있는 방 = **선반 칸이 가장 많은 방**(창고를 짓거나 올리면 물건이 그리로 옮겨 간다 —
    창고 레벨업이 선반으로 보여야 한다, D2). 칸 수가 같으면 지금 쓰던 방을 지킨다(물건이 괜히 옮겨 다니지 않게)."""
    live = [r for r in live_rooms(st) if r["id"] in SHELF_ROOMS]
    if not live:
        return None
    keep = st.get("shelf_room_slot")
    live.sort(key=lambda r: (-shelves_of(r), r["slot"] != keep, SHELF_ROOMS.index(r["id"]), r["slot"]))
    st["shelf_room_slot"] = live[0]["slot"]
    return live[0]


def shelf_capacity(st: dict) -> int:
    """S18: 선반이 **자란다**(economy.json `shelf`, 기획 S18-D) —
    식량창고 바탕 base_pantry + 창고 방마다 per_storage_level[레벨](큰 것부터 max_storage_rooms_counted 개)
    + 되찾은 층마다 per_floor_reclaimed. 표가 없으면 예전 규칙(칸이 가장 많은 방 하나)."""
    r = shelf_room(st)
    sh = (_ECON_ALL.get("shelf") or {}) if isinstance(_ECON_ALL.get("shelf"), dict) else {}
    if not r:
        # S19(플레이테스트 2차 B): 선반 방을 모두 물에 잃으면 선반이 통째로 사라졌다 — 창고 상자가 선반 구실(바탕 칸)
        if any(x.get("flooded") and (x.get("flooded_from") or {}).get("id", x.get("id")) in SHELF_ROOMS
               for x in st.get("rooms") or []):
            return int(sh.get("base_pantry", 6))
        return 0
    if not sh.get("per_storage_level"):
        return shelves_of(r)
    total = int(sh.get("base_pantry", 6)) if any(x["id"] == "pantry" for x in live_rooms(st)) else 0
    lv = sorted((int((sh["per_storage_level"] or {}).get(str(room_level(x)), 0))
                 for x in live_rooms(st) if x["id"] == "storage"), reverse=True)
    total += sum(lv[:int(sh.get("max_storage_rooms_counted", 2))])
    total += int(sh.get("per_floor_reclaimed", 0)) * int(st.get("reclaimed_total") or 0)
    return total


def shelf_public(st: dict) -> list[dict]:
    cap = shelf_capacity(st)
    if not cap:
        return []
    keys = ("slot", "prop_id", "name", "category", "rarity", "family", "scanned_at",
            "barcode", "relic_name", "variant")          # S13: 뒤 셋은 덧붙임(계약 앞 일곱은 그대로)
    out = []
    for it in (st.get("shelf") or []):
        if int(it.get("slot", 0)) + prop_width(it.get("prop_id", "")) > cap:
            continue
        row = {k: it.get(k) for k in keys}
        row["card_id"] = it.get("card_id")             # S19-A2: 선반 물건을 고를 때(arc.ask relic·/api/give relic_id)
        row["display_name"] = it.get("relic_name") or it.get("name")   # S31 r8-2: 물건 이름(문어 줄과 같은 이름). name 은 소품 이름
        row["subtype"] = shelf_subtype(it)
        lv = polish_level(it)
        row["polish"] = lv
        row["polish_label"] = moment(f"shelf.levels.{lv}.label")
        row["polish_value_mult"] = polish_value_mult(lv)
        out.append(row)
    return out


def shelf_subtype(it: dict) -> str | None:
    """선반 물건의 줄기 종류. 바코드가 있으면 같은 유물을 다시 만들어 읽는다(D6). 없으면 None."""
    if it.get("subtype"):
        return it["subtype"]
    bc = it.get("barcode")
    if not bc:
        return None
    try:
        return GEN.generate(bc, user_category=it.get("category")).subtype or None
    except ValueError:
        return None


def shelf_place(st: dict, card: dict) -> int | None:
    """스캔한 물건 하나를 선반의 빈 칸에 놓는다. 놓인 칸 번호, 자리가 없으면 None.
    같은 카테고리를 여러 번 찍으면 소품 넷을 돌아가며 쓴다(relic_props._for_dev)."""
    cap = shelf_capacity(st)
    if not cap:
        return None
    shelf = st.setdefault("shelf", [])
    cat = card.get("category") or "unknown"
    pool = _PROPS.get(cat) or _PROPS.get("unknown") or []
    if not pool:
        return None
    used = set()
    for it in shelf:
        for c in range(int(it["slot"]), int(it["slot"]) + prop_width(it["prop_id"])):
            used.add(c)
    n_same = sum(1 for it in shelf if it.get("category") == cat)
    order = [pool[(n_same + i) % len(pool)] for i in range(len(pool))]   # 돌아가며, 안 맞으면 다음 것
    for prop in order:
        w = prop_width(prop["id"])
        for start in range(0, cap - w + 1):
            if all(c not in used for c in range(start, start + w)):
                shelf.append({"slot": start, "prop_id": prop["id"], "name": prop.get("name"),
                              "category": cat, "rarity": card.get("rarity"),
                              "family": card.get("family_name") or None,
                              "scanned_at": time.time(), "card_id": card.get("id"),
                              # S13 닦기·변형: 같은 바코드는 이 칸 하나를 키운다(새 칸을 먹지 않는다)
                              "barcode": card.get("barcode"), "relic_name": card.get("name"),
                              "polish": 1, "polish_scans": 0, "placed_day": card.get("_day"),
                              "variant": "sea" if card.get("sea_variant") else None})
                return start
    return None


def shelf_remove_card(st: dict, card_id: str | None) -> None:
    if card_id:
        st["shelf"] = [it for it in (st.get("shelf") or []) if it.get("card_id") != card_id]


# ─────────────────────────────────────────────────────────────
# S13-A 이해관계·수집 (docs/reports/review_fun_collection_20261003.md 추천 1~4, 사용자 승인)
#   수치 정본: data/balance/stakes.json (기획 소유) — 여기에는 숫자를 두지 않는다.
#   화면 문장: data/ui_moments.json (시나리오 소유) — GET /api/text/moments 로 그대로 내보낸다.
#   계약: docs/API_S13.md
# ─────────────────────────────────────────────────────────────
# 파일이 없거나 키가 빠졌을 때만 쓰는 안전값. **정본이 아니다**(TODO: stakes.json 이 항상 있으면 지운다).
# 값은 stakes.json 1차 값과 같게 두어, 파일이 깨져도 게임의 성격이 바뀌지 않게 한다.
_STAKES_SAFE = {
    "staffing": {"staff_mult": [0.5, 1.0, 1.35, 1.6, 1.8]},
    "crack": {"prod_mult": 0.7, "room_base_penalty": -0.5, "repair_cost": {"cloth": 1, "med": 1}, "stacks": False},
    "lid": {"reveal_target": True, "reveal_from_stage": "silhouette"},
    "night_judge": {"hour": 21, "worst_result": "scarred", "reward_mult": 1.0},
    "polish": {"scans_per_level": [3, 5], "value_mult": [1.0, 1.25, 1.5], "max_level": 3, "per_barcode_per_day": 1},
    "variant": {"rate": 0.03125, "seed_rule": "barcode+isoweek"},
    "family_sets": {"pieces_required": 3, "reward": {"lore_piece": 1, "decor": 1, "morale": 2}},
    "category_lock": True,
    "spot_unlock": {"count_distinct_barcodes": True},
    # S14 능력치 생산. 정본은 stakes.json stat_production(기획). 이 값은 파일·키가 없을 때만 쓴다(TODO 지울 것)
    "stat_production": {
        "room_stat": {"workshop": "hand", "generator": "hand", "storage": "hand", "pantry": "hand", "infirmary": "hand",
                      "well": "breath", "greenhouse": "breath", "airlock": "breath", "quarters": "breath", "bath": "breath",
                      "decoder": "eye", "library": "eye", "lounge": "eye", "hall": "eye"},
        "center": 5, "per_point": 0.05, "min_mult": 0.85, "max_mult": 1.2,
        "aggregate": "mean", "best_plus_others": 0.5,
        "role_bonus_in_room_only": True, "injured_counts": False,
    },
}
_STAKES_CACHE: dict = {"mtime": "unset", "data": {}}


def stakes() -> dict:
    """stakes.json 을 읽는다(파일이 바뀌면 재시작 없이 반영 — 기획이 아직 다듬는 중). 없으면 안전값."""
    p = ROOT / "data" / "balance" / "stakes.json"
    try:
        mtime = p.stat().st_mtime
    except OSError:
        mtime = None
    if mtime != _STAKES_CACHE["mtime"]:
        data = {}
        if mtime is not None:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                # 기획이 쓰는 도중이면 잠깐 깨져 있을 수 있다 → 마지막으로 읽힌 값을 지킨다(없을 때만 안전값)
                data = _STAKES_CACHE.get("data") or {}
                print(f"[stakes] stakes.json 을 읽지 못했다 → {'직전 값' if data else '안전값'}으로 돈다: {e}")
        else:
            print("[stakes] data/balance/stakes.json 없음 → 안전값(TODO 기획)")
        _STAKES_CACHE.update({"mtime": mtime, "data": data})
    return _STAKES_CACHE["data"]


def stk(path: str):
    """'crack.prod_mult' 같은 경로. 파일 값이 이기고, 없으면 안전값."""
    for src in (stakes(), _STAKES_SAFE):
        cur = src
        ok = True
        for k in path.split("."):
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                ok = False
                break
        if ok:
            return cur
    return None


# ── 화면 문장(data/ui_moments.json) ─────────────────────────────
_MOMENTS_CACHE: dict = {"mtime": "unset", "data": {}}


def moments() -> dict:
    p = ROOT / "data" / "ui_moments.json"
    try:
        mtime = p.stat().st_mtime
    except OSError:
        mtime = None
    if mtime != _MOMENTS_CACHE["mtime"]:
        data = {}
        if mtime is not None:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                print(f"[moments] ui_moments.json 무시: {e}")
        _MOMENTS_CACHE.update({"mtime": mtime, "data": data})
    return _MOMENTS_CACHE["data"]


def moment(key: str, **vars) -> str | None:
    """'family_set.complete.8801043' 같은 키의 문장(중첩·점 섞인 키 둘 다 받는다). 치환자는 {name} 꼴."""
    cur = moments()
    parts = key.split(".")
    i = 0
    while i < len(parts) and isinstance(cur, dict):
        for j in range(len(parts), i, -1):            # 가장 긴 키부터 — "complete.8801043" 처럼 점이 든 키도 받는다
            k = ".".join(parts[i:j])
            if k in cur:
                cur, i = cur[k], j
                break
        else:
            return None
    if i < len(parts) or not isinstance(cur, str):
        return None
    for k, v in vars.items():
        cur = cur.replace("{" + k + "}", str(v))
    return cur


# ── 일지(하루 마감이 읽는 '오늘 바뀐 것') ─────────────────────────
DAY_LOG_KEEP = 7


def day_note(st: dict, kind: str, value) -> None:
    log_ = st.setdefault("day_log", {})
    d = str(day_of(st))
    row = log_.setdefault(d, {})
    row.setdefault(kind, []).append(value)
    for k in sorted(log_, key=lambda x: int(x))[:-DAY_LOG_KEEP]:
        log_.pop(k, None)


# ── 배치 = 생산 (staffing) · 금 (crack) ──────────────────────────
def staff_mult(n: int) -> float:
    arr = stk("staffing.staff_mult") or [1.0]
    return float(arr[max(0, min(int(n), len(arr) - 1))])


def staff_people(st: dict, slot) -> list[dict]:
    """그 방에 서 있는 사람(밖에 나간 사람 제외). stakes stat_production.injured_counts 가 거짓이면 부상자는 빠진다
    — 머릿수(staff_mult)에서도 능력치에서도 역할 보정에서도. 전투 판정의 사람 목록과는 별개다."""
    ppl = list(stations_map(st).get(int(slot), []))
    if not stk("stat_production.injured_counts"):
        ppl = [p for p in ppl if not p.get("injured")]
    return ppl


def staff_counts(st: dict) -> dict:
    return {str(k): len(v) for k, v in stations_map(st).items()}


def staff_ids(st: dict) -> dict:
    return {str(k): [p["id"] for p in v] for k, v in stations_map(st).items()}


def staff_snapshot_active(st: dict) -> dict | None:
    """stakes staffing.measure == contact_snapshot: 습격 접촉 순간의 배치가 **그 틱**의 생산을 정한다.
    (옮겨서 막고 바로 되돌리면 비용이 0 이 되던 구멍 — design_stakes §7.) 아직 정산되지 않은 그 틱에만 산다."""
    snap = st.get("staff_snapshot")
    if not isinstance(snap, dict) or stk("staffing.measure") != "contact_snapshot":
        return None
    return snap if float(snap.get("tick_start", -1)) >= float(st.get("last_tick", 0)) else None


def take_staff_snapshot(st: dict) -> None:
    """S14: 머릿수만이 아니라 **누가** 서 있었는지(id)를 남긴다 — 능력치·역할 보정도 같은 순간 배치로 센다."""
    if stk("staffing.measure") == "contact_snapshot":
        lt = float(st.get("last_tick") or time.time())
        start = lt + int(max(0.0, time.time() - lt) // PRODUCTION_TICK_SEC) * PRODUCTION_TICK_SEC   # 지금이 든 틱
        st["staff_snapshot"] = {"tick_start": start, "counts": staff_counts(st), "ids": staff_ids(st),
                                "at": time.time()}


def snapshot_people(st: dict, snap: dict | None, slot) -> list[dict] | None:
    """스냅숏의 그 방 사람들(스탯·부상은 지금 값). 옛 스냅숏(counts 만)이거나 스냅숏이 없으면 None."""
    if not snap or not isinstance(snap.get("ids"), dict):
        return None
    ids = snap["ids"].get(str(int(slot))) or []
    by = {r["id"]: r for r in st.get("residents_list") or []}
    ppl = [by[i] for i in ids if i in by]
    if not stk("stat_production.injured_counts"):
        ppl = [p for p in ppl if not p.get("injured")]
    return ppl


# ── S14 능력치 생산 (stakes.json stat_production) ─────────────────
#   stat_mult = clamp(1 + per_point × A, min_mult, max_mult), d_i = (그 사람의 방 능력치) − center
#     aggregate "mean"       : A = 평균(d_i)
#     aggregate "sum_excess" : A = 합(d_i)
#     aggregate "best_plus"  : A = 최대(d_i) + best_plus_others × 합(나머지 사람의 max(0, d_i))
#   사람이 없으면 1.0(빈 방 값은 staff_mult[0] 이 이미 낸다).
def stat_production_params() -> dict:
    sp = stk("stat_production") or {}
    d = _STAKES_SAFE["stat_production"]
    return {k: (sp.get(k) if sp.get(k) is not None else d.get(k))
            for k in ("center", "per_point", "min_mult", "max_mult", "aggregate", "best_plus_others",
                      "role_bonus_in_room_only", "injured_counts")}


def room_stat_of(rid: str) -> str | None:
    v = (stk("stat_production.room_stat") or {}).get(rid)
    return v if v in STAT_KEYS else None


def stat_factor(people: list[dict], stat: str | None) -> tuple[float, list[dict]]:
    if not people or not stat:
        return 1.0, [{"id": p["id"], "name": p.get("name"), "stat": stat, "value": None, "d": 0, "v": 0.0}
                     for p in people]
    g = stat_production_params()
    center, pp = float(g["center"]), float(g["per_point"])
    lo, hi = float(g["min_mult"]), float(g["max_mult"])
    agg = str(g["aggregate"] or "mean")
    ds = [(p, int((p.get("stats") or {}).get(stat, center)) - center) for p in people]
    contrib: dict = {}
    if agg == "sum_excess":
        for p, d in ds:
            contrib[p["id"]] = pp * d
    elif agg == "best_plus":
        best = max(ds, key=lambda x: x[1])[0]["id"]
        ow = float(g["best_plus_others"] if g["best_plus_others"] is not None else 0.5)
        for p, d in ds:
            contrib[p["id"]] = pp * d if p["id"] == best else pp * ow * max(0.0, d)
    else:                                              # mean
        for p, d in ds:
            contrib[p["id"]] = pp * d / len(ds)
    f = max(lo, min(hi, 1.0 + sum(contrib.values())))
    per = [{"id": p["id"], "name": p.get("name"), "stat": stat,
            "value": int((p.get("stats") or {}).get(stat, center)), "d": d, "v": round(contrib[p["id"]], 4)}
           for p, d in ds]
    return round(f, 4), per


def resident_room_bonus(r: dict) -> dict:
    """그 사람이 가진 방 보정(역할 effects.room_bonus + 각인 effect/cost 의 room_bonus). 부상자는 없다(role_effects 와 같다)."""
    out: dict = {}
    if r.get("injured"):
        return out
    srcs = [((ROLES.get(r.get("role")) or {}).get("effects") or {}).get("room_bonus") or {}]
    for imp_id in r.get("imprints") or []:
        imp = IMPRINTS.get(imp_id) or {}
        for src in (imp.get("effect") or {}, (imp.get("cost") or {}).get("effect") or {}):
            if isinstance(src.get("room_bonus"), dict):
                srcs.append(src["room_bonus"])
    for rb in srcs:
        for room, bonus in rb.items():
            if isinstance(bonus, dict):
                for k, v in bonus.items():
                    if isinstance(v, (int, float)):
                        out.setdefault(room, {})[k] = out.get(room, {}).get(k, 0) + v
    return out


def room_bonus_for(st: dict, room: dict, people: list[dict] | None = None, eff: dict | None = None) -> dict:
    """그 방의 역할 보정. stakes stat_production.role_bonus_in_room_only 면 **그 방에 서 있는 사람의 것만**."""
    if not stat_production_params()["role_bonus_in_room_only"]:
        return dict(((eff or role_effects(st))["room_bonus"]).get(room["id"], {}))
    ppl = staff_people(st, room["slot"]) if people is None else people
    out: dict = {}
    for p in ppl:
        for k, v in (resident_room_bonus(p).get(room["id"]) or {}).items():
            out[k] = out.get(k, 0) + v
    return out


def room_mult(st: dict, room: dict, counts: dict | None = None, people: list[dict] | None = None) -> tuple[float, dict]:
    """그 방 생산 배율 = 일손 배율 × 능력치 배율 × 금 배율(불은 정산이 따로 곱한다). 미리보기와 정산이 같은 함수(D2).
    people 을 주면 그 사람들로(접촉 순간 스냅숏). counts 만 주면 옛 스냅숏 — 능력치 1.0."""
    if people is None and counts is not None:
        n, sf, per = int(counts.get(str(room["slot"]), 0)), 1.0, []
    else:
        ppl = staff_people(st, room["slot"]) if people is None else people
        n = len(ppl)
        sf, per = stat_factor(ppl, room_stat_of(room["id"]))
    sm = staff_mult(n)
    cm = float(stk("crack.prod_mult")) if room.get("cracked") else 1.0
    nb = need_bonus_mult(st, room)                    # S19 오늘의 필요를 채운 사람의 방 +10%(그날 하루)
    out_meta = {"staff": n, "staff_mult": sm, "stat": room_stat_of(room["id"]), "stat_mult": sf,
                "per_person": per, "cracked": bool(room.get("cracked")), "crack_mult": cm}
    if nb != 1.0:
        out_meta["need_mult"] = nb
    return sm * sf * cm * nb, out_meta


def room_segments(st: dict, room: dict, snap: dict | None, ticks: int, eff: dict | None = None) -> list:
    """정산 구간 [(틱 수, 배율(불 제외), 역할 보정)]. 접촉한 틱 하나는 스냅숏 사람으로, 나머지는 지금 배치로."""
    cur_m = room_mult(st, room)[0]
    cur_b = room_bonus_for(st, room, eff=eff)
    if not snap or ticks <= 0:
        return [(ticks, cur_m, cur_b)]
    sp = snapshot_people(st, snap, room["slot"])
    snap_m = room_mult(st, room, counts=snap.get("counts") or {}, people=sp)[0]
    snap_b = room_bonus_for(st, room, people=sp, eff=eff) if sp is not None else cur_b
    segs = [(1, snap_m, snap_b)]
    if ticks > 1:
        segs.append((ticks - 1, cur_m, cur_b))
    return segs


def room_output(st: dict, room: dict, people: list[dict]) -> float:
    """그 방의 한 틱 산출(쌓이는 자원 합 + heal·blueprint 같은 수치형 생산). 미리보기 비교용 한 숫자."""
    m = room_mult(st, room, people=people)[0] * (1.0 if light_on(st, room["slot"]) else 0.5)
    bn = room_bonus_for(st, room, people=people)
    tot = 0.0
    for k, v in room_produces(room).items():
        if isinstance(v, (int, float)) and k not in ("power_supply", "craft_slots"):
            tot += (v + bn.get(k, 0)) * m
    return tot


def move_preview(st: dict) -> dict:
    """S14 드래그 미리보기(PM 결정: 서버가 미리 계산한다). resident_id -> slot(또는 "hall") ->
    {room_delta_pct: 옮겨 간 방 산출 변화 %, from_delta_pct: 떠난 방 산출 변화 %}.
    지금 배치 기준(접촉 스냅숏이 걸린 틱이라도 '다음 틱부터'의 값). 생산하는 방만 숫자가 있고, 아니면 null.
    정원이 찬 방은 can:false. 밖에 나간 사람은 빠진다."""
    outside = set(st.get("outside") or [])
    rooms = [r for r in live_rooms(st)]
    prod = {r["slot"]: bool(room_produces(r)) for r in rooms}
    base_ppl = {r["slot"]: staff_people(st, r["slot"]) for r in rooms}
    all_here = {r["slot"]: list(stations_map(st).get(int(r["slot"]), [])) for r in rooms}
    base_out = {r["slot"]: room_output(st, r, base_ppl[r["slot"]]) for r in rooms if prod[r["slot"]]}
    inj_ok = bool(stat_production_params()["injured_counts"])
    base_total = sum(base_out.values())

    def pct(new, old):
        if old <= 0:
            return None if new <= 0 else 100.0
        return round((new - old) / old * 100.0, 1)

    out: dict = {}
    for p in st.get("residents_list") or []:
        if p["id"] in outside:
            continue
        cur = station_slot(st, p["id"])
        counts = (not p.get("injured")) or inj_ok          # 이 사람이 생산에 세지는가
        row: dict = {}
        from_room = next((r for r in rooms if r["slot"] == cur), None) if cur is not None else None
        from_delta = None
        from_new = None
        if from_room is not None and prod[cur]:
            left = [x for x in base_ppl[cur] if x["id"] != p["id"]]
            from_new = room_output(st, from_room, left) if counts else base_out[cur]
            from_delta = pct(from_new, base_out[cur]) if counts else 0.0
        for r in rooms + [None]:
            slot = r["slot"] if r else None
            key = "hall" if slot is None else str(slot)
            if slot == cur:
                continue
            cell = {"from_delta_pct": from_delta, "room_delta_pct": None, "can": True}
            if r is not None:
                cap = room_cap_of(r)
                if len([x for x in all_here[slot] if x["id"] != p["id"]]) >= cap:
                    cell["can"] = False
                if prod[slot]:
                    newp = base_ppl[slot] + ([p] if counts else [])
                    to_new = room_output(st, r, newp)
                    cell["room_delta_pct"] = pct(to_new, base_out[slot])
            # S18-A2 방주 전체 산출 변화(떠난 방 + 옮겨 간 방, 나머지는 그대로). 화면은 이 한 숫자를 크게 쓴다
            new_total = base_total
            if from_new is not None:
                new_total += from_new - base_out[cur]
            if r is not None and prod[slot]:
                new_total += to_new - base_out[slot]
            cell["ark_delta_pct"] = pct(new_total, base_total) if base_total > 0 else None
            row[key] = cell
        out[p["id"]] = row
    return out


def production_public(st: dict) -> dict:
    out = {}
    for r in live_rooms(st):
        if not room_produces(r):
            continue                                  # 생산하는 방만(stakes staffing.applies_to)
        snap = staff_snapshot_active(st)
        sp = snapshot_people(st, snap, r["slot"]) if snap else None
        m, info = room_mult(st, r, (snap.get("counts") or {}) if snap else None, people=sp)
        name = (ROOMS.get(r["id"]) or {}).get("name", r["id"])
        info.update({"room_id": r["id"], "mult": round(m, 3), "snapshot": bool(snap),
                     "role_bonus": room_bonus_for(st, r, people=sp)})
        if snap:
            # 이번 틱은 접촉 순간 배치로 이미 정해졌다. 다음 틱부터는 지금 배치(now_mult)
            nm, ninfo = room_mult(st, r)
            info["now_mult"] = round(nm, 3)
            info["now_stat_mult"] = ninfo["stat_mult"]
        if info["staff"] == 0:
            info["label"] = moment("staffing.label")
            info["ko"] = moment("staffing.reduced", room=name)
        if info["cracked"]:
            info["crack_label"] = moment("crack.label_cracked")
            info["crack_ko"] = moment("crack.still_cracked", room=name)
        out[str(r["slot"])] = info
    return out


def crack_room(st: dict, room: dict) -> bool:
    """금. 이미 금 간 방은 더 나빠지지 않는다(stakes crack.stacks=false). 새로 금 갔으면 True."""
    if room.get("cracked") and not stk("crack.stacks"):
        return False
    room["cracked"] = True
    room["cracked_day"] = day_of(st)
    return True


# ── 변형(바다 무늬) ───────────────────────────────────────────
def iso_week(ts: float | None = None) -> str:
    y, w, _ = datetime.fromtimestamp(ts if ts is not None else time.time()).isocalendar()
    return f"{y}-W{w:02d}"


def sea_variant(code: str, ts: float | None = None) -> dict:
    """같은 주·같은 바코드 = 전 세계 같은 결과(D6). 수치 가치는 없다 — 표시만."""
    import hashlib
    week = iso_week(ts)
    rule = str(stk("variant.seed_rule") or "barcode+isoweek")
    key = f"{code}:{week}" if rule == "barcode+isoweek" else code
    h = int(hashlib.sha256(f"VARIANT|{key}".encode()).hexdigest()[:8], 16) / 2 ** 32
    shiny = h < float(stk("variant.rate") or 0)
    return {"id": "sea" if shiny else None, "shiny": shiny, "week": week,
            "label": moment("variant.label") if shiny else None}


# ── 닦기(polish) ──────────────────────────────────────────────
def polish_level(it: dict) -> int:
    try:
        return max(1, min(int(stk("polish.max_level")), int(it.get("polish") or 1)))
    except (TypeError, ValueError):
        return 1


def polish_value_mult(lv: int) -> float:
    arr = stk("polish.value_mult") or [1.0]
    return float(arr[max(0, min(lv - 1, len(arr) - 1))])


def polish_threshold(lv: int) -> int | None:
    """lv 에서 lv+1 로 가는 누적 재스캔 수. 최대면 None."""
    arr = list(stk("polish.scans_per_level") or [])
    if lv >= int(stk("polish.max_level")) or lv - 1 >= len(arr):
        return None
    return int(sum(arr[:lv]))


def shelf_item_for(st: dict, code: str) -> dict | None:
    """선반 또는 창고 상자에 이미 있는 그 바코드(있으면 새로 놓지 않고 닦는다)."""
    return next((it for it in (st.get("shelf") or []) + (st.get("stored") or []) if it.get("barcode") == code), None)


def polish_item(st: dict, it: dict, card_name: str) -> dict:
    """선반에 이미 있는 바코드를 다시 찍었다 — 새 칸 대신 그 물건을 닦는다. 하루 한 번만 센다."""
    day = day_of(st)
    prev = polish_level(it)
    counted = False
    per_day = int(stk("polish.per_barcode_per_day") or 1)
    if it.get("polish_day") != day:                   # 날이 바뀌었다 — 오늘 몫을 새로 센다
        it["polish_day"] = day
        it["polish_today"] = 0
    # 놓인 날(placed_day)에는 닦지 않는다: '다른 날' 다시 찍어야 한다(stakes polish._rule)
    if it.get("placed_day") != day and int(it.get("polish_today") or 0) < per_day:
        it["polish_today"] = int(it.get("polish_today") or 0) + 1
        it["polish_scans"] = int(it.get("polish_scans") or 0) + 1
        counted = True
    lv = prev
    while True:
        need = polish_threshold(lv)
        if need is None or int(it.get("polish_scans") or 0) < need:
            break
        lv += 1
    it["polish"] = lv
    nxt = polish_threshold(lv)
    at_max = nxt is None
    return {"barcode": it.get("barcode"), "slot": it.get("slot"), "level": lv, "prev_level": prev,
            "leveled_up": lv > prev, "scans": int(it.get("polish_scans") or 0), "next_at": nxt,
            "max": int(stk("polish.max_level")), "counted_today": counted, "value_mult": polish_value_mult(lv),
            "label": moment(f"shelf.levels.{lv}.label"), "line": moment(f"shelf.levels.{lv}.line"),
            # 같은 날 두 번째(세지 않은) 재스캔에는 '닦았다'고 말하지 않는다 — 거짓 문장이 된다
            "ko": (moment("shelf.rescan_max", item=card_name) if (at_max and lv == prev)
                   else moment("shelf.rescan", item=card_name) if counted else None)}


# ── 가문 세트 · 첫 만남 ────────────────────────────────────────
FAMILY_LORE = ((_load_json("family_lore.json") or {}).get("families") or {})
FAMILY_NAMES = {k: v for k, v in (_load_json("family_names.json") or {}).items()
                if not k.startswith("_") and isinstance(v, dict)}
FIRST_MEET = _load_json("first_meet.json") or {}
_KNOWN_FAM_CAT = {k: (v or {}).get("category") for k, v in GEN.families.items()
                  if not k.startswith("_") and isinstance(v, dict)}     # 카테고리만. 실제 이름은 쓰지 않는다


def family_have(uid: str, code: str) -> int:
    with db() as con:
        return con.execute("SELECT COUNT(DISTINCT barcode) c FROM scans WHERE uid=? AND substr(barcode,1,7)=?",
                           (uid, code)).fetchone()["c"]


def family_set_state(st: dict, uid: str, code: str) -> dict | None:
    if code not in FAMILY_NAMES:
        return None
    total = int(stk("family_sets.pieces_required"))
    have = family_have(uid, code)
    name = FAMILY_NAMES[code].get("name")
    done = code in (st.get("family_sets") or {})
    return {"code": code, "name": name, "have": min(have, total), "total": total, "completed": done}


def family_set_check(st: dict, uid: str, code: str) -> dict | None:
    """스캔 직후. 문턱을 처음 넘으면 완성 보상(이야기·장식·사기)을 한 번 준다."""
    fs = family_set_state(st, uid, code)
    if not fs:
        return None
    fs["just_completed"] = False
    fs["reward"] = None
    if not fs["completed"] and fs["have"] >= fs["total"]:
        rw = dict(stk("family_sets.reward") or {})
        if _KNOWN_FAM_CAT.get(code) in SAFE_EXCLUDE_CATS:
            rw = {}                                   # S24: 담배 가문은 한 벌이 돼도 보상이 없다(완성 표시만)
        lore = FAMILY_LORE.get(code) or {}
        st.setdefault("family_sets", {})[code] = {"day": day_of(st), "decor": lore.get("decor")}
        mor = int(rw.get("morale") or 0)
        if mor:
            st["resources"]["morale"] = int(st["resources"].get("morale", 0)) + mor
        fs.update({"completed": True, "just_completed": True,
                   "reward": {"story": lore.get("story") if rw.get("lore_piece") else None,
                              "decor": lore.get("decor") if rw.get("decor") else None, "morale": mor}})
        fs["ko"] = moment(f"family_set.complete.{code}") or moment("family_set.complete_default", family=fs["name"])
        day_note(st, "family_set", fs["name"])
    elif fs["completed"]:
        fs["ko"] = None
    elif fs["total"] - fs["have"] == 1:
        fs["ko"] = moment("family_set.one_left", family=fs["name"])
    else:
        fs["ko"] = moment("family_set.progress", family=fs["name"], n=fs["have"], total=fs["total"])
    return fs


def first_meet_lines(st: dict, cat: str, fam: str) -> list[dict]:
    out = []
    seen_f = st.setdefault("seen_families", [])
    seen_c = st.setdefault("seen_categories", [])
    if fam in FAMILY_NAMES and fam not in seen_f:
        seen_f.append(fam)
        fm = (FIRST_MEET.get("families") or {}).get(fam) or {}
        if fm.get("line"):
            out.append({"kind": "family", "key": fam, "line": fm["line"], "line_short": fm.get("line_short")})
    if cat not in seen_c:
        seen_c.append(cat)
        fm = (FIRST_MEET.get("categories") or {}).get(cat) or {}
        if fm.get("line"):
            out.append({"kind": "category", "key": cat, "line": fm["line"], "line_short": fm.get("line_short")})
    return out


# ── 도감 메타(줄기별 희귀도·변형) ─────────────────────────────
def codex_pool(cat: str) -> list:
    """도감 칸 = relic_templates 줄기 + 시나리오 추가 줄기(relic_stems.json). 추가 줄기는 이름이 겹치지 않는 것만."""
    base = list(TEMPLATES.get(cat) or [])
    names = {t["name"] for t in base}
    more = ((GEN.extra().get("categories") or {}).get(cat)) or []
    return base + [t for t in more if isinstance(t, dict) and t.get("name") and t["name"] not in names]


def stem_of(cat: str, name: str) -> str | None:
    for t in codex_pool(cat):
        s = t["name"].replace("{adj} ", "")
        if name.endswith(s):
            return s
    return None


def codex_note(st: dict, cat: str, name: str, rarity: str, variant: bool) -> None:
    s = stem_of(cat, name)
    if not s:
        return
    row = st.setdefault("codex_meta", {}).setdefault(cat, {}).setdefault(s, {"rarities": [], "variant": False})
    if rarity not in row["rarities"]:
        row["rarities"].append(rarity)
    row["variant"] = bool(row.get("variant") or variant)
    row["name"] = name


def ensure_codex_meta(st: dict, uid: str) -> bool:
    """구버전 방주: 희귀도 기록이 없으면 scans 표의 (바코드, 카테고리)로 다시 만들어 채운다(같은 바코드 = 같은 유물)."""
    if isinstance(st.get("codex_meta"), dict):
        return False
    st["codex_meta"] = {}
    with db() as con:
        rows = con.execute("SELECT DISTINCT barcode, category FROM scans WHERE uid=?", (uid,)).fetchall()
    for r in rows:
        try:
            c = GEN.generate(r["barcode"], user_category=r["category"])
        except ValueError:
            continue
        codex_note(st, c.category.value, c.name, c.rarity.value, False)
    return True


RARITY_KEYS = ("common", "uncommon", "rare", "epic", "legendary")
REPAIR_PATCH_TOOL = next((t for t, v in combat.TOOLS.items() if v.get("heals_crack")), None)   # 봉합 패치


# ── 문어(동거 짐승) ───────────────────────────────────────────
OCTOPUS = _load_json("companion_octopus.json") or {}


def octopus_tick(st: dict, uid: str) -> dict | None:
    """첫 등장(arrival.day)부터 하루 선물 하나. 전날 찍은 카테고리와 맞는 것에 가중치(data _for_dev 권장식)."""
    arr = OCTOPUS.get("arrival") or {}
    day = day_of(st)
    if not arr or day < int(arr.get("day") or 1):
        return None
    oc = st.setdefault("octopus", {"arrived_day": day, "name": None, "finds": {}, "gift_day": None})
    out: dict = {}
    if not oc.get("arrival_shown"):
        oc["arrival_shown"] = True
        out["arrival"] = {"beats": arr.get("beats") or [], "closing": arr.get("closing"), "where": arr.get("where")}
    finds = [f for f in (OCTOPUS.get("finds") or []) if isinstance(f, dict) and f.get("id")]
    if finds and oc.get("gift_day") != day:
        with db() as con:
            rows = con.execute("SELECT DISTINCT category FROM scans WHERE uid=? AND day=?", (uid, day - 1)).fetchall()
        fav = {r["category"] for r in rows}
        weights = [1 + (int(f.get("weight") or 0) if f.get("favor_category") in fav else 0) for f in finds]
        pick = random.Random(f"{uid}|{day}|octopus_gift").choices(finds, weights=weights, k=1)[0]
        if beat_today_id(st) == "octopus_story_gift":       # S19 비트 5: 처음 보는 색 조각(누군가의 사슬에 닿는 것)
            story = [f for f in finds if f.get("kind") == "spot_clue" and not int((oc.get("finds") or {}).get(f["id"], 0))]
            story.sort(key=lambda f: (f["id"] != "oct_color_chip", f["id"]))
            if story:
                pick = story[0]
        oc["gift_day"] = day
        gr = guaranteed_rare_due(st)
        if gr:                                        # S30: 첫 주 귀함 하나 보장(B — 띄엄띄엄 켜는 사람의 빈 가보 칸)
            safe_f = [f for f in finds if f.get("favor_category") in EX.CATS and f.get("kind") == "relic_shard"
                      and item_safe({"category": f.get("favor_category"), "subtype": None})]   # 담배·약(붕대 밖)은 가보가 될 수 없다
            liked = {x.get("category") for r_ in st.get("residents_list") or []
                     for x in likes_of(uid, r_) + list(role_taste(r_.get("role", "")).get("needs") or []) if isinstance(x, dict)}
            safe_f = [f for f in safe_f if f.get("favor_category") in liked] or safe_f   # S31 r8-1: 누군가 반가워할 갈래로
            if safe_f and (pick not in safe_f):
                pick = random.Random(f"{uid}|{day}|guaranteed_rare").choice(safe_f)   # S31 r8-1: 담배 조각은 가보가 될 수 없다
                oc["gift_today"] = pick["id"]
            oc["gift_relic"] = octopus_gift_relic(st, pick, day)
            core_of(st)["flags"]["guaranteed_rare_day"] = day
            first_rare_tick(st, {"rarity": "rare"})
            core_of(st)["flags"]["heir_open_day"] = day
            G = (moments().get("guaranteed_rare") or {}).get("octopus") or []
            t, _ = _rot(st, "guaranteed_rare.octopus", G)
            oc["guaranteed_ko"] = (t or "문어가 「{item}」 하나를 물어 왔습니다.").replace("{item}", pick.get("name") or "") \
                .replace("{oct_name}", oc.get("name") or "문어")
            out["guaranteed_rare"] = {"item": pick.get("name"), "ko": oc["guaranteed_ko"], "card_id": oc["gift_relic"]["card_id"]}
            overnight_add(st, "guaranteed_rare", out["guaranteed_rare"])
        elif beat_today_id(st) == "octopus_story_gift":
            oc["gift_relic"] = octopus_gift_relic(st, pick, day)   # S21: 그 조각을 「어디로」로 건넬 수 있는 물건으로
        oc.setdefault("finds", {})[pick["id"]] = int(oc["finds"].get(pick["id"], 0)) + 1
        oc["gift_today"] = pick["id"]
        day_note(st, "octopus", pick["name"])
        out["gift"] = pick
    return out


def octopus_public(st: dict) -> dict:
    oc = st.get("octopus")
    if not oc:
        return {"arrived": False}
    moods = OCTOPUS.get("moods") or []
    # TODO(기획): 기분 단계 규칙 수치가 아직 없다. 임시 = 첫 단계 + 이름을 지었으면 +1 + 함께 지낸 주(週)마다 +1.
    days = max(0, day_of(st) - int(oc.get("arrived_day") or day_of(st)))
    stage = 1 + (1 if oc.get("name") else 0) + days // 7
    mood = moods[max(0, min(stage, len(moods)) - 1)] if moods else None
    g = next((f for f in (OCTOPUS.get("finds") or []) if f.get("id") == oc.get("gift_today")), None)
    gift = None
    if g and oc.get("gift_day") == day_of(st):
        gift = {"id": g["id"], "name": g["name"], "line": role_text(g, "line", st), "kind": g.get("kind"),
                "spot_hint": g.get("spot_hint"), "label": moment("octopus_gift.label"),
                "ko": moment("octopus_gift.pop", item=g["name"])}
    return {"arrived": True, "name": oc.get("name"), "arrived_day": oc.get("arrived_day"),
            "mood": ({k: mood.get(k) for k in ("id", "ko", "stage", "line", "tell")} if mood else None),
            "gift_today": gift, "finds_count": sum(int(v) for v in (oc.get("finds") or {}).values())}


# ── 주민 바람(wishes) ─────────────────────────────────────────
WISHES = [w for w in ((_load_json("wishes.json") or {}).get("wishes") or []) if isinstance(w, dict) and w.get("id")]


def wish_progress(st: dict, uid: str, w: dict, resident: dict) -> tuple[bool, dict | None]:
    """data 의 condition.hint 를 판정식으로 읽는다(정본은 개발 — wishes.json _for_dev). 아는 키만 본다."""
    h = (w.get("condition") or {}).get("hint") or {}
    hand = st.get("hand") or []
    rooms = {r["id"] for r in live_rooms(st)}
    if h.get("room_feature") == "window":
        # 창이 있는 방 = 전망 라운지. 이 주민이 거기 서 있어야 한다(assign: self)
        slot = station_slot(st, resident["id"])
        r = room_at(st, slot) if slot is not None else None
        return bool(r and r.get("id") == "lounge" and not r.get("flooded")), None
    if h.get("props_category"):
        need = int(h.get("count") or 1)
        have = sum(1 for it in (st.get("shelf") or []) if it.get("category") == h["props_category"])
        return have >= need, {"have": min(have, need), "need": need}
    if h.get("category") and h.get("room"):
        return (h["room"] in rooms and any(c.get("category") == h["category"] for c in hand)), None
    if h.get("spot") or h.get("or_spot") or h.get("octopus_find"):
        ok = any(spot_found(st, uid, s) for s in (h.get("spot"), h.get("or_spot")) if s)
        if h.get("octopus_find") and int(((st.get("octopus") or {}).get("finds") or {}).get(h["octopus_find"], 0)) > 0:
            ok = True
        for k, v in (h.get("or_resource") or {}).items():
            if int(st["resources"].get(k, 0)) >= int(v):
                ok = True
        return ok, None
    if h.get("flag") == "survived_together":
        return any(v > 0 for v in (resident.get("trust") or {}).values()), None
    if h.get("family") or h.get("or_tag"):
        ok = bool(h.get("family")) and family_have(uid, h["family"]) > 0
        if h.get("or_tag") and any(h["or_tag"] in (c.get("tags") or []) for c in hand):
            ok = True
        return ok, None
    return False, None


def wishes_public(st: dict, uid: str) -> list[dict]:
    done = st.get("wishes_done") or {}
    out = []
    for r in st.get("residents_list") or []:
        for w in WISHES:
            if w.get("role") != r.get("role"):
                continue
            d = done.get(w["id"])
            # S19: 진척 = 그 바람을 잇는 사슬의 매듭(저절로 이뤄지지 않는다)
            arc = next((a for a in ARCS if a.get("wish_id") == w["id"]), None)
            prog = None
            if arc and not d:
                s_ = arc_state(st, r["id"], arc["id"])
                prog = {"have": int(s_["step"]), "need": len(arc["beats"]), "arc_id": arc["id"]}
            out.append({"id": w["id"], "resident_id": r["id"], "name": r["name"], "role": r["role"],
                        "wish": w.get("wish"), "condition": (w.get("condition") or {}).get("text"),
                        "done": bool(d), "done_day": (d or {}).get("day"),
                        "line": (w.get("line_after") if d else w.get("line_before") or "").replace("{name}", r["name"]),
                        "beast_beat": w.get("beast_beat") if d else None, "progress": prog})
    return out


def wishes_tick(st: dict, uid: str) -> list[dict]:
    """S19: 바람은 **저절로 이뤄지지 않는다**(CORE_LOOP_A §4). 사슬 끝 매듭이 풀릴 때 fire_beat 가 wishes_done 에 적고
    여기서 한 번 내보낸다(이번에 이뤄진 것만)."""
    c = core_of(st)
    new, c["wish_new"] = list(c["wish_new"]), []
    return new


# ── 밤 자동 판정 ──────────────────────────────────────────────
_RESULT_RANK = {"held": 0, "passed": 0, "scarred": 1, "breached": 2}


def night_deadline(started: float) -> float:
    """습격을 처음 본 시각 다음에 오는 night_judge.hour 정각."""
    hour = int(stk("night_judge.hour"))
    t = datetime.fromtimestamp(started)
    dl = t.replace(hour=hour, minute=0, second=0, microsecond=0)
    if t >= dl:
        from datetime import timedelta
        dl = dl + timedelta(days=1)
    return dl.timestamp()


def night_judge(st: dict, uid: str, force: bool = False) -> dict | None:
    """접촉을 누르지 않은 오늘(또는 어제)의 습격을 그 시각의 배치 그대로 판정한다. 최악은 worst_result.
    습격은 /api/raid/today 를 연 날에만 생긴다 = 플레이어가 화면에서 봤다(stakes applies_if).
    이미 끝난 습격은 건드리지 않는다(멱등)."""
    raid = st.get("raid")
    if not raid or raid.get("none") or raid.get("resolved"):
        return None
    if _DEV_HOUR.get() is not None:                  # ★ S27 r5-4: 개발 시계가 있으면 그 방주의 시각만 본다(실제 시계 마감 무시)
        h = now_hour()
        due = force or raid.get("day") != day_of(st) or h >= int(stk("night_judge.hour")) or h < NIGHT_END
    else:
        due = force or raid.get("day") != day_of(st) or time.time() >= night_deadline(float(raid.get("started") or time.time()))
    if not due:
        return None
    # 상한은 데이터만 정한다. 값이 없거나(null) 엔진 결과 이름이 아니면 상한 없음 = 누른 것과 같은 결과
    # (사용자 결정 2026-10-03: worst_result = "breached" → 상한이 걸리지 않는다)
    cap = stk("night_judge.worst_result")
    cap = cap if cap in _RESULT_RANK else None
    out = resolve_raid(st, uid, raid, [], cap=cap, auto=True)
    cre = combat.CREATURES.get(raid["creature"]) or {}
    room = out.get("room_name") or ""
    key = {"held": "night_judge.blocked", "passed": "night_judge.passed",
           "scarred": "night_judge.cracked", "breached": "night_judge.lost"}.get(out["result"])
    ko = moment(key, creature=cre.get("name", ""), room=room) if key else None
    return {"raid_id": raid.get("id"), "creature": cre.get("name"), "creature_id": raid.get("creature"),
            "result": out["result"], "result_ko": out["result_ko"], "capped": bool(out.get("capped")),
            "room": room, "gained": out.get("gained"), "lost_room": out.get("lost_room"),
            "ko": ko or out.get("line"), "key": key}


def far_call_note(st: dict) -> None:
    """먼 울음 간격을 날마다 적어 둔다(하루 마감 cry_shorter 가 어제와 비교한다)."""
    fl = st.setdefault("far_call_log", {})
    fl[str(day_of(st))] = gauges_of(st)["far_call_sec"]
    for k in sorted(fl, key=lambda x: int(x))[:-DAY_LOG_KEEP]:
        fl.pop(k, None)


def day_tick(st: dict, uid: str, force_night: bool = False) -> dict:
    """상태를 읽는 요청마다 한 번. 원정 귀환·두드림(S15) → 밤 판정 → 문어 → 바람 → 울음 기록. 모두 멱등이다.
    원정 귀환을 먼저 정산한다 — 돌아온 사람은 밤 판정에서 집에 있는 사람이다(아직 밖이면 없는 사람)."""
    s15 = s15_tick(st, uid)
    out = {"night_judge": night_judge(st, uid, force=force_night)}
    out.update(s15)
    out["depth_crossed"] = depth_check(st)
    # S18 아침 「밤사이」 한 장: 이번에 생긴 것을 모은다(화면은 overnight 하나만 열면 된다)
    if out["night_judge"]:
        overnight_add(st, "night_judge", out["night_judge"])
    if s15.get("expedition_return"):
        r_ = s15["expedition_return"]
        overnight_add(st, "expedition_return", {"id": r_["id"], "line": r_.get("line"), "member_names": r_.get("member_names"),
                                                "discovered": r_.get("discovered"), "newcomer": r_.get("newcomer"),
                                                "request_hint": r_.get("request_hint")})
    if s15.get("knock"):
        overnight_add(st, "knock", {"guest_id": s15["knock"]["guest_id"], "name": s15["knock"]["name"]})
    out["octopus"] = octopus_tick(st, uid)
    if (out["octopus"] or {}).get("gift"):
        g_ = out["octopus"]["gift"]
        oname = (st.get("octopus") or {}).get("name") or "문어"
        overnight_add(st, "octopus", {"id": g_["id"], "name": g_["name"], "line": role_text(g_, "line", st), "who": oname,
                                      "label": f"{oname}가 물어 온 것" if oname == "문어" else f"{oname}(문어)가 물어 온 것",
                                      "ko": moment("octopus_gift.pop", item=g_["name"]) or f"문어가 「{g_['name']}」 하나를 물어 왔습니다."})
    out["wishes_new"] = wishes_tick(st, uid)
    for w_ in out["wishes_new"]:
        overnight_add(st, "wish", w_)
    far_call_note(st)
    return out


# ── 저장 이전(S13) ────────────────────────────────────────────
def migrate_s13(st: dict, uid: str) -> bool:
    """구버전 방주 보강. 선반 물건의 바코드를 card_id 앞부분에서 되살리고, 옛 중복 칸 버그로 생긴
    같은 바코드 두 번째 칸부터는 걷어 낸다. 바코드 카테고리 고정·첫 만남 기록은 scans 표에서 채운다."""
    changed = False
    shelf = st.get("shelf") if isinstance(st.get("shelf"), list) else []
    seen, keep = set(), []
    for it in shelf:
        if not isinstance(it, dict):
            changed = True
            continue
        if not it.get("barcode"):
            head = str(it.get("card_id") or "").split("-")[0]
            if head.isdigit() and len(head) == 13:
                it["barcode"] = head; changed = True
        if "polish" not in it:
            it["polish"] = 1; it["polish_scans"] = 0; changed = True
        bc = it.get("barcode")
        if bc and bc in seen:
            changed = True                              # 옛 버그의 중복 칸 — 첫 칸만 남긴다
            continue
        if bc:
            seen.add(bc)
        keep.append(it)
    if changed:
        st["shelf"] = keep
    if not isinstance(st.get("barcodes"), dict):
        st["barcodes"] = {}
        with db() as con:
            rows = con.execute("SELECT barcode, category FROM scans WHERE uid=? ORDER BY ts", (uid,)).fetchall()
        for r in rows:
            if r["category"] and r["category"] != "unknown":
                st["barcodes"].setdefault(r["barcode"], {"category": r["category"]})
        changed = True
    if not isinstance(st.get("seen_categories"), list) or not isinstance(st.get("seen_families"), list):
        with db() as con:
            rows = con.execute("SELECT DISTINCT barcode, category FROM scans WHERE uid=?", (uid,)).fetchall()
        st["seen_categories"] = sorted({r["category"] for r in rows if r["category"]})
        st["seen_families"] = sorted({r["barcode"][:7] for r in rows if r["barcode"][:7] in FAMILY_NAMES})
        changed = True
    for r in st.get("rooms") or []:                      # 옛 '잃은 방'(flooded) → 무엇이었는지 기억하는 물 찬 칸
        if r.get("flooded") and not isinstance(r.get("flooded_from"), dict):
            r["flooded_from"] = {"id": r.get("id"), "level": room_level(r)}; changed = True
    if not isinstance(st.get("depth_marks"), list):        # S18: 이미 넘은 깊이는 조용히 넘긴 것으로
        st["depth_marks"] = [m for m in (stk("depth_announce.thresholds") or []) if depth_of(st) >= int(m)]; changed = True
    if not isinstance(st.get("stored"), list):
        st["stored"] = []; changed = True
    if not isinstance(st.get("event_days"), dict):
        st["event_days"] = {}; changed = True
    if "threat_raids" not in st:
        st["threat_raids"] = sum(1 for r in st.get("raid_log") or []
                                 if (combat.CREATURES.get(r.get("creature")) or {}).get("threat")); changed = True
    for key in ("family_sets", "wishes_done", "day_log", "far_call_log"):
        if not isinstance(st.get(key), dict):
            st[key] = {}; changed = True
    return changed


# ─────────────────────────────────────────────────────────────
# S15 원정·문간 (docs/EXPEDITION.md · 계약 docs/API_EXPEDITION.md)
#   수치 정본: data/balance/expedition.json (기획). 결과 굴림: engine/expedition.py (순수 함수, 시드 uid|exp_id)
#   여기서는 상태를 읽어 엔진에 넘기고, 펼친 결과를 상태에 쓴다.
# ─────────────────────────────────────────────────────────────
import math  # noqa: E402
import expedition as EX  # noqa: E402

DEEP_SPOT_IDS = [x["id"] for x in SPOTS if x.get("_src") == "spots_deep.json"]
LEN_ORDER = ("short", "half", "long")


def now_ts() -> float:
    return time.time()


# ── 스팟: 단서와 발견을 나눈다(DECISIONS 2026-10-03 ④) ─────────────
def spot_clue(st: dict, uid: str, sid: str) -> bool:
    """스캔 문턱을 넘었거나(소문) 모르는 쪽 원정에서 우연히 얻은 단서."""
    if sid in (st.get("clues_extra") or []):
        return True
    gate = spot_gate(sid, next((x for x in SPOTS if x.get("id") == sid), None))
    if not gate:
        return False
    counts = scan_counts(uid)
    return sum(counts.get(c, 0) for c in gate["categories"]) >= gate["need"]


def spot_state(st: dict, uid: str, sid: str) -> str:
    if sid in (st.get("spots_found") or []):
        return "found"
    return "clue" if spot_clue(st, uid, sid) else "none"


# ── 공기 ──────────────────────────────────────────────────────
def entrance_people(st: dict) -> list[dict]:
    """문간(=홀)에 있는 사람. 다친 사람은 문간에 오지 않는다(눕는다)."""
    return [r for r in hall_of(st) if not r.get("injured")]


def top_stat(r: dict) -> str:
    s = r.get("stats") or {}
    order = ("hand", "eye", "breath", "nerve")                       # 동률이면 손 > 눈 > 숨 > 담
    return max(order, key=lambda k: (int(s.get(k, 0)), -order.index(k)))


def entrance_activities(st: dict) -> tuple[dict, list[dict]]:
    """활동마다 덤은 한 사람 몫. 밖에 나간 사람과 신뢰가 가장 높은 사람은 문을 보고 기다린다(효과 없음)."""
    ppl = entrance_people(st)
    out_ids = list(st.get("outside") or [])
    waiting = None
    if out_ids and ppl:
        waiting = max(ppl, key=lambda r: (max([int((r.get("trust") or {}).get(o, 0)) for o in out_ids] or [0]), r["id"]))
    acts: dict = {}
    rows = []
    for r in ppl:
        if waiting is not None and r["id"] == waiting["id"]:
            rows.append({"id": r["id"], "name": r["name"], "activity": "waiting", "waiting_for": out_ids[0]})
            continue
        if r.get("role") == "kid":
            rows.append({"id": r["id"], "name": r["name"], "activity": "kid"})
            continue
        a = top_stat(r)
        acts.setdefault(a, r["id"])
        rows.append({"id": r["id"], "name": r["name"], "activity": a,
                     "activity_ko": ((EX.g(f"entrance.idle.activities.{a}") or {}).get("ko"))})
    return acts, rows


def air_supply(st: dict) -> float:
    base = float(EX.g("air.daily_supply_base", 8))
    gh = room_level_of(st, "greenhouse")
    base += float((EX.g("air.greenhouse_bonus") or {}).get(str(gh), 0)) if gh else 0
    acts, _ = entrance_activities(st)
    if "breath" in acts:
        base += float(((EX.g("entrance.idle.activities.breath") or {}).get("effect") or {}).get("air_per_day", 0))
    al = room_level_of(st, "airlock")
    mul = 1.0
    for lv, m in (EX.g("air.airlock_mul") or {}).items():
        if al >= int(lv):
            mul = max(mul, float(m))
    return round(base * mul, 3)


def air_state(st: dict) -> dict:
    a = st.setdefault("air", {})
    sup = air_supply(st)
    if not isinstance(a.get("value"), (int, float)):
        a["value"] = sup
    a["value"] = round(min(float(a["value"]), sup), 3)
    return {"value": a["value"], "supply": sup, "band": round(a["value"] / sup, 4) if sup else 0.0}


def air_refill(st: dict, ticks: int) -> None:
    """생산 틱마다 하루 공급의 1/3. 하루치 이상 쌓이지 않는다(expedition.json air.refill)."""
    if ticks <= 0:
        return
    sup = air_supply(st)
    a = st.setdefault("air", {})
    v = float(a.get("value", sup))
    a["value"] = round(min(sup, v + ticks * sup / 3.0), 3)


# ── 잠수복 ────────────────────────────────────────────────────
def suits_state(st: dict) -> dict:
    n = int(EX.g("entrance.shared_suits", 1)) + (1 if room_level_of(st, "airlock") >= 1 else 0)
    s = st.setdefault("suits", {"shared_wear": []})
    wear = list(s.get("shared_wear") or [])
    wear = (wear + [0] * n)[:n]
    s["shared_wear"] = wear
    lim = int(EX.g("gear.shared_suit_wear_limit", 5))
    usable = sum(1 for w in wear if w < lim)
    return {"total": n, "usable": usable, "wear": wear, "wear_limit": lim, "pair_ok": usable >= 2,
            "repair_cost": dict(EX.g("gear.repair_cost") or {})}


# ── 목적지 ────────────────────────────────────────────────────
def dest_spec(st: dict, uid: str, dest: dict) -> dict:
    """목적지 하나의 사양과 갈 수 있는지. why 가 있으면 못 간다."""
    kind = (dest or {}).get("kind")
    D = EX.g("destinations") or {}
    lens_all = list((EX.g("lengths") or {}).keys()) or list(LEN_ORDER)
    if kind == "door":
        d = D.get("door") or {}
        return {"kind": "door", "ko": d.get("ko", "문 앞 바닥"), "lengths": d.get("lengths") or ["short", "half"],
                "cat": "unknown", "danger_mul": float(d.get("danger_mul", 0.5)), "kinds": None, "why": None}
    if kind == "unknown":
        d = D.get("unknown") or {}
        return {"kind": "unknown", "ko": d.get("ko", "모르는 쪽"), "lengths": d.get("lengths") or ["half", "long"],
                "cat": "*", "danger_mul": float(d.get("danger_mul", 1.3)), "kinds": None, "why": None}
    if kind in ("spot", "clue"):
        sid = (dest or {}).get("id")
        sp = (D.get("spots") or {}).get(sid)
        if not sp:
            return {"kind": kind, "why": "없는 곳입니다", "lengths": []}
        minl = sp.get("min_length", "half")
        week1 = kind == "clue" and minl == "long" and week1_half_ok(st, uid, sid)
        if week1:
            minl = "half"                                # S19: 1주차 단서 하나는 반나절로(에어락·밤 넘기기 없이)
        lens = lens_all[lens_all.index(minl):] if minl in lens_all else lens_all
        name = next((x.get("name") for x in SPOTS if x.get("id") == sid), sid)
        state = spot_state(st, uid, sid)
        why = None
        if kind == "spot" and state != "found":
            why = "아직 찾지 못한 곳입니다"
        if kind == "clue" and state != "clue":
            why = "이미 찾은 곳입니다" if state == "found" else "아직 단서가 없습니다"
        if depth_of(st) < int(sp.get("min_base_depth_m", 0)):
            why = f"거점이 {int(sp.get('min_base_depth_m', 0))}m 까지 내려와야 갈 수 있습니다"
        prefix = "단서를 따라 · " if kind == "clue" else ""
        return {"kind": kind, "id": sid, "ko": prefix + str(name), "lengths": lens, "cat": sp.get("category", "unknown"),
                "danger_mul": float(sp.get("danger_mul", 1.0)), "kinds": sp.get("kinds"), "why": why,
                "deep": int(sp.get("depth_m", 0)) >= 120, "first_visit_imprint": sp.get("first_visit_imprint"),
                "week1_half": bool(week1)}
    return {"kind": kind, "why": "없는 목적지입니다", "lengths": []}


def lingering_now(st: dict) -> str | None:
    """오늘 습격이 접촉 전이면 그 생물은 바깥에 있다."""
    r = st.get("raid")
    if r and not r.get("none") and not r.get("resolved") and r.get("day") == day_of(st):
        return r.get("creature")
    return None


def exp_errors(st: dict, uid: str, members: list, dest: dict, length: str) -> tuple[list, dict | None, list]:
    errs = []
    ex = st.get("expedition")
    if ex:
        errs.append("이미 나가 있는 조가 있습니다. 문은 하나입니다")
    by = {r["id"]: r for r in st.get("residents_list") or []}
    ppl = []
    if not members or len(members) > int(EX.g("party.max", 2)) or len(set(members)) != len(members):
        errs.append(f"1~{int(EX.g('party.max', 2))}명을 골라 주세요")
    for m in members or []:
        r = by.get(m)
        if not r:
            errs.append("없는 사람입니다")
            continue
        if r.get("injured"):
            errs.append(f"{r['name']} 님은 다쳐서 누워 있습니다")
        if m in (st.get("outside") or []):
            errs.append(f"{r['name']} 님은 이미 밖에 있습니다")
        ppl.append(r)
    sp = dest_spec(st, uid, dest)
    if sp.get("why"):
        errs.append(sp["why"])
    L = (EX.g("lengths") or {}).get(length)
    if not L:
        errs.append("없는 길이입니다")
    elif length not in (sp.get("lengths") or []):
        errs.append(f"{sp.get('ko', '그곳')}에는 {L.get('ko', length)}로 갈 수 없습니다")
    elif length == "long" and room_level_of(st, "airlock") < 1:
        errs.append("밤 넘기기는 에어락 Lv1 이 필요합니다")
    su = suits_state(st)
    if len(members or []) > su["usable"]:
        errs.append("입을 잠수복이 모자랍니다" + (" — 마모된 잠수복을 먼저 고쳐 주세요" if su["usable"] < su["total"] else ""))
    if L:
        cost = int(L.get("tank", 2)) * max(1, len(members or []))
        if air_state(st)["value"] + 1e-9 < cost:
            errs.append(f"공기가 모자랍니다(필요 {cost})")
    return errs, sp, ppl


def exp_numbers(st: dict, uid: str, ppl: list, sp: dict, length: str) -> dict:
    """미리 보기와 출발이 같은 값을 쓴다(D2)."""
    eye = max(int((p.get("stats") or {}).get("eye", 5)) for p in ppl)
    ling = lingering_now(st)
    learning = int(st.get("exp_count") or 0) < int(EX.g("danger.learning_trips_without_danger", 2))
    kind = sp["kind"]
    R = EX.g("newcomers.rescue.chance") or {}
    if kind == "unknown":
        rp = float(R.get(f"unknown_{length}", 0))
    else:
        rp = float(R.get(kind, 0))
    if rp > 0:
        rp += float(EX.g("newcomers.rescue.per_eye_above_5", 0.01)) * max(0, eye - 5)
    if kind == "unknown" and EX.g("newcomers.rescue.first_unknown_guaranteed") and not st.get("unknown_done"):
        rp = 1.0
    if core_of(st)["flags"].get("rescue_due") and kind != "door" and length != "short":
        rp = 1.0                                         # S19 비트 6: 두 번째 새 주민(구조)을 운 대신 차례로
    cp = 0.0
    if kind == "unknown":
        cs = EX.g("destinations.unknown.clue_stumble") or {}
        cp = float(cs.get(length, 0)) + float(cs.get("per_eye_above_5", 0.01)) * max(0, eye - 5)
    dp = 0.0
    if kind == "clue":
        dd = EX.g("stats.eye.discovery") or {}
        tries = int((st.get("clue_tries") or {}).get(sp.get("id"), 0))
        dp = float(dd.get("base", 0.4)) + float(dd.get("per_point", 0.06)) * (eye - 5) + \
            float(EX.g("destinations.clue.fail_memory", 0.15)) * tries
        dp = max(float(dd.get("min", 0.2)), min(float(dd.get("max", 0.9)), dp))
    return {"lingering": ling, "learning": learning, "rescue_p": round(min(1.0, rp), 4),
            "clue_p": round(cp, 4), "discover_p": round(dp, 4), "eye": eye}


def recent_categories(uid: str, day: int) -> list[str]:
    with db() as con:
        rows = con.execute("SELECT DISTINCT category FROM scans WHERE uid=? AND day>? ORDER BY category",
                           (uid, day - 7)).fetchall()
    return [r["category"] for r in rows if r["category"] in EX.CATS]


def exp_preview(st: dict, uid: str, members: list, dest: dict, length: str) -> dict:
    errs, sp, ppl = exp_errors(st, uid, members, dest, length)
    out: dict = {"ok": not errs, "errors": errs, "warnings": []}
    if not ppl or not sp or sp.get("why") or length not in (EX.g("lengths") or {}):
        return out
    L = EX.g("lengths")[length]
    nums = exp_numbers(st, uid, ppl, sp, length)
    breath = min(int((p.get("stats") or {}).get("breath", 5)) for p in ppl)
    x = int(L.get("tank", 2)) * (1 + float(EX.g("stats.breath.per_point", 0.1)) * (breath - 5))
    carry = sum(EX.carry_slots(int((p.get("stats") or {}).get("hand", 5))) for p in ppl)
    p = 0.0 if nums["learning"] else float(L.get("danger", 0)) * sp["danger_mul"] + \
        float((EX.g("raid_link.lingering_add") or {}).get(nums["lingering"] or "", 0))
    w = dict(sp.get("kinds") or EX.g("danger.default_kind_weights") or {})
    tot = sum(w.values()) or 1
    kinds = []
    for k, v in w.items():
        stat = ((EX.g("danger.kinds") or {}).get(k) or {}).get("check", "breath")
        best = max(int((pp.get("stats") or {}).get(stat, 5)) for pp in ppl)
        kinds.append({"kind": k, "ko": ((EX.g("danger.kinds") or {}).get(k) or {}).get("ko"), "stat": stat,
                      "weight": round(v / tot, 3), "p_pass": round(EX.check_p(best, len(ppl) > 1), 3)})
    cost = int(L.get("tank", 2)) * len(ppl)
    if nums["lingering"] == "claws":
        out["warnings"].append("손톱 무리가 바깥에 있다 — 접촉 때 밖에 사람이 있으면 관문이 깨진다")
    vb = None
    if sp["kind"] == "spot":
        last = (st.get("spot_visits") or {}).get(sp["id"])
        if last is None or day_of(st) - int(last) >= int(EX.g("destinations.spot.visit_bonus_cooldown_days", 3)):
            vb = (next((x for x in SPOTS if x.get("id") == sp["id"]), {}).get("resource") or {}).get("gain")
    if int(st.get("exp_count") or 0) == 0:
        x = float(EX.head_n())                       # 튜토리얼은 줍기 3번(문서와 같게 — 플레이테스트 버그 13)
    out.update({"actions": max(int(EX.g("stats.breath.min_actions", 1)), int(x)),   # 화면용: 보장되는 수(내림)
                "actions_expected": round(max(1.0, x), 3),                            # 시뮬용 기댓값(소수)
                "carry": carry, "air_cost": cost,
                "air_after": round(air_state(st)["value"] - cost, 3),
                "returns_at": now_ts() + int(L.get("minutes", 30)) * 60,
                "danger": {"p": round(max(0.0, min(0.95, p)), 4),
                           "lingering_add": float((EX.g("raid_link.lingering_add") or {}).get(nums["lingering"] or "", 0)),
                           "learning": nums["learning"], "kinds": kinds},
                "rescue_p": nums["rescue_p"], "clue_p": nums["clue_p"], "discover_p": nums["discover_p"],
                "visit_bonus": vb, "finds_p": {k: round(v, 4) for k, v in EX.find_probs(nums["eye"]).items()}})
    return out


# ── 출발 ──────────────────────────────────────────────────────
def exp_start(st: dict, uid: str, members: list, dest: dict, length: str) -> dict:
    tutorial = int(st.get("exp_count") or 0) == 0
    if tutorial:
        dest, length = {"kind": "door"}, "short"                     # 첫 원정 = 튜토리얼(문 앞, 짧게, 위험 없음)
        members = list(members or [])[:1]
    errs, sp, ppl = exp_errors(st, uid, members, dest, length)
    if errs:
        raise HTTPException(400, " · ".join(errs))
    L = EX.g("lengths")[length]
    nums = exp_numbers(st, uid, ppl, sp, length)
    n_exp = int(st.get("exp_count") or 0) + 1
    eid = f"exp-{day_of(st)}-{n_exp}"
    res = EX.roll(f"{uid}|{eid}",
                  members=[{"id": p["id"], "stats": p.get("stats") or {}} for p in ppl],
                  dest=dest, dest_cat=sp["cat"], length=length, danger_mul=sp["danger_mul"],
                  lingering=nums["lingering"], learning=nums["learning"],
                  recent_cats=recent_categories(uid, day_of(st)), kinds_weights=sp.get("kinds"),
                  rescue_p=nums["rescue_p"], clue_p=nums["clue_p"], discover_p=nums["discover_p"],
                  tutorial=tutorial, deep=bool(sp.get("deep") or sp["kind"] == "unknown"))
    # 갈림길 자동(expedition.json scene.fork, S15-D2): 상자 대기가 auto_box_backlog 이상이거나
    # auto_low_materials 중 가장 적은 재고가 auto_low_stock 미만이면 불빛(재료), 아니면 어둠(상자). 출발 때 정해 둔다(D6)
    auto_fork = auto_fork_for(st)
    cost = int(L.get("tank", 2)) * len(ppl)
    st.setdefault("air", {})["value"] = round(air_state(st)["value"] - cost, 3)
    t = now_ts()
    dur = int(L.get("minutes", 30)) * 60
    # 잠수복: 마모 적은 것부터
    su = suits_state(st)
    order = sorted(range(su["total"]), key=lambda i: su["wear"][i])
    suit_idx = [i for i in order if su["wear"][i] < su["wear_limit"]][:len(ppl)]
    ex = {"id": eid, "members": [p["id"] for p in ppl], "dest": {k: v for k, v in dest.items() if k in ("kind", "id")},
          "dest_ko": sp.get("ko"), "length": length, "started": t,
          "returns_at": t + (30 * 60 if tutorial else dur), "duration": dur, "air_used": cost,
          "lingering": nums["lingering"], "seed": f"{uid}|{eid}", "result": res, "auto_fork": auto_fork,
          "tutorial": tutorial, "suits": suit_idx, "recalled_at": None, "recall_keep": None,
          "first_visit_imprint": sp.get("first_visit_imprint"),
          "stations": {p["id"]: station_slot(st, p["id"]) for p in ppl},
          "scene": {"picked": [], "fork": None, "danger": None, "dropped": [], "committed": False}}
    st["expedition"] = ex
    st["exp_count"] = n_exp
    st["outside"] = list(ex["members"])
    if sp["kind"] == "unknown":
        st["unknown_done"] = True
    log(uid, "expedition_start", {"id": eid, "members": ex["members"], "dest": ex["dest"], "length": length,
                                  "air": cost, "lingering": nums["lingering"]})
    return ex


def auto_fork_for(st: dict) -> str:
    F = EX.g("scene.fork") or {}
    backlog = int(F.get("auto_box_backlog", 3))
    lows = [m for m in (F.get("auto_low_materials") or []) if isinstance(m, str)]
    low_stock = int(F.get("auto_low_stock", 3))
    if len(st.get("boxes") or []) >= backlog:
        return "lit"
    if lows and min(int(st["resources"].get(m, 0)) for m in lows) < low_stock:
        return "lit"
    return "dark"


def exp_progress(ex: dict, t: float | None = None) -> float:
    t = now_ts() if t is None else t
    span = max(1.0, float(ex["returns_at"]) - float(ex["started"]))
    return round(max(0.0, min(1.0, (t - float(ex["started"])) / span)), 4)


def scene_open(ex: dict, t: float | None = None) -> bool:
    if ex["scene"].get("committed"):
        return False
    if ex.get("tutorial"):
        return True
    t = now_ts() if t is None else t
    win = min(float(ex.get("duration") or 1800) * 0.1, 30 * 60)
    return t - float(ex["started"]) <= win


def exp_public(st: dict, ex: dict | None) -> dict | None:
    if not ex:
        return None
    by = {r["id"]: r for r in st.get("residents_list") or []}
    return {"id": ex["id"], "members": list(ex["members"]),
            "member_names": [by.get(m, {}).get("name") for m in ex["members"]],
            "dest": ex["dest"], "dest_ko": ex.get("dest_ko"), "length": ex["length"],
            "started": ex["started"], "returns_at": ex["returns_at"], "now": now_ts(),
            "progress": exp_progress(ex), "air_used": ex.get("air_used"), "lingering": ex.get("lingering"),
            "recalled": bool(ex.get("recalled_at")), "tutorial": bool(ex.get("tutorial")),
            "scene": {"open": scene_open(ex), "committed": bool(ex["scene"].get("committed"))}}


# ── 따라 나가기 장면 ────────────────────────────────────────────
def scene_geometry(ex: dict) -> dict:
    rng = random.Random(f"scene|{ex['seed']}")
    radius = {"short": 18, "half": 36, "long": 60}.get(ex["length"], 30)
    n = 9
    pts = [{"x": 0.0, "z": 0.0}]
    for i in range(1, n):
        a = (i / n) * math.pi * 1.2 - 0.2 + rng.uniform(-0.15, 0.15)
        r = radius * math.sin(math.pi * i / n) + rng.uniform(-2, 2)
        pts.append({"x": round(max(2.0, r * math.cos(a) + 3), 2), "z": round(r * math.sin(a), 2)})
    pts.append({"x": 0.0, "z": 0.0})
    return {"waypoints": pts}


def discover_pos(ex: dict) -> dict:
    """발견 연출 자리 = 장면 경로에서 문(원점)에서 가장 먼 점. scene GET 과 같은 좌표계(m, 문 원점)."""
    wp = scene_geometry(ex)["waypoints"]
    return dict(max(wp, key=lambda p: p["x"] ** 2 + p["z"] ** 2))


def scene_next(ex: dict) -> str:
    res, sc = ex["result"], ex["scene"]
    if sc.get("committed"):
        return "done"
    k = len(sc.get("picked") or [])
    d = res.get("danger")
    H = min(EX.head_n(), res["actions"])
    if d and d["at"] < H and sc.get("danger") is None and k >= d["at"]:
        return "danger"
    if sc.get("danger") == "turn_back":
        return "done"
    if sc.get("need_drop"):
        return "drop"
    if k < H:
        return f"pick:{k}"
    if res["actions"] > H and sc.get("fork") is None:
        return "fork"
    return "done"


def scene_public(st: dict, ex: dict) -> dict:
    res, sc = ex["result"], ex["scene"]
    geo = scene_geometry(ex)
    wp = geo["waypoints"]
    H = min(EX.head_n(), res["actions"])
    picks = []
    picked = {int(p["i"]): p for p in sc.get("picked") or []}
    for i in range(H):
        row = {"i": i, "pos": wp[min(i + 1, len(wp) - 1)], "state": "picked" if i in picked else "sparkle"}
        if i in picked:
            row["item"] = picked[i]["item"]
        picks.append(row)
    d = res.get("danger")
    danger = None
    if d and d["at"] < H:
        danger = {"before_pick": d["at"], "kind": d["kind"],
                  "ko": ((EX.g("danger.kinds") or {}).get(d["kind"]) or {}).get("ko"),
                  "stat": d["stat"], "p_hide": d["p_pass"], "options": ["hide", "turn_back"],
                  "auto": EX.danger_auto(d), "chosen": sc.get("danger")}
    fork = None
    if res["actions"] > H:
        F = EX.g("scene.fork") or {}
        fork = {"after": H, "pos": wp[min(H + 1, len(wp) - 1)],
                "options": [{"id": "lit", "ko": "불빛 쪽", "shift": F.get("lit")},
                            {"id": "dark", "ko": "어둠 쪽", "shift": F.get("dark")}],
                "auto": ex.get("auto_fork"), "chosen": sc.get("fork")}
    items = [p["item"] for p in sc.get("picked") or [] if p["item"]["kind"] != "empty"
             and int(p["i"]) not in set(sc.get("dropped") or [])]
    disc = None
    if ex["dest"].get("kind") == "clue" and res["u_discover"] < res["discover_p"]:
        disc = {"spot_id": ex["dest"].get("id"), "pos": discover_pos(ex)}
    by = {r["id"]: r for r in st.get("residents_list") or []}
    spent = len(sc.get("picked") or [])
    return {"exp_id": ex["id"], "terrain_seed": f"{ex['seed'].split('|')[0]}|{ex['dest'].get('id') or ex['dest'].get('kind')}",
            "dest": ex["dest"], "dest_ko": ex.get("dest_ko"), "started": ex["started"], "returns_at": ex["returns_at"],
            "now": now_ts(), "progress": exp_progress(ex),
            "members": [{"id": m, "name": by.get(m, {}).get("name"), "role": by.get(m, {}).get("role"),
                         "stats": by.get(m, {}).get("stats"), "imprints": by.get(m, {}).get("imprints")}
                        for m in ex["members"]],
            "lantern_radius_m": 8, "waypoints": wp,
            "head": {"picks": picks, "fork": fork, "danger": danger},
            "carry": {"slots": res["carry"], "used": sum(EX.slots_of(it) for it in items), "items": items},
            "air_band": round(max(0.0, 1.0 - spent / max(1, res["actions"])), 4),
            "open": scene_open(ex), "committed": bool(sc.get("committed")), "next": scene_next(ex),
            "discovers": disc, "tutorial": bool(ex.get("tutorial")),
            "auto_rules": {"fork": "오늘 가장 모자란 쪽", "danger": "판정 확률 ≥ 0.55 면 숨는다",
                           "drop": "상자 > 유물 > 재료"}}


def scene_act(st: dict, ex: dict, action: str, i=None, choice=None, keep=None) -> None:
    res, sc = ex["result"], ex["scene"]
    if not scene_open(ex):
        raise HTTPException(400, "따라 나가기는 이미 끝났습니다. 지금은 보기만 할 수 있습니다")
    nxt = scene_next(ex)
    if action == "done":
        sc["committed"] = True
        if ex.get("tutorial"):
            ex["returns_at"] = now_ts()                    # 튜토리얼은 장면이 끝나면 바로 돌아온다
        return
    if action == "danger":
        if nxt != "danger" or choice not in ("hide", "turn_back"):
            raise HTTPException(400, f"지금은 그 선택을 할 차례가 아닙니다(다음: {nxt})")
        sc["danger"] = choice
        if choice == "turn_back":
            d = res["danger"]
            ex["returns_at"] = float(ex["started"]) + (float(ex["returns_at"]) - float(ex["started"])) * \
                (d["at"] / max(1, res["actions"]))
        return
    if action == "pick":
        if nxt != f"pick:{i}":
            raise HTTPException(400, f"그 칸은 지금 주울 수 없습니다(다음: {nxt})")
        item = EX.item_at(res, int(i), None)
        sc.setdefault("picked", []).append({"i": int(i), "item": item})
        held = [p["item"] for p in sc["picked"] if p["item"]["kind"] != "empty"
                and int(p["i"]) not in set(sc.get("dropped") or [])]
        if sum(EX.slots_of(it) for it in held) > res["carry"]:
            sc["need_drop"] = True
        return
    if action == "drop":
        if nxt != "drop" or not isinstance(keep, list):
            raise HTTPException(400, f"지금은 내려놓을 차례가 아닙니다(다음: {nxt})")
        held = [p["item"] for p in sc["picked"] if p["item"]["kind"] != "empty"]
        ks = {int(x) for x in keep}
        kept = [it for it in held if it["i"] in ks]
        if sum(EX.slots_of(it) for it in kept) > res["carry"] or not ks <= {it["i"] for it in held}:
            raise HTTPException(400, "그만큼은 들 수 없습니다")
        sc["dropped"] = sorted({it["i"] for it in held} - ks)
        sc["need_drop"] = False
        return
    if action == "fork":
        if nxt != "fork" or choice not in ("lit", "dark"):
            raise HTTPException(400, f"지금은 갈림길이 아닙니다(다음: {nxt})")
        sc["fork"] = choice
        return
    raise HTTPException(400, "없는 행동입니다")


# ── 귀환 정산 ──────────────────────────────────────────────────
def make_guest(st: dict, uid: str, seed: str, src: str, rescued_by: list | None = None) -> dict | None:
    if len(st.get("guests") or []) >= int(EX.g("entrance.guest_spots", 2)):
        return None
    rng = random.Random(f"guest|{seed}")
    have = {r["role"] for r in (st.get("residents_list") or []) + (st.get("guests") or [])}
    pool = [r for r in ROLE_IDS if r not in have] or ROLE_IDS
    taken = {r["name"] for r in (st.get("residents_list") or []) + (st.get("guests") or [])}
    tilt = guest_role_weights(st)                        # S19 꼬리표 손님 기울기(오는 횟수는 그대로, 누가 오는지만)
    if tilt and any(r_ in tilt for r_ in pool):
        sp = sorted(pool)
        role_ = rng.choices(sp, weights=[tilt.get(x, 1) for x in sp], k=1)[0]
    else:
        role_ = rng.choice(sorted(pool))
    g = make_resident(role_, rng, taken, uid)
    ensure_stats(uid, g)
    g.update({"guest_id": "g-" + g["id"], "arrived": now_ts(), "src": src, "rescued_by": list(rescued_by or [])})
    st.setdefault("guests", []).append(g)
    log(uid, "guest_arrived", {"src": src, "role": g["role"]})
    return g


BOX_CATS = tuple(EX.CATS) + ("blank",)


def box_cat(cat: str | None, seed: str) -> str:
    """상자 갈래는 정본 여덟(food…tobacco) + blank(튜토리얼 빈 원)만. 옛 'any' → blank,
    'unknown'·그 밖 → 시드로 여덟 중 하나(만들 때 정한다 — 화면에 날 이름이 나가지 않게)."""
    if cat in BOX_CATS:
        return cat
    if cat == "any":
        return "blank"
    return EX.CATS[int(hashlib.sha256(f"boxcat|{seed}".encode()).hexdigest()[:8], 16) % len(EX.CATS)]


def box_new(st: dict, cat: str, frm: str | None, seed: str) -> dict:
    b = {"id": f"box-{seed}", "cat": box_cat(cat, seed), "found_day": day_of(st), "found_ts": now_ts(), "from": frm}
    st.setdefault("boxes", []).append(b)
    return b


def relic_to_shelf(st: dict, cat: str, rarity: str, seed: str) -> int | None:
    card = {"category": cat if cat in EX.CATS else "unknown", "rarity": rarity, "id": f"shard-{seed}",
            "name": None, "family_name": None, "barcode": None, "_day": day_of(st)}
    slot = shelf_place(st, card)
    if slot is None and shelf_capacity(st):
        store_overflow(st, card)                     # S18: 자리가 없으면 창고 상자로(사라지지 않는다)
    return slot


_EXP_TEXT: dict = {"mtime": "unset", "data": {}}


def exp_text() -> dict:
    p = ROOT / "data" / "expedition_text.json"
    try:
        mt = p.stat().st_mtime
    except OSError:
        mt = None
    if mt != _EXP_TEXT["mtime"]:
        data = _EXP_TEXT.get("data") or {}
        if mt is not None:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                print(f"[expedition_text] 무시: {e}")
        _EXP_TEXT.update({"mtime": mt, "data": data})
    return _EXP_TEXT["data"]


def xt(path: str, **vars) -> str | None:
    cur = exp_text()
    for k in path.split("."):
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return None
    if isinstance(cur, list):
        cur = cur[0] if cur else None
    if not isinstance(cur, str):
        return None
    for k, v in vars.items():
        cur = cur.replace("{" + k + "}", str(v))
    return cur


def box_pattern(cat: str) -> str | None:
    # 시나리오가 아홉 갈래를 sealed_box.patterns 아래로 모았다(blank 포함). 옛 자리(sealed_box.blank)도 받아 준다
    return xt(f"sealed_box.patterns.{cat}.name") or (xt("sealed_box.blank.name") if cat == "blank" else None)


TEXT_LEN_KEY = {"short": "short", "half": "half", "long": "overnight"}     # 시나리오 키 이름 맞춤표


def exp_log_line(ex: dict, names: list, haul: dict, left: dict, out: dict, imps: list, discovered, clue,
                 newcomer, no_room, st: dict) -> str | None:
    """시나리오 조각(expedition.log.*)으로 일지 한 줄을 조립한다(scenario_S15 F2 순서). 조각이 없으면 None."""
    if ex.get("tutorial") and xt("expedition.log.tutorial"):
        return xt("expedition.log.tutorial")
    head = xt("expedition.log.head", name="·".join(names), dest=ex.get("dest_ko") or "",
              length=(xt(f"expedition.lengths.{ex['length']}.label")
                      or xt(f"expedition.lengths.{TEXT_LEN_KEY.get(ex['length'], ex['length'])}.label") or ex["length"]))
    if not head:
        return None
    bits = [head]
    nm, nb, ns = sum(haul["materials"].values()), len(haul["boxes"]), len(haul["relics"])
    bits.append(xt("expedition.log.haul", materials=nm, boxes=nb, shards=ns) if (nm or nb or ns)
                else xt("expedition.log.haul_empty"))
    nl = sum(left["materials"].values()) + left["boxes"] + left["relics"]
    if nl:
        bits.append(xt("expedition.log.left_behind", n=nl))
    for b in haul["boxes"]:
        bits.append(xt("expedition.log.box_found", pattern=box_pattern(b["cat"]) or ""))
    shelf = {int(it.get("slot", -1)): it for it in st.get("shelf") or []}
    for r in haul["relics"]:
        it = shelf.get(r.get("shelf_slot") if r.get("shelf_slot") is not None else -2)
        if it and it.get("name"):
            bits.append(xt("expedition.log.shard_on_shelf", item=it["name"]))
    d = out.get("danger")
    if d and d.get("ok") is not None:
        bits.append(xt(f"expedition.log.danger.{d['kind']}.{'pass' if d['ok'] else 'fail'}"))
    for im in imps or []:
        bits.append(xt("expedition.log.imprint_gained", name=im.get("resident"), imprint=(im.get("imprint") or {}).get("name")))
    if discovered:
        bits.append(xt("expedition.log.spot_found", spot=discovered.get("name")))
    elif ex["dest"].get("kind") == "clue" and not out.get("turned_back") and not ex.get("recalled_at"):
        bits.append(xt("expedition.log.spot_not_found"))
    if clue:
        bits.append(xt("expedition.log.clue_gained", spot=clue.get("name")))
    if newcomer:
        bits.append(xt("expedition.log.rescue", guest=newcomer.get("name")))
    elif no_room:
        bits.append(xt("expedition.log.rescue_no_room"))
    if ex.get("recalled_at"):
        bits.append(xt("expedition.log.recall"))
    return " ".join(b for b in bits if b)


def exp_settle(st: dict, uid: str) -> dict | None:
    """돌아올 시각이 지났으면 한 번 정산한다(멱등 — 정산하면 expedition 이 비워진다)."""
    ex = st.get("expedition")
    if not ex or now_ts() < float(ex["returns_at"]):
        return None
    res, sc = ex["result"], ex["scene"]
    fork = sc.get("fork") or ex.get("auto_fork") or "dark"
    out = EX.settle(res, fork=fork, danger_choice=sc.get("danger"), dropped=sc.get("dropped"),
                    recall_keep=ex.get("recall_keep"))
    by = {r["id"]: r for r in st.get("residents_list") or []}
    mem = [by[m] for m in ex["members"] if m in by]
    names = [m["name"] for m in mem]
    haul = {"materials": {}, "boxes": [], "relics": []}
    cat = res["dest_cat"]
    for it in out["kept"]:
        sd = f"{ex['id']}-{it['i']}"
        if it["kind"] == "material":
            st["resources"][it["res"]] = int(st["resources"].get(it["res"], 0)) + int(EX.g("finds.material_amount", 1))
            haul["materials"][it["res"]] = haul["materials"].get(it["res"], 0) + 1
        elif it["kind"] == "box":
            b = box_new(st, it["cat"], ex["dest"].get("id") or ex["dest"].get("kind"), sd)
            haul["boxes"].append({"id": b["id"], "cat": b["cat"]})
        elif it["kind"] == "relic":
            rc = cat if cat in EX.CATS else EX.CATS[int(res["acts"][it["i"]]["u3"] * 8) % 8]
            haul["relics"].append({"rarity": it["rarity"], "shelf_slot": relic_to_shelf(st, rc, it["rarity"], sd)})
    left = {"materials": {}, "boxes": 0, "relics": 0}
    for it in out["left"]:
        if it["kind"] == "material":
            left["materials"][it["res"]] = left["materials"].get(it["res"], 0) + 1
        elif it["kind"] == "box":
            left["boxes"] += 1
        elif it["kind"] == "relic":
            left["relics"] += 1
    # 위험의 결과(죽음·못 돌아옴·장비 소멸·방 상실은 규칙상 0)
    injured = None
    if out["injure"] and mem:
        stat = (res.get("danger") or {}).get("stat", "hand")
        who = min(mem, key=lambda r: (int((r.get("stats") or {}).get(stat, 5)), r["id"]))
        who["injured"] = True
        injured = who["name"]
        st["injured"] = sum(1 for x in st.get("residents_list", []) if x.get("injured"))
    su = suits_state(st)
    for i in ex.get("suits") or []:
        if i < len(su["wear"]):
            su["wear"][i] += int(EX.g("gear.wear_per_trip", 1)) + int(out["wear_extra"])
    st["suits"]["shared_wear"] = su["wear"]
    flags = list(out["flags"])
    discovered = clue = visit = None
    reached = not out["turned_back"] and not ex.get("recalled_at")
    kind = ex["dest"].get("kind")
    if kind == "clue" and reached:
        sid = ex["dest"].get("id")
        if res["u_discover"] < res["discover_p"]:
            st.setdefault("spots_found", [])
            if sid not in st["spots_found"]:
                st["spots_found"].append(sid)
            spot = next((x for x in SPOTS if x.get("id") == sid), {})
            discovered = {"spot_id": sid, "name": spot.get("name"), "discovery_text": spot.get("discovery_text"),
                          "pos": discover_pos(ex)}         # 3D 가 발견 연출을 그 자리에서 튼다(scene 좌표계)
            flags.append("healing_spot_found")
            day_note(st, "spot", spot.get("name") or sid)
        else:
            st.setdefault("clue_tries", {})[sid] = int(st.get("clue_tries", {}).get(sid, 0)) + 1
    if kind == "spot" and reached:
        sid = ex["dest"].get("id")
        last = (st.get("spot_visits") or {}).get(sid)
        if last is None or day_of(st) - int(last) >= int(EX.g("destinations.spot.visit_bonus_cooldown_days", 3)):
            gain = (next((x for x in SPOTS if x.get("id") == sid), {}).get("resource") or {}).get("gain") or {}
            visit = {}
            for k, v in gain.items():
                if k in st["resources"] and isinstance(v, (int, float)):
                    st["resources"][k] = int(st["resources"].get(k, 0)) + int(v)
                    visit[k] = int(v)
            st.setdefault("spot_visits", {})[sid] = day_of(st)
        first = sid not in (st.get("spots_visited") or [])
        st.setdefault("spots_visited", [])
        if first:
            st["spots_visited"].append(sid)
            if ex.get("first_visit_imprint") == "depth_mark":
                flags.append("deep_descent")
    if kind == "unknown" and reached and res["u_clue"] < res["clue_p"]:
        cand = [s for s in DEEP_SPOT_IDS if spot_state(st, uid, s) == "none"]
        if cand:
            sid = cand[int(res["u_clue_pick"] * len(cand)) % len(cand)]
            st.setdefault("clues_extra", []).append(sid)
            clue = {"spot_id": sid, "name": next((x.get("name") for x in SPOTS if x.get("id") == sid), sid)}
    newcomer, no_room = None, False
    if reached and res["u_rescue"] < res["rescue_p"]:
        g = make_guest(st, uid, ex["seed"], "rescue", ex["members"])
        if g:
            newcomer = {"guest_id": g["guest_id"], "name": g["name"], "role": g["role"]}
            if core_of(st)["flags"].get("rescue_due"):
                core_of(st)["flags"]["rescue_due"] = False
                core_of(st)["flags"]["rescue_done"] = True
        else:
            no_room = True
            st["resources"]["morale"] = int(st["resources"].get("morale", 0)) + 1
    flags = close_call_flags(flags, out, injured)       # S19(PM): 아슬아슬하게 돌아온 것만 사람을 바꾼다
    imps = grant_imprints(st, None, flags, mem, src="expedition") if flags else []
    # 신뢰: 둘이 가면 +3, 위험을 함께 넘기면 +10. 마중(담) 덤
    T = EX.g("trust") or {}
    if len(mem) == 2:
        a, b = mem
        dlt = int(T.get("pair_trip", 3)) + (int(T.get("shared_danger", 10)) if (out["danger"] or {}).get("ok") else 0)
        for x, y in ((a, b), (b, a)):
            x.setdefault("trust", {})[y["id"]] = min(TRUST_MAX, int(x["trust"].get(y["id"], 0)) + dlt)
    acts, _ = entrance_activities({**st, "outside": []})
    greeted = None
    if "nerve" in acts and acts["nerve"] not in ex["members"] and acts["nerve"] in by:
        gr = by[acts["nerve"]]
        eff = ((EX.g("entrance.idle.activities.nerve") or {}).get("effect") or {})
        st["resources"]["morale"] = int(st["resources"].get("morale", 0)) + int(eff.get("return_morale", 1))
        for m in mem:
            for x, y in ((gr, m), (m, gr)):
                x.setdefault("trust", {})[y["id"]] = min(TRUST_MAX, int(x["trust"].get(y["id"], 0)) + int(eff.get("return_trust", 2)))
        greeted = {"id": gr["id"], "name": gr["name"]}
    # 숨은 원정으로 아주 천천히 자란다(점수 8마다 +1, 태어난 값 +2 까지)
    grew = []
    pts = float((EX.g("stats.growth.trip_points") or {}).get(ex["length"], 0))
    for m in mem:
        s = m.setdefault("stats", {})
        m.setdefault("born_breath", int(s.get("breath", 5)))
        before = float(m.get("trip_pts") or 0)
        m["trip_pts"] = before + pts
        if int(m["trip_pts"] // 8) > int(before // 8) and int(s.get("breath", 5)) < int(m["born_breath"]) + 2:
            s["breath"] = int(s.get("breath", 5)) + 1
            grew.append({"id": m["id"], "to": s["breath"]})
    # 사람은 돌아와 원래 자리로(정원이 찼으면 문간)
    st["outside"] = [o for o in (st.get("outside") or []) if o not in ex["members"]]
    for m in ex["members"]:
        slot = (ex.get("stations") or {}).get(m)
        r = room_at(st, slot) if slot is not None else None
        if r is None or r.get("flooded") or len([p for p in stations_map(st).get(int(slot), []) if p["id"] != m]) >= room_cap_of(r):
            set_station(st, m, None)
    L = (EX.g("lengths") or {}).get(ex["length"]) or {}
    dk = (out["danger"] or {}).get("kind")
    line = (f"{'·'.join(names)} — {ex.get('dest_ko')}, {L.get('ko', ex['length'])}. "
            f"재료 {sum(haul['materials'].values())} · 상자 {len(haul['boxes'])} · 유물 {len(haul['relics'])}"
            + (f", 두고 온 것 {sum(left['materials'].values()) + left['boxes'] + left['relics']}" if out["left"] else "")
            + (f". {((EX.g('danger.kinds') or {}).get(dk) or {}).get('ko')}" if dk else "") + ".")
    line = exp_log_line(ex, names, haul, left, out, imps, discovered, clue, newcomer, no_room, st) or line
    ret = {"id": ex["id"], "members": list(ex["members"]), "member_names": names, "dest": ex["dest"],
           "dest_ko": ex.get("dest_ko"), "length": ex["length"], "returned_at": now_ts(),
           "haul": haul, "left_behind": left,
           "danger": ({**out["danger"], "ko": ((EX.g("danger.kinds") or {}).get(dk) or {}).get("ko")} if out["danger"] else None),
           "injured": injured, "imprints": imps, "newcomer": newcomer, "rescued_but_no_room": no_room,
           "clue": clue, "discovered": discovered, "visit_bonus": visit, "breath_grew": grew,
           "greeted_by": greeted, "line": line, "recalled": bool(ex.get("recalled") or ex.get("recalled_at")),
           "tutorial": bool(ex.get("tutorial")), "value": out["value"],
           "request_hint": exp_request_hint(st, uid, ex)}
    st.setdefault("exp_log", []).append({k: ret[k] for k in ("id", "members", "dest", "length", "haul", "left_behind",
                                                             "danger", "injured", "newcomer", "recalled")}
                                        | {"day": day_of(st)})
    del st["exp_log"][:-60]
    st["exp_unseen"] = ret
    st["expedition"] = None
    day_note(st, "expedition", ret["line"])
    log(uid, "expedition_return", {"id": ex["id"], "value": out["value"], "danger": out["danger"],
                                   "newcomer": bool(newcomer), "discovered": bool(discovered)})
    return ret


def exp_recall(st: dict, uid: str, immediate: bool = False) -> dict:
    ex = st.get("expedition")
    if not ex:
        raise HTTPException(400, "밖에 나간 사람이 없습니다")
    if ex.get("recalled_at"):
        return ex
    t = now_ts()
    frac = exp_progress(ex, t)
    ex["recall_keep"] = int(ex["result"]["actions"] * frac)
    ex["recalled_at"] = t
    ex["recalled"] = True
    R = EX.g("raid_link.recall.arrive_minutes") or {}
    mins = 0 if immediate else (int(R.get("airlock_lv3", 0)) if room_level_of(st, "airlock") >= 3 else int(R.get("default", 20)))
    ex["returns_at"] = min(float(ex["returns_at"]), t + mins * 60)
    ex["scene"]["committed"] = True
    log(uid, "expedition_recall", {"id": ex["id"], "keep": ex["recall_keep"], "minutes": mins})
    return ex


# ── 문 두드림 · 공용 잠수복 수선 · 하루 덤 ──────────────────────
def knock_tick(st: dict, uid: str) -> dict | None:
    day = day_of(st)
    if int(st.get("knock_checked_day") or 0) >= day:
        return None
    st["knock_checked_day"] = day
    K = EX.g("newcomers.knock") or {}
    first = int(K.get("first_knock_day", 3))
    if day < first or (CALENDAR_ENFORCE and not is_unlocked(st, "guest_knock")):
        return None
    if len(st.get("guests") or []) >= int(EX.g("entrance.guest_spots", 2)):
        return None
    hit = not st.get("first_knock_done")
    due = int(core_of(st)["flags"].get("arc_guest_due") or 0)
    if not hit and due:                                  # S19 사슬 끝 매듭이 부른 옛 무리 손님
        hit = True
        core_of(st)["flags"]["arc_guest_due"] = due - 1
    if not hit and random.Random(f"{uid}|{day}|knock").random() < float(K.get("daily_chance", 0.08)):
        hit = True
    if not hit:
        return None
    st["first_knock_done"] = True
    g = make_guest(st, uid, f"{uid}|{day}|knock", "knock")
    if g:
        day_note(st, "knock", g["name"])
    return g


def entrance_daily(st: dict) -> None:
    """손 활동(수선)은 하루 한 번 가장 닳은 공용 잠수복 마모 −1."""
    day = day_of(st)
    if int(st.get("mend_day") or 0) >= day:
        return
    st["mend_day"] = day
    acts, _ = entrance_activities(st)
    if "hand" in acts:
        su = suits_state(st)
        if su["wear"] and max(su["wear"]) > 0:
            i = su["wear"].index(max(su["wear"]))
            su["wear"][i] -= 1
            st["suits"]["shared_wear"] = su["wear"]


def beds_state(st: dict) -> dict:
    lv = room_level_of(st, "quarters")
    total = int((EX.g("newcomers.beds_by_quarters_level") or {}).get(str(lv), 3))
    used = len(st.get("residents_list") or [])
    return {"total": total, "used": used, "free": max(0, total - used)}


def entrance_public(st: dict) -> dict:
    acts, rows = entrance_activities(st)
    gs = [{"id": g["guest_id"], "name": g["name"], "role": g["role"], "role_ko": g.get("role_ko"),
           "stats": g.get("stats"), "quirk": g.get("quirk"), "trait": g.get("trait"), "src": g.get("src"),
           "rescued_by": g.get("rescued_by"), "arrived": g.get("arrived")} for g in st.get("guests") or []]
    return {"people": rows, "activities": acts, "guests": gs, "guest_spots": int(EX.g("entrance.guest_spots", 2)),
            "beds": beds_state(st), "suits": suits_state(st), "air": air_state(st)}


def boxes_public(st: dict) -> list[dict]:
    day = day_of(st)
    after = int(EX.g("boxes.pry.after_days", 7))
    return [{"id": b["id"], "cat": b["cat"], "pattern": box_pattern(b["cat"]),
             "any": b["cat"] == "blank", "blank": b["cat"] == "blank", "found_day": b["found_day"], "age_days": day - int(b["found_day"]),
             "from": b.get("from"), "pry_ok": day - int(b["found_day"]) >= after,
             "pry_in_days": max(0, after - (day - int(b["found_day"])))} for b in st.get("boxes") or []]


def box_open(st: dict, b: dict, mul: float, seed: str) -> dict:
    units = int(round(float(EX.g("boxes.value.units", 4)) * mul))
    mat = EX.main_material(b["cat"]) if b["cat"] != "blank" else "food"   # 빈 원 상자 — 첫날 가장 쓸모 있는 것
    st["resources"][mat] = int(st["resources"].get(mat, 0)) + units
    rng = random.Random(f"box|{seed}|{b['id']}")
    relic = None
    if rng.random() < float(EX.g("boxes.value.relic_chance", 0.25)) * mul:
        rar = EX.rarity_of(rng.random(), rng.random(), False)
        relic = {"rarity": rar, "shelf_slot": relic_to_shelf(st, b["cat"] if b["cat"] in EX.CATS else "unknown", rar, b["id"])}
    st["boxes"] = [x for x in st.get("boxes") or [] if x["id"] != b["id"]]
    return {"id": b["id"], "cat": b["cat"], "gained": {mat: units}, "relic": relic}


def box_try_scan(st: dict, uid: str, code: str, cat: str) -> dict | None:
    """유효 스캔 하나가 같은 갈래 상자 하나를 연다(가장 오래된 것). 같은 바코드는 하루 한 상자. 감쇠와 무관."""
    day = day_of(st)
    keys = st.setdefault("box_keys", {})
    if int(keys.get(code, 0)) == day:
        return None
    cand = [b for b in st.get("boxes") or [] if b["cat"] == cat or b["cat"] == "blank"]
    if not cand:
        return None
    b = min(cand, key=lambda x: (float(x.get("found_ts") or 0), x["id"]))
    keys[code] = day
    for k in [k for k, v in keys.items() if int(v) < day - 1]:
        keys.pop(k, None)
    out = box_open(st, b, 1.0, f"{uid}|{code}")
    log(uid, "box_open", {"box": b["id"], "cat": b["cat"], "by": "scan"})
    return out


def s15_tick(st: dict, uid: str) -> dict:
    """상태를 읽는 요청마다(day_tick 안). 귀환 정산 → 두드림 → 문간 수선. 모두 멱등."""
    ret = exp_settle(st, uid)
    knock = knock_tick(st, uid)
    entrance_daily(st)
    return {"expedition_return": ret, "knock": knock}


def migrate_s15(st: dict) -> bool:
    changed = False
    if not isinstance(st.get("suits"), dict) or not isinstance(st["suits"].get("shared_wear"), list):
        # 잠수복 마모는 처음부터 저장에 둔다(전에는 suits_state 가 메모리에서만 만들어, 저장 시점에 따라 키가 없었다)
        st["suits"] = {"shared_wear": []}; changed = True
    for key, dflt in (("boxes", []), ("guests", []), ("exp_log", []), ("spots_found", []), ("clues_extra", []),
                      ("spots_visited", []), ("clue_tries", {}), ("spot_visits", {}), ("box_keys", {})):
        if not isinstance(st.get(key), type(dflt)):
            st[key] = type(dflt)(); changed = True
    if "expedition" not in st:
        st["expedition"] = None; changed = True
    for b in st["boxes"]:                                   # S15-A2: 옛 'any'·'unknown' 상자 갈래를 정본으로
        nc = box_cat(b.get("cat"), b.get("id", ""))
        if nc != b.get("cat"):
            b["cat"] = nc; changed = True
    if not st.get("s15_spots_migrated"):
        # 이전 저장: 스캔 문턱을 넘어 이미 '찾은' 1막 스팟은 발견한 것으로 옮긴다(진행이 뒤로 가지 않게)
        for sid in st.get("rumors_seen") or []:
            if sid in DEEP_SPOT_IDS and sid not in st["spots_found"]:
                st["spots_found"].append(sid)
        st["s15_spots_migrated"] = True; changed = True
    # 옛 습격 차출로 밖에 남은 사람(원정이 아닌 outside)은 들어온다 — 이제 outside 는 원정대만이다
    ex = st.get("expedition")
    keep = set((ex or {}).get("members") or [])
    if any(o not in keep for o in st.get("outside") or []):
        st["outside"] = [o for o in st.get("outside") or [] if o in keep]; changed = True
    return changed


def dev_advance(st: dict, sec: float) -> None:
    """★ 개발 전용: 이 방주의 시계를 sec 만큼 앞으로(저장된 시각을 뒤로 민다)."""
    st["created"] -= sec
    st["last_tick"] -= sec
    ex = st.get("expedition")
    if ex:
        for k in ("started", "returns_at", "recalled_at"):
            if isinstance(ex.get(k), (int, float)):
                ex[k] -= sec
    r = st.get("raid")
    if r and isinstance(r.get("started"), (int, float)):
        r["started"] -= sec
    snap = st.get("staff_snapshot")
    if isinstance(snap, dict):
        for k in ("tick_start", "at"):
            if isinstance(snap.get(k), (int, float)):
                snap[k] -= sec
    for b in st.get("boxes") or []:
        if isinstance(b.get("found_ts"), (int, float)):
            b["found_ts"] -= sec
    # S19: 주민 합류 시각·세션 시각도 같이 민다(사슬의 days_since_join, 세션 간격이 시계를 따르게)
    for r_ in (st.get("residents_list") or []) + (st.get("guests") or []):
        for k in ("joined", "arrived"):
            if isinstance(r_.get(k), (int, float)):
                r_[k] -= sec
    ss = (st.get("core") or {}).get("session") or {}
    for k in ("last", "start"):
        if isinstance(ss.get(k), (int, float)):
            ss[k] -= sec


# ─────────────────────────────────────────────────────────────
# S18 7일 플레이테스트 고침 (docs/reports/playtest_7day_20261004.md §5·§6)
#   수치: stakes.json(기획 S18-D) — 키가 없으면 아래 안전값. 문장: 시나리오(S18-S) 키 — 없으면 조용히 생략.
# ─────────────────────────────────────────────────────────────
_STAKES_SAFE.update({
    "events": {"no_repeat_days": 3},                         # TODO(기획): 같은 쪽지가 다시 나오기까지 최소 날
    "shelf": {"additive": True, "stored_max": 60},           # TODO(기획): 창고 선반이 식량창고 선반에 더해진다
    "depth_announce": {"thresholds": [60, 120, 180]},
})


# ── 사실 확인 문장 고르기 ───────────────────────────────────────
# 문장이 전제하는 사실(돌아왔다·아이가 있다·상자를 열었다)을 상태에서 확인한 뒤에만 쓴다.
# 정본은 줄에 붙은 `requires`(시나리오가 dict 줄로 적을 때). 문자열 줄은 아래 표로 전제를 읽는다(임시 안전망).
TEXT_PRESUMES = (("상자 하나 열어", "box_opened"), ("돌아온 뒤", "returned"), ("돌아왔", "returned"),
                 ("아이 손목", "kid"), ("아이가", "kid"), ("아이만", "kid"))


def line_requires(line) -> set:
    if isinstance(line, dict):
        r = line.get("requires")
        return set(r if isinstance(r, list) else [r] if isinstance(r, str) else [])
    text = str(line or "")
    return {need for frag, need in TEXT_PRESUMES if frag in text}


def line_text(line) -> str:
    return line.get("text", "") if isinstance(line, dict) else str(line or "")


def pick_fact_line(lines: list, facts: set, seed: str) -> str | None:
    ok_ = [ln for ln in lines or [] if line_requires(ln) <= facts]
    if not ok_:
        return None
    return line_text(random.Random(seed).choice(ok_))


def ark_facts(st: dict) -> set:
    f = set()
    if any(r.get("role") == "kid" for r in st.get("residents_list") or []):
        f.add("kid")
    return f


# ── 각인 표시: 날 id 대신 이름 ───────────────────────────────────
def parts_display(parts: list | None) -> list:
    out = []
    for p in parts or []:
        q = dict(p)
        ko = str(q.get("ko") or "")
        if "刻 " in ko:
            head, iid = ko.rsplit("刻 ", 1)
            imp = IMPRINTS.get(iid.strip())
            q["ko"] = head + "각인 「" + (imp["name"] if imp else "각인") + "」"
        out.append(q)
    return out


# ── 같은 각인 아침 문장 묶기 ─────────────────────────────────────
def merge_morning(items: list) -> list:
    """같은 날 같은 각인을 받은 사람들은 한 줄로(이름을 잇는다). 줄은 각인 문장 틀에 이름을 다시 넣는다."""
    out, idx = [], {}
    for p in items or []:
        key = (p.get("day"), p.get("imprint_id"))
        if key in idx and p.get("imprint_id"):
            row = out[idx[key]]
            row["residents"].append(p.get("resident"))
            row["resident_ids"].append(p.get("resident_id"))
            imp = IMPRINTS.get(p.get("imprint_id")) or {}
            tpl = ((imp.get("visual") or {}).get("line")) or ""
            row["resident"] = "·".join(row["residents"])
            row["line"] = tpl.replace("{name}", row["resident"]) if tpl else row["line"]
            row["evolved"] = bool(row.get("evolved") or p.get("evolved"))
            continue
        q = dict(p)
        q["residents"] = [p.get("resident")]
        q["resident_ids"] = [p.get("resident_id")]
        idx[key] = len(out)
        out.append(q)
    return out


# ── 쪽지 반복 금지 창 ───────────────────────────────────────────
def recent_event_ids(st: dict) -> set:
    win = int(stk("events.no_repeat_days") or 0)
    day = day_of(st)
    return {eid for eid, d in (st.get("event_days") or {}).items() if day - int(d) < win}


# ── 선반이 자란다 · 넘치면 창고 상자 ─────────────────────────────
def stored_item(st: dict, card: dict) -> dict:
    cat = card.get("category") or "unknown"
    pool = _PROPS.get(cat) or _PROPS.get("unknown") or [{}]
    prop = pool[0] if pool else {}
    return {"id": card.get("id") or f"st-{int(time.time() * 1000)}", "prop_id": prop.get("id"), "name": prop.get("name"),
            "category": cat, "rarity": card.get("rarity"), "family": card.get("family_name") or None,
            "scanned_at": time.time(), "card_id": card.get("id"), "barcode": card.get("barcode"),
            "relic_name": card.get("name"), "polish": 1, "polish_scans": 0, "placed_day": day_of(st),
            "variant": "sea" if card.get("sea_variant") else None}


def store_overflow(st: dict, card: dict) -> dict:
    """선반에 자리가 없으면 창고 상자(목록)에 넣는다 — 사라지지 않고 보인다(플레이테스트 최악 1)."""
    rows = st.setdefault("stored", [])
    it = stored_item(st, card)
    rows.append(it)
    del rows[:-int(stk("shelf.stored_max") or 60)]
    return it


def swap_candidates(st: dict, n: int = 3, width: int = 1) -> list:
    """꽉 찼을 때 바꿀 후보 — 가장 덜 닦인 것, 같으면 오래된 것. S19: 빼면 새 물건(폭 width)이 들어가는 칸만."""
    rows = sorted(st.get("shelf") or [], key=lambda it: (polish_level(it), float(it.get("scanned_at") or 0)))
    if width > 1:
        cap = shelf_capacity(st)
        fit = []
        for it in rows:
            used = set()
            for x in st.get("shelf") or []:
                if x is it:
                    continue
                for c_ in range(int(x["slot"]), int(x["slot"]) + prop_width(x.get("prop_id", ""))):
                    used.add(c_)
            if any(all(c_ not in used for c_ in range(a, a + width)) for a in range(0, cap - width + 1)):
                fit.append(it)
        rows = fit
    return [{"slot": it.get("slot"), "name": it.get("name"), "relic_name": it.get("relic_name"),
             "category": it.get("category"), "rarity": it.get("rarity"), "polish": polish_level(it)} for it in rows[:n]]


def stored_public(st: dict) -> list:
    keys = ("id", "prop_id", "name", "relic_name", "category", "rarity", "family", "barcode", "variant", "scanned_at")
    return [dict({k: it.get(k) for k in keys}, polish=polish_level(it)) for it in st.get("stored") or []]


def shelf_try_put(st: dict, it: dict) -> int | None:
    """창고 상자 물건 하나를 선반 빈 칸에 놓는다(소품 폭을 지킨다)."""
    cap = shelf_capacity(st)
    used = set()
    for x in st.get("shelf") or []:
        for c in range(int(x["slot"]), int(x["slot"]) + prop_width(x.get("prop_id", ""))):
            used.add(c)
    w = prop_width(it.get("prop_id") or "")
    for start in range(0, cap - w + 1):
        if all(c not in used for c in range(start, start + w)):
            row = dict(it)
            row["slot"] = start
            row.pop("id", None)
            st.setdefault("shelf", []).append(row)
            return start
    return None


# ── 첫 주 위협 보장 ─────────────────────────────────────────────
def first_week_guarantee() -> dict:
    """threats.json first_week_guarantee(기획 S18-D): by_day 까지 위협이 없었으면 creature·severity 로 고정,
    대상은 사람이 서 있는 방(target=occupied_room). until_day 는 by_day 를 넘겨 들어온 사람도 받게 하는 끝."""
    g = (combat.THR.get("first_week_guarantee") or {}) if isinstance(combat.THR.get("first_week_guarantee"), dict) else {}
    return {"by_day": int(g.get("by_day", 4)), "until_day": int(g.get("until_day", 7)),
            "creature": g.get("creature"), "severity": g.get("severity"), "target": g.get("target")}


# ── 깊이 문턱 방송 ─────────────────────────────────────────────
def depth_check(st: dict) -> list:
    """거점 깊이가 처음 문턱(60·120·180m)을 넘은 날 한 번. 문장은 시나리오 키(ui_moments depth.cross.<m>)."""
    marks = st.setdefault("depth_marks", [])
    d = depth_of(st)
    out = []
    for m in sorted(int(x) for x in (stk("depth_announce.thresholds") or [])):
        if d >= m and m not in marks:
            marks.append(m)
            text = moment(f"depth.first_{m}") or moment(f"depth.cross.{m}") or moment("depth.cross", m=m)
            row = {"m": m, "zone": depth_zone(m), "ko": text, "day": day_of(st)}
            out.append(row)
            day_note(st, "depth", m)
            overnight_add(st, "depth", row)
    return out


# ── 아침 「밤사이」 한 장 ───────────────────────────────────────
def overnight_add(st: dict, kind: str, payload) -> None:
    ov = st.setdefault("overnight", {"items": []})
    items = ov.setdefault("items", [])
    key = f"{kind}|{json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)[:200]}"
    if any(it.get("key") == key for it in items):
        return
    items.append({"kind": kind, "key": key, "day": day_of(st), "at": time.time(), "data": payload})
    del items[:-40]


def overnight_public(st: dict) -> dict | None:
    ov = st.get("overnight") or {}
    items = [{k: v for k, v in it.items() if k != "key"} for it in ov.get("items") or []]
    if not items:
        return None
    if FIRST_ENTRY_GATE and first_entry(st):          # PM 첫 세션: 새 방주에 「자리 비우신 사이」는 맞지 않는다
        fe = (moments().get("morning") or {}).get("first_entry") or {}
        if not (isinstance(fe, dict) and fe.get("title")):
            return None
        return {"items": items, "title": fe.get("title"), "open": fe.get("open"), "close": fe.get("close") or moment("morning.close"),
                "count": len(items), "band": "first_entry", "first_entry": True}
    order = {"night_judge": 0, "expedition_return": 1, "depth": 2, "imprint": 3, "octopus": 4, "knock": 5, "wish": 6,
             "overflow": 7, "visit": 8, "needs": 9, "keepsake": 10, "arc_morning": 11}
    items.sort(key=lambda it: (order.get(it["kind"], 9), it["at"]))
    h = now_hour()
    band = "morning" if 5 <= h < 11 else "day" if 11 <= h < 17 else "evening" if 17 <= h < 21 else "night"
    bt = ((moments().get("morning") or {}).get("by_time") or {}).get(band) or {}
    return {"items": items, "title": bt.get("title") or moment("morning.title"), "open": bt.get("open") or moment("morning.open"),
            "close": moment("morning.close"), "count": len(items), "band": band}


# ── S18-D 재스캔 감쇠 · 자원 저장 상한 · 재료 출처 · 공방 바꾸기 · 값 0 반응 ──────────────
def rescan_mult(prev: int) -> float:
    """economy.json scan.rescan_decay.values(기획 S18-D [1, .5, .25, .1]). 표 끝 값이 바닥(네 번째부터 0.1).
    표가 없으면 엔진의 예전 감쇠."""
    vals = (((_ECON_ALL.get("scan") or {}).get("rescan_decay") or {}).get("values"))
    if not isinstance(vals, list) or not vals:
        return rescan_multiplier(prev)
    i = max(0, int(prev))
    return float(vals[i] if i < len(vals) else vals[-1])


def rescan_window_days() -> int:
    v = (((_ECON_ALL.get("scan") or {}).get("rescan_decay") or {}).get("window_days"))
    return int(v) if isinstance(v, (int, float)) else 7


STOCK_KEYS = ("food", "water", "med", "parts", "cloth", "trade", "knowledge", "scrap", "chem", "power")


def storage_cap(st: dict) -> int | None:
    """재료 한 가지당 저장 상한(economy.json rooms.storage_cap). 정본 글: 「창고 선반 수 × 6
    (창고 없음 4칸 → 24 / Lv1 6 → 36 / Lv2 12 → 72 / Lv3 20 → 120)」. 구조 키(per_shelf·no_storage_shelves)가
    오면 그것을, 없으면 그 글의 숫자를 쓴다. 표가 아예 없으면 상한 없음."""
    sc = (_ECON.get("storage_cap") or {}) if isinstance(_ECON.get("storage_cap"), dict) else {}
    if not sc:
        return None
    per = int(sc.get("per_shelf", 6))
    none_ = int(sc.get("no_storage_shelves", 4))
    best = max([shelves_of(r) for r in live_rooms(st) if r["id"] == "storage"] or [none_])
    return per * best


def apply_storage_cap(st: dict, before: dict | None) -> dict:
    """넘치는 분은 들어오지 않는다. 이미 넘쳐 있던 재고는 깎지 않는다(늘지만 않게) — 넘쳐서 버린 양을 돌려준다."""
    cap = storage_cap(st)
    lost: dict = {}
    if cap is None:
        return lost
    res = st.get("resources") or {}
    for k in STOCK_KEYS:
        v = int(res.get(k, 0) or 0)
        b = int((before or {}).get(k, 0) or 0)
        if v > cap and v > b:
            keep = max(b, cap)
            lost[k] = v - keep
            res[k] = keep
    if lost:
        # S19(플레이테스트 2차 새 문제 1): 말없이 버리지 않는다 — 식량·물 5 → 사기 1, 그 밖 4 → 교역 1(⚠ 임시 비율), 밤사이에 한 줄
        day = day_of(st)
        prev = st.get("storage_overflow") if (st.get("storage_overflow") or {}).get("day") == day else None
        tot = dict((prev or {}).get("lost") or {})
        for k, v in lost.items():
            tot[k] = int(tot.get(k, 0)) + int(v)
        carry = dict(st.get("overflow_carry") or {})
        to_table = 0
        for k, v in lost.items():
            if k in ("food", "water") and TABLE_STORE_FIRST:     # S23: 넘친 식량·물은 한 상 몫부터 채운다
                core_ = core_of(st)
                room_ = max(0, TABLE_STORE_MAX - int(core_.get("table_store") or 0))
                put = min(room_, int(v))
                core_["table_store"] = int(core_.get("table_store") or 0) + put
                to_table += put
                v = int(v) - put
            g = "morale" if k in ("food", "water") else "trade"
            carry[g] = int(carry.get(g, 0)) + int(v)
        conv = dict((prev or {}).get("converted") or {})
        for g, rate in (("morale", OVERFLOW_RATE["to_morale"]), ("trade", OVERFLOW_RATE["to_trade"])):
            n = int(carry.get(g, 0)) // rate
            if g == "morale":                         # S20: 넘침 사기는 하루 morale_per_day_max 까지
                n = max(0, min(n, OVERFLOW_RATE["morale_day_max"] - int(conv.get("morale", 0))))
                if not n and int(carry.get(g, 0)) >= rate:
                    carry[g] = rate - 1               # 상한에 닿은 날의 넘침은 쌓아 두지 않는다
            if n:
                res[g] = int(res.get(g, 0)) + n
                conv[g] = int(conv.get(g, 0)) + n
                carry[g] = int(carry.get(g, 0)) - n * rate
        st["overflow_carry"] = carry
        what = " · ".join(f"{RES_KO_SRV.get(k, k)} {v}개" for k, v in tot.items())
        got = " · ".join(f"{RES_KO_SRV.get(k, k)} {v}" for k, v in conv.items() if v)
        gotm = " · ".join(f"{RES_KO_SRV.get(k, k)}를 {v}" for k, v in conv.items() if v)
        ko = moment("storage.overflow", what=what, got=got) or \
            (f"창고가 차서 {what}는 들이지 못했습니다." + (f" 대신 {gotm} 올려 두었습니다." if gotm else " 조금 더 모이면 사기·교역품으로 바꿔 두겠습니다."))
        st["storage_overflow"] = {"day": day, "lost": tot, "converted": conv, "ko": ko}
        ov = st.setdefault("overnight", {"items": []}).setdefault("items", [])
        ov[:] = [it for it in ov if not (it.get("kind") == "overflow" and it.get("day") == day)]
        ov.append({"kind": "overflow", "key": f"overflow|{day}", "day": day, "at": time.time(),
                   "data": {"lost": tot, "converted": conv, "ko": ko}})
    return lost


def storage_public(st: dict) -> dict:
    cap = storage_cap(st)
    res = st.get("resources") or {}
    return {"cap": cap, "full": [k for k in STOCK_KEYS if cap is not None and int(res.get(k, 0)) >= cap],
            "overflow": st.get("storage_overflow") if (st.get("storage_overflow") or {}).get("day") == day_of(st) else None}


MATERIAL_SOURCES = {k: v for k, v in (_ECON_ALL.get("material_sources") or {}).items() if not str(k).startswith("_")} \
    if isinstance(_ECON_ALL.get("material_sources"), dict) else {}


def zero_reaction(st: dict, uid: str, code: str, card, mult: float, polish: dict | None) -> dict | None:
    """값이 낮은 재스캔(감쇠 < 1)에 작은 반응 하나(stakes polish.zero_reaction.order 의 첫 해당). 표시용 — 문어만 사기 +0.1."""
    if mult >= 1.0:
        return None
    zr = (stk("polish.zero_reaction") or {}) if isinstance(stk("polish.zero_reaction"), dict) else {}
    order = zr.get("order") or ["box_key_hint", "polish_progress", "wish_hint", "octopus_mood"]
    cat = card.category.value
    for kind in order:
        if kind == "box_key_hint":
            if int((st.get("box_keys") or {}).get(code, 0)) == day_of(st) and \
                    any(b["cat"] in (cat, "blank") for b in st.get("boxes") or []):
                return {"kind": kind, "ko": moment("zero.box_key_hint")}
        elif kind == "polish_progress":
            if polish and polish.get("counted_today"):
                ko_, key_ = rescan_low_line(st)
                return {"kind": kind, "scans": polish.get("scans"), "next_at": polish.get("next_at"),
                        "ko": ko_ or moment("zero.polish_progress"), "key": key_ or "zero.polish_progress"}
        elif kind == "wish_hint":
            wh = core_of(st)["flags"].setdefault("wish_hint_day", {})     # S19: 같은 사람 바람 힌트는 하루 한 번(되풀이 막기)
            for w in wishes_public(st, uid):
                if wh.get(w["resident_id"]) == day_of(st):
                    continue
                h = (next((x for x in WISHES if x["id"] == w["id"]), {}).get("condition") or {}).get("hint") or {}
                if not w["done"] and cat in (h.get("category"), h.get("props_category")):
                    wh[w["resident_id"]] = day_of(st)
                    return {"kind": kind, "resident": w["name"], "resident_id": w["resident_id"],
                            "ko": moment("zero.wish_hint", name=w["name"])}
        elif kind == "octopus_mood":
            oc = st.get("octopus")
            if oc:
                day = day_of(st)
                if oc.get("mood_day") != day:
                    oc["mood_day"], oc["mood_n"] = day, 0
                if int(oc.get("mood_n") or 0) < 3:
                    oc["mood_n"] = int(oc.get("mood_n") or 0) + 1
                    frac = float(st.get("morale_frac") or 0) + 0.1
                    if frac >= 1.0 - 1e-9:
                        st["resources"]["morale"] = int(st["resources"].get("morale", 0)) + 1
                        frac -= 1.0
                    st["morale_frac"] = round(frac, 3)
                    return {"kind": kind, "ko": moment("zero.octopus_mood")}
    ko_, key_ = rescan_low_line(st)
    if ko_:
        return {"kind": "rescan_low", "ko": ko_, "key": key_}
    if mult <= 0.1 + 1e-9:
        rz = ((moments().get("shelf") or {}).get("rescan_zero")) or []
        if rz:
            return {"kind": "rescan_zero", "ko": random.Random(f"{uid}|{code}|{day_of(st)}|rz").choice(rz)}
    return None


class TradeIn(BaseModel):
    uid: str
    give: str            # food | water
    get: str             # cloth | parts | scrap
    n: int = 1


@app.post("/api/workshop/trade")
def workshop_trade(inp: TradeIn):
    """공방 바꾸기(economy.json workshop_trade): 식량·물 rate 개 → 막힌 재료 1개. 하루 daily_out_cap 개까지,
    바꾼 뒤에도 내는 쪽 재고가 keep_reserve 이상이어야 한다. 나쁜 비율이라 찍기를 대신하지 못한다(B5)."""
    T = _ECON_ALL.get("workshop_trade") or {}
    if not isinstance(T, dict) or not T:
        raise HTTPException(400, "바꾸기 표가 없습니다")
    st = load_state(inp.uid)
    tick_production(st)
    if inp.give not in (T.get("from") or []) or inp.get not in (T.get("to") or []):
        raise HTTPException(400, "그건 바꿀 수 없습니다")
    if not any(r["id"] == "workshop" for r in live_rooms(st)):
        raise HTTPException(400, "공방이 있어야 바꿀 수 있습니다")
    day = day_of(st)
    if st.get("trade_day") != day:
        st["trade_day"], st["trade_out"] = day, 0
    n = max(1, int(inp.n))
    cap = int(T.get("daily_out_cap", 2))
    if int(st.get("trade_out") or 0) + n > cap:
        raise HTTPException(400, f"오늘은 {cap - int(st.get('trade_out') or 0)}개까지만 바꿀 수 있습니다")
    cost = int(T.get("rate", 4)) * n
    have = int(st["resources"].get(inp.give, 0))
    if have - cost < int(T.get("keep_reserve", 12)):
        raise HTTPException(400, f"{RES_KO_SRV.get(inp.give, inp.give)}을(를) {int(T.get('keep_reserve', 12))}개는 남겨야 합니다")
    st["resources"][inp.give] = have - cost
    st["resources"][inp.get] = int(st["resources"].get(inp.get, 0)) + n
    st["trade_out"] = int(st.get("trade_out") or 0) + n
    save_state(inp.uid, st)
    log(inp.uid, "workshop_trade", {"give": inp.give, "get": inp.get, "n": n})
    return {"ok": True, "paid": {inp.give: cost}, "got": {inp.get: n}, "left_today": cap - st["trade_out"],
            "state": public_state(st, inp.uid)}


# ─────────────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────────────
class ScanIn(BaseModel):
    uid: str
    barcode: str
    user_category: str | None = None
    user_subtype: str | None = None    # PM 첫 세션 큐 ③: 한 번에 고르기(peek.quick_pick) — 갈래와 하위 종류를 같이
    source: str | None = None          # S24: "manual" = 손으로 친 숫자(전역 이름 투표·집계에서 뺀다)


@app.get("/api/peek")
def peek(barcode: str, uid: str | None = None):
    """스캔 직전: 카테고리를 유저에게 물어야 하는지 알려준다.
    S13: uid 를 주면 그 방주에서 이 바코드에 고정된 카테고리(category_lock)가 있을 때 묻지 않는다."""
    try:
        code = GEN.normalize(barcode)
    except ValueError as e:
        raise HTTPException(400, str(e))
    parsed = GEN.parse(code)
    cat = GEN.infer_category(parsed)
    locked = None
    if uid and stk("category_lock") and cat == Category.UNKNOWN and ark_exists(uid):
        locked = ((load_state(uid).get("barcodes") or {}).get(code) or {}).get("category")
    need_cat = cat == Category.UNKNOWN and not locked
    return {"barcode": code, "known_category": None if cat == Category.UNKNOWN else cat.value,
            "needs_category": need_cat, "locked_category": locked,
            "quick_pick": quick_pick_for(load_state(uid) if uid and ark_exists(uid) else None, uid or "", code) if need_cat else None,
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
                           (inp.uid, code, time.time() - rescan_window_days() * 86400)).fetchone()["c"]
    if today >= DAILY_SCAN_CAP:
        raise HTTPException(429, "오늘의 성문 해독 상한에 도달했습니다 (20회).")

    # S13 카테고리 고정(stakes category_lock): 이 방주에서 그 바코드에 처음 정해진 카테고리를 다시 쓴다.
    # 모르는 가문 바코드가 고르는 카테고리마다 다른 유물(평균 7개)이 되던 구멍 — 같은 바코드 = 같은 유물.
    bmeta = st.setdefault("barcodes", {}).setdefault(code, {})
    locked = bmeta.get("category") if stk("category_lock") else None
    pick_cat = locked or inp.user_category
    qp_sub = quick_pick_apply(st, inp, code, bmeta, pick_cat)     # 큐 ③: 한 번에 고른 하위 종류를 먼저 적어 둔다
    card = GEN.generate(code, hour=now_hour(), user_category=pick_cat,
                        user_subtype=bmeta.get("subtype"))      # S22: 이 방주가 정한 하위 종류(없으면 예전 그대로)
    if card.category != Category.UNKNOWN and not bmeta.get("category"):
        bmeta["category"] = card.category.value       # 정체불명(고르지 않음)은 고정하지 않는다 — 다음에 고를 수 있게
    mult = rescan_mult(prev)
    gained = {k: int(round(v * mult)) for k, v in card.yields.items() if round(v * mult) >= 1}
    for k, v in gained.items():
        st["resources"][k] = st["resources"].get(k, 0) + v
    if card.category == Category.BOOK:
        eff = role_effects(st)
        st["blueprint_progress"] += eff["blueprint_rate"]
        if eff["book_bonus"]:
            gained["knowledge"] = gained.get("knowledge", 0) + eff["book_bonus"]; st["resources"]["knowledge"] += eff["book_bonus"]

    # S13 변형(바다 무늬): 바코드 + ISO 주. 수치 보상은 없다
    var = sea_variant(code)
    if (not var["shiny"] and beat_today_id(st) == "first_shelf_visitor_variant" and mult >= 1.0
            and core_of(st)["flags"].get("variant_forced_day") != day):
        var = dict(var, id="sea", shiny=True, forced=True)       # S19 비트 12: 첫 물빛 변형 보장(그날 새 물건 하나)
        core_of(st)["flags"]["variant_forced_day"] = day
    if var["shiny"]:
        var["ko"] = moment("variant.found", item=card.name)

    # 도감
    cx = st["codex"].setdefault(card.category.value, {})
    first_time = card.name not in cx
    cx[card.name] = cx.get(card.name, 0) + 1
    ensure_codex_meta(st, inp.uid)
    codex_note(st, card.category.value, card.name, card.rarity.value, var["shiny"])

    # 손패 (대항용). 정체불명은 대항 태그가 없으므로 손패에 넣지 않음
    card_d = card.to_dict()
    card_d["id"] = f"{code}-{int(time.time()*1000)}"
    card_d["sea_variant"] = var["shiny"]
    card_d["subtype_ko"] = sub_ko(card_d["category"], card_d.get("subtype")) if card_d.get("subtype") else None
    card_d["history"] = card_history(st, code)              # S22 ②: 이 바코드를 전에 누구에게 줬나
    usable_tags = [t for t in card.tags if t != "미확인"]
    if mult > 0 and usable_tags and len(st["hand"]) < HAND_LIMIT:
        st["hand"].append(card_d)
    # E1 — 찍은 물건이 선반에 놓인다. S13: **이미 선반에 있는 바코드면 새 칸을 먹지 않고 닦는다**
    # (감쇠 0.5·0.1 재스캔이 같은 물건을 한 칸 더 놓던 버그의 수정). 값이 0인 재스캔도 닦는다.
    polish = None
    stored, swap_offer = None, None
    have_it = shelf_item_for(st, code)
    if have_it:
        polish = polish_item(st, have_it, card.name)
        if var["shiny"] and not have_it.get("variant"):
            have_it["variant"] = "sea"
        shelf_slot, shelf_new = have_it.get("slot"), False
    else:
        card_d["_day"] = day
        shelf_slot = shelf_place(st, card_d) if mult > 0 else None
        card_d.pop("_day", None)
        shelf_new = shelf_slot is not None
        if shelf_slot is None and mult > 0 and shelf_capacity(st):
            # S18: 선반이 꽉 찼다 — 사라지지 않고 창고 상자에 들어가고, 바꿀지 묻는다
            stored = store_overflow(st, card_d)
            ssn = core_of(st)["session"].get("n")
            if core_of(st)["flags"].get("shelf_full_ses") != ssn:   # S27: 세션에 한 번만 묻는다
                core_of(st)["flags"]["shelf_full_ses"] = ssn
                swap_offer = {"stored_id": stored["id"], "candidates": swap_candidates(st, width=prop_width(stored.get("prop_id") or "")),
                              "ko": moment("shelf.full.prompt", item=card.name),
                              "kept_ko": moment("shelf.full.kept", item=card.name)}
            else:
                stored = dict(stored, quiet_ko=moment("shelf.full.kept", item=card.name))

    # 가문 크라우드소싱
    manual = (inp.source or "").lower() == "manual"
    if inp.user_category and card.family_code not in GEN.families and not manual and not vote_excluded(inp.uid, st):
        with db() as con:
            con.execute("INSERT INTO family_votes VALUES(?,?,?,?)", (inp.uid, card.family_code, inp.user_category, time.time()))

    with db() as con:
        con.execute("INSERT INTO scans(uid,barcode,category,rarity,mult,ts,day,source) VALUES(?,?,?,?,?,?,?,?)",
                    (inp.uid, code, card.category.value, card.rarity.value, mult, time.time(), day,
                     "manual" if manual else "camera"))
    # S13 첫 만남(가문 먼저) · 가문 세트(서로 다른 바코드 수, 방금 넣은 스캔 포함) · 바람
    first_meet = first_meet_lines(st, card.category.value, card.family_code)
    if qp_sub:                                              # 한 번에 고른 하위 종류에 맞춘 첫 만남 줄로 바꾼다
        first_meet = [first_meet_sub(card_d_name_cat(card), qp_sub, card.name) if m.get("kind") == "category" else m for m in first_meet]
    # S15 봉인 상자: 같은 갈래 바코드가 열쇠다(값 0 인 재스캔도). 가장 오래된 것 하나, 같은 바코드는 하루 한 상자
    box_opened = box_try_scan(st, inp.uid, code, card.category.value)
    zr_ = zero_reaction(st, inp.uid, code, card, mult, polish) if not box_opened else None
    fam_set = family_set_check(st, inp.uid, card.family_code)
    wishes_new = wishes_tick(st, inp.uid)
    # S19 「어디로」: 이 한 점을 누구에게, 어디에(CORE_LOOP_A §1). 스캔이 놓은 자리(선반·창고 상자·사본)를 기억해 둔다
    cc = core_of(st)
    heir_up = heirloom_polish_tick(st, inp.uid, code)       # S25 닦아 오르기
    first_rare_tick(st, card_d)                             # S25 가보 칸 해금
    heir_open_tick(st, card_d)                              # S30: 3일째 이후 그날 첫 귀함 카드 = 가보 칸이 열리는 순간
    keep_note = keep_note_tick(st, card_d)                  # PM 첫 세션: 가보 칸이 열리기 전 귀함 카드는 「간직할 것」
    if qp_sub:
        ssq = cc.setdefault("seen_subtypes", {}).setdefault(card_d["category"], [])
        if qp_sub not in ssq:
            ssq.append(qp_sub)
    ss_ = cc["session"]
    ss_["scans"] = int(ss_.get("scans") or 0) + 1
    if ss_.get("last") and time.time() - float(ss_["last"]) <= SESSION_GAP_SEC:
        ss_["last"] = time.time()                    # S21: 찍는 동안은 같은 세션
    item_ = item_from_card(card_d)
    cc["scans"][card_d["id"]] = {"item": item_, "day": day, "given": False, "at": time.time(), "barcode": code, "manual": manual,
                                 "placed": "shelf" if shelf_new else ("stored" if stored else "copy")}
    if card_d.get("subtype"):
        ssub = cc.setdefault("seen_subtypes", {}).setdefault(card_d["category"], [])
        if card_d["subtype"] not in ssub:
            ssub.append(card_d["subtype"])
    for k_ in list(cc["scans"])[:-80]:                 # S21: 넣은 순서대로 오래된 것부터(날 정렬은 순서를 섞을 수 있었다)
        cc["scans"].pop(k_, None)
    where = where_for(st, inp.uid, item_, compact=int(ss_.get("scans") or 0) > 1)
    cc["scans"][card_d["id"]]["warm"] = list(where.get("warm_ids") or [])
    cc["scans"][card_d["id"]]["first_meet_cat"] = any(m.get("kind") == "category" for m in first_meet or [])
    cc["scans"][card_d["id"]]["chain"] = [{"rid": x["target"].get("resident_id"), "name": x.get("name"), "tier": x["tier"]}
                                          for x in where.pop("_internal", None) or where.get("suggest") or []
                                          if x["tier"] in ("chain_beat", "memory") and x["kind"] == "resident"]
    where["subtype_pick"] = subtype_pick_for(st, code, card_d, bmeta, inp.uid)
    where["rename"] = rename_offer(st, card_d, bmeta) if not where["subtype_pick"] else None   # S27 ⑥ 이미 이름 붙인 바코드
    if manual and where["subtype_pick"]:
        where["subtype_pick"].update({"suggest": None, "suggest_ko": None})
    first_beat = beat_public(st, inp.uid) if first_scan_beat_due(st) else None
    save_state(inp.uid, st)
    log(inp.uid, "scan", {"barcode": code, "rarity": card.rarity.value, "category": card.category.value, "mult": mult,
                          "locked": bool(locked), "variant": var["id"], "polish": (polish or {}).get("level"),
                          "family_set": (fam_set or {}).get("just_completed")})
    # 스캔은 버튼이 아니라 세계에 물자가 도착하는 장면이다(WORLD_PRESENTATION §1-3) → 두 AI 중 하나가 한 줄 읊는다
    vseed = f"{inp.uid}|{code}|{today}"
    cat = card.category.value
    _act = int(st.get("act") or 1)
    voice = voice_for(f"scan_{cat}", vseed, act=_act) or voice_for(SCAN_VOICE_FALLBACK.get(cat, ""), vseed, act=_act)
    return {"card": card_d, "gained": gained, "rescan_multiplier": mult, "first_time": first_time,
            "shelf_slot": shelf_slot, "shelf_new": shelf_new,
            "category_locked": locked, "variant": var, "polish": polish,
            "first_meet": first_meet, "family_set": fam_set, "wishes_done": wishes_new,
            "box_opened": box_opened,
            "stored": stored, "swap_offer": swap_offer,
            "zero_reaction": zr_,
            "where": where,
            "heirloom_ascend": heir_up, "keep_note": keep_note,
            "unlock_new": unlock_new(st, inp.uid, heir_screen=bool(where.get("heirloom")) or None) if CALENDAR_ENFORCE else [],   # S30·S31: 가보 칸 방송은 고를 화면과 함께
            "beat_today": first_beat,                     # PM 첫 세션: 첫 스캔 뒤에 첫 비트
            "scans_today": today + 1, "scan_cap": DAILY_SCAN_CAP, "resources": st["resources"], "voice": voice,
            "storage": storage_public(st)}


# ── 이어하기 API ──────────────────────────────────────────────
def ark_exists(uid: str) -> bool:
    with db() as con:
        return con.execute("SELECT 1 FROM arks WHERE uid=?", (uid,)).fetchone() is not None


@app.get("/api/account")
def account(uid: str):
    """이 방주의 복구 코드. 처음 물으면 그 자리에서 발급된다(기존 uid 사용자 포함).
    **이미 있는 방주에만** 발급한다 — 아무 uid 로 물어 빈 방주가 쌓이지 않게(리뷰 2026-10-03)."""
    if not ark_exists(uid):
        raise HTTPException(404, "아직 없는 방주입니다")
    st = load_state(uid)
    code = issue_code(uid)
    return {"uid": uid, "code": code, "pretty": code_pretty(code),
            "day": day_of(st), "rooms": len(st.get("rooms") or []),
            "residents": len(st.get("residents_list") or []),
            "ko": "이 여섯 글자가 방주의 열쇠다. 적어 두면 다른 기계에서도 이어서 할 수 있다."}


class RestoreIn(BaseModel):
    code: str


@app.post("/api/account/restore")
def account_restore(inp: RestoreIn, request: Request):
    """코드로 다른 기기에서 이어하기. 계정도 비밀번호도 없다 — 코드가 곧 방주다."""
    ip = (request.client.host if request.client else "?") or "?"
    wait = restore_gate(ip)
    if wait > 0:
        raise HTTPException(429, f"너무 여러 번 틀렸습니다. {int(wait) + 1}초 뒤에 다시 적어 주세요")
    code = normalize_code(inp.code)
    if not code:
        restore_failed(ip)
        raise HTTPException(400, f"{CODE_LEN}글자를 적어 주세요 (0·O·1·I 는 코드에 없습니다)")
    uid = uid_for_code(code)
    if not uid:
        restore_failed(ip)
        raise HTTPException(404, "그런 코드는 없습니다. 적어 둔 것을 다시 봐 주세요")
    st = load_state(uid)
    log(uid, "restore", {"code": code})
    return {"uid": uid, "code": code, "pretty": code_pretty(code), "day": day_of(st),
            "rooms": len(st.get("rooms") or []), "residents": len(st.get("residents_list") or []),
            "ko": f"{day_of(st)}일째 방주로 돌아왔다."}


@app.get("/api/ark")
def get_ark(uid: str, debug_act: int | None = Query(None, description="★ 개발 전용(DEV ONLY): 이 방주의 막(1 심해/2 터널/3 지상)을 바꾼다. 막별 사건 풀 검증용. RELIC_DEV=1 에서만 동작한다."),
            debug_night: int | None = Query(None, description="★ 개발 전용(DEV ONLY): 밤 자동 판정 시각을 기다리지 않고 지금 판정한다. RELIC_DEV=1 에서만.")):
    if debug_night and not DEV_MODE:
        raise HTTPException(404, "없는 질의입니다")
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
    # S19: 이미 한 번 내려간 밤사이 항목은 다음 날 저절로 비운다(닫기만 하고 「확인」을 안 눌러도 쌓이지 않게)
    ov_ = st.get("overnight") or {}
    if ov_.get("items"):
        ov_["items"] = [it for it in ov_["items"] if not (it.get("shown_day") is not None and int(it["shown_day"]) < day)]
    beat_play_tick(st)                             # S19 켠 날 차례(비트가 그날 콘텐츠를 고정하므로 day_tick 앞)
    ticked = day_tick(st, uid, force_night=bool(debug_night) and DEV_MODE)
    core_t = core_tick(st, uid)
    # 각인의 다음 날 아침: 밀린 연출 문장을 한 번만 내려보내고 큐에서 뺀다
    pending = st.get("morning_pending") or []
    morning = merge_morning([p for p in pending if p.get("day", 0) <= day])   # S18: 같은 각인은 한 줄로
    if morning:
        st["morning_pending"] = [p for p in pending if p.get("day", 0) > day]
        for m_ in morning:
            overnight_add(st, "imprint", {"imprint_id": m_.get("imprint_id"), "residents": m_.get("residents"),
                                          "line": m_.get("line"), "imprint_name": m_.get("imprint_name")})
    first_light = not st.get("greeted")            # 이 방주의 첫 화면 — 리더의 첫 말
    if first_light:
        st["greeted"] = True
    save_state(uid, st)
    out = public_state(st, uid)
    out["produced_while_away"] = produced
    out["consumed_while_away"] = st.pop("_consumed_now", None)
    out["night_judge"]["report"] = ticked["night_judge"]
    out["knock"] = ({"guest_id": ticked["knock"]["guest_id"], "name": ticked["knock"]["name"],
                     "role": ticked["knock"]["role"]} if ticked.get("knock") else None)
    out["wishes_new"] = ticked["wishes_new"]
    if (ticked.get("octopus") or {}).get("arrival"):
        out["octopus"]["arrival"] = ticked["octopus"]["arrival"]
    out["rooms_catalog"] = ROOMS
    out["morning_lines"] = morning
    out["overnight"] = overnight_public(st)
    out["depth_crossed"] = ticked.get("depth_crossed") or []
    # ── S19 (docs/API_S19.md §3~§7) ──
    if out["overnight"] and core_t["session"].get("new") and any(
            it["kind"] in ("night_judge", "expedition_return", "knock", "depth", "wish", "imprint")
            for it in out["overnight"]["items"]):
        big_take(st)                                       # 큰 소식이 든 밤사이 한 장은 큰 창 하나(필요·방문 줄만이면 아님)
    for it in (st.get("overnight") or {}).get("items") or []:
        it.setdefault("shown_day", day)
    eu = st.get("exp_unseen")
    if isinstance(eu, dict):                          # S29 r6-3: 귀환 소식은 한 세션만(화면이 seen 을 못 불러도)
        sn_ = core_t["session"].get("n")
        if eu.get("_ses") is None:
            eu["_ses"] = sn_
        elif eu["_ses"] != sn_:
            st["exp_unseen"] = None
            out["expedition_return"] = None
    out["visits"] = core_of(st)["visits"].get("rows") or []
    out["beat_today"] = beat_public(st, uid)
    out["next_visit"] = next_visit_public(st, uid)
    ss = core_of(st)["session"]
    out["session"] = {"n": ss.get("n"), "new": bool(ss.get("new")), "big_windows": int(ss.get("big") or 0),
                      "big_left": max(0, BIG_WINDOWS_PER_SESSION - int(ss.get("big") or 0)), "evening": is_evening()}
    arc_new = [x for x in core_of(st)["arc_log"] if not x.get("shown")]
    for x in arc_new:
        x["shown"] = True
    out["arc_events"] = [{k: v for k, v in x.items() if k != "shown"} for x in arc_new]
    out["shelf_autofill"] = core_t.get("autofill") or []
    out["octopus_gift_where"] = octopus_gift_where(st, uid)
    out["decor_trace"] = decor_trace(st, uid)
    out["visitors_book"] = visitors_book(st)
    out["missed_chain"] = missed_chain_of(st, uid)
    out["evening_table"] = evening_table_public(st, uid)
    out["unlocked"] = unlocked_public(st)
    out["unlocked"]["new"] = unlock_new(st, uid)
    out["next_visit"], out["tomorrow_ask"], out["leave_order"] = leave_lines(st, uid, nv=out["next_visit"])
    out["memory_wall"] = memory_wall_public(st, uid)
    out["notebook_tip"] = (core_of(st).get("gossip") or {}) if (core_of(st).get("gossip") or {}).get("day") == day else None
    out["novelty"] = core_t.get("novelty")
    out["wishes_new"] = list(out.get("wishes_new") or []) + wishes_tick(st, uid)
    save_state(uid, st)
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


def spot_found(st: dict, uid: str, sid: str) -> bool:
    """S15(DECISIONS 2026-10-03 ④): 1막 스팟은 **원정으로 가서 찾아야** 발견이다. 스캔 문턱은 단서(spot_clue)다.
    지상(3막) 스팟은 원정이 아직 없어 예전 규칙(스캔 문턱 = 발견)을 그대로 쓴다."""
    if sid in DEEP_SPOT_IDS:
        return sid in (st.get("spots_found") or [])
    if sid in (st.get("rumors_seen") or []):
        return True
    gate = spot_gate(sid, next((x for x in SPOTS if x.get("id") == sid), None))
    if not gate:
        return False
    counts = scan_counts(uid)
    return sum(counts.get(c, 0) for c in gate["categories"]) >= gate["need"]


def room_level_of(st: dict, rid: str) -> int:
    """그 종류의 방 중 가장 높은 레벨(홀은 방주 하나에 하나, 상태에 따로 있다). 없으면 0."""
    if rid == HALL_ID:
        return int(st.get("hall_level") or 1)
    lv = [room_level(r) for r in live_rooms(st) if r["id"] == rid]
    if rid == "airlock" and (st.get("entrance_airlock") or {}).get("level"):
        lv.append(int(st["entrance_airlock"]["level"]))      # S19 문간 증설
    return max(lv) if lv else 0


def cond_check(st: dict, uid: str, cond: dict | None) -> list[str]:
    """돈으로 못 사는 조건. 못 채운 것의 문장 목록(빈 목록 = 충족)."""
    if not cond:
        return []
    miss = []
    res = st.get("residents_list") or []
    if cond.get("role") and not any(r.get("role") == cond["role"] for r in res):
        miss.append(cond["ko"])
    if cond.get("room_level"):
        rid, n = cond["room_level"]
        if room_level_of(st, rid) < n:
            miss.append(cond["ko"])
    if cond.get("depth_m") and depth_of(st) < cond["depth_m"]:
        miss.append(cond["ko"])
    if cond.get("imprints_on_one") and not any(len(r.get("imprints") or []) >= cond["imprints_on_one"] for r in res):
        miss.append(cond["ko"])
    if cond.get("imprint") and not any(cond["imprint"] in (r.get("imprints") or []) for r in res):
        miss.append(cond["ko"])
    if cond.get("spot") and not spot_found(st, uid, cond["spot"]):
        miss.append(cond["ko"])
    return miss


def priced(st: dict, cost: dict) -> tuple[dict, dict]:
    disc = role_effects(st)["build_discount"]
    cost = {k: max(1, int(round(v * (1 - disc)))) for k, v in (cost or {}).items()}
    lack = {k: v - int(st["resources"].get(k, 0)) for k, v in cost.items() if int(st["resources"].get(k, 0)) < v}
    return cost, lack


def build_options(st: dict, uid: str) -> dict:
    """방마다 '지금 지을 수 있나'. 화면은 계산하지 않고 이것을 그린다(D2·정보를 숨기지 않는다)."""
    out = {}
    for rid, spec in ROOMS.items():
        if spec.get("fixed"):
            continue
        cost, lack = priced(st, spec.get("cost"))
        miss = cond_check(st, uid, BUILD_COND.get(rid))
        out[rid] = {"cost": cost, "lacking": lack, "cond": (BUILD_COND.get(rid) or {}).get("ko"),
                    "cond_missing": miss, "can": not lack and not miss}
        # S26 칸마다 물 빼기를 더한 판정(방 비용과 따로 drain_cost, 합친 missing)
        by = {}
        for sl, cell in drain_cells(st).items():
            tot = dict(cost)
            for k, v in cell["drain_cost"].items():
                tot[k] = int(tot.get(k, 0)) + int(v)
            m_ = {k: v - int(st["resources"].get(k, 0)) for k, v in tot.items() if int(st["resources"].get(k, 0)) < v}
            by[sl] = {"drain_cost": cell["drain_cost"], "missing": m_, "can": not m_ and not miss}
        out[rid]["by_slot"] = by
    return out


def upgrade_option(st: dict, uid: str, rid: str, level: int) -> dict | None:
    """다음 레벨로 올리는 데 필요한 것. 최고 레벨이면 None."""
    if level >= 3:
        return None
    row = (ROOMS.get(rid, {}).get("levels") or {}).get(str(level + 1))
    if not row:
        return None
    cost, lack = priced(st, row.get("cost"))
    miss = cond_check(st, uid, UPGRADE_COND.get((rid, level + 1)))
    return {"to": level + 1, "cost": cost, "lacking": lack, "opens": row.get("opens"),
            "cond": row.get("cond_ko"), "cond_missing": miss, "can": not lack and not miss}


@app.post("/api/ark/build")
def build(inp: BuildIn):
    st = load_state(inp.uid)
    tick_production(st)
    if inp.room_id not in ROOMS:
        raise HTTPException(400, "없는 방입니다")
    if ROOMS[inp.room_id].get("fixed"):
        raise HTTPException(400, "홀은 처음부터 있습니다. 짓는 것이 아니라 올리는 방입니다")
    if inp.room_id == "airlock" and inp.slot == -1:
        # S19: 에어락 = 문간 증설(칸을 먹지 않는다). 플레이테스트 2차: 에어락에 빈 칸이 필요해 6일째부터 막혔다
        if room_level_of(st, "airlock") >= 1:
            raise HTTPException(400, "에어락은 이미 있습니다")
        cost, lacking = priced(st, ROOMS["airlock"]["cost"])
        if lacking:
            raise HTTPException(400, f"자원이 부족합니다: {lacking}")
        for k, v in cost.items():
            st["resources"][k] -= v
        st["entrance_airlock"] = {"level": 1, "built": time.time()}
        save_state(inp.uid, st)
        log(inp.uid, "build", {"room": "airlock", "slot": -1, "cost": cost, "entrance": True})
        out = public_state(st, inp.uid)
        out["reclaimed"] = None
        out["depth_crossed"] = []
        return out
    if not (0 <= inp.slot < SLOTS) or any(r["slot"] == inp.slot and not r.get("flooded") for r in st["rooms"]):
        raise HTTPException(400, "그 자리는 비어 있지 않습니다")
    flooded = next((r for r in st["rooms"] if r["slot"] == inp.slot and r.get("flooded")), None)
    miss = cond_check(st, inp.uid, BUILD_COND.get(inp.room_id))
    if miss:
        raise HTTPException(400, "아직 지을 수 없습니다: " + " · ".join(miss))
    cost, lacking = priced(st, ROOMS[inp.room_id]["cost"])
    drain = drain_cost(st, inp.slot, reclaim=bool(flooded))          # S26 물 빼기(방 건설비에 더한다)
    total = dict(cost)
    for k, v in drain.items():
        total[k] = int(total.get(k, 0)) + int(v)
    missing = {k: v - int(st["resources"].get(k, 0)) for k, v in total.items() if int(st["resources"].get(k, 0)) < v}
    if missing:
        from fastapi.responses import JSONResponse
        mk = " · ".join(f"{RES_KO_SRV.get(k, k)} {v}" for k, v in missing.items())
        return JSONResponse(status_code=400, content={"detail": f"자원이 부족합니다: {mk}", "missing": missing, "missing_ko": mk,
                                                      "cost": cost, "drain_cost": drain})
    for k, v in total.items():
        st["resources"][k] -= v
    reclaimed = None
    if flooded:
        # 물 찬 칸 되찾기(사용자 결정 2026-10-03): 물을 빼고 **새로 짓는다** — 보통 건설비, Lv1.
        # 예전 방·레벨을 공짜로 되살리지 않는 이유: 되살리기가 싸면 상실이 '잠깐 불편'이 되고, 비싸게 따로
        # 매기려면 새 경제 수치가 필요하다(기획 소유). 그래서 보통 짓기 하나로 둔다. 무엇이었는지는 기록에 남긴다.
        st["rooms"].remove(flooded)
        reclaimed = dict(flooded.get("flooded_from") or {"id": flooded.get("id"), "level": room_level(flooded)})
        reclaimed.update({"slot": inp.slot, "day": day_of(st), "flooded_day": flooded.get("flooded_day"),
                          "rebuilt_as": inp.room_id})
        st.setdefault("reclaimed", []).append(reclaimed)
        st["reclaimed_total"] = int(st.get("reclaimed_total") or 0) + 1
        del st["reclaimed"][:-30]
        day_note(st, "reclaimed", ROOMS.get(inp.room_id, {}).get("name", inp.room_id))
    st["rooms"].append({"id": inp.room_id, "slot": inp.slot, "built": time.time(), "level": 1})
    if reclaimed:
        decor_on_reclaim(st, inp.slot)
    shelf_autofill(st)
    save_state(inp.uid, st)
    log(inp.uid, "build", {"room": inp.room_id, "slot": inp.slot, "cost": cost, "reclaimed": reclaimed})
    crossed = depth_check(st)
    if crossed:
        save_state(inp.uid, st)
    out = public_state(st, inp.uid)
    out["reclaimed"] = reclaimed
    out["depth_crossed"] = crossed
    return out


class UpgradeIn(BaseModel):
    uid: str
    slot: int | None = None       # 칸의 방. 홀은 칸이 없으므로 room_id="hall"
    room_id: str | None = None


@app.post("/api/ark/upgrade")
def upgrade(inp: UpgradeIn):
    """레벨업 = **재료 + 조건**(ROOMS_AND_ITEMS §2-1). 각 레벨은 '새로 할 수 있는 것' 하나를 연다."""
    st = load_state(inp.uid)
    tick_production(st)
    ent = None
    if inp.room_id == HALL_ID:
        rid, room, level = HALL_ID, None, int(st.get("hall_level") or 1)
    elif inp.room_id == "airlock" and inp.slot is None and (st.get("entrance_airlock") or {}).get("level"):
        ent = st["entrance_airlock"]
        rid, room, level = "airlock", None, int(ent["level"])
    else:
        room = room_at(st, inp.slot)
        if not room:
            raise HTTPException(400, "그 자리에는 방이 없습니다")
        if room.get("flooded"):
            raise HTTPException(400, "물이 찬 방은 올릴 수 없습니다")
        rid, level = room["id"], room_level(room)
    opt = upgrade_option(st, inp.uid, rid, level)
    if not opt:
        raise HTTPException(400, "더 올릴 수 없습니다")
    if opt["cond_missing"]:
        raise HTTPException(400, "아직 조건이 안 됩니다: " + " · ".join(opt["cond_missing"]))
    if opt["lacking"]:
        raise HTTPException(400, f"자원이 부족합니다: {opt['lacking']}")
    for k, v in opt["cost"].items():
        st["resources"][k] -= v
    if ent is not None:
        ent["level"] = opt["to"]
    elif room is None:
        st["hall_level"] = opt["to"]
    else:
        room["level"] = opt["to"]
    shelf_autofill(st)
    save_state(inp.uid, st)
    log(inp.uid, "upgrade", {"room": rid, "slot": inp.slot, "to": opt["to"], "cost": opt["cost"]})
    out = public_state(st, inp.uid)
    out["upgraded"] = {"room_id": rid, "slot": inp.slot, "level": opt["to"], "opens": opt["opens"],
                       "name": ROOMS[rid]["name"]}
    return out


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
            raise HTTPException(400, "물이 찬 방입니다. 다시 지어야 들어갈 수 있습니다")
        cap = room_cap_of(room)
        here = [p for p in stations_map(st).get(int(inp.slot), []) if p["id"] != inp.resident_id]
        if len(here) >= cap:
            raise HTTPException(400, f"{ROOMS[room['id']]['name']}{combat.josa(ROOMS[room['id']]['name'], ('은', '는'))} {cap}명까지입니다")
    before = station_slot(st, inp.resident_id)
    set_station(st, inp.resident_id, inp.slot)
    # 「덮개」의 관문은 **아무도 움직이지 않는 것**이다. 습격이 시작된 뒤의 이동을 센다 —
    # 이 게임의 주된 동사(사람을 옮긴다)가 최악수가 되는 유일한 생물이라 세는 자리가 필요하다.
    raid = st.get("raid")
    if (raid and not raid.get("none") and not raid.get("resolved")
            and raid.get("day") == day_of(st) and before != (int(inp.slot) if inp.slot is not None else None)
            and not lid_revealed(raid, combat.CREATURES.get(raid.get("creature")) or {})):
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
    """밖에 있는 사람을 들인다. S15: 원정이 있으면 원정 불러들이기(20분, 에어락 Lv3 즉시)와 같다."""
    st = load_state(inp.uid)
    had = list(st.get("outside") or [])
    arrives = None
    if st.get("expedition"):
        ex = exp_recall(st, inp.uid)
        arrives = ex["returns_at"]
        exp_settle(st, inp.uid)                  # 즉시 귀환(에어락 Lv3)이면 그 자리에서 정산
    else:
        st["outside"] = []
    save_state(inp.uid, st)
    log(inp.uid, "recall", {"count": len(had)})
    return {"recalled": had, "arrives_at": arrives, "state": public_state(st, inp.uid)}


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
        shelf_remove_card(st, card.get("id"))      # 선반의 그 자리도 빈다(creatures.json follower.lines.held)
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
        bits.append(f"「{gone_card}」 하나를 내려보냈다. 도감의 그 칸은 비어 있는 채로 남는다")
    if spec.get("next_severity"):
        bits.append("위로 빛을 비췄다. 다음에 오는 것이 한 단계 세진다")
    return {"ok": True, "action": spec["id"], "paid": paid, "lost_tools": lost,
            "lost_card": gone_card, "ko": " ".join(bits),
            "raid": raid_public(st, raid), "state": public_state(st, inp.uid)}


def resolve_raid(st: dict, uid: str, raid: dict, consumables: list,
                 cap: str | None = None, auto: bool = False) -> dict:
    """접촉. **방어 판정 공식은 engine/combat.evaluate 하나뿐이고 난수가 없다**(D6).
    같은 배치 = 같은 결과, 다른 배치 = 다른 결과. 이것이 이 시스템의 합격 기준이다.
    S13: cap 을 주면 결과가 그보다 나쁠 수 없다(밤 자동 판정 = stakes night_judge.worst_result). auto 는 그 표시."""
    cre = combat.CREATURES[raid["creature"]]
    day = raid["day"]
    if week1_cap(st) and (cap is None or _RESULT_RANK.get(cap, 2) > _RESULT_RANK[combat.SCARRED]):
        cap = combat.SCARRED                          # S30: 켠 날 1~7은 방을 잃지 않는다(금까지)
    owned = st.setdefault("tools", {})
    use = [t for t in (consumables or []) if combat.TOOLS.get(t, {}).get("kind") in combat.CARRY_KINDS
           and int(owned.get(t, 0)) > 0]
    # ① 소모품의 '쓰는 즉시' 효과를 **판정 전에** 적용한다. 귀환 신호기는 부르는 물건이지 점수가 아니다
    for t in use:
        if combat.TOOLS[t].get("recalls") and st.get("outside"):
            if st.get("expedition"):
                exp_recall(st, uid, immediate=True)     # 신호기는 즉시 부른다(지난 만큼만 들고)
                exp_settle(st, uid)
            else:
                st["outside"] = []
    ctx = raid_ctx(st, raid, use)
    take_staff_snapshot(st)                         # S13 staffing.measure: 접촉 순간 배치가 이번 틱 생산을 정한다
    ev = combat.evaluate(cre, ctx)
    result = ev["result"]
    capped = False
    if cap and _RESULT_RANK.get(result, 0) > _RESULT_RANK.get(cap, 2):
        result, capped = cap, True                  # 보지 않는 사이 방을 잃게 하지 않는다(B4)
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
    # 들키지 않고 넘긴 위협(문지기)은 막은 것과 같은 보상 — 그날 생산을 통째로 내준 값이다
    gained = combat.reward_for(combat.HELD if (result == combat.PASSED and cre.get("threat")) else result,
                               raid["severity"], int(raid.get("grade") or 1))
    if auto:
        rm = float(stk("night_judge.reward_mult") if stk("night_judge.reward_mult") is not None else 1.0)
        gained = {k: int(round(v * rm)) for k, v in gained.items() if int(round(v * rm))}
    for k, v in gained.items():
        st["resources"][k] = max(0, st["resources"].get(k, 0) + v)

    flags, hurt, lost_room = [], None, None
    near = float(ev.get("margin") or 0) < NEAR_MARGIN       # S19(PM): 각인은 아슬아슬했을 때만
    if result == combat.PASSED and cre.get("threat"):
        flags = list(cre.get("hold_flags") or []) if near else []    # 숨죽여 넘긴 것도 '겪고 넘긴' 것이다(문지기)
        line = (cre.get("lines") or {}).get("held") or line
    if result == combat.HELD:
        flags = list(cre.get("hold_flags") or []) if near else []
    elif result == combat.SCARRED and room:
        flags = list(cre.get("hold_flags") or [])     # 방을 거의 잃을 뻔했다 — 버틴 사람이 변한다
        if any(combat.TOOLS[t].get("heals_crack") for t in use):   # 봉합 패치로 그 자리에서 꿰맨다
            line += " 봉합 패치가 그 자리를 덮었다."
        elif crack_room(st, room):                  # S13: 금이 실효를 갖는다 — 수리 전까지 생산 ×crack.prod_mult
            day_note(st, "crack", room_name)
            decor_on_crack(st, room["slot"])        # S19: 꾸밈 물건이 떨어져 상자로(수리하면 제자리)
    elif result == combat.BREACHED and room:
        # 격벽이 닫힌다. 그 방은 **사라지지 않고 물이 찬 채로 영구히 남는다**(§3-6 흔적)
        room["flooded"] = True
        room["cracked"] = False
        # 사용자 결정 2026-10-03: 상실 = **물 찬 칸**. 영구 삭제가 아니다 — 무엇이 몇 레벨이었는지 기억하고,
        # 그 칸은 보통 짓기(/api/ark/build, economy.json 건설비)로 Lv1 부터 다시 지을 수 있다
        room["flooded_from"] = {"id": room["id"], "level": room_level(room)}
        room["flooded_day"] = day
        room["flooded_by"] = cre["id"]
        lost_room = ROOMS.get(room["id"], {}).get("name", room["id"])
        day_note(st, "room_lost", lost_room)
        for p in list(stations_map(st).get(int(raid["target_slot"]), [])):
            set_station(st, p["id"], None)          # 살아 나온 사람은 홀로 모인다
        (st.get("lights") or {}).pop(str(raid["target_slot"]), None)
        (st.get("room_tools") or {}).pop(str(raid["target_slot"]), None)   # 붙어 있던 것도 함께 잠긴다
        flags = list(cre.get("breach_flags") or [])
        decor_on_breach(st, raid["target_slot"])    # S19: 꾸밈 물건은 창고 상자로, 되찾으면 돌아온다
        pool = [p for p in st.get("residents_list", []) if not p.get("injured")]
        if pool:
            pool.sort(key=lambda p: 0 if p["role"] == "kid" else 1)
            pool[0]["injured"] = True; hurt = pool[0]["name"]
            st["injured"] = sum(1 for x in st.get("residents_list", []) if x.get("injured"))

    # ④ 각인: 그 방에서 **겪은 사람**만 변한다(GROWTH_AND_MYTH §1). 배치가 곧 참여자다
    here = [p for p in stations_map(st).get(int(raid["target_slot"]), [])][:MAX_PARTICIPANTS] \
        or hall_of(st)[:1]
    new_imprints = grant_imprints(st, None, flags, here) if flags else []
    if lost_room:
        # S19: 「빈 자리」는 방을 잃는 드문 상실에만 — 그 방에 없던 사람 하나가 지켜본다
        here_ids = {p["id"] for p in here}
        wit = [p for p in st.get("residents_list", []) if p["id"] not in here_ids and not p.get("injured")
               and p["id"] not in (st.get("outside") or [])]
        if wit:
            new_imprints += grant_imprints(st, None, ["ally_crisis"], wit[:1])

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
    if result in (combat.HELD, combat.PASSED) and cre.get("threat"):
        day_note(st, "blocked", cre["id"])
    raid.update({"stage": "done", "resolved": True, "result": result, "line": line,
                 "auto": bool(auto), "capped": capped,
                 "score": ev["score"], "need": ev["need"], "margin": ev["margin"],
                 "gate_ok": ev["gate"]["ok"], "used": use, "ended": time.time(),
                 "shielded": ev.get("shielded")})
    archive_raid(st, raid)
    log(uid, "raid_resolved", {"raid": raid["id"], "creature": cre["id"], "result": result,
                               "slot": raid["target_slot"], "score": ev["score"], "need": ev["need"],
                               "gate": ev["gate"]["ok"], "used": use, "grade": raid.get("grade"),
                               "severity": raid.get("severity"), "acts": list(raid.get("acts") or []),
                               "moves": raid.get("moves"), "shielded": ev.get("shielded"),
                               "auto": bool(auto), "capped": capped})
    return {"result": result,
            "result_ko": (combat.RESULT_KO[result] if capped else (ev.get("result_ko") or combat.RESULT_KO[result])),
            "line": line, "auto": bool(auto), "capped": capped, "room_name": room_name,
            "score": ev["score"], "need": ev["need"], "margin": ev["margin"],
            "gate": ev["gate"], "parts": parts_display(ev["parts"]), "used": use, "worn_out": worn,
            "shielded": ev.get("shielded"), "grade": int(raid.get("grade") or 1),
            "gained": gained, "injured": hurt, "lost_room": lost_room,
            "new_imprints": new_imprints, "next_raid_hint": hint,
            "imprint_credit": imprint_credit_parts(st, ev.get("parts"), f"{uid}|{day}|raid"),
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
    # S13: 어제(또는 오늘 밤 시각을 넘긴) 누르지 않은 습격을 먼저 판정한다 — ensure_raid 가 덮어쓰기 전에
    ticked = day_tick(st, uid)
    if debug_raid or is_unlocked(st, "raids"):          # S25: 습격은 켠 날 4부터(개발 훅은 예외)
        ensure_raid(st, uid, force=debug_raid, reset=bool(debug_reset), grade_force=debug_grade)
    save_state(uid, st)
    out = combat_public(st)
    return {"raid": out["raid"], "day": day_of(st), "outside": out["outside"],
            "next_raid_hint": out["next_raid_hint"], "night_judge": ticked["night_judge"],
            "state": public_state(st, uid)}


class VerbIn(BaseModel):
    uid: str
    verb: str | None = None          # light|power|station|tool|act, None 이면 고르지 않은 상태로


@app.post("/api/raid/verb")
def raid_verb(inp: VerbIn):
    """단서 모드에서 동사 하나를 고른다 → 미리보기가 열린다. 접촉 전까지 몇 번이든 바꿀 수 있다. 시계는 없다."""
    st = load_state(inp.uid)
    raid = st.get("raid")
    if not raid or raid.get("none") or raid.get("resolved") or raid.get("day") != day_of(st):
        raise HTTPException(400, "지금 맞설 것이 없습니다")
    if inp.verb is not None and inp.verb not in VERBS:
        raise HTTPException(400, "없는 동사입니다")
    raid["verb"] = inp.verb
    save_state(inp.uid, st)
    return {"ok": True, "raid": raid_public(st, raid), "state": public_state(st, inp.uid)}


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


# 막을 여는 카드 — 그 막에 들어서면 **무작위보다 먼저**, 이 순서로 한 장씩 나온다.
# 2막: 「먼 울음」 회수 두 장(DECISIONS 2026-09-22 — 1막 내내 숨긴 정체를 2막 입구에서 회수).
# 뒤에 섞여 나오면 200년 묵은 수수께끼의 회수가 김이 빠진다(PM 2026-10-03).
ACT_OPENERS = {2: ("tunnel_cry_at_the_mouth", "tunnel_log_last_line")}
ALL_OPENERS = {e for ids in ACT_OPENERS.values() for e in ids}


def act_opener(st: dict) -> str | None:
    """이 막에서 아직 안 나온 여는 카드 중 첫 번째. 없으면 None(→ 평소처럼 뽑는다)."""
    seen = set(st.get("seen_events") or [])
    for eid in ACT_OPENERS.get(int(st.get("act") or 1), ()):
        if eid in EVENTS and eid not in seen:
            return eid
    return None


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
        opener = act_opener(st)
        _ark = ark_state_obj(st)
        _ark.depth_m = depth_of(st)                    # S18: 깊이 문(180m 전용 카드가 0m 1일째에 나오던 버그)
        ev = EVENTS[opener] if opener else             pick_event(_ark, rng=random.Random(f"{uid}|{day}"),
                       exclude=seen_once(st) | ALL_OPENERS | recent_event_ids(st)
                       | ACT_TEXT_DENY.get(int(st.get("act") or 1), set()))   # S19 막 필터 누수(땅 문장 카드)    # S18: 며칠 안에 본 쪽지는 다시 안 나온다
        te = {"day": day, "event_id": ev["id"], "resolved": False, "countered": None, "shown_at": time.time()}
        st["today_event"] = te
        mark_seen(st, ev["id"])
        st.setdefault("event_days", {})[ev["id"]] = day
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
    fp = int(st["resources"].pop("free_pack", 0) or 0)      # S19: 자원 줄에 날 키가 남던 것 — 봉인 상자 하나로
    if fp:
        applied.pop("free_pack", None)
        boxes_ = [box_new(st, "blank", ev["id"], f"{inp.uid}|{te['day']}|{ev['id']}|fp{i}") for i in range(fp)]
        applied["box"] = len(boxes_)
        applied["box_ko"] = moment("event.box_gained") or "봉인 상자 하나가 문간에 놓였습니다."

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
    # S19(PM): 각인은 드물고 무겁게 — 평범한 사건 쪽지 결과로는 주지 않는다(아슬아슬한 습격·원정·사슬 끝에서만)
    new_imprints = []
    credit = imprint_credit_event(st, ev, how, hero)
    # S19(플레이테스트 2차·시나리오 imprint_lines _line_minor_rule): 쪽지 실패의 부상 같은 가벼운 일에는 「빈 자리」를
    # 주지 않는다. 방을 잃는 드문 상실에만(resolve_raid).
    # ── 신뢰: 함께 넘기면 오르고, 실패하면 급락한다 ──
    bump_trust(st, TRUST_ON_COUNTER if countered else TRUST_ON_FAIL)

    te.update({"resolved": True, "countered": countered, "how": how})
    save_state(inp.uid, st)
    log(inp.uid, "event_resolved", {"event": ev["id"], "countered": countered, "how": how, "card": bool(inp.card_id),
                                    "imprints": [n["imprint"]["id"] for n in new_imprints]})
    return {"countered": countered, "how": how, "applied": applied, "used_card": used, "hero": hero,
            "new_imprints": new_imprints, "trust_delta": TRUST_ON_COUNTER if countered else TRUST_ON_FAIL,
            "imprint_credit": credit,
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
    _act_now = int(st.get("act") or 1)
    for spot in SPOTS:
        sid = spot.get("id")
        if (1 if spot.get("_src") == "spots_deep.json" else 3) != _act_now:
            continue                                    # S18: 지금 막의 소문만(1막에 지상 스팟 소문이 새던 버그 8)
        rule = spot_gate(sid, spot)
        if not rule:
            continue
        have = sum(counts.get(c, 0) for c in rule["categories"])
        need = rule["need"]
        unlocked = have >= need
        is_new = False
        if unlocked and sid not in seen:
            seen.append(sid); changed = is_new = True
            if (1 if spot.get("_src") == "spots_deep.json" else 3) == int(st.get("act") or 1):
                day_note(st, "clue" if sid in DEEP_SPOT_IDS else "spot", spot.get("name") or sid)   # S15: 1막은 단서. 발견은 원정이
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
            "state": spot_state(st, uid, sid) if sid in DEEP_SPOT_IDS else ("found" if unlocked else "none"),
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
    _st_sp = load_state(uid) if uid else {}
    seen = set(_st_sp.get("rumors_seen") or []) if uid else set()
    out = []
    for spot in SPOTS:
        sid = spot["id"]
        gate = spot_gate(sid, spot)
        have = sum(counts.get(c, 0) for c in gate["categories"]) if gate else 0
        unlocked = bool(uid) and bool(gate) and have >= gate["need"]
        _sp_act = 1 if spot.get("_src") == "spots_deep.json" else 3
        other_act = bool(uid) and _sp_act != int((_st_sp or {}).get("act") or 1)
        if other_act:
            unlocked = False                            # S18: 다른 막의 스팟은 열리지도 '찾음'이 되지도 않는다
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
            "state": ("other_act" if other_act else
                      (spot_state(_st_sp, uid, sid) if sid in DEEP_SPOT_IDS else ("found" if unlocked else "none"))
                      if uid else "none"),
            "progress": ({"have": min(have, gate["need"]), "need": gate["need"]} if gate else None),
            "gate": ({"categories": gate["categories"],
                      "categories_ko": "·".join(CAT_KO.get(c, c) for c in gate["categories"]),
                      "need": gate["need"], "source": gate["source"]} if gate else None),
            "source_file": spot.get("_src"),
        })
    return out


@app.get("/api/codex")
def codex(uid: str):
    """도감. 옛 필드(category·total·found·names)는 그대로(옛 화면 app.js 가 읽는다).
    S13: 칸마다 entries — **모르는 칸도 실루엣으로 전부**(stem 은 숨기고 그림자 문장만), 본 칸은 최고 희귀도·변형."""
    st = load_state(uid)
    if ensure_codex_meta(st, uid):
        save_state(uid, st)
    meta = st.get("codex_meta") or {}
    out = []
    for cat in TEMPLATES:
        if cat.startswith("_"):
            continue
        pool = codex_pool(cat)
        found = st["codex"].get(cat, {})
        # 템플릿 이름은 {adj}가 치환되므로 접미 부분으로 매칭
        stems = [t["name"].replace("{adj} ", "") for t in pool]
        got = [s for s in stems if any(n.endswith(s) for n in found)]
        hint = moment(f"codex.category_hints.{cat}")
        entries, rar = [], {k: 0 for k in RARITY_KEYS}
        for t, stem in zip(pool, stems):
            m = (meta.get(cat) or {}).get(stem) or {}
            if stem in got:
                rs = [r for r in RARITY_KEYS if r in (m.get("rarities") or [])]
                for r in rs:
                    rar[r] += 1
                entries.append({"stem": stem, "known": True,
                                "name": m.get("name") or next((n for n in found if n.endswith(stem)), stem),
                                "count": sum(c for n, c in found.items() if n.endswith(stem)),
                                "rarity_best": rs[-1] if rs else None, "rarities": rs,
                                "variant_seen": bool(m.get("variant")),
                                "tags": t.get("tags") or [], "flavor": t.get("flavor")})
            else:
                entries.append({"stem": None, "known": False, "silhouette": hint,
                                "hint_ko": (moment("codex.unknown", hint=hint) if hint
                                            else moment("codex.unknown_no_hint")),
                                "rarity_best": None, "variant_seen": False})   # 모르는 칸은 태그도 숨긴다
        out.append({"category": cat, "category_ko": CAT_KO.get(cat, cat), "total": len(stems), "found": len(got),
                    "names": got, "entries": entries, "rarity": rar,
                    "in_completion": cat not in SAFE_EXCLUDE_CATS})          # S24: 담배는 도감 완성에 세지 않는다
    return out


@app.get("/api/collection")
def collection(uid: str):
    """도감의 나머지 쪽 — 가문 세트 18 · 생물 · 문어 선물 · 희귀도 요약. 모르는 칸은 실루엣(known:false)."""
    st = load_state(uid)
    if ensure_codex_meta(st, uid):
        save_state(uid, st)
    total = int(stk("family_sets.pieces_required"))
    seen_f = set(st.get("seen_families") or [])
    done = st.get("family_sets") or {}
    fams = []
    for code, fn in FAMILY_NAMES.items():
        cat = _KNOWN_FAM_CAT.get(code)
        lore = FAMILY_LORE.get(code) or {}
        known = code in seen_f
        hint = moment(f"codex.category_hints.{cat}") if cat else None
        row = {"code": code, "known": known, "name": fn.get("name") if known else None,
               "in_completion": cat not in SAFE_EXCLUDE_CATS,
               "category": cat, "category_ko": CAT_KO.get(cat or "", ""),
               "have": min(family_have(uid, code), total) if known else 0, "total": total,
               "completed": code in done, "lore_set_count": lore.get("set_count"),
               "story": lore.get("story") if code in done else None,
               "decor": lore.get("decor") if code in done else None,
               "flavor": fn.get("flavor") if known else None}
        if not known:
            row["silhouette"] = moment("codex.unknown", hint=hint) if hint else moment("codex.unknown_no_hint")
        fams.append(row)
    seen_c: dict = {}
    for r in st.get("raid_log") or []:
        c = r.get("creature")
        if c:
            seen_c.setdefault(c, {"times": 0, "last": None})
            seen_c[c]["times"] += 1
            seen_c[c]["last"] = r.get("result")
    cres = []
    for cid, c in combat.CREATURES.items():
        k = cid in seen_c
        cres.append({"id": cid, "known": k, "name": c.get("name") if k else None,
                     "how": c.get("how") if k else None, "threat": bool(c.get("threat")),
                     "times": seen_c.get(cid, {}).get("times", 0), "last_result": seen_c.get(cid, {}).get("last"),
                     "silhouette": None if k else c.get("silhouette")})
    oc_f = (st.get("octopus") or {}).get("finds") or {}
    finds = [{"id": f["id"], "known": f["id"] in oc_f, "name": f.get("name") if f["id"] in oc_f else None,
              "line": f.get("line") if f["id"] in oc_f else None, "kind": f.get("kind"),
              "count": int(oc_f.get(f["id"], 0))} for f in (OCTOPUS.get("finds") or []) if f.get("id")]
    rar = {k: 0 for k in RARITY_KEYS}
    with db() as con:
        for r in con.execute("SELECT rarity, COUNT(DISTINCT barcode) c FROM scans WHERE uid=? GROUP BY rarity", (uid,)):
            if r["rarity"] in rar:
                rar[r["rarity"]] = r["c"]
    variants = sum(1 for cat in (st.get("codex_meta") or {}).values() for m in cat.values() if m.get("variant"))
    deep = [x for x in SPOTS if x.get("_src") == "spots_deep.json"]
    return {"families": fams, "families_done": sum(1 for c_ in done if _KNOWN_FAM_CAT.get(c_) not in SAFE_EXCLUDE_CATS),
            "families_total": sum(1 for c_ in FAMILY_NAMES if _KNOWN_FAM_CAT.get(c_) not in SAFE_EXCLUDE_CATS),
            "creatures": cres, "octopus_finds": finds, "rarity": rar, "variants": {"seen": variants},
            "spots": {"found": sum(1 for x in deep if spot_found(st, uid, x["id"])), "total": len(deep)}}


@app.get("/api/text/moments")
def text_moments():
    """S13 화면 순간 문장(data/ui_moments.json) + S15 원정 문장(data/expedition_text.json 의 최상위 묶음
    entrance·guest·expedition·sealed_box·spot — 파일에 실제로 있는 것). 둘 다 시나리오 소유, 읽기 전용."""
    out = dict(moments())
    for k, v in exp_text().items():
        if not str(k).startswith("_"):
            out[k] = v
    return out


@app.get("/api/wishes")
def wishes(uid: str):
    """주민의 작은 바람(E5, data/wishes.json). 지금 방주에 있는 역할의 것만. 이루면 대사가 영구히 바뀐다."""
    st = load_state(uid)
    new = wishes_tick(st, uid)
    if new:
        save_state(uid, st)
    return wishes_public(st, uid)


class OctoNameIn(BaseModel):
    uid: str
    name: str


@app.post("/api/octopus/name")
def octopus_name(inp: OctoNameIn):
    st = load_state(inp.uid)
    require_unlocked(st, "octopus_name")
    oc = st.get("octopus")
    if not oc:
        raise HTTPException(400, "아직 아무도 오지 않았습니다")
    name = " ".join(str(inp.name or "").split())
    if not (1 <= len(name) <= 12):
        raise HTTPException(400, "이름은 1~12자로 적어 주세요")
    had = oc.get("name")
    oc["name"] = name
    save_state(inp.uid, st)
    log(inp.uid, "octopus_name", {"name": name, "rename": bool(had)})
    nm = OCTOPUS.get("naming") or {}
    line = (nm.get("rename_line") if had else nm.get("after_name_line")) or ""
    return {"name": name, "ko": line.replace("{oct_name}", name), "octopus": octopus_public(st)}


class RepairIn(BaseModel):
    uid: str
    slot: int
    use_patch: bool = False


@app.post("/api/ark/repair")
def repair(inp: RepairIn):
    """금 간 방 수리(stakes crack.repair_cost). 봉합 패치가 있으면 패치 하나로 대신할 수 있다. 즉시 끝난다."""
    st = load_state(inp.uid)
    tick_production(st)                       # 금 간 채로 흐른 시간은 금 간 값으로 먼저 정산한다
    room = room_at(st, inp.slot)
    if not room or room.get("flooded"):
        raise HTTPException(400, "그 자리에는 고칠 방이 없습니다")
    if not room.get("cracked"):
        raise HTTPException(400, "금 간 데가 없습니다")
    name = (ROOMS.get(room["id"]) or {}).get("name", room["id"])
    paid, used_patch = {}, False
    if inp.use_patch:
        if not REPAIR_PATCH_TOOL or int((st.get("tools") or {}).get(REPAIR_PATCH_TOOL, 0)) <= 0:
            raise HTTPException(400, "봉합 패치가 없습니다")
        st["tools"][REPAIR_PATCH_TOOL] -= 1
        used_patch = True
    else:
        cost = {k: int(v) for k, v in (stk("crack.repair_cost") or {}).items()}
        if int(((st.get("core") or {}).get("repair_discount") or {}).get(str(inp.slot), -1)) == day_of(st) and cost:
            k0 = max(cost, key=lambda k: cost[k])     # S20 유리닦이 불가사리: 수리비 −1(최소 1)
            cost[k0] = max(1, cost[k0] - 1)
        lack = {k: v - int(st["resources"].get(k, 0)) for k, v in cost.items() if int(st["resources"].get(k, 0)) < v}
        if lack:
            raise HTTPException(400, "모자랍니다: " + " · ".join(f"{RES_KO_SRV.get(k, k)} {v}" for k, v in lack.items()))
        for k, v in cost.items():
            st["resources"][k] = int(st["resources"].get(k, 0)) - v
        paid = cost
    room["cracked"] = False
    room.pop("cracked_day", None)
    decor_on_repair(st, inp.slot)
    day_note(st, "repaired", name)
    save_state(inp.uid, st)
    log(inp.uid, "repair", {"slot": inp.slot, "room": room["id"], "paid": paid, "patch": used_patch})
    return {"ok": True, "slot": inp.slot, "paid": paid, "used_patch": used_patch,
            "ko": moment("crack.repaired", room=name), "state": public_state(st, inp.uid)}


DAY_END = _load_json("day_end.json") or {}


@app.get("/api/day_end")
def day_end(uid: str):
    """하루 마감 컷(E6). **오늘 바뀐 것만**, data/day_end.json 상황표의 우선순위·최대 줄 수로 고른다. 시드 uid|day."""
    st = load_state(uid)
    day = day_of(st)
    note = (st.get("day_log") or {}).get(str(day)) or {}
    oc = st.get("octopus") or {}
    fl = st.get("far_call_log") or {}
    # 울음 간격: 오늘 값은 **지금 상태**에서 읽는다(기록이 낡으면 80/85 가 어긋났다 — 플레이테스트 버그 4c)
    now_sec, prev_sec = gauges_of(st)["far_call_sec"], fl.get(str(day - 1))
    imp0 = (note.get("imprint") or [None])[0]
    imp0 = imp0 if isinstance(imp0, dict) else ({"name": imp0, "src": "event"} if imp0 else None)
    facts = ark_facts(st)
    if imp0 and imp0.get("src") == "expedition":
        facts.add("returned")
    vals = {
        "imprint": ({"name": imp0["name"]} if imp0 else None),
        "room_lost": ({"room": note["room_lost"][0]} if note.get("room_lost") else None),
        "octopus_brought": ({"oct_name": oc.get("name") or "문어", "item": note["octopus"][0]}
                            if note.get("octopus") else None),
        "spot_found": ({"spot": note["spot"][0]} if note.get("spot") else None),
        "cry_shorter": ({"sec": now_sec, "delta": prev_sec - now_sec}
                        if isinstance(now_sec, int) and isinstance(prev_sec, int) and now_sec < prev_sec else None),
    }
    frame = DAY_END.get("frame") or {}
    sits = sorted([x for x in (DAY_END.get("situations") or []) if isinstance(x, dict)],
                  key=lambda x: int(x.get("priority", 9)))
    lines = []
    for sit in sits:
        v = vals.get(sit.get("id"))
        if v is None or not sit.get("lines"):
            continue
        t = pick_fact_line(sit["lines"], facts, f"{uid}|{day}|day_end|{sit['id']}")
        if t is None:
            continue                                    # 사실과 맞는 줄이 없으면 그 상황은 말하지 않는다
        for k, x in v.items():
            t = t.replace("{" + k + "}", str(x))
        lines.append({"id": sit["id"], "text": t})
    lines = lines[: int(frame.get("max_lines") or 3)]
    if not lines:
        q = next((x for x in sits if x.get("id") == "quiet"), None)
        if q and q.get("lines"):
            t = pick_fact_line(q["lines"], facts, f"{uid}|{day}|day_end|quiet")
            lines = [{"id": "quiet", "text": t}] if t else []
    with db() as con:
        n_scan = con.execute("SELECT COUNT(*) c FROM scans WHERE uid=? AND day=?", (uid, day)).fetchone()["c"]
    blocked = len(note.get("blocked") or [])
    # 「되찾은 층」 = 물 찬 칸을 다시 지은 수(지은 층 수가 아니다 — 버그 4b). 0 이면 말하지 않는다
    floors = int(st.get("reclaimed_total") or len(st.get("reclaimed") or []))
    facts_ko = [x for x in (moment("day_end.scans", scan_count=n_scan) if n_scan else None,
                            moment("day_end.blocked", blocked=blocked) if blocked else None,
                            moment("day_end.floors", floors=floors) if floors else None) if x]
    # 맺음 줄(내일의 낚싯바늘)은 **사실일 때만** 쓴다: [0] 내일 아침 볼 것(각인 아침 연출) / [1] 문어가 있다 /
    # [2] 내일 예보된 손님(문어의 다음 습격 예고). 해당 없으면 생략(day_end.json frame — 생략 가능)
    cl = frame.get("closing") or []
    hint = st.get("next_raid_hint") or {}
    cand = [cl[i] for i, ok in ((2, hint.get("day") == day + 1 and hint.get("creature")),
                                (0, any(p.get("day", 0) > day for p in st.get("morning_pending") or [])),
                                (1, bool(oc))) if ok and i < len(cl)]
    return {"day": day, "title": frame.get("title"), "open": moment("day_end.open"),
            "lines": lines, "facts": {"scan_count": n_scan, "blocked": blocked, "floors": floors},
            "facts_ko": facts_ko,
            "nothing": moment("day_end.nothing") if not note else None,
            "closing": cand[0] if cand else None,
            "close": moment("day_end.close")}


# 에이전트·PM이 만든 테스트 방주. 지표(H1~H5)에서 뺀다. ?all=1 로 전부 볼 수 있다.
TEST_UIDS = {"smoke", "uakdrgvja", "scn_s2_check", "log_demo"}
TEST_UID_PREFIXES = ("pmcheck", "scn_", "s2b_", "imp_", "test", "dev_")


def is_test_uid(uid: str) -> bool:
    return uid in TEST_UIDS or uid.startswith(TEST_UID_PREFIXES)


# S25 후속: 전역 투표·집계에서 빼는 시험·플레이테스트 방주(지표 제외 목록 + 플레이테스트 도구 uid 꼴)
VOTE_EXCLUDE_PREFIXES = TEST_UID_PREFIXES + ("pt", "r4dry", "r5dry", "dry", "smoke", "s22check", "s22c", "s22d", "s22e",
                                             "s23", "s24", "s25", "devs", "play", "bug")
VOTES_EXCLUDE_TEST = True       # 투표 장치 자체를 시험하는 옛 스위트(S22~S25)만 끈다


def vote_uid_excluded(uid: str) -> bool:
    if not VOTES_EXCLUDE_TEST:
        return False
    u = str(uid or "").lower()
    return uid in TEST_UIDS or u.startswith(VOTE_EXCLUDE_PREFIXES)


def vote_excluded(uid: str, st: dict | None = None) -> bool:
    """이 방주의 표를 전역 집계에 넣지 않나 — 시험 uid 꼴이거나, 개발 서버에서 만든 방주(test_ark)."""
    if not VOTES_EXCLUDE_TEST:
        return False
    return vote_uid_excluded(uid) or bool((st or {}).get("test_ark"))


@app.get("/api/lore/tower")
def tower_lore():
    """S12-B: M5 거점 화면의 되찾기 한 줄·180 m 아래 문장(data/tower_lore.json, 시나리오 소유). 읽기 전용."""
    p = ROOT / "data" / "tower_lore.json"
    try:
        j = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"reclaim": [], "below_limit": None}
    return {"reclaim": j.get("reclaim") or [], "below_limit": j.get("below_limit")}


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
# S15 원정·문간 API (docs/API_EXPEDITION.md)
# ─────────────────────────────────────────────────────────────
def _s15_load(uid: str) -> dict:
    st = load_state(uid)
    tick_production(st)
    s15_tick(st, uid)
    return st


@app.get("/api/entrance")
def entrance(uid: str):
    st = _s15_load(uid)
    save_state(uid, st)
    return entrance_public(st)


class GuestIn(BaseModel):
    uid: str
    guest_id: str
    accept: bool


@app.post("/api/entrance/guest")
def entrance_guest(inp: GuestIn):
    """들인다(빈 잠자리 필요) / 다른 돔 쪽으로 안내한다(벌도 보상도 없다). 손님은 스스로 떠나지 않는다."""
    st = _s15_load(inp.uid)
    g = next((x for x in st.get("guests") or [] if x.get("guest_id") == inp.guest_id), None)
    if not g:
        raise HTTPException(400, "그런 손님은 없습니다")
    if inp.accept:
        if beds_state(st)["free"] <= 0:
            raise HTTPException(400, "빈 잠자리가 없습니다. 거주실을 올리면 잠자리가 늘어납니다")
        r = {k: v for k, v in g.items() if k not in ("guest_id", "arrived", "src", "rescued_by")}
        r["joined"] = now_ts()
        r.setdefault("trust", {})
        st.setdefault("residents_list", []).append(r)
        tr = int(EX.g("newcomers.rescue.rescuer_trust", 20))
        for rid in g.get("rescued_by") or []:
            res = next((x for x in st["residents_list"] if x["id"] == rid), None)
            if res:
                res.setdefault("trust", {})[r["id"]] = max(int(res["trust"].get(r["id"], 0)), tr)
                r["trust"][rid] = max(int(r["trust"].get(rid, 0)), tr)
        st["residents"] = len(st["residents_list"])
        day_note(st, "newcomer", r["name"])
    st["guests"] = [x for x in st.get("guests") or [] if x.get("guest_id") != inp.guest_id]
    save_state(inp.uid, st)
    log(inp.uid, "guest_" + ("accept" if inp.accept else "decline"), {"role": g.get("role"), "src": g.get("src")})
    return {"ok": True, "accepted": inp.accept, "resident_id": g["id"] if inp.accept else None,
            "entrance": entrance_public(st), "state": public_state(st, inp.uid)}


@app.post("/api/entrance/suit_repair")
def suit_repair(inp: UidIn):
    st = _s15_load(inp.uid)
    su = suits_state(st)
    worn = [i for i, w in enumerate(su["wear"]) if w >= su["wear_limit"]]
    if not worn:
        raise HTTPException(400, "고칠 잠수복이 없습니다")
    cost = {k: int(v) for k, v in (su["repair_cost"] or {}).items()}
    lack = {k: v - int(st["resources"].get(k, 0)) for k, v in cost.items() if int(st["resources"].get(k, 0)) < v}
    if lack:
        raise HTTPException(400, "모자랍니다: " + " · ".join(f"{RES_KO_SRV.get(k, k)} {v}" for k, v in lack.items()))
    for k, v in cost.items():
        st["resources"][k] -= v
    su["wear"][worn[0]] = 0
    st["suits"]["shared_wear"] = su["wear"]
    save_state(inp.uid, st)
    return {"ok": True, "paid": cost, "suits": suits_state(st), "ko": xt("entrance.suit_repair.done"),
            "state": public_state(st, inp.uid)}


@app.get("/api/expedition/options")
def expedition_options(uid: str):
    st = _s15_load(uid)
    require_unlocked(st, "expedition")
    save_state(uid, st)
    out_ids = set(st.get("outside") or [])
    ling = lingering_now(st)
    dests = [{"kind": "door"}] + [{"kind": "spot", "id": s} for s in DEEP_SPOT_IDS if spot_state(st, uid, s) == "found"] + \
            [{"kind": "clue", "id": s} for s in DEEP_SPOT_IDS if spot_state(st, uid, s) == "clue"] + [{"kind": "unknown"}]
    drows = []
    for d in dests:
        sp = dest_spec(st, uid, d)
        drows.append({"dest": d, "ko": sp.get("ko"), "lengths": sp.get("lengths"), "can": not sp.get("why"),
                      "why": sp.get("why"), "category": sp.get("cat")})
    lens = {}
    for k, L in (EX.g("lengths") or {}).items():
        why = "밤 넘기기는 에어락 Lv1 이 필요합니다" if (k == "long" and room_level_of(st, "airlock") < 1) else None
        lens[k] = {"ko": L.get("ko"), "minutes": L.get("minutes"), "tank": L.get("tank"), "can": not why, "why": why,
                   "returns_at": now_ts() + int(L.get("minutes", 30)) * 60}
    return {"air": air_state(st), "suits": suits_state(st), "out": exp_public(st, st.get("expedition")),
            "lingering": ({"creature": ling, "name": (combat.CREATURES.get(ling) or {}).get("name"),
                           "add": float((EX.g("raid_link.lingering_add") or {}).get(ling, 0))} if ling else None),
            "residents": [{"id": r["id"], "name": r["name"], "stats": r.get("stats"),
                           "can": not r.get("injured") and r["id"] not in out_ids,
                           "why": ("다쳤다" if r.get("injured") else "밖에 있다" if r["id"] in out_ids else None)}
                          for r in st.get("residents_list") or []],
            "dests": drows, "lengths": lens, "tutorial": int(st.get("exp_count") or 0) == 0}


class ExpIn(BaseModel):
    uid: str
    members: list[str]
    dest: dict
    length: str


@app.post("/api/expedition/preview")
def expedition_preview(inp: ExpIn):
    st = _s15_load(inp.uid)
    require_unlocked(st, "expedition")
    return exp_preview(st, inp.uid, inp.members, inp.dest, inp.length)


@app.post("/api/expedition/start")
def expedition_start(inp: ExpIn):
    st = _s15_load(inp.uid)
    require_unlocked(st, "expedition")
    ex = exp_start(st, inp.uid, inp.members, inp.dest, inp.length)
    save_state(inp.uid, st)
    return {"ok": True, "expedition": exp_public(st, ex), "state": public_state(st, inp.uid)}


@app.get("/api/expedition")
def expedition_poll(uid: str):
    st = _s15_load(uid)
    save_state(uid, st)
    return {"expedition": exp_public(st, st.get("expedition")), "expedition_return": st.get("exp_unseen")}


@app.post("/api/expedition/recall")
def expedition_recall(inp: UidIn):
    st = _s15_load(inp.uid)
    ex = exp_recall(st, inp.uid)
    save_state(inp.uid, st)
    return {"ok": True, "arrives_at": ex["returns_at"], "kept_actions": ex["recall_keep"],
            "expedition": exp_public(st, ex), "state": public_state(st, inp.uid)}


@app.post("/api/expedition/seen")
def expedition_seen(inp: UidIn):
    st = load_state(inp.uid)
    st["exp_unseen"] = None
    save_state(inp.uid, st)
    return {"ok": True}


@app.get("/api/expedition/scene")
def expedition_scene(uid: str):
    st = _s15_load(uid)
    save_state(uid, st)
    ex = st.get("expedition")
    if not ex:
        raise HTTPException(404, "밖에 나간 사람이 없습니다")
    return scene_public(st, ex)


class SceneIn(BaseModel):
    uid: str
    action: str
    i: int | None = None
    choice: str | None = None
    keep: list[int] | None = None


@app.post("/api/expedition/scene")
def expedition_scene_act(inp: SceneIn):
    st = load_state(inp.uid)
    tick_production(st)
    ex = st.get("expedition")
    if not ex:
        raise HTTPException(400, "밖에 나간 사람이 없습니다")
    scene_act(st, ex, inp.action, i=inp.i, choice=inp.choice, keep=inp.keep)
    save_state(inp.uid, st)
    return scene_public(st, ex)


@app.get("/api/boxes")
def boxes(uid: str):
    st = _s15_load(uid)
    save_state(uid, st)
    return boxes_public(st)


class PryIn(BaseModel):
    uid: str
    box_id: str


@app.post("/api/box/pry")
def box_pry(inp: PryIn):
    """7일 동안 열쇠를 못 찾은 상자를 손이 가장 좋은 주민이 억지로 연다(절반)."""
    st = _s15_load(inp.uid)
    b = next((x for x in st.get("boxes") or [] if x["id"] == inp.box_id), None)
    if not b:
        raise HTTPException(400, "그런 상자는 없습니다")
    after = int(EX.g("boxes.pry.after_days", 7))
    if day_of(st) - int(b["found_day"]) < after:
        raise HTTPException(400, f"{after - (day_of(st) - int(b['found_day']))}일 더 열쇠를 찾아볼 수 있습니다")
    inside = [r for r in st.get("residents_list") or [] if r["id"] not in (st.get("outside") or []) and not r.get("injured")]
    if not inside:
        raise HTTPException(400, "열 사람이 없습니다")
    who = max(inside, key=lambda r: (int((r.get("stats") or {}).get("hand", 0)), r["id"]))
    out = box_open(st, b, float(EX.g("boxes.pry.value_mul", 0.5)), f"{inp.uid}|pry")
    out["by"] = {"id": who["id"], "name": who["name"]}
    save_state(inp.uid, st)
    log(inp.uid, "box_open", {"box": b["id"], "cat": b["cat"], "by": "pry"})
    return {"ok": True, "box_opened": out, "state": public_state(st, inp.uid)}


class DevAdvIn(BaseModel):
    uid: str
    minutes: float


@app.post("/api/dev/advance")
def dev_advance_api(inp: DevAdvIn):
    """★ 개발 전용(RELIC_DEV=1): 그 방주의 시계를 minutes 만큼 앞으로. 배포에는 없는 것과 같다(404)."""
    if not DEV_MODE:
        raise HTTPException(404, "없는 경로입니다")
    st = load_state(inp.uid)
    dev_advance(st, float(inp.minutes) * 60)
    save_state(inp.uid, st)
    return {"ok": True, "day": day_of(st)}


class DevImprintIn(BaseModel):
    uid: str
    resident_id: str
    ids: list[str]
    personal: bool = False


@app.post("/api/dev/imprint")
def dev_imprint(inp: DevImprintIn):
    """★ 개발 전용(RELIC_DEV=1): 주민에게 각인 1~3개를 바로 준다(실화면 외형 확인용). 배포에는 없는 것과 같다(404).
    ids 는 data/imprints.json(위기 각인) 또는 personal=true 면 imprints_arcs.json(개인 각인). 기존 목록을 이 ids 로 바꾼다."""
    if not DEV_MODE:
        raise HTTPException(404, "없는 경로입니다")
    if not 1 <= len(inp.ids) <= 3 or len(set(inp.ids)) != len(inp.ids):
        raise HTTPException(400, "각인은 서로 다른 1~3개")
    cat = ARC_IMPRINTS if inp.personal else IMPRINTS
    bad = [i for i in inp.ids if i not in cat]
    if bad:
        raise HTTPException(400, f"없는 각인입니다: {bad}")
    st = load_state(inp.uid)
    r = next((x for x in st.get("residents_list") or [] if x["id"] == inp.resident_id), None)
    if not r:
        raise HTTPException(400, "없는 사람입니다")
    if inp.personal:
        r["personal_imprints"] = list(inp.ids)
    else:
        r["imprints"] = list(inp.ids)
        r["crises"] = sorted({IMPRINTS[i]["crisis"] for i in inp.ids} | set(r.get("crises") or []))
        if len(r["imprints"]) >= EVOLVE_AT and not r.get("role_evolved"):
            r["role_evolved"] = True
            r["evolved_ko"] = ROLE_EVOLUTION.get(r["role"], r.get("role_ko"))
    save_state(inp.uid, st)
    log(inp.uid, "dev_imprint", {"resident": inp.resident_id, "ids": inp.ids, "personal": inp.personal})
    return {"ok": True, "resident_id": r["id"], "imprints": r.get("imprints"), "personal_imprints": r.get("personal_imprints"),
            "role_evolved": bool(r.get("role_evolved")), "evolved_ko": r.get("evolved_ko")}


class DevClockIn(BaseModel):
    uid: str
    hour: int | None = None


@app.post("/api/dev/clock")
def dev_clock(inp: DevClockIn):
    """★ 개발 전용(RELIC_DEV=1): 이 방주의 시각(시)을 고정한다 — 아침·저녁 세션, 밤, 21시 자동 판정, 밤 손님, 밤사이 제목이
    모두 이 시각을 쓴다. hour=null 이면 실제 시계로 돌아간다. 배포에는 없는 것과 같다(404, 배포 전 제거 목록)."""
    if not DEV_MODE:
        raise HTTPException(404, "없는 경로입니다")
    if inp.hour is not None and not 0 <= int(inp.hour) <= 23:
        raise HTTPException(400, "0~23시")
    st = load_state(inp.uid)
    if inp.hour is None:
        st.pop("dev_clock_hour", None)
    else:
        st["dev_clock_hour"] = int(inp.hour)
    save_state(inp.uid, st)
    _DEV_HOUR.set(st.get("dev_clock_hour"))
    return {"ok": True, "hour": st.get("dev_clock_hour"), "now_hour": now_hour(), "is_night": is_night(), "evening": is_evening()}


class SwapIn(BaseModel):
    uid: str
    stored_id: str
    slot: int | None = None          # 비우고 그 자리에 놓을 선반 칸. None 이면 빈 칸에만 놓는다


@app.post("/api/shelf/swap")
def shelf_swap(inp: SwapIn):
    """S18: 창고 상자의 유물을 선반에 올린다. slot 을 주면 그 칸의 물건을 창고 상자로 내린다(바꾸기)."""
    st = load_state(inp.uid)
    it = next((x for x in st.get("stored") or [] if x.get("id") == inp.stored_id), None)
    if not it:
        raise HTTPException(400, "창고 상자에 그런 물건이 없습니다")
    shelf_room(st)
    old = None
    if inp.slot is not None:
        old = next((x for x in st.get("shelf") or [] if int(x.get("slot", -1)) == int(inp.slot)), None)
        if not old:
            raise HTTPException(400, "그 칸에는 물건이 없습니다")
        st["shelf"] = [x for x in st["shelf"] if x is not old]
    put = shelf_try_put(st, it)
    if put is None:
        if old:
            st["shelf"].append(old)
        raise HTTPException(400, "선반에 놓을 자리가 없습니다")
    st["stored"] = [x for x in st["stored"] if x.get("id") != inp.stored_id]
    if old:
        down = dict(old)
        down["id"] = old.get("card_id") or f"st-{int(time.time() * 1000)}"
        down.pop("slot", None)
        st["stored"].append(down)
    save_state(inp.uid, st)
    log(inp.uid, "shelf_swap", {"stored": inp.stored_id, "slot": put, "down": bool(old)})
    nm = it.get("relic_name") or it.get("name") or ""
    return {"ok": True, "slot": put, "down": (old or {}).get("relic_name") or (old or {}).get("name"),
            "ko": moment("shelf.full.placed", item=nm),
            "down_ko": moment("shelf.full.moved", item=(old or {}).get("relic_name") or (old or {}).get("name") or "") if old else None,
            "state": public_state(st, inp.uid)}


@app.post("/api/overnight/seen")
def overnight_seen(inp: UidIn):
    """S18: 아침 「밤사이」 한 장을 봤다 — 모아 둔 것을 비운다."""
    st = load_state(inp.uid)
    st["overnight"] = {"items": []}
    save_state(inp.uid, st)
    return {"ok": True}


# ═════════════════════════════════════════════════════════════
# S19 핵심 루프 A — 「현실에서 찍은 물건이, 바다 밑에서 이 사람들의 삶이 된다」 (docs/CORE_LOOP_A.md, 계약 docs/API_S19.md)
#   수치 정본: data/balance/core_a.json (없으면 data/draft/core_a.json)
#   문장·매칭 정본(시나리오): data/resident_tastes.json · arcs.json · arcs2.json · room_decor.json · visitors.json ·
#                           beats.json · next_visit.json (없으면 data/draft/ 의 같은 이름)
#   상태: st["core"] 한 덩이. 시드는 전부 uid|…|day|목적(D6).
# ═════════════════════════════════════════════════════════════
def _live_or_draft(rel: str) -> dict:
    for p in (ROOT / "data" / rel, ROOT / "data" / "draft" / Path(rel).name):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                return d
        except (OSError, json.JSONDecodeError):
            continue
    return {}


CORE_A = _live_or_draft("balance/core_a.json")
TASTES = _live_or_draft("resident_tastes.json")
ARCS = [a for f in ("arcs.json", "arcs2.json") for a in (_live_or_draft(f).get("arcs") or [])
        if isinstance(a, dict) and a.get("id") and a.get("beats")]
ARC_BY_ID = {a["id"]: a for a in ARCS}
DECOR_TAGS = [t for t in (_live_or_draft("room_decor.json").get("tags") or []) if isinstance(t, dict) and t.get("id")]
DECOR_BY_ID = {t["id"]: t for t in DECOR_TAGS}
VISITORS_BY_TAG = {v["tag"]: v for v in (_live_or_draft("visitors.json").get("visitors") or [])
                   if isinstance(v, dict) and v.get("tag")}
BEATS = (_live_or_draft("beats.json").get("days") or {})
NEXT_VISIT = _live_or_draft("next_visit.json")
SUBTYPE_KO = TEMPLATES.get("_subtypes") or {}
_GP = (CORE_A.get("give_place") or {})
OUTCOME_V = {k: float(v) for k, v in (_GP.get("outcome_V") or {}).items() if not str(k).startswith("_")} or \
    {"chain_beat": 1.2, "need": 1.1, "memory": 1.2, "like": 1.0, "decor": 1.0, "neutral_person": 0.5, "keep": 0.8}
GIVE_EFFECTS = {k: v for k, v in (_GP.get("effects") or {}).items() if not str(k).startswith("_")}
TIER_ORDER = ("chain_beat", "memory", "need", "like", "decor", "warm")       # 값이 같을 때(core_a suggest_order)
TIER_ICON = {"chain_beat": "chain", "memory": "memory", "need": "need", "like": "like", "decor": "decor", "warm": "warm"}
WARM_V = 0.9          # S20 「누군가 반가워할」 — 좋아함(1.0)과 선반(0.8) 사이. 모든 스캔에 진짜 고르기가 둘 이상(PM 스모크)
TIER_REASON = {"warm": "반가워하실 것 같습니다", "chain_beat": "이야기가 움직입니다", "memory": "무언가 떠올리실 것 같습니다",
               "need": "오늘 필요하신 물건", "like": "좋아하시는 쪽", "decor": "손님이 바뀝니다"}   # ⚠ 시나리오 문장 대기(요청함)
_DIM = (_GP.get("diminish") or {})            # S21: core_a give_place.diminish(3차 플테 문제 1)
DIM_SAME_DAY = float(_DIM.get("same_person_session", 0.8))   # 같은 사람 같은 **세션** 두 번째부터(이름은 옛 것 그대로)
DIM_SAME_ITEM = float(_DIM.get("same_item_days", 0.6))       # 같은 물건을 며칠 안에 같은 사람에게
DIM_ITEM_DAYS = int(_DIM.get("item_days", 3))
DIM_COMBINE = str(_DIM.get("combine", "min"))                 # min = 둘이 겹치면 작은 쪽 하나만
DIM_FALLBACK_GAP = float(_DIM.get("session_fallback_gap_hours", 4)) * 3600
_TR = (CORE_A.get("decor") or {}).get("tag_rules") or {}
DECOR_SLOTS = {int(k): int(v) for k, v in ((CORE_A.get("decor") or {}).get("slots_by_level") or {"1": 2, "2": 3, "3": 4}).items()}
ITEMS_TO_TAG = int(_TR.get("items_to_tag", 2))
MAX_TAGS_PER_ROOM = 2
VISIT_P = {k: float(v) for k, v in (_TR.get("visitor_daily_chance") or {}).items() if isinstance(v, (int, float))} or \
    {"residents": 1.0, "octopus": 0.5, "small_fish": 0.5, "gardener": 0.15}
# 손님 기울기: 꼬리표 visitors 에 guest 가 있는 꼬리표 → 역할(core_a decor.visitors 의 1차 매핑에서 옮김). ⚠ 기획 확인 대기
S19N = CORE_A.get("s19_server_numbers") or {}                     # S20: 기획 확정값(design_s20_numbers_20261005.md)
_TGR = S19N.get("tag_guest_roles") or {}
TAG_GUEST_ROLES = {k: list(v) for k, v in _TGR.items() if not str(k).startswith("_") and isinstance(v, list)}
TAG_GUEST_WEIGHT = int(_TGR.get("weight", 2))
TAG_NEWHUMAN_LINEAGE = {"book_smell": "lamp_eye", "trade_corner": "kelp_hand"}      # 신인류는 보류(DECISIONS 10-04) — 표시만
RAID_CHERISHED_MULT = 1.5    # core_a seasoning.raid_targets_cherished
SHINY_LONGNECK_MULT = next((float(v.get("mult", 1.3)) for v in (CORE_A.get("decor") or {}).get("visitors") or []
                            if isinstance(v, dict) and v.get("id") == "v_shiny"), 1.3)
ARC_COOLDOWN_DEFAULT = int((CORE_A.get("chains") or {}).get("cooldown_days", 2))
SESSION_GAP_SEC = int(S19N.get("session_gap_min", 30)) * 60
BIG_WINDOWS_PER_SESSION = 2
_OV = S19N.get("overflow") or {}
OVERFLOW_RATE = {"to_morale": int(_OV.get("food_water_per_morale", 6)), "to_trade": int(_OV.get("other_per_trade", 5)),
                 "morale_day_max": int(_OV.get("morale_per_day_max", 1))}
_OW = S19N.get("octopus_with") or {}
OCTO_WITH = {"daily_chance": float(_OW.get("daily_chance", 0.5)), "guarantee_after_misses": int(_OW.get("guarantee_after_misses", 2))}
_VE = CORE_A.get("visitor_effects") or {}
VISITOR_DAILY = float(_VE.get("daily_chance_when_tagged", 0.35))
BEAT_FORCE_CREATURE = {"first_threat_longneck": "longneck", "second_threat_swarm": "swarm",
                       "third_threat_mirror_eye": "mirror_eye", "weekly_log_shade": "shade"}
EVENING_START, EVENING_END = (list(S19N.get("evening_hours") or [17, 5]) + [17, 5])[:2]   # 저녁 세션(core_a)
ACT_TEXT_DENY = {1: {"relic_cache"}}      # 막 표시는 [1,2,3]인데 문장이 땅(콘크리트·땅을 파다) — 1막에서 뺀다(시나리오 요청함)


import contextvars  # noqa: E402
_DEV_HOUR = contextvars.ContextVar("dev_hour", default=None)   # ★ 개발 전용 방주 시계(요청마다 load_state 가 정한다)


def now_hour() -> int:
    """테스트가 바꿔 끼울 수 있게 한 군데서 읽는다. ★ RELIC_DEV 에서는 그 방주의 개발 시계(/api/dev/clock)가 이긴다."""
    h = _DEV_HOUR.get()
    return int(h) if h is not None else datetime.now().hour


_now_hour_impl = now_hour      # 테스트가 now_hour 를 바꿔 끼운 뒤 되돌릴 때


def is_evening(h: int | None = None) -> bool:
    h = now_hour() if h is None else h
    return h >= EVENING_START or h < EVENING_END


def core_of(st: dict) -> dict:
    c = st.setdefault("core", {})
    for k, d in (("res", {}), ("rooms", {}), ("scans", {}), ("deferred", []), ("arc_log", []), ("props", []),
                 ("morning_next", []), ("visits", {}), ("visitors_seen", []), ("tags_seen", {}), ("flags", {}),
                 ("beats", {}), ("session", {}), ("wish_new", [])):
        if not isinstance(c.get(k), type(d)):
            c[k] = type(d)()
    return c


def cres(st: dict, rid: str) -> dict:
    c = core_of(st)["res"].setdefault(rid, {})
    for k, d in (("items", []), ("given", []), ("memories_seen", []), ("arcs", {})):
        if not isinstance(c.get(k), type(d)):
            c[k] = type(d)()
    c.setdefault("keepsake", None)
    return c


def sub_ko(cat: str, sub) -> str:
    subs = sub if isinstance(sub, list) else [sub] if sub else []
    names = [(SUBTYPE_KO.get(cat) or {}).get(s, s) for s in subs]
    return "·".join(names) if names else CAT_KO.get(cat, cat)


def rule_ko(rule: dict) -> str:
    if rule.get("family"):
        return ((FAMILY_NAMES.get(rule["family"]) or {}).get("name")) or "어느 가문 물건"
    return sub_ko(rule.get("category", ""), rule.get("subtype"))


def match(rule, it: dict) -> bool:
    """매칭 단위: category / subtype(목록) / family(7자리) / rarity_min. 규칙이 비면 거짓."""
    if not isinstance(rule, dict) or not (rule.get("family") or rule.get("category")):
        return False
    if rule.get("family") and str(it.get("family") or "") != str(rule["family"]):
        return False
    if rule.get("category") and it.get("category") != rule["category"]:
        return False
    sub = rule.get("subtype")
    if sub:
        subs = sub if isinstance(sub, list) else [sub]
        if it.get("subtype") not in subs:
            return False
    if rule.get("rarity_min") in RARITY_KEYS and \
            RARITY_KEYS.index(it.get("rarity") if it.get("rarity") in RARITY_KEYS else "common") < RARITY_KEYS.index(rule["rarity_min"]):
        return False
    return True


def item_key(it: dict) -> str:
    return str(it.get("barcode") or it.get("name") or it.get("card_id") or "")


def item_from_card(card_d: dict) -> dict:
    return {"name": card_d.get("name"), "category": card_d.get("category"), "subtype": card_d.get("subtype") or None,
            "family": card_d.get("family_code") or (str(card_d.get("barcode") or "")[:7] or None),
            "rarity": card_d.get("rarity"), "barcode": card_d.get("barcode"), "card_id": card_d.get("id")}


def item_from_row(row: dict) -> dict:
    """선반·창고 상자 물건 → 매칭용. 바코드가 있으면 같은 유물을 다시 만들어 줄기 종류를 읽는다(D6)."""
    sub, fam = None, None
    bc = row.get("barcode")
    if bc:
        try:
            cd = GEN.generate(bc, user_category=row.get("category"), user_subtype=row.get("subtype"))
            sub, fam = cd.subtype or None, cd.family_code
        except ValueError:
            pass
    if row.get("subtype"):
        sub = row["subtype"]                          # S29 r6-1: 이 방주가 정한(다시 붙인) 하위 종류가 이긴다
    return {"name": row.get("relic_name") or row.get("name"), "category": row.get("category"), "subtype": sub,
            "family": fam, "rarity": row.get("rarity"), "barcode": bc, "card_id": row.get("card_id") or row.get("id"),
            "prop_id": row.get("prop_id")}


# ── 주민의 마음: 좋아함·필요·기억·덧붙임 ─────────────────────────────
def role_taste(role: str) -> dict:
    return ((TASTES.get("roles") or {}).get(role)) or {}


def twist_of(uid: str, r: dict) -> dict:
    """사람마다 시드로 좋아함 하나 + 안 맞음 하나(역할 좋아함·필요와 겹치지 않는 하위 종류)."""
    pt = TASTES.get("personal_twist") or {}
    rt = role_taste(r.get("role", ""))
    taken = list(rt.get("likes") or []) + list(rt.get("needs") or [])
    pool = [p for p in (pt.get("pool") or []) if isinstance(p, dict)
            and not any(match(t, {"category": p["category"], "subtype": p.get("subtype")}) for t in taken)]
    if len(pool) < 2:
        return {}
    rng = random.Random(f"{uid}|{r['id']}|twist")
    like, dislike = rng.sample(pool, 2)
    out = {}
    for k, p, tpl in (("like", like, pt.get("like_line")), ("dislike", dislike, pt.get("dislike_line"))):
        ko = sub_ko(p["category"], p.get("subtype"))
        out[k] = {"category": p["category"], "subtype": p.get("subtype"), "ko": ko,
                  "line": (tpl or "").replace("{name}", r.get("name", "")).replace("{subtype_ko}", ko) or None}
    return out


def likes_of(uid: str, r: dict) -> list:
    tw = twist_of(uid, r).get("like")
    return list(role_taste(r.get("role", "")).get("likes") or []) + \
        ([{"category": tw["category"], "subtype": [tw["subtype"]] if tw.get("subtype") else None}] if tw else [])


def need_today(uid: str, r: dict, day: int) -> dict | None:
    allr = [n for n in (role_taste(r.get("role", "")).get("needs") or []) if isinstance(n, dict)]
    needs = [n for n in allr if safe_rule(n)]          # S24: 찾으러 보내는 것은 안전 목록 안에서만
    if not needs:
        return None
    n = random.Random(f"{uid}|{r['id']}|{day}|need").choice(needs)
    sn = safe_rule(n)
    return {"category": sn.get("category"), "subtype": sn.get("subtype"), "ko": rule_ko(sn), "idx": allr.index(n)}


def join_day(st: dict, r: dict) -> int:
    j = float(r.get("joined") or st.get("created") or 0)
    return max(1, int((j - float(st["created"])) // 86400) + 1)


# ── 사슬 ────────────────────────────────────────────────────────
def arc_state(st: dict, rid: str, aid: str) -> dict:
    a = cres(st, rid)["arcs"].setdefault(aid, {})
    a.setdefault("step", 0)
    a.setdefault("last_day", None)
    a.setdefault("asks", {})
    a.setdefault("done", False)
    return a


def arc_done_any(st: dict, aid: str) -> bool:
    return any(((v.get("arcs") or {}).get(aid) or {}).get("done") for v in core_of(st)["res"].values())


def current_arc(st: dict, r: dict) -> tuple[dict | None, dict | None]:
    for a in ARCS:
        if a.get("role") != r.get("role"):
            continue
        s = arc_state(st, r["id"], a["id"])
        if s["done"]:
            continue
        req = (a.get("requires") or {}).get("arc_done")
        if req and not ((cres(st, r["id"])["arcs"].get(req) or {}).get("done")):
            continue
        return a, s
    return None, None


def next_beat(a: dict, s: dict) -> dict | None:
    beats = sorted(a.get("beats") or [], key=lambda b: int(b.get("step", 0)))
    return beats[s["step"]] if s["step"] < len(beats) else None


def arc_of_beat(beat: dict) -> dict | None:
    return next((a for a in ARCS if any(b is beat for b in a.get("beats") or [])), None)


def first_open_raw(st: dict, r: dict, beat: dict) -> int:
    """첫 매듭이 열리는 날. arcs 의 opens_day(사슬 또는 매듭에, 켠 날 차례 = 게임 날)가 있으면 그것 —
    처음부터 있던 사람은 그날, 뒤에 온 사람은 합류한 날 + (opens_day − 1). 없으면 합류 + days_since_join."""
    trig = beat.get("trigger") or {}
    a = arc_of_beat(beat) or {}
    od = trig.get("opens_day", beat.get("opens_day", a.get("opens_day")))
    if isinstance(od, (int, float)):
        return join_day(st, r) + int(od) - 1
    return join_day(st, r) + int(trig.get("days_since_join", 0))


def early_arc_rid(st: dict) -> str | None:
    """1~2일째 보장(PM 스모크 3): 아직 아무 사슬도 한 걸음 안 나갔으면, 지금 있는 사람 중 첫 매듭이 가장 먼저 열릴
    사람 하나(같으면 명단 순서). 그 사람의 첫 매듭은 늦어도 2일째에 열리고, 밤 조건은 저녁 세션으로 풀어 준다.
    명단이 무작위여도(요리사가 없어도) 누군가 하나는 1~2일째에 매듭이 있다."""
    best = None
    out_ids = set(st.get("outside") or [])
    for i, r in enumerate(st.get("residents_list") or []):
        for x in ((core_of(st)["res"].get(r["id"]) or {}).get("arcs") or {}).values():
            if int(x.get("step") or 0) > 0 and not x.get("migrated"):
                return None
        if r["id"] in out_ids:
            continue
        a, s_ = current_arc(st, r)
        b = next_beat(a, s_) if a else None
        if not b or s_["step"] != 0:
            continue
        d = first_open_raw(st, r, b)
        if best is None or (d, i) < best[:2]:
            best = (d, i, r["id"])
    return best[2] if best else None


def beat_opens_day(st: dict, r: dict, s: dict, beat: dict) -> int:
    trig = beat.get("trigger") or {}
    if evening_step_ok(st, s, beat):
        return day_of(st)
    if s["step"] == 0 and s.get("last_day") is None:
        d = first_open_raw(st, r, beat)
        if d > 2 and early_arc_rid(st) == r["id"]:
            d = max(2, join_day(st, r))
        return d
    return int(s.get("last_day") or day_of(st)) + int(trig.get("min_days_after_prev", ARC_COOLDOWN_DEFAULT))


def beat_open(st: dict, r: dict, s: dict, beat: dict, day: int | None = None) -> bool:
    return (day_of(st) if day is None else day) >= beat_opens_day(st, r, s, beat)


def given_distinct(st: dict, rid: str, rule: dict) -> int:
    keys = {item_key(g) for g in cres(st, rid)["given"] if match(rule, g)}
    return len(keys)


def octo_with(st: dict, uid: str, r: dict) -> bool:
    oc = st.get("octopus")
    if not oc:
        return False
    day = day_of(st)
    slot = station_slot(st, r["id"])
    for v in (core_of(st)["visits"].get("rows") or []) if core_of(st)["visits"].get("day") == day else []:
        if v.get("kind") == "octopus" and slot is not None and v.get("slot") == slot:
            return True
    om = core_of(st).setdefault("octo_miss", {}).setdefault(r["id"], {"day": None, "misses": 0, "hit": False})
    if om.get("day") != day:                          # 그날 처음 볼 때 한 번만 굴린다(같은 날은 같은 답)
        guaranteed = int(om.get("misses") or 0) >= OCTO_WITH["guarantee_after_misses"]
        hit = guaranteed or random.Random(f"{uid}|{day}|{r['id']}|octo_with").random() < OCTO_WITH["daily_chance"]
        om.update({"day": day, "hit": hit, "misses": 0 if hit else int(om.get("misses") or 0) + 1})
    return bool(om.get("hit"))


def night_event_since(st: dict, since: int, what) -> bool:
    for x in st.get("raid_log") or []:
        if int(x.get("day") or 0) >= since and x.get("result") and (what is True or x.get("creature") == what):
            return True
    if what is True:
        c = core_of(st)["visits"]
        if int(c.get("day") or 0) >= since and any(v.get("kind") in ("visitor", "octopus", "gardener") for v in c.get("rows") or []):
            return True
        if int(st.get("knock_checked_day") or 0) >= since and st.get("first_knock_done"):
            return True
    return False


def room_tags_on(st: dict, slot) -> list:
    return [t["id"] for t in decor_tags(st, slot) if t["on"]]


def any_tag_on(st: dict, tag: str, room_id: str | None = None) -> bool:
    for r in live_rooms(st):
        if room_id and r["id"] != room_id:
            continue
        if tag in room_tags_on(st, r["slot"]):
            return True
    return False


def place_ok(st: dict, r: dict, v: dict) -> bool:
    rid_room = v.get("room")
    if v.get("resident") == "self":
        rm = room_at(st, station_slot(st, r["id"]))
        return bool(rm and not rm.get("flooded") and rm["id"] == rid_room)
    if v.get("decor"):
        return any_tag_on(st, v["decor"], rid_room)
    for rm in live_rooms(st):
        if rm["id"] != rid_room:
            continue
        items = (core_of(st)["rooms"].get(str(rm["slot"])) or {}).get("items") or []
        if not v.get("category") or any(match({"category": v["category"], "subtype": v.get("subtype")}, it) for it in items):
            return True
    return False


def trig_one(st: dict, uid: str, r: dict, s: dict, k: str, v, ev: dict | None) -> bool:
    if k == "give":
        if not (ev and ev.get("item")):
            return False
        to_ok = ev.get("to") == r["id"] or (isinstance(v, dict) and v.get("to") == "any")
        rl = safe_rule(soft_rule(s, v))                # S24: 안전 목록 밖 조건은 지운다(없으면 이 갈래로는 못 푼다)
        return bool(to_ok and rl and match(rl, ev["item"]))
    if k == "give_distinct":
        rl = safe_rule(soft_rule(s, {"category": v.get("category"), "subtype": v.get("subtype")}))
        if not rl:
            return False
        return given_distinct(st, r["id"], rl) >= int(v.get("n", 1))
    if k == "place":
        return place_ok(st, r, v or {})
    if k == "octopus_with":
        return octo_with(st, uid, r)
    if k == "session":
        return v != "evening" or is_evening()
    if k == "night_event":
        since = int(s.get("last_day") or join_day(st, r))
        if night_event_since(st, since, v):
            return True
        # 보장: 2일째 끝까지 아무 매듭도 없으면 그 사람의 밤 조건은 저녁 세션으로 푼다(PM)
        return (int(s.get("step") or 0) == 0 and play_day(st) >= 2 and is_evening()
                and early_arc_rid(st) == r["id"])
    if k == "any_of":
        return any(isinstance(x, dict) and trig_all(st, uid, r, s, x, ev) for x in v or [])
    if k == "choice":
        return v in [x.get("choice") for x in (s.get("asks") or {}).values() if isinstance(x, dict)]
    if k == "spot":
        return spot_found(st, uid, v)
    if k == "octopus_find":
        return int(((st.get("octopus") or {}).get("finds") or {}).get(v, 0)) > 0
    if k == "family_set_complete":
        return v in (st.get("family_sets") or {})
    if k == "arc_done":
        return bool((cres(st, r["id"])["arcs"].get(v) or {}).get("done")) or arc_done_any(st, v)
    if k == "flag":
        if v == "survived_together":
            return any(int(x) > 0 for x in (r.get("trust") or {}).values())
        return bool(core_of(st)["flags"].get(v))
    if k == "decor":
        return any_tag_on(st, v)
    if k == "other_arc_step":
        aid, n = (v or {}).get("arc"), int((v or {}).get("step", 1))
        return any(int(((x.get("arcs") or {}).get(aid) or {}).get("step", 0)) >= n for x in core_of(st)["res"].values())
    return False


def trig_all(st: dict, uid: str, r: dict, s: dict, trig: dict, ev: dict | None) -> bool:
    for k, v in (trig or {}).items():
        if k in ("days_since_join", "min_days_after_prev"):
            continue
        if not trig_one(st, uid, r, s, k, v, ev):
            return False
    return True


def trig_needs_give(trig: dict) -> bool:
    """이 매듭이 '건네는 순간'에만 풀리는가(any_of 는 갈래 하나라도 건네기가 아니면 수동 판정도 한다)."""
    if "give" in (trig or {}):
        return True
    alts = (trig or {}).get("any_of")
    if alts:
        return all(isinstance(x, dict) and "give" in x for x in alts)
    return False


def fill_text(t, st: dict, r: dict, item: dict | None = None, other: str | None = None, **kw) -> str | None:
    if isinstance(t, dict):                            # S22 r4-6: {"text", "requires_role", "text_alt"}
        t = t.get("text") if role_ok(t, st) else t.get("text_alt")
    if not t:
        return None
    oc = st.get("octopus") or {}
    t = str(t).replace("{name}", r.get("name", "")).replace("{item}", (item or {}).get("name") or "그 물건")
    t = t.replace("{oct_name}", oc.get("name") or "문어").replace("{other}", other or "누군가")
    kid = next((x["name"] for x in st.get("residents_list") or [] if x.get("role") == "kid"), None)
    t = t.replace("{kid}", kid or "아이")
    for k, v in kw.items():
        t = t.replace("{" + k + "}", str(v))
    return t


def arc_other(st: dict, r: dict, s: dict, beat: dict) -> str | None:
    pick = (s.get("asks") or {}).get("pick_residents")
    by = {x["id"]: x for x in st.get("residents_list") or []}
    if isinstance(pick, dict):
        for i in pick.get("resident_ids") or []:
            if i != r["id"] and i in by:
                return by[i]["name"]
    trig = json.dumps(beat.get("trigger") or {}, ensure_ascii=False)
    if "other_arc_step" in trig:
        for oid, x in core_of(st)["res"].items():
            for aid, a in (x.get("arcs") or {}).items():
                if aid in trig and oid in by and oid != r["id"] and int(a.get("step", 0)) > 0:
                    return by[oid]["name"]
    best = max(((v, k) for k, v in (r.get("trust") or {}).items() if k in by), default=None)
    if best:
        return by[best[1]]["name"]
    other = next((x for x in st.get("residents_list") or [] if x["id"] != r["id"]), None)
    return other["name"] if other else None


def arc_public_beat(st: dict, r: dict, a: dict, s: dict, beat: dict, item: dict | None, other: str | None) -> dict:
    ask = beat.get("ask")
    return {"arc_id": a["id"], "title": a.get("title"), "resident_id": r["id"], "name": r["name"],
            "step": int(beat.get("step", s["step"])), "steps": len(a.get("beats") or []), "size": beat.get("size", "small"),
            # S22 r4-7: announce 가 비면(문어 매듭) 문어 서술·입말로 대신한다. r4-6: 없는 역할을 말하는 줄은 _alt
            "announce": fill_text(role_text(beat, "announce", st), st, r, item, other)
                        or octo_fallback(st, r, beat)
                        or fill_text(role_text(beat, "beat", st), st, r, item, other)
                        or fill_text("{name} 님 쪽 이야기가 한 걸음 움직였습니다.", st, r, item, other),   # S27 r5-5: 입말(line)을 되풀이하지 않는다
            "line": fill_text(role_text(beat, "line", st), st, r, item, other),
            "beat": fill_text(role_text(beat, "beat", st), st, r, item, other),
            "log": fill_text(role_text(beat, "log", st), st, r, item, other),
            "ask": ({k: ask.get(k) for k in ("kind", "label", "options", "default", "category", "subtype", "room", "n")}
                    if isinstance(ask, dict) else None),
            "after_ask": fill_text(beat.get("after_ask"), st, r, item, other)}


def fire_beat(st: dict, uid: str, r: dict, a: dict, s: dict, beat: dict, item: dict | None = None,
              force: bool = False) -> dict:
    """매듭 하나를 푼다. 큰 매듭은 하루 하나(감독) — 이미 나왔으면 미뤄 두고 다음 조용한 순간(다음 날 첫 /api/ark)에 뜬다."""
    c = core_of(st)
    day = day_of(st)
    big = beat.get("size") == "big"
    if big and not force and c.get("big_day") == day:
        key = f"{r['id']}|{a['id']}|{beat.get('step')}"
        if not any(d.get("key") == key for d in c["deferred"]):
            c["deferred"].append({"key": key, "rid": r["id"], "arc": a["id"], "step": beat.get("step"), "day": day,
                                  "item": item})
        return {"arc_id": a["id"], "step": beat.get("step"), "deferred": True, "resident_id": r["id"]}
    if big:
        c["big_day"] = day
    other = arc_other(st, r, s, beat)
    row = arc_public_beat(st, r, a, s, beat, item, other)
    core_of(st)["session"].setdefault("fired", []).append(f"{r['id']}|{a['id']}|{beat.get('step')}")
    s["step"] = int(s["step"]) + 1
    if s.get("last_day") == day and is_evening():
        s["evening_extra_day"] = day                  # S31: 아침에 한 걸음, 같은 저녁에 작은 한 걸음 더(하루 한 번만)
    s["last_day"] = day
    s["last_evening"] = is_evening()
    s.setdefault("days", {})[str(s["step"])] = day
    if beat.get("ask"):
        s["ask_pending"] = int(beat.get("step", s["step"]))
    r["arc_line"] = row["line"] or r.get("arc_line")            # 대사 한 줄이 영구히 바뀐다
    eff = GIVE_EFFECTS.get("chain_beat") or {"mood": 2}
    morale_add(st, float(eff.get("mood", 2)))
    for pk in (beat.get("set_prop"), (beat.get("after") or {}).get("prop")):
        if pk and pk not in c["props"]:
            c["props"].append(pk)
    if beat.get("announce_next_morning"):
        c["morning_next"].append({"day": day + 1, "kind": "arc_morning", "resident_id": r["id"],
                                  "text": fill_text(beat["announce_next_morning"], st, r, item, other)})
    after = beat.get("after") or {}
    if after.get("morning_line") or after.get("evening_line"):
        cres(st, r["id"])["after_line"] = after.get("morning_line") or after.get("evening_line")
    done = s["step"] >= len(a.get("beats") or [])
    row["done"] = done
    row["deferred"] = False
    row["day"] = day
    if done:
        s["done"] = True
        s["done_day"] = day
        # 끝 매듭: 그 사람의 '자리'(물건이 그 방에 영구 장식) + 옛 무리에서 손님 하나(문간에 자리가 있으면)
        seat_item = (item or (cres(st, r["id"])["items"] or [{}])[-1] or {}).get("name")
        cres(st, r["id"])["seat"] = {"arc": a["id"], "item": seat_item, "day": day, "slot": seat_slot(st, r, a)}
        c["flags"]["arc_guest_due"] = int(c["flags"].get("arc_guest_due") or 0) + 1
        row["imprint"] = grant_personal_imprint(st, r, a)
        if a.get("wish_id"):
            st.setdefault("wishes_done", {})[a["wish_id"]] = {"day": day, "resident_id": r["id"], "arc": a["id"]}
            w = next((x for x in WISHES if x["id"] == a["wish_id"]), {})
            c["wish_new"].append({"id": a["wish_id"], "resident_id": r["id"], "name": r["name"],
                                  "line": (w.get("line_after") or row["line"] or "").replace("{name}", r["name"])})
        day_note(st, "wish", r["name"])
    c["arc_log"].append({k: row.get(k) for k in ("arc_id", "resident_id", "name", "step", "size", "announce", "line",
                                                 "beat", "log", "ask", "done", "day", "imprint")} | {"shown": False})
    del c["arc_log"][:-60]
    day_note(st, "arc", r["name"])
    session_note(st, row.get("announce") or row.get("beat") or row.get("line"))
    log(uid, "arc_beat", {"arc": a["id"], "step": s["step"], "resident": r["id"], "done": done})
    return row


def arc_tick(st: dict, uid: str) -> list:
    """수동 판정(건네기가 필요 없는 매듭) + 미룬 큰 매듭. 사람마다 하루 한 매듭."""
    c = core_of(st)
    day = day_of(st)
    out = []
    keep = []
    for d in c["deferred"]:
        r = next((x for x in st.get("residents_list") or [] if x["id"] == d["rid"]), None)
        a = ARC_BY_ID.get(d["arc"])
        if not r or not a:
            continue
        s = arc_state(st, r["id"], a["id"])
        beat = next_beat(a, s)
        if beat is None or int(beat.get("step", 0)) != int(d.get("step") or 0):
            continue
        if int(d.get("day") or 0) < day and c.get("big_day") != day:
            out.append(fire_beat(st, uid, r, a, s, beat, d.get("item"), force=True))
        else:
            keep.append(d)
    c["deferred"] = keep
    fired = {x.get("resident_id") for x in out}
    if CALENDAR_ENFORCE and not is_unlocked(st, "first_chain_knot"):
        return out
    for r in st.get("residents_list") or []:
        if r["id"] in fired or r["id"] in (st.get("outside") or []):
            continue
        a, s = current_arc(st, r)
        if not a:
            continue
        beat = next_beat(a, s)
        if not beat or not beat_open(st, r, s, beat) or arc_today_blocked(st, s, beat):
            continue
        trig = beat.get("trigger") or {}
        soft_check(st, r, s, beat)
        if trig_needs_give(trig) or beat_already_fired(st, r, a, s, beat):
            continue
        if trig_all(st, uid, r, s, trig, None):
            out.append(fire_beat(st, uid, r, a, s, beat))
    return out


def arc_try_give(st: dict, uid: str, r: dict, item: dict, preview: bool = False) -> dict | None:
    """그 사람에게 이 물건을 주면 사슬 다음 매듭이 풀리나. preview 면 판정만(주기 기록 없이 give_distinct 를 하나 더 센다)."""
    if CALENDAR_ENFORCE and not is_unlocked(st, "first_chain_knot"):
        return None                                   # S25: 매듭은 켠 날 3부터
    a, s = current_arc(st, r)
    if not a:
        return None
    beat = next_beat(a, s)
    if not beat or not beat_open(st, r, s, beat) or arc_today_blocked(st, s, beat):
        return None
    if beat_already_fired(st, r, a, s, beat):
        return None                                   # S22 r4-1: 이미 푼 매듭은 다시 제안하지도 풀지도 않는다
    soft_check(st, r, s, beat)
    trig = beat.get("trigger") or {}
    if "give" not in json.dumps(trig) and "give_distinct" not in json.dumps(trig):
        return None
    ev = {"item": item, "to": r["id"]}
    if preview:
        res = cres(st, r["id"])
        res["given"].append(dict(item, day=day_of(st), _probe=True))
        try:
            ok = trig_all(st, uid, r, s, trig, ev)
        finally:
            res["given"] = [g for g in res["given"] if not g.get("_probe")]
        return {"arc_id": a["id"], "step": beat.get("step")} if ok else None
    if trig_all(st, uid, r, s, trig, ev):
        return fire_beat(st, uid, r, a, s, beat, item)
    return None


def arc_status(st: dict, uid: str, r: dict) -> dict | None:
    a, s = current_arc(st, r)
    if not a:
        last = [aid for aid, x in (cres(st, r["id"])["arcs"] or {}).items() if x.get("done")]
        return {"id": last[-1], "done": True, "title": (ARC_BY_ID.get(last[-1]) or {}).get("title")} if last else None
    beat = next_beat(a, s)
    nxt = None
    if beat:
        soft_check(st, r, s, beat)
        trig = beat.get("trigger") or {}
        hint = None
        soft = s.get("soft_step") == int(s["step"]) + 1
        for key in ("give", "give_distinct", "place"):
            if key in trig:
                v = (safe_rule(soft_rule(s, trig[key])) or {"category": ""}) if key != "place" else trig[key]
                hint = (rule_ko(v) + (f" 서로 다른 것 {v.get('n')}개" if key == "give_distinct" else "")) if key != "place" \
                    else f"{(ROOMS.get(v.get('room')) or {}).get('name', v.get('room'))}에 놓기"
                break
        pend = s.get("ask_pending")
        prev = next((b for b in a["beats"] if int(b.get("step", 0)) == pend), None) if pend else None
        nxt = {"step": int(beat.get("step", s["step"] + 1)), "open": beat_open(st, r, s, beat),
               "opens_day": beat_opens_day(st, r, s, beat), "hint_ko": hint, "icon": "chain",
               "size": beat.get("size", "small"), "evening": (trig.get("session") == "evening"),
               "soft": soft, "soft_hint": fill_text(beat.get("soft_hint"), st, r) if soft else None,
               "ask": ({"step": pend, **{k: (prev.get("ask") or {}).get(k) for k in ("kind", "label", "options", "default", "category", "subtype", "room", "n")}}
                       if prev and str(pend) not in (s.get("asks") or {}) else None)}
    return {"id": a["id"], "title": a.get("title"), "step": int(s["step"]), "steps": len(a.get("beats") or []),
            "next": nxt, "done": False}


# ── 주기 판정 ───────────────────────────────────────────────────
def morale_add(st: dict, amount: float) -> int:
    frac = float(st.get("morale_frac") or 0) + float(amount)
    whole = int(frac + 1e-9)
    st["resources"]["morale"] = int(st["resources"].get("morale", 0)) + whole
    st["morale_frac"] = round(frac - whole, 3)
    return whole


def memory_match(st: dict, r: dict, item: dict) -> dict | None:
    seen = set(cres(st, r["id"])["memories_seen"])
    for m in role_taste(r.get("role", "")).get("memories") or []:
        if isinstance(m, dict) and m.get("id") not in seen and match(m.get("trigger"), item):
            return m
    return None


def resident_tier(st: dict, uid: str, r: dict, item: dict) -> tuple[str, dict]:
    """한 사람에게 이 물건 — 사슬 > 기억 > (안 맞음) > 필요 > 좋아함 > 그 밖(not_for_me)."""
    info: dict = {}
    if not item_safe(item):                           # S30 r7-1: 담배·술·붕대 밖 약은 판정도 많아야 반가움(좋아함·필요·기억·매듭·big 없음)
        tw = twist_of(uid, r).get("dislike")
        if tw and match({"category": tw["category"], "subtype": tw.get("subtype")}, item):
            return "not_for_me", info
        return "warm", {"unsafe": True}
    arc = arc_try_give(st, uid, r, item, preview=True)
    if arc:
        info["arc"] = arc
    mem = memory_match(st, r, item)
    if mem:
        info["memory"] = mem
    if arc:
        return "chain_beat", info
    if mem:
        return "memory", info
    tw = twist_of(uid, r)
    if tw.get("dislike") and match({"category": tw["dislike"]["category"], "subtype": tw["dislike"].get("subtype")}, item):
        return "not_for_me", info
    nd = need_today(uid, r, day_of(st))
    if nd and match(nd, item):
        info["need"] = nd
        return "need", info
    if any(match(lk, item) for lk in likes_of(uid, r)):
        return "like", info
    rt = role_taste(r.get("role", ""))
    cats = {x.get("category") for x in likes_of(uid, r) + list(rt.get("needs") or []) if isinstance(x, dict)}
    if item.get("category") in cats:
        return "warm", info                          # S20: 같은 갈래면 반가워한다(정확히 좋아하는 종류는 아니어도)
    return "not_for_me", info


def cur_session_n(st: dict) -> int | None:
    """지금 세션 번호. 마지막 활동이 세션 간격을 넘었으면 다음 /api/ark 가 열 새 세션(n+1)으로 본다. 세션이 없으면 None."""
    ss = core_of(st)["session"]
    if not ss.get("n"):
        return None
    if ss.get("last") and time.time() - float(ss["last"]) > SESSION_GAP_SEC:
        return int(ss["n"]) + 1
    return int(ss["n"])


def same_session(st: dict, rec: dict) -> bool:
    """S21: 같은 사람 감쇠는 세션마다 초기화(아침·저녁 따로). 세션을 모르면 4시간 간격을 새 세션으로."""
    n = cur_session_n(st)
    if n is not None and rec.get("ses") is not None:
        return int(rec["ses"]) == n and int(rec.get("day") or 0) == day_of(st)
    at = rec.get("at")
    if isinstance(at, (int, float)):
        return time.time() - float(at) < DIM_FALLBACK_GAP
    return int(rec.get("day") or 0) == day_of(st)


def give_diminish(st: dict, r: dict, item: dict) -> tuple[float, list]:
    day = day_of(st)
    g = cres(st, r["id"])["given"]
    why = []
    if any(same_session(st, x) for x in g):
        why.append({"kind": "same_person_today", "mult": DIM_SAME_DAY})
    k = item_key(item)
    if k and any(item_key(x) == k and day - int(x.get("day") or 0) < DIM_ITEM_DAYS for x in g):
        why.append({"kind": "same_item_3days", "mult": DIM_SAME_ITEM})
    if not why:
        return 1.0, []
    if DIM_COMBINE == "min":
        w = min(why, key=lambda x: x["mult"])         # 곱하지 않는다 — 작은 쪽 하나만
        return round(w["mult"], 4), [w]
    m = 1.0
    for w in why:
        m *= w["mult"]
    return round(m, 4), why


def decor_cap(room: dict) -> int:
    return int(DECOR_SLOTS.get(room_level(room), 2))


def decor_items(st: dict, slot) -> list:
    return (core_of(st)["rooms"].get(str(slot)) or {}).get("items") or []


def tag_feeds(tag: dict, it: dict) -> bool:
    return any(match(f, it) for f in tag.get("feeds") or [])


def decor_tags(st: dict, slot, prefer: str | None = None) -> list:
    """S22 r4-10: 꼬리표는 방주에 한 번만 붙는다 — 처음 붙은 칸이 그 꼬리표를 가진다(core.tags_formed).
    prefer 를 주면 같은 진척일 때 그 꼬리표가 먼저 붙는다(r4-9 제안한 꼬리표 = 붙는 꼬리표)."""
    items = [it for it in decor_items(st, slot) if not it.get("boxed")]
    formed = core_of(st).setdefault("tags_formed", {})
    rows = []
    for t in DECOR_TAGS:
        have = sum(1 for it in items if tag_feeds(t, it))
        if have:
            owner = formed.get(t["id"])
            rows.append({"id": t["id"], "ko": t.get("ko"), "have": have, "need": ITEMS_TO_TAG, "on": False, "look": t.get("look"),
                         "elsewhere": owner is not None and int(owner) != int(slot)})
    order = [t["id"] for t in DECOR_TAGS]
    rows.sort(key=lambda x: (x["elsewhere"], -x["have"], x["id"] != prefer, order.index(x["id"])))
    n_on = 0
    for x in rows:
        if x["have"] >= ITEMS_TO_TAG and n_on < MAX_TAGS_PER_ROOM and not x["elsewhere"]:
            x["on"] = True
            n_on += 1
            formed.setdefault(x["id"], int(slot))
    return rows


def leading_tag(st: dict, room: dict) -> str | None:
    """그 방에서 가장 앞선(아직 안 붙은) 꼬리표. 진척(have/need)이 가장 크고, 같으면 물건 수, 같으면 어울리는 방·표 순서.
    아무 꼬리표도 시작하지 않았으면 None(그때는 물건이 먹이는 꼬리표 중 고른다)."""
    on = set(room_tags_on(st, room["slot"]))
    rows = [x for x in decor_tags(st, room["slot"]) if not x["on"] and x["id"] not in on and x["have"] > 0 and not x.get("elsewhere")]
    if not rows:
        return None
    order = [t["id"] for t in DECOR_TAGS]
    rows.sort(key=lambda x: (-x["have"] / max(1, x["need"]), -x["have"],
                             room["id"] not in ((DECOR_BY_ID.get(x["id"]) or {}).get("best_rooms") or []), order.index(x["id"])))
    return rows[0]["id"]


def room_decor_tier(st: dict, uid: str, room: dict, item: dict) -> tuple[str, dict]:
    """방에 놓을 때 — 사슬(놓기 매듭) > 꾸밈(꼬리표에 다가감) > plain."""
    for r in st.get("residents_list") or []:
        a, s = current_arc(st, r)
        beat = next_beat(a, s) if a else None
        if not beat or not beat_open(st, r, s, beat) or arc_today_blocked(st, s, beat):
            continue
        pv = (beat.get("trigger") or {}).get("place") or {}
        if pv.get("room") == room["id"] and pv.get("category") and \
                match({"category": pv["category"], "subtype": pv.get("subtype")}, item) and \
                trig_all(st, uid, r, s, {k: v for k, v in beat["trigger"].items() if k != "place"}, None):
            return "chain_beat", {"arc": {"arc_id": a["id"], "step": beat.get("step"), "resident_id": r["id"]}}
    on = room_tags_on(st, room["slot"])
    lead = leading_tag(st, room)
    best = None
    formed = core_of(st).setdefault("tags_formed", {})
    for t in DECOR_TAGS:
        if not tag_feeds(t, item) or t["id"] in on:
            continue
        if formed.get(t["id"]) is not None and int(formed[t["id"]]) != int(room["slot"]):
            continue                                  # S22: 다른 방이 이미 가진 꼬리표는 권하지 않는다
        if lead and t["id"] != lead:
            continue                                  # S21: 그 방에서 가장 앞선 꼬리표만 권한다(꾸밈 루프가 닫히게)
        have = sum(1 for it in decor_items(st, room["slot"]) if not it.get("boxed") and tag_feeds(t, it))
        pref = room["id"] in (t.get("best_rooms") or [])
        score = (have, pref)                          # S20: 어울리는 꼬리표가 하나라도 있으면 그 방도 후보(어울리는 방이 먼저)
        if best is None or score > best[0]:
            best = (score, t, have)
    if best:
        t = best[1]
        return "decor", {"tag": t["id"], "tag_ko": t.get("ko"), "tag_have": best[2], "tag_need": ITEMS_TO_TAG}
    return "plain", {}


def give_value(tier: str) -> float:
    if tier == "warm":
        return WARM_V
    if tier == "not_for_me":
        return OUTCOME_V.get("neutral_person", 0.5)
    if tier == "plain":
        return OUTCOME_V.get("keep", 0.8)
    return OUTCOME_V.get(tier, 1.0)


def where_for(st: dict, uid: str, item: dict, compact: bool = False) -> dict:
    sug = []
    out_ids = set(st.get("outside") or [])
    for r in st.get("residents_list") or []:
        if r["id"] in out_ids:
            continue
        tier, info = resident_tier(st, uid, r, item)
        if tier not in TIER_ICON:
            continue
        mult, _ = give_diminish(st, r, item)
        row = {"kind": "resident", "target": {"resident_id": r["id"]}, "name": r["name"], "role": r.get("role"),
               "tier": tier, "icon": TIER_ICON[tier], "value": give_value(tier), "mult": mult,
               "reason_ko": TIER_REASON.get(tier)}
        if info.get("arc"):
            row.update({"arc_id": info["arc"]["arc_id"], "step": info["arc"]["step"]})
        sug.append(row)
    for rm in (live_rooms(st) if (not CALENDAR_ENFORCE or is_unlocked(st, "decor_place")) else []):
        if len([x for x in decor_items(st, rm["slot"])]) >= decor_cap(rm):
            continue
        tier, info = room_decor_tier(st, uid, rm, item)
        if tier not in TIER_ICON:
            continue
        row = {"kind": "room", "target": {"slot": rm["slot"]}, "room_id": rm["id"],
               "name": room_display_name(st, rm), "name_ko": (ROOMS.get(rm["id"]) or {}).get("name", rm["id"]),
               "tier": tier, "icon": TIER_ICON[tier],
               "value": give_value(tier), "mult": 1.0,
               "free_slots": decor_cap(rm) - len(decor_items(st, rm["slot"])),
               "reason_ko": (f"{info.get('tag_ko')}까지 하나" if info.get("tag_have", 0) + 1 >= ITEMS_TO_TAG
                             else f"{info.get('tag_ko')} 쪽으로") if tier == "decor" else TIER_REASON.get(tier)}
        row.update({k: v for k, v in info.items() if k in ("tag", "tag_ko", "tag_have", "tag_need")})
        if info.get("arc"):
            row.update({"arc_id": info["arc"]["arc_id"], "step": info["arc"]["step"]})
        sug.append(row)
    if not item_safe(item):                            # S24: 담배·술·약을 '좋아함'으로 권하지 않는다(우연히 주는 건 괜찮다)
        for x in sug:
            if x["kind"] == "resident" and x["tier"] in ("like", "memory"):
                x.update({"tier": "warm", "icon": "warm", "value": WARM_V, "reason_ko": TIER_REASON["warm"], "unsafe_like": True})
    # S20 늘 둘 이상: 제안 밖 사람 중 '반가워할' 사람(같은 갈래를 좋아하거나 필요한 사람 → 오늘 아직 안 받은 사람)
    have_ids = {x["target"].get("resident_id") for x in sug if x["kind"] == "resident"}
    if len(sug) < 2:
        rng = random.Random(f"{uid}|{day_of(st)}|{item_key(item)}|warm")
        fb = []
        for r in st.get("residents_list") or []:
            if r["id"] in out_ids or r["id"] in have_ids:
                continue
            tw = twist_of(uid, r).get("dislike")
            if tw and match({"category": tw["category"], "subtype": tw.get("subtype")}, item):
                continue
            rt = role_taste(r.get("role", ""))
            near = sum(1 for x in likes_of(uid, r) + list(rt.get("needs") or []) if isinstance(x, dict) and x.get("category") == item.get("category"))
            given = cres(st, r["id"]) and sum(1 for g in cres(st, r["id"])["given"] if int(g.get("day") or 0) == day_of(st))
            fb.append((-near, given, rng.random(), r))
        fb.sort(key=lambda x: x[:3])
        for _, _, _, r in fb[: 2 - len(sug)]:
            mult, _ = give_diminish(st, r, item)
            sug.append({"kind": "resident", "target": {"resident_id": r["id"]}, "name": r["name"], "role": r.get("role"),
                        "tier": "warm", "icon": "warm", "value": WARM_V, "mult": mult, "reason_ko": TIER_REASON["warm"],
                        "fallback": True})
    tie = random.Random(f"{uid}|{day_of(st)}|{item_key(item)}|order")     # 같은 값이면 날·물건마다 순서가 달라진다
    tiek = {id(x): tie.random() for x in sug}
    sug.sort(key=lambda x: (-round(x["value"] * x["mult"], 4), TIER_ORDER.index(x["tier"]), x["kind"] != "resident",
                            -int(x.get("tag_have") or 0), tiek[id(x)]))     # S22: 같으면 많이 찬 꼬리표 먼저
    if sug and sug[0]["tier"] == "warm":
        nw = next((x for x in sug if x["tier"] != "warm"), None)
        if nw:                                        # S21: 1순위만 누르는 사람(B)에게 warm 이 첫자리면 「잘 받으셨습니다」로 끝난다
            sug.remove(nw)
            sug.insert(0, nw)
    pick, n_room = [], 0
    room_cap = 1 if decor_unlock_day(st) else 2       # S30: 꾸밈이 열린 날 「어디로」가 꾸밈으로 차지 않게
    for x in sug:
        if x["kind"] == "room":
            near_tag = int(x.get("tag_have") or 0) + 1 >= int(x.get("tag_need") or ITEMS_TO_TAG)
            if n_room >= room_cap and not (near_tag and n_room < 2):
                continue
            n_room += 1
        pick.append(x)
        if len(pick) >= int(_GP.get("suggest_count", 3)):
            break
    return notebook_view(st, uid, item, {"scan_id": item.get("card_id"), "suggest": pick,
            "heirloom": heirloom_options(st, uid, item),
            "warm_ids": [x["target"]["resident_id"] for x in pick if x.get("fallback")],
            "shelf": {"target": "shelf", "value": OUTCOME_V.get("keep", 0.8), "label": "선반에"},
            "default": "shelf", "compact": bool(compact)})


def detach_item(st: dict, ref: str | None, placed: str | None) -> dict | None:
    """물건을 선반·창고 상자에서 떼어 낸다(준 순간 그 사람·방으로 간다). 사본(재스캔)이면 아무것도 안 뗀다."""
    if not ref or placed == "copy":
        return None
    for it in list(st.get("shelf") or []):
        if it.get("card_id") == ref:
            st["shelf"] = [x for x in st["shelf"] if x is not it]
            return it
    for it in list(st.get("stored") or []):
        if it.get("id") == ref or it.get("card_id") == ref:
            st["stored"] = [x for x in st["stored"] if x is not it]
            return it
    return None


def return_to_shelf(st: dict, row: dict | None) -> str:
    if not row:
        return "shelf"
    r = dict(row)
    r.pop("boxed", None)
    if shelf_try_put(st, r) is not None:
        return "shelf"
    r["id"] = r.get("card_id") or r.get("id") or f"st-{int(time.time() * 1000)}"
    r.pop("slot", None)
    st.setdefault("stored", []).append(r)
    return "stored"


GIVE_LINES = {"place_decor": "place_progress", "warm": "soft_thanks"}


def generic_reaction(kind: str, item: dict, room: str | None = None, st: dict | None = None, **kw) -> dict:
    """S20: 문장이 늘 있다. ui_moments give.<kind>[] 를 돌려 쓰고(같은 줄 연속 금지), 없으면 기본 줄."""
    nm = (item or {}).get("name") or "그 물건"
    dflt = {"shelf": "「{item}」, 선반에 올려 두었습니다.",
            "place_progress": "「{item}」, {room}에 놓아 두었습니다.",
            "place_tag_formed": "{room}, 이제 「{tag}」입니다.",
            "place_plain": "「{item}」, {room}에 놓아 두었습니다.",
            "soft_thanks": "{name} 님이 고맙게 받아 두셨습니다."}
    k = GIVE_LINES.get(kind, kind)
    lines = (moments().get("give") or {}).get(k)
    if isinstance(lines, str):
        lines = [lines]
    i = 0
    if lines and st is not None:
        rot = core_of(st)["flags"].setdefault("give_rot", {})
        i = int(rot.get(k, 0)) % len(lines)
        rot[k] = i + 1
    tpl = lines[i] if lines else dflt.get(k, "")
    vals = {"item": nm, "room": room or "", **{x: str(v) for x, v in kw.items()}}
    for x, v in vals.items():
        tpl = tpl.replace("{" + x + "}", v)
    return {"announce_key": f"give.{k}" + (f".{i}" if lines else ""), "announce": tpl}


def give_apply(st: dict, uid: str, item: dict, target, placed: str | None, warm_ids: list | None = None) -> dict:
    day = day_of(st)
    c = core_of(st)
    if target == "shelf" or target is None:
        g = generic_reaction("shelf", item, st=st)
        session_note(st, g["announce"])
        return {"tier": "keep", "value": OUTCOME_V.get("keep", 0.8), "mult": 1.0, "diminish": None, "target": "shelf",
                "who": None, "reaction": dict(g, line=None, line_key=None), "effects": {"returned_to_shelf": False}}
    if not isinstance(target, dict):
        raise HTTPException(400, "어디로 줄지 골라 주세요")
    A = TASTES.get("announce") or {}
    if target.get("resident_id"):
        r = next((x for x in st.get("residents_list") or [] if x["id"] == target["resident_id"]), None)
        if not r:
            raise HTTPException(400, "없는 사람입니다")
        if r["id"] in (st.get("outside") or []):
            raise HTTPException(400, f"{r['name']} 님은 지금 밖에 나가 있습니다")
        tier, info = resident_tier(st, uid, r, item)
        if tier == "not_for_me" and r["id"] in (warm_ids or []):
            tw = twist_of(uid, r).get("dislike")
            if not (tw and match({"category": tw["category"], "subtype": tw.get("subtype")}, item)):
                tier = "warm"                         # 「어디로」가 반가워할 사람으로 제안한 것은 지킨다
        mult, why = give_diminish(st, r, item)
        rt = role_taste(r.get("role", ""))
        eff: dict = {"morale": 0, "room_bonus": None, "keepsake": None, "memory": None, "arc": None, "decor": None,
                     "returned_to_shelf": False}
        reaction = {"who": r["id"]}
        if tier == "not_for_me":
            reaction.update({"announce_key": "resident_tastes.announce.give_not_for_me",
                             "announce": fill_text(A.get("give_not_for_me"), st, r, item),
                             "line_key": f"resident_tastes.roles.{r.get('role')}.not_for_me",
                             "line": fill_text(rt.get("not_for_me"), st, r, item)})
            eff["returned_to_shelf"] = True
            session_note(st, reaction["announce"])
            return {"tier": tier, "value": give_value(tier), "mult": 1.0, "diminish": None, "target": target,
                    "who": {"id": r["id"], "name": r["name"], "role": r.get("role")}, "reaction": reaction, "effects": eff}
        row = detach_item(st, item.get("card_id"), placed)
        res = cres(st, r["id"])
        rec = {k: item.get(k) for k in ("name", "category", "subtype", "family", "rarity", "barcode", "card_id")}
        rec.update({"day": day, "ses": cur_session_n(st), "at": time.time()})
        res["given"].append(rec)
        del res["given"][:-80]
        res["items"].append(dict(rec, row=row))
        del res["items"][:-30]
        # 사슬(건넨 기록을 넣은 뒤 판정 — give_distinct 가 이번 물건을 센다)
        if tier == "chain_beat":
            eff["arc"] = arc_try_give(st, uid, r, item)
            if not eff["arc"]:
                tier = "like"
        if info.get("memory"):
            m = info["memory"]
            res["memories_seen"].append(m["id"])
            res["memory_day"] = day                   # S27 r5-1
            eff["memory"] = {"id": m["id"], "announce": fill_text(m.get("announce"), st, r, item),
                             "line": fill_text(m.get("line"), st, r, item)}
        mood = float(((GIVE_EFFECTS.get(tier) or {}).get("mood")) or {"need": 2, "like": 1, "memory": 2, "warm": 0.5}.get(tier, 0))
        if tier != "chain_beat":                    # 사슬 매듭의 사기 +2 는 fire_beat 가 이미 더했다
            eff["morale"] = morale_add(st, mood * mult)
        else:
            eff["morale"] = int(mood)
        if tier == "need":
            slot = station_slot(st, r["id"])
            if slot is not None and room_at(st, slot):
                c.setdefault("need_bonus", {})[str(slot)] = day
                eff["room_bonus"] = {"slot": slot, "pct": int(round(100 * float((GIVE_EFFECTS.get("need") or {}).get("room_output_bonus_today", 0.1)))), "day": day}
        if tier in ("like", "need", "memory", "chain_beat") and not res.get("keepsake") and \
                any(match(lk, item) for lk in likes_of(uid, r)):
            res["keepsake"] = {k: item.get(k) for k in ("name", "category", "subtype")} | {"day": day}
            ks = (TASTES.get("personal_twist") or {}).get("keepsake") or {}
            eff["keepsake"] = {"name": item.get("name"), "line": fill_text(ks.get("line"), st, r, item)}
        key = {"chain_beat": "give_plain", "memory": "memory_open", "need": "give_needed", "like": "give_liked",
               "warm": "give_plain"}[tier]
        lkey = {"need": "needed_lines", "like": "liked_lines", "warm": "warm_lines"}.get(tier, "")
        lines = rt.get(lkey) or []
        li = None
        if lines:                                     # S21: 사람마다 돌려 쓴다(8줄이면 7일 안에 같은 줄 없음)
            rot = res.setdefault("line_rot", {})
            if lkey not in rot:
                rot[lkey] = random.Random(f"{uid}|{r['id']}|{lkey}").randrange(len(lines))
            li = int(rot[lkey]) % len(lines)
            rot[lkey] = li + 1
        reaction.update({"announce_key": f"resident_tastes.announce.{key}",
                         "announce": (eff["arc"] or {}).get("announce") or (eff["memory"] or {}).get("announce")
                         or fill_text(A.get(key), st, r, item),
                         "line_key": (f"resident_tastes.roles.{r.get('role')}.{lkey}.{li}" if li is not None else None),
                         "line": (eff["arc"] or {}).get("line") or (eff["memory"] or {}).get("line")
                         or (fill_text(lines[li], st, r, item) if li is not None else None)
                         or None})
        if tier == "warm":
            gw = generic_reaction("warm", item, st=st, name=r["name"])
            reaction.update({"announce": gw["announce"], "announce_key": gw["announce_key"]})
            if not reaction.get("line") or reaction["line"] == gw["announce"]:
                reaction["line"], reaction["line_key"] = None, None     # warm_lines 가 없으면 같은 문장을 두 번 내지 않는다
        session_note(st, reaction["announce"])
        log(uid, "give", {"to": r["id"], "tier": tier, "mult": mult, "item": item_key(item)})
        return {"tier": tier, "value": give_value(tier), "mult": mult, "diminish": why or None, "target": target,
                "who": {"id": r["id"], "name": r["name"], "role": r.get("role")}, "reaction": reaction, "effects": eff}
    if target.get("slot") is not None:
        require_unlocked(st, "decor_place")
        rm = room_at(st, target["slot"])
        if not rm or rm.get("flooded"):
            raise HTTPException(400, "그 자리에는 꾸밀 방이 없습니다")
        cur = decor_items(st, rm["slot"])
        if len(cur) >= decor_cap(rm):
            raise HTTPException(400, "꾸밈 칸이 다 찼습니다")
        tier, info = room_decor_tier(st, uid, rm, item)
        sug_tag = info.get("tag")                     # S21 버그 2: 반응은 제안한 그 꼬리표로 말한다
        before = set(room_tags_on(st, rm["slot"]))
        first_tag_ever = not any(room_tags_on(st, x["slot"]) for x in live_rooms(st))
        row = detach_item(st, item.get("card_id"), placed)
        rec = {k: item.get(k) for k in ("name", "category", "subtype", "family", "rarity", "barcode", "card_id", "prop_id")}
        rec.update({"id": f"dec-{item.get('card_id') or int(time.time() * 1000)}", "day": day, "row": row, "boxed": False})
        c["rooms"].setdefault(str(rm["slot"]), {}).setdefault("items", []).append(rec)
        after = [x["id"] for x in decor_tags(st, rm["slot"], prefer=sug_tag) if x["on"]]
        if sug_tag in after:                          # S22 r4-9: 둘이 함께 붙으면 제안한 꼬리표를 먼저 말한다
            after = [sug_tag] + [x for x in after if x != sug_tag]
        added = None
        rname = (ROOMS.get(rm["id"]) or {}).get("name", rm["id"])
        for tid in after:
            if tid not in before and not added:
                t = DECOR_BY_ID[tid]
                seen = c["tags_seen"].setdefault(str(rm["slot"]), [])
                added = {"id": tid, "ko": t.get("ko"), "look": t.get("look"),
                         "announce": (t.get("announce") or "").replace("{room}", rname) if tid not in seen else None}
                if tid not in seen:
                    seen.append(tid)
        if added and first_tag_ever and not c["flags"].get("visit_guarantee_used"):
            # S22: 첫 꼬리표가 붙으면 다음 세션(30분 이상 뒤)에 첫 손님 확정. 그날 안 오면 다음 날 굴림에서 확정
            c["flags"]["visit_guarantee"] = {"at": time.time(), "day": day, "slot": rm["slot"], "tag": added["id"], "done": False}
            c["flags"]["visit_guarantee_used"] = True
        arc_row = None
        for r in st.get("residents_list") or []:          # 놓기 매듭은 놓는 순간 판정
            a, s = current_arc(st, r)
            beat = next_beat(a, s) if a else None
            if beat and beat_open(st, r, s, beat) and s.get("last_day") != day and "place" in json.dumps(beat.get("trigger") or {}) \
                    and not trig_needs_give(beat.get("trigger") or {}) and trig_all(st, uid, r, s, beat["trigger"], None):
                arc_row = fire_beat(st, uid, r, a, s, beat, item)
                break
        if tier == "decor" or added:
            tier = "decor" if not arc_row else "chain_beat"
        elif arc_row:
            tier = "chain_beat"
        eff = {"morale": 0, "decor": {"slot": rm["slot"], "room_id": rm["id"], "items": len(decor_items(st, rm["slot"])),
                                      "cap": decor_cap(rm), "tag_added": added, "tags": decor_tags(st, rm["slot"])},
               "arc": arc_row, "returned_to_shelf": False}
        session_note(st, (added or {}).get("announce") or (arc_row or {}).get("announce"))
        log(uid, "place", {"slot": rm["slot"], "tier": tier, "tag": (added or {}).get("id")})
        _tg = next((x for x in decor_tags(st, rm["slot"]) if x["id"] == sug_tag and not x["on"]), None) \
            or (next((x for x in decor_tags(st, rm["slot"]) if not x["on"] and tag_feeds(DECOR_BY_ID[x["id"]], item)), None)
                if not sug_tag else None) or {}
        gr = (generic_reaction("place_tag_formed", item, rname, st=st, tag=added.get("ko")) if added else
              generic_reaction("place_decor", item, rname, st=st, tag=_tg.get("ko") or "", n=_tg.get("have", 0), m=_tg.get("need", ITEMS_TO_TAG))
              if tier == "decor" and _tg else generic_reaction("place_plain", item, rname, st=st))
        ann = (arc_row or {}).get("announce") or (added or {}).get("announce")
        if added and not ann:
            ann = None
        return {"tier": tier, "value": give_value(tier), "mult": 1.0, "diminish": None, "target": target, "who": None,
                "reaction": {"announce": ann or gr["announce"],
                             "announce_key": (f"room_decor.tags.{added['id']}.announce" if added else None) if ann else gr["announce_key"],
                             # S21 버그 4: 관리실 줄과 같은 문장을 line 으로 다시 내지 않는다(없으면 null)
                             "line": (arc_row or {}).get("line") or (added or {}).get("look") or None,
                             "line_key": "arc" if (arc_row or {}).get("line") else
                                         (f"room_decor.tags.{added['id']}.look" if added else None)},
                "effects": eff}
    raise HTTPException(400, "어디로 줄지 골라 주세요")


# ── 방문자(꼬리표가 부르는 이) ─────────────────────────────────────
def visit_roll(uid: str, day: int, slot, tag: str, kind: str) -> float:
    return random.Random(f"{uid}|{day}|visit|{slot}|{tag}|{kind}").random()


def visit_rows_for(st: dict, uid: str, day: int) -> list:
    rows = []
    c = core_of(st)
    hall_ids = [r["id"] for r in hall_of(st)]
    for rm in live_rooms(st):
        rname = (ROOMS.get(rm["id"]) or {}).get("name", rm["id"])
        for tid in room_tags_on(st, rm["slot"]):
            t = DECOR_BY_ID.get(tid) or {}
            kinds = list(t.get("visitors") or [])
            v = VISITORS_BY_TAG.get(tid)
            vg = c["flags"].get("visit_guarantee") or {}
            forced = (not vg.get("done") and vg.get("slot") == rm["slot"] and vg.get("tag") == tid
                      and (day == int(vg.get("day") or 0) + 1 if vg.get("at") else vg.get("day") == day))
            if v and (forced or visit_roll(uid, day, rm["slot"], tid, "visitor") < VISITOR_DAILY):
                first = v["id"] not in c["visitors_seen"]
                rows.append({"day": day, "slot": rm["slot"], "room": rname, "tag": tid, "kind": "visitor",
                             "visitor_id": v["id"], "ko": v.get("ko"), "where": v.get("where"), "first": first,
                             "line": (v.get("arrival") if first else v.get("again") or v.get("arrival") or "").replace("{room}", rname),
                             "desc": v.get("desc"), "look": v.get("look")})
            for k in kinds:
                if k == "residents" and hall_ids:
                    rows.append({"day": day, "slot": rm["slot"], "tag": tid, "kind": "residents", "resident_ids": hall_ids})
                elif k == "octopus" and st.get("octopus") and visit_roll(uid, day, rm["slot"], tid, k) < VISIT_P.get("octopus", 0.5):
                    rows.append({"day": day, "slot": rm["slot"], "room": rname, "tag": tid, "kind": "octopus",
                                 "line": f"{(st.get('octopus') or {}).get('name') or '문어'}, {rname}에서 한참 놀다 갔습니다."})
                elif k == "gardener" and visit_roll(uid, day, rm["slot"], tid, k) < VISIT_P.get("gardener", 0.15):
                    vv = voice_for("spot_water_reflection", f"{uid}|{day}|gardener|{rm['slot']}", who="gardener",
                                   act=int(st.get("act") or 1))
                    rows.append({"day": day, "slot": rm["slot"], "room": rname, "tag": tid, "kind": "gardener",
                                 "line": f"{rname} 창밖에 은빛 떼가 잠깐 머물렀습니다.", "voice": vv})
                elif k == "newhuman":
                    rows.append({"day": day, "slot": rm["slot"], "tag": tid, "kind": "newhuman_tilt",
                                 "lineage": TAG_NEWHUMAN_LINEAGE.get(tid)})
            rare_p = display_rare_chance(st, rm["slot"])      # S25 진귀함 이상을 걸면 드문 모습
            if v and rare_p and visit_roll(uid, day, rm["slot"], tid, "rare") < rare_p:
                rv = v.get("rare") or {}
                rows.append({"day": day, "slot": rm["slot"], "room": rname, "tag": tid, "kind": "visitor", "form": "rare",
                             "visitor_id": v["id"], "ko": rv.get("ko") or f"드문 {v.get('ko')}", "where": v.get("where"),
                             "first": f"{v['id']}:rare" not in c["visitors_seen"],
                             "line": (rv.get("arrival") or f"{rname} 창에 처음 보는 빛깔의 {v.get('ko')} 손님이 왔습니다.").replace("{room}", rname),
                             "desc": rv.get("desc")})
            if TAG_GUEST_ROLES.get(tid):                 # S20: core_a tag_guest_roles(꼬리표 다섯 × 역할 둘)
                rows.append({"day": day, "slot": rm["slot"], "tag": tid, "kind": "guest_tilt",
                             "roles": {x: TAG_GUEST_WEIGHT for x in TAG_GUEST_ROLES[tid]}})
    return rows


def visit_tick(st: dict, uid: str) -> list:
    c = core_of(st)
    day = day_of(st)
    if c["visits"].get("day") == day:
        return []
    rows = visit_rows_for(st, uid, day)
    prev = c["visits"] if isinstance(c.get("visits"), dict) else {}
    visitor_carry(st, prev)                           # 어제 손님이 남긴 다음 아침 효과(담요게)
    c["visits"] = {"day": day, "rows": rows}
    for v in rows:
        if v["kind"] == "visitor":
            apply_visit_row(st, uid, v)
        elif v["kind"] in ("octopus", "gardener"):
            overnight_add(st, "visit", {k: v.get(k) for k in ("slot", "room", "kind", "line")})
    return rows


def guest_role_weights(st: dict) -> dict:
    c = core_of(st)
    w: dict = {}
    for v in (c["visits"].get("rows") or []) if c["visits"].get("day") == day_of(st) else []:
        if v.get("kind") == "guest_tilt":
            for role, m in (v.get("roles") or {}).items():
                w[role] = max(w.get(role, 1), int(m))
    return w


def raid_target_weights(st: dict) -> dict | None:
    """꾸밈·사슬 물건이 있는 방은 습격 대상 가중 ×1.5(아끼는 것을 노린다). 하나도 없으면 None(옛 추첨 그대로)."""
    w = {}
    heir_slots = {station_slot(st, r["id"]) for r in st.get("residents_list") or [] if r.get("heirloom")}
    for rm in live_rooms(st):
        if any(not it.get("boxed") for it in decor_items(st, rm["slot"])) or rm["slot"] in heir_slots:
            w[rm["slot"]] = RAID_CHERISHED_MULT
    return w or None


def creature_mult(st: dict) -> dict | None:
    """트인 쪽(오른쪽, slot 홀수) 방에 전자제품 꾸밈이 둘 이상이면 긴목 ×1.3. 첫 주(켠 날 7 이하)는 끔(기획 위험 5)."""
    if play_day(st) <= 7:
        return None
    for rm in live_rooms(st):
        if int(rm["slot"]) % 2 == 1 and sum(1 for it in decor_items(st, rm["slot"])
                                             if it.get("category") == "electronics" and not it.get("boxed")) >= 2:
            return {"longneck": SHINY_LONGNECK_MULT}
    return None


def decor_on_crack(st: dict, slot) -> int:
    n = 0
    for it in decor_items(st, slot):
        if not it.get("boxed"):
            it["boxed"] = True
            n += 1
    if n:
        morale_add(st, -1)
    return n


def decor_on_repair(st: dict, slot) -> int:
    n = 0
    for it in decor_items(st, slot):
        if it.get("boxed"):
            it["boxed"] = False
            n += 1
    return n


def decor_on_breach(st: dict, slot) -> int:
    c = core_of(st)
    items = (c["rooms"].pop(str(slot), None) or {}).get("items") or []
    for it in items:
        row = dict(it.get("row") or {k: it.get(k) for k in ("name", "category", "rarity", "barcode", "card_id", "prop_id")})
        row["relic_name"] = row.get("relic_name") or it.get("name")
        row["id"] = it.get("id")
        row["from_slot"] = int(slot)
        row.pop("slot", None)
        st.setdefault("stored", []).append(row)
    return len(items)


def decor_on_reclaim(st: dict, slot) -> int:
    back = [x for x in st.get("stored") or [] if x.get("from_slot") == int(slot)]
    if not back:
        return 0
    st["stored"] = [x for x in st["stored"] if x.get("from_slot") != int(slot)]
    rm = room_at(st, slot)
    cap = decor_cap(rm) if rm else 2
    items = core_of(st)["rooms"].setdefault(str(slot), {}).setdefault("items", [])
    for row in back:
        if len(items) >= cap:
            st["stored"].append({k: v for k, v in row.items() if k != "from_slot"})
            continue
        it = item_from_row(row)
        it.update({"id": row.get("id") or f"dec-{row.get('card_id')}", "day": day_of(st), "boxed": False,
                   "row": {k: v for k, v in row.items() if k != "from_slot"}})
        items.append(it)
    return len(back)


def room_decor_public(st: dict) -> dict:
    out = {}
    for rm in live_rooms(st):
        items = decor_items(st, rm["slot"])
        out[str(rm["slot"])] = {"room_id": rm["id"], "level": room_level(rm), "cap": decor_cap(rm),
                                "items": [{k: it.get(k) for k in ("id", "name", "category", "subtype", "rarity", "boxed", "day")}
                                          for it in items],
                                "tags": decor_tags(st, rm["slot"]),
                                "boxed": [it.get("id") for it in items if it.get("boxed")]}
    return out


# ── 아침: 필요·머리맡 물건 ───────────────────────────────────────
def need_line(r: dict, nd: dict) -> str:
    # ⚠ 시나리오 문장 대기(요청함) — resident_tastes 에 need 방송 틀이 없다
    return f"{r['name']} 님이 오늘 「{nd['ko']}」 쪽 물건을 찾으십니다."


def need_met_today(st: dict, uid: str, r: dict, nd: dict | None = None) -> bool:
    """오늘의 필요를 이미 받았나 — 오늘 그 사람이 받은 물건 중 필요에 맞는 것이 있으면(등급이 사슬·기억이어도) 참.
    돌려준 물건(안 맞음)은 given 에 남지 않으므로 세지 않는다."""
    day = day_of(st)
    nd = nd if nd is not None else need_today(uid, r, day)
    if not nd:
        return False
    return any(int(g.get("day") or 0) == day and match(nd, g) for g in cres(st, r["id"])["given"])


def needs_today_public(st: dict, uid: str) -> list:
    day = day_of(st)
    out = []
    for r in st.get("residents_list") or []:
        nd = need_today(uid, r, day)
        if nd:
            out.append({"resident_id": r["id"], "name": r["name"], "need": nd, "announce": need_line(r, nd),
                        "met": need_met_today(st, uid, r, nd)})
    return out


def core_public(st: dict, uid: str) -> dict:
    day = day_of(st)
    res = {}
    for r in st.get("residents_list") or []:
        cr = cres(st, r["id"])
        rt = role_taste(r.get("role", ""))
        nd = need_today(uid, r, day)
        res[r["id"]] = {
            "needs_today": [nd] if nd else [],
            "likes": [{"category": x.get("category"), "subtype": x.get("subtype"), "family": x.get("family"), "ko": rule_ko(x)}
                      for x in rt.get("likes") or []],
            "twist": twist_of(uid, r),
            "keepsake": cr.get("keepsake"),
            "items": [{k: it.get(k) for k in ("name", "category", "subtype", "day")} for it in cr["items"][-8:]],
            "memories_seen": list(cr["memories_seen"]),
            "given_today": sum(1 for g in cr["given"] if int(g.get("day") or 0) == day),
            # S21 후속: 화면(base_core.js normTaste)이 「받음」 표시에 읽는 값 — 오늘의 필요를 받았으면 true
            "given_need_today": need_met_today(st, uid, r, nd),
            "arc": arc_status(st, uid, r),
            "seat": seat_public(st, r, cr),
            "arc_line": r.get("arc_line"),
            "keepsakes_recent": keepsakes_recent(cr),        # S22 ②: 그 사람 곁에 그릴 최근 받은 물건 셋
            "heirloom": heirloom_public(r),                     # S25 가보 칸
            "third_memory_open": bool(r.get("third_memory_open")),
            "notebook": notebook_public(st, uid, r),             # S23 사람 수첩
        }
    return {"residents": res, "props": list(core_of(st)["props"])}


def morning_core(st: dict, uid: str) -> None:
    """새 날의 첫 /api/ark 에서 한 번: 오늘 필요 방송·머리맡 물건 한 줄·사슬 다음 날 아침 줄."""
    c = core_of(st)
    day = day_of(st)
    if c.get("morning_day") == day:
        return
    c["morning_day"] = day
    nd = needs_today_public(st, uid)
    if nd:
        overnight_add(st, "needs", {"rows": [{"resident_id": x["resident_id"], "name": x["name"], "ko": x["need"]["ko"],
                                              "announce": x["announce"]} for x in nd]})
    ks = [(r, cres(st, r["id"])["keepsake"]) for r in st.get("residents_list") or [] if cres(st, r["id"]).get("keepsake")]
    if ks:
        r, k = random.Random(f"{uid}|{day}|keepsake").choice(ks)
        tpl = (((TASTES.get("personal_twist") or {}).get("keepsake") or {}).get("morning"))
        overnight_add(st, "keepsake", {"resident_id": r["id"], "name": r["name"], "item": k.get("name"),
                                       "line": fill_text(tpl, st, r, {"name": k.get("name")})})
    keep = []
    for m in c["morning_next"]:
        if int(m.get("day") or 0) <= day:
            overnight_add(st, m.get("kind", "arc_morning"), {"resident_id": m.get("resident_id"), "line": m.get("text")})
        else:
            keep.append(m)
    c["morning_next"] = keep
    for r in st.get("residents_list") or []:
        al = cres(st, r["id"]).get("after_line")
        if al and day % 3 == 0:
            n = random.Random(f"{uid}|{day}|{r['id']}|count").randint(2, 7)
            overnight_add(st, "arc_morning", {"resident_id": r["id"], "line": fill_text(al, st, r, None, None, n=n)})


# ── 세션·비트 캘린더 ─────────────────────────────────────────────
def play_day(st: dict) -> int:
    return int((core_of(st)["beats"]).get("play_day") or 0)


def session_tick(st: dict) -> dict:
    ss = core_of(st)["session"]
    t = time.time()
    new = not ss.get("last") or t - float(ss["last"]) > SESSION_GAP_SEC
    if new:
        ss.update({"n": int(ss.get("n") or 0) + 1, "start": t, "big": 0, "scans": 0, "changes": [],
                   "day": day_of(st)})
    ss["last"] = t
    ss["new"] = new
    return ss


def session_note(st: dict, text) -> None:
    ss = core_of(st)["session"]
    if text:
        ss.setdefault("changes", []).append(str(text))
        del ss["changes"][:-12]


def big_take(st: dict) -> bool:
    ss = core_of(st)["session"]
    if int(ss.get("big") or 0) >= BIG_WINDOWS_PER_SESSION:
        return False
    ss["big"] = int(ss.get("big") or 0) + 1
    return True


def beat_play_tick(st: dict) -> None:
    b = core_of(st)["beats"]
    day = day_of(st)
    if b.get("last_day") != day:
        b["play_day"] = int(b.get("play_day") or 0) + 1
        b["last_day"] = day
        b.setdefault("days", {})[str(b["play_day"])] = day


def beat_id_for(p: int) -> str | None:
    d = BEATS.get(str(p)) if p <= 14 else None
    return (d or {}).get("beat")


def beat_today_id(st: dict) -> str | None:
    return beat_id_for(play_day(st))


def weekly_log(st: dict, uid: str) -> dict:
    day = day_of(st)
    with db() as con:
        n = con.execute("SELECT COUNT(*) c FROM scans WHERE uid=? AND day>?", (uid, day - 7)).fetchone()["c"]
        first = con.execute("SELECT barcode FROM scans WHERE uid=? ORDER BY ts LIMIT 1", (uid,)).fetchone()
    top = max(st.get("shelf") or [{}], key=lambda it: (polish_level(it) if it else 0, -(float(it.get("scanned_at") or 0)) if it else 0))
    return {"scans_week": n, "first_barcode": first["barcode"] if first else None,
            "residents": [r["name"] for r in st.get("residents_list") or []],
            "octopus": (st.get("octopus") or {}).get("name"),
            "blocked": sum(1 for x in st.get("raid_log") or [] if x.get("result") in ("held", "passed") and int(x.get("day") or 0) > day - 7),
            "polished": (top or {}).get("relic_name") or (top or {}).get("name"),
            "arcs_done": [aid for v in core_of(st)["res"].values() for aid, a in (v.get("arcs") or {}).items() if a.get("done")]}


def beat_compose(st: dict, uid: str, p: int) -> dict:
    """켠 날 p 의 비트. 1~14 = beats.json(조건이 안 되면 alt), 15+ = 하루 하나·주 하나·두 주 하나."""
    oc = st.get("octopus") or {}
    spot_name = next((x.get("name") for x in SPOTS if x.get("id") in (st.get("spots_found") or [])), None)
    if p <= 14 and str(p) in BEATS:
        d = BEATS[str(p)]
        use_alt = False
        if d.get("beat") == "first_tide_first_spot" and not spot_name:
            use_alt = True
        if d.get("beat") == "newhuman_or_family_decor":
            use_alt = True                         # 신인류 그림 보류(DECISIONS 2026-10-04) — 대체 비트
        star = d.get("alt") if use_alt and d.get("alt") else d.get("star")
        if d.get("beat") == "rescue_second_resident_goal" and not rescue_happened(st):
            nm = newest_resident_name(st)
            star = (d.get("star_no_rescue") if nm else None) or d.get("alt") or \
                "관리실에서 알려 드립니다. 오늘 문간은 조용했습니다. 원정 나가실 분은 모르는 쪽으로 가 보셔도 좋겠습니다."
            star = star.replace("{name}", nm or "새 식구")
            use_alt = True
        if d.get("beat") == "first_knock_first_request" and not open_asks(st):
            # S21: 「부탁을 하나 하셨습니다」는 그날 열린 물음이 있을 때만. 없으면 star_no_ask(시나리오) → 서버 대체 줄
            star = d.get("star_no_ask") or "관리실에서 알려 드립니다. 문간 유리를 누가 두 번 두드렸습니다. 오늘은 그게 전부입니다."
            use_alt = True
        rep = lambda t: (t or "").replace("{oct_name}", oc.get("name") or "문어").replace("{spot}", spot_name or "그곳")
        out = {"play_day": p, "beat": d.get("beat"), "star": rep(star), "teaser": rep(d.get("teaser")), "alt": use_alt,
               "big": True}
        if d.get("beat") in ("weekly_log_shade", "second_log_far_cry_page"):
            out["weekly_log"] = weekly_log(st, uid)
        if d.get("first_session_scene"):
            out["first_session_scene"] = d["first_session_scene"]      # S25 5일째 원정 첫 장면(J3 문턱)
        return out
    # 15일째부터
    if p % 14 == 0:
        return {"play_day": p, "beat": "fortnight_log", "star": (BEATS.get("14") or {}).get("star"),
                "teaser": (BEATS.get("14") or {}).get("teaser"), "alt": False, "big": True, "weekly_log": weekly_log(st, uid)}
    if p % 7 == 0:
        return {"play_day": p, "beat": "weekly_log", "star": (BEATS.get("7") or {}).get("star"),
                "teaser": (BEATS.get("7") or {}).get("teaser"), "alt": False, "big": True, "weekly_log": weekly_log(st, uid)}
    prev = (core_of(st)["beats"].get("kinds") or {}).get(str(p - 1))
    cands = []
    for r in st.get("residents_list") or []:
        a, s = current_arc(st, r)
        beat = next_beat(a, s) if a else None
        if beat and beat_open(st, r, s, beat):
            cands.append(("daily_arc", fill_text(random.Random(f"{uid}|{p}|nva").choice((NEXT_VISIT.get("promises") or {}).get("arc_beat_ready") or ["{name} 님 쪽에서 작은 일이 하나 생길 것 같습니다."]), st, r)))
            break
    vrows = [v for v in (core_of(st)["visits"].get("rows") or []) if v.get("kind") == "visitor"]
    if vrows:
        cands.append(("daily_visitor", vrows[0].get("line")))
    unseen = [cid for cid, cr in combat.CREATURES.items() if not cr.get("threat") and cid not in encounters_of(st)]
    if oc:
        cands.append(("daily_octopus", f"{oc.get('name') or '문어'}, 오늘은 무언가를 오래 들여다보고 있습니다."))
    cands = [x for x in cands if x[0] != prev] or cands
    kind, star = cands[0] if cands else ("daily_quiet", moment("morning.nothing"))
    core_of(st)["beats"].setdefault("kinds", {})[str(p)] = kind
    return {"play_day": p, "beat": kind, "star": star, "teaser": None, "alt": False, "big": False,
            "unseen_creatures": len(unseen)}


def beat_public(st: dict, uid: str) -> dict | None:
    """오늘 비트 + 세션당 큰 창 2개. 안 보인(밀린) 비트가 있으면 그것부터(켠 날 차례)."""
    b = core_of(st)["beats"]
    p = play_day(st)
    if p <= 0:
        return None
    if FIRST_ENTRY_GATE and p == 1 and beat_today_id(st) == "first_scan" and not core_of(st)["scans"]:
        return None                                   # PM 첫 세션: 「처음으로 바깥 물건이 들어왔습니다」는 첫 스캔 뒤에
    shown = b.setdefault("shown", {})
    unseen = [q for q in range(max(1, p - 3), p + 1) if not shown.get(str(q))]
    cur = beat_compose(st, uid, p)
    cur["new"] = False
    cur["queued"] = max(0, len(unseen) - 1)
    ss = core_of(st)["session"]
    if unseen and ss.get("shown_beat_session") != ss.get("n"):
        q = unseen[0]
        if not beat_compose(st, uid, q).get("big") or big_take(st):
            shown[str(q)] = True
            ss["shown_beat_session"] = ss.get("n")
            if q != p:
                old = beat_compose(st, uid, q)
                old.update({"new": True, "queued": max(0, len(unseen) - 1), "late": True})
                return old
            cur["new"] = True
            cur["queued"] = max(0, len(unseen) - 1)
    return cur


def beat_force_tick(st: dict, uid: str) -> None:
    """비트가 '운 대신 차례'로 내보내는 것들(이미 있는 콘텐츠). 나쁜 일은 등급 1 보호 안에서만."""
    c = core_of(st)
    bid = beat_today_id(st)
    p = play_day(st)
    if bid == "rescue_second_resident_goal" and not c["flags"].get("rescue_done"):
        c["flags"]["rescue_due"] = True
    # 1주차 단서 하나 보장(새 문제 2): 켠 날 5 이상인데 단서도 발견도 없으면 반나절로 갈 수 있는 곳 하나
    if p >= 5 and not (st.get("spots_found")) and not any(spot_state(st, uid, s) == "clue" for s in DEEP_SPOT_IDS):
        sid = week1_clue_spot(st)
        if sid and sid not in (st.get("clues_extra") or []):
            st.setdefault("clues_extra", []).append(sid)
            nm = next((x.get("name") for x in SPOTS if x.get("id") == sid), sid)
            overnight_add(st, "clue", {"spot_id": sid, "name": nm,
                                       "line": f"문어가 물어 온 것에 「{nm}」 쪽 냄새가 묻어 있었습니다. 단서 하나가 생겼습니다."})


def week1_clue_spot(st: dict) -> str | None:
    """반나절로 갈 수 있고 지금 깊이에서 열리는 단서 스팟 중 첫째(min_base_depth_m 작은 순)."""
    sp = (EX.g("destinations.spots") or {})
    ids = [s for s in DEEP_SPOT_IDS if isinstance(sp.get(s), dict) and depth_of(st) >= int(sp[s].get("min_base_depth_m", 0))]
    ids.sort(key=lambda s: (LEN_ORDER.index(sp[s].get("min_length", "half")) if sp[s].get("min_length") in LEN_ORDER else 1,
                            int(sp[s].get("min_base_depth_m", 0)), s))
    return ids[0] if ids else None


def week1_half_ok(st: dict, uid: str, sid: str) -> bool:
    """첫 발견 전·켠 날 10 이하에는 지금 가진 단서 하나를 반나절로도 갈 수 있다(밤 넘기기·에어락 없이)."""
    if st.get("spots_found") or play_day(st) > 10:
        return False
    clues = [s for s in DEEP_SPOT_IDS if spot_state(st, uid, s) == "clue"]
    sp = (EX.g("destinations.spots") or {})
    clues = [s for s in clues if depth_of(st) >= int((sp.get(s) or {}).get("min_base_depth_m", 0))]
    return bool(clues) and sid == clues[0]


# ── 떠날 때 카드 ────────────────────────────────────────────────
def clock_ko(ts: float) -> str:
    t = datetime.fromtimestamp(ts)
    h = t.hour
    return f"{'오전' if h < 12 else '오후'} {h % 12 or 12}:{t.minute:02d}"


def next_visit_public(st: dict, uid: str) -> dict:
    """S20: 지킬 수 있는 약속을 모두 모아 가장 설레는 것부터(귀환 > 매듭 > 손님 > 방문자 > 상자 > 모자람).
    지난 세션과 같은 문장이면, 다른 약속이 있을 때 그다음 것을 쓴다. 같은 세션 안에서는 같은 약속."""
    c = core_of(st)
    ss = c["session"]
    cands = next_visit_candidates(st, uid)
    memo = c.setdefault("nv", {})
    if memo.get("session") == ss.get("n") and memo.get("cur"):
        cur = next((x for x in cands if x["kind"] == memo["cur"]["kind"] and x["line"] == memo["cur"]["line"]), None)
        if cur and NV_ORDER.index(cands[0]["kind"]) >= NV_ORDER.index(cur["kind"]):
            return cur                                # 더 설레는 약속이 새로 생기면 같은 세션이라도 그쪽으로
    last = (memo.get("prev") or {}).get("line") if memo.get("session") == ss.get("n") else (memo.get("cur") or {}).get("line")
    pick = next((x for x in cands if x["line"] != last), cands[0])
    if memo.get("session") != ss.get("n"):
        memo["prev"] = memo.get("cur")
    memo.update({"session": ss.get("n"), "cur": {"kind": pick["kind"], "line": pick["line"]}})
    return pick


NV_ORDER = ("expedition_return", "arc_beat_ready", "guest_at_door", "visitor_expected", "box_key_hint", "need_tomorrow", "nothing")


def next_visit_candidates(st: dict, uid: str) -> list:
    out = []
    for kind in NV_ORDER:
        for row in _nv_kind(st, uid, kind):
            out.append(row)
    return out


def _nv_kind(st: dict, uid: str, kind: str) -> list:
    P = NEXT_VISIT.get("promises") or {}
    card = NEXT_VISIT.get("card") or {}
    day = day_of(st)
    rng = random.Random(f"{uid}|{day}|{core_of(st)['session'].get('n')}|next_visit|{kind}")
    want = kind

    def pick(kind, **kw):
        lines = P.get(kind) or []
        t = rng.choice(lines) if lines else ""
        for k, v in kw.items():
            t = t.replace("{" + k + "}", str(v))
        return t

    rows = _nv_rows(st, uid, pick, card, day)
    return [x for x in rows if x["kind"] == want]


def _nv_rows(st: dict, uid: str, pick, card: dict, day: int) -> list:
    rows = []
    ex = st.get("expedition")
    by = {r["id"]: r for r in st.get("residents_list") or []}
    if ex:
        names = "·".join(by[m]["name"] for m in ex.get("members") or [] if m in by) or "원정대"
        rows.append({"kind": "expedition_return", "title": card.get("title"),
                "line": pick("expedition_return", name=names, return_at=clock_ko(float(ex["returns_at"]))),
                "data": {"return_at": ex["returns_at"]}})

    if st.get("guests"):
        rows.append({"kind": "guest_at_door", "title": card.get("title"), "line": pick("guest_at_door"),
                "data": {"guests": len(st["guests"])}})

    c = core_of(st)
    for d in c["deferred"]:
        r = by.get(d.get("rid"))
        if r:
            rows.append({"kind": "arc_beat_ready", "title": card.get("title"), "line": pick("arc_beat_ready", name=r["name"]),
                    "data": {"resident_id": r["id"], "arc_id": d.get("arc")}})

    for r in st.get("residents_list") or []:
        a, s = current_arc(st, r)
        beat = next_beat(a, s) if a else None
        if a and s.get("ask_pending") and str(s["ask_pending"]) not in (s.get("asks") or {}):
            rows.append({"kind": "arc_beat_ready", "title": card.get("title"), "line": pick("arc_beat_ready", name=r["name"]),
                         "data": {"resident_id": r["id"], "arc_id": a["id"], "ask_step": s["ask_pending"]}})
            continue
        if beat and trig_needs_give(beat.get("trigger") or {}) and beat_open(st, r, s, beat, day + 1) \
                and arc_item_at_home(st, uid, r, beat):       # S21: 집에 맞는 물건이 있을 때만 약속한다
            rows.append({"kind": "arc_beat_ready", "title": card.get("title"), "line": pick("arc_beat_ready", name=r["name"]),
                    "data": {"resident_id": r["id"], "arc_id": a["id"], "hint_ko": (arc_status(st, uid, r) or {}).get("next", {}).get("hint_ko")}})

    if st.get("boxes"):
        b = st["boxes"][0]
        rows.append({"kind": "box_key_hint", "title": card.get("title"),
                "line": pick("box_key_hint", pattern=box_pattern(b["cat"]) or "무늬"), "data": {"box_id": b["id"], "cat": b["cat"]}})

    for v in visit_rows_for(st, uid, day + 1):                # 내일 굴림을 미리 본다(시드 고정 — 지킬 수 있는 약속만)
        if v.get("kind") == "visitor":
            first_v = v.get("visitor_id") not in core_of(st)["visitors_seen"]
            rows.append({"kind": "visitor_expected", "title": card.get("title"),
                    "line": (pick("visitor_expected_first", room=v.get("room"), visitor=v.get("ko"))
                             or f"{v.get('room')} 창밖으로 {v.get('ko')} 손님이 처음 올 것 같습니다.") if first_v
                            else pick("visitor_expected", room=v.get("room"), visitor=v.get("ko")),
                    "data": {"slot": v.get("slot"), "visitor_id": v.get("visitor_id")}})

    low = sorted(("food", "water", "parts", "cloth"), key=lambda k: int(st["resources"].get(k, 0)))[0]
    if int(st["resources"].get(low, 0)) < 5:
        rows.append({"kind": "need_tomorrow", "title": card.get("title"), "line": pick("need_tomorrow", need=RES_KO_SRV.get(low, low)),
                "data": {"res": low}})

    rows.append({"kind": "nothing", "title": card.get("title"), "line": pick("nothing"), "data": {}})
    return rows


def core_tick(st: dict, uid: str) -> dict:
    """GET /api/ark 마다(day_tick 뒤). 세션 → 켠 날 → 비트 강제 → 방문 → 사슬 → 아침 줄 → 자동 선반."""
    ss = session_tick(st)
    beat_play_tick(st)
    beat_force_tick(st, uid)
    visits = visit_tick(st, uid)
    visits = list(visits or []) + force_first_visit(st, uid, ss)
    if needs_today_public(st, uid) and (core_of(st).get("needs_shown") or {}).get("day") != day_of(st):
        core_of(st)["needs_shown"] = {"day": day_of(st), "at": time.time()}    # S22 의도: 오늘 필요를 처음 보여 준 시각
    food_all_tick(st)
    arcs = arc_tick(st, uid)
    morning_core(st, uid)
    moved = shelf_autofill(st)
    nov = novelty_tick(st, uid, visits, arcs)
    gossip_tick(st, uid, ss)
    night_visitor_tick(st, uid)
    return {"session": ss, "visits": visits, "arcs": arcs, "autofill": moved, "novelty": nov}


def migrate_s19(st: dict, uid: str) -> bool:
    """옛 바람(wishes_done)은 그 역할 사슬을 끝낸 것으로 옮긴다(되돌아가지 않게). 자원 줄의 free_pack 은 상자로."""
    changed = False
    if not st.get("s19_migrated"):
        core_of(st)
        for wid, d in (st.get("wishes_done") or {}).items():
            a = next((x for x in ARCS if x.get("wish_id") == wid), None)
            rid = (d or {}).get("resident_id")
            if a and rid:
                s = arc_state(st, rid, a["id"])
                s.update({"step": len(a["beats"]), "done": True, "done_day": (d or {}).get("day"), "migrated": True})
        st["s19_migrated"] = True
        changed = True
    n = int((st.get("resources") or {}).pop("free_pack", 0) or 0)
    for i in range(n):
        box_new(st, "blank", "event", f"{uid}|free_pack|{i}|{int(time.time())}")
        changed = True
    return changed


def shelf_autofill(st: dict) -> list:
    """선반 칸이 늘면 창고 상자에서 저절로 올라온다(닦은 것·귀한 것 먼저). 물 찬 방에서 온 꾸밈 물건은 기다린다."""
    moved = []
    if not st.get("stored") or not shelf_capacity(st):
        return moved
    order = sorted([x for x in st["stored"] if x.get("from_slot") is None],
                   key=lambda it: (-polish_level(it), -(RARITY_KEYS.index(it.get("rarity")) if it.get("rarity") in RARITY_KEYS else 0),
                                   float(it.get("scanned_at") or 0)))
    for it in order:
        if shelf_try_put(st, it) is None:
            continue
        st["stored"] = [x for x in st["stored"] if x is not it]
        moved.append(it.get("relic_name") or it.get("name"))
    return moved


# ── API ───────────────────────────────────────────────────────
class GiveIn(BaseModel):
    uid: str
    scan_id: str | None = None
    relic_id: str | None = None
    target: dict | str | None = "shelf"


@app.post("/api/give")
def give(inp: GiveIn):
    st = load_state(inp.uid)
    tick_production(st)
    c = core_of(st)
    day = day_of(st)
    placed = None
    p = c["scans"].get(inp.scan_id) if inp.scan_id else None
    if inp.scan_id and (not p or int(p.get("day") or 0) < day - 1):
        # S21 버그 1: 기록이 없어도 그 스캔이 선반·창고 상자에 있으면(scan_id = card_id) 그 물건으로 준다
        row = next((x for x in st.get("shelf") or [] if x.get("card_id") == inp.scan_id), None) or \
            next((x for x in st.get("stored") or [] if x.get("id") == inp.scan_id or x.get("card_id") == inp.scan_id), None)
        if not row:
            raise HTTPException(400, "그 물건을 찾을 수 없습니다")
        it_ = item_from_row(row)
        it_["card_id"] = inp.scan_id
        p = c["scans"][inp.scan_id] = {"item": it_, "day": day, "given": False, "placed": "shelf", "recovered": True}
    if inp.scan_id:
        if p.get("given"):
            raise HTTPException(400, "이미 자리를 정한 물건입니다")
        item = dict(p["item"])
        placed = p.get("placed")
    elif inp.relic_id:
        row = next((x for x in st.get("shelf") or [] if x.get("card_id") == inp.relic_id), None) or \
            next((x for x in st.get("stored") or [] if x.get("id") == inp.relic_id or x.get("card_id") == inp.relic_id), None)
        if not row:
            raise HTTPException(400, "선반·창고 상자에 그런 물건이 없습니다")
        item = item_from_row(row)
        item["card_id"] = inp.relic_id
        placed = "shelf"
    else:
        raise HTTPException(400, "scan_id 나 relic_id 가 필요합니다")
    warm_ids = (c["scans"].get(inp.scan_id) or {}).get("warm") if inp.scan_id else None
    if warm_ids is None:
        warm_ids = list(where_for(st, inp.uid, item).get("warm_ids") or [])   # S22 r4-2: 선반 물건도 「어디로」가 제안한 그대로
    target = inp.target if inp.target not in ("keep",) else "shelf"
    if isinstance(target, dict) and target.get("heirloom"):
        if any(o.get("near") and o["target"]["resident_id"] == target.get("resident_id") for o in heirloom_options(st, inp.uid, item)):
            warm_ids = list(warm_ids or []) + [target["resident_id"]]   # S29: 「다른 분도」로 보인 사람은 반가워한다(돌려주지 않는다)
        hp = heirloom_prepare(st, inp.uid, item, target)       # S25 가보: 바꿀까요? 물음이면 아무것도 바꾸지 않고 돌려준다
        if hp.get("ask_swap"):
            return {"ok": False, "ask_swap": hp["ask_swap"], "state": None}
    nb_before = notebook_before(st, inp.uid, item, target)
    out = give_apply(st, inp.uid, item, target, placed, warm_ids=warm_ids)
    out["intent"] = give_intent(st, inp.uid, c["scans"].get(inp.scan_id) if inp.scan_id else None, item, target, out)
    out["revealed"] = notebook_record(st, inp.uid, item, target, out, nb_before)
    if isinstance(target, dict) and target.get("heirloom"):
        if out.get("tier") == "not_for_me":            # S27 r5-2: 돌려받았으면 가보가 되지 않는다 — 결과는 한 줄(돌려받음)
            out["heirloom"] = None
            out["heirloom_refused"] = True
        else:
            out["heirloom"] = heirloom_place(st, inp.uid, item, target, out)
    out["repeat"] = repeat_line(st, inp.uid, item, target, out)
    if out["tier"] != "not_for_me" and target != "shelf":
        og = (st.get("octopus") or {}).get("gift_relic")
        if og and og.get("card_id") == item.get("card_id"):
            og["given"] = True                              # S22 r4-2: 문어 조각은 한 번 건네면 끝
    if inp.scan_id:
        c["scans"][inp.scan_id]["given"] = True
        c["scans"][inp.scan_id]["to"] = target
    save_state(inp.uid, st)
    out["ok"] = True
    out["item"] = {k: item.get(k) for k in ("name", "category", "subtype")} | {"subtype_ko": sub_ko(item.get("category", ""), item.get("subtype")) if item.get("subtype") else None,
                                                                              "history": card_history(st, item.get("barcode"))}
    out["state"] = public_state(st, inp.uid)
    return out


class DecorRemoveIn(BaseModel):
    uid: str
    slot: int
    item_id: str


@app.post("/api/decor/remove")
def decor_remove(inp: DecorRemoveIn):
    st = load_state(inp.uid)
    room = core_of(st)["rooms"].get(str(inp.slot)) or {}
    it = next((x for x in room.get("items") or [] if x.get("id") == inp.item_id), None)
    if not it:
        raise HTTPException(400, "그 방에 그런 물건이 없습니다")
    room["items"] = [x for x in room["items"] if x is not it]
    row = it.get("row") or {k: it.get(k) for k in ("name", "category", "rarity", "barcode", "card_id", "prop_id")}
    if not row.get("prop_id"):
        pool = _PROPS.get(it.get("category") or "unknown") or _PROPS.get("unknown") or [{}]
        row["prop_id"] = (pool[0] or {}).get("id")
        row["relic_name"] = row.get("relic_name") or it.get("name")
    where = return_to_shelf(st, row)
    save_state(inp.uid, st)
    return {"ok": True, "back_to": where, "state": public_state(st, inp.uid)}


class ArcAskIn(BaseModel):
    uid: str
    arc_id: str
    step: int
    choice: str | None = None
    relic_id: str | None = None
    resident_ids: list[str] | None = None
    skip: bool = False                     # S21: 물건 고르기를 넘김(답별 뒷말 "skip")


@app.post("/api/arc/ask")
def arc_ask(inp: ArcAskIn):
    st = load_state(inp.uid)
    a = ARC_BY_ID.get(inp.arc_id)
    if not a:
        raise HTTPException(400, "없는 사슬입니다")
    r, s = None, None
    for x in st.get("residents_list") or []:
        if x.get("role") == a.get("role"):
            s_ = arc_state(st, x["id"], a["id"])
            if int(s_.get("ask_pending") or 0) == int(inp.step):
                r, s = x, s_
                break
    if not r:
        raise HTTPException(400, "지금 묻는 것이 없습니다")
    beat = next((b for b in a["beats"] if int(b.get("step", 0)) == int(inp.step)), None)
    ask = (beat or {}).get("ask") or {}
    kind = ask.get("kind")
    applied, item = {}, None
    answer = "done"
    if inp.skip and kind in ("give", "place", "pick_residents"):
        s["asks"][str(inp.step)] = {"skipped": True}
        answer = "skip"
    elif kind == "choice":
        if inp.choice not in (ask.get("options") or []):
            raise HTTPException(400, "고를 수 있는 것이 아닙니다")
        s["asks"][str(inp.step)] = {"choice": inp.choice}
        answer = inp.choice
    elif kind == "pick_residents":
        ids = [i for i in inp.resident_ids or [] if any(x["id"] == i for x in st.get("residents_list") or [])]
        if len(set(ids)) != int(ask.get("n", 2)):
            raise HTTPException(400, f"{int(ask.get('n', 2))}명을 골라 주세요")
        s["asks"][str(inp.step)] = {"resident_ids": ids}
        s["asks"]["pick_residents"] = {"resident_ids": ids}
    elif kind in ("give", "place"):
        row = next((x for x in st.get("shelf") or [] if x.get("card_id") == inp.relic_id), None) or \
            next((x for x in st.get("stored") or [] if x.get("id") == inp.relic_id), None)
        if not row:
            raise HTTPException(400, "선반·창고 상자에 그런 물건이 없습니다")
        item = item_from_row(row)
        item["card_id"] = inp.relic_id
        if ask.get("category") and not match({"category": ask["category"], "subtype": ask.get("subtype")}, item):
            raise HTTPException(400, "그 물건은 맞지 않습니다")
        if kind == "give":
            applied = give_apply(st, inp.uid, item, {"resident_id": r["id"]}, "shelf")
        else:
            rm = next((x for x in live_rooms(st) if x["id"] == ask.get("room")), None)
            if rm and len(decor_items(st, rm["slot"])) < decor_cap(rm):
                applied = give_apply(st, inp.uid, item, {"slot": rm["slot"]}, "shelf")
        s["asks"][str(inp.step)] = {"relic_id": inp.relic_id, "item": item.get("name")}
    else:
        raise HTTPException(400, "묻는 종류를 모릅니다")
    s.pop("ask_pending", None)
    save_state(inp.uid, st)
    aa = beat.get("after_ask")
    if isinstance(aa, dict):
        aa = aa.get(answer) or aa.get("_default")
    ko = fill_text(aa, st, r, item, arc_other(st, r, s, beat)) or \
        fill_text(moment("arc.after_ask_default") or "알겠습니다. {name} 님께 그대로 전해 드렸습니다.", st, r, item)
    return {"ok": True, "arc_id": a["id"], "step": inp.step, "answer": answer, "applied": applied or None,
            "after_ask_ko": ko, "state": public_state(st, inp.uid)}


class FeastIn(BaseModel):
    uid: str
    pair: list[str]


FEAST = (S19N.get("feast") or {})
FEAST_COST = {k: int(v) for k, v in (FEAST.get("cost") or {"food": 24, "water": 12}).items()}


@app.post("/api/feast")
def feast(inp: FeastIn):
    st = load_state(inp.uid)
    tick_production(st)
    day = day_of(st)
    c = core_of(st)
    by = {r["id"]: r for r in st.get("residents_list") or []}
    if len(set(inp.pair)) != 2 or any(p not in by for p in inp.pair):
        raise HTTPException(400, "마주 앉을 두 분을 골라 주세요")
    if max(play_day(st), 0) < int(FEAST.get("unlock_day", 10)) and day < int(FEAST.get("unlock_day", 10)):
        raise HTTPException(400, f"잔치는 {int(FEAST.get('unlock_day', 10))}일째부터 열 수 있습니다")
    last = c["flags"].get("feast_day")
    if last is not None and day - int(last) < int(FEAST.get("cooldown_days", 7)):
        raise HTTPException(400, f"잔치는 {int(FEAST.get('cooldown_days', 7))}일에 한 번입니다")
    lack = {k: v - int(st["resources"].get(k, 0)) for k, v in FEAST_COST.items() if int(st["resources"].get(k, 0)) < v}
    if lack:
        raise HTTPException(400, "모자랍니다: " + " · ".join(f"{RES_KO_SRV.get(k, k)} {v}" for k, v in lack.items()))
    for k, v in FEAST_COST.items():
        st["resources"][k] -= v
    a, b = (by[x] for x in inp.pair)
    tr = int(FEAST.get("trust_all_present", 5))
    present = [r for r in st.get("residents_list") or [] if r["id"] not in (st.get("outside") or [])]
    for x in present:                                  # S20: 그 자리에 있던 모두가 서로 신뢰 +5
        for y in present:
            if x is not y:
                x.setdefault("trust", {})[y["id"]] = min(TRUST_MAX, int(x["trust"].get(y["id"], 0)) + tr)
    morale_add(st, float(FEAST.get("morale_all", 3)))
    c["flags"]["feast_day"] = day
    line = f"어젯밤 잔치에서 {a['name']} 님과 {b['name']} 님이 마주 앉으셨습니다. 그릇은 둘 다 비었습니다."
    c["morning_next"].append({"day": day + 1, "kind": "feast", "text": line})
    session_note(st, f"잔치 — {a['name']}·{b['name']}")
    day_note(st, "feast", f"{a['name']}·{b['name']}")
    save_state(inp.uid, st)
    log(inp.uid, "feast", {"pair": inp.pair})
    return {"ok": True, "paid": FEAST_COST, "morale": int(FEAST.get("morale_all", 3)), "trust": tr,
            "present": [r["id"] for r in present], "line": line, "state": public_state(st, inp.uid)}


@app.get("/api/leaving")
def leaving(uid: str):
    st = load_state(uid)
    ss = core_of(st)["session"]
    ch = [x for x in (ss.get("changes") or []) if x][-2:]
    if not ch:
        note = (st.get("day_log") or {}).get(str(day_of(st))) or {}
        ch = [f"{k} {', '.join(map(str, v[:2]))}" for k, v in note.items() if isinstance(v, list)][:2]
    card = NEXT_VISIT.get("card") or {}
    mc = missed_chain_of(st, uid)
    save_state(uid, st)
    nv, ta, order = leave_lines(st, uid)
    return {"title": card.get("changed_title"), "changed": ch, "next_visit": nv,
            "missed_chain": mc, "tomorrow_ask": ta, "unlock_teaser": unlock_teaser(st),
            "order": [k for k in order if k != "missed_chain" or mc],
            "close_label": card.get("close_label")}




def need_bonus_mult(st: dict, room: dict) -> float:
    m = 1.0
    nb = ((st.get("core") or {}).get("need_bonus") or {}).get(str(room.get("slot")))
    if nb is not None and int(nb) == day_of(st):
        m *= 1.0 + float((GIVE_EFFECTS.get("need") or {}).get("room_output_bonus_today", 0.1))
    vb = ((st.get("core") or {}).get("visit_bonus") or {}).get(str(room.get("slot")))
    if vb is not None and int(vb) == day_of(st):
        m *= 1.1                                      # S20 아기 해파리 떼: 그날 그 방 +10%(core_a visitor_effects)
    return m


def short_of_word(st: dict, raid: dict, cre: dict, ready: dict) -> str | None:
    """단서 모드에서 관문은 맞는데 점수가 모자라면 모자란 갈래를 한 단어로(손/눈/숨/담/도구/불). 답은 말하지 않는다."""
    if not ready or not (ready.get("gate") or {}).get("ok") or ready.get("would") in ("held", "passed"):
        return None
    slot = raid.get("target_slot")
    ppl = stations_map(st).get(int(slot), []) if slot is not None else []
    rm = room_at(st, slot) if slot is not None else None
    if not ppl or len(ppl) < min(2, room_cap_of(rm) if rm else 2):
        return "손"
    if any(p.get("injured") for p in ppl):
        return "숨"
    owned = {t for t, n in (st.get("tools") or {}).items() if int(n) > 0}
    if not installed_at(st, slot) and (owned or any(r["id"] == "workshop" for r in live_rooms(st))):
        return "도구"
    if min(int((p.get("stats") or {}).get("nerve", 5)) for p in ppl) < 6:
        return "담"
    if not light_on(st, slot):
        return "불"
    return "눈"


def rescan_low_line(st: dict) -> tuple[str | None, str | None]:
    """ui_moments shelf.rescan_low[] 를 돌려 쓴다(값 낮은 재스캔 반응이 한 문장만 되풀이되던 것)."""
    lines = ((moments().get("shelf") or {}).get("rescan_low")) or []
    if not lines:
        return None, None
    c = core_of(st)
    i = int(c["flags"].get("rescan_low_i") or 0)
    c["flags"]["rescan_low_i"] = i + 1
    return lines[i % len(lines)], f"shelf.rescan_low.{i % len(lines)}"


def exp_request_hint(st: dict, uid: str, ex: dict) -> dict | None:
    """원정은 부탁 단서를 가져온다(CORE_LOOP_A §5): 내일 누가 무엇을 찾을지 한 줄 — 시드가 정해 둔 진짜 내일 필요다."""
    ppl = [r for r in st.get("residents_list") or [] if r["id"] not in (ex.get("members") or [])] or list(st.get("residents_list") or [])
    if not ppl:
        return None
    day = day_of(st)
    r = random.Random(f"{uid}|{ex.get('id')}|hint").choice(ppl)
    nd = need_today(uid, r, day + 1)
    if not nd:
        return None
    return {"resident_id": r["id"], "name": r["name"], "day": day + 1, "need": nd,
            "ko": f"돌아오는 길에 들었습니다. {r['name']} 님이 내일은 「{nd['ko']}」 쪽 물건을 찾으실 것 같답니다."}

# ── S19(PM 추가) 각인: 드물고 무겁게 · 사슬 끝 개인 각인 · 성장이 결과에 보이게 ─────────────
ARC_IMPRINTS = {i["id"]: i for i in (_live_or_draft("imprints_arcs.json").get("imprints") or [])
                if isinstance(i, dict) and i.get("id")}
NEAR_MARGIN = float(S19N.get("near_margin", 1.0))      # 습격 여유(score − need)가 이보다 작으면 '아슬아슬'(core_a)
for _iid, _v in (((CORE_A.get("arc_imprints") or {}).get("values")) or {}).items():   # S20 수치는 core_a 가 이긴다(런타임 병합)
    if _iid in ARC_IMPRINTS and isinstance(_v, dict):
        if isinstance(_v.get("effect"), dict):
            ARC_IMPRINTS[_iid]["effect"] = dict(_v["effect"])
        if isinstance(_v.get("cost"), dict):
            ARC_IMPRINTS[_iid].setdefault("cost", {})
            ARC_IMPRINTS[_iid]["cost"] = dict(ARC_IMPRINTS[_iid]["cost"], effect=dict(_v["cost"]))


def close_call_flags(flags: list, out: dict, injured) -> list:
    """원정 각인 flag 중 아슬아슬한 것만 남긴다: 숨이 떨어짐(air_survived), 위험에 지거나 다쳐서 돌아옴(beast_left).
    발견·깊이 첫 방문처럼 위기가 아닌 것은 각인이 아니라 일지·발견 연출로 남는다."""
    d = out.get("danger") or {}
    close = bool(injured) or d.get("ok") is False
    return [f for f in flags or [] if f == "air_survived" or (f == "beast_left" and close)]


def grant_personal_imprint(st: dict, r: dict, a: dict) -> dict | None:
    """사슬을 이룬 사람의 개인 각인(arcs 의 imprint_on_done). 위기 각인과 따로 센다 — evolve_at·max_per_resident 밖(PM 결정)."""
    spec_in = a.get("imprint_on_done")
    iid = spec_in.get("id") if isinstance(spec_in, dict) else spec_in
    if not iid:
        return None
    spec = ARC_IMPRINTS.get(iid) or (spec_in if isinstance(spec_in, dict) else {})
    pi = r.setdefault("personal_imprints", [])
    if iid in pi:
        return None
    gd = st.setdefault("imprint_days", {}).get(iid)
    if gd and int(gd.get("day") or 0) == day_of(st) and gd.get("rid") != r["id"]:
        return None
    pi.append(iid)
    st["imprint_days"][iid] = {"day": day_of(st), "rid": r["id"]}
    vis = spec.get("visual") or {}
    line = (vis.get("line") or spec.get("line") or (spec_in or {}).get("line") or "").replace("{name}", r["name"])
    day_note(st, "imprint", {"name": r["name"], "src": "arc", "imprint": iid})
    st.setdefault("morning_pending", []).append({
        "day": day_of(st) + 1, "resident": r["name"], "resident_id": r["id"], "imprint_id": iid,
        "imprint_name": spec.get("name"), "visual": vis.get("ko") or spec.get("mark_ko"), "line": line,
        "evolved": False, "personal": True})
    return {"id": iid, "name": spec.get("name"), "personal": True, "visual": vis.get("ko") or spec.get("mark_ko"),
            "ability_ko": spec.get("ability_ko"), "cost": (spec.get("cost") or {}).get("ko") or spec.get("cost_ko"),
            "line": line, "resident_id": r["id"], "resident": r["name"]}


def credit_line(name: str, imp_name: str, seed: str) -> tuple[str, str]:
    lines = moments().get("imprint_credit")
    if isinstance(lines, dict):
        lines = lines.get("lines") or [v for k, v in lines.items() if not str(k).startswith("_") and isinstance(v, str)]
    if isinstance(lines, str):
        lines = [lines]
    if not lines:
        return f"{name} 님의 「{imp_name}」 덕분입니다.", "imprint_credit"
    i = random.Random(seed).randrange(len(lines))
    return str(lines[i]).replace("{name}", name).replace("{imprint}", imp_name), f"imprint_credit.{i}"


def imprint_credit_parts(st: dict, parts: list | None, seed: str) -> list:
    """습격 판정에서 각인이 실제로 점수를 보탰으면(엔진 parts 의 「이름 · 刻 id」) 그 사람·각인을 한 줄로."""
    out = []
    for p in parts or []:
        ko = str(p.get("ko") or "")
        if "刻 " not in ko or not float(p.get("v") or 0):
            continue
        head, iid = ko.rsplit("刻 ", 1)
        iid = iid.strip()
        nm = head.split(" · ")[0].strip()
        imp = IMPRINTS.get(iid) or ARC_IMPRINTS.get(iid) or {}
        txt, key = credit_line(nm, imp.get("name") or "각인", f"{seed}|{iid}")
        out.append({"key": key, "name": nm, "imprint_id": iid, "imprint": imp.get("name"), "ko": txt, "v": p.get("v")})
    return out


def imprint_credit_event(st: dict, ev: dict, how: str, hero: dict | None) -> list:
    """역할 자동 대항이 각인의 counter_bonus 덕을 봤으면(그 태그) 그 사람의 각인을 한 줄로."""
    if how != "role" or not hero:
        return []
    tags = set(ev.get("counter_tags") or [])
    out = []
    for iid in list(hero.get("imprints") or []) + list(hero.get("personal_imprints") or []):
        imp = IMPRINTS.get(iid) or ARC_IMPRINTS.get(iid) or {}
        cb = (imp.get("effect") or {}).get("counter_bonus") or {}
        if set(cb) & tags:
            txt, key = credit_line(hero["name"], imp.get("name") or "각인", f"{ev.get('id')}|{iid}")
            out.append({"key": key, "name": hero["name"], "imprint_id": iid, "imprint": imp.get("name"), "ko": txt})
    return out


# ── S20 장식 손님 효과(core_a visitor_effects) · 모두의 하루 식량(food_daily_all) ─────────────
def visitor_apply(st: dict, uid: str, v: dict) -> dict | None:
    """손님이 온 날 한 번(visit_tick 이 하루 한 번만 부른다). 효과는 아주 작게 — 그림·한 줄이 주인공."""
    c = core_of(st)
    day = day_of(st)
    vid, slot = v.get("visitor_id"), v.get("slot")
    res = st["resources"]
    if vid == "lantern_fish_pair":
        res["power"] = int(res.get("power", 0)) + 1           # 조명 전력 점유 −1 = 그날 전력 1 덜 씀
        return {"power": 1}
    if vid == "page_shrimp":
        res["knowledge"] = int(res.get("knowledge", 0)) + 1    # 해독실 기록 +1
        return {"knowledge": 1}
    if vid == "steam_eel":
        res["food"] = max(0, int(res.get("food", 0)) - 1)
        morale_add(st, 0.5)
        return {"food": -1, "morale": 0.5}
    if vid == "baby_jelly_drift":
        c.setdefault("visit_bonus", {})[str(slot)] = day
        return {"room_pct": 10, "slot": slot}
    if vid == "glass_star":
        rm = room_at(st, slot)
        if rm and rm.get("cracked"):
            c.setdefault("repair_discount", {})[str(slot)] = day
            return {"repair_discount": 1, "slot": slot}
        return None
    if vid == "screw_crab":
        last = c["flags"].get("screw_crab_day")
        if last is None or day - int(last) >= 3:
            res["parts"] = int(res.get("parts", 0)) + 1
            c["flags"]["screw_crab_day"] = day
            return {"parts": 1}
        return None
    if vid == "blanket_crab":
        n = len(stations_map(st).get(int(slot), [])) if slot is not None else 0
        if n:
            c["flags"]["blanket_morning"] = {"day": day + 1, "morale": round(0.3 * n, 3)}
            return {"next_morning_morale": round(0.3 * n, 3)}
        return None
    if vid == "hermit_trader":
        items = [it for it in decor_items(st, slot) if not it.get("boxed")]
        if not items:
            return None
        it = random.Random(f"{uid}|{day}|hermit").choice(items)
        cats = [x for x in EX.CATS if x != it.get("category")]
        nc = random.Random(f"{uid}|{day}|hermit|cat").choice(cats)
        pool = _PROPS.get(nc) or [{}]
        new = (pool[0] or {}).get("name") or CAT_KO.get(nc, nc)
        old = it.get("name")
        it.update({"category": nc, "subtype": None, "name": new, "row": None, "traded_from": old})
        v["line_left"] = str(VISITORS_BY_TAG.get("trade_corner", {}).get("leaves_line") or "").replace("{item}", new)
        return {"swapped": {"from": old, "to": new, "category": nc}}
    return None


def visitor_carry(st: dict, prev: dict) -> None:
    bm = core_of(st)["flags"].get("blanket_morning")
    if isinstance(bm, dict) and int(bm.get("day") or 0) <= day_of(st):
        morale_add(st, float(bm.get("morale") or 0))
        core_of(st)["flags"].pop("blanket_morning", None)


def food_all_tick(st: dict) -> float:
    """사슬 각인 「잎을 나누는 이」의 food_daily_all(주민 1인당 하루 식량, 음수 = 덜 먹음 → 그만큼 남는다). 하루 한 번."""
    c = core_of(st)
    day = day_of(st)
    if c["flags"].get("food_all_day") == day:
        return 0.0
    c["flags"]["food_all_day"] = day
    per = float(role_effects(st).get("food_daily_all") or 0)
    if not per:
        return 0.0
    amt = -per * len(st.get("residents_list") or [])
    frac = float(c["flags"].get("food_all_frac") or 0) + amt
    whole = int(frac) if frac >= 0 else -int(-frac)
    st["resources"]["food"] = max(0, int(st["resources"].get("food", 0)) + whole)
    c["flags"]["food_all_frac"] = round(frac - whole, 4)
    return amt


# ── S21 (3차 플레이테스트 고침) ────────────────────────────────────
def open_asks(st: dict) -> list:
    """답하지 않은 매듭 물음(사람마다)."""
    out = []
    for r in st.get("residents_list") or []:
        for aid, s in (cres(st, r["id"])["arcs"] or {}).items():
            pend = s.get("ask_pending")
            if pend and str(pend) not in (s.get("asks") or {}):
                out.append({"resident_id": r["id"], "arc_id": aid, "step": pend})
    return out


def arc_item_at_home(st: dict, uid: str, r: dict, beat: dict) -> bool:
    """그 매듭을 풀 물건이 선반·창고 상자에 있나(건네기 매듭의 give / give_distinct 규칙)."""
    trig = beat.get("trigger") or {}
    rules = []
    for x in [trig] + list(trig.get("any_of") or []):
        if isinstance(x, dict):
            if x.get("give"):
                rules.append(x["give"])
            if x.get("give_distinct"):
                rules.append({"category": x["give_distinct"].get("category"), "subtype": x["give_distinct"].get("subtype")})
    if not rules:
        return False
    for row in list(st.get("shelf") or []) + list(st.get("stored") or []):
        if not row.get("category"):
            continue
        if not any(rl.get("category") in (None, row.get("category")) for rl in rules):
            continue
        it = item_from_row(row)
        if any(match({k: v for k, v in rl.items() if k in ("category", "subtype", "family", "rarity_min")}, it) for rl in rules):
            return True
    return False


def octopus_gift_relic(st: dict, find: dict, day: int) -> dict | None:
    """문어 이야기 선물(비트 5)을 선반(차면 창고 상자)에 건넬 수 있는 물건으로 놓는다. card_id = oct-<id>-<day>."""
    cat = find.get("favor_category") if find.get("favor_category") in EX.CATS else "stationery"
    if cat in SAFE_EXCLUDE_CATS:
        cat = "stationery"                            # S31: 문어 조각이 담배 갈래 선반 물건이 되지 않게
    cid = f"oct-{find['id']}-{day}"
    card = {"category": cat, "rarity": "rare", "id": cid, "name": find.get("name"), "family_name": None,
            "barcode": None, "_day": day}
    slot = shelf_place(st, card)
    for it in st.get("shelf") or []:
        if it.get("card_id") == cid:
            it["relic_name"] = find.get("name")
            it["octopus"] = find["id"]
    if slot is None:
        row = store_overflow(st, card)
        row["relic_name"] = find.get("name")
        row["octopus"] = find["id"]
    return {"card_id": cid, "name": find.get("name"), "category": cat}


def octopus_gift_where(st: dict, uid: str) -> dict | None:
    """비트 5 색 조각이 아직 선반·창고 상자에 있으면 그 「어디로」(스캔과 같은 모양, scan_id = relic_id)."""
    g = (st.get("octopus") or {}).get("gift_relic")
    if not g or g.get("given"):
        return None
    row = next((x for x in (st.get("shelf") or []) + (st.get("stored") or [])
                if x.get("card_id") == g["card_id"] or x.get("id") == g["card_id"]), None)
    if not row:
        return None
    it = item_from_row(row)
    it["card_id"] = g["card_id"]
    w = where_for(st, uid, it)
    w.pop("_internal", None)
    w["relic_id"] = g["card_id"]
    w["name"] = g.get("name")
    w["heirloom_first"] = bool(w.get("heirloom")) and core_of(st)["flags"].get("guaranteed_rare_day") is not None
    return w


NOVELTY_FROM_DAY = 4


def novelty_line(st: dict, kind: str, fallback: str, vals: dict) -> tuple[str, str | None]:
    """ui_moments novelty.<kind>[] 를 종류마다 돌려 쓴다(같은 줄 연속 금지). 배열이 없으면 서버 기본 줄."""
    lines = (moments().get("novelty") or {}).get(kind)
    if isinstance(lines, str):
        lines = [lines]
    if not lines:
        return fallback, None
    rot = core_of(st)["flags"].setdefault("novelty_rot", {})
    i = int(rot.get(kind, 0)) % len(lines)
    rot[kind] = i + 1
    t = str(lines[i])
    for k, v in (vals or {}).items():
        t = t.replace("{" + k + "}", str(v))
    return t, f"novelty.{kind}.{i}"


def novelty_tick(st: dict, uid: str, visits: list, arcs: list) -> dict | None:
    """S21 주 후반 새것 보장(3차 플테 문제 5). **방법**: 켠 날 4부터 세션마다 한 번, 그 세션에 새것·모르는 결과가
    하나도 없으면(새 방문자·매듭·새 비트·밤사이 새 항목 없음) 아래 순서로 하나를 만든다 —
    ① 아직 안 열린 기억의 실마리(누가 어떤 갈래를 보면 무언가 떠올릴 것 같다 — 결과는 모른다)
    ② 꼬리표 직전 방의 손님 실마리(하나만 더 놓으면 누가 올지 모른다)
    ③ 아직 머리맡 물건이 없는 사람(처음 좋아할 물건이 머리맡이 된다)
    ④ 문어의 행동 한 줄. 같은 실마리는 다시 쓰지 않는다(core.novelty_seen)."""
    c = core_of(st)
    ss = c["session"]
    if play_day(st) < NOVELTY_FROM_DAY or ss.get("novelty_n") == ss.get("n"):
        return ss.get("novelty") if ss.get("novelty_n") == ss.get("n") else None
    # S22: 아침마다 되풀이되는 줄(머리맡·사슬 뒷날 줄·두 번째 이후 방문)과 비트는 새것으로 세지 않는다
    fresh_kinds = {"expedition_return", "knock", "wish", "imprint", "clue", "souvenir"}
    if any(v.get("kind") == "visitor" and v.get("first") for v in visits or []) or arcs or \
            any(it.get("kind") in fresh_kinds and it.get("shown_day") is None for it in (st.get("overnight") or {}).get("items") or []):
        ss["novelty_n"] = ss.get("n")
        ss["novelty"] = None
        return None
    seen = c.setdefault("novelty_seen", [])
    rng = random.Random(f"{uid}|{day_of(st)}|{ss.get('n')}|novelty")
    out = None
    ppl = list(st.get("residents_list") or [])
    rng.shuffle(ppl)
    for r in ppl:                                         # ① 기억 실마리
        for m in role_taste(r.get("role", "")).get("memories") or []:
            key = f"memory|{r['id']}|{m.get('id')}"
            if m.get("id") in cres(st, r["id"])["memories_seen"] or key in seen:
                continue
            tr = m.get("trigger") or {}
            if not memory_hint_ok(st, tr) or not safe_rule(tr, strict=True):
                continue                                  # S22: 이 방주가 실제로 찍은 적 있는 하위 종류만 귀띔한다
            ko = rule_ko(tr)
            out = {"kind": "memory_hint", "resident_id": r["id"], "key": key,
                   "line": f"{r['name']} 님이 요즘 「{ko}」 쪽 물건 이야기를 자주 꺼내십니다. 무슨 사연인지는 아직 말씀이 없으십니다.",
                   "data": {"category": tr.get("category"), "subtype": tr.get("subtype")},
                   "_vals": {"name": r["name"], "ko": ko}}
            break
        if out:
            break
    if not out:                                           # ② 꼬리표 직전 방
        for rm in live_rooms(st):
            for x in decor_tags(st, rm["slot"]):
                key = f"tag|{rm['slot']}|{x['id']}"
                if not x["on"] and x["have"] + 1 >= x["need"] and key not in seen:
                    rn = (ROOMS.get(rm["id"]) or {}).get("name", rm["id"])
                    out = {"kind": "visitor_hint", "key": key, "line": f"{rn}에 「{x['ko']}」 물건이 하나만 더 놓이면, 누가 창에 붙을지 모르겠습니다.",
                           "data": {"slot": rm["slot"], "tag": x["id"]}, "_vals": {"room": rn, "tag": x["ko"]}}
                    break
            if out:
                break
    if not out:                                           # ③ 아직 머리맡이 빈 사람
        for r in ppl:
            key = f"keepsake|{r['id']}"
            if not cres(st, r["id"]).get("keepsake") and key not in seen:
                out = {"kind": "keepsake_hint", "resident_id": r["id"], "key": key,
                       "line": f"{r['name']} 님 머리맡은 아직 비어 있습니다. 처음 마음에 드는 물건이 그 자리에 놓일 겁니다.",
                       "data": {}, "_vals": {"name": r["name"]}}
                break
    if not out and st.get("octopus"):                     # ④ 문어
        nm = (st.get("octopus") or {}).get("name") or "문어"
        out = {"kind": "octopus_hint", "key": f"oct|{day_of(st)}|{ss.get('n')}",
               "line": f"{nm}, 선반 앞에서 무언가 하나를 오래 만지작거립니다. 무엇인지는 아직 모릅니다.", "data": {},
               "_vals": {"oct_name": nm}}
    if out:                                               # 문장은 시나리오 ui_moments novelty.<kind>[] (돌려 쓰기), 없으면 위 기본 줄
        out["line"], out["line_key"] = novelty_line(st, out["kind"], out["line"], out.pop("_vals", {}))
    ss["novelty_n"] = ss.get("n")
    ss["novelty"] = out
    if out:
        seen.append(out["key"])
        del seen[:-80]
        overnight_add(st, "novelty", {k: v for k, v in out.items() if k != "key"})
    return out


# ── S22 1단계 「약속을 지키는 루프」 앞쪽 (docs/API_S19.md §12) ─────────────────────
S22N = CORE_A.get("s22_server_numbers") or {}
_SP = S22N.get("subtype_pick") or {}
SUBTYPE_OPTIONS_MAX = int(_SP.get("options_max", 6))
SUBTYPE_VOTE_MIN = int(_SP.get("vote_min_arks", 3))
SUBTYPE_VOTE_SHARE = float(_SP.get("vote_share_min", 0.6))
_SOFT = S22N.get("arc_soft") or {}
SOFT_AFTER_DAYS = int(_SOFT.get("after_days", 2))
SOFT_PLAYED_ONLY = bool(_SOFT.get("count_played_days_only", False))
INTENT_ONCE = bool((S22N.get("intent") or {}).get("once_per_resident_per_day", True))
SOFT_RARITY = dict(_SOFT.get("rarity_relax") or {"rare": "uncommon", "epic": "rare", "legendary": "epic"})
FIRST_VISIT_GAP = float((S22N.get("visitor_first") or {}).get("gap_minutes", 30)) * 60
SOUVENIR_VISITS = int((S22N.get("souvenir") or {}).get("visits", 3))
KEEPSAKES_RECENT_MAX = int(S22N.get("keepsakes_recent_max", 3))


def octo_fallback(st: dict, r: dict, beat: dict) -> str | None:
    """문어가 끼는 매듭(octopus_with)의 관리실 줄이 비었을 때 ui_moments arc_fallback.octopus_with[]."""
    if "octopus_with" not in json.dumps(beat.get("trigger") or {}):
        return None
    lines = (moments().get("arc_fallback") or {}).get("octopus_with") or []
    if not lines:
        return None
    rot = core_of(st)["flags"].setdefault("octo_fb_rot", 0)
    core_of(st)["flags"]["octo_fb_rot"] = int(rot) + 1
    return fill_text(lines[int(rot) % len(lines)], st, r)


def seat_slot(st: dict, r: dict, a: dict | None) -> int | None:
    """사슬 끝 「자리」가 놓일 방 칸 — 그 사람이 선 방, 없으면 사슬 매듭이 가리킨 방(place.room), 없으면 None(홀)."""
    sl = station_slot(st, r["id"])
    rm = room_at(st, sl) if sl is not None else None
    if rm and not rm.get("flooded"):
        return int(sl)
    for b in reversed((a or {}).get("beats") or []):
        trig = b.get("trigger") or {}
        rooms_ = [(x.get("place") or {}).get("room") for x in [trig] + [y for y in (trig.get("any_of") or []) if isinstance(y, dict)]]
        rooms_.append((b.get("ask") or {}).get("room"))            # 매듭 물음이 가리킨 방(예: 요리사 상 → 식량창고)
        for room_id in rooms_:
            hit = next((q for q in live_rooms(st) if q["id"] == room_id), None) if room_id else None
            if hit:
                return int(hit["slot"])
    return None


def seat_public(st: dict, r: dict, cr: dict) -> dict | None:
    """옛 저장의 자리에는 slot 이 없다 — 처음 읽을 때 한 번 정해 굳힌다(그 뒤로 방을 옮겨도 자리는 그 방에)."""
    seat = cr.get("seat")
    if not seat:
        return None
    if "slot" not in seat:
        seat["slot"] = seat_slot(st, r, ARC_BY_ID.get(seat.get("arc")))
    return seat


def role_ok(obj, st: dict) -> bool:
    """줄에 붙은 requires_role(문자열·목록)의 역할이 지금 방주에 모두 있나. 없으면 그 줄을 쓰지 않는다(r4-6)."""
    if not isinstance(obj, dict):
        return True
    req = obj.get("requires_role")
    if not req:
        return True
    need = set(req if isinstance(req, list) else [req])
    have = {r.get("role") for r in st.get("residents_list") or []}
    return need <= have


def role_text(obj: dict, field: str, st: dict):
    """obj[field], 역할 요구가 안 맞으면 obj[field + '_alt'](없으면 None)."""
    if not isinstance(obj, dict):
        return None
    if role_ok(obj, st):
        return obj.get(field)
    if field + "_alt" in obj:
        return obj.get(field + "_alt")
    return None if field == "line" else obj.get(field)     # S27(arcs _alt_rule): announce_alt 가 없으면 announce 그대로


# ① 「이게 뭐예요?」 ───────────────────────────────────────────────
def subtype_options(cat: str) -> list:
    only = set((TEMPLATES.get("_family_only") or {}).get(cat) or [])
    subs = [(k, v) for k, v in (SUBTYPE_KO.get(cat) or {}).items() if k not in only and k != "any"]
    return [{"id": k, "ko": v} for k, v in subs[:SUBTYPE_OPTIONS_MAX]]


def subtype_vote_suggest(code: str, cat: str) -> dict | None:
    """다른 방주들이 이 바코드를 뭐라고 불렀나 — 서로 다른 방주 수만 센다(개인 정보 없음)."""
    if cat not in SUBTYPE_KO:
        return None
    with db() as con:
        raw = con.execute("SELECT uid, subtype FROM subtype_votes WHERE barcode=? AND category=?", (code, cat)).fetchall()
    cnt: dict = {}
    for r_ in raw:                                   # S25 후속: 시험·플레이테스트 방주 표는 세지 않는다. 그 갈래 종류만
        if vote_uid_excluded(r_["uid"]) or r_["subtype"] not in (SUBTYPE_KO.get(cat) or {}):
            continue
        cnt.setdefault(r_["subtype"], set()).add(r_["uid"])
    rows = [{"subtype": k, "n": len(v)} for k, v in cnt.items()]
    tot = sum(int(r["n"]) for r in rows)
    if tot < SUBTYPE_VOTE_MIN or not rows:
        return None
    top = max(rows, key=lambda r: (int(r["n"]), r["subtype"]))
    if int(top["n"]) / tot < SUBTYPE_VOTE_SHARE:
        return None
    return {"id": top["subtype"], "ko": sub_ko(cat, top["subtype"]), "arks": int(top["n"]), "category": cat}


def subtype_pick_for(st: dict, code: str, card_d: dict, bmeta: dict, uid: str = "") -> dict | None:
    """하위 종류가 정해지지 않은 바코드(알려진 가문 18곳·책·정체불명 밖)를 처음 찍으면 그림 단추 4~6개."""
    cat = card_d.get("category")
    try:
        fixed = GEN.subtype_fixed(code, Category(cat))
    except ValueError:
        fixed = True
    if fixed or bmeta.get("subtype"):
        return None
    opts = subtype_options(cat)
    if len(opts) < 2:
        return None
    assert all(o["id"] in (SUBTYPE_KO.get(cat) or {}) for o in opts)   # S25 후속 회귀 가드: 선택지는 카드 갈래의 것만
    wanted = any(cat in {x.get("category") for x in list(role_taste(r.get("role", "")).get("needs") or []) + likes_of(uid, r)
                         if isinstance(x, dict)} for r in st.get("residents_list") or [])
    sug = subtype_vote_suggest(code, cat)
    asks = (moments().get("scan") or {}).get("subtype_ask")
    ask = (asks[int(hashlib.sha256(code.encode()).hexdigest()[:4], 16) % len(asks)] if isinstance(asks, list) and asks
           else asks if isinstance(asks, str) else "이건 뭐라고 부를까요?")
    sug_tpl = (moments().get("scan") or {}).get("subtype_suggest") or "「{ko}」, 다른 방주 {arks}곳에서는 그렇게 부르더군요."
    return {"needed": bool(wanted), "later_ok": True, "options": opts, "suggest": sug, "ask_ko": ask,
            "suggest_ko": sug_tpl.replace("{ko}", sug["ko"]).replace("{arks}", str(sug["arks"])) if sug else None}


class SubtypeIn(BaseModel):
    uid: str
    scan_id: str | None = None
    subtype: str
    rename: bool = False
    barcode: str | None = None          # rename: 바코드로 고를 수도 있다(수첩 화면)


@app.post("/api/scan/subtype")
def scan_subtype(inp: SubtypeIn):
    """그 방주에서 그 바코드의 하위 종류를 영구히 정한다 → 카드·「어디로」를 다시 계산해 돌려준다."""
    st = load_state(inp.uid)
    c = core_of(st)
    p = c["scans"].get(inp.scan_id) if inp.scan_id else None
    code = (p or {}).get("barcode") or inp.barcode or str(inp.scan_id or "").split("-")[0]
    try:
        code = GEN.normalize(code)
    except ValueError:
        raise HTTPException(400, "그 물건을 찾을 수 없습니다")
    bmeta = st.setdefault("barcodes", {}).setdefault(code, {})
    cat = bmeta.get("category") or ((p or {}).get("item") or {}).get("category")
    if not cat or inp.subtype not in [o["id"] for o in subtype_options(cat)]:
        raise HTTPException(400, "그 갈래에서 고를 수 있는 것이 아닙니다")
    old_sub = bmeta.get("subtype")
    if old_sub and old_sub != inp.subtype and not inp.rename:
        raise HTTPException(400, "이 성문은 이미 「" + sub_ko(cat, bmeta["subtype"]) + "」로 적어 두었습니다")
    if inp.rename:                                     # S27: 하루 한 번, 이미 정한 바코드의 이름 다시 붙이기(수첩 기록은 그대로)
        if not old_sub:
            raise HTTPException(400, "아직 이름을 붙이지 않은 성문입니다")
        rd = c["flags"].setdefault("rename_days", {})        # S29: 바코드마다 하루 한 번
        if rd.get(code) == day_of(st):
            raise HTTPException(400, "이 물건 이름은 오늘 이미 다시 붙였습니다")
        rd[code] = day_of(st)
        for k_ in [k_ for k_, v_ in rd.items() if int(v_) < day_of(st) - 1]:
            rd.pop(k_, None)
    bmeta["subtype"] = inp.subtype
    card = GEN.generate(code, hour=now_hour(), user_category=cat, user_subtype=inp.subtype)
    cd = card.to_dict()
    cd["id"] = inp.scan_id
    cd["subtype_ko"] = sub_ko(cat, inp.subtype)
    cd["history"] = card_history(st, code)
    old_name = ((p or {}).get("item") or {}).get("name")
    for rows in (st.get("shelf") or [], st.get("stored") or []):          # 선반·창고 상자의 그 물건 이름도 새 이름으로
        for it in rows:
            if it.get("card_id") == inp.scan_id or it.get("barcode") == code:
                it["relic_name"] = card.name
                it["subtype"] = inp.subtype                 # S29 r6-1: 선반·창고의 그 물건도 새 하위 종류로 판정
    for h in st.get("hand") or []:
        if h.get("barcode") == code:
            h.update({"name": card.name, "subtype": inp.subtype, "flavor": card.flavor})
    cx = st.setdefault("codex", {}).setdefault(cat, {})
    if old_name and old_name != card.name and cx.get(old_name):
        cx[old_name] = int(cx[old_name]) - 1
        if cx[old_name] <= 0:
            cx.pop(old_name, None)
        cx[card.name] = int(cx.get(card.name, 0)) + 1
    ssub = c.setdefault("seen_subtypes", {}).setdefault(cat, [])
    if inp.subtype not in ssub:
        ssub.append(inp.subtype)
    item = item_from_card(cd)
    where = None
    if p is not None:
        p["item"] = item
        where = where_for(st, inp.uid, item)
        p["warm"] = list(where.get("warm_ids") or [])
        p["chain"] = [{"rid": x["target"].get("resident_id"), "name": x.get("name"), "tier": x["tier"]}
                      for x in where.pop("_internal", None) or where.get("suggest") or [] if x["tier"] in ("chain_beat", "memory") and x["kind"] == "resident"]
    if not (p or {}).get("manual") and not vote_excluded(inp.uid, st):   # S24 손 입력 · S25 시험 방주는 전역 투표에 넣지 않는다
        with db() as con:
            con.execute("INSERT OR REPLACE INTO subtype_votes VALUES(?,?,?,?,?)", (inp.uid, code, cat, inp.subtype, time.time()))
    save_state(inp.uid, st)
    log(inp.uid, "subtype_pick", {"barcode": code, "subtype": inp.subtype})
    M_ = moments().get("scan") or {}
    done = M_.get("rename_done") if inp.rename else M_.get("subtype_done")
    return {"ok": True, "card": cd, "where": where, "subtype": inp.subtype, "subtype_ko": cd["subtype_ko"],
            "first_meet": first_meet_sub(cat, inp.subtype, cd.get("name")),   # 고른 하위 종류에 맞춘 첫 만남 줄(옛 짐작 줄 대신)
            "first_meet_was_shown": bool((p or {}).get("first_meet_cat")),
            "renamed_from": sub_ko(cat, old_sub) if inp.rename and old_sub else None,
            "done_ko": done.replace("{ko}", cd["subtype_ko"]) if isinstance(done, str) else None}


def give_intent(st: dict, uid: str, rec: dict | None, item: dict, target, out: dict) -> bool:
    """그날 필요를 보여 준 **뒤에** 찍은 물건으로 그 사람의 필요를 채웠나. 그렇다면 전용 문장으로 바꾼다(값 보너스 없음)."""
    ns = core_of(st).get("needs_shown") or {}
    if not rec or not isinstance(target, dict) or not target.get("resident_id") or out.get("tier") in ("not_for_me", "keep"):
        return False
    if ns.get("day") != day_of(st) or int(rec.get("day") or 0) != day_of(st) or float(rec.get("at") or 0) <= float(ns.get("at") or 0):
        return False
    r = next((x for x in st.get("residents_list") or [] if x["id"] == target["resident_id"]), None)
    nd = need_today(uid, r, day_of(st)) if r else None
    if not nd or not match(nd, item):
        return False
    if vote_mismatch(st, item):
        return False                                  # S23: 다른 방주들이 다르게 부르는 것을 내 마음대로 불렀으면 큰 장면 없음
    idays = core_of(st).setdefault("intent_days", {})
    if INTENT_ONCE and idays.get(r["id"]) == day_of(st):
        return False                                  # 같은 사람 하루 한 번(기획 S22 intent.once_per_resident_per_day)
    idays[r["id"]] = day_of(st)
    if out.get("tier") == "need":
        rx = out.setdefault("reaction", {})
        anns = (TASTES.get("announce") or {}).get("give_intent")
        if isinstance(anns, str):
            anns = [anns]
        res = cres(st, r["id"])
        rot = res.setdefault("line_rot", {})
        if anns:
            i = int(rot.get("_give_intent", 0)) % len(anns)
            rot["_give_intent"] = i + 1
            rx.update({"announce": fill_text(anns[i], st, r, item), "announce_key": f"resident_tastes.announce.give_intent.{i}"})
        il = role_taste(r.get("role", "")).get("intent_lines") or []
        if il:
            j = int(rot.get("intent_lines", 0)) % len(il)
            rot["intent_lines"] = j + 1
            rx.update({"line": fill_text(il[j], st, r, item), "line_key": f"resident_tastes.roles.{r.get('role')}.intent_lines.{j}"})
    return True


# ② 사슬 부드러운 대체 ──────────────────────────────────────────────
def soft_rule(s: dict, v):
    """soft_step 이 지금 매듭이면 좁은 조건(하위 종류·희귀도)을 넓힌다: 하위 종류 → 갈래 전체, 희귀도 한 단계 아래."""
    if not isinstance(v, dict) or s.get("soft_step") != int(s.get("step") or 0) + 1:
        return v
    w = {k: x for k, x in v.items() if k != "subtype"}
    if w.get("rarity_min") in SOFT_RARITY:
        w["rarity_min"] = SOFT_RARITY[w["rarity_min"]]
    return w


def beat_is_narrow(beat: dict) -> bool:
    trig = beat.get("trigger") or {}
    for x in [trig] + [y for y in (trig.get("any_of") or []) if isinstance(y, dict)]:
        for key in ("give", "give_distinct"):
            v = x.get(key)
            if isinstance(v, dict) and (v.get("subtype") or v.get("rarity_min")):
                return True
    return False


def soft_check(st: dict, r: dict, s: dict, beat: dict) -> bool:
    """좁은 조건 매듭이 열린 지 SOFT_AFTER_DAYS 일이 지나도 안 풀렸으면 soft_step 을 켠다(되돌리지 않는다)."""
    step = int(beat.get("step") or (int(s.get("step") or 0) + 1))
    if s.get("soft_step") == step:
        return True
    if not beat_is_narrow(beat):
        return False
    od = beat_opens_day(st, r, s, beat)
    if SOFT_PLAYED_ONLY:                                # 켠 날만 센다(기획 S22): 열린 날 뒤로 실제로 켠 날 수
        played = {int(d) for d in (core_of(st)["beats"].get("days") or {}).values()}
        waited = sum(1 for d in played if od < d <= day_of(st))
    else:
        waited = day_of(st) - od
    if waited >= SOFT_AFTER_DAYS:
        s["soft_step"] = step
        return True
    return False


def beat_already_fired(st: dict, r: dict, a: dict, s: dict, beat: dict) -> bool:
    """r4-1 방어: 이 매듭(사람·사슬·번호)이 이미 풀렸던 기록이 있으면 참(s.days 또는 이번 세션 기록)."""
    step = str(beat.get("step"))
    if step in (s.get("days") or {}):
        return True
    return f"{r['id']}|{a['id']}|{beat.get('step')}" in (core_of(st)["session"].get("fired") or [])


def memory_hint_ok(st: dict, tr: dict) -> bool:
    """기억 실마리는 이 방주가 그 갈래(하위 종류 조건이면 그 하위 종류)를 찍은 적 있을 때만."""
    cat = tr.get("category")
    seen = core_of(st).get("seen_subtypes") or {}
    if tr.get("family"):
        return tr["family"] in (st.get("seen_families") or [])
    if not cat or cat not in (st.get("seen_categories") or []) and cat not in seen:
        return False
    subs = tr.get("subtype")
    if not subs:
        return True
    subs = subs if isinstance(subs, list) else [subs]
    return bool(set(subs) & set(seen.get(cat) or []))


# ③ 꾸밈 → 손님 ────────────────────────────────────────────────
def room_display_name(st: dict, rm: dict) -> str:
    """같은 이름의 방이 둘 이상이면 구분하는 말을 붙인다: 그 방에 선 사람 이름, 없으면 위·아래(r4-8)."""
    nm = (ROOMS.get(rm["id"]) or {}).get("name", rm["id"])
    same = sorted([x for x in live_rooms(st) if x["id"] == rm["id"]], key=lambda x: x["slot"])
    if len(same) < 2:
        return nm
    ppl = stations_map(st).get(int(rm["slot"]), [])
    if ppl:
        return f"{nm}({ppl[0]['name']} 님 방)"
    i = [x["slot"] for x in same].index(rm["slot"])
    word = "위층" if i == 0 else ("아래층" if i == len(same) - 1 else f"가운데 {i}")
    return f"{nm}({word})"


def apply_visit_row(st: dict, uid: str, v: dict) -> None:
    """손님 한 번 — 효과·도감 셈·세 번째면 기념품·밤사이 줄."""
    c = core_of(st)
    v["effect"] = visitor_apply(st, uid, v)
    vkey = v["visitor_id"] + (":rare" if v.get("form") == "rare" else "")
    if vkey not in c["visitors_seen"]:
        c["visitors_seen"].append(vkey)
    book = c.setdefault("visitor_book", {}).setdefault(vkey, {"count": 0, "first_day": day_of(st), "souvenir": None})
    book["count"] = int(book.get("count") or 0) + 1
    overnight_add(st, "visit", {k: v.get(k) for k in ("slot", "room", "visitor_id", "ko", "line", "first", "where")})
    day_note(st, "visit", v.get("ko"))
    if v.get("form") != "rare" and book["count"] >= SOUVENIR_VISITS and not book.get("souvenir"):
        vis = next((x for x in VISITORS_BY_TAG.values() if x["id"] == v["visitor_id"]), {})
        nm = vis.get("souvenir") or f"{vis.get('ko', '손님')}이 남긴 것"
        tag = DECOR_BY_ID.get(v.get("tag")) or {}
        cat = next((f.get("category") for f in tag.get("feeds") or [] if f.get("category") in EX.CATS), "stationery")
        cid = f"souv-{v['visitor_id']}"
        card = {"category": cat, "rarity": "uncommon", "id": cid, "name": nm, "family_name": None, "barcode": None,
                "_day": day_of(st)}
        if shelf_place(st, card) is None:
            row = store_overflow(st, card)
            row["relic_name"] = nm
        for it in st.get("shelf") or []:
            if it.get("card_id") == cid:
                it["relic_name"] = nm
        book["souvenir"] = {"name": nm, "relic_id": cid, "day": day_of(st)}
        line = (vis.get("souvenir_line") or "「{item}」 하나가 {room}에 남아 있습니다.").replace("{item}", nm).replace("{room}", v.get("room") or "")
        overnight_add(st, "souvenir", {"visitor_id": v["visitor_id"], "name": nm, "relic_id": cid, "line": line})


def force_first_visit(st: dict, uid: str, ss: dict) -> list:
    """첫 꼬리표가 붙은 뒤 **다음 세션**(FIRST_VISIT_GAP 이상 지난 새 세션)에 그 방 첫 손님이 와 있다."""
    c = core_of(st)
    vg = c["flags"].get("visit_guarantee") or {}
    if not vg.get("at") or vg.get("done"):
        if vg and not vg.get("done") and any(r.get("kind") == "visitor" and r.get("slot") == vg.get("slot") and r.get("tag") == vg.get("tag")
                                             for r in (c["visits"].get("rows") or [])):
            vg["done"] = True
        return []
    if any(r.get("kind") == "visitor" and r.get("slot") == vg.get("slot") and r.get("tag") == vg.get("tag")
           for r in (c["visits"].get("rows") or []) if c["visits"].get("day") == day_of(st)):
        vg["done"] = True
        return []
    if not ss.get("new") or time.time() - float(vg["at"]) < FIRST_VISIT_GAP:
        return []
    rm = room_at(st, vg.get("slot"))
    v = VISITORS_BY_TAG.get(vg.get("tag"))
    if not rm or rm.get("flooded") or not v or vg.get("tag") not in room_tags_on(st, rm["slot"]):
        return []
    rname = (ROOMS.get(rm["id"]) or {}).get("name", rm["id"])
    first = v["id"] not in c["visitors_seen"]
    row = {"day": day_of(st), "slot": rm["slot"], "room": rname, "tag": vg["tag"], "kind": "visitor",
           "visitor_id": v["id"], "ko": v.get("ko"), "where": v.get("where"), "first": first, "forced": True,
           "line": (v.get("arrival") if first else v.get("again") or v.get("arrival") or "").replace("{room}", rname),
           "desc": v.get("desc"), "look": v.get("look")}
    if c["visits"].get("day") != day_of(st):
        c["visits"] = {"day": day_of(st), "rows": []}
    c["visits"].setdefault("rows", []).append(row)
    apply_visit_row(st, uid, row)
    vg["done"] = True
    return [row]


def decor_trace(st: dict, uid: str) -> list:
    """꼬리표까지 하나 남은 방의 흔적(예고) — visitors.json trace[] 중 하루 하나."""
    out = []
    for rm in live_rooms(st):
        rname = (ROOMS.get(rm["id"]) or {}).get("name", rm["id"])
        for x in decor_tags(st, rm["slot"]):
            if x["on"] or x.get("elsewhere") or x["have"] != x["need"] - 1:
                continue
            v = VISITORS_BY_TAG.get(x["id"])
            if not v:
                continue
            tr = v.get("trace")
            tr = tr if isinstance(tr, list) else [tr] if tr else []
            line = random.Random(f"{uid}|{day_of(st)}|trace|{rm['slot']}|{x['id']}").choice(tr).replace("{room}", rname) if tr else None
            out.append({"slot": rm["slot"], "tag": x["id"], "tag_ko": x["ko"], "visitor_id": v["id"], "ko": v.get("ko"),
                        "line": line})
    return out


def visitors_book(st: dict) -> list:
    """꾸밈 손님 도감(빈칸 포함). 세 번 오면 기념품."""
    book = core_of(st).get("visitor_book") or {}
    seen = core_of(st).get("visitors_seen") or []
    out = []
    for v in VISITORS_BY_TAG.values():
        b = book.get(v["id"]) or {}
        cnt = int(b.get("count") or (1 if v["id"] in seen else 0))
        rb = book.get(v["id"] + ":rare") or {}
        out.append({"id": v["id"], "ko": v.get("ko"), "tag": v.get("tag"), "count": cnt, "first_day": b.get("first_day"),
                    "souvenir": b.get("souvenir"), "souvenir_name": v.get("souvenir"),
                    "rare": {"count": int(rb.get("count") or 0), "first_day": rb.get("first_day"),
                             "ko": (v.get("rare") or {}).get("ko")}})      # S25: 도감 8 → 16칸(드문 모습)
    return out


# ⑥ 두 번째 기회 · ⑦ 그림용 필드 ─────────────────────────────────────
def missed_chain_of(st: dict, uid: str) -> dict | None:
    """오늘 「어디로」가 매듭·기억을 제안했는데 닫았거나 다른 데 준 것 — 그 사람이 아직 그 매듭·기억을 못 풀었으면 한 줄."""
    c = core_of(st)
    day = day_of(st)
    by = {r["id"]: r for r in st.get("residents_list") or []}
    for rec in reversed(list(c["scans"].values())):
        if int(rec.get("day") or 0) != day:
            continue
        if not rec.get("given"):
            continue                                  # 아직 「어디로」를 고르지 않은 스캔(방금 찍은 것)은 놓친 게 아니다
        for ch in rec.get("chain") or []:
            rid = ch.get("rid")
            if rid not in by or (rec.get("given") and isinstance(rec.get("to"), dict) and rec["to"].get("resident_id") == rid):
                continue
            r = by[rid]
            if solved_today(st, rid):
                continue                              # S27 r5-1: 그 사람은 오늘 이미 매듭이나 기억을 풀었다
            if ch.get("tier") == "chain_beat":
                a, s = current_arc(st, r)
                if not a or s.get("last_day") == day:
                    continue
            else:
                if len(cres(st, rid)["memories_seen"]) and rec.get("item") and not memory_match(st, r, rec["item"]):
                    continue
            lines = (NEXT_VISIT.get("promises") or {}).get("missed_chain") or []
            tpl = random.Random(f"{uid}|{day}|missed|{rid}").choice(lines) if lines else \
                "{name} 님이 아까 뭔가 하실 말씀이 있었던 것 같습니다. 다음에 한 번 보여 드려 보세요."
            return {"resident_id": rid, "name": r["name"], "kind": ch.get("tier"), "line": tpl.replace("{name}", r["name"])}
    return None


def _props_by_subtype() -> dict:
    try:
        m = json.loads((ROOT / "static" / "art" / "props" / "props_meta.json").read_text(encoding="utf-8"))
        return m.get("by_subtype") or {}
    except (OSError, json.JSONDecodeError):
        return {}


PROPS_BY_SUBTYPE = _props_by_subtype()


def prop_for_item(it: dict) -> str | None:
    """S22 ②: 그 물건을 그릴 소품 — props_meta.json by_subtype[갈래][하위 종류] → 그 갈래 첫 good → unknown.any → 옛 규칙."""
    cat, sub = it.get("category") or "unknown", it.get("subtype")
    bc = PROPS_BY_SUBTYPE.get(cat) or {}
    if sub and isinstance(bc.get(sub), dict) and bc[sub].get("prop"):
        return bc[sub]["prop"]
    good = next((v.get("prop") for v in bc.values() if isinstance(v, dict) and v.get("match") == "good" and v.get("prop")), None)
    if good:
        return good
    ua = ((PROPS_BY_SUBTYPE.get("unknown") or {}).get("any") or {}).get("prop")
    if ua:
        return ua
    row = it.get("row") or {}
    pid = row.get("prop_id") or it.get("prop_id")
    if pid and pid in _PROPS_META:
        return pid
    for p_ in _PROPS.get(it.get("category") or "unknown") or []:
        if p_.get("id") in _PROPS_META:
            return p_["id"]
    return pid


def keepsakes_recent(cr: dict) -> list:
    out = []
    for it in reversed(cr.get("items") or []):
        out.append({"relic_id": it.get("card_id"), "name": it.get("name"), "category": it.get("category"),
                    "subtype": it.get("subtype"), "prop": prop_for_item(it), "day": it.get("day")})
        if len(out) >= KEEPSAKES_RECENT_MAX:
            break
    return out


def card_history(st: dict, code: str | None) -> list:
    """이 방주에서 이 바코드를 누구에게(어느 방에) 줬나 — [{day, to_name}] 날 순."""
    if not code:
        return []
    by = {r["id"]: r["name"] for r in st.get("residents_list") or []}
    rows = []
    for rid, cr in (core_of(st).get("res") or {}).items():
        for g in cr.get("given") or []:
            if g.get("barcode") == code:
                rows.append({"day": g.get("day"), "to_name": by.get(rid) or "떠난 분", "resident_id": rid})
    for slot, room in (core_of(st).get("rooms") or {}).items():
        rm = room_at(st, int(slot))
        for it in room.get("items") or []:
            if it.get("barcode") == code:
                rows.append({"day": it.get("day"), "to_name": (ROOMS.get((rm or {}).get("id")) or {}).get("name", "방"), "slot": int(slot)})
    rows.sort(key=lambda x: int(x.get("day") or 0))
    return rows


def rescue_happened(st: dict) -> bool:
    return bool(core_of(st)["flags"].get("rescue_done") or any(x.get("newcomer") for x in st.get("exp_log") or []))


def newest_resident_name(st: dict) -> str | None:
    """처음 셋 뒤로 들어온 사람 중 가장 최근(두드림·사건으로 온 분). 없으면 None."""
    start = float(st.get("created") or 0) + 60
    late = [r for r in st.get("residents_list") or [] if float(r.get("joined") or 0) > start]
    return max(late, key=lambda r: float(r.get("joined") or 0))["name"] if late else None


# ── S23 1단계 뒤쪽: 사람 수첩 · 받는 저녁 · 내일의 부탁 (docs/API_S19.md §13) ──────────────
_S22B = CORE_A.get("s22") or {}
_NB = _S22B.get("notebook") or {}
_ET = _S22B.get("evening_table") or {}
NB_LABELS_UNTIL = int(_NB.get("labels_until_day", 2))
NB_RECORD_EARLY = bool(_NB.get("record_days_1_2", True))
NB_GOSSIP_PER_EVENING = int(_NB.get("gossip_per_evening", 1))
ET_FOOD = int(_ET.get("food_cost_total", 4))
ET_NO_FOOD_OK = bool(_ET.get("no_food_ok", True))
ET_TRUST = (int(_ET.get("trust_pair", 3)), int(_ET.get("trust_pair_if_item_liked_by_either", 5)),
            int(_ET.get("trust_pair_if_item_liked_by_both", 7)))
ET_REPEAT = float(_ET.get("same_pair_repeat_mult", 0.5))
_OVX = (CORE_A.get("s19_server_numbers") or {}).get("overflow") or {}
TABLE_STORE_FIRST = bool(_OVX.get("to_table_store_first", False))
TABLE_STORE_MAX = int(_OVX.get("table_store_max", 12))
NIGHT_VISITORS = [v for v in (_live_or_draft("visitors.json").get("night_visitors") or []) if isinstance(v, dict) and v.get("id")]
KIND_KO = {"like": "좋아함", "need": "필요", "memory": "기억", "dislike": "안 맞음"}


def _rot(st: dict, key: str, lines: list):
    """줄 목록을 방주 안에서 돌려 쓴다(같은 줄 연속 금지). (줄, 번호) 또는 (None, None)."""
    if isinstance(lines, str):
        lines = [lines]
    if not lines:
        return None, None
    rot = core_of(st)["flags"].setdefault("rot", {})
    i = int(rot.get(key, 0)) % len(lines)
    rot[key] = i + 1
    return lines[i], i


# ① 사람 수첩 ─────────────────────────────────────────────────
def labels_shown(st: dict) -> bool:
    if CALENDAR_ENFORCE:                               # S25: 기색·수첩은 켠 날 3(해금 달력)부터
        return not is_unlocked(st, "mood_hints") or bool((st.get("prefs") or {}).get("labels_always"))
    return day_of(st) <= NB_LABELS_UNTIL or bool((st.get("prefs") or {}).get("labels_always"))


def notebook_slots(st: dict, uid: str, r: dict) -> list:
    """수첩 칸: 좋아함(역할 + 덧붙임) · 필요(역할 목록) · 기억(열려야 이름이 보인다) · 안 맞음(덧붙임)."""
    rt = role_taste(r.get("role", ""))
    out = []
    for i, x in enumerate(likes_of(uid, r)):
        if not item_rule_safe(x):
            continue                                  # S24: 담배·술·약 좋아함은 수첩의 '찾을 것'에 올리지 않는다(번호는 그대로)
        out.append({"key": f"like:{i}", "kind": "like", "ko": rule_ko(x), "rule": x})
    for i, x in enumerate(rt.get("needs") or []):
        if safe_rule(x):
            out.append({"key": f"need:{i}", "kind": "need", "ko": rule_ko(safe_rule(x)), "rule": safe_rule(x)})
    for m in rt.get("memories") or []:
        if not safe_rule(m.get("trigger") or {}, strict=True):
            continue                                  # S24: 안전 목록 밖 기억(술·약)은 수첩 칸·귀띔에 올리지 않는다
        out.append({"key": f"memory:{m.get('id')}", "kind": "memory", "ko": rule_ko(m.get("trigger") or {}), "rule": m.get("trigger")})
    tw = twist_of(uid, r).get("dislike")
    if tw:
        out.append({"key": "dislike", "kind": "dislike", "ko": tw.get("ko"), "rule": {"category": tw["category"], "subtype": tw.get("subtype")}})
    return out


def nb_known(st: dict, rid: str) -> dict:
    return cres(st, rid).setdefault("notebook", {})


def slot_for_tier(st: dict, uid: str, r: dict, item: dict, tier: str, info: dict | None = None) -> str | None:
    """이 물건이 그 사람의 어느 칸을 건드리나(tier 에 맞춰)."""
    if tier == "need":
        nd = need_today(uid, r, day_of(st))
        return f"need:{nd['idx']}" if nd and match(nd, item) else None
    if tier == "like":
        for i, x in enumerate(likes_of(uid, r)):
            if match(x, item):
                return f"like:{i}"
        return None
    if tier == "memory":
        m = (info or {}).get("memory") or memory_match(st, r, item)
        return f"memory:{m.get('id')}" if m else None
    if tier == "not_for_me":
        tw = twist_of(uid, r).get("dislike")
        if tw and match({"category": tw["category"], "subtype": tw.get("subtype")}, item):
            return "dislike"
    return None


def sign_candidates(st: dict, r: dict, item: dict, slot: str | None, uid: str = "") -> list:
    """기색 후보 [(템플릿, 출처)] — 칸 정확히(signs.needs/likes[i]) → 역할×갈래(signs.by_category) → 갈래 공통(signs_generic)."""
    signs = role_taste(r.get("role", "")).get("signs") or {}
    out = []

    def add(lines, src):
        if isinstance(lines, str):
            lines = [lines]
        for t in lines or []:
            if isinstance(t, str) and t:
                out.append((t, src))
    if slot is None or not slot.startswith(("need:", "like:")):
        for key, rules in (("needs", list(role_taste(r.get("role", "")).get("needs") or [])), ("likes", likes_of(uid, r))):
            arr = signs.get(key) or []
            for k, rl in enumerate(rules):
                if k < len(arr) and isinstance(rl, dict) and item_rule_safe(rl) and rule_at_home(st, rl):
                    add(arr[k], "home")                # S27: 이 집에 있는(찍은·선반·창고) 하위 종류를 가리키는 기색 — 풀 수 있는 수수께끼
    for pre, key in (("need:", "needs"), ("like:", "likes")):
        if slot and slot.startswith(pre):
            k = int(slot.split(":")[1])
            src_rules = likes_of(uid, r) if key == "likes" else (role_taste(r.get("role", "")).get("needs") or [])
            if k < len(src_rules) and not item_rule_safe(src_rules[k]):
                continue                              # S24: 안전 목록 밖 칸을 가리키는 기색은 쓰지 않는다
            arr = signs.get(key) or []
            add(arr[k] if k < len(arr) else None, "slot")
    add((signs.get("by_category") or {}).get(item.get("category") or ""), "role")
    add((moments().get("signs_generic") or {}).get(item.get("category") or ""), "generic")
    return out


def sign_hint(st: dict, uid: str, r: dict, item: dict, tier: str, slot: str | None, used: set | None = None) -> str:
    """라벨 대신 기색 한 줄. 한 「어디로」 안에서 같은 템플릿을 두 사람에게 쓰지 않는다(used).
    갈래 공통 줄을 쓸 때는 그 사람의 역할을 붙여 누구 이야기인지 읽히게 한다(「요리사 도담 님이…」)."""
    used = used if used is not None else set()
    cands = sign_candidates(st, r, item, slot, uid)
    rng = random.Random(f"{uid}|{day_of(st)}|{r['id']}|{item_key(item)}|sign")
    for src in ("slot", "home", "role", "generic"):
        pool = [t for t, s_ in cands if s_ == src and t not in used]
        if pool:
            t = rng.choice(pool)
            used.add(t)
            if src == "generic":
                rk = r.get("evolved_ko") or r.get("role_ko") or (ROLES.get(r.get("role")) or {}).get("ko") or ""
                t = t.replace("{name} 님", f"{rk} {{name}} 님", 1) if rk else t
            return fill_text(t, st, r, item)
    rk = r.get("role_ko") or ""
    qk = ((r.get("quirk") or {}).get("ko") or "") if isinstance(r.get("quirk"), dict) else ""
    t = f"{rk} {{name}} 님이 이쪽을 한 번 보셨습니다." + (f" {qk}고들 합니다." if qk else "")   # 후보가 다 쓰였을 때만
    return fill_text(t.strip(), st, r, item)


def last_given_at(st: dict, rid: str) -> float:
    g = cres(st, rid)["given"]
    if not g:
        return -1.0
    return max(float(x.get("at") or 0) or float(x.get("day") or 0) for x in g)


def notebook_view(st: dict, uid: str, item: dict, w: dict) -> dict:
    """3일째부터(설정 labels_always 가 아니면): 순서는 **가장 오래 못 받은 사람부터**(받은 적 없는 사람 먼저) → 방.
    값 정렬·첫자리 강조 없음. 모르는 칸은 라벨 대신 기색(한 「어디로」 안에서 같은 문장 없음)."""
    pin_rows(st, uid, item, w)                           # S27: 부탁한 사람·필요/좋아함이 맞는 사람은 줄에서 빠지지 않는다
    w["_internal"] = [dict(x) for x in w["suggest"]]     # 서버만 쓰는 원래 등급(응답 전에 뺀다)
    if labels_shown(st):
        story = evening_story_first(st, w)
        if story:                                     # S30: 저녁 세션 첫 칸 = 그날 아직 안 움직인 이야기
            row = next(x for x in w["suggest"] if x.get("target", {}).get("resident_id") == story)
            w["suggest"].remove(row)
            w["suggest"].insert(0, dict(row, first_reason="story"))
        else:
            ppl_ = [x for x in w["suggest"] if x["kind"] == "resident"]
            rest_ = [x for x in w["suggest"] if x["kind"] != "resident"]
            ppl_ = memory_for_evening(st, w, ppl_)
            if ppl_ and w["suggest"] and w["suggest"][0]["kind"] == "resident":
                w["suggest"] = ppl_ + rest_
            else:
                w["suggest"] = [x for x in w["suggest"] if x["kind"] != "resident" or x in ppl_]
        w.update({"labels": True, "order": "value"})
        return w
    by = {r["id"]: r for r in st.get("residents_list") or []}
    order = [r["id"] for r in st.get("residents_list") or []]

    def room_pos(rid):                                   # 같으면 방 순서(그 사람이 선 칸, 문간·홀은 뒤)
        sl = station_slot(st, rid)
        return (sl if sl is not None else 99, order.index(rid) if rid in order else 99)
    ppl = sorted([x for x in w["suggest"] if x["kind"] == "resident"],
                 key=lambda x: (last_given_at(st, x["target"]["resident_id"]), room_pos(x["target"]["resident_id"])))
    pinned = [x for x in ppl if x.get("pinned")]
    if pinned and len(ppl) > 1 and ppl[0].get("pinned") and not all(x.get("pinned") for x in ppl):
        first = next(x for x in ppl if not x.get("pinned"))   # 고정한 사람은 첫 칸이 아니라 둘째 칸부터
        ppl.remove(first)
        ppl.insert(0, first)
    rooms = sorted([x for x in w["suggest"] if x["kind"] != "resident"], key=lambda x: x["target"].get("slot", 0))
    used: set = set()
    for x in ppl:
        r = by.get(x["target"]["resident_id"])
        if not r:
            continue
        tier = x.get("tier")
        if tier == "chain_beat":
            x["known"] = True                         # 사슬은 이미 보이는 이야기다
            continue
        slot = slot_for_tier(st, uid, r, item, tier)
        if slot and slot in nb_known(st, r["id"]):
            x["known"] = True
            x["slot"] = slot
            continue
        x["hint_ko"] = sign_hint(st, uid, r, item, tier, slot, used)
        x["known"] = False
        for k in ("tier", "icon", "reason_ko", "value", "mult", "fallback", "arc_id", "step"):
            x.pop(k, None)
    for x in rooms:
        x["known"] = True
    kfit = [x for x in ppl if x.get("known") and x.get("slot") and str(x["slot"]).startswith(("need:", "like:", "memory"))]
    story = evening_story_first(st, w)
    if story:
        kfit = [x for x in ppl if x["target"]["resident_id"] == story]
    elif not kfit and known_total(st) < LOW_KNOWN:  # S31 ③: 아는 칸이 아직 적은 방주(B) — 지금 찍은 물건과 기색이 맞는 사람이 첫 칸
        tiers = {x["target"].get("resident_id"): x.get("tier") for x in w.get("_internal") or [] if x.get("kind") == "resident"}
        fitp = [x for x in ppl if tiers.get(x["target"]["resident_id"]) in ("need", "like", "memory", "chain_beat")]
        if fitp:
            kfit = fitp[:1]
            kfit[0]["slot_hint_first"] = True
    if kfit:                                          # S29: 이미 얻은 앎(수첩)이 맞는 사람이 첫 칸 — 답을 흘리는 것이 아니다
        kfit.sort(key=lambda x: 0 if str(x.get("slot") or "").startswith("need:") else 1)
        ppl = kfit + [x for x in ppl if x not in kfit]
        for x in kfit:
            x["first_reason"] = "story" if story else ("fit" if x.pop("slot_hint_first", None) else "known")
    ppl = memory_for_evening(st, w, ppl)               # S31 ②: 아침에는 기억 하나를 저녁 몫으로(뒤로, 고르면 줄 수 있다)
    w["suggest"] = ppl + rooms
    w.update({"labels": False, "order": "least_recent"})
    return w


def notebook_before(st: dict, uid: str, item: dict, target) -> dict:
    """주기 전 — 라벨이 보였나, 그 사람의 그 칸을 이미 알았나(맞힘 판정)."""
    if not isinstance(target, dict) or not target.get("resident_id"):
        return {}
    r = next((x for x in st.get("residents_list") or [] if x["id"] == target["resident_id"]), None)
    if not r:
        return {}
    return {"labels": labels_shown(st), "known": set(nb_known(st, r["id"]).keys())}


def notebook_record(st: dict, uid: str, item: dict, target, out: dict, before: dict) -> dict | None:
    """건넨 뒤 결과 공개 + 수첩 기록. big = 라벨 없이 맞혔다(모르던 칸을 처음 맞힘)."""
    if not isinstance(target, dict) or not target.get("resident_id"):
        return None
    r = next((x for x in st.get("residents_list") or [] if x["id"] == target["resident_id"]), None)
    if not r:
        return None
    tier = out.get("tier")
    info = {"memory": {"id": ((out.get("effects") or {}).get("memory") or {}).get("id")}} if (out.get("effects") or {}).get("memory") else None
    slot = slot_for_tier(st, uid, r, item, tier, info)
    if not slot and tier == "chain_beat":                # 사슬이 풀린 물건도 좋아함·필요 칸을 건드렸으면 적는다
        for t2 in ("need", "like"):
            slot = slot_for_tier(st, uid, r, item, t2)
            if slot:
                break
    known_before = slot in (before.get("known") or set()) if slot else True
    big = bool(slot) and not known_before and not before.get("labels") and tier in ("need", "like", "memory", "chain_beat")
    if slot and (NB_RECORD_EARLY or not before.get("labels")) and slot not in nb_known(st, r["id"]):
        nb_known(st, r["id"])[slot] = {"day": day_of(st), "how": "give", "item": item.get("name")}
    R = moments().get("reveal") or {}
    kind = "discovered" if big else (tier if tier in R else None)
    line, i = _rot(st, f"reveal.{kind}", R.get(kind) or []) if kind else (None, None)
    return {"kind": tier, "big": big, "slot": slot, "new": bool(slot) and not known_before,
            "slot_ko": next((x["ko"] for x in notebook_slots(st, uid, r) if x["key"] == slot), None) if slot else None,
            "line": fill_text(line, st, r, item), "line_key": f"reveal.{kind}.{i}" if line else None}


def notebook_public(st: dict, uid: str, r: dict) -> dict:
    kn = nb_known(st, r["id"])
    rows = []
    for x in notebook_slots(st, uid, r):
        k = x["key"] in kn
        rows.append({"key": x["key"], "kind": x["kind"], "kind_ko": KIND_KO.get(x["kind"]), "known": k,
                     "ko": x["ko"] if k else None, "how": (kn.get(x["key"]) or {}).get("how"),
                     "day": (kn.get(x["key"]) or {}).get("day")})
    return {"slots": rows, "known": sum(1 for x in rows if x["known"]), "total": len(rows)}


def repeat_line(st: dict, uid: str, item: dict, target, out: dict) -> dict | None:
    """같은 세션 같은 사람 두 번째 — 그 사람이 「{other} 님 드려 보세요」(값은 안에서 ×0.8 그대로)."""
    if not isinstance(target, dict) or not target.get("resident_id"):
        return None
    if not any(d.get("kind") == "same_person_today" for d in out.get("diminish") or []):
        return None
    r = next((x for x in st.get("residents_list") or [] if x["id"] == target["resident_id"]), None)
    if not r:
        return None
    rank = {"chain_beat": 0, "memory": 1, "need": 2, "like": 3, "warm": 4, "not_for_me": 9}
    cands = []
    for o in st.get("residents_list") or []:
        if o["id"] == r["id"] or o["id"] in (st.get("outside") or []):
            continue
        t, _ = resident_tier(st, uid, o, item)
        given = sum(1 for g in cres(st, o["id"])["given"] if same_session(st, g))
        cands.append((rank.get(t, 5), given, o["name"], o))
    if not cands:
        return None
    other = min(cands, key=lambda x: x[:3])[3]
    line, i = _rot(st, f"repeat.{r['id']}", role_taste(r.get("role", "")).get("repeat_lines") or [])
    line = line or "{other} 님 드려 보세요. 저는 오늘 많이 받았어요."
    return {"line": fill_text(line, st, r, item, other["name"]), "other_id": other["id"], "other_name": other["name"],
            "line_key": f"resident_tastes.roles.{r.get('role')}.repeat_lines.{i}" if i is not None else None}


def gossip_tick(st: dict, uid: str, ss: dict) -> dict | None:
    """그날 첫 저녁 세션: 가장 많이 받은 사람의 모르는 칸 하나를 다른 주민·관리실이 흘린다."""
    c = core_of(st)
    day = day_of(st)
    if NB_GOSSIP_PER_EVENING <= 0 or not is_evening() or (c.get("gossip") or {}).get("day") == day or not ss.get("new"):
        return None
    ppl = [r for r in st.get("residents_list") or []]
    if not ppl:
        return None
    def _unk(r_):
        return [x for x in notebook_slots(st, uid, r_) if x["key"] not in nb_known(st, r_["id"]) and x["kind"] in ("like", "need", "dislike")]
    left = [r_ for r_ in ppl if _unk(r_)]             # S29: 5일째부터 멈추던 것 — 빈칸이 있는 사람 중에서 고른다
    top = max(left, key=lambda r: (len(cres(st, r["id"])["given"]), r["id"])) if left else ppl[0]
    unknown = _unk(top) if left else []
    if not unknown:
        c["gossip"] = {"day": day, "none": True}
        return None
    rng = random.Random(f"{uid}|{day}|gossip")
    slot = unknown[0] if len(unknown) == 1 else rng.choice(unknown)
    others = [r for r in ppl if r["id"] != top["id"]]
    teller = rng.choice(others) if others and rng.random() < 0.7 else None
    N = moments().get("notebook") or {}
    lines = (N.get("gossip_resident") if teller else N.get("gossip_office")) or N.get("gossip") or []
    line, _ = _rot(st, "gossip", lines)
    line = line or ("{other} 님 말로는, {name} 님이 「{ko}」 쪽을 반가워하신답니다." if teller
                    else "관리실에서 귀띔해 드립니다. {name} 님은 「{ko}」 쪽에 마음이 가신다고 합니다.")
    line = fill_text(line, st, top, None, teller["name"] if teller else "관리실", ko=slot["ko"], kind_ko=KIND_KO.get(slot["kind"], ""))
    nb_known(st, top["id"])[slot["key"]] = {"day": day, "how": "gossip"}
    g = {"day": day, "resident_id": top["id"], "name": top["name"], "slot": slot["key"], "kind": slot["kind"], "ko": slot["ko"],
         "teller_id": teller["id"] if teller else None, "line": line}
    c["gossip"] = g
    overnight_add(st, "notebook_tip", {k: v for k, v in g.items() if k != "day"})
    return g


class PrefsIn(BaseModel):
    uid: str
    labels_always: bool | None = None


@app.post("/api/prefs")
def set_prefs(inp: PrefsIn):
    st = load_state(inp.uid)
    pr = st.setdefault("prefs", {})
    if inp.labels_always is not None:
        pr["labels_always"] = bool(inp.labels_always)
    save_state(inp.uid, st)
    return {"ok": True, "prefs": {"labels_always": bool(pr.get("labels_always"))},
            "label_ko": (moments().get("notebook") or {}).get("labels_always_label") or "늘 이름표 보기"}


# ② 받는 저녁, 한 상 ─────────────────────────────────────────────
def table_candidates(st: dict) -> list:
    day = day_of(st)
    out, seen = [], set()
    rows = list(st.get("shelf") or []) + list(st.get("stored") or [])
    today = [rec for rec in core_of(st)["scans"].values() if int(rec.get("day") or 0) == day]
    today_ids = {(rec.get("item") or {}).get("card_id") for rec in today}
    rows.sort(key=lambda x: (x.get("card_id") not in today_ids, x.get("category") not in ("food", "drink")))
    for it in rows:
        rid = it.get("card_id") or it.get("id")
        if not rid or rid in seen:
            continue
        seen.add(rid)
        out.append({"relic_id": rid, "name": it.get("relic_name") or it.get("name"), "category": it.get("category"),
                    "today": rid in today_ids})
        if len(out) >= 8:
            break
    return out


def evening_table_public(st: dict, uid: str) -> dict | None:
    """그날 첫 저녁 세션(17~5시)에 한 상. 이미 차렸으면 done 과 결과."""
    daytime = not is_evening()
    if (daytime and not DAYTIME_TABLE) or (CALENDAR_ENFORCE and not is_unlocked(st, "evening_table")):
        return None
    c = core_of(st)
    day = day_of(st)
    tb = c.get("table") or {}
    E = (moments().get("daytime_table") or {}) if daytime else (moments().get("evening") or {})
    if tb.get("day") == day:
        return {"open": False, "done": True, "result": tb.get("result")}
    by = {r["id"]: r for r in st.get("residents_list") or []}
    returned = []
    for rid, cr in (c.get("res") or {}).items():
        for g in cr.get("given") or []:
            if int(g.get("day") or 0) == day and rid in by:
                returned.append({"name": g.get("name"), "to_name": by[rid]["name"], "resident_id": rid})
    for v in (c["visits"].get("rows") or []) if c["visits"].get("day") == day else []:
        if v.get("kind") in ("visitor", "night_visitor"):
            returned.append({"visitor_id": v.get("visitor_id"), "name": v.get("ko"), "room": v.get("room")})
    op = E.get("open") or []
    open_line = random.Random(f"{uid}|{day}|{'daytime' if daytime else 'evening'}").choice(op) if op else None
    return {"open": True, "done": False, "daytime": daytime, "open_ko": open_line, "table_prompt": E.get("table_prompt"),
            "seat_prompt": E.get("seat_prompt"), "returned": returned,
            "candidates": {"items": table_candidates(st),
                           "residents": [{"id": r["id"], "name": r["name"], "role": r.get("role")}
                                         for r in st.get("residents_list") or [] if r["id"] not in (st.get("outside") or [])]},
            "food_cost": ET_FOOD, "table_store": int(c.get("table_store") or 0)}


class TableIn(BaseModel):
    uid: str
    relic_id: str
    seats: list[list[str]]


@app.post("/api/table")
def table(inp: TableIn):
    st = load_state(inp.uid)
    tick_production(st)
    c = core_of(st)
    day = day_of(st)
    require_unlocked(st, "evening_table")
    daytime = not is_evening()
    if daytime and not DAYTIME_TABLE:
        raise HTTPException(400, "한 상은 저녁에 차립니다")
    if (c.get("table") or {}).get("day") == day:
        raise HTTPException(400, "오늘 상은 이미 차렸습니다")
    by = {r["id"]: r for r in st.get("residents_list") or []}
    if len(inp.seats) != 1 or len(inp.seats[0]) != 2 or len(set(inp.seats[0])) != 2 or any(x not in by for x in inp.seats[0]):
        raise HTTPException(400, "마주 앉을 두 분을 골라 주세요")
    row = next((x for x in st.get("shelf") or [] if x.get("card_id") == inp.relic_id), None) or \
        next((x for x in st.get("stored") or [] if x.get("id") == inp.relic_id or x.get("card_id") == inp.relic_id), None)
    it = item_from_row(row) if row else ((c["scans"].get(inp.relic_id) or {}).get("item"))
    if not it:
        raise HTTPException(400, "상에 올릴 물건이 없습니다")
    a, b = by[inp.seats[0][0]], by[inp.seats[0][1]]
    # 식량: 한 상 몫부터, 모자라면 재고에서, 그래도 모자라면 물건만(no_food_ok)
    need = ET_FOOD
    paid_store = min(need, int(c.get("table_store") or 0))
    c["table_store"] = int(c.get("table_store") or 0) - paid_store
    need -= paid_store
    paid_food = 0
    if need and int(st["resources"].get("food", 0)) >= need:
        st["resources"]["food"] -= need
        paid_food = need
    elif need and not ET_NO_FOOD_OK:
        c["table_store"] += paid_store
        raise HTTPException(400, "식량이 모자랍니다")
    la = any(match(x, it) for x in likes_of(inp.uid, a))
    lb = any(match(x, it) for x in likes_of(inp.uid, b))
    delta = ET_TRUST[2] if la and lb else ET_TRUST[1] if la or lb else ET_TRUST[0]
    pair = sorted([a["id"], b["id"]])
    last = (c.get("table_last") or {}).get("pair")
    repeat = last == pair
    if repeat:
        delta = max(1, int(round(delta * ET_REPEAT)))
    for x, y in ((a, b), (b, a)):
        x.setdefault("trust", {})[y["id"]] = min(TRUST_MAX, int(x["trust"].get(y["id"], 0)) + delta)
    # 대화 한 장면
    E = moments().get("evening") or {}
    T = E.get("talk") or {}
    pairs = T.get("pairs") or {}
    used = c.setdefault("table_talk_used", [])
    key, flip = None, False
    for k_, f_ in ((f"{a.get('role')}+{b.get('role')}", False), (f"{b.get('role')}+{a.get('role')}", True)):
        if k_ in pairs:
            key, flip = k_, f_
            break
    talk = None
    if key:
        opts = [i for i in range(len(pairs[key])) if f"{key}|{i}" not in used]
        if opts:
            i = opts[0]
            used.append(f"{key}|{i}")
            talk, tk = pairs[key][i], f"evening.talk.pairs.{key}.{i}"
    DT = moments().get("daytime_table") or {}
    if talk is None and daytime and DT.get("generic"):
        talk, gi = _rot(st, "daytime_table.generic", DT.get("generic") or [])
        tk = f"daytime_table.generic.{gi}"
    if talk is None:
        g = (T.get("generic") or {}).get(it.get("category") if it.get("category") in ("food", "drink") else "other") or []
        talk, gi = _rot(st, f"table_generic.{it.get('category')}", g)
        tk = f"evening.talk.generic.{it.get('category') if it.get('category') in ('food', 'drink') else 'other'}.{gi}"
    pa, pb = (b, a) if flip else (a, b)

    def f_(t):
        return (t or "").replace("{a_name}", pa["name"]).replace("{b_name}", pb["name"]).replace("{item}", it.get("name") or "그것")
    lines = [{"who": pa["id"], "name": pa["name"], "line": f_((talk or {}).get("a"))},
             {"who": pb["id"], "name": pb["name"], "line": f_((talk or {}).get("b"))}] if talk else []
    promise, _ = _rot(st, "evening.promise", E.get("promise") or [])
    if daytime:
        promise, _ = _rot(st, "daytime_table.close", DT.get("close") or [])
    result = {"daytime": daytime, "pair": pair, "names": [a["name"], b["name"]], "item": it.get("name"), "relic_id": inp.relic_id,
              "trust_delta": delta, "liked_by": [x["id"] for x, l in ((a, la), (b, lb)) if l], "repeat_pair": repeat,
              "food_paid": paid_food, "table_store_paid": paid_store, "talk": lines, "talk_key": tk, "promise": promise}
    c["table"] = {"day": day, "result": result}
    c["table_last"] = {"day": day, "pair": pair}
    session_note(st, f"한 상 — {a['name']}·{b['name']}")
    day_note(st, "table", f"{a['name']}·{b['name']}")
    save_state(inp.uid, st)
    log(inp.uid, "table", {"pair": pair, "delta": delta, "relic": inp.relic_id})
    return {"ok": True, **result, "state": public_state(st, inp.uid)}


def night_visitor_tick(st: dict, uid: str) -> dict | None:
    """밤 손님(visitors.json night_visitors): hours_from 시 이후 하루 한 번, 불 켜진 방 창에. 다음 날 아침 흔적."""
    if not NIGHT_VISITORS:
        return None
    c = core_of(st)
    day = day_of(st)
    if c["flags"].get("night_visit_day") == day:
        return None
    h = now_hour()
    first_h = min(int(x.get("hours_from", 19)) for x in NIGHT_VISITORS)
    ok_ = list(NIGHT_VISITORS) if (h >= first_h or h < 5) else []   # S30 r7-3: 19시 세션에도 넷 모두(시각은 첫 손님 기준)
    if not ok_:
        return None
    last = c["flags"].get("night_visit_last")
    pool = [x for x in ok_ if x["id"] != last] or ok_          # S29 r6-4: 이틀 연속 같은 손님 없음
    v = random.Random(f"{uid}|{day}|night_visitor").choice(pool)
    rooms = [r for r in live_rooms(st) if light_on(st, r["slot"])]
    if not rooms:
        return None
    rooms.sort(key=lambda r: (r["id"] != "quarters", r["slot"]))
    rm = rooms[0]
    rname = (ROOMS.get(rm["id"]) or {}).get("name", rm["id"])
    c["flags"]["night_visit_day"] = day
    c["flags"]["night_visit_last"] = v["id"]
    arr = v.get("arrival") or []
    line, _ = _rot(st, f"night.{v['id']}", arr)
    row = {"day": day, "slot": rm["slot"], "room": rname, "kind": "night_visitor", "visitor_id": v["id"], "ko": v.get("ko"),
           "sprite": v.get("sprite"), "where": v.get("where"), "line": (line or "").replace("{room}", rname),
           "first": v["id"] not in c["visitors_seen"]}
    if c["visits"].get("day") != day:
        c["visits"] = {"day": day, "rows": []}
    c["visits"].setdefault("rows", []).append(row)
    if v["id"] not in c["visitors_seen"]:
        c["visitors_seen"].append(v["id"])
    mt = v.get("morning_trace") or []
    if mt:
        t = random.Random(f"{uid}|{day}|nighttrace").choice(mt).replace("{room}", rname)
        c["morning_next"].append({"day": day + 1, "kind": "night_trace", "text": t})
    return row


# ③ 내일의 부탁 · 이름 투표 어긋남 ─────────────────────────────────────
def tomorrow_ask(st: dict, uid: str) -> dict | None:
    """내일 실제로 뜰 필요 하나(같은 시드 — 내일 need_today 와 같다)를 미리 한 줄로."""
    day = day_of(st) + 1
    ppl = [r for r in st.get("residents_list") or [] if need_today(uid, r, day)]
    if not ppl:
        return None
    r = random.Random(f"{uid}|{day}|tomorrow_ask").choice(ppl)
    nd = need_today(uid, r, day)
    tm = ((role_taste(r.get("role", "")).get("tomorrow") or {}).get("needs") or [])
    lines = tm[nd["idx"]] if nd["idx"] < len(tm) else None
    if not lines:
        lines = role_taste(r.get("role", "")).get("tomorrow_ask") or []
    if not lines:
        lines = (NEXT_VISIT.get("promises") or {}).get("tomorrow_ask") or []
    if isinstance(lines, str):
        lines = [lines]
    t = random.Random(f"{uid}|{day}|tomorrow_line|{r['id']}").choice(lines) if lines else \
        "내일 아침 {name} 님이 「{ko}」 쪽 물건을 찾으실 것 같습니다."
    return {"resident_id": r["id"], "name": r["name"], "day": day, "need": {k: nd[k] for k in ("category", "subtype", "ko")},
            "line": fill_text(t, st, r, None, None, ko=nd["ko"])}


def vote_mismatch(st: dict, item: dict) -> bool:
    """전역 이름이 정해진(3곳·60%) 바코드를 이 방주가 다르게 정했나."""
    code = item.get("barcode")
    if not code:
        return False
    bm = (st.get("barcodes") or {}).get(code) or {}
    if not bm.get("subtype"):
        return False
    sug = subtype_vote_suggest(code, item.get("category") or bm.get("category") or "")
    return bool(sug and sug["id"] != bm["subtype"])


# ── S24 안전 목록 (찾으러 보내는 것) ─────────────────────────────────
_SAFE = CORE_A.get("safe_targets") or {}
SAFE_EXCLUDE_CATS = set(_SAFE.get("exclude_categories") or ["tobacco"])
SAFE_EXCLUDE_SUBS = {k: set(v) for k, v in (_SAFE.get("exclude_subtypes") or {"drink": ["alcohol"]}).items()
                     if not str(k).startswith("_")}
SAFE_ONLY_SUBS = {k: list(v) for k, v in (_SAFE.get("allow_only_subtypes") or {"medical": ["bandage"]}).items()
                  if not str(k).startswith("_")}      # 의약은 붕대만(시나리오·PM 합의)


def safe_rule(rule, strict: bool = False):
    """찾으러 보낼 수 있는 규칙만. 갈래가 막힌 목록이면 None, 하위 종류에 막힌 것이 섞였으면 그것만 뺀다(남는 게 없으면 None).
    strict=True(기억 칸·귀띔)면 하위 종류가 없는 갈래 전체 규칙도, 그 갈래에 막힌 종류가 있으면 그대로 둔다(갈래 이름만 보이므로).
    갈래 전체 조건(예: 의약 아무거나)은 막힌 종류로 채울 수도 있지만 '그걸 찾아오라'는 말은 아니라 남긴다."""
    if not isinstance(rule, dict):
        return rule
    cat = rule.get("category")
    if cat in SAFE_EXCLUDE_CATS:
        return None
    sub = rule.get("subtype")
    if cat in SAFE_ONLY_SUBS:                          # 허용 목록 갈래: 하위 종류가 없으면 허용된 것으로 좁힌다
        subs = (sub if isinstance(sub, list) else [sub]) if sub else list(SAFE_ONLY_SUBS[cat])
        ok_ = [x for x in subs if x in SAFE_ONLY_SUBS[cat]]
        if not ok_:
            return None
        return dict(rule, subtype=ok_) if ok_ != (sub if isinstance(sub, list) else [sub] if sub else None) else rule
    if sub:
        subs = sub if isinstance(sub, list) else [sub]
        ok_ = [x for x in subs if x not in SAFE_EXCLUDE_SUBS.get(cat, set())]
        if not ok_:
            return None
        if len(ok_) != len(subs):
            return dict(rule, subtype=ok_)
    return rule


def item_rule_safe(rule) -> bool:
    """좋아함 규칙이 안전한가 — 갈래가 막혔거나, 허용 목록 갈래(의약)에서 허용 밖 종류만 가리키면 거짓."""
    if not isinstance(rule, dict):
        return True
    cat = rule.get("category")
    if cat in SAFE_EXCLUDE_CATS:
        return False
    sub = rule.get("subtype")
    subs = (sub if isinstance(sub, list) else [sub]) if sub else []
    if cat in SAFE_ONLY_SUBS:
        return bool(subs) and all(x in SAFE_ONLY_SUBS[cat] for x in subs)
    return not subs or any(x not in SAFE_EXCLUDE_SUBS.get(cat, set()) for x in subs)


def item_safe(item: dict) -> bool:
    """이 물건을 '권해도' 되나(찍은 물건 하나 기준)."""
    cat, sub = item.get("category"), item.get("subtype")
    if cat in SAFE_EXCLUDE_CATS:
        return False
    if cat in SAFE_ONLY_SUBS:
        return sub in SAFE_ONLY_SUBS[cat]
    return sub not in SAFE_EXCLUDE_SUBS.get(cat, set())


def safety_audit() -> list:
    """데이터에서 안전 목록 밖으로 찾으러 보내는 곳(필요·사슬 건네기 조건). 기동 로그와 테스트가 읽는다."""
    bad = []
    for role, rt in (TASTES.get("roles") or {}).items():
        for i, n in enumerate(rt.get("needs") or []):
            if safe_rule(n) != n:
                bad.append(f"needs:{role}:{i}")
    for a in ARCS:
        for b in a.get("beats") or []:
            trig = b.get("trigger") or {}
            for x in [trig] + [y for y in (trig.get("any_of") or []) if isinstance(y, dict)]:
                for key in ("give", "give_distinct"):
                    v = x.get(key)
                    if isinstance(v, dict) and safe_rule({"category": v.get("category"), "subtype": v.get("subtype")}) != \
                            {"category": v.get("category"), "subtype": v.get("subtype")}:
                        bad.append(f"arc:{a['id']}:{b.get('step')}:{key}")
    return bad


_SAFETY_BAD = safety_audit()
if _SAFETY_BAD:
    print(f"[safety] 안전 목록 밖으로 찾으러 보내는 데이터 {len(_SAFETY_BAD)}곳 — 서버가 걸러 낸다: {_SAFETY_BAD}")


# ── S25 첫 주 해금 달력 (docs/FIRST_WEEK_CALENDAR.md · data/balance/unlock_calendar.json) ──────────
UNLOCK_CAL = _live_or_draft("balance/unlock_calendar.json")
CALENDAR_ENFORCE = True          # 옛 스위트(S13~S24)는 달력 전 기능을 시험하므로 테스트에서만 끈다
FEATURES_ALWAYS = {"scan", "give_where_labels"}


def unlocked_set(st: dict) -> set:
    """켠 날 차례(비트와 같은 셈)까지 열린 기능 + 조건 해금(가보 = 첫 귀함 이상 카드)."""
    p = max(1, play_day(st))
    out = set(FEATURES_ALWAYS)
    for d, row in (UNLOCK_CAL.get("days") or {}).items():
        if str(d).isdigit() and int(d) <= p:
            out |= set((row or {}).get("unlocks") or [])
    hc = (UNLOCK_CAL.get("conditional") or {}).get("heirloom") or {}
    fl_ = core_of(st)["flags"]
    if fl_.get("first_rare_day") is not None and p >= int(hc.get("min_play_day") or 1) and (
            fl_.get("heir_open_day") is not None or int(hc.get("min_play_day") or 1) <= 1):
        out.add("heirloom")                           # PM 첫 세션: 1·2일째는 고를 근거가 없다 → 3일째부터
    return out


def is_unlocked(st: dict, feat: str) -> bool:
    if not CALENDAR_ENFORCE:
        return True
    return feat in unlocked_set(st)


def require_unlocked(st: dict, feat: str) -> None:
    if CALENDAR_ENFORCE and not is_unlocked(st, feat):
        raise HTTPException(403, "아직 열리지 않았습니다")


def unlocked_public(st: dict) -> dict:
    p = max(1, play_day(st))
    nxt = (UNLOCK_CAL.get("days") or {}).get(str(p + 1)) or {}
    return {"play_day": p, "features": sorted(unlocked_set(st)) if CALENDAR_ENFORCE else ["*"],
            "next": {"play_day": p + 1, "unlocks": nxt.get("unlocks") or [],
                     "teaser": (unlock_teaser(st) or {}).get("line")} if nxt else None}      # 문장 정본 = beats.json teaser


def unlock_teaser(st: dict) -> dict | None:
    """떠날 때 카드: 내일(다음 켠 날) 열릴 것 예고. 문장의 정본은 beats.json days[오늘 켠 날].teaser(PM 결정)."""
    if not CALENDAR_ENFORCE:
        return None
    p = max(1, play_day(st))
    nxt = (UNLOCK_CAL.get("days") or {}).get(str(p + 1)) or {}
    b = BEATS.get(str(p)) or {}
    if not nxt.get("unlocks") or not b.get("teaser"):
        return None
    oc = (st.get("octopus") or {}).get("name") or "문어"
    return {"play_day": p + 1, "unlocks": nxt.get("unlocks") or [], "line": str(b["teaser"]).replace("{oct_name}", oc),
            "required": bool(b.get("teaser_required"))}


def unlock_new(st: dict, uid: str = "", heir_screen: bool | None = None) -> list:
    """이번 켠 날에 처음 열린 기능의 방송(ui_moments.unlock.<기능>). 한 번만.
    S31: 가보 칸 방송은 고를 화면(가보 후보가 있는 「어디로」)이 있을 때만 — 없으면 미룬다."""
    if not CALENDAR_ENFORCE:
        return []
    c = core_of(st)
    shown = c["flags"].setdefault("unlock_shown", [])
    U = moments().get("unlock") or {}
    out = []
    for f in sorted(unlocked_set(st)):
        if f in shown or f in FEATURES_ALWAYS:
            continue
        if f == "heirloom" and HEIR_BROADCAST_NEEDS_SCREEN:
            ok_ = heir_screen if heir_screen is not None else heir_choosable(st, uid)
            if not ok_:
                continue
        shown.append(f)
        ln = U.get(f)
        if isinstance(ln, list):
            ln = ln[0] if ln else None
        if isinstance(ln, str):
            out.append({"feature": f, "line": ln})
    return out


# ── S25 가보 칸 (docs/HEIRLOOM.md · core_a.heirloom) ──────────────────────────
HEIR = CORE_A.get("heirloom") or {}
HEIR_MIN = HEIR.get("min_rarity", "rare")
HEIR_V = float(HEIR.get("outcome_V", 1.2))
HEIR_POLISH_DAYS = int((HEIR.get("polish_ascend") or {}).get("distinct_days", 6))
HEIR_RARE_P = {k: float(v) for k, v in ((HEIR.get("display_rare_visitor") or {}).get("daily_chance") or {"epic": 0.2, "legendary": 0.35}).items()}
HEIR_DISPLAY_MIN = (HEIR.get("display_rare_visitor") or {}).get("min_rarity", "epic")


def _rk(r: str | None) -> int:
    return RARITY_KEYS.index(r) if r in RARITY_KEYS else 0


def heir_tier(rarity: str | None, polish_lv: int = 1) -> str:
    """가보로서의 등급 — 닦기 3단계면 한 단계 위(전설까지)."""
    i = _rk(rarity) + (1 if polish_lv >= 3 and _rk(rarity) >= _rk(HEIR_MIN) else 0)
    return RARITY_KEYS[min(i, len(RARITY_KEYS) - 1)]


def item_polish(st: dict, item: dict) -> int:
    bc = item.get("barcode")
    it = shelf_item_for(st, bc) if bc else None
    if not it:
        it = next((x for x in st.get("stored") or [] if x.get("barcode") == bc), None) if bc else None
    return polish_level(it) if it else 1


def heirloom_owner(st: dict, barcode: str | None) -> dict | None:
    if not barcode:
        return None
    return next((r for r in st.get("residents_list") or [] if (r.get("heirloom") or {}).get("barcode") == barcode), None)


def heirloom_public(r: dict) -> dict | None:
    h = r.get("heirloom")
    if not h:
        return None
    return {k: h.get(k) for k in ("card_id", "name", "category", "subtype", "rarity", "tier", "since_day", "boxed", "prop")} | \
        {"history": list(r.get("heirloom_history") or [])}


def heirloom_options(st: dict, uid: str, item: dict) -> list:
    """귀함 이상 카드의 「어디로」에 붙는 「가보로 · ○○」 — 빈 칸이거나 지금 가보보다 등급이 낮은 사람. 바코드가 이미 누군가의 가보면 없다."""
    if CALENDAR_ENFORCE and not is_unlocked(st, "heirloom"):
        return []
    tier = heir_tier(item.get("rarity"), item_polish(st, item))
    if _rk(tier) < _rk(HEIR_MIN) or heirloom_owner(st, item.get("barcode")) or not item_safe(item):
        return []
    lab = (moments().get("heirloom") or {}).get("option_label") or "가보로"
    out = []
    order = [r["id"] for r in st.get("residents_list") or []]
    for r in sorted(st.get("residents_list") or [], key=lambda r: order.index(r["id"])):
        if r["id"] in (st.get("outside") or []):
            continue
        h = r.get("heirloom")
        if h and _rk(h.get("tier")) >= _rk(tier):
            continue
        if join_day(st, r) >= day_of(st) and day_of(st) > 1:
            continue                                  # S29: 오늘 들어온 사람은 내일부터(첫날 가보·세 번째 기억 방지)
        t_, _ = resident_tier(st, uid, r, item)
        if t_ == "not_for_me":
            continue                                  # S27 r5-2: 돌려줄 사람에게는 가보로 권하지 않는다
        out.append({"kind": "heirloom", "target": {"resident_id": r["id"], "heirloom": True}, "name": r["name"],
                    "label": f"{lab} · {r['name']}", "tier": tier, "value": HEIR_V, "swap": bool(h),
                    "current": heirloom_public(r), "hint_ko": heir_fit_hint(st, r, item)})
    base = len(out)
    while len(out) < 2:                               # S29: 하나면 하나 더 · S31: 0이면 가까운 사람 둘(보장 귀함이 갈 데가 없던 r8-1)
        nx = heirloom_second(st, uid, item, tier, {o["target"]["resident_id"] for o in out})
        if not nx:
            break
        if nx:
            r = nx
            H = moments().get("heirloom") or {}
            out.append({"kind": "heirloom", "target": {"resident_id": r["id"], "heirloom": True}, "name": r["name"],
                        "label": f"{lab} · {r['name']}", "tier": tier, "value": HEIR_V, "swap": bool(r.get("heirloom")),
                        "current": heirloom_public(r), "second": base > 0 or len(out) > 0, "near": True,
                        "more_ko": (H.get("more_label") if isinstance(H.get("more_label"), str) else "다른 분도 보여 드릴까요?")
                        if (base > 0 or len(out) > 0) else None,
                        "hint_ko": heir_fit_hint(st, r, item)})
    return out


def heirloom_prepare(st: dict, uid: str, item: dict, target: dict) -> dict:
    r = next((x for x in st.get("residents_list") or [] if x["id"] == target.get("resident_id")), None)
    if not r:
        raise HTTPException(400, "없는 사람입니다")
    require_unlocked(st, "heirloom")
    tier = heir_tier(item.get("rarity"), item_polish(st, item))
    if _rk(tier) < _rk(HEIR_MIN):
        raise HTTPException(400, "가보는 귀함 이상만 됩니다")
    own = heirloom_owner(st, item.get("barcode"))
    if own and own["id"] != r["id"]:
        raise HTTPException(400, f"이 물건은 이미 {own['name']} 님의 가보입니다")
    if not item_safe(item):
        raise HTTPException(400, "그 물건은 가보로 두지 않습니다")
    h = r.get("heirloom")
    if h and not target.get("swap"):
        H = moments().get("heirloom") or {}
        t = (H.get("ask_swap") or "{name} 님은 이미 「{old}」를 아끼십니다. 「{new}」로 바꿀까요?")
        return {"ask_swap": {"resident_id": r["id"], "current": heirloom_public(r),
                             "new": {"name": item.get("name"), "rarity": item.get("rarity"), "tier": tier},
                             "line": t.replace("{name}", r["name"]).replace("{old}", h.get("name") or "").replace("{new}", item.get("name") or ""),
                             "default": "keep"}}
    return {"tier": tier}


def heirloom_place(st: dict, uid: str, item: dict, target: dict, out: dict) -> dict:
    """보통 건네기를 마친 뒤 가보 칸에 둔다(값 1.2V). 바꾸면 옛 가보는 선반으로, 이력·열린 기억은 남는다."""
    day = day_of(st)
    r = next(x for x in st.get("residents_list") or [] if x["id"] == target["resident_id"])
    H = moments().get("heirloom") or {}
    rt = role_taste(r.get("role", "")).get("heirloom") or {}
    pol = item_polish(st, item)
    tier = heir_tier(item.get("rarity"), pol)
    old = r.get("heirloom")
    swapped = None
    if old:
        r.setdefault("heirloom_history", []).append({"name": old.get("name"), "from_day": old.get("since_day"), "to_day": day,
                                                     "tier": old.get("tier")})
        where_back = return_to_shelf(st, old.get("row")) if old.get("row") else "shelf"
        swapped = {"old": old.get("name"), "back_to": where_back}
    res = cres(st, r["id"])
    row = next((it.get("row") for it in reversed(res["items"]) if it.get("card_id") == item.get("card_id")), None)
    if row is not None:                                # 가보는 머리맡 목록에서 칸으로 옮긴다(row 는 가보가 들고 있다)
        res["items"] = [it for it in res["items"] if it.get("card_id") != item.get("card_id")]
    r["heirloom"] = {"card_id": item.get("card_id"), "barcode": item.get("barcode"), "name": item.get("name"),
                     "category": item.get("category"), "subtype": item.get("subtype"), "rarity": item.get("rarity"),
                     "tier": tier, "since_day": day, "row": row, "seen_days": [day], "boxed": False,
                     "prop": prop_for_item(item)}
    out["value"] = HEIR_V
    lines = {}
    fill = lambda t: fill_text(t, st, r, item)
    ln, _ = _rot(st, "heirloom.placed", H.get("placed") or [])
    lines["placed"] = fill(ln) or fill("{name} 님이 「{item}」를 가보로 받으셨습니다. 금테 받침 위에 놓였습니다.")
    if swapped:
        ln, _ = _rot(st, "heirloom.swapped", H.get("swapped") or [])
        lines["swapped"] = (ln or "「{old}」는 선반으로 돌아가고, 「{new}」가 그 자리에 놓였습니다.").replace("{name}", r["name"]) \
            .replace("{old}", swapped["old"] or "").replace("{new}", item.get("name") or "")
    if any(match(x, item) for x in likes_of(uid, r)):
        ln, _ = _rot(st, "heirloom.fits", H.get("fits") or [])
        lines["fits"] = fill(ln) or fill("{name} 님 손에 어울리는 가보입니다.")
    lines.update(heirloom_tier_lines(st, r, item, tier))
    session_note(st, lines["placed"])
    log(uid, "heirloom", {"resident": r["id"], "tier": tier, "swap": bool(swapped)})
    return {"resident_id": r["id"], "tier": tier, "swapped": swapped, "lines": lines,
            "third_memory": lines.get("third_memory"), "heirloom": heirloom_public(r)}


def heirloom_tier_lines(st: dict, r: dict, item: dict, tier: str) -> dict:
    """귀함: 쓰는 모습 / 진귀함: 대사의 주어 / 전설: 세 번째 기억(사람마다 한 번, 닫히지 않음)."""
    rt = role_taste(r.get("role", "")).get("heirloom") or {}
    out = {}
    fill = lambda t: fill_text(t, st, r, item)
    use = rt.get("use") or []
    if use:
        out["use"] = fill(random.Random(f"{r['id']}|{item.get('card_id')}|use").choice(use))
    else:
        out["use"] = fill("{name} 님이 「{item}」를 손 닿는 데 두고 쓰십니다.")
    if _rk(tier) >= _rk("epic"):
        sp = rt.get("speak") or []
        out["speak"] = fill(random.Random(f"{r['id']}|{item.get('card_id')}|speak").choice(sp)) if sp else \
            fill("「{item}」 옆에 있으면 일이 손에 잘 붙어요.")
        r["arc_line"] = out["speak"]
    if _rk(tier) >= _rk("legendary") and not r.get("third_memory_open"):
        tm = rt.get("third_memory") or {}
        r["third_memory_open"] = True
        r["third_memory"] = {"id": tm.get("id") or f"third_{r.get('role')}", "day": day_of(st)}
        out["third_memory"] = {"id": r["third_memory"]["id"],
                               "announce": fill(tm.get("announce") or "관리실에서 알려 드립니다. 「{item}」를 받으신 뒤로 {name} 님이 옛날 이야기를 하나 꺼내셨습니다."),
                               "line": fill(tm.get("line") or "이건 아주 옛날 이름인데요. 가라앉기 전 하루를 아직 기억해요.")}
        overnight_add(st, "third_memory", {"resident_id": r["id"], "name": r["name"], **out["third_memory"]})
    return out


def heirloom_polish_tick(st: dict, uid: str, code: str) -> dict | None:
    """가보 바코드를 서로 다른 날 찍은 수가 닦기 3단계 문턱(6일)에 닿으면 가보로서 한 등급 위."""
    r = heirloom_owner(st, code)
    if not r:
        return None
    h = r["heirloom"]
    day = day_of(st)
    seen = h.setdefault("seen_days", [])
    if day in seen:
        return None
    seen.append(day)
    if h.get("ascended") or len(seen) < HEIR_POLISH_DAYS or _rk(h.get("tier")) >= len(RARITY_KEYS) - 1:
        return None
    h["tier"] = RARITY_KEYS[_rk(h.get("tier")) + 1]
    h["ascended"] = True
    it = {"name": h.get("name"), "card_id": h.get("card_id"), "category": h.get("category")}
    H = moments().get("heirloom") or {}
    ln, _ = _rot(st, "heirloom.ascend", H.get("ascend") or [])
    out = {"resident_id": r["id"], "tier": h["tier"], "line": fill_text(ln or "{name} 님의 「{item}」, 손때가 앉아 한층 귀해졌습니다.", st, r, it)}
    out.update(heirloom_tier_lines(st, r, it, h["tier"]))
    return out


def display_rare_chance(st: dict, slot) -> float:
    """그 방 꾸밈 칸에 걸린 가장 귀한 물건(닦아 오르기 포함)이 진귀함 이상이면 드문 손님 하루 확률."""
    best = None
    for it in decor_items(st, slot):
        if it.get("boxed"):
            continue
        t = heir_tier(it.get("rarity"), polish_level(it.get("row") or {}) if it.get("row") else 1)
        if _rk(t) >= _rk(HEIR_DISPLAY_MIN) and (best is None or _rk(t) > _rk(best)):
            best = t
    return float(HEIR_RARE_P.get(best, 0.0)) if best else 0.0


def first_rare_tick(st: dict, card_d: dict) -> bool:
    """가보 칸 해금 = 첫 귀함 이상 카드(달력 conditional)."""
    f = core_of(st)["flags"]
    if f.get("first_rare_day") is None and _rk(card_d.get("rarity")) >= _rk(HEIR_MIN):
        f["first_rare_day"] = day_of(st)
        return True
    return False


# ── S26 물 빼기 · 하루 소비 (economy.json drain · daily_consumption_server) ─────────────
_DRAIN = _ECON_ALL.get("drain") or {}
DRAIN_BY_DEPTH = {int(k): {kk: int(vv) for kk, vv in (v or {}).items() if not str(kk).startswith("_")}
                  for k, v in (_DRAIN.get("by_depth_m") or {}).items() if str(k).isdigit()}
DRAIN_RECLAIM = float(_DRAIN.get("reclaim_mult", 0.5))
_DCS = _ECON_ALL.get("daily_consumption_server") or {}
_CONS = _ECON_ALL.get("consumption") or {}
CONSUME_ON = bool(_DCS.get("implement", False))
CONSUME_FOOD = float(_DCS.get("food_per_resident_day", _CONS.get("food_per_resident_day", 0.6)))
CONSUME_WATER = float(_DCS.get("water_per_resident_day", _CONS.get("water_per_resident_day", 0.6)))
STARVE_MORALE = float(((_CONS.get("starvation") or {}).get("morale_per_day")) or -1.0)
DRAIN_ENFORCE = True          # 옛 스위트(무료 짓기 가정)만 끈다
CONSUME_ENFORCE = True


def slot_depth_m(slot: int) -> int:
    return max(0, int(slot) // FLOOR_SLOTS - DOME_FLOOR) * DEPTH_PER_FLOOR


def drain_cost(st: dict, slot, reclaim: bool = False) -> dict:
    """그 칸의 물 빼기 비용(깊이 0/60/120/180m). 되찾기는 ×0.5 올림(0 이 아닌 항목은 최소 1). 문간(-1)은 없음."""
    if not DRAIN_ENFORCE or slot is None or int(slot) < 0:
        return {}
    d = slot_depth_m(int(slot))
    base = DRAIN_BY_DEPTH.get(max([k for k in DRAIN_BY_DEPTH if k <= d] or [0]), {})
    if not reclaim:
        return dict(base)
    return {k: max(1, math.ceil(v * DRAIN_RECLAIM)) for k, v in base.items() if v}


def drain_cells(st: dict) -> dict:
    """비어 있거나 물 찬 칸마다 {depth_m, drain_cost, reclaim, missing}."""
    taken = {r["slot"]: r for r in st.get("rooms") or []}
    out = {}
    for sl in range(SLOTS):
        r = taken.get(sl)
        if r and not r.get("flooded"):
            continue
        rc = bool(r and r.get("flooded"))
        dc = drain_cost(st, sl, reclaim=rc)
        out[str(sl)] = {"depth_m": slot_depth_m(sl), "drain_cost": dc, "reclaim": rc,
                        "missing": {k: v - int(st["resources"].get(k, 0)) for k, v in dc.items() if int(st["resources"].get(k, 0)) < v}}
    return out


def consume_tick(st: dict, ticks: int) -> dict:
    """주민 1인당 하루 식량 0.6·물 0.6(하루 3틱). 모자라면 0 에서 멈추고, 굶은 날만큼 사기 −1/일. 아무도 죽지 않는다."""
    if not CONSUME_ON or not CONSUME_ENFORCE or ticks <= 0:
        return {}
    n = len(st.get("residents_list") or [])
    if not n:
        return {}
    acc = st.setdefault("consume_acc", {"food": 0.0, "water": 0.0, "hunger": 0.0})
    res = st["resources"]
    out = {}
    short = False
    for key, per in (("food", CONSUME_FOOD), ("water", CONSUME_WATER)):
        acc[key] = float(acc.get(key) or 0) + per * n * ticks / 3.0
        whole = int(acc[key])
        if whole <= 0:
            continue
        have = int(res.get(key, 0))
        take = min(have, whole)
        res[key] = have - take
        out[key] = take
        if take < whole:
            short = True
        acc[key] -= whole
    if short:
        acc["hunger"] = float(acc.get("hunger") or 0) + ticks / 3.0
        days = int(acc["hunger"])
        if days:
            morale_add(st, STARVE_MORALE * days)
            acc["hunger"] -= days
            out["morale"] = int(STARVE_MORALE * days)
    st["_consumed_now"] = {k: v for k, v in out.items() if v} or None
    return out


def consumption_public(st: dict) -> dict:
    n = len(st.get("residents_list") or [])
    return {"food_per_day": round(CONSUME_FOOD * n, 2), "water_per_day": round(CONSUME_WATER * n, 2),
            "on": bool(CONSUME_ON and CONSUME_ENFORCE)}


# ── S27 (5차 플레이테스트 원인 고침) ───────────────────────────────────────
def home_subtypes(st: dict) -> dict:
    """이 집에 있는 하위 종류: 찍은 것(seen_subtypes) + 선반·창고 상자 물건(바코드로 다시 만든 줄기)."""
    out = {k: set(v) for k, v in (core_of(st).get("seen_subtypes") or {}).items()}
    for it in list(st.get("shelf") or []) + list(st.get("stored") or []):
        cat = it.get("category")
        sub = it.get("subtype") or shelf_subtype(it)
        if cat and sub:
            out.setdefault(cat, set()).add(sub)
    return out


def rule_at_home(st: dict, rule: dict) -> bool:
    hs = home_subtypes(st)
    cat = rule.get("category")
    if not cat or cat not in hs:
        return False
    sub = rule.get("subtype")
    if not sub:
        return True
    subs = sub if isinstance(sub, list) else [sub]
    return bool(set(subs) & hs[cat])


def asked_today(st: dict, uid: str) -> dict | None:
    """어제 떠날 때 「내일의 부탁」으로 말한 사람(같은 시드 — tomorrow_ask 와 같은 선택)."""
    day = day_of(st)
    ppl = [r for r in st.get("residents_list") or [] if need_today(uid, r, day)]
    if not ppl:
        return None
    return random.Random(f"{uid}|{day}|tomorrow_ask").choice(ppl)


def pin_rows(st: dict, uid: str, item: dict, w: dict) -> None:
    """「어디로」 사람 줄에 반드시 있어야 할 사람: 이 물건이 필요·좋아함·기억·매듭으로 맞는 사람, 오늘 부탁한 사람.
    값 순서 3개에 없으면 덧붙이고(사람 줄은 많아야 3 — 고정이 아닌 끝 사람을 뺀다), 표시(pinned)만 한다."""
    by = {r["id"]: r for r in st.get("residents_list") or []}
    out_ids = set(st.get("outside") or [])
    want = []
    for r in st.get("residents_list") or []:
        if r["id"] in out_ids:
            continue
        t_, _ = resident_tier(st, uid, r, item)
        if t_ in ("need", "like", "memory", "chain_beat"):
            want.append((r, t_, "fit"))
    ak = asked_today(st, uid)
    if ak and ak["id"] not in out_ids and not any(x[0]["id"] == ak["id"] for x in want):
        t_, _ = resident_tier(st, uid, ak, item)
        want.append((ak, t_, "asked"))
    rows = w["suggest"]
    have = {x["target"].get("resident_id"): x for x in rows if x["kind"] == "resident"}
    for r, t_, why in want[:3]:
        if r["id"] in have:
            have[r["id"]]["pinned"] = why
            continue
        tier = t_ if t_ in TIER_ICON else "warm"
        if t_ == "not_for_me":
            w.setdefault("warm_ids", []).append(r["id"])   # 부탁한 사람이 줄에 있는데 돌려주면 안 된다 — 반가워함으로
        mult, _ = give_diminish(st, r, item)
        row = {"kind": "resident", "target": {"resident_id": r["id"]}, "name": r["name"], "role": r.get("role"),
               "tier": tier, "icon": TIER_ICON.get(tier, "warm"), "value": give_value(tier), "mult": mult,
               "reason_ko": TIER_REASON.get(tier), "pinned": why}
        ppl = [x for x in rows if x["kind"] == "resident"]
        if len(ppl) >= 3:
            drop = next((x for x in reversed(ppl) if not x.get("pinned")), None)
            if drop:
                rows.remove(drop)
        rows.append(row)
        have[r["id"]] = row


DAYTIME_TABLE = True       # S27 ④: 저녁에 못 켜는 사람도 한 상(하루 한 번). 옛 S23 테스트는 저녁 전용을 본다


def solved_today(st: dict, rid: str) -> bool:
    """그 사람이 오늘 매듭을 풀었거나 기억을 열었다."""
    day = day_of(st)
    cr = cres(st, rid)
    if int(cr.get("memory_day") or 0) == day:
        return True
    return any(isinstance(v, dict) and v.get("last_day") == day for v in (cr.get("arcs") or {}).values())


def leave_lines(st: dict, uid: str, nv: dict | None = None) -> tuple:
    """S27 r5-3: 「다음에 켜시면」과 「내일의 부탁」이 겹치지 않게. 다음 약속이 필요·없음 수준이면
    내일의 부탁 한 줄로 합친다(next_visit 자리에 넣고 tomorrow_ask 는 null). 아니면 둘 다 + 보여 줄 순서."""
    nv = nv if nv is not None else next_visit_public(st, uid)
    ta = tomorrow_ask(st, uid)
    if ta and (nv or {}).get("kind") in ("need_tomorrow", "nothing"):
        nv = {"kind": "tomorrow_ask", "title": (nv or {}).get("title"), "line": ta["line"],
              "data": {"resident_id": ta["resident_id"], "need": ta["need"]}, "merged_from": (nv or {}).get("kind")}
        return nv, None, ["next_visit", "missed_chain"]
    return nv, ta, ["next_visit", "missed_chain", "tomorrow_ask"]


# ── ④ 기억 벽(7일째, 식량창고 벽 4칸 — 첫 칸은 미리 채워서 연다) ─────────
MEMORY_WALL_SLOTS = 4


def memory_wall_first(st: dict) -> dict | None:
    """첫 칸: 이 집에서 가장 먼저 건넨 물건, 없으면 가장 먼저 찍은 물건."""
    by = {r["id"]: r for r in st.get("residents_list") or []}
    best = None
    for rid, cr in (core_of(st).get("res") or {}).items():
        for g in cr.get("given") or []:
            if g.get("_probe"):
                continue
            k = (int(g.get("day") or 0), float(g.get("at") or 0))
            if best is None or k < best[0]:
                best = (k, g, rid)
    if best:
        g, rid = best[1], best[2]
        return {"name": g.get("name"), "barcode": g.get("barcode"), "category": g.get("category"),
                "subtype": g.get("subtype"), "day": g.get("day"), "from": "first_given",
                "resident_id": rid, "resident_name": (by.get(rid) or {}).get("name"),
                "prop": prop_for_item(g)}
    for rec in core_of(st)["scans"].values():
        it = rec.get("item") or {}
        if it.get("name"):
            return {"name": it.get("name"), "barcode": it.get("barcode"), "category": it.get("category"),
                    "subtype": it.get("subtype"), "day": rec.get("day"), "from": "first_scan", "prop": prop_for_item(it)}
    return None


def memory_wall_public(st: dict, uid: str) -> dict | None:
    if CALENDAR_ENFORCE and not is_unlocked(st, "memory_wall"):
        return None
    c = core_of(st)
    mw = c.get("memory_wall")
    if not isinstance(mw, dict):
        first = memory_wall_first(st)
        mw = {"room": "pantry", "opened_day": day_of(st),
              "slots": [first] + [None] * (MEMORY_WALL_SLOTS - 1)}
        c["memory_wall"] = mw
    M = moments().get("memory_wall") if isinstance(moments().get("memory_wall"), dict) else {}
    filled = sum(1 for x in mw["slots"] if x)
    first_open = not mw.get("announced")
    mw["announced"] = True                            # 처음 열릴 때 방송은 한 번
    return {"open": True, "room": mw["room"], "opened_day": mw.get("opened_day"), "slots": mw["slots"],
            "filled": filled, "total": len(mw["slots"]), "complete": filled == len(mw["slots"]),
            "first_label_ko": (M or {}).get("first_label"), "hang_prompt_ko": (M or {}).get("hang_prompt"),
            "open_ko": (str((M or {}).get("open") or "").replace("{item}", (mw["slots"][0] or {}).get("name") or "") or None) if first_open else None,
            "prefilled_ko": str((M or {}).get("prefilled") or "").replace("{item}", (mw["slots"][0] or {}).get("name") or "") or None if mw["slots"] and mw["slots"][0] and mw["slots"][0].get("from") in ("first_given", "first_scan") else None,
            "story": list((M or {}).get("story") or []) if filled == len(mw["slots"]) else None}


class WallIn(BaseModel):
    uid: str
    relic_id: str
    slot: int | None = None


@app.post("/api/memory_wall/hang")
def memory_wall_hang(inp: WallIn):
    """선반·창고 물건 하나를 기억 벽 빈 고리에 건다(물건은 선반에서 벽으로 옮겨진다)."""
    st = load_state(inp.uid)
    require_unlocked(st, "memory_wall")
    memory_wall_public(st, inp.uid)
    mw = core_of(st)["memory_wall"]
    empty = [i for i, x in enumerate(mw["slots"]) if not x]
    if not empty:
        raise HTTPException(400, "벽의 고리가 다 찼습니다")
    i = inp.slot if inp.slot is not None else empty[0]
    if i not in empty:
        raise HTTPException(400, "그 고리에는 이미 걸려 있습니다")
    row = next((x for x in st.get("shelf") or [] if x.get("card_id") == inp.relic_id), None) or \
        next((x for x in st.get("stored") or [] if x.get("id") == inp.relic_id or x.get("card_id") == inp.relic_id), None)
    if not row:
        raise HTTPException(400, "걸 물건이 없습니다")
    it = item_from_row(row)
    detach_item(st, it.get("card_id") or inp.relic_id, None)
    mw["slots"][i] = {"name": it.get("name"), "barcode": it.get("barcode"), "category": it.get("category"),
                      "subtype": it.get("subtype"), "day": day_of(st), "from": "hung", "prop": prop_for_item(it)}
    M = moments().get("memory_wall") if isinstance(moments().get("memory_wall"), dict) else {}
    n, m = sum(1 for x in mw["slots"] if x), len(mw["slots"])
    ln, _ = _rot(st, "memory_wall.hung", (M or {}).get("hung") or [])
    line = (ln or "「{item}」, 식량창고 벽에 걸었습니다. {n}/{m}.").replace("{item}", it.get("name") or "").replace("{n}", str(n)).replace("{m}", str(m))
    done = n == m
    if done:
        mw["complete_day"] = day_of(st)
    session_note(st, line)
    save_state(inp.uid, st)
    return {"ok": True, "line": line, "complete": done, "complete_ko": (M or {}).get("complete") if done else None,   # 보상 약속 없는 완성 방송(시나리오 2026-10-17)
            "story": list((M or {}).get("story") or []) if done else None,
            "memory_wall": memory_wall_public(st, inp.uid), "state": public_state(st, inp.uid)}


# ── ⑧ 「관리실이 대신 막을까요?」(낮 세션) ───────────────────────────
def office_offer(st: dict, raid: dict) -> dict | None:
    if not raid or raid.get("none") or raid.get("resolved") or raid.get("day") != day_of(st) or is_evening():
        return None
    O = moments().get("raid_office") or {}
    return {"ask": O.get("ask"), "yes_label": O.get("yes_label"), "no_label": O.get("no_label")}


def office_plan(st: dict, raid: dict) -> tuple:
    """지금 판(방·사람·도구)에서 가장 나은 배치 하나. 바꿀 수 있는 것은 불·전원·사람 자리뿐(행동·소모품은 쓰지 않는다).
    같은 배치 = 같은 답(난수 없음). 결과가 같으면 덜 바꾼 배치."""
    import copy
    cre = combat.CREATURES[raid["creature"]]
    slot = int(raid["target_slot"])
    room = room_at(st, slot)
    cap = room_cap_of(room) if room else 0
    out_ids = set(st.get("outside") or [])
    healthy = [r for r in st.get("residents_list") or [] if r["id"] not in out_ids]
    healthy.sort(key=lambda r: (bool(r.get("injured")), -int((r.get("stats") or {}).get("nerve", 5)), r["id"]))
    plans = []
    for light in (None, True, False):
        for power in (None, True, False):
            for fill in (0, 1, 2):
                plans.append({"light": light, "power": power, "fill": fill})
    best = None
    for pl in plans:
        t = copy.deepcopy(st)
        changes = 0
        if pl["power"] is not None and bool(t.get("power_on", True)) != pl["power"]:
            t["power_on"] = pl["power"]; changes += 1
        if pl["light"] is not None and light_on(t, slot) != pl["light"]:
            t.setdefault("lights", {})[str(slot)] = pl["light"]; changes += 1
        if pl["fill"] == 1 and room and not room.get("flooded"):   # 안의 사람으로 그 방을 정원까지
            here = [r for r in healthy if station_slot(t, r["id"]) == slot]
            for r in healthy:
                if len(here) >= cap:
                    break
                if station_slot(t, r["id"]) != slot:
                    set_station(t, r["id"], slot); here.append(r); changes += 1
        elif pl["fill"] == 2 and room and not room.get("flooded"):  # 모두 그 방에 모인다
            for r in healthy:
                if station_slot(t, r["id"]) != slot:
                    set_station(t, r["id"], slot); changes += 1
        ev = combat.evaluate(cre, raid_ctx(t, raid))
        key = (_RESULT_RANK.get(ev["result"], 9), -float(ev.get("margin") or 0), changes)
        if best is None or key < best[0]:
            best = (key, pl, t, ev)
    return best[1], best[2], best[3]


class OfficeIn(BaseModel):
    uid: str


@app.post("/api/raid/auto_defend")
def raid_auto_defend(inp: OfficeIn):
    """S27 ⑧ 낮 세션에만. 관리실이 지금 판에서 가장 나은 배치로 맞서고, 끝나면 배치를 원래대로 돌려 둔다(벌 없음)."""
    st = load_state(inp.uid)
    tick_production(st)
    raid = st.get("raid")
    if not raid or raid.get("none") or raid.get("day") != day_of(st):
        raise HTTPException(400, "오늘 오는 것이 없습니다")
    if raid.get("resolved"):
        raise HTTPException(400, "오늘의 습격은 이미 지나갔습니다")
    if is_evening():
        raise HTTPException(400, "저녁에는 직접 맞섭니다")
    keep = {"stations": dict(st.get("stations") or {}), "lights": dict(st.get("lights") or {}),
            "power_on": st.get("power_on", True)}
    plan, t, ev = office_plan(st, raid)
    st["stations"], st["lights"], st["power_on"] = t.get("stations") or {}, t.get("lights") or {}, t.get("power_on", True)
    out = resolve_raid(st, inp.uid, raid, [], cap=combat.SCARRED, auto=True)
    raid["office"] = True
    st["stations"], st["lights"], st["power_on"] = keep["stations"], keep["lights"], keep["power_on"]
    for rid, sl in list(st["stations"].items()):        # 방이 잠겼으면(상한 덕에 없지만) 그 자리 사람은 홀로
        rm = room_at(st, sl)
        if not rm or rm.get("flooded"):
            set_station(st, rid, None)
    O = moments().get("raid_office") or {}
    cre = combat.CREATURES.get(raid["creature"]) or {}
    good = out["result"] in (combat.HELD, combat.PASSED)
    arr = O.get("held" if good else "scarred") or []
    ln, _ = _rot(st, "raid_office." + ("held" if good else "scarred"), arr)
    out["office"] = {"plan": plan, "line": (ln or "").replace("{creature}", cre.get("name", "")).replace("{room}", out.get("room_name") or "") or None}
    session_note(st, out["office"]["line"] or "관리실이 대신 맞섰습니다")
    save_state(inp.uid, st)
    log(inp.uid, "raid_office", {"raid": raid["id"], "result": out["result"], "plan": plan})
    out["raid"] = raid_public(st, raid)
    out["state"] = public_state(st, inp.uid)
    return out


# ── PM 첫 세션 플레이(2026-10-17) 큐 ①② ───────────────────────────────
FIRST_ENTRY_GATE = True    # 옛 스위트(S19·S25b)는 새 방주의 밤사이·비트를 바로 본다


def first_entry(st: dict) -> bool:
    """처음 켠 방주: 1일째, 아직 아무것도 찍지 않았다."""
    return play_day(st) <= 1 and not core_of(st)["scans"]


def first_scan_beat_due(st: dict) -> bool:
    c = core_of(st)
    return play_day(st) == 1 and beat_today_id(st) == "first_scan" and len(c["scans"]) == 1 \
        and not (c["beats"].get("shown") or {}).get("1")


def keep_note_tick(st: dict, card_d: dict) -> dict | None:
    """가보 칸이 열리기 전 귀함 이상 카드: 「간직할 것」으로 적어 둔다(열리면 그 목록이 먼저 보인다)."""
    if _rk(card_d.get("rarity")) < _rk(HEIR_MIN) or (CALENDAR_ENFORCE and is_unlocked(st, "heirloom")) or not CALENDAR_ENFORCE:
        return None
    ks = core_of(st).setdefault("keep_list", [])
    if not any(k.get("barcode") == card_d.get("barcode") for k in ks):
        ks.append({"barcode": card_d.get("barcode"), "card_id": card_d.get("id") or card_d.get("card_id"),
                   "name": card_d.get("name"), "rarity": card_d.get("rarity"), "day": day_of(st)})
        del ks[:-12]
    H = moments().get("heirloom") or {}
    kn = H.get("keep_note")
    t = (random.Random(f"{card_d.get('barcode')}|keep").choice(kn) if isinstance(kn, list) and kn
         else kn if isinstance(kn, str) else None)
    return {"name": card_d.get("name"), "rarity": card_d.get("rarity"),
            "ko": (t or "「{item}」, 간직할 것으로 적어 두었습니다. 며칠 뒤 누군가에게 오래 맡길 수 있게 됩니다.").replace("{item}", card_d.get("name") or "")}


# ── 큐 ③ 한 번에 고르기(peek.quick_pick → /api/scan user_category+user_subtype) ─────────────
QUICK_PICK_N = 8
QUICK_DEFAULTS = [("apparel", "small"), ("electronics", "cable"), ("food", "grain"),
                  ("food", "canned"), ("drink", "milk"), ("stationery", "sticky"), ("medical", "hygiene"), ("electronics", "light")]
# S30 r7-1: 「알약」은 기본에서 뺐다(약을 권하지 않는다 — 「기타」로는 고를 수 있다). 빈자리 = 6차 로그 다음 빈도(LED 전구 → 조명).
# S29(6차 로그 재집계): 한 번에 고르기 13번 중 보기에 있음 2. 「기타」로 가서 고른 것 = 알약 3·장갑양말 2·충전선 2·곡물·통조림·붙이는 메모.
# 이야기책은 ISBN 이라 묻는 일이 없고, 면·과자·물·건전지는 대개 알려진 가문이라 한 번에 고르기에 오지 않는다.
QUICK_ARK_MAX = 3          # 이 방주가 고른 것은 3칸까지(이미 정한 바코드는 다시 묻지 않으니 같은 종류가 자리를 다 먹지 않게)


def quick_ok(cat: str, sub: str) -> bool:
    """고를 수 있는 쌍: 그 갈래의 하위 종류(가문 전용 빼고), 안전 목록 안(담배·술 없음)."""
    if cat in ("tobacco", "unknown") or (cat, sub) == ("drink", "alcohol"):
        return False
    return any(o["id"] == sub for o in subtype_options(cat))


def quick_pick_for(st: dict | None, uid: str, code: str) -> dict:
    """PM 결정(2026-10-17): 8 + 기타. 오늘 필요·좋아함으로 개인화하지 않는다(답을 흘린다).
    순서 ① 이 방주가 전에 고른 하위 종류(돌아가며 — 바코드마다 시작점이 다르다) ② 전역 투표 순위(시험 방주 제외) ③ 기본 8."""
    picked = []
    if st:
        for bm in reversed(list((st.get("barcodes") or {}).values())):
            k = (bm.get("category"), bm.get("subtype"))
            if k[0] and k[1] and quick_ok(*k) and k not in picked:
                picked.append(k)
        if picked:
            off = int(hashlib.sha256(code.encode()).hexdigest()[:4], 16) % len(picked)
            picked = (picked[off:] + picked[:off])[:QUICK_ARK_MAX]
    glob = []
    with db() as con:
        raw = con.execute("SELECT uid, category, subtype FROM subtype_votes").fetchall()
    cnt: dict = {}
    for r_ in raw:
        if vote_uid_excluded(r_["uid"]) or not quick_ok(r_["category"], r_["subtype"]):
            continue
        cnt.setdefault((r_["category"], r_["subtype"]), set()).add(r_["uid"])
    glob = [k for k, _ in sorted(cnt.items(), key=lambda kv: (-len(kv[1]), kv[0]))]
    out, seen = [], set()
    for src, rows in (("ark", picked), ("votes", glob), ("default", QUICK_DEFAULTS)):
        for k in rows:
            if len(out) >= QUICK_PICK_N:
                break
            if k in seen or not quick_ok(*k):
                continue
            seen.add(k)
            pr = ((PROPS_BY_SUBTYPE.get(k[0]) or {}).get(k[1]) or {})
            out.append({"category": k[0], "subtype": k[1], "ko": sub_ko(k[0], k[1]), "prop": pr.get("prop") if isinstance(pr, dict) else None,
                        "src": src})
    Q = (moments().get("scan") or {}).get("quick_pick") or {}
    pq = Q.get("prompt")
    prompt = (pq[int(hashlib.sha256(code.encode()).hexdigest()[4:8], 16) % len(pq)] if isinstance(pq, list) and pq
              else pq if isinstance(pq, str) else "이건 무엇에 가까운가요?")
    return {"prompt_ko": prompt, "options": out, "other": {"label_ko": Q.get("other_label") or "기타", "next": "categories"}}


def quick_pick_apply(st: dict, inp, code: str, bmeta: dict, pick_cat) -> str | None:
    """한 번에 고른 하위 종류: 그 바코드가 아직 하위 종류 없고, 고른 갈래의 것이면 이 방주에 적고 전역 투표에 넣는다."""
    sub = getattr(inp, "user_subtype", None)
    if not sub or not pick_cat or bmeta.get("subtype"):
        return None
    if bmeta.get("category") and bmeta["category"] != pick_cat:
        return None
    if not quick_ok(pick_cat, sub):
        raise HTTPException(400, "그 갈래에서 고를 수 있는 것이 아닙니다")
    bmeta["subtype"] = sub
    manual = (getattr(inp, "source", None) or "").lower() == "manual"
    if not manual and not vote_excluded(inp.uid, st):
        with db() as con:
            con.execute("INSERT OR REPLACE INTO subtype_votes VALUES(?,?,?,?,?)", (inp.uid, code, pick_cat, sub, time.time()))
    return sub


def card_d_name_cat(card) -> str:
    return card.category.value


def first_meet_sub(cat: str, sub: str, name: str | None) -> dict:
    """하위 종류를 고른 뒤의 첫 만남 줄: first_meet.json subtypes[갈래][하위 종류] → 없으면 하위 종류 이름으로 짠 줄.
    (갈래 줄은 하위 종류를 짐작한 문장이라 고른 것과 어긋날 수 있다 — 예: 우유를 골랐는데 「민물 냄새」)"""
    fm = ((FIRST_MEET.get("subtypes") or {}).get(cat) or {}).get(sub) or {}
    sf = ((moments().get("subtype_first") or {}).get(cat) or {}).get(sub)
    if isinstance(sf, list) and sf:                   # 시나리오 S27: ui_moments.subtype_first.<갈래>.<종류>[] (자리표시자 없음)
        t = random.Random(f"{cat}|{sub}|{name}|first").choice(sf)
        fm = {"line": t, "line_short": t}
    ko = sub_ko(cat, sub)
    line = fm.get("line") or f"처음 보는 {ko}입니다. 「{name or ko}」, 선반에 올려 두겠습니다."
    short = fm.get("line_short") or f"처음 보는 {ko}입니다."
    return {"kind": "subtype", "key": f"{cat}.{sub}", "line": line, "line_ko": line, "line_short": short,
            "replaces": "category", "fallback": not fm.get("line")}


def rename_offer(st: dict, card_d: dict, bmeta: dict) -> dict | None:
    """이미 하위 종류를 정한 바코드: 이름 다시 붙이기 화면용 선택지(지금 것 표시)와 오늘 할 수 있는지."""
    cat, cur = card_d.get("category"), bmeta.get("subtype")
    if not cur or cat not in SUBTYPE_KO:
        return None
    opts = [dict(o, current=o["id"] == cur) for o in subtype_options(cat)]
    if len(opts) < 2:
        return None
    M_ = moments().get("scan") or {}
    return {"options": opts, "current": {"id": cur, "ko": sub_ko(cat, cur)},
            "can_today": (core_of(st)["flags"].get("rename_days") or {}).get(card_d.get("barcode")) != day_of(st),
            "label_ko": M_.get("rename_label"),
            "confirm_ko": (M_.get("rename_confirm") or "").replace("{old}", sub_ko(cat, cur)) or None}


# ── S29 ────────────────────────────────────────────────────────────
def heirloom_second(st: dict, uid: str, item: dict, tier: str, taken: set) -> dict | None:
    """가보 후보가 하나뿐일 때 하나 더: 같은 갈래에 좋아함·기억이 있는 사람 → 받은 게 많은 사람. 안 맞음(twist dislike)·오늘 들어온 사람은 뺀다."""
    cat = item.get("category")
    best = None
    for r in st.get("residents_list") or []:
        if r["id"] in taken or r["id"] in (st.get("outside") or []):
            continue
        h = r.get("heirloom")
        if h and _rk(h.get("tier")) >= _rk(tier):
            continue
        if join_day(st, r) >= day_of(st) and day_of(st) > 1:
            continue
        tw = twist_of(uid, r).get("dislike")
        if tw and match({"category": tw["category"], "subtype": tw.get("subtype")}, item):
            continue
        like_cat = any(isinstance(x, dict) and x.get("category") == cat for x in likes_of(uid, r))
        mem_cat = any(isinstance(m, dict) and (m.get("trigger") or {}).get("category") == cat
                      for m in (role_taste(r.get("role", "")).get("memories") or []))
        k = (0 if mem_cat else 1, 0 if like_cat else 1, -len(cres(st, r["id"])["given"]), r["id"])
        if best is None or k < best[0]:
            best = (k, r)
    return best[1] if best else None


# ── S30 ────────────────────────────────────────────────────────────
WEEK1_DAYS = 7


WEEK1_CAP = True          # 옛 S13 스위트는 방을 잃는 판정 자체를 시험한다


def week1_cap(st: dict) -> bool:
    return WEEK1_CAP and 1 <= play_day(st) <= WEEK1_DAYS


def decor_unlock_day(st: dict) -> bool:
    """오늘(켠 날)이 꾸밈이 처음 열린 날인가."""
    if not CALENDAR_ENFORCE:
        return False
    p = play_day(st)
    for d_, row in (UNLOCK_CAL.get("days") or {}).items():
        if "decor_place" in ((row or {}).get("unlocks") or []):
            return str(d_).isdigit() and int(d_) == p
    return False


def evening_story_first(st: dict, w: dict) -> str | None:
    """저녁 세션: 그날 아직 안 움직인 매듭·기억 후보가 줄에 있으면 그 사람(첫 칸에)."""
    if not is_evening():
        return None
    for x in w.get("_internal") or w.get("suggest") or []:
        if x.get("kind") == "resident" and x.get("tier") in ("chain_beat", "memory"):
            rid = x["target"]["resident_id"]
            if not solved_today(st, rid):
                return rid
    return None


def heir_open_tick(st: dict, card_d: dict) -> None:
    """가보 칸이 열리는 순간: 켠 날 min_play_day 이상에서 들어온 귀함 이상 카드."""
    hc = (UNLOCK_CAL.get("conditional") or {}).get("heirloom") or {}
    f = core_of(st)["flags"]
    if f.get("heir_open_day") is None and _rk(card_d.get("rarity")) >= _rk(HEIR_MIN) \
            and play_day(st) >= int(hc.get("min_play_day") or 1):
        f["heir_open_day"] = day_of(st)


def guaranteed_rare_due(st: dict) -> bool:
    """켠 날 4 이상·첫 주 안인데 귀함 이상이 한 번도 없었다."""
    f = core_of(st)["flags"]
    return 4 <= play_day(st) <= WEEK1_DAYS and f.get("first_rare_day") is None and f.get("guaranteed_rare_day") is None


def heir_fit_hint(st: dict, r: dict, item: dict) -> str:
    """가보 후보 단서: roles.<역할>.heirloom.fit_hint_by_category.<갈래>[] → fit_hint[](물건마다 돌려 쓰기) → 서버 줄."""
    H = role_taste(r.get("role", "")).get("heirloom") or {}
    pool = ((H.get("fit_hint_by_category") or {}).get(item.get("category") or "") or [])
    if isinstance(pool, str):
        pool = [pool]
    if not pool:
        fh = H.get("fit_hint") or []
        pool = [fh] if isinstance(fh, str) else list(fh)
    t = random.Random(f"{r['id']}|{item_key(item)}|fit").choice(pool) if pool else "{name} 님 손에 오래 머물 것 같습니다."
    return fill_text(t, st, r, item)


# ── S31 ────────────────────────────────────────────────────────────
HEIR_BROADCAST_NEEDS_SCREEN = True
LOW_KNOWN = 3              # 방주 전체 아는 칸이 이보다 적으면(B 4일째 2/36) 기색이 맞는 사람을 첫 칸에


def known_total(st: dict) -> int:
    return sum(len(cres(st, r["id"]).get("notebook") or {}) for r in st.get("residents_list") or [])


def evening_step_ok(st: dict, s: dict, beat: dict | None) -> bool:
    """아침(낮)에 한 걸음 간 사슬의 다음 작은 걸음은 같은 날 저녁에 한 번 더 열 수 있다(min_days_after_prev ≤ 1)."""
    if not beat or not is_evening():
        return False
    day = day_of(st)
    if s.get("last_day") != day or s.get("last_evening") is not False or s.get("evening_extra_day") == day:
        return False
    trig = beat.get("trigger") or {}
    gap = int(trig.get("min_days_after_prev", ARC_COOLDOWN_DEFAULT))
    return gap <= 1 and (beat.get("size") or "small") == "small"


def arc_today_blocked(st: dict, s: dict, beat: dict | None) -> bool:
    return s.get("last_day") == day_of(st) and not evening_step_ok(st, s, beat)


def memory_for_evening(st: dict, w: dict, ppl: list) -> list:
    """아침·낮 세션: 오늘 아직 아무 기억도 안 열렸으면 기억 후보 하나를 줄 끝으로(저녁 몫). 저녁엔 그대로."""
    if is_evening() or len(ppl) < 2:
        return ppl
    day = day_of(st)
    if any(int(cres(st, r["id"]).get("memory_day") or 0) == day for r in st.get("residents_list") or []):
        return ppl
    tiers = {x["target"].get("resident_id"): x.get("tier") for x in w.get("_internal") or [] if x.get("kind") == "resident"}
    mem = [x for x in ppl if tiers.get(x["target"]["resident_id"]) == "memory"]
    if not mem:
        return ppl
    m = mem[0]
    out = [x for x in ppl if x is not m] + [m]
    m["evening_reserve"] = True
    if m.get("first_reason"):
        m.pop("first_reason", None)
    return out


def heir_choosable(st: dict, uid: str) -> bool:
    """지금 가보로 고를 화면이 있나: 선반·창고의 귀함 이상 물건 중 가보 후보가 있는 것."""
    for row in (st.get("shelf") or []) + (st.get("stored") or []):
        if _rk(row.get("rarity")) < _rk(HEIR_MIN):
            continue
        it = item_from_row(row)
        if heirloom_options(st, uid, it):
            return True
    return False


@app.get("/api/relic/where")
def relic_where(uid: str, relic_id: str):
    """S31 ①: 선반·창고 물건 하나의 「어디로」(가보 후보 포함) — 선반에서 「가보로 드리기」. 건네기는 /api/give {relic_id, target}."""
    st = load_state(uid)
    row = next((x for x in st.get("shelf") or [] if x.get("card_id") == relic_id), None) or \
        next((x for x in st.get("stored") or [] if x.get("id") == relic_id or x.get("card_id") == relic_id), None)
    if not row:
        raise HTTPException(400, "선반·창고 상자에 그런 물건이 없습니다")
    it = item_from_row(row)
    it["card_id"] = relic_id
    w = where_for(st, uid, it)
    w.pop("_internal", None)
    w.update({"relic_id": relic_id, "name": it.get("name"),
              "heirloom_label": (moments().get("heirloom") or {}).get("give_label") or "가보로 드리기"})
    new = unlock_new(st, uid, heir_screen=bool(w.get("heirloom")))
    save_state(uid, st)
    return dict(w, unlock_new=new)


class DevRaidIn(BaseModel):
    uid: str
    creature: str
    grade: int | None = None


@app.post("/api/dev/raid")
def dev_raid(inp: DevRaidIn):
    """★ 개발 전용(RELIC_DEV=1): 오늘의 습격을 이 생물로 새로 연다(소리 단계부터). 배포에서는 404."""
    if not DEV_MODE:
        raise HTTPException(404, "없는 경로입니다")
    if inp.creature not in combat.CREATURES:
        raise HTTPException(400, f"없는 생물입니다: {inp.creature}")
    st = load_state(inp.uid)
    tick_production(st)
    ensure_raid(st, inp.uid, force=inp.creature, reset=True, grade_force=inp.grade)
    save_state(inp.uid, st)
    return {"ok": True, "raid": raid_public(st, st.get("raid")), "state": public_state(st, inp.uid)}


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

