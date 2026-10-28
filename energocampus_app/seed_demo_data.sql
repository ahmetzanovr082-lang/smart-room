-- ============================================================================
-- ИИС «ЭнергоКампус»: Начальное демонстрационное заполнение БД (seed_demo_data.sql)
-- СУБД: PostgreSQL 16+ (совместимо со схемой schema.sql из 14 таблиц в 3НФ)
-- ВНИМАНИЕ: Все временные ряды и замеры являются синтетическими демонстрационными
-- данными (is_synthetic = true) для 6 кабинетов (72 ПК) учебного корпуса А.
-- Пароли не хранятся в открытом виде (указаны демонстрационные bcrypt-заглушки).
-- ============================================================================

BEGIN;

-- 1. Роли пользователей (4 роли согласно диаграмме UML Use Case)
INSERT INTO roles (role_code, role_name, permissions_json) VALUES
    ('laborant', 'Лаборант компьютерного класса', '{"read": true, "simulate": true, "recommend_action": true}'::jsonb),
    ('energomanager', 'Ответственный за энергохозяйство', '{"read": true, "analytics": true, "settings": true, "export_csv": true}'::jsonb),
    ('it_admin', 'ИТ-администратор', '{"read": true, "controllers": true, "logs": true}'::jsonb),
    ('sys_admin', 'Администратор системы', '{"all": true}'::jsonb)
ON CONFLICT (role_code) DO NOTHING;

-- 2. Учётные записи пользователей (демонстрационные хеши паролей)
INSERT INTO users (role_id, login, password_hash, full_name, position_title, is_active) VALUES
    (1, 'lab_operator', '$2b$12$DEMO_HASH_PLACEHOLDER_LABORANT_000000000000000000000', 'Балташев А. Ж.', 'Дежурный лаборант корпуса А', TRUE),
    (2, 'energy_chief', '$2b$12$DEMO_HASH_PLACEHOLDER_MANAGER_0000000000000000000000', 'Ахметжанов Р. К.', 'Ответственный за энергохозяйство', TRUE),
    (3, 'it_engineer',  '$2b$12$DEMO_HASH_PLACEHOLDER_ITADMIN_0000000000000000000000', 'Инженер ИТ-службы', 'Инженер по обслуживанию датчиков', TRUE),
    (4, 'sys_admin',    '$2b$12$DEMO_HASH_PLACEHOLDER_SYSADMIN_000000000000000000000', 'Администратор ИИС', 'Системный администратор', TRUE)
ON CONFLICT (login) DO NOTHING;

-- 3. Справочник 6 контролируемых кабинетов корпуса А (суммарно 72 ПК)
INSERT INTO rooms (room_id, building_code, floor_num, room_name, room_type, total_pcs, light_line_watts, current_state) VALUES
    ('201', 'A', 2, 'Компьютерный класс',           'Компьютерный класс',      12, 120, 'S1_OCCUPIED'),
    ('202', 'A', 2, 'Лаборатория информатики',      'Учебная лаборатория',     12, 120, 'S2_IDLE'),
    ('204', 'A', 2, 'Компьютерный класс',           'Компьютерный класс',      12, 120, 'S3_EXCESS'),
    ('301', 'A', 3, 'Лаборатория программирования', 'Учебная лаборатория',     16, 120, 'S1_OCCUPIED'),
    ('302', 'A', 3, 'Мультимедийный класс',         'Мультимедийная аудитория', 8, 120, 'S3_EXCESS'),
    ('305', 'A', 3, 'Компьютерный класс',           'Компьютерный класс',      12, 120, 'S0_OFFLINE')
ON CONFLICT (room_id) DO NOTHING;

