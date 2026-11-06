"""Run with ``python -m config.validate`` to check startup configuration."""

import sys

from pydantic import ValidationError

from config.settings import Settings


def main() -> int:
    try:
        settings = Settings()
        missing_providers = settings.validate_runtime_configuration()
    except ValidationError as exc:
        # Pydantic's normal rendering includes input values. Never print it here.
        fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
        print("Configuration invalid for: " + ", ".join(fields), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Configuration invalid: {exc}", file=sys.stderr)
        return 1

    print("Configuration valid (database URL and core settings).")
    if missing_providers:
        print("Provider configuration incomplete: " + ", ".join(missing_providers))
    else:
        print("Provider configuration complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
