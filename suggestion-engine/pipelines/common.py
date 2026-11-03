"""Shared pieces of the Vertex pipeline definitions.

Components are thin wrappers: the real logic lives in the fieldshift package (tested offline) and is
imported inside the component. The container image must contain fieldshift AND kfp
(docker/pipeline-base.Dockerfile does), so `install_kfp_package` is turned off.
"""
from __future__ import annotations

import os

# Set FIELDSHIFT_BASE_IMAGE to your pushed image when compiling for Vertex.
BASE_IMAGE = os.environ.get("FIELDSHIFT_BASE_IMAGE", "python:3.11-slim")


def component_kwargs() -> dict:
    return {"base_image": BASE_IMAGE, "install_kfp_package": False, "packages_to_install": []}
