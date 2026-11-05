"""Submit a compiled pipeline to Vertex AI Pipelines.

The argument names are checked against the installed google-cloud-aiplatform in tests, but a real
submission has NOT been made from the development sandbox: try it once in your project (docs/runbook.md).
"""
from __future__ import annotations

from typing import Any, Optional


def submit_pipeline(project: str, location: str, template_path: str, pipeline_root: str,
                    parameter_values: dict[str, Any], display_name: str,
                    service_account: Optional[str] = None, enable_caching: bool = False):
    try:
        from google.cloud import aiplatform
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("pip install google-cloud-aiplatform") from e
    aiplatform.init(project=project, location=location)
    job = aiplatform.PipelineJob(
        display_name=display_name,
        template_path=template_path,
        pipeline_root=pipeline_root,
        parameter_values=parameter_values,
        enable_caching=enable_caching,
    )
    job.submit(service_account=service_account)
    return job
