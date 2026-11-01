import json

import jsonschema
import pytest

from fieldshift.api.schema_export import OUT, schemas
from fieldshift.common.config import REPO_ROOT


def test_committed_schemas_match_the_models():
    """If this fails, run `python -m fieldshift.api.schema_export` and tell the backend team."""
    for name, schema in schemas().items():
        on_disk = json.loads((OUT / name).read_text(encoding="utf-8"))
        assert on_disk == json.loads(json.dumps(schema, sort_keys=True)), f"{name} is out of date"


def _validate(name, instance):
    schema = json.loads((OUT / name).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(instance)


def test_example_files_match_schemas():
    mock = REPO_ROOT / "contracts" / "mock_server"
    _validate("request.schema.json", json.loads((mock / "example_request.json").read_text(encoding="utf-8")))
    _validate("response.schema.json", json.loads((mock / "example_response.json").read_text(encoding="utf-8")))


@pytest.mark.parametrize("irrigation", ["rainfed", "limited", "full"])
def test_live_responses_validate_against_the_schema(client, base_request, irrigation):
    body = {**base_request, "irrigation": irrigation}
    _validate("request.schema.json", body)
    r = client.post("/v1/recommend", json=body)
    assert r.status_code == 200
    _validate("response.schema.json", r.json())
