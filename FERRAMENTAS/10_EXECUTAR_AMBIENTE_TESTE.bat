@echo off
setlocal EnableExtensions
set "AGILIZE_BASE_URL=https://dev-ml.startinghub.com.br"
set "AUTOMACAO_AGILIZE_ENV=teste"
echo ============================================================
echo Automacao Agilize - Ambiente de TESTE
echo ============================================================
echo URL: %AGILIZE_BASE_URL%
echo Dados locais: %%LOCALAPPDATA%%\AutomacaoAgilize-Teste
echo.
call "%~dp001_EXECUTAR_DEV.bat"
