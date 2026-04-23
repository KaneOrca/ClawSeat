#!/usr/bin/env bash
# INTERNAL — do not call directly.
# This is the L3 execution primitive in the v0.7 Seat Lifecycle Pyramid:
#   L1 (user-facing): scripts/install.sh, scripts/apply-koder-overlay.sh
#   L2 (CLI ops):     agent_admin session start-engineer, agent_admin project ...
#   L3 (this file):   agent-launcher.sh — sandbox HOME + secrets + runtime_dir
# See docs/ARCHITECTURE.md §3z for the full contract.
# If you find yourself calling this script directly from a TODO or doc,
# reconsider — L1 or L2 should already cover your case.
# Unified deterministic launcher for Claude Code, Codex, and Gemini CLI.
#
# Merged into clawseat from ~/Desktop/agent-launcher.command.
# All intra-launcher paths are now self-relative so this file can live in
# any directory. User-specific defaults (preset store, workspace
# bookmarks) read from env vars with desktop-compat defaults for back-compat.

set -euo pipefail

REAL_HOME="$HOME"
LAUNCHER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAUNCHER_REPO_ROOT="$(cd "$LAUNCHER_DIR/../.." && pwd)"
LAUNCHER_PYTHON_BIN="${PYTHON_BIN:-python3}"
HELPER="$LAUNCHER_DIR/agent-launcher-common.sh"
DISCOVER_HELPER="$LAUNCHER_DIR/agent-launcher-discover.py"
# Export so launcher helpers can resolve sibling files self-relatively.
export AGENT_LAUNCHER_DIR="$LAUNCHER_DIR"
# User preset storage — default to XDG config, fall back to legacy desktop path
# if it exists (seamless upgrade for users migrating from the desktop-only era).
if [[ -n "${AGENT_LAUNCHER_CUSTOM_PRESET_STORE:-}" ]]; then
  CUSTOM_PRESET_STORE="$AGENT_LAUNCHER_CUSTOM_PRESET_STORE"
elif [[ -f "$REAL_HOME/Desktop/.agent-launcher-custom-presets.json" ]]; then
  CUSTOM_PRESET_STORE="$REAL_HOME/Desktop/.agent-launcher-custom-presets.json"
else
  CUSTOM_PRESET_STORE="$REAL_HOME/.config/clawseat/launcher-custom-presets.json"
fi

if [[ ! -f "$HELPER" ]]; then
  echo "error: missing helper script: $HELPER" >&2
  exit 1
fi

# shellcheck source=./agent-launcher-common.sh
source "$HELPER"

launcher_config_value() {
  local query="$1"
  local tool="${2:-}"
  local provider="${3:-}"
  "$LAUNCHER_PYTHON_BIN" - "$LAUNCHER_REPO_ROOT" "$query" "$tool" "$provider" <<'PY'
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

launcher_tool_default_base_url() {
  launcher_config_value "tool-default-base-url" "$1"
}

launcher_provider_default_base_url() {
  launcher_config_value "provider-default-base-url" "$1" "$2"
}

TOOL_NAME=""
SESSION_NAME=""
AUTH_MODE=""
WORKDIR=""
EXEC_MODE=""
CUSTOM_ENV_FILE=""
GENERATED_CUSTOM_ENV_FILE="0"
HEADLESS="0"
DRY_RUN="0"
CHECK_SECRETS_TOOL=""      # set by --check-secrets <tool> (needs --auth too)

print_help() {
  cat <<'EOF'
Usage: agent-launcher.sh [options]

Options:
  --tool <claude|codex|gemini>   Agent CLI to launch
  --auth <mode>                  Authentication mode for the selected tool
  --dir <path>                   Startup directory
  --session <name>               tmux session name
  --custom-env-file <path>       Internal one-shot custom API env file
  --headless                     Compatibility flag; launcher is tmux-only
  --dry-run                      Print resolved launch config and exit
  --exec-agent                   Internal flag used inside tmux
  --check-secrets <tool>         Report secret-file readiness as JSON
  -h, --help                     Show this help
EOF
}

uppercase_ascii() {
  printf '%s' "$1" | tr '[:lower:]' '[:upper:]'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tool) TOOL_NAME="$2"; shift 2 ;;
    --session) SESSION_NAME="$2"; shift 2 ;;
    --auth) AUTH_MODE="$2"; shift 2 ;;
    --dir) WORKDIR="$2"; shift 2 ;;
    --custom-env-file) CUSTOM_ENV_FILE="$2"; shift 2 ;;
    --headless) HEADLESS="1"; shift ;;
    --dry-run) DRY_RUN="1"; shift ;;
    --exec-agent) EXEC_MODE="1"; shift ;;
    # Preflight hook: agent-launcher.sh --check-secrets <tool> --auth <mode>
    # prints one JSON line saying whether the auth's secret file/key is ready.
    --check-secrets) CHECK_SECRETS_TOOL="$2"; shift 2 ;;
    --help|-h) print_help; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

