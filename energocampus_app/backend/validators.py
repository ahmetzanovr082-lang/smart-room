# -*- coding: utf-8 -*-
"""
Модуль проверки и валидации входных данных, санитизации строк от XSS,
проверки SQL-запросов и контроля ролевого доступа (RBAC) для ИИС «ЭнергоКампус».
"""
import html
import math
import re
import secrets
from typing import Any, Dict, Optional, Tuple
from .config import ACTIVE_SESSION_TOKENS, ROLE_PROFILES, ROLE_TOKENS, VALIDATION_BOUNDS

ALLOWED_ROOM_IDS = {"201", "202", "204", "301", "302", "305"}
ALLOWED_RECOMMENDATION_STATUSES = {"new", "accepted", "completed", "rejected"}
ALLOWED_STATE_CLASSES = {"S1_OCCUPIED", "S2_IDLE", "S3_EXCESS", "S0_OFFLINE"}
ALLOWED_ANOMALY_TYPES = {"energy", "climate", "window", "offline"}
ALLOWED_SEVERITIES = {"warning", "neutral", "critical"}
ALLOWED_DEVICE_TYPES = {"PC", "LIGHT", "HVAC", "SWITCH"}
ALLOWED_EVENT_TYPES = {"energy", "climate", "window", "offline", "ok", "settings", "report_export"}

FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE|ATTACH|DETACH|VACUUM|REINDEX|GRANT|REVOKE|BEGIN|COMMIT|ROLLBACK|SAVEPOINT)\b",
    re.IGNORECASE,
)


class ValidationError(Exception):
    """Исключение при нарушении формата, прав доступа или допустимых границ входных данных."""

    def __init__(self, message: str, field: str = "", code: int = 422):
        super().__init__(message)
        self.message = message
        self.field = field
        self.code = code


def sanitize_text(value: Any, max_len: int = 300) -> str:
    """Экранирование спецсимволов HTML (защита от XSS) и ограничение длины строки."""
    if value is None:
        return ""
    raw = str(value).strip()
    if len(raw) > max_len:
        raw = raw[:max_len]
    return html.escape(raw, quote=True)


def issue_role_session_token(role_code: str) -> Tuple[str, Dict[str, Any]]:
    """Генерация случайного сессионного токена для авторизованной роли."""
    norm_role = "sys_admin" if role_code in ("sys_admin", "sysadmin") else (
        "energomanager" if role_code in ("energomanager", "energy_chief") else "laborant"
    )
    profile = dict(ROLE_PROFILES[norm_role])
    if norm_role == "laborant":
        return "demo-role-laborant", profile
    token = f"sess_{secrets.token_urlsafe(24)}"
    ACTIVE_SESSION_TOKENS[token] = profile
    return token, profile


def check_role_permission(token: str, required_perm: str) -> Dict[str, Any]:
    """Проверка токена роли (сессионного или демонстрационного) и наличия требуемого разрешения."""
    if not token:
        if required_perm in ("settings", "adapt_model", "admin"):
            raise ValidationError(
                f"Отказано в доступе: для операции '{required_perm}' требуется авторизация привилегированной роли.",
                field="Authorization",
                code=403,
            )
        return ROLE_PROFILES["laborant"]

    clean_token = token.replace("Bearer ", "").strip()
    role_info = ACTIVE_SESSION_TOKENS.get(clean_token) or ROLE_TOKENS.get(clean_token)
    if not role_info:
        raise ValidationError("Недействительный или истёкший токен сессии.", field="Authorization", code=401)
    if required_perm not in role_info["permissions"]:
        raise ValidationError(
            f"Роль '{role_info['role_name']}' не обладает правом '{required_perm}'.",
            field="Authorization",
            code=403,
        )
    return role_info


