@echo off
rem Serves Helply at https://helply.work through Cloudflare Tunnel.
rem The tunnel connects OUT to Cloudflare, so no ports need to be opened and it works on any network.
rem Needs CLOUDFLARE_TUNNEL_TOKEN (and optionally ONLINE_HOSTNAME) in .env. Public-mode settings
rem are switched on only for this window, never for normal local runs.
rem
rem Starting this file never changes your data: no tickets are deleted, no passwords or people are reset.
rem Demo data is loaded only when the database has no users at all (a brand-new install). To wipe the
rem demo and start it over on purpose, run reset-demo.bat.
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

netstat -ano | findstr /r /c:"127.0.0.1:8000 .*LISTENING" >nul
if not errorlevel 1 (
  echo Port 8000 is already in use - probably the start-demo.bat window is still open.
  echo Close that window first, then run this file again.
  pause
  exit /b 1
)

call tools\start-db.bat
echo Applying database updates...
"%HELPLY_PY%" manage.py migrate --verbosity 0 || goto :failed
rem Only a brand-new, empty database gets demo data (public mode: each account gets its own one-time password).
"%HELPLY_PY%" manage.py seed_demo --if-empty || goto :failed
"%HELPLY_PY%" manage.py collectstatic --noinput --verbosity 0 || goto :failed

rem Production-style settings for this session only.
set "HELPLY_ENVIRONMENT=demo"
set "DJANGO_DEBUG=false"
set "HELPLY_SITE_URL=https://%HELPLY_PUBLIC_HOST%"
for /f "delims=" %%k in ('"%HELPLY_PY%" -c "import secrets; print(secrets.token_urlsafe(50))"') do set "DJANGO_SECRET_KEY=%%k"

echo Connecting the Cloudflare tunnel...
start "" /b "tools\cloudflared.exe" tunnel --no-autoupdate --protocol http2 --loglevel warn run
rem Scheduled jobs: SLA checks, ticket follow-ups, renewal reminders, daily backup (stop when this window closes).
start "" /b "%HELPLY_PY%" manage.py run_jobs --every 5
rem Offline detection for monitored servers.
start "" /b "%HELPLY_PY%" manage.py monitor_check --every 30

echo.
echo ================================================================
echo   Helply is online at  https://%HELPLY_PUBLIC_HOST%
echo   Close this window to go offline. Your data is kept.
echo ================================================================
echo.
rem cloudflared runs on this computer, so trust only its X-Forwarded-Proto header (it marks HTTPS visits).
"%HELPLY_PY%" -m waitress --listen=127.0.0.1:8000 --threads=8 --trusted-proxy=127.0.0.1 --trusted-proxy-headers=x-forwarded-proto config.wsgi:application
pause
exit /b 0

:failed
echo.
echo Could not start Helply - see the error above.
pause
exit /b 1