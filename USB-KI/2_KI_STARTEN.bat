@echo off
setlocal
title USB-KI - dieses Fenster offen lassen
cd /d "%~dp0"

if not exist "daten\llamafile.exe" goto fehlt
if not exist "daten\ki-modell.gguf" goto fehlt

echo ==========================================================
echo   USB-KI startet ...
echo   Gleich oeffnet sich die Rover-KI im Browser.
echo   Falls nicht: die Datei web\index.html auf dem Stick oeffnen.
echo   Einfacher Ersatz-Chat: http://127.0.0.1:8080
echo.
echo   Zum Beenden dieses Fenster schliessen.
echo ==========================================================
echo.

rem Rover-KI-Chat oeffnen - die Seite wartet selbst, bis das Modell geladen ist
start "" "%~dp0web\index.html"

"daten\llamafile.exe" --server --nobrowser -m "daten\ki-modell.gguf" --host 127.0.0.1 --port 8080 -c 8192 -ngl 0
echo.
echo Die KI wurde beendet.
pause
exit /b 0

:fehlt
echo Die KI-Dateien fehlen noch.
echo Starte zuerst zuhause "1_EINRICHTEN_zuhause.bat" mit Internet.
pause
exit /b 1
