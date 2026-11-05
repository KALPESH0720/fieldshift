"""Version stamps. These travel with every output and form part of the cache key."""
from __future__ import annotations

import hashlib
from pathlib import Path

MODEL_VERSION = "0.1.0"


def hash_files(paths: list[Path]) -> str:
    """Stable 8-character hash over file names and contents."""
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:8]
