@echo off
setlocal
set "FINORA_ROOT=C:\Finora"
if not exist ".venv\Scripts\python.exe" (
  echo Virtuelle Umgebung fehlt. Bitte zuerst install_windows.bat ausfuehren.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
start "" http://127.0.0.1:8020
python -m uvicorn app.main:app --host 127.0.0.1 --port 8020
