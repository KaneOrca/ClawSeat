#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0; PROJECT="install"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CLAWSEAT_ROOT="${CLAWSEAT_ROOT:-$REPO_ROOT}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

# Resolve real user $HOME. install.sh writes user-level state under
# ~/.agents/... and reads user-level python user-site (iterm2 etc).
# When invoked from inside a sandboxed seat (minimax smoke tests),
# $HOME points to ~/.agent-runtime/identities/.../home which would
# scatter install state into the sandbox and hide iterm2/oauth.
# Resolve real HOME explicitly and re-export, so every subprocess
# (preflight, scan, iterm driver, memory hook, brief render) sees it.
REAL_HOME="${CLAWSEAT_REAL_HOME:-}"
if [[ -z "$REAL_HOME" ]]; then
  if [[ "$(uname -s)" == "Darwin" ]]; then
    REAL_HOME="$(/usr/bin/dscl . -read "/Users/$(id -un)" NFSHomeDirectory 2>/dev/null | awk 'NR==1{print $2}')"
  fi
  if [[ -z "$REAL_HOME" ]] && command -v getent >/dev/null 2>&1; then
    REAL_HOME="$(getent passwd "$(id -un)" 2>/dev/null | cut -d: -f6)"
  fi
  [[ -z "$REAL_HOME" ]] && REAL_HOME="$HOME"
fi
export HOME="$REAL_HOME"
SCAN_SCRIPT="$REPO_ROOT/core/skills/memory-oracle/scripts/scan_environment.py"
ITERM_DRIVER="$REPO_ROOT/core/scripts/iterm_panes_driver.py"
TEMPLATE_PATH="$REPO_ROOT/core/templates/ancestor-brief.template.md"
MEMORY_HOOK_INSTALLER="$REPO_ROOT/core/skills/memory-oracle/scripts/install_memory_hook.py"
LAUNCHER_SCRIPT="$REPO_ROOT/core/launchers/agent-launcher.sh"
AGENT_ADMIN_SCRIPT="$REPO_ROOT/core/scripts/agent_admin.py"
WAIT_FOR_SEAT_SCRIPT="$REPO_ROOT/scripts/wait-for-seat.sh"
MEMORY_ROOT="$HOME/.agents/memory"; PROVIDER_ENV=""; BRIEF_PATH=""
MEMORY_WORKSPACE=""
GRID_WINDOW_ID=""
GUIDE_FILE=""
PROVIDER_MODE=""
PROVIDER_KEY=""
PROVIDER_BASE=""
PROVIDER_MODEL=""
FORCE_PROVIDER=""
FORCE_BASE_URL=""
FORCE_API_KEY=""
FORCE_MODEL=""
PROJECT_LOCAL_TOML=""
PROJECT_RECORD_PATH=""
AGENTS_TEMPLATES_ROOT="$HOME/.agents/templates"
CLAWSEAT_TEMPLATE_NAME="clawseat-default"
BOOTSTRAP_TEMPLATE_DIR="$AGENTS_TEMPLATES_ROOT/$CLAWSEAT_TEMPLATE_NAME"
BOOTSTRAP_TEMPLATE_PATH="$BOOTSTRAP_TEMPLATE_DIR/template.toml"
PENDING_SEATS=(planner builder reviewer qa designer)

die() { local n="$1" code="$2" msg="$3"; printf '%s\nERR_CODE: %s\n' "$msg" "$code" >&2; exit "$n"; }
note() { printf '==> %s\n' "$*"; }
run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] '
    printf '%q ' "$@"
    printf '\n'
    return 0
  fi
  "$@" || die 99 COMMAND_FAILED "command failed: $*"
}
export_line() { printf 'export %s=%q\n' "$1" "$2"; }
remember_provider_selection() {
  PROVIDER_MODE="$1"
  PROVIDER_KEY="${2:-}"
  PROVIDER_BASE="${3:-}"
  PROVIDER_MODEL="${4:-}"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) DRY_RUN=1; shift ;;
      --project) PROJECT="$2"; shift 2 ;;
      --provider) FORCE_PROVIDER="$2"; shift 2 ;;
      --base-url) FORCE_BASE_URL="$2"; shift 2 ;;
      --api-key) FORCE_API_KEY="$2"; shift 2 ;;
      --model) FORCE_MODEL="$2"; shift 2 ;;
      --help|-h) printf 'Usage: scripts/install.sh [--project <name>] [--provider <mode>] [--base-url <url> --api-key <key> [--model <name>]] [--dry-run]\n'; exit 0 ;;
      *) die 2 UNKNOWN_FLAG "unknown flag: $1" ;;
    esac
  done
  [[ "$PROJECT" =~ ^[a-z0-9-]+$ ]] || die 2 INVALID_PROJECT "project must match ^[a-z0-9-]+$"
  if [[ -n "$FORCE_BASE_URL" ]]; then
    [[ -n "$FORCE_API_KEY" ]] || die 2 INVALID_FLAGS "--base-url 必须和 --api-key 成对"
    [[ -z "$FORCE_PROVIDER" || "$FORCE_PROVIDER" == "custom_api" ]] \
      || die 2 INVALID_FLAGS "--base-url/--api-key 只能配 --provider custom_api 或不传 --provider"
  elif [[ -n "$FORCE_API_KEY" ]]; then
    case "$FORCE_PROVIDER" in
      minimax|anthropic_console) ;;
      *)
        die 2 INVALID_FLAGS "--base-url 必须和 --api-key 成对"
        ;;
    esac
  fi
  if [[ -n "$FORCE_MODEL" ]]; then
    if [[ -n "$FORCE_BASE_URL" && -n "$FORCE_API_KEY" ]]; then
      :
    elif [[ -n "$FORCE_API_KEY" && ( "$FORCE_PROVIDER" == "minimax" || "$FORCE_PROVIDER" == "anthropic_console" ) ]]; then
      :
    else
      die 2 INVALID_FLAGS "--model 只能与 --base-url/--api-key 一起使用，或配合 --provider minimax|anthropic_console + --api-key"
    fi
  fi
  PROVIDER_ENV="$HOME/.agents/tasks/$PROJECT/ancestor-provider.env"
  BRIEF_PATH="$HOME/.agents/tasks/$PROJECT/patrol/handoffs/ancestor-bootstrap.md"
  MEMORY_WORKSPACE="$HOME/.agents/workspaces/$PROJECT/memory"
  PROJECT_LOCAL_TOML="$HOME/.agents/tasks/$PROJECT/project-local.toml"
  PROJECT_RECORD_PATH="$HOME/.agents/projects/$PROJECT/project.toml"
  GUIDE_FILE="$HOME/.agents/tasks/$PROJECT/OPERATOR-START-HERE.md"
}

