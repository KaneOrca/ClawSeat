#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0; PROJECT="install"; REPO_ROOT_OVERRIDE=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CLAWSEAT_ROOT="${CLAWSEAT_ROOT_OVERRIDE:-$REPO_ROOT}"
PYTHON_BIN_WAS_SET="${PYTHON_BIN+1}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
FORCE_REINSTALL=0
CALLER_HOME="${HOME:-}"

# HOME is intentionally rebound once for the whole script: keep CALLER_HOME only
# for diagnostics, and use exported HOME for all persisted user state paths.
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
ITERM_DRIVER_TIMEOUT_SECONDS=30
TEMPLATE_PATH="$REPO_ROOT/core/templates/ancestor-brief.template.md"
ANCESTOR_PATROL_TEMPLATE="$REPO_ROOT/core/templates/ancestor-patrol.plist.in"
MEMORY_HOOK_INSTALLER="$REPO_ROOT/core/skills/memory-oracle/scripts/install_memory_hook.py"
SEAT_CLAUDE_TEMPLATE_SCRIPT="$REPO_ROOT/core/scripts/seat_claude_template.py"
LAUNCHER_SCRIPT="$REPO_ROOT/core/launchers/agent-launcher.sh"
AGENT_ADMIN_SCRIPT="$REPO_ROOT/core/scripts/agent_admin.py"
SEND_AND_VERIFY_SCRIPT="$REPO_ROOT/core/shell-scripts/send-and-verify.sh"
WAIT_FOR_SEAT_SCRIPT="$REPO_ROOT/scripts/wait-for-seat.sh"
MEMORY_ROOT="$HOME/.agents/memory"; PROVIDER_ENV=""; BRIEF_PATH=""
MEMORY_WORKSPACE=""
GRID_WINDOW_ID=""
GUIDE_FILE=""
ANCESTOR_PATROL_PLIST_LABEL=""
ANCESTOR_PATROL_PLIST_PATH=""
ANCESTOR_PATROL_LOG_DIR=""
PROVIDER_MODE=""
PROVIDER_KEY=""
PROVIDER_BASE=""
PROVIDER_MODEL=""
FORCE_PROVIDER=""
FORCE_PROVIDER_CHOICE="${CLAWSEAT_INSTALL_PROVIDER:-}"
FORCE_BASE_URL=""
FORCE_API_KEY=""
FORCE_MODEL=""
STATUS_FILE=""
PROJECT_LOCAL_TOML=""
PROJECT_RECORD_PATH=""
AGENTS_TEMPLATES_ROOT="$HOME/.agents/templates"
CLAWSEAT_TEMPLATE_NAME="clawseat-default"
BOOTSTRAP_TEMPLATE_DIR=""
BOOTSTRAP_TEMPLATE_PATH=""
PENDING_SEATS=(planner builder reviewer qa designer)

