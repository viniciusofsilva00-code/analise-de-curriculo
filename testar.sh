#!/usr/bin/env bash
# Roda todos os testes do sistema com um comando só.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.venv/ms-playwright"
.venv/bin/python scripts/build_app.py
exec .venv/bin/python -m pytest tests "$@"
