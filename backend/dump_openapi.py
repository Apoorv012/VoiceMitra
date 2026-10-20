"""Write the API's OpenAPI spec to web/openapi.json, from which the frontend generates its TypeScript
types (`npm run gen:api` in web/). Run after changing a response model in backend/views.py:

    python -m backend.dump_openapi

Builds the spec without starting the server, so it needs no running backend or database.
"""

from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from backend.main import app  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "web" / "openapi.json"

if __name__ == "__main__":
    OUT.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
