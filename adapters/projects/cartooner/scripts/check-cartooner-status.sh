#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../../../.." && pwd)
CONSUMER_REPO_ROOT="${CARTOONER_REPO_ROOT:-$HOME/coding/cartooner}"

export TASKS_ROOT="$CONSUMER_REPO_ROOT/.tasks"
export PATROL_DIR="$CONSUMER_REPO_ROOT/.tasks/patrol"
export DEFAULT_SESSIONS="engineer-a engineer-b engineer-c engineer-d engineer-e"
export AGENT_PROJECT="cartooner"

exec "$REPO_ROOT/core/shell-scripts/check-engineer-status.sh" "$@"
