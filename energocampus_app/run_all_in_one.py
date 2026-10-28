# -*- coding: utf-8 -*-
"""
ИИС «ЭнергоКампус» — ЕДИНЫЙ ФАЙЛ ЗАПУСКА «ВСЁ-В-ОДНОМ» (All-in-One Launcher).

В одном файле и одном окне консоли объединено:
1. Автоматический запуск локального веб-сервера (Python ThreadingHTTPServer + REST API /api/v1/*).
2. Автоматическое открытие сайта в браузере (http://127.0.0.1:8000).
3. Прямое подключение к реляционной базе данных SQLite (14 таблиц в 3НФ).
4. Интерактивное меню управления базой данных «на лету» (изменение ПК, света, окон, температуры, тарифа, произвольные SQL-запросы).
5. При любых изменениях в консоли открытый сайт в браузере обновляется в реальном времени (автосинхронизация каждые 2 секунды).
"""
import os
import socket
import sys
import threading
import time
import webbrowser
from http.server import ThreadingHTTPServer

from backend.ai_engine import EnergoAIEngine
from backend.config import BASE_DIR, DB_PATH
from backend.db_manager import DatabaseManager
from backend.server import EnergoCampusApplication, create_http_handler

sys.stdout.reconfigure(encoding="utf-8")


def find_free_port(start_port: int = 8000, max_attempts: int = 10) -> int:
    """Поиск свободного локального порта, если 8000 занят другим процессом."""
    for p in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return start_port


def print_banner(port: int):
    print("\n" + "=" * 74)
    print("   ИИС «ЭНЕРГОКАМПУС» — СИСТЕМА МОНИТОРИНГА ЭНЕРГОПОТРЕБЛЕНИЯ")
    print(f"   Локальный сервер:  http://127.0.0.1:{port}")
    print(f"   Файл базы данных:  {os.path.abspath(DB_PATH)}")
    print("   Реляционная схема: 14 таблиц в 3НФ (PostgreSQL 16 DDL / SQLite 3)")
    print("=" * 74)


def print_rooms_table(db: DatabaseManager):
    st = db.get_all_rooms_state()
    settings = st["settings"]
    print("\n[ТЕКУЩИЕ НАСТРОЙКИ В БД (system_settings_tariffs)]:")
    print(f"  Мощность ПК: {settings['pcWatts']} Вт | Освещение: {settings['lightWatts']} Вт | "
          f"Тариф: {settings['tariffKzt']} тг/кВт·ч | Диапазон темп.: {settings['minTemp']}..{settings['maxTemp']} °C")
    print("\n[СОСТОЯНИЕ 6 КАБИНЕТОВ В БД (таблицы rooms, telemetry_measurements, workstations_devices)]:")
    print(f"  {'Каб.':<6} {'Связь':<9} {'Занятость':<10} {'ПК вкл.':<9} {'Свет':<7} {'Окна':<6} {'Темп.':<8} {'Класс ИИ':<12} {'Мощность'}")
    print("  " + "-" * 74)
    for r in st["rooms"]:
        online = "ONLINE" if r["online"] else "OFFLINE"
        occ = "Занят" if r["occupied"] else "Свободен"
        pcs = f"{r['pcs']}/{r['total']}"
        light = "ВКЛ" if r["light"] else "ВЫКЛ"
        wins = f"{r['windows']} откр."
        temp = f"{r['temp']} °C"
        s_cls = r.get("state_class", "S1_NORMAL")
        calc_kw = (r["pcs"] * settings["pcWatts"] + (settings["lightWatts"] if r.get("light") else 0)) / 1000.0 if r.get("online") else 0.0
        p_kw_val = float(r.get("power_kw", calc_kw))
        p_kw = f"{p_kw_val:.2f} кВт"
        print(f"  {r['id']:<6} {online:<9} {occ:<10} {pcs:<9} {light:<7} {wins:<6} {temp:<8} {s_cls:<12} {p_kw}")
    print()


