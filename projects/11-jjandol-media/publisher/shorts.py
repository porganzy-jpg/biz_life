# -*- coding: utf-8 -*-
"""가계부 하루 → 세로 쇼츠 mp4.

렌더 엔진을 새로 만들지 않고 `10-shorts-factory` 의 모듈을 그대로 쓴다.
거기엔 이미 해결된 함정이 여럿 박혀 있다 — edge-tts 앞뒤 무음 제거, libass 없이
PIL로 자막 PNG를 그려 overlay, ffmpeg 미설치 시 imageio-ffmpeg 폴백, zoompan 떨림 보정.
같은 문제를 두 번 풀 이유가 없다.

두 채널이 다른 건 **설정값과 컷 구성**이지 렌더 파이프라인이 아니다.
그래서 factory 를 복사하지 않고, factory 모듈이 읽는 `config` 자리에
shorts_config 를 끼워 넣는다 (아래 use_factory 참조).
"""
from __future__ import annotations

import contextlib
import sys
from pathlib import Path

import shorts_config
from config import OPENING, SIGNATURE, SIGNATURE_PAUSE_SEC, SPEND_LINE
from content import DayContent, spend_comment

FACTORY = shorts_config.ROOT.parent / "10-shorts-factory"
SPEAKER = "아저씨"

_loaded = None

# publisher 와 factory 에 같은 이름의 모듈이 둘 다 있는 것들.
# import 하는 동안만 치워두지 않으면 factory 것 대신 publisher 것이 잡힌다.
_COLLIDING = ("config", "render")


@contextlib.contextmanager
def _factory_namespace():
    """factory 모듈을 import 하는 **그 순간에만** 이름 충돌을 걷어낸다.

    publisher/config.py 와 publisher/render.py 는 factory 의 config.py, render.py 와
    이름이 정면 충돌한다. sys.modules 에 이미 publisher 것이 올라가 있으면
    `import render` 가 factory 것을 아예 읽지 않고 publisher 것을 돌려준다.

    factory 모듈들은 최상단에서 `import config` 를 한 번 하고 그 참조를 계속 들고 있으므로,
    **import 시점만** 넘기면 그 뒤로는 원상복구해도 안전하다.
    렌더 중에는 이 컨텍스트를 쓰면 안 된다 — 그 사이 publisher 코드가
    `from config import ...` 를 하면 shorts_config 를 읽어 엉뚱하게 깨진다.
    """
    saved = {n: sys.modules.pop(n, None) for n in _COLLIDING}
    sys.modules["config"] = shorts_config
    try:
        yield
    finally:
        for n in _COLLIDING:
            sys.modules.pop(n, None)
            if saved[n] is not None:
                sys.modules[n] = saved[n]


def use_factory():
    """factory 의 (parse_script, voices, render) 를 한 번만 로드해 캐시한다."""
    global _loaded
    if _loaded is None:
        if not FACTORY.exists():
            raise FileNotFoundError(
                f"쇼츠 렌더 엔진을 찾을 수 없습니다: {FACTORY}. "
                "10-shorts-factory 가 같은 projects/ 아래에 있어야 합니다."
            )
        sys.path.insert(0, str(FACTORY))
        try:
            with _factory_namespace():
                import parse_script
                import render
                import voices
            _loaded = (parse_script, voices, render)
        finally:
            sys.path.remove(str(FACTORY))
    return _loaded


def _photo_ref(day: DayContent, i: int) -> str:
    """i번째 컷이 쓸 사진. 사진이 모자라면 돌려쓰고, 하나도 없으면 빈 문자열."""
    if not day.photos:
        return ""
    p = day.photos[i % len(day.photos)]
    try:
        return str(p.relative_to(shorts_config.ROOT))
    except ValueError:
        return str(p)


def _closing_photo(day: DayContent) -> str:
    """마무리 컷(쉼 + 시그니처)이 쓸 사진. 항상 마지막 한 장."""
    if not day.photos:
        return ""
    p = day.photos[-1]
    try:
        return str(p.relative_to(shorts_config.ROOT))
    except ValueError:
        return str(p)


def build_cuts(day: DayContent, recent: list[int]):
    """하루치 데이터를 컷 리스트로 편성한다.

    고정 3막 구조를 그대로 영상으로 옮긴다 — ① 오늘의 지출 ② 오늘의 한 끼 ③ 오늘의 한 줄.
    숫자는 자막(CAPTION)으로 크게 띄운다. 썸네일에 그대로 쓸 수 있게.
    """
    parse_script, _, _ = use_factory()
    Cut = parse_script.Cut

    plan: list[tuple[str, str]] = [                 # (대사, 상단 숫자 자막)
        (OPENING, ""),
        (f"오늘 먹은 건 {day.meal}.", ""),
        (f"재료값 {day.meal_cost_fmt}원.", f"{day.meal_cost_fmt}원"),
    ]
    if day.note:
        plan.append((day.note, ""))
    plan.append((SPEND_LINE.format(spend=day.spend_fmt), f"{day.spend_fmt}원"))
    if comment := spend_comment(day.spend, recent, day.day):
        plan.append((comment, ""))

    cuts = []
    for i, (line, caption) in enumerate(plan):
        cuts.append(Cut(
            no=i + 1, speaker=SPEAKER, line=line, caption=caption,
            clip=_photo_ref(day, i),
            clip_mode=shorts_config.KENBURNS_MODES[i % len(shorts_config.KENBURNS_MODES)],
        ))

    # 시그니처 앞 0.4초 쉼. 이 문장은 쉼이 전부라 무음 컷을 하나 끼운다.
    # 닫는 두 컷은 순환에서 빼고 **항상 마지막 사진**을 쓴다.
    # 돌려쓰기에 맡기면 인덱스가 앞으로 되감겨 방금 나온 사진이 다시 나오고,
    # 여운을 남겨야 할 자리에 라면 냄비가 재등장한다.
    last_photo = _closing_photo(day)
    cuts.append(Cut(no=len(cuts) + 1, clip=last_photo, clip_mode="in",
                    length=SIGNATURE_PAUSE_SEC))
    cuts.append(Cut(no=len(cuts) + 1, speaker=SPEAKER, line=SIGNATURE,
                    clip=last_photo, clip_mode="in"))
    return cuts


def build(day: DayContent, recent: list[int], dry: bool = False) -> Path | None:
    """하루치 쇼츠를 렌더해서 mp4 경로를 돌려준다. dry=True 면 타이밍만 출력."""
    parse_script, voices, render = use_factory()

    ep = parse_script.Episode(title=f"{day.day:%Y-%m-%d}", slug=f"{day.day:%Y-%m-%d}")
    ep.cuts = build_cuts(day, recent)

    # 여기서는 이름을 바꿔치기하지 않는다. factory 모듈은 이미 shorts_config 를
    # 붙잡고 있고, 이 아래에서는 publisher 쪽 config 를 읽는 코드가 돌기 때문이다.
    voices.build_voices(ep.cuts)
    total = sum(c.duration for c in ep.cuts)

    print(f"\n[쇼츠] {len(ep.cuts)}컷 / {total:.1f}초")
    for c in ep.cuts:
        print(f"  {c.no:>2}  {c.duration:>4.2f}s  {c.line or '(쉼)'}")
    if total > 45:
        print("  [주의] 45초 초과. 쇼츠 완주율이 급감합니다. note 를 줄이세요.")
    if not day.photos:
        print("  [주의] 사진이 없어 스토리보드 카드로 렌더됩니다. 가계부 photos 칸을 채우세요.")

    if dry:
        return None
    return render.render(ep)
