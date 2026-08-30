"""하루치 콘텐츠 한 덩어리. CSV 한 줄 = 하루 = 5채널 전부의 원재료."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from config import LEDGER_CSV, ROOT


@dataclass
class DayContent:
    day: date
    spend: int            # 오늘 쓴 돈(원)
    meal: str             # 오늘의 한 끼
    meal_cost: int        # 그 한 끼의 원가(원)
    note: str             # 오늘의 한 줄
    photos: list[Path] = field(default_factory=list)
    video: Path | None = None

    @property
    def spend_fmt(self) -> str:
        return f"{self.spend:,}"

    @property
    def meal_cost_fmt(self) -> str:
        return f"{self.meal_cost:,}"


def _paths(raw: str) -> list[Path]:
    return [ROOT / p.strip() for p in raw.split(";") if p.strip()]


def load_ledger(path: Path = LEDGER_CSV) -> list[DayContent]:
    """가계부 CSV를 읽어 날짜순으로 돌려준다."""
    if not path.exists():
        raise FileNotFoundError(
            f"가계부가 없습니다: {path}\n"
            "data/ledger.csv 를 만들고 하루 한 줄씩 기록하세요. 이게 모든 콘텐츠의 원재료입니다."
        )

    rows: list[DayContent] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for i, r in enumerate(csv.DictReader(f), start=2):
            if not r.get("date", "").strip():
                continue
            try:
                video = r.get("video", "").strip()
                rows.append(DayContent(
                    day=date.fromisoformat(r["date"].strip()),
                    spend=int(r["spend"]),
                    meal=r["meal"].strip(),
                    meal_cost=int(r["meal_cost"] or 0),
                    note=r["note"].strip(),
                    photos=_paths(r.get("photos", "")),
                    video=(ROOT / video) if video else None,
                ))
            except (KeyError, ValueError) as e:
                raise ValueError(f"{path.name} {i}행을 읽을 수 없습니다: {e}") from e

    rows.sort(key=lambda d: d.day)
    return rows


def pick(rows: list[DayContent], target: date | None) -> DayContent:
    """지정 날짜의 하루를 고른다. 날짜를 안 주면 가장 최근 기록."""
    if not rows:
        raise ValueError("가계부가 비어 있습니다.")
    if target is None:
        return rows[-1]
    for d in rows:
        if d.day == target:
            return d
    raise ValueError(f"{target} 기록이 가계부에 없습니다.")


# ─────────────────────────────────────────────────────────────
# 아웃트로 바로 앞에 붙는 한 줄. 그날 영상의 '표정'을 결정한다.
#
#   "오늘, 3,200원이었습니다."
#   "그럭저럭입니다."             ← 이 함수가 만드는 문장
#   "이렇게 살아도, 삽니다."
#
# 두 가지 방식을 다 구현해 뒀다. config.SPEND_COMMENT_MODE 로 고른다.
# 톤 규칙: 자조는 되지만 비굴하면 안 된다. "돈이 없어서"가 아니라 "안 썼다"로 쓴다.
# ─────────────────────────────────────────────────────────────

# A안 — 절대값. 금액 구간이 고정이라 시청자가 기준을 외우게 된다.
#        상한선(원)과 그때의 문장. 위에서부터 처음 걸리는 구간을 쓴다.
ABSOLUTE_LADDER: list[tuple[int, str]] = [
    (0,      "한 푼도 안 썼습니다."),
    (2_000,  "거의 안 썼습니다."),
    (5_000,  "그럭저럭입니다."),
    (15_000, "오늘은 좀 썼습니다."),
]
ABSOLUTE_OVER = "오늘은 크게 썼습니다."


def spend_comment_absolute(spend: int, recent: list[int]) -> str:
    """금액 구간으로 판단한다. recent 는 쓰지 않는다.

    장점 — 규칙이 단순해서 시청자가 사다리를 외운다. 첫날부터 바로 작동한다.
    단점 — 돈을 쓴 날엔 늘 같은 문장이 나온다. 몇 달 지나면 예측된다.
    """
    for ceiling, line in ABSOLUTE_LADDER:
        if spend <= ceiling:
            return line
    return ABSOLUTE_OVER


def _median(xs: list[int]) -> int:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) // 2


def spend_comment_relative(spend: int, recent: list[int]) -> str:
    """평소 대비로 판단한다.

    장점 — 매번 문장이 달라져 안 질리고, 금액이 들어가 정보성이 붙는다.
    단점 — 왜 그런 말이 나왔는지 시청자는 모른다. 기준이 안 보인다.

    **기준선은 "돈을 쓴 날"들의 중앙값이다.** 두 번 걸러진 이유가 있다.

    1. 평균이 아니라 중앙값 — 쌀 10kg 같은 큰 지출 하나가 평균을 통째로 끌어올린다.
    2. 0원인 날을 제외 — 무지출 챌린지를 하면 0원인 날이 절반을 넘는다.
       그대로 넣으면 중앙값이 0이 되어 비율 계산 자체가 무너진다.
       (실제로 20일 샘플에서 이 필터가 없으면 문장이 세 종류밖에 안 나왔다.)
    """
    spent_days = [x for x in recent if x > 0]
    if len(spent_days) < 3:        # 비교할 게 없으면 비교하는 척하지 않는다
        return spend_comment_absolute(spend, recent)

    base = _median(spent_days)
    if spend == 0:
        return "오늘은 0원입니다."

    ratio = spend / base
    if ratio < 0.4:
        return "쓴 날 치고는 거의 안 썼습니다."
    if ratio < 0.85:
        return f"평소 쓰는 날보다 {base - spend:,}원 적습니다."
    if ratio <= 1.15:
        return "돈 쓰는 날의 평소만큼입니다."
    if ratio < 2:
        return f"평소보다 {spend - base:,}원 더 썼습니다."
    return f"평소 쓰는 날의 {ratio:.0f}배입니다."


def spend_comment(spend: int, recent: list[int]) -> str:
    """오늘 지출액을 보고 한 줄 코멘트를 만든다.

    Args:
        spend:  오늘 쓴 금액(원)
        recent: 최근 14일 지출 리스트(원). 첫 2주는 비어 있거나 짧다.

    Returns:
        한 문장(마침표 포함). 빈 문자열이면 코멘트 줄이 통째로 빠진다.
    """
    from config import SPEND_COMMENT_MODE
    if SPEND_COMMENT_MODE == "relative":
        return spend_comment_relative(spend, recent)
    return spend_comment_absolute(spend, recent)
