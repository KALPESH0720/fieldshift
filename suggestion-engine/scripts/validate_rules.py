
"""Validate FieldShift knowledge and reason-code YAML files.

Usage:
    py scripts/validate_rules.py
    py scripts/validate_rules.py --knowledge knowledge --reason-codes contracts/reason_codes.yaml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


def load_yaml(path: Path):
    try:
        with path.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {path}: {exc}") from exc


def validate_reason_codes(path: Path) -> list[str]:
    errors = []
    data = load_yaml(path)

    if not isinstance(data, dict):
        return [f"{path}: root must be a YAML mapping"]

    if not isinstance(data.get("version"), int):
        errors.append(f"{path}: missing integer 'version'")

    codes = data.get("codes")
    if not isinstance(codes, dict) or not codes:
        return errors + [f"{path}: 'codes' must be a non-empty mapping"]

    for code, definition in codes.items():
        if not isinstance(code, str) or not code:
            errors.append(f"{path}: invalid reason-code name")

        if not isinstance(definition, dict):
            errors.append(f"{path}: {code} must be a mapping")
            continue

        if not isinstance(definition.get("kind"), str):
            errors.append(f"{path}: {code} missing 'kind'")

        params = definition.get("params", [])
        if not isinstance(params, list):
            errors.append(f"{path}: {code} params must be a list")

        text = definition.get("text_en")
        if not isinstance(text, str) or not text:
            errors.append(f"{path}: {code} missing 'text_en'")

    if errors:
        return errors

    print(f"Validated {len(codes)} reason codes: {path}")
    return []


def validate_knowledge(directory: Path) -> list[str]:
    errors = []

    if not directory.exists():
        return [f"Knowledge directory not found: {directory}"]

    files = sorted(
        list(directory.rglob("*.yaml"))
        + list(directory.rglob("*.yml"))
    )

    if not files:
        return [f"No YAML knowledge files found in {directory}"]

    for path in files:
        try:
            load_yaml(path)
            print(f"YAML OK: {path}")
        except ValueError as exc:
            errors.append(str(exc))

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate FieldShift agronomic knowledge files"
    )
    parser.add_argument("--knowledge", default="knowledge")
    parser.add_argument(
        "--reason-codes",
        default="contracts/reason_codes.yaml",
    )
    args = parser.parse_args()

    errors = []
    errors.extend(validate_knowledge(Path(args.knowledge)))
    errors.extend(validate_reason_codes(Path(args.reason_codes)))

    if errors:
        print("\nVALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        sys.exit(1)

    print("\nFieldShift knowledge validation passed.")


if __name__ == "__main__":
    main()
