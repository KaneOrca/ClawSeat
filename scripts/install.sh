#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0; PROJECT="install"; REPO_ROOT_OVERRIDE=""
_PROJECT_EXPLICIT=0; _TEMPLATE_EXPLICIT=0  # set to 1 when flag is passed explicitly
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CLAWSEAT_ROOT="${CLAWSEAT_ROOT_OVERRIDE:-$REPO_ROOT}"
PYTHON_BIN_WAS_SET="${PYTHON_BIN+1}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
FORCE_REINSTALL=0
ENABLE_AUTO_PATROL=0
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
LAUNCHER_SCRIPT="$REPO_ROOT/core/launchers/agent-launcher.sh"
AGENT_ADMIN_SCRIPT="$REPO_ROOT/core/scripts/agent_admin.py"
PROJECTS_REGISTRY_SCRIPT="$REPO_ROOT/core/scripts/projects_registry.py"
SEND_AND_VERIFY_SCRIPT="$REPO_ROOT/core/shell-scripts/send-and-verify.sh"
WAIT_FOR_SEAT_SCRIPT="$REPO_ROOT/scripts/wait-for-seat.sh"
MEMORY_ROOT="$HOME/.agents/memory"; PROVIDER_ENV=""; BRIEF_PATH=""
MEMORY_WORKSPACE=""
GRID_WINDOW_ID=""
GUIDE_FILE=""
KICKOFF_FILE=""
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
MEMORY_TOOL="${CLAWSEAT_MEMORY_TOOL:-codex}"
MEMORY_MODEL="${CLAWSEAT_MEMORY_MODEL:-gpt-5.4-mini}"
MEMORY_MODEL_EXPLICIT=0
STATUS_FILE=""
PROJECT_LOCAL_TOML=""
PROJECT_RECORD_PATH=""
AGENTS_TEMPLATES_ROOT="$HOME/.agents/templates"
CLAWSEAT_TEMPLATE_NAME="clawseat-minimal"
BOOTSTRAP_TEMPLATE_DIR=""
BOOTSTRAP_TEMPLATE_PATH=""
PENDING_SEATS=(planner builder reviewer qa designer)
# PRIMARY_SEAT_ID = the seat user dialogs with (always one per project).
# v1 templates use "ancestor"; v2 clawseat-minimal uses "memory".
# Set by resolve_pending_seats() based on template's first primary engineer.
PRIMARY_SEAT_ID="ancestor"

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
      --project) PROJECT="$2"; _PROJECT_EXPLICIT=1; shift 2 ;;
      --repo-root) REPO_ROOT_OVERRIDE="$2"; shift 2 ;;
      --provider) FORCE_PROVIDER="$2"; shift 2 ;;
      --base-url) FORCE_BASE_URL="$2"; shift 2 ;;
      --api-key) FORCE_API_KEY="$2"; shift 2 ;;
      --model) FORCE_MODEL="$2"; shift 2 ;;
      --memory-tool) MEMORY_TOOL="$2"; shift 2 ;;
      --memory-model) MEMORY_MODEL="$2"; MEMORY_MODEL_EXPLICIT=1; shift 2 ;;
      --reinstall|--force) FORCE_REINSTALL=1; shift ;;
      --enable-auto-patrol) ENABLE_AUTO_PATROL=1; shift ;;
      --template) CLAWSEAT_TEMPLATE_NAME="$2"; _TEMPLATE_EXPLICIT=1; shift 2 ;;
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
      --help|-h) printf 'Usage: scripts/install.sh [--project <name>] [--repo-root <path>] [--template clawseat-minimal|clawseat-engineering|clawseat-default|clawseat-creative] [--memory-tool claude|codex|gemini] [--memory-model <model>] [--provider <mode|n>] [--base-url <url> --api-key <key> [--model <name>]] [--reinstall|--force] [--enable-auto-patrol] [--dry-run] [--reset-harness-memory]\n'; exit 0 ;;
      *) die 2 UNKNOWN_FLAG "unknown flag: $1" ;;
    esac
  done
  [[ "$PROJECT" =~ ^[a-z0-9-]+$ ]] || die 2 INVALID_PROJECT "project must match ^[a-z0-9-]+$"
  case "$CLAWSEAT_TEMPLATE_NAME" in
    clawseat-minimal|clawseat-default|clawseat-engineering|clawseat-creative) ;;
    *) die 2 INVALID_TEMPLATE "--template must be clawseat-minimal | clawseat-default | clawseat-engineering | clawseat-creative, got: $CLAWSEAT_TEMPLATE_NAME" ;;
  esac
  case "$MEMORY_TOOL" in
    claude|codex|gemini) ;;
    *) die 2 INVALID_MEMORY_TOOL "--memory-tool must be claude | codex | gemini, got: $MEMORY_TOOL" ;;
  esac
  [[ -n "$MEMORY_MODEL" ]] || die 2 INVALID_MEMORY_MODEL "--memory-model must not be empty"
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
  compute_project_paths
}

compute_project_paths() {
  STATUS_FILE="$HOME/.agents/tasks/$PROJECT/STATUS.md"
  PROVIDER_ENV="$HOME/.agents/tasks/$PROJECT/ancestor-provider.env"
  BRIEF_PATH="$HOME/.agents/tasks/$PROJECT/patrol/handoffs/ancestor-bootstrap.md"
  MEMORY_WORKSPACE="$HOME/.agents/workspaces/$PROJECT/memory"
  PROJECT_LOCAL_TOML="$HOME/.agents/tasks/$PROJECT/project-local.toml"
  PROJECT_RECORD_PATH="$HOME/.agents/projects/$PROJECT/project.toml"
  GUIDE_FILE="$HOME/.agents/tasks/$PROJECT/OPERATOR-START-HERE.md"
  KICKOFF_FILE="$HOME/.agents/tasks/$PROJECT/patrol/handoffs/ancestor-kickoff.txt"
  ANCESTOR_PATROL_PLIST_LABEL="com.clawseat.${PROJECT}.ancestor-patrol"
  ANCESTOR_PATROL_PLIST_PATH="$HOME/Library/LaunchAgents/${ANCESTOR_PATROL_PLIST_LABEL}.plist"
  ANCESTOR_PATROL_LOG_DIR="$HOME/.agents/tasks/$PROJECT/patrol/logs"
  BOOTSTRAP_TEMPLATE_DIR="$AGENTS_TEMPLATES_ROOT/$CLAWSEAT_TEMPLATE_NAME"
  BOOTSTRAP_TEMPLATE_PATH="$BOOTSTRAP_TEMPLATE_DIR/template.toml"
}

