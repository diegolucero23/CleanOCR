@echo off
setlocal
title CleanOCR Launcher

:: ---------------------------------------------------------
:: 1. Check for Docker
:: ---------------------------------------------------------
echo [1/4] Checking Docker status...
docker info >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    cls
    color 0C
    echo ========================================================
    echo  [ERROR] DOCKER IS NOT RUNNING
    echo ========================================================
    echo.
    echo  Please open "Docker Desktop" from your Start Menu.
    echo  Wait for the whale icon to stop animating.
    echo  Then run this script again.
    echo.
    echo ========================================================
    pause
    exit /b
)

:: ---------------------------------------------------------
:: 2. Check/Create .env Configuration
:: ---------------------------------------------------------
echo [2/4] Checking configuration...
if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        cls
        color 0E
        echo ========================================================
        echo  [SETUP] FIRST RUN CONFIGURATION
        echo ========================================================
        echo.
        echo  We have created a ".env" file for you.
        echo.
        echo  ACTION REQUIRED:
        echo  1. Open the file ".env" in Notepad.
        echo  2. Paste your Google API Key next to GOOGLE_API_KEY=
        echo  3. Save the file.
        echo.
        echo  Once done, run this script again.
        echo ========================================================
        pause
        exit /b
    ) else (
        echo [ERROR] .env.example not found! Cannot create config.
        pause
        exit /b
    )
)

:: ---------------------------------------------------------
:: 3. Launch Application
:: ---------------------------------------------------------
echo [3/4] Launching CleanOCR Containers...
echo.
docker-compose up -d --build
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker Compose failed to start.
    pause
    exit /b
)

:: ---------------------------------------------------------
:: 4. Wait for Health & Open Browser
:: ---------------------------------------------------------
echo.
echo [4/4] Waiting for application to startup (this may take 30s)...
echo.

:wait_loop
timeout /t 2 >nul
curl -s http://localhost:8000/docs >nul
if %ERRORLEVEL% NEQ 0 (
    <nul set /p=.
    goto wait_loop
)

echo.
echo.
echo ========================================================
echo   CLEANOCR IS READY!
echo ========================================================
echo.
echo  Opening browser to: http://localhost:5173
echo.

start http://localhost:5173

echo  [PRESS ANY KEY TO STOP THE SERVER AND EXIT]
pause >nul

echo Stopping containers...
docker-compose down
echo Bye!
timeout /t 2 >nul
