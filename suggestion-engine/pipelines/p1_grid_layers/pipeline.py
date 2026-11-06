"""P1: build the per-cell feature layer for a region (weather -> features -> validated layer)."""
# Do not add `from __future__ import annotations`: KFP reads real type annotations.

from kfp import compiler, dsl

from pipelines.common import component_kwargs


@dsl.component(**component_kwargs())
def fetch_weather_op(region_id: str, data_root: str, source: str, workers: int) -> int:
    from fieldshift.features.p1_factory import run_fetch
    return run_fetch(region_id, data_root, source, workers)


@dsl.component(**component_kwargs())
def build_layer_op(region_id: str, data_root: str, layer_version: str, source: str, soil_source: str,
                   soil_path: str, smap_csv: str, ndvi_csv: str, future_json: str,
                   failed_downloads: int) -> str:
    from fieldshift.features.p1_factory import run_build
    report = run_build(region_id, data_root, layer_version, source, soil_source,
                       soil_path or None, smap_csv or None, ndvi_csv or None, future_json or None)
    return f"{report['n_cells']} cells, {len(report['warnings'])} warnings, {failed_downloads} failed downloads"


@dsl.pipeline(name="fieldshift-p1-grid-layers", description="Build the per-cell climate and soil feature layer")
def p1_pipeline(region_id: str, data_root: str, layer_version: str, source: str = "power",
                soil_source: str = "raster", soil_path: str = "", smap_csv: str = "", ndvi_csv: str = "",
                future_json: str = "", workers: int = 4):
    fetch = fetch_weather_op(region_id=region_id, data_root=data_root, source=source, workers=workers)
    build_layer_op(region_id=region_id, data_root=data_root, layer_version=layer_version, source=source,
                   soil_source=soil_source, soil_path=soil_path, smap_csv=smap_csv, ndvi_csv=ndvi_csv,
                   future_json=future_json, failed_downloads=fetch.output)


def compile_pipeline(path: str) -> str:
    compiler.Compiler().compile(p1_pipeline, package_path=path)
    return path