validate_tool_name() {
  case "$1" in
    claude|codex|gemini) return 0 ;;
    *)
      echo "error: --tool must be claude|codex|gemini, got '$1'" >&2
      exit 2
      ;;
  esac
}

validate_auth_mode() {
  local tool="$1" auth="$2"
  case "$tool:$auth" in
    claude:oauth|claude:oauth_token|claude:anthropic-console|claude:minimax|claude:xcode|claude:custom|\
    codex:chatgpt|codex:xcode|codex:custom|\
    gemini:oauth|gemini:primary|gemini:custom)
      return 0
      ;;
    *)
      echo "error: unsupported auth '$auth' for tool '$tool'" >&2
      exit 2
      ;;
  esac
}

resolve_launcher_workdir() {
  local raw_path="${1:-}"
  if [[ -z "$raw_path" ]]; then
    pwd -P
    return 0
  fi
  launcher_resolve_directory_path "$raw_path" 2>/dev/null || {
    echo "error: startup directory does not exist: $raw_path" >&2
    exit 1
  }
}

default_session_name() {
  local tool="$1" auth="$2" workdir="$3"
  printf '%s\n' "${tool}-${auth}-$(launcher_slugify "$(basename "$workdir")")"
}

prompt_tool_and_auth_interactive() {
  # Only prompt when stdin is a TTY and not running headless.
  if [[ ! -t 0 ]] || [[ "$HEADLESS" == "1" ]]; then
    return 1
  fi
  if [[ -z "$TOOL_NAME" ]]; then
    printf 'Tool [claude/codex/gemini]: ' >&2
    read -r TOOL_NAME
  fi
  if [[ -z "$AUTH_MODE" ]]; then
    printf 'Auth mode [oauth/oauth_token/api/custom/...]: ' >&2
    read -r AUTH_MODE
  fi
  return 0
}

validate_top_level_inputs() {
  if [[ -z "$TOOL_NAME" ]]; then
    if ! prompt_tool_and_auth_interactive; then
      echo "error: --tool is required" >&2
      exit 2
    fi
  fi
  validate_tool_name "$TOOL_NAME"

  if [[ -z "$AUTH_MODE" ]]; then
    if ! prompt_tool_and_auth_interactive; then
      echo "error: --auth is required" >&2
      exit 2
    fi
  fi
  validate_auth_mode "$TOOL_NAME" "$AUTH_MODE"

  WORKDIR="$(resolve_launcher_workdir "$WORKDIR")"
  [[ -n "$SESSION_NAME" ]] || SESSION_NAME="$(default_session_name "$TOOL_NAME" "$AUTH_MODE" "$WORKDIR")"
}


write_custom_env_file() {
  local api_key="$1"
  local base_url="$2"
  local model="$3"
  local env_file
  env_file="$(mktemp /tmp/agent-launcher-custom.XXXXXX)"
  chmod 600 "$env_file"
  {
    printf 'export LAUNCHER_CUSTOM_API_KEY=%q\n' "$api_key"
    if [[ -n "$base_url" ]]; then
      printf 'export LAUNCHER_CUSTOM_BASE_URL=%q\n' "$base_url"
    fi
    if [[ -n "$model" ]]; then
      printf 'export LAUNCHER_CUSTOM_MODEL=%q\n' "$model"
    fi
  } >"$env_file"
  printf '%s\n' "$env_file"
}

env_file_has_key() {
  local path="$1"
  local key="$2"
  python3 - "$path" "$key" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
if not path.exists():
    raise SystemExit(1)

try:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
except Exception:
    raise SystemExit(1)

for line in lines:
    s = line.strip()
    if not s or s.startswith("#"):
        continue
    if s.startswith("export "):
        s = s[len("export "):].strip()
    if not s.startswith(key + "="):
        continue
    value = s.split("=", 1)[1].strip().strip('"').strip("'")
    if value:
        raise SystemExit(0)

raise SystemExit(1)
PY
}

