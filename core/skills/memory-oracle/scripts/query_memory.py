#!/usr/bin/env python3
"""
query_memory.py — query the Memory CC knowledge base.

Two modes:
  1. Direct read (fast, key-value) — reads ~/.agents/memory/*.json directly
     python3 query_memory.py --key credentials.keys.MINIMAX_API_KEY
     python3 query_memory.py --search feishu
     python3 query_memory.py --file openclaw --section feishu

  2. Ask Memory CC TUI (slow, reasoning) — writes to TODO, waits for response
     python3 query_memory.py --ask "designer seat uses which provider?"

Zero third-party dependencies.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
DEFAULT_MEMORY_DIR = HOME / ".agents" / "memory"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_memory_file(memory_dir: Path, name: str) -> dict | None:
    path = memory_dir / f"{name}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def walk_path(data: dict | list, path_parts: list[str]) -> object | None:
    """Walk a dotted path through nested dict/list."""
    current: object = data
    for part in path_parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
        if current is None:
            return None
    return current


def cmd_key(memory_dir: Path, key: str) -> int:
    """Read a dotted path like 'credentials.keys.MINIMAX_API_KEY.value'."""
    parts = key.split(".")
    if not parts:
        print("error: empty key", file=sys.stderr)
        return 2
    file_name = parts[0]
    data = load_memory_file(memory_dir, file_name)
    if data is None:
        print(f"error: memory file not found: {memory_dir / (file_name + '.json')}", file=sys.stderr)
        return 1
    if len(parts) == 1:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    value = walk_path(data, parts[1:])
    if value is None:
        print(f"not_found: {key}", file=sys.stderr)
        return 1
    if isinstance(value, (dict, list)):
        print(json.dumps(value, indent=2, ensure_ascii=False))
    else:
        print(value)
    return 0


def cmd_file(memory_dir: Path, name: str, section: str | None) -> int:
    data = load_memory_file(memory_dir, name)
    if data is None:
        print(f"error: memory file not found: {memory_dir / (name + '.json')}", file=sys.stderr)
        return 1
    if section:
        value = walk_path(data, section.split("."))
        if value is None:
            print(f"not_found: {name}.{section}", file=sys.stderr)
            return 1
        data = value  # type: ignore
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


def flatten(obj: object, prefix: str = "") -> list[tuple[str, object]]:
    """Flatten nested dict/list into (dotted_path, value) pairs."""
    out: list[tuple[str, object]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                out.extend(flatten(v, key))
            else:
                out.append((key, v))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            key = f"{prefix}.{i}" if prefix else str(i)
            if isinstance(v, (dict, list)):
                out.extend(flatten(v, key))
            else:
                out.append((key, v))
    return out


def cmd_search(memory_dir: Path, term: str, *, files: list[str] | None = None) -> int:
    """Case-insensitive search across all memory files for term in keys or values."""
    term_lower = term.lower()
    targets: list[str]
    if files:
        targets = files
    else:
        targets = [p.stem for p in memory_dir.glob("*.json") if p.stem != "response"]
    matches: list[dict] = []
    for fname in targets:
        data = load_memory_file(memory_dir, fname)
        if data is None:
            continue
        for path, value in flatten(data):
            key_hit = term_lower in path.lower()
            val_hit = term_lower in str(value).lower()
            if key_hit or val_hit:
                matches.append({
                    "file": fname,
                    "path": path,
                    "value": str(value)[:200],
                    "match": "key" if key_hit else "value",
                })
    if not matches:
        print(f"no matches for: {term}", file=sys.stderr)
        return 1
    print(json.dumps({"term": term, "count": len(matches), "matches": matches}, indent=2, ensure_ascii=False))
    return 0


def cmd_ask(question: str, *, profile_path: str | None, timeout: float) -> int:
    """Ask Memory CC via dispatch_task.py + poll response.json."""
    if not profile_path:
        print("error: --ask requires --profile <profile.toml>", file=sys.stderr)
        return 2

    # Build task_id from timestamp
    task_id = f"MEMORY-QUERY-{int(time.time())}"
    response_path = DEFAULT_MEMORY_DIR / "response.json"
    # Clear stale response
    if response_path.exists():
        try:
            response_path.unlink()
        except OSError:
            pass

    # Locate dispatch_task.py (walks up from this script)
    script_dir = Path(__file__).resolve().parent
    # memory-oracle/scripts/ -> skills/ -> core/skills/ -> we need sibling gstack-harness/scripts
    clawseat_root = script_dir.parents[3]
    dispatch = clawseat_root / "core" / "skills" / "gstack-harness" / "scripts" / "dispatch_task.py"
    if not dispatch.is_file():
        print(f"error: dispatch_task.py not found at {dispatch}", file=sys.stderr)
        return 2

    import subprocess
    cmd = [
        "python3", str(dispatch),
        "--profile", profile_path,
        "--source", "memory-client",
        "--target", "memory",
        "--task-id", task_id,
        "--title", "Memory query",
        "--objective", question,
    ]
    dispatch_result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if dispatch_result.returncode != 0:
        print(f"error: dispatch failed: {dispatch_result.stderr}", file=sys.stderr)
        return 1

    # Poll response.json
    deadline = time.time() + timeout
    while time.time() < deadline:
        if response_path.exists():
            try:
                response = json.loads(response_path.read_text(encoding="utf-8"))
                if response.get("query_id") == task_id:
                    # Auto-verify claims against disk before returning
                    verified = verify_claims(response, DEFAULT_MEMORY_DIR)
                    response["verification"] = verified
                    print(json.dumps(response, indent=2, ensure_ascii=False))
                    # Exit 0 only if all claims verified, 3 if any failed
                    return 0 if verified["all_verified"] else 3
            except json.JSONDecodeError:
                pass
        time.sleep(1)
    print(f"error: timed out waiting for response after {timeout}s", file=sys.stderr)
    return 1


def verify_claims(response: dict, memory_dir: Path) -> dict:
    """Verify each claim's evidence against disk JSON files.

    Each claim has shape:
        {statement, evidence: [{file, path, expected_value}, ...]}

    Returns:
        {all_verified: bool, claim_results: [{statement, verified, mismatches: [...]}]}
    """
    claims = response.get("claims")
    # Back-compat: old schema has flat "answer" + "sources" strings
    if claims is None:
        legacy_sources = response.get("sources", [])
        return {
            "all_verified": None,
            "reason": "legacy_schema_no_evidence",
            "legacy_sources": legacy_sources,
        }

    if not isinstance(claims, list):
        return {"all_verified": False, "reason": "claims_not_list"}

    results = []
    all_ok = True
    for i, claim in enumerate(claims):
        if not isinstance(claim, dict):
            results.append({"index": i, "verified": False, "reason": "claim_not_dict"})
            all_ok = False
            continue
        statement = claim.get("statement", "")
        evidence_list = claim.get("evidence", [])
        if not evidence_list:
            results.append({
                "index": i,
                "statement": statement[:80],
                "verified": False,
                "reason": "no_evidence",
            })
            all_ok = False
            continue
        mismatches = []
        for ev in evidence_list:
            fname = ev.get("file", "")
            path = ev.get("path", "")
            expected = ev.get("expected_value")
            # strip .json extension if present
            if fname.endswith(".json"):
                fname = fname[:-5]
            data = load_memory_file(memory_dir, fname)
            if data is None:
                mismatches.append({"file": fname, "path": path, "reason": "file_not_found"})
                continue
            actual = walk_path(data, path.split(".")) if path else data
            if actual != expected:
                mismatches.append({
                    "file": fname,
                    "path": path,
                    "expected": expected,
                    "actual": actual,
                    "reason": "mismatch" if actual is not None else "path_not_found",
                })
        verified = len(mismatches) == 0
        results.append({
            "index": i,
            "statement": statement[:80],
            "verified": verified,
            "mismatches": mismatches,
        })
        if not verified:
            all_ok = False
    return {"all_verified": all_ok, "claim_results": results}


def cmd_status(memory_dir: Path) -> int:
    """Print memory DB status."""
    if not memory_dir.is_dir():
        print(json.dumps({"exists": False, "path": str(memory_dir)}, indent=2))
        return 1
    index_data = load_memory_file(memory_dir, "index")
    files = sorted(p.name for p in memory_dir.glob("*.json"))
    result = {
        "exists": True,
        "path": str(memory_dir),
        "files": files,
        "index": index_data,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Query the Memory CC knowledge base.")
    p.add_argument(
        "--memory-dir",
        default=str(DEFAULT_MEMORY_DIR),
        help=f"Memory DB root (default: {DEFAULT_MEMORY_DIR})",
    )
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--key", help="Dotted path, e.g. credentials.keys.MINIMAX_API_KEY")
    group.add_argument("--file", help="Dump a single memory file (e.g. openclaw)")
    group.add_argument("--search", help="Case-insensitive search across all files")
    group.add_argument("--ask", help="Ask Memory CC TUI (requires --profile)")
    group.add_argument("--status", action="store_true", help="Show memory DB status")
    p.add_argument("--section", help="With --file: dotted sub-path to extract")
    p.add_argument("--profile", help="With --ask: profile TOML for dispatch")
    p.add_argument("--timeout", type=float, default=60.0, help="With --ask: poll timeout seconds")
    p.add_argument("--files", help="With --search: comma-separated file names to restrict scope")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    memory_dir = Path(args.memory_dir).expanduser().resolve()

    if args.status:
        return cmd_status(memory_dir)
    if args.key:
        return cmd_key(memory_dir, args.key)
    if args.file:
        return cmd_file(memory_dir, args.file, args.section)
    if args.search:
        files = args.files.split(",") if args.files else None
        return cmd_search(memory_dir, args.search, files=files)
    if args.ask:
        return cmd_ask(args.ask, profile_path=args.profile, timeout=args.timeout)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
