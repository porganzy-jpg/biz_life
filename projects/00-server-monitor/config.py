"""프로젝트 설정 - 대시보드와 텔레그램 봇 공용"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECTS_DIR = Path(r"C:\Users\itzia\biz_life\projects")

# === 스마트 알림 & 이상 탐지 설정 ===
ALERT_CONFIG = {
    # 알림 활성화 여부
    "ALERT_ENABLED": os.getenv("ALERT_ENABLED", "true").lower() in ("true", "1", "yes"),

    # 임계치 설정
    "CPU_THRESHOLD": float(os.getenv("CPU_THRESHOLD", "85")),
    "MEMORY_THRESHOLD": float(os.getenv("MEMORY_THRESHOLD", "80")),
    "DISK_THRESHOLD": float(os.getenv("DISK_THRESHOLD", "90")),
    "DISK_PREDICT_TARGET": float(os.getenv("DISK_PREDICT_TARGET", "95")),

    # 이상 탐지 파라미터
    "CPU_STD_MULTIPLIER": float(os.getenv("CPU_STD_MULTIPLIER", "2.0")),      # CPU 표준편차 배수
    "CPU_CONSECUTIVE_MIN": int(os.getenv("CPU_CONSECUTIVE_MIN", "3")),         # CPU 연속 이상 최소 횟수
    "MEMORY_LEAK_MINUTES": int(os.getenv("MEMORY_LEAK_MINUTES", "30")),        # 메모리 누수 판단 시간(분)
    "DISK_GROWTH_RATE_THRESHOLD": float(os.getenv("DISK_GROWTH_RATE_THRESHOLD", "1.0")),  # 디스크 증가율 %/시간
    "RESTART_STORM_COUNT": int(os.getenv("RESTART_STORM_COUNT", "3")),         # 재시작 폭풍 횟수
    "RESTART_STORM_WINDOW_MINUTES": int(os.getenv("RESTART_STORM_WINDOW_MINUTES", "10")),  # 재시작 폭풍 윈도우(분)

    # 쿨다운 및 주기 설정
    "ALERT_COOLDOWN_MINUTES": int(os.getenv("ALERT_COOLDOWN_MINUTES", "30")),  # 동일 알림 쿨다운(분)
    "METRICS_COLLECT_INTERVAL": int(os.getenv("METRICS_COLLECT_INTERVAL", "60")),  # 메트릭 수집 간격(초)
    "ANOMALY_CHECK_INTERVAL": int(os.getenv("ANOMALY_CHECK_INTERVAL", "120")),  # 이상 탐지 주기(초)
    "METRICS_MAX_ENTRIES": int(os.getenv("METRICS_MAX_ENTRIES", "1440")),       # 최대 메트릭 항목(24h x 60분)

    # 유지보수 윈도우 기본값
    "MAINTENANCE_WINDOW_DEFAULT_HOURS": int(os.getenv("MAINTENANCE_WINDOW_DEFAULT_HOURS", "2")),
}

# 각 프로젝트의 실행 정보
PROJECTS = {
    "01-promo-map": {
        "port": 8000,
        "desc": "프로모션 지도",
        "cwd": "backend",
        "cmd": [".venv/Scripts/python.exe", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
    },
    "02-barcode-game": {
        "port": 8001,
        "desc": "바코드 게임",
        "cwd": "backend",
        "cmd": [".venv/Scripts/python.exe", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"],
    },
    "03-voice-memory": {
        "port": 8002,
        "desc": "음성 메모리",
        "cwd": "backend",
        "cmd": [".venv/Scripts/python.exe", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"],
    },
    "04-crypto-trader": {
        "port": 8081,
        "desc": "암호화폐 트레이더",
        "cwd": ".",
        "cmd": [".venv/Scripts/python.exe", "-m", "scalper.run", "--with-dashboard"],
    },
    "05-stock-trader": {
        "port": 8082,
        "desc": "주식 트레이더",
        "cwd": "dashboard",
        "cmd": [".venv/Scripts/python.exe", "app.py"],
    },
    "06-home-finder": {
        "port": 8006,
        "desc": "집 찾기",
        "cwd": ".",
        "cmd": [".venv/Scripts/python.exe", "main.py"],
    },
}

# === 자동 배포 설정 ===
DEPLOY_CONFIG = {
    "DEPLOY_ENABLED": os.getenv("DEPLOY_ENABLED", "true").lower() in ("true", "1", "yes"),
    "DEPLOY_WEBHOOK_SECRET": os.getenv("DEPLOY_WEBHOOK_SECRET", ""),
    "DEPLOY_REPO_DIR": os.getenv("DEPLOY_REPO_DIR", str(PROJECTS_DIR.parent)),  # biz_life 루트
    "DEPLOY_AUTO_RESTART": os.getenv("DEPLOY_AUTO_RESTART", "true").lower() in ("true", "1", "yes"),
}
