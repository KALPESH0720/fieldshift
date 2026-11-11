import inspect

import pytest
import yaml

pytest.importorskip("kfp")


def test_pipelines_compile_and_expose_the_expected_parameters(tmp_path):
    from pipelines.p1_grid_layers.pipeline import compile_pipeline as c1
    from pipelines.p2_simulation.pipeline import compile_pipeline as c2
    p1 = yaml.safe_load(open(c1(str(tmp_path / "p1.yaml"))).read())
    p2 = yaml.safe_load(open(c2(str(tmp_path / "p2.yaml"))).read())
    assert set(p1["root"]["inputDefinitions"]["parameters"]) == {
        "region_id", "data_root", "layer_version", "source", "soil_source", "soil_path", "smap_csv", "ndvi_csv",
        "future_json", "workers"}
    # the parameters the Vertex launcher sends must exist in the P2 pipeline
    assert {"job_json", "region_id", "data_root", "engine_url"} <= set(p2["root"]["inputDefinitions"]["parameters"])
    assert set(p1["components"]) == {"comp-fetch-weather-op", "comp-build-layer-op"}


def test_component_wrappers_call_the_library_with_matching_arguments(tmp_path, monkeypatch):
    """Execute the component function bodies locally against a tiny region (no Vertex needed)."""
    import yaml

    from fieldshift.features.p1_factory import KNOWLEDGE_REGIONS
    from pipelines.p1_grid_layers.pipeline import build_layer_op, fetch_weather_op

    regions = tmp_path / "regions"
    regions.mkdir()
    cfg = yaml.safe_load((KNOWLEDGE_REGIONS / "pune_demo.yaml").read_text())
    cfg.update(id="tiny", name="tiny", bbox=[73.8, 18.5, 73.9, 18.6], climate_years=[2010, 2024])
    (regions / "tiny.yaml").write_text(yaml.safe_dump(cfg))
    monkeypatch.setenv("FIELDSHIFT_REGIONS_DIR", str(regions))
    root = str(tmp_path / "data")
    failed = fetch_weather_op.python_func(region_id="tiny", data_root=root, source="synthetic", workers=1)
    assert failed == 0
    msg = build_layer_op.python_func(region_id="tiny", data_root=root, layer_version="v1", source="synthetic",
                                     soil_source="synthetic", soil_path="", smap_csv="", ndvi_csv="", future_json="",
                                     failed_downloads=failed)
    assert msg == "1 cells, 0 warnings, 0 failed downloads"


def test_p2_component_arguments_match_run_remote():
    from fieldshift.simulation.p2_remote import run_remote
    from pipelines.p2_simulation.pipeline import simulate_job_op
    comp = list(inspect.signature(simulate_job_op.python_func).parameters)
    assert comp == ["job_json", "region_id", "data_root", "layer_version", "engine_url", "api_key_secret"]
    assert list(inspect.signature(run_remote).parameters)[:6] == comp


def test_submit_script_parameters_match_the_p1_pipeline(tmp_path):
    import importlib.util
    from pathlib import Path

    from pipelines.p1_grid_layers.pipeline import compile_pipeline
    spec = importlib.util.spec_from_file_location("submit_p1", Path(__file__).resolve().parents[2] / "scripts" / "submit_p1.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    args = mod.parser().parse_args(["--region-id", "r", "--layer-version", "v1"])
    params = mod.build_parameters(args, "gs://b/data")
    compiled = yaml.safe_load(open(compile_pipeline(str(tmp_path / "p1.yaml"))).read())
    assert set(params) == set(compiled["root"]["inputDefinitions"]["parameters"])


def test_submit_p2_script_parses_args_correctly():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("submit_p2", Path(__file__).resolve().parents[2] / "scripts" / "submit_p2.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    args = mod.parser().parse_args(["--region-id", "pune_demo", "--layer-version", "2026a", "--engine-url", "http://localhost:8080"])
    assert args.region_id == "pune_demo"
    assert args.layer_version == "2026a"
    assert args.engine_url == "http://localhost:8080"

