@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
cd /d "%ROOT%"
set "PYTHONPATH=%ROOT%\app"

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
echo Automacao Agilize - Diagnostico de atualizacao v0.8.4+
echo ============================================================
echo Fonte oficial:
echo https://github.com/JoseLuiz095/automacao-agilize/releases/latest
echo.
%PY% "%ROOT%\app\updater.py"

echo.
echo Estados esperados:
echo   updated           = sistema atualizado
echo   update_available  = nova Release pronta para instalar
echo   no_release        = nenhuma Release publicada
echo   local_newer       = app local mais novo que a Release
echo   offline           = sem acesso a internet
echo   rate_limited      = limite temporario da API do GitHub
echo   check_failed      = Release incompleta/erro inesperado
echo.
echo Log: %%LOCALAPPDATA%%\AutomacaoAgilize\logs\update.log
pause
