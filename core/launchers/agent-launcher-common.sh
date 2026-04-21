#!/usr/bin/env bash

set -euo pipefail

launcher_choose_from_list() {
  local prompt="$1"
  local default_choice="$2"
  shift 2
  local launcher_home picker
  launcher_home="${REAL_HOME:-$HOME}"
  picker="${AGENT_LAUNCHER_DIR:-$launcher_home/Desktop}/agent-launcher-fuzzy.py"
  if [[ ! -f "$picker" && -f "$launcher_home/Desktop/.agent-launcher-fuzzy.py" ]]; then
    picker="$launcher_home/Desktop/.agent-launcher-fuzzy.py"  # legacy fallback
  fi

  if [[ -f "$picker" && -t 0 && -t 1 && "${TERM:-dumb}" != "dumb" ]]; then
    local choices_file
    choices_file="$(mktemp -t agent-launcher-choices.XXXXXX)"
    printf '%s\n' "$@" >"$choices_file"
    local choice=""
    if choice="$(python3 "$picker" \
      --mode choices \
      --choices-file "$choices_file" \
      --prompt "$prompt" \
      --default-choice "$default_choice")"; then
      rm -f "$choices_file"
      printf '%s\n' "$choice"
      return 0
    fi
    rm -f "$choices_file"
    return 1
  fi

  osascript - "$prompt" "$default_choice" "$@" <<'APPLESCRIPT'
on run argv
  set promptText to item 1 of argv
  set defaultChoice to item 2 of argv
  if (count of argv) < 3 then error "No options provided"
  set optionList to items 3 thru -1 of argv
  set chosen to choose from list optionList with prompt promptText default items {defaultChoice}
  if chosen is false then
    return "__CANCEL__"
  end if
  return item 1 of chosen
end run
APPLESCRIPT
}

launcher_choose_folder() {
  local prompt="$1"
  osascript - "$prompt" <<'APPLESCRIPT'
on run argv
  set promptText to item 1 of argv
  set chosenFolder to choose folder with prompt promptText
  return POSIX path of chosenFolder
end run
APPLESCRIPT
}

launcher_prompt_text() {
  local prompt="$1"
  local default_answer="${2:-}"
  osascript - "$prompt" "$default_answer" <<'APPLESCRIPT'
on run argv
  set promptText to item 1 of argv
  set defaultAnswer to item 2 of argv
  try
    set dialogResult to display dialog promptText default answer defaultAnswer buttons {"取消", "确认"} default button "确认"
    return text returned of dialogResult
  on error number -128
    return "__CANCEL__"
  end try
end run
APPLESCRIPT
}

launcher_prompt_secret() {
  local prompt="$1"
  osascript - "$prompt" <<'APPLESCRIPT'
on run argv
  set promptText to item 1 of argv
  try
    set dialogResult to display dialog promptText default answer "" with hidden answer buttons {"取消", "确认"} default button "确认"
    return text returned of dialogResult
  on error number -128
    return "__CANCEL__"
  end try
end run
APPLESCRIPT
}

launcher_prompt_yes_no() {
  local prompt="$1"
  local default_choice="${2:-否}"
  local choice
  choice="$(launcher_choose_from_list "$prompt" "$default_choice" "是" "否")" || return 1
  case "$choice" in
    "是") return 0 ;;
    *) return 1 ;;
  esac
}

launcher_show_message() {
  local title="$1"
  local message="$2"
  osascript - "$title" "$message" <<'APPLESCRIPT'
on run argv
  set titleText to item 1 of argv
  set bodyText to item 2 of argv
  display alert titleText message bodyText as informational buttons {"好"} default button "好"
end run
APPLESCRIPT
}

