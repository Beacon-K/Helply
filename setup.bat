@echo off
rem One-time setup of Helply on THIS computer. Run it once on each computer that will use this drive.
rem With HELPLY_ENVIRONMENT=production in .env it prepares a real installation (no demo data);
rem otherwise it loads the demo data.
rem Requires Python 3.12 or newer (https://www.python.org/downloads/) and an internet connection.
cd /d "%~dp0"
call tools\helply-env.bat

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

echo Setting up Helply for computer %COMPUTERNAME%
if exist "%HELPLY_PY%" (
  echo Virtual environment already exists - reusing it.
) else (
  echo Creating virtual environment in .venv-%COMPUTERNAME% ...
  %PY% -m venv "%HELPLY_VENV%" || goto :failed
)

echo Installing dependencies...
"%HELPLY_PY%" -m pip install --quiet --upgrade pip
"%HELPLY_PY%" -m pip install --quiet -r requirements.txt || goto :failed

set "ENV_MODE="
for /f "usebackq tokens=1,* delims==" %%a in (".env") do if /i "%%a"=="HELPLY_ENVIRONMENT" set "ENV_MODE=%%b"
if /i "%ENV_MODE%"=="production" goto :production

call tools\start-db.bat
echo Creating the database tables and loading demo data...
"%HELPLY_PY%" manage.py migrate --verbosity 0 || goto :failed
rem --if-empty: running setup again on another computer that shares this drive must never wipe existing data.
"%HELPLY_PY%" manage.py seed_demo --if-empty || goto :failed
echo.
echo Setup complete. Double-click start-demo.bat to run the demo.
pause
exit /b 0

:production
echo Production setup: no demo data will be loaded.
"%HELPLY_PY%" tools\make_secret.py || goto :failed
call tools\start-db.bat strict || goto :failed
"%HELPLY_PY%" manage.py migrate --verbosity 0 || goto :failed
"%HELPLY_PY%" manage.py init_helply || goto :failed
echo.
echo Setup complete. Double-click start-production.bat to run Helply.
pause
exit /b 0

:failed
echo.
echo Setup failed - see the error above.
pause
exit /b 1
