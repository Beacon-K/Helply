@echo off
rem Runs Helply for real use. Never loads, wipes or changes demo data or passwords.
rem Requires HELPLY_ENVIRONMENT=production in .env (setup.bat prepares the rest).
rem Starts: the database check, the scheduled jobs (SLA checks, follow-ups, daily backup),
rem the Cloudflare tunnel if CLOUDFLARE_TUNNEL_TOKEN is set, and the Waitress web server.
cd /d "%~dp0"
call tools\helply-env.bat

if not exist "%HELPLY_PY%" (
  echo Helply is not set up on this computer ^(%COMPUTERNAME%^) yet. Run setup.bat once first.
  pause
  exit /b 1
)

set "ENV_MODE="
set "TUNNEL_TOKEN="
set "ONLINE_HOSTNAME="
set "HELPLY_LISTEN=127.0.0.1:8000"
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
  if /i "%%a"=="HELPLY_ENVIRONMENT" set "ENV_MODE=%%b"
  if /i "%%a"=="CLOUDFLARE_TUNNEL_TOKEN" set "TUNNEL_TOKEN=%%b"
  if /i "%%a"=="ONLINE_HOSTNAME" set "ONLINE_HOSTNAME=%%b"
  if /i "%%a"=="HELPLY_LISTEN" set "HELPLY_LISTEN=%%b"
)
if /i not "%ENV_MODE%"=="production" (
  echo This launcher is for production. Add  HELPLY_ENVIRONMENT=production  to .env first
  echo ^(see README, "Production"^). For demos use start-demo.bat or start-online.bat.
  pause
  exit /b 1
)

call tools\start-db.bat strict || goto :failed
echo Applying database updates...
"%HELPLY_PY%" manage.py migrate --verbosity 0 || goto :failed
"%HELPLY_PY%" manage.py collectstatic --noinput --verbosity 0 || goto :failed

if defined TUNNEL_TOKEN (
  if not defined ONLINE_HOSTNAME set "ONLINE_HOSTNAME=helply.work"
)
if defined TUNNEL_TOKEN set "HELPLY_PUBLIC_HOST=%ONLINE_HOSTNAME%"

echo Checking the production configuration...
"%HELPLY_PY%" manage.py check --deploy --fail-level ERROR || goto :failed

echo Starting scheduled jobs (SLA checks, follow-ups, daily backup)...
start "" /b "%HELPLY_PY%" manage.py run_jobs --every 5
rem Server monitoring: offline detection every 30 seconds and metric roll-up.
start "" /b "%HELPLY_PY%" manage.py monitor_check --every 30

if defined TUNNEL_TOKEN (
  if not exist "tools\cloudflared.exe" (
    echo tools\cloudflared.exe is missing - cannot connect the tunnel.
    goto :failed
  )
  echo Connecting the Cloudflare tunnel...
  start "" /b "tools\cloudflared.exe" tunnel --no-autoupdate --loglevel warn run
)

echo.
echo ================================================================
if defined TUNNEL_TOKEN (
  echo   Helply is running at  https://%ONLINE_HOSTNAME%
) else (
  echo   Helply is running at  http://%HELPLY_LISTEN%
)
echo   Errors are logged to logs\helply.log. Close this window to stop.
echo ================================================================
echo.
"%HELPLY_PY%" -m waitress --listen=%HELPLY_LISTEN% --threads=8 --trusted-proxy=127.0.0.1 --trusted-proxy-headers=x-forwarded-proto config.wsgi:application
pause
exit /b 0

:failed
echo.
echo Helply did not start - see the message above.
pause
exit /b 1
