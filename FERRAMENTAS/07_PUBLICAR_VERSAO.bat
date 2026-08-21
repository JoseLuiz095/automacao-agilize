@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
cd /d "%ROOT%"

where git.exe >nul 2>nul || (
  echo Git nao encontrado.
  pause
  exit /b 1
)

git remote get-url origin >nul 2>nul || (
  echo Remote origin nao configurado. Execute 06_CONFIGURAR_GITHUB.bat primeiro.
  pause
  exit /b 1
)

git ls-remote origin >nul 2>nul
if errorlevel 1 (
  echo Repositorio origin nao acessivel. Corrija o GitHub antes de publicar.
  pause
  exit /b 1
)

if "%~1"=="" (
  set /p VERSION=Informe a versao sem v ^(ex: 0.8.2^): 
) else (
  set "VERSION=%~1"
)
if not defined VERSION exit /b 1

echo %VERSION%| findstr /r "^[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*$" >nul
if errorlevel 1 (
  echo Versao invalida: %VERSION%
  echo Use o formato 0.8.2
  pause
  exit /b 1
)

>VERSAO.txt echo %VERSION%

git add -A
git commit -m "release v%VERSION%"
if errorlevel 1 (
  echo.
  echo Nenhuma alteracao para commit ou o commit falhou.
  echo Se VERSAO.txt ja estava em %VERSION%, altere para uma nova versao.
  pause
  exit /b 1
)

git push origin main
if errorlevel 1 (
  echo Falha ao enviar a branch main.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo PUBLICACAO ENVIADA

echo Versao: v%VERSION%
echo ============================================================
echo.
echo Nao e mais necessario criar a tag manualmente.
echo O GitHub Actions vai automaticamente:
echo   1. validar o projeto
echo   2. gerar o AutomacaoAgilize.exe
echo   3. gerar o AutomacaoAgilize-Setup.exe
echo   4. criar a Release v%VERSION%
echo   5. publicar Setup.exe + SHA-256
echo.
echo Durante alguns minutos a aplicacao pode mostrar:
echo   "Aguardar instalador"
echo.
echo Assim que a Release terminar, o proprio sistema consegue baixar e instalar.
echo.
pause
exit /b 0
