@echo off
title CryptoBot Scalper (24/7)
cd /d "C:\Users\itzia\biz_life\projects\04-crypto-trader"

set PYTHON=C:\Users\itzia\biz_life\projects\04-crypto-trader\.venv\Scripts\python.exe
set LOG_DIR=C:\Users\itzia\biz_life\projects\04-crypto-trader\logs

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

:loop
echo [%date% %time%] Starting bot... >> "%LOG_DIR%\restart.log"
echo [%date% %time%] Starting bot...

"%PYTHON%" -m scalper.run --with-dashboard 2>&1 | findstr /v "^$"

echo [%date% %time%] Bot stopped (exit code: %errorlevel%). Restarting in 10s... >> "%LOG_DIR%\restart.log"
echo [%date% %time%] Bot stopped. Restarting in 10 seconds...
timeout /t 10 /nobreak >nul
goto loop
