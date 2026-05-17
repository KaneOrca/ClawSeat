#!/usr/bin/env python3
"""ClawSeat v3 brief subcommand.

Memory writes brief markdown + appends task_created event to per-team queue.
Planner reads queue via 7-step loop (see core/lib/queue_io.py).

Subcommands:
  queue    Write brief file + append task_created event
  list     Show pending tasks for a team
  claim    Planner claims a pending task
  show     Show current state of a task_id

Phase 1 minimal scope: standalone CLI. Phase 2 integrates into agent_admin.py
PARSER_HOOKS dispatch.

See spec §4.2 (brief schema) + §4.3 (queue events).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CORE_LIB = _REPO_ROOT / "core" / "lib"
if str(_CORE_LIB) not in sys.path:
    sys.path.insert(0, str(_CORE_LIB))

from queue_io import (  # noqa: E402
    QueueError,
    append_event,
    query_pending,
    read_current_state,
)
from acceptance_criteria import (  # noqa: E402
    SCOPE_GUARD_PORTABLE_TEMPLATE,
    brief_acceptance_ready,
    load_brief_frontmatter,
    load_brief_frontmatter_text,
)
from profile_loader_v3 import ProfileV3Error, load_profile_v3  # noqa: E402
from real_home import real_user_home  # noqa: E402

try:
    import yaml  # type: ignore
except ImportError as _exc:  # pragma: no cover
    raise SystemExit("PyYAML required for agent_admin_brief")


class _QuotedStrDumper(yaml.SafeDumper):
    """SafeDumper that single-quotes all str scalars.

    Why: default safe_dump emits plain ISO datetime strings, which round-trip
    through safe_load become datetime objects. jsonschema then rejects them
    because schema declares string. Quoting forces unambiguous str on load.
    Fix #B (post-review retest).
    """


def _quoted_str_representer(dumper, data):  # type: ignore[no-untyped-def]
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="'")


_QuotedStrDumper.add_representer(str, _quoted_str_representer)

# Post-review fix #4: input validation to prevent path traversal.
# Patterns must mirror the schemas: project/team match project_toml_v3.schema
# (^[a-z0-9][a-z0-9-]*$) and task_id matches brief.schema (^[A-Za-z0-9][A-Za-z0-9_.-]*$).
_PROJECT_TEAM_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class InputValidationError(RuntimeError):
    pass


class WakeHookError(RuntimeError):
    def __init__(self, reason: str, *, target: str = "") -> None:
        super().__init__(reason)
        self.target = target


def _validate_identifier(value: str, kind: str) -> None:
    pattern = _TASK_ID_PATTERN if kind == "task_id" else _PROJECT_TEAM_PATTERN
    if not pattern.match(value or ""):
        raise InputValidationError(
            f"invalid {kind}: {value!r} (must match {pattern.pattern})"
        )
    if ".." in value or "/" in value or "\\" in value:
        raise InputValidationError(
            f"invalid {kind}: {value!r} contains path-traversal characters"
        )


def _validate_cli_inputs(project: str, team: str, task_id: str | None = None) -> None:
    _validate_identifier(project, "project")
    _validate_identifier(team, "team")
    if task_id is not None:
        _validate_identifier(task_id, "task_id")


def _validate_external_brief_content(
    brief_text: str, source_path: str, project: str, team: str, task_id: str
) -> None:
    """Validate caller-supplied brief content (--brief-content-file).

    Post-retest #2: parse frontmatter, verify schema + CLI match. Raise
    InputValidationError on any failure.
    """
    if not brief_text.startswith("---\n"):
        raise InputValidationError(
            f"{source_path}: brief content must start with '---' frontmatter"
        )
    end = brief_text.find("\n---\n", 4)
    if end == -1:
        end = brief_text.find("\n---", 4)
    if end == -1:
        raise InputValidationError(f"{source_path}: unterminated frontmatter")

    try:
        data = yaml.safe_load(brief_text[4:end])
    except Exception as exc:  # noqa: BLE001
        raise InputValidationError(f"{source_path}: frontmatter parse error: {exc}")
    if not isinstance(data, dict):
        raise InputValidationError(f"{source_path}: frontmatter must be a mapping")

    # CLI match
    for field_name, expected in (("task_id", task_id), ("project", project), ("team", team)):
        actual = data.get(field_name)
        if actual is None:
            raise InputValidationError(
                f"{source_path}: brief missing required field {field_name!r}"
            )
        if str(actual) != str(expected):
            raise InputValidationError(
                f"{source_path}: brief.{field_name}={actual!r} mismatches CLI {field_name}={expected!r}"
            )

    # Schema minItems sanity (cheap fallback even without jsonschema)
    seats = data.get("seats_required")
    if not isinstance(seats, list) or not seats:
        raise InputValidationError(
            f"{source_path}: brief.seats_required must have minItems 1"
        )
    ac = data.get("acceptance_criteria") or {}
    mech = ac.get("mechanical")
    if not isinstance(mech, list) or not mech:
        raise InputValidationError(
            f"{source_path}: brief.acceptance_criteria.mechanical must have minItems 1"
        )


def _agents_root() -> Path:
    return real_user_home() / ".agents"


def _project_team_root(project: str, team: str) -> Path:
    return _agents_root() / "tasks" / project / team


def _queue_path(project: str, team: str) -> Path:
    return _project_team_root(project, team) / "tasks.queue.jsonl"


def _profile_path(project: str) -> Path:
    return _agents_root() / "profiles" / f"{project}-profile-dynamic.toml"


def _send_script_path() -> Path:
    override = os.environ.get("CLAWSEAT_BRIEF_WAKE_SEND_SCRIPT", "").strip()
    if override:
        return Path(override)
    return _REPO_ROOT / "core" / "shell-scripts" / "send-and-verify.sh"


def _one_line_detail(text: str, *, limit: int = 240) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) > limit:
        return compact[: limit - 3] + "..."
    return compact or "unknown"


def _planner_seat_for_team(project: str, team: str) -> str:
    try:
        profile = load_profile_v3(_profile_path(project))
        team_name = team if profile.is_multi() else "default"
        seats = profile.seats_of(team_name)
    except ProfileV3Error as exc:
        raise WakeHookError(f"profile resolution failed: {exc}") from exc

    planners = [seat for seat in seats if profile.seat_roles.get(seat) == "planner"]
    if not planners:
        raise WakeHookError(f"team {team!r} has no planner seat")
    if len(planners) > 1:
        raise WakeHookError(f"team {team!r} has multiple planner seats: {planners}")
    return planners[0]


def _wake_team_planner(project: str, team: str, task_id: str) -> str:
    target = _planner_seat_for_team(project, team)
    send_script = _send_script_path()
    if not send_script.exists():
        raise WakeHookError(f"send script not found: {send_script}", target=target)

    message = (
        f"[QUEUE-WAKE] {project}/{team} {task_id}; "
        "run brief claim, then plan workflow."
    )
    result = subprocess.run(
        ["bash", str(send_script), "--project", project, target, message],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = _one_line_detail(result.stderr or result.stdout or f"exit {result.returncode}")
        raise WakeHookError(detail, target=target)
    return target


def _list_teams(project: str) -> list[str]:
    """Return all team subdirs under tasks/<project>/ that have a queue file."""
    proj_root = _agents_root() / "tasks" / project
    if not proj_root.exists():
        return []
    teams = []
    for child in proj_root.iterdir():
        if not child.is_dir():
            continue
        if (child / "tasks.queue.jsonl").exists() or (child / "brief").exists():
            teams.append(child.name)
    return sorted(teams)


def _resolve_cross_team_upstream(
    project: str, current_team: str, task_id: str
) -> tuple[str, str] | None:
    """Post-retest #5: locate a task_id across ALL teams in the project.

    Returns (team, status) if found, None otherwise. Used to evaluate
    cross-team depends_on without forcing planner to know which team owns
    each upstream task.
    """
    teams = _list_teams(project)
    for team in teams:
        if team == current_team:
            continue
        q = _queue_path(project, team)
        if not q.exists():
            continue
        state = read_current_state(q)
        if task_id in state:
            return team, state[task_id].status
    return None


def _unmet_dependencies(
    project: str,
    team: str,
    state: dict,
    depends_on: list[str],
) -> list[str]:
    unmet: list[str] = []
    for upstream_id in depends_on:
        up = state.get(upstream_id)
        if up is not None:
            if up.status != "task_done":
                unmet.append(upstream_id)
            continue
        cross = _resolve_cross_team_upstream(project, team, upstream_id)
        if cross is None or cross[1] != "task_done":
            unmet.append(upstream_id)
    return unmet


def _brief_path(project: str, team: str, task_id: str) -> Path:
    return _project_team_root(project, team) / "brief" / f"{task_id}.md"


def _resolve_task_brief_path(project: str, team: str, brief_path: str | None) -> Path | None:
    if not brief_path:
        return None
    path = Path(brief_path)
    if path.is_absolute():
        return path
    agents_relative = _agents_root() / path
    team_relative = _project_team_root(project, team) / path
    if agents_relative.exists() or not team_relative.exists():
        return agents_relative
    return team_relative


def _brief_acceptance_ready_for_task(project: str, team: str, brief_path: str | None) -> tuple[bool, str]:
    resolved = _resolve_task_brief_path(project, team, brief_path)
    if resolved is None:
        return False, "brief_path missing"
    if not resolved.exists():
        return False, f"brief not found: {resolved}"
    try:
        return brief_acceptance_ready(load_brief_frontmatter(resolved))
    except Exception as exc:  # noqa: BLE001
        return False, f"brief acceptance parse failed: {exc}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _default_scope_guard_command(repo_root: Path | None = None) -> str:
    """Return the portable scope-guard mechanical command for a generated brief skeleton.

    Uses SCOPE_GUARD_PORTABLE_TEMPLATE with a standard forbidden-file spec and
    the supplied (or auto-detected) repo_root. Produced command is shell-safe:
    explicit origin/main...HEAD range and python3 filtering (no pipe-negation).
    """
    root = str(repo_root or _REPO_ROOT.parent)
    forbidden_spec = (
        "[('tasks.queue.jsonl','/handoffs/'),('WORKSPACE_CONTRACT.toml',''),"
        "('project.toml',''),('TEAM_OWNERSHIP.md',''),('QUALITY.md','quality-docs/')]"
    )
    return SCOPE_GUARD_PORTABLE_TEMPLATE.format(
        repo_root=root,
        forbidden_spec=forbidden_spec,
    )


def cmd_queue(args: argparse.Namespace) -> int:
    """Append task_created event + write brief markdown skeleton.

    Post-review fixes:
    - #4 input validation (project/team/task_id pattern + path-traversal block)
    - #5 atomic non-destructive write (temp file → rename only after append)
    - #7 schema-valid skeleton (seats_required + mechanical have ≥1 item)
    """
    try:
        _validate_cli_inputs(args.project, args.team, args.task_id)
    except InputValidationError as exc:
        print(f"input validation failed: {exc}", file=sys.stderr)
        return 2

    project = args.project
    team = args.team
    task_id = args.task_id

    brief = _brief_path(project, team, task_id)
    brief.parent.mkdir(parents=True, exist_ok=True)

    # Pre-check overwrite policy BEFORE writing anything (Fix #5)
    brief_pre_exists = brief.exists()
    if brief_pre_exists and not args.force:
        print(f"refusing to overwrite existing brief: {brief}", file=sys.stderr)
        return 2

    if args.brief_content_file:
        brief_text = Path(args.brief_content_file).read_text(encoding="utf-8")
        # Post-retest #2: when caller supplies content, still validate it
        # both against brief schema (minItems etc.) AND against CLI args
        # (no mismatched task_id/project/team).
        try:
            _validate_external_brief_content(
                brief_text, args.brief_content_file, project, team, task_id
            )
        except InputValidationError as exc:
            print(f"brief content validation failed: {exc}", file=sys.stderr)
            return 2
    else:
        # Fix #B (post-review retest): build dict + yaml.safe_dump to handle
        # quotes / special chars / non-string scalars correctly. Also forces
        # created to be a string (default yaml.safe_dump would emit ISO without
        # quotes which PyYAML on load parses as datetime).
        frontmatter = {
            "task_id": str(task_id),
            "project": str(project),
            "team": str(team),
            "created": _utc_now(),
            "created_by": "memory",
            "objective": str(args.objective),
            "depends_on": list(args.depends_on or []),
            "acceptance_criteria": {
                "mechanical": [
                    _default_scope_guard_command(),
                ],
                "reviewer": [],
                "operator": [],
            },
            "seats_required": list(args.seats_required or ["builder"]),
            "fuzz_required": False,
            "priority": "P2",
            "notify_on_completion": ["memory"],
        }
        # default_style='"' would force JSON-quoting every string. We instead
        # use default mode but specify default_flow_style=False + allow_unicode
        # so strings with quotes/colons get properly escaped, and `created`
        # stays a quoted string (because we passed it as a Python str).
        # Explicit-quoting `created` removes ambiguity on round-trip parse.
        yaml_body = yaml.dump(
            frontmatter,
            Dumper=_QuotedStrDumper,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=4096,
        )
        brief_text = (
            "---\n"
            + yaml_body
            + "---\n\n"
            "# Brief 正文\n\n"
            "## 目标\n\n"
            + str(args.objective).strip()
            + "\n\n"
            "## 验收说明\n\n"
            "<待 memory 补全 mechanical/reviewer/operator 路由项>\n"
        )

    try:
        acceptance_ready, acceptance_reason = brief_acceptance_ready(
            load_brief_frontmatter_text(brief_text, str(brief))
        )
    except Exception as exc:  # noqa: BLE001
        acceptance_ready = False
        acceptance_reason = f"brief acceptance parse failed: {exc}"

    # Fix #5: write to temp file, atomic rename ONLY after append succeeds.
    # If append fails, we unlink the temp file and leave any pre-existing brief alone.
    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=f".{task_id}.", suffix=".tmp", dir=str(brief.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            fh.write(brief_text)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    queue = _queue_path(project, team)
    event = {
        "event_type": "task_created",
        "actor": "memory",
        "task_id": task_id,
        "brief_path": str(brief.relative_to(_agents_root())),
        "parent_task_id": args.parent_task_id,
        "depends_on": args.depends_on or [],
    }
    try:
        result = append_event(queue, event)
    except QueueError as exc:
        # Fix #5: never unlink pre-existing brief on append failure.
        tmp_path.unlink(missing_ok=True)
        print(f"queue append failed: {exc}", file=sys.stderr)
        return 1

    # Append succeeded; atomic rename temp → final.
    os.replace(tmp_path, brief)

    print(f"queued task {task_id}")
    print(f"  brief: {brief}")
    print(f"  queue: {queue}")
    print(f"  seq:   {result['seq']}")
    if args.no_wake:
        print("WAKE_SKIPPED (--no-wake)")
        return 0
    if not acceptance_ready:
        print(f"WAKE_DEFERRED reason={acceptance_reason}")
        return 0
    # Defer gracefully when no profile is configured yet; HOOK_WAKE_FAILED is
    # reserved for delivery failures on an otherwise-ready profile.
    profile_path = _profile_path(project)
    if not profile_path.exists():
        print(f"WAKE_DEFERRED reason=profile_not_found:{profile_path}")
        return 0
    try:
        target = _wake_team_planner(project, team, task_id)
    except WakeHookError as exc:
        target = exc.target or "<unresolved>"
        print(f"HOOK_WAKE_FAILED target={target} reason={exc}", file=sys.stderr)
        return 3
    print(f"WAKE_OK target={target}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """Show pending tasks for a team. Default: pending only; --all shows all."""
    try:
        _validate_cli_inputs(args.project, args.team)
    except InputValidationError as exc:
        print(f"input validation failed: {exc}", file=sys.stderr)
        return 2
    queue = _queue_path(args.project, args.team)
    if not queue.exists():
        print(f"queue not initialized: {queue}", file=sys.stderr)
        return 0

    state = read_current_state(queue)
    if args.all:
        rows = list(state.values())
    else:
        rows = [ts for ts in state.values() if ts.status == "task_created"]
    rows.sort(key=lambda ts: ts.last_seq)

    if not rows:
        print(f"no {'tasks' if args.all else 'pending tasks'} in {args.project}/{args.team}")
        return 0

    for ts in rows:
        depends = ",".join(ts.depends_on) if ts.depends_on else "-"
        print(f"{ts.task_id}\t{ts.status}\t{ts.actor}\t{ts.last_event_ts}\tdepends_on={depends}")
    return 0


def cmd_claim(args: argparse.Namespace) -> int:
    """Planner claims a pending task. Appends task_claimed event.

    Checks depends_on first; if unmet, writes task_waiting_for instead.
    (Fix #6: task_created -> task_waiting_for transition allowed by queue_io
    VALID_TRANSITIONS as of v3 Phase 1 post-review.)
    """
    try:
        _validate_cli_inputs(args.project, args.team, args.task_id)
    except InputValidationError as exc:
        print(f"input validation failed: {exc}", file=sys.stderr)
        return 2
    queue = _queue_path(args.project, args.team)
    state = read_current_state(queue)
    ts = state.get(args.task_id)
    if ts is None:
        print(f"task_id {args.task_id!r} not in queue", file=sys.stderr)
        return 2
    # Fix #A (post-review retest): allow retry from task_waiting_for state.
    # State machine permits task_waiting_for → task_claimed when deps now met,
    # or task_waiting_for → task_waiting_for if still blocked.
    if ts.status not in ("task_created", "task_waiting_for"):
        print(
            f"task_id {args.task_id!r} is in state {ts.status!r}, not claimable",
            file=sys.stderr,
        )
        return 2

    acceptance_ready, acceptance_reason = _brief_acceptance_ready_for_task(
        args.project, args.team, ts.brief_path
    )
    if not acceptance_ready:
        event = {
            "event_type": "task_waiting_for",
            "actor": args.actor,
            "task_id": args.task_id,
            "waiting_for": "acceptance_criteria",
        }
        try:
            append_event(queue, event)
        except QueueError as exc:
            print(f"waiting_for append failed: {exc}", file=sys.stderr)
            return 1
        print(f"task {args.task_id} blocked on acceptance_criteria: {acceptance_reason}")
        return 3

    # Post-retest #5: check depends_on across ALL teams in the project.
    # Local queue checked first; if absent, fall through to cross-team scan.
    unmet = _unmet_dependencies(args.project, args.team, state, ts.depends_on)

    if unmet:
        for up_id in unmet:
            event = {
                "event_type": "task_waiting_for",
                "actor": args.actor,
                "task_id": args.task_id,
                "waiting_for": up_id,
            }
            try:
                append_event(queue, event)
            except QueueError as exc:
                print(f"waiting_for append failed: {exc}", file=sys.stderr)
                return 1
        print(f"task {args.task_id} blocked on upstream: {unmet}")
        return 3

    event = {
        "event_type": "task_claimed",
        "actor": args.actor,
        "task_id": args.task_id,
    }
    try:
        result = append_event(queue, event)
    except QueueError as exc:
        print(f"claim append failed: {exc}", file=sys.stderr)
        return 1
    print(f"claimed {args.task_id} (seq {result['seq']})")
    print(f"  brief: {ts.brief_path}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    try:
        _validate_cli_inputs(args.project, args.team, args.task_id)
    except InputValidationError as exc:
        print(f"input validation failed: {exc}", file=sys.stderr)
        return 2
    queue = _queue_path(args.project, args.team)
    state = read_current_state(queue)
    ts = state.get(args.task_id)
    if ts is None:
        print(f"task_id {args.task_id!r} not in queue", file=sys.stderr)
        return 2
    print(json.dumps(
        {
            "task_id": ts.task_id,
            "status": ts.status,
            "last_seq": ts.last_seq,
            "last_event_ts": ts.last_event_ts,
            "actor": ts.actor,
            "brief_path": ts.brief_path,
            "depends_on": ts.depends_on,
            "waiting_for": ts.waiting_for,
            "verdict": ts.verdict,
            "fail_reason": ts.fail_reason,
            "bounce_reason": ts.bounce_reason,
            "reset_count": ts.reset_count,
        },
        indent=2,
    ))
    return 0


def cmd_done(args: argparse.Namespace) -> int:
    """Mark a brief task as done by appending the official queue events.

    The command is intentionally tolerant of older rehearsal/task flows that
    reached a durable handoff PASS before the queue was advanced. It preserves
    queue_io's state machine by appending any missing intermediate states
    instead of bypassing validation.
    """
    try:
        _validate_cli_inputs(args.project, args.team, args.task_id)
    except InputValidationError as exc:
        print(f"input validation failed: {exc}", file=sys.stderr)
        return 2

    queue = _queue_path(args.project, args.team)
    state = read_current_state(queue)
    ts = state.get(args.task_id)
    if ts is None:
        print(f"task_id {args.task_id!r} not in queue", file=sys.stderr)
        return 2

    actor = args.actor
    if ts.status == "task_done":
        if ts.verdict == "PASS":
            print(f"task {args.task_id} already done")
            return 0
        print(
            f"task_id {args.task_id!r} is done with verdict {ts.verdict!r}, not PASS",
            file=sys.stderr,
        )
        return 2

    unmet = _unmet_dependencies(args.project, args.team, state, ts.depends_on)
    if unmet:
        print(
            f"task_id {args.task_id!r} still blocked on upstream: {unmet}",
            file=sys.stderr,
        )
        return 3

    plan: list[str]
    if ts.status in ("task_created", "task_waiting_for"):
        plan = ["task_claimed", "task_in_progress", "task_done"]
    elif ts.status == "task_claimed":
        plan = ["task_in_progress", "task_done"]
    elif ts.status == "task_in_progress":
        plan = ["task_done"]
    else:
        print(
            f"task_id {args.task_id!r} is in state {ts.status!r}, not completable",
            file=sys.stderr,
        )
        return 2

    last_result: dict | None = None
    for event_type in plan:
        event = {
            "event_type": event_type,
            "actor": actor,
            "task_id": args.task_id,
        }
        if event_type == "task_done":
            event["verdict"] = "PASS"
        try:
            last_result = append_event(queue, event)
        except QueueError as exc:
            print(f"done append failed: {exc}", file=sys.stderr)
            return 1

    seq = last_result["seq"] if last_result else "?"
    print(f"done {args.task_id} (seq {seq}, verdict PASS)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agent_admin_brief",
        description="ClawSeat v3 brief / queue subcommand (Phase 1 minimal).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("queue", help="Write brief + append task_created event")
    q.add_argument("--project", required=True)
    q.add_argument("--team", required=True)
    q.add_argument("--task-id", required=True, dest="task_id")
    q.add_argument("--objective", required=True)
    q.add_argument("--depends-on", nargs="*", default=[], dest="depends_on")
    q.add_argument(
        "--seats-required",
        nargs="*",
        default=None,
        dest="seats_required",
        help="Seats required (default: ['builder']). Schema requires non-empty.",
    )
    q.add_argument("--parent-task-id", default=None, dest="parent_task_id")
    q.add_argument("--brief-content-file", default=None, dest="brief_content_file",
                   help="Optional path to pre-written brief markdown (overrides skeleton).")
    q.add_argument("--force", action="store_true", help="Overwrite existing brief.")
    q.add_argument("--no-wake", action="store_true",
                   help="Append the queue event without waking the team planner.")
    q.set_defaults(func=cmd_queue)

    l = sub.add_parser("list", help="List tasks for a team (default: pending only)")
    l.add_argument("--project", required=True)
    l.add_argument("--team", required=True)
    l.add_argument("--all", action="store_true")
    l.set_defaults(func=cmd_list)

    c = sub.add_parser("claim", help="Planner claims a pending task")
    c.add_argument("--project", required=True)
    c.add_argument("--team", required=True)
    c.add_argument("--task-id", required=True, dest="task_id")
    c.add_argument("--actor", required=True,
                   help="Format: <role>@<tool>, e.g. planner@claude")
    c.set_defaults(func=cmd_claim)

    s = sub.add_parser("show", help="Show current state of a task_id")
    s.add_argument("--project", required=True)
    s.add_argument("--team", required=True)
    s.add_argument("--task-id", required=True, dest="task_id")
    s.set_defaults(func=cmd_show)

    d = sub.add_parser("done", help="Append task_done PASS for a brief task")
    d.add_argument("--project", required=True)
    d.add_argument("--team", required=True)
    d.add_argument("--task-id", required=True, dest="task_id")
    d.add_argument("--actor", required=True,
                   help="Format: <role>@<tool>, e.g. planner@claude")
    d.add_argument("--verdict", default="PASS", choices=["PASS"],
                   help="Only PASS is accepted for task_done.")
    d.set_defaults(func=cmd_done)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
