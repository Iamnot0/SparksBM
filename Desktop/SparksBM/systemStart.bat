@echo off
REM ═══════════════════════════════════════════════════════════════════════════════
REM  SparksBM - Complete System Startup (Windows - No WSL Required)
REM  Uses existing configuration - no setup needed
REM ═══════════════════════════════════════════════════════════════════════════════

echo.
echo ════════════════════════════════════════════════════════════════════════════
echo            ⚡ SparksBM - Starting Complete System
echo ════════════════════════════════════════════════════════════════════════════
echo.

REM Check dependencies
echo [1/5] Checking dependencies...

where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker not found.
    echo.
    echo Install Docker Desktop: https://www.docker.com/products/docker-desktop
    echo.
    pause
    exit /b 1
)
echo   ✓ Docker

where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found.
    echo.
    echo Install Node.js: https://nodejs.org/
    echo.
    pause
    exit /b 1
)
echo   ✓ Node.js

where java >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Java not found.
    echo.
    echo Install Java 21 JDK: https://adoptium.net/
    echo.
    pause
    exit /b 1
)
echo   ✓ Java

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found.
    echo.
    echo Install Python 3: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
echo   ✓ Python
echo.

echo [2/5] Starting Docker services (PostgreSQL, Keycloak, RabbitMQ)...
cd SparksbmISMS\keycloak
docker compose up -d
if %errorlevel% neq 0 (
    echo [ERROR] Failed to start Docker services
    pause
    exit /b 1
)
cd ..\..

echo [3/5] Starting ISMS Backend...
cd SparksbmISMS\verinice-veo
start /B gradlew.bat veo-rest:bootRun -PspringProfiles=local > %TEMP%\sparksbm-backend.log 2>&1
cd ..\..

echo [4/5] Starting ISMS Frontend...
cd SparksbmISMS\verinice-veo-web
start /B npm run dev > %TEMP%\sparksbm-isms-frontend.log 2>&1
cd ..\..

echo [5/5] Starting NotebookLLM...
cd NotebookLLM\api
start /B python -m uvicorn main:app --reload --port 8000 > %TEMP%\sparksbm-api.log 2>&1
cd ..\frontend
set PORT=3002
start /B npm run dev > %TEMP%\sparksbm-notebookllm-frontend.log 2>&1
cd ..\..

echo.
echo ════════════════════════════════════════════════════════════════════════════
echo  SparksBM System Starting!
echo ════════════════════════════════════════════════════════════════════════════
echo.
echo  ISMS Platform:
echo    🌐 Frontend:    http://localhost:3001
echo    🔧 Backend:     http://localhost:8070
echo    🔐 Keycloak:    http://localhost:8080
echo.
echo  NotebookLLM:
echo    🌐 Frontend:    http://localhost:3002
echo    🔧 API:         http://localhost:8000
echo.
echo Services are starting in background...
echo.
echo Check logs:
echo   type %TEMP%\sparksbm-backend.log
echo   type %TEMP%\sparksbm-isms-frontend.log
echo   type %TEMP%\sparksbm-api.log
echo   type %TEMP%\sparksbm-notebookllm-frontend.log
echo.
echo Waiting 15 seconds for services to start...
timeout /t 15 /nobreak >nul
echo.
echo Services should be ready now!
echo.
pause
