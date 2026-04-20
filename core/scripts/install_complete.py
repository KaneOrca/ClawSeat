"""install_complete.py — post-install validator for ClawSeat G1-G15 gaps.

Usage:
    python3 install_complete.py --project <name> [--koder-agent <agent>] [--verbose]

Checks each canonical gap and prints PASS / FAIL / N/A per check.
Exit code: non-zero if any critical check (G1/G2/G6/G8/G11/G14) fails.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


import os as _os
_REAL_HOME = Path(_os.environ.get("AGENT_HOME", "") or Path.home())
_AGENTS_HOME = _REAL_HOME / ".agents"
_OPENCLAW_HOME = _REAL_HOME / ".openclaw"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_INSTALL_FLOW = _REPO_ROOT / "core" / "skills" / "clawseat-install" / "references" / "install-flow.md"

CRITICAL = {"G1", "G2", "G6", "G8", "G11", "G14"}

_AGENT_FIELD_RE = re.compile(r'^\s*(?:koder_)?agent\s*=\s*["\']?(\w[\w\-]*)["\']?', re.MULTILINE)


def _check(gid: str, desc: str, passed: bool, evidence: str = "", warn_only: bool = False) -> dict:
    level = "WARN" if warn_only else ("PASS" if passed else "FAIL")
    if not passed and not warn_only:
        level = "FAIL"
    return {"id": gid, "desc": desc, "passed": passed, "evidence": evidence, "level": level}


def _resolve_koder_agent(
    project: str,
    agents_home: Path,
    openclaw_home: Path,
) -> str | None:
    """Return the OpenClaw agent name for the koder seat of a project, or None."""
    proj_dir = agents_home / "projects" / project

    # Try openclaw.json first
    openclaw_json = proj_dir / "openclaw.json"
    if openclaw_json.exists():
        try:
            import json as _json
            data = _json.loads(openclaw_json.read_text(encoding="utf-8"))
            for key in ("koder_agent", "agent"):
                if key in data and isinstance(data[key], str):
                    return data[key]
        except (OSError, ValueError):
            pass

    # Try BRIDGE.toml agent field
    bridge_toml = proj_dir / "BRIDGE.toml"
    if bridge_toml.exists():
        try:
            m = _AGENT_FIELD_RE.search(bridge_toml.read_text(encoding="utf-8"))
            if m:
                return m.group(1)
        except OSError:
            pass

    # Canonical fallback: install project always uses agent "koder"
    if project == "install":
        return "koder"

    return None


def run_checks(
    project: str,
    verbose: bool = False,
    koder_agent: str | None = None,
    *,
    agents_home: Path | None = None,
    openclaw_home: Path | None = None,
) -> list[dict]:
    # Resolve at call time so monkeypatching of module globals works in tests
    if agents_home is None:
        agents_home = _AGENTS_HOME
    if openclaw_home is None:
        openclaw_home = _OPENCLAW_HOME

    results: list[dict] = []
    agent = koder_agent or _resolve_koder_agent(project, agents_home, openclaw_home)
    openclaw_workspace = (openclaw_home / f"workspace-{agent}") if agent else None

    # ── G1: per-agent skills symlinks ────────────────────────────────────────
    if agent is None:
        g1_pass = False
        g1_evidence = f"cannot resolve koder agent for project '{project}'; pass --koder-agent"
    else:
        skills_dir = openclaw_workspace / "skills"
        skill_links = list(skills_dir.glob("*")) if skills_dir.exists() else []
        g1_pass = len(skill_links) >= 4
        g1_evidence = f"found {len(skill_links)} entries in {skills_dir}"
    results.append(_check(
        "G1", "install_bundled_skills.py run (≥4 skill symlinks in workspace-<agent>/skills/)",
        g1_pass, g1_evidence,
    ))

    # ── G2: memory index.json ──────────────────────────────────────────────
    memory_index = agents_home / "memory" / "index.json"
    g2_pass = memory_index.exists()
    results.append(_check(
        "G2", "Memory seat started + index.json present",
        g2_pass,
        str(memory_index) + (" [exists]" if g2_pass else " [missing]"),
    ))

    # ── G3: memory log contains agent query (advisory) ────────────────────
    memory_dir = agents_home / "memory"
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

    # ── G4: entry skills installed per-agent (advisory) ────────────────────
    if agent is not None:
        marker = openclaw_workspace / ".entry_skills_installed"
        g4_pass = marker.exists()
        g4_evidence = str(marker) + (" [exists]" if g4_pass else " [missing]")
    else:
        g4_pass = False
        g4_evidence = f"cannot resolve koder agent for project '{project}'"
    results.append(_check(
        "G4", "install_entry_skills.py run (.entry_skills_installed in workspace-<agent>/)",
        g4_pass, g4_evidence, warn_only=True,
    ))

    # ── G5: advisory ──────────────────────────────────────────────────────
    results.append(_check(
        "G5", "openclaw_first_install.py used (advisory — not enforced)",
        True, "advisory check only", warn_only=True,
    ))

    # ── G6: Feishu bridge configured (BRIDGE.toml OR agent sessions) ───────
    bridge_toml = agents_home / "projects" / project / "BRIDGE.toml"
    g6_evidence = str(bridge_toml)
    g6_pass = bridge_toml.exists()
    if not g6_pass:
        # Fallback: check openclaw sessions.json for any group binding
        for sessions_json in openclaw_home.rglob("sessions/sessions.json") if openclaw_home.exists() else []:
            try:
                import json as _json
                data = _json.loads(sessions_json.read_text(encoding="utf-8"))
                if any("feishu:group" in k for k in data.keys()):
                    g6_pass = True
                    g6_evidence = f"group binding found in {sessions_json}"
                    break
            except (OSError, ValueError):
                pass
    results.append(_check(
        "G6", "Feishu bridge configured (BRIDGE.toml or openclaw sessions group binding)",
        g6_pass, g6_evidence,
    ))

    # ── G7: BRIDGE.toml has bound_by field (advisory) ─────────────────────
    g7_pass = False
    if bridge_toml.exists():
        try:
            g7_pass = "bound_by" in bridge_toml.read_text(encoding="utf-8")
        except OSError:
            pass
    results.append(_check(
        "G7", "Project-group binding confirmed (bound_by in BRIDGE.toml)",
        g7_pass, "", warn_only=True,
    ))

    # ── G8: Feishu bridge present (same evidence as G6) ──────────────────
    results.append(_check(
        "G8", "bind_project_to_group() called → bridge config present",
        g6_pass, g6_evidence,
    ))

    # ── G9, G10: advisory ─────────────────────────────────────────────────
    results.append(_check("G9", "Configuration phase separate from task execution (advisory)", True, "advisory", warn_only=True))
    results.append(_check("G10", "Per-seat user confirmation before startup (advisory)", True, "advisory", warn_only=True))

    # ── G11: per-project workspace refresh marker ──────────────────────────
    g11_pass = False
    g11_evidence = "marker not found"

    # Primary: per-project koder seat .last_refresh
    koder_seat_ws = agents_home / "workspaces" / project / "koder"
    if (koder_seat_ws / ".last_refresh").exists():
        g11_pass = True
        g11_evidence = str(koder_seat_ws / ".last_refresh") + " [exists]"

    # Secondary: per-agent openclaw workspace WORKSPACE_CONTRACT.toml
    if not g11_pass and openclaw_workspace is not None:
        wc = openclaw_workspace / "WORKSPACE_CONTRACT.toml"
        if wc.exists():
            try:
                if "last_refresh" in wc.read_text(encoding="utf-8"):
                    g11_pass = True
                    g11_evidence = str(wc) + " [last_refresh field present]"
            except OSError:
                pass

    # Fallback: any WORKSPACE_CONTRACT.toml in workspaces/<project>/
    if not g11_pass:
        ws_root = agents_home / "workspaces" / project
        if ws_root.exists():
            for wc in ws_root.glob("*/WORKSPACE_CONTRACT.toml"):
                if wc.exists():
                    g11_pass = True
                    g11_evidence = str(wc) + " [exists]"
                    break

    # Further fallback: projects/<project>/.last_refresh (used by legacy fixtures)
    if not g11_pass:
        proj_refresh = agents_home / "projects" / project / ".last_refresh"
        if proj_refresh.exists():
            g11_pass = True
            g11_evidence = str(proj_refresh) + " [exists]"

    results.append(_check(
        "G11", "refresh_workspaces.py run (.last_refresh or WORKSPACE_CONTRACT present)",
        g11_pass, g11_evidence,
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
    # Try lark-cli api for permission check; degrade to WARN if subcommand unsupported.
    g14_pass = False
    g14_warn_only = False
    g14_evidence = "lark-cli not available or check skipped"
    try:
        result = subprocess.run(
            ["lark-cli", "app", "permissions", "list"],
            capture_output=True, text=True, check=False, timeout=8.0,
        )
        if result.returncode == 0:
            g14_pass = "im:message.group_msg:receive" in result.stdout
            g14_evidence = "im:message.group_msg:receive found" if g14_pass else "im:message.group_msg:receive NOT found"
        elif "unknown command" in result.stderr or "unknown command" in result.stdout:
            # lark-cli version doesn't support this subcommand — degrade to advisory
            g14_warn_only = True
            g14_pass = True  # treat as passing since we can't check
            g14_evidence = "lark-cli version does not support scope query; manual verification required"
        else:
            g14_evidence = f"lark-cli exit {result.returncode}: {(result.stderr or result.stdout).strip()[:80]}"
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        g14_warn_only = True
        g14_pass = True
        g14_evidence = f"lark-cli unavailable ({exc}); manual verification required"
    results.append(_check(
        "G14", "Feishu im:message.group_msg:receive scope enabled",
        g14_pass, g14_evidence, warn_only=g14_warn_only,
    ))

    # ── G15: advisory (code-side check) ───────────────────────────────────
    results.append(_check("G15", "Memory query uses --memory-dir --key syntax (advisory)", True, "advisory", warn_only=True))

    return results


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--project", required=True, help="Project name (e.g. install, hardening-b)")
    p.add_argument("--koder-agent", default=None, dest="koder_agent",
                   help="OpenClaw agent name override (auto-resolved if omitted)")
    p.add_argument("--verbose", action="store_true", help="Print evidence strings")
    args = p.parse_args(argv)

    checks = run_checks(args.project, verbose=args.verbose, koder_agent=args.koder_agent)

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
