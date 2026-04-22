#!/usr/bin/env bash
# launch_ancestor.sh — v0.5 frontstage: pull up the ancestor CC session.
#
# Reuses:
#   agent-launcher.sh         — credential verification + headless seat launch
#   agent_admin.py           — session switch-harness + start-engineer
#   send-and-verify.sh       — 3-Enter flush contract for prompt injection
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_CLAWSEAT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
if [[ -n "${CLAWSEAT_ROOT:-}" ]] && [[ -d "${CLAWSEAT_ROOT}/core/scripts" ]]; then
  CLAWSEAT_ROOT="$CLAWSEAT_ROOT"
else
  CLAWSEAT_ROOT="$DEFAULT_CLAWSEAT_ROOT"
fi
SEND_AND_VERIFY="$CLAWSEAT_ROOT/core/shell-scripts/send-and-verify.sh"
AGENT_LAUNCHER="$CLAWSEAT_ROOT/core/launchers/agent-launcher.sh"
AGENT_ADMIN="$CLAWSEAT_ROOT/core/scripts/agent_admin.py"
ANCESTOR_SKILL="$CLAWSEAT_ROOT/core/skills/clawseat-ancestor/SKILL.md"

# ── argument parsing ────────────────────────────────────────────────────

PROJECT=""; TOOL=""; AUTH_MODE=""; PROVIDER=""; MODEL=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2 ;;
    --tool)    TOOL="$2";    shift 2 ;;
    --auth-mode) AUTH_MODE="$2"; shift 2 ;;
    --provider)  PROVIDER="$2"; shift 2 ;;
    --model)     MODEL="$2";  shift 2 ;;
    --help) cat <<'EOF'
Usage:
  scripts/launch_ancestor.sh --project <name> \
    --tool claude \
    --auth-mode oauth|oauth_token|api \
    --provider <provider> \
    [--model <model-id>]

Exits:
  0 on ancestor tmux session created and prompt-ready
  2 on input error (missing/invalid flags, unknown auth)
  3 on environment error (missing binary, no auth credential)
  4 on launch failure (session.toml write failed, tmux send-keys blocked)
EOF
exit 0 ;;
    *) echo "UNKNOWN_FLAG: $1" >&2; exit 2 ;;
  esac
done

# ── flag validation ─────────────────────────────────────────────────────

[[ -n "$PROJECT" ]]  || { echo "MISSING_FLAG: --project" >&2; exit 2; }
[[ -n "$TOOL" ]]     || { echo "MISSING_FLAG: --tool"    >&2; exit 2; }
[[ -n "$AUTH_MODE" ]] || { echo "MISSING_FLAG: --auth-mode" >&2; exit 2; }
[[ -n "$PROVIDER" ]]  || { echo "MISSING_FLAG: --provider"  >&2; exit 2; }

case "$TOOL" in claude|codex|gemini) ;; *)
  echo "UNKNOWN_TOOL: $TOOL" >&2; exit 2 ;;
esac
case "$AUTH_MODE" in oauth|oauth_token|api) ;; *)
  echo "UNKNOWN_AUTH_MODE: $AUTH_MODE" >&2; exit 2 ;;
esac
if [[ -n "$MODEL" && "$TOOL" != "claude" ]]; then
  echo "MODEL_UNSUPPORTED: --model is only supported for --tool claude" >&2
  exit 2
fi

validate_runtime_combo() {
  python3 - "$CLAWSEAT_ROOT" "$TOOL" "$AUTH_MODE" "$PROVIDER" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
sys.path.insert(0, str(root / "core" / "scripts"))
from agent_admin_config import validate_runtime_combo

try:
    validate_runtime_combo(sys.argv[2], sys.argv[3], sys.argv[4], error_cls=RuntimeError)
except Exception as exc:
    sys.stderr.write(f"UNSUPPORTED_RUNTIME_COMBO: {exc}\n")
    raise SystemExit(2)
PY
}

