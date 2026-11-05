#!/usr/bin/env bash
# Regenerate the API contract types.
# Usage: bash tools/gen_types.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -x "backend/.venv/bin/python" ]; then
  PY="backend/.venv/bin/python"
elif [ -x "backend/.venv/Scripts/python.exe" ]; then
  PY="backend/.venv/Scripts/python.exe"
else
  echo "backend venv not found: create backend/.venv first" >&2
  exit 1
fi

"$PY" backend/scripts/export_openapi.py

cd frontend
npm run gen:api
echo "types regenerated -> frontend/src/generated/api.d.ts"