# ── --check-secrets dispatch ───────────────────────────────────────────
# install preflight hook: given --check-secrets <tool> + --auth <mode>,
# resolve the expected secret file and report its state as one JSON line on
# stdout so Python callers can parse without shelling out to jq.
#   exit 0 = secret file present + required key found (or inherently not needed)
#   exit 1 = missing file or missing key (hint in payload)
#   exit 2 = bad (tool, auth) combination or --auth missing
if [[ -n "$CHECK_SECRETS_TOOL" ]]; then
  if [[ -z "$AUTH_MODE" ]]; then
    echo '{"status":"error","reason":"--check-secrets requires --auth <mode>"}' >&2
    exit 2
  fi
  _cs_file=""
  _cs_key=""
  case "$CHECK_SECRETS_TOOL" in
    claude)
      case "$AUTH_MODE" in
        oauth)
          printf '{"status":"ok","note":"legacy keychain oauth; no secret file"}\n'
          exit 0 ;;
        oauth_token)
          _cs_file="$REAL_HOME/.agents/.env.global"
          _cs_key="CLAUDE_CODE_OAUTH_TOKEN" ;;
        anthropic-console)
          _cs_file="$REAL_HOME/.agents/secrets/claude/anthropic-console.env"
          _cs_key="ANTHROPIC_API_KEY" ;;
        minimax)
          _cs_file="$REAL_HOME/.agent-runtime/secrets/claude/minimax.env"
          _cs_key="ANTHROPIC_AUTH_TOKEN" ;;
        xcode)
          _cs_file="$REAL_HOME/.agent-runtime/secrets/claude/xcode.env"
          _cs_key="ANTHROPIC_AUTH_TOKEN" ;;
        custom)
          printf '{"status":"ok","note":"custom auth — secret via --custom-env-file"}\n'
          exit 0 ;;
        *) echo "{\"status\":\"error\",\"reason\":\"unknown claude auth '$AUTH_MODE'\"}" >&2 ; exit 2 ;;
      esac ;;
    codex)
      case "$AUTH_MODE" in
        chatgpt)
          printf '{"status":"ok","note":"codex chatgpt login uses ~/.codex (keychain); no file needed"}\n'
          exit 0 ;;
        xcode)
          _cs_file="$REAL_HOME/.agent-runtime/secrets/codex/xcode.env"
          _cs_key="OPENAI_API_KEY" ;;
        custom)
          printf '{"status":"ok","note":"custom auth — secret via --custom-env-file"}\n'
          exit 0 ;;
        *) echo "{\"status\":\"error\",\"reason\":\"unknown codex auth '$AUTH_MODE'\"}" >&2 ; exit 2 ;;
      esac ;;
    gemini)
      case "$AUTH_MODE" in
        oauth)
          printf '{"status":"ok","note":"gemini google oauth uses ~/.gemini (keychain); no file needed"}\n'
          exit 0 ;;
        primary)
          _cs_file="$REAL_HOME/.agent-runtime/secrets/gemini/primary.env"
          _cs_key="GEMINI_API_KEY" ;;
        custom)
          printf '{"status":"ok","note":"custom auth — secret via --custom-env-file"}\n'
          exit 0 ;;
        *) echo "{\"status\":\"error\",\"reason\":\"unknown gemini auth '$AUTH_MODE'\"}" >&2 ; exit 2 ;;
      esac ;;
    *)
      echo "{\"status\":\"error\",\"reason\":\"--check-secrets tool must be claude|codex|gemini, got '$CHECK_SECRETS_TOOL'\"}" >&2
      exit 2 ;;
  esac
  if [[ ! -f "$_cs_file" ]]; then
    if [[ "$CHECK_SECRETS_TOOL" = "claude" ]] && [[ "$AUTH_MODE" = "oauth_token" ]]; then
      _hint="run: claude setup-token    # paste result into $_cs_file"
    else
      _hint="obtain the $_cs_key for $CHECK_SECRETS_TOOL/$AUTH_MODE and write it into $_cs_file"
    fi
    printf '{"status":"missing-file","file":"%s","key":"%s","hint":"%s"}\n' \
      "$_cs_file" "$_cs_key" "$_hint"
    exit 1
  fi
  if ! env_file_has_key "$_cs_file" "$_cs_key"; then
    printf '{"status":"missing-key","file":"%s","key":"%s","hint":"add %s=... to %s"}\n' \
      "$_cs_file" "$_cs_key" "$_cs_key" "$_cs_file"
    exit 1
  fi
  printf '{"status":"ok","file":"%s","key":"%s"}\n' "$_cs_file" "$_cs_key"
  exit 0
fi

ensure_custom_env_file_for_auth() {
  if [[ "$AUTH_MODE" != "custom" ]]; then
    return 0
  fi
  if [[ -n "$CUSTOM_ENV_FILE" ]]; then
    if [[ ! -f "$CUSTOM_ENV_FILE" ]]; then
      echo "error: missing custom env file: $CUSTOM_ENV_FILE" >&2
      exit 2
    fi
    return 0
  fi
  if [[ -z "${LAUNCHER_CUSTOM_API_KEY:-}" ]]; then
    echo "error: --auth custom requires --custom-env-file or LAUNCHER_CUSTOM_API_KEY in env" >&2
    exit 2
  fi
  CUSTOM_ENV_FILE="$(write_custom_env_file \
    "${LAUNCHER_CUSTOM_API_KEY:-}" \
    "${LAUNCHER_CUSTOM_BASE_URL:-}" \
    "${LAUNCHER_CUSTOM_MODEL:-}")"
  GENERATED_CUSTOM_ENV_FILE="1"
}

