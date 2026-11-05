"""Read/write text and JSON on a local path or a gs:// URI.

The local branch is covered by tests. The gs:// branch uses google-cloud-storage and has NOT been
run against a real bucket from the development sandbox: test it once in your project (runbook).
"""
from __future__ import annotations

import json
import os
import tempfile
from typing import Any


def is_gcs(path: str) -> bool:
    return str(path).startswith("gs://")


def _split_gcs(path: str) -> tuple[str, str]:
    rest = str(path)[5:]
    bucket, _, blob = rest.partition("/")
    if not bucket or not blob:
        raise ValueError(f"bad gs:// path: {path}")
    return bucket, blob


def _gcs_blob(path: str):
    try:
        from google.cloud import storage
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("pip install google-cloud-storage to use gs:// paths") from e
    bucket, blob = _split_gcs(path)
    return storage.Client().bucket(bucket).blob(blob)


def exists(path: str) -> bool:
    if is_gcs(path):
        return _gcs_blob(path).exists()
    return os.path.exists(path)


def read_text(path: str) -> str:
    if is_gcs(path):
        return _gcs_blob(path).download_as_text(encoding="utf-8")
    with open(path, encoding="utf-8") as f:
        return f.read()


def write_text(path: str, text: str) -> None:
    if is_gcs(path):
        _gcs_blob(path).upload_from_string(text.encode("utf-8"), content_type="text/plain")
        return
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=parent, suffix=".tmp")  # write then rename: readers never see half a file
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def read_json(path: str) -> Any:
    return json.loads(read_text(path))


def write_json(path: str, obj: Any, indent: int | None = 2) -> None:
    write_text(path, json.dumps(obj, indent=indent, ensure_ascii=False))
