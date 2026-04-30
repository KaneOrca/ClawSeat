from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


VALID_STATUSES = {"pending", "in_progress", "done", "blocked"}
ALLOWED_TRANSITIONS = {
    "pending": {"in_progress"},
    "in_progress": {"done", "blocked"},
}
DISPATCH_LOG_HEADER = "## dispatch log (append-only, last 20)"
DISPATCH_LOG_COMMENT = (
    "<!-- dispatch_task.py / complete_handoff.py append entries here. "
    "Do not delete this section. -->"
)


@dataclass
class WorkflowStep:
    name: str
    owner_role: str = ""
    status: str = "pending"
    prereq: list[str] = field(default_factory=list)
    start: int = 0
    end: int = 0
    status_line: int = -1


class TaskCommandError(RuntimeError):
    pass


def _task_id_ok(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_.-]+", value or ""))


def tasks_root(home: Path | None = None) -> Path:
    root = home if home is not None else Path(os.environ.get("CLAWSEAT_REAL_HOME", str(Path.home()))).expanduser()
    return root / ".agents" / "tasks"


def project_tasks_dir(project: str, *, home: Path | None = None) -> Path:
    return tasks_root(home) / project


def task_dir(project: str, task_id: str, *, home: Path | None = None) -> Path:
    return project_tasks_dir(project, home=home) / task_id


def _workflow_template(task_id: str, template: str) -> str:
    return "\n".join(
        [
            f"# Workflow: {task_id}",
            "",
            f"workflow_template: {template or 'blank'}",
            "",
            "steps: []",
            "",
        ]
    )


def _status_template(task_id: str) -> str:
    return (
        f"# Status: {task_id}\n\n"
        "status: pending\n\n"
        f"{DISPATCH_LOG_HEADER}\n\n"
        f"{DISPATCH_LOG_COMMENT}\n"
    )


def _ensure_status_dispatch_log_section(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if DISPATCH_LOG_HEADER in text:
        return
    path.write_text(
        text.rstrip() + f"\n\n{DISPATCH_LOG_HEADER}\n\n{DISPATCH_LOG_COMMENT}\n",
        encoding="utf-8",
    )


def create_task(args: Any) -> int:
    task_id = str(args.task_id)
    project = str(args.project)
    if not _task_id_ok(task_id):
        raise TaskCommandError(f"invalid task_id: {task_id}")
    root = task_dir(project, task_id)
    root.mkdir(parents=True, exist_ok=True)
    workflow = root / "workflow.md"
    status = root / "STATUS.md"
    if not workflow.exists():
        workflow.write_text(_workflow_template(task_id, str(getattr(args, "workflow_template", "") or "")), encoding="utf-8")
    if not status.exists():
        status.write_text(_status_template(task_id), encoding="utf-8")
    else:
        _ensure_status_dispatch_log_section(status)
    print(root)
    return 0


def _parse_list(value: str) -> list[str]:
    raw = value.strip()
    if not raw or raw in {"[]", "null", "None"}:
        return []
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return [item.strip().strip("\"'") for item in raw.split(",") if item.strip().strip("\"'")]


def parse_workflow(text: str) -> list[WorkflowStep]:
    lines = text.splitlines()
    starts: list[tuple[str, int]] = []
    for index, line in enumerate(lines):
        match = re.match(r"^##\s+Step\s+\d+\s*:\s*(.+?)\s*$", line)
        if match:
            starts.append((match.group(1).strip(), index))

    steps: list[WorkflowStep] = []
    for offset, (name, start) in enumerate(starts):
        end = starts[offset + 1][1] if offset + 1 < len(starts) else len(lines)
        step = WorkflowStep(name=name, start=start, end=end)
        for line_no in range(start + 1, end):
            line = lines[line_no]
            match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*?)\s*$", line)
            if not match:
                continue
            key, value = match.group(1), match.group(2)
            if key == "owner_role":
                step.owner_role = value.strip().strip("\"'")
            elif key == "status":
                step.status = value.strip().strip("\"'")
                step.status_line = line_no
            elif key == "prereq":
                step.prereq = _parse_list(value)
        steps.append(step)
    return steps


def _ready_steps(path: Path, owner_role: str) -> list[WorkflowStep]:
    text = path.read_text(encoding="utf-8")
    steps = parse_workflow(text)
    status_by_name = {step.name: step.status for step in steps}
    ready: list[WorkflowStep] = []
    for step in steps:
        if step.owner_role != owner_role or step.status != "pending":
            continue
        if all(status_by_name.get(name) == "done" for name in step.prereq):
            ready.append(step)
    return ready


def list_pending(args: Any) -> int:
    project = str(args.project)
    owner_role = str(args.owner_role)
    root = project_tasks_dir(project)
    if not root.exists():
        return 0
    for workflow in sorted(root.glob("*/workflow.md")):
        task_id = workflow.parent.name
        for step in _ready_steps(workflow, owner_role):
            print(f"{task_id}\t{step.name}")
    return 0


def _atomic_write(path: Path, content: str) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def update_status(args: Any) -> int:
    task_id = str(args.task_id)
    project = str(args.project)
    step_name = str(args.step_name)
    new_status = str(args.status)
    if new_status not in VALID_STATUSES:
        raise TaskCommandError(f"invalid status: {new_status}")

    workflow = task_dir(project, task_id) / "workflow.md"
    if not workflow.exists():
        raise TaskCommandError(f"workflow not found: {workflow}")

    text = workflow.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    steps = parse_workflow(text)
    matches = [step for step in steps if step.name == step_name]
    if not matches:
        raise TaskCommandError(f"step not found: {step_name}")
    if len(matches) > 1:
        raise TaskCommandError(f"ambiguous step name: {step_name}")
    step = matches[0]
    if step.status_line < 0:
        raise TaskCommandError(f"step has no status field: {step_name}")
    allowed = ALLOWED_TRANSITIONS.get(step.status, set())
    if new_status not in allowed:
        raise TaskCommandError(f"invalid transition: {step.status} -> {new_status}")

    newline = "\n" if lines[step.status_line].endswith("\n") else ""
    indent = re.match(r"^(\s*)", lines[step.status_line]).group(1)
    lines[step.status_line] = f"{indent}status: {new_status}{newline}"
    _atomic_write(workflow, "".join(lines))
    print(f"{task_id}\t{step_name}\t{new_status}")
    return 0
