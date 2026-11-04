"""
FieldShift WOFOST Integration Adapter.

Provides a structured interface for connecting a genuine
WOFOST crop growth simulation backend.
"""

from dataclasses import dataclass, asdict
from typing import Any, Callable, Mapping


class WofostConfigurationError(RuntimeError):
    """WOFOST backend configuration error."""


@dataclass(frozen=True)
class WofostRequest:

    crop: str

    start_date: str

    end_date: str

    weather: Mapping[str, Any]

    soil: Mapping[str, Any]

    crop_parameters: Mapping[str, Any]

    management: Mapping[str, Any]

    def validate(self):

        if not self.crop.strip():
            raise ValueError("Crop name is required.")

        if not self.start_date or not self.end_date:
            raise ValueError("Simulation dates are required.")

        if not self.weather:
            raise ValueError("Weather data is required.")

        if not self.soil:
            raise ValueError("Soil data is required.")

        if not self.crop_parameters:
            raise ValueError("Crop parameters are required.")


class WofostRunner:
    """
    Adapter around an externally configured WOFOST backend.

    Backend signature:
        backend(request_dictionary) -> dictionary of outputs
    """

    def __init__(
        self,
        backend: Callable[
            [dict[str, Any]],
            Mapping[str, Any]
        ] | None = None
    ):

        self.backend = backend

    def run(self, request):

        if isinstance(request, Mapping):

            request = WofostRequest(

                crop=str(request["crop"]),

                start_date=str(request["start_date"]),

                end_date=str(request["end_date"]),

                weather=request["weather"],

                soil=request["soil"],

                crop_parameters=request["crop_parameters"],

                management=request.get("management", {})
            )

        request.validate()

        if self.backend is None:

            return {

                "model": "WOFOST",

                "status": "not_configured",

                "executed": False,

                "message": (
                    "No WOFOST backend was supplied. "
                    "Configure a supported WOFOST implementation "
                    "and the required crop, soil and weather parameters."
                ),

                "request": asdict(request),

                "outputs": None
            }

        try:

            raw_output = self.backend(asdict(request))

        except Exception as exc:

            return {

                "model": "WOFOST",

                "status": "failed",

                "executed": True,

                "error_type": type(exc).__name__,

                "message": str(exc),

                "outputs": None
            }

        if not isinstance(raw_output, Mapping):

            raise WofostConfigurationError(
                "WOFOST backend must return a mapping."
            )

        return {

            "model": "WOFOST",

            "status": "completed",

            "executed": True,

            "outputs": dict(raw_output),

            "provenance": "external_wofost_backend"
        }