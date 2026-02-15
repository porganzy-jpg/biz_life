@echo off
title CryptoBot Scalper (24/7)
cd /d "C:\Users\user\Desktop\biz_life\projects\04-crypto-trader"

set PYTHON=C:\Users\user\AppData\Local\Programs\Python\Python313\python.exe
set CLOUDFLARED=C:\Users\user\AppData\Local\Microsoft\WinGet\Packages\Cloudflare.cloudflared_Microsoft.Winget.Source_8wekyb3d8bbwe\cloudflared.exe
set LOG_DIR=C:\Users\user\Desktop\biz_life\projects\04-crypto-trader\logs

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

:: Start Cloudflare Tunnel in background
echo [%date% %time%] Starting Cloudflare Tunnel... >> "%LOG_DIR%\restart.log"
start "Cloudflare Tunnel" /min "%CLOUDFLARED%" tunnel --url http://localhost:8081

:loop
echo [%date% %time%] Starting bot... >> "%LOG_DIR%\restart.log"
echo [%date% %time%] Starting bot...

"%PYTHON%" -m scalper.run --with-dashboard 2>&1 | findstr /v "^$"

echo [%date% %time%] Bot stopped (exit code: %errorlevel%). Restarting in 10s... >> "%LOG_DIR%\restart.log"
echo [%date% %time%] Bot stopped. Restarting in 10 seconds...
timeout /t 10 /nobreak >nul
goto loop
