@echo off
title biz_life Server Startup
echo ============================================
echo   biz_life - All Projects Startup
echo   %date% %time%
echo ============================================
echo.

set BASE=C:\Users\itzia\biz_life\projects

:: Create log directories
for %%P in (00-server-monitor 01-promo-map 02-barcode-game 03-voice-memory 04-crypto-trader 05-stock-trader 06-home-finder) do (
    if not exist "%BASE%\%%P\logs" mkdir "%BASE%\%%P\logs"
)

echo [1/7] Starting 01-promo-map (port 8000)...
cd /d "%BASE%\01-promo-map\backend"
start "01-promo-map" /min cmd /c ""%BASE%\01-promo-map\.venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000 >> "%BASE%\01-promo-map\logs\server.log" 2>&1"
timeout /t 2 /nobreak >nul

echo [2/7] Starting 02-barcode-game (port 8001)...
cd /d "%BASE%\02-barcode-game\backend"
start "02-barcode-game" /min cmd /c ""%BASE%\02-barcode-game\.venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8001 >> "%BASE%\02-barcode-game\logs\server.log" 2>&1"
timeout /t 2 /nobreak >nul

echo [3/7] Starting 03-voice-memory (port 8002)...
cd /d "%BASE%\03-voice-memory\backend"
start "03-voice-memory" /min cmd /c ""%BASE%\03-voice-memory\.venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8002 >> "%BASE%\03-voice-memory\logs\server.log" 2>&1"
timeout /t 2 /nobreak >nul

echo [4/7] Starting 04-crypto-trader (port 8081)...
cd /d "%BASE%\04-crypto-trader"
start "04-crypto-trader" /min cmd /c ""%BASE%\04-crypto-trader\.venv\Scripts\python.exe" -m scalper.run --with-dashboard >> "%BASE%\04-crypto-trader\logs\server.log" 2>&1"
timeout /t 2 /nobreak >nul

echo [5/7] Starting 05-stock-trader (port 8082)...
cd /d "%BASE%\05-stock-trader\dashboard"
start "05-stock-trader" /min cmd /c ""%BASE%\05-stock-trader\.venv\Scripts\python.exe" app.py >> "%BASE%\05-stock-trader\logs\server.log" 2>&1"
timeout /t 2 /nobreak >nul

echo [6/7] Starting 06-home-finder (port 8006)...
cd /d "%BASE%\06-home-finder"
start "06-home-finder" /min cmd /c ""%BASE%\06-home-finder\.venv\Scripts\python.exe" main.py >> "%BASE%\06-home-finder\logs\server.log" 2>&1"
timeout /t 2 /nobreak >nul

echo [7/7] Starting 00-server-monitor (port 9000 + telegram bot + monitoring)...
cd /d "%BASE%\00-server-monitor"
start "00-server-monitor" /min cmd /c ""%BASE%\00-server-monitor\.venv\Scripts\python.exe" main.py >> "%BASE%\00-server-monitor\logs\main.log" 2>&1"
timeout /t 2 /nobreak >nul

echo.
echo ============================================
echo   All projects started!
echo   Monitor: http://localhost:9000
echo ============================================
echo.
echo This window will close in 10 seconds...
timeout /t 10 /nobreak >nul
