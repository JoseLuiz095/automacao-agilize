@echo off
setlocal EnableExtensions
set "LOG=%LOCALAPPDATA%\AutomacaoAgilize\logs\update.log"
if not exist "%LOG%" (
  echo Ainda nao existe log de atualizacao.
  echo Caminho esperado: %LOG%
  pause
  exit /b 0
)
start "" notepad.exe "%LOG%"
