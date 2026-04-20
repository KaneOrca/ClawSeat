"""install_complete.py — post-install validator for ClawSeat G1-G15 gaps.

Usage:
    python3 install_complete.py --project <name> [--verbose]

Checks each canonical gap and prints PASS / FAIL / N/A per check.
Exit code: non-zero if any critical check (G1/G2/G6/G8/G11/G14) fails.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


_AGENTS_HOME = Path.home() / ".agents"
_OPENCLAW_HOME = Path.home() / ".openclaw"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_INSTALL_FLOW = _REPO_ROOT / "core" / "skills" / "clawseat-install" / "references" / "install-flow.md"

CRITICAL = {"G1", "G2", "G6", "G8", "G11", "G14"}


def _check(gid: str, desc: str, passed: bool, evidence: str = "", warn_only: bool = False) -> dict:
    level = "WARN" if warn_only else ("PASS" if passed else "FAIL")
    if not passed and not warn_only:
        level = "FAIL"
    return {"id": gid, "desc": desc, "passed": passed, "evidence": evidence, "level": level}


def run_checks(project: str, verbose: bool = False) -> list[dict]:
    results: list[dict] = []

    # ── G1: bundled skills symlinks ─────────────────────────────────────────
    skills_dir = _OPENCLAW_HOME / "skills"
    skill_links = list(skills_dir.glob("*")) if skills_dir.exists() else []
    g1_pass = len(skill_links) >= 4
    results.append(_check(
        "G1", "install_bundled_skills.py run (≥4 skill symlinks in ~/.openclaw/skills/)",
        g1_pass,
        f"found {len(skill_links)} entries in {skills_dir}",
    ))

    # ── G2: memory index.json ──────────────────────────────────────────────
    memory_index = _AGENTS_HOME / "memory" / "index.json"
    g2_pass = memory_index.exists()
    results.append(_check(
        "G2", "Memory seat started + index.json present",
        g2_pass,
        str(memory_index) + (" [exists]" if g2_pass else " [missing]"),
    ))

    # ── G3: memory log contains agent query (advisory) ────────────────────
    memory_dir = _AGENTS_HOME / "memory"
    g3_pass = False
    if memory_dir.exists():
        for f in memory_dir.rglob("*.json"):
            try:
                if "agent" in f.read_text(encoding="utf-8", errors="replace").lower():
                    g3_pass = True
                    break
            except OSError:
                pass
    results.append(_check(
        "G3", "Memory queried for target agent (agent keyword in memory logs)",
        g3_pass, "", warn_only=True,
    ))

    # ── G4: entry skills installed ──────────────────────────────────────────
    # Check for .entry_skills_installed marker in any workspace
    g4_markers = list(_OPENCLAW_HOME.glob("workspace-*/.entry_skills_installed")) if _OPENCLAW_HOME.exists() else []
    g4_pass = bool(g4_markers)
    results.append(_check(
        "G4", "install_entry_skills.py run (.entry_skills_installed marker present)",
        g4_pass,
        f"markers found: {[str(m) for m in g4_markers]}" if g4_pass else "no .entry_skills_installed markers found",
        warn_only=True,
    ))

    # ── G5: advisory ──────────────────────────────────────────────────────
    results.append(_check(
        "G5", "openclaw_first_install.py used (advisory — not enforced)",
        True, "advisory check only", warn_only=True,
    ))

    # ── G6: BRIDGE.toml present ─────────────────────────────────────────────
    bridge_toml = _AGENTS_HOME / "projects" / project / "BRIDGE.toml"
    g6_pass = bridge_toml.exists()
    results.append(_check(
        "G6", f"Feishu bridge BRIDGE.toml present (~/.agents/projects/{project}/BRIDGE.toml)",
        g6_pass,
        str(bridge_toml) + (" [exists]" if g6_pass else " [missing]"),
    ))

    # ── G7: BRIDGE.toml has bound_by field (advisory) ─────────────────────
    g7_pass = False
    if g6_pass:
        try:
            g7_pass = "bound_by" in bridge_toml.read_text(encoding="utf-8")
        except OSError:
            pass
    results.append(_check(
        "G7", "Project-group binding confirmed (bound_by in BRIDGE.toml)",
        g7_pass, "", warn_only=True,
    ))

    # ── G8: BRIDGE.toml present (same as G6 — direct bind call) ──────────
    results.append(_check(
        "G8", "bind_project_to_group() called → BRIDGE.toml exists",
        g6_pass,
        str(bridge_toml) + (" [exists]" if g6_pass else " [missing]"),
    ))

    # ── G9, G10: advisory ─────────────────────────────────────────────────
    results.append(_check("G9", "Configuration phase separate from task execution (advisory)", True, "advisory", warn_only=True))
    results.append(_check("G10", "Per-seat user confirmation before startup (advisory)", True, "advisory", warn_only=True))

    # ── G11: refresh_workspaces.py marker ─────────────────────────────────
    # Check .last_refresh in any project workspace or WORKSPACE_CONTRACT.toml last_refresh
    g11_pass = False
    project_ws_root = _AGENTS_HOME / "projects" / project
    if project_ws_root.exists():
        # Check .last_refresh file
        if (project_ws_root / ".last_refresh").exists():
            g11_pass = True
        else:
            # Check WORKSPACE_CONTRACT.toml in any seat workspace
            for wc in project_ws_root.rglob("WORKSPACE_CONTRACT.toml"):
                try:
                    if "last_refresh" in wc.read_text(encoding="utf-8"):
                        g11_pass = True
                        break
                except OSError:
                    pass
    # Also check runtime identities for WORKSPACE_CONTRACT.toml
    if not g11_pass:
        for wc in (_AGENTS_HOME / "runtime" / "identities").rglob(f"*/{project}/*/WORKSPACE_CONTRACT.toml"):
            try:
                if "last_refresh" in wc.read_text(encoding="utf-8"):
                    g11_pass = True
                    break
            except OSError:
                pass
    results.append(_check(
        "G11", "refresh_workspaces.py run (.last_refresh or WORKSPACE_CONTRACT last_refresh)",
        g11_pass, "marker not found" if not g11_pass else "marker found",
    ))

    # ── G12: install-flow.md has AGENT_HOME section ────────────────────────
    g12_pass = False
    if _INSTALL_FLOW.exists():
        try:
            g12_pass = "AGENT_HOME" in _INSTALL_FLOW.read_text(encoding="utf-8")
        except OSError:
            pass
    results.append(_check(
        "G12", "install-flow.md contains AGENT_HOME section",
        g12_pass,
        str(_INSTALL_FLOW) + (" [AGENT_HOME found]" if g12_pass else " [AGENT_HOME missing]"),
    ))

    # ── G13: advisory ─────────────────────────────────────────────────────
    results.append(_check("G13", "lark-cli auth via canonical device flow (advisory)", True, "advisory", warn_only=True))

    # ── G14: Feishu scope evidence ─────────────────────────────────────────
    g14_pass = False
    g14_evidence = "lark-cli not available or check skipped"
    try:
        result = subprocess.run(
            ["lark-cli", "app", "permissions", "list"],
            capture_output=True, text=True, check=False, timeout=8.0,
        )
        if result.returncode == 0:
            g14_pass = "im:message.group_msg:receive" in result.stdout
            g14_evidence = "im:message.group_msg:receive found in lark-cli output" if g14_pass else "im:message.group_msg:receive NOT found in lark-cli output"
        else:
            g14_evidence = f"lark-cli exit {result.returncode}: {result.stderr.strip()[:80]}"
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        g14_evidence = f"lark-cli unavailable: {exc}"
    results.append(_check(
        "G14", "Feishu im:message.group_msg:receive scope enabled",
        g14_pass, g14_evidence,
    ))

    # ── G15: advisory (code-side check) ───────────────────────────────────
    results.append(_check("G15", "Memory query uses --memory-dir --key syntax (advisory)", True, "advisory", warn_only=True))

    return results


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--project", required=True, help="Project name (e.g. install, hardening-b)")
    p.add_argument("--verbose", action="store_true", help="Print evidence strings")
    args = p.parse_args(argv)

    checks = run_checks(args.project, verbose=args.verbose)

    failures: list[str] = []
    for c in checks:
        icon = "✓" if c["passed"] else ("~" if c["level"] == "WARN" else "✗")
        line = f"  [{c['level']:4s}] {c['id']:3s} {icon} {c['desc']}"
        print(line)
        if args.verbose and c["evidence"]:
            print(f"         evidence: {c['evidence']}")
        if c["level"] == "FAIL" and c["id"] in CRITICAL:
            failures.append(c["id"])

    print()
    if failures:
        print(f"RESULT: FAIL — critical checks failed: {', '.join(failures)}")
        return 1
    print("RESULT: PASS — all critical checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