cleanup_generated_custom_env_file() {
  if [[ "$GENERATED_CUSTOM_ENV_FILE" == "1" && -n "$CUSTOM_ENV_FILE" && -f "$CUSTOM_ENV_FILE" ]]; then
    rm -f "$CUSTOM_ENV_FILE"
  fi
}

load_custom_env() {
  local env_file="$1"
  if [[ -z "$env_file" ]]; then
    return 0
  fi
  if [[ ! -f "$env_file" ]]; then
    echo "error: missing custom env file: $env_file" >&2
    exit 1
  fi

  set -a
  source "$env_file"
  set +a
  rm -f "$env_file"
}

seed_user_tool_dirs() {
  # Seed user-level tool directories/files from the real HOME into the
  # per-seat sandbox HOME. This keeps user-auth state and tool sockets
  # visible to isolated runtimes without copying secrets out of band.
  #
  # If a sandbox already has an independent copy, move it aside under
  # .sandbox-pre-seed-backup/ and replace it with a symlink so we can
  # retroactively heal old runtimes.
  local runtime_home="$1"
  local project_name="${2:-${CLAWSEAT_PROJECT:-}}"
  if [[ "$runtime_home" == "$REAL_HOME" ]]; then
    return 0
  fi
  local source_home="$REAL_HOME"
  if [[ "${CLAWSEAT_TOOLS_ISOLATION:-shared-real-home}" == "per-project" && -n "$project_name" ]]; then
    source_home="${CLAWSEAT_PROJECT_TOOL_ROOT:-${AGENT_HOME:-$REAL_HOME}/.agent-runtime/projects/$project_name}"
    [[ -d "$source_home" ]] || return 0
  fi
  local seeds=(
    ".lark-cli"
    "Library/Application Support/iTerm2"
    "Library/Preferences/com.googlecode.iterm2.plist"
    ".config/gemini"
    ".gemini"
    ".config/codex"
    ".codex"
  )

  local subpath src tgt backup_base backup_path current_target
  backup_base="$runtime_home/.sandbox-pre-seed-backup"
  for subpath in "${seeds[@]}"; do
    src="$source_home/$subpath"
    tgt="$runtime_home/$subpath"
    [[ -e "$src" ]] || continue

    if [[ -L "$tgt" ]]; then
      current_target="$(readlink "$tgt" 2>/dev/null || true)"
      if [[ "$current_target" == "$src" ]]; then
        continue
      fi
      rm -f "$tgt"
    elif [[ -e "$tgt" ]]; then
      backup_path="$backup_base/$subpath.$(date +%s)"
      mkdir -p "$(dirname "$backup_path")"
      mv "$tgt" "$backup_path"
    fi

    if [[ ! -e "$tgt" ]]; then
      mkdir -p "$(dirname "$tgt")"
      ln -s "$src" "$tgt"
    fi
  done
}

resolve_claude_secret_file() {
  case "$1" in
    oauth_token) printf '%s\n' "$REAL_HOME/.agents/.env.global" ;;
    anthropic-console) printf '%s\n' "$REAL_HOME/.agents/secrets/claude/anthropic-console.env" ;;
    minimax) printf '%s\n' "$REAL_HOME/.agent-runtime/secrets/claude/minimax.env" ;;
    xcode) printf '%s\n' "$REAL_HOME/.agent-runtime/secrets/claude/xcode.env" ;;
    *) return 1 ;;
  esac
}

show_claude_auth_setup_hint() {
  local auth_mode="$1"
  case "$auth_mode" in
    oauth_token)
      cat >&2 <<'EOF'
hint: missing Claude OAuth token
  run: claude setup-token
  then write the result into: ~/.agents/.env.global
  example: export CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...
EOF
      ;;
    anthropic-console)
      cat >&2 <<'EOF'
hint: missing Anthropic Console API key
  create a Claude Code scoped key in Anthropic Console
  then write it into: ~/.agents/secrets/claude/anthropic-console.env
  example: ANTHROPIC_API_KEY=sk-ant-api03-...
EOF
      ;;
  esac
}

prepare_codex_home() {
  local codex_home="$1"
  local source_home="${2:-$HOME}"
  mkdir -p "$codex_home"

  local shared_items=(
    "config.toml"
    "skills"
    "plugins"
    "rules"
    "vendor_imports"
  )

  local item
  for item in "${shared_items[@]}"; do
    if [[ -e "$source_home/.codex/$item" && ! -e "$codex_home/$item" ]]; then
      ln -s "$source_home/.codex/$item" "$codex_home/$item"
    fi
  done
}

