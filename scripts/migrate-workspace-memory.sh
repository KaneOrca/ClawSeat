#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: scripts/migrate-workspace-memory.sh <project>" >&2
  exit 2
fi

PROJECT="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

python3 "$REPO_ROOT/core/scripts/agent_admin.py" session start-engineer memory --project "$PROJECT" --accept-override

