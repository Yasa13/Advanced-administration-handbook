@echo off
setlocal
where py >nul 2>nul
if errorlevel 1 (
  echo Python wurde nicht gefunden. Bitte Python 3.11 oder neuer installieren und danach erneut starten.
  pause
  exit /b 1
)
py -3 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
mkdir C:\Finora 2>nul
mkdir C:\Finora\Eingang 2>nul
mkdir C:\Finora\Ablage 2>nul
mkdir C:\Finora\Datenbank 2>nul
mkdir C:\Finora\OCR 2>nul
mkdir C:\Finora\Backup 2>nul
echo.
echo Installation abgeschlossen.
echo Fuer Bild-OCR muss Tesseract OCR auf Windows installiert sein.
echo Danach start_windows.bat ausfuehren.
pause
