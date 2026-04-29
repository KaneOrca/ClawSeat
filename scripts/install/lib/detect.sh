#!/usr/bin/env bash
# shellcheck shell=bash
# EE3: Intelligent environment detection for AI-native install UX.

_CLAWSEAT_DETECT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

_detect_repo_root() {
  if [[ -n "${CLAWSEAT_ROOT:-}" ]]; then
    printf '%s\n' "$CLAWSEAT_ROOT"
  else
    cd "$_CLAWSEAT_DETECT_LIB_DIR/../../.." && pwd
  fi
}

_detect_json_string() {
  local value="${1:-}"
  python3 - "$value" <<'PY' 2>/dev/null || printf '"%s"' "${value//\"/\\\"}"
import json
import sys

print(json.dumps(sys.argv[1]))
PY
}

_detect_tool_state() {
  local -a candidates=("$@")
  local candidate=""
  for candidate in "${candidates[@]}"; do
    [[ -e "$candidate" ]] && { printf 'ok\n'; return 0; }
  done
  printf 'missing\n'
}

detect_oauth_states() {
  local claude_state="missing" codex_state="missing" gemini_state="missing"

  claude_state="$(_detect_tool_state \
    "$HOME/.claude/auth.json" \
    "$HOME/.claude/.credentials.json" \
    "$HOME/.config/claude/auth.json")"
  codex_state="$(_detect_tool_state \
    "$HOME/.codex/auth.json" \
    "$HOME/.codex/auth.toml" \
    "$HOME/.codex/auth")"
  gemini_state="$(_detect_tool_state \
    "$HOME/.gemini/oauth_creds.json" \
    "$HOME/.gemini/auth.json" \
    "$HOME/.config/gcloud/application_default_credentials.json")"

  printf '{"claude":"%s","codex":"%s","gemini":"%s"}\n' \
    "$claude_state" "$codex_state" "$gemini_state"
}

detect_pty_resource() {
  local used="0" total="256" warn="false"
  used="$(tmux ls 2>/dev/null | wc -l | tr -d '[:space:]' || printf '0')"
  [[ "$used" =~ ^[0-9]+$ ]] || used="0"
  (( used > 200 )) && warn="true"
  printf '{"used":%s,"total":%s,"warn":%s}\n' "$used" "$total" "$warn"
}

detect_template_from_name() {
  local name="${1:-}" lowered=""
  lowered="$(printf '%s' "$name" | tr '[:upper:]' '[:lower:]')"
  if [[ "$lowered" =~ (solo|minimal|personal) ]]; then
    printf 'clawseat-solo\n'
  elif [[ "$lowered" =~ (game|app|api|server|backend|web|tool) ]]; then
    printf 'clawseat-engineering\n'
  else
    printf 'clawseat-creative\n'
  fi
}

detect_branch_state() {
  local repo_root="" branch="" warn="false"
  repo_root="$(_detect_repo_root)"
  branch="$(git -C "$repo_root" rev-parse --abbrev-ref HEAD 2>/dev/null || printf 'unknown')"
  [[ "$branch" != "main" ]] && warn="true"
  printf '{"branch":%s,"warn":%s}\n' "$(_detect_json_string "$branch")" "$warn"
}

detect_existing_projects() {
  local dir="$HOME/.agents/projects"
  if [[ ! -d "$dir" ]]; then
    printf '[]\n'
    return 0
  fi
  find "$dir" -maxdepth 1 -mindepth 1 -type d -print 2>/dev/null \
    | sort \
    | while IFS= read -r project_path; do basename "$project_path"; done \
    | python3 -c 'import json, sys; print(json.dumps([line.strip() for line in sys.stdin if line.strip()]))'
}

detect_all() {
  local oauth="" pty="" branch="" projects="" timestamp=""
  oauth="$(detect_oauth_states)"
  pty="$(detect_pty_resource)"
  branch="$(detect_branch_state)"
  projects="$(detect_existing_projects)"
  timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  cat <<JSON
{
  "oauth": ${oauth},
  "pty": ${pty},
  "branch": ${branch},
  "existing_projects": ${projects},
  "timestamp": "$timestamp"
}
JSON
}
