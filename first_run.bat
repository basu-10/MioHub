@echo off
echo Activating virtual environment...
call .venv\Scripts\activate
if errorlevel 1 (
    echo Failed to activate virtual environment.
    pause
    exit /b 1
)

echo Running database initialization...
python init_db.py
if errorlevel 1 (
    echo Failed to initialize database.
    pause
    exit /b 1
)

echo Creating additional test users...
python create_test_users.py
if errorlevel 1 (
    echo Failed to create test users.
    pause
    exit /b 1
)

echo First run setup completed successfully!
pause