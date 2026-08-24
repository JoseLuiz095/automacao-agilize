@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
cd /d "%ROOT%"

echo ============================================================
echo Automacao Agilize - Migracao do atualizador antigo
echo ============================================================
echo.
echo Use este utilitario somente para sair de uma versao antiga que

echo detecta VERSAO.txt novo, mas nao consegue acessar a Release privada.
echo.
echo Antes, publique a versao atual usando:
echo   FERRAMENTAS\07_PUBLICAR_VERSAO.bat 0.8.1
echo.
pause
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\FERRAMENTAS\migrar_atualizador_antigo.ps1"
if errorlevel 1 (
  echo.
  echo [FALHA] A migracao nao foi concluida.
  pause
  exit /b 1
)
exit /b 0
