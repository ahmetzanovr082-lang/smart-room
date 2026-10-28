# -*- coding: utf-8 -*-
"""
Сервер приложений и REST API ИИС «ЭнергоКампус» (Модуль 3).
Объединяет:
- раздачу статических файлов веб-интерфейса (index.html, styles.css, model.js, app.js, favicon.svg);
- REST API (/api/v1/*) с единым JSON-форматом ответов и кодов ошибок (200, 400, 401, 403, 404, 409, 422, 500);
- интеграцию с реляционной БД из 14 таблиц (DatabaseManager) и гибридным ИИ-модулем (EnergoAIEngine).
"""
import json
import mimetypes
import os
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from .ai_engine import EnergoAIEngine
from .config import BASE_DIR, DB_PATH, HOST as DEFAULT_HOST, PORT as DEFAULT_PORT, verify_role_password
from .db_manager import DatabaseManager
from .validators import (
    ValidationError,
    check_role_permission,
    issue_role_session_token,
    sanitize_text,
    validate_recommendation_action,
    validate_settings_payload,
    validate_telemetry_payload,
)


class EnergoCampusApplication:
    """Ядро серверного приложения ИИС «ЭнергоКампус» (может вызываться напрямую из тестов и через HTTP)."""

    def __init__(self, db_path: str = DB_PATH):
        self.ai_engine = EnergoAIEngine(random_seed=42)
        self.db = DatabaseManager(db_path=db_path, ai_engine=self.ai_engine)

    def dispatch(
        self,
        method: str,
        path: str,
        query_params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, Dict[str, Any]]:
        """Маршрутизация API-запросов с централизованной обработкой ошибок и проверкой RBAC."""
        q = query_params or {}
        hdrs = {k.lower(): v for k, v in (headers or {}).items()}
        auth_token = hdrs.get("authorization", hdrs.get("x-role-token", ""))

        try:
            if method == "GET" and path == "/api/v1/health":
                check_role_permission(auth_token, "read")
                return 200, {
                    "status": "ok",
                    "service": "EnergoCampus IIS REST API",
                    "model_version": self.ai_engine.version_tag,
                    "is_synthetic_data": True,
                    "metrics": self.ai_engine.metrics,
                }

            if method == "GET" and path == "/api/v1/state":
                check_role_permission(auth_token, "read")
                return 200, {
                    "status": "ok",
                    "data": self.db.get_all_rooms_state(),
                }

            if method == "GET" and path == "/api/v1/rooms":
                check_role_permission(auth_token, "read")
                st = self.db.get_all_rooms_state()
                rooms = st["rooms"]
                floor_f = q.get("floor", "all")
                search_q = sanitize_text(q.get("query", ""), max_len=64).lower()
                if floor_f != "all":
                    try:
                        fl_num = int(floor_f)
                        rooms = [r for r in rooms if r["floor"] == fl_num]
                    except ValueError:
                        raise ValidationError("Параметр floor должен быть числом или 'all'.", field="floor", code=422)
                if search_q:
                    rooms = [
                        r for r in rooms
                        if search_q in f"{r['id']} {r['name']}".lower()
                    ]
                return 200, {
                    "status": "ok",
                    "count": len(rooms),
                    "rooms": rooms,
                }

            if method == "GET" and path == "/api/v1/analytics":
                check_role_permission(auth_token, "read")
                room_id = str(q.get("room_id", "all")).strip()
                horizon = str(q.get("horizon", "day_24h")).strip()
                series = self.db.get_analytics_series(room_id=room_id, horizon=horizon)
                return 200, {
                    "status": "ok",
                    "analytics": series,
                }

            if method == "POST" and path == "/api/v1/ai/evaluate":
                check_role_permission(auth_token, "read")
                validated = validate_telemetry_payload(body or {})
                eval_res = self.ai_engine.evaluate_room(validated)
                return 200, {
                    "status": "ok",
                    "evaluation": eval_res,
                }

            if method == "POST" and path == "/api/v1/telemetry":
                check_role_permission(auth_token, "simulate")
                validated = validate_telemetry_payload(body or {})
                note = sanitize_text((body or {}).get("event_note", ""), max_len=200)
                eval_res = self.db.process_telemetry_and_evaluate(validated, event_note=note or None)
                return 200, {
                    "status": "ok",
                    "evaluation": eval_res,
                    "state": self.db.get_all_rooms_state(),
                }

            if method == "POST" and path == "/api/v1/recommendations/action":
                role_info = check_role_permission(auth_token, "recommend_action")
                rec_id, new_status, comment = validate_recommendation_action(body or {})
                updated_rec = self.db.update_recommendation_status(
                    recommendation_id=rec_id,
                    new_status=new_status,
                    operator_comment=comment,
                    user_id=role_info["user_id"],
                )
                return 200, {
                    "status": "ok",
                    "recommendation": updated_rec,
                    "state": self.db.get_all_rooms_state(),
                }

            if method == "POST" and path == "/api/v1/settings":
                # Для изменения уставок и тарифа требуется роль Энергетика или Администратора
                effective_token = auth_token or (body or {}).get("role_token", "")
                role_info = check_role_permission(effective_token, "settings")
                validated_cfg = validate_settings_payload(body or {})
                saved_cfg = self.db.update_settings(validated_cfg, user_id=role_info["user_id"])
                return 200, {
                    "status": "ok",
                    "settings": saved_cfg,
                    "state": self.db.get_all_rooms_state(),
                }

            if method == "POST" and path == "/api/v1/ai/adapt":
                effective_token = auth_token or (body or {}).get("role_token", "")
                check_role_permission(effective_token, "adapt_model")
                samples = (body or {}).get("feedback_samples", [])
                if not isinstance(samples, list):
                    raise ValidationError("Поле feedback_samples должно быть списком.", field="feedback_samples", code=422)
                adapt_report = self.ai_engine.adapt_model(samples)
                return 200, {
                    "status": "ok",
                    "adaptation": adapt_report,
                }

            if method == "POST" and path == "/api/v1/reset":
                check_role_permission(auth_token, "admin")
                self.db.init_database(force_reset=True)
                self.db._dedup_cache.clear()
                return 200, {
                    "status": "ok",
                    "message": "База данных и состояние демонстрации сброшены к исходным значениям.",
                    "state": self.db.get_all_rooms_state(),
                }

            if method == "GET" and path == "/api/v1/database/tables":
                check_role_permission(auth_token, "settings")
                return 200, {
                    "status": "ok",
                    "tables": self.db.get_database_tables_summary(),
                }

            if method == "GET" and path == "/api/v1/database/table":
                check_role_permission(auth_token, "settings")
                tbl_name = str(q.get("name", q.get("table", "rooms"))).strip()
                try:
                    limit_val = int(q.get("limit", 50))
                except ValueError:
                    limit_val = 50
                return 200, {
                    "status": "ok",
                    "data": self.db.get_table_data(tbl_name, limit=limit_val),
                }

            if method == "POST" and path == "/api/v1/database/query":
                check_role_permission(auth_token, "admin")
                query_str = (body or {}).get("query", "")
                res = self.db.execute_sql_query(query_str)
                return 200, res

            if method == "POST" and path == "/api/v1/database/scenario":
                sc_name = str((body or {}).get("scenario", "")).strip().lower()
                if sc_name == "seed_reset":
                    check_role_permission(auth_token, "admin")
                elif sc_name == "set_tariff":
                    check_role_permission(auth_token, "settings")
                else:
                    check_role_permission(auth_token, "simulate")
                res = self.db.execute_scenario(sc_name, params=body or {})
                res["state"] = self.db.get_all_rooms_state()
                return 200, res

            if method == "POST" and path == "/api/v1/database/update_row":
                role_info = check_role_permission(auth_token, "settings")
                b = body or {}
                tbl = str(b.get("table", "")).strip()
                pk_c = str(b.get("pk_column", "")).strip()
                pk_v = b.get("pk_value")
                vals = b.get("values", {})
                res = self.db.update_table_row(
                    table_name=tbl,
                    pk_column=pk_c,
                    pk_value=pk_v,
                    values=vals,
                    user_id=role_info["user_id"],
                )
                res["state"] = self.db.get_all_rooms_state()
                return 200, res

            if method == "POST" and path == "/api/v1/auth/role":
                b = body or {}
                req_role = str(b.get("role", "laborant")).strip().lower()
                pwd = str(b.get("password", "")).strip()
                if req_role in ("energomanager", "sysadmin", "energy_chief", "sys_admin"):
                    if not verify_role_password(req_role, pwd):
                        return 401, {
                            "status": "error",
                            "code": 401,
                            "message": "Неверный пароль доступа для выбранной привилегированной роли.",
                        }
                    session_token, role_info = issue_role_session_token(req_role)
                    return 200, {
                        "status": "ok",
                        "token": session_token,
                        "role": role_info,
                        "message": f"Доступ разрешён: {role_info['role_name']}",
                    }
                else:
                    session_token, role_info = issue_role_session_token("laborant")
                    return 200, {
                        "status": "ok",
                        "token": session_token,
                        "role": role_info,
                        "message": "Профиль лаборанта активен.",
                    }

            return 404, {
                "status": "error",
                "code": 404,
                "message": f"Маршрут {method} {path} не найден.",
            }

        except ValidationError as verr:
            return verr.code, {
                "status": "error",
                "code": verr.code,
                "field": verr.field,
                "message": verr.message,
            }
        except Exception as exc:
            traceback.print_exc()
            return 500, {
                "status": "error",
                "code": 500,
                "message": f"Внутренняя ошибка сервера: {sanitize_text(str(exc), 200)}",
            }


