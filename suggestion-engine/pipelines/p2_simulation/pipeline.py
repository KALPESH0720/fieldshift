"""P2: simulate the shortlisted sequences of one engine job and post indicators back to the engine."""
# Do not add `from __future__ import annotations`: KFP reads real type annotations.

from kfp import compiler, dsl

from pipelines.common import component_kwargs


@dsl.component(**component_kwargs())
def simulate_job_op(job_json: str, region_id: str, data_root: str, layer_version: str, engine_url: str,
                    api_key_secret: str) -> str:
    from fieldshift.simulation.p2_remote import run_remote
    out = run_remote(job_json, region_id, data_root, layer_version, engine_url, api_key_secret or None)
    return f"{out['indicators']} indicators for job {out['job_id']}"


@dsl.pipeline(name="fieldshift-p2-simulation", description="Deep-tier simulation for one engine job")
def p2_pipeline(job_json: str, region_id: str, data_root: str, layer_version: str, engine_url: str,
                api_key_secret: str = ""):
    simulate_job_op(job_json=job_json, region_id=region_id, data_root=data_root, layer_version=layer_version,
                    engine_url=engine_url, api_key_secret=api_key_secret)


def compile_pipeline(path: str) -> str:
    compiler.Compiler().compile(p2_pipeline, package_path=path)
    return path