def validate_readonly_sql_query(query: str) -> str:
    """
    Строгая валидация SQL-запроса из веб-консоли:
    разрешается только одиночный оператор SELECT или PRAGMA table_info(...).
    Любые модифицирующие команды (INSERT, UPDATE, DELETE, DROP, ATTACH) и множественные запросы блокируются.
    """
    raw_q = (query or "").strip()
    if not raw_q:
        raise ValidationError("SQL-запрос не может быть пустым.", field="query", code=422)

    if "--" in raw_q or "/*" in raw_q or "*/" in raw_q:
        raise ValidationError("SQL-комментарии в интерактивной консоли запрещены политикой безопасности.", field="query", code=403)

    # Допускается не более одной точки с запятой только в самом конце строки
    stripped_semi = raw_q[:-1].strip() if raw_q.endswith(";") else raw_q
    if ";" in stripped_semi:
        raise ValidationError(
            "Множественные SQL-операторы запрещены политикой безопасности. Разрешён только одиночный запрос чтения.",
            field="query",
            code=403,
        )

    if FORBIDDEN_SQL_PATTERN.search(stripped_semi):
        raise ValidationError(
            "В SQL-консоли запрещены модифицирующие и административные команды (INSERT, UPDATE, DELETE, DROP, ATTACH). Изменение записей допускается только через валидируемую форму update_row.",
            field="query",
            code=403,
        )

    upper_q = stripped_semi.upper()
    if upper_q.startswith("SELECT"):
        return stripped_semi + ";"

    pragma_match = re.match(r"^PRAGMA\s+table_info\s*\(\s*([a-zA-Z0-9_]+)\s*\)$", stripped_semi, re.IGNORECASE)
    if pragma_match:
        return f"PRAGMA table_info({pragma_match.group(1)});"

    raise ValidationError(
        "В SQL-консоли разрешены только одиночные запросы SELECT или PRAGMA table_info(table_name).",
        field="query",
        code=403,
    )


