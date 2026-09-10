@echo off
REM Installation complete (Windows) : backend Python, modele Vosk, frontend.
cd /d "%~dp0\.."

echo ==^> 1/4 Environnement virtuel Python
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip

echo ==^> 2/4 Dependances backend
pip install -r requirements.txt
if errorlevel 1 goto :error

echo ==^> 3/4 Modele Vosk francais (~40 Mo)
python scripts\download_model.py

echo ==^> 4/4 Dependances frontend (Node.js)
where npm >nul 2>nul
if errorlevel 1 (
  echo npm introuvable : installez Node.js 18+ depuis https://nodejs.org puis relancez : cd frontend ^&^& npm install
) else (
  cd frontend
  call npm install
  cd ..
)

echo.
echo ✅ Installation terminee !
echo Demarrage : scripts\run_backend.bat dans un terminal, scripts\run_frontend.bat dans un autre,
echo puis ouvrez http://localhost:3000
goto :eof

:error
echo ❌ Une erreur sest produite. Verifiez que Python 3.10+ est installe et dans le PATH.
exit /b 1
