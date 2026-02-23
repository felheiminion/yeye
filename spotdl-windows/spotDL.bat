@echo off
setlocal EnableDelayedExpansion
title spotDL

:: ── Paths ───────────────────────────────────────────────────────────
set "BASEDIR=%~dp0"
set "RUNTIME=%BASEDIR%.runtime"
set "PYTHON=%RUNTIME%\python\python.exe"

:: If local runtime exists, skip straight to launch
if exist "%PYTHON%" goto :launch

:: ── Check path is safe before setup ────────────────────────────────
:: Paths with !, ^, %%, or unicode can break batch/PowerShell interactions
set "PATH_OK=1"
echo "%BASEDIR%" | findstr /R "[!^%%]" >nul 2>&1 && set "PATH_OK=0"

:: ── No runtime — set it up ─────────────────────────────────────────
echo.
echo ======================================================
echo   spotDL - First Time Setup
echo ======================================================
echo.
echo   Current folder: %BASEDIR%
echo.

if "%PATH_OK%"=="0" (
    echo   [!] Your folder path has special characters that
    echo       can cause problems. Move this folder to one of:
    echo.
    echo       C:\spotDL
    echo       C:\Users\%USERNAME%\Desktop\spotDL
    echo       C:\Users\%USERNAME%\Documents\spotDL
    echo.
    echo   Then run spotDL.bat again from the new location.
    echo.
    pause
    exit /b 1
)

:: Check if bootstrap.ps1 exists
if not exist "%BASEDIR%bootstrap.ps1" (
    echo   [ERROR] bootstrap.ps1 not found.
    echo   Re-download the spotDL package.
    echo.
    pause
    exit /b 1
)

echo   This will download Python 3.13 and set everything up
echo   in a local folder. No system changes are made.
echo   Total download: ~50MB  (one time only)
echo.
echo   1.  Continue with setup
echo   0.  Cancel
echo.
set /p CHOICE="  Choose (1/0): "

if "!CHOICE!"=="1" goto :do_bootstrap
echo   Cancelled.
pause
exit /b 0

:: ── Bootstrap portable Python ──────────────────────────────────────
:do_bootstrap
echo.
echo   Running setup... (this takes 1-2 minutes)
echo.

:: Strip trailing backslash — PowerShell interprets \" as escaped quote
set "SAFEDIR=%BASEDIR:~0,-1%"
powershell -ExecutionPolicy Bypass -File "%SAFEDIR%\bootstrap.ps1" "%SAFEDIR%"

if errorlevel 1 (
    echo.
    echo   [ERROR] Setup failed.
    echo.
    echo   Try one of these:
    echo     - Move this folder to C:\spotDL and try again
    echo     - Right-click spotDL.bat and "Run as administrator"
    echo.
    pause
    exit /b 1
)

:: Verify Python landed
if not exist "%PYTHON%" (
    echo.
    echo   [ERROR] Python didn't install correctly.
    echo.
    echo   Move this folder to C:\spotDL and try again.
    echo.
    pause
    exit /b 1
)

:: ── Launch ──────────────────────────────────────────────────────────
:launch
"%PYTHON%" "%BASEDIR%spotdl_launcher.py"

if errorlevel 1 (
    echo.
    echo   Something went wrong. To reset, delete the .runtime
    echo   folder and double-click spotDL.bat again.
    echo.
)
pause
