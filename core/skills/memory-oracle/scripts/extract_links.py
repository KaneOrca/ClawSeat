#!/usr/bin/env python3
"""
extract_links.py — deterministic typed-link extraction for memory pages.

Reads a memory page (.md or .json), extracts entity references via regex
(zero LLM calls), and writes typed edges to two JSONL indexes:

    ~/.agents/memory/_links/<flat-source>.jsonl       (outgoing edges)
    ~/.agents/memory/_backlinks/<flat-target>.jsonl   (incoming edges)

Source slugs are paths relative to MEMORY_ROOT, sans extension. External
entities (task IDs, commits, URLs, ...) live in the namespace `entity:<type>:<value>`.

Usage:
    python3 extract_links.py --file <path> [--memory-dir <root>] [--quiet]

Idempotent: re-running on the same file updates the source's outgoing edges
and reconciles backlinks (removes stale entries, appends new).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _memory_paths import MEMORY_ROOT  # noqa: E402

# ── Edge-type regex patterns (deterministic, project-aware but generic) ────

PATTERNS: list[tuple[str, str, re.Pattern]] = [
    # (edge_type, entity_namespace, compiled regex)
    ("references-task", "taskid", re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")),
    ("references-commit", "commit", re.compile(r"\bcommit\s+([a-f0-9]{7,40})\b", re.IGNORECASE)),
    ("references-commit", "commit", re.compile(r"\b([a-f0-9]{7,40})\b(?=\s+[A-Z]|$|\s*[—–])")),
    ("references-component", "component", re.compile(r"\b([A-Z][a-zA-Z0-9]+(?:Phasic|Physic|View|Engine|Layer|Component))\b")),
    ("references-file", "file", re.compile(r"\b([a-zA-Z][\w./-]*\.(?:tsx|ts|py|md|toml|sh|json|yaml|yml|sql|js))\b")),
    ("references-url", "url", re.compile(r"(https?://[^\s)\]\"<>]+)")),
    ("references-key", "key", re.compile(r"\[KEY:\s*([^\]]+)\]")),
    ("references-project", "project", re.compile(r"~/\.agents/memory/projects/([a-zA-Z][\w-]*)\b")),
]

_SNIPPET_RADIUS = 60
_FLAT_PATH_SEP = "__"
_FLAT_NS_SEP = "++"


def _flat(slug: str) -> str:
    """Encode a slug into a filesystem-safe flat name."""
    return slug.replace("/", _FLAT_PATH_SEP).replace(":", _FLAT_NS_SEP)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _source_slug(file_path: Path, memory_root: Path) -> str | None:
    """Derive source slug as MEMORY_ROOT-relative path, no extension.

    Returns None if file_path is not under memory_root.
    """
    try:
        rel = file_path.resolve().relative_to(memory_root.resolve())
    except ValueError:
        return None
    return str(rel.with_suffix(""))


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _snippet(text: str, start: int, end: int) -> str:
    """Return ~120 char window around match, single-line, no leading/trailing ws."""
    s = max(0, start - _SNIPPET_RADIUS)
    e = min(len(text), end + _SNIPPET_RADIUS)
    window = text[s:e].replace("\n", " ").strip()
    return re.sub(r"\s+", " ", window)


def extract_edges(text: str) -> list[dict]:
    """Run all regex patterns over text. Returns deduped edges with snippets."""
    seen: dict[tuple[str, str], dict] = {}
    for edge_type, namespace, pattern in PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(1)
            target = f"entity:{namespace}:{value}"
            key = (edge_type, target)
            if key in seen:
                continue
            seen[key] = {
                "to": target,
                "type": edge_type,
                "snippet": _snippet(text, match.start(), match.end()),
            }
    return list(seen.values())


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")
    tmp.write_text(text, encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return out


def _write_jsonl(path: Path, records: list[dict]) -> None:
    if not records:
        if path.is_file():
            try:
                path.unlink()
            except OSError:
                pass
        return
    text = "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in records) + "\n"
    _atomic_write(path, text)


def _backlinks_path(memory_root: Path, target: str) -> Path:
    return memory_root / "_backlinks" / f"{_flat(target)}.jsonl"


def _links_path(memory_root: Path, source: str) -> Path:
    return memory_root / "_links" / f"{_flat(source)}.jsonl"


def update_indexes(source: str, edges: list[dict], memory_root: Path) -> dict:
    """Reconcile both indexes for `source`.

    1. Read current outgoing edges (old)
    2. Compute diff: removed targets, added targets
    3. Write new outgoing index for `source`
    4. For each removed target: rewrite its backlinks file (drop this source)
    5. For each added target: append to its backlinks file

    Returns a summary of what changed.
    """
    links_path = _links_path(memory_root, source)
    old_edges = _read_jsonl(links_path)
    old_targets = {e.get("to") for e in old_edges if e.get("to")}
    new_targets = {e.get("to") for e in edges if e.get("to")}

    removed = old_targets - new_targets
    added = new_targets - old_targets
    timestamp = _now_iso()

    # New outgoing index includes timestamp + edges
    out_records = [
        {**edge, "from": source, "extracted_at": timestamp}
        for edge in edges
    ]
    _write_jsonl(links_path, out_records)

    # Drop this source from removed targets' backlinks
    for target in removed:
        bl_path = _backlinks_path(memory_root, target)
        existing = _read_jsonl(bl_path)
        retained = [r for r in existing if r.get("from") != source]
        _write_jsonl(bl_path, retained)

    # Append this source to added/updated targets' backlinks
    for edge in out_records:
        target = edge["to"]
        bl_path = _backlinks_path(memory_root, target)
        existing = _read_jsonl(bl_path)
        # Drop any prior entry from this source for this target (idempotency)
        existing = [r for r in existing if r.get("from") != source]
        existing.append({
            "from": source,
            "type": edge["type"],
            "snippet": edge["snippet"],
            "extracted_at": timestamp,
        })
        _write_jsonl(bl_path, existing)

    return {
        "source": source,
        "edges_total": len(edges),
        "targets_added": sorted(added),
        "targets_removed": sorted(removed),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Extract typed links from a memory page.")
    p.add_argument("--file", required=True, help="Path to memory page (.md or .json)")
    p.add_argument(
        "--memory-dir",
        default=str(MEMORY_ROOT),
        help=f"Memory root directory (default: {MEMORY_ROOT})",
    )
    p.add_argument("--quiet", action="store_true", help="Suppress stdout summary")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    file_path = Path(args.file).expanduser()
    memory_root = Path(args.memory_dir).expanduser().resolve()

    if not file_path.is_file():
        print(f"error: not a file: {file_path}", file=sys.stderr)
        return 2

    source = _source_slug(file_path, memory_root)
    if source is None:
        print(f"error: file is not under memory root {memory_root}: {file_path}", file=sys.stderr)
        return 2

    text = _read_text(file_path)
    edges = extract_edges(text) if text else []
    summary = update_indexes(source, edges, memory_root)

    if not args.quiet:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
