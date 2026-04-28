#!/usr/bin/env bash
# shellcheck shell=bash
# Loaded by scripts/install.sh. Resolve this file with BASH_SOURCE so
# callers may source install.sh from any current working directory.
_CLAWSEAT_INSTALL_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

prompt_template_for_choice() {
  case "${1:-1}" in
    ""|1) printf '%s\n' "clawseat-creative" ;;
    2) printf '%s\n' "clawseat-engineering" ;;
    3) printf '%s\n' "clawseat-solo" ;;
    *) return 1 ;;
  esac
}

prompt_placeholder_for_template() {
  case "$1" in
    clawseat-creative)    printf '%s\n' "e.g. cartooner, artistic-tool" ;;
    clawseat-engineering) printf '%s\n' "e.g. coding-project, webapp" ;;
    clawseat-solo)        printf '%s\n' "e.g. minimal-solo, creative-side-project" ;;
    *)                    printf '%s\n' "e.g. myproject, experiment-01" ;;
  esac
}

prompt_kind_first_flow() {
  # Skip when either flag was explicitly provided.
  [[ "$_PROJECT_EXPLICIT" == "0" && "$_TEMPLATE_EXPLICIT" == "0" ]] || return 0
  if [[ ! -t 0 || ! -t 1 ]]; then
    die 2 NON_TTY_NO_TEMPLATE \
      "non-TTY environment detected; use --template <name>. Run: bash scripts/install.sh --help"
  fi

  printf '\nClawSeat — 新项目配置 / New project setup\n' >&2
  printf '\n选择项目类型 / Choose project mode:\n' >&2
  printf '  1) 创作项目 (5 seat: memory + planner + builder + patrol + designer)  [default]\n' >&2
  printf '  2) 工程项目 (6 seat: + reviewer 独立审查)\n' >&2
  printf '  3) 创作 minimal (3 seat: memory + builder + designer, all OAuth)\n' >&2

  local _kind=""
  while true; do
    printf '选择 [1-3, Enter=1]: ' >&2
    read -r _kind < /dev/tty
    if CLAWSEAT_TEMPLATE_NAME="$(prompt_template_for_choice "$_kind")"; then
      break
    fi
    printf '请输入 1、2 或 3 (回车 = 1 创作项目)\n' >&2
  done

  local _placeholder
  _placeholder="$(prompt_placeholder_for_template "$CLAWSEAT_TEMPLATE_NAME")"

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
  # PRIMARY_SEAT_ID is the seat the user dialogs with. Current canonical
  # templates are v2 memory-primary; PENDING_SEATS is everyone else (workers).
  local template_file="$REPO_ROOT/templates/${CLAWSEAT_TEMPLATE_NAME}.toml"
  if [[ ! -f "$template_file" ]]; then
    PRIMARY_SEAT_ID="memory"
    return 0
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
  PRIMARY_SEAT_ID="${primary:-memory}"

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

memory_primary_uses_codex() {
  [[ "$PRIMARY_SEAT_ID" == "memory" && "$(primary_effective_tool)" == "codex" ]]
}

memory_primary_uses_gemini() {
  [[ "$PRIMARY_SEAT_ID" == "memory" && "$(primary_effective_tool)" == "gemini" ]]
}

memory_primary_skips_claude_provider() {
  [[ "$PRIMARY_SEAT_ID" == "memory" && "$(primary_effective_tool)" != "claude" ]]
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

primary_effective_tool() {
  local template_tool template_auth template_provider template_model
  read -r template_tool template_auth template_provider template_model < <(
    template_seat_config "$PRIMARY_SEAT_ID" 2>/dev/null || printf 'claude oauth anthropic \n'
  )
  if [[ "$PRIMARY_SEAT_ID" == "memory" && "$MEMORY_TOOL_EXPLICIT" == "1" ]]; then
    printf '%s\n' "$MEMORY_TOOL"
  else
    printf '%s\n' "${template_tool:-claude}"
  fi
}

template_seat_config() {
  local seat="$1"
  local template_file="$REPO_ROOT/templates/${CLAWSEAT_TEMPLATE_NAME}.toml"
  [[ -f "$template_file" ]] || return 1
  "$PYTHON_BIN" - "$template_file" "$seat" <<'PY'
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
        raise SystemExit(0)
raise SystemExit(1)
PY
}

seat_tmux_name() {
  local seat="$1" tool="$2"
  case "$seat" in
    *-"$tool") printf '%s\n' "$seat" ;;
    *) printf '%s-%s\n' "$seat" "$tool" ;;
  esac
}

