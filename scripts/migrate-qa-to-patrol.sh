#!/usr/bin/env bash
set -euo pipefail

HOME_DIR="${CLAWSEAT_REAL_HOME:-${HOME}}"
PROJECTS=(install cartooner arena lotus-radar koder)
if [[ "$#" -gt 0 ]]; then
  PROJECTS=("$@")
fi

backup_file() {
  local path="$1"
  [[ -f "$path" ]] || return 0
  cp "$path" "${path}.bak.$(date +%Y%m%d-%H%M%S)"
}

migrate_project_toml() {
  local project="$1" path="$HOME_DIR/.agents/projects/$project/project.toml"
  [[ -f "$path" ]] || return 0
  backup_file "$path"
  python3 - "$path" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = re.sub(r'"qa"', '"patrol"', text)
text = re.sub(r"^\[seat_overrides\.qa\]\s*$", "[seat_overrides.patrol]", text, flags=re.MULTILINE)
text = re.sub(r"(?m)^qa\s*=", "patrol =", text)
path.write_text(text, encoding="utf-8")
PY
}

migrate_dynamic_profile() {
  local project="$1" path="$HOME_DIR/.agents/profiles/${project}-profile-dynamic.toml"
  [[ -f "$path" ]] || return 0
  backup_file "$path"
  python3 - "$path" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = re.sub(r'"qa"', '"patrol"', text)
text = re.sub(r"^\[seat_overrides\.qa\]\s*$", "[seat_overrides.patrol]", text, flags=re.MULTILINE)
text = re.sub(r"(?m)^qa\s*=", "patrol =", text)
if "[seat_overrides.patrol]" not in text:
    block = '\n\n[seat_overrides.patrol]\ntool = "claude"\nauth_mode = "api"\nprovider = "minimax"\nmodel = "MiniMax-M2.7-highspeed"\n'
    text = text.rstrip() + block
path.write_text(text, encoding="utf-8")
PY
}

migrate_secret_files() {
  local provider_dir old_path new_path
  for provider_dir in "$HOME_DIR"/.agents/secrets/*/*; do
    [[ -d "$provider_dir" ]] || continue
    old_path="$provider_dir/qa.env"
    new_path="$provider_dir/patrol.env"
    [[ -f "$old_path" ]] || continue
    if [[ -e "$new_path" ]]; then
      backup_file "$old_path"
      rm -f "$old_path"
    else
      mv "$old_path" "$new_path"
      chmod 600 "$new_path" || true
    fi
  done
}

for project in "${PROJECTS[@]}"; do
  migrate_project_toml "$project"
  migrate_dynamic_profile "$project"
  if [[ -x "$HOME_DIR/.agents/bin/agent-admin" ]]; then
    "$HOME_DIR/.agents/bin/agent-admin" session rename --project "$project" --from qa --to patrol || true
  fi
done
migrate_secret_files
