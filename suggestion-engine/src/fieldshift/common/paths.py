"""Storage layout shared by all pipelines (matches the Cloud Storage layout in the plan).

    raw/{source}/{region}/...        untouched downloads, kept so reruns never refetch
    layers/{region}/{layer_version}/ per-cell feature tables written by P1
    runs/{pipeline}/{run_id}/        inputs, outputs, logs of each run
    models/{param_version}/          calibrated parameters
    exports/                         reports
`root` is a local folder or a gs:// URI. Paths always use forward slashes.
"""
from __future__ import annotations

from dataclasses import dataclass


def _join(*parts: str) -> str:
    cleaned = [p.strip("/") if i else p.rstrip("/") for i, p in enumerate(parts) if p != ""]
    return "/".join(cleaned)


@dataclass(frozen=True)
class Layout:
    root: str

    def raw(self, source: str, region: str, name: str) -> str:
        return _join(self.root, "raw", source, region, name)

    def weather(self, region: str, cell_id: str) -> str:
        return self.raw("power", region, f"{cell_id}.json")

    def layers_dir(self, region: str, layer_version: str) -> str:
        return _join(self.root, "layers", region, layer_version)

    def cells_file(self, region: str, layer_version: str) -> str:
        return _join(self.layers_dir(region, layer_version), "cells.json")

    def layer_report(self, region: str, layer_version: str) -> str:
        return _join(self.layers_dir(region, layer_version), "report.json")

    def run_dir(self, pipeline: str, run_id: str) -> str:
        return _join(self.root, "runs", pipeline, run_id)

    def run_file(self, pipeline: str, run_id: str, name: str) -> str:
        return _join(self.run_dir(pipeline, run_id), name)

    def models_dir(self, param_version: str) -> str:
        return _join(self.root, "models", param_version)

    def exports_dir(self) -> str:
        return _join(self.root, "exports")
