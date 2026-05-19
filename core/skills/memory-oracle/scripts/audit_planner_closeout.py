#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_ROOT = _SCRIPTS_DIR.parents[3]
_HARNESS_SCRIPTS = _ROOT / "core" / "skills" / "gstack-harness" / "scripts"
for _path in (_HARNESS_SCRIPTS, _SCRIPTS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from _common import load_profile, sanitize_name  # noqa: E402


def _expand_path(value: object | None) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return Path(os.path.expandvars(text)).expanduser().resolve()


def _delivery_task_id(delivery_path: Path) -> str | None:
    try:
        lines = delivery_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower().startswith("task_id"):
            _, _, value = stripped.partition(":")
            value = value.strip()
            return value or None
        continue
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit planner closeout artifacts.")
    parser.add_argument("--profile", required=True, help="Path to the project profile TOML.")
    parser.add_argument("--task-id", required=True, help="Task id.")
    return parser.parse_args()


def _resolve_planner_seats(profile: object) -> list[str]:
    """Return ordered list of planner seat names to check.

    Prefers team-scoped planner seats from profile.seat_roles (roles
    'planner' or 'planner-dispatcher') then appends the legacy 'planner'
    fallback so both naming conventions are covered.
    """
    planner_roles = {"planner", "planner-dispatcher"}
    seat_roles: dict = getattr(profile, "seat_roles", None) or {}
    team_planners = [
        str(seat)
        for seat, role in seat_roles.items()
        if str(role).lower() in planner_roles
    ]
    # Always append legacy 'planner' so old single-team receipts still pass.
    # De-duplicate while preserving team-scoped order first.
    if "planner" not in team_planners:
        team_planners.append("planner")
    return team_planners


def main() -> int:
    args = parse_args()
    profile = load_profile(_expand_path(args.profile))
    handoff_dir = _expand_path(getattr(profile, "handoff_dir"))  # type: ignore[arg-type]
    if handoff_dir is None:
        raise SystemExit("profile missing handoff_dir")

    task_key = sanitize_name(args.task_id)
    planner_seats = _resolve_planner_seats(profile)
    errors: list[str] = []

    # Check 1: consumed receipt — any planner seat delivered to
    consumed_matches: list[Path] = []
    for seat in planner_seats:
        consumed_matches.extend(handoff_dir.glob(f"{task_key}__*__{sanitize_name(seat)}.json.consumed"))
    if not consumed_matches:
        seats_tried = ", ".join(planner_seats)
        errors.append(
            f".consumed missing: searched {handoff_dir} for"
            f" {task_key}__*__{{{seats_tried}}}.json.consumed"
        )

    # Check 2: planner→memory receipt — any planner seat sent to memory
    receipt_path: Path | None = None
    for seat in planner_seats:
        candidate = handoff_dir / f"{task_key}__{sanitize_name(seat)}__memory.json"
        if candidate.is_file():
            receipt_path = candidate
            break
    if receipt_path is None:
        seats_tried = ", ".join(planner_seats)
        errors.append(
            f"planner→memory receipt missing: searched {handoff_dir} for"
            f" {task_key}__{{{seats_tried}}}__memory.json"
        )

    # Check 3: planner DELIVERY.md with matching task_id — any planner seat workspace
    delivery_found = False
    delivery_error: str | None = None
    for seat in planner_seats:
        try:
            dp = Path(profile.delivery_path(seat))  # type: ignore[attr-defined]
        except Exception:
            continue
        actual_task_id = _delivery_task_id(dp)
        if actual_task_id is None:
            # File missing for this seat; try next
            delivery_error = f"planner DELIVERY.md missing: {dp}"
            continue
        if actual_task_id != args.task_id:
            delivery_error = (
                f"planner DELIVERY.md task_id mismatch: expected {args.task_id},"
                f" got {actual_task_id} (in {dp})"
            )
            # task_id mismatch is an error for this seat but keep checking others
            continue
        delivery_found = True
        break
    if not delivery_found:
        if delivery_error:
            errors.append(delivery_error)
        else:
            seats_tried = ", ".join(planner_seats)
            errors.append(
                f"planner DELIVERY.md missing: checked seats {{{seats_tried}}}"
            )

    if errors:
        for line in errors:
            print(line)
        return 1

    print("all 3 artifacts present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
