@echo off
setlocal
pushd "%~dp0"
set "FINORA_ROOT=C:\Finora"
if not exist "..\finora\.venv\Scripts\python.exe" (
  echo Finora-Umgebung fehlt. Bitte zuerst Finora installieren.
  pause
  exit /b 1
)
call ..\finora\.venv\Scripts\activate.bat
start "" http://127.0.0.1:8030
python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8030
popd