prepare_gemini_home() {
  local runtime_home="$1"
  local workdir="${2:-${WORKDIR:-}}"
  local project_name="${3:-${CLAWSEAT_PROJECT:-}}"
  local source_home="$REAL_HOME"
  if [[ "${CLAWSEAT_TOOLS_ISOLATION:-shared-real-home}" == "per-project" && -n "$project_name" ]]; then
    source_home="${CLAWSEAT_PROJECT_TOOL_ROOT:-${AGENT_HOME:-$REAL_HOME}/.agent-runtime/projects/$project_name}"
    [[ -d "$source_home" ]] || source_home="$REAL_HOME"
  fi
  local gemini_home="$runtime_home/.gemini"
  local source_gemini_home="$source_home/.gemini"
  local current_target=""
  mkdir -p "$gemini_home"

  if [[ -L "$gemini_home" ]]; then
    current_target="$(readlink "$gemini_home" 2>/dev/null || true)"
    if [[ "$current_target" == "$source_gemini_home" ]]; then
      rm -f "$gemini_home"
      mkdir -p "$gemini_home"
    fi
  fi

  if [[ -d "$source_gemini_home" ]]; then
    local item item_name
    shopt -s nullglob
    for item in "$source_gemini_home"/*; do
      item_name="${item##*/}"
      [[ "$item_name" == "trustedFolders.json" ]] && continue
      if [[ ! -e "$gemini_home/$item_name" ]]; then
        ln -s "$item" "$gemini_home/$item_name"
      fi
    done
    shopt -u nullglob
  fi

  if [[ -n "$workdir" ]]; then
    if [[ -L "$gemini_home/trustedFolders.json" ]]; then
      rm -f "$gemini_home/trustedFolders.json"
    fi
    python3 - "$source_gemini_home/trustedFolders.json" "$gemini_home/trustedFolders.json" "$workdir" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
workdir = sys.argv[3]
data: dict[str, str] = {}
for candidate in (src, dst):
    if not candidate.exists():
        continue
    try:
        loaded = json.loads(candidate.read_text(encoding="utf-8"))
    except Exception:
        loaded = {}
    if isinstance(loaded, dict):
        data.update({str(key): str(value) for key, value in loaded.items()})
data[workdir] = "TRUST_FOLDER"
dst.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY
  fi
}

prepare_claude_home() {
  # Seed Claude Code's isolated HOME so onboarding doesn't fire for every
  # seat launch. Keep Claude on an explicit white-list model: share a
  # small set of user-level compatibility paths, but materialize the
  # sandbox's settings/skills from the seat-specific .claude-template.
  local runtime_home="$1"
  local session_name="${2:-}"
  local runtime_claude="$runtime_home/.claude"
  local source_claude="$REAL_HOME/.claude"
  local source_claude_json="$REAL_HOME/.claude.json"
  local runtime_claude_json="$runtime_home/.claude.json"
  local existing_runtime_claude_json=""
  mkdir -p "$runtime_claude"

  # Always materialize a runtime-local .claude.json for isolated API seats.
  # The real host file may carry an unfinished onboarding state that forces
  # Claude Code back into the login picker even when API auth env is already
  # present. Keep useful host/runtime fields, but force onboarding complete.
  if [[ -f "$runtime_claude_json" && ! -L "$runtime_claude_json" ]]; then
    existing_runtime_claude_json="$runtime_claude_json"
  fi
  if [[ -L "$runtime_claude_json" ]]; then
    rm -f "$runtime_claude_json"
  fi
  python3 - "$source_claude_json" "$existing_runtime_claude_json" "$runtime_claude_json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

source_path = Path(sys.argv[1])
existing_runtime_path = Path(sys.argv[2]) if sys.argv[2] else None
target_path = Path(sys.argv[3])
data: dict[str, object] = {}

for candidate in (source_path, existing_runtime_path):
    if candidate is None or not candidate.exists():
        continue
    try:
        loaded = json.loads(candidate.read_text(encoding="utf-8"))
    except Exception:
        loaded = {}
    if isinstance(loaded, dict):
        data.update(loaded)

data["hasCompletedOnboarding"] = True
data["hasSeenWelcome"] = True
version = data.get("lastOnboardingVersion")
if not isinstance(version, str) or not version.strip():
    data["lastOnboardingVersion"] = "99.99.99"

target_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY

  # Preserve compatibility caches and definition directories that remain
  # intentionally shared across sandboxes.
  local compat_items=(
    "statsig"
  )
  local item
  for item in "${compat_items[@]}"; do
    if [[ -e "$source_claude/$item" && ! -e "$runtime_claude/$item" ]]; then
      ln -s "$source_claude/$item" "$runtime_claude/$item"
    fi
  done

  local shared_items=(
    "commands"
    "agents"
  )
  for item in "${shared_items[@]}"; do
    if [[ -e "$source_claude/$item" && ! -e "$runtime_claude/$item" ]]; then
      ln -s "$source_claude/$item" "$runtime_claude/$item"
    fi
  done

  local seat_id="${CLAWSEAT_SEAT:-${CLAWSEAT_ENGINEER_ID:-}}"
  # Fallback: infer seat_id from session_name when env not passed.
  # session_name formats: "<project>-<seat>-<tool>" or "<project>-ancestor" or "machine-memory-<tool>"
  if [[ -z "$seat_id" && -n "$session_name" ]]; then
    local _project="${CLAWSEAT_PROJECT:-}"
    local _candidate="$session_name"
    [[ -n "$_project" ]] && _candidate="${_candidate#${_project}-}"
    _candidate="${_candidate#machine-}"
    _candidate="${_candidate%-claude}"
    _candidate="${_candidate%-codex}"
    _candidate="${_candidate%-gemini}"
    if [[ -d "${AGENTS_ROOT:-$REAL_HOME/.agents}/engineers/$_candidate" ]]; then
      seat_id="$_candidate"
    fi
  fi
  local runtime_settings="$runtime_claude/settings.json"
  local runtime_skills="$runtime_claude/skills"
  if [[ -n "$seat_id" ]]; then
    "$LAUNCHER_PYTHON_BIN" - "$LAUNCHER_REPO_ROOT" "${AGENTS_ROOT:-$REAL_HOME/.agents}" "$seat_id" "$runtime_claude" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
agents_root = Path(sys.argv[2])
seat_id = sys.argv[3]
runtime_claude_root = Path(sys.argv[4])
sys.path.insert(0, str(repo_root / "core" / "scripts"))

from seat_claude_template import copy_seat_claude_template_to_runtime

copy_seat_claude_template_to_runtime(
    agents_root / "engineers",
    seat_id,
    runtime_claude_root,
    clawseat_root=repo_root,
)
PY
    return 0
  fi

  if [[ -L "$runtime_settings" ]]; then
    rm -f "$runtime_settings"
  fi
  if [[ -L "$runtime_skills" ]]; then
    rm -f "$runtime_skills"
  fi
  mkdir -p "$runtime_skills"
  "$LAUNCHER_PYTHON_BIN" - "$runtime_settings" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

target_path = Path(sys.argv[1])
data: dict[str, object] = {}
if target_path.exists():
    try:
        loaded = json.loads(target_path.read_text(encoding="utf-8"))
    except Exception:
        loaded = {}
    if isinstance(loaded, dict):
        data.update(loaded)
if not isinstance(data.get("hooks"), dict):
    data["hooks"] = {}
if not isinstance(data.get("permissions"), dict):
    data["permissions"] = {}
target_path.parent.mkdir(parents=True, exist_ok=True)
target_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY
}

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
    # Reference: /Users/ywf/coding/agent-launcher (launcher_runtime.sh:201,
    # launcher_data.py:124) has the canonical recipe; ClawSeat used to
    # only restore HOME (missed XDG + CLAUDE_CODE_OAUTH_TOKEN), which
    # left Claude looking at sandbox XDG dirs and picking up whatever
    # stale token env we inherited — the real "re-auth every start" bug.
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

