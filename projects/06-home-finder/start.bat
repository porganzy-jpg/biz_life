@echo off
echo ============================================
echo   HomeFinder - 마지막 집 찾기
echo ============================================
echo.

cd /d "%~dp0"

:: .env 체크
if not exist .env (
    echo [!] .env 파일이 없습니다.
    echo     .env.example을 복사해서 API 키를 입력하세요:
    echo.
    echo     copy .env.example .env
    echo     notepad .env
    echo.
    pause
    exit /b 1
)

:: 패키지 설치 확인
echo [1/3] 패키지 확인 중...
pip install -r requirements.txt -q 2>nul

:: 서버 시작
echo [2/3] HomeFinder 서버 시작 (http://localhost:8006)
start "HomeFinder Server" cmd /k python main.py

:: Cloudflare Tunnel (핸드폰 접속)
echo [3/3] Cloudflare Tunnel 시작 (핸드폰 접속용)
timeout /t 5 /nobreak >nul

where cloudflared >nul 2>&1
if %errorlevel% equ 0 (
    start "Cloudflare Tunnel" cmd /k cloudflared tunnel --url http://localhost:8006
    echo.
    echo [OK] Cloudflare Tunnel 창에서 https://xxx.trycloudflare.com URL을 확인하세요
) else (
    :: WinGet 설치 경로 확인
    for /f "delims=" %%i in ('where /r "%LOCALAPPDATA%\Microsoft\WinGet" cloudflared.exe 2^>nul') do (
        start "Cloudflare Tunnel" cmd /k "%%i" tunnel --url http://localhost:8006
        echo.
        echo [OK] Cloudflare Tunnel 창에서 https://xxx.trycloudflare.com URL을 확인하세요
        goto :done
    )
    echo [!] cloudflared가 설치되지 않았습니다.
    echo     설치: winget install Cloudflare.cloudflared
    echo     핸드폰 접속 없이 localhost:8006으로만 사용 가능합니다.
)

:done
echo.
echo ============================================
echo   브라우저: http://localhost:8006
echo   핸드폰:   Cloudflare Tunnel 창의 URL
echo ============================================
echo.
pause
