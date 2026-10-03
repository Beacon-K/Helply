@echo off
rem Public demo: serves Helply at https://helply.work through Cloudflare Tunnel.
rem The tunnel connects OUT to Cloudflare, so no ports need to be opened and it works on any network.
rem Needs CLOUDFLARE_TUNNEL_TOKEN (and optionally ONLINE_HOSTNAME) in .env. Public-mode settings
rem are switched on only for this window, never for normal local runs.
rem NOTE: refreshes the demo data (deletes ALL tickets) and gives every demo account a new random password.
cd /d "%~dp0"
call tools\helply-env.bat

if not exist "%HELPLY_PY%" (
  echo Helply is not set up on this computer ^(%COMPUTERNAME%^) yet. Run setup.bat once first.
  pause
  exit /b 1
)
if not exist "tools\cloudflared.exe" (
  echo tools\cloudflared.exe is missing. Download cloudflared-windows-amd64.exe from
  echo https://github.com/cloudflare/cloudflared/releases and save it as tools\cloudflared.exe
  pause
  exit /b 1
)

set "TUNNEL_TOKEN="
set "HELPLY_PUBLIC_HOST=helply.work"
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
  if /i "%%a"=="CLOUDFLARE_TUNNEL_TOKEN" set "TUNNEL_TOKEN=%%b"
  if /i "%%a"=="ONLINE_HOSTNAME" set "HELPLY_PUBLIC_HOST=%%b"
)
if not defined TUNNEL_TOKEN (
  echo No tunnel token found. Add this line to the .env file in this folder:
  echo     CLOUDFLARE_TUNNEL_TOKEN=^<token from the Cloudflare dashboard^>
  pause
  exit /b 1
)

call tools\start-db.bat
echo Preparing the demo...
"%HELPLY_PY%" manage.py migrate --verbosity 0 || goto :failed
"%HELPLY_PY%" manage.py seed_demo --reset || goto :failed
"%HELPLY_PY%" manage.py collectstatic --noinput --verbosity 0 || goto :failed

rem Production-style settings for this session only.
set "HELPLY_ENVIRONMENT=demo"
set "DJANGO_DEBUG=false"
set "HELPLY_SITE_URL=https://%HELPLY_PUBLIC_HOST%"
for /f "delims=" %%k in ('"%HELPLY_PY%" -c "import secrets; print(secrets.token_urlsafe(50))"') do set "DJANGO_SECRET_KEY=%%k"

echo.
"%HELPLY_PY%" manage.py demo_passwords --public || goto :failed
echo.

echo Connecting the Cloudflare tunnel...
start "" /b "tools\cloudflared.exe" tunnel --no-autoupdate --loglevel warn run
rem Offline detection for real monitored servers (stops when this window closes).
start "" /b "%HELPLY_PY%" manage.py monitor_check --every 30

echo.
echo ================================================================
echo   Helply is online at  https://%HELPLY_PUBLIC_HOST%
echo   Use the passwords listed above. Close this window to go offline.
echo ================================================================
echo.
rem cloudflared runs on this computer, so trust only its X-Forwarded-Proto header (it marks HTTPS visits).
"%HELPLY_PY%" -m waitress --listen=127.0.0.1:8000 --threads=8 --trusted-proxy=127.0.0.1 --trusted-proxy-headers=x-forwarded-proto config.wsgi:application
pause
exit /b 0

:failed
echo.
echo Could not start the public demo - see the error above.
pause
exit /b 1
