@echo off
REM Lance le backend Flask sur http://localhost:5001
cd /d "%~dp0\.."
call .venv\Scripts\activate.bat
python chatbot.py
