#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import os
import re
import sys
import tempfile
import time
from pathlib import Path

# Add core/lib to path so seat_resolver can be imported
_scripts_dir = Path(__file__).parent.resolve()
_core_lib = _scripts_dir.parent.parent.parent / "lib"
if str(_core_lib) not in sys.path:
    sys.path.insert(0, str(_core_lib))

from _common import (
    _should_announce_planner_event,
    _try_announce_planner_event,
    add_notify_args,
    append_consumed_ack,
    append_status_dispatch_event,
    append_task_to_queue,
    broadcast_feishu_group_message,
    build_delegation_report_text,
    build_completion_message,
    complete_task_in_queue,
    load_json,
    load_profile,
    legacy_feishu_group_broadcast_enabled,
    notify,
    require_success,
    resolve_notify,
    send_feishu_user_message,
    sanitize_name,
    stable_dispatch_nonce,
    utc_now_iso,
    write_delivery,
    write_json,
    write_todo,
)

from seat_resolver import resolve_seat_from_profile


def _do_prune(text: str, task_id: str) -> str:
    """Return text with ALL [pending]/[queued] blocks matching task_id removed.

    Splits on '^## [' line anchors (spec approach-b) to avoid any dependency on
    '# Completed' appearing literally as a split token — objective/title fields
    may contain that text. The trailing non-entry content (e.g. '# Completed'
    section) is located by scanning for h1 headings after the last ## [ block
    only, so poison lines inside earlier entry bodies are invisible.
    Removes all matching blocks (defense-in-depth for pre-#16 duplicate residue).
    Returns the same object (identity) if no match found.
    """
    lines = text.splitlines(keepends=True)

    task_pat = re.compile(rf"^task_id:\s*{re.escape(task_id)}\s*$")
    status_pat = re.compile(r"^## \[(pending|queued)\]")
    h1_pat = re.compile(r"^# (?!#)")  # h1 heading that is not ## or ###

    # Find ## [ block start positions
    block_starts = [i for i, ln in enumerate(lines) if ln.startswith("## [")]
    if not block_starts:
        return text

    # Locate the trailing non-entry section (e.g. '# Completed').
    # Scan only from the last ## [ block onwards so poison h1 lines inside
    # earlier entry bodies do not influence the boundary.
    tail_start = len(lines)
    for k in range(block_starts[-1] + 1, len(lines)):
        if h1_pat.match(lines[k]):
            tail_start = k
            break

    # Each block runs from its start to the next block start (or tail_start)
    block_ends = list(block_starts[1:]) + [tail_start]
    blocks = list(zip(block_starts, block_ends))

    # Identify ALL matching [pending]/[queued] blocks (not just first).
    # Defense-in-depth: pre-#16 dispatch retries may have left duplicate entries.
    matching = []
    for i, (bstart, bend) in enumerate(blocks):
        seg = lines[bstart:bend]
        if status_pat.match(seg[0]) and any(task_pat.match(l) for l in seg):
            matching.append(i)

    if not matching:
        return text

    # Rebuild without any of the matching blocks
    header = "".join(lines[: block_starts[0]])
    matching_set = set(matching)
    remaining = [b for i, b in enumerate(blocks) if i not in matching_set]

    if remaining:
        parts = ["".join(lines[bs:be]) for bs, be in remaining]
        entries = "".join(parts)
        # Strip dangling --- separator when the deleted block was non-last
        entries = re.sub(r"\n\n---\n\n\s*$", "\n", entries)
        result = header + entries
    else:
        result = header.rstrip("\n")

    # Reattach trailing section (e.g. '# Completed') with proper spacing
    tail = "".join(lines[tail_start:])
    if tail:
        if not result.endswith("\n\n"):
            result = result.rstrip("\n") + "\n\n"
        result += tail
    elif not result.endswith("\n"):
        result += "\n"

    return result


def _prune_todo_entry(todo_path: Path, task_id: str) -> None:
    """Delete all [pending]/[queued] blocks for task_id from todo_path.

    Atomic write via tempfile + os.replace. Fail-safe: any IO/regex error is
    printed to stderr and swallowed — ACK main flow is unaffected.
    """
    if not todo_path.exists():
        return
    try:
        text = todo_path.read_text(encoding="utf-8")
        pruned = _do_prune(text, task_id)
        if pruned is text:
            return  # no match, nothing to write
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=todo_path.parent, delete=False, suffix=".tmp"
        ) as tf:
            tf.write(pruned)
            tmp_name = tf.name
        os.replace(tmp_name, todo_path)
    except Exception as exc:
        print(f"warn: prune_todo_entry failed for {task_id}: {exc}", file=sys.stderr)


