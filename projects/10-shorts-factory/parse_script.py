# -*- coding: utf-8 -*-
"""대본 마크다운(.md)의 표를 컷 리스트로 변환한다.

표 형식 (열 순서는 자유, 헤더 이름으로 매칭):

    | # | 길이 | 클립           | 화자 | 대사      | 자막     | 효과음 |
    |---|------|----------------|------|-----------|----------|--------|
    | 1 | 1.3  | bawi_sleep.mp4 |      |           | 月 06:00 | snore  |
    | 2 | 1.1  | kkamu.mp4@12.5 | 까뮈 | 일어나.   |          | thud   |

클립 칸의 `@12.5` 는 "원본 영상 12.5초 지점부터" 라는 뜻.
길게 찍은 한 테이크에서 순간을 여러 개 뽑아 쓸 때 사용한다.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

# 헤더 이름 → 내부 필드명
COLUMN_ALIASES = {
    "#": "no", "no": "no", "컷": "no",
    "길이": "length", "len": "length", "초": "length",
    "클립": "clip", "화면": "clip", "clip": "clip",
    "화자": "speaker", "speaker": "speaker",
    "대사": "line", "line": "line",
    "자막": "caption", "caption": "caption",
    "효과음": "sfx", "sfx": "sfx", "se": "sfx",
}

EMPTY = {"", "-", "—", "–", "ㅡ"}


@dataclass
class Cut:
    no: int
    length: float = 1.5
    clip: str = ""            # 파일명 (없으면 검은 화면)
    clip_start: float = 0.0   # 원본에서 잘라올 시작 지점 (영상)
    clip_mode: str = ""       # 켄번스 모드 in/out/left/right (정지 이미지)
    speaker: str = ""
    line: str = ""
    caption: str = ""
    sfx: str = ""
    # 렌더 단계에서 채워짐
    voice_path: Path | None = None
    duration: float = 0.0


@dataclass
class Episode:
    title: str
    slug: str
    cuts: list[Cut] = field(default_factory=list)
    bgm: str = ""

    @property
    def total(self) -> float:
        return sum(c.duration or c.length for c in self.cuts)


def _cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def _is_separator(row: str) -> bool:
    return bool(re.fullmatch(r"[|\s:\-—]+", row))


def _num(text: str, default: float) -> float:
    m = re.search(r"\d+(?:\.\d+)?", text or "")
    return float(m.group()) if m else default


def parse(path: str | Path) -> Episode:
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines()

    title = path.stem
    bgm = ""
    for ln in lines:
        if ln.startswith("# "):
            title = ln[2:].strip()
            break
    for ln in lines:
        m = re.match(r"^\s*>\s*bgm\s*[:：]\s*(.+)$", ln, re.I)
        if m:
            bgm = m.group(1).strip()

    header: list[str] | None = None
    cuts: list[Cut] = []

    for ln in lines:
        if not ln.lstrip().startswith("|"):
            continue
        if _is_separator(ln):
            continue
        cells = _cells(ln)

        if header is None:
            # 첫 표 행을 헤더로 간주
            header = [COLUMN_ALIASES.get(c.lower(), c.lower()) for c in cells]
            if "length" not in header and "clip" not in header:
                raise ValueError(
                    f"{path.name}: 표 헤더에 '길이' 또는 '클립' 열이 필요합니다. 찾은 헤더={cells}"
                )
            continue

        row = {k: (v if v not in EMPTY else "") for k, v in zip(header, cells)}
        if not any(row.values()):
            continue

        clip, start, mode = row.get("clip", ""), 0.0, ""
        if "@" in clip:
            clip, _, off = clip.partition("@")
            clip, off = clip.strip(), off.strip()
            if re.fullmatch(r"\d+(?:\.\d+)?", off):
                start = float(off)        # 영상: 시작 지점(초)
            else:
                mode = off.lower()        # 이미지: 켄번스 모드

        speaker = row.get("speaker", "")
        line = row.get("line", "")
        if not speaker and ":" in line:            # "까뮈: 일어나." 형태도 허용
            speaker, _, line = line.partition(":")
            speaker, line = speaker.strip(), line.strip()

        cuts.append(Cut(
            no=int(_num(row.get("no", ""), len(cuts) + 1)),
            length=_num(row.get("length", ""), 1.5),
            clip=clip,
            clip_start=start,
            clip_mode=mode,
            speaker=speaker,
            line=line,
            caption=row.get("caption", ""),
            sfx=row.get("sfx", ""),
        ))

    if not cuts:
        raise ValueError(f"{path.name}: 컷을 하나도 찾지 못했습니다. 표 형식을 확인하세요.")

    return Episode(title=title, slug=path.stem, cuts=cuts, bgm=bgm)


if __name__ == "__main__":
    import sys
    for _s in (sys.stdout, sys.stderr):
        try: _s.reconfigure(encoding='utf-8', errors='replace')
        except Exception: pass

    import sys
    ep = parse(sys.argv[1])
    print(f"{ep.title}  ({len(ep.cuts)}컷, 대본상 {ep.total:.1f}초)")
    for c in ep.cuts:
        who = f"{c.speaker}: " if c.speaker else ""
        print(f"  {c.no:>2} {c.length:>4.1f}s  {c.clip or '(검은화면)':<24} {who}{c.line}")
