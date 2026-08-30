# -*- coding: utf-8 -*-
"""쇼츠 렌더 CLI.

  python make.py scripts/ep01_monday.md      # 렌더
  python make.py --all                       # scripts/*.md 전부
  python make.py scripts/ep01_monday.md --dry  # 대본 검증 + 타이밍만 출력 (렌더 X)
"""

import argparse
import sys
from pathlib import Path

import config
import parse_script
import voices
from ffutil import find_asset


def build(path: Path, dry: bool) -> None:
    ep = parse_script.parse(path)
    print(f"\n[{ep.title}]  {len(ep.cuts)}컷")

    voices.build_voices(ep.cuts)
    total = sum(c.duration for c in ep.cuts)

    if dry:
        for c in ep.cuts:
            flag = "  <- 길이 조정됨" if abs(c.duration - c.length) > 0.05 else ""
            who = f"{c.speaker}: " if c.speaker else ""
            print(f"  {c.no:>2} 대본{c.length:>4.1f}s → 실제{c.duration:>4.2f}s  {who}{c.line}{flag}")
        print(f"\n  총 {total:.1f}초")
        if total > 45:
            print("  [주의] 45초 초과. 쇼츠 완주율이 급감합니다. 컷을 줄이세요.")
        return

    import render
    out = render.render(ep)
    print(f"\n  완성: {out}  ({total:.1f}초)")


def shotlist(paths) -> None:
    """대본들이 요구하는 클립 목록을 뽑아 촬영 체크리스트로 출력한다."""
    need: dict[str, list[str]] = {}
    for p in paths:
        ep = parse_script.parse(p)
        for c in ep.cuts:
            if c.clip:
                need.setdefault(c.clip, []).append(f"{ep.slug}#{c.no}")

    have = sorted(n for n in need if find_asset(config.CLIPS_DIR, n))
    todo = sorted(n for n in need if n not in have)

    print()
    print(f"촬영 체크리스트  (필요 {len(need)}컷 / 확보 {len(have)} / 미촬영 {len(todo)})")
    print()
    for name in todo:
        uses = need[name]
        mark = f"  (재사용 {len(uses)}회)" if len(uses) > 1 else ""
        print(f"  [ ] {name:<22}{mark}")
    if have:
        print()
        print(f"  확보됨: {', '.join(have)}")
    print()
    print("  파일명 그대로 clips/ 에 넣으세요. 확장자는 mp4/mov 아무거나 됩니다.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("script", nargs="?", help="대본 .md 경로")
    ap.add_argument("--all", action="store_true", help="scripts/ 전체 렌더")
    ap.add_argument("--dry", action="store_true", help="렌더 없이 타이밍만 확인")
    ap.add_argument("--shotlist", action="store_true", help="필요한 촬영 클립 목록 출력")
    args = ap.parse_args()

    if args.all:
        paths = sorted(config.SCRIPTS_DIR.glob("*.md"))
    elif args.script:
        paths = [Path(args.script)]
    else:
        ap.print_help()
        return 1

    if not paths:
        print("대본을 찾지 못했습니다.")
        return 1

    if args.shotlist:
        shotlist(paths)
        return 0

    for p in paths:
        try:
            build(p, args.dry)
        except Exception as e:
            print(f"\n  [실패] {p.name}: {e}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    import sys
    for _s in (sys.stdout, sys.stderr):
        try: _s.reconfigure(encoding='utf-8', errors='replace')
        except Exception: pass

    raise SystemExit(main())
