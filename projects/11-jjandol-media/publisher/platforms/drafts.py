"""API가 없는 3개 채널 — 초안 파일을 만들어 out/ 에 떨군다.

티스토리 Open API는 글쓰기 기능이 폐지됐고, 네이버 블로그와 웹툰 도전만화는
애초에 공개 업로드 API가 없다. 브라우저 자동화로 뚫을 수는 있지만
네이버는 봇 감지에 걸리면 저품질 처리가 되고, 그러면 5채널 중 협찬 수주력이
가장 높은 채널이 통째로 죽는다. 손익이 맞지 않아 의도적으로 하지 않는다.

대신 붙여넣기만 하면 되는 상태까지 만들어 둔다. 시간을 잡아먹는 건 클릭이 아니라 글이다.
"""
from __future__ import annotations

from pathlib import Path

import render
from config import OUT_DIR
from content import DayContent

FILES = {
    "naver.txt": render.naver_draft,
    "tistory.md": render.tistory_draft,
    "webtoon.md": render.webtoon_script,
    "instagram.txt": lambda d, r: render.instagram_caption(d, r),
}


def write_all(day: DayContent, recent: list[int]) -> Path:
    out = OUT_DIR / f"{day.day:%Y-%m-%d}"
    out.mkdir(parents=True, exist_ok=True)
    for name, fn in FILES.items():
        (out / name).write_text(fn(day, recent), encoding="utf-8")

    (out / "narration.txt").write_text(
        "\n".join(render.narration(day, recent)), encoding="utf-8")
    return out
