# -*- coding: utf-8 -*-
"""쇼츠 팩토리 설정 - 캐릭터 목소리, 화면 규격, 자막 스타일."""

from pathlib import Path

ROOT = Path(__file__).parent
CLIPS_DIR = ROOT / "clips"
SFX_DIR = ROOT / "sfx"
BGM_DIR = ROOT / "bgm"
SCRIPTS_DIR = ROOT / "scripts"
BUILD_DIR = ROOT / "build"
CACHE_DIR = ROOT / ".cache"

# ── 화면 규격 (유튜브 쇼츠 세로) ──────────────────────────────
WIDTH, HEIGHT, FPS = 1080, 1920, 30
CRF = 20                      # 낮을수록 고화질/큰용량 (18~23 권장)
USE_SOURCE_AUDIO = False      # 원본 촬영 소리 사용 여부. 더빙 스타일이면 False
PLACEHOLDER = True            # clips/ 에 없는 컷을 스토리보드 카드로 채움 (촬영 전용)

# 켄번스 - clips/ 에 정지 이미지(png/jpg)를 넣으면 슬로우 줌/팬으로 움직이는 컷이 된다.
# AI 이미지 1장이나 사진 1장만 있어도 컷이 채워진다. 나중에 실사 mp4로 교체하면 자동 전환.
KENBURNS = True
KENBURNS_ZOOM = 1.18                            # 1.0 = 정지. 1.3 넘으면 화질이 뭉개짐
KENBURNS_MODES = ("in", "left", "out", "right")  # 컷 번호 순서대로 순환

# ── 캐릭터 ────────────────────────────────────────────────────
# voice: edge-tts 화자 (`python -m edge_tts --list-voices` 로 목록 확인)
# pitch/rate: 목소리 개성의 핵심. 두 캐릭터를 반대 방향으로 밀어야 구분됨.
# 실제 버릇 = 캐릭터의 뼈대 (러닝개그)
#   까뮈: 물그릇에 발을 담근다  -> 논리 100%, 자기인식 0%. 약점은 언제나 '발'
#         바위의 필살기 대사 "형, 발." 두 글자로 까뮈의 권위가 끝난다
#   바위: 혼나면 소파 뒤로만 숨는다 -> 논리 0%, 정직 100%. 숨는 순간이 곧 자백
#         28kg라 엉덩이가 다 나온다. 자막 "은신 완료"
CHARACTERS = {
    "까뮈": {  # 검은 프렌치 불독 - 하이톤 속사포
        "voice": "ko-KR-SunHiNeural",
        "pitch": "+40Hz",
        "rate":  "+18%",
        "color": (255, 255, 255),   # 자막 흰색
    },
    "바위": {  # 회색 아메리칸 불리 - 저음 느릿
        "voice": "ko-KR-InJoonNeural",
        "pitch": "-35Hz",
        "rate":  "-12%",
        "color": (255, 214, 0),     # 자막 노랑
    },
}

# ── 자막 스타일 ───────────────────────────────────────────────
FONT_PATH = r"C:\Windows\Fonts\malgunbd.ttf"   # 맑은 고딕 Bold

DIALOG = {                 # 대사 자막 (화면 하단)
    "size": 82,
    "y": 1430,
    "stroke": 9,
    "stroke_color": (0, 0, 0),
    "max_chars": 13,       # 이 길이 넘으면 줄바꿈
}
CAPTION = {                # 상황 자막 (화면 상단)
    "size": 66,
    "y": 330,
    "stroke": 8,
    "stroke_color": (0, 0, 0),
    "color": (255, 255, 255),
    "max_chars": 16,
}

# ── 오디오 믹스 ───────────────────────────────────────────────
VOICE_GAIN = 1.0
SFX_GAIN   = 0.55
BGM_GAIN   = 0.12          # 대사를 덮지 않도록 아주 낮게
TAIL_PAD   = 0.12          # 대사 끝나고 남기는 여백(초)

# edge-tts 출력 앞뒤 무음 제거 (이 장르에서는 사실상 필수)
TRIM_SILENCE = True
SILENCE_DB   = -45         # 이 값보다 조용하면 무음으로 간주. -50이면 더 바짝 자름


# ══════════════════════════════════════════════════════════════
# TODO(사용자 결정): 컷 길이 확정 로직
# ══════════════════════════════════════════════════════════════
# 이 장르의 핵심 긴장은 "빠른 컷 리듬" vs "대사 전달"입니다.
# 대본에 1.2초라고 썼는데 TTS가 1.9초 나오면 어떻게 할까요?
#
#   A) 대사 우선  : 컷을 1.9초로 늘림   → 대사 다 들림, 리듬이 늘어짐
#   B) 리듬 우선  : 1.2초 유지 + rate 상향 → 리듬 유지, 급하게 들림(이 장르 특유의 맛)
#   C) 절충      : max(대본길이, 대사길이) 하되 상한 CUT_MAX 로 잘라냄
#
# 지금은 C를 기본값으로 넣어뒀습니다. 몇 편 뽑아보고 취향대로 바꾸세요.
CUT_MAX = 3.0   # 컷 최대 길이(초). 이 장르에서 3초 넘으면 스크롤 넘어갑니다.
CUT_MIN = 0.6

def resolve_cut_duration(spec_len: float, voice_len: float) -> float:
    """대본에 적힌 길이와 실제 TTS 길이로 최종 컷 길이(초)를 결정한다.

    spec_len : 대본 '길이' 칸의 값 (대사 없는 컷이면 이 값이 그대로 쓰임)
    voice_len: edge-tts가 만든 오디오 실제 길이. 대사 없으면 0.0
    """
    need = voice_len + TAIL_PAD if voice_len else 0.0
    return max(CUT_MIN, min(max(spec_len, need), CUT_MAX))