VALID_VERDICTS = {
    "APPROVED",
    "APPROVED_WITH_NITS",
    "CHANGES_REQUESTED",
    "BLOCKED",
    "DECISION_NEEDED",
}

VALID_FRONTSTAGE_DISPOSITIONS = {
    "AUTO_ADVANCE",
    "USER_DECISION_NEEDED",
}


def _write_completion_to_ledger(
    *,
    task_id: str,
    project: str,
    source: str,
    disposition: str,
) -> None:
    """Record task completion in state.db. Defensive: never fails handoff."""
    try:
        from core.lib.state import open_db, mark_task_completed, record_event
        with open_db() as conn:
            mark_task_completed(conn, task_id, disposition=disposition)
            record_event(conn, "task.completed", project,
                         task_id=task_id, source=source, disposition=disposition)
    except Exception as exc:
        print(f"warn: state.db unavailable, skipping ledger write: {exc}", file=sys.stderr)


def _seat_fallback_path(profile: object, seat: str, filename: str) -> Path:
    return profile.workspace_for(seat) / filename  # type: ignore[attr-defined]


def _seat_fallback_receipt_path(profile: object, seat: str, primary: Path) -> Path:
    return profile.workspace_for(seat) / ".clawseat" / "handoffs" / primary.name  # type: ignore[attr-defined]


def persist_delivery(
    profile: object,
    *,
    seat: str,
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
    correlation_id: str | None = None,
    branch: str | None = None,
    commit: str | None = None,
    sweep_count: int | None = None,
    core_ux_gate: str | None = None,
) -> tuple[Path, bool]:
    primary = profile.delivery_path(seat)  # type: ignore[attr-defined]
    try:
        write_delivery(
            primary,
            task_id=task_id,
            owner=owner,
            target=target,
            title=title,
            summary=summary,
            status=status,
            verdict=verdict,
            frontstage_disposition=frontstage_disposition,
            user_summary=user_summary,
            next_action=next_action,
            correlation_id=correlation_id,
            branch=branch,
            commit=commit,
            sweep_count=sweep_count,
            core_ux_gate=core_ux_gate,
        )
        return primary, False
    except PermissionError as exc:
        fallback = _seat_fallback_path(profile, seat, "DELIVERY.md")
        write_delivery(
            fallback,
            task_id=task_id,
            owner=owner,
            target=target,
            title=title,
            summary=summary,
            status=status,
            verdict=verdict,
            frontstage_disposition=frontstage_disposition,
            user_summary=user_summary,
            next_action=next_action,
            correlation_id=correlation_id,
            branch=branch,
            commit=commit,
            sweep_count=sweep_count,
            core_ux_gate=core_ux_gate,
        )
        print(
            f"warn: delivery path {primary} not writable ({exc}); "
            f"wrote fallback delivery to {fallback}",
            file=sys.stderr,
        )
        return fallback, True


def persist_receipt(
    profile: object,
    *,
    seat: str,
    primary: Path,
    payload: dict[str, object],
) -> Path:
    try:
        write_json(primary, payload)
        return primary
    except PermissionError as exc:
        fallback = _seat_fallback_receipt_path(profile, seat, primary)
        write_json(fallback, payload)
        print(
            f"warn: receipt path {primary} not writable ({exc}); "
            f"wrote fallback receipt to {fallback}",
            file=sys.stderr,
        )
        return fallback


def append_consumed_ack_with_fallback(
    profile: object,
    *,
    seat: str,
    task_id: str,
    source: str,
) -> tuple[str, Path]:
    primary = profile.todo_path(seat)  # type: ignore[attr-defined]
    try:
        return append_consumed_ack(primary, task_id=task_id, source=source), primary
    except PermissionError as exc:
        fallback = _seat_fallback_path(profile, seat, "TODO.md")
        ack_line = append_consumed_ack(fallback, task_id=task_id, source=source)
        print(
            f"warn: todo path {primary} not writable ({exc}); "
            f"appended consumed ACK to fallback TODO {fallback}",
            file=sys.stderr,
        )
        return ack_line, fallback


def complete_source_queue_if_possible(
    profile: object,
    *,
    seat: str,
    task_id: str,
    summary: str,
) -> Path:
    primary = profile.todo_path(seat)  # type: ignore[attr-defined]
    try:
        complete_task_in_queue(primary, task_id=task_id, summary=summary)
        return primary
    except PermissionError as exc:
        print(
            f"warn: todo path {primary} not writable ({exc}); "
            "skipping source queue completion in shared task ledger",
            file=sys.stderr,
        )
        return primary


