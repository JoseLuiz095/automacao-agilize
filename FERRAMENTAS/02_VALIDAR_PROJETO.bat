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
echo Automacao Agilize - Validacao do projeto
echo ============================================================

%PY% "%ROOT%\tests\validar_projeto.py"
if errorlevel 1 goto :falha

for %%F in ("%ROOT%\tests\test_regressoes_v*.py") do (
  echo.
  echo Executando %%~nxF
  %PY% "%%~fF"
  if errorlevel 1 goto :falha
)

echo.
echo [OK] Todas as validacoes passaram.
pause
exit /b 0

:falha
echo.
echo [FALHA] A validacao encontrou um problema.
pause
exit /b 1
