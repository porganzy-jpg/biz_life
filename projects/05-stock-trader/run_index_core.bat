@echo off
chcp 65001 >nul 2>&1
REM v4.0 지수 코어: 평일 장 마감 후 1회 실행 (작업 스케줄러 "StockBot_IndexCore" 15:45)
cd /d "%~dp0trading-bot"
if not exist "..\logs" mkdir "..\logs"
set PYTHONUNBUFFERED=1
python -u index_core_trader.py >> "..\logs\index_core.log" 2>&1