ensure_host_deps() {
  note "Step 1: preflight"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] %q %q --project %q --phase bootstrap\n' \
      "$PYTHON_BIN" "$REPO_ROOT/core/preflight.py" "$PROJECT"
    return 0
  fi

  local pf_out="" pf_rc=0
  if pf_out="$("$PYTHON_BIN" "$REPO_ROOT/core/preflight.py" --project "$PROJECT" --phase bootstrap 2>&1)"; then
    pf_rc=0
  else
    pf_rc=$?
  fi
  printf '%s\n' "$pf_out"
  if [[ $pf_rc -ne 0 ]]; then
    if [[ "$pf_out" == *"HARD_BLOCKED"* ]]; then
      die 10 PREFLIGHT_FAILED "preflight 检测到 HARD_BLOCKED 项。按上面 fix_command 修复后重跑 install.sh。"
    fi
    die 10 PREFLIGHT_FAILED "preflight failed. 按上面的输出修复后重跑 install.sh。"
  fi
  echo "OK: preflight"
}

scan_machine() {
  note "Step 2: environment scan"
  run "$PYTHON_BIN" "$SCAN_SCRIPT" --output "$MEMORY_ROOT"
  [[ "$DRY_RUN" == "1" ]] && { printf '[dry-run] verify %s\n' "$MEMORY_ROOT/machine/{credentials,network,openclaw,github,current_context}.json"; return; }
  local name
  for name in credentials network openclaw github current_context; do
    [[ -f "$MEMORY_ROOT/machine/$name.json" ]] || die 2 ENV_SCAN_INCOMPLETE "missing memory artifact: $MEMORY_ROOT/machine/$name.json"
  done
}

detect_provider() {
  "$PYTHON_BIN" - "$MEMORY_ROOT/machine/credentials.json" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
if not p.is_file(): raise SystemExit(1)
d = json.loads(p.read_text(encoding="utf-8"))
def lookup(name):
    obj = d
    for part in name.split("."):
        if not isinstance(obj, dict) or part not in obj: return ""
        obj = obj[part]
    return "true" if obj is True else ("false" if obj is False else ("" if obj is None else str(obj)))

candidates = []
seen = set()
def add(mode, label, key="", base=""):
    sig = (mode, key or "", base or "")
    if sig in seen:
        return
    seen.add(sig)
    candidates.append((mode, label, key, base))

k, b = lookup("keys.MINIMAX_API_KEY.value"), lookup("keys.MINIMAX_BASE_URL.value")
if k:
    add("minimax", "claude-code + minimax (MINIMAX_API_KEY env)", k, b or "https://api.minimaxi.com/anthropic")
k, b = lookup("keys.ANTHROPIC_AUTH_TOKEN.value"), lookup("keys.ANTHROPIC_BASE_URL.value")
if k and "minimaxi.com" in b:
    add("minimax", "claude-code + minimax (ANTHROPIC_AUTH_TOKEN -> minimaxi)", k, b)
elif k and b:
    add("custom_api", f"claude-code + custom API ({b})", k, b)
k, b = lookup("keys.ANTHROPIC_API_KEY.value"), lookup("keys.ANTHROPIC_BASE_URL.value")
if k and b:
    add("custom_api", f"claude-code + custom API ({b})", k, b)
elif k:
    add("anthropic_console", "claude-code + anthropic-console (ANTHROPIC_API_KEY)", k, "")
k = lookup("keys.CLAUDE_CODE_OAUTH_TOKEN.value")
if k:
    add("oauth_token", "claude-code + oauth_token (CLAUDE_CODE_OAUTH_TOKEN)", k, "")
k, b = lookup("keys.DASHSCOPE_API_KEY.value"), lookup("keys.DASHSCOPE_BASE_URL.value")
if k:
    add("custom_api", "claude-code + custom API (DASHSCOPE_API_KEY)", k, b)
if lookup("oauth.has_any") == "true":
    add("oauth", "claude-code + host oauth (Anthropic Pro / Claude.ai login)", "", "")

for mode, label, key, base in candidates:
    print("\t".join([mode, label, key, base]))
PY
}