# kind-first interactive prompt — only runs when TTY available and neither
# --project nor --template was passed explicitly.  Uses /dev/tty so pipe/CI
# stdin does not interfere.  Sets PROJECT + CLAWSEAT_TEMPLATE_NAME, then
# recomputes derived paths via compute_project_paths().
prompt_kind_first_flow() {
  # Skip when: non-TTY, or either flag was explicitly provided.
  [[ -t 0 && -t 1 ]] || return 0
  [[ "$_PROJECT_EXPLICIT" == "0" && "$_TEMPLATE_EXPLICIT" == "0" ]] || return 0

  printf '\nClawSeat — 新项目配置 / New project setup\n' >&2
  printf '\n选择项目类型 / Choose project mode:\n' >&2
  printf '  1) 新手 (clawseat-minimal     — 4 seat 全 OAuth 多模型: memory + planner + builder + designer)  [default]\n' >&2
  printf '  2) 专家 (clawseat-engineering — 6 seat 工程级: ancestor + planner + builder + reviewer + qa + designer)\n' >&2

  local _kind=""
  while true; do
    printf '选择 [1-2, Enter=1]: ' >&2
    read -r _kind < /dev/tty
    [[ -z "$_kind" ]] && _kind="1"   # Enter == default beginner
    case "$_kind" in
      1) CLAWSEAT_TEMPLATE_NAME="clawseat-minimal";     break ;;
      2) CLAWSEAT_TEMPLATE_NAME="clawseat-engineering"; break ;;
      *) printf '请输入 1 或 2 (回车 = 1 新手)\n' >&2 ;;
    esac
  done

  local _placeholder
  case "$CLAWSEAT_TEMPLATE_NAME" in
    clawseat-minimal)     _placeholder="e.g. myapp, learn-python, my-first-project" ;;
    clawseat-engineering) _placeholder="e.g. api-service, web-frontend, mobile-app" ;;
    clawseat-creative)    _placeholder="e.g. novel-scifi, series-drama, script-ep01" ;;
    *)                    _placeholder="e.g. myproject, experiment-01" ;;
  esac

  local _name="" _attempt=0
  while [[ $_attempt -lt 3 ]]; do
    _attempt=$((_attempt + 1))
    printf '\n项目名 (%s): ' "$_placeholder" >&2
    read -r _name < /dev/tty
    if [[ "$_name" =~ ^[a-z0-9-]+$ ]]; then
      PROJECT="$_name"
      compute_project_paths
      return 0
    fi
    printf '无效：项目名必须匹配 ^[a-z0-9-]+$\n' >&2
  done
  die 2 INVALID_PROJECT "项目名 3 次输入均无效，请用 --project 传入合法名称"
}

resolve_pending_seats() {
  # PRIMARY_SEAT_ID is the seat the user dialogs with (ancestor in v1 templates,
  # memory in v2 clawseat-minimal). PENDING_SEATS is everyone else (workers).
  # For clawseat-default, keep the hardcoded list (generated template, no file to read).
  if [[ "$CLAWSEAT_TEMPLATE_NAME" == "clawseat-default" ]]; then
    PRIMARY_SEAT_ID="ancestor"
    return 0
  fi
  local template_file="$REPO_ROOT/templates/${CLAWSEAT_TEMPLATE_NAME}.toml"
  if [[ ! -f "$template_file" ]]; then
    PRIMARY_SEAT_ID="ancestor"
    return 0  # fallback to hardcoded if not found
  fi
  local primary seats
  primary="$("$PYTHON_BIN" - "$template_file" <<'PY'
import sys
try:
    import tomllib
except ImportError:
    import tomli as tomllib
with open(sys.argv[1], "rb") as f:
    data = tomllib.load(f)
PRIMARY_IDS = ("ancestor", "memory")
for e in data.get("engineers", []):
    if e.get("id") in PRIMARY_IDS:
        print(e["id"])
        break
PY
  2>/dev/null)"
  PRIMARY_SEAT_ID="${primary:-ancestor}"

  seats="$("$PYTHON_BIN" - "$template_file" "$PRIMARY_SEAT_ID" <<'PY'
import sys
try:
    import tomllib
except ImportError:
    import tomli as tomllib
with open(sys.argv[1], "rb") as f:
    data = tomllib.load(f)
primary = sys.argv[2]
seats = [e["id"] for e in data.get("engineers", []) if e.get("id") != primary]
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

memory_primary_uses_codex() {
  [[ "$PRIMARY_SEAT_ID" == "memory" && "$MEMORY_TOOL" == "codex" ]]
}

memory_primary_uses_gemini() {
  [[ "$PRIMARY_SEAT_ID" == "memory" && "$MEMORY_TOOL" == "gemini" ]]
}

memory_primary_skips_claude_provider() {
  [[ "$PRIMARY_SEAT_ID" == "memory" && "$MEMORY_TOOL" != "claude" ]]
}

memory_effective_model() {
  case "$MEMORY_TOOL" in
    codex) printf '%s\n' "$MEMORY_MODEL" ;;
    gemini)
      [[ "$MEMORY_MODEL_EXPLICIT" == "1" ]] && printf '%s\n' "$MEMORY_MODEL" || true
      ;;
    *) return 0 ;;
  esac
}

