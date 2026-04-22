#!/usr/bin/env bash
# Unified launcher for Claude Code, Codex, and Gemini CLI with iTerm + tmux.
#
# Merged into clawseat from ~/Desktop/agent-launcher.command.
# All intra-launcher paths are now self-relative so this file can live in
# any directory. User-specific defaults (preset store, workspace
# bookmarks) read from env vars with desktop-compat defaults for back-compat.

set -euo pipefail

REAL_HOME="$HOME"
LAUNCHER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HELPER="$LAUNCHER_DIR/agent-launcher-common.sh"
DISCOVER_HELPER="$LAUNCHER_DIR/agent-launcher-discover.py"
# Export so common.sh / discover can locate the picker without hard-coding.
export AGENT_LAUNCHER_DIR="$LAUNCHER_DIR"
# User preset storage — default to XDG config, fall back to legacy desktop path
# if it exists (seamless upgrade for users migrating from the desktop-only era).
if [[ -n "${AGENT_LAUNCHER_CUSTOM_PRESET_STORE:-}" ]]; then
  CUSTOM_PRESET_STORE="$AGENT_LAUNCHER_CUSTOM_PRESET_STORE"
elif [[ -f "$REAL_HOME/Desktop/.agent-launcher-custom-presets.json" ]]; then
  CUSTOM_PRESET_STORE="$REAL_HOME/Desktop/.agent-launcher-custom-presets.json"
else
  CUSTOM_PRESET_STORE="$REAL_HOME/.config/clawseat/launcher-custom-presets.json"
  mkdir -p "$(dirname "$CUSTOM_PRESET_STORE")"
fi

if [[ ! -f "$HELPER" ]]; then
  echo "error: missing helper script: $HELPER" >&2
  exit 1
fi

# shellcheck source=./agent-launcher-common.sh
source "$HELPER"

TOOL_NAME=""
SESSION_NAME=""
AUTH_MODE=""
WORKDIR=""
EXEC_MODE=""
CUSTOM_ENV_FILE=""
HEADLESS="0"
DRY_RUN="0"
CLONE_FROM=""
SKIP_ANCESTOR_PREFLIGHT="0"
PROMPT_AUTH_TOOL=""        # set by --prompt-auth <tool>; triggers early dispatch
CHECK_SECRETS_TOOL=""      # set by --check-secrets <tool> (needs --auth too)

print_help() {
  cat <<'EOF'
Usage: agent-launcher.command [options]

Options:
  --tool <claude|codex|gemini>   Agent CLI to launch
  --auth <mode>                  Authentication mode for the selected tool
  --dir <path>                   Startup directory
  --session <name>               tmux session name
  --custom-env-file <path>       Internal one-shot custom API env file
  --headless                     Do not open iTerm/Terminal; manage tmux only
  --dry-run                      Print resolved launch config and exit
  --exec-agent                   Internal flag used inside tmux
  --clone-from <project>         When bootstrapping a new project via an
                                 ancestor session, clone profile + seats
                                 from the named existing project (wizard
                                 only asks for the *new* project's chat_id)
  --skip-ancestor-preflight      Skip the ancestor-session auto-wizard hook
                                 (useful for smoke tests / recovery restarts)
  -h, --help                     Show this help
EOF
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
    --clone-from) CLONE_FROM="$2"; shift 2 ;;
    --skip-ancestor-preflight) SKIP_ANCESTOR_PREFLIGHT="1"; shift ;;
    # Sub-command for ClawSeat install helpers: pop the AppleScript auth
    # picker for <tool> and print the user's chosen auth value to stdout.
    # Exits 0 on selection, 1 on cancel, 2 on bad tool name.
    --prompt-auth) PROMPT_AUTH_TOOL="$2"; shift 2 ;;
    # Preflight hook: agent-launcher.sh --check-secrets <tool> --auth <mode>
    # prints one JSON line saying whether the auth's secret file/key is ready.
    --check-secrets) CHECK_SECRETS_TOOL="$2"; shift 2 ;;
    --help|-h) print_help; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

prompt_tool_name() {
  local choice
  choice="$(launcher_choose_from_list \
    "选择要启动的 AI CLI" \
    "Claude Code" \
    "Claude Code" \
    "Codex" \
    "Gemini CLI")"

  case "$choice" in
    "__CANCEL__") return 1 ;;
    "Claude Code") printf '%s\n' "claude" ;;
    "Codex") printf '%s\n' "codex" ;;
    "Gemini CLI") printf '%s\n' "gemini" ;;
    *) return 1 ;;
  esac
}

