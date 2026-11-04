"""
FieldShift AquaCrop Integration Adapter.

Provides a controlled interface for connecting an actual
AquaCrop-compatible simulation backend.
"""

from dataclasses import dataclass, asdict
from typing import Any, Callable, Mapping


class AquaCropConfigurationError(RuntimeError):
    """AquaCrop backend configuration error."""


@dataclass(frozen=True)
class AquaCropRequest:

    crop: str

    start_date: str

    end_date: str

    weather: Mapping[str, Any]

    soil: Mapping[str, Any]

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


class AquaCropRunner:
    """
    Adapter around an externally configured AquaCrop backend.

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

            request = AquaCropRequest(

                crop=str(request["crop"]),

                start_date=str(request["start_date"]),

                end_date=str(request["end_date"]),

                weather=request["weather"],

                soil=request["soil"],

                management=request.get("management", {})
            )

        request.validate()

        if self.backend is None:

            return {

                "model": "AquaCrop",

                "status": "not_configured",

                "executed": False,

                "message": (
                    "No AquaCrop backend was supplied. "
                    "Configure a supported AquaCrop integration "
                    "before running actual crop simulations."
                ),

                "request": asdict(request),

                "outputs": None
            }

        try:

            raw_output = self.backend(asdict(request))

        except Exception as exc:

            return {

                "model": "AquaCrop",

                "status": "failed",

                "executed": True,

                "error_type": type(exc).__name__,

                "message": str(exc),

                "outputs": None
            }

        if not isinstance(raw_output, Mapping):

            raise AquaCropConfigurationError(
                "AquaCrop backend must return a mapping."
            )

        return {

            "model": "AquaCrop",

            "status": "completed",

            "executed": True,

            "outputs": dict(raw_output),

            "provenance": "external_aquacrop_backend"
        }