write_provider_env() {
  local mode="$1" key="${2:-}" base="${3:-}"
  mkdir -p "$(dirname "$PROVIDER_ENV")" || die 22 PROVIDER_ENV_DIR_FAILED "unable to create provider env directory."
  {
    printf '# generated by scripts/install.sh for project=%s\n# provider_mode=%s\n' "$PROJECT" "$mode"
    case "$mode" in
      minimax)
        export_line ANTHROPIC_BASE_URL "$base"
        export_line ANTHROPIC_AUTH_TOKEN "$key"
        export_line ANTHROPIC_MODEL "${PROVIDER_MODEL:-MiniMax-M2.7-highspeed}"
        echo 'export API_TIMEOUT_MS=3000000'
        echo 'export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1'
        echo 'unset CLAUDE_CODE_OAUTH_TOKEN ANTHROPIC_API_KEY'
        ;;
      custom_api)
        export_line ANTHROPIC_BASE_URL "$base"
        export_line ANTHROPIC_AUTH_TOKEN "$key"
        [[ -n "$PROVIDER_MODEL" ]] && export_line ANTHROPIC_MODEL "$PROVIDER_MODEL" || echo 'unset ANTHROPIC_MODEL'
        echo 'unset CLAUDE_CODE_OAUTH_TOKEN ANTHROPIC_API_KEY API_TIMEOUT_MS CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC'
        ;;
      anthropic_console)
        export_line ANTHROPIC_API_KEY "$key"
        [[ -n "$PROVIDER_MODEL" ]] && export_line ANTHROPIC_MODEL "$PROVIDER_MODEL" || echo 'unset ANTHROPIC_MODEL'
        echo 'unset CLAUDE_CODE_OAUTH_TOKEN ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL API_TIMEOUT_MS CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC'
        ;;
      oauth_token) export_line CLAUDE_CODE_OAUTH_TOKEN "$key"; echo 'unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL ANTHROPIC_MODEL API_TIMEOUT_MS CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC' ;;
      oauth) echo 'unset CLAUDE_CODE_OAUTH_TOKEN ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL ANTHROPIC_MODEL API_TIMEOUT_MS CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC' ;;
      *) die 22 PROVIDER_MODE_UNKNOWN "unknown provider mode: $mode" ;;
    esac
  } >"$PROVIDER_ENV" || die 22 PROVIDER_ENV_WRITE_FAILED "unable to write $PROVIDER_ENV"
  chmod 600 "$PROVIDER_ENV" || die 22 PROVIDER_ENV_CHMOD_FAILED "unable to chmod $PROVIDER_ENV"
}