def build_frontstage_objective(
    *,
    source: str,
    task_id: str,
    delivery_path: str,
    disposition: str,
    user_summary: str,
    next_action: str | None,
) -> str:
    lines = [
        f"Read {delivery_path}.",
        f"{source} returned {task_id} to frontstage.",
        f"FrontstageDisposition: {disposition}",
        f"UserSummary: {user_summary}",
        "Before replying to the user, review the delivery trail, consolidate the wrap-up, and update PROJECT.md / TASKS.md / STATUS.md when the stage closeout changes the project record.",
    ]
    if disposition == "AUTO_ADVANCE":
        lines.append("Summarize the result for the user in plain language and auto-advance the chain unless a real decision gate appears.")
    if next_action:
        lines.append(f"NextAction: {next_action}")
    return "\n".join(lines)


def _infer_target_from_dispatch_handoff(
    profile: object,
    *,
    task_id: str,
    source: str,
) -> str:
    safe_task = sanitize_name(task_id)
    safe_source = sanitize_name(source)
    handoff_dir = _expanded_profile_handoff_dir(profile)
    pattern = f"{safe_task}__*__{safe_source}.json"
    candidates: list[Path] = []
    for path in handoff_dir.glob(pattern):
        if path.is_file():
            candidates.append(path)
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for path in candidates:
        payload = load_json(path)
        if not isinstance(payload, dict):
            continue
        reply_to = payload.get("reply_to")
        if isinstance(reply_to, str) and reply_to.strip():
            return reply_to.strip()
    raise SystemExit(
        f"--target required: could not infer from dispatch handoff for task_id={task_id!r}; "
        f"searched {handoff_dir} with pattern {pattern}"
    )


def _expanded_profile_handoff_dir(profile: object) -> Path:
    text = str(getattr(profile, "handoff_dir")).strip()
    return Path(os.path.expandvars(text)).expanduser().resolve()


def _profile_handoff_path(profile: object, task_id: str, source: str, target: str) -> Path:
    return _expanded_profile_handoff_dir(profile) / (
        f"{sanitize_name(task_id)}__{sanitize_name(source)}__{sanitize_name(target)}.json"
    )


def _mark_planner_incoming_consumed(handoffs_dir: Path, task_id: str) -> list[Path]:
    handoffs_dir = Path(os.path.expandvars(str(handoffs_dir))).expanduser().resolve()
    pattern = f"{sanitize_name(task_id)}__*__planner.json"
    def _emit_skip_rename() -> None:
        message = f"info: skip rename; no incoming planner handoffs found for {task_id} in {handoffs_dir}"
        print(message)
        print(message, file=sys.stderr)
    if not handoffs_dir.exists():
        _emit_skip_rename()
        return []
    candidates = [path for path in handoffs_dir.glob(pattern) if path.is_file()]
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    renamed: list[Path] = []
    for path in candidates:
        consumed = path.with_suffix(path.suffix + ".consumed")
        path.replace(consumed)
        renamed.append(consumed)
    if not renamed:
        _emit_skip_rename()
    return renamed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Complete or consume a harness handoff.")
    parser.add_argument("--profile", required=True, help="Path to the project profile TOML.")
    parser.add_argument("--source", required=True, help="Source seat for the completion or ACK.")
    parser.add_argument("--target", help="Target seat.")
    parser.add_argument("--branch", help="Feature branch used to auto-fill branch_base/branch_tip.")
    parser.add_argument("--pr-number", help="Pull Request number for closure fields.")
    parser.add_argument("--ci-conclusion", help="CI conclusion marker for closure fields.")
    parser.add_argument("--task-id", required=True, help="Task id.")
    parser.add_argument("--title", help="Delivery title.")
    parser.add_argument("--summary", help="Delivery summary text.")
    parser.add_argument("--status", default="completed", help="Delivery status.")
    parser.add_argument("--verdict", help="Canonical review verdict.")
    parser.add_argument("--commit", help="Optional commit SHA to include in STATUS.md ack log.")
    parser.add_argument("--sweep-count", type=int, help="Planner sweep count metadata for DELIVERY.md.")
    parser.add_argument(
        "--core-ux-gate",
        help="Required core UX gate marker when the dispatch receipt marks the step as core UX.",
    )
    parser.add_argument(
        "--base-drift-acknowledged",
        action="store_true",
        help="Acknowledge intentional current-main drift for a branch closeout.",
    )
    parser.add_argument(
        "--drift-reason",
        help="JSON drift reason with drift_from, drift_to, and orthogonal_files_verified.",
    )
    parser.add_argument(
        "--test-policy",
        choices=["UPDATE", "FREEZE", "EXTEND", "N/A"],
        help="Optional test policy override for STATUS.md ack log; normally read from dispatch receipt.",
    )
    parser.add_argument(
        "--frontstage-disposition",
        help="Canonical planner->frontstage outcome: AUTO_ADVANCE or USER_DECISION_NEEDED.",
    )
    parser.add_argument(
        "--user-summary",
        help="Short plain-language summary that frontstage can relay to the user.",
    )
    parser.add_argument(
        "--next-action",
        help="Short frontstage instruction, especially when a user decision is needed.",
    )
    parser.add_argument(
        "--allow-branch-mismatch",
        action="store_true",
        help="Bypass branch lock validation when a deliberate worktree mismatch is expected.",
    )
    parser.add_argument(
        "--enforce-planner-self-closeout",
        nargs="?",
        const=True,
        default=True,
        type=_parse_bool,
        help="Mark planner incoming handoffs consumed before closeout (use =false to disable).",
    )
    parser.add_argument("--ack-only", action="store_true", help="Only append the durable Consumed ACK.")
    add_notify_args(parser)
    return parser.parse_args()


