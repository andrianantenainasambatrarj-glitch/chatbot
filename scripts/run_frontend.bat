@echo off
REM Lance le frontend React sur http://localhost:3000
cd /d "%~dp0\..\frontend"
if not exist node_modules call npm install
call npm start