launcher_state_store_path() {
  local launcher_home default_store
  launcher_home="${REAL_HOME:-$HOME}"
  # Prefer explicit env; otherwise reuse legacy desktop path if present so
  # users don't lose their state on clawseat migration; otherwise XDG.
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

launcher_format_dir_label() {
  local path="$1"
  local name
  name="$(basename "$path")"
  if [[ "$path" == "/" ]]; then
    name="/"
  fi
  printf 'Recent: %s — %s\n' "$name" "$path"
}

launcher_list_recent_dirs() {
  local store
  store="$(launcher_state_store_path)"
  python3 - "$store" <<'PY'
import json
import os
import sys

store_path = sys.argv[1]
if not os.path.exists(store_path):
    raise SystemExit(0)

try:
    with open(store_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
except Exception:
    raise SystemExit(0)

for path in data.get("recent_dirs", []):
    if not isinstance(path, str) or not os.path.isdir(path):
        continue
    name = os.path.basename(path) or "/"
    print(f"Recent: {name} — {path}")
PY
}

launcher_lookup_recent_dir() {
  local label="$1"
  python3 - "$label" <<'PY'
import sys

label = sys.argv[1]
prefix = "Recent: "
if not label.startswith(prefix) or " — " not in label:
    raise SystemExit(1)
_, path = label.split(" — ", 1)
print(path)
PY
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

recent = [entry for entry in data.get("recent_dirs", []) if isinstance(entry, str) and entry != path and os.path.isdir(entry)]
recent.insert(0, path)
data["recent_dirs"] = recent[:12]

with open(store_path, "w", encoding="utf-8") as handle:
  json.dump(data, handle, ensure_ascii=False, indent=2)
PY
}

launcher_search_directories_by_query() {
  local query="$1"
  python3 - "$query" <<'PY'
import os
import sys
from pathlib import Path

query = sys.argv[1].strip().lower()
if not query:
    raise SystemExit(0)

path_query = "/" in query

# Workspace roots for fuzzy search — defaults match the original desktop
# layout; operators override via CLAWSEAT_LAUNCHER_ROOTS (colon-separated).
home = Path(os.environ.get("REAL_HOME", os.environ.get("HOME", str(Path.home()))))
_env_roots = os.environ.get("CLAWSEAT_LAUNCHER_ROOTS", "")
if _env_roots.strip():
    roots = [Path(p).expanduser() for p in _env_roots.split(":") if p.strip()]
else:
    roots = [
        home / "coding",
        home / "Desktop" / "work",
        home / "Desktop",
        home / "Documents",
        home,
    ]

ignored = {
    ".git", "node_modules", ".pnpm-store", ".venv", "venv", "__pycache__",
    ".next", "dist", "build", ".codex", ".agents", "Library", ".Trash",
}

max_depth = 5
limit = 200
scored = {}

def score(path_str: str) -> tuple[int, int, str]:
    name = os.path.basename(path_str).lower()
    exact = 0 if name == query else 1
    starts = 0 if name.startswith(query) else 1
    depth = path_str.count(os.sep)
    return (exact, starts, depth, path_str.lower())

for root in roots:
    if not root.exists():
        continue

    for current_root, dirnames, _ in os.walk(root):
        rel = Path(current_root).relative_to(root)
        depth = len(rel.parts)
        dirnames[:] = [d for d in dirnames if d not in ignored]
        if depth >= max_depth:
          dirnames[:] = []

        path_obj = Path(current_root)
        path_str = str(path_obj)
        name = path_obj.name.lower()
        matched = query in name
        if not matched and path_query:
            matched = query in path_str.lower()
        if matched:
            scored[path_str] = score(path_str)

for path_str, _ in sorted(scored.items(), key=lambda item: item[1])[:limit]:
    print(path_str)
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
if path.is_dir():
    print(path.resolve())
    raise SystemExit(0)

raise SystemExit(1)
PY
}

launcher_search_for_directory_dialog() {
  while true; do
    local query
    query="$(launcher_prompt_text "输入目录关键词，或直接粘贴绝对路径" "$HOME/coding/cartooner")"
    if [[ "$query" == "__CANCEL__" ]]; then
      return 1
    fi

    local resolved=""
    if resolved="$(launcher_resolve_directory_path "$query" 2>/dev/null)"; then
      printf '%s\n' "$resolved"
      return 0
    fi

    local -a matches=()
    while IFS= read -r line; do
      [[ -n "$line" ]] && matches+=("$line")
    done < <(launcher_search_directories_by_query "$query")

    if [[ ${#matches[@]} -eq 0 ]]; then
      launcher_show_message "未找到目录" "没有匹配 “$query” 的目录。你可以继续搜索、手动粘贴绝对路径，或者取消。"
      continue
    fi

    local choice
    choice="$(launcher_choose_from_list "选择匹配到的目录" "${matches[0]}" "${matches[@]}")"
    if [[ "$choice" == "__CANCEL__" ]]; then
      return 1
    fi
    printf '%s\n' "$choice"
    return 0
  done
}

launcher_fuzzy_pick_directory() {
  local launcher_home picker
  launcher_home="${REAL_HOME:-$HOME}"
  picker="${AGENT_LAUNCHER_DIR:-$launcher_home/Desktop}/agent-launcher-fuzzy.py"
  if [[ ! -f "$picker" && -f "$launcher_home/Desktop/.agent-launcher-fuzzy.py" ]]; then
    picker="$launcher_home/Desktop/.agent-launcher-fuzzy.py"  # legacy fallback
  fi

  if [[ ! -f "$picker" || ! -t 0 || ! -t 1 || "${TERM:-dumb}" == "dumb" ]]; then
    launcher_search_for_directory_dialog
    return $?
  fi

  python3 "$picker"
}

launcher_choose_start_dir() {
  while true; do
    local -a recent_choices=()
    while IFS= read -r line; do
      [[ -n "$line" ]] && recent_choices+=("$line")
    done < <(launcher_list_recent_dirs)

    local -a options=()
    if [[ ${#recent_choices[@]} -gt 0 ]]; then
      options+=("${recent_choices[@]}")
    fi
    options+=(
      "Cartooner ($HOME/coding/cartooner)"
      "Desktop work ($HOME/Desktop/work)"
      "Live fuzzy search..."
      "Enter path manually..."
      "Choose another folder..."
      "Home ($HOME)"
    )

    local selection
    local default_choice="Cartooner ($HOME/coding/cartooner)"
    if [[ ${#recent_choices[@]} -gt 0 ]]; then
      default_choice="${recent_choices[0]}"
    fi
    selection="$(launcher_choose_from_list \
      "选择启动目录。支持最近目录、快捷目录、搜索目录、手动输入路径。" \
      "$default_choice" \
      "${options[@]}")"

    case "$selection" in
      "__CANCEL__")
        return 1
        ;;
      Recent:*)
        launcher_lookup_recent_dir "$selection"
        return 0
        ;;
      "Cartooner ($HOME/coding/cartooner)")
        printf '%s\n' "$HOME/coding/cartooner"
        return 0
        ;;
      "Desktop work ($HOME/Desktop/work)")
        printf '%s\n' "$HOME/Desktop/work"
        return 0
        ;;
      "Live fuzzy search...")
        launcher_fuzzy_pick_directory && return 0
        ;;
      "Enter path manually...")
        local manual_path
        manual_path="$(launcher_prompt_text "输入绝对路径或 ~ 路径" "$HOME/coding/cartooner")"
        if [[ "$manual_path" == "__CANCEL__" ]]; then
          return 1
        fi
        local resolved=""
        if resolved="$(launcher_resolve_directory_path "$manual_path" 2>/dev/null)"; then
          printf '%s\n' "$resolved"
          return 0
        fi
        launcher_show_message "目录无效" "这个路径不存在，或者不是目录：$manual_path"
        ;;
      "Choose another folder...")
        launcher_choose_folder "选择启动目录"
        return 0
        ;;
      "Home ($HOME)")
        printf '%s\n' "$HOME"
        return 0
        ;;
      *)
        return 1
        ;;
    esac
  done
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

launcher_attach_tmux_session() {
  local session_name="$1"
  local window_title="$2"

  if [[ -d /Applications/iTerm.app ]]; then
    osascript >/dev/null <<APPLESCRIPT
tell application "iTerm"
  activate
  set w to (create window with default profile)
  tell current session of w
    set name to "$window_title"
    write text "tmux attach -t $session_name"
  end tell
end tell
APPLESCRIPT
    printf 'attached iTerm window to tmux session %s\n' "$session_name"
  else
    osascript >/dev/null <<APPLESCRIPT
tell application "Terminal"
  activate
  do script "tmux attach -t $session_name"
end tell
APPLESCRIPT
    printf 'attached Terminal window to tmux session %s (iTerm not installed)\n' "$session_name"
  fi
}

launcher_close_invoking_terminal_window() {
  if [[ "${TERM_PROGRAM:-}" != "Apple_Terminal" || -n "${TMUX:-}" ]]; then
    return 0
  fi

  local my_tty
  my_tty="$(tty 2>/dev/null || true)"
  if [[ -z "$my_tty" ]]; then
    return 0
  fi

  osascript >/dev/null 2>&1 <<APPLESCRIPT &
tell application "Terminal"
  repeat with w in windows
    repeat with t in tabs of w
      try
        if (tty of t) is "$my_tty" then
          close w saving no
          return
        end if
      end try
    end repeat
  end repeat
end tell
APPLESCRIPT
}
