@echo off
rem Brings the online site up to date: fetches the latest code, stops the running site and starts it again.
rem The site is offline for a few seconds. Your data is never touched (start-online.bat only applies
rem database updates and never resets anything).
rem Run this on the computer that serves helply.work, then leave the new window open.
cd /d "%~dp0"
call tools\helply-env.bat

if not exist ".git" goto :nogit
echo Fetching the latest code...
git pull --ff-only
if errorlevel 1 (
  echo.
  echo Could not update the code ^(no network, or this folder has changes that conflict^).
  choice /c YN /m "Restart the site with the code that is here now"
  if errorlevel 2 exit /b 1
)
goto :deps
:nogit
echo This folder is not a git checkout, so the code is not fetched - restarting with what is here.

:deps
if exist "%HELPLY_PY%" (
  echo Checking Python packages...
  "%HELPLY_PY%" -m pip install -q -r requirements.txt
)

echo Stopping the running site...
powershell -NoProfile -ExecutionPolicy Bypass -File "tools\stop-online.ps1" -Root "%~dp0."
timeout /t 3 /nobreak >nul

echo Starting the site again...
start "Helply online" "%~dp0start-online.bat"
echo Done. The new window shows the address once it is ready.
timeout /t 5 >nul
exit /b 0
