@echo off
title Printer Tracker
cd /d "%~dp0"

echo ============================================================
echo   Printer Tracker - Starting all services
echo ============================================================
echo.

:: 1. Camera server (background)
echo [1/3] Starting camera server on port 8766...
start "Camera Server" /min cmd /c "python scripts\camera_server.py --camera auto --port 8766"
timeout /t 2 /nobreak >nul

:: 2. Printer backend (background)
echo [2/3] Starting printer backend on port 8765...
start "Printer Backend" /min cmd /c "python -m backend.main --auto"
timeout /t 8 /nobreak >nul

:: 3. Visual servo watcher (foreground)
echo [3/3] Starting visual servo watcher on port 8767...
echo.
echo   Visualization:  http://127.0.0.1:8767
echo   Digital Twin:   http://127.0.0.1:8767/twin
echo   Camera feed:    http://127.0.0.1:8766
echo.
echo   Close this window to stop all services.
echo ============================================================
echo.

python scripts\watch_servo.py -- --printer-url http://127.0.0.1:8765 --camera-url http://127.0.0.1:8766 --step 1.0 --save-frames --timeout 600 --viz-port 8767 --z-height 10
