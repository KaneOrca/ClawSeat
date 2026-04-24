#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# Add core/lib to path so seat_resolver can be imported
_scripts_dir = Path(__file__).parent.resolve()
_core_lib = _scripts_dir.parent.parent.parent / "lib"
if str(_core_lib) not in sys.path:
    sys.path.insert(0, str(_core_lib))
from real_home import real_user_home

from _common import (
    _should_announce_planner_event,
    _try_announce_planner_event,
    add_notify_args,
    append_status_note,
    append_task_to_queue,
    assert_target_not_memory,
    broadcast_feishu_group_message,
    build_notify_message,
    load_profile,
    legacy_feishu_group_broadcast_enabled,
    normalize_role,
    notify,
    require_success,
    resolve_notify,
    stable_dispatch_nonce,
    upsert_tasks_row,
    utc_now_iso,
    write_json,
    write_todo,
)

from seat_resolver import resolve_seat_from_profile


def _is_task_already_queued(todo_path: Path, task_id: str) -> bool:
    """Return True if task_id appears under a [pending] or [queued] header in todo_path."""
    if not todo_path.exists():
        return False
    content = todo_path.read_text(encoding="utf-8")
    return bool(re.search(
        rf'^## \[(pending|queued)\]\s+{re.escape(task_id)}\b',
        content,
        re.MULTILINE,
    ))



# ── Intent → gstack skill mapping ──────────────────────────────────────
#
# Users describe needs in natural language ("做个工程审查", "推上去", "想大一点").
# They should not have to remember gstack skill trigger phrases — that is
# koder's job per SOUL.md §5 (the "代用户激活 gstack skill" hard rule).
#
# This map lets koder pass --intent <key> and the dispatch prepends the
# canonical trigger phrase to the objective AND adds the SKILL.md path to
# --skill-refs, so the downstream planner Claude Code runtime picks up the
# right skill without guesswork.
#
# To add a new intent:
#   1. Confirm the gstack SKILL.md trigger phrase in its frontmatter.
#   2. Append an entry here.
#   3. Add a row to TOOLS/dispatch.md's intent table in init_koder.py.
#   4. Add a test row in tests/test_dispatch_intent.py.
#
# All four MUST move together — the SKILL.md text is the source of truth.

def _resolve_gstack_skills_root() -> str:
    env = (os.environ.get("GSTACK_SKILLS_ROOT") or "").strip()
    if env:
        expanded = Path(env).expanduser()
        if not expanded.is_absolute():
            # Refuse relative paths — they silently resolve against cwd,
            # which produces mystery "not found" errors at dispatch time.
            # Keep the pattern identical to skill_registry._resolve_gstack_skills_root.
            sys.stderr.write(
                f"warning: GSTACK_SKILLS_ROOT={env!r} is not absolute; "
                f"ignoring and falling back to ~/.gstack/repos/gstack/.agents/skills.\n"
                f"         Set it to an absolute path like "
                f"{Path(env).expanduser().resolve()} to take effect.\n"
            )
        else:
            return str(expanded)
    return str(real_user_home() / ".gstack" / "repos" / "gstack" / ".agents" / "skills")


_GSTACK_SKILLS_ROOT = _resolve_gstack_skills_root()

