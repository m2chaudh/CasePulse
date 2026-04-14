@echo off
REM CasePulse - Windows Build Script
REM Usage: build_win.bat
REM
REM Prerequisites:
REM   pip install pyinstaller pywebview pystray Pillow
REM
REM Output:
REM   dist\CasePulse\CasePulse.exe

echo === CasePulse Windows Build ===

REM Activate venv
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo ERROR: Virtual environment not found.
    echo Run: python -m venv venv ^&^& venv\Scripts\activate ^&^& pip install -r requirements.txt -r requirements-desktop.txt
    exit /b 1
)

REM Check dependencies
echo Checking build dependencies...
python -c "import pywebview; import PyInstaller" 2>nul || (
    echo Installing desktop build dependencies...
    pip install -r requirements-desktop.txt
)

REM Generate icons if missing
if not exist "icon.ico" (
    echo Generating icons...
    cd assets
    python generate_icon.py
    copy icon.ico ..
    copy icon.png ..
    cd ..
)

REM Clean previous build
echo Cleaning previous build...
rmdir /s /q build\CasePulse 2>nul
rmdir /s /q dist\CasePulse 2>nul

REM Run PyInstaller (modify spec for Windows icon)
echo Building with PyInstaller...
pyinstaller casepulse.spec --noconfirm

echo.
echo === Build Complete ===
echo Executable: dist\CasePulse\CasePulse.exe
echo.

REM Create installer if Inno Setup is available
where iscc >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo Creating installer with Inno Setup...
    iscc installer_win.iss
    echo.
    echo Installer: dist\CasePulse_Setup.exe
) else (
    echo To create a Windows installer:
    echo   1. Download Inno Setup from https://jrsoftware.org/isinfo.php
    echo   2. Open installer_win.iss in Inno Setup Compiler
    echo   3. Click Build ^> Compile
    echo   4. Output: dist\CasePulse_Setup.exe
)
