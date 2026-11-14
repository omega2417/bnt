@echo off
setlocal
cd /d "%~dp0"
if exist .venv\Scripts\python.exe goto install
where py >nul 2>nul
if errorlevel 1 (
  python -m venv .venv
) else (
  py -3 -m venv .venv
)
if errorlevel 1 goto fail
:install
if exist .venv\.satqkd-ready goto run
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo ready>.venv\.satqkd-ready
:run
.venv\Scripts\python.exe run.py %*
if errorlevel 1 goto fail
echo.
echo Report: results\demo\report.html
pause
exit /b 0
:fail
echo Launch failed. Check Python 3.10+ and Internet access for first installation.
pause
exit /b 1