def execute_action(db: DatabaseManager, choice: str):
    if choice == "1":
        print("\n>>> Выполняется: Каб. 204 — включить все 12 ПК и свет в свободном классе (создать перерасход S3_EXCESS)...")
        pcs = [True] * 12
        db.save_telemetry_snapshot({
            "room_id": "204", "online": True, "occupied": False,
            "computers_on": 12, "total_pcs": 12, "computers": pcs,
            "light_on": True, "windows_open": 0, "door_open": True,
            "temp_c": 23.5, "event_note": "Включены все 12 ПК и свет в свободном каб. 204"
        })
        print("✓ Успешно записано в SQLite! На сайте кабинет 204 станет янтарным, мощность подскочит до ~1.92 кВт!")

    elif choice == "2":
        print("\n>>> Выполняется: Каб. 204 — выключить все ПК и свет (лаборант устранил перерасход)...")
        pcs = [False] * 12
        db.save_telemetry_snapshot({
            "room_id": "204", "online": True, "occupied": False,
            "computers_on": 0, "total_pcs": 12, "computers": pcs,
            "light_on": False, "windows_open": 0, "door_open": False,
            "temp_c": 21.8, "event_note": "Лаборант отключил технику и освещение в каб. 204"
        })
        print("✓ Успешно записано в SQLite! Мощность кабинета 204 снизилась до 0.00 кВт (статус S1_NORMAL).")

    elif choice == "3":
        print("\n>>> Выполняется: Каб. 302 — открыть окно и охладить до 15.5 °C (нарушение микроклимата)...")
        pcs = [False] * 8
        db.save_telemetry_snapshot({
            "room_id": "302", "online": True, "occupied": False,
            "computers_on": 0, "total_pcs": 8, "computers": pcs,
            "light_on": False, "windows_open": 1, "door_open": False,
            "temp_c": 15.5, "event_note": "Открыто окно, температура 15.5 °C (< 18 °C)"
        })
        print("✓ Успешно записано в SQLite! На сайте сработает предупреждение о нарушении микроклимата.")

    elif choice == "4":
        print("\n>>> Выполняется: Каб. 302 — закрыть окно и вернуть температуру 21.5 °C (норма)...")
        pcs = [False] * 8
        db.save_telemetry_snapshot({
            "room_id": "302", "online": True, "occupied": False,
            "computers_on": 0, "total_pcs": 8, "computers": pcs,
            "light_on": False, "windows_open": 0, "door_open": False,
            "temp_c": 21.5, "event_note": "Окно закрыто, температура нормализована"
        })
        print("✓ Успешно записано в SQLite! Кабинет 302 вернулся в штатный зелёный режим.")

    elif choice == "5":
        print("\n>>> Выполняется: Каб. 305 — восстановить связь с контроллером (is_online = 1)...")
        pcs = [False] * 12
        db.save_telemetry_snapshot({
            "room_id": "305", "online": True, "occupied": False,
            "computers_on": 0, "total_pcs": 12, "computers": pcs,
            "light_on": False, "windows_open": 0, "door_open": False,
            "temp_c": 21.2, "event_note": "Связь с контроллером 305 восстановлена"
        })
        print("✓ Успешно записано в SQLite! На сайте теперь все 6 контроллеров на связи.")

    elif choice == "6":
        print("\n>>> Выполняется: Каб. 305 — сымитировать обрыв связи (is_online = 0, статус S0_OFFLINE)...")
        pcs = [False] * 12
        db.save_telemetry_snapshot({
            "room_id": "305", "online": False, "occupied": False,
            "computers_on": 0, "total_pcs": 12, "computers": pcs,
            "light_on": False, "windows_open": 0, "door_open": False,
            "temp_c": 21.2, "event_note": "Обрыв связи с контроллером 305"
        })
        print("✓ Успешно записано в SQLite! Кабинет 305 переведён в статус «Нет связи» (S0_OFFLINE).")

    elif choice == "7":
        val = input("\nВведите новый тариф университета в тенге за 1 кВт·ч (например, 45.0): ").strip()
        try:
            tariff = float(val)
            if tariff <= 0:
                print("Ошибка: тариф должен быть положительным числом.")
                return
            db.update_settings({"tariffKzt": tariff})
            print(f"✓ Успешно записано в таблицу system_settings_tariffs! Новый тариф: {tariff:.2f} тг/кВт·ч.")
            print("На сайте все суммы экономии в тенге пересчитаются автоматически!")
        except ValueError:
            print("Ошибка: введено не число.")

    elif choice == "8":
        print("\n[КОНСОЛЬ SQL-ЗАПРОСОВ К БАЗЕ ДАННЫХ]")
        print("Примеры запросов для проверки преподавателем:")
        print("  SELECT room_id, power_kw, temp_c, is_occupied, is_online FROM telemetry_measurements ORDER BY measurement_id DESC LIMIT 6;")
        print("  SELECT recommendation_id, room_id, status, potential_saving_kwh, action_text FROM saving_recommendations;")
        print("  SELECT setting_id, pc_watts, light_watts, tariff_kzt_kwh FROM system_settings_tariffs;")
        query = input("\nВведите SQL-запрос: ").strip()
        if not query:
            return
        with db._connect() as conn:
            cur = conn.cursor()
            try:
                cur.execute(query)
                if query.upper().startswith("SELECT") or query.upper().startswith("PRAGMA"):
                    rows = cur.fetchall()
                    if not rows:
                        print("Результат: 0 строк.")
                    else:
                        cols = rows[0].keys()
                        print("\n" + " | ".join(cols))
                        print("-" * 65)
                        for r in rows:
                            print(" | ".join(str(r[c]) for c in cols))
                        print(f"\nВсего строк: {len(rows)}")
                else:
                    conn.commit()
                    print(f"✓ Запрос успешно выполнен, затронуто строк: {cur.rowcount}")
            except Exception as e:
                print(f"Ошибка выполнения SQL: {e}")

    elif choice == "9":
        confirm = input("\nСбросить базу данных к исходным демонстрационным значениям? (д/н): ").strip().lower()
        if confirm in ("д", "y", "да", "yes"):
            db.init_database(force_reset=True)
            print("✓ База данных сброшена и пересоздана с исходными 14 таблицами и 72 ПК!")