-- 4. Контроллеры телеметрии ESP32 по кабинетам
INSERT INTO room_controllers (room_id, mac_address, ip_address, firmware_ver, is_online, last_seen_at) VALUES
    ('201', 'AA:BB:CC:00:01:01', '192.168.10.201', 'v1.2.0-esp32', TRUE,  CURRENT_TIMESTAMP),
    ('202', 'AA:BB:CC:00:02:02', '192.168.10.202', 'v1.2.0-esp32', TRUE,  CURRENT_TIMESTAMP),
    ('204', 'AA:BB:CC:00:03:03', '192.168.10.204', 'v1.2.0-esp32', TRUE,  CURRENT_TIMESTAMP),
    ('301', 'AA:BB:CC:00:04:04', '192.168.10.301', 'v1.2.0-esp32', TRUE,  CURRENT_TIMESTAMP),
    ('302', 'AA:BB:CC:00:05:05', '192.168.10.302', 'v1.2.0-esp32', TRUE,  CURRENT_TIMESTAMP),
    ('305', 'AA:BB:CC:00:06:06', '192.168.10.305', 'v1.2.0-esp32', FALSE, CURRENT_TIMESTAMP - INTERVAL '8 minutes')
ON CONFLICT (room_id) DO NOTHING;

-- 5. Учебное расписание занятий (schedule_slots)
INSERT INTO schedule_slots (room_id, day_of_week, pair_number, time_start, time_end, group_code, subject_name, teacher_name) VALUES
    ('201', 3, 3, '12:00', '13:30', 'ИСУ-23-1',        'Интеллектуальные информационные системы', 'доц. Астапенко Н. В.'),
    ('301', 3, 3, '12:00', '13:30', 'ИСУ(kz-us)-23-2', 'Проектирование баз данных и экспертных систем', 'доц. Астапенко Н. В.');

-- 6. Системные уставки мощности, температурных границ и тарифа
-- [ДАННЫЕ: действующий тариф на электроэнергию для учебных корпусов, тг/кВт·ч = 32.50]
INSERT INTO system_settings_tariffs (pc_watts, light_watts, min_temp_c, max_temp_c, tariff_kzt_kwh, is_active) VALUES
    (150, 120, 18.0, 26.0, 32.50, TRUE);

-- 7. Реестр версий моделей ИИ (ml_models)
INSERT INTO ml_models (model_name, version_tag, algorithm_type, artifact_uri, confidence_threshold, metrics_json, is_active) VALUES
    ('EnergoHybrid_Rule_GBR', 'v1.2-gbr', 'Hybrid Rule-Based + scikit-learn GradientBoostingRegressor',
     'memory://scikit-learn/GradientBoostingRegressor', 0.75,
     '{"dataset_type": "synthetic_demonstration", "MAE_kw": 0.0413, "RMSE_kw": 0.1030, "MAPE_active_pct": 17.36, "R2_score": 0.9580}'::jsonb,
     TRUE)
ON CONFLICT (version_tag) DO NOTHING;

-- 8. Первичные срезы телеметрии по 6 кабинетам (входные факторы x1..x7 в отдельных столбцах)
INSERT INTO telemetry_measurements (
    room_id, controller_id, is_online, is_occupied, active_pcs, total_pcs,
    light_on, pc_watts_snapshot, light_watts_snapshot, tariff_kzt_snapshot,
    temp_c, open_windows, door_open, calc_power_kw
) VALUES
    ('201', 1, TRUE,  TRUE,  7, 12, TRUE,  150, 120, 32.50, 22.4, 0, FALSE, 1.17),
    ('202', 2, TRUE,  FALSE, 0, 12, FALSE, 150, 120, 32.50, 21.6, 0, FALSE, 0.00),
    ('204', 3, TRUE,  FALSE, 4, 12, TRUE,  150, 120, 32.50, 23.1, 0, TRUE,  0.72),
    ('301', 4, TRUE,  TRUE,  8, 16, TRUE,  150, 120, 32.50, 24.2, 0, FALSE, 1.32),
    ('302', 5, TRUE,  FALSE, 2,  8, FALSE, 150, 120, 32.50, 17.8, 1, FALSE, 0.30),
    ('305', 6, FALSE, FALSE, 0, 12, FALSE, 150, 120, 32.50, 21.2, 0, FALSE, 0.00);

