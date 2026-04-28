#!/usr/bin/env bash
# Sourced by agent-launcher.sh. Keep path resolution BASH_SOURCE-based because
# sourced files observe a different $0 than the top-level launcher.

if [[ -z "${LAUNCHER_DIR:-}" ]]; then
  _launcher_lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  case "$_launcher_lib_dir" in
    */helpers|*/runtimes) LAUNCHER_DIR="$(cd "$_launcher_lib_dir/.." && pwd)" ;;
    *) LAUNCHER_DIR="$_launcher_lib_dir" ;;
  esac
  export LAUNCHER_DIR
fi
if [[ -z "${LAUNCHER_REPO_ROOT:-}" ]]; then
  LAUNCHER_REPO_ROOT="$(cd "$LAUNCHER_DIR/../.." && pwd)"
fi
REAL_HOME="${REAL_HOME:-${HOME:-}}"
LAUNCHER_PYTHON_BIN="${LAUNCHER_PYTHON_BIN:-${PYTHON_BIN:-python3}}"

if ! declare -F load_custom_env >/dev/null; then
  # shellcheck source=../helpers/env.sh
  source "$LAUNCHER_DIR/helpers/env.sh"
fi
if ! declare -F resolve_claude_secret_file >/dev/null; then
  # shellcheck source=../helpers/auth.sh
  source "$LAUNCHER_DIR/helpers/auth.sh"
fi
if ! declare -F seed_user_tool_dirs >/dev/null; then
  # shellcheck source=../helpers/sandbox.sh
  source "$LAUNCHER_DIR/helpers/sandbox.sh"
fi

