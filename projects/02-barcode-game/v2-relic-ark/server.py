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
_ECON = (combat._balance("economy").get("rooms") or {})
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
        CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, uid TEXT, kind TEXT, payload TEXT, ts REAL);
        CREATE TABLE IF NOT EXISTS codes (code TEXT PRIMARY KEY, uid TEXT NOT NULL, created REAL, used REAL);
        CREATE INDEX IF NOT EXISTS codes_uid ON codes(uid);
        """)
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
        if changed:
            save_state(uid, st)
        return st
    st = new_state(uid)
    migrate_s13(st, uid)
    migrate_s15(st)
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
        day_note(st, "imprint", r["name"])
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
                           "ko": "불을 꺼 둔 방은 절반만 일했다 — " + " · ".join(sorted(set(dark_rooms)))}
    # 부상 회복: 틱마다 1명 (의무병 있으면 2명) + 의무실·물 끓이는 방의 회복(heal) 값
    heal = int(round((eff["heal_rate"] + heal_extra) * ticks))
    # 숨이 긴 사람이 먼저 일어난다(RESIDENT_STATS §4 "부상 회복 = 숨 + 의무실 등급")
    for res in sorted(st.get("residents_list", []),
                      key=lambda r: -int((r.get("stats") or {}).get("breath", 5))):
        if res.get("injured") and heal > 0:
            res["injured"] = False; heal -= 1
    st["injured"] = sum(1 for x in st.get("residents_list", []) if x.get("injured"))
    st["last_tick"] += ticks * PRODUCTION_TICK_SEC
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
                               residents=len(st.get("residents_list") or []))
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
    revealed = lid_revealed(raid, cre)                # S13 덮개: stakes lid.reveal_from_stage 부터 대상 방을 연다
    if revealed:
        quiet = False
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
        "lid_revealed": revealed,
        "reveal_ko": moment("lid.target_revealed", room=room_name or "") if revealed else None,
        "auto": bool(raid.get("auto")), "capped": bool(raid.get("capped")),
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
        # E1 선반(계약 형식 고정). shelf_room 은 어느 방의 선반인지 알려 주는 덧붙임
        "shelf": shelf_public(st),
        "shelf_room": ({"slot": shelf_room(st)["slot"], "room_id": shelf_room(st)["id"],
                        "level": room_level(shelf_room(st)), "capacity": shelf_capacity(st)}
                       if shelf_room(st) else None),
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
        # S15 원정·문간(docs/API_EXPEDITION.md)
        "expedition": exp_public(st, st.get("expedition")),
        "expedition_return": st.get("exp_unseen"),
        "air": air_state(st),
        "guests": len(st.get("guests") or []),
        "boxes": boxes_public(st),
        "beds": beds_state(st),
        "entrance": entrance_public(st),                    # /api/entrance 와 같은 모양(S15-A2)
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
    r = shelf_room(st)
    return shelves_of(r) if r else 0


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
        lv = polish_level(it)
        row["polish"] = lv
        row["polish_label"] = moment(f"shelf.levels.{lv}.label")
        row["polish_value_mult"] = polish_value_mult(lv)
        out.append(row)
    return out


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
    return sm * sf * cm, {"staff": n, "staff_mult": sm, "stat": room_stat_of(room["id"]), "stat_mult": sf,
                          "per_person": per, "cracked": bool(room.get("cracked")), "crack_mult": cm}


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
        if from_room is not None and prod[cur]:
            left = [x for x in base_ppl[cur] if x["id"] != p["id"]]
            from_delta = pct(room_output(st, from_room, left), base_out[cur]) if counts else 0.0
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
                    cell["room_delta_pct"] = pct(room_output(st, r, newp), base_out[slot])
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
    return next((it for it in (st.get("shelf") or []) if it.get("barcode") == code), None)


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
        line = ((FIRST_MEET.get("families") or {}).get(fam) or {}).get("line")
        if line:
            out.append({"kind": "family", "key": fam, "line": line})
    if cat not in seen_c:
        seen_c.append(cat)
        line = ((FIRST_MEET.get("categories") or {}).get(cat) or {}).get("line")
        if line:
            out.append({"kind": "category", "key": cat, "line": line})
    return out


# ── 도감 메타(줄기별 희귀도·변형) ─────────────────────────────
def stem_of(cat: str, name: str) -> str | None:
    for t in (TEMPLATES.get(cat) or []):
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
        oc["gift_day"] = day
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
        gift = {"id": g["id"], "name": g["name"], "line": g.get("line"), "kind": g.get("kind"),
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
            ok, prog = (True, None) if d else wish_progress(st, uid, w, r)
            out.append({"id": w["id"], "resident_id": r["id"], "name": r["name"], "role": r["role"],
                        "wish": w.get("wish"), "condition": (w.get("condition") or {}).get("text"),
                        "done": bool(d), "done_day": (d or {}).get("day"),
                        "line": (w.get("line_after") if d else w.get("line_before") or "").replace("{name}", r["name"]),
                        "beast_beat": w.get("beast_beat") if d else None, "progress": prog})
    return out


def wishes_tick(st: dict, uid: str) -> list[dict]:
    """이뤄진 바람을 기록한다(되돌아가지 않는다). 이번에 이뤄진 것만 돌려준다."""
    done = st.setdefault("wishes_done", {})
    new = []
    for r in st.get("residents_list") or []:
        for w in WISHES:
            if w.get("role") != r.get("role") or w["id"] in done:
                continue
            ok, _ = wish_progress(st, uid, w, r)
            if ok:
                done[w["id"]] = {"day": day_of(st), "resident_id": r["id"]}
                day_note(st, "wish", r["name"])
                new.append({"id": w["id"], "resident_id": r["id"], "name": r["name"],
                            "line": (w.get("line_after") or "").replace("{name}", r["name"])})
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
    out["octopus"] = octopus_tick(st, uid)
    out["wishes_new"] = wishes_tick(st, uid)
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
                "deep": int(sp.get("depth_m", 0)) >= 120, "first_visit_imprint": sp.get("first_visit_imprint")}
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
    g = make_resident(rng.choice(sorted(pool)), rng, taken, uid)
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
    return shelf_place(st, card)


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
        else:
            no_room = True
            st["resources"]["morale"] = int(st["resources"].get("morale", 0)) + 1
    imps = grant_imprints(st, None, flags, mem) if flags else []
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
           "tutorial": bool(ex.get("tutorial")), "value": out["value"]}
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
    if day < first:
        return None
    if len(st.get("guests") or []) >= int(EX.g("entrance.guest_spots", 2)):
        return None
    hit = not st.get("first_knock_done")
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


# ─────────────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────────────
class ScanIn(BaseModel):
    uid: str
    barcode: str
    user_category: str | None = None


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
    return {"barcode": code, "known_category": None if cat == Category.UNKNOWN else cat.value,
            "needs_category": cat == Category.UNKNOWN and not locked, "locked_category": locked,
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

    # S13 카테고리 고정(stakes category_lock): 이 방주에서 그 바코드에 처음 정해진 카테고리를 다시 쓴다.
    # 모르는 가문 바코드가 고르는 카테고리마다 다른 유물(평균 7개)이 되던 구멍 — 같은 바코드 = 같은 유물.
    bmeta = st.setdefault("barcodes", {}).setdefault(code, {})
    locked = bmeta.get("category") if stk("category_lock") else None
    pick_cat = locked or inp.user_category
    card = GEN.generate(code, hour=datetime.now().hour, user_category=pick_cat)
    if card.category != Category.UNKNOWN and not bmeta.get("category"):
        bmeta["category"] = card.category.value       # 정체불명(고르지 않음)은 고정하지 않는다 — 다음에 고를 수 있게
    mult = rescan_multiplier(prev)
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
    usable_tags = [t for t in card.tags if t != "미확인"]
    if mult > 0 and usable_tags and len(st["hand"]) < HAND_LIMIT:
        st["hand"].append(card_d)
    # E1 — 찍은 물건이 선반에 놓인다. S13: **이미 선반에 있는 바코드면 새 칸을 먹지 않고 닦는다**
    # (감쇠 0.5·0.1 재스캔이 같은 물건을 한 칸 더 놓던 버그의 수정). 값이 0인 재스캔도 닦는다.
    polish = None
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

    # 가문 크라우드소싱
    if inp.user_category and card.family_code not in GEN.families:
        with db() as con:
            con.execute("INSERT INTO family_votes VALUES(?,?,?,?)", (inp.uid, card.family_code, inp.user_category, time.time()))

    with db() as con:
        con.execute("INSERT INTO scans(uid,barcode,category,rarity,mult,ts,day) VALUES(?,?,?,?,?,?,?)",
                    (inp.uid, code, card.category.value, card.rarity.value, mult, time.time(), day))
    # S13 첫 만남(가문 먼저) · 가문 세트(서로 다른 바코드 수, 방금 넣은 스캔 포함) · 바람
    first_meet = first_meet_lines(st, card.category.value, card.family_code)
    # S15 봉인 상자: 같은 갈래 바코드가 열쇠다(값 0 인 재스캔도). 가장 오래된 것 하나, 같은 바코드는 하루 한 상자
    box_opened = box_try_scan(st, inp.uid, code, card.category.value)
    fam_set = family_set_check(st, inp.uid, card.family_code)
    wishes_new = wishes_tick(st, inp.uid)
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
            "scans_today": today + 1, "scan_cap": DAILY_SCAN_CAP, "resources": st["resources"], "voice": voice}


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
    ticked = day_tick(st, uid, force_night=bool(debug_night) and DEV_MODE)
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
    out["night_judge"]["report"] = ticked["night_judge"]
    out["knock"] = ({"guest_id": ticked["knock"]["guest_id"], "name": ticked["knock"]["name"],
                     "role": ticked["knock"]["role"]} if ticked.get("knock") else None)
    out["wishes_new"] = ticked["wishes_new"]
    if (ticked.get("octopus") or {}).get("arrival"):
        out["octopus"]["arrival"] = ticked["octopus"]["arrival"]
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
    if not (0 <= inp.slot < SLOTS) or any(r["slot"] == inp.slot and not r.get("flooded") for r in st["rooms"]):
        raise HTTPException(400, "그 자리는 비어 있지 않습니다")
    flooded = next((r for r in st["rooms"] if r["slot"] == inp.slot and r.get("flooded")), None)
    miss = cond_check(st, inp.uid, BUILD_COND.get(inp.room_id))
    if miss:
        raise HTTPException(400, "아직 지을 수 없습니다: " + " · ".join(miss))
    cost, lacking = priced(st, ROOMS[inp.room_id]["cost"])
    if lacking:
        raise HTTPException(400, f"자원이 부족합니다: {lacking}")
    for k, v in cost.items():
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
        del st["reclaimed"][:-30]
        day_note(st, "reclaimed", ROOMS.get(inp.room_id, {}).get("name", inp.room_id))
    st["rooms"].append({"id": inp.room_id, "slot": inp.slot, "built": time.time(), "level": 1})
    save_state(inp.uid, st)
    log(inp.uid, "build", {"room": inp.room_id, "slot": inp.slot, "cost": cost, "reclaimed": reclaimed})
    out = public_state(st, inp.uid)
    out["reclaimed"] = reclaimed
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
    if inp.room_id == HALL_ID:
        rid, room, level = HALL_ID, None, int(st.get("hall_level") or 1)
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
    if room is None:
        st["hall_level"] = opt["to"]
    else:
        room["level"] = opt["to"]
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
        bits.append(f"「{gone_card}」을(를) 내려보냈다. 도감의 그 칸은 비어 있는 채로 남는다")
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
    if result == combat.PASSED and cre.get("threat"):
        flags = list(cre.get("hold_flags") or [])     # 숨죽여 넘긴 것도 '겪고 넘긴' 것이다(문지기)
        line = (cre.get("lines") or {}).get("held") or line
    if result == combat.HELD:
        flags = list(cre.get("hold_flags") or [])
    elif result == combat.SCARRED and room:
        if any(combat.TOOLS[t].get("heals_crack") for t in use):   # 봉합 패치로 그 자리에서 꿰맨다
            line += " 봉합 패치가 그 자리를 덮었다."
        elif crack_room(st, room):                  # S13: 금이 실효를 갖는다 — 수리 전까지 생산 ×crack.prod_mult
            day_note(st, "crack", room_name)
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
    # S13: 어제(또는 오늘 밤 시각을 넘긴) 누르지 않은 습격을 먼저 판정한다 — ensure_raid 가 덮어쓰기 전에
    ticked = day_tick(st, uid)
    ensure_raid(st, uid, force=debug_raid, reset=bool(debug_reset), grade_force=debug_grade)
    save_state(uid, st)
    out = combat_public(st)
    return {"raid": out["raid"], "day": day_of(st), "outside": out["outside"],
            "next_raid_hint": out["next_raid_hint"], "night_judge": ticked["night_judge"],
            "state": public_state(st, uid)}


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
        ev = EVENTS[opener] if opener else             pick_event(ark_state_obj(st), rng=random.Random(f"{uid}|{day}"),
                       exclude=seen_once(st) | ALL_OPENERS)    # 여는 카드는 한 번뿐이다. 무작위로 다시 나오지 않는다
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
            "state": ((spot_state(_st_sp, uid, sid) if sid in DEEP_SPOT_IDS else ("found" if unlocked else "none"))
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
    for cat, pool in TEMPLATES.items():
        if cat.startswith("_"):
            continue
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
                    "names": got, "entries": entries, "rarity": rar})
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
    return {"families": fams, "families_done": len(done), "families_total": len(FAMILY_NAMES),
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
        lack = {k: v - int(st["resources"].get(k, 0)) for k, v in cost.items() if int(st["resources"].get(k, 0)) < v}
        if lack:
            raise HTTPException(400, "모자랍니다: " + " · ".join(f"{RES_KO_SRV.get(k, k)} {v}" for k, v in lack.items()))
        for k, v in cost.items():
            st["resources"][k] = int(st["resources"].get(k, 0)) - v
        paid = cost
    room["cracked"] = False
    room.pop("cracked_day", None)
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
    now_sec, prev_sec = fl.get(str(day)), fl.get(str(day - 1))
    vals = {
        "imprint": ({"name": note["imprint"][0]} if note.get("imprint") else None),
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
        t = random.Random(f"{uid}|{day}|day_end|{sit['id']}").choice(sit["lines"])
        for k, x in v.items():
            t = t.replace("{" + k + "}", str(x))
        lines.append({"id": sit["id"], "text": t})
    lines = lines[: int(frame.get("max_lines") or 3)]
    if not lines:
        q = next((x for x in sits if x.get("id") == "quiet"), None)
        if q and q.get("lines"):
            lines = [{"id": "quiet", "text": random.Random(f"{uid}|{day}|day_end|quiet").choice(q["lines"])}]
    with db() as con:
        n_scan = con.execute("SELECT COUNT(*) c FROM scans WHERE uid=? AND day=?", (uid, day)).fetchone()["c"]
    blocked = len(note.get("blocked") or [])
    floors = len({r["slot"] // FLOOR_SLOTS for r in live_rooms(st)})
    facts_ko = [x for x in (moment("day_end.scans", scan_count=n_scan) if n_scan else None,
                            moment("day_end.blocked", blocked=blocked) if blocked else None,
                            moment("day_end.floors", floors=floors)) if x]
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
    return {"ok": True, "paid": cost, "suits": suits_state(st), "state": public_state(st, inp.uid)}


@app.get("/api/expedition/options")
def expedition_options(uid: str):
    st = _s15_load(uid)
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
    return exp_preview(st, inp.uid, inp.members, inp.dest, inp.length)


@app.post("/api/expedition/start")
def expedition_start(inp: ExpIn):
    st = _s15_load(inp.uid)
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