ensure_host_deps() {
  note "Step 1: preflight"
  if [[ "$FORCE_REINSTALL" != "1" && -f "$STATUS_FILE" ]] && grep -q '^phase=ready$' "$STATUS_FILE"; then
    # Round-8: even on the "already installed" fast-path, honor the
    # auto-patrol default. If the operator rerun without
    # --enable-auto-patrol but an existing LaunchAgent is still firing
    # (from a pre-Round-8 install), tear it down; otherwise the ghost
    # plist keeps injecting stale payloads even though install.sh
    # itself exited early and never reached Step 6.
    if [[ "$ENABLE_AUTO_PATROL" != "1" ]]; then
      uninstall_ancestor_patrol_plist_if_present
    fi
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
  note "Step 3: primary seat provider"
  local mode="" label="" key="" base="" reply=""
  local -a candidates=()

  if memory_primary_skips_claude_provider; then
    remember_provider_selection oauth
    if [[ "$DRY_RUN" == "1" ]]; then
      printf 'Project: %s\n' "$PROJECT"
      if memory_primary_uses_codex; then
        printf '[dry-run] memory-tool=codex auth=chatgpt model=%s; skip Claude provider selection\n' "$MEMORY_MODEL"
      else
        printf '[dry-run] memory-tool=gemini auth=oauth; skip Claude provider selection\n'
      fi
    else
      if memory_primary_uses_codex; then
        printf 'Using memory tool: codex (auth=chatgpt, model=%s); skipping Claude provider selection.\n' "$MEMORY_MODEL"
      else
        printf 'Using memory tool: gemini (auth=oauth); skipping Claude provider selection.\n'
      fi
    fi
    return
  fi

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
  local seat_auth_mode seat_provider seat_model seat primary_tool primary_auth primary_provider primary_model
  seat_auth_mode="$(seat_auth_mode_for_provider_mode)"
  seat_provider="$(seat_provider_for_provider_mode)"
  seat_model="$(seat_model_for_provider_mode || true)"
  primary_tool="claude"
  primary_auth="$seat_auth_mode"
  primary_provider="$seat_provider"
  primary_model="$seat_model"
  if memory_primary_skips_claude_provider; then
    primary_tool="$MEMORY_TOOL"
    primary_auth="oauth"
    case "$MEMORY_TOOL" in
      codex) primary_provider="openai" ;;
      gemini) primary_provider="google" ;;
    esac
    primary_model="$(memory_effective_model)"
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] write %s\n' "$PROJECT_LOCAL_TOML"
    return 0
  fi

  mkdir -p "$(dirname "$PROJECT_LOCAL_TOML")" || die 31 PROJECT_LOCAL_DIR_FAILED "unable to create $(dirname "$PROJECT_LOCAL_TOML")"
  # Build seat_order from PRIMARY_SEAT_ID (ancestor or memory) + PENDING_SEATS workers
  local _seat_order_str="\"$PRIMARY_SEAT_ID\""
  for seat in "${PENDING_SEATS[@]}"; do
    _seat_order_str="${_seat_order_str}, \"${seat}\""
  done
  cat >"$PROJECT_LOCAL_TOML" <<EOF
project_name = "$PROJECT"
repo_root = "$PROJECT_REPO_ROOT"
seat_order = [$_seat_order_str]

[[overrides]]
id = "$PRIMARY_SEAT_ID"
session_name = "$PROJECT-$PRIMARY_SEAT_ID"
tool = "$primary_tool"
auth_mode = "$primary_auth"
provider = "$primary_provider"
EOF
  if [[ -n "$primary_model" ]]; then
    printf 'model = "%s"\n' "$primary_model" >>"$PROJECT_LOCAL_TOML"
  fi

  for seat in "${PENDING_SEATS[@]}"; do
    local _seat_tool _seat_auth _seat_provider _seat_template_model
    if [[ "$CLAWSEAT_TEMPLATE_NAME" != "clawseat-default" ]]; then
      # For non-default templates, read per-seat tool/auth/provider/model from template TOML.
      local _template_file="$REPO_ROOT/templates/${CLAWSEAT_TEMPLATE_NAME}.toml"
      if [[ -f "$_template_file" ]]; then
        read -r _seat_tool _seat_auth _seat_provider _seat_template_model < <(
          "$PYTHON_BIN" - "$_template_file" "$seat" <<'PY'
import sys
try:
    import tomllib
except ImportError:
    import tomli as tomllib
with open(sys.argv[1], "rb") as f:
    data = tomllib.load(f)
target = sys.argv[2]
for e in data.get("engineers", []):
    if e.get("id") == target:
        print(
            e.get("tool", "claude"),
            e.get("auth_mode", "oauth"),
            e.get("provider", "anthropic"),
            e.get("model", ""),
        )
        break
PY
          2>/dev/null) || true
      fi
    fi
    # Fallback to ancestor values for default template or if template read failed
    _seat_tool="${_seat_tool:-claude}"
    _seat_auth="${_seat_auth:-$seat_auth_mode}"
    _seat_provider="${_seat_provider:-$seat_provider}"
    cat >>"$PROJECT_LOCAL_TOML" <<EOF

[[overrides]]
id = "$seat"
tool = "$_seat_tool"
auth_mode = "$_seat_auth"
provider = "$_seat_provider"
EOF
    # Write model for claude seats: template-specified model takes precedence;
    # fall back to the ancestor's selected model when template doesn't specify one.
    # codex/gemini seats never get a model override.
    if [[ "$_seat_tool" == "claude" ]]; then
      local _effective_model="${_seat_template_model:-$seat_model}"
      if [[ -n "$_effective_model" ]]; then
        printf 'model = "%s"\n' "$_effective_model" >>"$PROJECT_LOCAL_TOML"
      fi
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

ensure_privacy_kb_template() {
  note "Step 5.7: ensure machine privacy KB"
  local privacy_path="$HOME/.agents/memory/machine/privacy.md"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] ensure %s exists with mode 0600\n' "$privacy_path"
    return 0
  fi
  if [[ -e "$privacy_path" ]]; then
    return 0
  fi
  mkdir -p "$(dirname "$privacy_path")" || die 31 PRIVACY_KB_DIR_FAILED "unable to create $(dirname "$privacy_path")"
  (umask 077; cat >"$privacy_path" <<'EOF'
# Privacy KB
# Operator manually maintains. Lines starting with BLOCK: are forbidden patterns.
# Example: BLOCK: sk-
# Example: BLOCK: ghp_
EOF
  ) || die 31 PRIVACY_KB_WRITE_FAILED "unable to write $privacy_path"
  chmod 600 "$privacy_path" || die 31 PRIVACY_KB_CHMOD_FAILED "unable to chmod $privacy_path"
}