-- 9. Запуски интеллектуального оценивания (ai_evaluation_runs)
INSERT INTO ai_evaluation_runs (
    room_id, measurement_id, model_id, setting_id, derived_features,
    state_class, current_power_kw, baseline_forecast_kw,
    saving_kwh_1h, saving_kwh_4h, saving_kzt_4h, confidence_score
) VALUES
    ('201', 1, 1, 1, '{"hour": 14, "day_of_week": 3, "is_synthetic": true}'::jsonb, 'S1_OCCUPIED', 1.17, 1.15, 0.02, 0.08,   2.60, 0.92),
    ('202', 2, 1, 1, '{"hour": 14, "day_of_week": 3, "is_synthetic": true}'::jsonb, 'S2_IDLE',     0.00, 0.00, 0.00, 0.00,   0.00, 0.92),
    ('204', 3, 1, 1, '{"hour": 14, "day_of_week": 3, "is_synthetic": true}'::jsonb, 'S3_EXCESS',   0.72, 0.00, 0.72, 2.88,  93.60, 0.92),
    ('301', 4, 1, 1, '{"hour": 14, "day_of_week": 3, "is_synthetic": true}'::jsonb, 'S1_OCCUPIED', 1.32, 1.30, 0.02, 0.08,   2.60, 0.92),
    ('302', 5, 1, 1, '{"hour": 14, "day_of_week": 3, "is_synthetic": true}'::jsonb, 'S3_EXCESS',   0.30, 0.00, 0.30, 1.20,  39.00, 0.92),
    ('305', 6, 1, 1, '{"hour": 14, "day_of_week": 3, "is_synthetic": true}'::jsonb, 'S0_OFFLINE',  0.00, 0.00, 0.00, 0.00,   0.00, 0.00);

-- 10. Обнаруженные аномалии с факторами XAI (detected_anomalies)
INSERT INTO detected_anomalies (run_id, room_id, anomaly_type, severity, title, explanation_text, xai_factors) VALUES
    (3, '204', 'energy',  'warning', 'Техника в свободном кабинете', '4 ПК · свет включён (потери 0.72 кВт·ч/ч)',
     '[{"factor": "4 ПК (150 Вт)", "value": "4 шт.", "impact_kw": 0.60, "share_pct": 83.3}, {"factor": "Освещение (120 Вт)", "value": "включено", "impact_kw": 0.12, "share_pct": 16.7}]'::jsonb),
    (5, '302', 'energy',  'warning', 'Техника в свободном кабинете', '2 ПК · свет выключен (потери 0.30 кВт·ч/ч)',
     '[{"factor": "2 ПК (150 Вт)", "value": "2 шт.", "impact_kw": 0.30, "share_pct": 100.0}]'::jsonb),
    (5, '302', 'climate', 'warning', 'Температура ниже нормы',       '17.8 °C (норма 18.0–26.0 °C) · окно открыто',
     '[{"factor": "Температура воздуха x5", "value": "17.8 °C", "impact_kw": 0.0, "share_pct": 70.0}, {"factor": "Оконные створки x6", "value": "открыто (1)", "impact_kw": 0.0, "share_pct": 30.0}]'::jsonb),
    (6, '305', 'offline', 'neutral', 'Нет связи с контроллером',     'Состояние устройств неизвестно. Расчёт экономии заблокирован (NFR-2).',
     '[{"factor": "Связь x7 (is_online)", "value": "false", "impact_kw": 0.0, "share_pct": 100.0}]'::jsonb);

-- 11. Рекомендации энергосбережения со статусами жизненного цикла (saving_recommendations)
INSERT INTO saving_recommendations (
    anomaly_id, room_id, assigned_user_id, action_text,
    expected_saving_kwh, expected_saving_kzt, status, created_at, processed_at, operator_comment
) VALUES
    (1, '204', 1, 'Выключить 4 ПК и освещение в свободном каб. 204', 2.88, 93.60, 'new', CURRENT_TIMESTAMP, NULL, NULL),
    (2, '302', 1, 'Выключить 2 ПК и закрыть окно в свободном каб. 302', 1.20, 39.00, 'new', CURRENT_TIMESTAMP, NULL, NULL);

COMMIT;
