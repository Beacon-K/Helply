@echo off
rem Helply local launcher: starts the server and opens the browser.
rem Starting this file never changes your data. Demo data is loaded only when the database has no users at all.
rem To wipe the demo and start it over on purpose, run reset-demo.bat.
cd /d "%~dp0"
call tools\helply-env.bat

if not exist "%HELPLY_PY%" (
  echo Helply is not set up on this computer ^(%COMPUTERNAME%^) yet.
  echo Double-click setup.bat once, then run this file again.
  pause
  exit /b 1
)

call tools\start-db.bat

echo Applying database updates...
"%HELPLY_PY%" manage.py migrate --verbosity 0
"%HELPLY_PY%" manage.py seed_demo --if-empty
if errorlevel 1 (
  echo.
  echo Could not prepare the database. See the message above.
  pause
  exit /b 1
)

for /f "usebackq tokens=1,* delims==" %%a in (".env") do if /i "%%a"=="HELPLY_DEMO_PASSWORD" echo Password of accounts created from the demo set: %%b ^(people who changed theirs use their own^)

echo.
rem Scheduled jobs and offline detection for monitored servers (stop when this window closes).
start "" /b "%HELPLY_PY%" manage.py run_jobs --every 5
start "" /b "%HELPLY_PY%" manage.py monitor_check --every 30

echo Starting Helply at http://127.0.0.1:8000  (close this window to stop)
start "" http://127.0.0.1:8000
"%HELPLY_PY%" manage.py runserver 127.0.0.1:8000
pause