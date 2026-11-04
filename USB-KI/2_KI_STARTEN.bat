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
echo   Sobald die KI geladen ist, oeffnet sich die Rover-KI im Browser.
echo   Falls nicht: im Browser  http://127.0.0.1:8080  eingeben.
echo.
echo   Die vielen Textzeilen hier sind normal.
echo   Zum Beenden dieses Fenster schliessen.
echo ==========================================================
echo.

rem Browser oeffnen, sobald der KI-Server antwortet. Die Rover-KI-Seite
rem kommt direkt vom KI-Server (--path), so blockiert der Browser nichts.
start "" /min cmd /c "for /l %%i in (1,1,150) do (curl -s -f -o nul http://127.0.0.1:8080/health && (start http://127.0.0.1:8080/ & exit) & ping -n 3 127.0.0.1 >nul)"

echo %KIPROG% | findstr /i "llamafile" >nul
if not errorlevel 1 (
  "%KIPROG%" --server --nobrowser -m "daten\ki-modell.gguf" --host 127.0.0.1 --port 8080 -c 8192 -ngl 0 --path "%~dp0web"
) else (
  "%KIPROG%" -m "daten\ki-modell.gguf" --host 127.0.0.1 --port 8080 -c 8192 --path "%~dp0web"
)
echo.
echo Die KI wurde beendet.
pause
exit /b 0
