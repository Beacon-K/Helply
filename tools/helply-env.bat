@echo off
rem Shared by setup.bat, start-demo.bat and start-public.bat.
rem Each computer gets its own virtual environment on this drive (.venv-COMPUTERNAME),
rem because a virtual environment only works with the Python installation that created it.
rem Paths are relative to this folder, so the drive letter does not matter.
for %%I in ("%~dp0..") do set "HELPLY_ROOT=%%~fI"
set "HELPLY_VENV=%HELPLY_ROOT%\.venv-%COMPUTERNAME%"
set "HELPLY_PY=%HELPLY_VENV%\Scripts\python.exe"
