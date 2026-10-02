@echo off
rem Helply demo launcher: refreshes the demo data, starts the server and opens the browser.
rem NOTE: refreshing deletes ALL tickets and regenerates the demo set.
cd /d "%~dp0"

rem If .env points at PostgreSQL, make sure its Docker container is running first.
findstr /b /c:"POSTGRES_DB=" .env >nul 2>nul
if not errorlevel 1 (
  echo Starting the PostgreSQL database container...
  docker compose up -d db
  if errorlevel 1 (
    echo.
    echo Could not start PostgreSQL. Open Docker Desktop, wait until it says "Engine running", then try again.
    pause
    exit /b 1
  )
)

echo Refreshing demo data (this takes about 20 seconds)...
".venv\Scripts\python.exe" manage.py seed_demo --reset
if errorlevel 1 (
  echo.
  echo Demo data refresh failed. See the message above.
  pause
  exit /b 1
)

echo.
echo Starting Helply at http://127.0.0.1:8000  (close this window to stop)
start "" http://127.0.0.1:8000
".venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000
pause