def validate_table_row_update(
    table_name: str,
    values: Dict[str, Any],
    current_row: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Валидация обновляемых полей строки таблицы БД по физическим и доменным границам VALIDATION_BOUNDS.
    При нарушении ограничений выбрасывает ValidationError с кодом HTTP 422.
    """
    if not isinstance(values, dict) or not values:
        raise ValidationError("Набор обновляемых полей не может быть пустым.", field="values", code=422)

    cur = current_row or {}
    bound_field_map = {
        "pc_watts": "pc_watts",
        "pc_watts_snapshot": "pc_watts",
        "rated_watts": "pc_watts",
        "light_watts": "light_watts",
        "light_watts_snapshot": "light_watts",
        "light_line_watts": "light_watts",
        "min_temp_c": "min_temp_c",
        "max_temp_c": "max_temp_c",
        "temp_c": "temp_c",
        "tariff_kzt_kwh": "tariff_kzt_kwh",
        "tariff_kzt_snapshot": "tariff_kzt_kwh",
        "total_pcs": "total_pcs",
        "open_windows": "open_windows",
    }

    bool_fields = {"is_online", "is_occupied", "light_on", "door_open", "is_power_on", "is_active"}
    non_negative_float_fields = {
        "calc_power_kw", "current_power_kw", "baseline_forecast_kw",
        "saving_kwh_1h", "saving_kwh_4h", "saving_kzt_4h",
        "predicted_kw", "baseline_no_ctrl_kw",
        "expected_saving_kwh", "expected_saving_kzt",
    }

    cleaned: Dict[str, Any] = {}
    for col, raw_val in values.items():
        if raw_val is None or raw_val == "":
            cleaned[col] = None
            continue

        if col in bound_field_map:
            b_key = bound_field_map[col]
            low, high = VALIDATION_BOUNDS[b_key]
            try:
                num_val = float(raw_val)
            except (ValueError, TypeError):
                raise ValidationError(f"Поле '{col}' должно быть числом.", field=col, code=422)
            if math.isnan(num_val) or math.isinf(num_val) or not (low <= num_val <= high):
                raise ValidationError(
                    f"Значение поля '{col}' ({raw_val}) выходит за допустимые границы [{low}; {high}].",
                    field=col,
                    code=422,
                )
            cleaned[col] = int(num_val) if isinstance(low, int) and isinstance(high, int) else round(num_val, 2)
            continue

        if col in bool_fields:
            if str(raw_val).strip().lower() in ("1", "true"):
                cleaned[col] = 1
            elif str(raw_val).strip().lower() in ("0", "false"):
                cleaned[col] = 0
            else:
                raise ValidationError(f"Логическое поле '{col}' должно принимать значение 0 или 1.", field=col, code=422)
            continue

        if col == "active_pcs":
            try:
                act_val = int(raw_val)
            except (ValueError, TypeError):
                raise ValidationError("Поле 'active_pcs' должно быть целым числом.", field="active_pcs", code=422)
            max_cap = int(values.get("total_pcs", cur.get("total_pcs", VALIDATION_BOUNDS["total_pcs"][1])))
            if act_val < 0 or act_val > max_cap:
                raise ValidationError(
                    f"Число включённых ПК ({act_val}) не может быть отрицательным или превышать ёмкость кабинета ({max_cap}).",
                    field="active_pcs",
                    code=422,
                )
            cleaned[col] = act_val
            continue

        if col == "floor_num":
            try:
                fl_val = int(raw_val)
            except (ValueError, TypeError):
                raise ValidationError("Поле 'floor_num' должно быть целым числом.", field="floor_num", code=422)
            if not (1 <= fl_val <= 12):
                raise ValidationError("Этаж 'floor_num' должен находиться в диапазоне [1; 12].", field="floor_num", code=422)
            cleaned[col] = fl_val
            continue

        if col in ("confidence_threshold", "confidence_score"):
            try:
                c_val = float(raw_val)
            except (ValueError, TypeError):
                raise ValidationError(f"Поле '{col}' должно быть вещественным числом.", field=col, code=422)
            if math.isnan(c_val) or not (0.0 <= c_val <= 1.0):
                raise ValidationError(f"Поле '{col}' ({raw_val}) должно быть в диапазоне [0.0; 1.0].", field=col, code=422)
            cleaned[col] = round(c_val, 4)
            continue

        if col in non_negative_float_fields:
            try:
                f_val = float(raw_val)
            except (ValueError, TypeError):
                raise ValidationError(f"Поле '{col}' должно быть числом.", field=col, code=422)
            if math.isnan(f_val) or math.isinf(f_val) or f_val < 0.0 or f_val > 10000.0:
                raise ValidationError(f"Значение '{col}' ({raw_val}) должно быть неотрицательным числом в пределах [0; 10000].", field=col, code=422)
            cleaned[col] = round(f_val, 2)
            continue

        if col in ("current_state", "state_class"):
            s_val = str(raw_val).strip()
            if s_val not in ALLOWED_STATE_CLASSES:
                raise ValidationError(f"Недопустимый класс состояния '{s_val}'.", field=col, code=422)
            cleaned[col] = s_val
            continue

        if col == "status" and table_name == "saving_recommendations":
            s_val = str(raw_val).strip()
            if s_val not in ALLOWED_RECOMMENDATION_STATUSES:
                raise ValidationError(f"Недопустимый статус рекомендации '{s_val}'.", field=col, code=422)
            cleaned[col] = s_val
            continue

        if col == "anomaly_type":
            s_val = str(raw_val).strip()
            if s_val not in ALLOWED_ANOMALY_TYPES:
                raise ValidationError(f"Недопустимый тип аномалии '{s_val}'.", field=col, code=422)
            cleaned[col] = s_val
            continue

        if col == "severity":
            s_val = str(raw_val).strip()
            if s_val not in ALLOWED_SEVERITIES:
                raise ValidationError(f"Недопустимый уровень критичности '{s_val}'.", field=col, code=422)
            cleaned[col] = s_val
            continue

        if col == "device_type":
            s_val = str(raw_val).strip()
            if s_val not in ALLOWED_DEVICE_TYPES:
                raise ValidationError(f"Недопустимый тип устройства '{s_val}'.", field=col, code=422)
            cleaned[col] = s_val
            continue

        if col == "event_type":
            s_val = str(raw_val).strip()
            if s_val not in ALLOWED_EVENT_TYPES:
                raise ValidationError(f"Недопустимый тип события '{s_val}'.", field=col, code=422)
            cleaned[col] = s_val
            continue

        json_fields = {
            "xai_factors", "derived_features", "permissions_json",
            "metrics_json", "parameters_json", "feature_importances",
        }
        if col in json_fields:
            if isinstance(raw_val, (dict, list)):
                cleaned[col] = json.dumps(raw_val, ensure_ascii=False)
            elif isinstance(raw_val, str):
                s_raw = html.unescape(raw_val).strip()
                try:
                    parsed = json.loads(s_raw)
                    cleaned[col] = json.dumps(parsed, ensure_ascii=False)
                except Exception:
                    raise ValidationError(f"Поле '{col}' должно содержать корректный JSON.", field=col, code=422)
            continue

        if isinstance(raw_val, str):
            cleaned[col] = sanitize_text(raw_val, max_len=500)
        else:
            cleaned[col] = raw_val

    # Проверка перекрёстного инварианта температурных порогов
    if "min_temp_c" in cleaned or "max_temp_c" in cleaned:
        eff_min = float(cleaned.get("min_temp_c", cur.get("min_temp_c", 18.0)))
        eff_max = float(cleaned.get("max_temp_c", cur.get("max_temp_c", 26.0)))
        if eff_min >= eff_max:
            raise ValidationError(
                f"Нижний порог температуры ({eff_min} °C) должен быть строго меньше верхнего ({eff_max} °C).",
                field="min_temp_c",
                code=422,
            )

    # Проверка перекрёстного инварианта числа ПК при уменьшении total_pcs
    if "total_pcs" in cleaned and ("active_pcs" in cleaned or "active_pcs" in cur):
        eff_tot = int(cleaned["total_pcs"])
        eff_act = int(cleaned.get("active_pcs", cur.get("active_pcs", 0)))
        if eff_act > eff_tot:
            raise ValidationError(
                f"Число включённых ПК ({eff_act}) превышает новое значение total_pcs ({eff_tot}).",
                field="total_pcs",
                code=422,
            )

    return cleaned


def validate_telemetry_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Полная структурная и физическая валидация пакета телеметрии/оценки кабинета
    (соответствует шагу BP-02 и шлюзу GW-1 из Главы 2, а также таблице 1.5).
    """
    if not isinstance(payload, dict):
        raise ValidationError("Тело запроса должно быть JSON-объектом.", field="body", code=400)

    room_id = str(payload.get("room_id", "")).strip()
    if not room_id or not re.match(r"^[0-9A-Za-z_-]{1,16}$", room_id):
        raise ValidationError("Некорректный идентификатор кабинета room_id.", field="room_id", code=422)
    if room_id not in ALLOWED_ROOM_IDS:
        raise ValidationError(f"Кабинет '{room_id}' не найден в реестре корпуса А.", field="room_id", code=404)

    online = payload.get("online", payload.get("is_online", True))
    if not isinstance(online, bool):
        raise ValidationError("Поле online (x7) должно иметь логический тип boolean.", field="online", code=422)

    occupied = payload.get("occupied", payload.get("is_occupied", False))
    if not isinstance(occupied, bool):
        raise ValidationError("Поле occupied (x4) должно иметь логический тип boolean.", field="occupied", code=422)

    light_on = payload.get("light_on", payload.get("light", False))
    if not isinstance(light_on, bool):
        raise ValidationError("Поле light_on (x2) должно иметь логический тип boolean.", field="light_on", code=422)

    door_open = payload.get("door_open", payload.get("door", False))
    if not isinstance(door_open, bool):
        raise ValidationError("Поле door_open (x6) должно иметь логический тип boolean.", field="door_open", code=422)

    try:
        total_pcs = int(payload.get("total_pcs", payload.get("total", 12)))
        computers_on = int(payload.get("computers_on", payload.get("active_pcs", payload.get("pcs", 0))))
        windows_open = int(payload.get("windows_open", payload.get("open_windows", payload.get("windows", 0))))
        temp_c = float(payload.get("temp_c", payload.get("temp", 22.0)))
    except (ValueError, TypeError) as exc:
        raise ValidationError(f"Ошибка числового типа во входных параметрах: {exc}", field="numeric", code=422)

    if math.isnan(temp_c) or math.isinf(temp_c):
        raise ValidationError("Значение температуры temp_c не может быть NaN или бесконечностью.", field="temp_c", code=422)

    min_t, max_t = VALIDATION_BOUNDS["temp_c"]
    if not (min_t <= temp_c <= max_t):
        raise ValidationError(
            f"Температура {temp_c} °C выходит за физически допустимый диапазон датчика [{min_t}; {max_t}] °C.",
            field="temp_c",
            code=422,
        )

    min_tot, max_tot = VALIDATION_BOUNDS["total_pcs"]
    if not (min_tot <= total_pcs <= max_tot):
        raise ValidationError(
            f"Общее число ПК ({total_pcs}) вне допустимого диапазона [{min_tot}; {max_tot}].",
            field="total_pcs",
            code=422,
        )

    if computers_on < 0 or computers_on > total_pcs:
        raise ValidationError(
            f"Число включённых ПК ({computers_on}) не может быть отрицательным или превышать ёмкость кабинета ({total_pcs}).",
            field="computers_on",
            code=422,
        )

    min_w, max_w = VALIDATION_BOUNDS["open_windows"]
    if not (min_w <= windows_open <= max_w):
        raise ValidationError(
            f"Число открытых окон ({windows_open}) вне допустимого диапазона [{min_w}; {max_w}].",
            field="windows_open",
            code=422,
        )

    # Опциональные поля дедупликации пакетов от контроллера ESP32
    boot_id = sanitize_text(payload.get("boot_id", "demo-session"), max_len=32)
    sequence = payload.get("sequence")
    if sequence is not None:
        try:
            sequence = int(sequence)
        except (ValueError, TypeError):
            raise ValidationError("Поле sequence должно быть целым числом.", field="sequence", code=422)

    return {
        "room_id": room_id,
        "online": online,
        "occupied": occupied,
        "computers_on": computers_on,
        "total_pcs": total_pcs,
        "light_on": light_on,
        "windows_open": windows_open,
        "door_open": door_open,
        "temp_c": round(temp_c, 1),
        "boot_id": boot_id,
        "sequence": sequence,
        "computers": payload.get("computers"),
    }


def validate_settings_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Валидация параметров мониторинга и тарифа (требование FR-9, NFR-5)."""
    if not isinstance(payload, dict):
        raise ValidationError("Тело запроса настроек должно быть JSON-объектом.", field="body", code=400)

    try:
        pc_watts = int(payload.get("pc_watts", payload.get("pcWatts", 150)))
        light_watts = int(payload.get("light_watts", payload.get("lightWatts", 120)))
        min_temp_c = float(payload.get("min_temp_c", payload.get("minTemp", 18.0)))
        max_temp_c = float(payload.get("max_temp_c", payload.get("maxTemp", 26.0)))
        tariff_kzt = float(payload.get("tariff_kzt_kwh", payload.get("tariffKzt", 32.50)))
    except (ValueError, TypeError) as exc:
        raise ValidationError(f"Некорректный числовой формат настроек: {exc}", field="settings", code=422)

    for key, val in [
        ("pc_watts", pc_watts),
        ("light_watts", light_watts),
        ("min_temp_c", min_temp_c),
        ("max_temp_c", max_temp_c),
        ("tariff_kzt_kwh", tariff_kzt),
    ]:
        low, high = VALIDATION_BOUNDS[key]
        if math.isnan(val) or not (low <= val <= high):
            raise ValidationError(
                f"Параметр '{key}' ({val}) выходит за допустимые границы [{low}; {high}].",
                field=key,
                code=422,
            )

    if min_temp_c >= max_temp_c:
        raise ValidationError(
            f"Нижний порог температуры ({min_temp_c} °C) должен быть строго меньше верхнего ({max_temp_c} °C).",
            field="min_temp_c",
            code=422,
        )

    return {
        "pc_watts": pc_watts,
        "light_watts": light_watts,
        "min_temp_c": round(min_temp_c, 1),
        "max_temp_c": round(max_temp_c, 1),
        "tariff_kzt_kwh": round(tariff_kzt, 2),
    }


def validate_recommendation_action(payload: Dict[str, Any]) -> Tuple[int, str, str]:
    """Валидация запроса подтверждения или отклонения рекомендации лаборантом (шаги BP-10, GW-4, BP-11)."""
    if not isinstance(payload, dict):
        raise ValidationError("Ожидался JSON-объект.", field="body", code=400)

    try:
        rec_id = int(payload.get("recommendation_id", 0))
    except (ValueError, TypeError):
        raise ValidationError("Некорректный идентификатор recommendation_id.", field="recommendation_id", code=422)

    status = str(payload.get("status", "")).strip()
    if status not in ALLOWED_RECOMMENDATION_STATUSES or status == "new":
        raise ValidationError(
            "Недопустимый целевой статус рекомендации. Допустимы: 'accepted', 'completed', 'rejected'.",
            field="status",
            code=422,
        )

    comment = sanitize_text(payload.get("operator_comment", ""), max_len=250)
    if status == "rejected" and not comment:
        raise ValidationError(
            "При отклонении рекомендации ('rejected') необходимо указать причину в поле operator_comment.",
            field="operator_comment",
            code=422,
        )

    return rec_id, status, comment
