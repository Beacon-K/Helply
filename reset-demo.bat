@echo off
rem Wipes the DEMO data on purpose and starts it over: deletes ALL tickets, puts the demo people, SLA targets and
rem assets back to their demo values, and gives every demo account a new random password.
rem Never use this on a system that holds real data. It refuses to run in production or when real accounts exist.
cd /d "%~dp0"
call tools\helply-env.bat

if not exist "%HELPLY_PY%" (
  echo Helply is not set up on this computer ^(%COMPUTERNAME%^) yet. Run setup.bat once first.
  pause
  exit /b 1
)

echo.
echo   This will DELETE every ticket and reset the demo company to its starting state.
echo   People's own password changes, role changes and SLA edits will be lost.
echo.
set "CONFIRM="
set /p "CONFIRM=Type RESET and press Enter to continue (anything else cancels): "
if /i not "%CONFIRM%"=="RESET" (
  echo Cancelled. Nothing was changed.
  pause
  exit /b 0
)

call tools\start-db.bat
"%HELPLY_PY%" manage.py migrate --verbosity 0 || goto :failed
"%HELPLY_PY%" manage.py seed_demo --reset --overwrite || goto :failed
"%HELPLY_PY%" manage.py demo_passwords --rotate || goto :failed
echo.
echo Done. Restart start-online.bat or start-demo.bat if it is running.
pause
exit /b 0

:failed
echo.
echo The reset did not finish - see the error above.
pause
exit /b 1