select_provider() {
  note "Step 3: ancestor provider"
  local mode="" label="" key="" base="" reply=""
  local -a candidates=()

  if [[ -n "$FORCE_PROVIDER" && -z "$FORCE_BASE_URL" && -n "$FORCE_API_KEY" ]]; then
    case "$FORCE_PROVIDER" in
      minimax)
        [[ -n "$FORCE_MODEL" ]] || FORCE_MODEL="MiniMax-M2.7-highspeed"
        remember_provider_selection minimax "$FORCE_API_KEY" "https://api.minimaxi.com/anthropic" "$FORCE_MODEL"
        if [[ "$DRY_RUN" == "1" ]]; then
          printf '[dry-run] force provider=minimax via explicit api-key and write %s\n' "$PROVIDER_ENV"
        else
          write_provider_env minimax "$FORCE_API_KEY" "https://api.minimaxi.com/anthropic"
          printf 'Using forced provider: minimax (base_url=%s)\n' "https://api.minimaxi.com/anthropic"
        fi
        return
        ;;
      anthropic_console)
        remember_provider_selection anthropic_console "$FORCE_API_KEY" "" "$FORCE_MODEL"
        if [[ "$DRY_RUN" == "1" ]]; then
          printf '[dry-run] force provider=anthropic_console via explicit api-key and write %s\n' "$PROVIDER_ENV"
        else
          write_provider_env anthropic_console "$FORCE_API_KEY"
          printf 'Using forced provider: anthropic_console\n'
        fi
        return
        ;;
    esac
  fi

  if [[ -n "$FORCE_BASE_URL" && -n "$FORCE_API_KEY" ]]; then
    remember_provider_selection custom_api "$FORCE_API_KEY" "$FORCE_BASE_URL" "$FORCE_MODEL"
    if [[ "$DRY_RUN" == "1" ]]; then
      printf '[dry-run] force provider=custom_api via explicit flags and write %s\n' "$PROVIDER_ENV"
    else
      write_provider_env custom_api "$FORCE_API_KEY" "$FORCE_BASE_URL"
      printf 'Using: explicit custom API (base_url=%s)\n' "$FORCE_BASE_URL"
    fi
    return
  fi

  while IFS= read -r line; do
    [[ -n "$line" ]] && candidates+=("$line")
  done < <(detect_provider 2>/dev/null || true)

  if [[ -n "$FORCE_PROVIDER" ]]; then
    local c forced_found=0
    for c in "${candidates[@]-}"; do
      IFS=$'\t' read -r mode label key base <<<"$c"
      if [[ "$mode" != "$FORCE_PROVIDER" ]]; then
        continue
      fi
      forced_found=1
      case "$mode" in
        minimax) remember_provider_selection "$mode" "$key" "$base" "MiniMax-M2.7-highspeed" ;;
        *) remember_provider_selection "$mode" "$key" "$base" ;;
      esac
      if [[ "$DRY_RUN" == "1" ]]; then
        printf '[dry-run] force provider=%s via %s and write %s\n' "$FORCE_PROVIDER" "$label" "$PROVIDER_ENV"
      else
        write_provider_env "$mode" "$key" "$base"
        printf 'Using forced provider: %s\n' "$label"
      fi
      return
    done
    if (( forced_found == 1 )); then
      return
    fi
    if [[ "$DRY_RUN" == "1" && ${#candidates[@]} -eq 0 ]]; then
      case "$FORCE_PROVIDER" in
        minimax) remember_provider_selection minimax "dry-run-placeholder-key" "https://api.minimaxi.com/anthropic" "MiniMax-M2.7-highspeed" ;;
        custom_api) remember_provider_selection custom_api "dry-run-placeholder-key" "https://api.anthropic.com" "$FORCE_MODEL" ;;
        anthropic_console) remember_provider_selection anthropic_console "dry-run-placeholder-key" ;;
        oauth_token) remember_provider_selection oauth_token "dry-run-placeholder-token" ;;
        oauth) remember_provider_selection oauth ;;
        *) die 22 PROVIDER_NOT_FOUND "unsupported --provider value: $FORCE_PROVIDER" ;;
      esac
      printf '[dry-run] inspect %s and write %s\n' "$MEMORY_ROOT/machine/credentials.json" "$PROVIDER_ENV"
      return
    fi
    die 22 PROVIDER_NOT_FOUND "--provider $FORCE_PROVIDER not detected on this host"
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    if [[ ${#candidates[@]} -eq 0 ]]; then
      remember_provider_selection custom_api "dry-run-placeholder-key" "https://api.anthropic.com"
    else
      IFS=$'\t' read -r mode label key base <<<"${candidates[0]}"
      case "$mode" in
        minimax) remember_provider_selection "$mode" "$key" "$base" "MiniMax-M2.7-highspeed" ;;
        *) remember_provider_selection "$mode" "$key" "$base" ;;
      esac
    fi
    printf '[dry-run] inspect %s and write %s\n' "$MEMORY_ROOT/machine/credentials.json" "$PROVIDER_ENV"
    return
  fi

  if [[ ${#candidates[@]} -gt 0 ]]; then
    printf 'Detected %d Claude Code provider candidate(s) on this host:\n' "${#candidates[@]}"
    local i=1 c m l _k _b
    for c in "${candidates[@]}"; do
      IFS=$'\t' read -r m l _k _b <<<"$c"
      if [[ $i -eq 1 ]]; then
        printf '  [%d] %s   (recommended)\n' "$i" "$l"
      else
        printf '  [%d] %s\n' "$i" "$l"
      fi
      i=$((i+1))
    done
    printf '  [c] enter custom base_url + api_key manually\n'
    read -r -p "Choose [1]: " reply
    reply="${reply:-1}"
    if [[ "$reply" =~ ^[0-9]+$ ]] && (( reply >= 1 && reply <= ${#candidates[@]} )); then
      IFS=$'\t' read -r mode label key base <<<"${candidates[$((reply-1))]}"
      case "$mode" in
        minimax) remember_provider_selection "$mode" "$key" "$base" "MiniMax-M2.7-highspeed" ;;
        *) remember_provider_selection "$mode" "$key" "$base" ;;
      esac
      write_provider_env "$mode" "$key" "$base"
      printf 'Using: %s\n' "$label"
      return
    fi
    if [[ ! "$reply" =~ ^[Cc]$ ]]; then
      die 22 INVALID_PROVIDER_CHOICE "invalid choice: $reply (expected 1-${#candidates[@]} or c)"
    fi
  fi

  [[ -t 0 ]] || die 22 INTERACTIVE_REQUIRED "provider selection requires a tty when auto-detection is insufficient."
  if [[ ${#candidates[@]} -eq 0 ]]; then
    printf '未检测到可用的 Claude Code 登录方式。请输入：\n'
  fi
  read -r -p "  base_url (回车=官方 Anthropic): " reply; [[ -n "$reply" ]] && base="$reply"
  read -r -p "  api_key: " reply; [[ -n "$reply" ]] && key="$reply"
  [[ -n "$key" ]] || die 22 PROVIDER_INPUT_MISSING "no provider credential supplied."
  if [[ -n "$base" ]]; then
    remember_provider_selection custom_api "$key" "$base"
    write_provider_env custom_api "$key" "$base"
  else
    remember_provider_selection anthropic_console "$key"
    write_provider_env anthropic_console "$key"
  fi
}

seat_auth_mode_for_provider_mode() {
  case "$PROVIDER_MODE" in
    minimax|custom_api|anthropic_console) printf '%s\n' "api" ;;
    oauth_token) printf '%s\n' "oauth_token" ;;
    oauth) printf '%s\n' "oauth" ;;
    *) die 22 PROVIDER_MODE_UNKNOWN "unknown provider mode for seat auth mapping: ${PROVIDER_MODE:-<unset>}" ;;
  esac
}

seat_provider_for_provider_mode() {
  case "$PROVIDER_MODE" in
    minimax) printf '%s\n' "minimax" ;;
    custom_api|anthropic_console) printf '%s\n' "anthropic-console" ;;
    oauth_token|oauth) printf '%s\n' "anthropic" ;;
    *) die 22 PROVIDER_MODE_UNKNOWN "unknown provider mode for seat provider mapping: ${PROVIDER_MODE:-<unset>}" ;;
  esac
}

seat_model_for_provider_mode() {
  case "$PROVIDER_MODE" in
    minimax) printf '%s\n' "${PROVIDER_MODEL:-MiniMax-M2.7-highspeed}" ;;
    custom_api|anthropic_console) [[ -n "$PROVIDER_MODEL" ]] && printf '%s\n' "$PROVIDER_MODEL" || true ;;
    *) return 0 ;;
  esac
}