INTENT_MAP: dict[str, dict[str, str]] = {
    # ── Plan-phase intents (planner's own skills) ─────────────────────
    "eng-review": {
        "trigger": "Review the architecture and lock in the plan",
        "skill_md": f"{_GSTACK_SKILLS_ROOT}/gstack-plan-eng-review/SKILL.md",
        "description": "engineering plan review (architecture / data flow / test coverage / perf)",
    },
    "ceo-review": {
        "trigger": "Think bigger and expand scope if it creates a better product",
        "skill_md": f"{_GSTACK_SKILLS_ROOT}/gstack-plan-ceo-review/SKILL.md",
        "description": "CEO/founder-mode strategy review (scope expand / hold / reduce)",
    },
    "design-review": {
        "trigger": "Review the design plan and design critique",
        "skill_md": f"{_GSTACK_SKILLS_ROOT}/gstack-plan-design-review/SKILL.md",
        "description": "designer's-eye plan review (UX / visual / component; plan-mode)",
    },
    "devex-review": {
        "trigger": "DX review and developer experience audit (Addy Osmani framework)",
        "skill_md": f"{_GSTACK_SKILLS_ROOT}/gstack-plan-devex-review/SKILL.md",
        "description": "developer experience audit (zero friction / learn by doing / fight uncertainty)",
    },
    # ── Build / ship intents (builder-1) ──────────────────────────────
    "ship": {
        "trigger": "Ship it and create a PR (run tests, review diff, bump VERSION, update CHANGELOG)",
        "skill_md": f"{_GSTACK_SKILLS_ROOT}/gstack-ship/SKILL.md",
        "description": "ship workflow (test → diff → version → commit → push → PR)",
    },
    "land": {
        "trigger": "Land the PR and deploy — merge, wait for CI and deploy, verify production",
        "skill_md": f"{_GSTACK_SKILLS_ROOT}/gstack-land-and-deploy/SKILL.md",
        "description": "merge + canary + production verification",
    },
    "investigate": {
        "trigger": "Investigate root cause — debug this, why is this broken, root cause analysis",
        "skill_md": f"{_GSTACK_SKILLS_ROOT}/gstack-investigate/SKILL.md",
        "description": "bug RCA (investigate → analyze → hypothesize → implement)",
    },
    "freeze": {
        "trigger": "Freeze and restrict edits to this directory",
        "skill_md": f"{_GSTACK_SKILLS_ROOT}/gstack-freeze/SKILL.md",
        "description": "restrict Edit/Write to one module for the session",
    },
    "unfreeze": {
        "trigger": "Unfreeze and remove the edit restriction",
        "skill_md": f"{_GSTACK_SKILLS_ROOT}/gstack-unfreeze/SKILL.md",
        "description": "clear the /freeze boundary, allow all-directory edits again",
    },
    # ── Review intent (reviewer-1) ────────────────────────────────────
    "code-review": {
        "trigger": "Code review — pre-landing PR review, check the diff for SQL safety, LLM trust, conditional side effects, structural issues",
        "skill_md": f"{_GSTACK_SKILLS_ROOT}/gstack-review/SKILL.md",
        "description": "pre-landing PR review (NOT plan-review; for final diff check)",
    },
    # ── QA intents (qa-1) ────────────────────────────────────────────
    "qa-test": {
        "trigger": "QA — systematically test this web app and fix bugs found (test → fix → verify loop)",
        "skill_md": f"{_GSTACK_SKILLS_ROOT}/gstack-qa/SKILL.md",
        "description": "full QA test-fix-verify loop with before/after health scores",
    },
    "qa-only": {
        "trigger": "QA report only — just report bugs, don't fix anything",
        "skill_md": f"{_GSTACK_SKILLS_ROOT}/gstack-qa-only/SKILL.md",
        "description": "report-only QA (no source code edits, only a structured report)",
    },
    # ── Design intents (designer-1) ───────────────────────────────────
    "design-critique": {
        "trigger": "Audit the design — visual QA, check if it looks good, design polish (post-implementation)",
        "skill_md": f"{_GSTACK_SKILLS_ROOT}/gstack-design-review/SKILL.md",
        "description": "post-implementation visual audit (iteratively fixes visual issues)",
    },
    "design-html": {
        "trigger": "Finalize this design and turn it into production HTML/CSS",
        "skill_md": f"{_GSTACK_SKILLS_ROOT}/gstack-design-html/SKILL.md",
        "description": "design → production HTML/CSS via Pretext patterns",
    },
    "design-shotgun": {
        "trigger": "Design shotgun — generate multiple AI design variants and compare",
        "skill_md": f"{_GSTACK_SKILLS_ROOT}/gstack-design-shotgun/SKILL.md",
        "description": "multi-variant design exploration with comparison board",
    },
    # ── Cross-cutting intents (all seats) ─────────────────────────────
    "office-hours": {
        "trigger": "Office hours brainstorm — help me think through this, is this worth building",
        "skill_md": f"{_GSTACK_SKILLS_ROOT}/gstack-office-hours/SKILL.md",
        "description": "YC office-hours brainstorm (6 forcing questions / design doc)",
    },
    "checkpoint": {
        "trigger": "Checkpoint — save progress and where was I",
        "skill_md": f"{_GSTACK_SKILLS_ROOT}/gstack-checkpoint/SKILL.md",
        "description": "save/resume working state across sessions",
    },
}


