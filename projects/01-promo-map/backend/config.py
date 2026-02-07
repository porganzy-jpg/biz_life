"""
PromoMap - 환경 설정 (.env 기반)
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드 (프로젝트 루트)
_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / ".env")


class Settings:
    # JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "biz-life-dev-secret-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
    JWT_REFRESH_EXPIRE_DAYS: int = int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "30"))

    # Admin
    ADMIN_SESSION_SECRET: str = os.getenv("ADMIN_SESSION_SECRET", "promo-map-admin-secret-change-in-production")

    # Kakao Map
    KAKAO_MAP_API_KEY: str = os.getenv("KAKAO_MAP_API_KEY", "")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///promomap.db")

    # CORS (Android emulator uses 10.0.2.2 to reach host)
    CORS_ORIGINS: list = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8000,http://10.0.2.2:8000,http://127.0.0.1:8000"
    ).split(",")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Rate limiting
    RATE_LIMIT_AUTH: str = os.getenv("RATE_LIMIT_AUTH", "10/minute")
    RATE_LIMIT_SEARCH: str = os.getenv("RATE_LIMIT_SEARCH", "60/minute")

    # Paths
    PROJECT_ROOT: Path = _project_root
    BACKEND_DIR: Path = _project_root / "backend"
    TEMPLATES_DIR: Path = _project_root / "templates"
    STATIC_DIR: Path = _project_root / "static"
    DB_PATH: Path = BACKEND_DIR / "promomap.db"


settings = Settings()
