@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
cd /d "%ROOT%"
set "VENV=%LOCALAPPDATA%\AutomacaoAgilizeDev\venv"
set "PYTHON=%VENV%\Scripts\python.exe"
if not exist "%PYTHON%" (
  if not exist "%LOCALAPPDATA%\AutomacaoAgilizeDev" mkdir "%LOCALAPPDATA%\AutomacaoAgilizeDev" >nul 2>nul
  where py.exe >nul 2>nul
  if not errorlevel 1 py -3 -m venv "%VENV%"
  if not exist "%PYTHON%" python -m venv "%VENV%"
)
"%PYTHON%" -m pip install -r "%ROOT%\build\requirements.txt"
if errorlevel 1 pause & exit /b 1
set "PYTHONPATH=%ROOT%\app"
"%PYTHON%" "%ROOT%\app\launcher.py"
