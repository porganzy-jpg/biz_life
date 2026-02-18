@echo off
echo ============================================
echo   Server Monitor 자동 시작 설정
echo ============================================
echo.

set TARGET=C:\Users\itzia\biz_life\projects\startup_all.bat
set SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\biz_life_startup.lnk
set VBS_TEMP=%TEMP%\create_shortcut.vbs

echo 시작 프로그램 폴더에 바로가기 생성 중...

:: VBScript로 바로가기 생성
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%VBS_TEMP%"
echo sLinkFile = "%SHORTCUT%" >> "%VBS_TEMP%"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%VBS_TEMP%"
echo oLink.TargetPath = "%TARGET%" >> "%VBS_TEMP%"
echo oLink.WorkingDirectory = "C:\Users\itzia\biz_life\projects" >> "%VBS_TEMP%"
echo oLink.WindowStyle = 7 >> "%VBS_TEMP%"
echo oLink.Description = "biz_life 전체 프로젝트 자동 시작" >> "%VBS_TEMP%"
echo oLink.Save >> "%VBS_TEMP%"

cscript //nologo "%VBS_TEMP%"
del "%VBS_TEMP%"

if exist "%SHORTCUT%" (
    echo.
    echo 설정 완료!
    echo 바로가기: %SHORTCUT%
    echo 다음 부팅부터 자동으로 모든 프로젝트가 시작됩니다.
) else (
    echo.
    echo 설정 실패. 수동으로 시작 프로그램 폴더에 추가하세요.
    echo 경로: %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
)
echo.
pause
