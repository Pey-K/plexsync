@echo off
REM Build script to create Windows executable from launcher.py
REM Requires: pip install pyinstaller

echo Building Windows executable...
echo.

REM Check if PyInstaller is installed
python -c "import PyInstaller" >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

echo.
echo Creating executable...
pyinstaller --onefile --windowed --name "PlexSyncLauncher" --icon=NONE launcher.py

echo.
echo Build complete! Executable is in the 'dist' folder.
echo You can distribute PlexSyncLauncher.exe to Windows users.
echo.
pause

