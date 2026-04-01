@echo off
echo ========================================
echo   SCOUT AI - Autonomous Business Intelligence
echo ========================================
echo.

:: Kill any existing Python processes on port 7860
echo Cleaning up old processes...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :7860 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

:: Check for API key
if "%GROQ_API_KEY%"=="" (
    if "%OPENAI_API_KEY%"=="" (
        echo.
        echo [ERROR] No API key found!
        echo Set one of these environment variables:
        echo   set GROQ_API_KEY=gsk_...
        echo   set OPENAI_API_KEY=sk-...
        echo.
        pause
        exit /b 1
    )
)

:: Start the server
echo Starting SCOUT AI server...
echo.
cd /d "%~dp0"
python scout_server.py

pause