def _parse_bool(value: str | bool | None) -> bool:
    if value is None or value is True:
        return True
    if value is False:
        return False
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError(
        "--enforce-planner-self-closeout expects a boolean value (true/false)"
    )


def _receipt_test_policy(
    profile: object,
    *,
    receipt: dict[str, object],
    task_id: str,
    source: str,
    target: str,
    override: str | None = None,
) -> str | None:
    if override:
        return override
    value = receipt.get("test_policy")
    if isinstance(value, str) and value:
        return value
    try:
        reverse = load_json(_profile_handoff_path(profile, task_id, target, source))
    except Exception:  # noqa: BLE001 best-effort status decoration
        reverse = None
    if isinstance(reverse, dict):
        value = reverse.get("test_policy")
        if isinstance(value, str) and value:
            return value
    return None


def _load_dispatch_receipt_for_completion(
    profile: object,
    task_id: str,
    source: str,
) -> dict[str, object] | None:
    safe_task = sanitize_name(task_id)
    safe_source = sanitize_name(source)
    handoff_dir = _expanded_profile_handoff_dir(profile)
    pattern = f"{safe_task}__*__{safe_source}.json"
    candidates: list[Path] = []
    for path in handoff_dir.glob(pattern):
        if path.is_file():
            candidates.append(path)
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for path in candidates:
        payload = load_json(path)
        if isinstance(payload, dict) and payload.get("kind") == "dispatch":
            return payload
    return None


def _validate_branch_lock(
    receipt: dict[str, object],
    dispatch_receipt: dict[str, object] | None,
    *,
    source: str,
    target: str,
    allow_branch_mismatch: bool = False,
) -> None:
    if not source.startswith("builder") or not target.startswith("planner"):
        return
    if not isinstance(dispatch_receipt, dict):
        return
    expected_branch = dispatch_receipt.get("expected_branch")
    if not isinstance(expected_branch, str) or not expected_branch:
        return
    actual_branch = receipt.get("branch")
    if not isinstance(actual_branch, str) or not actual_branch:
        actual_branch = receipt.get("branch_tip")
    if not isinstance(actual_branch, str) or not actual_branch:
        return
    if re.fullmatch(r"[0-9a-f]{7,64}", actual_branch):
        return
    if actual_branch == "main":
        return
    if actual_branch == expected_branch:
        return
    if allow_branch_mismatch:
        print("WARNING: bypassing branch lock; worktree drift risk", file=sys.stderr)
        return
    raise SystemExit(f"BOUNCE: branch mismatch — expected {expected_branch} got {actual_branch}")


def _git_main_ref(repo_root: Path) -> str | None:
    if not repo_root:
        return None
    for ref in ("clawseat/main", "origin/main"):
        try:
            subprocess.run(
                ["git", "-C", str(repo_root), "rev-parse", "--verify", ref],
                check=True,
                capture_output=True,
                text=True,
            )
        except Exception:
            continue
        return ref
    return None


def _git_main_tip_sha(repo_root: Path) -> str | None:
    main_ref = _git_main_ref(repo_root)
    if main_ref is None:
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", main_ref],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    sha = result.stdout.strip()
    return sha or None