run_claude_runtime() {
  local auth_mode="$1"
  local workdir="$2"
  local session_name="$3"
  local mode_label="Claude Code"

  if [[ "$auth_mode" == "oauth" ]]; then
    # "oauth" in ClawSeat is not "launcher does OAuth" — it's "reuse the
    # host's existing Claude Code login state" (OAuth handled by Claude
    # Code itself, not us). To make that work we must:
    #   1. route HOME + every XDG base dir back to REAL_HOME so Claude
    #      finds its own ~/.claude, ~/.claude.json, keychain session,
    #      and XDG cache/state (credentials, project history)
    #   2. drop all agent-launcher-provided token env vars so Claude
    #      doesn't prefer a stale token/API-mode path over its own
    #      native login flow
    # Older ClawSeat builds only restored HOME and missed XDG + CLAUDE_CODE_OAUTH_TOKEN,
    # leaving Claude looking at sandbox XDG dirs and picking up stale token env —
    # the root cause of the "re-auth every start" bug.
    unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL ANTHROPIC_MODEL
    unset CLAUDE_CODE_OAUTH_TOKEN CLAUDE_CODE_SUBSCRIBER_SUBSCRIPTION_ID
    export HOME="$REAL_HOME"
    export XDG_CONFIG_HOME="$REAL_HOME/.config"
    export XDG_DATA_HOME="$REAL_HOME/.local/share"
    export XDG_CACHE_HOME="$REAL_HOME/.cache"
    export XDG_STATE_HOME="$REAL_HOME/.local/state"
    seed_user_tool_dirs "$HOME" "${CLAWSEAT_PROJECT:-}"
    cd "$workdir"
    echo "────────────────────────────────────────"
    echo " Claude Code · Host OAuth (reuse)"
    echo " Session:    $session_name"
    echo " Directory:  $workdir"
    echo " HOME:       $HOME"
    echo " XDG_*:      \$REAL_HOME/{config,cache,state,local/share}"
    echo "────────────────────────────────────────"
    exec claude --dangerously-skip-permissions
  fi

  local secret_file="" runtime_dir
  if [[ "$auth_mode" != "custom" ]]; then
    secret_file="$(resolve_claude_secret_file "$auth_mode")"
    if [[ ! -f "$secret_file" ]]; then
      show_claude_auth_setup_hint "$auth_mode"
      echo "error: missing Claude secret file: $secret_file" >&2
      exit 1
    fi
  fi

  case "$auth_mode" in
    oauth_token)
      runtime_dir="$REAL_HOME/.agent-runtime/identities/claude/oauth_token/${auth_mode}-${session_name}"
      ;;
    *)
      runtime_dir="$REAL_HOME/.agent-runtime/identities/claude/api/${auth_mode}-${session_name}"
      ;;
  esac
  mkdir -p \
    "$runtime_dir/home" \
    "$runtime_dir/xdg/config" \
    "$runtime_dir/xdg/data" \
    "$runtime_dir/xdg/cache" \
    "$runtime_dir/xdg/state"

  unset CLAUDE_CODE_OAUTH_TOKEN CLAUDE_CODE_SUBSCRIBER_SUBSCRIPTION_ID
  unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL ANTHROPIC_MODEL

  if [[ "$auth_mode" == "custom" ]]; then
    load_custom_env "$CUSTOM_ENV_FILE"
    # Claude Code reports a conflict if both ANTHROPIC_AUTH_TOKEN and
    # ANTHROPIC_API_KEY are set. For non-anthropic.com endpoints
    # (minimax / xcode-best / any custom proxy) the correct variable is
    # AUTH_TOKEN. anthropic-console seats use --auth anthropic-console,
    # which lands in the explicit branch below and sets API_KEY only.
    export ANTHROPIC_AUTH_TOKEN="${LAUNCHER_CUSTOM_API_KEY:-}"
    export ANTHROPIC_BASE_URL="${LAUNCHER_CUSTOM_BASE_URL:-}"
    export ANTHROPIC_MODEL="${LAUNCHER_CUSTOM_MODEL:-}"
    export API_TIMEOUT_MS=3000000
    export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
    mode_label="Custom API"
  else
    set -a
    source "$secret_file"
    set +a
    case "$auth_mode" in
      oauth_token)
        if ! env_file_has_key "$secret_file" "CLAUDE_CODE_OAUTH_TOKEN"; then
          show_claude_auth_setup_hint "$auth_mode"
          echo "error: CLAUDE_CODE_OAUTH_TOKEN missing in $secret_file" >&2
          exit 1
        fi
        export CLAUDE_CODE_OAUTH_TOKEN="${CLAUDE_CODE_OAUTH_TOKEN:-}"
        mode_label="OAuth token"
        ;;
      anthropic-console)
        if ! env_file_has_key "$secret_file" "ANTHROPIC_API_KEY"; then
          show_claude_auth_setup_hint "$auth_mode"
          echo "error: ANTHROPIC_API_KEY missing in $secret_file" >&2
          exit 1
        fi
        export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
        mode_label="Anthropic Console API"
        ;;
      minimax)
        export API_TIMEOUT_MS=3000000
        export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
        mode_label="MiniMax API"
        ;;
      deepseek)
        export API_TIMEOUT_MS=3000000
        export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
        mode_label="DeepSeek API"
        ;;
      xcode)
        export API_TIMEOUT_MS=3000000
        export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
        mode_label="Xcode API"
        ;;
    esac
  fi

  export AGENT_HOME="$REAL_HOME"
  export AGENTS_ROOT="$REAL_HOME/.agents"
  export HOME="$runtime_dir/home"
  export XDG_CONFIG_HOME="$runtime_dir/xdg/config"
  export XDG_DATA_HOME="$runtime_dir/xdg/data"
  export XDG_CACHE_HOME="$runtime_dir/xdg/cache"
  export XDG_STATE_HOME="$runtime_dir/xdg/state"

  seed_user_tool_dirs "$HOME" "${CLAWSEAT_PROJECT:-}"
  # Skip Claude onboarding in the isolated HOME. Without this the seat
  # blocks on the welcome + auth pages even when API keys are live in env.
  prepare_claude_home "$HOME" "$session_name"

  cd "$workdir"
  echo "────────────────────────────────────────"
  echo " Claude Code · $mode_label"
  echo " Session:    $session_name"
  echo " Directory:  $workdir"
  echo " Model:      ${ANTHROPIC_MODEL:-<unset>}"
  echo " Endpoint:   ${ANTHROPIC_BASE_URL:-default}"
  echo " HOME:       $HOME"
  echo " AGENT_HOME: $AGENT_HOME"
  echo "────────────────────────────────────────"
  exec claude --dangerously-skip-permissions
}