write_bootstrap_template() {
  local seat_auth_mode seat_provider seat_model
  seat_auth_mode="$(seat_auth_mode_for_provider_mode)"
  seat_provider="$(seat_provider_for_provider_mode)"
  seat_model="$(seat_model_for_provider_mode || true)"

  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] write %s\n' "$BOOTSTRAP_TEMPLATE_PATH"
    return 0
  fi

  mkdir -p "$BOOTSTRAP_TEMPLATE_DIR" || die 31 TEMPLATE_DIR_CREATE_FAILED "unable to create $BOOTSTRAP_TEMPLATE_DIR"
  cat >"$BOOTSTRAP_TEMPLATE_PATH" <<EOF
version = 1
template_name = "$CLAWSEAT_TEMPLATE_NAME"
description = "install.sh-generated ClawSeat spawn template"

[defaults]
window_mode = "tabs-1up"
monitor_max_panes = 5
open_detail_windows = false

[[engineers]]
id = "ancestor"
display_name = "Ancestor"
role = "ancestor"
monitor = true
tool = "claude"
auth_mode = "$seat_auth_mode"
provider = "$seat_provider"
EOF
  if [[ -n "$seat_model" ]]; then
    printf 'model = "%s"\n' "$seat_model" >>"$BOOTSTRAP_TEMPLATE_PATH"
  fi

  local seat role title
  for seat in "${PENDING_SEATS[@]}"; do
    role="$seat"
    title="$(printf '%s%s' "$(printf '%s' "${seat:0:1}" | tr '[:lower:]' '[:upper:]')" "${seat:1}")"
    cat >>"$BOOTSTRAP_TEMPLATE_PATH" <<EOF

[[engineers]]
id = "$seat"
display_name = "$title"
role = "$role"
monitor = true
tool = "claude"
auth_mode = "$seat_auth_mode"
provider = "$seat_provider"
EOF
    if [[ -n "$seat_model" ]]; then
      printf 'model = "%s"\n' "$seat_model" >>"$BOOTSTRAP_TEMPLATE_PATH"
    fi
  done
  chmod 600 "$BOOTSTRAP_TEMPLATE_PATH" || die 31 TEMPLATE_CHMOD_FAILED "unable to chmod $BOOTSTRAP_TEMPLATE_PATH"
}

write_project_local_toml() {
  local seat_auth_mode seat_provider seat_model seat
  seat_auth_mode="$(seat_auth_mode_for_provider_mode)"
  seat_provider="$(seat_provider_for_provider_mode)"
  seat_model="$(seat_model_for_provider_mode || true)"

  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] write %s\n' "$PROJECT_LOCAL_TOML"
    return 0
  fi

  mkdir -p "$(dirname "$PROJECT_LOCAL_TOML")" || die 31 PROJECT_LOCAL_DIR_FAILED "unable to create $(dirname "$PROJECT_LOCAL_TOML")"
  cat >"$PROJECT_LOCAL_TOML" <<EOF
project_name = "$PROJECT"
repo_root = "$REPO_ROOT"
seat_order = ["ancestor", "planner", "builder", "reviewer", "qa", "designer"]

[[overrides]]
id = "ancestor"
session_name = "$PROJECT-ancestor"
tool = "claude"
auth_mode = "$seat_auth_mode"
provider = "$seat_provider"
EOF
  if [[ -n "$seat_model" ]]; then
    printf 'model = "%s"\n' "$seat_model" >>"$PROJECT_LOCAL_TOML"
  fi

  for seat in "${PENDING_SEATS[@]}"; do
    cat >>"$PROJECT_LOCAL_TOML" <<EOF

[[overrides]]
id = "$seat"
tool = "claude"
auth_mode = "$seat_auth_mode"
provider = "$seat_provider"
EOF
    if [[ -n "$seat_model" ]]; then
      printf 'model = "%s"\n' "$seat_model" >>"$PROJECT_LOCAL_TOML"
    fi
  done
  chmod 600 "$PROJECT_LOCAL_TOML" || die 31 PROJECT_LOCAL_CHMOD_FAILED "unable to chmod $PROJECT_LOCAL_TOML"
}

seat_secret_file_for() {
  local seat="$1" seat_auth_mode seat_provider
  seat_auth_mode="$(seat_auth_mode_for_provider_mode)"
  seat_provider="$(seat_provider_for_provider_mode)"
  case "$seat_auth_mode" in
    api) printf '%s\n' "$HOME/.agents/secrets/claude/$seat_provider/$seat.env" ;;
    oauth|oauth_token) return 0 ;;
    *) die 22 PROVIDER_MODE_UNKNOWN "unsupported seat auth mode for secret seeding: $seat_auth_mode" ;;
  esac
}

