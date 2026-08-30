# -*- coding: utf-8 -*-
"""ffmpeg 실행 헬퍼. 시스템에 ffmpeg이 없으면 imageio-ffmpeg 내장 바이너리를 쓴다."""

import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def ffmpeg_bin() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        raise RuntimeError(
            "ffmpeg을 찾을 수 없습니다. `pip install imageio-ffmpeg` 를 실행하세요."
        ) from e


def run(args: list[str], what: str = "ffmpeg") -> None:
    """ffmpeg을 실행하고 실패하면 stderr 꼬리를 붙여 예외를 던진다."""
    p = subprocess.run(
        [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if p.returncode != 0:
        tail = "\n".join((p.stderr or "").strip().splitlines()[-15:])
        raise RuntimeError(f"{what} 실패 (exit {p.returncode})\n{tail}")


def probe_duration(path: str | Path) -> float:
    """미디어 길이(초). `ffmpeg -i` 의 stderr를 파싱한다 (ffprobe 불필요)."""
    p = subprocess.run(
        [ffmpeg_bin(), "-hide_banner", "-i", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", p.stderr or "")
    if not m:
        raise RuntimeError(f"길이를 읽지 못했습니다: {path}")
    h, mn, s = m.groups()
    return int(h) * 3600 + int(mn) * 60 + float(s)


VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
AUDIO_EXTS = (".wav", ".mp3", ".m4a", ".ogg", ".aac", ".flac")
MEDIA_EXTS = VIDEO_EXTS + IMAGE_EXTS + AUDIO_EXTS


def is_image(path) -> bool:
    from pathlib import Path as _P
    return _P(path).suffix.lower() in IMAGE_EXTS


def find_asset(folder: Path, name: str) -> Path | None:
    """확장자를 생략해도 찾아준다. 없으면 None."""
    if not name:
        return None
    p = folder / name
    if p.exists():
        return p
    if not Path(name).suffix:
        for ext in MEDIA_EXTS:
            c = folder / (name + ext)
            if c.exists():
                return c
    hits = sorted(folder.glob(Path(name).stem + ".*"))
    return hits[0] if hits else None