run_codex_runtime() {
  local auth_mode="$1"
  local workdir="$2"
  local session_name="$3"

  if [[ "$auth_mode" == "chatgpt" ]]; then
    export HOME="$REAL_HOME"
    export CODEX_HOME="$REAL_HOME/.codex"
    seed_user_tool_dirs "$HOME" "${CLAWSEAT_PROJECT:-}"
    cd "$workdir"
    echo "────────────────────────────────────────"
    echo " Codex · ChatGPT login"
    echo " Session:    $session_name"
    echo " Directory:  $workdir"
    echo " CODEX_HOME: $CODEX_HOME"
    echo "────────────────────────────────────────"
    exec codex --dangerously-bypass-approvals-and-sandbox -C "$workdir"
  fi

  local secret_file="" runtime_dir
  if [[ "$auth_mode" != "custom" ]]; then
    secret_file="$REAL_HOME/.agent-runtime/secrets/codex/xcode.env"
    if [[ ! -f "$secret_file" ]]; then
      echo "error: missing Codex secret file: $secret_file" >&2
      exit 1
    fi
  fi

  runtime_dir="$REAL_HOME/.agent-runtime/identities/codex/api/${auth_mode}-$session_name"
  mkdir -p "$runtime_dir/home" "$runtime_dir/codex-home"

  export HOME="$runtime_dir/home"
  export CODEX_HOME="$runtime_dir/codex-home"
  seed_user_tool_dirs "$HOME" "${CLAWSEAT_PROJECT:-}"
  prepare_codex_home "$CODEX_HOME" "$HOME"

  if [[ "$auth_mode" == "custom" ]]; then
    load_custom_env "$CUSTOM_ENV_FILE"
    rm -f "$CODEX_HOME/config.toml"
    python3 - "$CODEX_HOME/config.toml" "${LAUNCHER_CUSTOM_MODEL:-gpt-5.4}" "${LAUNCHER_CUSTOM_BASE_URL:-$(launcher_tool_default_base_url codex)}" "${LAUNCHER_CUSTOM_API_KEY:-}" <<'PY'
import json
import sys

config_path, model, base_url, api_key = sys.argv[1:5]
with open(config_path, "w", encoding="utf-8") as handle:
    handle.write(f"model = {json.dumps(model)}\n")
    handle.write("[model_providers.customapi]\n")
    handle.write('name = "customapi"\n')
    handle.write(f"base_url = {json.dumps(base_url)}\n")
    handle.write('wire_api = "responses"\n')
    handle.write(f"experimental_bearer_token = {json.dumps(api_key)}\n")
PY
  else
    set -a
    source "$secret_file"
    set +a
    rm -f "$CODEX_HOME/config.toml"
    if [[ -z "${OPENAI_BASE_URL:-}" && -z "${OPENAI_API_BASE:-}" ]]; then
      case "${CLAWSEAT_PROVIDER:-}" in
        xcode-best)
          export OPENAI_BASE_URL="$(launcher_provider_default_base_url codex xcode-best)"
          ;;
      esac
    fi
    python3 - "$CODEX_HOME/config.toml" "${OPENAI_BASE_URL:-${OPENAI_API_BASE:-$(launcher_provider_default_base_url codex xcode-best)}}" "${OPENAI_API_KEY:-}" <<'PY'
