"""Prints the FastAPI app's OpenAPI schema to stdout.

Used by `make openapi-client` (see root Makefile) to regenerate the frontend's typed
API client: ``python -m should_cost.scripts.export_openapi > ../frontend/openapi.json``.
Importing should_cost.main is enough to get the schema — the app's lifespan (which talks
to Azure) never runs for ``app.openapi()``.
"""

from __future__ import annotations

import json

from should_cost.main import app


def main() -> None:
    print(json.dumps(app.openapi(), indent=2))


if __name__ == "__main__":
    main()
