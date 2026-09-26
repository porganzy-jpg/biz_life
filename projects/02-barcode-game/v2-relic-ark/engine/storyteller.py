"""
잔해 방주 — 스토리텔러 (사건 카드 선택기)

림월드의 스토리텔러 AI에 해당한다. 방주 상태(ArkState)를 보고
data/events.json 중 어떤 사건 카드를 오늘 뽑을지 결정한다.

설계 의도:
  - 사건은 "무작위"가 아니라 "방주의 약점을 찌르되, 대항할 길은 남겨둔다".
  - 같은 사건이 연속으로 나오면 지루하므로 최근 사건은 억제한다.
  - 긍정 사건(표류자, 유물 창고)은 방주가 힘들 때 숨 쉴 틈으로 섞인다.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass
class ArkState:
    day: int = 1
    act: int = 1                                       # 1 심해 / 2 터널 / 3 지상 (DECISIONS 2026-09-23)
    resources: dict = field(default_factory=lambda: {
        "food": 5, "water": 5, "med": 0, "power": 0, "parts": 0,
        "morale": 5, "cloth": 0, "trade": 0, "knowledge": 0, "scrap": 0,
    })
    rooms: list = field(default_factory=list)        # ["pantry", "infirmary", ...]
    residents: int = 3
    injured: int = 0
    recent_events: list = field(default_factory=list)  # 최근 사건 id (최신이 마지막)
    hardcore: bool = False                             # 결정 #1: 기본 False


EVENT_REQUIRED = ("id", "name", "faction", "severity", "text", "counter_tags", "counter_room",
                  "on_fail", "on_counter", "timer_sec")


# 사건 카드 파일 목록. 시나리오가 새 묶음을 내면 여기 한 줄만 추가한다.
#   events.json        — 기본(방주 안)
#   events_tribes.json — 일곱 부족 접촉
#   events_outside.json— 바깥(공룡·원정·스팟 단서)
#   events_deep.json   — 1막 심해(유리돔·깊이 4구역·큰 것들). 2026-09-22 결정으로 1막이 심해가 됐다
EVENT_FILES = ("events.json", "events_tribes.json", "events_outside.json", "events_deep.json")


# ─────────────────────────────────────────────────────────────
# 막(acts) — DECISIONS 2026-09-23
#   1 심해 유리돔 / 2 침수 지하철 터널 / 3 지상 쇼핑몰. [1,2,3] 이면 어디서나.
#   정본은 카드 파일의 `acts` 배열(data/events_schema.json)이고, **파일이 언제나 이긴다.**
#   아래 표는 시나리오가 값을 적기 전까지의 **임시 분류표**다. 파일에 acts 가 들어오면
#   그 카드는 이 표를 쳐다보지도 않는다(acts_of() 첫 줄).
# ─────────────────────────────────────────────────────────────
ACT_DEEP, ACT_TUNNEL, ACT_SURFACE = 1, 2, 3
ALL_ACTS = (1, 2, 3)

# 접두어 규칙: deep_* 는 1막, dino_* 와 부족 카드(tribe_*)는 3막(지상 콘텐츠로 유지).
# 2026-09-26(S4-C 이후): 사건 60장 **전부** 파일에 acts 가 들어와 아래 두 표는 지금 한 장도 타지 않는다.
# 지우지 않고 남기는 이유는 안전망이다 — acts 없는 카드가 새로 들어올 때 dino_/tribe_ 가 1막으로
# 새지 않게 막는다(그 사고가 dev_S3 R7 이었다). 파일이 언제나 이기므로 시나리오 작업을 방해하지 않는다.
ACT_BY_PREFIX = (("deep_", (1,)), ("dino_", (3,)), ("tribe_", (3,)))

# id 별 규칙(접두어보다 먼저 본다). events.json 10장 중 **장소를 타지 않는 것**
# (질병·물·굶주림·불신 계열)만 전 막 공용으로 둔다 — 나머지는 본문이 장소를 말한다.
ACT_BY_ID = {
    "infection":  ALL_ACTS,   # 포자·질병: 돔 이음매에서도 같은 일이 난다
    "famine":     ALL_ACTS,   # 굶주림: 빈 항아리는 어디서나 빈다
    "drought":    ALL_ACTS,   # 물탱크 균열: 심해에서 마실 물은 더 절실하다
    "confusion":  ALL_ACTS,   # 성문 오독: 바코드를 읽는 한 어느 막에서도 난다
    "cold_snap":  (2, 3),     # "밤 기온" — 공기가 있는 곳의 사건
    "drifter":    (2, 3),     # "잠든 철길 쪽에서 걸어왔다"
    "relic_cache": (2, 3),    # "콘크리트 아래 굴착"
    "raid_scavs": (2, 3),     # "회색 개들" — 물속엔 개가 없다(심해 약탈은 deep_cut_moorings)
    "machine_patrol": (3,),   # 빛의 사원 경비 드론(심해 기계는 deep_dock_arms)
    "mutant_magpie":  (3,),   # 까치 떼
    "expedition_late_return": (2, 3),   # 빛 게이지 = 해가 있는 곳
    "wet_paws_at_dawn": (3,),
    "crow_paper_scrap": (3,),
}

_UNCLASSIFIED: set = set()      # acts 도 없고 표에도 없는 카드. 한 번만 알린다


def acts_of(event: dict) -> list[int]:
    """이 카드가 나올 수 있는 막. 파일의 acts > id 표 > 접두어 > (모름이면) 전 막 공용.
    모르는 카드를 1막에서 지워 버리는 대신 전 막 공용으로 두는 이유: **안 나오는 카드는
    화면에서 사라져 아무도 못 본다**(D4 막힘은 버그). 대신 목록을 표준출력에 남긴다."""
    raw = event.get("acts")
    if isinstance(raw, list):
        vals = sorted({int(a) for a in raw if isinstance(a, (int, float)) and int(a) in ALL_ACTS})
        if vals:
            return vals
    eid = event.get("id", "")
    if eid in ACT_BY_ID:
        return list(ACT_BY_ID[eid])
    for prefix, acts in ACT_BY_PREFIX:
        if eid.startswith(prefix):
            return list(acts)
    if eid and eid not in _UNCLASSIFIED:
        _UNCLASSIFIED.add(eid)
        print(f"[storyteller] acts 미지정 카드 → 전 막 공용으로 둔다: {eid}")
    return list(ALL_ACTS)


def events_for_act(act: int, events: list[dict] | None = None) -> list[dict]:
    """그 막에서 뽑힐 수 있는 카드만. 1막 풀 크기 점검(시뮬레이션)에도 쓴다."""
    return [e for e in (events if events is not None else load_events()) if act in acts_of(e)]


def load_events(files: tuple | list = EVENT_FILES) -> list[dict]:
    """사건 카드 전부를 한 풀로 병합한다. 시나리오 에이전트는 data/events_schema.json 에 맞춰 쓴다.
    파일이 없거나 깨졌거나 필수 필드가 빠진 카드는 조용히 건너뛴다(게임이 죽지 않게. 이유는 표준출력에)."""
    events: list[dict] = []
    have: set = set()
    for fname in files:
        path = DATA_DIR / fname
        if not path.exists():
            continue
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"[storyteller] {fname} 무시: {e}")
            continue
        for e in rows if isinstance(rows, list) else []:
            if not isinstance(e, dict) or e.get("id") in have:
                continue
            missing = [k for k in EVENT_REQUIRED if k not in e]
            if missing:
                print(f"[storyteller] {fname} 카드 건너뜀 ({e.get('id')}): 필수 필드 없음 {missing}")
                continue
            events.append(e); have.add(e["id"])
    return events


# ─────────────────────────────────────────────────────────────
# ★ 설계 훅: 사건 가중치
#
# 이 함수가 게임의 "성격"을 정한다. 같은 방주 상태라도 여기서
# 무엇을 크게 보느냐에 따라 게임이 잔혹해지거나 너그러워진다.
#
# 현재는 동작하는 기본 규칙(baseline)이 들어 있다. 바꿔볼 만한 방향:
#   - 약점 타격 강도: 의무실이 없을 때 전염 가중치를 얼마나 올릴까?
#     (강하면 "방주가 나를 가르친다", 약하면 "운이 나빴다"로 느껴진다)
#   - 자비 규칙: 사기가 2 이하면 긍정 사건을 강제할까?
#   - 리듬: 3일 연속 위협 뒤에는 반드시 조용한 날을 줄까?
#   - 하드코어: on이면 severity 2 사건 가중치를 얼마나 더 줄까?
# ─────────────────────────────────────────────────────────────
def weight_for(event: dict, ark: ArkState) -> float:
    w = 1.0

    # 1) 약점 타격: 대항할 방이 없으면 그 사건이 더 자주 온다 (배움의 압력)
    room = event.get("counter_room")
    if room and room not in ark.rooms:
        w *= 1.8

    # 2) 자원 결핍이 있는 곳으로 사건이 흐른다
    fail = event.get("on_fail", {})
    for res, delta in fail.items():
        if isinstance(delta, int) and delta < 0 and ark.resources.get(res, 0) <= 2:
            w *= 1.4

    # 3) 자비: 사기가 바닥이면 긍정 사건 편향
    if ark.resources.get("morale", 5) <= 2 and event.get("positive"):
        w *= 3.0

    # 4) 반복 억제
    if event["id"] in ark.recent_events[-2:]:
        w *= 0.15

    # 5) 하드코어면 심각한 사건이 더 온다 (결정 #1의 옵트인 효과)
    if ark.hardcore and event.get("severity", 0) >= 2:
        w *= 1.5

    # 6) 첫 3일은 튜토리얼 구간: 심각도 2 사건 억제
    if ark.day <= 3 and event.get("severity", 0) >= 2:
        w *= 0.3

    return w


def pick_event(ark: ArkState, events: list[dict] | None = None, rng: random.Random | None = None,
               exclude: set | None = None) -> dict:
    """exclude: 이미 소모된 1회성 카드 id(부족 첫 접촉 등). 제외하고 나면 남는 게 없을 때는
    게임이 멈추지 않도록 원래 풀로 되돌아간다."""
    events = events or load_events()
    rng = rng or random.Random()
    # 막 필터가 먼저다 — 1막(심해)에 육상 공룡·부족 카드가 섞이던 결함(dev_S3 R7)의 교정.
    # 그 막의 카드가 하나도 없으면 게임을 멈추는 대신 전체 풀로 되돌아간다(막힘은 버그).
    in_act = [e for e in events if ark.act in acts_of(e)]
    if in_act:
        events = in_act
    else:
        print(f"[storyteller] {ark.act}막 카드가 0장이라 전체 풀로 되돌아간다")
    if exclude:
        pool = [e for e in events if e["id"] not in exclude]
        if pool:
            events = pool
    weights = [weight_for(e, ark) for e in events]
    return rng.choices(events, weights=weights, k=1)[0]


def resolve(event: dict, ark: ArkState, countered: bool) -> dict:
    """사건 결과를 방주에 적용. 반환값은 변경 요약(UI 연출용)."""
    outcome = event["on_counter"] if countered else event["on_fail"]
    applied = {}
    for k, v in outcome.items():
        if k == "injured":
            ark.injured += v
            applied[k] = v
        elif k == "resident":
            ark.residents += v
            applied[k] = v
        elif isinstance(v, int):
            ark.resources[k] = max(0, ark.resources.get(k, 0) + v)
            applied[k] = v
        else:
            applied[k] = v  # capture / free_pack 등은 상위 레이어가 처리
    ark.recent_events.append(event["id"])
    ark.recent_events = ark.recent_events[-5:]
    return applied


if __name__ == "__main__":
    # 막별 카드 풀 크기 (DECISIONS 2026-09-23: 1막은 최소 24장이 목표)
    _all = load_events()
    for a in ALL_ACTS:
        pool = events_for_act(a, _all)
        print(f"  {a}막 풀 {len(pool):>2}장 / 전체 {len(_all)}장")
    # 7일 시뮬레이션: 의무실 없는 방주가 어떤 사건을 겪는지 본다 (1막 기준)
    rng = random.Random(880)
    ark = ArkState(rooms=["pantry", "well"], act=1)
    for d in range(1, 8):
        ark.day = d
        ev = pick_event(ark, rng=rng)
        countered = rng.random() < 0.4
        delta = resolve(ev, ark, countered)
        print(f"Day {d}: {ev['name']:<10} {'대항 성공' if countered else '피해'}  {delta}  → 사기 {ark.resources['morale']}, 부상 {ark.injured}")
