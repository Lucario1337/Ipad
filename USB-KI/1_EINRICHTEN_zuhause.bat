@echo off
setlocal
title USB-KI einrichten
cd /d "%~dp0"

echo ==========================================================
echo   USB-KI einrichten  -  einmal ZUHAUSE mit Internet starten
echo ==========================================================
echo.
echo Welches KI-Modell soll auf den Stick?
echo.
echo   [1] Klein   - Qwen2.5-Coder 1.5B  ca. 1,1 GB  schnell, auch auf alten PCs
echo   [2] Mittel  - Qwen2.5-Coder 3B    ca. 2,0 GB  guter Kompromiss  EMPFOHLEN
echo   [3] Gross   - Qwen2.5-Coder 7B    ca. 4,7 GB  am schlausten, braucht 8+ GB RAM
echo.
echo Hinweis fuer [3]: Der Stick muss exFAT oder NTFS sein, nicht FAT32.
echo.
set "WAHL="
set /p WAHL="Deine Wahl 1, 2 oder 3 [Enter = 2]: "
if "%WAHL%"=="" set WAHL=2

set "HF=https://huggingface.co/bartowski"
if "%WAHL%"=="1" set "MODELURL=%HF%/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/main/Qwen2.5-Coder-1.5B-Instruct-Q4_K_M.gguf"
if "%WAHL%"=="2" set "MODELURL=%HF%/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf"
if "%WAHL%"=="3" set "MODELURL=%HF%/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf"
if not defined MODELURL (
  echo Ungueltige Wahl.
  pause
  exit /b 1
)

where curl >nul 2>nul
if errorlevel 1 (
  echo curl wurde nicht gefunden. Du brauchst Windows 10 oder neuer.
  pause
  exit /b 1
)

if not exist "daten" mkdir "daten"

echo.
echo [1/2] Lade das KI-Programm llamafile ...
curl -L --fail -o "daten\llamafile.exe" "https://github.com/Mozilla-Ocho/llamafile/releases/download/0.9.3/llamafile-0.9.3"
if errorlevel 1 (
  echo FEHLER beim Download von llamafile. Internet pruefen und nochmal starten.
  pause
  exit /b 1
)

echo.
echo [2/2] Lade das KI-Modell - das kann ein paar Minuten dauern ...
curl -L --fail -C - -o "daten\ki-modell.gguf" "%MODELURL%"
if errorlevel 1 (
  echo FEHLER beim Download des Modells. Einfach nochmal starten, es geht dort weiter.
  pause
  exit /b 1
)

echo.
echo ==========================================================
echo   Fertig! Jetzt kannst du den Stick in den Schul-PC stecken
echo   und dort "2_KI_STARTEN.bat" doppelklicken.
echo ==========================================================
pause
