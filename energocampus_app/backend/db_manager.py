# -*- coding: utf-8 -*-
"""
Менеджер реляционной базы данных ИИС «ЭнергоКампус» (14 таблиц в 3НФ).
Обеспечивает:
- автоматическое создание схемы из 14 таблиц (совместимой с schema.sql для PostgreSQL 16 и локальным движком SQLite 3);
- начальное заполнение синтетическими демонстрационными данными 6 учебных кабинетов (72 ПК);
- строго параметризованные SQL-запросы (защита от SQL-инъекций);
- дедупликацию пакетов телеметрии по (room_id, boot_id, sequence);
- хранение и обновление статусов рекомендаций ('new', 'accepted', 'completed', 'rejected') с меткой времени processed_at.
"""
import contextlib
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .ai_engine import EnergoAIEngine, ROOMS_CATALOG
from .config import DB_PATH, DEFAULT_SETTINGS
from .validators import (
    ValidationError,
    sanitize_text,
    validate_readonly_sql_query,
    validate_settings_payload,
    validate_table_row_update,
    validate_telemetry_payload,
)

ALL_14_TABLES = [
    "roles",
    "users",
    "rooms",
    "room_controllers",
    "workstations_devices",
    "schedule_slots",
    "system_settings_tariffs",
    "telemetry_measurements",
    "ml_models",
    "ai_evaluation_runs",
    "energy_forecasts",
    "detected_anomalies",
    "saving_recommendations",
    "system_events_log",
]

INITIAL_ROOMS_SEED = [
    {"room_id": "201", "floor": 2, "name": "Компьютерный класс", "type": "Компьютерный класс", "total_pcs": 12, "active_pcs": 7, "light_on": True, "door_open": False, "open_windows": 0, "temp_c": 22.4, "is_occupied": True, "is_online": True},
    {"room_id": "202", "floor": 2, "name": "Лаборатория информатики", "type": "Учебная лаборатория", "total_pcs": 12, "active_pcs": 0, "light_on": False, "door_open": False, "open_windows": 0, "temp_c": 21.6, "is_occupied": False, "is_online": True},
    {"room_id": "204", "floor": 2, "name": "Компьютерный класс", "type": "Компьютерный класс", "total_pcs": 12, "active_pcs": 4, "light_on": True, "door_open": True, "open_windows": 0, "temp_c": 23.1, "is_occupied": False, "is_online": True},
    {"room_id": "301", "floor": 3, "name": "Лаборатория программирования", "type": "Учебная лаборатория", "total_pcs": 16, "active_pcs": 8, "light_on": True, "door_open": False, "open_windows": 0, "temp_c": 24.2, "is_occupied": True, "is_online": True},
    {"room_id": "302", "floor": 3, "name": "Мультимедийный класс", "type": "Мультимедийная аудитория", "total_pcs": 8, "active_pcs": 2, "light_on": False, "door_open": False, "open_windows": 1, "temp_c": 17.8, "is_occupied": False, "is_online": True},
    {"room_id": "305", "floor": 3, "name": "Компьютерный класс", "type": "Компьютерный класс", "total_pcs": 12, "active_pcs": 0, "light_on": False, "door_open": False, "open_windows": 0, "temp_c": 21.2, "is_occupied": False, "is_online": False},
]

# Профили нагрузки по умолчанию для графиков «Сутки» (24 ч) и «Неделя» (7 дн.)
CAMPUS_DAY_CURRENT = [0.25, 0.22, 0.20, 0.20, 0.20, 0.25, 0.30, 0.65, 2.40, 3.80, 3.20, 4.10, 3.50, 4.40, 3.50, 3.20, 2.50, 1.70, 1.20, 0.50, 0.30, 0.25, 0.23, 0.20]
CAMPUS_DAY_BASE = [0.80, 0.80, 0.70, 0.70, 0.70, 0.80, 0.90, 1.60, 3.20, 4.80, 4.20, 5.30, 4.60, 5.40, 4.60, 4.20, 3.60, 2.80, 2.30, 1.60, 1.40, 1.20, 1.10, 0.90]
CAMPUS_WEEK_CURRENT = [24.0, 28.0, 26.0, 30.0, 22.0, 9.0, 7.0]
CAMPUS_WEEK_BASE = [34.0, 38.0, 35.0, 41.0, 33.0, 16.0, 13.0]


