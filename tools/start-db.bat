@echo off
rem Chooses the database for this run and starts it if needed.
rem   - .env asks for PostgreSQL and Docker is running  -> start the PostgreSQL container
rem   - otherwise                                        -> use the SQLite database on this drive
rem Sets HELPLY_USE_SQLITE=1 for the caller when falling back, so a demo always runs.
rem
rem   call tools\start-db.bat strict
rem In strict mode (production) there is NO fallback: if PostgreSQL is configured but cannot be
rem started, it exits with an error, because silently switching databases would hide real data.
set "HELPLY_USE_SQLITE="
set "HELPLY_DB_STRICT=%~1"
findstr /b /c:"POSTGRES_DB=" "%HELPLY_ROOT%\.env" >nul 2>nul
if errorlevel 1 goto :sqlite

where docker >nul 2>nul
if errorlevel 1 goto :fallback
docker info >nul 2>nul
if errorlevel 1 goto :fallback

echo Starting PostgreSQL (Docker)...
docker compose -f "%HELPLY_ROOT%\docker-compose.yml" up -d --wait db
if errorlevel 1 goto :fallback
echo PostgreSQL is running.
exit /b 0

:fallback
if /i "%HELPLY_DB_STRICT%"=="strict" (
  echo.
  echo   ERROR: PostgreSQL is configured in .env but could not be started.
  echo          Start Docker Desktop ^(or the PostgreSQL server^) and try again.
  echo.
  exit /b 1
)
echo.
echo   NOTE: PostgreSQL is configured, but Docker is not running on this computer.
echo         Continuing with the SQLite database stored on this drive.
echo         To use PostgreSQL instead, start Docker Desktop and run this again.
echo.

:sqlite
set "HELPLY_USE_SQLITE=1"
exit /b 0