die() { local n="$1" code="$2" msg="$3"; printf '%s\nERR_CODE: %s\n' "$msg" "$code" >&2; exit "$n"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
note() { printf '==> %s\n' "$*"; }
PYTHON_BIN_OVERRIDE="${PYTHON_BIN:-}"
PYTHON_BIN_VERSION=""
PYTHON_BIN_RESOLUTION=""

resolve_python_candidate() {
  local candidate="$1"
  if [[ "$candidate" == */* ]]; then
    [[ -x "$candidate" ]] || return 1
    printf '%s\n' "$candidate"
    return 0
  fi
  command -v "$candidate" 2>/dev/null || return 1
}

python_candidate_version() {
  local candidate="$1"
  "$candidate" -c 'import sys; print(".".join(str(part) for part in sys.version_info[:3]))' 2>/dev/null
}

python_version_supported() {
  local version="$1"
  local major="" minor="" patch=""
  IFS=. read -r major minor patch <<<"$version"
  [[ "$major" =~ ^[0-9]+$ && "$minor" =~ ^[0-9]+$ ]] || return 1
  (( major > 3 || (major == 3 && minor >= 11) ))
}

resolve_supported_python_bin() {
  local resolved="" version="" detail="" candidate=""
  local -a attempted=()
  local -a candidates=(
    "python3.13"
    "python3.12"
    "python3.11"
    "/opt/homebrew/bin/python3.13"
    "/opt/homebrew/bin/python3.12"
    "/opt/homebrew/bin/python3.11"
    "/usr/local/bin/python3.13"
    "/usr/local/bin/python3.12"
    "/usr/local/bin/python3.11"
    "python3"
    "python"
  )

  if [[ -n "$PYTHON_BIN_WAS_SET" && -n "$PYTHON_BIN_OVERRIDE" ]]; then
    resolved="$(resolve_python_candidate "$PYTHON_BIN_OVERRIDE" || true)"
    if [[ -z "$resolved" ]]; then
      die 2 INVALID_PYTHON_BIN \
        "PYTHON_BIN=$PYTHON_BIN_OVERRIDE was provided, but that executable was not found. ClawSeat install requires Python >= 3.11 before preflight can import. Try: PYTHON_BIN=/opt/homebrew/bin/python3.12 bash scripts/install.sh --provider 1"
    fi
    version="$(python_candidate_version "$resolved" || true)"
    if [[ -n "$version" ]] && python_version_supported "$version"; then
      PYTHON_BIN="$resolved"
      PYTHON_BIN_VERSION="$version"
      PYTHON_BIN_RESOLUTION="explicit"
      export PYTHON_BIN
      return 0
    fi
    detail="version probe failed"
    [[ -n "$version" ]] && detail="Python $version"
    die 2 INVALID_PYTHON_BIN \
      "PYTHON_BIN=$PYTHON_BIN_OVERRIDE resolves to $resolved ($detail), but ClawSeat install requires Python >= 3.11 before preflight can import. Try: PYTHON_BIN=/opt/homebrew/bin/python3.12 bash scripts/install.sh --provider 1"
  fi

  for candidate in "${candidates[@]}"; do
    resolved="$(resolve_python_candidate "$candidate" || true)"
    [[ -n "$resolved" ]] || continue
    version="$(python_candidate_version "$resolved" || true)"
    if [[ -n "$version" ]]; then
      attempted+=("$resolved=$version")
      if python_version_supported "$version"; then
        PYTHON_BIN="$resolved"
        PYTHON_BIN_VERSION="$version"
        PYTHON_BIN_RESOLUTION="auto"
        export PYTHON_BIN
        return 0
      fi
    fi
  done

  local attempted_summary="none"
  if [[ ${#attempted[@]} -gt 0 ]]; then
    attempted_summary="$(printf '%s' "${attempted[0]}")"
    local idx=1
    while (( idx < ${#attempted[@]} )); do
      attempted_summary+=", ${attempted[$idx]}"
      ((idx += 1))
    done
  fi
  die 2 MISSING_PYTHON311 \
    "No supported Python >= 3.11 found for ClawSeat install before preflight import. Detected: $attempted_summary. Install/use python3.11+ or run: PYTHON_BIN=/opt/homebrew/bin/python3.12 bash scripts/install.sh --provider 1"
}

resolve_supported_python_bin
if [[ "$PYTHON_BIN_RESOLUTION" == "auto" ]]; then
  note "Using Python $PYTHON_BIN_VERSION at $PYTHON_BIN"
fi

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

provider_config_value() {
  local query="$1"
  local tool="$2"
  local provider="${3:-}"
  "$PYTHON_BIN" - "$REPO_ROOT" "$query" "$tool" "$provider" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
query = sys.argv[2]
tool = sys.argv[3]
provider = sys.argv[4]
sys.path.insert(0, str(repo_root / "core" / "scripts"))

from agent_admin_config import provider_default_base_url, tool_default_base_url

value = ""
if query == "tool-default-base-url":
    value = tool_default_base_url(tool) or ""
elif query == "provider-default-base-url":
    value = provider_default_base_url(tool, provider) or ""
print(value)
PY
}

install_provider_default_model() {
  local provider="$1"
  "$PYTHON_BIN" - "$REPO_ROOT" "$provider" <<'PY'
from __future__ import annotations
import sys
from pathlib import Path
repo_root = Path(sys.argv[1])
provider = sys.argv[2]
sys.path.insert(0, str(repo_root / "core" / "scripts"))
from agent_admin_config import provider_default_model
print(provider_default_model('claude', provider) or '')
PY
}

CLAUDE_DEFAULTS_LOADED=0
CLAUDE_DEFAULT_BASE_URL=""
CLAUDE_MINIMAX_DEFAULT_BASE_URL=""
CLAUDE_ARK_DEFAULT_BASE_URL=""
CLAUDE_XCODE_DEFAULT_BASE_URL=""

load_claude_default_base_urls() {
  [[ "$CLAUDE_DEFAULTS_LOADED" == "1" ]] && return 0
  CLAUDE_DEFAULT_BASE_URL="$(provider_config_value tool-default-base-url claude)"
  CLAUDE_MINIMAX_DEFAULT_BASE_URL="$(provider_config_value provider-default-base-url claude minimax)"
  CLAUDE_ARK_DEFAULT_BASE_URL="$(provider_config_value provider-default-base-url claude ark)"
  CLAUDE_XCODE_DEFAULT_BASE_URL="$(provider_config_value provider-default-base-url claude xcode-best)"
  CLAUDE_DEFAULTS_LOADED=1
}

claude_tool_default_base_url() {
  load_claude_default_base_urls
  printf '%s\n' "$CLAUDE_DEFAULT_BASE_URL"
}

provider_default_base_url() {
  load_claude_default_base_urls
  case "$1" in
    minimax) printf '%s\n' "$CLAUDE_MINIMAX_DEFAULT_BASE_URL" ;;
    ark) printf '%s\n' "$CLAUDE_ARK_DEFAULT_BASE_URL" ;;
    xcode-best) printf '%s\n' "$CLAUDE_XCODE_DEFAULT_BASE_URL" ;;
    anthropic_console) printf '%s\n' "$CLAUDE_DEFAULT_BASE_URL" ;;
    *) return 1 ;;
  esac
}

provider_base_or_default() {
  local mode="$1" base="${2:-}"
  if [[ -n "$base" ]]; then
    printf '%s\n' "$base"
    return 0
  fi
  provider_default_base_url "$mode"
}

print_provider_url_notice() {
  local mode="$1" base="${2:-}"
  case "$mode" in
    minimax|ark|xcode-best)
      [[ -n "$base" ]] && printf 'Provider URL will be auto-configured to %s\n' "$base"
      ;;
  esac
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) DRY_RUN=1; shift ;;
      --project) PROJECT="$2"; shift 2 ;;
      --repo-root) REPO_ROOT_OVERRIDE="$2"; shift 2 ;;
      --provider) FORCE_PROVIDER="$2"; shift 2 ;;
      --base-url) FORCE_BASE_URL="$2"; shift 2 ;;
      --api-key) FORCE_API_KEY="$2"; shift 2 ;;
      --model) FORCE_MODEL="$2"; shift 2 ;;
      --reinstall|--force) FORCE_REINSTALL=1; shift ;;
      --template) CLAWSEAT_TEMPLATE_NAME="$2"; shift 2 ;;
      --reset-harness-memory)
        "$PYTHON_BIN" - "$REPO_ROOT" <<'PY'
import sys
sys.path.insert(0, sys.argv[1] + "/core/scripts")
from seat_harness_memory import reset_all_harness_memory
removed = reset_all_harness_memory()
if removed:
    print("reset harness memory for: " + ", ".join(sorted(removed)))
else:
    print("no harness memory files found")
PY
        exit 0
        ;;
      --help|-h) printf 'Usage: scripts/install.sh [--project <name>] [--repo-root <path>] [--template clawseat-default|clawseat-engineering|clawseat-creative] [--provider <mode|n>] [--base-url <url> --api-key <key> [--model <name>]] [--reinstall|--force] [--dry-run] [--reset-harness-memory]\n'; exit 0 ;;
      *) die 2 UNKNOWN_FLAG "unknown flag: $1" ;;
    esac
  done
  [[ "$PROJECT" =~ ^[a-z0-9-]+$ ]] || die 2 INVALID_PROJECT "project must match ^[a-z0-9-]+$"
  case "$CLAWSEAT_TEMPLATE_NAME" in
    clawseat-default|clawseat-engineering|clawseat-creative) ;;
    *) die 2 INVALID_TEMPLATE "--template must be clawseat-default | clawseat-engineering | clawseat-creative, got: $CLAWSEAT_TEMPLATE_NAME" ;;
  esac
  if [[ -n "$REPO_ROOT_OVERRIDE" ]]; then
    [[ -d "$REPO_ROOT_OVERRIDE" ]] || die 2 INVALID_REPO_ROOT "--repo-root must be an existing directory: $REPO_ROOT_OVERRIDE"
  fi
  PROJECT_REPO_ROOT="${REPO_ROOT_OVERRIDE:-$REPO_ROOT}"
  if [[ -n "$FORCE_BASE_URL" ]]; then
    [[ -n "$FORCE_API_KEY" ]] || die 2 INVALID_FLAGS "--base-url 必须和 --api-key 成对"
    [[ -z "$FORCE_PROVIDER" || "$FORCE_PROVIDER" == "custom_api" ]] \
      || die 2 INVALID_FLAGS "--base-url/--api-key 只能配 --provider custom_api 或不传 --provider"
  elif [[ -n "$FORCE_API_KEY" ]]; then
    case "$FORCE_PROVIDER" in
      minimax|anthropic_console|ark|xcode-best) ;;
      *)
        die 2 INVALID_FLAGS "--base-url 必须和 --api-key 成对"
        ;;
    esac
  fi
  if [[ -n "$FORCE_MODEL" ]]; then
    if [[ -n "$FORCE_BASE_URL" && -n "$FORCE_API_KEY" ]]; then
      :
    elif [[ -n "$FORCE_API_KEY" && ( "$FORCE_PROVIDER" == "minimax" || "$FORCE_PROVIDER" == "anthropic_console" || "$FORCE_PROVIDER" == "ark" || "$FORCE_PROVIDER" == "xcode-best" ) ]]; then
      :
    else
      die 2 INVALID_FLAGS "--model 只能与 --base-url/--api-key 一起使用，或配合 --provider minimax|anthropic_console|ark|xcode-best + --api-key"
    fi
  fi
  STATUS_FILE="$HOME/.agents/tasks/$PROJECT/STATUS.md"
  PROVIDER_ENV="$HOME/.agents/tasks/$PROJECT/ancestor-provider.env"
  BRIEF_PATH="$HOME/.agents/tasks/$PROJECT/patrol/handoffs/ancestor-bootstrap.md"
  MEMORY_WORKSPACE="$HOME/.agents/workspaces/$PROJECT/memory"
  PROJECT_LOCAL_TOML="$HOME/.agents/tasks/$PROJECT/project-local.toml"
  PROJECT_RECORD_PATH="$HOME/.agents/projects/$PROJECT/project.toml"
  GUIDE_FILE="$HOME/.agents/tasks/$PROJECT/OPERATOR-START-HERE.md"
  ANCESTOR_PATROL_PLIST_LABEL="com.clawseat.${PROJECT}.ancestor-patrol"
  ANCESTOR_PATROL_PLIST_PATH="$HOME/Library/LaunchAgents/${ANCESTOR_PATROL_PLIST_LABEL}.plist"
  ANCESTOR_PATROL_LOG_DIR="$HOME/.agents/tasks/$PROJECT/patrol/logs"
  BOOTSTRAP_TEMPLATE_DIR="$AGENTS_TEMPLATES_ROOT/$CLAWSEAT_TEMPLATE_NAME"
  BOOTSTRAP_TEMPLATE_PATH="$BOOTSTRAP_TEMPLATE_DIR/template.toml"
}

resolve_pending_seats() {
  # For clawseat-default, keep the hardcoded list (generated template, no file to read).
  [[ "$CLAWSEAT_TEMPLATE_NAME" == "clawseat-default" ]] && return 0
  local template_file="$REPO_ROOT/templates/${CLAWSEAT_TEMPLATE_NAME}.toml"
  [[ -f "$template_file" ]] || return 0  # fallback to hardcoded if not found
  local seats
  seats="$("$PYTHON_BIN" - "$template_file" <<'PY'
import sys
try:
    import tomllib
except ImportError:
    import tomli as tomllib
with open(sys.argv[1], "rb") as f:
    data = tomllib.load(f)
seats = [e["id"] for e in data.get("engineers", []) if e.get("id") != "ancestor"]
print(" ".join(seats))
PY
  2>/dev/null)"
  [[ -n "$seats" ]] && read -ra PENDING_SEATS <<< "$seats"
}

normalize_provider_choice() {
  if [[ "$FORCE_PROVIDER" =~ ^[0-9]+$ ]]; then
    FORCE_PROVIDER_CHOICE="$FORCE_PROVIDER"
    FORCE_PROVIDER=""
  fi
  if [[ -n "$FORCE_PROVIDER_CHOICE" && ! "$FORCE_PROVIDER_CHOICE" =~ ^[0-9]+$ ]]; then
    FORCE_PROVIDER_CHOICE=""
  fi
}

ensure_host_deps() {
  note "Step 1: preflight"
  if [[ "$FORCE_REINSTALL" != "1" && -f "$STATUS_FILE" ]] && grep -q '^phase=ready$' "$STATUS_FILE"; then
    printf 'Project %s already installed (phase=ready) at %s.\n' "$PROJECT" "$STATUS_FILE"
    printf 'Use --reinstall or --force to rebuild.\n'
    exit 0
  fi
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

ensure_python_tomllib_fallback() {
  note "Step 2.5: ensure Python tomllib fallback"
  if "$PYTHON_BIN" -c 'import tomllib' >/dev/null 2>&1; then
    return 0
  fi
  if "$PYTHON_BIN" -c 'import tomli' >/dev/null 2>&1; then
    return 0
  fi
  "$PYTHON_BIN" -m pip install --user --quiet tomli >/dev/null 2>&1 || true
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
  "$PYTHON_BIN" - "$REPO_ROOT" "$MEMORY_ROOT/machine/credentials.json" <<'PY'
import json, sys
from pathlib import Path
repo_root = Path(sys.argv[1])
sys.path.insert(0, str(repo_root / "core" / "scripts"))

from agent_admin_config import provider_default_base_url, provider_url_matches

p = Path(sys.argv[2])
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
    default_base = provider_default_base_url("claude", "minimax") or ""
    add("minimax", "claude-code + minimax (MINIMAX_API_KEY env)", k, b or default_base)
k, b = lookup("keys.ANTHROPIC_AUTH_TOKEN.value"), lookup("keys.ANTHROPIC_BASE_URL.value")
if k and provider_url_matches("claude", "minimax", b):
    add("minimax", "claude-code + minimax (ANTHROPIC_AUTH_TOKEN -> minimaxi)", k, b)
elif k and provider_url_matches("claude", "xcode-best", b):
    add("xcode-best", "claude-code + xcode-best (ANTHROPIC_AUTH_TOKEN -> xcode.best)", k, b)
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
k, b = lookup("keys.ARK_API_KEY.value"), lookup("keys.ARK_BASE_URL.value")
if k:
    default_base = provider_default_base_url("claude", "ark") or ""
    add("ark", f"claude-code + ARK 火山方舟 ({b or default_base})", k, b or default_base)
if lookup("oauth.has_any") == "true":
    add("oauth", "claude-code + host oauth (Anthropic Pro / Claude.ai login)", "", "")

for mode, label, key, base in candidates:
    print("\t".join([mode, label, key, base]))
PY
}

write_provider_env() {
  local mode="$1" key="${2:-}" base="${3:-}"
  local resolved_base=""
  mkdir -p "$(dirname "$PROVIDER_ENV")" || die 22 PROVIDER_ENV_DIR_FAILED "unable to create provider env directory."
  {
    printf '# generated by scripts/install.sh for project=%s\n# provider_mode=%s\n' "$PROJECT" "$mode"
    case "$mode" in
      minimax)
        resolved_base="$(provider_base_or_default minimax "$base")"
        export_line ANTHROPIC_BASE_URL "$resolved_base"
        export_line ANTHROPIC_AUTH_TOKEN "$key"
        export_line ANTHROPIC_MODEL "${PROVIDER_MODEL:-MiniMax-M2.7-highspeed}"
        echo 'export API_TIMEOUT_MS=3000000'
        echo 'export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1'
        echo 'unset CLAUDE_CODE_OAUTH_TOKEN ANTHROPIC_API_KEY'
        ;;
      ark)
        resolved_base="$(provider_base_or_default ark "$base")"
        export_line ANTHROPIC_BASE_URL "$resolved_base"
        export_line ANTHROPIC_AUTH_TOKEN "$key"
        export_line ANTHROPIC_MODEL "${PROVIDER_MODEL:-ark-code-latest}"
        echo 'export API_TIMEOUT_MS=3000000'
        echo 'export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1'
        echo 'unset CLAUDE_CODE_OAUTH_TOKEN ANTHROPIC_API_KEY'
        ;;
      xcode-best)
        resolved_base="$(provider_base_or_default xcode-best "$base")"
        export_line ANTHROPIC_BASE_URL "$resolved_base"
        export_line ANTHROPIC_AUTH_TOKEN "$key"
        [[ -n "$PROVIDER_MODEL" ]] && export_line ANTHROPIC_MODEL "$PROVIDER_MODEL" || echo 'unset ANTHROPIC_MODEL'
        echo 'unset CLAUDE_CODE_OAUTH_TOKEN ANTHROPIC_API_KEY API_TIMEOUT_MS CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC'
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

select_provider_candidate() {
  local choice="$1"
  shift
  local -a candidates=("$@")
  local mode label key base

  if [[ ! "$choice" =~ ^[0-9]+$ ]]; then
    die 22 INVALID_PROVIDER_CHOICE "invalid provider choice: $choice"
  fi
  if (( choice < 1 || choice > ${#candidates[@]} )); then
    die 22 PROVIDER_NOT_FOUND "requested provider choice $choice but only ${#candidates[@]} candidate(s) were detected"
  fi

  IFS=$'\t' read -r mode label key base <<<"${candidates[$((choice-1))]}"
  case "$mode" in
    minimax) remember_provider_selection minimax "$key" "$base" "$(install_provider_default_model minimax)" ;;
    ark) remember_provider_selection ark "$key" "$base" "$(install_provider_default_model ark)" ;;
    xcode-best) remember_provider_selection xcode-best "$key" "$base" "$FORCE_MODEL" ;;
    *) remember_provider_selection "$mode" "$key" "$base" ;;
  esac

  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] choose provider #%s via %s and write %s\n' "$choice" "$label" "$PROVIDER_ENV"
  else
    write_provider_env "$mode" "$key" "$base"
    print_provider_url_notice "$mode" "$(provider_base_or_default "$mode" "$base" || true)"
    printf 'Using selected provider candidate #%s: %s\n' "$choice" "$label"
  fi
}

select_provider() {
  note "Step 3: ancestor provider"
  local mode="" label="" key="" base="" reply=""
  local -a candidates=()

  if [[ -n "$FORCE_PROVIDER" && -z "$FORCE_BASE_URL" && -n "$FORCE_API_KEY" ]]; then
    case "$FORCE_PROVIDER" in
      minimax)
        [[ -n "$FORCE_MODEL" ]] || FORCE_MODEL="MiniMax-M2.7-highspeed"
        remember_provider_selection minimax "$FORCE_API_KEY" "$(provider_base_or_default minimax)" "$FORCE_MODEL"
        if [[ "$DRY_RUN" == "1" ]]; then
          printf '[dry-run] force provider=minimax via explicit api-key and write %s\n' "$PROVIDER_ENV"
        else
          write_provider_env minimax "$FORCE_API_KEY" "$(provider_base_or_default minimax)"
          print_provider_url_notice minimax "$(provider_base_or_default minimax)"
          printf 'Using forced provider: minimax (base_url=%s)\n' "$(provider_base_or_default minimax)"
        fi
        return
        ;;
      ark)
        [[ -n "$FORCE_MODEL" ]] || FORCE_MODEL="ark-code-latest"
        remember_provider_selection ark "$FORCE_API_KEY" "$(provider_base_or_default ark)" "$FORCE_MODEL"
        if [[ "$DRY_RUN" == "1" ]]; then
          printf '[dry-run] force provider=ark via explicit api-key and write %s\n' "$PROVIDER_ENV"
        else
          write_provider_env ark "$FORCE_API_KEY" "$(provider_base_or_default ark)"
          print_provider_url_notice ark "$(provider_base_or_default ark)"
          printf 'Using forced provider: ark (base_url=%s)\n' "$(provider_base_or_default ark)"
        fi
        return
        ;;
      xcode-best)
        remember_provider_selection xcode-best "$FORCE_API_KEY" "$(provider_base_or_default xcode-best)" "$FORCE_MODEL"
        if [[ "$DRY_RUN" == "1" ]]; then
          printf '[dry-run] force provider=xcode-best via explicit api-key and write %s\n' "$PROVIDER_ENV"
        else
          write_provider_env xcode-best "$FORCE_API_KEY" "$(provider_base_or_default xcode-best)"
          print_provider_url_notice xcode-best "$(provider_base_or_default xcode-best)"
          printf 'Using forced provider: xcode-best (base_url=%s)\n' "$(provider_base_or_default xcode-best)"
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

  if [[ -n "$FORCE_PROVIDER_CHOICE" ]]; then
    select_provider_candidate "$FORCE_PROVIDER_CHOICE" "${candidates[@]}"
    return
  fi

  if [[ -n "$FORCE_PROVIDER" ]]; then
    local c forced_found=0
    for c in "${candidates[@]-}"; do
      IFS=$'\t' read -r mode label key base <<<"$c"
      if [[ "$mode" != "$FORCE_PROVIDER" ]]; then
        continue
      fi
      forced_found=1
      case "$mode" in
        minimax) remember_provider_selection "$mode" "$key" "$base" "$(install_provider_default_model "$mode")" ;;
        ark) remember_provider_selection "$mode" "$key" "$base" "$(install_provider_default_model "$mode")" ;;
        xcode-best) remember_provider_selection "$mode" "$key" "$base" "$FORCE_MODEL" ;;
        *) remember_provider_selection "$mode" "$key" "$base" ;;
      esac
      if [[ "$DRY_RUN" == "1" ]]; then
        printf '[dry-run] force provider=%s via %s and write %s\n' "$FORCE_PROVIDER" "$label" "$PROVIDER_ENV"
      else
        write_provider_env "$mode" "$key" "$base"
        print_provider_url_notice "$mode" "$(provider_base_or_default "$mode" "$base" || true)"
        printf 'Using forced provider: %s\n' "$label"
      fi
      return
    done
    if (( forced_found == 1 )); then
      return
    fi
    if [[ "$DRY_RUN" == "1" && ${#candidates[@]} -eq 0 ]]; then
      case "$FORCE_PROVIDER" in
        minimax) remember_provider_selection minimax "dry-run-placeholder-key" "$(provider_base_or_default minimax)" "$(install_provider_default_model minimax)" ;;
        ark) remember_provider_selection ark "dry-run-placeholder-key" "$(provider_base_or_default ark)" "$(install_provider_default_model ark)" ;;
        xcode-best) remember_provider_selection xcode-best "dry-run-placeholder-key" "$(provider_base_or_default xcode-best)" "$FORCE_MODEL" ;;
        custom_api) remember_provider_selection custom_api "dry-run-placeholder-key" "$(claude_tool_default_base_url)" "$FORCE_MODEL" ;;
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
    printf 'Project: %s\n' "$PROJECT"
    if [[ ${#candidates[@]} -eq 0 ]]; then
      remember_provider_selection custom_api "dry-run-placeholder-key" "$(claude_tool_default_base_url)"
    else
      IFS=$'\t' read -r mode label key base <<<"${candidates[0]}"
      case "$mode" in
        minimax) remember_provider_selection "$mode" "$key" "$base" "$(install_provider_default_model minimax)" ;;
        ark) remember_provider_selection "$mode" "$key" "$base" "$(install_provider_default_model ark)" ;;
        xcode-best) remember_provider_selection "$mode" "$key" "$base" "$FORCE_MODEL" ;;
        *) remember_provider_selection "$mode" "$key" "$base" ;;
      esac
    fi
    printf '[dry-run] inspect %s and write %s\n' "$MEMORY_ROOT/machine/credentials.json" "$PROVIDER_ENV"
    return
  fi

  if [[ ${#candidates[@]} -gt 0 ]]; then
    printf 'Project: %s\n' "$PROJECT"
    printf 'Detected %d Claude Code provider candidate(s) on this host:\n' "${#candidates[@]}"
    local i=1 c m l _k _b mdl
    for c in "${candidates[@]}"; do
      IFS=$'\t' read -r m l _k _b <<<"$c"
      mdl="$(install_provider_default_model "$m" 2>/dev/null || true)"
      if [[ $i -eq 1 ]]; then
        if [[ -n "$mdl" ]]; then
          printf '  [%d] %s  (model: %s)  (recommended)\n' "$i" "$l" "$mdl"
        else
          printf '  [%d] %s   (recommended)\n' "$i" "$l"
        fi
      else
        if [[ -n "$mdl" ]]; then
          printf '  [%d] %s  (model: %s)\n' "$i" "$l" "$mdl"
        else
          printf '  [%d] %s\n' "$i" "$l"
        fi
      fi
      i=$((i+1))
    done
    printf '  [c] enter custom base_url + api_key manually\n'
    read -r -p "Choose [1]: " reply
    reply="${reply:-1}"
    if [[ "$reply" =~ ^[0-9]+$ ]] && (( reply >= 1 && reply <= ${#candidates[@]} )); then
      IFS=$'\t' read -r mode label key base <<<"${candidates[$((reply-1))]}"
      case "$mode" in
        minimax) remember_provider_selection "$mode" "$key" "$base" "$(install_provider_default_model minimax)" ;;
        ark) remember_provider_selection "$mode" "$key" "$base" "$(install_provider_default_model ark)" ;;
        xcode-best) remember_provider_selection "$mode" "$key" "$base" "$FORCE_MODEL" ;;
        *) remember_provider_selection "$mode" "$key" "$base" ;;
      esac
      write_provider_env "$mode" "$key" "$base"
      print_provider_url_notice "$mode" "$(provider_base_or_default "$mode" "$base" || true)"
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
    minimax|ark|xcode-best|custom_api|anthropic_console) printf '%s\n' "api" ;;
    oauth_token) printf '%s\n' "oauth_token" ;;
    oauth) printf '%s\n' "oauth" ;;
    *) die 22 PROVIDER_MODE_UNKNOWN "unknown provider mode for seat auth mapping: ${PROVIDER_MODE:-<unset>}" ;;
  esac
}

seat_provider_for_provider_mode() {
  case "$PROVIDER_MODE" in
    minimax) printf '%s\n' "minimax" ;;
    ark) printf '%s\n' "ark" ;;
    xcode-best) printf '%s\n' "xcode-best" ;;
    custom_api|anthropic_console) printf '%s\n' "anthropic-console" ;;
    oauth_token|oauth) printf '%s\n' "anthropic" ;;
    *) die 22 PROVIDER_MODE_UNKNOWN "unknown provider mode for seat provider mapping: ${PROVIDER_MODE:-<unset>}" ;;
  esac
}

seat_model_for_provider_mode() {
  case "$PROVIDER_MODE" in
    minimax) printf '%s\n' "${PROVIDER_MODEL:-MiniMax-M2.7-highspeed}" ;;
    ark) printf '%s\n' "${PROVIDER_MODEL:-ark-code-latest}" ;;
    xcode-best|custom_api|anthropic_console) [[ -n "$PROVIDER_MODEL" ]] && printf '%s\n' "$PROVIDER_MODEL" || true ;;
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
  # Build seat_order from resolved PENDING_SEATS (ancestor always first)
  local _seat_order_str="\"ancestor\""
  for seat in "${PENDING_SEATS[@]}"; do
    _seat_order_str="${_seat_order_str}, \"${seat}\""
  done
  cat >"$PROJECT_LOCAL_TOML" <<EOF
project_name = "$PROJECT"
repo_root = "$PROJECT_REPO_ROOT"
seat_order = [$_seat_order_str]

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
        export_line ANTHROPIC_BASE_URL "$(provider_base_or_default minimax "$PROVIDER_BASE")"
        export_line ANTHROPIC_MODEL "${PROVIDER_MODEL:-MiniMax-M2.7-highspeed}"
        ;;
      ark)
        export_line ANTHROPIC_AUTH_TOKEN "$PROVIDER_KEY"
        export_line ANTHROPIC_BASE_URL "$(provider_base_or_default ark "$PROVIDER_BASE")"
        export_line ANTHROPIC_MODEL "${PROVIDER_MODEL:-ark-code-latest}"
        ;;
      xcode-best)
        export_line ANTHROPIC_AUTH_TOKEN "$PROVIDER_KEY"
        export_line ANTHROPIC_BASE_URL "$(provider_base_or_default xcode-best "$PROVIDER_BASE")"
        if [[ -n "$PROVIDER_MODEL" ]]; then
          export_line ANTHROPIC_MODEL "$PROVIDER_MODEL"
        fi
        ;;
      custom_api)
        export_line ANTHROPIC_API_KEY "$PROVIDER_KEY"
        export_line ANTHROPIC_AUTH_TOKEN "$PROVIDER_KEY"
        export_line ANTHROPIC_BASE_URL "${PROVIDER_BASE:-$(provider_base_or_default anthropic_console)}"
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
  # Only write a locally-generated template for clawseat-default; other templates
  # (clawseat-engineering, clawseat-creative) have canonical definitions in
  # templates/*.toml and must not be overridden by the install-time generated version.
  [[ "$CLAWSEAT_TEMPLATE_NAME" == "clawseat-default" ]] && write_bootstrap_template
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

ancestor_patrol_cadence_seconds() {
  local cadence_minutes="${CLAWSEAT_ANCESTOR_PATROL_CADENCE_MINUTES:-30}"
  if [[ ! "$cadence_minutes" =~ ^[0-9]+$ ]] || (( cadence_minutes <= 0 )); then
    cadence_minutes=30
  fi
  printf '%s\n' "$((cadence_minutes * 60))"
}

install_ancestor_patrol_plist() {
  note "Step 6: install ancestor patrol LaunchAgent"
  [[ -f "$ANCESTOR_PATROL_TEMPLATE" || "$DRY_RUN" == "1" ]] || die 31 ANCESTOR_PATROL_TEMPLATE_MISSING "missing patrol plist template: $ANCESTOR_PATROL_TEMPLATE"

  local cadence_seconds="" launchd_domain=""
  cadence_seconds="$(ancestor_patrol_cadence_seconds)"
  launchd_domain="gui/$(id -u)"

  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] mkdir -p %q %q\n' "$(dirname "$ANCESTOR_PATROL_PLIST_PATH")" "$ANCESTOR_PATROL_LOG_DIR"
    printf '[dry-run] render %s -> %s\n' "$ANCESTOR_PATROL_TEMPLATE" "$ANCESTOR_PATROL_PLIST_PATH"
    printf '[dry-run] launchctl bootout %s/%s 2>/dev/null || true\n' "$launchd_domain" "$ANCESTOR_PATROL_PLIST_LABEL"
    printf '[dry-run] launchctl bootstrap %s %q\n' "$launchd_domain" "$ANCESTOR_PATROL_PLIST_PATH"
    return 0
  fi

  mkdir -p "$(dirname "$ANCESTOR_PATROL_PLIST_PATH")" "$ANCESTOR_PATROL_LOG_DIR" \
    || die 31 ANCESTOR_PATROL_DIR_FAILED "unable to create patrol plist/log directories"

  sed \
    -e "s|{PROJECT}|${PROJECT}|g" \
    -e "s|{CADENCE_SECONDS}|${cadence_seconds}|g" \
    -e "s|{CLAWSEAT_ROOT}|${CLAWSEAT_ROOT}|g" \
    -e "s|{LOG_DIR}|${ANCESTOR_PATROL_LOG_DIR}|g" \
    "$ANCESTOR_PATROL_TEMPLATE" > "$ANCESTOR_PATROL_PLIST_PATH" \
    || die 31 ANCESTOR_PATROL_RENDER_FAILED "unable to render $ANCESTOR_PATROL_PLIST_PATH"
  chmod 644 "$ANCESTOR_PATROL_PLIST_PATH" \
    || die 31 ANCESTOR_PATROL_CHMOD_FAILED "unable to chmod $ANCESTOR_PATROL_PLIST_PATH"

  if command -v plutil >/dev/null 2>&1; then
    plutil -lint "$ANCESTOR_PATROL_PLIST_PATH" >/dev/null 2>&1 \
      || die 31 ANCESTOR_PATROL_INVALID "rendered patrol plist is not valid XML: $ANCESTOR_PATROL_PLIST_PATH"
  fi

  if [[ "$(uname -s)" != "Darwin" ]]; then
    warn "Skipping launchctl bootstrap for ancestor patrol on non-macOS host."
    return 0
  fi
  if ! command -v launchctl >/dev/null 2>&1; then
    if is_sandbox_install; then
      warn "Skipping launchctl bootstrap for ancestor patrol in sandbox/headless install: launchctl missing."
      return 0
    fi
    die 31 ANCESTOR_PATROL_LAUNCHCTL_MISSING "launchctl is required to bootstrap $ANCESTOR_PATROL_PLIST_PATH"
  fi

  launchctl bootout "${launchd_domain}/${ANCESTOR_PATROL_PLIST_LABEL}" 2>/dev/null || true
  if ! launchctl bootstrap "$launchd_domain" "$ANCESTOR_PATROL_PLIST_PATH" 2>/dev/null; then
    if is_sandbox_install; then
      warn "Skipping launchctl bootstrap for ancestor patrol in sandbox/headless install."
      return 0
    fi
    die 31 ANCESTOR_PATROL_BOOTSTRAP_FAILED "failed to bootstrap $ANCESTOR_PATROL_PLIST_PATH"
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

## 如果 ancestor 报 BRIEF_DRIFT_DETECTED

ancestor 在每个 B 步开始前会先跑 `${CLAWSEAT_ROOT}/scripts/ancestor-brief-mtime-check.sh`。这只能检测 brief 是否在你启动后被更新，不能让运行中的 Claude Code 热更新 system prompt。

推荐处理：

1. \`tmux kill-session -t ${PROJECT}-ancestor\`
2. 重新启动 ancestor（建议重跑 \`scripts/install.sh --project ${PROJECT} --reinstall\`，或按同样的 \`agent-launcher.sh\` 参数重起）
3. 让 ancestor 重新读取 \`\$CLAWSEAT_ANCESTOR_BRIEF\`

如果你暂时不 restart，也可以继续按旧 brief 跑，但它不会自动感知后续改动。
EOF
  chmod 600 "$GUIDE_FILE" || die 30 GUIDE_CHMOD_FAILED "unable to chmod $GUIDE_FILE"
}

phase_a_kickoff_prompt() {
  printf '读 %s 开始 Phase-A。按 brief 顺序执行 B0-B7，每步向我汇报或 CLI prompt 我确认。不要 fan-out specialist seat；spawn engineer seat 要 one-at-a-time。\n' "$BRIEF_PATH"
}

capture_tmux_pane_text() {
  local session_name="$1"
  tmux capture-pane -t "=$session_name" -p -S -120 2>/dev/null || true
}

pane_has_non_whitespace() {
  local pane_text="$1"
  printf '%s' "$pane_text" | grep -q '[^[:space:]]'
}

ancestor_pane_waiting_on_operator() {
  local pane_text="$1"
  case "$pane_text" in
    *"Browser didn't open? Use the url below to sign in"*|\
    *"Paste code here if prompted >"*|\
    *"Login successful. Press Enter to continue"*|\
    *"Accessing workspace:"*|\
    *"Quick safety check:"*|\
    *"WARNING: Claude Code running in Bypass Permissions mode"*|\
    *"OAuth error:"*|\
    *"Do you trust the files in this folder"*|\
    *"Trust folder"*)
      return 0
      ;;
  esac
  return 1
}

ancestor_pane_shows_active_response() {
  local pane_text="$1"
  case "$pane_text" in
    *"Thinking..."*|*"Shell awaiting input"*|*"✶ "*|*"✻ "*|*"✢ "*|*"✳ "*|*"✽ "*|*"⏺ "*)
      return 0
      ;;
  esac
  if printf '%s\n' "$pane_text" | grep -Eq '(^|[[:space:]])Read [0-9]+ files?'; then
    return 0
  fi
  return 1
}

pane_contains_text_relaxed() {
  local pane_text="$1" expected_text="$2" pane_compact="" expected_compact=""
  pane_compact="$(printf '%s' "$pane_text" | tr -d '[:space:]')"
  expected_compact="$(printf '%s' "$expected_text" | tr -d '[:space:]')"
  [[ -n "$expected_compact" && "$pane_compact" == *"$expected_compact"* ]]
}

auto_send_phase_a_kickoff() {
  local kickoff="$1" session_name="$PROJECT-ancestor"
  local max_polls=24 poll_seconds=3 post_send_seconds=2 max_send_attempts=3
  local poll_count=0 send_attempts=0 pane_text="" post_send_text=""

  while [[ "$poll_count" -lt "$max_polls" ]]; do
    poll_count=$((poll_count + 1))
    if ! tmux has-session -t "=$session_name" 2>/dev/null; then
      sleep "$poll_seconds"
      continue
    fi

    pane_text="$(capture_tmux_pane_text "$session_name")"
    if ! pane_has_non_whitespace "$pane_text"; then
      sleep "$poll_seconds"
      continue
    fi
    if ancestor_pane_waiting_on_operator "$pane_text"; then
      sleep "$poll_seconds"
      continue
    fi

    send_attempts=$((send_attempts + 1))
    if bash "$SEND_AND_VERIFY_SCRIPT" --project "$PROJECT" ancestor "$kickoff" >/dev/null 2>&1; then
      sleep "$post_send_seconds"
      post_send_text="$(capture_tmux_pane_text "$session_name")"
      if pane_contains_text_relaxed "$post_send_text" "$kickoff"; then
        note "Phase-A kickoff delivered to $session_name"
        return 0
      fi
      if ancestor_pane_shows_active_response "$post_send_text"; then
        note "Phase-A kickoff submitted to $session_name"
        return 0
      fi
    fi

    if [[ "$send_attempts" -ge "$max_send_attempts" ]]; then
      break
    fi
    sleep "$poll_seconds"
  done

  warn "Auto-send could not verify kickoff delivery to $session_name. Use the fallback prompt below."
  return 1
}

print_operator_banner() {
  local kickoff=""
  kickoff="$(phase_a_kickoff_prompt)"
  printf '\n'
  printf '╔════════════════════════════════════════════════════════════════╗\n'
  printf '║  ClawSeat install complete                                   ║\n'
  printf '║                                                              ║\n'
  printf '║  NEXT STEPS: cat %s\n' "$GUIDE_FILE"
  printf '║                                                              ║\n'
  printf '║  Or read the file at: %s\n' "$GUIDE_FILE"
  printf '╚════════════════════════════════════════════════════════════════╝\n'
  printf '\n'
  if [[ "$DRY_RUN" != "1" ]]; then
    printf 'IF ANCESTOR IS IDLE, COPY AND PASTE THIS:\n'
    printf '%s\n' "$kickoff"
    printf '\n'
  fi
}

launcher_auth_for_provider() {
  case "$PROVIDER_MODE" in
    minimax|ark|xcode-best|custom_api|anthropic_console) printf '%s\n' "custom" ;;
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
      base_url="$(provider_base_or_default minimax "$PROVIDER_BASE")"
      model="${PROVIDER_MODEL:-MiniMax-M2.7-highspeed}"
      ;;
    ark)
      api_key="$PROVIDER_KEY"
      base_url="$(provider_base_or_default ark "$PROVIDER_BASE")"
      model="${PROVIDER_MODEL:-ark-code-latest}"
      ;;
    xcode-best)
      api_key="$PROVIDER_KEY"
      base_url="$(provider_base_or_default xcode-best "$PROVIDER_BASE")"
      model="$PROVIDER_MODEL"
      ;;
    custom_api)
      api_key="$PROVIDER_KEY"
      base_url="$PROVIDER_BASE"
      model="$PROVIDER_MODEL"
      ;;
    anthropic_console)
      api_key="$PROVIDER_KEY"
      base_url="${PROVIDER_BASE:-$(provider_base_or_default anthropic_console)}"
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

configure_tmux_session_display() {
  local session="$1"
  # tmux accepts `=name` for exact matching in has-session, but set-option
  # rejects that target form on this host. Use the plain session name here.
  run tmux set-option -t "$session" detach-on-destroy off
  run tmux set-option -t "$session" status on
  run tmux set-option -t "$session" status-left "[#{session_name}] "
  run tmux set-option -t "$session" status-right "#{?client_attached,ATTACHED,WAITING} | %H:%M"
  run tmux set-option -t "$session" status-style "fg=white,bg=blue,bold"
}

ensure_tmux_session_alive() {
  local session="$1"
  if tmux has-session -t "=$session" 2>/dev/null; then
    return 0
  fi
  die 31 TMUX_SESSION_DIED_AFTER_LAUNCH "tmux session vanished before display configuration: $session"
}

launch_seat() {
  local session="$1" cwd="${2:-$REPO_ROOT}" brief_path="${3:-}" seat_id="${4:-}" auth_mode="" custom_env_file=""
  auth_mode="$(launcher_auth_for_provider)"
  custom_env_file="$(launcher_custom_env_file_for_session "$session")"

  if [[ "$DRY_RUN" == "1" ]]; then
    run tmux kill-session -t "=$session"
  else
    tmux kill-session -t "=$session" 2>/dev/null || true
    mkdir -p "$cwd" || die 31 TMUX_CWD_CREATE_FAILED "unable to create launcher cwd: $cwd"
  fi

  local -a cmd=(env "CLAWSEAT_ROOT=$CLAWSEAT_ROOT")
  cmd+=("CLAWSEAT_PROJECT=$PROJECT")
  cmd+=("CLAWSEAT_ANCESTOR_BRIEF=$brief_path")
  [[ -n "$seat_id" ]] && cmd+=("CLAWSEAT_SEAT=$seat_id")
  cmd+=(bash "$LAUNCHER_SCRIPT" --headless --tool claude --auth "$auth_mode" --dir "$cwd" --session "$session")
  [[ -n "$custom_env_file" ]] && cmd+=(--custom-env-file "$custom_env_file")
  [[ "$DRY_RUN" == "1" ]] && cmd+=(--dry-run)

  if [[ "$DRY_RUN" == "1" ]]; then
    run "${cmd[@]}"
    configure_tmux_session_display "$session"
    return 0
  fi

  if ! "${cmd[@]}"; then
    [[ -n "$custom_env_file" && -f "$custom_env_file" ]] && rm -f "$custom_env_file"
    die 31 TMUX_SESSION_CREATE_FAILED "unable to launch tmux session via agent-launcher: $session"
  fi
  ensure_tmux_session_alive "$session"
  configure_tmux_session_display "$session"
}

install_memory_hook() {
  note "Step 7.5: install memory Stop-hook"
  local engineers_root="$HOME/.agents/engineers"
  local template_settings="$engineers_root/memory/.claude-template/settings.json"
  if [[ "$DRY_RUN" == "1" ]]; then
    run "$PYTHON_BIN" "$SEAT_CLAUDE_TEMPLATE_SCRIPT" --seat memory --engineers-root "$engineers_root" --clawseat-root "$CLAWSEAT_ROOT"
    run "$PYTHON_BIN" "$MEMORY_HOOK_INSTALLER" --workspace "$MEMORY_WORKSPACE" --settings-path "$template_settings" --clawseat-root "$CLAWSEAT_ROOT" --dry-run
    return 0
  fi
  mkdir -p "$MEMORY_WORKSPACE" || die 32 MEMORY_WORKSPACE_CREATE_FAILED "unable to create memory workspace: $MEMORY_WORKSPACE"
  "$PYTHON_BIN" "$SEAT_CLAUDE_TEMPLATE_SCRIPT" --seat memory --engineers-root "$engineers_root" --clawseat-root "$CLAWSEAT_ROOT" \
    || die 32 MEMORY_TEMPLATE_PREP_FAILED "failed to prepare Claude template for memory seat"
  "$PYTHON_BIN" "$MEMORY_HOOK_INSTALLER" --workspace "$MEMORY_WORKSPACE" --settings-path "$template_settings" --clawseat-root "$CLAWSEAT_ROOT" \
    || die 32 MEMORY_HOOK_INSTALL_FAILED "failed to install memory Stop-hook into $template_settings"
}

check_iterm_window_exists() {
  local title="$1"
  if ! command -v osascript >/dev/null 2>&1; then
    printf '0\n'
    return 0
  fi
  osascript - "$title" <<'APPLESCRIPT' 2>/dev/null || printf '0\n'
on run argv
  set wanted to item 1 of argv
  tell application "iTerm"
    repeat with w in windows
      try
        if (name of w as string) contains wanted then
          return "1"
        end if
      end try
    end repeat
  end tell
  return "0"
end run
APPLESCRIPT
}

is_sandbox_install() {
  if PYTHONPATH="$REPO_ROOT/core/lib${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" - "$CALLER_HOME" <<'PY' >/dev/null 2>&1
import sys
from pathlib import Path

from real_home import is_sandbox_home, real_user_home

caller_home = Path(sys.argv[1]).expanduser()
real_home = real_user_home()
raise SystemExit(0 if is_sandbox_home(caller_home) or caller_home != real_home else 1)
PY
  then
    return 0
  fi

  case "$CALLER_HOME" in
    *"/.agents/runtime/identities/"*|*"/.agent-runtime/identities/"*)
      return 0
      ;;
  esac
  return 1
}

open_iterm_window() {
  local payload="$1" target_var="$2" err_file out status
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] %q %q <<JSON\n%s\nJSON\n' "$PYTHON_BIN" "$ITERM_DRIVER" "$payload"
    printf -v "$target_var" '%s' "dry-run-$target_var"; return
  fi
  if [[ "$(uname -s)" != "Darwin" ]]; then
    if is_sandbox_install; then
      warn "Skipping iTerm window open in sandbox/headless install: native iTerm panes require macOS."
      printf -v "$target_var" '%s' ""
      return 0
    fi
    die 40 ITERM_MACOS_ONLY "native iTerm panes require macOS."
  fi
  if ! "$PYTHON_BIN" -c 'import iterm2' >/dev/null 2>&1; then
    if is_sandbox_install; then
      warn "Skipping iTerm window open in sandbox/headless install: missing iterm2 module."
      printf -v "$target_var" '%s' ""
      return 0
    fi
    die 40 ITERM2_PYTHON_MISSING "missing iterm2 module; install with: pip3 install --user --break-system-packages iterm2"
  fi
  err_file="$(mktemp)"
  out="$(
    printf '%s' "$payload" | timeout "${ITERM_DRIVER_TIMEOUT_SECONDS}s" "$PYTHON_BIN" "$ITERM_DRIVER" 2>"$err_file"
  )" || {
    status=$?
    cat "$err_file" >&2
    rm -f "$err_file"
    if [[ "$status" == "124" ]]; then
      if is_sandbox_install; then
        warn "Skipping iTerm window open in sandbox/headless install: iTerm pane driver timed out after ${ITERM_DRIVER_TIMEOUT_SECONDS}s."
        printf -v "$target_var" '%s' ""
        return 0
      fi
      die 40 ITERM_DRIVER_FAILED "iTerm pane driver timed out after ${ITERM_DRIVER_TIMEOUT_SECONDS}s."
    fi
    if is_sandbox_install; then
      warn "Skipping iTerm window open in sandbox/headless install: iTerm pane driver execution failed."
      printf -v "$target_var" '%s' ""
      return 0
    fi
    die 40 ITERM_DRIVER_FAILED "iTerm pane driver execution failed."
  }
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
            + shlex.quote(project)
            + " "
            + shlex.quote(seat),
        }
    )
print(json.dumps({"title": f"clawseat-{project}", "panes": panes}, ensure_ascii=False))
PY
}
memory_payload() { printf '%s' '{"title":"machine-memory-claude","panes":[{"label":"memory","command":"tmux attach -t '\''=machine-memory-claude'\''"}]}'; }

main() {
  local memory_window_id=""
  parse_args "$@"; resolve_pending_seats; normalize_provider_choice; ensure_host_deps; ensure_python_tomllib_fallback; scan_machine; select_provider; render_brief
  note "Step 5: launch ancestor seat via agent-launcher"
  launch_seat "$PROJECT-ancestor" "$PROJECT_REPO_ROOT" "$BRIEF_PATH" "ancestor"
  bootstrap_project_profile
  install_ancestor_patrol_plist
  note "Step 7: open six-pane iTerm grid"; open_iterm_window "$(grid_payload)" GRID_WINDOW_ID
  note "Step 8: ensure memory singleton daemon"
  if [[ "$DRY_RUN" == "1" ]]; then
    install_memory_hook
    launch_seat "machine-memory-claude" "$MEMORY_WORKSPACE" "" "memory"
    open_iterm_window "$(memory_payload)" memory_window_id
  elif tmux has-session -t '=machine-memory-claude' 2>/dev/null; then
    printf 'memory seat already running (machine-memory-claude), reusing.\n'
    install_memory_hook
    if [[ "$(check_iterm_window_exists "machine-memory-claude")" != "1" ]]; then
      open_iterm_window "$(memory_payload)" memory_window_id
    else
      printf 'memory iTerm window already open, skipping open.\n'
    fi
  else
    install_memory_hook
    launch_seat "machine-memory-claude" "$MEMORY_WORKSPACE" "" "memory"
    open_iterm_window "$(memory_payload)" memory_window_id
  fi
  note "Step 9: focus ancestor and persist operator guide"
  if [[ -n "$GRID_WINDOW_ID" ]]; then
    run sleep 3
    focus_iterm_window "$GRID_WINDOW_ID" "ancestor"
  else
    warn "Skipping ancestor focus because no iTerm grid window was opened."
  fi
  if [[ "$DRY_RUN" != "1" ]]; then
    note "Step 9.5: auto-send Phase-A kickoff prompt"
    local kickoff=""
    kickoff="$(phase_a_kickoff_prompt)"
    auto_send_phase_a_kickoff "$kickoff" || true
  fi
  write_operator_guide
  print_operator_banner
}

main "$@"
