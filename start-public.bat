@echo off
rem Helply public demo launcher: serves Helply on this computer's public IP so others can open it.
rem Usage: start-public.bat [host]   e.g. start-public.bat 107.173.15.18
rem Debug pages are turned off so errors do not leak code or settings to visitors.
rem For a short demo only - runserver is not a production web server.
cd /d "%~dp0"
call tools\helply-env.bat

if not exist "%HELPLY_PY%" (
  echo Helply is not set up on this computer ^(%COMPUTERNAME%^) yet. Run setup.bat once first.
  pause
  exit /b 1
)

set "PUBLIC_HOST=%~1"
if not defined PUBLIC_HOST set "PUBLIC_HOST=107.173.15.18"

call tools\start-db.bat
"%HELPLY_PY%" manage.py migrate --verbosity 0

set "DJANGO_DEBUG=false"
set "DJANGO_ALLOWED_HOSTS=%PUBLIC_HOST%,localhost,127.0.0.1"
for /f "delims=" %%k in ('"%HELPLY_PY%" -c "import secrets; print(secrets.token_urlsafe(50))"') do set "DJANGO_SECRET_KEY=%%k"

echo Starting Helply at http://%PUBLIC_HOST%:8000  (close this window to stop)
rem --insecure lets runserver serve CSS/JS while DEBUG is off.
"%HELPLY_PY%" manage.py runserver 0.0.0.0:8000 --insecure
pause