write_bootstrap_secret_file() {
  local path="$1"
  mkdir -p "$(dirname "$path")" || die 31 PROJECT_SECRET_DIR_FAILED "unable to create $(dirname "$path")"
  {
    printf '# generated by scripts/install.sh for project=%s\n' "$PROJECT"
    case "$PROVIDER_MODE" in
      minimax)
        export_line ANTHROPIC_AUTH_TOKEN "$PROVIDER_KEY"
        export_line ANTHROPIC_BASE_URL "${PROVIDER_BASE:-https://api.minimaxi.com/anthropic}"
        export_line ANTHROPIC_MODEL "${PROVIDER_MODEL:-MiniMax-M2.7-highspeed}"
        ;;
      custom_api)
        export_line ANTHROPIC_API_KEY "$PROVIDER_KEY"
        export_line ANTHROPIC_AUTH_TOKEN "$PROVIDER_KEY"
        export_line ANTHROPIC_BASE_URL "${PROVIDER_BASE:-https://api.anthropic.com}"
        if [[ -n "$PROVIDER_MODEL" ]]; then
          export_line ANTHROPIC_MODEL "$PROVIDER_MODEL"
        fi
        ;;
      anthropic_console)
        export_line ANTHROPIC_API_KEY "$PROVIDER_KEY"
        if [[ -n "$PROVIDER_BASE" ]]; then
          export_line ANTHROPIC_BASE_URL "$PROVIDER_BASE"
        fi
        if [[ -n "$PROVIDER_MODEL" ]]; then
          export_line ANTHROPIC_MODEL "$PROVIDER_MODEL"
        fi
        ;;
      oauth_token)
        export_line CLAUDE_CODE_OAUTH_TOKEN "$PROVIDER_KEY"
        ;;
      oauth)
        ;;
      *)
        die 22 PROVIDER_MODE_UNKNOWN "unknown provider mode for secret seeding: $PROVIDER_MODE"
        ;;
    esac
  } >"$path" || die 31 PROJECT_SECRET_WRITE_FAILED "unable to write $path"
  chmod 600 "$path" || die 31 PROJECT_SECRET_CHMOD_FAILED "unable to chmod $path"
}

seed_bootstrap_secrets() {
  note "Step 5.6: seed default seat secrets"
  local seat secret_path
  if [[ "$DRY_RUN" == "1" ]]; then
    for seat in "${PENDING_SEATS[@]}"; do
      secret_path="$(seat_secret_file_for "$seat" || true)"
      [[ -n "$secret_path" ]] && printf '[dry-run] write %s\n' "$secret_path"
    done
    return 0
  fi

  for seat in "${PENDING_SEATS[@]}"; do
    secret_path="$(seat_secret_file_for "$seat" || true)"
    [[ -n "$secret_path" ]] || continue
    write_bootstrap_secret_file "$secret_path"
  done
}

bootstrap_project_profile() {
  note "Step 5.5: bootstrap project engineer profiles (no tmux start)"
  [[ -f "$WAIT_FOR_SEAT_SCRIPT" || "$DRY_RUN" == "1" ]] || die 31 WAIT_SCRIPT_MISSING "missing wait-for-seat script: $WAIT_FOR_SEAT_SCRIPT"
  [[ -f "$AGENT_ADMIN_SCRIPT" || "$DRY_RUN" == "1" ]] || die 31 AGENT_ADMIN_MISSING "missing agent_admin script: $AGENT_ADMIN_SCRIPT"
  write_bootstrap_template
  write_project_local_toml

  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] (cd %q && %q %q project bootstrap --template %q --local %q)\n' \
      "$AGENTS_TEMPLATES_ROOT" "$PYTHON_BIN" "$AGENT_ADMIN_SCRIPT" "$CLAWSEAT_TEMPLATE_NAME" "$PROJECT_LOCAL_TOML"
    seed_bootstrap_secrets
    return 0
  fi

  if [[ -f "$PROJECT_RECORD_PATH" ]]; then
    printf 'Project %s already exists at %s; skipping bootstrap.\n' "$PROJECT" "$PROJECT_RECORD_PATH"
    return 0
  fi

  mkdir -p "$AGENTS_TEMPLATES_ROOT" || die 31 TEMPLATE_ROOT_CREATE_FAILED "unable to create $AGENTS_TEMPLATES_ROOT"
  (
    cd "$AGENTS_TEMPLATES_ROOT" &&
    "$PYTHON_BIN" "$AGENT_ADMIN_SCRIPT" project bootstrap --template "$CLAWSEAT_TEMPLATE_NAME" --local "$PROJECT_LOCAL_TOML"
  ) || die 31 PROJECT_BOOTSTRAP_FAILED "unable to bootstrap project profile via agent_admin: $PROJECT"
  seed_bootstrap_secrets
}

render_brief() {
  note "Step 4: render ancestor brief"
  [[ -f "$TEMPLATE_PATH" || "$DRY_RUN" == "1" ]] || die 30 TEMPLATE_MISSING "missing template: $TEMPLATE_PATH"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] render %s -> %s\n' "$TEMPLATE_PATH" "$BRIEF_PATH"
  else
    "$PYTHON_BIN" - "$TEMPLATE_PATH" "$BRIEF_PATH" "$PROJECT" "$REPO_ROOT" "$REAL_HOME" <<'PY'
from pathlib import Path
from string import Template
import sys
out = Path(sys.argv[2]); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(Template(Path(sys.argv[1]).read_text(encoding="utf-8")).safe_substitute(PROJECT_NAME=sys.argv[3], CLAWSEAT_ROOT=sys.argv[4], AGENT_HOME=sys.argv[5]), encoding="utf-8")
PY
    chmod 600 "$BRIEF_PATH" || die 30 BRIEF_CHMOD_FAILED "unable to chmod $BRIEF_PATH"
  fi
}

write_operator_guide() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] write %s\n' "$GUIDE_FILE"
    return 0
  fi

  mkdir -p "$(dirname "$GUIDE_FILE")" || die 30 GUIDE_DIR_FAILED "unable to create $(dirname "$GUIDE_FILE")"
  cat >"$GUIDE_FILE" <<EOF
