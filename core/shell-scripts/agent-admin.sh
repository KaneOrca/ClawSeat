#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3.12)"
elif command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3.11)"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  echo "python3 is required for agent-admin" >&2
  exit 1
fi

if [[ $# -eq 0 ]]; then
  exec "$PYTHON_BIN" "$REPO_ROOT/core/scripts/agent_admin.py" --help
fi

exec "$PYTHON_BIN" "$REPO_ROOT/core/scripts/agent_admin.py" "$@"
