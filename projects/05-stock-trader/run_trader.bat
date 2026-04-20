@echo off
chcp 65001 >nul 2>&1
title StockBot v3.7

REM === 대시보드 서버 (백그라운드) ===
start "StockBot Dashboard" /min cmd /c "cd /d "%~dp0dashboard" && python -u app.py >> "%~dp0logs\dashboard.log" 2>&1"
echo [%date% %time%] 대시보드 서버 시작 (http://localhost:8082)

REM === 트레이딩 봇 (자동 재시작 루프) ===
cd /d "%~dp0trading-bot"

:loop
echo [%date% %time%] StockBot 시작...
set PYTHONUNBUFFERED=1
echo CONFIRM | python -u trader.py >> "..\logs\trader_v37.log" 2>&1
echo [%date% %time%] StockBot 종료 (코드: %errorlevel%). 10초 후 재시작...
timeout /t 10 /nobreak >nul
goto loop
