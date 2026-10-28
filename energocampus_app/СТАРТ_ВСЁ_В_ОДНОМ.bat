@echo off
chcp 65001 > nul
title ИИС «ЭнергоКампус» — Сервер, База Данных SQLite и Панель Управления
py run_all_in_one.py
if errorlevel 1 (
    python run_all_in_one.py
)
pause
