"""
BIZ LIFE - 통합 로깅 유틸리티
모든 프로젝트에서 일관된 로깅 설정을 사용합니다.
"""
import logging
import os
import sys
from datetime import datetime


def setup_logger(
    name: str,
    log_dir: str = None,
    level: str = "INFO",
    log_to_file: bool = True,
    log_to_console: bool = True,
) -> logging.Logger:
    """
    프로젝트별 로거 설정

    Args:
        name: 로거 이름 (프로젝트명, 예: "CryptoBot", "StockBot")
        log_dir: 로그 파일 저장 디렉토리 (None이면 프로젝트 루트/logs)
        level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: 파일 로깅 여부
        log_to_console: 콘솔 로깅 여부

    Returns:
        logging.Logger: 설정된 로거
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(
        "%(asctime)s [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if log_to_file and log_dir:
        os.makedirs(log_dir, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        file_path = os.path.join(log_dir, f"{name}_{today}.log")
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """기존 로거 반환 (없으면 기본 설정으로 생성)"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name, log_to_file=False)
    return logger