primary_tmux_name() {
  local primary_tool="claude"
  [[ "$PRIMARY_SEAT_ID" == "memory" ]] && primary_tool="$(primary_effective_tool)"
  seat_tmux_name "${PROJECT}-${PRIMARY_SEAT_ID}" "$primary_tool"
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
id = "memory"
display_name = "Memory"
role = "memory"
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
  local seat_auth_mode seat_provider seat_model seat primary_tool primary_auth primary_provider primary_model primary_session_name
  local primary_template_tool primary_template_auth primary_template_provider primary_template_model
  seat_auth_mode="$(seat_auth_mode_for_provider_mode)"
  seat_provider="$(seat_provider_for_provider_mode)"
  seat_model="$(seat_model_for_provider_mode || true)"
  read -r primary_template_tool primary_template_auth primary_template_provider primary_template_model < <(
    template_seat_config "$PRIMARY_SEAT_ID" 2>/dev/null || printf 'claude oauth anthropic \n'
  )
  primary_tool="$primary_template_tool"
  primary_auth="$primary_template_auth"
  primary_provider="$primary_template_provider"
  primary_model="$primary_template_model"
  if [[ "$PRIMARY_SEAT_ID" == "memory" && "$MEMORY_TOOL_EXPLICIT" == "1" ]]; then
    primary_tool="$MEMORY_TOOL"
    case "$MEMORY_TOOL" in
      claude)
        primary_auth="$seat_auth_mode"
        primary_provider="$seat_provider"
        primary_model="$seat_model"
        ;;
      codex)
        primary_auth="oauth"
        primary_provider="openai"
        primary_model="$(memory_effective_model)"
        ;;
      gemini)
        primary_auth="oauth"
        primary_provider="google"
        primary_model="$(memory_effective_model)"
        ;;
    esac
  elif [[ "$primary_tool" == "claude" ]]; then
    primary_auth="$seat_auth_mode"
    primary_provider="$seat_provider"
    primary_model="${seat_model:-$primary_model}"
  fi
  primary_session_name="$(seat_tmux_name "$PROJECT-$PRIMARY_SEAT_ID" "$primary_tool")"

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
session_name = "$primary_session_name"
tool = "$primary_tool"
auth_mode = "$primary_auth"
provider = "$primary_provider"
EOF
  if [[ -n "$primary_model" ]]; then
    printf 'model = "%s"\n' "$primary_model" >>"$PROJECT_LOCAL_TOML"
  fi

  for seat in "${PENDING_SEATS[@]}"; do
    local _seat_tool _seat_auth _seat_provider _seat_template_model
    read -r _seat_tool _seat_auth _seat_provider _seat_template_model < <(
      template_seat_config "$seat" 2>/dev/null || true
    )
    # Fallback to memory provider values only if template read failed.
    _seat_tool="${_seat_tool:-claude}"
    _seat_auth="${_seat_auth:-$seat_auth_mode}"
    _seat_provider="${_seat_provider:-$seat_provider}"
    if [[ -n "$FORCE_ALL_API_PROVIDER" && "$_seat_auth" == "api" ]]; then
      _seat_provider="$(seat_provider_for_explicit_provider "$FORCE_ALL_API_PROVIDER")"
      _seat_template_model="$(seat_model_for_explicit_provider "$FORCE_ALL_API_PROVIDER")"
    fi
    cat >>"$PROJECT_LOCAL_TOML" <<EOF

[[overrides]]
id = "$seat"
tool = "$_seat_tool"
auth_mode = "$_seat_auth"
provider = "$_seat_provider"
EOF
    # Write model for claude seats only. Template-specified models stay scoped
    # to their seats; --provider is memory-only, and --all-api-provider is the
    # explicit global override for API seats.
    if [[ "$_seat_tool" == "claude" ]]; then
      local _effective_model="${_seat_template_model:-}"
      if [[ -n "$_effective_model" ]]; then
        printf 'model = "%s"\n' "$_effective_model" >>"$PROJECT_LOCAL_TOML"
      fi
    fi
  done
  chmod 600 "$PROJECT_LOCAL_TOML" || die 31 PROJECT_LOCAL_CHMOD_FAILED "unable to chmod $PROJECT_LOCAL_TOML"
}