def main():
    port = find_free_port(8000)
    app = EnergoCampusApplication()
    handler_cls = create_http_handler(app)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler_cls)

    # 1. Запуск HTTP-сервера в фоновом потоке
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    # 2. Небольшая пауза и открытие сайта в браузере по умолчанию
    time.sleep(0.5)
    site_url = f"http://127.0.0.1:{port}"
    webbrowser.open(site_url)

    # 3. Интерактивная консоль в основном потоке (то же самое окно!)
    while True:
        print_banner(port)
        print_rooms_table(app.db)
        print("ВЫБЕРИТЕ ДЕЙСТВИЕ ДЛЯ ПРОВЕРКИ:")
        print("  1. Каб. 204: Включить 12 ПК и свет (создать мощный перерасход S3_EXCESS)")
        print("  2. Каб. 204: Выключить все ПК и свет (нормализовать S1_NORMAL)")
        print("  3. Каб. 302: Открыть окно и охладить до 15.5 °C (тревога микроклимата)")
        print("  4. Каб. 302: Закрыть окно и вернуть 21.5 °C (нормализовать климат)")
        print("  5. Каб. 305: Восстановить связь с контроллером (is_online = 1)")
        print("  6. Каб. 305: Сымитировать потерю связи (is_online = 0, S0_OFFLINE)")
        print("  7. Изменить тариф электроэнергии в тенге (system_settings_tariffs)")
        print("  8. Выполнить произвольный SQL-запрос к БД (SELECT, UPDATE...)")
        print("  9. Сбросить БД к исходным значениям (seed)")
        print("  0. Выход и остановка сервера")
        print("=" * 74)
        choice = input("Введите номер команды (0-9): ").strip()
        if choice in ("0", "q", "exit"):
            print("\nОстановка сервера и выход...")
            httpd.shutdown()
            httpd.server_close()
            print("Сервер остановлен. До свидания!")
            break
        try:
            execute_action(app.db, choice)
        except Exception as e:
            print(f"\n[!] Ошибка выполнения действия: {e}")
        input("\nНажмите Enter, чтобы обновить состояние в консоли...")


if __name__ == "__main__":
    main()
