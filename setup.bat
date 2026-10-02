@echo off
rem One-time setup for Helply on a new Windows computer.
rem Requires Python 3.12 or newer (https://www.python.org/downloads/) and an internet connection.
cd /d "%~dp0"

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (
  echo Python was not found. Install Python 3.12 or newer from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" during installation, then run this file again.
  pause
  exit /b 1
)

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"
if errorlevel 1 (
  echo Helply needs Python 3.12 or newer. Found:
  %PY% --version
  pause
  exit /b 1
)

if exist ".venv\Scripts\python.exe" (
  echo Virtual environment already exists - reusing it.
) else (
  echo Creating virtual environment...
  %PY% -m venv .venv || goto :failed
)

echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt || goto :failed

echo Creating the database and loading demo data...
".venv\Scripts\python.exe" manage.py migrate --verbosity 0 || goto :failed
".venv\Scripts\python.exe" manage.py seed_demo --reset || goto :failed

echo.
echo Setup complete. Double-click start-demo.bat to run Helply.
pause
exit /b 0

:failed
echo.
echo Setup failed - see the error above.
pause
exit /b 1
