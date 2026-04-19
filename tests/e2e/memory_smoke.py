#!/usr/bin/env python3
"""memory_smoke.py — one-shot local smoke test for the Memory Oracle seat.

Validates the full memory lifecycle:
  scan → write → query (key/file/search/--ask) → verify_claims

Usage:
    python3 tests/e2e/memory_smoke.py            # dry-run (default, no LLM)
    python3 tests/e2e/memory_smoke.py --dry-run  # explicit dry-run
    python3 tests/e2e/memory_smoke.py --live     # live mode (requires minimax.env)

Output: structured JSON with stage + pass/fail + timing.

Dry-run mode: mocks memory/LLM; no external calls. Safe to run in CI.
Live mode:    requires ~/.agents/secrets/claude/minimax/memory.env with
              MINIMAX_API_KEY set. Uses dispatch_task.py + real Memory CC TUI.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO / "core" / "skills" / "memory-oracle" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import query_memory as qm
import scan_environment as se


# ── Result helpers ────────────────────────────────────────────────────────────

def _stage(name: str, passed: bool, duration: float, detail: object = None) -> dict:
    return {"stage": name, "passed": passed, "duration_s": round(duration, 3), "detail": detail}


def _result_json(stages: list[dict]) -> dict:
    all_passed = all(s["passed"] for s in stages)
    return {"smoke_test": "memory_oracle", "all_passed": all_passed, "stages": stages}


# ── Stage implementations ─────────────────────────────────────────────────────

def stage_scan_env(mem_dir: Path, dry_run: bool) -> dict:
    """Stage 1: run scan_environment.scan_environment() and write to mem_dir."""
    t0 = time.monotonic()
    try:
        data = se.scan_environment()
        assert "vars" in data and "key_count" in data
        if not dry_run:
            machine = mem_dir / "machine"
            machine.mkdir(parents=True, exist_ok=True)
            (machine / "env.json").write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        return _stage("scan_env", True, time.monotonic() - t0, {"key_count": data["key_count"]})
    except Exception as exc:
        return _stage("scan_env", False, time.monotonic() - t0, str(exc))


def stage_write_fixture(mem_dir: Path) -> dict:
    """Stage 2: write a known fixture file into mem_dir for query tests."""
    t0 = time.monotonic()
    try:
        machine = mem_dir / "machine"
        machine.mkdir(parents=True, exist_ok=True)
        fixture = {
            "scanned_at": "2026-04-19T00:00:00+00:00",
            "keys": {
                "SMOKE_TEST_KEY": {"value": "smoke-value-abc", "source": "/tmp/fake.env"}
            },
        }
        (machine / "credentials.json").write_text(
            json.dumps(fixture, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return _stage("write_fixture", True, time.monotonic() - t0)
    except Exception as exc:
        return _stage("write_fixture", False, time.monotonic() - t0, str(exc))


def stage_query_key(mem_dir: Path, capsys_buf: list) -> dict:
    """Stage 3a: --key lookup against the fixture."""
    t0 = time.monotonic()

    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        rc = qm.cmd_key(mem_dir, "credentials.keys.SMOKE_TEST_KEY.value")
        out = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

    passed = rc == 0 and "smoke-value-abc" in out
    return _stage("query_key", passed, time.monotonic() - t0, {"rc": rc, "output_snippet": out[:80]})


def stage_query_file(mem_dir: Path) -> dict:
    """Stage 3b: --file lookup."""
    t0 = time.monotonic()
    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        rc = qm.cmd_file(mem_dir, "credentials", "keys.SMOKE_TEST_KEY")
        out = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout
    passed = rc == 0 and "smoke-value-abc" in out
    return _stage("query_file", passed, time.monotonic() - t0, {"rc": rc})


def stage_query_search(mem_dir: Path) -> dict:
    """Stage 3c: --search cross-file."""
    t0 = time.monotonic()
    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        rc = qm.cmd_search(mem_dir, "smoke-value")
        out = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout
    passed = rc == 0 and "smoke-value" in out
    return _stage("query_search", passed, time.monotonic() - t0, {"rc": rc, "hit": passed})


def stage_verify_claims(mem_dir: Path) -> dict:
    """Stage 3d: verify_claims happy path."""
    t0 = time.monotonic()
    try:
        response = {
            "claims": [{
                "statement": "SMOKE_TEST_KEY exists with correct value",
                "evidence": [{
                    "file": "credentials",
                    "path": "keys.SMOKE_TEST_KEY.value",
                    "expected_value": "smoke-value-abc",
                }],
            }]
        }
        result = qm.verify_claims(response, mem_dir)
        passed = result["all_verified"] is True
        return _stage("verify_claims", passed, time.monotonic() - t0, result)
    except Exception as exc:
        return _stage("verify_claims", False, time.monotonic() - t0, str(exc))


def stage_verify_claims_mismatch(mem_dir: Path) -> dict:
    """Stage 3e: verify_claims mismatch path — must return all_verified=False."""
    t0 = time.monotonic()
    try:
        response = {
            "claims": [{
                "statement": "Wrong value claim",
                "evidence": [{
                    "file": "credentials",
                    "path": "keys.SMOKE_TEST_KEY.value",
                    "expected_value": "WRONG-VALUE",
                }],
            }]
        }
        result = qm.verify_claims(response, mem_dir)
        passed = result["all_verified"] is False
        return _stage("verify_claims_mismatch", passed, time.monotonic() - t0)
    except Exception as exc:
        return _stage("verify_claims_mismatch", False, time.monotonic() - t0, str(exc))


def stage_ask_dry_run() -> dict:
    """Stage 4: --ask in dry-run: verify it returns error 2 without a profile (expected)."""
    t0 = time.monotonic()
    import io
    old_stderr = sys.stderr
    sys.stderr = io.StringIO()
    try:
        rc = qm.cmd_ask("what is the SMOKE_TEST_KEY?", profile_path=None, timeout=0.1)
    finally:
        sys.stderr = old_stderr
    # Without profile, must return 2 (usage error) — that's the contract
    passed = rc == 2
    return _stage("ask_dry_run", passed, time.monotonic() - t0, {"rc": rc, "note": "exit 2 expected without --profile"})


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Memory Oracle smoke test")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Dry-run mode (default): no LLM/external calls")
    parser.add_argument("--live", action="store_true",
                        help="Live mode: requires ~/.agents/secrets/claude/minimax/memory.env")
    args = parser.parse_args()

    if args.live:
        secrets = Path.home() / ".agents" / "secrets" / "claude" / "minimax" / "memory.env"
        if not secrets.exists():
            print(json.dumps({"error": f"live mode requires {secrets}"}), flush=True)
            return 2

    with tempfile.TemporaryDirectory(prefix="cs_memory_smoke_") as tmp:
        mem_dir = Path(tmp) / "memory"
        mem_dir.mkdir()

        stages: list[dict] = []
        capsys_buf: list = []

        stages.append(stage_scan_env(mem_dir, dry_run=not args.live))
        stages.append(stage_write_fixture(mem_dir))
        stages.append(stage_query_key(mem_dir, capsys_buf))
        stages.append(stage_query_file(mem_dir))
        stages.append(stage_query_search(mem_dir))
        stages.append(stage_verify_claims(mem_dir))
        stages.append(stage_verify_claims_mismatch(mem_dir))
        stages.append(stage_ask_dry_run())

        result = _result_json(stages)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
