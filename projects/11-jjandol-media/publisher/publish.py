"""하루치 콘텐츠 1개를 5채널로 내보낸다.

    python publish.py                      # 가장 최근 기록, 초안만 생성 (자격증명 불필요)
    python publish.py --date 2026-08-30
    python publish.py --youtube            # 쇼츠까지 업로드 (비공개로)
    python publish.py --youtube --public   # 바로 공개
    python publish.py --instagram          # 릴스 업로드 (공개 URL 호스팅 필요)
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Windows 콘솔 기본 코드페이지(cp949)에서 한글이 깨지는 것을 막는다.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

import render
from content import load_ledger, pick
from platforms import drafts


def main() -> int:
    ap = argparse.ArgumentParser(description="짠돌이 미디어 - 5채널 배포")
    ap.add_argument("--date", type=date.fromisoformat, default=None,
                    help="YYYY-MM-DD. 생략하면 가계부의 마지막 줄")
    ap.add_argument("--youtube", action="store_true", help="유튜브 쇼츠 업로드")
    ap.add_argument("--instagram", action="store_true", help="인스타 릴스 업로드")
    ap.add_argument("--public", action="store_true",
                    help="유튜브를 바로 공개 (기본은 비공개 업로드)")
    args = ap.parse_args()

    rows = load_ledger()
    day = pick(rows, args.date)
    recent = [d.spend for d in rows if d.day < day.day][-14:]

    out = drafts.write_all(day, recent)
    print(f"[초안] {out}")
    for f in sorted(out.iterdir()):
        print(f"        {f.name}")

    print(f"\n[아웃트로]\n{render.outro(day, recent)}\n")

    if args.youtube:
        from platforms import youtube
        if not day.video:
            print("[유튜브] 건너뜀 — 가계부의 video 칸이 비어 있습니다.")
        else:
            vid = youtube.upload(day.video, render.youtube_meta(day, recent),
                                 privacy="public" if args.public else "private")
            print(f"[유튜브] https://youtu.be/{vid}"
                  f"{'' if args.public else '  (비공개 — 확인 후 공개하세요)'}")

    if args.instagram:
        import os

        from platforms import instagram
        base = os.getenv("PUBLIC_MEDIA_BASE")
        if not (base and day.video):
            print("[인스타] 건너뜀 — PUBLIC_MEDIA_BASE 와 video 가 모두 필요합니다.")
            print("         공개 URL 호스팅이 없으면 out/instagram.txt 를 수동으로 올리세요.")
        else:
            mid = instagram.upload_reel(
                f"{base.rstrip('/')}/{day.video.name}",
                render.instagram_caption(day, recent))
            print(f"[인스타] media id {mid}")

    print("\n[수동] 티스토리 · 네이버 블로그 · 웹툰은 out/ 파일을 붙여넣으세요. (공개 API 없음)")
    return 0


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parent / ".env")
    except ImportError:
        pass
    sys.exit(main())
