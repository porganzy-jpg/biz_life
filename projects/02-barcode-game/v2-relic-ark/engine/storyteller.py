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


def load_events() -> list[dict]:
    """기본 사건 + (있으면) 부족 사건. 부족 사건은 시나리오 에이전트가 data/events_schema.json 에
    맞춰 data/events_tribes.json 에 쓴다. 파일이 없거나 깨졌거나 필수 필드가 빠진 카드는 조용히 건너뛴다
    (게임이 죽지 않게. 건너뛴 이유는 표준출력에 남긴다)."""
    events = json.loads((DATA_DIR / "events.json").read_text(encoding="utf-8"))
    extra = DATA_DIR / "events_tribes.json"
    if not extra.exists():
        return events
    try:
        more = json.loads(extra.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[storyteller] events_tribes.json 무시: {e}")
        return events
    have = {e["id"] for e in events}
    for e in more if isinstance(more, list) else []:
        if not isinstance(e, dict) or e.get("id") in have:
            continue
        missing = [k for k in EVENT_REQUIRED if k not in e]
        if missing:
            print(f"[storyteller] events_tribes.json 카드 건너뜀 ({e.get('id')}): 필수 필드 없음 {missing}")
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


def pick_event(ark: ArkState, events: list[dict] | None = None, rng: random.Random | None = None) -> dict:
    events = events or load_events()
    rng = rng or random.Random()
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
    # 7일 시뮬레이션: 의무실 없는 방주가 어떤 사건을 겪는지 본다
    rng = random.Random(880)
    ark = ArkState(rooms=["pantry", "well"])
    for d in range(1, 8):
        ark.day = d
        ev = pick_event(ark, rng=rng)
        countered = rng.random() < 0.4
        delta = resolve(ev, ark, countered)
        print(f"Day {d}: {ev['name']:<10} {'대항 성공' if countered else '피해'}  {delta}  → 사기 {ark.resources['morale']}, 부상 {ark.injured}")
