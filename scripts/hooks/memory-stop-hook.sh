#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_CLAWSEAT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CLAWSEAT_ROOT="${CLAWSEAT_ROOT:-${CLAUDE_PROJECT_DIR:-$DEFAULT_CLAWSEAT_ROOT}}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
# v1 LEGACY (M4 remove): retired global memory session "machine-memory-claude".
LEGACY_GLOBAL_MEMORY_SESSION="$(printf '%s-%s-%s' machine memory claude)"
SESSION_NAME="${TMUX_SESSION_NAME:-$LEGACY_GLOBAL_MEMORY_SESSION}"

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

# [Memory] marker detection (BJ5 path preserved)
import re as _re
_footer_re = _re.compile(
    r'_via Memory @ (?P<ts>[^|]+) \| project=(?P<proj>[^|]+) \| session=(?P<sess>[^_]+?)(?:\s*_)',
    _re.DOTALL,
)
if _re.search(r'^\[Memory\]', last_assistant_message, _re.MULTILINE):
    _fm = _footer_re.search(last_assistant_message)
    if _fm:
        emit("MEMORY_PUSH", "1")
        emit("MEMORY_PUSH_TEXT", last_assistant_message)
        emit("MEMORY_PUSH_PROJECT", _fm.group("proj").strip())
    else:
        emit("MEMORY_PUSH", "0")
        emit("FEISHU_PUSH_MISSING_FOOTER", "1")
else:
    emit("MEMORY_PUSH", "0")
    emit("FEISHU_PUSH_MISSING_FOOTER", "0")

emit("DELIVER_TARGET", target)
emit("DELIVER_TASK_ID", task_id)
emit("DELIVER_PROJECT", project)
emit("DELIVER_PROFILE", profile_path)
emit("DELIVER_VERDICT", attrs.get("verdict", "") or "")
emit("DELIVER_SUMMARY", attrs.get("summary", "") or "")
emit("DELIVER_COMMIT", attrs.get("commit", "") or "")
emit("DELIVER_SWEEP", attrs.get("sweep", "") or "")
emit("DELIVER_TASK", attrs.get("task", "") or "")
emit("DELIVER_TITLE", attrs.get("title", "") or "")
emit("DELIVER_RESPONSE_JSON", json.dumps(response, ensure_ascii=False))
PY
}

tmux_session_name() {
  tmux display-message -p '#S' 2>/dev/null || echo unknown
}

send_clear() {
  local candidates=()
  local candidate=""
  candidates+=("$SESSION_NAME")
  candidates+=("$LEGACY_GLOBAL_MEMORY_SESSION" "install-memory-claude" "memory-claude")
  for candidate in "${candidates[@]}"; do
    [[ -n "$candidate" ]] || continue
    sleep 0.5
    env -u TMUX tmux send-keys -t "=${candidate#=}" "/clear" Enter 2>/dev/null && return 0 || true
  done
  return 0
}

read_feishu_group_id() {
  local project="$1"
  local binding_path="$HOME/.agents/tasks/${project}/PROJECT_BINDING.toml"
  "$PYTHON_BIN" - "$binding_path" <<'PY' || true
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

path = Path(sys.argv[1]).expanduser()
if not path.is_file():
    raise SystemExit(0)
try:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)

group_id = str(data.get("feishu_group_id") or "").strip()
if not group_id:
    bridge = data.get("bridge")
    if isinstance(bridge, dict):
        group_id = str(bridge.get("group_id") or "").strip()
print(group_id)
PY
}

send_feishu_message() {
  local project="$1" group_id="$2" message="$3"

  [[ -n "$group_id" ]] || { echo "[memory-hook] no group_id; skip feishu" >&2; return 0; }
  command -v lark-cli >/dev/null 2>&1 || { echo "[memory-hook] lark-cli missing; skip feishu" >&2; return 0; }

  if [[ -n "${CALLS_LOG:-}" ]]; then
    printf -- '--as user im +messages-send --chat-id %s --text %s\n' "$group_id" "$message" >> "$CALLS_LOG"
  fi
  LARK_CLI_NO_PROXY=1 lark-cli im +messages-send --as user \
    --chat-id "$group_id" --text "$message" 2>&1 | while IFS= read -r line; do
      echo "[memory-hook] $line" >&2
    done || true
}

