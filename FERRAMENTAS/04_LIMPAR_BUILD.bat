@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
if exist "%ROOT%\build\out" rmdir /s /q "%ROOT%\build\out"
if exist "%ROOT%\installer\output" del /q "%ROOT%\installer\output\*" >nul 2>nul
if exist "%ROOT%\installer\gerar_instalador.log" del /q "%ROOT%\installer\gerar_instalador.log"
echo Build limpo.
pause
