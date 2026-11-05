"""Dump the FastAPI OpenAPI schema to backend/openapi.json.

The file is a build artifact: it is gitignored and consumed by
`npm run gen:api` (openapi-typescript) to produce frontend types.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402


def main() -> None:
    out = BACKEND_DIR / "openapi.json"
    out.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
