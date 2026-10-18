#!/usr/bin/env bash
# Regenerates the typed web client from the FastAPI OpenAPI spec.
set -euo pipefail
cd "$(dirname "$0")/.."
(cd services/api && DATABASE_URL=sqlite:///:memory: PYTHONPATH=. .venv/bin/python -c "
import json
from helm.main import app
print(json.dumps(app.openapi()))" > ../../apps/web/openapi.json)
pnpm --filter web exec openapi-typescript openapi.json -o src/lib/api-schema.ts