def _git_changed_files(repo_root: Path, left: str, right: str) -> set[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--name-only", left, right],
        check=True,
        capture_output=True,
        text=True,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _validate_base_drift(
    *,
    repo_root: Path,
    branch_base: str,
    branch_tip: str,
    expected_base_sha: str | None,
    base_drift_acknowledged: bool,
    drift_reason_text: str | None,
) -> dict[str, object] | None:
    if not isinstance(expected_base_sha, str) or not expected_base_sha:
        return None
    current_main_sha = _git_main_tip_sha(repo_root)
    if not current_main_sha:
        return None
    if current_main_sha == branch_base:
        if base_drift_acknowledged:
            print(
                "warn: base drift acknowledgement ignored; branch already aligned with current main",
                file=sys.stderr,
            )
        return None
    if not base_drift_acknowledged:
        raise SystemExit("base drift detected: current main advanced since dispatch")
    if not drift_reason_text:
        raise SystemExit("base drift detected: missing --drift-reason")
    try:
        drift_reason = json.loads(drift_reason_text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid --drift-reason JSON: {exc}") from exc
    if not isinstance(drift_reason, dict):
        raise SystemExit("invalid --drift-reason JSON: expected object")
    drift_from = drift_reason.get("drift_from")
    drift_to = drift_reason.get("drift_to")
    if drift_from != branch_base or drift_to != current_main_sha:
        raise SystemExit("base drift detected: drift_reason does not match current main transition")
    if not drift_reason.get("orthogonal_files_verified"):
        raise SystemExit("base drift detected: orthogonal_files_verified must be true")
    branch_files = _git_changed_files(repo_root, branch_base, branch_tip)
    drift_files = _git_changed_files(repo_root, str(drift_from), str(drift_to))
    if branch_files & drift_files:
        raise SystemExit("base drift is not orthogonal")
    return drift_reason


def _git_branch_and_base(
    repo_root: Path,
    branch: str,
) -> tuple[str, str]:
    base_ref = _git_main_ref(Path(repo_root))
    if base_ref is None:
        raise RuntimeError("could not resolve main ref in repo; expected clawseat/main or origin/main")
    branch_tip = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", branch],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not branch_tip:
        raise RuntimeError(f"could not resolve branch tip for {branch!r}")
    branch_base = subprocess.run(
        ["git", "-C", str(repo_root), "merge-base", branch, base_ref],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not branch_base:
        raise RuntimeError(f"could not resolve merge-base for branch {branch!r} against {base_ref}")
    return branch_base, branch_tip


def _validate_completion_receipt(
    receipt: dict[str, object],
    source_dispatch: dict[str, object] | None,
) -> None:
    expected_base = (
        source_dispatch.get("expected_base_sha")
        if isinstance(source_dispatch, dict)
        else None
    )
    if not isinstance(expected_base, str) or not expected_base:
        return

    missing = [
        key
        for key in ("branch_base", "branch_tip", "pr_number", "ci_conclusion")
        if not receipt.get(key)
    ]
    if missing:
        raise SystemExit(
            f"closure receipt missing required fields: {missing} "
            "Add --branch, --pr-number and --ci-conclusion."
        )

    actual_base = receipt.get("branch_base")
    if actual_base != expected_base:
        raise SystemExit(
            "branch_base mismatch: receipt base does not match dispatch expected_base_sha."
            " Rebase the feature branch onto the current main and retry."
        )


def main() -> int:
    args = parse_args()
    do_notify = resolve_notify(args)
    profile = load_profile(args.profile)
    if args.target is None:
        args.target = _infer_target_from_dispatch_handoff(
            profile,
            task_id=args.task_id,
            source=args.source,
        )
    if (
        not args.enforce_planner_self_closeout
        and args.source in {"planner", "planner-dispatcher"}
        and args.target == "memory"
    ):
        print(
            "WARNING: bypassing planner self-closeout; .consumed + DELIVERY.md may drift",
            file=sys.stderr,
        )
        return 0
    receipt_path = _profile_handoff_path(profile, args.task_id, args.source, args.target)
    correlation_id = stable_dispatch_nonce(profile.project_name, "planning", args.task_id)
    receipt = load_json(receipt_path) or {
        "kind": "completion",
        "task_id": args.task_id,
        "source": args.source,
        "target": args.target,
    }
    receipt["correlation_id"] = correlation_id
    if args.branch:
        repo_root = getattr(profile, "repo_root", None)
        if not repo_root:
            raise SystemExit("cannot compute branch closure fields without profile.repo_root")
        try:
            branch_base, branch_tip = _git_branch_and_base(Path(repo_root), args.branch)
        except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
            raise SystemExit(
                f"failed to auto-compute closure fields for branch {args.branch!r}: {exc}"
            )
        receipt["branch_base"] = branch_base
        receipt["branch_tip"] = branch_tip
    if args.pr_number is not None:
        receipt["pr_number"] = args.pr_number
    if args.ci_conclusion is not None:
        receipt["ci_conclusion"] = args.ci_conclusion
    source_dispatch_receipt = _load_dispatch_receipt_for_completion(
        profile,
        task_id=args.task_id,
        source=args.source,
    )
    expected_base_sha = (
        source_dispatch_receipt.get("expected_base_sha")
        if isinstance(source_dispatch_receipt, dict)
        else None
    )
    if args.branch:
        repo_root = getattr(profile, "repo_root", None)
        if not repo_root:
            raise SystemExit("cannot compute branch closure fields without profile.repo_root")
        try:
            branch_base, branch_tip = _git_branch_and_base(Path(repo_root), args.branch)
        except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
            raise SystemExit(
                f"failed to auto-compute closure fields for branch {args.branch!r}: {exc}"
            )
        receipt["branch"] = args.branch
        receipt["branch_base"] = branch_base
        receipt["branch_tip"] = branch_tip
        if not args.ack_only:
            drift_reason = _validate_base_drift(
                repo_root=Path(repo_root),
                branch_base=branch_base,
                branch_tip=branch_tip,
                expected_base_sha=expected_base_sha if isinstance(expected_base_sha, str) else None,
                base_drift_acknowledged=args.base_drift_acknowledged,
                drift_reason_text=args.drift_reason,
            )
            if drift_reason is not None:
                receipt["base_drift_acknowledged"] = True
                receipt["drift_reason"] = args.drift_reason
    if args.commit is not None:
        receipt["commit"] = args.commit
    if args.sweep_count is not None:
        receipt["sweep_count"] = args.sweep_count
    if args.core_ux_gate is not None:
        receipt["core_ux_gate"] = args.core_ux_gate
    if not args.ack_only:
        _validate_completion_receipt(receipt, source_dispatch_receipt)
        if isinstance(source_dispatch_receipt, dict) and source_dispatch_receipt.get("core_ux"):
            if not args.core_ux_gate or not args.core_ux_gate.strip():
                raise SystemExit("core_ux_gate is required for core_ux steps")

    source_role = profile.seat_roles.get(args.source, "")
    target_role = profile.seat_roles.get(args.target, "")
    receipt_test_policy = _receipt_test_policy(
        profile,
        receipt=receipt,
        task_id=args.task_id,
        source=args.source,
        target=args.target,
        override=args.test_policy,
    )
    if receipt_test_policy:
        receipt["test_policy"] = receipt_test_policy

    summary = args.summary or f"{args.task_id} completed by {args.source}."
    title = args.title or args.task_id
    receipt["kind"] = "completion"
    receipt["status"] = args.status
    receipt["title"] = title
    receipt["summary"] = summary

    if args.enforce_planner_self_closeout and args.source in {"planner", "planner-dispatcher"}:
        _mark_planner_incoming_consumed(_expanded_profile_handoff_dir(profile), args.task_id)

    if args.ack_only:
        ack_line, ack_path = append_consumed_ack_with_fallback(
            profile,
            seat=args.target,
            task_id=args.task_id,
            source=args.source,
        )
        _prune_todo_entry(profile.todo_path(args.source), args.task_id)  # type: ignore[attr-defined]
        receipt["consumed_at"] = utc_now_iso()
        receipt["consumed_ack"] = ack_line
        receipt["todo_path"] = str(ack_path)
        receipt_path = persist_receipt(
            profile,
            seat=args.source,
            primary=receipt_path,
            payload=receipt,
        )
        append_status_dispatch_event(
            profile.status_doc,
            source=args.source,
            task_id=args.task_id,
            verdict=args.verdict,
            commit=args.commit,
            test_policy=receipt_test_policy,
        )
        print(ack_line)
        print(f"receipt: {receipt_path}")
        if _should_announce_planner_event(args.source, args.target, profile=profile):
            _try_announce_planner_event(
                project=profile.project_name,
                source=args.source,
                target=args.target,
                task_id=args.task_id,
                verb="consumed",
            )
        return 0

    _validate_branch_lock(
        receipt,
        source_dispatch_receipt,
        source=args.source,
        target=args.target,
        allow_branch_mismatch=args.allow_branch_mismatch,
    )

    if source_role == "reviewer" and args.verdict not in VALID_VERDICTS:
        raise SystemExit(
            f"{args.source} delivery requires --verdict with a canonical value "
            "because the source seat is a reviewer"
        )

    if args.frontstage_disposition and args.frontstage_disposition not in VALID_FRONTSTAGE_DISPOSITIONS:
        raise SystemExit("invalid --frontstage-disposition; use AUTO_ADVANCE or USER_DECISION_NEEDED")

    frontstage_target_name = str(profile.heartbeat_owner).strip() or "koder"
    frontstage_targeted = args.target in {frontstage_target_name, "koder"}
    planner_to_frontstage = (
        args.source == profile.active_loop_owner
        and frontstage_targeted
    )
    # Guard (followup #22): only planner can close out to the frontstage
    # supervisor (koder). Non-planner specialists that target koder fall
    # into the tmux seat path — but koder runs inside OpenClaw, not as a
    # tmux session, so `notify` silently fails and the Feishu
    # OC_DELEGATION_REPORT_V1 path is skipped (that path is gated on
    # source=planner). The receipt lands on disk but the user never hears
    # about it. Force such specialists back through planner.
    if frontstage_targeted and not planner_to_frontstage:
        raise SystemExit(
            f"complete_handoff to {frontstage_target_name!r} requires "
            f"source={profile.active_loop_owner!r} (got source={args.source!r}). "
            f"Non-planner specialists must close back to planner; planner "
            f"aggregates and forwards to {frontstage_target_name!r} via Feishu "
            f"OC_DELEGATION_REPORT_V1. This enforces canonical chain §6 "
            f"closeout path."
        )
    if planner_to_frontstage:
        if args.frontstage_disposition not in VALID_FRONTSTAGE_DISPOSITIONS:
            raise SystemExit(
                "planner delivery back to frontstage requires --frontstage-disposition "
                "with AUTO_ADVANCE or USER_DECISION_NEEDED"
            )
        if not args.user_summary:
            raise SystemExit("planner delivery back to frontstage requires --user-summary")
        if args.frontstage_disposition == "USER_DECISION_NEEDED" and not args.next_action:
            raise SystemExit(
                "planner delivery with USER_DECISION_NEEDED requires --next-action"
            )

    delivery_path, used_fallback_delivery = persist_delivery(
        profile,
        seat=args.source,
        task_id=args.task_id,
        owner=args.source,
        target=args.target,
        title=title,
        summary=summary,
        status=args.status,
        verdict=args.verdict,
        frontstage_disposition=args.frontstage_disposition,
        user_summary=args.user_summary,
        next_action=args.next_action,
        correlation_id=correlation_id,
        branch=args.branch,
        commit=args.commit,
        sweep_count=args.sweep_count,
        core_ux_gate=args.core_ux_gate,
    )
    source_todo_path = complete_source_queue_if_possible(
        profile,
        seat=args.source,
        task_id=args.task_id,
        summary=summary,
    )
    receipt["delivery_path"] = str(delivery_path)
    receipt["delivered_at"] = utc_now_iso()
    receipt["source_todo_path"] = str(source_todo_path)
    receipt["used_fallback_delivery"] = used_fallback_delivery
    receipt["verdict"] = args.verdict
    receipt["frontstage_disposition"] = args.frontstage_disposition
    receipt["user_summary"] = args.user_summary
    receipt["next_action"] = args.next_action
    if planner_to_frontstage:
        frontstage_todo = profile.todo_path(args.target)
        append_task_to_queue(
            frontstage_todo,
            task_id=args.task_id,
            project=profile.project_name,
            owner=args.target,
            title=title,
            objective=build_frontstage_objective(
                source=args.source,
                task_id=args.task_id,
                delivery_path=str(delivery_path),
                disposition=args.frontstage_disposition or "",
                user_summary=args.user_summary or "",
                next_action=args.next_action,
            ),
            source=args.source,
            reply_to=args.source,
        )
        print(
            f"warn: planner is closing task {args.task_id!r} directly to koder"
            " (self-close path). If this involved implementation, ensure"
            " builder-1 and reviewer-1 were in the loop (R-03 Review Gate).",
            file=sys.stderr,
        )
        receipt["todo_path"] = str(frontstage_todo)
        receipt["assigned_at"] = utc_now_iso()
    # Graceful degrade for external callers (e.g. the ancestor Claude Code
    # running an install via query_memory.py --ask). These callers pass
    # source strings like "memory-client" / "bootstrap-installer" that are
    # not real tmux seats — trying to notify them via send-and-verify.sh
    # fails with a bogus tmux session name.
    target_is_known_seat = args.target in (getattr(profile, "seats", None) or [])
    if not target_is_known_seat and do_notify:
        receipt["notify_skipped"] = "target_not_registered_seat"
        # Auditable: we KNOW we skipped; caller can inspect receipt JSON.
        print(
            f"notify_skipped: target {args.target!r} is not a registered seat; "
            "completion receipt written but no tmux/Feishu notification sent.",
            file=sys.stderr,
        )
        do_notify = False

    if do_notify:
        message = build_completion_message(
            args.task_id,
            delivery_path,
            source=args.source,
            target=args.target,
            user_summary=args.user_summary,
        )
        # Resolve target kind via seat_resolver — determines Feishu vs tmux path.
        resolution = resolve_seat_from_profile(args.target, profile)
        openclaw_koder = planner_to_frontstage and resolution.kind == "openclaw"
        if openclaw_koder:
            # ── OpenClaw koder path ────────────────────────────────────────────
            # Send OC_DELEGATION_REPORT_V1 directly. Never attempt tmux for this case.
            # Pass project so send_feishu_user_message resolves the group from BRIDGE.toml
            # rather than the first global entry in openclaw.json.
            delegation_report = build_delegation_report_text(
                project=profile.project_name,
                lane="planning",
                task_id=args.task_id,
                dispatch_nonce=stable_dispatch_nonce(
                    profile.project_name,
                    "planning",
                    args.task_id,
                ),
                report_status=(
                    "done"
                    if args.frontstage_disposition == "AUTO_ADVANCE"
                    else "needs_decision"
                ),
                decision_hint=(
                    "proceed"
                    if args.frontstage_disposition == "AUTO_ADVANCE"
                    else "ask_user"
                ),
                user_gate=(
                    "none"
                    if args.frontstage_disposition == "AUTO_ADVANCE"
                    else "required"
                ),
                next_action=(
                    "consume_closeout"
                    if args.frontstage_disposition == "AUTO_ADVANCE"
                    else "ask_user"
                ),
                summary=args.user_summary or args.summary or args.title or args.task_id,
                human_summary=args.user_summary or args.summary or args.title,
            )
            _broadcast = None
            for _attempt in range(3):
                _broadcast = send_feishu_user_message(
                    delegation_report, project=profile.project_name
                )
                if _broadcast.get("status") != "failed":
                    break
                if _attempt < 2:
                    time.sleep(2 ** _attempt)  # 1s then 2s
            broadcast = _broadcast
            receipt["feishu_delegation_report"] = broadcast
            if broadcast.get("status") == "failed":
                detail = (
                    broadcast.get("stderr")
                    or broadcast.get("stdout")
                    or broadcast.get("reason", "unknown")
                )
                raise RuntimeError(
                    f"completion notify (feishu openclaw koder) failed after 3 attempts"
                    f" for {args.task_id}: {detail}"
                )
            if broadcast.get("status") != "failed":
                receipt["notified_at"] = utc_now_iso()
            receipt["notify_message"] = message
        else:
            # ── tmux seat path (local CLI koder or any non-frontstage seat) ───
            result = notify(profile, args.target, message)
            require_success(result, "completion notify")
            receipt["notified_at"] = utc_now_iso()
            receipt["notify_message"] = message
            # Legacy group broadcast is opt-in and only applies to tmux-mode transitions.
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
                    broadcast_message = (
                        f"{profile.project_name} 项目 planner 阶段收尾 {args.task_id}："
                        f"{args.user_summary or args.summary or args.title or args.task_id}。"
                        f" FrontstageDisposition={args.frontstage_disposition or 'n/a'}."
                    )
                elif target_role in {"planner", "planner-dispatcher"} and source_role not in {
                    "planner",
                    "planner-dispatcher",
                }:
                    broadcast_message = (
                        f"{profile.project_name} 项目 planner 已收到回执 {args.task_id}，"
                        f"来自 {args.source}。{args.summary or args.title or ''}".strip()
                    )
                else:
                    broadcast_message = (
                        f"{profile.project_name} 项目 planner 完成任务流转 {args.task_id}："
                        f"{args.source} -> {args.target}。"
                    )
                broadcast = broadcast_feishu_group_message(broadcast_message, project=profile.project_name)
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
    if do_notify:
        assert (
            receipt.get("notified_at")
            or receipt.get("notify_skipped")
            or receipt.get("feishu_delegation_report", {}).get("status") == "ok"
        ), "notify path produced no observable success/skip marker"
    receipt_path = persist_receipt(
        profile,
        seat=args.source,
        primary=receipt_path,
        payload=receipt,
    )
    _write_completion_to_ledger(
        task_id=args.task_id,
        project=profile.project_name,
        source=args.source,
        disposition=args.frontstage_disposition or "",
    )
    append_status_dispatch_event(
        profile.status_doc,
        source=args.source,
        task_id=args.task_id,
        verdict=args.verdict,
        commit=args.commit,
        test_policy=receipt_test_policy,
    )
    print(f"completed {args.task_id} -> {args.target}")
    print(f"delivery: {delivery_path}")
    print(f"receipt: {receipt_path}")
    if _should_announce_planner_event(args.source, args.target, profile=profile):
        _try_announce_planner_event(
            project=profile.project_name,
            source=args.source,
            target=args.target,
            task_id=args.task_id,
            verb="delivered",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
