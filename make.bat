@echo off
REM EII — ERP Incident Intelligence
REM Windows batch helper (run in cmd.exe or PowerShell: .\make.bat <target>)

set PYTHON=python
set PIP=pip

if "%1"=="install" goto install
if "%1"=="run" goto run
if "%1"=="api" goto api
if "%1"=="test" goto test
if "%1"=="test-all" goto test-all
if "%1"=="docker-build" goto docker-build
if "%1"=="docker-run" goto docker-run
if "%1"=="clean" goto clean

echo Usage: make.bat [install ^| run ^| api ^| test ^| test-all ^| docker-build ^| docker-run ^| clean]
goto eof

:install
%PIP% install -r requirements.txt
goto eof

:run
%PYTHON% app.py
goto eof

:api
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
goto eof

:test
%PYTHON% -m pytest tests/ -v --tb=short
goto eof

:test-all
%PYTHON% -m pytest tests/ smartrouter/tests/ -v --tb=short
goto eof

:docker-build
docker build -t eii .
goto eof

:docker-run
docker run -p 7860:7860 --env-file .env eii
goto eof

:clean
for /r %%i in (__pycache__) do if exist "%%i" rmdir /s /q "%%i"
del /s /q *.pyc 2>nul
del /q eii_incidents.db 2>nul

goto eof

:eof
