#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_CLAWSEAT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CLAWSEAT_ROOT="${CLAWSEAT_ROOT:-${CLAUDE_PROJECT_DIR:-$DEFAULT_CLAWSEAT_ROOT}}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SESSION_NAME="${TMUX_SESSION_NAME:-machine-memory-claude}"

parse_payload() {
  local payload_json="$1"
  HOOK_PAYLOAD_JSON="$payload_json" "$PYTHON_BIN" - "$CLAWSEAT_ROOT" <<'PY'
import json
import os
import re
import shlex
import sys
from pathlib import Path

clawseat_root = Path(sys.argv[1]).expanduser()
for extra in (clawseat_root, clawseat_root / "core" / "lib"):
    text = str(extra)
    if text not in sys.path:
        sys.path.insert(0, text)

try:
    from core.resolve import dynamic_profile_path
except Exception:  # pragma: no cover - best effort for hook runtime
    dynamic_profile_path = None  # type: ignore[assignment]


def emit(name: str, value: str) -> None:
    print(f"{name}={shlex.quote(value)}")


raw = os.environ.get("HOOK_PAYLOAD_JSON", "").strip()
if not raw:
    raise SystemExit(0)
try:
    payload = json.loads(raw)
except json.JSONDecodeError:
    raise SystemExit(0)

transcript_path = str(payload.get("transcript_path", "") or "").strip()
last_assistant_message = str(payload.get("last_assistant_message", "") or "")

transcript_text = ""
if transcript_path:
    try:
        transcript_text = Path(transcript_path).expanduser().read_text(encoding="utf-8", errors="replace")
    except OSError:
        transcript_text = ""

combined = "\n".join(part for part in (transcript_text, last_assistant_message) if part)

deliver_match = re.search(r"\[DELIVER:([^\]]+)\]", combined)
attrs: dict[str, str] = {}
if deliver_match:
    for token in re.split(r"[,\s]+", deliver_match.group(1).strip()):
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        key = key.strip().lower().replace("-", "_")
        value = value.strip()
        if key and value:
            attrs[key] = value

task_id = (
    attrs.get("task_id")
    or attrs.get("task")
    or attrs.get("query_id")
    or ""
)
if not task_id:
    for pattern in (
        r"(?mi)^task_id:\s*([A-Za-z0-9._-]+)\s*$",
        r"(?mi)^task-id:\s*([A-Za-z0-9._-]+)\s*$",
        r"\b(MEMORY-QUERY-\d+-\d+)\b",
    ):
        match = re.search(pattern, combined)
        if match:
            task_id = match.group(1).strip()
            break

project = (
    attrs.get("project")
    or os.environ.get("CLAWSEAT_PROJECT", "")
    or os.environ.get("AGENTS_PROJECT", "")
)
if not project:
    match = re.search(r"(?mi)^project:\s*([A-Za-z0-9._-]+)\s*$", combined)
    if match:
        project = match.group(1).strip()

profile_path = attrs.get("profile", "")
if not profile_path and project:
    if dynamic_profile_path is not None:
        try:
            profile_path = str(dynamic_profile_path(project))
        except Exception:
            profile_path = str(Path.home() / ".agents" / "profiles" / f"{project}-profile-dynamic.toml")
    else:
        profile_path = str(Path.home() / ".agents" / "profiles" / f"{project}-profile-dynamic.toml")

target = (
    attrs.get("seat")
    or attrs.get("target")
    or attrs.get("to")
    or ""
)

clean_answer = last_assistant_message or combined
clean_answer = re.sub(r"\[CLEAR-REQUESTED\]", "", clean_answer)
clean_answer = re.sub(r"\[DELIVER:[^\]]+\]", "", clean_answer)
clean_answer = clean_answer.strip()
if not clean_answer:
    clean_answer = "Memory completed the requested query."

response = {
    "answer": clean_answer,
    "claims": [],
    "sources": [],
    "confidence": "medium",
}

emit("TRANSCRIPT_PATH", transcript_path)
emit("CLEAR_REQUESTED", "1" if "[CLEAR-REQUESTED]" in combined else "0")
emit("DELIVER_TARGET", target)
emit("DELIVER_TASK_ID", task_id)
emit("DELIVER_PROJECT", project)
emit("DELIVER_PROFILE", profile_path)
emit("DELIVER_RESPONSE_JSON", json.dumps(response, ensure_ascii=False))
PY
}

send_clear() {
  local candidates=()
  local candidate=""
  candidates+=("$SESSION_NAME")
  candidates+=("machine-memory-claude" "install-memory-claude" "memory-claude")
  for candidate in "${candidates[@]}"; do
    [[ -n "$candidate" ]] || continue
    sleep 0.5
    env -u TMUX tmux send-keys -t "=${candidate#=}" "/clear" Enter 2>/dev/null && return 0 || true
  done
  return 0
}

deliver_response() {
  local target="$1" task_id="$2" profile="$3" response_json="$4"
  local deliver_script="$CLAWSEAT_ROOT/core/skills/memory-oracle/scripts/memory_deliver.py"

  [[ -n "$target" ]] || return 0
  [[ -n "$task_id" ]] || {
    echo "[memory-hook] deliver_skipped: missing task_id for target '$target'" >&2
    return 0
  }
  [[ -n "$profile" ]] || {
    echo "[memory-hook] deliver_skipped: missing profile for target '$target' task '$task_id'" >&2
    return 0
  }

  "$PYTHON_BIN" "$deliver_script" \
    --profile "$profile" \
    --task-id "$task_id" \
    --target "$target" \
    --response-inline "$response_json" \
    --summary "Auto-delivered by memory Stop hook." \
    2>&1 | while IFS= read -r line; do
      echo "[memory-hook] $line" >&2
    done || true
  return 0
}

main() {
  local payload_json="" parsed=""
  payload_json="$(cat || true)"
  [[ -n "$payload_json" ]] || return 0

  parsed="$(parse_payload "$payload_json" || true)"
  [[ -n "$parsed" ]] || return 0
  eval "$parsed"

  if [[ "${CLEAR_REQUESTED:-0}" == "1" ]]; then
    send_clear || true
  fi

  if [[ -n "${DELIVER_TARGET:-}" ]]; then
    deliver_response \
      "${DELIVER_TARGET:-}" \
      "${DELIVER_TASK_ID:-}" \
      "${DELIVER_PROFILE:-}" \
      "${DELIVER_RESPONSE_JSON:-}" || true
  fi
}

main "$@" || true
exit 0
