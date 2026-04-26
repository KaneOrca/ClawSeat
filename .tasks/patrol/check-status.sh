#!/bin/bash
set -euo pipefail

export TASKS_ROOT=/Users/ywf/coding/arena-pretext-ui/.tasks
export PATROL_DIR=/Users/ywf/coding/arena-pretext-ui/.tasks/patrol
export DEFAULT_SESSIONS="engineer-b engineer-a engineer-c engineer-d engineer-e"

exec /Users/ywf/coding/.scripts/check-engineer-status.sh "$@"
