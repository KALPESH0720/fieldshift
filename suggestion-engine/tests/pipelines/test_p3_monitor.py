
from unittest.mock import Mock

import pytest

from pipelines.p3_monitor.pipeline import (
    run_monitor_checks,
    run_p3_monitor_pipeline,
)


def test_run_monitor_checks_executes_registered_checks():
    rainfall_check = Mock(return_value={"rainfall_mm": 2200})
    temperature_check = Mock(return_value={"temperature_c": 27.5})

    checks = {
        "rainfall": rainfall_check,
        "temperature": temperature_check,
    }

    inputs = {
        "rainfall": {"threshold": 2000},
        "temperature": {"threshold": 35},
    }

    result = run_monitor_checks(checks, inputs)

    rainfall_check.assert_called_once_with(threshold=2000)
    temperature_check.assert_called_once_with(threshold=35)

    assert result["checks_completed"] == 2
    assert result["checks_failed"] == 0
    assert result["failed_checks"] == []
    assert result["overall_status"] == "success"

    assert result["checks"]["rainfall"] == {
        "status": "success",
        "result": {"rainfall_mm": 2200},
    }


def test_run_monitor_checks_skips_missing_inputs():
    rainfall_check = Mock(return_value=2200)
    temperature_check = Mock(return_value=27.5)

    checks = {
        "rainfall": rainfall_check,
        "temperature": temperature_check,
    }

    inputs = {
        "rainfall": {"threshold": 2000},
    }

    result = run_monitor_checks(checks, inputs)

    rainfall_check.assert_called_once()
    temperature_check.assert_not_called()

    assert result["checks_completed"] == 1
    assert result["checks_failed"] == 0

    assert result["checks"]["temperature"] == {
        "status": "skipped",
        "reason": "missing_check_inputs",
    }

    assert result["overall_status"] == "success"


def test_run_monitor_checks_records_failure_and_continues():
    def failing_check(**kwargs):
        raise ValueError("Invalid rainfall data")

    temperature_check = Mock(return_value=28)

    checks = {
        "rainfall": failing_check,
        "temperature": temperature_check,
    }

    inputs = {
        "rainfall": {"value": 2200},
        "temperature": {"value": 28},
    }

    result = run_monitor_checks(checks, inputs)

    temperature_check.assert_called_once_with(value=28)

    assert result["checks"]["rainfall"] == {
        "status": "failed",
        "error": "Invalid rainfall data",
    }

    assert result["checks"]["temperature"] == {
        "status": "success",
        "result": 28,
    }

    assert result["checks_completed"] == 1
    assert result["checks_failed"] == 1
    assert result["failed_checks"] == ["rainfall"]
    assert result["overall_status"] == "warning"


def test_run_monitor_checks_handles_multiple_failures():
    checks = {
        "rainfall": Mock(side_effect=ValueError("Rainfall error")),
        "temperature": Mock(side_effect=RuntimeError("Temperature error")),
    }

    inputs = {
        "rainfall": {},
        "temperature": {},
    }

    result = run_monitor_checks(checks, inputs)

    assert result["checks_failed"] == 2
    assert set(result["failed_checks"]) == {
        "rainfall",
        "temperature",
    }
    assert result["overall_status"] == "warning"


def test_run_monitor_checks_with_empty_checks():
    result = run_monitor_checks({}, {})

    assert result == {
        "checks": {},
        "checks_completed": 0,
        "checks_failed": 0,
        "failed_checks": [],
        "overall_status": "success",
    }


def test_run_p3_monitor_pipeline_returns_expected_structure():
    checks = {
        "rainfall": Mock(return_value={"alert": False}),
    }

    inputs = {
        "rainfall": {"value": 1800},
    }

    result = run_p3_monitor_pipeline(checks, inputs)

    assert result["stage"] == "p3_monitor"
    assert result["status"] == "success"

    assert result["report"]["checks_completed"] == 1
    assert result["report"]["checks_failed"] == 0
    assert result["report"]["overall_status"] == "success"


def test_run_p3_monitor_pipeline_returns_warning_on_failure():
    checks = {
        "rainfall": Mock(side_effect=ValueError("Bad data")),
    }

    inputs = {
        "rainfall": {"value": 1800},
    }

    result = run_p3_monitor_pipeline(checks, inputs)

    assert result["stage"] == "p3_monitor"
    assert result["status"] == "warning"
    assert result["report"]["checks_failed"] == 1
    assert result["report"]["failed_checks"] == ["rainfall"]


@pytest.mark.parametrize(
    ("checks", "inputs", "expected_completed", "expected_failed"),
    [
        ({}, {}, 0, 0),
        ({"rainfall": Mock(return_value=1)}, {}, 0, 0),
        ({"rainfall": Mock(return_value=1)}, {"rainfall": {}}, 1, 0),
    ],
)
def test_monitor_pipeline_status_counts(
    checks,
    inputs,
    expected_completed,
    expected_failed,
):
    result = run_p3_monitor_pipeline(checks, inputs)

    assert result["report"]["checks_completed"] == expected_completed
    assert result["report"]["checks_failed"] == expected_failed
