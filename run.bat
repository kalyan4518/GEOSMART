@echo off
setlocal

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"
if errorlevel 1 (
  echo ERROR: Could not open the project directory: "%PROJECT_DIR%"
  exit /b 1
)

where py >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul
  if errorlevel 1 (
    echo ERROR: Python was not found. Install 64-bit Python 3.10-3.14 and enable the Python launcher.
    exit /b 1
  )
  set "PYTHON_CMD=python"
) else (
  set "PYTHON_CMD=py -3.14"
)

if not exist ".venv\Scripts\activate.bat" (
  echo ERROR: The project virtual environment is missing.
  echo Create it with: %PYTHON_CMD% -m venv .venv
  echo Then run: .venv\Scripts\python.exe -m pip install -r requirements.txt
  exit /b 1
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
  echo ERROR: Could not activate .venv.
  exit /b 1
)

python -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] <= (3, 14) else 1)"
if errorlevel 1 (
  echo ERROR: .venv must use a supported Python version from 3.10 through 3.14.
  echo Recreate it with: py -3.14 -m venv .venv
  exit /b 1
)

python -c "import flask, dotenv, yaml, sqlalchemy, ultralytics, cv2"
if errorlevel 1 (
  echo ERROR: Required packages are missing from .venv.
  echo Install them with: .venv\Scripts\python.exe -m pip install -r requirements.txt
  exit /b 1
)

echo Starting GEOSMART at http://127.0.0.1:5000
python app.py
if errorlevel 1 (
  echo ERROR: GEOSMART exited with an error. Review the traceback above.
  exit /b 1
)

endlocal
