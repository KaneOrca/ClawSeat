"""Task dispatch/completion file operations — extracted from _common.py."""
from __future__ import annotations

import re
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


def build_completion_message(
    task_id: str,
    delivery_path: Path,
    *,
    source: str,
    target: str,
    user_summary: str | None = None,
) -> str:
    base = (
        f"{task_id} complete from {source} to {target}. "
        f"Read {delivery_path} and write a durable Consumed ACK when handled."
    )
    if user_summary and user_summary.strip():
        return f"{base} UserSummary: {user_summary.strip()}"
    return base


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
    if kind == "completion":
        candidate = Path(delivery_path) if delivery_path else source_delivery_path
        return file_declares_task(candidate, task_id)
    if str(source_delivery_path) == str(delivery_path or ""):
        return file_declares_task(source_delivery_path, task_id)
    return file_declares_task(todo_path, task_id)


def append_task_to_queue(
    path: Path,
    *,
    task_id: str,
    project: str,
    owner: str,
    title: str,
    objective: str,
    source: str,
    reply_to: str,
    skill_refs: list[str] | None = None,
    task_type: str = "unspecified",
    review_required: bool = False,
) -> None:
    existing = read_text(path)

    # Backward compat: old format (task_id: header) auto-wrapped as queue head.
    # Special case: task_id: null is a bootstrap placeholder — discard it entirely.
    if existing.strip() and existing.lstrip().startswith("task_id:"):
        old_task_id_match = re.search(r"^task_id: (.+)$", existing, re.MULTILINE)
        old_task_id = old_task_id_match.group(1).strip() if old_task_id_match else "legacy"
        if old_task_id == "null":
            # Bootstrap placeholder — replace with empty queue
            existing = ""
        else:
            existing = f"# Queue: {owner}\n\n## [pending] {old_task_id}\n{existing.strip()}\n"

    has_active = bool(re.search(r"^## \[(pending|queued)\]", existing, re.MULTILINE))
    status = "queued" if has_active else "pending"

    entry_lines = [
        f"## [{status}] {task_id}",
        f"task_id: {task_id}",
        f"title: {title}",
        f"task_type: {task_type}",
        f"review_required: {'true' if review_required else 'false'}",
        f"source: {source}",
        f"reply_to: {reply_to}",
        f"dispatched_at: {utc_now_iso()}",
        "",
        "### Objective",
        "",
        objective.strip(),
    ]
    if skill_refs:
        entry_lines += ["", "### Skill Refs", ""] + [f"- {ref}" for ref in skill_refs]

    entry = "\n".join(entry_lines)

    if not existing.strip():
        content = f"# Queue: {owner}\n\n{entry}\n"
    elif "\n# Completed" in existing:
        idx = existing.index("\n# Completed")
        content = existing[:idx].rstrip() + f"\n\n---\n\n{entry}\n" + existing[idx:]
    else:
        content = existing.rstrip() + f"\n\n---\n\n{entry}\n"

    write_text(path, content)


def complete_task_in_queue(
    path: Path,
    *,
    task_id: str,
    summary: str,
) -> str | None:
    """Mark task_id as [completed], activate next [queued] task.
    Returns next task_id if one was activated, else None."""
    content = read_text(path)
    if not content.strip():
        return None

    content, n = re.subn(
        rf"^## \[pending\] {re.escape(task_id)}",
        f"## [completed] {task_id}",
        content,
        flags=re.MULTILINE,
    )
    if n == 0:
        return None

    next_task_id = None
    m = re.search(r"^## \[queued\] (\S+)", content, re.MULTILINE)
    if m:
        next_task_id = m.group(1)
        content = content[: m.start()] + f"## [pending] {next_task_id}" + content[m.end():]

    completed_line = f"- [{utc_now_iso()[:10]}] {task_id} — {summary}"
    if "# Completed" not in content:
        content = content.rstrip() + f"\n\n# Completed\n\n{completed_line}\n"
    else:
        content = content.replace("# Completed\n", f"# Completed\n{completed_line}\n", 1)

    write_text(path, content)
    return next_task_id
