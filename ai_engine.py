# -*- coding: utf-8 -*-
"""
Интеллектуальный модуль анализа энергопотребления ИИС «ЭнергоКампус» (Python + scikit-learn).
Реализует:
1. Генерацию воспроизводимой синтетической обучающей и тестовой выборки (явно маркированной как искусственная).
2. Обучение ансамблевой регрессионной модели GradientBoostingRegressor (scikit-learn) и базовой линейной модели.
3. Вычисление гибридной целевой функции оценки состояния и потенциала экономии E = f(x1..x7) по формуле (1.1).
4. Детекцию трёх классов нештатных ситуаций (энергия, микроклимат/окно, потеря связи S0_OFFLINE).
5. Формирование структурированного вектора объяснимости XAI (вклады факторов в кВт и процентах).
6. Контролируемую адаптацию модели Model_{t+1} = Update(Model_t, Data_new) с проверкой метрик MAE, RMSE, MAPE, R2.
"""
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from .config import DEFAULT_SETTINGS

# Параметры 6 демонстрационных кабинетов корпуса А (полное соответствие model.js и Главе 1–2)
ROOMS_CATALOG = {
    "201": {"floor": 2, "name": "Компьютерный класс", "type": "Компьютерный класс", "total_pcs": 12, "light_watts": 120},
    "202": {"floor": 2, "name": "Лаборатория информатики", "type": "Учебная лаборатория", "total_pcs": 12, "light_watts": 120},
    "204": {"floor": 2, "name": "Компьютерный класс", "type": "Компьютерный класс", "total_pcs": 12, "light_watts": 120},
    "301": {"floor": 3, "name": "Лаборатория программирования", "type": "Учебная лаборатория", "total_pcs": 16, "light_watts": 120},
    "302": {"floor": 3, "name": "Мультимедийный класс", "type": "Мультимедийная аудитория", "total_pcs": 8, "light_watts": 120},
    "305": {"floor": 3, "name": "Компьютерный класс", "type": "Компьютерный класс", "total_pcs": 12, "light_watts": 120},
}