import json
import sys

config_path, base_url, api_key = sys.argv[1:4]
with open(config_path, "w", encoding="utf-8") as handle:
    handle.write('model_provider = "xcodeapi"\n')
    handle.write('model = "gpt-5.4"\n')
    handle.write("[model_providers.xcodeapi]\n")
    handle.write('name = "xcodeapi"\n')
    handle.write(f"base_url = {json.dumps(base_url)}\n")
    handle.write('wire_api = "responses"\n')
    handle.write(f"experimental_bearer_token = {json.dumps(api_key)}\n")
PY
    if [[ ! -f "$CODEX_HOME/auth.json" ]]; then
      printf '%s' "${OPENAI_API_KEY:-}" | HOME="$HOME" CODEX_HOME="$CODEX_HOME" codex login --with-api-key >/dev/null
    fi
  fi

  cd "$workdir"
  echo "────────────────────────────────────────"
  echo " Codex · $(uppercase_ascii "$auth_mode") API"
  echo " Session:    $session_name"
  echo " Directory:  $workdir"
  echo " HOME:       $HOME"
  echo " CODEX_HOME: $CODEX_HOME"
  echo "────────────────────────────────────────"
  if [[ "$auth_mode" == "custom" ]]; then
    if [[ -n "${LAUNCHER_CUSTOM_MODEL:-}" ]]; then
      exec codex --dangerously-bypass-approvals-and-sandbox -C "$workdir" -c model_provider=customapi -m "${LAUNCHER_CUSTOM_MODEL}"
    fi
    exec codex --dangerously-bypass-approvals-and-sandbox -C "$workdir" -c model_provider=customapi
  fi
  exec codex --dangerously-bypass-approvals-and-sandbox -C "$workdir"
}

run_gemini_runtime() {
  local auth_mode="$1"
  local workdir="$2"
  local session_name="$3"

  if [[ "$auth_mode" == "oauth" ]]; then
    unset GEMINI_API_KEY GOOGLE_API_KEY
    export HOME="$REAL_HOME"
    seed_user_tool_dirs "$HOME" "${CLAWSEAT_PROJECT:-}"
    prepare_gemini_home "$HOME" "$workdir"
    cd "$workdir"
    echo "────────────────────────────────────────"
    echo " Gemini CLI · OAuth"
    echo " Session:    $session_name"
    echo " Directory:  $workdir"
    echo " HOME:       $HOME"
    echo "────────────────────────────────────────"
    exec gemini
  fi

  local secret_file="" runtime_dir
  if [[ "$auth_mode" != "custom" ]]; then
    secret_file="$REAL_HOME/.agent-runtime/secrets/gemini/primary.env"
    if [[ ! -f "$secret_file" ]]; then
      echo "error: missing Gemini secret file: $secret_file" >&2
      exit 1
    fi
  fi

  runtime_dir="$REAL_HOME/.agent-runtime/identities/gemini/api/${auth_mode}-${session_name}"
  mkdir -p \
    "$runtime_dir/home" \
    "$runtime_dir/xdg/config" \
    "$runtime_dir/xdg/data" \
    "$runtime_dir/xdg/cache" \
    "$runtime_dir/xdg/state"

  export HOME="$runtime_dir/home"
  export XDG_CONFIG_HOME="$runtime_dir/xdg/config"
  export XDG_DATA_HOME="$runtime_dir/xdg/data"
  export XDG_CACHE_HOME="$runtime_dir/xdg/cache"
  export XDG_STATE_HOME="$runtime_dir/xdg/state"
  seed_user_tool_dirs "$HOME" "${CLAWSEAT_PROJECT:-}"
  prepare_gemini_home "$HOME" "$workdir"

  if [[ "$auth_mode" == "custom" ]]; then
    load_custom_env "$CUSTOM_ENV_FILE"
    export GEMINI_API_KEY="${LAUNCHER_CUSTOM_API_KEY:-}"
    export GOOGLE_API_KEY="${LAUNCHER_CUSTOM_API_KEY:-}"
    export GOOGLE_GEMINI_BASE_URL="${LAUNCHER_CUSTOM_BASE_URL:-}"
  else
    set -a
    source "$secret_file"
    set +a
    export GOOGLE_API_KEY="${GOOGLE_API_KEY:-${GEMINI_API_KEY:-}}"
  fi

  cd "$workdir"
  echo "────────────────────────────────────────"
  echo " Gemini CLI · $(uppercase_ascii "$auth_mode") API"
  echo " Session:    $session_name"
  echo " Directory:  $workdir"
  echo " HOME:       $HOME"
  echo " XDG_CONFIG: $XDG_CONFIG_HOME"
  echo "────────────────────────────────────────"
  if [[ -n "${LAUNCHER_CUSTOM_MODEL:-}" ]]; then
    exec gemini -m "${LAUNCHER_CUSTOM_MODEL}"
  fi
  exec gemini
}