def create_http_handler(app_instance: EnergoCampusApplication):
    """Фабрика HTTP-обработчика для ThreadingHTTPServer."""

    class EnergoHTTPRequestHandler(BaseHTTPRequestHandler):
        def _send_json(self, status_code: int, payload: Dict[str, Any]) -> None:
            body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body_bytes)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Role-Token")
            self.end_headers()
            self.wfile.write(body_bytes)

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Role-Token")
            self.end_headers()

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/"):
                q_raw = parse_qs(parsed.query)
                q_flat = {k: v[0] for k, v in q_raw.items() if v}
                hdrs = {k: v for k, v in self.headers.items()}
                code, resp = app_instance.dispatch("GET", parsed.path, query_params=q_flat, headers=hdrs)
                self._send_json(code, resp)
                return

            # Раздача статических файлов клиентского приложения (SPA)
            rel_path = "index.html" if parsed.path in ("/", "") else parsed.path.lstrip("/")
            safe_path = os.path.normpath(os.path.join(BASE_DIR, rel_path))
            if not safe_path.startswith(os.path.normpath(BASE_DIR)) or not os.path.isfile(safe_path):
                self._send_json(404, {"status": "error", "code": 404, "message": "Файл не найден"})
                return

            mime_type, _ = mimetypes.guess_type(safe_path)
            with open(safe_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", f"{mime_type or 'application/octet-stream'}; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            try:
                body_obj = json.loads(raw_body) if raw_body.strip() else {}
            except json.JSONDecodeError:
                self._send_json(400, {"status": "error", "code": 400, "message": "Некорректный синтаксис JSON в теле запроса."})
                return

            hdrs = {k: v for k, v in self.headers.items()}
            code, resp = app_instance.dispatch("POST", parsed.path, body=body_obj, headers=hdrs)
            self._send_json(code, resp)

        def log_message(self, fmt: str, *args: Any) -> None:
            # Лаконичное логирование запросов
            pass

    return EnergoHTTPRequestHandler


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    app = EnergoCampusApplication()
    handler_cls = create_http_handler(app)
    httpd = ThreadingHTTPServer((host, port), handler_cls)
    print(f"[ЭнергоКампус] Сервер ИИС запущен: http://{host}:{port}")
    print(f"[ЭнергоКампус] Реляционная БД (14 таблиц): {DB_PATH}")
    print(f"[ЭнергоКампус] Активная модель ИИ: {app.ai_engine.version_tag} ({app.ai_engine.algorithm_type})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[ЭнергоКампус] Остановка сервера...")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
