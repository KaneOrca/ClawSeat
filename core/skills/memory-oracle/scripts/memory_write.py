#!/usr/bin/env python3
"""
memory_write.py — write a structured memory fact to the knowledge base.

Usage:
    python3 memory_write.py \\
        --kind decision \\
        --project install \\
        --title "Use option B" \\
        --body "We chose B because..." \\
        --author planner \\
        [--evidence '[{"type":"file","value":"SPEC.md","trust":"high","source_url":"https://..."}]'] \\
        [--related-task-ids T-001,T-002] \\
        [--confidence high|medium|low] \\
        [--source write_api] \\
        [--supersedes <old-id>] \\
        [--seats seat1,seat2]    # whitelist for author governance check \\
        [--memory-dir ~/.agents/memory]  # override root \\
        [--dry-run]              # validate but do not write

Exit codes:
    0  success (or dry-run validation passed)
    1  schema validation failed (hard error)
    2  bad CLI usage / invalid JSON
    Stdout: JSON with {id, path, warnings} on success, or record JSON on dry-run.
    Stderr: warnings (soft governance) or error messages.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _memory_paths import (  # noqa: E402
    MEMORY_ROOT,
    KIND_SUBDIRS,
    SHARED_KIND_SUBDIRS,
    generate_id,
    reflections_path,
)
from _memory_schema import SchemaError, make_record, validate  # noqa: E402


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fact_path(kind: str, project: str, fact_id: str, memory_root: Path) -> Path:
    """Resolve storage path relative to a given memory_root."""
    if project == "_shared":
        subdir_name = SHARED_KIND_SUBDIRS.get(kind, f"{kind}s")
        return memory_root / "shared" / subdir_name / f"{fact_id}.json"
    if kind == "reflection":
        return reflections_path(project, memory_root=memory_root)
    subdir_name = KIND_SUBDIRS.get(kind)
    if subdir_name:
        return memory_root / "projects" / project / subdir_name / f"{fact_id}.json"
    return memory_root / "projects" / project / f"{fact_id}.json"


def _write_fact(record: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False, sort_keys=False),
        encoding="utf-8",
    )
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _append_jsonl(record: dict, path: Path) -> None:
    """Append one JSON record as a single line to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, sort_keys=False) + "\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Write a memory fact to the structured knowledge base."
    )
    p.add_argument("--kind", required=True, help="Fact kind (decision, finding, …)")
    p.add_argument("--project", required=True, help="Project name or '_shared'")
    p.add_argument("--title", required=True, help="Short title")
    p.add_argument("--body", default="", help="Long-form body (markdown OK)")
    p.add_argument("--author", required=True, help="Author seat name")
    p.add_argument(
        "--evidence",
        default="[]",
        help=(
            "JSON array of evidence items. "
            'library_knowledge/finding require trust+source_url on each item. '
            'Example: \'[{"type":"file","value":"SPEC.md","trust":"high","source_url":"https://..."}]\''
        ),
    )
    p.add_argument(
        "--related-task-ids",
        default="",
        help="Comma-separated task IDs (e.g. T-001,T-002)",
    )
    p.add_argument(
        "--confidence",
        default="medium",
        choices=["high", "medium", "low"],
        help="Confidence level (default: medium)",
    )
    p.add_argument(
        "--source",
        default="write_api",
        choices=["scanner", "write_api", "reflection", "event_derived", "research"],
        help="Provenance source (default: write_api)",
    )
    p.add_argument("--supersedes", default=None, help="ID of the record this supersedes")
    p.add_argument(
        "--seats",
        default="",
        help="Comma-separated authorised seat names for author governance (soft check)",
    )
    p.add_argument(
        "--memory-dir",
        default=str(MEMORY_ROOT),
        help=f"Memory root directory (default: {MEMORY_ROOT})",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate schema and print the record without writing to disk",
    )
    p.add_argument("--quiet", action="store_true", help="Suppress stdout output")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    # ── Parse evidence JSON ──────────────────────────────────────────
    try:
        evidence: list[dict] = json.loads(args.evidence)
    except json.JSONDecodeError as exc:
        print(f"error: --evidence is not valid JSON: {exc}", file=sys.stderr)
        return 2

    if not isinstance(evidence, list):
        print("error: --evidence must be a JSON array", file=sys.stderr)
        return 2

    # ── Parse related_task_ids ───────────────────────────────────────
    related = [t.strip() for t in args.related_task_ids.split(",") if t.strip()]

    # ── Parse seats for soft author governance ───────────────────────
    known_authors: list[str] | None = (
        [s.strip() for s in args.seats.split(",") if s.strip()] or None
    )

    ts = now_iso()
    fact_id = generate_id(args.kind, args.project, args.title)

    record = make_record(
        kind=args.kind,
        project=args.project,
        author=args.author,
        ts=ts,
        title=args.title,
        body=args.body,
        fact_id=fact_id,
        evidence=evidence,
        related_task_ids=related,
        supersedes=args.supersedes,
        confidence=args.confidence,
        source=args.source,
    )

    # ── Validate (hard failures raise, soft failures return warnings) ─
    try:
        warnings = validate(record, known_authors=known_authors)
    except SchemaError as exc:
        print(f"error: schema validation failed: {exc}", file=sys.stderr)
        return 1

    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)

    if args.dry_run:
        if not args.quiet:
            print(json.dumps(record, indent=2, ensure_ascii=False))
        return 0

    # ── Write to disk ────────────────────────────────────────────────
    memory_root = Path(args.memory_dir).expanduser().resolve()
    out_path = _fact_path(args.kind, args.project, fact_id, memory_root)

    if args.kind == "reflection":
        _append_jsonl(record, out_path)
    else:
        _write_fact(record, out_path)

    if not args.quiet:
        result = {
            "id": fact_id,
            "path": str(out_path),
            "warnings": warnings,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
