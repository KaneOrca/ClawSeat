"""Install entrypoint — v0.4 canonical install orchestrator.

Replaces the v0.3 ``/cs`` flow. Given a project name, this script:

  1. Resolves the v2 profile (runs install_wizard if missing / --clone-from)
  2. Verifies PROJECT_BINDING.toml.feishu_group_id is present
  3. Ensures entry skills are installed for the local runtime
  4. Preflight every seat's auth via ``agent-launcher.sh --check-secrets``
  5. Renders the ancestor bootstrap brief
  6. Invokes ``agent-launcher.sh`` to start the ancestor tmux session
     (the launcher's own ancestor-preflight will install the Phase-B
     launchd plist)
  7. Opens one visible iTerm pane attached to ancestor
  8. Primes the fresh ancestor session with a bootstrap prompt pointing at
     the ancestor skill + brief

Design: this is a thin Python orchestrator on top of the bash launcher.
The launcher remains the runtime (it owns tmux + iTerm + env isolation);
install_entrypoint.py owns the per-project setup sequencing.

Usage:

    python3 -m core.tui.install_entrypoint --project install
    python3 -m core.tui.install_entrypoint --project install --clone-from cartooner
    python3 -m core.tui.install_entrypoint --project install --dry-run

Not for CI: the underlying wizard is interactive (stdin TTY). Call
install_wizard with --accept-defaults + --feishu-group-id if we ever
need a non-interactive path.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python <3.11
    import tomli as tomllib  # type: ignore[no-redef]


CLAWSEAT_ROOT = Path(os.environ.get("CLAWSEAT_ROOT", str(Path.home() / ".clawseat"))).expanduser()
LAUNCHER = CLAWSEAT_ROOT / "core" / "launchers" / "agent-launcher.sh"
ITERM_DRIVER = CLAWSEAT_ROOT / "core" / "scripts" / "iterm_panes_driver.py"
INSTALL_ENTRY_SKILLS = CLAWSEAT_ROOT / "core" / "skills" / "clawseat-install" / "scripts" / "install_entry_skills.py"
ANCESTOR_ENGINEER_TEMPLATE = CLAWSEAT_ROOT / "core" / "templates" / "ancestor-engineer.toml"
PROFILE_DIR = Path.home() / ".agents" / "profiles"
TASKS_DIR = Path.home() / ".agents" / "tasks"
ENGINEERS_DIR = Path.home() / ".agents" / "engineers"


# ── colour helpers ────────────────────────────────────────────────────

_IS_TTY = sys.stderr.isatty()


def _c(txt: str, code: str) -> str:
    return f"\x1b[{code}m{txt}\x1b[0m" if _IS_TTY else txt


def _green(s: str) -> str: return _c(s, "32")
def _yellow(s: str) -> str: return _c(s, "33")
def _red(s: str) -> str: return _c(s, "31")
def _dim(s: str) -> str: return _c(s, "2")


# ── small process helpers ─────────────────────────────────────────────

def tmux_has_session(session: str) -> bool:
    r = subprocess.run(
        ["tmux", "has-session", "-t", f"={session}"],
        capture_output=True, text=True, check=False,
    )
    return r.returncode == 0


# ── profile resolution ────────────────────────────────────────────────

def profile_path(project: str) -> Path:
    return PROFILE_DIR / f"{project}-profile-dynamic.toml"


def binding_path(project: str) -> Path:
    return TASKS_DIR / project / "PROJECT_BINDING.toml"


def load_profile_if_v2(project: str) -> dict | None:
    """Return parsed v2 profile dict, or None if missing / v1 / malformed."""
    p = profile_path(project)
    if not p.is_file():
        return None
    try:
        raw = tomllib.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if int(raw.get("version", 0)) != 2:
        return None
    return raw


def run_wizard(*, project: str, clone_from: str | None) -> None:
    """Invoke install_wizard as a subprocess so its own prompts work."""
    cmd = [
        sys.executable, "-m", "core.tui.install_wizard",
        "--project", project,
    ]
    if clone_from:
        cmd += ["--clone-from", clone_from]
    env = os.environ.copy()
    core_lib = CLAWSEAT_ROOT / "core" / "lib"
    env["PYTHONPATH"] = f"{core_lib}:{env.get('PYTHONPATH', '')}"
    print(_dim(f"→ running install_wizard for {project} (clone_from={clone_from or 'none'})"))
    r = subprocess.run(cmd, cwd=str(CLAWSEAT_ROOT), env=env)
    if r.returncode != 0:
        raise SystemExit(f"install_wizard failed with exit {r.returncode}")


def ensure_profile(project: str, *, clone_from: str | None) -> dict:
    raw = load_profile_if_v2(project)
    if raw is not None and not clone_from:
        print(_green(f"✓ profile OK: {profile_path(project)} (v2)"))
        return raw
    if raw is not None and clone_from:
        raise SystemExit(
            _red(f"✗ --clone-from given but {profile_path(project)} already exists; "
                 "remove or rename before re-cloning")
        )
    run_wizard(project=project, clone_from=clone_from)
    raw = load_profile_if_v2(project)
    if raw is None:
        raise SystemExit(_red(
            f"✗ install_wizard did not produce a valid v2 profile at {profile_path(project)}"
        ))
    return raw


# ── binding verification ──────────────────────────────────────────────

def verify_binding(project: str) -> str:
    """Return feishu_group_id. Raises on missing/empty."""
    p = binding_path(project)
    if not p.is_file():
        raise SystemExit(_red(
            f"✗ PROJECT_BINDING.toml missing at {p}; wizard should have written it"
        ))
    raw = tomllib.loads(p.read_text(encoding="utf-8"))
    group_id = str(raw.get("feishu_group_id", "")).strip()
    if not group_id:
        raise SystemExit(_red(
            f"✗ PROJECT_BINDING.toml.feishu_group_id is empty at {p}; "
            "edit and set a valid oc_xxx chat_id"
        ))
    print(_green(f"✓ PROJECT_BINDING binds {project} → {group_id}"))
    return group_id


# ── auth preflight per seat ───────────────────────────────────────────

def check_seat_secret(tool: str, auth_mode: str) -> tuple[bool, str]:
    """Call agent-launcher.sh --check-secrets; return (ok, message)."""
    r = subprocess.run(
        [str(LAUNCHER), "--check-secrets", tool, "--auth", auth_mode],
        capture_output=True, text=True,
    )
    blob = (r.stdout or r.stderr or "{}").strip().splitlines()[-1]
    try:
        data = json.loads(blob)
    except Exception:
        return (False, f"(unparseable response: {blob!r})")
    status = data.get("status", "error")
    if status == "ok":
        note = data.get("note") or data.get("file", "")
        return (True, note)
    if status in ("missing-file", "missing-key"):
        return (False, data.get("hint", data.get("reason", "missing")))
    return (False, data.get("reason", status))


def preflight_seats(profile: dict) -> list[tuple[str, str, bool]]:
    """For each seat in profile.seats, check its auth secret. Return
    list of (seat, message, ok). Does not raise — collects results."""
    seats = list(profile.get("seats", []))
    overrides = profile.get("seat_overrides", {}) or {}
    results: list[tuple[str, str, bool]] = []
    print(_dim("→ preflight seat auth…"))
    for seat in seats:
        ov = overrides.get(seat, {}) or {}
        tool = ov.get("tool", "claude")
        # Translate clawseat auth_mode (api/oauth_token/oauth) to launcher token.
        auth_mode = ov.get("auth_mode", "oauth_token")
        provider = ov.get("provider", "")
        launcher_auth = _clawseat_auth_to_launcher(tool, auth_mode, provider)
        if launcher_auth is None:
            results.append((seat, f"no launcher mapping for ({tool}, {auth_mode}, {provider})", False))
            continue
        ok, msg = check_seat_secret(tool, launcher_auth)
        results.append((seat, f"{launcher_auth}: {msg}", ok))
    return results


def _clawseat_auth_to_launcher(tool: str, auth_mode: str, provider: str) -> str | None:
    """Mirror of LAUNCHER_AUTH_TO_CLAWSEAT (install_wizard) in reverse."""
    key = (tool, auth_mode, provider)
    TABLE = {
        ("claude", "oauth_token", "anthropic"):        "oauth_token",
        ("claude", "api", "anthropic-console"):        "anthropic-console",
        ("claude", "api", "minimax"):                  "minimax",
        ("claude", "api", "xcode"):                    "xcode",
        ("claude", "api", "xcode-best"):               "xcode",
        ("claude", "api", "custom"):                   "custom",
        ("claude", "oauth", "anthropic"):              "oauth",
        ("codex",  "oauth", "chatgpt"):                "chatgpt",
        ("codex",  "api", "xcode-best"):               "xcode",
        ("codex",  "api", "xcode"):                    "xcode",
        ("codex",  "api", "custom"):                   "custom",
        ("gemini", "oauth", "google"):                 "oauth",
        ("gemini", "api", "google-primary"):           "primary",
        ("gemini", "api", "custom"):                   "custom",
    }
    return TABLE.get(key)


# ── runtime skill install ─────────────────────────────────────────────

def ensure_entry_skills() -> None:
    if not INSTALL_ENTRY_SKILLS.is_file():
        raise SystemExit(_red(f"✗ install_entry_skills.py not found at {INSTALL_ENTRY_SKILLS}"))
    print(_dim("→ ensuring entry skills are installed…"))
    r = subprocess.run(
        [sys.executable, str(INSTALL_ENTRY_SKILLS)],
        cwd=str(CLAWSEAT_ROOT),
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise SystemExit(
            _red(f"✗ install_entry_skills failed: {r.stderr.strip() or r.stdout.strip()}")
        )
    print(_green("✓ entry skills installed"))


def ensure_ancestor_engineer(*, dry_run: bool) -> Path:
    if not ANCESTOR_ENGINEER_TEMPLATE.is_file():
        raise SystemExit(
            _red(f"✗ ancestor engineer template not found at {ANCESTOR_ENGINEER_TEMPLATE}")
        )
    target = ENGINEERS_DIR / "ancestor" / "engineer.toml"
    rendered = ANCESTOR_ENGINEER_TEMPLATE.read_text(encoding="utf-8").replace(
        "{CLAWSEAT_ROOT}",
        str(CLAWSEAT_ROOT),
    )
    if dry_run:
        print(_yellow(f"→ dry-run: would render ancestor engineer → {target}"))
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    current = target.read_text(encoding="utf-8") if target.is_file() else None
    if current == rendered:
        print(_green(f"✓ ancestor engineer already current: {target}"))
        return target
    target.write_text(rendered, encoding="utf-8")
    print(_green(f"✓ ancestor engineer → {target}"))
    return target


# ── brief rendering ───────────────────────────────────────────────────

def render_brief(project: str) -> Path:
    cmd = [sys.executable, "-m", "core.tui.ancestor_brief", "--project", project]
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{CLAWSEAT_ROOT / 'core' / 'lib'}:{env.get('PYTHONPATH', '')}"
    print(_dim("→ rendering ancestor bootstrap brief…"))
    r = subprocess.run(cmd, cwd=str(CLAWSEAT_ROOT), env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(
            _red(f"✗ ancestor_brief failed: {r.stderr.strip() or r.stdout.strip()}")
        )
    brief = TASKS_DIR / project / "patrol" / "handoffs" / "ancestor-bootstrap.md"
    if not brief.is_file():
        raise SystemExit(_red(f"✗ brief did not land at {brief}"))
    print(_green(f"✓ brief → {brief}"))
    return brief


# ── ancestor launch ───────────────────────────────────────────────────

def launch_ancestor(
    project: str,
    profile: dict,
    *,
    workdir: Path,
    brief: Path,
    dry_run: bool,
) -> tuple[str, bool]:
    overrides = profile.get("seat_overrides", {}) or {}
    ancestor_ov = overrides.get("ancestor", {}) or {}
    tool = ancestor_ov.get("tool", "claude")
    launcher_auth = _clawseat_auth_to_launcher(
        tool,
        ancestor_ov.get("auth_mode", "oauth_token"),
        ancestor_ov.get("provider", "anthropic"),
    )
    if launcher_auth is None:
        raise SystemExit(_red(
            f"✗ cannot map ancestor auth to launcher value: "
            f"tool={tool} auth_mode={ancestor_ov.get('auth_mode')} provider={ancestor_ov.get('provider')}"
        ))
    session = f"{project}-ancestor-{tool}"
    cmd = [
        str(LAUNCHER),
        "--tool", tool,
        "--auth", launcher_auth,
        "--session", session,
        "--dir", str(workdir),
        "--headless",
    ]
    created = not tmux_has_session(session)
    if dry_run:
        print(_yellow("→ dry-run: would invoke:"))
        print("  " + " ".join(cmd))
        return (session, created)
    print(_dim(f"→ launching {session} via agent-launcher.sh --headless"))
    env = os.environ.copy()
    env["CLAWSEAT_ROOT"] = str(CLAWSEAT_ROOT)
    env["CLAWSEAT_PROJECT"] = project
    env["CLAWSEAT_ANCESTOR_BRIEF"] = str(brief)
    r = subprocess.run(cmd, env=env)
    if r.returncode != 0:
        raise SystemExit(_red(f"✗ launcher exited {r.returncode}"))
    print(_green(f"✓ ancestor tmux session started: {session}"))
    print(_dim("  attach with: tmux attach -t " + session))
    return (session, created)


def open_ancestor_window(project: str, session: str, *, dry_run: bool) -> None:
    payload = {
        "title": f"{project} · ancestor",
        "panes": [
            {
                "label": "ancestor",
                "command": f"tmux attach -t '={session}'",
            }
        ],
    }
    if dry_run:
        print(_yellow("→ dry-run: would open iTerm pane via iterm_panes_driver.py"))
        print("  " + json.dumps(payload, ensure_ascii=False))
        return
    if not ITERM_DRIVER.is_file():
        raise SystemExit(_red(f"✗ iTerm driver not found at {ITERM_DRIVER}"))
    print(_dim("→ opening visible ancestor pane in iTerm…"))
    r = subprocess.run(
        [sys.executable, str(ITERM_DRIVER)],
        cwd=str(CLAWSEAT_ROOT),
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    raw = (r.stdout or r.stderr or "").strip().splitlines()
    last = raw[-1] if raw else "{}"
    try:
        data = json.loads(last)
    except Exception:
        data = None
    if r.returncode != 0:
        raise SystemExit(
            _red(
                "✗ iterm_panes_driver failed: "
                + (r.stderr.strip() or r.stdout.strip() or f"exit {r.returncode}")
            )
        )
    if not isinstance(data, dict) or data.get("status") != "ok":
        reason = (data or {}).get("reason") if isinstance(data, dict) else last
        raise SystemExit(
            _red(
                "✗ iTerm pane open failed: "
                + (reason or "unknown driver response")
                + "\n  tmux session is still alive; you can attach manually."
            )
        )
    print(_green("✓ visible ancestor pane opened"))


def prime_ancestor(session: str, brief: Path, *, dry_run: bool) -> None:
    prompt = (
        "You are the project ancestor for this ClawSeat install flow. "
        f"Read the role spec at {CLAWSEAT_ROOT / 'core' / 'skills' / 'clawseat-ancestor' / 'SKILL.md'} "
        f"and the bootstrap brief at {brief}. "
        "Then execute Phase-A B1..B7 now for this project. "
        "Treat the brief and skill file as your contract, continue autonomously, "
        "and update the project status as you progress."
    )
    if dry_run:
        print(_yellow("→ dry-run: would prime ancestor with bootstrap prompt"))
        return
    print(_dim("→ priming ancestor with bootstrap prompt…"))
    text_cmd = ["tmux", "send-keys", "-l", "-t", session, prompt]
    enter_cmd = ["tmux", "send-keys", "-t", session, "Enter"]
    r1 = subprocess.run(text_cmd, capture_output=True, text=True)
    if r1.returncode != 0:
        raise SystemExit(_red(f"✗ failed to prime ancestor input buffer for {session}"))
    r2 = subprocess.run(enter_cmd, capture_output=True, text=True)
    if r2.returncode != 0:
        raise SystemExit(_red(f"✗ failed to submit bootstrap prompt for {session}"))
    print(_green("✓ ancestor bootstrap prompt sent"))


# ── main ──────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ClawSeat v0.4 install entrypoint")
    ap.add_argument("--project", required=True, help="project name (alphanum + dash)")
    ap.add_argument("--clone-from", help="clone profile from an existing v2 project")
    ap.add_argument("--workdir", type=Path, default=None,
                    help="ancestor working directory (default: ~/.clawseat)")
    ap.add_argument("--dry-run", action="store_true",
                    help="run all preflight steps but do not actually launch ancestor")
    args = ap.parse_args(argv)

    project = args.project
    workdir = args.workdir or CLAWSEAT_ROOT

    if shutil.which("tmux") is None:
        raise SystemExit(_red("✗ tmux not on PATH; install tmux first"))
    if not LAUNCHER.is_file():
        raise SystemExit(_red(f"✗ launcher not found at {LAUNCHER}"))

    print(f"install_entrypoint: project={project} workdir={workdir}")
    profile = ensure_profile(project, clone_from=args.clone_from)
    verify_binding(project)

    ensure_entry_skills()
    ensure_ancestor_engineer(dry_run=args.dry_run)

    preflight = preflight_seats(profile)
    ok_seats = [s for s, _, ok in preflight if ok]
    bad_seats = [(s, m) for s, m, ok in preflight if not ok]
    for seat, msg, ok in preflight:
        mark = _green("✓") if ok else _yellow("!")
        print(f"  {mark} {seat}: {msg}")
    if bad_seats:
        print(_yellow(
            f"\nwarn: {len(bad_seats)}/{len(preflight)} seat(s) have missing/invalid auth. "
            "Ancestor will mark them state=dead at B4 per skill §2; you can rerun "
            "after fixing auth."
        ))

    brief = render_brief(project)
    session, created = launch_ancestor(
        project,
        profile,
        workdir=workdir,
        brief=brief,
        dry_run=args.dry_run,
    )
    open_ancestor_window(project, session, dry_run=args.dry_run)
    if created:
        prime_ancestor(session, brief, dry_run=args.dry_run)
    else:
        print(_yellow(
            "→ existing ancestor session reused; skipped auto-prime to avoid duplicating bootstrap"
        ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
