# -*- coding: utf-8 -*-
"""
Модуль проверки и валидации входных данных, санитизации строк от XSS
и контроля ролевого доступа (RBAC) для ИИС «ЭнергоКампус».
"""
import html
import math
import re
from typing import Any, Dict, Tuple
from .config import VALIDATION_BOUNDS, ROLE_TOKENS

ALLOWED_ROOM_IDS = {"201", "202", "204", "301", "302", "305"}
ALLOWED_RECOMMENDATION_STATUSES = {"new", "accepted", "completed", "rejected"}


class ValidationError(Exception):
    """Исключение при нарушении формата или допустимых границ входных данных."""

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


def check_role_permission(token: str, required_perm: str) -> Dict[str, Any]:
    """Проверка токена роли и наличия требуемого разрешения."""
    if not token:
        # В демонстрационном режиме по умолчанию используется профиль Лаборанта,
        # но для административных операций требуется явный токен роли
        if required_perm in ("settings", "adapt_model", "admin"):
            raise ValidationError(
                f"Отказано в доступе: для операции '{required_perm}' требуется авторизация роли Энергетика или Администратора.",
                field="Authorization",
                code=403,
            )
        return ROLE_TOKENS["demo-role-laborant"]

    clean_token = token.replace("Bearer ", "").strip()
    role_info = ROLE_TOKENS.get(clean_token)
    if not role_info:
        raise ValidationError("Недействительный токен учётной записи.", field="Authorization", code=401)
    if required_perm not in role_info["permissions"]:
        raise ValidationError(
            f"Роль '{role_info['role_name']}' не обладает правом '{required_perm}'.",
            field="Authorization",
            code=403,
        )
    return role_info


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
