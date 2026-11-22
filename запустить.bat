@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
if exist log.txt del /q log.txt
python bot.py
echo.
echo ============================================================
echo  Bot stopped. If there was an error, open log.txt
echo ============================================================
pause >nul
