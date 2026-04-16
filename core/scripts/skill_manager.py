#!/usr/bin/env python3
"""ClawSeat skill manager CLI — check, list, and diff-template."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure core/ is importable.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_CORE_PATH = str(_REPO_ROOT / "core")
if _CORE_PATH not in sys.path:
    sys.path.insert(0, _CORE_PATH)

from skill_registry import (
    SkillCheckResult,
    diff_template,
    load_registry,
    validate_all,
)


def cmd_check(args: argparse.Namespace) -> int:
    result: SkillCheckResult = validate_all(
        role=args.role,
        source=args.source,
    )
    if args.json:
        out = {
            "all_present": result.all_present,
            "required_missing": len(result.required_missing),
            "optional_missing": len(result.optional_missing),
            "items": [
                {
                    "name": i.name,
                    "source": i.source,
                    "path": i.expanded_path,
                    "exists": i.exists,
                    "required": i.required,
                    "fix_hint": i.fix_hint,
                }
                for i in result.items
            ],
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        for line in result.summary_lines():
            print(line)

    if result.required_missing:
        return 1
    if result.optional_missing:
        return 2
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    entries = load_registry()
    if args.role:
        from skill_registry import skills_for_role
        entries = skills_for_role(entries, args.role)
    if args.source:
        from skill_registry import skills_for_source
        entries = skills_for_source(entries, args.source)

    if args.json:
        out = [
            {
                "name": e.name,
                "source": e.source,
                "path": e.path,
                "required": e.required,
                "roles": e.roles,
                "description": e.description,
            }
            for e in entries
        ]
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        for e in entries:
            req = "required" if e.required else "optional"
            roles = ", ".join(e.roles) if e.roles else "(entry skill)"
            print(f"  {e.name} [{e.source}] ({req})")
            print(f"    path:  {e.path}")
            print(f"    roles: {roles}")
            if e.description:
                print(f"    desc:  {e.description}")
    return 0


def cmd_diff_template(args: argparse.Namespace) -> int:
    result = diff_template(args.template)
    if "error" in result:
        for msg in result["error"]:
            print(f"error: {msg}", file=sys.stderr)
        return 1

    unregistered = result.get("unregistered", [])
    uncovered = result.get("uncovered", [])

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if unregistered:
            print(f"Unregistered skills in template (not in registry):")
            for p in unregistered:
                print(f"  - {p}")
        if uncovered:
            print(f"Registry skills not assigned in template:")
            for name in uncovered:
                print(f"  - {name}")
        if not unregistered and not uncovered:
            print(f"Template '{args.template}' is fully consistent with the registry.")

    return 1 if unregistered else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="skill_manager",
        description="ClawSeat skill registry management",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # check
    p_check = sub.add_parser("check", help="Validate skill paths")
    p_check.add_argument("--role", help="Filter by role (e.g. planner-dispatcher)")
    p_check.add_argument("--source", help="Filter by source (bundled/gstack/agent)")
    p_check.add_argument("--json", action="store_true", help="JSON output")

    # list
    p_list = sub.add_parser("list", help="List registered skills")
    p_list.add_argument("--role", help="Filter by role")
    p_list.add_argument("--source", help="Filter by source")
    p_list.add_argument("--json", action="store_true", help="JSON output")

    # diff-template
    p_diff = sub.add_parser("diff-template", help="Compare template vs registry")
    p_diff.add_argument("template", help="Template name (e.g. gstack-harness)")
    p_diff.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()
    if args.command == "check":
        return cmd_check(args)
    elif args.command == "list":
        return cmd_list(args)
    elif args.command == "diff-template":
        return cmd_diff_template(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
