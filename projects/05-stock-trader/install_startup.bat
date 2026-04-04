@echo off
chcp 65001 >nul 2>&1

set SCRIPT_PATH=%~dp0run_trader.bat
set SHORTCUT_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\StockBot.lnk

echo StockBot 시작프로그램 등록...

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%SHORTCUT_PATH%'); $sc.TargetPath = '%SCRIPT_PATH%'; $sc.WorkingDirectory = '%~dp0'; $sc.WindowStyle = 7; $sc.Save()"

if exist "%SHORTCUT_PATH%" (
    echo 등록 완료: %SHORTCUT_PATH%
    echo PC 재시작 시 StockBot이 자동으로 실행됩니다.
) else (
    echo 등록 실패
)
pause
