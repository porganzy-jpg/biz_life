"""채널별 텍스트 생성.

핵심 원칙: **같은 소재를 채널마다 다른 글로 만든다.**
네이버와 티스토리에 같은 문장이 들어가면 구글이 중복으로 판단해 한쪽을 색인에서 뺀다.
그래서 여기서 문장을 바꾸는 게 아니라 아예 다른 구조로 조립한다.

  네이버   = 그날의 일기 (감성 · 사진 위주 · 1인칭)
  티스토리 = 같은 소재의 정보형 (표 · 숫자 · 3인칭)
  인스타   = 짧은 캡션 + 해시태그
  유튜브   = 제목/설명/태그
  웹툰     = 4컷 대본
"""
from __future__ import annotations

from config import (CHANNEL_NAME, INSTAGRAM_TAGS, NAVER_KEYWORDS, OPENING,
                    SIGNATURE, SPEND_LINE)
from content import DayContent, spend_comment


def outro(day: DayContent, recent: list[int]) -> str:
    """모든 채널이 공유하는 마무리 2단 구조."""
    lines = [SPEND_LINE.format(spend=day.spend_fmt)]
    if c := spend_comment(day.spend, recent, day.day):
        lines.append(c)
    lines.append(SIGNATURE)
    return "\n".join(lines)


# ── 유튜브 쇼츠 ───────────────────────────────────────────────

def narration(day: DayContent, recent: list[int]) -> list[str]:
    """쇼츠 나레이션. 한 줄 = 한 컷. TTS에 그대로 넘긴다."""
    cuts = [OPENING, f"오늘 먹은 건 {day.meal}.", f"재료값 {day.meal_cost_fmt}원."]
    if day.note:
        cuts.append(day.note)
    cuts += outro(day, recent).split("\n")
    return cuts


def youtube_meta(day: DayContent, recent: list[int]) -> dict:
    title = f"오늘 {day.spend_fmt}원 썼습니다 | {day.meal} #shorts"
    desc = "\n".join([
        f"{day.day:%Y년 %m월 %d일}",
        f"오늘의 지출 {day.spend_fmt}원 / 오늘의 한 끼 {day.meal} ({day.meal_cost_fmt}원)",
        "",
        day.note,
        "",
        SIGNATURE,
        "",
        f"— {CHANNEL_NAME}",
        "#" + " #".join(INSTAGRAM_TAGS[:6]),
    ])
    return {"title": title[:100], "description": desc[:4900],
            "tags": INSTAGRAM_TAGS[:10], "category_id": "22"}


# ── 인스타그램 ────────────────────────────────────────────────

def instagram_caption(day: DayContent, recent: list[int]) -> str:
    return "\n".join([
        f"오늘의 지출 {day.spend_fmt}원",
        f"오늘의 한 끼 {day.meal} · {day.meal_cost_fmt}원",
        "",
        day.note,
        "",
        SIGNATURE,
        "",
        "#" + " #".join(INSTAGRAM_TAGS),
    ])


# ── 네이버 블로그 (감성 · 일기) ───────────────────────────────

def naver_draft(day: DayContent, recent: list[int]) -> str:
    photos = "\n".join(f"[사진] {p.name}" for p in day.photos) or "[사진] (오늘 찍은 것 첨부)"
    return f"""제목: {day.day:%m월 %d일} — 오늘 {day.spend_fmt}원 썼습니다

{photos}

{OPENING}

{day.note}

{day.meal}. 재료값은 {day.meal_cost_fmt}원 나왔습니다.

{outro(day, recent)}

---
검색 키워드: {', '.join(NAVER_KEYWORDS)}
※ 제목 앞쪽에 키워드를 넣을 것. 티스토리와 문장이 겹치면 안 됨.
"""


# ── 티스토리 (정보형 · 표) ────────────────────────────────────

def tistory_draft(day: DayContent, recent: list[int]) -> str:
    """티스토리는 **뼈대만** 만든다.

    본문을 자동 생성해서 그대로 올리면 애드센스 심사에서 죽는다.
    여기서 채워주는 건 그날의 진짜 숫자와 표 틀까지고, 문장은 직접 쓴다.
    """
    avg = sum(recent) // len(recent) if recent else 0
    rows = "\n".join(
        f"| {i+1}일 전 | {v:,}원 |" for i, v in enumerate(reversed(recent[-7:]))
    ) or "| — | 기록 없음 |"

    return f"""# (제목 — docs/TISTORY_FIRST_30.md 에서 고르기)

> 첫 문단에 결론 숫자부터. 검색으로 들어온 사람이 3초 안에 답을 봐야 한다.

{day.day:%Y년 %m월 %d일} 기준, 하루 지출은 **{day.spend_fmt}원**이었다.
최근 7일 평균은 {avg:,}원.

## 오늘 쓴 돈

| 항목 | 금액 |
|------|------|
| {day.meal} | {day.meal_cost_fmt}원 |
| (기타 — 직접 채우기) | |
| **합계** | **{day.spend_fmt}원** |

## 최근 7일 추이

| 날짜 | 지출 |
|------|------|
{rows}

## (여기에 본문 — 왜 이 금액이 나왔는지, 무엇을 바꿨는지)

<!-- 자동 생성된 문장을 그대로 올리지 말 것. 애드센스 심사 탈락 사유. -->

## 정리

{day.note}

{SIGNATURE}

---
<!-- 쿠팡 링크를 넣은 경우에만 아래 문구를 반드시 포함 -->
<!-- 이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다. -->
"""


# ── 웹툰 4컷 ──────────────────────────────────────────────────

def webtoon_script(day: DayContent, recent: list[int]) -> str:
    return f"""# 4컷 — {day.day:%Y-%m-%d}

1컷 | 방 안. 아저씨 누워 있음.
     대사: "{OPENING}"

2컷 | 냉장고 앞. 문 열고 들여다봄.
     대사: "{day.meal}."

3컷 | 앉아서 먹음. 표정 없음.
     대사: "{day.meal_cost_fmt}원."

4컷 | 창밖. 뒷모습.
     대사: "{SIGNATURE}"      ← 마지막 컷 말풍선은 항상 이 문장 (불변)
"""
