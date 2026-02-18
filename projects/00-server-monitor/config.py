"""프로젝트 설정 - 대시보드와 텔레그램 봇 공용"""
from pathlib import Path

PROJECTS_DIR = Path(r"C:\Users\itzia\biz_life\projects")

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
