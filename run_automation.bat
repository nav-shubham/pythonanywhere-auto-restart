@echo off
cd /d "%~dp0"
echo Running PythonAnywhere automation...
uv run main.py
echo.
echo Task completed. Log details saved to automation.log
pause
