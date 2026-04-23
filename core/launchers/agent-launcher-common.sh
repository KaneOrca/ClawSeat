#!/usr/bin/env bash

set -euo pipefail

launcher_state_store_path() {
  local launcher_home default_store
  launcher_home="${REAL_HOME:-$HOME}"
  if [[ -n "${LAUNCHER_STATE_STORE:-}" ]]; then
    printf '%s\n' "$LAUNCHER_STATE_STORE"
  elif [[ -f "$launcher_home/Desktop/.agent-launcher-state.json" ]]; then
    printf '%s\n' "$launcher_home/Desktop/.agent-launcher-state.json"
  else
    default_store="$launcher_home/.config/clawseat/launcher-state.json"
    mkdir -p "$(dirname "$default_store")"
    printf '%s\n' "$default_store"
  fi
}

launcher_remember_recent_dir() {
  local path="$1"
  local store
  store="$(launcher_state_store_path)"
  python3 - "$store" "$path" <<'PY'
import json
import os
import sys

store_path, raw_path = sys.argv[1:3]
path = os.path.realpath(os.path.expanduser(raw_path))
if not os.path.isdir(path):
    raise SystemExit(0)

data = {}
if os.path.exists(store_path):
    try:
        with open(store_path, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
            if isinstance(loaded, dict):
                data = loaded
    except Exception:
        data = {}

recent = [
    entry
    for entry in data.get("recent_dirs", [])
    if isinstance(entry, str) and entry != path and os.path.isdir(entry)
]
recent.insert(0, path)
data["recent_dirs"] = recent[:12]

with open(store_path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, ensure_ascii=False, indent=2)
PY
}

launcher_resolve_directory_path() {
  local raw_path="$1"
  python3 - "$raw_path" <<'PY'
from pathlib import Path
import sys

raw = sys.argv[1].strip()
if not raw:
    raise SystemExit(1)

path = Path(raw).expanduser()
if not path.is_dir():
    raise SystemExit(1)

print(path.resolve())
PY
}

launcher_slugify() {
  local raw="${1:-session}"
  local slug
  slug="$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]' | tr -cs '[:alnum:]' '-')"
  slug="${slug#-}"
  slug="${slug%-}"
  if [[ -z "$slug" ]]; then
    slug="session"
  fi
  printf '%s\n' "$slug"
}
