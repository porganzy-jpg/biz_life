# -*- coding: utf-8 -*-
"""대본의 클립 칸을 AI 생성 테이크 기준으로 다시 쓴다.

  kkamu_stare  ->  kkamu_front_take.mp4@0.2

컷 길이(TTS 실제 길이 포함)를 보고 테이크 5초를 넘지 않는 시작 지점을 배분한다.
같은 테이크를 쓰는 컷들은 서로 다른 지점을 잡아 표정이 반복돼 보이지 않게 한다.
사물/배경/2마리 컷은 테이크로 묶지 않으므로 이름을 그대로 둔다.
"""

import collections
import unicodedata

import config
import parse_script
import takemap
import voices


def w(text: str) -> int:
    """한글은 monospace에서 2칸을 차지한다."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def pad(text: str, width: int) -> str:
    return text + " " * max(0, width - w(text))


def remap_file(path, counters) -> tuple[int, int]:
    ep = parse_script.parse(path)
    voices.build_voices(ep.cuts)
    by_no = {c.no: c for c in ep.cuts}

    lines = path.read_text(encoding="utf-8").splitlines()
    idx = [i for i, ln in enumerate(lines) if ln.lstrip().startswith("|")]
    if not idx:
        return 0, 0

    rows = [[c.strip() for c in lines[i].strip().strip("|").split("|")] for i in idx]
    header = [parse_script.COLUMN_ALIASES.get(c.lower(), c.lower()) for c in rows[0]]
    ci = header.index("clip")
    ni = header.index("no") if "no" in header else 0

    changed = 0
    for r, row in enumerate(rows):
        if r < 2 or len(row) <= ci:          # 헤더/구분선 건너뜀
            continue
        old = row[ci]
        if not old or old in takemap.STANDALONE:
            continue
        take = takemap.CLIP_TO_TAKE.get(old.split("@")[0])
        if not take:
            continue
        cut = by_no.get(int(row[ni]) if row[ni].isdigit() else -1)
        dur = cut.duration if cut else 1.5
        slot = takemap.slot_for(dur, counters[take])
        counters[take].append(slot)
        row[ci] = f"{take}.mp4@{slot}"
        changed += 1

    # 열 너비 재정렬
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    widths = [max(w(r[c]) for r in rows if r[c] != "-" * len(r[c]) or True)
              for c in range(ncol)]
    for r, row in enumerate(rows):
        if r == 1:
            cells = ["-" * max(3, widths[c]) for c in range(ncol)]
        else:
            cells = [pad(row[c], widths[c]) for c in range(ncol)]
        lines[idx[r]] = "| " + " | ".join(cells) + " |"

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return changed, len(rows) - 2


if __name__ == "__main__":
    import sys
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass

    # 테이크별로 이미 쓴 슬롯 기록. 에피소드가 바뀌어도 이어져 반복을 더 줄인다.
    counters: dict = collections.defaultdict(list)
    total = 0
    for p in sorted(config.SCRIPTS_DIR.glob("*.md")):
        ch, n = remap_file(p, counters)
        total += ch
        print(f"  {p.name:<24} {ch}/{n}컷 재매핑")
    print(f"\n총 {total}컷 -> 테이크 {len(counters)}종")
