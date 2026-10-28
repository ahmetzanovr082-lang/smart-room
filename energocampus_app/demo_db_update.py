# -*- coding: utf-8 -*-
"""
Интерактивная утилита для демонстрации прямой работы с базой данных SQLite (14 таблиц в 3НФ).
Позволяет изменять значения в таблицах БД 'на лету', чтобы показать научному руководителю/преподавателю
мгновенное отображение изменений на сайте «ЭнергоКампус».
"""
import os
import sqlite3
import sys

from backend.ai_engine import EnergoAIEngine
from backend.config import DB_PATH
from backend.db_manager import DatabaseManager

sys.stdout.reconfigure(encoding="utf-8")


def print_header():
    print("\n" + "=" * 70)
    print("   ИИС «ЭнергоКампус» — Интерактивное управление базой данных SQLite")
    print(f"   Файл базы: {os.path.abspath(DB_PATH)}")
    print("=" * 70)


def show_current_state(db: DatabaseManager):
    st = db.get_all_rooms_state()
    settings = st["settings"]
    print("\n[ТЕКУЩИЕ НАСТРОЙКИ В БД (system_settings_tariffs)]:")
    print(f"  ПК: {settings['pcWatts']} Вт | Свет: {settings['lightWatts']} Вт | Тариф: {settings['tariffKzt']} тг/кВт·ч | Норма темп.: {settings['minTemp']}..{settings['maxTemp']} °C")
    print("\n[ТЕКУЩЕЕ СОСТОЯНИЕ 6 КАБИНЕТОВ В БД (rooms + telemetry_measurements)]:")
    print(f"  {'Каб.':<6} {'Связь':<10} {'Занятость':<10} {'ПК вкл.':<9} {'Свет':<8} {'Окна':<6} {'Темп.':<8} {'Класс ИИ':<12} {'Мощность'}")
    print("  " + "-" * 76)
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
        print(f"  {r['id']:<6} {online:<10} {occ:<10} {pcs:<9} {light:<8} {wins:<6} {temp:<8} {s_cls:<12} {p_kw}")
    print()


