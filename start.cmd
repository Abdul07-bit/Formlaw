@echo off
rem FormLaw local launcher (Windows): starts the API and the website in their own windows, then opens the browser.
rem Double-click this file, or run  start.cmd  from a terminal. Close the two windows to stop FormLaw.
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\python.exe" (
  echo Python environment missing. Run:  python -m venv backend\.venv  and  backend\.venv\Scripts\pip install -r backend\requirements.txt
  pause
  exit /b 1
)

start "FormLaw API (port 8000)" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
start "FormLaw website (port 5173)" cmd /k "set "PATH=C:\Program Files\nodejs;%PATH%" && npm.cmd run dev"

echo Starting FormLaw... the browser opens in a few seconds.
timeout /t 8 /nobreak >nul
start "" http://localhost:5173
