@echo off
chcp 65001 >nul 2>&1
title StockBot v3.7

cd /d "%~dp0trading-bot"

:loop
echo [%date% %time%] StockBot 시작...
set PYTHONUNBUFFERED=1
echo CONFIRM | python -u trader.py >> "..\logs\trader_v37.log" 2>&1
echo [%date% %time%] StockBot 종료 (코드: %errorlevel%). 10초 후 재시작...
timeout /t 10 /nobreak >nul
goto loop
