@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not defined TEMP exit /b 1

:choose_directory
set "TRAINING_DIR=%TEMP%\radar-training-%RANDOM%-%RANDOM%"
if exist "%TRAINING_DIR%" goto choose_directory
mkdir "%TRAINING_DIR%"
if errorlevel 1 exit /b 1

set "CRAWLER_AGENT_DATASET_PATH=%TRAINING_DIR%\crawler_agent_data.json"

"%PYTHON%" data\build_crawler_agent_data.py --output "%CRAWLER_AGENT_DATASET_PATH%"
if errorlevel 1 goto failed
"%PYTHON%" models\train_models.py
if errorlevel 1 goto failed
set "STATUS=0"
goto cleanup

:failed
set "STATUS=%ERRORLEVEL%"

:cleanup
rd /s /q "%TRAINING_DIR%"
if errorlevel 1 if "%STATUS%"=="0" set "STATUS=1"
exit /b %STATUS%