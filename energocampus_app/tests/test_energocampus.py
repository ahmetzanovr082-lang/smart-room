# -*- coding: utf-8 -*-
"""
Автоматизированный тестовый набор ИИС «ЭнергоКампус» (Модуль 3).
Включает 16 верифицируемых тест-кейсов (TC-01 .. TC-16):
- модульное, интеграционное и системное тестирование API, БД (14 таблиц) и ИИ-модуля;
- позитивные, негативные и граничные сценарии (NFR-2, NFR-5);
- проверка безопасности (экранирование XSS, параметризация против SQLi, ролевой доступ RBAC);
- проверка метрик качества регрессии (MAE, RMSE, MAPE, R2) и контура адаптации Update(Model_t, Data_new).
"""
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.server import EnergoCampusApplication
from backend.validators import sanitize_text


class EnergoCampusTestSuite(unittest.TestCase):
    """Полный набор из 16 тестов для верификации прототипа ИИС «ЭнергоКампус»."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_db_path = os.path.join(cls.temp_dir.name, "test_energocampus.sqlite3")
        cls.app = EnergoCampusApplication(db_path=cls.test_db_path)
        cls.results_log = []

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def _record(self, tc_id: str, category: str, title: str, input_desc: str, expected: str, actual: str, passed: bool, duration_ms: float):
        self.__class__.results_log.append({
            "tc_id": tc_id,
            "category": category,
            "title": title,
            "input": input_desc,
            "expected": expected,
            "actual": actual,
            "status": "PASSED" if passed else "FAILED",
            "duration_ms": round(duration_ms, 2),
        })

    def test_01_db_schema_14_tables_and_seed(self):
        """TC-01 (БД и схема): Проверка автоматического создания всех 14 таблиц в 3НФ и начального заполнения (6 кабинетов, 72 ПК)."""
        t0 = time.perf_counter()
        conn = sqlite3.connect(self.test_db_path)
        try:
            cur = conn.cursor()
            tables = [
                r[0] for r in cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
                ).fetchall()
            ]
            rooms_cnt = cur.execute("SELECT COUNT(*) FROM rooms;").fetchone()[0]
            pcs_cnt = cur.execute("SELECT COUNT(*) FROM workstations_devices WHERE device_type='PC';").fetchone()[0]
            roles_cnt = cur.execute("SELECT COUNT(*) FROM roles;").fetchone()[0]
        finally:
            conn.close()

        expected_tables = {
            "roles", "users", "rooms", "room_controllers", "workstations_devices",
            "schedule_slots", "system_settings_tariffs", "telemetry_measurements",
            "ml_models", "ai_evaluation_runs", "energy_forecasts",
            "detected_anomalies", "saving_recommendations", "system_events_log"
        }
        self.assertEqual(set(tables), expected_tables)
        self.assertEqual(rooms_cnt, 6)
        self.assertEqual(pcs_cnt, 72)
        self.assertEqual(roles_cnt, 4)
        dt = (time.perf_counter() - t0) * 1000
        self._record(
            "TC-01", "База данных (3НФ)", "Инициализация 14 таблиц схемы и проверка 6 кабинетов (72 ПК)",
            "SQLite/PostgreSQL DDL + начальный seed",
            "Создано 14 таблиц, 6 кабинетов, 72 ПК, 4 роли",
            f"Таблиц: {len(tables)}, кабинетов: {rooms_cnt}, ПК: {pcs_cnt}, ролей: {roles_cnt}",
            True, dt
        )

    def test_02_positive_excess_detection_and_xai_room_204(self):
        """TC-02 (Позитивный, ИИ + XAI): Оценка свободного кабинета № 204 с 4 включёнными ПК и светом."""
        t0 = time.perf_counter()
        code, resp = self.app.dispatch("POST", "/api/v1/ai/evaluate", body={
            "room_id": "204", "online": True, "occupied": False,
            "computers_on": 4, "total_pcs": 12, "light_on": True,
            "windows_open": 0, "door_open": True, "temp_c": 23.1
        })
        ev = resp["evaluation"]
        self.assertEqual(code, 200)
        self.assertEqual(ev["state_class"], "S3_EXCESS")
        self.assertAlmostEqual(ev["current_power_kw"], 0.72, places=2)
        self.assertAlmostEqual(ev["saving_potential_kwh_1h"], 0.72, places=2)
        self.assertAlmostEqual(ev["saving_kwh_4h"], 2.88, places=2)
        self.assertAlmostEqual(ev["saving_potential_kzt_4h"], 93.60, places=2)
        self.assertTrue(len(ev["explanation"]["xai_factors"]) >= 2)
        dt = (time.perf_counter() - t0) * 1000
        self._record(
            "TC-02", "Позитивный (ИИ + XAI)", "Расчёт нагрузки, класса S3_EXCESS и потенциала экономии для каб. 204",
            "room_id='204', occupied=False, computers_on=4, light_on=True",
            "HTTP 200, S3_EXCESS, P=0.72 кВт, ΔW(4ч)=2.88 кВт·ч, ΔC(4ч)=93.60 тг, 2 фактора XAI",
            f"HTTP {code}, {ev['state_class']}, P={ev['current_power_kw']} кВт, ΔW(4ч)={ev['saving_kwh_4h']} кВт·ч, ΔC={ev['saving_potential_kzt_4h']} тг",
            True, dt
        )

    def test_03_positive_occupied_schedule_room_201(self):
        """TC-03 (Позитивный, Штатное занятие): Оценка занятого кабинета № 201 во время учебной пары."""
        t0 = time.perf_counter()
        code, resp = self.app.dispatch("POST", "/api/v1/ai/evaluate", body={
            "room_id": "201", "online": True, "occupied": True,
            "computers_on": 7, "total_pcs": 12, "light_on": True,
            "windows_open": 0, "door_open": False, "temp_c": 22.4
        })
        ev = resp["evaluation"]
        self.assertEqual(code, 200)
        self.assertEqual(ev["state_class"], "S1_OCCUPIED")
        self.assertAlmostEqual(ev["current_power_kw"], 1.17, places=2)
        self.assertEqual(len(ev["anomalies"]), 0)
        dt = (time.perf_counter() - t0) * 1000
        self._record(
            "TC-03", "Позитивный (ИИ)", "Оценка штатного учебного занятия в каб. 201 (I_зан = 1)",
            "room_id='201', occupied=True, computers_on=7, light_on=True, temp_c=22.4",
            "HTTP 200, класс S1_OCCUPIED, аномалий 0",
            f"HTTP {code}, класс {ev['state_class']}, P={ev['current_power_kw']} кВт, аномалий: {len(ev['anomalies'])}",
            True, dt
        )

    def test_04_offline_controller_protection_nfr2_room_305(self):
        """TC-04 (Граничный / Сбой связи NFR-2): Блокировка ложной оценки экономии при потере связи с контроллером (S0_OFFLINE)."""
        t0 = time.perf_counter()
        code, resp = self.app.dispatch("POST", "/api/v1/ai/evaluate", body={
            "room_id": "305", "online": False, "occupied": False,
            "computers_on": 8, "total_pcs": 12, "light_on": True,
            "windows_open": 0, "door_open": False, "temp_c": 21.2
        })
        ev = resp["evaluation"]
        self.assertEqual(code, 200)
        self.assertEqual(ev["state_class"], "S0_OFFLINE")
        self.assertIsNone(ev["current_power_kw"])
        self.assertEqual(ev["saving_potential_kwh_1h"], 0.0)
        self.assertEqual(ev["saving_potential_kzt_4h"], 0.0)
        dt = (time.perf_counter() - t0) * 1000
        self._record(
            "TC-04", "Надёжность (NFR-2)", "Защита от ложной экономии при обрыве связи с контроллером (каб. 305)",
            "room_id='305', online=False, computers_on=8",
            "HTTP 200, S0_OFFLINE, current_power_kw=None, saving=0.0",
            f"HTTP {code}, {ev['state_class']}, power={ev['current_power_kw']}, saving={ev['saving_potential_kwh_1h']}",
            True, dt
        )

    def test_05_climate_and_open_window_detection_room_302(self):
        """TC-05 (Позитивный / Микроклимат): Детекция переохлаждения (17.8 °C < 18.0 °C) и открытого окна в каб. 302."""
        t0 = time.perf_counter()
        code, resp = self.app.dispatch("POST", "/api/v1/ai/evaluate", body={
            "room_id": "302", "online": True, "occupied": False,
            "computers_on": 2, "total_pcs": 8, "light_on": False,
            "windows_open": 1, "door_open": False, "temp_c": 17.8
        })
        ev = resp["evaluation"]
        anom_types = [a["anomaly_type"] for a in ev["anomalies"]]
        self.assertEqual(code, 200)
        self.assertIn("energy", anom_types)
        self.assertIn("climate", anom_types)
        dt = (time.perf_counter() - t0) * 1000
        self._record(
            "TC-05", "Граничный (Климат)", "Одновременная детекция энергетической и климатической аномалии (17.8 °C)",
            "room_id='302', occupied=False, computers_on=2, temp_c=17.8, windows_open=1",
            "HTTP 200, типы аномалий: ['energy', 'climate']",
            f"HTTP {code}, типы аномалий: {anom_types}",
            True, dt
        )

    def test_06_negative_invalid_temperature_bounds(self):
        """TC-06 (Негативный, Валидация): Отклонение нефизического значения температуры (temp_c = 999.0 °C)."""
        t0 = time.perf_counter()
        code, resp = self.app.dispatch("POST", "/api/v1/telemetry", body={
            "room_id": "204", "online": True, "occupied": False,
            "computers_on": 2, "total_pcs": 12, "temp_c": 999.0
        })
        self.assertEqual(code, 422)
        self.assertEqual(resp["field"], "temp_c")
        dt = (time.perf_counter() - t0) * 1000
        self._record(
            "TC-06", "Негативный (Валидация)", "Отклонение пакета телеметрии с температурой за пределами [-10; +55] °C",
            "temp_c = 999.0",
            "HTTP 422 Unprocessable Entity (field='temp_c')",
            f"HTTP {code}, field='{resp.get('field')}', msg='{resp.get('message')}'",
            True, dt
        )

    def test_07_negative_active_pcs_exceed_total_capacity(self):
        """TC-07 (Негативный / Граничный): Отклонение пакета, где число включённых ПК превышает ёмкость кабинета (15 > 12)."""
        t0 = time.perf_counter()
        code, resp = self.app.dispatch("POST", "/api/v1/telemetry", body={
            "room_id": "204", "online": True, "occupied": False,
            "computers_on": 15, "total_pcs": 12, "temp_c": 22.0
        })
        self.assertEqual(code, 422)
        self.assertEqual(resp["field"], "computers_on")
        dt = (time.perf_counter() - t0) * 1000
        self._record(
            "TC-07", "Граничный (Валидация)", "Проверка инварианта 0 <= computers_on <= total_pcs",
            "computers_on = 15 при total_pcs = 12",
            "HTTP 422 Unprocessable Entity (field='computers_on')",
            f"HTTP {code}, field='{resp.get('field')}'",
            True, dt
        )

    def test_08_negative_settings_min_temp_greater_than_max_temp(self):
        """TC-08 (Негативный, Настройки): Запрет сохранения порога minTemp >= maxTemp (27.0 >= 22.0)."""
        t0 = time.perf_counter()
        code, resp = self.app.dispatch(
            "POST", "/api/v1/settings",
            body={"pcWatts": 150, "lightWatts": 120, "minTemp": 27.0, "maxTemp": 22.0, "tariffKzt": 32.5},
            headers={"Authorization": "Bearer demo-role-energomanager"}
        )
        self.assertEqual(code, 422)
        self.assertEqual(resp["field"], "min_temp_c")
        dt = (time.perf_counter() - t0) * 1000
        self._record(
            "TC-08", "Негативный (Настройки)", "Проверка ограничения min_temp_c < max_temp_c при обновлении уставок",
            "minTemp=27.0, maxTemp=22.0",
            "HTTP 422 Unprocessable Entity (field='min_temp_c')",
            f"HTTP {code}, field='{resp.get('field')}'",
            True, dt
        )

    def test_09_deduplication_sequence_replay_protection(self):
        """TC-09 (Надёжность / Дедупликация): Отбрасывание дублирующегося пакета телеметрии по (room_id, boot_id, sequence)."""
        t0 = time.perf_counter()
        payload = {
            "room_id": "202", "online": True, "occupied": False,
            "computers_on": 1, "total_pcs": 12, "light_on": False,
            "temp_c": 21.8, "boot_id": "esp32-boot-01", "sequence": 105
        }
        code1, _ = self.app.dispatch("POST", "/api/v1/telemetry", body=payload)
        code2, resp2 = self.app.dispatch("POST", "/api/v1/telemetry", body=payload)
        self.assertEqual(code1, 200)
        self.assertEqual(code2, 409)
        dt = (time.perf_counter() - t0) * 1000
        self._record(
            "TC-09", "Дедупликация пакетов", "Защита от повторной записи пакета с тем же sequence=105",
            "Два пакета подряд с boot_id='esp32-boot-01', sequence=105",
            "1-й запрос: HTTP 200; 2-й запрос (дубликат): HTTP 409 Conflict",
            f"1-й: HTTP {code1}; 2-й: HTTP {code2} ({resp2.get('message')})",
            True, dt
        )

    def test_10_recommendation_lifecycle_and_db_check_constraint(self):
        """TC-10 (Бизнес-процесс BP-10/BP-11 + БД): Перевод рекомендации из 'new' в 'accepted' и 'completed' с проверкой processed_at."""
        t0 = time.perf_counter()
        _, st_resp = self.app.dispatch("GET", "/api/v1/state")
        recs = st_resp["data"]["recommendations"]
        target_rec = next(r for r in recs if r["room_id"] == "204")
        rec_id = target_rec["recommendation_id"]

        code_acc, resp_acc = self.app.dispatch("POST", "/api/v1/recommendations/action", body={
            "recommendation_id": rec_id,
            "status": "accepted",
            "operator_comment": "Лаборант направлен в кабинет 204"
        })
        self.assertEqual(code_acc, 200)
        self.assertEqual(resp_acc["recommendation"]["status"], "accepted")
        self.assertIsNotNone(resp_acc["recommendation"]["processed_at"])

        code_comp, resp_comp = self.app.dispatch("POST", "/api/v1/recommendations/action", body={
            "recommendation_id": rec_id,
            "status": "completed",
            "operator_comment": "4 ПК и свет штатно выключены лаборантом"
        })
        self.assertEqual(code_comp, 200)
        self.assertEqual(resp_comp["recommendation"]["status"], "completed")
        room_204 = next(r for r in resp_comp["state"]["rooms"] if r["id"] == "204")
        self.assertEqual(room_204["pcs"], 0)
        self.assertFalse(room_204["light"])
        dt = (time.perf_counter() - t0) * 1000
        self._record(
            "TC-10", "Жизненный цикл рекомендации", "Переход статуса 'new' -> 'accepted' -> 'completed' и отключение нагрузки",
            f"recommendation_id={rec_id} (каб. 204)",
            "HTTP 200, processed_at заполнен, в каб. 204 выключены 4 ПК и свет (pcs=0)",
            f"HTTP {code_comp}, status={resp_comp['recommendation']['status']}, pcs={room_204['pcs']}",
            True, dt
        )

    def test_11_empty_search_filter_result(self):
        """TC-11 (Пустой результат поиска): Запрос списка кабинетов по несуществующему поисковому запросу."""
        t0 = time.perf_counter()
        code, resp = self.app.dispatch("GET", "/api/v1/rooms", query_params={"query": "999-несуществующий"})
        self.assertEqual(code, 200)
        self.assertEqual(resp["count"], 0)
        self.assertEqual(resp["rooms"], [])
        dt = (time.perf_counter() - t0) * 1000
        self._record(
            "TC-11", "Граничный (Поиск)", "Корректная обработка пустого результата поиска кабинетов",
            "GET /api/v1/rooms?query=999-несуществующий",
            "HTTP 200, count=0, пустой массив rooms=[] без сбоя",
            f"HTTP {code}, count={resp['count']}, rooms={resp['rooms']}",
            True, dt
        )

    def test_12_security_xss_sanitization(self):
        """TC-12 (Информационная безопасность — XSS): Экранирование вредоносного скрипта в комментарии оператора."""
        t0 = time.perf_counter()
        malicious = "<script>alert('XSS')</script><img src=x onerror=alert(1)>"
        cleaned = sanitize_text(malicious)
        self.assertNotIn("<script>", cleaned)
        self.assertIn("&lt;script&gt;", cleaned)
        dt = (time.perf_counter() - t0) * 1000
        self._record(
            "TC-12", "Безопасность (XSS)", "Санитизация HTML/JS-тегов во входных текстовых полях",
            malicious,
            "Спецсимволы < > ' \" экранированы в HTML-сущности",
            cleaned,
            True, dt
        )

    def test_13_security_sql_injection_protection(self):
        """TC-13 (Информационная безопасность — SQLi): Попытка внедрения SQL-инъекции через параметр room_id и поиск."""
        t0 = time.perf_counter()
        sqli_payload = "204'; DROP TABLE rooms; --"
        code_post, _ = self.app.dispatch("POST", "/api/v1/telemetry", body={
            "room_id": sqli_payload, "online": True, "occupied": False, "computers_on": 1, "total_pcs": 12, "temp_c": 22.0
        })
        code_get, resp_get = self.app.dispatch("GET", "/api/v1/rooms", query_params={"query": sqli_payload})
        self.assertEqual(code_post, 422)
        self.assertEqual(code_get, 200)
        # Проверяем, что таблица rooms осталась целой (6 записей)
        _, st = self.app.dispatch("GET", "/api/v1/state")
        self.assertEqual(len(st["data"]["rooms"]), 6)
        dt = (time.perf_counter() - t0) * 1000
        self._record(
            "TC-13", "Безопасность (SQLi)", "Блокировка SQL-инъекции валидатором и параметризованными запросами",
            sqli_payload,
            "HTTP 422 при записи, таблица rooms сохранена (6 кабинетов)",
            f"POST HTTP {code_post}, GET HTTP {code_get}, кабинетов в БД: {len(st['data']['rooms'])}",
            True, dt
        )

    def test_14_security_rbac_role_access_control(self):
        """TC-14 (Информационная безопасность — RBAC): Запрет изменения тарифа и уставок для роли Лаборанта (403 Forbidden)."""
        t0 = time.perf_counter()
        code, resp = self.app.dispatch(
            "POST", "/api/v1/settings",
            body={"pcWatts": 160, "lightWatts": 120, "minTemp": 18.0, "maxTemp": 26.0, "tariffKzt": 35.0},
            headers={"Authorization": "Bearer demo-role-laborant"}
        )
        self.assertEqual(code, 403)
        dt = (time.perf_counter() - t0) * 1000
        self._record(
            "TC-14", "Безопасность (RBAC)", "Проверка ролевого разграничения прав доступа (Лаборант vs Энергетик)",
            "POST /api/v1/settings с токеном роли 'laborant'",
            "HTTP 403 Forbidden (недостаточно прав)",
            f"HTTP {code}, msg='{resp.get('message')}'",
            True, dt
        )

    def test_15_ai_model_regression_metrics_verification(self):
        """TC-15 (Качество ИИ-модели): Проверка метрик MAE, RMSE, MAPE и R2 ансамбля GradientBoostingRegressor на тестовой выборке."""
        t0 = time.perf_counter()
        metrics = self.app.ai_engine.metrics
        gbr = metrics["gbr_model"]
        ridge = metrics["ridge_baseline"]
        self.assertLess(gbr["MAE_kw"], 0.08)
        self.assertLess(gbr["RMSE_kw"], 0.12)
        self.assertGreater(gbr["R2_score"], 0.95)
        self.assertLess(gbr["MAE_kw"], ridge["MAE_kw"])
        dt = (time.perf_counter() - t0) * 1000
        self._record(
            "TC-15", "Метрики ИИ (scikit-learn)", "Сравнение точности GradientBoostingRegressor и базовой модели Ridge",
            f"Синтетическая выборка: {metrics['train_samples']} обуч. / {metrics['test_samples']} тест.",
            "MAE(GBR) < 0.08 кВт, R2(GBR) > 0.95, MAE(GBR) < MAE(Ridge)",
            f"GBR: MAE={gbr['MAE_kw']} кВт, RMSE={gbr['RMSE_kw']} кВт, MAPE={gbr['MAPE_active_pct']}%, R2={gbr['R2_score']} (Ridge MAE={ridge['MAE_kw']})",
            True, dt
        )

    def test_16_controlled_model_adaptation_loop(self):
        """TC-16 (Адаптация ИИС): Проверка формулы Model_{t+1} = Update(Model_t, Data_new) с контролем невозрастания ошибки."""
        t0 = time.perf_counter()
        code, resp = self.app.dispatch(
            "POST", "/api/v1/ai/adapt",
            body={
                "feedback_samples": [
                    {"total_pcs": 12, "is_occupied": False, "hour": 14, "day_of_week": 3, "temp_c": 23.1, "open_windows": 0, "verified_baseline_kw": 0.02},
                    {"total_pcs": 16, "is_occupied": True, "hour": 10, "day_of_week": 2, "temp_c": 23.8, "open_windows": 0, "verified_baseline_kw": 1.92},
                ]
            },
            headers={"Authorization": "Bearer demo-role-sysadmin"}
        )
        ad = resp["adaptation"]
        self.assertEqual(code, 200)
        self.assertTrue(ad["accepted"])
        self.assertIn("adapted", ad["candidate_version"])
        dt = (time.perf_counter() - t0) * 1000
        self._record(
            "TC-16", "Адаптация ИИС", "Дообучение модели ИИ по верифицированной обратной связи Update(Model_t, Data_new)",
            "2 верифицированных наблюдения + токен sys_admin",
            "HTTP 200, accepted=True, версия обновлена до v1.3-gbr-adapted",
            f"HTTP {code}, version={ad['candidate_version']}, MAE={ad['candidate_metrics']['MAE_kw']} кВт, accepted={ad['accepted']}",
            True, dt
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(EnergoCampusTestSuite)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Сохраняем машиночитаемый протокол выполнения тестов для включения в Главу 3 и Приложение Г
    report_path = os.path.join(BASE_DIR, "tests", "test_report.json")
    summary_payload = {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "total_tests": result.testsRun,
        "passed": result.testsRun - len(result.failures) - len(result.errors),
        "failed": len(result.failures),
        "errors": len(result.errors),
        "ai_metrics": EnergoCampusTestSuite.app.ai_engine.metrics if hasattr(EnergoCampusTestSuite, "app") else {},
        "test_cases": EnergoCampusTestSuite.results_log,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary_payload, f, ensure_ascii=False, indent=2)
    print(f"\n[Протокол тестирования сохранён]: {report_path}")
    sys.exit(0 if result.wasSuccessful() else 1)
