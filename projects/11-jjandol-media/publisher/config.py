"""프로젝트 전역 상수. 시그니처 문장은 여기 한 곳에서만 정의한다."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── 시그니처 (1년간 변경 금지) ────────────────────────────────
OPENING = "오늘도 안 치웠습니다."
SIGNATURE = "이렇게 살아도, 삽니다."

# 변수부 템플릿. {spend}에 콤마 찍힌 금액이 들어간다.
SPEND_LINE = "오늘, {spend}원이었습니다."

# 시그니처 앞 쉼. TTS 합성 시 이 길이만큼 무음을 끼운다.
SIGNATURE_PAUSE_SEC = 0.4

CHANNEL_NAME = "월 30만원 아저씨"

# ── 경로 ──────────────────────────────────────────────────────
LEDGER_CSV = ROOT / "data" / "ledger.csv"
OUT_DIR = ROOT / "out"

# ── 플랫폼별 해시태그 / 키워드 ────────────────────────────────
INSTAGRAM_TAGS = [
    "1인가구", "자취", "짠테크", "무지출챌린지", "절약",
    "자취생", "생활비", "가계부", "절약생활", "자취요리",
]
NAVER_KEYWORDS = ["1인가구 식비", "자취 생활비", "무지출 챌린지", "짠테크"]
