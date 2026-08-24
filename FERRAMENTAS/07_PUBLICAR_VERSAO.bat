@echo off
setlocal EnableExtensions EnableDelayedExpansion
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
cd /d "%ROOT%"

set "REPO=JoseLuiz095/automacao-agilize"
set "SETUP=%ROOT%\installer\output\AutomacaoAgilize-Setup.exe"
set "SHA_FILE=%SETUP%.sha256"

where git.exe >nul 2>nul
if errorlevel 1 (
  echo Git nao encontrado. O release ainda pode ser publicado pelo GitHub CLI,
  echo mas o codigo fonte nao sera sincronizado automaticamente.
)

set "GH=gh.exe"
where gh.exe >nul 2>nul
if errorlevel 1 if exist "%ProgramFiles%\GitHub CLI\gh.exe" set "GH=%ProgramFiles%\GitHub CLI\gh.exe"
if /I "%GH%"=="gh.exe" (
  where gh.exe >nul 2>nul
  if errorlevel 1 (
    echo GitHub CLI nao encontrado. Tentando instalar pelo WinGet...
    where winget.exe >nul 2>nul
    if not errorlevel 1 winget install --id GitHub.cli -e --source winget --accept-package-agreements --accept-source-agreements
    if exist "%ProgramFiles%\GitHub CLI\gh.exe" set "GH=%ProgramFiles%\GitHub CLI\gh.exe"
  )
)
if /I "%GH%"=="gh.exe" (
  where gh.exe >nul 2>nul
  if errorlevel 1 (
    echo GitHub CLI nao foi localizado. Instale em https://cli.github.com/
    pause
    exit /b 1
  )
)

"%GH%" auth status -h github.com >nul 2>nul
if errorlevel 1 (
  echo Autenticacao do GitHub CLI necessaria. O navegador sera aberto.
  "%GH%" auth login -h github.com --git-protocol https --web
  if errorlevel 1 (
    echo Falha ao autenticar no GitHub CLI.
    pause
    exit /b 1
  )
)

if "%~1"=="" (
  set /p VERSION=Informe a versao sem v ^(ex: 0.8.4^): 
) else (
  set "VERSION=%~1"
)
if not defined VERSION exit /b 1

echo %VERSION%| findstr /r "^[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*$" >nul
if errorlevel 1 (
  echo Versao invalida: %VERSION%
  pause
  exit /b 1
)

>VERSAO.txt echo %VERSION%

REM Tenta sincronizar o codigo se esta pasta ja for um clone Git valido.
if exist ".git" (
  git remote get-url origin >nul 2>nul
  if not errorlevel 1 (
    git add -A
    git diff --cached --quiet
    if errorlevel 1 git commit -m "release source v%VERSION%"
    git push origin main
    if errorlevel 1 echo [AVISO] O push do codigo falhou. A Release ainda sera publicada.
  )
)

REM Gera o instalador localmente. Nao depende de GitHub Actions.
call "%ROOT%\installer\GERAR_INSTALADOR_EXE.bat" --silent
if errorlevel 1 (
  echo Falha ao gerar o instalador local.
  pause
  exit /b 1
)
if not exist "%SETUP%" (
  echo Setup.exe nao encontrado: %SETUP%
  pause
  exit /b 1
)
if not exist "%SHA_FILE%" (
  echo SHA-256 nao encontrado: %SHA_FILE%
  pause
  exit /b 1
)

set "TAG=v%VERSION%"
"%GH%" release view "%TAG%" --repo "%REPO%" >nul 2>nul
if errorlevel 1 (
  echo Criando Release %TAG% com os arquivos prontos...
  "%GH%" release create "%TAG%" "%SETUP%" "%SHA_FILE%" --repo "%REPO%" --target main --title "Automacao Agilize %TAG%" --notes "Atualizacao da Automacao Agilize %TAG%." --latest
  if errorlevel 1 (
    echo Falha ao criar a Release no GitHub.
    pause
    exit /b 1
  )
) else (
  echo Release %TAG% ja existe. Atualizando os arquivos...
  "%GH%" release upload "%TAG%" "%SETUP%" "%SHA_FILE%" --repo "%REPO%" --clobber
  if errorlevel 1 (
    echo Falha ao atualizar os arquivos da Release.
    pause
    exit /b 1
  )
  "%GH%" release edit "%TAG%" --repo "%REPO%" --latest >nul 2>nul
)

REM Confirma que a Release possui exatamente os dois assets obrigatorios.
for /f "delims=" %%J in ('"%GH%" release view "%TAG%" --repo "%REPO%" --json assets --jq ".assets[].name"') do (
  if /I "%%J"=="AutomacaoAgilize-Setup.exe" set "HAS_SETUP=1"
  if /I "%%J"=="AutomacaoAgilize-Setup.exe.sha256" set "HAS_SHA=1"
)
if not defined HAS_SETUP (
  echo Release criada sem AutomacaoAgilize-Setup.exe.
  pause
  exit /b 1
)
if not defined HAS_SHA (
  echo Release criada sem AutomacaoAgilize-Setup.exe.sha256.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo RELEASE PUBLICADA COM SUCESSO
echo ============================================================
echo Versao: %TAG%
echo https://github.com/%REPO%/releases/tag/%TAG%
echo.
echo O aplicativo usa somente a ultima GitHub Release.
echo Nao depende mais de VERSAO.txt nem de GitHub Actions para atualizar.
echo.
pause
exit /b 0
