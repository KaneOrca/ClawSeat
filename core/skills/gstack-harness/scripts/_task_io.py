"""Task dispatch/completion file operations — extracted from _common.py."""
from __future__ import annotations

from pathlib import Path

from _utils import CONSUMED_RE, TASK_ROW_RE, read_text, utc_now_iso, write_text


def build_notify_message(
    target_seat: str,
    todo_path: Path,
    task_id: str,
    *,
    source: str,
    reply_to: str,
) -> str:
    return (
        f"{task_id} assigned from {source} to {target_seat}. "
        f"Read {todo_path}. When complete, reply to {reply_to} via DELIVERY + notify."
    )


def build_completion_message(task_id: str, delivery_path: Path, *, source: str, target: str) -> str:
    return (
        f"{task_id} complete from {source} to {target}. "
        f"Read {delivery_path} and write a durable Consumed ACK when handled."
    )


def upsert_tasks_row(path: Path, *, task_id: str, title: str, owner: str, status: str, notes: str) -> None:
    existing = read_text(path).splitlines()
    if not existing:
        existing = [
            "# Tasks",
            "",
            "| ID | Title | Owner | Status | Notes |",
            "|----|-------|-------|--------|-------|",
        ]
    new_row = f"| {task_id} | {title} | {owner} | {status} | {notes} |"
    row_index = None
    table_end = None
    for idx, line in enumerate(existing):
        if TASK_ROW_RE.match(line):
            table_end = idx
            if line.startswith(f"| {task_id} |"):
                row_index = idx
        elif table_end is not None and line.strip() and not line.startswith("|"):
            break
    if row_index is not None:
        existing[row_index] = new_row
    else:
        insert_at = table_end + 1 if table_end is not None else len(existing)
        existing.insert(insert_at, new_row)
    write_text(path, "\n".join(existing))


def append_status_note(path: Path, note: str) -> None:
    timestamp = utc_now_iso()
    existing = read_text(path)
    block = f"- {timestamp}: {note}"
    if existing.strip():
        write_text(path, existing.rstrip() + "\n" + block)
    else:
        write_text(path, "# Status\n\n" + block)


def write_todo(
    path: Path,
    *,
    task_id: str,
    project: str,
    owner: str,
    status: str,
    title: str,
    objective: str,
    source: str,
    reply_to: str,
) -> None:
    text = (
        f"task_id: {task_id}\n"
        f"project: {project}\n"
        f"owner: {owner}\n"
        f"status: {status}\n"
        f"title: {title}\n\n"
        f"# Objective\n\n{objective.strip()}\n\n"
        f"# Dispatch\n\n"
        f"source: {source}\n"
        f"reply_to: {reply_to}\n"
        f"dispatched_at: {utc_now_iso()}\n"
    )
    write_text(path, text)


def write_delivery(
    path: Path,
    *,
    task_id: str,
    owner: str,
    target: str,
    title: str,
    summary: str,
    status: str,
    verdict: str | None = None,
    frontstage_disposition: str | None = None,
    user_summary: str | None = None,
    next_action: str | None = None,
) -> None:
    lines = [
        f"task_id: {task_id}",
        f"owner: {owner}",
        f"target: {target}",
        f"status: {status}",
        f"date: {utc_now_iso()}",
        "",
        f"# Delivery: {title}",
        "",
        "## Summary",
        "",
        summary.strip(),
    ]
    if verdict:
        lines.extend(["", f"Verdict: {verdict}"])
    if frontstage_disposition:
        lines.extend(["", f"FrontstageDisposition: {frontstage_disposition}"])
    if user_summary:
        lines.extend(["", f"UserSummary: {user_summary.strip()}"])
    if next_action:
        lines.extend(["", f"NextAction: {next_action.strip()}"])
    write_text(path, "\n".join(lines))


def append_consumed_ack(path: Path, *, task_id: str, source: str) -> str:
    existing = read_text(path)
    for line in existing.splitlines():
        match = CONSUMED_RE.match(line.strip())
        if not match:
            continue
        if match.group("task_id") == task_id and match.group("source") == source:
            return line.strip()
    ack_line = f"Consumed: {task_id} from {source} at {utc_now_iso()}"
    if existing.strip():
        write_text(path, existing.rstrip() + "\n" + ack_line)
    else:
        write_text(path, ack_line)
    return ack_line


def find_consumed_ack(path: Path, *, task_id: str, source: str) -> str | None:
    for line in read_text(path).splitlines():
        match = CONSUMED_RE.match(line.strip())
        if not match:
            continue
        if match.group("task_id") == task_id and match.group("source") == source:
            return line.strip()
    return None


def extract_canonical_verdict(path: Path) -> str | None:
    for line in read_text(path).splitlines():
        if line.startswith("Verdict: "):
            verdict = line.split("Verdict: ", 1)[1].strip()
            return verdict or None
    return None


def extract_prefixed_value(path: Path, prefix: str) -> str | None:
    for line in read_text(path).splitlines():
        if line.startswith(prefix):
            value = line.split(prefix, 1)[1].strip()
            return value or None
    return None


def file_declares_task(path: Path, task_id: str) -> bool:
    return path.exists() and f"task_id: {task_id}" in read_text(path)


def handoff_assigned(
    profile: object,
    *,
    task_id: str,
    source: str,
    target: str,
    kind: str = "dispatch",
    delivery_path: str | None = None,
) -> bool:
    todo_path = profile.todo_path(target)  # type: ignore[attr-defined]
    source_delivery_path = profile.delivery_path(source)  # type: ignore[attr-defined]
    if kind == "completion" or str(source_delivery_path) == str(delivery_path or ""):
        return file_declares_task(source_delivery_path, task_id)
    return file_declares_task(todo_path, task_id)
