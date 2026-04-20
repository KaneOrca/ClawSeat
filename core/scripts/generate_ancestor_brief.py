"""generate_ancestor_brief.py — derive an executable ancestor brief from ancestor-runbook.md.

Usage:
    generate_ancestor_brief.py --project <name> --koder-agent <agent> \
        --feishu-group-id <oc_xxx> [--mode ancestor] [--output <path>]

Parses the canonical ancestor-runbook.md, substitutes project variables, and
emits a brief.md that can be followed step-by-step. Replaces hand-written briefs
that may embed B1-B6 anti-patterns.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNBOOK = _REPO_ROOT / "core" / "skills" / "clawseat-install" / "references" / "ancestor-runbook.md"

_PHASE_HEADING_RE = re.compile(r"^## Phase \d+", re.MULTILINE)


def _load_runbook(runbook_path: Path) -> str:
    if not runbook_path.exists():
        raise FileNotFoundError(f"ancestor-runbook.md not found at {runbook_path}")
    return runbook_path.read_text(encoding="utf-8")


def _extract_phases(text: str) -> list[str]:
    """Return list of phase sections (## Phase N … up to next ## Phase or end)."""
    parts = _PHASE_HEADING_RE.split(text)
    headings = _PHASE_HEADING_RE.findall(text)
    if not headings:
        return []
    return [f"{h}\n{body.lstrip()}" for h, body in zip(headings, parts[1:])]


def _substitute(text: str, project: str, koder_agent: str, feishu_group_id: str) -> str:
    """Replace canonical placeholders with actual values."""
    replacements = {
        "<PROJECT>": project,
        "${PROJECT}": project,
        '"$PROJECT"': f'"{project}"',
        "<AGENT_NAME>": koder_agent,
        "<AGENT>": koder_agent,
        "<GROUP_ID>": feishu_group_id,
        "<oc_xxx>": feishu_group_id,
    }
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    return text


def generate(
    project: str,
    koder_agent: str,
    feishu_group_id: str,
    *,
    runbook_path: Path | None = None,
    mode: str = "ancestor",
) -> str:
    runbook_path = runbook_path or _RUNBOOK
    raw = _load_runbook(runbook_path)
    phases = _extract_phases(raw)

    if not phases:
        raise ValueError("No Phase sections found in runbook — check ancestor-runbook.md format")

    header = (
        f"# Ancestor Brief — {project}\n\n"
        f"Generated from: ancestor-runbook.md (canonical SOP)\n"
        f"Project: {project} | Koder agent: {koder_agent} | Feishu group: {feishu_group_id}\n"
        f"Mode: {mode}\n\n"
        "---\n\n"
        "**Reversibility check**: after completing all phases, run:\n"
        f"```bash\npython3 $CLAWSEAT_ROOT/core/scripts/install_complete.py --project {project}\n```\n"
        "Expected: RESULT: PASS\n\n"
        "---\n\n"
    )

    body = "\n\n".join(phases)
    full = header + body
    return _substitute(full, project, koder_agent, feishu_group_id)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--project", required=True, help="Project name (e.g. hardening-b)")
    p.add_argument("--koder-agent", required=True, help="OpenClaw agent name (e.g. mor)")
    p.add_argument("--feishu-group-id", required=True, help="Feishu group ID (oc_xxx)")
    p.add_argument("--mode", default="ancestor", help="Brief mode (default: ancestor)")
    p.add_argument("--output", default=None, help="Output path (default: stdout)")
    p.add_argument("--runbook", default=None, help="Override runbook path (for testing)")
    args = p.parse_args(argv)

    runbook_path = Path(args.runbook) if args.runbook else None
    try:
        brief = generate(
            args.project,
            args.koder_agent,
            args.feishu_group_id,
            runbook_path=runbook_path,
            mode=args.mode,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.output:
        Path(args.output).write_text(brief, encoding="utf-8")
        print(f"brief written to {args.output}")
    else:
        print(brief)

    return 0


if __name__ == "__main__":
    sys.exit(main())
