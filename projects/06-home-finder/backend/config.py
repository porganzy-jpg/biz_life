"""
HomeFinder - 환경 설정 (.env 기반)
"""
import os
from pathlib import Path
from dotenv import load_dotenv

_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / ".env")


class Settings:
    # Server
    PORT: int = int(os.getenv("HOMEFINDER_PORT", "8006"))

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///homefinder.db")

    # API Keys
    PUBLIC_DATA_API_KEY: str = os.getenv("PUBLIC_DATA_API_KEY", "")
    KAKAO_REST_API_KEY: str = os.getenv("KAKAO_REST_API_KEY", "")

    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Budget (KRW)
    BUDGET_MIN_KRW: int = int(os.getenv("BUDGET_MIN_KRW", "800000000"))
    BUDGET_MAX_KRW: int = int(os.getenv("BUDGET_MAX_KRW", "1500000000"))

    # Target areas
    TARGET_DISTRICTS: list = os.getenv(
        "TARGET_DISTRICTS",
        "마포구,용산구,성동구,광진구,영등포구,동작구,강동구,은평구,강서구,노원구"
    ).split(",")
    TARGET_CITIES: list = os.getenv(
        "TARGET_CITIES",
        "서울특별시,하남시,과천시,성남시,광명시,고양시,구리시,남양주시"
    ).split(",")
    # 경기도 근교 지역 (서울 외곽)
    TARGET_SUBURBS: list = os.getenv(
        "TARGET_SUBURBS",
        "하남시,과천시,성남시 분당구,성남시 수정구,광명시,고양시 일산동구,고양시 일산서구,고양시 덕양구,구리시,남양주시,의정부시,김포시,파주시 운정"
    ).split(",")

    # Scoring weights
    SCORE_WEIGHT_LOCATION: float = float(os.getenv("SCORE_WEIGHT_LOCATION", "0.35"))
    SCORE_WEIGHT_PRICE: float = float(os.getenv("SCORE_WEIGHT_PRICE", "0.25"))
    SCORE_WEIGHT_PROPERTY: float = float(os.getenv("SCORE_WEIGHT_PROPERTY", "0.20"))
    SCORE_WEIGHT_AREA: float = float(os.getenv("SCORE_WEIGHT_AREA", "0.20"))

    # Scraper
    SCRAPER_ENABLED: bool = os.getenv("SCRAPER_ENABLED", "true").lower() in ("true", "1", "yes")
    SCRAPER_INTERVAL_HOURS: float = float(os.getenv("SCRAPER_INTERVAL_HOURS", "24"))
    SCRAPER_TARGET_DISTRICTS: list = os.getenv(
        "SCRAPER_TARGET_DISTRICTS",
        "",
    ).split(",") if os.getenv("SCRAPER_TARGET_DISTRICTS") else []
    SCRAPER_RATE_LIMIT_SEC: float = float(os.getenv("SCRAPER_RATE_LIMIT_SEC", "2"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # CORS
    CORS_ORIGINS: list = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8006,http://127.0.0.1:8006"
    ).split(",")

    # Paths
    PROJECT_ROOT: Path = _project_root
    BACKEND_DIR: Path = _project_root / "backend"
    TEMPLATES_DIR: Path = _project_root / "templates"
    STATIC_DIR: Path = _project_root / "static"
    DATA_DIR: Path = _project_root / "data"


settings = Settings()
