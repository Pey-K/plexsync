@echo off
REM Plex Collection Sync - One-Click Launcher for Windows
REM This script sets up and runs the entire application

title Plex Collection Sync Launcher

echo ========================================
echo  Plex Collection Sync - Windows Launcher
echo ========================================
echo.

REM Check if .env exists
if not exist .env (
    echo [ERROR] .env file not found!
    echo.
    echo Please create a .env file with your Plex credentials.
    echo You can copy .env.example to .env and edit it.
    echo.
    pause
    exit /b 1
)

REM Check for Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found in PATH!
    echo Please install Python 3.9+ from https://www.python.org/
    echo.
    pause
    exit /b 1
)

REM Check for Node.js
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js not found in PATH!
    echo Please install Node.js 18+ from https://nodejs.org/
    echo.
    pause
    exit /b 1
)

echo [1/5] Checking Python dependencies...
python -c "import plexapi" >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Installing Python dependencies...
    pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to install Python dependencies!
        pause
        exit /b 1
    )
) else (
    echo Python dependencies OK
)

echo.
echo [2/5] Checking Node.js dependencies...
if not exist node_modules (
    echo Installing Node.js dependencies...
    call npm install
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to install Node.js dependencies!
        pause
        exit /b 1
    )
) else (
    echo Node.js dependencies OK
)

echo.
echo [3/5] Creating necessary directories...
if not exist data mkdir data
if not exist assets\images mkdir assets\images
if not exist assets\images\movie_image mkdir assets\images\movie_image
if not exist assets\images\tv_image mkdir assets\images\tv_image
if not exist assets\images\music_image mkdir assets\images\music_image

echo.
echo [4/5] Running initial sync (this may take a while)...
echo.
python plex_sync.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [WARNING] Sync completed with errors. Continuing anyway...
)

echo.
echo [5/5] Starting backend server...
echo.
echo ========================================
echo  Backend server starting...
echo  API will be available at: http://localhost:3000
echo  Press Ctrl+C to stop the server
echo ========================================
echo.

REM Start the backend server
node server.js

pause

