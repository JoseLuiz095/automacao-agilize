@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
cd /d "%ROOT%"

where git.exe >nul 2>nul || (
  echo Git nao encontrado.
  pause
  exit /b 1
)

if not exist ".git" git init
git branch -M main
git remote remove origin >nul 2>nul
git remote add origin https://github.com/JoseLuiz095/automacao-agilize.git

echo ============================================================
echo Automacao Agilize - GitHub
echo ============================================================
echo Remote configurado:
git remote -v

echo.
echo Validando acesso ao repositorio...
git ls-remote origin >nul 2>nul
if errorlevel 1 (
  echo.
  echo [ATENCAO] O repositorio nao esta acessivel com as credenciais atuais.
  echo Confirme se ele existe em:
  echo https://github.com/JoseLuiz095/automacao-agilize
  echo.
  echo Para atualizacao automatica dos usuarios, o canal de Releases deve
  echo estar acessivel sem depender das credenciais Git da maquina do usuario.
  pause
  exit /b 2
)

echo [OK] Repositorio acessivel.
pause
exit /b 0