project_profile_needs_template_migration() {
  [[ -f "$PROJECT_RECORD_PATH" ]] || return 1
  local template_file="$REPO_ROOT/templates/${CLAWSEAT_TEMPLATE_NAME}.toml"
  [[ -f "$template_file" ]] || return 1
  "$PYTHON_BIN" - "$PROJECT_RECORD_PATH" "$template_file" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore

path = Path(sys.argv[1])
template_path = Path(sys.argv[2])
data = tomllib.loads(path.read_text(encoding="utf-8"))
template = tomllib.loads(template_path.read_text(encoding="utf-8"))
raw_engineers = [str(item) for item in data.get("engineers", [])]
raw_monitor_engineers = [str(item) for item in data.get("monitor_engineers", [])]
raw_overrides = data.get("seat_overrides") or {}
if "qa" in raw_engineers or "qa" in raw_monitor_engineers or "qa" in raw_overrides:
    raise SystemExit(0)
def normalize_seat(value: object) -> str:
    text = str(value)
    return "patrol" if text == "qa" else text

engineers = [normalize_seat(item) for item in data.get("engineers", [])]
monitor_engineers = [normalize_seat(item) for item in data.get("monitor_engineers", [])]
overrides = {normalize_seat(key): value for key, value in (data.get("seat_overrides") or {}).items()}
needs = False
for spec in template.get("engineers", []):
    seat = str(spec.get("id", ""))
    if not seat:
        continue
    if seat not in engineers or seat not in monitor_engineers:
        needs = True
        break
    current = overrides.get(seat) or {}
    for key in ("tool", "auth_mode", "provider"):
        if key not in current and key in spec:
            needs = True
            break
    if needs:
        break
    if spec.get("model") and "model" not in current:
        needs = True
        break
raise SystemExit(0 if needs else 1)
PY
}

migrate_project_profile_to_v2() {
  note "Step 5.6: migrate project profile from template defaults"
  if [[ ! -f "$PROJECT_RECORD_PATH" ]]; then
    warn "project profile migration skipped; missing $PROJECT_RECORD_PATH"
    return 0
  fi
  if ! project_profile_needs_template_migration; then
    note "[install] project.toml already contains template-defined seats and override defaults"
    return 0
  fi

  local answer="${CLAWSEAT_PATROL_PROFILE_MIGRATE:-${CLAWSEAT_QA_PROFILE_MIGRATE:-}}"
  if [[ -z "$answer" ]]; then
    if [[ -t 0 && -t 1 ]]; then
      printf '[install] 检测到 project.toml 缺 patrol engineer，是否升级? (Y/n) '
      read -r answer
    else
      answer="y"
    fi
  fi
  if [[ "$answer" =~ ^[Nn]$ ]]; then
    warn "project.toml patrol engineer migration skipped by operator"
    return 0
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] migrate %q from template %q; preserve existing seat_overrides\n' "$PROJECT_RECORD_PATH" "$CLAWSEAT_TEMPLATE_NAME"
    return 0
  fi

  local backup_path="${PROJECT_RECORD_PATH}.bak.$(date +%Y%m%d-%H%M%S)"
  cp "$PROJECT_RECORD_PATH" "$backup_path" \
    || die 31 PROJECT_PROFILE_BACKUP_FAILED "unable to backup $PROJECT_RECORD_PATH"
  "$PYTHON_BIN" - "$PROJECT_RECORD_PATH" "$REPO_ROOT/templates/${CLAWSEAT_TEMPLATE_NAME}.toml" <<'PY' \
    || die 31 PROJECT_PROFILE_MIGRATE_FAILED "unable to migrate $PROJECT_RECORD_PATH"
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore

path = Path(sys.argv[1])
template_path = Path(sys.argv[2])
text = path.read_text(encoding="utf-8")
text = re.sub(r"^\[seat_overrides\.qa\]\s*$", "[seat_overrides.patrol]", text, flags=re.MULTILINE)
data = tomllib.loads(text)
template = tomllib.loads(template_path.read_text(encoding="utf-8"))
template_defaults = template.get("defaults") or {}
template_engineers = [
    spec for spec in template.get("engineers", [])
    if str(spec.get("id", "")).strip()
]

