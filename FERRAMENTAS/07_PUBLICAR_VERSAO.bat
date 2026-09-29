@echo off
setlocal EnableExtensions EnableDelayedExpansion
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
cd /d "%ROOT%"

title Automacao Agilize - Publicar versao

set "REPO=JoseLuiz095/automacao-agilize"
set "REMOTE_URL=https://github.com/JoseLuiz095/automacao-agilize.git"
set "SETUP=%ROOT%\installer\output\AutomacaoAgilize-Setup.exe"
set "SHA_FILE=%SETUP%.sha256"

set "GIT=git.exe"
where git.exe >nul 2>nul
if errorlevel 1 if exist "%ProgramFiles%\Git\cmd\git.exe" set "GIT=%ProgramFiles%\Git\cmd\git.exe"
if /I "%GIT%"=="git.exe" (
  where git.exe >nul 2>nul
  if errorlevel 1 (
    echo Git nao encontrado. Tentando instalar pelo WinGet...
    where winget.exe >nul 2>nul
    if not errorlevel 1 winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
    if exist "%ProgramFiles%\Git\cmd\git.exe" set "GIT=%ProgramFiles%\Git\cmd\git.exe"
  )
)
if /I "%GIT%"=="git.exe" (
  where git.exe >nul 2>nul
  if errorlevel 1 (
    echo.
    echo [FALHA] Git nao foi localizado.
    echo Instale o Git for Windows e execute este BAT novamente.
    pause
    exit /b 1
  )
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
    echo.
    echo [FALHA] GitHub CLI nao foi localizado.
    echo Instale em https://cli.github.com/ e execute novamente.
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
"%GH%" auth setup-git >nul 2>nul

if "%~1"=="" (
  set /p VERSION=Informe a versao sem v ^(ex: 0.9.11^): 
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

echo.
echo ============================================================
echo ETAPA 1/3 - GERANDO INSTALADOR v%VERSION%
echo ============================================================
call "%ROOT%\installer\GERAR_INSTALADOR_EXE.bat" --silent
if errorlevel 1 (
  echo Falha ao gerar o instalador local. Nenhuma publicacao foi enviada.
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

echo.
echo ============================================================
echo ETAPA 2/3 - SINCRONIZANDO CODIGO-FONTE COM O GITHUB
echo ============================================================

REM O projeto pode ter vindo de um ZIP e, portanto, nao possuir .git.
REM O BAT cria/configura o repositorio local e preserva o historico remoto.
if not exist ".git" (
  "%GIT%" init
  if errorlevel 1 (
    echo [FALHA] Nao foi possivel inicializar o repositorio Git local.
    pause
    exit /b 1
  )
)

"%GIT%" branch -M main >nul 2>nul
"%GIT%" remote get-url origin >nul 2>nul
if errorlevel 1 (
  "%GIT%" remote add origin "%REMOTE_URL%"
) else (
  "%GIT%" remote set-url origin "%REMOTE_URL%"
)

REM Garante identidade local somente quando o computador ainda nao possui uma.
"%GIT%" config user.name >nul 2>nul
if errorlevel 1 "%GIT%" config user.name "JoseLuiz095"
"%GIT%" config user.email >nul 2>nul
if errorlevel 1 "%GIT%" config user.email "JoseLuiz095@users.noreply.github.com"

echo Buscando o historico atual de origin/main...
"%GIT%" fetch origin main
if errorlevel 1 (
  echo.
  echo [FALHA] Nao foi possivel baixar origin/main.
  echo O codigo NAO sera publicado nem a Release sera criada.
  pause
  exit /b 1
)

REM Se esta pasta ja tinha commits locais, mantemos uma referencia de seguranca.
"%GIT%" rev-parse --verify HEAD >nul 2>nul
if not errorlevel 1 "%GIT%" branch "backup-before-v%VERSION%" HEAD >nul 2>nul

REM Ponto importante para projetos recebidos por ZIP:
REM usa origin/main como pai do novo commit, mas MANTEM os arquivos atuais no disco.
REM Assim o GitHub recebe a versao completa atual sem perder o historico v0.8.x.
"%GIT%" reset --mixed origin/main
if errorlevel 1 (
  echo [FALHA] Nao foi possivel alinhar o indice com origin/main.
  pause
  exit /b 1
)
"%GIT%" branch -M main >nul 2>nul

"%GIT%" add -A
"%GIT%" diff --cached --quiet
if errorlevel 1 (
  echo Criando commit de versao...
  "%GIT%" commit -m "Versao v%VERSION%"
  if errorlevel 1 (
    echo.
    echo [FALHA] Nao foi possivel criar o commit da versao.
    echo Verifique nome/e-mail do Git e os arquivos exibidos acima.
    pause
    exit /b 1
  )
) else (
  echo Nenhuma alteracao de codigo pendente em relacao ao GitHub.
)

echo Enviando main para %REMOTE_URL%...
"%GIT%" push origin main
if errorlevel 1 (
  echo.
  echo [FALHA] O push do codigo-fonte falhou.
  echo A Release NAO sera publicada para evitar GitHub com codigo antigo.
  pause
  exit /b 1
)

echo [OK] Codigo-fonte v%VERSION% sincronizado no GitHub.

echo.
echo ============================================================
echo ETAPA 3/3 - PUBLICANDO RELEASE
echo ============================================================
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

set "HAS_SETUP="
set "HAS_SHA="
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
echo PUBLICACAO CONCLUIDA COM SUCESSO
echo ============================================================
echo Codigo-fonte: https://github.com/%REPO%/tree/main
echo Versao: %TAG%
echo Release: https://github.com/%REPO%/releases/tag/%TAG%
echo.
echo A partir desta versao o BAT exige push do codigo-fonte antes da Release.
echo Isso evita que o repositorio fique parado em uma versao antiga.
echo.
pause
exit /b 0