def run_scenario(db: DatabaseManager, choice: str):
    if choice == "1":
        # Кабинет 204: Включить 12 компьютеров и освещение (создать мощный перерасход S3_EXCESS)
        print("\n>>> Выполняется: Каб. 204 — включение всех 12 ПК и света в свободном классе...")
        pcs = [True] * 12
        db.save_telemetry_snapshot({
            "room_id": "204", "online": True, "occupied": False,
            "computers_on": 12, "total_pcs": 12, "computers": pcs,
            "light_on": True, "windows_open": 0, "door_open": True,
            "temp_c": 23.5, "event_note": "Демонстрация: в пустом кабинете 204 включены все 12 ПК"
        })
        print("✓ Успешно записано в БД! Перерасход зафиксирован. На сайте кабинет 204 станет ярко-янтарным!")

    elif choice == "2":
        # Кабинет 204: Полное выключение техники (устранение перерасхода, S1_NORMAL)
        print("\n>>> Выполняется: Каб. 204 — отключение всех ПК и освещения (лаборант выключил технику)...")
        pcs = [False] * 12
        db.save_telemetry_snapshot({
            "room_id": "204", "online": True, "occupied": False,
            "computers_on": 0, "total_pcs": 12, "computers": pcs,
            "light_on": False, "windows_open": 0, "door_open": False,
            "temp_c": 21.8, "event_note": "Демонстрация: вся техника в кабинете 204 выключена"
        })
        print("✓ Успешно записано в БД! Мощность кабинета 204 упала до 0.00 кВт (статус S1_NORMAL).")

    elif choice == "3":
        # Кабинет 302: Открыть окно и снизить температуру до 15.5 °C (нарушение микроклимата)
        print("\n>>> Выполняется: Каб. 302 — открытие окна и падение температуры до 15.5 °C...")
        pcs = [False] * 8
        db.save_telemetry_snapshot({
            "room_id": "302", "online": True, "occupied": False,
            "computers_on": 0, "total_pcs": 8, "computers": pcs,
            "light_on": False, "windows_open": 1, "door_open": False,
            "temp_c": 15.5, "event_note": "Демонстрация: открыто окно, выхолаживание до 15.5 °C"
        })
        print("✓ Успешно записано в БД! Сработало предупреждение о нарушении микроклимата.")

    elif choice == "4":
        # Кабинет 302: Закрыть окно и вернуть температуру 21.5 °C (норма)
        print("\n>>> Выполняется: Каб. 302 — закрытие окна и нормализация температуры до 21.5 °C...")
        pcs = [False] * 8
        db.save_telemetry_snapshot({
            "room_id": "302", "online": True, "occupied": False,
            "computers_on": 0, "total_pcs": 8, "computers": pcs,
            "light_on": False, "windows_open": 0, "door_open": False,
            "temp_c": 21.5, "event_note": "Демонстрация: окно закрыто, температура в норме"
        })
        print("✓ Успешно записано в БД! Кабинет 302 перешёл в штатное состояние.")

    elif choice == "5":
        # Кабинет 305: Восстановить связь с контроллером (ONLINE)
        print("\n>>> Выполняется: Каб. 305 — контроллер восстановил связь по сети...")
        pcs = [False] * 12
        db.save_telemetry_snapshot({
            "room_id": "305", "online": True, "occupied": False,
            "computers_on": 0, "total_pcs": 12, "computers": pcs,
            "light_on": False, "windows_open": 0, "door_open": False,
            "temp_c": 21.2, "event_note": "Демонстрация: контроллер 305 вернулся в онлайн"
        })
        print("✓ Успешно записано в БД! На сайте теперь все 6 контроллеров на связи.")

    elif choice == "6":
        # Кабинет 305: Сымитировать обрыв связи (OFFLINE)
        print("\n>>> Выполняется: Каб. 305 — потеря связи (статус S0_OFFLINE)...")
        pcs = [False] * 12
        db.save_telemetry_snapshot({
            "room_id": "305", "online": False, "occupied": False,
            "computers_on": 0, "total_pcs": 12, "computers": pcs,
            "light_on": False, "windows_open": 0, "door_open": False,
            "temp_c": 21.2, "event_note": "Демонстрация: обрыв связи с контроллером 305"
        })
        print("✓ Успешно записано в БД! Кабинет 305 переведён в серый статус S0_OFFLINE.")

    elif choice == "7":
        # Изменение тарифа электроэнергии
        val = input("\nВведите новый тариф университета в тенге за 1 кВт·ч (например, 45.0): ").strip()
        try:
            tariff = float(val)
            if tariff <= 0:
                print("Ошибка: тариф должен быть положительным числом.")
                return
            db.update_settings({"tariffKzt": tariff})
            print(f"✓ Успешно! Тариф в таблице system_settings_tariffs обновлён на {tariff} тг/кВт·ч.")
            print("На сайте все суммы экономии в тенге пересчитаются автоматически!")
        except ValueError:
            print("Ошибка: введено не число.")

    elif choice == "8":
        # Выполнение произвольного SQL-запроса
        print("\nПримеры запросов:")
        print("  SELECT room_id, power_kw, temp_c, is_occupied FROM telemetry_measurements ORDER BY measurement_id DESC LIMIT 6;")
        print("  SELECT * FROM saving_recommendations;")
        print("  SELECT * FROM system_settings_tariffs;")
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
                        print("-" * 60)
                        for r in rows:
                            print(" | ".join(str(r[c]) for c in cols))
                        print(f"\nВсего строк: {len(rows)}")
                else:
                    conn.commit()
                    print(f"✓ Запрос выполнен, изменено строк: {cur.rowcount}")
            except Exception as e:
                print(f"Ошибка выполнения SQL: {e}")

    elif choice == "9":
        # Сброс базы данных к исходным демонстрационным значениям
        confirm = input("\nВы уверены, что хотите сбросить БД к исходным значениям? (д/н): ").strip().lower()
        if confirm in ("д", "y", "да", "yes"):
            db.init_database(force_reset=True)
            print("✓ База данных сброшена и пересоздана с исходными 14 таблицами и 72 ПК!")


def main():
    ai = EnergoAIEngine(random_seed=42)
    db = DatabaseManager(db_path=DB_PATH, ai_engine=ai)

    while True:
        print_header()
        show_current_state(db)
        print("ВЫБЕРИТЕ ДЕЙСТВИЕ ДЛЯ ПРОВЕРКИ:")
        print("  1. Каб. 204: Включить 12 ПК и свет (создать мощный перерасход S3_EXCESS)")
        print("  2. Каб. 204: Выключить все ПК и свет (устранить перерасход, норма)")
        print("  3. Каб. 302: Открыть окно и охладить до 15.5 °C (тревога микроклимата)")
        print("  4. Каб. 302: Закрыть окно и вернуть 21.5 °C (нормализовать климат)")
        print("  5. Каб. 305: Восстановить связь с контроллером (ONLINE)")
        print("  6. Каб. 305: Сымитировать потерю связи (OFFLINE)")
        print("  7. Изменить тариф электроэнергии в тенге (в таблице system_settings_tariffs)")
        print("  8. Выполнить произвольный SQL-запрос к БД")
        print("  9. Сбросить БД к исходному состоянию (seed)")
        print("  0. Выход")
        print("=" * 70)
        choice = input("Введите номер (0-9): ").strip()
        if choice in ("0", "q", "exit"):
            print("\nВыход из утилиты.")
            break
        try:
            run_scenario(db, choice)
        except Exception as e:
            print(f"\n[!] Ошибка выполнения сценария: {e}")
        input("\nНажмите Enter, чтобы продолжить...")


if __name__ == "__main__":
    main()
