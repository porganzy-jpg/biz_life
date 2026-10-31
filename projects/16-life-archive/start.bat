@echo off
cd /d "%~dp0"
echo 나의 아카이브: http://localhost:8016
start "" http://localhost:8016
python app.py
