# -*- coding: utf-8 -*-
"""쇼츠 렌더 설정 — 10-shorts-factory 의 config 계약을 만족한다.

이 파일은 렌더 중에만 `config` 라는 이름으로 factory 모듈에 주입된다 (shorts.py 참조).
강아지 채널(10-shorts-factory/config.py)과 **같은 계약, 다른 값**이다.
그 채널은 빠른 컷 개그, 이쪽은 느린 사진 슬라이드라 거의 모든 값이 반대로 간다.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 사진 경로는 가계부에 ROOT 기준 상대경로로 적히므로 CLIPS_DIR 이 곧 ROOT 다.
CLIPS_DIR = ROOT
SFX_DIR = ROOT / "sfx"
BGM_DIR = ROOT / "bgm"
BUILD_DIR = ROOT / "build"
CACHE_DIR = ROOT / ".cache"

# ── 화면 규격 (유튜브 쇼츠 / 인스타 릴스 공용 세로) ────────────
WIDTH, HEIGHT, FPS = 1080, 1920, 30
CRF = 20
PLACEHOLDER = True          # 사진이 없는 컷은 스토리보드 카드로 채운다

# 켄번스 — 실사 사진 한 장을 움직이는 컷으로 만든다.
# 강아지 채널은 1.18인데 여기는 1.08이다. 정지 사진에 줌이 세면 싸구려로 보이고,
# 이 채널의 톤(무심함, 느림)과 정면으로 어긋난다. 거의 안 움직이는 정도가 맞다.
KENBURNS = True
KENBURNS_ZOOM = 1.08
KENBURNS_MODES = ("in", "left", "out", "right")

# ── 화자 ──────────────────────────────────────────────────────
# 강아지 채널 '바위'의 저음 세팅을 그대로 가져왔다. 이 톤이 컨셉과 정확히 맞는다.
CHARACTERS = {
    "아저씨": {
        "voice": "ko-KR-InJoonNeural",
        "pitch": "-35Hz",
        "rate":  "-12%",
        "color": (255, 255, 255),
    },
}

# ── 자막 ──────────────────────────────────────────────────────
FONT_PATH = r"C:\Windows\Fonts\malgunbd.ttf"

DIALOG = {                  # 나레이션 자막 (하단)
    "size": 72,             # 강아지 채널(82)보다 작다. 문장이 길고 개그가 아니다
    "y": 1480,
    "stroke": 8,
    "stroke_color": (0, 0, 0),
    "max_chars": 15,
}
CAPTION = {                 # 숫자 (상단) — 이 채널의 주인공
    "size": 132,            # 크게. 썸네일에서도 이 숫자만 보이면 된다
    "y": 380,
    "stroke": 11,
    "stroke_color": (0, 0, 0),
    "color": (255, 214, 0),
    "max_chars": 10,
}

# ── 오디오 ────────────────────────────────────────────────────
VOICE_GAIN = 1.0
SFX_GAIN = 0.55
BGM_GAIN = 0.10
TAIL_PAD = 0.35             # 느린 톤이라 말끝 여백을 강아지 채널(0.12)보다 길게

TRIM_SILENCE = True         # edge-tts 앞뒤 무음 제거. 안 하면 컷마다 1초씩 붕 뜬다
SILENCE_DB = -45


# ── 컷 길이 정책 ──────────────────────────────────────────────
# 강아지 채널은 C안(절충, 상한 3.0초)을 썼다. 빠른 컷 리듬이 그 장르의 맛이라서다.
# 이 채널은 **A안(대사 우선)** 이다. 사진 슬라이드에 무심한 나레이션이라
# 말이 잘리면 아무것도 안 남는다. 리듬보다 전달이 먼저다.
CUT_MAX = 5.0
CUT_MIN = 0.9


def resolve_cut_duration(spec_len: float, voice_len: float) -> float:
    """대사 길이를 그대로 쓰고 상한으로만 자른다.

    spec_len 은 대사 없는 컷(시그니처 앞 0.4초 쉼)에만 의미가 있다.
    """
    if not voice_len:
        return max(0.3, min(spec_len, CUT_MAX))
    return max(CUT_MIN, min(voice_len + TAIL_PAD, CUT_MAX))
