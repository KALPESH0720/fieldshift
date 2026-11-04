"""
FieldShift Anomaly Detection Module.

Detects unusual weather, vegetation and soil observations using
statistical thresholds and rolling historical baselines.

This module identifies data anomalies and agricultural risk signals.
It does not independently diagnose crop disease.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from math import isfinite
from statistics import mean, pstdev
from typing import Any, Mapping, Sequence


class AnomalyDetectionError(ValueError):
    """Raised when anomaly detection inputs are invalid."""


@dataclass(frozen=True)
class Anomaly:
    variable: str
    observed_value: float
    expected_value: float
    deviation: float
    severity: str
    anomaly_type: str
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _validate_values(values: Sequence[float], name: str) -> list[float]:
    result = []

    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise AnomalyDetectionError(
                f"{name} contains a non-numeric value."
            ) from exc

        if not isfinite(number):
            raise AnomalyDetectionError(
                f"{name} contains a non-finite value."
            )

        result.append(number)

    return result


def calculate_z_score(
    observed_value: float,
    historical_values: Sequence[float],
) -> float | None:
    """
    Calculate a z-score against historical observations.

    Returns None if historical variability is zero or history is empty.
    """

    history = _validate_values(
        historical_values, "historical_values"
    )

    if not history:
        return None

    observed = float(observed_value)

    if not isfinite(observed):
        raise AnomalyDetectionError(
            "Observed value must be finite."
        )

    historical_mean = mean(history)
    standard_deviation = pstdev(history)

    if standard_deviation == 0:
        return None

    return round(
        (observed - historical_mean) / standard_deviation,
        4
    )


def classify_severity(
    z_score: float,
    warning_threshold: float = 2.0,
    critical_threshold: float = 3.0,
) -> str:
    """Classify anomaly severity using absolute z-score."""

    if warning_threshold <= 0:
        raise AnomalyDetectionError(
            "Warning threshold must be positive."
        )

    if critical_threshold <= warning_threshold:
        raise AnomalyDetectionError(
            "Critical threshold must exceed warning threshold."
        )

    magnitude = abs(z_score)

    if magnitude >= critical_threshold:
        return "critical"

    if magnitude >= warning_threshold:
        return "warning"

    return "normal"


def detect_statistical_anomaly(
    variable: str,
    observed_value: float,
    historical_values: Sequence[float],
    warning_threshold: float = 2.0,
    critical_threshold: float = 3.0,
) -> dict[str, Any]:
    """
    Detect an anomaly relative to a historical baseline.

    Requires sufficient historical observations for meaningful
    interpretation. The thresholds are configurable.
    """

    history = _validate_values(
        historical_values, "historical_values"
    )

    if len(history) < 5:
        return {
            "variable": variable,
            "status": "insufficient_history",
            "observed_value": observed_value,
            "history_count": len(history),
            "anomaly": None,
        }

    observed = float(observed_value)

    if not isfinite(observed):
        raise AnomalyDetectionError(
            "Observed value must be finite."
        )

    baseline = mean(history)
    z_score = calculate_z_score(observed, history)

    if z_score is None:
        return {
            "variable": variable,
            "status": "constant_baseline",
            "observed_value": observed,
            "expected_value": baseline,
            "anomaly": None,
        }

    severity = classify_severity(
        z_score,
        warning_threshold,
        critical_threshold,
    )

    anomaly = Anomaly(
        variable=variable,
        observed_value=round(observed, 4),
        expected_value=round(baseline, 4),
        deviation=round(observed - baseline, 4),
        severity=severity,
        anomaly_type=(
            "high_anomaly" if z_score > 0
            else "low_anomaly"
        ),
        explanation=(
            f"{variable} is {abs(z_score):.2f} standard deviations "
            f"from its historical mean."
        ),
    )

    return {
        "variable": variable,
        "status": severity,
        "z_score": z_score,
        "history_count": len(history),
        "anomaly": anomaly.to_dict(),
    }


def detect_weather_anomalies(
    current_weather: Mapping[str, float],
    historical_weather: Mapping[str, Sequence[float]],
) -> list[dict[str, Any]]:
    """
    Detect anomalies in temperature and rainfall.

    Example variable names:
        temperature_c
        rainfall_mm
        humidity_pct
    """

    results = []

    for variable, observed in current_weather.items():

        if variable not in historical_weather:
            continue

        result = detect_statistical_anomaly(
            variable=variable,
            observed_value=observed,
            historical_values=historical_weather[variable],
        )

        results.append(result)

    return results


def detect_ndvi_anomaly(
    current_ndvi: float,
    historical_ndvi: Sequence[float],
) -> dict[str, Any]:
    """
    Detect unusually low or high NDVI relative to history.

    Low NDVI can indicate vegetation stress, but interpretation
    depends on crop stage, cloud contamination and season.
    """

    if not -1 <= current_ndvi <= 1:
        raise AnomalyDetectionError(
            "NDVI must be between -1 and 1."
        )

    result = detect_statistical_anomaly(
        variable="ndvi",
        observed_value=current_ndvi,
        historical_values=historical_ndvi,
    )

    if result.get("anomaly"):
        result["agricultural_interpretation"] = (
            "An unusual vegetation signal detected. "
            "Check crop stage, cloud quality and field conditions."
        )

    return result


def detect_soil_anomalies(
    current_soil: Mapping[str, float],
    historical_soil: Mapping[str, Sequence[float]],
) -> list[dict[str, Any]]:
    """Detect unusual soil observations against historical values."""

    results = []

    for variable, observed in current_soil.items():

        if variable not in historical_soil:
            continue

        results.append(
            detect_statistical_anomaly(
                variable=variable,
                observed_value=observed,
                historical_values=historical_soil[variable],
            )
        )

    return results


def detect_all_anomalies(
    weather=None,
    historical_weather=None,
    current_ndvi=None,
    historical_ndvi=None,
    soil=None,
    historical_soil=None,
) -> dict[str, Any]:
    """Combine weather, NDVI and soil anomaly results."""

    weather_results = (
        detect_weather_anomalies(
            weather, historical_weather
        )
        if weather and historical_weather
        else []
    )

    ndvi_result = (
        detect_ndvi_anomaly(
            current_ndvi, historical_ndvi
        )
        if current_ndvi is not None and historical_ndvi
        else None
    )

    soil_results = (
        detect_soil_anomalies(
            soil, historical_soil
        )
        if soil and historical_soil
        else []
    )

    return {
        "weather_anomalies": weather_results,
        "ndvi_anomaly": ndvi_result,
        "soil_anomalies": soil_results,
        "monitoring_status": "completed",
    }