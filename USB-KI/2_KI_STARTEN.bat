@echo off
setlocal
title USB-KI - dieses Fenster offen lassen
cd /d "%~dp0"

echo "%~dp0" | findstr /i /c:"\AppData\Local\Temp" >nul
if not errorlevel 1 (
  echo STOPP: Du hast die Datei direkt aus der ZIP geoeffnet.
  echo Bitte zuerst entpacken und die Datei im entpackten Ordner starten.
  pause
  exit /b 1
)

call "%~dp0hilfe\pruefen.bat"
if errorlevel 1 (
  echo.
  echo Starte zuerst zuhause "1_EINRICHTEN_zuhause.bat" mit Internet.
  pause
  exit /b 1
)

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

echo %KIPROG% | findstr /i "llamafile" >nul
if not errorlevel 1 (
  "%KIPROG%" --server --nobrowser -m "daten\ki-modell.gguf" --host 127.0.0.1 --port 8080 -c 8192 -ngl 0
) else (
  "%KIPROG%" -m "daten\ki-modell.gguf" --host 127.0.0.1 --port 8080 -c 8192
)
echo.
echo Die KI wurde beendet.
pause
exit /b 0
