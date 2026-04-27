@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 start_student.py %*
) else (
  python start_student.py %*
)
if errorlevel 1 pause
