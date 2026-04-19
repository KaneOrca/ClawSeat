#!/usr/bin/env python3
"""
query_memory.py — query the Memory CC knowledge base.

Modes:
  1. Direct read (fast, key-value) — reads ~/.agents/memory/*.json directly
     python3 query_memory.py --key credentials.keys.MINIMAX_API_KEY
     python3 query_memory.py --search feishu
     python3 query_memory.py --file openclaw --section feishu

  2. Schema introspection (discover fields without reading secrets)
     python3 query_memory.py --schema                      # all-file summary
     python3 query_memory.py --schema credentials --depth 4

  3. Unmask raw credential (reads secrets/ sidecar, writes audit log)
     python3 query_memory.py --unmask MINIMAX_API_KEY --reason "configure seat"

  4. Ask Memory CC TUI (slow, reasoning) — writes to TODO, waits for response
     python3 query_memory.py --ask "designer seat uses which provider?"

Zero third-party dependencies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
DEFAULT_MEMORY_DIR = HOME / ".agents" / "memory"
SECRETS_SUBDIR = "secrets"
SECRETS_FILENAME = "credentials.secrets.json"
AUDIT_LOG_FILENAME = "audit.log"


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
    """Ask Memory CC via dispatch_task.py + poll responses/{task_id}.json.

    This is the mechanism for callers who are NOT tmux seats (e.g. the
    ancestor Claude Code running the install). Real seats should use
    ``dispatch_task.py`` directly and receive DELIVERY.md via the canonical
    harness flow — no polling needed.
    """
    if not profile_path:
        print("error: --ask requires --profile <profile.toml>", file=sys.stderr)
        return 2

    # Build task_id from timestamp + pid to avoid collisions
    task_id = f"MEMORY-QUERY-{int(time.time())}-{os.getpid()}"
    responses_dir = DEFAULT_MEMORY_DIR / "responses"
    responses_dir.mkdir(parents=True, exist_ok=True)
    response_path = responses_dir / f"{task_id}.json"

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

    # Poll the per-query response file (no collision with other queries)
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
            expected_hash = ev.get("expected_value_sha256")
            # ── normalize file ──────────────────────────────────
            # LLMs emit any of: "github", "github.json",
            #   "/Users/ywf/.agents/memory/github.json", "memory/github"
            # → take the basename, strip .json
            fname = os.path.basename(fname)
            if fname.endswith(".json"):
                fname = fname[:-5]
            # ── normalize path ──────────────────────────────────
            # LLMs emit any of: "a.b.c", "$.a.b.c", "/a/b/c",
            #   "a['b'].c", "a/b/c" — normalize to dot-separated.
            if path:
                path = path.strip()
                if path.startswith("$."):
                    path = path[2:]
                elif path.startswith("$"):
                    path = path[1:].lstrip(".")
                path = path.lstrip("/").replace("/", ".")
                # strip bracket notation: a['b'] → a.b
                path = path.replace("[", ".").replace("]", "").replace("'", "").replace('"', "")
                # collapse double dots
                while ".." in path:
                    path = path.replace("..", ".")
                path = path.strip(".")

            data = load_memory_file(memory_dir, fname)
            if data is None:
                mismatches.append({"file": fname, "path": path, "reason": "file_not_found"})
                continue
            actual = walk_path(data, path.split(".")) if path else data

            # Hash-based evidence takes precedence when provided. This lets
            # Memory CC prove a credential without echoing it in response.json.
            if expected_hash is not None:
                if actual is None:
                    mismatches.append({
                        "file": fname, "path": path,
                        "reason": "path_not_found",
                        "expected_sha256": expected_hash,
                    })
                else:
                    actual_hash = sha256_hex(str(actual))
                    if actual_hash != expected_hash:
                        mismatches.append({
                            "file": fname, "path": path,
                            "reason": "sha256_mismatch",
                            "expected_sha256": expected_hash,
                            "actual_sha256": actual_hash,
                        })
            elif "expected_value" not in ev:
                # Neither form supplied — can't verify.
                mismatches.append({
                    "file": fname, "path": path,
                    "reason": "no_evidence_value",
                })
            elif actual != expected:
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


def _schema_node(value: object, depth: int, max_depth: int, *, safe_sample: bool) -> dict:
    """Recursively describe a value's shape.

    When ``safe_sample`` is True we never emit raw string samples — only
    length. This keeps ``--schema`` from accidentally echoing credentials
    if the scanner ever regresses and stores plaintext under a surprising
    field name. Preview/hash fields and short metadata fields may still
    include a ``sample`` when called with ``safe_sample=False`` on a known
    non-secret branch (e.g. the ``_provenance`` sub-tree).
    """
    if isinstance(value, dict):
        node: dict = {"type": "object"}
        if depth < max_depth:
            children: dict = {}
            for k, v in value.items():
                # Strings under a 'value' key are treated as secrets — never
                # sample them. Everything else gets normal handling.
                child_safe = safe_sample or (isinstance(k, str) and k == "value")
                children[k] = _schema_node(v, depth + 1, max_depth, safe_sample=child_safe)
            node["children"] = children
        else:
            node["truncated"] = True
            if isinstance(value, dict):
                node["top_level_keys"] = sorted(list(value.keys()))
        return node
    if isinstance(value, list):
        node = {"type": "array", "length": len(value)}
        if value and depth < max_depth:
            # Sample first element's shape only
            node["item"] = _schema_node(value[0], depth + 1, max_depth, safe_sample=safe_sample)
        return node
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "boolean", "sample": value}
    if isinstance(value, (int, float)):
        return {"type": type(value).__name__, "sample": value}
    if isinstance(value, str):
        node = {"type": "string", "sample_length": len(value)}
        if not safe_sample and len(value) <= 40:
            node["sample"] = value
        return node
    return {"type": type(value).__name__}


def cmd_schema(memory_dir: Path, file: str | None, depth: int) -> int:
    """Introspect the memory knowledge base schema.

    ``--schema`` (no arg) → summary of all files (top-level keys + size).
    ``--schema <file>`` → nested schema tree for that file.

    Never prints raw credential values: the ``value`` field under
    ``credentials.keys.*`` is always sampled as ``{type, sample_length}``
    only. Safe to paste into logs.
    """
    if not memory_dir.is_dir():
        print(f"error: memory dir not found: {memory_dir}", file=sys.stderr)
        return 1
    if file:
        fname = os.path.basename(file)
        if fname.endswith(".json"):
            fname = fname[:-5]
        data = load_memory_file(memory_dir, fname)
        if data is None:
            print(f"error: memory file not found: {memory_dir / (fname + '.json')}", file=sys.stderr)
            return 1
        schema = _schema_node(data, 0, max_depth=depth, safe_sample=False)
        out = {"file": fname, "depth": depth, "schema": schema}
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    # Summary mode — list every file with top-level keys + byte size
    files: dict[str, dict] = {}
    for p in sorted(memory_dir.glob("*.json")):
        if p.stem == "response":
            continue
        try:
            raw = p.read_text(encoding="utf-8")
            parsed = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            files[p.stem] = {"error": str(exc)}
            continue
        entry: dict = {"size_bytes": p.stat().st_size}
        if isinstance(parsed, dict):
            entry["top_level_keys"] = sorted(list(parsed.keys()))
        elif isinstance(parsed, list):
            entry["top_level_type"] = "array"
            entry["length"] = len(parsed)
        files[p.stem] = entry
    secrets_file = memory_dir / SECRETS_SUBDIR / SECRETS_FILENAME
    result = {
        "memory_dir": str(memory_dir),
        "files": files,
        "secrets_file_present": secrets_file.is_file(),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_unmask(memory_dir: Path, key: str, reason: str | None) -> int:
    """Read a raw credential value from the secrets sidecar + write audit log.

    The secrets file is separate from ``credentials.json`` so that the main
    knowledge base can be safely printed / shared / shown via ``--schema``
    without leaking secrets. Every ``--unmask`` call appends a JSONL line
    to ``secrets/audit.log`` so the user can review access history.
    """
    secrets_path = memory_dir / SECRETS_SUBDIR / SECRETS_FILENAME
    if not secrets_path.is_file():
        print(
            f"error: secrets file not found: {secrets_path}\n"
            "hint: re-run scan_environment.py to produce the secrets sidecar.",
            file=sys.stderr,
        )
        return 1
    try:
        payload = json.loads(secrets_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: could not read {secrets_path}: {exc}", file=sys.stderr)
        return 1
    keys = payload.get("keys") or {}
    if key not in keys:
        print(f"not_found: {key}", file=sys.stderr)
        # Still record the miss so audit log reflects attempts.
        _append_audit(memory_dir, key, reason, hit=False)
        return 1
    # Write audit log FIRST so a crash between audit and stdout still leaves
    # a trace of the access attempt.
    _append_audit(memory_dir, key, reason, hit=True)
    print(keys[key])
    return 0


def _append_audit(memory_dir: Path, key: str, reason: str | None, *, hit: bool) -> None:
    audit_dir = memory_dir / SECRETS_SUBDIR
    try:
        audit_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(audit_dir, 0o700)
    except OSError:
        pass
    audit_path = audit_dir / AUDIT_LOG_FILENAME
    entry = {
        "ts": now_iso(),
        "key": key,
        "reason": reason or "",
        "hit": hit,
        "caller_pid": os.getpid(),
        "caller_ppid": os.getppid(),
        "caller_cwd": os.getcwd(),
    }
    try:
        with audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        try:
            os.chmod(audit_path, 0o600)
        except OSError:
            pass
    except OSError as exc:
        print(f"warning: could not append audit log: {exc}", file=sys.stderr)


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
    group.add_argument(
        "--schema",
        nargs="?",
        const="",
        default=None,
        metavar="FILE",
        help="Introspect memory schema. No arg: summary. With FILE: full tree.",
    )
    group.add_argument(
        "--unmask",
        metavar="KEY",
        help="Read raw credential value from secrets sidecar. Writes audit log.",
    )
    group.add_argument("--status", action="store_true", help="Show memory DB status")
    p.add_argument("--section", help="With --file: dotted sub-path to extract")
    p.add_argument("--profile", help="With --ask: profile TOML for dispatch")
    p.add_argument("--timeout", type=float, default=60.0, help="With --ask: poll timeout seconds")
    p.add_argument("--files", help="With --search: comma-separated file names to restrict scope")
    p.add_argument("--depth", type=int, default=3, help="With --schema <FILE>: max tree depth (default 3)")
    p.add_argument("--reason", help="With --unmask: recorded in audit log (e.g. 'configure MiniMax seat')")
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
    if args.schema is not None:
        return cmd_schema(memory_dir, args.schema or None, args.depth)
    if args.unmask:
        return cmd_unmask(memory_dir, args.unmask, args.reason)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
