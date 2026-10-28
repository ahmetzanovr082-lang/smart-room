@echo off
chcp 65001 > nul
title EnergoCampus IIS — All-in-One Launcher
py run_all_in_one.py
if errorlevel 1 (
    python run_all_in_one.py
)
pause