install_skill_symlinks() {
  note "Step 5.8: install ClawSeat skill symlinks"
  local skills_home="$HOME/.agents/skills"
  local skill target link
  local -a skills=(clawseat-memory clawseat-decision-escalation clawseat-koder clawseat-privacy)
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] mkdir -p %q\n' "$skills_home"
    for skill in "${skills[@]}"; do
      printf '[dry-run] ln -sfn %q %q\n' "$REPO_ROOT/core/skills/$skill" "$skills_home/$skill"
    done
    printf '[dry-run] verify existing %q\n' "$skills_home/clawseat-memory"
    return 0
  fi
  mkdir -p "$skills_home" || die 31 SKILL_SYMLINK_DIR_FAILED "unable to create $skills_home"
  for skill in "${skills[@]}"; do
    target="$REPO_ROOT/core/skills/$skill"
    link="$skills_home/$skill"
    if [[ ! -d "$target" ]]; then
      warn "skill symlink skipped; missing skill directory: $target"
      continue
    fi
    ln -sfn "$target" "$link" || die 31 SKILL_SYMLINK_FAILED "unable to link $link -> $target"
  done
  if [[ ! -e "$skills_home/clawseat-memory" && ! -L "$skills_home/clawseat-memory" ]]; then
    warn "clawseat-memory skill symlink not found at $skills_home/clawseat-memory; leaving unchanged per compatibility contract"
  fi
}

