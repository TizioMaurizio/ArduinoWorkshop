@echo off
REM ── 3D Printer Controller Launcher ──────────────────────────────────
REM Starts the Python backend and React frontend in one click.
REM Close this window (or press Ctrl+C) to stop both.

set BASE=%~dp0printer_controller

REM ── Check venv exists ───────────────────────────────────────────────
if not exist "%BASE%\.venv\Scripts\python.exe" (
    echo [ERROR] Python venv not found. Run first:
    echo   cd %BASE%
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM ── Check node_modules ──────────────────────────────────────────────
if not exist "%BASE%\react_visualizer\node_modules" (
    echo [INFO] Installing React dependencies...
    cd /d "%BASE%\react_visualizer"
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed.
        pause
        exit /b 1
    )
)

REM ── Start Python backend ────────────────────────────────────────────
echo [1/2] Starting Python backend (auto-detect printer)...
set PYTHONPATH=%BASE%
start "PrinterBackend" cmd /c "cd /d %BASE% && .venv\Scripts\python.exe -m backend.main --auto"

REM Give backend a moment to bind the port
timeout /t 3 /nobreak >nul

REM ── Start React frontend ────────────────────────────────────────────
echo [2/2] Starting React frontend...
start "PrinterFrontend" cmd /c "cd /d %BASE%\react_visualizer && npm run dev"

timeout /t 3 /nobreak >nul

echo.
echo ============================================================
echo   Backend:  http://127.0.0.1:8765
echo   Frontend: http://localhost:5173
echo ============================================================
echo   Press any key to stop both...
echo.
pause >nul

REM ── Cleanup ─────────────────────────────────────────────────────────
taskkill /fi "WINDOWTITLE eq PrinterBackend*" /f >nul 2>&1
taskkill /fi "WINDOWTITLE eq PrinterFrontend*" /f >nul 2>&1
echo Stopped.
