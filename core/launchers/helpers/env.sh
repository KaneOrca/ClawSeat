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