check_secrets_auth_mode() {
  case "$TOOL/$AUTH_MODE/$PROVIDER" in
    claude/oauth/anthropic) printf '%s\n' "oauth" ;;
    claude/oauth_token/anthropic) printf '%s\n' "oauth_token" ;;
    claude/api/anthropic-console) printf '%s\n' "anthropic-console" ;;
    claude/api/minimax) printf '%s\n' "minimax" ;;
    claude/api/xcode-best) printf '%s\n' "xcode" ;;
    codex/oauth/openai) printf '%s\n' "chatgpt" ;;
    codex/api/xcode-best) printf '%s\n' "xcode" ;;
    gemini/oauth/google) printf '%s\n' "oauth" ;;
    gemini/api/google-api-key) printf '%s\n' "primary" ;;
    *)
      echo "UNSUPPORTED_RUNTIME_COMBO: no credential-check mapping for $TOOL/$AUTH_MODE/$PROVIDER" >&2
      exit 2
      ;;
  esac
}

validate_runtime_combo
CHECK_SECRETS_MODE="$(check_secrets_auth_mode)"

# ── credential check ────────────────────────────────────────────────────

# agent-launcher.sh --check-secrets exits 1 with JSON when credential missing.
# If the launcher script doesn't exist or fails to produce JSON, we cannot
# verify credentials — treat that as a missing credential error.
creds_json=$("$AGENT_LAUNCHER" --check-secrets "$TOOL" --auth "$CHECK_SECRETS_MODE" 2>&1) || true
if [[ -z "$creds_json" ]]; then
  echo "MISSING_CREDENTIAL: $TOOL/$AUTH_MODE/$PROVIDER (could not run credential check)" >&2
  exit 3
fi
creds_status=$(echo "$creds_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "error")
if [[ "$creds_status" != "ok" ]]; then
  # Extract file hint from JSON for the error message.
  creds_file=$(echo "$creds_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('file',''))" 2>/dev/null || echo "")
  echo "MISSING_CREDENTIAL: $TOOL/$AUTH_MODE/$PROVIDER ($creds_file)" >&2
  exit 3
fi

# ── materialize session.toml via switch-harness ─────────────────────────

switch_cmd=(
  python3 "$AGENT_ADMIN" session switch-harness
  --project "$PROJECT"
  --engineer ancestor
  --tool "$TOOL"
  --mode "$AUTH_MODE"
  --provider "$PROVIDER"
)
if [[ -n "$MODEL" ]]; then
  switch_cmd+=(--model "$MODEL")
fi
"${switch_cmd[@]}" \
  || { echo "SESSION_TOML_WRITE_FAILED: switch-harness returned $?" >&2; exit 4; }

# ── start tmux session ─────────────────────────────────────────────────

start_rc=0
python3 "$AGENT_ADMIN" session start-engineer ancestor --project "$PROJECT" \
  || { echo "TMUX_SESSION_START_FAILED: start-engineer returned $?" >&2; exit 4; }

session_name="${PROJECT}-ancestor-${TOOL}"

# ── inject ancestor bootstrap prompt ────────────────────────────────────

prompt="You are the install frontstage for this ClawSeat v0.5 install. Read $ANCESTOR_SKILL, bring up the memory seat next, then the six-pane grid."

# 3-Enter flush contract via send-and-verify.sh (sleep-based).
if [[ -x "$SEND_AND_VERIFY" ]]; then
  "$SEND_AND_VERIFY" --project "$PROJECT" "$session_name" "$prompt"
else
  # Fallback: direct tmux send-keys 3-Enter flush.
  tmux send-keys -t "$session_name" "$prompt" 2>/dev/null || true
  sleep 0.3; tmux send-keys -t "$session_name" Enter 2>/dev/null || true
  sleep 0.2; tmux send-keys -t "$session_name" Enter 2>/dev/null || true
  sleep 0.2; tmux send-keys -t "$session_name" Enter 2>/dev/null || true
fi

echo "OK: ancestor launched as session $session_name; prompt injected"
exit 0
