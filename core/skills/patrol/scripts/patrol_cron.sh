#!/usr/bin/env bash
set -euo pipefail

mode="${1:-}"
[[ "$mode" == "daily" || "$mode" == "weekly" ]] || exit 0

project="${CLAWSEAT_PROJECT:-${AGENTS_PROJECT:-install}}"
session="${project}-patrol"
legacy_role="$(printf '%s%s' q a)"
legacy_session="${project}-${legacy_role}"
log_path="${HOME}/.agents/memory/_patrol.log"
mkdir -p "$(dirname "$log_path")"

if ! command -v tmux >/dev/null 2>&1; then
  exit 0
fi
if ! tmux has-session -t "$session" 2>/dev/null; then
  if tmux has-session -t "$legacy_session" 2>/dev/null; then
    session="$legacy_session"
  else
    exit 0
  fi
fi

message="patrol scan $mode"
{
  printf '%s project=%s mode=%s session=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$project" "$mode" "$session"
} >>"$log_path" 2>/dev/null || true

tmux send-keys -t "$session" "$message" Enter >/dev/null 2>&1 || true
exit 0