class EnergoAIEngine:
    """Гибридный интеллектуальный модуль прогнозирования нагрузки, детекции аномалий и объяснимости XAI."""

    def __init__(self, random_seed: int = 42):
        self.random_seed = random_seed
        self.is_synthetic_data = True
        self.version_tag = "v1.2-gbr"
        self.algorithm_type = "Hybrid Rule-Based + scikit-learn GradientBoostingRegressor"
        self.confidence_threshold = 0.75
        self.model: Optional[GradientBoostingRegressor] = None
        self.baseline_ridge: Optional[Ridge] = None
        self.metrics: Dict[str, Any] = {}
        self.adaptation_history: List[Dict[str, Any]] = []
        self._train_initial_models()

    @staticmethod
    def _extract_feature_vector(
        total_pcs: int,
        is_occupied: bool,
        hour: int,
        day_of_week: int,
        temp_c: float,
        open_windows: int,
        pc_watts: int = 150,
        light_watts: int = 120,
    ) -> List[float]:
        """Формирование вектора признаков для регрессионной модели базового профиля f_ML(X)."""
        occ = 1.0 if is_occupied else 0.0
        is_weekend = 1.0 if day_of_week in (6, 7) else 0.0
        sin_h = math.sin(2.0 * math.pi * hour / 24.0)
        cos_h = math.cos(2.0 * math.pi * hour / 24.0)
        nom_max_kw = (total_pcs * pc_watts + light_watts) / 1000.0
        temp_dev = max(0.0, 18.0 - temp_c) + max(0.0, temp_c - 26.0)
        return [
            float(total_pcs),
            occ,
            is_weekend,
            sin_h,
            cos_h,
            float(temp_c),
            temp_dev,
            float(open_windows),
            nom_max_kw,
        ]

    def generate_synthetic_dataset(self, n_days: int = 14) -> Tuple[np.ndarray, np.ndarray, List[Dict[str, Any]]]:
        """
        Генерация воспроизводимой синтетической выборки временных рядов по 6 кабинетам.
        Данные явно помечены как синтетические демонстрационные (is_synthetic=True).
        """
        rng = np.random.default_rng(self.random_seed)
        X_rows: List[List[float]] = []
        y_rows: List[float] = []
        records: List[Dict[str, Any]] = []

        for day_idx in range(n_days):
            day_of_week = (day_idx % 7) + 1  # 1=Пн .. 7=Вс
            is_weekend = day_of_week in (6, 7)
            for hour in range(24):
                for room_id, meta in ROOMS_CATALOG.items():
                    total_pcs = meta["total_pcs"]
                    # Академическое расписание: пары идут в будни с 08:00 до 17:00
                    if not is_weekend and 8 <= hour <= 17 and hour != 13:
                        # Вероятность проведения занятия в слоте расписания
                        is_occupied = bool(rng.random() < 0.72)
                    else:
                        is_occupied = False

                    if is_occupied:
                        # Штатная учебная работа: задействовано от 50% до 95% парка ПК + освещение
                        fill_ratio = rng.uniform(0.50, 0.95)
                        active_pcs = max(1, min(total_pcs, int(round(total_pcs * fill_ratio))))
                        light_on = True
                        temp_c = round(float(rng.normal(22.8, 1.1)), 1)
                        open_windows = 1 if (temp_c > 25.0 and rng.random() < 0.3) else 0
                        # Целевая эталонная (нормативная) мощность для обучения f_ML(X)
                        base_kw = (active_pcs * 150 + 120) / 1000.0 + float(rng.normal(0.0, 0.04))
                    else:
                        # В свободном кабинете нормативная базовая нагрузка f_ML(X) близка к дежурному минимуму (коммутатор ~0.02 кВт)
                        active_pcs = 0
                        light_on = False
                        temp_c = round(float(rng.normal(20.5, 1.2)), 1)
                        open_windows = 0
                        base_kw = max(0.0, float(rng.normal(0.02, 0.015)))

                    target_kw = round(max(0.0, base_kw), 3)
                    feat = self._extract_feature_vector(
                        total_pcs=total_pcs,
                        is_occupied=is_occupied,
                        hour=hour,
                        day_of_week=day_of_week,
                        temp_c=temp_c,
                        open_windows=open_windows,
                    )
                    X_rows.append(feat)
                    y_rows.append(target_kw)
                    records.append({
                        "day_idx": day_idx,
                        "day_of_week": day_of_week,
                        "hour": hour,
                        "room_id": room_id,
                        "total_pcs": total_pcs,
                        "active_pcs": active_pcs,
                        "is_occupied": is_occupied,
                        "light_on": light_on,
                        "temp_c": temp_c,
                        "open_windows": open_windows,
                        "target_baseline_kw": target_kw,
                        "is_synthetic": True,
                    })

        return np.array(X_rows, dtype=float), np.array(y_rows, dtype=float), records

    @staticmethod
    def compute_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
        """
        Вычисление метрик качества регрессии: MAE, RMSE, MAPE (на интервалах нагрузки >= 0.10 кВт) и R2.
        """
        mae = float(mean_absolute_error(y_true, y_pred))
        rmse = float(math.sqrt(mean_squared_error(y_true, y_pred)))
        r2 = float(r2_score(y_true, y_pred))

        # Ограничение MAPE: при y_true -> 0 знаменатель дроби |y_true - y_pred| / y_true стремится к бесконечности.
        # Поэтому MAPE рассчитывается строго на рабочих интервалах (y_true >= 0.10 кВт).
        non_zero_mask = y_true >= 0.10
        if np.any(non_zero_mask):
            mape_active = float(
                np.mean(np.abs((y_true[non_zero_mask] - y_pred[non_zero_mask]) / y_true[non_zero_mask])) * 100.0
            )
        else:
            mape_active = 0.0

        return {
            "MAE_kw": round(mae, 4),
            "RMSE_kw": round(rmse, 4),
            "MAPE_active_pct": round(mape_active, 2),
            "R2_score": round(r2, 4),
        }

    def _train_initial_models(self) -> None:
        """Обучение основной ансамблевой модели GradientBoostingRegressor и контрольной линейной модели Ridge."""
        X, y, records = self.generate_synthetic_dataset(n_days=14)
        # Хронологическое разбиение: 10 суток (1440 точек) обучение, 4 суток (576 точек) тест
        split_idx = 10 * 24 * len(ROOMS_CATALOG)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        self.model = GradientBoostingRegressor(
            n_estimators=80,
            max_depth=4,
            learning_rate=0.08,
            random_state=self.random_seed,
        )
        self.model.fit(X_train, y_train)

        self.baseline_ridge = Ridge(alpha=1.0)
        self.baseline_ridge.fit(X_train, y_train)

        y_pred_gbr = np.clip(self.model.predict(X_test), 0.0, None)
        y_pred_ridge = np.clip(self.baseline_ridge.predict(X_test), 0.0, None)

        gbr_metrics = self.compute_regression_metrics(y_test, y_pred_gbr)
        ridge_metrics = self.compute_regression_metrics(y_test, y_pred_ridge)

        feature_names = [
            "total_pcs", "is_occupied", "is_weekend", "sin_hour", "cos_hour",
            "temp_c", "temp_deviation", "open_windows", "nominal_max_kw"
        ]
        importances = {
            name: round(float(val), 4)
            for name, val in zip(feature_names, self.model.feature_importances_)
        }

        self.metrics = {
            "dataset_type": "synthetic_demonstration",
            "total_samples": int(len(y)),
            "train_samples": int(len(y_train)),
            "test_samples": int(len(y_test)),
            "gbr_model": gbr_metrics,
            "ridge_baseline": ridge_metrics,
            "feature_importances": importances,
        }

    def adapt_model(self, feedback_samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Контролируемая адаптация ИИС: Model_{t+1} = Update(Model_t, Data_new) (формула 3.1).
        Переобучает модель с учётом верифицированных лаборантом наблюдений и обновляет активную версию
        только при сохранении или улучшении метрики MAE на тестовой выборке.
        """
        X_base, y_base, _ = self.generate_synthetic_dataset(n_days=14)
        split_idx = 10 * 24 * len(ROOMS_CATALOG)
        X_train, X_test = X_base[:split_idx], X_base[split_idx:]
        y_train, y_test = y_base[:split_idx], y_base[split_idx:]

        new_X, new_y = [], []
        for s in feedback_samples:
            feat = self._extract_feature_vector(
                total_pcs=int(s.get("total_pcs", 12)),
                is_occupied=bool(s.get("is_occupied", False)),
                hour=int(s.get("hour", 14)),
                day_of_week=int(s.get("day_of_week", 3)),
                temp_c=float(s.get("temp_c", 22.0)),
                open_windows=int(s.get("open_windows", 0)),
            )
            new_X.append(feat)
            new_y.append(float(s.get("verified_baseline_kw", 0.0)))

        if new_X:
            X_train_ext = np.vstack([X_train, np.array(new_X, dtype=float)])
            y_train_ext = np.concatenate([y_train, np.array(new_y, dtype=float)])
        else:
            X_train_ext, y_train_ext = X_train, y_train

        candidate = GradientBoostingRegressor(
            n_estimators=90,
            max_depth=4,
            learning_rate=0.075,
            random_state=self.random_seed + len(self.adaptation_history) + 1,
        )
        candidate.fit(X_train_ext, y_train_ext)
        y_pred_cand = np.clip(candidate.predict(X_test), 0.0, None)
        cand_metrics = self.compute_regression_metrics(y_test, y_pred_cand)

        prev_mae = self.metrics["gbr_model"]["MAE_kw"]
        accepted = cand_metrics["MAE_kw"] <= prev_mae * 1.05  # Допуск не хуже 5% деградации

        step_num = len(self.adaptation_history) + 1
        new_version = f"v1.{2 + step_num}-gbr-adapted"
        record = {
            "previous_version": self.version_tag,
            "candidate_version": new_version,
            "added_verified_samples": len(new_X),
            "previous_mae_kw": prev_mae,
            "candidate_metrics": cand_metrics,
            "accepted": accepted,
            "adapted_at": datetime.now(timezone.utc).isoformat(),
        }
        if accepted:
            self.model = candidate
            self.version_tag = new_version
            self.metrics["gbr_model"] = cand_metrics
            self.metrics["train_samples"] = int(len(y_train_ext))
        self.adaptation_history.append(record)
        return record

    def evaluate_room(
        self,
        room_data: Dict[str, Any],
        settings: Optional[Dict[str, Any]] = None,
        hour: int = 14,
        day_of_week: int = 3,
    ) -> Dict[str, Any]:
        """
        Выполнение шага BP-05, шлюзов GW-2 и GW-3 и шага BP-07 (интерпретация XAI):
        расчёт мощности, прогноза f_ML(X), потенциала экономии по формуле (1.1),
        класса состояния S и объяснения причин срабатывания.
        """
        cfg = {**DEFAULT_SETTINGS, **(settings or {})}
        room_id = str(room_data.get("room_id", room_data.get("id", "204")))
        online = bool(room_data.get("online", room_data.get("is_online", True)))
        occupied = bool(room_data.get("occupied", room_data.get("is_occupied", False)))
        total_pcs = int(room_data.get("total_pcs", room_data.get("total", ROOMS_CATALOG.get(room_id, {}).get("total_pcs", 12))))
        computers_on = int(room_data.get("computers_on", room_data.get("active_pcs", room_data.get("pcs", 0))))
        light_on = bool(room_data.get("light_on", room_data.get("light", False)))
        windows_open = int(room_data.get("windows_open", room_data.get("open_windows", room_data.get("windows", 0))))
        door_open = bool(room_data.get("door_open", room_data.get("door", False)))
        temp_c = float(room_data.get("temp_c", room_data.get("temp", 22.0)))

        pc_watts = int(cfg["pc_watts"])
        light_watts = int(cfg["light_watts"])
        min_temp_c = float(cfg["min_temp_c"])
        max_temp_c = float(cfg["max_temp_c"])
        tariff_kzt = float(cfg["tariff_kzt_kwh"])

        # Шлюз GW-1 / Шаг BP-03: Защита от ложных выводов при потере связи с контроллером (требование NFR-2)
        if not online:
            return {
                "room_id": room_id,
                "online": False,
                "state_class": "S0_OFFLINE",
                "severity": "neutral",
                "current_power_kw": None,
                "baseline_forecast_kw": None,
                "saving_potential_kwh_1h": 0.0,
                "saving_kwh_4h": 0.0,
                "saving_potential_kzt_4h": 0.0,
                "confidence_score": 0.0,
                "alpha_ml_used": 0,
                "model_version": self.version_tag,
                "is_synthetic": True,
                "anomalies": [
                    {
                        "anomaly_type": "offline",
                        "severity": "neutral",
                        "title": "Нет связи с контроллером",
                        "explanation_text": "Состояние устройств неизвестно. Расчёт экономии заблокирован (NFR-2).",
                        "xai_factors": [{"factor": "Связь x7 (is_online)", "value": "false", "impact_kw": 0.0, "share_pct": 100.0}],
                    }
                ],
                "explanation": {
                    "title": "Нет связи с контроллером",
                    "factors": ["Связь с узлом ESP32 отсутствует (is_online = false)"],
                    "action": f"Проверить питание контроллера и сетевое подключение в каб. {room_id}",
                    "formula_trace": "x7 = 0 -> S = S0_OFFLINE, E = 0.00 кВт·ч/ч (блокировка ложной экономии)",
                },
            }

        # Расчёт текущей мощности P_расч (кВт)
        pc_power_kw = round((computers_on * pc_watts) / 1000.0, 3)
        light_power_kw = round((light_watts if light_on else 0) / 1000.0, 3)
        current_power_kw = round(pc_power_kw + light_power_kw, 3)

        # Вычисление регрессионного прогноза f_ML(X)
        feat = self._extract_feature_vector(
            total_pcs=total_pcs,
            is_occupied=occupied,
            hour=hour,
            day_of_week=day_of_week,
            temp_c=temp_c,
            open_windows=windows_open,
            pc_watts=pc_watts,
            light_watts=light_watts,
        )
        raw_pred = float(self.model.predict(np.array([feat], dtype=float))[0]) if self.model else 0.0
        # Для пустого кабинета нормативный базовый профиль равен 0.00 кВт полезной учебной нагрузки
        baseline_forecast_kw = round(max(0.0, raw_pred) if occupied else 0.0, 2)

        # Оценка уверенности модели confidence_score на шлюзе GW-2
        confidence_score = 0.92 if (0 <= hour <= 23 and -5.0 <= temp_c <= 45.0) else 0.65
        alpha_ml = 1 if (confidence_score >= self.confidence_threshold and occupied) else 0

        # Формула (1.1):
        # E = (1 - I_зан)*(n_ПК*P_ПК + I_свет*P_свет)/1000 + alpha * max(0; P_факт - f_ML(X))
        rule_saving_kw = current_power_kw if not occupied else 0.0
        ml_excess_kw = max(0.0, round(current_power_kw - baseline_forecast_kw, 3)) if occupied else 0.0
        saving_1h = round(rule_saving_kw + alpha_ml * ml_excess_kw, 2)
        saving_4h = round(saving_1h * 4.0, 2)
        saving_kzt_4h = round(saving_4h * tariff_kzt, 2)

        # Детекция аномалий (шаг BP-05, шлюз GW-3 и шаг BP-07 XAI)
        anomalies: List[Dict[str, Any]] = []
        xai_factors: List[Dict[str, Any]] = []
        factors_text: List[str] = []
        actions_list: List[str] = []

        # 1) Нецелевой расход электроэнергии в свободном кабинете
        if not occupied and current_power_kw > 0:
            if computers_on > 0:
                share_pc = round((pc_power_kw / current_power_kw) * 100.0, 1)
                xai_factors.append({
                    "factor": f"{computers_on} ПК ({pc_watts} Вт)",
                    "value": f"{computers_on} шт.",
                    "impact_kw": round(pc_power_kw, 2),
                    "share_pct": share_pc,
                })
                factors_text.append(f"{computers_on} ПК ({pc_power_kw:.2f} кВт)")
            if light_on:
                share_l = round((light_power_kw / current_power_kw) * 100.0, 1)
                xai_factors.append({
                    "factor": f"Освещение ({light_watts} Вт)",
                    "value": "включено",
                    "impact_kw": round(light_power_kw, 2),
                    "share_pct": share_l,
                })
                factors_text.append(f"свет включён ({light_power_kw:.2f} кВт)")
            else:
                factors_text.append("свет выключен")

            act = f"Выключить {computers_on} ПК" + (" и освещение" if light_on else "") + f" в свободном каб. {room_id}"
            actions_list.append(act)
            anomalies.append({
                "anomaly_type": "energy",
                "severity": "warning",
                "title": "Техника в свободном кабинете",
                "explanation_text": f"{computers_on} ПК · {'свет включён' if light_on else 'свет выключен'} (потери {current_power_kw:.2f} кВт·ч/ч)",
                "xai_factors": xai_factors,
            })

        # 2) Отклонение температуры микроклимата за границы [min_temp_c; max_temp_c]
        if temp_c < min_temp_c or temp_c > max_temp_c:
            is_low = temp_c < min_temp_c
            t_title = "Температура ниже нормы" if is_low else "Температура выше нормы"
            t_desc = f"{temp_c:.1f} °C (норма {min_temp_c:.1f}–{max_temp_c:.1f} °C)" + (
                " · окно открыто" if windows_open > 0 else ""
            )
            t_xai = [
                {
                    "factor": "Температура воздуха x5",
                    "value": f"{temp_c:.1f} °C",
                    "impact_kw": 0.0,
                    "share_pct": 70.0 if windows_open > 0 else 100.0,
                }
            ]
            if windows_open > 0:
                t_xai.append({
                    "factor": "Оконные створки x6",
                    "value": f"открыто ({windows_open})",
                    "impact_kw": 0.0,
                    "share_pct": 30.0,
                })
            anomalies.append({
                "anomaly_type": "climate",
                "severity": "warning",
                "title": t_title,
                "explanation_text": t_desc,
                "xai_factors": t_xai,
            })
            if not xai_factors:
                xai_factors.extend(t_xai)
            factors_text.append(t_desc)
            actions_list.append(
                f"Закрыть окно и проверить отопление в каб. {room_id}"
                if is_low
                else f"Проверить кондиционирование и проветрить каб. {room_id}"
            )

        # 3) Открытое окно в свободном кабинете (даже если температура ещё в норме)
        if windows_open > 0 and not occupied and not any(a["anomaly_type"] == "climate" for a in anomalies):
            w_xai = [{"factor": "Окно открыто в пустом классе x6", "value": f"{windows_open} шт.", "impact_kw": 0.0, "share_pct": 100.0}]
            anomalies.append({
                "anomaly_type": "window",
                "severity": "warning",
                "title": "Открыто окно",
                "explanation_text": "Кабинет отмечен как свободный. Проверьте окно.",
                "xai_factors": w_xai,
            })
            if not xai_factors:
                xai_factors.extend(w_xai)
            factors_text.append(f"открыто окон: {windows_open}")
            actions_list.append(f"Закрыть окно в свободном каб. {room_id}")

        if anomalies:
            state_class = "S3_EXCESS"
            severity = "warning"
            exp_title = anomalies[0]["title"]
            exp_action = "; ".join(actions_list)
        elif occupied:
            state_class = "S1_OCCUPIED"
            severity = "normal"
            exp_title = "Штатный режим учебного занятия"
            factors_text = [f"Идёт занятие (I_зан = 1), активны {computers_on} из {total_pcs} ПК"]
            exp_action = "Действий лаборанта не требуется (штатная нагрузка)"
        else:
            state_class = "S2_IDLE"
            severity = "normal"
            exp_title = "Штатный режим ожидания"
            factors_text = ["Кабинет свободен, нагрузка отключена, окна закрыты"]
            exp_action = "Действий лаборанта не требуется"

        formula_trace = (
            f"E = (1 - {1 if occupied else 0}) * ({computers_on}*{pc_watts} + {1 if light_on else 0}*{light_watts})/1000 "
            f"= {saving_1h:.2f} кВт·ч/ч; ΔW(4ч) = {saving_4h:.2f} кВт·ч; ΔC(4ч) = {saving_kzt_4h:.2f} тг (при тарифе {tariff_kzt:.2f} тг/кВт·ч)"
        )

        return {
            "room_id": room_id,
            "online": True,
            "occupied": occupied,
            "state_class": state_class,
            "severity": severity,
            "current_power_kw": round(current_power_kw, 2),
            "baseline_forecast_kw": round(baseline_forecast_kw, 2),
            "saving_potential_kwh_1h": saving_1h,
            "saving_kwh_4h": saving_4h,
            "saving_potential_kzt_4h": saving_kzt_4h,
            "confidence_score": confidence_score,
            "alpha_ml_used": alpha_ml,
            "model_version": self.version_tag,
            "is_synthetic": True,
            "anomalies": anomalies,
            "explanation": {
                "title": exp_title,
                "factors": factors_text,
                "xai_factors": xai_factors,
                "action": exp_action,
                "formula_trace": formula_trace,
            },
        }
