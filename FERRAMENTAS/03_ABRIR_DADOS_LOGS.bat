@echo off
setlocal
set "HOME=%LOCALAPPDATA%\AutomacaoAgilize"
if not exist "%HOME%" mkdir "%HOME%" >nul 2>nul
explorer.exe "%HOME%"
