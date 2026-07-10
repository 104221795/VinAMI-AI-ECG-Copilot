@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Missing .venv. Create it with:
  echo   python -m venv .venv
  echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
  exit /b 1
)

if "%VINSTROKE_STREAMLIT_PORT%"=="" set "VINSTROKE_STREAMLIT_PORT=8502"

echo Starting VinStroke ECG Clinical Research Workspace...
echo URL: http://127.0.0.1:%VINSTROKE_STREAMLIT_PORT%

".venv\Scripts\python.exe" -m streamlit run app.py --server.headless true --server.address 127.0.0.1 --server.port %VINSTROKE_STREAMLIT_PORT%