exec_agent_shell_command() {
  local -a cmd=(bash "$0" --tool "$TOOL_NAME" --session "$SESSION_NAME" --auth "$AUTH_MODE" --dir "$WORKDIR" --exec-agent)
  if [[ -n "$CUSTOM_ENV_FILE" ]]; then
    cmd+=(--custom-env-file "$CUSTOM_ENV_FILE")
  fi
  printf '%q ' "${cmd[@]}"
}

exec_inline_agent() {
  if [[ -n "$CUSTOM_ENV_FILE" ]]; then
    exec "$0" --tool "$TOOL_NAME" --session "$SESSION_NAME" --auth "$AUTH_MODE" --dir "$WORKDIR" --custom-env-file "$CUSTOM_ENV_FILE" --exec-agent
  fi
  exec "$0" --tool "$TOOL_NAME" --session "$SESSION_NAME" --auth "$AUTH_MODE" --dir "$WORKDIR" --exec-agent
}

run_selected_tool() {
  case "$1" in
    claude) run_claude_runtime "$2" "$3" "$4" ;;
    codex) run_codex_runtime "$2" "$3" "$4" ;;
    gemini) run_gemini_runtime "$2" "$3" "$4" ;;
    *) echo "error: unsupported tool: $1" >&2; exit 2 ;;
  esac
}

if [[ "${CLAWSEAT_AGENT_LAUNCHER_LIBRARY_ONLY:-}" == "1" ]]; then
  return 0 2>/dev/null || exit 0
fi

if [[ -z "$EXEC_MODE" ]]; then
  validate_top_level_inputs
  ensure_custom_env_file_for_auth

  if [[ "$DRY_RUN" == "1" ]]; then
    cat <<EOF
Unified launcher dry-run
  tool:     $TOOL_NAME
  auth:     $AUTH_MODE
  dir:      $WORKDIR
  session:  $SESSION_NAME
  custom:   $([[ -n "$CUSTOM_ENV_FILE" ]] && printf yes || printf no)
  headless: $HEADLESS
EOF
    cleanup_generated_custom_env_file
    exit 0
  fi

  if ! command -v tmux >/dev/null 2>&1; then
    echo "warn: tmux not found — falling back to inline $TOOL_NAME" >&2
    launcher_remember_recent_dir "$WORKDIR"
    exec_inline_agent
  fi

  if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "reusing existing tmux session '$SESSION_NAME'"
    tmux set-option -t "$SESSION_NAME" detach-on-destroy off
    cleanup_generated_custom_env_file
  else
    tmux new-session -d -s "$SESSION_NAME" -x 220 -y 60 \
      "$(exec_agent_shell_command)" \
      \; set-option -t "$SESSION_NAME" detach-on-destroy off
    echo "launched tmux session '$SESSION_NAME'"
  fi

  launcher_remember_recent_dir "$WORKDIR"

  # bash 3.2 on macOS has no ${VAR^} uppercase-first operator; use awk
  # (top-level scope here, so no `local` — that's a bash syntax error
  # outside a function in some shells).
  _tool_title="$(printf '%s' "$TOOL_NAME" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')"
  cat <<EOF

${_tool_title} session ready
  auth:     $AUTH_MODE
  dir:      $WORKDIR
  tmux:     $SESSION_NAME
  mode:     tmux-only deterministic launcher

Manual attach:
  tmux attach -t $SESSION_NAME

Kill session:
  tmux kill-session -t $SESSION_NAME

EOF
  exit 0
fi

validate_top_level_inputs
ensure_custom_env_file_for_auth

run_selected_tool "$TOOL_NAME" "$AUTH_MODE" "$WORKDIR" "$SESSION_NAME"
