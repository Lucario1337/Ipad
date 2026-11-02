@echo off
setlocal
title USB-KI - dieses Fenster offen lassen
cd /d "%~dp0"

if not exist "daten\llamafile.exe" goto fehlt
if not exist "daten\ki-modell.gguf" goto fehlt

echo ==========================================================
echo   USB-KI startet ...
echo   Gleich oeffnet sich der Browser mit dem Chat.
echo   Falls nicht: http://127.0.0.1:8080 im Browser eingeben.
echo.
echo   Zum Beenden dieses Fenster schliessen.
echo ==========================================================
echo.

rem Browser nach ein paar Sekunden oeffnen, wenn das Modell geladen ist
start "" /min cmd /c "timeout /t 8 >nul & start http://127.0.0.1:8080"

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
