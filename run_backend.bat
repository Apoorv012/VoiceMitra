@echo off
rem Starts the VoiceMitra backend, reachable from other devices (your phone) on the same Wi-Fi.
rem   PC:     http://localhost:8000
rem   Phone:  the HTTPS tunnel URL, if cloudflared is installed (see below).
rem
rem Phone browsers only allow the microphone on HTTPS, so a plain http://<pc-ip>:8000 page can load
rem but cannot start a call. For voice calls from the phone, install the free tunnel once:
rem     winget install Cloudflare.cloudflared
rem then re-run this file. The phone URL is https://test-voicemitra.apoorvm.com (named tunnel
rem "voicemitra-test", set up with `cloudflared tunnel login/create/route dns`).
rem
rem First time only: run "python -m backend.seed" to create a demo patient.
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo No .venv found. Run:  python -m venv .venv ^&^& .venv\Scripts\activate ^&^& pip install -r requirements.txt
    pause
    exit /b 1
)
if not exist ".env" (
    echo No .env found. Copy .env.example to .env and fill in the API keys.
    pause
    exit /b 1
)

echo.
echo === Open on this PC:  http://localhost:8000
echo === Same-Wi-Fi addresses (phone can load pages here, but no microphone over plain http):
powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -match '^(192\.168|10\.)' } | ForEach-Object { '    http://' + $_.IPAddress + ':8000' }"

where cloudflared >nul 2>nul
if %errorlevel%==0 (
    echo === Starting HTTPS tunnel in a new window. Use on your phone:  https://test-voicemitra.apoorvm.com
    rem Named tunnel "voicemitra-test"; hostname and target are in %USERPROFILE%\.cloudflared\config.yml
    start "VoiceMitra tunnel" cloudflared tunnel run voicemitra-test
) else (
    echo === cloudflared not installed, so no HTTPS URL for the phone. Install: winget install Cloudflare.cloudflared
)
echo.

call .venv\Scripts\activate.bat
rem If the phone can't reach the PC even on the same Wi-Fi, allow port 8000 once in an admin prompt:
rem   netsh advfirewall firewall add rule name="VoiceMitra" dir=in action=allow protocol=TCP localport=8000
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
pause
