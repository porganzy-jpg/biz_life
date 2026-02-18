@echo off
:: Run as Administrator!
echo ============================================
echo   biz_life - Firewall Setup (Tailscale only)
echo ============================================
echo.

:: Remove old rules if they exist
netsh advfirewall firewall delete rule name="biz_life - Allow Tailscale" >nul 2>&1

:: Allow project ports only through Tailscale interface
netsh advfirewall firewall add rule name="biz_life - Allow Tailscale" dir=in action=allow protocol=tcp localport=8000,8001,8002,8006,8081,8082,9000 interface="Tailscale"

if %errorlevel% equ 0 (
    echo.
    echo [OK] Firewall rules created successfully!
    echo      Ports 8000,8001,8002,8006,8081,8082,9000 are now accessible via Tailscale only.
) else (
    echo.
    echo [ERROR] Failed to create firewall rules.
    echo         Make sure to run this script as Administrator!
)

echo.
pause
