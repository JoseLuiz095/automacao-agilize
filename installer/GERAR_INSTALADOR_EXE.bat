@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Gerar instalador - Automacao Agilize

for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "VERSION_FILE=%ROOT%\VERSAO.txt"
set "BUILD_HOME=%LOCALAPPDATA%\AutomacaoAgilizeBuild"
set "VENV=%BUILD_HOME%\venv"
set "PYTHON=%VENV%\Scripts\python.exe"
set "OUT=%ROOT%\build\out"
set "OUTPUT=%ROOT%\installer\output\AutomacaoAgilize-Setup.exe"
set "SHA=%OUTPUT%.sha256"
set "LOG=%ROOT%\installer\gerar_instalador.log"
set "NO_PAUSE=0"
if /I "%~1"=="--silent" set "NO_PAUSE=1"
if /I "%~1"=="--ci" set "NO_PAUSE=1"

>"%LOG%" echo [%date% %time%] Inicio do build.

echo ============================================================
echo Automacao Agilize - Gerador do instalador EXE
echo ============================================================
echo.

if not exist "%VERSION_FILE%" (
  call :fail "VERSAO.txt nao encontrado."
  goto :end
)
set /p APP_VERSION=<"%VERSION_FILE%"
if not defined APP_VERSION (
  call :fail "VERSAO.txt esta vazio."
  goto :end
)
echo Versao: %APP_VERSION%
echo Projeto: %ROOT%
echo.

if not exist "%ROOT%\app\launcher.py" (
  call :fail "app\launcher.py nao encontrado. Verifique se o ZIP foi extraido por completo."
  goto :end
)
if not exist "%ROOT%\build\AutomacaoAgilize.spec" (
  call :fail "build\AutomacaoAgilize.spec nao encontrado."
  goto :end
)
if not exist "%ROOT%\assets\automacao-agilize.ico" (
  call :fail "assets\automacao-agilize.ico nao encontrado."
  goto :end
)

if not exist "%PYTHON%" (
  echo Criando ambiente de build em LocalAppData...
  if not exist "%BUILD_HOME%" mkdir "%BUILD_HOME%" >nul 2>nul
  where py.exe >nul 2>nul
  if not errorlevel 1 py -3 -m venv "%VENV%" >>"%LOG%" 2>&1
  if not exist "%PYTHON%" (
    where python.exe >nul 2>nul
    if not errorlevel 1 python -m venv "%VENV%" >>"%LOG%" 2>&1
  )
)
if not exist "%PYTHON%" (
  call :fail "Python 3 nao foi localizado para criar o ambiente de build."
  goto :end
)

"%PYTHON%" -m pip install --upgrade pip >>"%LOG%" 2>&1
if errorlevel 1 (
  call :fail "Falha ao atualizar pip."
  goto :end
)

"%PYTHON%" -m pip install -r "%ROOT%\build\requirements-build.txt" >>"%LOG%" 2>&1
if errorlevel 1 (
  call :fail "Falha ao instalar dependencias de build."
  goto :end
)

"%PYTHON%" "%ROOT%\build\gerar_version_info.py" >>"%LOG%" 2>&1
if errorlevel 1 (
  call :fail "Falha ao gerar metadados de versao."
  goto :end
)

"%PYTHON%" -m compileall -q "%ROOT%\app" >>"%LOG%" 2>&1
if errorlevel 1 (
  call :fail "Falha na validacao sintatica do codigo."
  goto :end
)

if exist "%OUT%" rmdir /s /q "%OUT%" >nul 2>nul
mkdir "%OUT%\dist" >nul 2>nul
mkdir "%OUT%\work" >nul 2>nul

>>"%LOG%" echo ROOT=%ROOT%
>>"%LOG%" echo SPEC=%ROOT%\build\AutomacaoAgilize.spec
>>"%LOG%" echo LAUNCHER=%ROOT%\app\launcher.py
pushd "%ROOT%"
"%PYTHON%" -m PyInstaller --noconfirm --clean --distpath "%OUT%\dist" --workpath "%OUT%\work" "build\AutomacaoAgilize.spec" >>"%LOG%" 2>&1
set "PYI_RC=!errorlevel!"
popd
if not "%PYI_RC%"=="0" (
  call :fail "PyInstaller retornou erro. Veja gerar_instalador.log."
  goto :end
)

if not exist "%OUT%\dist\AutomacaoAgilize\AutomacaoAgilize.exe" (
  call :fail "AutomacaoAgilize.exe nao foi gerado."
  goto :end
)

call :find_iscc
if not defined ISCC (
  echo Inno Setup nao encontrado. Tentando instalar pelo WinGet...
  where winget.exe >nul 2>nul
  if not errorlevel 1 (
    winget install --id JRSoftware.InnoSetup -e --source winget --accept-package-agreements --accept-source-agreements --silent >>"%LOG%" 2>&1
    call :find_iscc
  )
)
if not defined ISCC (
  call :fail "Inno Setup 6/7 nao foi localizado."
  goto :end
)

echo Compilador: %ISCC%
if exist "%OUTPUT%" del /q "%OUTPUT%" >nul 2>nul
if exist "%SHA%" del /q "%SHA%" >nul 2>nul

"%ISCC%" /DMyAppVersion=%APP_VERSION% "%ROOT%\installer\AutomacaoAgilize.iss" >>"%LOG%" 2>&1
if errorlevel 1 (
  call :fail "Inno Setup retornou erro. Veja gerar_instalador.log."
  goto :end
)
if not exist "%OUTPUT%" (
  call :fail "A compilacao terminou, mas o Setup.exe nao foi encontrado."
  goto :end
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$h=(Get-FileHash -Algorithm SHA256 -LiteralPath '%OUTPUT%').Hash.ToLower(); Set-Content -LiteralPath '%SHA%' -Value ($h + '  AutomacaoAgilize-Setup.exe') -Encoding ascii" >>"%LOG%" 2>&1
if errorlevel 1 (
  call :fail "Falha ao gerar SHA-256."
  goto :end
)

echo.
echo ============================================================
echo SUCESSO
echo ============================================================
echo Instalador:
echo %OUTPUT%
for %%S in ("%OUTPUT%") do echo Tamanho: %%~zS bytes
echo SHA-256:
echo %SHA%
echo Log:
echo %LOG%
explorer.exe /select,"%OUTPUT%" >nul 2>nul
set "RC=0"
goto :end

:find_iscc
set "ISCC="
for %%P in (
  "%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe"
  "%ProgramFiles%\Inno Setup 7\ISCC.exe"
  "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
  "%ProgramFiles%\Inno Setup 6\ISCC.exe"
  "%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe"
  "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
) do (
  if not defined ISCC if exist "%%~P" set "ISCC=%%~P"
)
exit /b 0

:fail
set "RC=1"
echo.
echo ============================================================
echo FALHA
echo ============================================================
echo %~1
echo [%date% %time%] ERRO: %~1>>"%LOG%"
echo Log: %LOG%
exit /b 0

:end
if not defined RC set "RC=1"
echo.
if "%NO_PAUSE%"=="0" pause
exit /b %RC%