def unique_extend(values: object, items: list[str]) -> list[str]:
    out = []
    if isinstance(values, list):
        for value in values:
            item = "patrol" if str(value) == "qa" else str(value)
            if item not in out:
                out.append(item)
    for item in items:
        if item not in out:
            out.append(item)
    return out

def q_array(values: list[str]) -> str:
    return "[" + ", ".join(f'"{v}"' for v in values) + "]"

template_ids = [str(spec["id"]) for spec in template_engineers]
engineers = unique_extend(data.get("engineers", []), template_ids)
monitor_engineers = unique_extend(data.get("monitor_engineers", []), template_ids)
monitor_max_panes = max(int(template_defaults.get("monitor_max_panes", 0) or 0), int(data.get("monitor_max_panes", 0) or 0))

def set_or_insert(src: str, key: str, rendered: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}\s*=.*$", re.MULTILINE)
    line = f"{key} = {rendered}"
    if pattern.search(src):
        return pattern.sub(line, src, count=1)
    marker = re.search(r"^\[seat_overrides\.", src, re.MULTILINE)
    if marker:
        return src[: marker.start()] + line + "\n" + src[marker.start():]
    return src.rstrip() + "\n" + line + "\n"

text = set_or_insert(text, "engineers", q_array(engineers))
text = set_or_insert(text, "monitor_engineers", q_array(monitor_engineers))
text = set_or_insert(text, "monitor_max_panes", str(monitor_max_panes))

def upsert_table_key(src: str, table: str, key: str, value: str, *, preserve_existing: bool = True) -> str:
    header = f"[{table}]"
    header_match = re.search(rf"^\[{re.escape(table)}\]\s*$", src, re.MULTILINE)
    line = f"{key} = {value}"
    if not header_match:
        return src.rstrip() + f"\n\n{header}\n{line}\n"
    block_start = header_match.end()
    after = src[block_start:]
    next_header = re.search(r"^\[", after, re.MULTILINE)
    block_end = block_start + (next_header.start() if next_header else len(after))
    block = src[block_start:block_end]
    key_match = re.search(rf"^{re.escape(key)}\s*=.*$", block, re.MULTILINE)
    if key_match:
        if preserve_existing:
            return src
        block = block[: key_match.start()] + line + block[key_match.end():]
    else:
        block = block.rstrip("\n") + "\n" + line + "\n"
    return src[:block_start] + block + src[block_end:]

def render_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return q_array([str(item) for item in value])
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'

for spec in template_engineers:
    seat = str(spec["id"])
    for key in ("tool", "auth_mode", "provider", "model", "base_url"):
        value = spec.get(key)
        if value in (None, ""):
            continue
        text = upsert_table_key(
            text,
            f"seat_overrides.{seat}",
            key,
            render_value(value),
            preserve_existing=True,
        )
path.write_text(text, encoding="utf-8")
PY
  note "[install] project.toml template migration complete (backup: $backup_path)"
}

ensure_qa_engineer_record() {
  local patrol_session="$HOME/.agents/sessions/$PROJECT/patrol/session.toml"
  local legacy_qa_session="$HOME/.agents/sessions/$PROJECT/qa/session.toml"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] %q %q engineer create patrol %q --no-monitor\n' \
      "$PYTHON_BIN" "$AGENT_ADMIN_SCRIPT" "$PROJECT"
    return 0
  fi
  if [[ -f "$patrol_session" || -f "$legacy_qa_session" ]]; then
    note "[install] patrol engineer session already registered"
    return 0
  fi
  if [[ ! -f "$AGENT_ADMIN_SCRIPT" ]]; then
    warn "patrol engineer create skipped; missing agent_admin helper: $AGENT_ADMIN_SCRIPT"
    return 0
  fi
  "$PYTHON_BIN" "$AGENT_ADMIN_SCRIPT" engineer create patrol "$PROJECT" --no-monitor \
    || die 31 QA_ENGINEER_CREATE_FAILED "unable to create patrol engineer session for $PROJECT"
}

