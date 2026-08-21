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
echo Automacao Agilize - Diagnostico de atualizacao
echo ============================================================
echo Repositorio: JoseLuiz095/automacao-agilize
echo.
%PY% "%ROOT%\app\updater.py"

echo.
echo Estados esperados:
echo   updated                 = sistema atualizado
echo   update_available        = nova Release pronta para instalar
echo   release_pending         = versao nova sem Setup/SHA publicado
echo   repository_unavailable  = repositorio nao encontrado/publico
echo   offline                 = sem acesso a internet
echo   rate_limited            = limite temporario do GitHub
echo.
echo Log: %%LOCALAPPDATA%%\AutomacaoAgilize\logs\update.log
pause