prompt_auth_mode() {
  case "$1" in
    claude)
      local choice=""
      choice="$(launcher_choose_from_list \
        "选择 Claude Code 认证方式" \
        "OAuth token (setup-token, recommended)" \
        "OAuth token (setup-token, recommended)" \
        "Anthropic Console API" \
        "MiniMax API" \
        "Xcode API" \
        "Custom API (key + URL)" \
        "Legacy Keychain OAuth")"
      case "$choice" in
        "__CANCEL__") return 1 ;;
        "OAuth token (setup-token, recommended)") printf '%s\n' "oauth_token" ;;
        "Anthropic Console API") printf '%s\n' "anthropic-console" ;;
        "MiniMax API") printf '%s\n' "minimax" ;;
        "Xcode API") printf '%s\n' "xcode" ;;
        "Custom API (key + URL)") printf '%s\n' "custom" ;;
        "Legacy Keychain OAuth") printf '%s\n' "oauth" ;;
        *) return 1 ;;
      esac
      ;;
    codex)
      local choice=""
      choice="$(launcher_choose_from_list \
        "选择 Codex 认证方式" \
        "ChatGPT login (existing)" \
        "ChatGPT login (existing)" \
        "OpenAI API key (xcode)" \
        "Custom API (key + URL)")"
      case "$choice" in
        "__CANCEL__") return 1 ;;
        "ChatGPT login (existing)") printf '%s\n' "chatgpt" ;;
        "OpenAI API key (xcode)") printf '%s\n' "xcode" ;;
        "Custom API (key + URL)") printf '%s\n' "custom" ;;
        *) return 1 ;;
      esac
      ;;
    gemini)
      local choice=""
      choice="$(launcher_choose_from_list \
        "选择 Gemini CLI 认证方式" \
        "Google OAuth (existing login)" \
        "Google OAuth (existing login)" \
        "Gemini API key (primary)" \
        "Custom API (key + URL)")"
      case "$choice" in
        "__CANCEL__") return 1 ;;
        "Google OAuth (existing login)") printf '%s\n' "oauth" ;;
        "Gemini API key (primary)") printf '%s\n' "primary" ;;
        "Custom API (key + URL)") printf '%s\n' "custom" ;;
        *) return 1 ;;
      esac
      ;;
    *)
      return 1
      ;;
  esac
}

# ── --prompt-auth dispatch ─────────────────────────────────────────────
# When the wizard wants the user to pick an auth via launcher's
# AppleScript dialog, it shells out as `agent-launcher.sh --prompt-auth claude`.
# We answer + exit immediately, before any further launcher logic runs.
if [[ -n "$PROMPT_AUTH_TOOL" ]]; then
  case "$PROMPT_AUTH_TOOL" in
    claude|codex|gemini)
      _picked="$(prompt_auth_mode "$PROMPT_AUTH_TOOL" || echo "__CANCEL__")"
      if [[ "$_picked" == "__CANCEL__" || -z "$_picked" ]]; then
        exit 1
      fi
      printf '%s\n' "$_picked"
      exit 0
      ;;
    *)
      echo "error: --prompt-auth tool must be claude|codex|gemini, got '$PROMPT_AUTH_TOOL'" >&2
      exit 2
      ;;
  esac
fi


format_custom_choice_label() {
  local kind="$1"
  local name="$2"
  local base_url="$3"
  local model="$4"
  local detail="$base_url"
  if [[ -n "$model" ]]; then
    detail="$detail · $model"
  fi
  printf '%s: %s — %s\n' "$kind" "$name" "$detail"
}

lookup_custom_choice() {
  local tool="$1"
  local label="$2"
  python3 - "$CUSTOM_PRESET_STORE" "$tool" "$label" <<'PY'
import json
import os
import sys

store_path, tool, label = sys.argv[1:4]
if not os.path.exists(store_path):
    raise SystemExit(1)
with open(store_path, "r", encoding="utf-8") as handle:
    data = json.load(handle)

def emit(kind, name, base_url, model):
    detail = base_url
    if model:
        detail = f"{detail} · {model}"
    expected = f"{kind}: {name} — {detail}"
    if expected == label:
        print(base_url)
        print(model or "")
        raise SystemExit(0)

for preset in data.get("presets", []):
    if preset.get("tool") == tool:
        emit("Preset", preset.get("name", ""), preset.get("base_url", ""), preset.get("model", ""))

for idx, recent in enumerate(data.get("recent_custom", []), start=1):
    if recent.get("tool") == tool:
        emit("Recent", recent.get("name", f"#{idx}"), recent.get("base_url", ""), recent.get("model", ""))

raise SystemExit(1)
PY
}

list_custom_choices() {
  local tool="$1"
  python3 - "$CUSTOM_PRESET_STORE" "$tool" <<'PY'
import json
import os
import sys

store_path, tool = sys.argv[1:3]
if not os.path.exists(store_path):
    raise SystemExit(0)
with open(store_path, "r", encoding="utf-8") as handle:
    data = json.load(handle)

for preset in data.get("presets", []):
    if preset.get("tool") != tool:
        continue
    detail = preset.get("base_url", "")
    model = preset.get("model", "")
    if model:
        detail = f"{detail} · {model}"
    print(f"Preset: {preset.get('name', 'unnamed')} — {detail}")

for idx, recent in enumerate(data.get("recent_custom", []), start=1):
    if recent.get("tool") != tool:
        continue
    detail = recent.get("base_url", "")
    model = recent.get("model", "")
    if model:
        detail = f"{detail} · {model}"
    print(f"Recent: {recent.get('name', f'#{idx}')} — {detail}")
PY
}

