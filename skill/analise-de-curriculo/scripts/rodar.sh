#!/usr/bin/env bash
# Roda um script da skill com o Python do ambiente virtual do projeto (pypdf, python-docx, jsonschema).
# Uso: rodar.sh <script>.py [args...]
set -euo pipefail
AQUI="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
PROJ="$(cd "$AQUI/../../.." && pwd)"
PY="$PROJ/.venv/bin/python"
[ -x "$PY" ] || PY="python3"
SCRIPT="$1"; shift
exec "$PY" "$AQUI/$SCRIPT" "$@"
