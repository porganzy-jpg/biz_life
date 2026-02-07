"""
BIZ LIFE - .env 기반 설정 로더
각 프로젝트의 .env 파일을 읽어 설정값을 관리합니다.
"""
import os
from dotenv import load_dotenv


class ConfigLoader:
    """환경변수 기반 설정 관리"""

    def __init__(self, env_path: str = None):
        """
        Args:
            env_path: .env 파일 경로 (None이면 현재 디렉토리)
        """
        if env_path and os.path.exists(env_path):
            load_dotenv(env_path)
        else:
            load_dotenv()

    def get(self, key: str, default: str = None) -> str:
        """환경변수 조회"""
        return os.getenv(key, default)

    def get_int(self, key: str, default: int = 0) -> int:
        """정수형 환경변수 조회"""
        val = os.getenv(key)
        if val is None:
            return default
        try:
            return int(val)
        except ValueError:
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        """실수형 환경변수 조회"""
        val = os.getenv(key)
        if val is None:
            return default
        try:
            return float(val)
        except ValueError:
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """불리언 환경변수 조회"""
        val = os.getenv(key, "").lower()
        if val in ("true", "1", "yes", "on"):
            return True
        if val in ("false", "0", "no", "off"):
            return False
        return default

    def get_list(self, key: str, separator: str = ",", default: list = None) -> list:
        """리스트형 환경변수 조회"""
        val = os.getenv(key)
        if val is None:
            return default or []
        return [item.strip() for item in val.split(separator) if item.strip()]

    def require(self, key: str) -> str:
        """필수 환경변수 조회 (없으면 에러)"""
        val = os.getenv(key)
        if val is None:
            raise EnvironmentError(f"Required environment variable '{key}' is not set")
        return val