list_discovered_choices() {
  local tool="$1"
  local workdir="${2:-}"
  if [[ ! -f "$DISCOVER_HELPER" ]]; then
    return 0
  fi
  python3 "$DISCOVER_HELPER" --mode list --tool "$tool" --workdir "$workdir"
}

lookup_discovered_choice() {
  local tool="$1"
  local label="$2"
  local workdir="${3:-}"
  if [[ ! -f "$DISCOVER_HELPER" ]]; then
    return 1
  fi
  python3 "$DISCOVER_HELPER" --mode lookup --tool "$tool" --workdir "$workdir" --label "$label"
}

list_custom_presets() {
  local tool="$1"
  python3 - "$CUSTOM_PRESET_STORE" "$tool" <<'PY'
import json
import os
import sys

store_path, tool = sys.argv[1:3]
if not os.path.exists(store_path):
    raise SystemExit(0)
with open(store_path, "r", encoding="utf-8") as handle:
    data = json.load(handle)

for preset in data.get("presets", []):
    if preset.get("tool") != tool:
        continue
    detail = preset.get("base_url", "")
    model = preset.get("model", "")
    if model:
        detail = f"{detail} · {model}"
    print(f"Preset: {preset.get('name', 'unnamed')} — {detail}")
PY
}

lookup_custom_preset_name() {
  local tool="$1"
  local label="$2"
  python3 - "$CUSTOM_PRESET_STORE" "$tool" "$label" <<'PY'
import json
import os
import sys

store_path, tool, label = sys.argv[1:4]
if not os.path.exists(store_path):
    raise SystemExit(1)
with open(store_path, "r", encoding="utf-8") as handle:
    data = json.load(handle)

for preset in data.get("presets", []):
    if preset.get("tool") != tool:
        continue
    detail = preset.get("base_url", "")
    model = preset.get("model", "")
    if model:
        detail = f"{detail} · {model}"
    expected = f"Preset: {preset.get('name', 'unnamed')} — {detail}"
    if expected == label:
        print(preset.get("name", ""))
        raise SystemExit(0)

raise SystemExit(1)
PY
}

rename_custom_preset() {
  local tool="$1"
  local old_name="$2"
  local new_name="$3"
  python3 - "$CUSTOM_PRESET_STORE" "$tool" "$old_name" "$new_name" <<'PY'
import json
import os
import sys

store_path, tool, old_name, new_name = sys.argv[1:5]
if not os.path.exists(store_path):
    raise SystemExit(1)

with open(store_path, "r", encoding="utf-8") as handle:
    data = json.load(handle)

updated = False
presets = []
for preset in data.get("presets", []):
    if preset.get("tool") == tool and preset.get("name") == old_name:
        preset = dict(preset)
        preset["name"] = new_name
        updated = True
    presets.append(preset)

if not updated:
    raise SystemExit(1)

data["presets"] = presets
with open(store_path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, ensure_ascii=False, indent=2)
PY
}

delete_custom_preset() {
  local tool="$1"
  local name="$2"
  python3 - "$CUSTOM_PRESET_STORE" "$tool" "$name" <<'PY'
import json
import os
import sys

store_path, tool, name = sys.argv[1:4]
if not os.path.exists(store_path):
    raise SystemExit(1)

with open(store_path, "r", encoding="utf-8") as handle:
    data = json.load(handle)

before = len(data.get("presets", []))
data["presets"] = [
    preset
    for preset in data.get("presets", [])
    if not (preset.get("tool") == tool and preset.get("name") == name)
]

if len(data["presets"]) == before:
    raise SystemExit(1)

with open(store_path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, ensure_ascii=False, indent=2)
PY
}

