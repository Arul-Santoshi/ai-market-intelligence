@echo off
REM ------------------------------------------------------------------
REM AI Market Intelligence — cross-platform start script (Windows)
REM
REM Usage:
REM   start.bat              - Launch both the scheduler and the dashboard
REM   start.bat --dashboard  - Launch only the Streamlit dashboard
REM   start.bat --scheduler  - Launch only the background scheduler
REM   start.bat --test       - Run the pipeline once (no scheduler, no dashboard)
REM ------------------------------------------------------------------

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo  =============================================
echo    AI Market Intelligence - Launcher
echo  =============================================
echo.

REM ── Virtual-environment detection ──────────────────────────────────
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [OK]    Activated virtual environment (venv^)
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo [OK]    Activated virtual environment (.venv^)
) else if defined VIRTUAL_ENV (
    echo [OK]    Already in virtual environment (%VIRTUAL_ENV%^)
) else (
    echo [WARN]  No virtual environment found - using system Python
)

REM ── Find Python ────────────────────────────────────────────────────
set PYTHON=
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set PYTHON=python
) else (
    where python3 >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        set PYTHON=python3
    ) else (
        echo [ERROR] Python not found. Install Python 3.10+ first.
        pause
        exit /b 1
    )
)
echo [INFO]  Using Python: %PYTHON%
%PYTHON% --version

REM ── Check dependencies ─────────────────────────────────────────────
%PYTHON% -c "import streamlit" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [WARN]  Missing dependencies - installing from requirements.txt ...
    %PYTHON% -m pip install -r requirements.txt
)

REM ── .env check ─────────────────────────────────────────────────────
if not exist ".env" (
    echo [WARN]  .env file not found - copy .env.example and fill in your API keys
)

REM ── Start modes ────────────────────────────────────────────────────
set MODE=%1
if "%MODE%"=="" set MODE=both

if "%MODE%"=="--dashboard" goto :dashboard
if "%MODE%"=="--scheduler" goto :scheduler
if "%MODE%"=="--test" goto :test
goto :both

:dashboard
echo [INFO]  Starting Streamlit dashboard ...
%PYTHON% -m streamlit run app.py --server.headless true
goto :eof

:scheduler
echo [INFO]  Starting background scheduler ...
%PYTHON% -m src.main
goto :eof

:test
echo [INFO]  Running pipeline once (--test) ...
%PYTHON% -m src.main --test
goto :eof

:both
echo [INFO]  Starting scheduler in background + dashboard in foreground ...
start "AI-Market-Scheduler" /min %PYTHON% -m src.main
echo [OK]    Scheduler started in background window
%PYTHON% -m streamlit run app.py --server.headless true
goto :eof

endlocal