template_has_seat() {
  local target="$1" seat
  [[ "$PRIMARY_SEAT_ID" == "$target" ]] && return 0
  for seat in "${PENDING_SEATS[@]}"; do
    [[ "$seat" == "$target" ]] && return 0
  done
  return 1
}

install_qa_bootstrap() {
  if ! template_has_seat "patrol"; then
    note "Step 7.6: patrol bootstrap skipped (template has no patrol seat)"
    return 0
  fi
  note "Step 7.6: install patrol hook + patrol cron"
  local patrol_workspace="$HOME/.agents/workspaces/$PROJECT/patrol"
  ensure_qa_engineer_record
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] mkdir -p %q\n' "$patrol_workspace"
    printf '[dry-run] %q %q --workspace %q\n' "$PYTHON_BIN" "$PATROL_HOOK_INSTALLER" "$patrol_workspace"
  elif [[ ! -f "$PATROL_HOOK_INSTALLER" ]]; then
    warn "patrol hook install skipped; missing helper: $PATROL_HOOK_INSTALLER"
  else
    mkdir -p "$patrol_workspace"
    "$PYTHON_BIN" "$PATROL_HOOK_INSTALLER" --workspace "$patrol_workspace"
  fi
  prompt_qa_patrol_cron_optin
}

bootstrap_project_profile() {
  note "Step 5.5: bootstrap project engineer profiles (no tmux start)"
  [[ -f "$WAIT_FOR_SEAT_SCRIPT" || "$DRY_RUN" == "1" ]] || die 31 WAIT_SCRIPT_MISSING "missing wait-for-seat script: $WAIT_FOR_SEAT_SCRIPT"
  [[ -f "$AGENT_ADMIN_SCRIPT" || "$DRY_RUN" == "1" ]] || die 31 AGENT_ADMIN_MISSING "missing agent_admin script: $AGENT_ADMIN_SCRIPT"
  # Canonical templates live in templates/*.toml and must not be overwritten
  # by install-time generated template files.
  write_project_local_toml

  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] (cd %q && %q %q project bootstrap --template %q --local %q)\n' \
      "$AGENTS_TEMPLATES_ROOT" "$PYTHON_BIN" "$AGENT_ADMIN_SCRIPT" "$CLAWSEAT_TEMPLATE_NAME" "$PROJECT_LOCAL_TOML"
    ensure_deepseek_secret_template
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
  ensure_deepseek_secret_template
  seed_bootstrap_secrets
}

register_project_registry() {
  local primary_tool="claude" primary_session_name
  [[ "$PRIMARY_SEAT_ID" == "memory" ]] && primary_tool="$(primary_effective_tool)"
  primary_session_name="$(primary_tmux_name)"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] %q %q register %q --primary-seat %q --primary-seat-tool %q --tmux-name %q --template-name %q --repo-path %q\n' \
      "$PYTHON_BIN" "$PROJECTS_REGISTRY_SCRIPT" "$PROJECT" "$PRIMARY_SEAT_ID" "$primary_tool" "$primary_session_name" "$CLAWSEAT_TEMPLATE_NAME" "$PROJECT_REPO_ROOT"
    return 0
  fi
  if [[ ! -f "$PROJECTS_REGISTRY_SCRIPT" ]]; then
    warn "projects.json register skipped; missing $PROJECTS_REGISTRY_SCRIPT"
    return 0
  fi
  "$PYTHON_BIN" "$PROJECTS_REGISTRY_SCRIPT" register "$PROJECT" \
    --primary-seat "$PRIMARY_SEAT_ID" \
    --primary-seat-tool "$primary_tool" \
    --tmux-name "$primary_session_name" \
    --template-name "$CLAWSEAT_TEMPLATE_NAME" \
    --repo-path "$PROJECT_REPO_ROOT" >/dev/null \
    || warn "projects.json register failed (non-fatal); see ~/.clawseat/projects.json"
}

uninstall_project_registry_entry() {
  local project="$1"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] %q %q unregister %q\n' "$PYTHON_BIN" "$PROJECTS_REGISTRY_SCRIPT" "$project"
    return 0
  fi
  [[ -f "$PROJECTS_REGISTRY_SCRIPT" ]] || die 31 PROJECTS_REGISTRY_MISSING "missing projects registry helper: $PROJECTS_REGISTRY_SCRIPT"
  "$PYTHON_BIN" "$PROJECTS_REGISTRY_SCRIPT" unregister "$project" || true
}

