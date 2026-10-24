@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" (
  echo [준비] 가상환경을 만듭니다...
  python -m venv .venv || (echo Python 3.11 이상이 필요합니다. & pause & exit /b 1)
)
call ".venv\Scripts\activate.bat"
python -m pip install -q -r requirements.txt
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:8000/"
python -m uvicorn api.index:app --host 127.0.0.1 --port 8000
pause
