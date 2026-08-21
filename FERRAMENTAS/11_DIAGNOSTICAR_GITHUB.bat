@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
cd /d "%ROOT%"

set "PY="
where py.exe >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python.exe >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo Python nao encontrado.
  pause
  exit /b 1
)

echo ============================================================
echo Automacao Agilize - Diagnostico GitHub
echo ============================================================
echo Repositorio: JoseLuiz095/automacao-agilize
if defined AUTOMACAO_AGILIZE_GITHUB_TOKEN (echo Token por ambiente: configurado) else (echo Token por ambiente: nao configurado)
echo.
set "PYTHONPATH=%ROOT%\app"
%PY% "%ROOT%\app\updater.py"
echo.
echo Log: %%LOCALAPPDATA%%\AutomacaoAgilize\logs\update.log
pause