format_feishu_message() {
  local response_json="$1"
  local task_id="$2" project="$3" session="$4" ts="$5"
  local verdict="$6" commit="$7" sweep="$8" summary="$9" title="${10}" task="${11}"

  FEISHU_HOOK_RESPONSE_JSON="$response_json" \
  FEISHU_HOOK_TASK_ID="$task_id" \
  FEISHU_HOOK_PROJECT="$project" \
  FEISHU_HOOK_SESSION="$session" \
  FEISHU_HOOK_TS="$ts" \
  FEISHU_HOOK_VERDICT="$verdict" \
  FEISHU_HOOK_COMMIT="$commit" \
  FEISHU_HOOK_SWEEP="$sweep" \
  FEISHU_HOOK_SUMMARY="$summary" \
  FEISHU_HOOK_TITLE="$title" \
  FEISHU_HOOK_TASK="$task" \
  "$PYTHON_BIN" - <<'PY'
import json
import os

raw_payload = os.environ.get("FEISHU_HOOK_RESPONSE_JSON", "").strip()
if not raw_payload:
    raise SystemExit(0)
payload = json.loads(raw_payload)

answer = str(payload.get("answer", "")).strip()
project = os.environ.get("FEISHU_HOOK_PROJECT", "unknown").strip() or "unknown"
session = os.environ.get("FEISHU_HOOK_SESSION", "unknown").strip() or "unknown"
hook_ts = os.environ.get("FEISHU_HOOK_TS", "")
task_id = os.environ.get("FEISHU_HOOK_TASK_ID", "").strip()
verdict = os.environ.get("FEISHU_HOOK_VERDICT", "").strip().upper()
commit = os.environ.get("FEISHU_HOOK_COMMIT", "").strip()
sweep = os.environ.get("FEISHU_HOOK_SWEEP", "").strip()
summary = os.environ.get("FEISHU_HOOK_SUMMARY", "").strip()
title = os.environ.get("FEISHU_HOOK_TITLE", "").strip()
task_hint = os.environ.get("FEISHU_HOOK_TASK", "").strip()

combined = " ".join(part for part in (answer, verdict, summary, title, task_hint, task_id) if part).upper()

def normalize_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line:
            lines.append(line)
    return lines

def clamp_lines(lines: list[str], max_lines: int = 4) -> list[str]:
    return lines[:max_lines]

if commit and task_id:
    headline_task = summary or task_hint or title or task_id or "任务"
    headline = f"[Memory] 📋 {headline_task}已完成"
    result_line = summary or task_hint or title or task_id or "任务已完成"
    if sweep:
        result_line = f"{result_line} | sweep {sweep}"
    body = [f"result={result_line}"]
    if task_id:
        body.append(f"task_id={task_id}")
    if commit:
        body.append(f"commit={commit}")
elif "BLOCKED" in combined or " FAIL" in combined:
    title_text = summary or title or task_hint or task_id or "任务"
    headline = f"[Memory] 🔴 需要决策:{title_text}"
    desc = next((line for line in normalize_lines(answer) if line), "请快速确认任务方向")
    options = []
    for line in normalize_lines(answer):
        if len(options) >= 2:
            break
        if line.startswith("A.") or line.startswith("B.") or line.startswith("a.") or line.startswith("b."):
            options.append(line.replace(" a.", "A.").replace(" b.", "B."))
    if len(options) < 2:
        options = ["A. 继续执行", "B. 人工确认"]
    body = [desc, options[0], options[1]]
else:
    # Pass/ready as success state unless explicitly blocked.
    pass_like = ("PASS" in combined or " READY" in combined or
                 combined.endswith("READY") or combined.startswith("READY") or
                 "PHASE=READY" in combined)
    headline_task = summary or task_hint or title or task_id or "任务"
    if pass_like and not headline_task:
        headline_task = "任务完成"
    headline = f"[Memory] ✅ {headline_task}"
    body = []
    if task_id:
        body.append(f"task_id={task_id}")
    if summary:
        body.append(f"summary={summary}")
    if verdict:
        body.append(f"verdict={verdict}")
    elif pass_like:
        body.append("verdict=PASS")
    else:
        body.append("verdict=UNKNOWN")
    if project:
        body.append(f"project={project}")
    if sweep:
        body.append(f"sweep {sweep}")
    body = clamp_lines(body)

legacy_footer = f"_via Memory @ {hook_ts} | project={project} | session={session}_"
signature = f"— Memory | {project} | {hook_ts}"
payload["answer"] = (
    f"{headline}\n\n"
    + "\n".join(clamp_lines(body, 4))
    + "\n\n"
    + legacy_footer
    + "\n"
    + signature
)
print(json.dumps(payload, ensure_ascii=False))
print("::FEISHU::")
print(payload["answer"])
PY
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
  local payload_json="" parsed="" hook_project="" hook_session="" hook_ts=""
  local feishu_group_id="" feishu_msg="" formatted_payload=""
  payload_json="$(cat || true)"
  [[ -n "$payload_json" ]] || return 0

  parsed="$(parse_payload "$payload_json" || true)"
  [[ -n "$parsed" ]] || return 0
  eval "$parsed"

  hook_project="${DELIVER_PROJECT:-${CLAWSEAT_PROJECT:-${AGENTS_PROJECT:-unknown}}}"
  [[ -n "$hook_project" ]] || hook_project="unknown"
  hook_session="$(tmux_session_name)"
  hook_ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if [[ -n "${DELIVER_RESPONSE_JSON:-}" ]]; then
    formatted_payload="$(
      format_feishu_message \
        "${DELIVER_RESPONSE_JSON}" \
        "${DELIVER_TASK_ID:-}" \
        "$hook_project" \
        "$hook_session" \
        "$hook_ts" \
        "${DELIVER_VERDICT:-}" \
        "${DELIVER_COMMIT:-}" \
        "${DELIVER_SWEEP:-}" \
        "${DELIVER_SUMMARY:-}" \
        "${DELIVER_TITLE:-}" \
        "${DELIVER_TASK:-}"
    )"

    if [[ "$formatted_payload" == *$'\n::FEISHU::\n'* ]]; then
      DELIVER_RESPONSE_JSON="${formatted_payload%%$'\n::FEISHU::\n'*}"
      feishu_msg="${formatted_payload#*::FEISHU::$'\n'}"
    else
      DELIVER_RESPONSE_JSON="$formatted_payload"
      feishu_msg="$(printf '%s' "$DELIVER_RESPONSE_JSON" | "$PYTHON_BIN" -c 'import json,sys; payload=json.load(sys.stdin); print(payload.get("answer",""))')"
    fi
  fi

  if [[ "${CLEAR_REQUESTED:-0}" == "1" ]]; then
    send_clear || true
  fi

  # [Memory] marker direct push (BJ5 path)
  if [[ "${FEISHU_PUSH_MISSING_FOOTER:-0}" == "1" ]]; then
    echo "[memory-hook] [Memory] message missing footer, skip" >&2
  fi
  if [[ "${MEMORY_PUSH:-0}" == "1" && "${CLAWSEAT_FEISHU_ENABLED:-1}" != "0" ]]; then
    local _mp_project="${MEMORY_PUSH_PROJECT:-$hook_project}"
    feishu_group_id="$(read_feishu_group_id "$_mp_project")"
    if [[ -n "$feishu_group_id" ]]; then
      send_feishu_message "$_mp_project" "$feishu_group_id" "${MEMORY_PUSH_TEXT:-}" || true
    fi
  fi

  if [[ -n "${DELIVER_TARGET:-}" ]]; then
    deliver_response \
      "${DELIVER_TARGET:-}" \
      "${DELIVER_TASK_ID:-}" \
      "${DELIVER_PROFILE:-}" \
      "${DELIVER_RESPONSE_JSON:-}" || true
    if [[ "${CLAWSEAT_FEISHU_ENABLED:-1}" != "0" && "$hook_project" != "unknown" ]]; then
      feishu_group_id="$(read_feishu_group_id "$hook_project")"
      if [[ -n "$feishu_group_id" && -n "$feishu_msg" ]]; then
        send_feishu_message "$hook_project" "$feishu_group_id" "$feishu_msg" || true
      fi
    fi
  fi
}

main "$@" || true
exit 0
