@echo off
rem Prueft, ob alle KI-Dateien da sind, und sagt genau, was fehlt.
rem Setzt KIPROG auf das gefundene Programm. Errorlevel 1 = etwas fehlt.
set "BASIS=%~dp0..\"
set "KIPROG="
for /r "%BASIS%daten\llama" %%F in (llama-server.exe) do if exist "%%F" set "KIPROG=%%F"
if not defined KIPROG if exist "%BASIS%daten\llamafile.exe" set "KIPROG=%BASIS%daten\llamafile.exe"

set FEHLT=0
if not defined KIPROG (
  set FEHLT=1
  echo.
  echo [FEHLT] Das KI-Programm - llama-server.exe oder llamafile.exe
  echo         Moegliche Gruende:
  echo         - Der Download hat nicht geklappt: Einrichten nochmal starten.
  echo         - Der Virenscanner hat es geloescht. Schau in Windows-Sicherheit
  echo           unter "Schutzverlauf" nach und stelle die Datei wieder her.
)
if not exist "%BASIS%daten\ki-modell.gguf" (
  set FEHLT=1
  echo.
  echo [FEHLT] Das KI-Modell - daten\ki-modell.gguf
  echo         Einrichten nochmal starten.
) else (
  for %%G in ("%BASIS%daten\ki-modell.gguf") do if %%~zG LSS 500000000 (
    set FEHLT=1
    echo.
    echo [KAPUTT] daten\ki-modell.gguf ist zu klein - Download unvollstaendig.
    echo          Einrichten nochmal starten, es geht dort weiter.
  )
)
if "%FEHLT%"=="1" (
  echo.
  echo Gesucht im Ordner: %BASIS%daten
  exit /b 1
)
echo Alle KI-Dateien sind da.
exit /b 0
