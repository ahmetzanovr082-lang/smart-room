# -*- coding: utf-8 -*-
"""
Конфигурация серверного приложения ИИС «ЭнергоКампус».
Все секреты и параметры подключения считываются из переменных окружения;
в исходном коде отсутствуют жёстко заданные пароли или реальные ключи.
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("ENERGOCAMPUS_DB_PATH", os.path.join(BASE_DIR, "energocampus_demo.sqlite3"))
SCHEMA_SQL_PATH = os.path.join(BASE_DIR, "schema.sql")

HOST = os.environ.get("ENERGOCAMPUS_HOST", "127.0.0.1")
PORT = int(os.environ.get("ENERGOCAMPUS_PORT", "8000"))

# Демонстрационные токены ролевого доступа (только для локального учебного стенда;
# в промышленной среде задаются через переменные окружения)
ROLE_TOKENS = {
    os.environ.get("ENERGOCAMPUS_TOKEN_LABORANT", "demo-role-laborant"): {
        "user_id": 1,
        "login": "lab_operator",
        "role_code": "laborant",
        "role_name": "Лаборант компьютерного класса",
        "permissions": ["read", "simulate", "recommend_action", "export_csv"],
    },
    os.environ.get("ENERGOCAMPUS_TOKEN_MANAGER", "demo-role-energomanager"): {
        "user_id": 2,
        "login": "energy_chief",
        "role_code": "energomanager",
        "role_name": "Ответственный за энергохозяйство",
        "permissions": ["read", "simulate", "recommend_action", "settings", "export_csv", "analytics"],
    },
    os.environ.get("ENERGOCAMPUS_TOKEN_ADMIN", "demo-role-sysadmin"): {
        "user_id": 3,
        "login": "sys_admin",
        "role_code": "sys_admin",
        "role_name": "Администратор системы",
        "permissions": ["read", "simulate", "recommend_action", "settings", "export_csv", "analytics", "adapt_model", "admin"],
    },
}

DEFAULT_SETTINGS = {
    "pc_watts": 150,
    "light_watts": 120,
    "min_temp_c": 18.0,
    "max_temp_c": 26.0,
    # [ДАННЫЕ: действующий тариф университета в тенге за 1 кВт·ч]
    # В демонстрационном контуре используется условный расчётный тариф 32.50 тенге/кВт·ч
    "tariff_kzt_kwh": float(os.environ.get("ENERGOCAMPUS_TARIFF_KZT", "32.50")),
}

# Нормативные границы физической валидации входных данных (защита от искажения телеметрии)
VALIDATION_BOUNDS = {
    "pc_watts": (30, 1000),
    "light_watts": (10, 2000),
    "min_temp_c": (10.0, 25.0),
    "max_temp_c": (18.0, 35.0),
    "temp_c": (-10.0, 55.0),
    "tariff_kzt_kwh": (1.0, 500.0),
    "total_pcs": (1, 60),
    "open_windows": (0, 10),
}