def apply_intent(
    intent: str | None,
    objective: str,
    skill_refs: list[str] | None,
) -> tuple[str, list[str]]:
    """Expand --intent into (augmented_objective, augmented_skill_refs).

    - If intent is None, return inputs unchanged.
    - If intent is valid, prepend the canonical trigger phrase to the objective
      and append the skill SKILL.md path to skill_refs (deduped).
    - If intent is unknown, raise ValueError listing valid intents.
    """
    if intent is None:
        return objective, (skill_refs or [])
    if intent not in INTENT_MAP:
        valid = ", ".join(sorted(INTENT_MAP.keys()))
        raise ValueError(
            f"unknown --intent {intent!r}; valid intents: {valid}"
        )
    spec = INTENT_MAP[intent]
    trigger = spec["trigger"]
    skill_md = spec["skill_md"]
    # Prepend trigger only if not already present (idempotent when koder
    # re-runs a dispatch with --intent after the trigger is already in the
    # objective — helpful when the operator wrote both by hand).
    if trigger.lower() not in objective.lower():
        new_objective = f"**{trigger}** — {objective.strip()}"
    else:
        new_objective = objective
    refs = list(skill_refs or [])
    if skill_md not in refs:
        refs.append(skill_md)
    return new_objective, refs


def _write_dispatch_to_ledger(
    *,
    task_id: str,
    project: str,
    source: str,
    target: str,
    role_hint: str | None,
    title: str | None,
    correlation_id: str | None,
) -> None:
    """Write task + task.dispatched event to state.db. Defensive: never fails dispatch."""
    try:
        from datetime import datetime, timezone as _tz
        from core.lib.state import open_db, record_task_dispatched, record_event, Task
        task = Task(
            id=task_id,
            project=project,
            source=source,
            target=target,
            role_hint=role_hint,
            status="dispatched",
            title=title,
            correlation_id=correlation_id,
            opened_at=datetime.now(_tz.utc).isoformat(timespec="seconds"),
        )
        with open_db() as conn:
            record_task_dispatched(conn, task)
            record_event(conn, "task.dispatched", project,
                         task_id=task_id, source=source, target=target)
    except Exception as exc:
        print(f"warn: state.db unavailable, skipping ledger write: {exc}", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dispatch a task to a target seat.")
    parser.add_argument("--profile", required=True, help="Path to the project profile TOML.")
    parser.add_argument("--source", default="planner", help="Seat dispatching the task.")
    _target_group = parser.add_mutually_exclusive_group(required=True)
    _target_group.add_argument("--target", help="Target seat (explicit seat id).")
    _target_group.add_argument(
        "--target-role",
        metavar="ROLE",
        help="Pick least-busy live seat with this role from state.db (e.g. 'builder').",
    )
    parser.add_argument("--task-id", required=True, help="Task id.")
    parser.add_argument("--title", required=True, help="Task title.")
    parser.add_argument("--objective", required=True, help="Objective/body text for the TODO.")
    parser.add_argument("--reply-to", help="Seat that should receive completion back from the target.")
    parser.add_argument("--notes", default="dispatched via gstack-harness", help="TASKS.md note.")
    parser.add_argument("--status-note", help="Optional STATUS.md note.")
    add_notify_args(parser)
    parser.add_argument(
        "--task-type",
        default="unspecified",
        help="Task type hint (implementation/review/research/unspecified).",
    )
    parser.add_argument(
        "--review-required",
        action="store_true",
        help="Mark task as requiring reviewer sign-off.",
    )
    parser.add_argument(
        "--skill-refs",
        nargs="*",
        metavar="SKILL_REF",
        default=None,
        help=(
            "Optional skill documentation pointers to include in the dispatched TODO.md "
            "(e.g. 'references/feishu-bridge-setup.md'). Appended as a '# Skill Refs' section."
        ),
    )
    parser.add_argument(
        "--allow-notify-failure",
        action="store_true",
        help=(
            "Continue even if tmux notify fails (exit 0). "
            "Default: exit 1 with a NOTIFY FAILED banner on failure. "
            "Use in CI/batch where notify is best-effort."
        ),
    )
    parser.add_argument(
        "--intent",
        choices=sorted(INTENT_MAP.keys()),
        default=None,
        help=(
            "High-level user-intent key that auto-injects the canonical gstack "
            "skill trigger phrase into --objective AND appends the skill's "
            "SKILL.md path to --skill-refs. Use this so koder does not have to "
            "memorise every gstack skill's trigger vocabulary. "
            "Valid keys: " + ", ".join(sorted(INTENT_MAP.keys())) + ". "
            "See TOOLS/dispatch.md for the user-intent → key mapping."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    do_notify = resolve_notify(args)
    role_hint: str | None = getattr(args, "target_role", None)

    # Load profile early when --target-role is used (need project_name for lookup).
    profile = None
    if role_hint:
        profile = load_profile(args.profile)
        try:
            from core.lib.state import open_db, pick_least_busy_seat
            with open_db() as conn:
                picked = pick_least_busy_seat(conn, profile.project_name, role_hint)
        except Exception as exc:
            print(f"warn: state.db unavailable for role resolution: {exc}", file=sys.stderr)
            picked = None
        if picked is None:
            print(
                f"seat_needed: no live seat with role={role_hint!r} in "
                f"project={profile.project_name!r}. "
                "Launch one or specify --target explicitly.",
                file=sys.stderr,
            )
            return 3
        args.target = picked.seat_id
        print(f"target-role resolved: {role_hint} -> {args.target}", file=sys.stderr)

    # T9: block dispatch to memory before touching the profile — memory is an
    # oracle, never a task worker; this check is profile-independent.
    assert_target_not_memory(args.target, "dispatch_task.py")
    if profile is None:
        profile = load_profile(args.profile)
    if args.target not in profile.seats:
        raise SystemExit(
            f"dispatch target {args.target!r} is not a declared seat for project "
            f"{profile.project_name!r}; known seats: {profile.seats}"
        )
    # Expand --intent into a canonical trigger phrase + skill-ref before we
    # write anything. This is the "koder should memorise triggers, not the
    # user" plumbing per SOUL.md §5.
    effective_objective, effective_skill_refs = apply_intent(
        args.intent,
        args.objective,
        args.skill_refs,
    )
    todo_path = profile.todo_path(args.target)
    if _is_task_already_queued(todo_path, args.task_id):
        print(
            f"TASK_ALREADY_QUEUED {args.task_id} @ {utc_now_iso()}",
            file=sys.stderr,
        )
        return 2
    reply_to = args.reply_to or args.source
    source_role = normalize_role(profile.seat_roles.get(args.source, ""))
    target_role = normalize_role(profile.seat_roles.get(args.target, ""))
    correlation_id = stable_dispatch_nonce(profile.project_name, "planning", args.task_id)
    append_task_to_queue(
        todo_path,
        task_id=args.task_id,
        project=profile.project_name,
        owner=args.target,
        title=args.title,
        objective=effective_objective,
        source=args.source,
        reply_to=reply_to,
        skill_refs=effective_skill_refs,
        task_type=args.task_type,
        review_required=args.review_required,
        correlation_id=correlation_id,
    )
    upsert_tasks_row(
        profile.tasks_doc,
        task_id=args.task_id,
        title=args.title,
        owner=args.target,
        status="pending",
        notes=args.notes,
    )
    append_status_note(
        profile.status_doc,
        args.status_note or f"{args.source} dispatched {args.task_id} to {args.target}",
    )
    receipt = {
        "kind": "dispatch",
        "task_id": args.task_id,
        "correlation_id": correlation_id,
        "source": args.source,
        "target": args.target,
        "title": args.title,
        "todo_path": str(todo_path),
        "reply_to": reply_to,
        "assigned_at": utc_now_iso(),
        "notified_at": None,
        "notify_message": None,
    }
    if do_notify:
        message = build_notify_message(
            args.target,
            todo_path,
            args.task_id,
            source=args.source,
            reply_to=reply_to,
        )
        resolution = resolve_seat_from_profile(args.target, profile)
        if resolution.kind == "tmux":
            result = notify(profile, args.target, message)
            if result.returncode != 0:
                detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
                print("============ NOTIFY FAILED ============", file=sys.stderr)
                print(f"  target : {args.target}", file=sys.stderr)
                print(f"  task   : {args.task_id}", file=sys.stderr)
                print(f"  reason : {detail}", file=sys.stderr)
                print(
                    f"  fix    : send-and-verify.sh --project {profile.project_name} "
                    f"{args.target} '<message>'",
                    file=sys.stderr,
                )
                print("=======================================", file=sys.stderr)
                if not getattr(args, "allow_notify_failure", False):
                    receipt_path = profile.handoff_path(args.task_id, args.source, args.target)
                    write_json(receipt_path, receipt)
                    return 1
                print("warn: --allow-notify-failure set; continuing", file=sys.stderr)
            else:
                receipt["notified_at"] = utc_now_iso()
                receipt["notify_message"] = message
            should_broadcast = (
                source_role in {"planner", "planner-dispatcher"}
                or target_role in {"planner", "planner-dispatcher"}
                or args.source == profile.active_loop_owner
                or args.target == profile.active_loop_owner
            )
            if should_broadcast and legacy_feishu_group_broadcast_enabled():
                if source_role in {"planner", "planner-dispatcher"} and target_role not in {
                    "planner",
                    "planner-dispatcher",
                }:
                    group_message = (
                        f"{profile.project_name} 项目 planner 已向 {args.target} 发布任务 {args.task_id}："
                        f"{args.title}. 回复链路 {reply_to}."
                    )
                elif target_role in {"planner", "planner-dispatcher"} and source_role not in {
                    "planner",
                    "planner-dispatcher",
                }:
                    group_message = (
                        f"{profile.project_name} 项目 planner 已收到任务 {args.task_id}，"
                        f"来自 {args.source}：{args.title}. 回复链路 {reply_to}."
                    )
                else:
                    group_message = (
                        f"{profile.project_name} 项目 planner 任务流转 {args.task_id}："
                        f"{args.source} -> {args.target}，{args.title}."
                    )
                broadcast = broadcast_feishu_group_message(group_message, project=profile.project_name)
                receipt["feishu_group_broadcast"] = broadcast
                if broadcast.get("status") == "failed":
                    print(
                        f"warn: feishu group broadcast failed for {args.task_id}: "
                        f"{broadcast.get('stderr') or broadcast.get('stdout') or broadcast.get('reason', 'unknown')}",
                        file=sys.stderr,
                    )
            elif should_broadcast:
                receipt["feishu_group_broadcast"] = {
                    "status": "skipped",
                    "reason": "legacy_group_broadcast_disabled",
                }
        else:
            # kind=openclaw or kind=file-only: tmux notify not applicable
            # For openclaw targets, use complete_handoff.py for the koder closeout path.
            print(
                f"warn: dispatch target {args.target!r} resolves to kind={resolution.kind} — "
                "tmux notify skipped. Use complete_handoff.py for the koder closeout path.",
                file=sys.stderr,
            )
            receipt["notify_message"] = message
            receipt["feishu_group_broadcast"] = {
                "status": "skipped",
                "reason": f"target_kind_{resolution.kind}",
            }
    receipt_path = profile.handoff_path(args.task_id, args.source, args.target)
    write_json(receipt_path, receipt)
    _write_dispatch_to_ledger(
        task_id=args.task_id,
        project=profile.project_name,
        source=args.source,
        target=args.target,
        role_hint=role_hint,
        title=args.title,
        correlation_id=correlation_id,
    )
    print(f"dispatched {args.task_id} -> {args.target}")
    print(f"todo: {todo_path}")
    print(f"receipt: {receipt_path}")
    if _should_announce_planner_event(args.source, args.target, profile=profile):
        _try_announce_planner_event(
            project=profile.project_name,
            source=args.source,
            target=args.target,
            task_id=args.task_id,
            verb="dispatched",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
