@echo off
rem Helply demo launcher: refreshes the demo data, starts the server and opens the browser.
rem NOTE: refreshing deletes ALL tickets and regenerates the demo set.
cd /d "%~dp0"
call tools\helply-env.bat

if not exist "%HELPLY_PY%" (
  echo Helply is not set up on this computer ^(%COMPUTERNAME%^) yet.
  echo Double-click setup.bat once, then run this file again.
  pause
  exit /b 1
)

call tools\start-db.bat

echo Refreshing demo data (this takes about 20 seconds)...
"%HELPLY_PY%" manage.py migrate --verbosity 0
"%HELPLY_PY%" manage.py seed_demo --reset
if errorlevel 1 (
  echo.
  echo Demo data refresh failed. See the message above.
  pause
  exit /b 1
)

echo.
echo Starting Helply at http://127.0.0.1:8000  (close this window to stop)
start "" http://127.0.0.1:8000
"%HELPLY_PY%" manage.py runserver 127.0.0.1:8000
pause