touch_project_registry() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] %q %q touch %q\n' "$PYTHON_BIN" "$PROJECTS_REGISTRY_SCRIPT" "$PROJECT"
    return 0
  fi
  [[ -f "$PROJECTS_REGISTRY_SCRIPT" ]] || return 0
  "$PYTHON_BIN" "$PROJECTS_REGISTRY_SCRIPT" touch "$PROJECT" >/dev/null 2>&1 || true
}

install_clawseat_cli_symlink() {
  local link="/usr/local/bin/clawseat"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] ln -sfn %q %q\n' "$CLAWSEAT_CLI_SCRIPT" "$link"
    return 0
  fi
  [[ -f "$CLAWSEAT_CLI_SCRIPT" ]] || { warn "clawseat CLI skipped; missing $CLAWSEAT_CLI_SCRIPT"; return 0; }
  if [[ -w "$(dirname "$link")" || ( ! -e "$link" && -w "$(dirname "$link")" ) ]]; then
    ln -sfn "$CLAWSEAT_CLI_SCRIPT" "$link" || warn "unable to install $link"
  else
    warn "clawseat CLI symlink skipped; $(dirname "$link") not writable"
  fi
}

render_brief() {
  note "Step 4: render memory bootstrap brief"
  [[ -f "$MEMORY_BRIEF_TEMPLATE" || "$DRY_RUN" == "1" ]] || die 30 TEMPLATE_MISSING "missing template: $MEMORY_BRIEF_TEMPLATE"
  local pending_seats_human primary_session_name
  printf -v pending_seats_human '%s, ' "${PENDING_SEATS[@]}"
  pending_seats_human="${pending_seats_human%, }"
  primary_session_name="$(primary_tmux_name)"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] render %s -> %s\n' "$MEMORY_BRIEF_TEMPLATE" "$BRIEF_PATH"
  else
    "$PYTHON_BIN" - "$MEMORY_BRIEF_TEMPLATE" "$BRIEF_PATH" "$PROJECT" "$REPO_ROOT" "$REAL_HOME" "$CLAWSEAT_TEMPLATE_NAME" "$PRIMARY_SEAT_ID" "$pending_seats_human" "$primary_session_name" <<'PY'
from pathlib import Path
from string import Template
import sys
tmpl = Template(Path(sys.argv[1]).read_text(encoding="utf-8")).safe_substitute(
    PROJECT_NAME=sys.argv[3],
    CLAWSEAT_ROOT=sys.argv[4],
    AGENT_HOME=sys.argv[5],
    PRIMARY_SEAT_ID=sys.argv[7],
    PENDING_SEATS_HUMAN=sys.argv[8],
    PRIMARY_SESSION_NAME=sys.argv[9],
)
tmpl = tmpl.replace("{CLAWSEAT_TEMPLATE_NAME}", sys.argv[6] if len(sys.argv) > 6 else "clawseat-creative")
out = Path(sys.argv[2]); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(tmpl, encoding="utf-8")
PY
    chmod 600 "$BRIEF_PATH" || die 30 BRIEF_CHMOD_FAILED "unable to chmod $BRIEF_PATH"
  fi
}

write_operator_guide() {
  local primary_session_name
  primary_session_name="$(primary_tmux_name)"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] write %s\n' "$GUIDE_FILE"
    return 0
  fi

  # The rendered guide uses `${primary_session_name}` so v2 memory-primary
  # projects and imported legacy templates both stay correct.
  mkdir -p "$(dirname "$GUIDE_FILE")" || die 30 GUIDE_DIR_FAILED "unable to create $(dirname "$GUIDE_FILE")"
  cat >"$GUIDE_FILE" <<EOF
# Operator — ClawSeat $PROJECT 启动指引

install.sh 已完成。现在按 6 步触发 Phase-A。v2 项目使用项目 workers 窗口 + shared memories 窗口；legacy template 可能仍使用单窗口布局。

