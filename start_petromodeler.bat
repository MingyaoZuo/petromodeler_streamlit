@echo off
setlocal

set "PROJECT_DIR=D:\Geomodel\petromodeler_streamlit"
set "APP_FILE=streamlit_app.py"
set "PORT=8501"

cd /d "%PROJECT_DIR%"
if errorlevel 1 (
    echo Failed to enter project directory: %PROJECT_DIR%
    pause
    exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found in PATH.
    echo Please install Python or add it to PATH, then run this shortcut again.
    pause
    exit /b 1
)

python -c "import streamlit" >nul 2>nul
if errorlevel 1 (
    echo Streamlit is not installed. Installing dependencies from requirements.txt...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Failed to install dependencies.
        pause
        exit /b 1
    )
)

echo Starting PetroModeler Streamlit app...
echo Project: %PROJECT_DIR%
echo URL: http://localhost:%PORT%
echo.

start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://localhost:%PORT%'"
python -m streamlit run "%APP_FILE%" --server.port %PORT%

echo.
echo Streamlit has stopped.
pause