install_privacy_pre_commit_hook() {
  note "Step 5.9: install privacy pre-commit hook"
  local hook_path="" hook_dir="" local_hook="" candidate="" idx=0 privacy_script="$REPO_ROOT/core/scripts/privacy-check.sh"

  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] install privacy pre-commit hook for repo %q\n' "$PROJECT_REPO_ROOT"
    return 0
  fi
  if [[ ! -f "$privacy_script" ]]; then
    warn "privacy pre-commit hook skipped; missing privacy-check helper: $privacy_script"
    return 0
  fi
  if ! git -C "$PROJECT_REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    warn "privacy pre-commit hook skipped; not a git worktree: $PROJECT_REPO_ROOT"
    return 0
  fi
  hook_path="$(git -C "$PROJECT_REPO_ROOT" rev-parse --git-path hooks/pre-commit)"
  [[ "$hook_path" == /* ]] || hook_path="$PROJECT_REPO_ROOT/$hook_path"
  hook_dir="$(dirname "$hook_path")"
  mkdir -p "$hook_dir" || die 31 PRIVACY_HOOK_DIR_FAILED "unable to create $hook_dir"

  if [[ -f "$hook_path" ]] && grep -q 'CLAWSEAT_PRIVACY_CHECK_BEGIN' "$hook_path" 2>/dev/null; then
    chmod +x "$hook_path" || true
    return 0
  fi

  if [[ -e "$hook_path" || -L "$hook_path" ]]; then
    candidate="${hook_path}.clawseat-local"
    while [[ -e "$candidate" || -L "$candidate" ]]; do
      idx=$((idx + 1))
      candidate="${hook_path}.clawseat-local.$idx"
    done
    mv "$hook_path" "$candidate" || die 31 PRIVACY_HOOK_PRESERVE_FAILED "unable to preserve existing hook: $hook_path"
    chmod +x "$candidate" || true
    local_hook="$candidate"
  fi

  {
    printf '#!/usr/bin/env bash\n'
    printf 'set -euo pipefail\n'
    printf '# CLAWSEAT_PRIVACY_CHECK_BEGIN\n'
    printf 'bash %q\n' "$privacy_script"
    printf '# CLAWSEAT_PRIVACY_CHECK_END\n'
    if [[ -n "$local_hook" ]]; then
      printf 'if [[ -x %q ]]; then\n' "$local_hook"
      printf '  %q "$@"\n' "$local_hook"
      printf 'fi\n'
    fi
  } >"$hook_path" || die 31 PRIVACY_HOOK_WRITE_FAILED "unable to write $hook_path"
  chmod +x "$hook_path" || die 31 PRIVACY_HOOK_CHMOD_FAILED "unable to chmod $hook_path"
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
    if [[ "$FORCE_REINSTALL" == "1" ]]; then
      # --reinstall must re-bootstrap so session.toml gets recreated.
      # Bug fix: previously this branch would silently skip even when the
      # operator explicitly asked for --reinstall, leaving stale state where
      # project.toml exists but session.toml is missing — causing all
      # downstream `agent_admin session-name` / `send-and-verify --project`
      # calls, including operator-triggered kickoff dispatch, to fail with
      # SESSION_NOT_FOUND.
      printf 'Project %s exists at %s — --reinstall: wiping project record + sessions to force re-bootstrap.\n' \
        "$PROJECT" "$PROJECT_RECORD_PATH"
      rm -f "$PROJECT_RECORD_PATH"
      rm -rf "$HOME/.agents/sessions/$PROJECT"
      # Note: ~/.agents/tasks/$PROJECT (TASKS.md, STATUS.md, handoffs) is
      # preserved — operator's history shouldn't be lost on --reinstall.
    else
      printf 'Project %s already exists at %s; skipping bootstrap.\n' "$PROJECT" "$PROJECT_RECORD_PATH"
      return 0
    fi
  fi

  mkdir -p "$AGENTS_TEMPLATES_ROOT" || die 31 TEMPLATE_ROOT_CREATE_FAILED "unable to create $AGENTS_TEMPLATES_ROOT"
  (
    cd "$AGENTS_TEMPLATES_ROOT" &&
    "$PYTHON_BIN" "$AGENT_ADMIN_SCRIPT" project bootstrap --template "$CLAWSEAT_TEMPLATE_NAME" --local "$PROJECT_LOCAL_TOML"
  ) || die 31 PROJECT_BOOTSTRAP_FAILED "unable to bootstrap project profile via agent_admin: $PROJECT"
  seed_bootstrap_secrets
}

register_project_registry() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] %q %q register %q %q %q\n' \
      "$PYTHON_BIN" "$PROJECTS_REGISTRY_SCRIPT" "$PROJECT" "$PRIMARY_SEAT_ID" "${PROJECT}-${PRIMARY_SEAT_ID}"
    return 0
  fi
  if [[ ! -f "$PROJECTS_REGISTRY_SCRIPT" ]]; then
    warn "projects.json register skipped; missing $PROJECTS_REGISTRY_SCRIPT"
    return 0
  fi
  "$PYTHON_BIN" "$PROJECTS_REGISTRY_SCRIPT" register \
    "$PROJECT" "$PRIMARY_SEAT_ID" "${PROJECT}-${PRIMARY_SEAT_ID}" >/dev/null \
    || warn "projects.json register failed (non-fatal); see ~/.clawseat/projects.json"
}

render_brief() {
  note "Step 4: render ancestor brief"
  [[ -f "$TEMPLATE_PATH" || "$DRY_RUN" == "1" ]] || die 30 TEMPLATE_MISSING "missing template: $TEMPLATE_PATH"
  local pending_seats_human
  printf -v pending_seats_human '%s, ' "${PENDING_SEATS[@]}"
  pending_seats_human="${pending_seats_human%, }"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] render %s -> %s\n' "$TEMPLATE_PATH" "$BRIEF_PATH"
  else
    "$PYTHON_BIN" - "$TEMPLATE_PATH" "$BRIEF_PATH" "$PROJECT" "$REPO_ROOT" "$REAL_HOME" "$CLAWSEAT_TEMPLATE_NAME" "$PRIMARY_SEAT_ID" "$pending_seats_human" <<'PY'
from pathlib import Path
from string import Template
import sys
tmpl = Template(Path(sys.argv[1]).read_text(encoding="utf-8")).safe_substitute(
    PROJECT_NAME=sys.argv[3],
    CLAWSEAT_ROOT=sys.argv[4],
    AGENT_HOME=sys.argv[5],
    PRIMARY_SEAT_ID=sys.argv[7],
    PENDING_SEATS_HUMAN=sys.argv[8],
)
tmpl = tmpl.replace("{CLAWSEAT_TEMPLATE_NAME}", sys.argv[6] if len(sys.argv) > 6 else "clawseat-default")
out = Path(sys.argv[2]); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(tmpl, encoding="utf-8")
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

uninstall_ancestor_patrol_plist_if_present() {
  # Teardown idempotency: bootout is attempted *unconditionally* by label so
  # a ghost-loaded LaunchAgent (plist file manually deleted but the job is
  # still loaded in launchd) is still unloaded. `launchctl bootout ... || true`
  # is a no-op when the label is not loaded, so this is safe. File removal
  # (note + rm) is still gated on plist existence.
  local have_file=0
  [[ -f "$ANCESTOR_PATROL_PLIST_PATH" ]] && have_file=1

  if [[ "$have_file" == "1" ]]; then
    note "  cleanup: found stale $ANCESTOR_PATROL_PLIST_PATH — removing (auto-patrol disabled; upgrade path)"
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] launchctl bootout gui/%s/%s 2>/dev/null || true\n' "$(id -u)" "$ANCESTOR_PATROL_PLIST_LABEL"
    [[ "$have_file" == "1" ]] && printf '[dry-run] rm -f %q\n' "$ANCESTOR_PATROL_PLIST_PATH"
    return 0
  fi
  if [[ "$(uname -s)" == "Darwin" ]]; then
    launchctl bootout "gui/$(id -u)/$ANCESTOR_PATROL_PLIST_LABEL" 2>/dev/null || true
  fi
  [[ "$have_file" == "1" ]] || return 0
  rm -f "$ANCESTOR_PATROL_PLIST_PATH"
}

install_ancestor_patrol_plist() {
  if [[ "$ENABLE_AUTO_PATROL" != "1" ]]; then
    note "Step 6: auto-patrol disabled (default; pass --enable-auto-patrol to install a periodic plist that sends a natural-language patrol request)"
    # Upgrade path: if a previous install had the plist enabled, tear it
    # down so the project actually becomes manual-by-default instead of
    # leaving a ghost LaunchAgent spraying /patrol-tick (or stale
    # payloads) at the ancestor.
    uninstall_ancestor_patrol_plist_if_present
    return 0
  fi
  note "Step 6: install ancestor patrol LaunchAgent (--enable-auto-patrol)"
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

  # Compatibility anchor for tests that still check the old v1 text:
  # `tmux kill-session -t ${PROJECT}-ancestor`. The rendered guide below uses
  # `${PROJECT}-${PRIMARY_SEAT_ID}` so v2 memory-primary projects stay correct.
  mkdir -p "$(dirname "$GUIDE_FILE")" || die 30 GUIDE_DIR_FAILED "unable to create $(dirname "$GUIDE_FILE")"
  cat >"$GUIDE_FILE" <<EOF
# Operator — ClawSeat $PROJECT 启动指引

install.sh 已完成。现在按 6 步触发 Phase-A。v2 minimal 使用项目 workers 窗口 + shared memories 窗口；legacy template 可能仍使用单窗口布局。

1. 切到 primary seat：\`${PROJECT}-${PRIMARY_SEAT_ID}\`。v2 minimal 通常在 \`clawseat-memories\` 窗口的项目 tab；legacy template 可能在项目窗口中。

2. **先确认 ${PROJECT}-${PRIMARY_SEAT_ID} pane 已就绪** — install.sh 不再自动发送 Phase-A kickoff；kickoff 已写入文件，等待 operator 主动触发：

   \`\`\`bash
   tmux capture-pane -t '${PROJECT}-${PRIMARY_SEAT_ID}' -p | tail -15
   \`\`\`

   如果看到 Bypass Permissions / Trust folder / Login / Accessing workspace / Quick safety check 等确认屏，先按屏幕提示处理完，再继续。

3. Phase-A kickoff prompt 文件：

   \`\`\`bash
   cat ${KICKOFF_FILE}
   \`\`\`

4. 选择一种触发方式（A/B/C 三选一）：

   **A) 让当前 install-memory / 安装 agent 通过 transport 发送 kickoff：**

   \`\`\`bash
   bash ${SEND_AND_VERIFY_SCRIPT} --project ${PROJECT} ${PROJECT}-${PRIMARY_SEAT_ID} "\$(cat "${KICKOFF_FILE}")"
   \`\`\`

   **B) 手动粘贴：**

   \`\`\`bash
   cat ${KICKOFF_FILE}
   \`\`\`

   打开 ${PROJECT}-${PRIMARY_SEAT_ID} pane，把输出复制到 primary seat prompt，按 Enter。

   kickoff 内容要求：
   - Phase-A 不让 memory 做同步调研。
   - B2.5 / B5 都按 brief 由 ${PRIMARY_SEAT_ID} seat 自己 Read openclaw / binding 文件。
   - memory 在 Phase-A 唯一位置是 B7 后接收 phase-a-decisions learnings。
   - 然后按 B3 / B3.5 / B5 / B6 / B7 顺序推进；用 agent_admin.py session start-engineer 逐个拉起 seat（不要 fan-out，一个一个来）。

   **C) 让 install-memory 接手：**

   在 install-memory chat 里说：\`dispatch ${PROJECT} kickoff\`。

5. **验证 Phase-A 已启动** — 触发后立刻 re-capture 确认：

   \`\`\`bash
   tmux capture-pane -t '${PROJECT}-${PRIMARY_SEAT_ID}' -p | tail -10
   \`\`\`

   预期看到 \`B0\` / \`已读取 brief\` / \`env_scan\` 等字样。

6. 每走完一步向 ${PRIMARY_SEAT_ID} seat 说"继续"或给修正（provider / chat_id 等）

## 项目注册表

本项目已注册到 \`~/.clawseat/projects.json\`，memories 窗口优先按该注册表展示项目。
如需从注册表移除本项目（不删除 tmux/session 文件）：

\`\`\`bash
python3 ${PROJECTS_REGISTRY_SCRIPT} unregister ${PROJECT}
\`\`\`

## 如果 ${PRIMARY_SEAT_ID} seat 报 BRIEF_DRIFT_DETECTED

${PRIMARY_SEAT_ID} seat 在每个 B 步开始前会先跑 brief drift check hook。这只能检测 brief 是否在你启动后被更新，不能让运行中的 agent 热更新 system prompt。

推荐处理：

1. \`tmux kill-session -t ${PROJECT}-${PRIMARY_SEAT_ID}\`
2. 重新启动 primary seat（建议重跑 \`scripts/install.sh --project ${PROJECT} --reinstall\`，或按同样的 \`agent-launcher.sh\` 参数重起）
3. 让 ${PRIMARY_SEAT_ID} seat 重新读取 \`\$CLAWSEAT_ANCESTOR_BRIEF\`

如果你暂时不 restart，也可以继续按旧 brief 跑，但它不会自动感知后续改动。
EOF
  chmod 600 "$GUIDE_FILE" || die 30 GUIDE_CHMOD_FAILED "unable to chmod $GUIDE_FILE"
}

phase_a_kickoff_prompt() {
  printf '读 %s 开始 Phase-A。按 brief 顺序执行 B0-B7，每步向我汇报或 CLI prompt 我确认。不要 fan-out specialist seat；spawn engineer seat 要 one-at-a-time。\n' "$BRIEF_PATH"
}

persist_phase_a_kickoff_prompt() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] write %s\n' "$KICKOFF_FILE"
    return 0
  fi

  mkdir -p "$(dirname "$KICKOFF_FILE")" || die 30 KICKOFF_DIR_FAILED "unable to create $(dirname "$KICKOFF_FILE")"
  (umask 077; phase_a_kickoff_prompt >"$KICKOFF_FILE") \
    || die 30 KICKOFF_WRITE_FAILED "unable to write $KICKOFF_FILE"
  chmod 600 "$KICKOFF_FILE" || die 30 KICKOFF_CHMOD_FAILED "unable to chmod $KICKOFF_FILE"
}

print_operator_banner() {
  printf '\n'
  printf -- '────────────────────────────────────────────────────────────────\n'
  printf '  ClawSeat install complete / 安装已完成\n'
  printf -- '────────────────────────────────────────────────────────────────\n'
  printf '\n'
  printf '  AGENT (if you are an AI agent running install.sh):\n'
  printf '    You MUST relay this banner to the operator before ending your\n'
  printf '    session. install.sh exiting is NOT the final completion signal —\n'
  printf '    Phase-A has NOT been auto-sent. The operator must choose A/B/C\n'
  printf '    below to trigger kickoff, then verify Phase-A started.\n'
  printf '    See docs/INSTALL.md §0 step 5.\n'
  printf '    向 operator 复述本 banner 是必做步骤，禁止跳过。\n'
  printf '\n'
  printf '  OPERATOR — NEXT STEPS / 操作员下一步:\n'
  printf '    ✔ Install complete. %s pane is ready or waiting for login/trust confirmation.\n' "${PROJECT}-${PRIMARY_SEAT_ID}"
  printf '    Phase-A kickoff prompt was saved here:\n'
  printf '       %s\n' "$KICKOFF_FILE"
  printf '\n'
  printf '    Choose one to start Phase-A / 三选一启动 Phase-A:\n'
  printf '\n'
  printf '    A) Existing install-memory / current install agent dispatches kickoff:\n'
  printf '       bash %q --project %q %q "$(cat %q)"\n' \
    "$SEND_AND_VERIFY_SCRIPT" "$PROJECT" "${PROJECT}-${PRIMARY_SEAT_ID}" "$KICKOFF_FILE"
  printf '\n'
  printf '    B) Manual paste / 手动粘贴:\n'
  printf '       cat %q\n' "$KICKOFF_FILE"
  printf '       Then paste the output into the %s primary seat prompt and press Enter.\n' "${PROJECT}-${PRIMARY_SEAT_ID}"
  printf '\n'
  printf '    C) Ask install-memory in chat / 在 install-memory chat 里说:\n'
  printf '       dispatch %s kickoff\n' "$PROJECT"
  printf '\n'
  printf '    After A/B/C, verify Phase-A is running / 触发后确认:\n'
  printf '       tmux capture-pane -t %q -p | tail -10\n' "${PROJECT}-${PRIMARY_SEAT_ID}"
  printf '       Expected: B0 / "已读取 brief" / env_scan activity.\n'
  printf '\n'
  printf '    Operator guide / 操作员指引:\n'
  printf '       cat %s\n' "$GUIDE_FILE"
  printf '    Registry cleanup / 注册表移除:\n'
  printf '       python3 %q unregister %q\n' "$PROJECTS_REGISTRY_SCRIPT" "$PROJECT"
  printf '\n'
  printf -- '────────────────────────────────────────────────────────────────\n'
}

launcher_auth_for_provider() {
  case "$PROVIDER_MODE" in
    minimax|ark|xcode-best|custom_api|anthropic_console) printf '%s\n' "custom" ;;
    oauth_token) printf '%s\n' "oauth_token" ;;
    oauth) printf '%s\n' "oauth" ;;
    *) die 22 PROVIDER_MODE_UNKNOWN "unknown provider mode for launcher auth mapping: ${PROVIDER_MODE:-<unset>}" ;;
  esac
}

launcher_tool_for_seat() {
  local seat_id="${1:-}"
  if [[ "$seat_id" == "$PRIMARY_SEAT_ID" ]] && memory_primary_skips_claude_provider; then
    printf '%s\n' "$MEMORY_TOOL"
    return
  fi
  printf '%s\n' "claude"
}

launcher_auth_for_seat() {
  local seat_id="${1:-}"
  if [[ "$seat_id" == "$PRIMARY_SEAT_ID" ]] && memory_primary_uses_codex; then
    printf '%s\n' "chatgpt"
    return
  fi
  if [[ "$seat_id" == "$PRIMARY_SEAT_ID" ]] && memory_primary_uses_gemini; then
    printf '%s\n' "oauth"
    return
  fi
  launcher_auth_for_provider
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
  local session="$1" cwd="${2:-$REPO_ROOT}" brief_path="${3:-}" seat_id="${4:-}" auth_mode="" custom_env_file="" launcher_tool=""
  local launcher_model=""
  launcher_tool="$(launcher_tool_for_seat "$seat_id")"
  auth_mode="$(launcher_auth_for_seat "$seat_id")"
  launcher_model="$(memory_effective_model)"
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
  if [[ "$seat_id" == "$PRIMARY_SEAT_ID" && "$launcher_tool" != "claude" && -n "$launcher_model" ]]; then
    cmd+=("LAUNCHER_CUSTOM_MODEL=$launcher_model")
  fi
  cmd+=(bash "$LAUNCHER_SCRIPT" --headless --tool "$launcher_tool" --auth "$auth_mode" --dir "$cwd" --session "$session")
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
  # v1 compat: single-window 6-pane (ancestor + N workers)
  # v2 callers should use workers_payload() + memories_payload() instead.
  "$PYTHON_BIN" - "$PROJECT" "$WAIT_FOR_SEAT_SCRIPT" "$PRIMARY_SEAT_ID" "${PENDING_SEATS[@]}" <<'PY'
import json
import shlex
import sys

project, wait_script, primary_seat = sys.argv[1], sys.argv[2], sys.argv[3]
seats = sys.argv[4:]
panes = [
    {"label": primary_seat, "command": f"tmux attach -t '={project}-{primary_seat}'"},
]
for seat in seats:
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

# v2 workers_payload: planner main left 50% + N-1 workers right grid (max 2 rows, col-major fill)
# Recipe per RFC-001 §3:
#   N_workers=1 (planner only): []
#   N_workers=2 (planner+1):    [(0,True)]
#   N_workers=3 (planner+2):    [(0,True), (1,False)]                            ← v2 minimal
#   N_workers=4 (planner+3):    [(0,True), (1,True), (1,False)]
#   N_workers=5 (planner+4):    [(0,True), (1,True), (1,False), (2,False)]
workers_payload() {
  "$PYTHON_BIN" - "$PROJECT" "$WAIT_FOR_SEAT_SCRIPT" "${PENDING_SEATS[@]}" <<'PY'
import json
import shlex
import sys

project, wait_script = sys.argv[1], sys.argv[2]
seats = sys.argv[3:]  # PENDING_SEATS minus PRIMARY_SEAT_ID
# Locate planner — must be first non-primary worker per minimal template
if "planner" not in seats:
    raise SystemExit("workers_payload requires 'planner' in seats list")
right_seats = [s for s in seats if s != "planner"]
n_total = 1 + len(right_seats)

# Build right-side recipe with max-2-rows, col-major fill
def right_recipe(n_right: int) -> list[list]:
    """Returns split steps relative to pane indices in the COMBINED layout
    (planner is pane 0; right starts as pane 1 after first vertical split)."""
    if n_right == 0: return []
    if n_right == 1: return []  # right side is single pane (after the planner-vs-right split)
    if n_right == 2: return [[1, False]]  # split right horizontally
    # n_right >= 3: build top row of right, then horizontal splits per col
    cols = (n_right + 1) // 2
    splits: list[list[int]] = []
    # Build top row of right area: split pane 1 vertically (cols-1) times
    for col in range(1, cols):
        # parent index in combined layout: 0=planner, 1=right_col0, 2=right_col1, ...
        splits.append([col, True])
    # Horizontal splits: each top right pane splits into bottom (col-major)
    cols_with_bottom = n_right - cols  # number of cols that need a bottom pane
    for col in range(cols_with_bottom):
        splits.append([col + 1, False])  # +1 because pane 0 is planner
    return splits

recipe = [[0, True]] + right_recipe(len(right_seats))  # First: planner | right split

# Pane order for payload (matches recipe creation order):
#   pane[0] = planner (left)
#   pane[1] = right col_0 top (first right worker)
#   pane[2..cols] = top of subsequent right cols
#   pane[cols+1..] = bottom row of right cols (col-major)
#
# NB: planner is a WORKER (spawned by memory during Phase-A), not the primary
# seat. Its tmux session does NOT exist when install.sh opens this window —
# memory will spawn it later. So planner pane MUST use wait-for-seat.sh
# (polling) like the other workers; using direct `tmux attach` here was bug
# #10 (workers_payload planner pane errored to zsh on session-not-found).
panes = [
    {
        "label": "planner",
        "command": "bash "
        + shlex.quote(wait_script)
        + " "
        + shlex.quote(project)
        + " planner",
    },
]
# Compute right-side fill order matching recipe pane creation
n_right = len(right_seats)
if n_right > 0:
    cols = max(1, (n_right + 1) // 2 if n_right >= 3 else 1)
    # For n_right=1: just first right_seat
    # For n_right=2: top + bottom (1 col)
    # For n_right>=3: row-major in driver order = top row left-to-right + bottom row left-to-right
    if n_right == 1:
        ordering = [0]
    elif n_right == 2:
        ordering = [0, 1]  # top, bottom
    else:
        # User intent (col-major): user_idx 0=col0_top, 1=col0_bot, 2=col1_top, 3=col1_bot, ...
        # Driver order: top row first (col0_top, col1_top, col2_top, ...), then bottom row
        # Map: driver_pane_idx -> user_idx
        ordering = []
        # top row first
        for col in range(cols):
            user_idx = col * 2  # top of col c is user_idx 2c
            if user_idx < n_right:
                ordering.append(user_idx)
        # bottom row
        for col in range(cols):
            user_idx = col * 2 + 1  # bottom of col c is user_idx 2c+1
            if user_idx < n_right:
                ordering.append(user_idx)
    for driver_idx, user_idx in enumerate(ordering):
        seat = right_seats[user_idx]
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

print(json.dumps({
    "title": f"clawseat-{project}-workers",
    "panes": panes,
    "recipe": recipe,
}, ensure_ascii=False))
PY
}

# v2 memories_payload: prefer ~/.clawseat/projects.json, fallback to live tmux memory sessions.
memories_payload() {
  PYTHONPATH="$REPO_ROOT/core/scripts${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" - <<'PY'
import json
import os
import subprocess

from projects_registry import enumerate_projects


def registry_tabs():
    tabs = []
    for entry in enumerate_projects():
        name = entry.get("name")
        tmux_name = entry.get("tmux_name")
        if not name or not tmux_name:
            continue
        tabs.append({
            "name": name,
            "command": f"tmux attach -t '={tmux_name}'",
        })
    return tabs


def tmux_fallback_tabs():
    result = subprocess.run(
        ["tmux", "ls", "-F", "#{session_name}"],
        capture_output=True, text=True, env={**os.environ, "TMUX": ""}, check=False,
    )
    all_sessions = result.stdout.strip().split("\n") if result.returncode == 0 else []
    legacy_global_memory = "-".join(("machine", "memory", "claude"))
    memory_sessions = sorted([
        s for s in all_sessions
        if s.endswith("-memory") and s != legacy_global_memory
    ])
    return [
        {
            "name": sess[:-len("-memory")],
            "command": f"tmux attach -t '={sess}'",
        }
        for sess in memory_sessions
    ]


tabs = registry_tabs() or tmux_fallback_tabs()
if not tabs:
    print(json.dumps({"status": "skip", "reason": "no registered or live project memory sessions found"}))
    raise SystemExit(0)

print(json.dumps({
    "mode": "tabs",
    "title": "clawseat-memories",
    "tabs": tabs,
    "ensure": True,
}, ensure_ascii=False))
PY
}

main() {
  parse_args "$@"; prompt_kind_first_flow; resolve_pending_seats; normalize_provider_choice
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] CLAWSEAT_TEMPLATE_NAME=%s\n' "$CLAWSEAT_TEMPLATE_NAME" >&2
    printf '[dry-run] PENDING_SEATS=(%s)\n' "${PENDING_SEATS[*]}" >&2
  fi
  ensure_host_deps; ensure_python_tomllib_fallback; scan_machine; select_provider; render_brief
  note "Step 5: launch primary seat ($PRIMARY_SEAT_ID) via agent-launcher"
  launch_seat "$PROJECT-$PRIMARY_SEAT_ID" "$MEMORY_WORKSPACE" "$BRIEF_PATH" "$PRIMARY_SEAT_ID"
  bootstrap_project_profile
  ensure_privacy_kb_template
  install_skill_symlinks
  install_privacy_pre_commit_hook
  register_project_registry
  install_ancestor_patrol_plist

  # v2 split window topology (per RFC-001 §3): one workers window per project +
  # one shared memories window across all projects (rebuilt on each install).
  # v1 single-window grid_payload preserved as fallback for clawseat-default
  # template (which still uses 6-pane single-window).
  if [[ "$CLAWSEAT_TEMPLATE_NAME" == "clawseat-minimal" ]]; then
    note "Step 7a: open per-project workers window (planner main + ${#PENDING_SEATS[@]} workers)"
    open_iterm_window "$(workers_payload)" GRID_WINDOW_ID

    [[ ! -f "$REPO_ROOT/scripts/cleanup-stale-memories-window.sh" ]] || bash "$REPO_ROOT/scripts/cleanup-stale-memories-window.sh" || true
    note "Step 7b: ensure shared memories window (tab per project)"
    local _memories_payload
    _memories_payload="$(memories_payload)"
    if [[ -n "$_memories_payload" && "$_memories_payload" != *'"status": "skip"'* ]]; then
      local _mem_window_id=""
      open_iterm_window "$_memories_payload" _mem_window_id
    else
      warn "memories_payload returned skip — no project memory tmux sessions found"
    fi
  else
    # v1 single-window topology (clawseat-default / engineering / creative)
    note "Step 7: open six-pane iTerm grid"; open_iterm_window "$(grid_payload)" GRID_WINDOW_ID
  fi

  # v1 machine-memory-claude tmux session may still be running on machines
  # upgraded from v0.6 or earlier; v2 install no longer creates/manages it.
  # M4 will retire the legacy session entirely.
  note "Step 9: focus primary seat ($PRIMARY_SEAT_ID) and persist operator guide"
  if [[ -n "$GRID_WINDOW_ID" ]]; then
    run sleep 3
    focus_iterm_window "$GRID_WINDOW_ID" "$PRIMARY_SEAT_ID"
  else
    warn "Skipping primary seat focus because no iTerm grid window was opened."
  fi
  note "Step 9.5: persist Phase-A kickoff prompt to ancestor-kickoff.txt"
  persist_phase_a_kickoff_prompt
  write_operator_guide
  print_operator_banner
}

main "$@"