remember_custom_target() {
  local tool="$1"
  local name="$2"
  local base_url="$3"
  local model="$4"
  local kind="${5:-recent}"
  python3 - "$CUSTOM_PRESET_STORE" "$tool" "$name" "$base_url" "$model" "$kind" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

store_path, tool, name, base_url, model, kind = sys.argv[1:7]
payload = {
    "name": name,
    "tool": tool,
    "base_url": base_url,
    "model": model,
    "updated_at": datetime.now(timezone.utc).isoformat(),
}

data = {"presets": [], "recent_custom": []}
if os.path.exists(store_path):
    try:
        with open(store_path, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
            if isinstance(loaded, dict):
                data.update(loaded)
    except Exception:
        pass

if kind == "preset":
    presets = [item for item in data.get("presets", []) if not (item.get("tool") == tool and item.get("name") == name)]
    presets.insert(0, payload)
    data["presets"] = presets[:20]
else:
    recents = [
        item
        for item in data.get("recent_custom", [])
        if not (
            item.get("tool") == tool
            and item.get("base_url") == base_url
            and item.get("model", "") == model
        )
    ]
    recents.insert(0, payload)
    data["recent_custom"] = recents[:20]

with open(store_path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, ensure_ascii=False, indent=2)
PY
}

manage_custom_presets() {
  local tool="$1"

  while true; do
    local -a preset_choices=()
    while IFS= read -r line; do
      [[ -n "$line" ]] && preset_choices+=("$line")
    done < <(list_custom_presets "$tool")

    if [[ ${#preset_choices[@]} -eq 0 ]]; then
      launcher_show_message "暂无预设" "这个工具当前还没有已保存的自定义 API 预设。"
      return 0
    fi

    local pick=""
    pick="$(launcher_choose_from_list \
      "选择要管理的自定义 API 预设" \
      "${preset_choices[0]}" \
      "${preset_choices[@]}" \
      "Back")" || return 0

    if [[ "$pick" == "__CANCEL__" || "$pick" == "Back" ]]; then
      return 0
    fi

    local preset_name=""
    preset_name="$(lookup_custom_preset_name "$tool" "$pick")" || continue

    local action=""
    action="$(launcher_choose_from_list \
      "管理预设：$preset_name" \
      "Rename preset" \
      "Rename preset" \
      "Delete preset" \
      "Back")" || return 0

    case "$action" in
      "Rename preset")
        local new_name=""
        new_name="$(launcher_prompt_text "输入新的预设名称" "$preset_name")" || continue
        if [[ -z "$new_name" || "$new_name" == "__CANCEL__" || "$new_name" == "$preset_name" ]]; then
          continue
        fi
        rename_custom_preset "$tool" "$preset_name" "$new_name" && \
          launcher_show_message "已重命名" "预设已从“$preset_name”重命名为“$new_name”。"
        ;;
      "Delete preset")
        if launcher_prompt_yes_no "确认删除预设“$preset_name”？（不会影响最近记录）" "否"; then
          delete_custom_preset "$tool" "$preset_name" && \
            launcher_show_message "已删除" "预设“$preset_name”已删除。"
        fi
        ;;
      *)
        ;;
    esac
  done
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


prompt_custom_api_env() {
  local tool="$1"
  local workdir="${2:-}"
  local key_prompt url_prompt default_url model_prompt default_model

  case "$tool" in
    claude)
      key_prompt="输入 Claude 兼容 API Key（仅本次会话使用）"
      url_prompt="输入 Claude 兼容 Base URL（可留空使用默认）"
      default_url="https://api.anthropic.com"
      model_prompt="输入 Claude 模型名（可留空使用 CLI 默认）"
      default_model=""
      ;;
    codex)
      key_prompt="输入 OpenAI 兼容 API Key（仅本次会话使用）"
      url_prompt="输入 OpenAI 兼容 Base URL（可留空使用默认）"
      default_url="https://api.openai.com/v1"
      model_prompt="输入 Codex 模型名（可留空使用默认，例如 gpt-5.4）"
      default_model=""
      ;;
    gemini)
      key_prompt="输入 Gemini API Key（仅本次会话使用）"
      url_prompt="输入 Gemini Base URL（可留空使用默认）"
      default_url="https://generativelanguage.googleapis.com"
      model_prompt="输入 Gemini 模型名（可留空使用 CLI 默认）"
      default_model=""
      ;;
    *)
      return 1
      ;;
  esac

  local -a saved_choices=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && saved_choices+=("$line")
  done < <(list_custom_choices "$tool")

  local -a preset_choices=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && preset_choices+=("$line")
  done < <(list_custom_presets "$tool")

  local -a discovered_choices=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && discovered_choices+=("$line")
  done < <(list_discovered_choices "$tool" "$workdir")

  if [[ ${#saved_choices[@]} -gt 0 || ${#preset_choices[@]} -gt 0 || ${#discovered_choices[@]} -gt 0 ]]; then
    local -a quick_options=("Create new custom API config")
    if [[ ${#preset_choices[@]} -gt 0 ]]; then
      quick_options+=("Manage saved presets...")
    fi
    if [[ ${#discovered_choices[@]} -gt 0 ]]; then
      quick_options+=("${discovered_choices[@]}")
    fi
    if [[ ${#saved_choices[@]} -gt 0 ]]; then
      quick_options+=("${saved_choices[@]}")
    fi

    local quick_choice=""
    quick_choice="$(launcher_choose_from_list \
      "选择已有自定义配置，或新建一个" \
      "Create new custom API config" \
      "${quick_options[@]}")" || return 1
    if [[ "$quick_choice" == "Manage saved presets..." ]]; then
      manage_custom_presets "$tool"
      prompt_custom_api_env "$tool" "$workdir"
      return $?
    fi
    if [[ "$quick_choice" == Discovered:* ]]; then
      local discovered=""
      if discovered="$(lookup_discovered_choice "$tool" "$quick_choice" "$workdir")"; then
        local api_key_found="" base_url_found="" model_found="" source_found=""
        api_key_found="$(printf '%s\n' "$discovered" | sed -n '1p')"
        base_url_found="$(printf '%s\n' "$discovered" | sed -n '2p')"
        model_found="$(printf '%s\n' "$discovered" | sed -n '3p')"
        source_found="$(printf '%s\n' "$discovered" | sed -n '4p')"
        remember_custom_target "$tool" "recent" "$base_url_found" "$model_found" "recent"
        if launcher_prompt_yes_no "是否把这个发现到的配置保存成预设？来源：$source_found" "否"; then
          local discovered_name=""
          discovered_name="$(launcher_prompt_text "给这个发现到的配置取个名字" "$tool-discovered")" || true
          if [[ -n "$discovered_name" && "$discovered_name" != "__CANCEL__" ]]; then
            remember_custom_target "$tool" "$discovered_name" "$base_url_found" "$model_found" "preset"
          fi
        fi
        write_custom_env_file "$api_key_found" "$base_url_found" "$model_found"
        return 0
      fi
    fi
    if [[ "$quick_choice" != "Create new custom API config" ]]; then
      local looked_up=""
      if looked_up="$(lookup_custom_choice "$tool" "$quick_choice")"; then
        local base_url_saved="" model_saved=""
        base_url_saved="$(printf '%s\n' "$looked_up" | sed -n '1p')"
        model_saved="$(printf '%s\n' "$looked_up" | sed -n '2p')"
        local api_key_saved=""
        api_key_saved="$(launcher_prompt_secret "$key_prompt")" || return 1
        if [[ "$api_key_saved" == "__CANCEL__" || -z "$api_key_saved" ]]; then
          return 1
        fi
        remember_custom_target "$tool" "recent" "$base_url_saved" "$model_saved" "recent"
        write_custom_env_file "$api_key_saved" "$base_url_saved" "$model_saved"
        return 0
      fi
    fi
  fi

  local api_key base_url model
  api_key="$(launcher_prompt_secret "$key_prompt")" || return 1
  if [[ "$api_key" == "__CANCEL__" || -z "$api_key" ]]; then
    return 1
  fi

  base_url="$(launcher_prompt_text "$url_prompt" "$default_url")" || return 1
  if [[ "$base_url" == "__CANCEL__" ]]; then
    return 1
  fi

  model="$(launcher_prompt_text "$model_prompt" "$default_model")" || return 1
  if [[ "$model" == "__CANCEL__" ]]; then
    return 1
  fi

  remember_custom_target "$tool" "recent" "$base_url" "$model" "recent"
  if launcher_prompt_yes_no "是否保存这个自定义 API 预设（仅保存 URL 和模型，不保存 API Key）？" "否"; then
    local preset_name=""
    preset_name="$(launcher_prompt_text "给这个预设取个名字" "$tool-custom")" || true
    if [[ -n "$preset_name" && "$preset_name" != "__CANCEL__" ]]; then
      remember_custom_target "$tool" "$preset_name" "$base_url" "$model" "preset"
    fi
  fi

  write_custom_env_file "$api_key" "$base_url" "$model"
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
      launcher_show_message \
        "缺少 Claude OAuth token" \
        "未找到可用的 CLAUDE_CODE_OAUTH_TOKEN。\n\n请先在终端运行：\nclaude setup-token\n\n然后把结果写入：\n~/.agents/.env.global\n\n例如：\nexport CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-..."
      ;;
    anthropic-console)
      launcher_show_message \
        "缺少 Anthropic Console API Key" \
        "未找到可用的 ANTHROPIC_API_KEY。\n\n请先在 Anthropic Console 创建 Claude Code scoped key，然后写入：\n~/.agents/secrets/claude/anthropic-console.env\n\n例如：\nANTHROPIC_API_KEY=sk-ant-api03-..."
      ;;
  esac
}

prepare_codex_home() {
  local codex_home="$1"
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
    if [[ -e "$REAL_HOME/.codex/$item" && ! -e "$codex_home/$item" ]]; then
      ln -s "$REAL_HOME/.codex/$item" "$codex_home/$item"
    fi
  done
}

prepare_gemini_home() {
  local runtime_home="$1"
  local gemini_home="$runtime_home/.gemini"
  mkdir -p "$gemini_home"

  local shared_items=(
    "settings.json"
    "installation_id"
    "skills"
  )

  local item
  for item in "${shared_items[@]}"; do
    if [[ -e "$REAL_HOME/.gemini/$item" && ! -e "$gemini_home/$item" ]]; then
      ln -s "$REAL_HOME/.gemini/$item" "$gemini_home/$item"
    fi
  done
}

prepare_claude_home() {
  # Seed Claude Code's isolated HOME so onboarding doesn't fire for every
  # seat launch. Claude checks `~/.claude.json.hasCompletedOnboarding`
  # (and related flags) on every start; if the isolated HOME has none,
  # Claude blocks on the onboarding screen even when API keys are live
  # in the environment — breaks every API-mode launch and every
  # programmatic spawn (B4-launch-pending-seats).
  #
  # Symlink `~/.claude.json` from the real HOME iff the seat wants shared
  # UI state (default); otherwise seed a minimal stub. We default to
  # symlink because the real `.claude.json` is append-only for onboarding
  # flags, and per-seat projects/history live under `~/.claude/projects/`
  # keyed by workdir — seats don't collide.
  local runtime_home="$1"
  mkdir -p "$runtime_home/.claude"

  if [[ -f "$REAL_HOME/.claude.json" && ! -e "$runtime_home/.claude.json" ]]; then
    ln -s "$REAL_HOME/.claude.json" "$runtime_home/.claude.json"
  elif [[ ! -f "$runtime_home/.claude.json" ]]; then
    # Fallback: real user hasn't run claude yet, seed minimal flags so
    # onboarding doesn't block the automated seat.
    cat > "$runtime_home/.claude.json" <<'JSON'
{
  "hasCompletedOnboarding": true,
  "lastOnboardingVersion": "99.99.99",
  "hasSeenWelcome": true
}
JSON
  fi

  # Carry over statsig / settings / projects listing from real HOME so
  # first-run analytics + theme pickers don't show either.
  local shared_items=(
    "settings.json"
    "statsig"
  )
  local item
  for item in "${shared_items[@]}"; do
    if [[ -e "$REAL_HOME/.claude/$item" && ! -e "$runtime_home/.claude/$item" ]]; then
      ln -s "$REAL_HOME/.claude/$item" "$runtime_home/.claude/$item"
    fi
  done
}

run_claude_runtime() {
  local auth_mode="$1"
  local workdir="$2"
  local session_name="$3"
  local mode_label="Claude Code"

  if [[ "$auth_mode" == "oauth" ]]; then
    unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL ANTHROPIC_MODEL
    export HOME="$REAL_HOME"
    cd "$workdir"
    echo "────────────────────────────────────────"
    echo " Claude Code · Legacy OAuth"
    echo " Session:    $session_name"
    echo " Directory:  $workdir"
    echo " HOME:       $HOME"
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
    export ANTHROPIC_AUTH_TOKEN="${LAUNCHER_CUSTOM_API_KEY:-}"
    export ANTHROPIC_BASE_URL="${LAUNCHER_CUSTOM_BASE_URL:-}"
    export ANTHROPIC_MODEL="${LAUNCHER_CUSTOM_MODEL:-}"
    export ANTHROPIC_API_KEY="${LAUNCHER_CUSTOM_API_KEY:-}"
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

  # Skip Claude onboarding in the isolated HOME. Without this the seat
  # blocks on the welcome + auth pages even when API keys are live in env.
  prepare_claude_home "$HOME"

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
    cd "$workdir"
    echo "────────────────────────────────────────"
    echo " Codex · ChatGPT login"
    echo " Session:    $session_name"
    echo " Directory:  $workdir"
    echo " CODEX_HOME: $CODEX_HOME"
    echo "────────────────────────────────────────"
    exec codex -C "$workdir"
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
  prepare_codex_home "$CODEX_HOME"

  if [[ "$auth_mode" == "custom" ]]; then
    load_custom_env "$CUSTOM_ENV_FILE"
    rm -f "$CODEX_HOME/config.toml"
    python3 - "$CODEX_HOME/config.toml" "${LAUNCHER_CUSTOM_MODEL:-gpt-5.4}" "${LAUNCHER_CUSTOM_BASE_URL:-https://api.openai.com/v1}" "${LAUNCHER_CUSTOM_API_KEY:-}" <<'PY'
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
    if [[ ! -f "$CODEX_HOME/auth.json" ]]; then
      printf '%s' "${OPENAI_API_KEY:-}" | HOME="$HOME" CODEX_HOME="$CODEX_HOME" codex login --with-api-key >/dev/null
    fi
  fi

  cd "$workdir"
  echo "────────────────────────────────────────"
  echo " Codex · ${auth_mode^^} API"
  echo " Session:    $session_name"
  echo " Directory:  $workdir"
  echo " HOME:       $HOME"
  echo " CODEX_HOME: $CODEX_HOME"
  echo "────────────────────────────────────────"
  if [[ "$auth_mode" == "custom" ]]; then
    if [[ -n "${LAUNCHER_CUSTOM_MODEL:-}" ]]; then
      exec codex -C "$workdir" -c model_provider=customapi -m "${LAUNCHER_CUSTOM_MODEL}"
    fi
    exec codex -C "$workdir" -c model_provider=customapi
  fi
  exec codex -C "$workdir"
}

run_gemini_runtime() {
  local auth_mode="$1"
  local workdir="$2"
  local session_name="$3"

  if [[ "$auth_mode" == "oauth" ]]; then
    unset GEMINI_API_KEY GOOGLE_API_KEY
    export HOME="$REAL_HOME"
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
  prepare_gemini_home "$HOME"

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
  echo " Gemini CLI · ${auth_mode^^} API"
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

run_selected_tool() {
  case "$1" in
    claude) run_claude_runtime "$2" "$3" "$4" ;;
    codex) run_codex_runtime "$2" "$3" "$4" ;;
    gemini) run_gemini_runtime "$2" "$3" "$4" ;;
    *) echo "error: unsupported tool: $1" >&2; exit 2 ;;
  esac
}

if [[ -z "$EXEC_MODE" ]]; then
  if [[ -z "$TOOL_NAME" ]]; then
    TOOL_NAME="$(prompt_tool_name)" || exit 130
  fi

  if [[ -z "$AUTH_MODE" ]]; then
    AUTH_MODE="$(prompt_auth_mode "$TOOL_NAME")" || exit 130
  fi

  if [[ -z "$WORKDIR" ]]; then
    WORKDIR="$(launcher_choose_start_dir)" || exit 130
  fi

  if [[ "$AUTH_MODE" == "custom" && -z "$CUSTOM_ENV_FILE" ]]; then
    CUSTOM_ENV_FILE="$(prompt_custom_api_env "$TOOL_NAME" "$WORKDIR")" || exit 130
  fi

  if [[ ! -d "$WORKDIR" ]]; then
    echo "error: startup directory does not exist: $WORKDIR" >&2
    exit 1
  fi

  if [[ -z "$SESSION_NAME" ]]; then
    SESSION_NAME="${TOOL_NAME}-${AUTH_MODE}-$(launcher_slugify "$(basename "$WORKDIR")")"
  fi

  # ── Ancestor-session preflight ──────────────────────────────────────
  # When session name matches "<project>-ancestor-<tool>", ensure the
  # playbook-generated profile + brief are present before spawning Claude.
  # This makes profile + brief
  # ready-to-consume by the time the ancestor skill comes online.
  if [[ "$SKIP_ANCESTOR_PREFLIGHT" != "1" && "$SESSION_NAME" =~ ^(.+)-ancestor-(claude|codex|gemini)$ ]]; then
    _preflight_project="${BASH_REMATCH[1]}"
    _preflight_tool="${BASH_REMATCH[2]}"
    _profile_path="$REAL_HOME/.agents/profiles/${_preflight_project}-profile-dynamic.toml"
    _brief_path="$REAL_HOME/.agents/tasks/${_preflight_project}/patrol/handoffs/ancestor-bootstrap.md"
    _binding_path="$REAL_HOME/.agents/tasks/${_preflight_project}/PROJECT_BINDING.toml"
    _clawseat_root="${CLAWSEAT_ROOT:-$REAL_HOME/ClawSeat}"
    _clawseat_core="$_clawseat_root/core"

    if [[ -f "$_profile_path" ]]; then
      # R-2: verify existing profile is v2 before reusing. Ancestor's brief
      # loader rejects v1 with a hard raise; better to fail loudly here
      # with a migration hint than to crash deep inside Phase-A.
      _profile_ver="$(
        python3 - "$_profile_path" <<'PY'
import sys
try:
    import tomllib
except ImportError:
    import tomli as tomllib
try:
    raw = tomllib.loads(open(sys.argv[1], 'rb').read().decode('utf-8'))
    print(raw.get("version", 0))
except Exception as exc:
    print(f"ERR:{exc}")
PY
      )"
      if [[ "$_profile_ver" != "2" ]]; then
        echo "error: profile at $_profile_path is not v2 (version=$_profile_ver)" >&2
        echo "       run: python3 $_clawseat_core/scripts/migrate_profile_to_v2.py apply --profile $_profile_path" >&2
        echo "       or remove the old profile and re-run docs/INSTALL.md" >&2
        exit 6
      fi
      if [[ -n "$CLONE_FROM" ]]; then
        echo "error: --clone-from given but project '$_preflight_project' already has a v2 profile at $_profile_path" >&2
        echo "       to re-clone, first remove or rename the existing profile" >&2
        exit 2
      fi
      echo "ancestor-preflight: reusing existing v2 profile for '$_preflight_project'"
    else
      echo "error: ancestor-preflight no longer auto-runs the retired TUI installer in v0.5" >&2
      echo "       materialize the v2 profile and PROJECT_BINDING first via docs/INSTALL.md, then relaunch ancestor" >&2
      if [[ -n "$CLONE_FROM" ]]; then
        echo "       requested clone source: $CLONE_FROM" >&2
      fi
      exit 3
    fi

    if [[ ! -f "$_binding_path" ]] || ! grep -q 'feishu_group_id *= *"oc_' "$_binding_path" 2>/dev/null; then
      echo "error: PROJECT_BINDING.toml for '$_preflight_project' is missing feishu_group_id" >&2
      echo "       the install playbook should have written it; rerun docs/INSTALL.md step 3 or bind manually" >&2
      exit 4
    fi

    if [[ ! -f "$_brief_path" ]]; then
      echo "ancestor-preflight: generating bootstrap brief for '$_preflight_project'"
      (
        cd "$_clawseat_root" &&
        PYTHONPATH="$_clawseat_core/lib:${PYTHONPATH:-}" \
          python3 -m core.tui.ancestor_brief --project "$_preflight_project"
      ) || {
        echo "error: ancestor_brief generation failed; aborting ancestor launch" >&2
        exit 5
      }
    else
      echo "ancestor-preflight: brief already present"
    fi

    # R-1: Install Phase-B launchd plist. Without this, ancestor Phase-A
    # completes but Phase-B patrol never fires. Idempotent via bootout +
    # bootstrap cycle.
    _plist_template="$_clawseat_core/templates/ancestor-patrol.plist.in"
    _plist_label="com.clawseat.${_preflight_project}.ancestor-patrol"
    _launchagents_dir="$REAL_HOME/Library/LaunchAgents"
    _plist_out="$_launchagents_dir/${_plist_label}.plist"
    _log_dir="$REAL_HOME/.agents/tasks/${_preflight_project}/patrol/logs"
    if [[ ! -f "$_plist_template" ]]; then
      echo "warn: Phase-B plist template missing ($_plist_template); ancestor Phase-B patrol will NOT be scheduled" >&2
    else
      _cadence_sec="$(
        python3 - "$_profile_path" <<'PY'
import sys
try:
    import tomllib
except ImportError:
    import tomli as tomllib
try:
    raw = tomllib.loads(open(sys.argv[1], 'rb').read().decode('utf-8'))
    print(int(raw.get("patrol", {}).get("cadence_minutes", 30)) * 60)
except Exception:
    print(1800)  # safe default 30min
PY
      )"
      mkdir -p "$_launchagents_dir" "$_log_dir"
      # Render template — use | as sed delimiter since paths contain /.
      sed \
        -e "s|{PROJECT}|${_preflight_project}|g" \
        -e "s|{TOOL}|${_preflight_tool}|g" \
        -e "s|{CADENCE_SECONDS}|${_cadence_sec}|g" \
        -e "s|{CLAWSEAT_ROOT}|${_clawseat_root}|g" \
        -e "s|{LOG_DIR}|${_log_dir}|g" \
        "$_plist_template" > "$_plist_out"
      # Idempotent activation: ignore bootout errors (plist may not be loaded).
      launchctl bootout "gui/$(id -u)/${_plist_label}" 2>/dev/null || true
      if launchctl bootstrap "gui/$(id -u)" "$_plist_out" 2>/dev/null; then
        echo "ancestor-preflight: Phase-B plist loaded (${_plist_label}, cadence=${_cadence_sec}s)"
      else
        echo "warn: launchctl bootstrap failed for $_plist_out; Phase-B patrol will not run automatically" >&2
        echo "       manual: launchctl bootstrap gui/$(id -u) $_plist_out" >&2
      fi
    fi

    unset _preflight_project _preflight_tool _profile_path _brief_path _binding_path
    unset _clawseat_root _clawseat_core _wizard_args _profile_ver
    unset _plist_template _plist_label _launchagents_dir _plist_out _log_dir _cadence_sec
  fi
  # ────────────────────────────────────────────────────────────────────

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
    if [[ -n "$CUSTOM_ENV_FILE" && -f "$CUSTOM_ENV_FILE" ]]; then
      rm -f "$CUSTOM_ENV_FILE"
    fi
    exit 0
  fi

  if ! command -v tmux >/dev/null 2>&1; then
    echo "warn: tmux not found — falling back to inline $TOOL_NAME" >&2
    launcher_remember_recent_dir "$WORKDIR"
    exec "$0" --tool "$TOOL_NAME" --session "$SESSION_NAME" --auth "$AUTH_MODE" --dir "$WORKDIR" --exec-agent
  fi

  if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "reusing existing tmux session '$SESSION_NAME'"
    if [[ -n "$CUSTOM_ENV_FILE" && -f "$CUSTOM_ENV_FILE" ]]; then
      rm -f "$CUSTOM_ENV_FILE"
    fi
  else
    tmux new-session -d -s "$SESSION_NAME" -x 220 -y 60 \
      "bash \"$0\" --tool \"$TOOL_NAME\" --session \"$SESSION_NAME\" --auth \"$AUTH_MODE\" --dir \"$WORKDIR\" --custom-env-file \"$CUSTOM_ENV_FILE\" --exec-agent"
    echo "launched tmux session '$SESSION_NAME'"
  fi

  launcher_remember_recent_dir "$WORKDIR"

  if [[ "$HEADLESS" != "1" ]]; then
    launcher_attach_tmux_session "$SESSION_NAME" "$SESSION_NAME (${TOOL_NAME})"
  fi

  # bash 3.2 on macOS has no ${VAR^} uppercase-first operator; use awk
  # (top-level scope here, so no `local` — that's a bash syntax error
  # outside a function in some shells).
  _tool_title="$(printf '%s' "$TOOL_NAME" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')"
  cat <<EOF

${_tool_title} session ready
  auth:     $AUTH_MODE
  dir:      $WORKDIR
  tmux:     $SESSION_NAME

Manual attach:
  tmux attach -t $SESSION_NAME

Kill session:
  tmux kill-session -t $SESSION_NAME

EOF

  launcher_close_invoking_terminal_window
  exit 0
fi

if [[ -z "$TOOL_NAME" || -z "$AUTH_MODE" || -z "$WORKDIR" || -z "$SESSION_NAME" ]]; then
  echo "error: --exec-agent requires --tool, --auth, --dir, and --session" >&2
  exit 2
fi

run_selected_tool "$TOOL_NAME" "$AUTH_MODE" "$WORKDIR" "$SESSION_NAME"