class DatabaseManager:
    """Управление реляционной БД из 14 таблиц (PostgreSQL 16 DDL / локальное исполнение SQLite 3)."""

    def __init__(self, db_path: str = DB_PATH, ai_engine: Optional[EnergoAIEngine] = None):
        self.db_path = db_path
        self.ai_engine = ai_engine or EnergoAIEngine()
        self._dedup_cache: Dict[Tuple[str, str], int] = {}
        self.init_database()

    @contextlib.contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
        finally:
            conn.close()

    def init_database(self, force_reset: bool = False) -> None:
        """Создание всех 14 таблиц схемы и заполнение начальными демонстрационными данными при первом запуске."""
        if force_reset and os.path.exists(self.db_path) and self.db_path != ":memory:":
            os.remove(self.db_path)

        with self._connect() as conn:
            cur = conn.cursor()
            if force_reset:
                for tbl in [
                    "system_events_log", "saving_recommendations", "detected_anomalies",
                    "energy_forecasts", "ai_evaluation_runs", "ml_models",
                    "telemetry_measurements", "system_settings_tariffs", "schedule_slots",
                    "workstations_devices", "room_controllers", "rooms", "users", "roles"
                ]:
                    cur.execute(f"DROP TABLE IF EXISTS {tbl};")

            # Создание всех 14 нормализованных таблиц (полное соответствие schema.sql из Главы 2)
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS roles (
                    role_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role_code TEXT NOT NULL UNIQUE,
                    role_name TEXT NOT NULL,
                    permissions_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role_id INTEGER NOT NULL REFERENCES roles(role_id) ON DELETE RESTRICT,
                    login TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    position_title TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS rooms (
                    room_id TEXT PRIMARY KEY,
                    building_code TEXT NOT NULL DEFAULT 'A',
                    floor_num INTEGER NOT NULL CHECK (floor_num BETWEEN 1 AND 12),
                    room_name TEXT NOT NULL,
                    room_type TEXT NOT NULL,
                    total_pcs INTEGER NOT NULL CHECK (total_pcs >= 0),
                    light_line_watts INTEGER NOT NULL DEFAULT 120 CHECK (light_line_watts >= 0),
                    current_state TEXT NOT NULL DEFAULT 'S2_IDLE'
                        CHECK (current_state IN ('S1_OCCUPIED', 'S2_IDLE', 'S3_EXCESS', 'S0_OFFLINE'))
                );

                CREATE TABLE IF NOT EXISTS room_controllers (
                    controller_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id TEXT NOT NULL UNIQUE REFERENCES rooms(room_id) ON DELETE CASCADE,
                    mac_address TEXT NOT NULL UNIQUE,
                    ip_address TEXT NULL,
                    firmware_ver TEXT NOT NULL DEFAULT 'v1.0.0',
                    is_online INTEGER NOT NULL DEFAULT 1,
                    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS workstations_devices (
                    device_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id TEXT NOT NULL REFERENCES rooms(room_id) ON DELETE CASCADE,
                    device_code TEXT NOT NULL,
                    device_type TEXT NOT NULL DEFAULT 'PC'
                        CHECK (device_type IN ('PC', 'LIGHT', 'HVAC', 'SWITCH')),
                    rated_watts INTEGER NOT NULL DEFAULT 150 CHECK (rated_watts > 0),
                    is_power_on INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (room_id, device_code)
                );

                CREATE TABLE IF NOT EXISTS schedule_slots (
                    slot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id TEXT NOT NULL REFERENCES rooms(room_id) ON DELETE CASCADE,
                    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
                    pair_number INTEGER NOT NULL CHECK (pair_number BETWEEN 1 AND 8),
                    time_start TEXT NOT NULL,
                    time_end TEXT NOT NULL,
                    group_code TEXT NOT NULL,
                    subject_name TEXT NOT NULL,
                    teacher_name TEXT NULL,
                    CHECK (time_end > time_start)
                );

                CREATE TABLE IF NOT EXISTS system_settings_tariffs (
                    setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pc_watts INTEGER NOT NULL DEFAULT 150 CHECK (pc_watts BETWEEN 30 AND 1000),
                    light_watts INTEGER NOT NULL DEFAULT 120 CHECK (light_watts BETWEEN 10 AND 2000),
                    min_temp_c REAL NOT NULL DEFAULT 18.0 CHECK (min_temp_c BETWEEN 10.0 AND 25.0),
                    max_temp_c REAL NOT NULL DEFAULT 26.0 CHECK (max_temp_c BETWEEN 18.0 AND 35.0),
                    tariff_kzt_kwh REAL NOT NULL DEFAULT 32.50 CHECK (tariff_kzt_kwh > 0),
                    valid_from TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    CHECK (max_temp_c > min_temp_c)
                );

                CREATE TABLE IF NOT EXISTS telemetry_measurements (
                    measurement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id TEXT NOT NULL REFERENCES rooms(room_id) ON DELETE RESTRICT,
                    controller_id INTEGER NOT NULL REFERENCES room_controllers(controller_id) ON DELETE RESTRICT,
                    measured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    is_online INTEGER NOT NULL DEFAULT 1,
                    is_occupied INTEGER NOT NULL DEFAULT 0,
                    active_pcs INTEGER NOT NULL CHECK (active_pcs >= 0),
                    total_pcs INTEGER NOT NULL CHECK (total_pcs >= 0),
                    light_on INTEGER NOT NULL DEFAULT 0,
                    pc_watts_snapshot INTEGER NOT NULL CHECK (pc_watts_snapshot > 0),
                    light_watts_snapshot INTEGER NOT NULL CHECK (light_watts_snapshot >= 0),
                    tariff_kzt_snapshot REAL NOT NULL CHECK (tariff_kzt_snapshot > 0),
                    temp_c REAL NOT NULL CHECK (temp_c BETWEEN -10.0 AND 55.0),
                    open_windows INTEGER NOT NULL DEFAULT 0 CHECK (open_windows >= 0),
                    door_open INTEGER NOT NULL DEFAULT 0,
                    calc_power_kw REAL NOT NULL CHECK (calc_power_kw >= 0),
                    CHECK (active_pcs <= total_pcs)
                );

                CREATE TABLE IF NOT EXISTS ml_models (
                    model_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_name TEXT NOT NULL,
                    version_tag TEXT NOT NULL UNIQUE,
                    algorithm_type TEXT NOT NULL,
                    artifact_uri TEXT NULL,
                    confidence_threshold REAL NOT NULL DEFAULT 0.75 CHECK (confidence_threshold BETWEEN 0.00 AND 1.00),
                    metrics_json TEXT NOT NULL DEFAULT '{}',
                    trained_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS ai_evaluation_runs (
                    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id TEXT NOT NULL REFERENCES rooms(room_id) ON DELETE RESTRICT,
                    measurement_id INTEGER NOT NULL REFERENCES telemetry_measurements(measurement_id) ON DELETE CASCADE,
                    model_id INTEGER NOT NULL REFERENCES ml_models(model_id) ON DELETE RESTRICT,
                    setting_id INTEGER NOT NULL REFERENCES system_settings_tariffs(setting_id) ON DELETE RESTRICT,
                    derived_features TEXT NOT NULL DEFAULT '{}',
                    state_class TEXT NOT NULL
                        CHECK (state_class IN ('S1_OCCUPIED', 'S2_IDLE', 'S3_EXCESS', 'S0_OFFLINE')),
                    current_power_kw REAL NOT NULL CHECK (current_power_kw >= 0),
                    baseline_forecast_kw REAL NOT NULL CHECK (baseline_forecast_kw >= 0),
                    saving_kwh_1h REAL NOT NULL DEFAULT 0.00 CHECK (saving_kwh_1h >= 0),
                    saving_kwh_4h REAL NOT NULL DEFAULT 0.00 CHECK (saving_kwh_4h >= 0),
                    saving_kzt_4h REAL NOT NULL DEFAULT 0.00 CHECK (saving_kzt_4h >= 0),
                    confidence_score REAL NOT NULL DEFAULT 1.00 CHECK (confidence_score BETWEEN 0.00 AND 1.00),
                    evaluated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS energy_forecasts (
                    forecast_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id TEXT NOT NULL REFERENCES rooms(room_id) ON DELETE CASCADE,
                    model_id INTEGER NOT NULL REFERENCES ml_models(model_id) ON DELETE RESTRICT,
                    horizon_type TEXT NOT NULL CHECK (horizon_type IN ('day_24h', 'week_7d')),
                    target_timestamp TEXT NOT NULL,
                    predicted_kw REAL NOT NULL CHECK (predicted_kw >= 0),
                    baseline_no_ctrl_kw REAL NOT NULL CHECK (baseline_no_ctrl_kw >= 0),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS detected_anomalies (
                    anomaly_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL REFERENCES ai_evaluation_runs(run_id) ON DELETE CASCADE,
                    room_id TEXT NOT NULL REFERENCES rooms(room_id) ON DELETE RESTRICT,
                    anomaly_type TEXT NOT NULL
                        CHECK (anomaly_type IN ('energy', 'climate', 'window', 'offline')),
                    severity TEXT NOT NULL DEFAULT 'warning'
                        CHECK (severity IN ('warning', 'neutral', 'critical')),
                    title TEXT NOT NULL,
                    explanation_text TEXT NOT NULL,
                    xai_factors TEXT NOT NULL DEFAULT '[]',
                    detected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS saving_recommendations (
                    recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    anomaly_id INTEGER NOT NULL REFERENCES detected_anomalies(anomaly_id) ON DELETE CASCADE,
                    room_id TEXT NOT NULL REFERENCES rooms(room_id) ON DELETE RESTRICT,
                    assigned_user_id INTEGER NULL REFERENCES users(user_id) ON DELETE SET NULL,
                    action_text TEXT NOT NULL,
                    expected_saving_kwh REAL NOT NULL DEFAULT 0.00 CHECK (expected_saving_kwh >= 0),
                    expected_saving_kzt REAL NOT NULL DEFAULT 0.00 CHECK (expected_saving_kzt >= 0),
                    status TEXT NOT NULL DEFAULT 'new'
                        CHECK (status IN ('new', 'accepted', 'completed', 'rejected')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    processed_at TEXT NULL,
                    operator_comment TEXT NULL,
                    CHECK (
                        (status = 'new' AND processed_at IS NULL)
                        OR (status IN ('accepted', 'completed', 'rejected') AND processed_at IS NOT NULL)
                    )
                );

                CREATE TABLE IF NOT EXISTS system_events_log (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id TEXT NULL REFERENCES rooms(room_id) ON DELETE SET NULL,
                    user_id INTEGER NULL REFERENCES users(user_id) ON DELETE SET NULL,
                    run_id INTEGER NULL REFERENCES ai_evaluation_runs(run_id) ON DELETE SET NULL,
                    event_type TEXT NOT NULL
                        CHECK (event_type IN ('energy', 'climate', 'window', 'offline', 'ok', 'settings', 'report_export')),
                    event_text TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            cnt = cur.execute("SELECT COUNT(*) FROM rooms;").fetchone()[0]
            if cnt == 0:
                self._seed_initial_data(conn)
            conn.commit()

    def _seed_initial_data(self, conn: sqlite3.Connection) -> None:
        """Начальное заполнение всех 14 таблиц демонстрационными синтетическими данными."""
        cur = conn.cursor()
        now = datetime.now(timezone.utc)

        # 1. Роли (4 роли из UML Use Case)
        roles_data = [
            ("laborant", "Лаборант компьютерного класса", json.dumps({"read": True, "simulate": True, "recommend_action": True})),
            ("energomanager", "Ответственный за энергохозяйство", json.dumps({"read": True, "analytics": True, "settings": True, "export_csv": True})),
            ("it_admin", "ИТ-администратор", json.dumps({"read": True, "controllers": True, "logs": True})),
            ("sys_admin", "Администратор системы", json.dumps({"all": True})),
        ]
        cur.executemany(
            "INSERT INTO roles (role_code, role_name, permissions_json) VALUES (?, ?, ?);",
            roles_data,
        )

        # 2. Пользователи (без реальных паролей и персональных данных — учебные хеши-заглушки)
        users_data = [
            (1, "lab_operator", "$2b$12$DEMO_HASH_PLACEHOLDER_LABORANT", "Оператор смены № 1", "Дежурный лаборант корпуса А", 1),
            (2, "energy_chief", "$2b$12$DEMO_HASH_PLACEHOLDER_MANAGER", "Главный энергетик корпуса А", "Ответственный за энергохозяйство", 1),
            (3, "it_engineer", "$2b$12$DEMO_HASH_PLACEHOLDER_ITADMIN", "Инженер ИТ-службы", "Инженер по обслуживанию датчиков", 1),
            (4, "sys_admin", "$2b$12$DEMO_HASH_PLACEHOLDER_SYSADMIN", "Администратор ИИС", "Системный администратор", 1),
        ]
        cur.executemany(
            "INSERT INTO users (role_id, login, password_hash, full_name, position_title, is_active) VALUES (?, ?, ?, ?, ?, ?);",
            users_data,
        )

        # 7. Настройки и тариф
        cur.execute(
            """
            INSERT INTO system_settings_tariffs (pc_watts, light_watts, min_temp_c, max_temp_c, tariff_kzt_kwh, is_active)
            VALUES (?, ?, ?, ?, ?, 1);
            """,
            (
                DEFAULT_SETTINGS["pc_watts"],
                DEFAULT_SETTINGS["light_watts"],
                DEFAULT_SETTINGS["min_temp_c"],
                DEFAULT_SETTINGS["max_temp_c"],
                DEFAULT_SETTINGS["tariff_kzt_kwh"],
            ),
        )
        setting_id = cur.lastrowid

        # 9. Реестр моделей ИИ
        cur.execute(
            """
            INSERT INTO ml_models (model_name, version_tag, algorithm_type, artifact_uri, confidence_threshold, metrics_json, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1);
            """,
            (
                "EnergoHybrid_Rule_GBR",
                self.ai_engine.version_tag,
                self.ai_engine.algorithm_type,
                "memory://scikit-learn/GradientBoostingRegressor",
                self.ai_engine.confidence_threshold,
                json.dumps(self.ai_engine.metrics, ensure_ascii=False),
            ),
        )
        model_id = cur.lastrowid

        # 3, 4, 5, 6. Кабинеты, контроллеры ESP32, 72 рабочих места ПК и расписание пар
        for idx, r in enumerate(INITIAL_ROOMS_SEED, start=1):
            room_id = r["room_id"]
            init_state = "S0_OFFLINE" if not r["is_online"] else ("S1_OCCUPIED" if r["is_occupied"] else "S2_IDLE")
            cur.execute(
                """
                INSERT INTO rooms (room_id, building_code, floor_num, room_name, room_type, total_pcs, light_line_watts, current_state)
                VALUES (?, 'A', ?, ?, ?, ?, 120, ?);
                """,
                (room_id, r["floor"], r["name"], r["type"], r["total_pcs"], init_state),
            )

            seen_time = (now - timedelta(minutes=8 if not r["is_online"] else 0)).isoformat()
            cur.execute(
                """
                INSERT INTO room_controllers (room_id, mac_address, ip_address, firmware_ver, is_online, last_seen_at)
                VALUES (?, ?, ?, 'v1.2.0-esp32', ?, ?);
                """,
                (
                    room_id,
                    f"AA:BB:CC:00:0{idx}:0{idx}",
                    f"192.168.10.{100 + int(room_id)}",
                    1 if r["is_online"] else 0,
                    seen_time,
                ),
            )
            controller_id = cur.lastrowid

            # Поштучный реестр ПК (72 компьютера суммарно по 6 кабинетам)
            for pc_i in range(1, r["total_pcs"] + 1):
                is_on = 1 if pc_i <= r["active_pcs"] else 0
                cur.execute(
                    """
                    INSERT INTO workstations_devices (room_id, device_code, device_type, rated_watts, is_power_on, updated_at)
                    VALUES (?, ?, 'PC', 150, ?, ?);
                    """,
                    (room_id, f"PC-{pc_i:02d}", is_on, seen_time),
                )

            # Расписание учебных пар (schedule_slots)
            cur.execute(
                """
                INSERT INTO schedule_slots (room_id, day_of_week, pair_number, time_start, time_end, group_code, subject_name, teacher_name)
                VALUES (?, 3, 3, '12:00', '13:30', ?, ?, 'доц. Астапенко Н. В.');
                """,
                (
                    room_id,
                    "ИСУ-23-1" if r["floor"] == 2 else "ИСУ(kz-us)-23-2",
                    "Интеллектуальные информационные системы",
                ),
            )

            # Первичный замер, запуск ИИ-модуля, аномалии и рекомендации
            self._record_evaluation_internal(
                cur=cur,
                room_id=room_id,
                controller_id=controller_id,
                setting_id=setting_id,
                model_id=model_id,
                payload={
                    "room_id": room_id,
                    "online": r["is_online"],
                    "occupied": r["is_occupied"],
                    "computers_on": r["active_pcs"],
                    "total_pcs": r["total_pcs"],
                    "light_on": r["light_on"],
                    "windows_open": r["open_windows"],
                    "door_open": r["door_open"],
                    "temp_c": r["temp_c"],
                },
                measured_at=seen_time,
            )

            # Суточные и недельные прогнозы (energy_forecasts) для каждого кабинета
            room_share = r["total_pcs"] / 72.0
            for h_idx in range(24):
                t_stamp = (now.replace(hour=h_idx, minute=0, second=0, microsecond=0)).isoformat()
                cur.execute(
                    """
                    INSERT INTO energy_forecasts (room_id, model_id, horizon_type, target_timestamp, predicted_kw, baseline_no_ctrl_kw)
                    VALUES (?, ?, 'day_24h', ?, ?, ?);
                    """,
                    (
                        room_id,
                        model_id,
                        t_stamp,
                        round(CAMPUS_DAY_CURRENT[h_idx] * room_share, 2),
                        round(CAMPUS_DAY_BASE[h_idx] * room_share, 2),
                    ),
                )
            for d_idx in range(7):
                t_stamp = (now + timedelta(days=d_idx)).strftime("%Y-%m-%d")
                cur.execute(
                    """
                    INSERT INTO energy_forecasts (room_id, model_id, horizon_type, target_timestamp, predicted_kw, baseline_no_ctrl_kw)
                    VALUES (?, ?, 'week_7d', ?, ?, ?);
                    """,
                    (
                        room_id,
                        model_id,
                        t_stamp,
                        round(CAMPUS_WEEK_CURRENT[d_idx] * room_share, 2),
                        round(CAMPUS_WEEK_BASE[d_idx] * room_share, 2),
                    ),
                )

    def _record_evaluation_internal(
        self,
        cur: sqlite3.Cursor,
        room_id: str,
        controller_id: int,
        setting_id: int,
        model_id: int,
        payload: Dict[str, Any],
        measured_at: str,
    ) -> Dict[str, Any]:
        """Внутренняя транзакционная запись среза телеметрии, запуска ИИ, аномалий и рекомендаций."""
        settings_row = cur.execute(
            "SELECT pc_watts, light_watts, min_temp_c, max_temp_c, tariff_kzt_kwh FROM system_settings_tariffs WHERE setting_id = ?;",
            (setting_id,),
        ).fetchone()
        settings = dict(settings_row) if settings_row else dict(DEFAULT_SETTINGS)

        ai_res = self.ai_engine.evaluate_room(payload, settings=settings)
        calc_kw = ai_res["current_power_kw"] if ai_res["current_power_kw"] is not None else 0.0

        # Шаг BP-04: Запись входных факторов x1..x7 в telemetry_measurements
        cur.execute(
            """
            INSERT INTO telemetry_measurements (
                room_id, controller_id, measured_at, is_online, is_occupied,
                active_pcs, total_pcs, light_on, pc_watts_snapshot, light_watts_snapshot,
                tariff_kzt_snapshot, temp_c, open_windows, door_open, calc_power_kw
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                room_id,
                controller_id,
                measured_at,
                1 if payload["online"] else 0,
                1 if payload["occupied"] else 0,
                payload["computers_on"],
                payload["total_pcs"],
                1 if payload["light_on"] else 0,
                settings["pc_watts"],
                settings["light_watts"],
                settings["tariff_kzt_kwh"],
                payload["temp_c"],
                payload["windows_open"],
                1 if payload["door_open"] else 0,
                calc_kw,
            ),
        )
        measurement_id = cur.lastrowid

        # Обновление статуса контроллера и кабинета
        cur.execute(
            "UPDATE room_controllers SET is_online = ?, last_seen_at = ? WHERE controller_id = ?;",
            (1 if payload["online"] else 0, measured_at, controller_id),
        )
        cur.execute(
            "UPDATE rooms SET current_state = ? WHERE room_id = ?;",
            (ai_res["state_class"], room_id),
        )

        # Обновление поштучного состояния ПК, если передан массив computers
        computers_arr = payload.get("computers")
        if isinstance(computers_arr, list):
            for idx_pc, is_on in enumerate(computers_arr, start=1):
                cur.execute(
                    "UPDATE workstations_devices SET is_power_on = ?, updated_at = ? WHERE room_id = ? AND device_code = ?;",
                    (1 if is_on else 0, measured_at, room_id, f"PC-{idx_pc:02d}"),
                )
        else:
            cur.execute(
                """
                UPDATE workstations_devices
                SET is_power_on = CASE WHEN CAST(SUBSTR(device_code, 4) AS INTEGER) <= ? THEN 1 ELSE 0 END,
                    updated_at = ?
                WHERE room_id = ? AND device_type = 'PC';
                """,
                (payload["computers_on"], measured_at, room_id),
            )

        # Шаг BP-06 / BP-08: Запись запуска ИИ в ai_evaluation_runs
        derived = {
            "hour": 14,
            "day_of_week": 3,
            "alpha_ml_used": ai_res["alpha_ml_used"],
            "is_synthetic": True,
        }
        cur.execute(
            """
            INSERT INTO ai_evaluation_runs (
                room_id, measurement_id, model_id, setting_id, derived_features,
                state_class, current_power_kw, baseline_forecast_kw,
                saving_kwh_1h, saving_kwh_4h, saving_kzt_4h, confidence_score, evaluated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                room_id,
                measurement_id,
                model_id,
                setting_id,
                json.dumps(derived, ensure_ascii=False),
                ai_res["state_class"],
                calc_kw,
                ai_res["baseline_forecast_kw"] if ai_res["baseline_forecast_kw"] is not None else 0.0,
                ai_res["saving_potential_kwh_1h"],
                ai_res["saving_kwh_4h"],
                ai_res["saving_potential_kzt_4h"],
                ai_res["confidence_score"],
                measured_at,
            ),
        )
        run_id = cur.lastrowid

        # Запись выявленных аномалий и рекомендаций
        created_rec_ids = []
        for anom in ai_res["anomalies"]:
            cur.execute(
                """
                INSERT INTO detected_anomalies (
                    run_id, room_id, anomaly_type, severity, title, explanation_text, xai_factors, detected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    run_id,
                    room_id,
                    anom["anomaly_type"],
                    anom["severity"],
                    anom["title"],
                    anom["explanation_text"],
                    json.dumps(anom["xai_factors"], ensure_ascii=False),
                    measured_at,
                ),
            )
            anomaly_id = cur.lastrowid

            if anom["anomaly_type"] in ("energy", "climate", "window"):
                cur.execute(
                    """
                    INSERT INTO saving_recommendations (
                        anomaly_id, room_id, assigned_user_id, action_text,
                        expected_saving_kwh, expected_saving_kzt, status, created_at
                    ) VALUES (?, ?, 1, ?, ?, ?, 'new', ?);
                    """,
                    (
                        anomaly_id,
                        room_id,
                        ai_res["explanation"]["action"],
                        ai_res["saving_kwh_4h"],
                        ai_res["saving_potential_kzt_4h"],
                        measured_at,
                    ),
                )
                created_rec_ids.append(cur.lastrowid)

            ev_type = anom["anomaly_type"] if anom["anomaly_type"] in ("energy", "climate", "window", "offline") else "ok"
            cur.execute(
                """
                INSERT INTO system_events_log (room_id, user_id, run_id, event_type, event_text, created_at)
                VALUES (?, 1, ?, ?, ?, ?);
                """,
                (room_id, run_id, ev_type, f"{anom['title']}: {anom['explanation_text']}", measured_at),
            )

        ai_res["measurement_id"] = measurement_id
        ai_res["run_id"] = run_id
        ai_res["recommendation_ids"] = created_rec_ids
        return ai_res

    def process_telemetry_and_evaluate(self, validated_payload: Dict[str, Any], event_note: Optional[str] = None) -> Dict[str, Any]:
        """Обработка входящего пакета телеметрии с защитой от дублирования (deviceId + bootId + sequence)."""
        room_id = validated_payload["room_id"]
        boot_id = validated_payload.get("boot_id", "demo-session")
        seq = validated_payload.get("sequence")
        if seq is not None:
            key = (room_id, boot_id)
            last_seq = self._dedup_cache.get(key, -1)
            if seq <= last_seq:
                raise ValidationError(
                    f"Отброшен дублирующийся или устаревший пакет телеметрии (sequence={seq} <= {last_seq}).",
                    field="sequence",
                    code=409,
                )
            self._dedup_cache[key] = seq

        now_iso = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cur = conn.cursor()
            ctrl = cur.execute("SELECT controller_id FROM room_controllers WHERE room_id = ?;", (room_id,)).fetchone()
            if not ctrl:
                raise ValidationError(f"Контроллер для кабинета {room_id} не зарегистрирован.", field="room_id", code=404)
            setting = cur.execute("SELECT setting_id FROM system_settings_tariffs WHERE is_active = 1 ORDER BY setting_id DESC LIMIT 1;").fetchone()
            model = cur.execute("SELECT model_id FROM ml_models WHERE is_active = 1 ORDER BY model_id DESC LIMIT 1;").fetchone()

            res = self._record_evaluation_internal(
                cur=cur,
                room_id=room_id,
                controller_id=ctrl["controller_id"],
                setting_id=setting["setting_id"],
                model_id=model["model_id"],
                payload=validated_payload,
                measured_at=now_iso,
            )
            if event_note:
                cur.execute(
                    "INSERT INTO system_events_log (room_id, user_id, run_id, event_type, event_text, created_at) VALUES (?, 1, ?, 'ok', ?, ?);",
                    (room_id, res["run_id"], event_note, now_iso),
                )
            conn.commit()
            return res

    def get_all_rooms_state(self) -> Dict[str, Any]:
        """Получение актуального состояния всех 6 кабинетов, настроек, активных рекомендаций и журнала из БД."""
        with self._connect() as conn:
            cur = conn.cursor()
            s_row = cur.execute(
                "SELECT pc_watts, light_watts, min_temp_c, max_temp_c, tariff_kzt_kwh FROM system_settings_tariffs WHERE is_active = 1 ORDER BY setting_id DESC LIMIT 1;"
            ).fetchone()
            settings = {
                "pcWatts": s_row["pc_watts"],
                "lightWatts": s_row["light_watts"],
                "minTemp": s_row["min_temp_c"],
                "maxTemp": s_row["max_temp_c"],
                "tariffKzt": s_row["tariff_kzt_kwh"],
            }

            rooms_rows = cur.execute("SELECT * FROM rooms ORDER BY room_id;").fetchall()
            rooms_out = []
            for r in rooms_rows:
                rid = r["room_id"]
                tm = cur.execute(
                    "SELECT * FROM telemetry_measurements WHERE room_id = ? ORDER BY measurement_id DESC LIMIT 1;",
                    (rid,),
                ).fetchone()
                devs = cur.execute(
                    "SELECT is_power_on FROM workstations_devices WHERE room_id = ? AND device_type = 'PC' ORDER BY device_code;",
                    (rid,),
                ).fetchall()
                computers = [bool(d["is_power_on"]) for d in devs]
                run = cur.execute(
                    "SELECT * FROM ai_evaluation_runs WHERE room_id = ? ORDER BY run_id DESC LIMIT 1;",
                    (rid,),
                ).fetchone()

                pcs_on = sum(1 for c in computers if c)
                is_on = bool(tm["is_online"]) if tm else True
                light_on = bool(tm["light_on"]) if tm else False
                calc_p_kw = round((pcs_on * settings["pcWatts"] + (settings["lightWatts"] if light_on else 0)) / 1000.0, 2) if is_on else 0.0

                rooms_out.append({
                    "id": rid,
                    "floor": r["floor_num"],
                    "name": r["room_name"],
                    "type": r["room_type"],
                    "total": r["total_pcs"],
                    "pcs": pcs_on,
                    "computers": computers,
                    "light": light_on,
                    "door": bool(tm["door_open"]) if tm else False,
                    "windows": int(tm["open_windows"]) if tm else 0,
                    "temp": float(tm["temp_c"]) if tm else 22.0,
                    "occupied": bool(tm["is_occupied"]) if tm else False,
                    "online": is_on,
                    "power_kw": calc_p_kw,
                    "state_class": r["current_state"],
                    "baseline_forecast_kw": float(run["baseline_forecast_kw"]) if run else 0.0,
                    "confidence_score": float(run["confidence_score"]) if run else 0.92,
                    "saving_kwh_1h": float(run["saving_kwh_1h"]) if run else 0.0,
                    "saving_kwh_4h": float(run["saving_kwh_4h"]) if run else 0.0,
                    "saving_kzt_4h": float(run["saving_kzt_4h"]) if run else 0.0,
                    "updatedAt": int(datetime.fromisoformat(tm["measured_at"]).timestamp() * 1000) if tm else int(datetime.now(timezone.utc).timestamp() * 1000),
                })

            recs = cur.execute(
                """
                SELECT r.recommendation_id, r.room_id, r.action_text, r.expected_saving_kwh,
                       r.expected_saving_kzt, r.status, r.created_at, r.processed_at, r.operator_comment,
                       a.title AS anomaly_title, a.explanation_text, a.xai_factors, a.anomaly_type
                FROM saving_recommendations r
                JOIN detected_anomalies a ON r.anomaly_id = a.anomaly_id
                ORDER BY r.recommendation_id DESC LIMIT 30;
                """
            ).fetchall()
            recommendations_out = []
            for rec in recs:
                recommendations_out.append({
                    "recommendation_id": rec["recommendation_id"],
                    "room_id": rec["room_id"],
                    "anomaly_type": rec["anomaly_type"],
                    "title": rec["anomaly_title"],
                    "explanation_text": rec["explanation_text"],
                    "xai_factors": json.loads(rec["xai_factors"] or "[]"),
                    "action_text": rec["action_text"],
                    "expected_saving_kwh": rec["expected_saving_kwh"],
                    "expected_saving_kzt": rec["expected_saving_kzt"],
                    "status": rec["status"],
                    "created_at": rec["created_at"],
                    "processed_at": rec["processed_at"],
                    "operator_comment": rec["operator_comment"],
                })

            evs = cur.execute(
                "SELECT event_id, room_id, event_type, event_text, created_at FROM system_events_log ORDER BY event_id DESC LIMIT 200;"
            ).fetchall()
            events_out = [
                {
                    "id": e["event_id"],
                    "at": int(datetime.fromisoformat(e["created_at"]).timestamp() * 1000),
                    "room": e["room_id"] or "—",
                    "text": e["event_text"],
                    "type": "offline" if e["event_type"] == "offline" else ("warning" if e["event_type"] in ("energy", "climate", "window") else "info"),
                }
                for e in evs
            ]

            return {
                "rooms": rooms_out,
                "settings": settings,
                "recommendations": recommendations_out,
                "events": events_out,
                "model_info": {
                    "version_tag": self.ai_engine.version_tag,
                    "algorithm_type": self.ai_engine.algorithm_type,
                    "is_synthetic_data": True,
                    "metrics": self.ai_engine.metrics,
                },
            }

    def update_recommendation_status(self, recommendation_id: int, new_status: str, operator_comment: str = "", user_id: int = 1) -> Dict[str, Any]:
        """
        Обновление статуса рекомендации лаборантом (шаги BP-10, GW-4, BP-11):
        перевод из 'new' в 'accepted', 'completed' или 'rejected' с фиксацией processed_at.
        Если статус = 'completed', выполняется штатное выключение забытых ПК и света в симуляторе кабинета.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cur = conn.cursor()
            rec = cur.execute(
                "SELECT * FROM saving_recommendations WHERE recommendation_id = ?;",
                (recommendation_id,),
            ).fetchone()
            if not rec:
                raise ValidationError(f"Рекомендация #{recommendation_id} не найдена в БД.", field="recommendation_id", code=404)

            room_id = rec["room_id"]
            cur.execute(
                """
                UPDATE saving_recommendations
                SET status = ?, processed_at = ?, operator_comment = ?, assigned_user_id = ?
                WHERE recommendation_id = ?;
                """,
                (new_status, now_iso, operator_comment or None, user_id, recommendation_id),
            )

            ev_msg = f"Рекомендация #{recommendation_id} переведена в статус '{new_status}'" + (
                f" ({operator_comment})" if operator_comment else ""
            )
            cur.execute(
                "INSERT INTO system_events_log (room_id, user_id, event_type, event_text, created_at) VALUES (?, ?, 'ok', ?, ?);",
                (room_id, user_id, ev_msg, now_iso),
            )

            if new_status == "completed":
                # При подтверждении выполнения лаборантом выключаются оставленные ПК и свет, закрываются окна
                tm = cur.execute(
                    "SELECT * FROM telemetry_measurements WHERE room_id = ? ORDER BY measurement_id DESC LIMIT 1;",
                    (room_id,),
                ).fetchone()
                ctrl = cur.execute("SELECT controller_id FROM room_controllers WHERE room_id = ?;", (room_id,)).fetchone()
                setting = cur.execute("SELECT setting_id FROM system_settings_tariffs WHERE is_active = 1 ORDER BY setting_id DESC LIMIT 1;").fetchone()
                model = cur.execute("SELECT model_id FROM ml_models WHERE is_active = 1 ORDER BY model_id DESC LIMIT 1;").fetchone()
                if tm and ctrl:
                    self._record_evaluation_internal(
                        cur=cur,
                        room_id=room_id,
                        controller_id=ctrl["controller_id"],
                        setting_id=setting["setting_id"],
                        model_id=model["model_id"],
                        payload={
                            "room_id": room_id,
                            "online": bool(tm["is_online"]),
                            "occupied": bool(tm["is_occupied"]),
                            "computers_on": 0,
                            "total_pcs": int(tm["total_pcs"]),
                            "light_on": False,
                            "windows_open": 0,
                            "door_open": False,
                            "temp_c": max(19.5, float(tm["temp_c"])),
                        },
                        measured_at=now_iso,
                    )

            conn.commit()
            updated = cur.execute(
                "SELECT * FROM saving_recommendations WHERE recommendation_id = ?;",
                (recommendation_id,),
            ).fetchone()
            return dict(updated)

    def save_telemetry_snapshot(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Прямая запись среза телеметрии и запуск оценки ИИ (для консольного меню, тестов и скриптов демонстрации)."""
        val = validate_telemetry_payload(payload)
        note = sanitize_text(payload.get("event_note", ""), max_len=200)
        return self.process_telemetry_and_evaluate(val, event_note=note or None)

    def update_settings(self, settings_payload: Dict[str, Any], user_id: int = 2) -> Dict[str, Any]:
        """Сохранение новой версии уставок мощности, порогов температуры и тарифа в system_settings_tariffs с поддержкой частичных обновлений."""
        with self._connect() as conn:
            cur = conn.cursor()
            curr = cur.execute(
                "SELECT pc_watts, light_watts, min_temp_c, max_temp_c, tariff_kzt_kwh FROM system_settings_tariffs WHERE is_active = 1 ORDER BY setting_id DESC LIMIT 1;"
            ).fetchone()
            current_dict = dict(curr) if curr else dict(DEFAULT_SETTINGS)
            merged = dict(current_dict)

            # Поддержка snake_case и camelCase
            if "pc_watts" in settings_payload or "pcWatts" in settings_payload:
                merged["pc_watts"] = settings_payload.get("pc_watts", settings_payload.get("pcWatts"))
            if "light_watts" in settings_payload or "lightWatts" in settings_payload:
                merged["light_watts"] = settings_payload.get("light_watts", settings_payload.get("lightWatts"))
            if "min_temp_c" in settings_payload or "minTemp" in settings_payload:
                merged["min_temp_c"] = settings_payload.get("min_temp_c", settings_payload.get("minTemp"))
            if "max_temp_c" in settings_payload or "maxTemp" in settings_payload:
                merged["max_temp_c"] = settings_payload.get("max_temp_c", settings_payload.get("maxTemp"))
            if "tariff_kzt_kwh" in settings_payload or "tariffKzt" in settings_payload:
                merged["tariff_kzt_kwh"] = settings_payload.get("tariff_kzt_kwh", settings_payload.get("tariffKzt"))

            validated_settings = validate_settings_payload(merged)
            now_iso = datetime.now(timezone.utc).isoformat()
            cur.execute("UPDATE system_settings_tariffs SET is_active = 0 WHERE is_active = 1;")
            cur.execute(
                """
                INSERT INTO system_settings_tariffs (pc_watts, light_watts, min_temp_c, max_temp_c, tariff_kzt_kwh, valid_from, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1);
                """,
                (
                    validated_settings["pc_watts"],
                    validated_settings["light_watts"],
                    validated_settings["min_temp_c"],
                    validated_settings["max_temp_c"],
                    validated_settings["tariff_kzt_kwh"],
                    now_iso,
                ),
            )
            cur.execute(
                "INSERT INTO system_events_log (room_id, user_id, event_type, event_text, created_at) VALUES (NULL, ?, 'settings', ?, ?);",
                (
                    user_id,
                    f"Обновлены уставки: ПК={validated_settings['pc_watts']} Вт, Свет={validated_settings['light_watts']} Вт, Тариф={validated_settings['tariff_kzt_kwh']} тг/кВт·ч",
                    now_iso,
                ),
            )
            conn.commit()
            return validated_settings

    def get_analytics_series(self, room_id: str = "all", horizon: str = "day_24h") -> Dict[str, Any]:
        """Выборка прогнозного и базового профилей потребления для выбранного кабинета или корпуса в целом."""
        if horizon not in ("day_24h", "week_7d"):
            raise ValidationError("Параметр horizon должен принимать значение 'day_24h' или 'week_7d'.", field="horizon", code=422)

        with self._connect() as conn:
            cur = conn.cursor()
            if room_id == "all":
                rows = cur.execute(
                    """
                    SELECT target_timestamp,
                           ROUND(SUM(predicted_kw), 2) AS predicted_kw,
                           ROUND(SUM(baseline_no_ctrl_kw), 2) AS baseline_kw
                    FROM energy_forecasts
                    WHERE horizon_type = ?
                    GROUP BY target_timestamp
                    ORDER BY target_timestamp;
                    """,
                    (horizon,),
                ).fetchall()
            else:
                if room_id not in ROOMS_CATALOG:
                    raise ValidationError(f"Кабинет '{room_id}' не существует.", field="room_id", code=404)
                rows = cur.execute(
                    """
                    SELECT target_timestamp, predicted_kw, baseline_no_ctrl_kw AS baseline_kw
                    FROM energy_forecasts
                    WHERE room_id = ? AND horizon_type = ?
                    ORDER BY target_timestamp;
                    """,
                    (room_id, horizon),
                ).fetchall()

            return {
                "room_id": room_id,
                "horizon": horizon,
                "unit": "кВт" if horizon == "day_24h" else "кВт·ч",
                "is_synthetic": True,
                "points": [dict(r) for r in rows],
            }

    def get_database_tables_summary(self) -> List[Dict[str, Any]]:
        """Получение списка всех 14 таблиц базы данных со счетчиком строк и схемой столбцов."""
        summary = []
        with self._connect() as conn:
            cur = conn.cursor()
            for tbl in ALL_14_TABLES:
                cnt = cur.execute(f"SELECT COUNT(*) AS c FROM {tbl};").fetchone()["c"]
                cols_info = cur.execute(f"PRAGMA table_info({tbl});").fetchall()
                cols = [
                    {
                        "cid": c["cid"],
                        "name": c["name"],
                        "type": c["type"],
                        "notnull": bool(c["notnull"]),
                        "pk": bool(c["pk"]),
                    }
                    for c in cols_info
                ]
                summary.append({
                    "name": tbl,
                    "count": cnt,
                    "columns": cols,
                })
        return summary

    def get_table_data(self, table_name: str, limit: int = 50) -> Dict[str, Any]:
        """Получение среза строк выбранной таблицы (с защитой от SQL-инъекций)."""
        clean_tbl = table_name.strip().lower()
        if clean_tbl not in ALL_14_TABLES:
            raise ValidationError(f"Таблица '{table_name}' не найдена в схеме из 14 таблиц ИИС.", field="table", code=404)

        limit_val = max(1, min(int(limit), 200))
        with self._connect() as conn:
            cur = conn.cursor()
            total_cnt = cur.execute(f"SELECT COUNT(*) AS c FROM {clean_tbl};").fetchone()["c"]
            cols_info = cur.execute(f"PRAGMA table_info({clean_tbl});").fetchall()
            cols = [c["name"] for c in cols_info]
            rows = cur.execute(f"SELECT * FROM {clean_tbl} ORDER BY 1 DESC LIMIT ?;", (limit_val,)).fetchall()
            rows_data = [dict(r) for r in rows]
            return {
                "table": clean_tbl,
                "columns": cols,
                "rows": rows_data,
                "total_count": total_cnt,
                "limit": limit_val,
            }

    def execute_sql_query(self, query: str) -> Dict[str, Any]:
        """
        Выполнение проверочного SQL-запроса через веб-консоль базы данных.
        Разрешены только одиночные запросы чтения (SELECT и PRAGMA table_info).
        """
        safe_q = validate_readonly_sql_query(query)

        with self._connect() as conn:
            cur = conn.cursor()
            try:
                cur.execute(safe_q)
                rows = cur.fetchmany(100)
                cols = list(rows[0].keys()) if rows else []
                data = [dict(r) for r in rows]
                return {
                    "status": "ok",
                    "is_select": True,
                    "columns": cols,
                    "rows": data,
                    "count": len(data),
                    "message": f"Найдено записей: {len(data)}",
                }
            except sqlite3.Error as exc:
                raise ValidationError(f"Ошибка выполнения SQL-запроса: {exc}", field="query", code=422)

    def execute_scenario(self, scenario_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Выполнение одного из 8 демонстрационных сценариев прямо из браузера."""
        p = params or {}
        sc = scenario_name.strip().lower()

        if sc == "pcs_204_on":
            pcs = [True] * 12
            res = self.save_telemetry_snapshot({
                "room_id": "204", "online": True, "occupied": False,
                "computers_on": 12, "total_pcs": 12, "computers": pcs,
                "light_on": True, "windows_open": 0, "door_open": True,
                "temp_c": 23.5, "event_note": "Сценарий: в пустом каб. 204 включены 12 ПК и свет"
            })
            return {"status": "ok", "scenario": sc, "message": "Каб. 204: Включено 12 ПК и свет (перерасход S3_EXCESS).", "eval": res}

        elif sc == "pcs_204_off":
            pcs = [False] * 12
            res = self.save_telemetry_snapshot({
                "room_id": "204", "online": True, "occupied": False,
                "computers_on": 0, "total_pcs": 12, "computers": pcs,
                "light_on": False, "windows_open": 0, "door_open": False,
                "temp_c": 21.8, "event_note": "Сценарий: в каб. 204 лаборант отключил технику и свет"
            })
            return {"status": "ok", "scenario": sc, "message": "Каб. 204: Техника выключена, статус S2_IDLE.", "eval": res}

        elif sc == "window_302_open":
            pcs = [False] * 8
            res = self.save_telemetry_snapshot({
                "room_id": "302", "online": True, "occupied": False,
                "computers_on": 0, "total_pcs": 8, "computers": pcs,
                "light_on": False, "windows_open": 1, "door_open": False,
                "temp_c": 15.5, "event_note": "Сценарий: в каб. 302 открыто окно, выхолаживание до 15.5 °C"
            })
            return {"status": "ok", "scenario": sc, "message": "Каб. 302: Окно открыто, температура 15.5 °C (нарушение микроклимата).", "eval": res}

        elif sc == "window_302_close":
            pcs = [False] * 8
            res = self.save_telemetry_snapshot({
                "room_id": "302", "online": True, "occupied": False,
                "computers_on": 0, "total_pcs": 8, "computers": pcs,
                "light_on": False, "windows_open": 0, "door_open": False,
                "temp_c": 21.5, "event_note": "Сценарий: в каб. 302 окно закрыто, температура в норме"
            })
            return {"status": "ok", "scenario": sc, "message": "Каб. 302: Окно закрыто, температура 21.5 °C (норма).", "eval": res}

        elif sc == "controller_305_online":
            pcs = [False] * 12
            res = self.save_telemetry_snapshot({
                "room_id": "305", "online": True, "occupied": False,
                "computers_on": 0, "total_pcs": 12, "computers": pcs,
                "light_on": False, "windows_open": 0, "door_open": False,
                "temp_c": 21.2, "event_note": "Сценарий: связь с контроллером 305 восстановлена"
            })
            return {"status": "ok", "scenario": sc, "message": "Каб. 305: Контроллер на связи (ONLINE).", "eval": res}

        elif sc == "controller_305_offline":
            pcs = [False] * 12
            res = self.save_telemetry_snapshot({
                "room_id": "305", "online": False, "occupied": False,
                "computers_on": 0, "total_pcs": 12, "computers": pcs,
                "light_on": False, "windows_open": 0, "door_open": False,
                "temp_c": 21.2, "event_note": "Сценарий: обрыв связи с контроллером 305"
            })
            return {"status": "ok", "scenario": sc, "message": "Каб. 305: Имитация потери связи (S0_OFFLINE).", "eval": res}

        elif sc == "set_tariff":
            t_val = float(p.get("tariff", p.get("tariffKzt", 32.5)))
            saved = self.update_settings({"tariffKzt": t_val})
            return {"status": "ok", "scenario": sc, "message": f"Тариф успешно изменён на {t_val} тг/кВт·ч.", "settings": saved}

        elif sc == "seed_reset":
            self.init_database(force_reset=True)
            self._dedup_cache.clear()
            return {"status": "ok", "scenario": sc, "message": "База данных сброшена к исходному демонстрационному состоянию."}

        else:
            raise ValidationError(f"Неизвестный сценарий '{scenario_name}'.", field="scenario", code=422)

    def update_table_row(
        self,
        table_name: str,
        pk_column: str,
        pk_value: Any,
        values: Dict[str, Any],
        user_id: int = 2
    ) -> Dict[str, Any]:
        """Обновление записи в таблице БД с проверкой физических границ VALIDATION_BOUNDS и пересчётом состояния."""
        clean_tbl = table_name.strip().lower()
        if clean_tbl not in ALL_14_TABLES:
            raise ValidationError(f"Таблица '{table_name}' не найдена в схеме ИИС.", field="table", code=404)

        if not values or not isinstance(values, dict):
            raise ValidationError("Набор обновляемых полей не может быть пустым.", field="values", code=422)

        with self._connect() as conn:
            cur = conn.cursor()
            cols_info = cur.execute(f"PRAGMA table_info({clean_tbl});").fetchall()
            valid_cols = {c["name"]: c["type"] for c in cols_info}

            if pk_column not in valid_cols:
                raise ValidationError(f"Первичный ключ '{pk_column}' не найден в таблице {clean_tbl}.", field="pk_column", code=422)

            existing_row = cur.execute(f"SELECT * FROM {clean_tbl} WHERE {pk_column} = ?;", (pk_value,)).fetchone()
            if not existing_row:
                raise ValidationError(f"Запись с ключом {pk_column}={pk_value} не найдена в таблице {clean_tbl}.", field=pk_column, code=404)

            filtered_input = {k: v for k, v in values.items() if k in valid_cols and k != pk_column}
            if not filtered_input:
                raise ValidationError("Нет допустимых полей для обновления.", field="values", code=422)

            # Валидация через VALIDATION_BOUNDS и доменные инварианты validators.py
            validated_vals = validate_table_row_update(clean_tbl, filtered_input, dict(existing_row))

            set_clauses = []
            param_vals = []
            for col, val in validated_vals.items():
                c_type = valid_cols[col].upper()
                typed_val = val
                if val is not None and val != "":
                    if "INT" in c_type and not isinstance(val, int):
                        try:
                            typed_val = int(val)
                        except (ValueError, TypeError):
                            raise ValidationError(f"Поле '{col}' должно быть целым числом.", field=col, code=422)
                    elif ("REAL" in c_type or "FLOAT" in c_type or "DOUBLE" in c_type) and not isinstance(val, (int, float)):
                        try:
                            typed_val = float(val)
                        except (ValueError, TypeError):
                            raise ValidationError(f"Поле '{col}' должно быть числом.", field=col, code=422)
                else:
                    typed_val = None

                set_clauses.append(f"{col} = ?")
                param_vals.append(typed_val)

            sql = f"UPDATE {clean_tbl} SET {', '.join(set_clauses)} WHERE {pk_column} = ?;"
            param_vals.append(pk_value)
            try:
                cur.execute(sql, param_vals)
            except sqlite3.IntegrityError as exc:
                raise ValidationError(f"Нарушение ограничений целостности БД: {exc}", field=pk_column, code=422)

            now_iso = datetime.now(timezone.utc).isoformat()
            cur.execute(
                "INSERT INTO system_events_log (room_id, user_id, event_type, event_text, created_at) VALUES (NULL, ?, 'settings', ?, ?);",
                (user_id, f"Изменена запись в {clean_tbl} ({pk_column}={pk_value}) через веб-интерфейс", now_iso),
            )

            # Если менялась телеметрия, пересчитываем расчётную мощность и синхронизируем ПК/статус кабинета
            if clean_tbl == "telemetry_measurements":
                row = cur.execute(f"SELECT * FROM telemetry_measurements WHERE {pk_column} = ?;", (pk_value,)).fetchone()
                if row:
                    rid = row["room_id"]
                    pcs = int(row["active_pcs"] or 0)
                    s_row = cur.execute("SELECT pc_watts, light_watts FROM system_settings_tariffs WHERE is_active = 1 LIMIT 1;").fetchone()
                    pc_w = s_row["pc_watts"] if s_row else 150
                    light_w = s_row["light_watts"] if s_row else 120
                    kw = round((pcs * pc_w + (light_w if row["light_on"] else 0)) / 1000.0, 2) if row["is_online"] else 0.0
                    cur.execute("UPDATE telemetry_measurements SET calc_power_kw = ? WHERE measurement_id = ?;", (kw, row["measurement_id"]))
                    if "active_pcs" in validated_vals:
                        cur.execute(
                            """
                            UPDATE workstations_devices
                            SET is_power_on = CASE WHEN CAST(SUBSTR(device_code, 4) AS INTEGER) <= ? THEN 1 ELSE 0 END,
                                updated_at = ?
                            WHERE room_id = ? AND device_type = 'PC';
                            """,
                            (pcs, now_iso, rid),
                        )

            conn.commit()

            updated = cur.execute(f"SELECT * FROM {clean_tbl} WHERE {pk_column} = ?;", (pk_value,)).fetchone()
            return {
                "status": "ok",
                "table": clean_tbl,
                "pk_column": pk_column,
                "pk_value": pk_value,
                "message": f"Запись #{pk_value} в таблице {clean_tbl} успешно обновлена в SQLite!",
                "row": dict(updated) if updated else {}
            }
