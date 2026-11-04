
from __future__ import annotations

from typing import Any, Callable, Mapping


class MonitorPipelineError(RuntimeError):
    """Monitoring pipeline failure."""


def run_monitor_checks(
    checks: Mapping[str, Callable[..., Any]],
    check_inputs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Execute registered monitoring checks."""

    results = {}

    for name, function in checks.items():

        if name not in check_inputs:
            results[name] = {
                "status": "skipped",
                "reason": "missing_check_inputs",
            }
            continue

        try:
            results[name] = {
                "status": "success",
                "result": function(**check_inputs[name]),
            }

        except Exception as exc:
            results[name] = {
                "status": "failed",
                "error": str(exc),
            }

    failed = [
        name for name, result in results.items()
        if result["status"] == "failed"
    ]

    return {
        "checks": results,
        "checks_completed": sum(
            result["status"] == "success"
            for result in results.values()
        ),
        "checks_failed": len(failed),
        "failed_checks": failed,
        "overall_status": (
            "warning" if failed else "success"
        ),
    }


def run_p3_monitor_pipeline(
    checks: Mapping[str, Callable[..., Any]],
    check_inputs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Execute P3 monitoring."""

    report = run_monitor_checks(
        checks,
        check_inputs,
    )

    return {
        "stage": "p3_monitor",
        "status": report["overall_status"],
        "report": report,
    }