# Operator — ClawSeat $PROJECT 启动指引

install.sh 已完成。现在做 3 件事：

1. 切到 iTerm 窗口 "clawseat-$PROJECT" 的 ancestor pane（左上角第一格）
2. 在 ancestor pane 粘贴以下 prompt（ctrl+V 或 cmd+V）：

---
读 \$CLAWSEAT_ANCESTOR_BRIEF 开始 Phase-A。

Phase-A 不让 memory 做同步调研。B2.5 / B5 都按 brief 由 ancestor 自己 Read openclaw / binding 文件；memory 在 Phase-A 唯一位置是 B7 后接收 phase-a-decisions learnings。

然后按 B3 / B3.5 / B5 / B6 / B7 顺序推进；用 agent_admin.py session start-engineer 逐个拉起 seat（不要 fan-out，一个一个来）。
---

3. 每走完一步向 ancestor 说"继续"或给修正（provider / chat_id 等）
EOF
  chmod 600 "$GUIDE_FILE" || die 30 GUIDE_CHMOD_FAILED "unable to chmod $GUIDE_FILE"
}

print_operator_banner() {
  printf '\n'
  printf '╔════════════════════════════════════════════════════════════════╗\n'
  printf '║  ClawSeat install complete                                   ║\n'
  printf '║                                                              ║\n'
  printf '║  NEXT STEPS: cat %s\n' "$GUIDE_FILE"
  printf '║                                                              ║\n'
  printf '║  Or read the file at: %s\n' "$GUIDE_FILE"
  printf '╚════════════════════════════════════════════════════════════════╝\n'
  printf '\n'
}

launcher_auth_for_provider() {
  case "$PROVIDER_MODE" in
    minimax|custom_api|anthropic_console) printf '%s\n' "custom" ;;
    oauth_token) printf '%s\n' "oauth_token" ;;
    oauth) printf '%s\n' "oauth" ;;
    *) die 22 PROVIDER_MODE_UNKNOWN "unknown provider mode for launcher auth mapping: ${PROVIDER_MODE:-<unset>}" ;;
  esac
}

launcher_custom_env_file_for_session() {
  local session="$1" safe_session api_key="" base_url="" model=""
  case "$PROVIDER_MODE" in
    minimax)
      api_key="$PROVIDER_KEY"
      base_url="${PROVIDER_BASE:-https://api.minimaxi.com/anthropic}"
      model="${PROVIDER_MODEL:-MiniMax-M2.7-highspeed}"
      ;;
    custom_api)
      api_key="$PROVIDER_KEY"
      base_url="$PROVIDER_BASE"
      model="$PROVIDER_MODEL"
      ;;
    anthropic_console)
      api_key="$PROVIDER_KEY"
      base_url="${PROVIDER_BASE:-https://api.anthropic.com}"
      model="$PROVIDER_MODEL"
      ;;
    *)
      return 0
      ;;
  esac

  safe_session="${session//[^A-Za-z0-9_.-]/_}"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '/tmp/clawseat-install-%s.env\n' "$safe_session"
    return 0
  fi
  [[ -n "$api_key" ]] || die 22 PROVIDER_INPUT_MISSING "no provider credential available for launcher custom env."

  local env_file=""
  env_file="$(mktemp "/tmp/clawseat-install-${safe_session}.XXXXXX")" \
    || die 22 PROVIDER_ENV_WRITE_FAILED "unable to create launcher custom env file."
  chmod 600 "$env_file" || die 22 PROVIDER_ENV_CHMOD_FAILED "unable to chmod $env_file"
  {
    printf 'export LAUNCHER_CUSTOM_API_KEY=%q\n' "$api_key"
    if [[ -n "$base_url" ]]; then
      printf 'export LAUNCHER_CUSTOM_BASE_URL=%q\n' "$base_url"
    fi
    if [[ -n "$model" ]]; then
      printf 'export LAUNCHER_CUSTOM_MODEL=%q\n' "$model"
    fi
  } >"$env_file" || die 22 PROVIDER_ENV_WRITE_FAILED "unable to write $env_file"
  printf '%s\n' "$env_file"
}

launch_seat() {
  local session="$1" cwd="${2:-$REPO_ROOT}" brief_path="${3:-}" auth_mode="" custom_env_file=""
  auth_mode="$(launcher_auth_for_provider)"
  custom_env_file="$(launcher_custom_env_file_for_session "$session")"

  if [[ "$DRY_RUN" == "1" ]]; then
    run tmux kill-session -t "=$session"
  else
    tmux kill-session -t "=$session" 2>/dev/null || true
    mkdir -p "$cwd" || die 31 TMUX_CWD_CREATE_FAILED "unable to create launcher cwd: $cwd"
  fi

  local -a cmd=(env "CLAWSEAT_ROOT=$CLAWSEAT_ROOT")
  [[ -n "$brief_path" ]] && cmd+=("CLAWSEAT_ANCESTOR_BRIEF=$brief_path")
  cmd+=(bash "$LAUNCHER_SCRIPT" --headless --tool claude --auth "$auth_mode" --dir "$cwd" --session "$session")
  [[ -n "$custom_env_file" ]] && cmd+=(--custom-env-file "$custom_env_file")
  [[ "$DRY_RUN" == "1" ]] && cmd+=(--dry-run)

  if [[ "$DRY_RUN" == "1" ]]; then
    run "${cmd[@]}"
    return 0
  fi

  if ! "${cmd[@]}"; then
    [[ -n "$custom_env_file" && -f "$custom_env_file" ]] && rm -f "$custom_env_file"
    die 31 TMUX_SESSION_CREATE_FAILED "unable to launch tmux session via agent-launcher: $session"
  fi
}

