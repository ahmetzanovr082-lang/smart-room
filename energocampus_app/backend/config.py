# -*- coding: utf-8 -*-
"""
Конфигурация серверного приложения ИИС «ЭнергоКампус».
Все секреты и параметры подключения считываются из переменных окружения (или локального файла .env);
в исходном коде отсутствуют жёстко заданные пароли или реальные ключи.
"""
import hashlib
import os
from typing import Dict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_dotenv_if_exists(env_path: str) -> None:
    """Загрузка переменных окружения из локального файла .env (если он существует)."""
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'").strip('"')
                if k and k not in os.environ:
                    os.environ[k] = v
    except OSError:
        pass


_load_dotenv_if_exists(os.path.join(BASE_DIR, ".env"))

DB_PATH = os.environ.get("ENERGOCAMPUS_DB_PATH", os.path.join(BASE_DIR, "energocampus_demo.sqlite3"))
SCHEMA_SQL_PATH = os.path.join(BASE_DIR, "schema.sql")

HOST = os.environ.get("ENERGOCAMPUS_HOST", "127.0.0.1")
PORT = int(os.environ.get("ENERGOCAMPUS_PORT", "8000"))

# Профили ролей для демонстрационной ролевой модели RBAC
ROLE_PROFILES = {
    "laborant": {
        "user_id": 1,
        "login": "lab_operator",
        "role_code": "laborant",
        "role_name": "Лаборант компьютерного класса",
        "permissions": ["read", "simulate", "recommend_action", "export_csv"],
    },
    "energomanager": {
        "user_id": 2,
        "login": "energy_chief",
        "role_code": "energomanager",
        "role_name": "Ответственный за энергохозяйство",
        "permissions": ["read", "simulate", "recommend_action", "settings", "export_csv", "analytics"],
    },
    "sys_admin": {
        "user_id": 3,
        "login": "sys_admin",
        "role_code": "sys_admin",
        "role_name": "Администратор системы",
        "permissions": ["read", "simulate", "recommend_action", "settings", "export_csv", "analytics", "adapt_model", "admin"],
    },
}

# Демонстрационные токены ролевого доступа (для автотестов и обратной совместимости стенда)
ROLE_TOKENS = {
    os.environ.get("ENERGOCAMPUS_TOKEN_LABORANT", "demo-role-laborant"): ROLE_PROFILES["laborant"],
    os.environ.get("ENERGOCAMPUS_TOKEN_MANAGER", "demo-role-energomanager"): ROLE_PROFILES["energomanager"],
    os.environ.get("ENERGOCAMPUS_TOKEN_ADMIN", "demo-role-sysadmin"): ROLE_PROFILES["sys_admin"],
}

# Хранилище выданных случайных сессионных токенов в памяти сервера
ACTIVE_SESSION_TOKENS: Dict[str, dict] = {}

# SHA-256 дайджест демонстрационного кода по умолчанию (используется только если не заданы переменные окружения)
DEFAULT_DEMO_PASS_SHA256 = os.environ.get(
    "ENERGOCAMPUS_PASS_SHA256",
    "0ffe1abd1a08215353c233d6e009613e95eec4253832a761af28ff37ac5a150c",
)


def verify_role_password(role_code: str, candidate_password: str) -> bool:
    """
    Проверка пароля для переключения привилегированной роли.
    Приоритетно считывает пароли из переменных окружения ENERGOCAMPUS_PASS_MANAGER,
    ENERGOCAMPUS_PASS_ADMIN или ENERGOCAMPUS_ROLE_PASSWORD. Если переменные окружения
    не заданы, сверяет SHA-256 хеш без хранения пароля в открытом виде.
    """
    pwd = (candidate_password or "").strip()
    if not pwd:
        return False

    env_specific = (
        os.environ.get("ENERGOCAMPUS_PASS_ADMIN")
        if role_code in ("sys_admin", "sysadmin")
        else os.environ.get("ENERGOCAMPUS_PASS_MANAGER")
    )
    env_common = os.environ.get("ENERGOCAMPUS_ROLE_PASSWORD")
    expected_plain = env_specific or env_common
    if expected_plain:
        return pwd == expected_plain

    digest = hashlib.sha256(pwd.encode("utf-8")).hexdigest()
    return digest == DEFAULT_DEMO_PASS_SHA256


DEFAULT_SETTINGS = {
    "pc_watts": 150,
    "light_watts": 120,
    "min_temp_c": 18.0,
    "max_temp_c": 26.0,
    # [ДАННЫЕ: действующий тариф университета в тенге за 1 кВт·ч]
    # В демонстрационном контуре используется условный расчётный тариф 32.50 тенге/кВт·ч
    "tariff_kzt_kwh": float(os.environ.get("ENERGOCAMPUS_TARIFF_KZT", "32.50")),
}

# Нормативные границы физической валидации входных данных (защита от искажения телеметрии и таблиц БД)
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
