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
#   "___________________"        ← 이 함수가 만드는 문장
#   "이렇게 살아도, 삽니다."
#
# TODO(user): 아래 함수를 채워주세요. 이건 캐릭터의 목소리라 대신 정할 수 없습니다.
#
# 판단해야 할 것 — 기준을 절대값으로 둘지, 상대값으로 둘지:
#   · 절대값 (예: 5,000원 미만이면 "잘 버텼다")
#       → 규칙이 단순하고 시청자가 기준을 외우게 된다. 대신 돈을 쓴 날엔 늘 같은 말이 나온다.
#   · 상대값 (최근 14일 평균 대비)
#       → 매번 문장이 달라져 안 질린다. 대신 시청자는 왜 그런 말이 나왔는지 모른다.
#
# 톤 주의: 자조는 되지만 비굴하면 안 된다. "돈이 없어서"가 아니라 "안 썼다"로 쓸 것.
# 길이는 8~20자. 이 뒤에 0.4초 쉼이 오고 시그니처가 나온다.
# ─────────────────────────────────────────────────────────────
def spend_comment(spend: int, recent: list[int]) -> str:
    """오늘 지출액을 보고 한 줄 코멘트를 만든다.

    Args:
        spend:  오늘 쓴 금액(원)
        recent: 최근 14일 지출 리스트(원). 첫 2주 동안은 비어 있거나 짧을 수 있다.

    Returns:
        한 문장(마침표 포함). 빈 문자열을 돌려주면 코멘트 줄이 통째로 빠진다.
    """
    return ""  # ← 여기를 채우면 모든 채널의 문장에 자동 반영됩니다