1. 切到 primary seat：\`${primary_session_name}\`。v2 项目通常在 \`clawseat-memories\` 窗口的项目 tab；legacy template 可能在项目窗口中。

2. **先确认 ${primary_session_name} pane 已就绪** — install.sh 不再自动发送 Phase-A kickoff；kickoff 已写入文件，等待 operator 主动触发：

   \`\`\`bash
   tmux capture-pane -t '${primary_session_name}' -p | tail -15
   \`\`\`

   如果看到 Bypass Permissions / Trust folder / Login / Accessing workspace / Quick safety check 等确认屏，先按屏幕提示处理完，再继续。

3. Phase-A kickoff prompt 文件：

   \`\`\`bash
   cat ${KICKOFF_FILE}
   \`\`\`

4. 选择一种触发方式（A/B/C 三选一）：

   **A) 让当前 install-memory / 安装 agent 通过 transport 发送 kickoff：**

   \`\`\`bash
   bash ${SEND_AND_VERIFY_SCRIPT} --project ${PROJECT} ${primary_session_name} "\$(cat "${KICKOFF_FILE}")"
   \`\`\`

   **B) 手动粘贴：**

   \`\`\`bash
   cat ${KICKOFF_FILE}
   \`\`\`

   打开 ${primary_session_name} pane，把输出复制到 primary seat prompt，按 Enter。

   kickoff 内容要求：
   - Phase-A 不让 memory 做同步调研。
   - B2.5 / B5 都按 brief 由 ${PRIMARY_SEAT_ID} seat 自己 Read openclaw / binding 文件。
   - memory 在 Phase-A 唯一位置是 B7 后接收 phase-a-decisions learnings。
   - 然后按 B3 / B3.5 / B5 / B6 / B7 顺序推进；用 agent_admin.py session start-engineer 逐个拉起 seat（不要 fan-out，一个一个来）。

   **C) 让 install-memory 接手：**

   在 install-memory chat 里说：\`dispatch ${PROJECT} kickoff\`。

5. **验证 Phase-A 已启动** — 触发后立刻 re-capture 确认：

   \`\`\`bash
   tmux capture-pane -t '${primary_session_name}' -p | tail -10
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

1. \`tmux kill-session -t ${primary_session_name}\`
2. 重新启动 primary seat（建议重跑 \`scripts/install.sh --project ${PROJECT} --reinstall\`，或按同样的 \`agent-launcher.sh\` 参数重起）
3. 让 ${PRIMARY_SEAT_ID} seat 重新读取 \`\$CLAWSEAT_MEMORY_BRIEF\`

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
  local primary_session_name
  primary_session_name="$(primary_tmux_name)"
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
  printf '    ✔ Install complete. %s pane is ready or waiting for login/trust confirmation.\n' "$primary_session_name"
  printf '    Phase-A kickoff prompt was saved here:\n'
  printf '       %s\n' "$KICKOFF_FILE"
  printf '\n'
  printf '    Choose one to start Phase-A / 三选一启动 Phase-A:\n'
  printf '\n'
  printf '    A) Existing install-memory / current install agent dispatches kickoff:\n'
  printf '       bash %q --project %q %q "$(cat %q)"\n' \
    "$SEND_AND_VERIFY_SCRIPT" "$PROJECT" "$primary_session_name" "$KICKOFF_FILE"
  printf '\n'
  printf '    B) Manual paste / 手动粘贴:\n'
  printf '       cat %q\n' "$KICKOFF_FILE"
  printf '       Then paste the output into the %s primary seat prompt and press Enter.\n' "$primary_session_name"
  printf '\n'
  printf '    C) Ask install-memory in chat / 在 install-memory chat 里说:\n'
  printf '       dispatch %s kickoff\n' "$PROJECT"
  printf '\n'
  printf '    After A/B/C, verify Phase-A is running / 触发后确认:\n'
  printf '       tmux capture-pane -t %q -p | tail -10\n' "$primary_session_name"
  printf '       Expected: B0 / "已读取 brief" / env_scan activity.\n'
  printf '\n'
  printf '    Operator guide / 操作员指引:\n'
  printf '       cat %s\n' "$GUIDE_FILE"
  printf '    Registry cleanup / 注册表移除:\n'
  printf '       python3 %q unregister %q\n' "$PROJECTS_REGISTRY_SCRIPT" "$PROJECT"
  printf '\n'
  printf -- '────────────────────────────────────────────────────────────────\n'
}
