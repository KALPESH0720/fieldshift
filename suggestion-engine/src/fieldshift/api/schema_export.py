"""Write the JSON Schemas in contracts/ and docs/api/openapi.yaml from the code. Run: python -m fieldshift.api.schema_export"""
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
    import yaml

    from .main import create_app
    spec = REPO_ROOT / "docs" / "api" / "openapi.yaml"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(yaml.safe_dump(create_app().openapi(), sort_keys=False), encoding="utf-8")
    print("wrote", spec)


if __name__ == "__main__":
    main()
