"""CLI utility to inspect and safely initialize ADH_CUSTOMER and ADH_USER."""

import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.schema import SchemaConflictError, initialize_auth_schema  # noqa: E402


def main() -> int:
    load_dotenv()
    try:
        report, created = initialize_auth_schema()
    except SchemaConflictError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Schema initialization failed: {exc}", file=sys.stderr)
        return 1

    print(f"Target database: {report.database}")
    if created:
        print(f"Created tables: {', '.join(created)}")
    else:
        print("Existing ADH_CUSTOMER and ADH_USER tables verified compatible; no changes made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
