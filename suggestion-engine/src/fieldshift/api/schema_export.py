"""Write the JSON Schemas in contracts/ from the pydantic models. Run: python -m fieldshift.api.schema_export"""
from __future__ import annotations

import json

from ..common.config import REPO_ROOT
from ..store.models import RecommendRequest, RecommendResponse

OUT = REPO_ROOT / "contracts"


def schemas() -> dict[str, dict]:
    return {
        "request.schema.json": RecommendRequest.model_json_schema(),
        "response.schema.json": RecommendResponse.model_json_schema(mode="serialization"),
    }


def main() -> None:
    for name, schema in schemas().items():
        (OUT / name).write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("wrote", OUT / name)


if __name__ == "__main__":
    main()
