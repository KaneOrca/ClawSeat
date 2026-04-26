#!/bin/bash
set -euo pipefail

exec python3 /Users/ywf/coding/.agents/skills/gstack-harness/scripts/patrol_supervisor.py --profile /Users/ywf/coding/.agents/skills/gstack-harness/assets/profiles/arena-pretext-ui.toml "$@"