install_memory_hook() {
  note "Step 7.5: install memory Stop-hook"
  if [[ "$DRY_RUN" == "1" ]]; then
    run "$PYTHON_BIN" "$MEMORY_HOOK_INSTALLER" --workspace "$MEMORY_WORKSPACE" --clawseat-root "$CLAWSEAT_ROOT" --dry-run
    return 0
  fi
  mkdir -p "$MEMORY_WORKSPACE" || die 32 MEMORY_WORKSPACE_CREATE_FAILED "unable to create memory workspace: $MEMORY_WORKSPACE"
  "$PYTHON_BIN" "$MEMORY_HOOK_INSTALLER" --workspace "$MEMORY_WORKSPACE" --clawseat-root "$CLAWSEAT_ROOT" \
    || die 32 MEMORY_HOOK_INSTALL_FAILED "failed to install memory Stop-hook into $MEMORY_WORKSPACE"
}

open_iterm_window() {
  local payload="$1" target_var="$2" err_file out status
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] %q %q <<JSON\n%s\nJSON\n' "$PYTHON_BIN" "$ITERM_DRIVER" "$payload"
    printf -v "$target_var" '%s' "dry-run-$target_var"; return
  fi
  [[ "$(uname -s)" == "Darwin" ]] || die 40 ITERM_MACOS_ONLY "native iTerm panes require macOS."
  "$PYTHON_BIN" -c 'import iterm2' >/dev/null 2>&1 || die 40 ITERM2_PYTHON_MISSING "missing iterm2 module; install with: pip3 install --user --break-system-packages iterm2"
  err_file="$(mktemp)"
  out="$(printf '%s' "$payload" | "$PYTHON_BIN" "$ITERM_DRIVER" 2>"$err_file")" || { cat "$err_file" >&2; rm -f "$err_file"; die 40 ITERM_DRIVER_FAILED "iTerm pane driver execution failed."; }
  [[ ! -s "$err_file" ]] || cat "$err_file" >&2; rm -f "$err_file"
  status="$(printf '%s' "$out" | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin).get("status",""))' 2>/dev/null || true)"
  [[ "$status" == "ok" ]] || die 40 ITERM_LAYOUT_FAILED "$(printf '%s' "$out" | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin).get("reason","driver returned non-ok status"))' 2>/dev/null || echo "driver returned non-ok status")"
  printf -v "$target_var" '%s' "$(printf '%s' "$out" | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin).get("window_id",""))')"
}

focus_iterm_window() {
  [[ "$DRY_RUN" == "1" ]] && { printf '[dry-run] focus iTerm window %s pane %s\n' "$1" "$2"; return; }
  "$PYTHON_BIN" - "$1" "$2" <<'PY' || die 41 ITERM_FOCUS_FAILED "unable to focus iTerm window/pane."
import sys, iterm2
target_window, target_label = sys.argv[1], sys.argv[2]
async def main(connection):
    app = await iterm2.async_get_app(connection); await app.async_activate()
    for window in app.windows:
        if window.window_id != target_window: continue
        await window.async_activate()
        for tab in window.tabs:
            for session in getattr(tab, "sessions", []):
                if getattr(session, "name", "") == target_label:
                    await session.async_activate(); return
        return
    raise SystemExit(1)
iterm2.run_until_complete(main)
PY
}

grid_payload() {
  "$PYTHON_BIN" - "$PROJECT" "$WAIT_FOR_SEAT_SCRIPT" <<'PY'
import json
import shlex
import sys

project, wait_script = sys.argv[1:3]
panes = [
    {"label": "ancestor", "command": f"tmux attach -t '={project}-ancestor'"},
]
for seat in ("planner", "builder", "reviewer", "qa", "designer"):
    panes.append(
        {
            "label": seat,
            "command": "bash "
            + shlex.quote(wait_script)
            + " "
            + shlex.quote(f"{project}-{seat}"),
        }
    )
print(json.dumps({"title": f"clawseat-{project}", "panes": panes}, ensure_ascii=False))
PY
}
memory_payload() { printf '%s' '{"title":"machine-memory-claude","panes":[{"label":"memory","command":"tmux attach -t '\''=machine-memory-claude'\''"}]}'; }

main() {
  local memory_window_id=""
  parse_args "$@"; ensure_host_deps; scan_machine; select_provider; render_brief
  note "Step 5: launch ancestor seat via agent-launcher"
  launch_seat "$PROJECT-ancestor" "$REPO_ROOT" "$BRIEF_PATH"
  bootstrap_project_profile
  note "Step 7: open six-pane iTerm grid"; open_iterm_window "$(grid_payload)" GRID_WINDOW_ID
  install_memory_hook
  note "Step 8: start memory session + iTerm window"
  launch_seat "machine-memory-claude" "$MEMORY_WORKSPACE"; open_iterm_window "$(memory_payload)" memory_window_id
  note "Step 9: focus ancestor, flush, and persist operator guide"
  run sleep 3; focus_iterm_window "$GRID_WINDOW_ID" "ancestor"
  run tmux send-keys -t "$PROJECT-ancestor" Enter; run sleep 0.5; run tmux send-keys -t "$PROJECT-ancestor" Enter; run sleep 0.5; run tmux send-keys -t "$PROJECT-ancestor" Enter
  write_operator_guide
  print_operator_banner
}

main "$@"
