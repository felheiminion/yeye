@echo off
title spotDL Installer
echo ============================================
echo   spotDL - Modified Edition - Installer
echo ============================================
echo.

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo.
    echo Download Python from: https://www.python.org/downloads/
    echo IMPORTANT: Check "Add Python to PATH" during install!
    echo.
    pause
    exit /b 1
)

echo [OK] Python found:
python --version
echo.

:: Check for ffmpeg
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [INFO] ffmpeg not found. spotDL will download it automatically on first run.
    echo.
) else (
    echo [OK] ffmpeg found.
    echo.
)

:: Install the wheel
echo Installing spotDL...
echo.
python -m pip install --force-reinstall spotdl-4.4.3-py3-none-any.whl
if errorlevel 1 (
    echo.
    echo [ERROR] Installation failed. Try running this as Administrator.
    pause
    exit /b 1
)

echo.

:: Write tuned config (rate limiter settings, retries, etc.)
python "%~dp0spotdl_launcher.py" --write-config
echo.

:: Download ffmpeg if not present
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo Downloading ffmpeg...
    python -m spotdl --download-ffmpeg
    echo.
)

echo ============================================
echo   Installation complete!
echo ============================================
echo.
echo Double-click spotDL.bat to start downloading music.
echo.
pause
