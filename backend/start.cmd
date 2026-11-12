@echo off
setlocal
cd /d "%~dp0"
set "BACKEND_PYTHON=venv\Scripts\python.exe"
if not exist "%BACKEND_PYTHON%" set "BACKEND_PYTHON=.venv\Scripts\python.exe"
if not exist "%BACKEND_PYTHON%" (
    echo Backend Python environment not found. Set up .venv or venv first. 1>&2
    exit /b 1
)
"%BACKEND_PYTHON%" -X utf8 app.py
exit /b %errorlevel%
