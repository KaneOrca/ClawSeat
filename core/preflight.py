"""
preflight.py — ClawSeat environment preflight checks.

Provides preflight_check() which verifies all prerequisites for a koder seat
to safely start a tmux session.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from core.resolve import try_resolve_clawseat_root as _try_resolve_clawseat_root
from core.resolve import dynamic_profile_path as _dynamic_profile_path


DEFAULT_OPENCLAW_HOME = Path.home() / ".openclaw"
CANONICAL_OPENCLAW_REPO = Path.home() / ".clawseat"
REQUIRED_OPENCLAW_GLOBAL_SKILLS = (
    "gstack-harness",
    "clawseat",
    "clawseat-install",
    "clawseat-koder-frontstage",
)
REQUIRED_OPENCLAW_KODER_SKILLS = (
    "gstack-harness",
    "clawseat-install",
    "clawseat-koder-frontstage",
)
BACKEND_CLI_OPTIONS = (
    ("claude", "npm install -g @anthropic-ai/claude-code"),
    ("codex", "npm install -g @openai/codex"),
    ("gemini", "npm install -g @google/gemini-cli"),
)


class PreflightStatus(Enum):
    PASS = "PASS"
    HARD_BLOCKED = "HARD_BLOCKED"
    RETRYABLE = "RETRYABLE"
    WARNING = "WARNING"


@dataclass(slots=True)
class PreflightItem:
    name: str
    status: PreflightStatus
    message: str
    fix_command: str = ""


@dataclass
class PreflightResult:
    all_pass: bool
    has_hard_blocked: bool
    has_retryable: bool
    hard_blocked_items: list[PreflightItem] = field(default_factory=list)
    retryable_items: list[PreflightItem] = field(default_factory=list)
    passing_items: list[PreflightItem] = field(default_factory=list)
    items: list[PreflightItem] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"preflight_check: {'PASS' if self.all_pass else 'FAIL'}"]
        for item in self.items:
            lines.append(f"  [{item.status.value}] {item.name}: {item.message}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _resolve_openclaw_home() -> Path:
    return Path(os.environ.get("OPENCLAW_HOME", str(DEFAULT_OPENCLAW_HOME))).expanduser()


def _load_toml_file(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _check_clawseat_root(*, runtime: str = "local") -> PreflightItem:
    """Check CLAWSEAT_ROOT env var and its inferred fallback."""
    env_val = os.environ.get("CLAWSEAT_ROOT", "").strip()
    canonical_root = CANONICAL_OPENCLAW_REPO.expanduser()
    if env_val:
        path = Path(env_val).expanduser()
        if path.exists():
            # Check required markers
            markers = (
                Path("core/scripts/agent_admin.py"),
                Path("core/harness_adapter.py"),
            )
            if all((path / m).exists() for m in markers):
                if runtime == "openclaw" and path.resolve() != canonical_root.resolve():
                    return PreflightItem(
                        name="CLAWSEAT_ROOT",
                        status=PreflightStatus.HARD_BLOCKED,
                        message=(
                            f"OpenClaw 首装要求 canonical checkout 位于 {canonical_root}; "
                            f"当前 env 指向 {path}"
                        ),
                        fix_command=(
                            "git clone https://github.com/KaneOrca/ClawSeat.git ~/.clawseat\n"
                            "export CLAWSEAT_ROOT=\"$HOME/.clawseat\""
                        ),
                    )
                return PreflightItem(
                    name="CLAWSEAT_ROOT",
                    status=PreflightStatus.PASS,
                    message=f"env set and valid at {path}",
                )
            else:
                return PreflightItem(
                    name="CLAWSEAT_ROOT",
                    status=PreflightStatus.HARD_BLOCKED,
                    message=f"CLAWSEAT_ROOT={path} exists but repository incomplete (missing core files)",
                    fix_command="export CLAWSEAT_ROOT=/path/to/ClawSeat",
                )
        else:
            return PreflightItem(
                name="CLAWSEAT_ROOT",
                status=PreflightStatus.HARD_BLOCKED,
                message=f"CLAWSEAT_ROOT={env_val} does not exist",
                fix_command=f"export CLAWSEAT_ROOT=/path/to/ClawSeat",
            )

    # Try to infer from __file__ or known locations
    helpers = (
        Path("core/scripts/agent_admin.py"),
        Path("core/skills/gstack-harness/scripts/_common.py"),
    )
    candidates: list[Path] = []

    # Walk up from this file
    script_path = Path(__file__).resolve()
    for parent in script_path.parents:
        candidates.append(parent)
        candidates.append(parent / "ClawSeat")

    # Add explicit locations
    agents_root = os.environ.get("AGENTS_ROOT", "")
    if agents_root:
        candidates.append(Path(agents_root).parent / "coding" / "ClawSeat")
    candidates.append(Path.home() / "coding" / "ClawSeat")

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if all((candidate / m).exists() for m in helpers):
            if runtime == "openclaw":
                if candidate.resolve() != canonical_root.resolve():
                    return PreflightItem(
                        name="CLAWSEAT_ROOT",
                        status=PreflightStatus.HARD_BLOCKED,
                        message=(
                            f"OpenClaw 首装要求 canonical checkout 位于 {canonical_root}; "
                            f"当前推断到的是 {candidate}"
                        ),
                        fix_command=(
                            "git clone https://github.com/KaneOrca/ClawSeat.git ~/.clawseat\n"
                            "export CLAWSEAT_ROOT=\"$HOME/.clawseat\""
                        ),
                    )
                return PreflightItem(
                    name="CLAWSEAT_ROOT",
                    status=PreflightStatus.PASS,
                    message=f"canonical OpenClaw checkout at {candidate}",
                )
            return PreflightItem(
                name="CLAWSEAT_ROOT",
                status=PreflightStatus.WARNING,
                message=f"env not set; inferred from filesystem: {candidate}",
                fix_command=f"export CLAWSEAT_ROOT={candidate}",
            )

    return PreflightItem(
        name="CLAWSEAT_ROOT",
        status=PreflightStatus.HARD_BLOCKED,
        message="cannot infer CLAWSEAT_ROOT; no env var set and no repository found",
        fix_command="export CLAWSEAT_ROOT=/path/to/ClawSeat",
    )


def _check_openclaw_host() -> list[PreflightItem]:
    items: list[PreflightItem] = []
    node = shutil.which("node")
    if node:
        items.append(
            PreflightItem(
                name="node",
                status=PreflightStatus.PASS,
                message=f"node at {node}",
            )
        )
    else:
        items.append(
            PreflightItem(
                name="node",
                status=PreflightStatus.HARD_BLOCKED,
                message="Node.js not found — OpenClaw runtime requires node",
                fix_command="brew install node",
            )
        )

    openclaw = shutil.which("openclaw")
    if openclaw:
        items.append(
            PreflightItem(
                name="openclaw",
                status=PreflightStatus.PASS,
                message=f"openclaw at {openclaw}",
            )
        )
    else:
        items.append(
            PreflightItem(
                name="openclaw",
                status=PreflightStatus.HARD_BLOCKED,
                message="OpenClaw CLI not found in PATH",
                fix_command="npm install -g openclaw",
            )
        )
    return items


def _check_backend_cli() -> PreflightItem:
    available: list[str] = []
    for binary, _install in BACKEND_CLI_OPTIONS:
        path = shutil.which(binary)
        if path:
            available.append(f"{binary} ({path})")
    if available:
        return PreflightItem(
            name="backend_cli",
            status=PreflightStatus.PASS,
            message="at least one backend CLI available: " + ", ".join(available),
        )
    return PreflightItem(
        name="backend_cli",
        status=PreflightStatus.HARD_BLOCKED,
        message="no backend CLI found — install at least one of claude, codex, or gemini before first seat launch",
        fix_command="\n".join(install for _, install in BACKEND_CLI_OPTIONS),
    )


def _check_openclaw_skill_bundle(clawseat_root: Path) -> PreflightItem:
    openclaw_home = _resolve_openclaw_home()
    if not openclaw_home.exists():
        return PreflightItem(
            name="openclaw_skill_bundle",
            status=PreflightStatus.RETRYABLE,
            message=f"OpenClaw home not found at {openclaw_home}",
            fix_command='python3 "${CLAWSEAT_ROOT}/shells/openclaw-plugin/install_openclaw_bundle.py"',
        )

    drift: list[str] = []
    for skill_name in REQUIRED_OPENCLAW_GLOBAL_SKILLS:
        dest = openclaw_home / "skills" / skill_name
        source = clawseat_root / "core" / "skills" / skill_name
        if not dest.is_symlink():
            drift.append(f"{dest} missing")
            continue
        if dest.resolve() != source.resolve():
            drift.append(f"{dest} -> {dest.resolve()} (expected {source})")
    for skill_name in REQUIRED_OPENCLAW_KODER_SKILLS:
        dest = openclaw_home / "workspace-koder" / "skills" / skill_name
        source = clawseat_root / "core" / "skills" / skill_name
        if not dest.is_symlink():
            drift.append(f"{dest} missing")
            continue
        if dest.resolve() != source.resolve():
            drift.append(f"{dest} -> {dest.resolve()} (expected {source})")

    if drift:
        return PreflightItem(
            name="openclaw_skill_bundle",
            status=PreflightStatus.RETRYABLE,
            message="skill symlink drift detected: " + "; ".join(drift[:4]),
            fix_command='python3 "${CLAWSEAT_ROOT}/shells/openclaw-plugin/install_openclaw_bundle.py"',
        )
    return PreflightItem(
        name="openclaw_skill_bundle",
        status=PreflightStatus.PASS,
        message=f"OpenClaw skill bundle points at {clawseat_root}",
    )


def _check_koder_workspace(project: str) -> PreflightItem:
    workspace = _resolve_openclaw_home() / "workspace-koder"
    required_files = (
        "IDENTITY.md",
        "SOUL.md",
        "AGENTS.md",
        "TOOLS.md",
        "MEMORY.md",
        "WORKSPACE_CONTRACT.toml",
    )
    if not workspace.exists():
        return PreflightItem(
            name="workspace_koder",
            status=PreflightStatus.RETRYABLE,
            message=f"workspace-koder missing at {workspace}",
            fix_command='python3 "${CLAWSEAT_ROOT}/core/skills/clawseat-install/scripts/openclaw_first_install.py"',
        )
    missing = [name for name in required_files if not (workspace / name).exists()]
    if missing:
        return PreflightItem(
            name="workspace_koder",
            status=PreflightStatus.RETRYABLE,
            message=f"workspace-koder incomplete: missing {', '.join(missing)}",
            fix_command='python3 "${CLAWSEAT_ROOT}/core/skills/clawseat-install/scripts/refresh_workspaces.py"',
        )
    try:
        contract = _load_toml_file(workspace / "WORKSPACE_CONTRACT.toml")
    except (OSError, tomllib.TOMLDecodeError):
        return PreflightItem(
            name="workspace_koder",
            status=PreflightStatus.RETRYABLE,
            message="workspace-koder contract unreadable",
            fix_command='python3 "${CLAWSEAT_ROOT}/core/skills/clawseat-install/scripts/refresh_workspaces.py"',
        )
    required_contract_keys = ("seat_id", "project", "profile", "backend_seats", "default_backend_start_seats")
    missing_keys = [key for key in required_contract_keys if key not in contract]
    if missing_keys or str(contract.get("project", "")).strip() != project:
        detail = (
            f"missing keys: {', '.join(missing_keys)}"
            if missing_keys
            else f"project mismatch: {contract.get('project')!r}"
        )
        return PreflightItem(
            name="workspace_koder",
            status=PreflightStatus.RETRYABLE,
            message=f"workspace-koder contract stale ({detail})",
            fix_command='python3 "${CLAWSEAT_ROOT}/core/skills/clawseat-install/scripts/refresh_workspaces.py"',
        )
    profile_path = Path(str(contract.get("profile", ""))).expanduser()
    if not profile_path.exists():
        return PreflightItem(
            name="workspace_koder",
            status=PreflightStatus.RETRYABLE,
            message=f"workspace-koder profile missing: {profile_path}",
            fix_command='python3 "${CLAWSEAT_ROOT}/core/skills/clawseat-install/scripts/refresh_workspaces.py"',
        )
    return PreflightItem(
        name="workspace_koder",
        status=PreflightStatus.PASS,
        message=f"workspace-koder ready at {workspace}",
    )


def _check_python() -> PreflightItem:
    """Check python3 >= 3.11 is available (tomllib is stdlib from 3.11)."""
    python = shutil.which("python3") or shutil.which("python")
    if not python:
        return PreflightItem(
            name="python3",
            status=PreflightStatus.HARD_BLOCKED,
            message="python3 not found in PATH",
            fix_command="brew install python3",
        )
    try:
        result = subprocess.run(
            ["python3", "-c", "import sys; print(sys.version_info[:2])"],
            text=True,
            capture_output=True,
            check=True,
        )
        version = tuple(map(int, result.stdout.strip().strip("()").split(", ")))
        major, minor = version[0], version[1]
        if major < 3 or (major == 3 and minor < 11):
            return PreflightItem(
                name="python3",
                status=PreflightStatus.HARD_BLOCKED,
                message=f"python {major}.{minor} < 3.11 (tomllib requires 3.11+)",
                fix_command="brew install python3  # 3.11+ recommended for tomllib stdlib",
            )
        return PreflightItem(
            name="python3",
            status=PreflightStatus.PASS,
            message=f"python {major}.{minor} (at {python})",
        )
    except subprocess.CalledProcessError:
        return PreflightItem(
            name="python3",
            status=PreflightStatus.HARD_BLOCKED,
            message="python3 found but cannot run",
            fix_command="brew install python3",
        )


def _check_tomllib() -> PreflightItem:
    """Check tomllib availability (Python 3.11+ stdlib)."""
    try:
        import tomllib

        return PreflightItem(
            name="tomllib",
            status=PreflightStatus.PASS,
            message="tomllib available (Python 3.11+ stdlib)",
        )
    except ModuleNotFoundError:
        return PreflightItem(
            name="tomllib",
            status=PreflightStatus.HARD_BLOCKED,
            message="tomllib not available — Python 3.11+ required",
            fix_command="brew install python3  # 3.11+ includes tomllib stdlib",
        )


def _check_tmux() -> tuple[PreflightItem, PreflightItem]:
    """Check tmux is installed AND server is running. Returns (install_check, server_check)."""
    tmux_path = shutil.which("tmux")
    if not tmux_path:
        has_brew = shutil.which("brew") is not None
        if has_brew:
            fix = "brew install tmux"
        else:
            fix = (
                '# Install Homebrew first:\n'
                '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"\n'
                '# Then install tmux:\n'
                'brew install tmux'
            )
        install_check = PreflightItem(
            name="tmux",
            status=PreflightStatus.HARD_BLOCKED,
            message="tmux not found in PATH",
            fix_command=fix,
        )
        return install_check, PreflightItem(
            name="tmux_server",
            status=PreflightStatus.HARD_BLOCKED,
            message="cannot check — tmux not installed",
        )

    # tmux is installed
    install_check = PreflightItem(
        name="tmux",
        status=PreflightStatus.PASS,
        message=f"tmux at {tmux_path}",
    )

    # Check server is running
    try:
        result = subprocess.run(
            ["tmux", "list-sessions"],
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
        if "no server" in result.stderr.lower() or result.returncode != 0:
            server_check = PreflightItem(
                name="tmux_server",
                status=PreflightStatus.RETRYABLE,
                message="tmux installed but no server running",
                fix_command="tmux new-session -d",
            )
        else:
            server_check = PreflightItem(
                name="tmux_server",
                status=PreflightStatus.PASS,
                message=f"server running ({result.stdout.splitlines().__len__()} sessions)",
            )
    except subprocess.TimeoutExpired:
        server_check = PreflightItem(
            name="tmux_server",
            status=PreflightStatus.HARD_BLOCKED,
            message="tmux list-sessions timed out",
            fix_command="brew install tmux",
        )
    except Exception as e:
        server_check = PreflightItem(
            name="tmux_server",
            status=PreflightStatus.RETRYABLE,
            message=f"tmux installed but server check failed: {e}",
            fix_command="tmux new-session -d",
        )

    return install_check, server_check


def _check_repo_integrity(clawseat_root: Path) -> PreflightItem:
    """Check ClawSeat repo has all required core files."""
    required = [
        Path("core/scripts/agent_admin.py"),
        Path("core/harness_adapter.py"),
        Path("core/adapter/clawseat_adapter.py"),
        Path("core/skills/gstack-harness/scripts/_common.py"),
        Path("adapters/harness/tmux-cli/adapter.py"),
    ]
    missing = [str(clawseat_root / r) for r in required if not (clawseat_root / r).exists()]
    if missing:
        return PreflightItem(
            name="repo_integrity",
            status=PreflightStatus.HARD_BLOCKED,
            message=f"missing files: {', '.join(missing)}",
            fix_command="export CLAWSEAT_ROOT=/path/to/ClawSeat  # ensure correct path",
        )
    return PreflightItem(
        name="repo_integrity",
        status=PreflightStatus.PASS,
        message="all required core files present",
    )


def _check_dynamic_profile(project: str, *, runtime: str = "local") -> PreflightItem:
    """Check dynamic profile exists for the project."""
    dynamic_path = _dynamic_profile_path(project)
    candidates = [dynamic_path]
    if runtime != "openclaw":
        candidates.append(Path(f"/tmp/{project}-profile.toml"))
    for candidate in candidates:
        if candidate.exists():
            try:
                payload = _load_toml_file(candidate)
            except (OSError, tomllib.TOMLDecodeError) as exc:
                return PreflightItem(
                    name="dynamic_profile",
                    status=PreflightStatus.RETRYABLE,
                    message=f"profile exists but is unreadable: {candidate} ({exc})",
                    fix_command=(
                        'python3 "${CLAWSEAT_ROOT}/core/skills/clawseat-install/scripts/cs_init.py" '
                        "--refresh-profile"
                        if project == "install"
                        else (
                            f'python3 "${{CLAWSEAT_ROOT}}/core/skills/gstack-harness/scripts/migrate_profile.py" '
                            f"--source-profile /tmp/{project}-profile.toml "
                            f"--output-profile {dynamic_path} "
                            f"--project-name {project}"
                        )
                    ),
                )

            if project == "install":
                dynamic = payload.get("dynamic_roster", {})
                missing_keys = [
                    key
                    for key in ("materialized_seats", "bootstrap_seats", "default_start_seats")
                    if key not in dynamic
                ]
                project_name = str(payload.get("project_name", "")).strip()
                if project_name and project_name != project:
                    return PreflightItem(
                        name="dynamic_profile",
                        status=PreflightStatus.RETRYABLE,
                        message=f"profile project mismatch: expected {project!r}, found {project_name!r}",
                        fix_command=(
                            'python3 "${CLAWSEAT_ROOT}/core/skills/clawseat-install/scripts/cs_init.py" '
                            "--refresh-profile"
                        ),
                    )
                if missing_keys:
                    return PreflightItem(
                        name="dynamic_profile",
                        status=PreflightStatus.RETRYABLE,
                        message=(
                            f"profile found at {candidate} but dynamic_roster is missing "
                            f"{', '.join(missing_keys)}"
                        ),
                        fix_command=(
                            'python3 "${CLAWSEAT_ROOT}/core/skills/clawseat-install/scripts/cs_init.py" '
                            "--refresh-profile"
                        ),
                    )
            return PreflightItem(
                name="dynamic_profile",
                status=PreflightStatus.PASS,
                message=f"profile found at {candidate}",
            )
    if project == "install":
        return PreflightItem(
            name="dynamic_profile",
            status=PreflightStatus.RETRYABLE,
            message="no dynamic profile found for canonical install project",
            fix_command=(
                "python3 \"${CLAWSEAT_ROOT}/core/skills/clawseat-install/scripts/cs_init.py\" "
                "--refresh-profile"
            ),
        )
    return PreflightItem(
        name="dynamic_profile",
        status=PreflightStatus.RETRYABLE,
        message=f"no dynamic profile found for {project}",
        fix_command=(
            f"python3 \"${{CLAWSEAT_ROOT}}/core/skills/gstack-harness/scripts/migrate_profile.py\" "
            f"--source-profile /tmp/{project}-profile.toml "
            f"--output-profile /tmp/{project}-profile-dynamic.toml "
            f"--project-name {project}"
        ),
    )


def _check_session_binding_dir(project: str) -> PreflightItem:
    """Check session binding directory exists, falling back to tmux session scan."""
    sessions_root = Path(os.environ.get("SESSIONS_ROOT", str(Path.home() / ".agents" / "sessions")))
    binding_dir = sessions_root / project
    if binding_dir.exists():
        return PreflightItem(
            name="session_binding_dir",
            status=PreflightStatus.PASS,
            message=f"binding directory exists: {binding_dir}",
        )

    # Fallback: if tmux has sessions for this project, the harness is functional
    # even if the binding directory path is non-standard
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
        prefix = f"{project}-"
        has_project_sessions = any(
            s.strip().startswith(prefix) for s in result.stdout.splitlines()
        )
        if has_project_sessions:
            return PreflightItem(
                name="session_binding_dir",
                status=PreflightStatus.WARNING,
                message=f"binding directory not found at {binding_dir} but tmux sessions exist for {project}",
                fix_command=f"mkdir -p {binding_dir}",
            )
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass

    return PreflightItem(
        name="session_binding_dir",
        status=PreflightStatus.RETRYABLE,
        message=f"binding directory does not exist: {binding_dir}",
        fix_command=f"mkdir -p {binding_dir}",
    )


# ---------------------------------------------------------------------------
# Auto-fix helpers
# ---------------------------------------------------------------------------


def auto_fix(item: PreflightItem, project: str = "", *, runtime: str = "local") -> PreflightItem:
    """
    Attempt to auto-fix a RETRYABLE item.

    Returns an updated PreflightItem with the result.
    """
    if item.status != PreflightStatus.RETRYABLE:
        return item

    if item.name == "tmux_server":
        # Start tmux server in background
        try:
            subprocess.run(["tmux", "new-session", "-d"], check=False, capture_output=True, timeout=10)
            result = subprocess.run(
                ["tmux", "list-sessions"],
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode == 0 and "no server" not in result.stderr.lower():
                return PreflightItem(
                    name=item.name,
                    status=PreflightStatus.PASS,
                    message="tmux server started",
                    fix_command="",
                )
            return PreflightItem(
                name=item.name,
                status=PreflightStatus.RETRYABLE,
                message="tmux server start attempted but still not running",
                fix_command="tmux new-session -d",
            )
        except Exception as e:
            return PreflightItem(
                name=item.name,
                status=PreflightStatus.RETRYABLE,
                message=f"tmux server start failed: {e}",
                fix_command="tmux new-session -d",
            )

    if item.name == "dynamic_profile":
        try:
            if project == "install":
                template_root = _resolve_clawseat_root_from_env()
                if template_root is None and runtime == "openclaw":
                    template_root = CANONICAL_OPENCLAW_REPO
                if template_root is None:
                    template_root = Path.home() / "coding" / "ClawSeat"
                template_path = template_root / "examples" / "starter" / "profiles" / "install.toml"
                output_profile = _dynamic_profile_path(project)
                if not template_path.exists():
                    return PreflightItem(
                        name=item.name,
                        status=PreflightStatus.RETRYABLE,
                        message=f"install profile template not found at {template_path}",
                        fix_command=item.fix_command,
                    )
                output_profile.parent.mkdir(parents=True, exist_ok=True)
                output_profile.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")
                return PreflightItem(
                    name=item.name,
                    status=PreflightStatus.PASS,
                    message=f"canonical install profile created at {output_profile}",
                    fix_command="",
                )

            # Find migrate_profile.py — prefer CLAWSEAT_ROOT, then filesystem inference
            clawseat_root = _resolve_clawseat_root_from_env()
            if clawseat_root is None:
                clawseat_root = CANONICAL_OPENCLAW_REPO if runtime == "openclaw" else Path.home() / "coding" / "ClawSeat"
            migrate_script = clawseat_root / "core" / "skills" / "gstack-harness" / "scripts" / "migrate_profile.py"
            if not migrate_script.exists():
                return PreflightItem(
                    name=item.name,
                    status=PreflightStatus.RETRYABLE,
                    message=f"migrate_profile.py not found at {migrate_script}",
                    fix_command=item.fix_command,
                )
            source_profile = Path(f"/tmp/{project}-profile.toml")
            output_profile = _dynamic_profile_path(project)
            if not source_profile.exists():
                return PreflightItem(
                    name=item.name,
                    status=PreflightStatus.RETRYABLE,
                    message=f"legacy profile not found at {source_profile}; cannot auto-create dynamic profile",
                    fix_command=item.fix_command,
                )
            result = subprocess.run(
                [
                    sys.executable,
                    str(migrate_script),
                    "--source-profile",
                    str(source_profile),
                    "--output-profile",
                    str(output_profile),
                    "--project-name",
                    project,
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if result.returncode == 0:
                return PreflightItem(
                    name=item.name,
                    status=PreflightStatus.PASS,
                    message="dynamic profile created",
                    fix_command="",
                )
            return PreflightItem(
                name=item.name,
                status=PreflightStatus.RETRYABLE,
                message=f"profile creation failed: {result.stderr or result.stdout}",
                fix_command=item.fix_command,
            )
        except Exception as e:
            return PreflightItem(
                name=item.name,
                status=PreflightStatus.RETRYABLE,
                message=f"profile creation failed: {e}",
                fix_command=item.fix_command,
            )

    if item.name == "session_binding_dir":
        try:
            sessions_root = Path(os.environ.get("SESSIONS_ROOT", str(Path.home() / ".agents" / "sessions")))
            binding_dir = sessions_root / project
            binding_dir.mkdir(parents=True, exist_ok=True)
            return PreflightItem(
                name=item.name,
                status=PreflightStatus.PASS,
                message=f"directory created: {binding_dir}",
                fix_command="",
            )
        except Exception as e:
            return PreflightItem(
                name=item.name,
                status=PreflightStatus.RETRYABLE,
                message=f"mkdir failed: {e}",
                fix_command=item.fix_command,
            )

    if item.name == "openclaw_skill_bundle":
        try:
            clawseat_root = _resolve_clawseat_root_from_env() or CANONICAL_OPENCLAW_REPO
            script = clawseat_root / "shells" / "openclaw-plugin" / "install_openclaw_bundle.py"
            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--openclaw-home",
                    str(_resolve_openclaw_home()),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
                env={**os.environ, "CLAWSEAT_ROOT": str(clawseat_root)},
            )
            if result.returncode == 0:
                return PreflightItem(
                    name=item.name,
                    status=PreflightStatus.PASS,
                    message="OpenClaw skill bundle repaired",
                    fix_command="",
                )
            detail = (result.stderr or result.stdout).strip() or "install_openclaw_bundle.py failed"
            return PreflightItem(
                name=item.name,
                status=PreflightStatus.RETRYABLE,
                message=detail,
                fix_command=item.fix_command,
            )
        except Exception as e:
            return PreflightItem(
                name=item.name,
                status=PreflightStatus.RETRYABLE,
                message=f"skill bundle repair failed: {e}",
                fix_command=item.fix_command,
            )

    if item.name == "workspace_koder":
        try:
            clawseat_root = _resolve_clawseat_root_from_env() or CANONICAL_OPENCLAW_REPO
            workspace = _resolve_openclaw_home() / "workspace-koder"
            profile_path = _dynamic_profile_path(project)
            env = {**os.environ, "CLAWSEAT_ROOT": str(clawseat_root)}
            if (workspace / "WORKSPACE_CONTRACT.toml").exists():
                script = clawseat_root / "core" / "skills" / "clawseat-install" / "scripts" / "refresh_workspaces.py"
                command = [
                    sys.executable,
                    str(script),
                    "--project",
                    project,
                    "--profile",
                    str(profile_path),
                    "--koder-workspace",
                    str(workspace),
                ]
            else:
                workspace.mkdir(parents=True, exist_ok=True)
                script = clawseat_root / "core" / "skills" / "clawseat-install" / "scripts" / "init_koder.py"
                command = [
                    sys.executable,
                    str(script),
                    "--workspace",
                    str(workspace),
                    "--project",
                    project,
                    "--profile",
                    str(profile_path),
                    "--feishu-group-id",
                    "",
                ]
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=90,
                env=env,
            )
            if result.returncode == 0:
                return PreflightItem(
                    name=item.name,
                    status=PreflightStatus.PASS,
                    message=f"workspace-koder ready at {workspace}",
                    fix_command="",
                )
            detail = (result.stderr or result.stdout).strip() or "workspace repair failed"
            return PreflightItem(
                name=item.name,
                status=PreflightStatus.RETRYABLE,
                message=detail,
                fix_command=item.fix_command,
            )
        except Exception as e:
            return PreflightItem(
                name=item.name,
                status=PreflightStatus.RETRYABLE,
                message=f"workspace repair failed: {e}",
                fix_command=item.fix_command,
            )

    # Unknown — cannot auto-fix
    return item


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def _check_optional_cli(binary: str, label: str, install_hint: str) -> PreflightItem:
    """Check an optional CLI tool. WARNING if missing, not HARD_BLOCKED."""
    path = shutil.which(binary)
    if path:
        return PreflightItem(
            name=binary,
            status=PreflightStatus.PASS,
            message=f"{label} at {path}",
        )
    return PreflightItem(
        name=binary,
        status=PreflightStatus.WARNING,
        message=f"{label} not found — needed for seats using this runtime",
        fix_command=install_hint,
    )


def _check_skills() -> list[PreflightItem]:
    """Validate all skills in the registry are present on disk."""
    try:
        try:
            from core.skill_registry import load_registry, validate_all
        except ImportError:
            from skill_registry import load_registry, validate_all
        result = validate_all()
        items: list[PreflightItem] = []
        for si in result.items:
            if si.exists:
                items.append(PreflightItem(
                    name=f"skill_{si.name}",
                    status=PreflightStatus.PASS,
                    message=f"skill {si.name}: ok ({si.source})",
                ))
            elif si.required:
                items.append(PreflightItem(
                    name=f"skill_{si.name}",
                    status=PreflightStatus.HARD_BLOCKED,
                    message=f"required skill {si.name} ({si.source}) not found at {si.expanded_path}",
                    fix_command=si.fix_hint,
                ))
            else:
                items.append(PreflightItem(
                    name=f"skill_{si.name}",
                    status=PreflightStatus.WARNING,
                    message=f"optional skill {si.name} ({si.source}) not found at {si.expanded_path}",
                    fix_command=si.fix_hint,
                ))
        return items
    except (ImportError, FileNotFoundError, OSError) as exc:
        return [PreflightItem(
            name="skill_registry",
            status=PreflightStatus.WARNING,
            message=f"skill registry check failed: {exc}",
        )]


def preflight_check(project: str, *, runtime: str = "local") -> PreflightResult:
    """
    Run all preflight checks for the given project.

    Returns a PreflightResult with per-item status and categorized lists.
    """
    items: list[PreflightItem] = []

    # CLAWSEAT_ROOT
    items.append(_check_clawseat_root(runtime=runtime))
    clawseat_root = _resolve_clawseat_root_from_env()

    # python3
    items.append(_check_python())

    # tomllib
    items.append(_check_tomllib())

    # tmux (install + server)
    tmux_install, tmux_server = _check_tmux()
    items.append(tmux_install)
    items.append(tmux_server)

    # repo integrity (only if CLAWSEAT_ROOT found)
    if clawseat_root and clawseat_root.exists():
        items.append(_check_repo_integrity(clawseat_root))
    else:
        items.append(PreflightItem(
            name="repo_integrity",
            status=PreflightStatus.HARD_BLOCKED,
            message="cannot check — CLAWSEAT_ROOT not resolved",
        ))

    # dynamic profile
    items.append(_check_dynamic_profile(project, runtime=runtime))

    # session binding dir
    items.append(_check_session_binding_dir(project))

    if runtime == "openclaw":
        items.extend(_check_openclaw_host())
        items.append(_check_backend_cli())
        if clawseat_root and clawseat_root.exists():
            items.append(_check_openclaw_skill_bundle(clawseat_root))
        else:
            items.append(PreflightItem(
                name="openclaw_skill_bundle",
                status=PreflightStatus.HARD_BLOCKED,
                message="cannot validate skill bundle — CLAWSEAT_ROOT not resolved",
            ))
        items.append(_check_koder_workspace(project))
        items.append(_check_optional_cli("lark-cli", "Feishu/Lark CLI", "brew install larksuite/cli/lark-cli"))
    else:
        # optional runtime CLIs (WARNING, not blocking)
        items.append(_check_optional_cli("claude", "Claude Code CLI", "npm install -g @anthropic-ai/claude-code"))
        items.append(_check_optional_cli("codex", "Codex CLI", "npm install -g @openai/codex"))
        items.append(_check_optional_cli("gemini", "Gemini CLI", "npm install -g @google/gemini-cli"))
        items.append(_check_optional_cli("lark-cli", "Feishu/Lark CLI", "brew install larksuite/cli/lark-cli"))

    # gstack skills (WARNING — needed for specialist seats)
    gstack_root = Path.home() / ".gstack" / "repos" / "gstack" / ".agents" / "skills"
    if not gstack_root.exists():
        items.append(PreflightItem(
            name="gstack",
            status=PreflightStatus.WARNING,
            message="gstack skills not found — specialist seats (builder, reviewer, qa, designer) will lack key capabilities",
            fix_command=(
                "git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git ~/.gstack/repos/gstack\n"
                "cd ~/.gstack/repos/gstack && ./setup"
            ),
        ))

    # skill registry validation
    items.extend(_check_skills())

    # Categorize
    hard_blocked = [i for i in items if i.status == PreflightStatus.HARD_BLOCKED]
    retryable = [i for i in items if i.status == PreflightStatus.RETRYABLE]
    passing = [i for i in items if i.status in (PreflightStatus.PASS, PreflightStatus.WARNING)]

    return PreflightResult(
        all_pass=len(hard_blocked) == 0 and len(retryable) == 0,
        has_hard_blocked=len(hard_blocked) > 0,
        has_retryable=len(retryable) > 0,
        hard_blocked_items=hard_blocked,
        retryable_items=retryable,
        passing_items=passing,
        items=items,
    )


def _resolve_clawseat_root_from_env() -> Path | None:
    """Resolve CLAWSEAT_ROOT, trying env then filesystem inference."""
    return _try_resolve_clawseat_root()


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ClawSeat environment preflight checks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "project",
        nargs="?",
        default=os.environ.get("OPENCLAW_PROJECT", ""),
        help="Project name (default: from OPENCLAW_PROJECT env var, or current project)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON",
    )
    parser.add_argument(
        "--auto-fix",
        action="store_true",
        help="Attempt to auto-fix retryable items",
    )
    parser.add_argument(
        "--runtime",
        choices=("local", "openclaw"),
        default="local",
        help="Preflight mode. 'openclaw' enables canonical checkout and host checks.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    result = preflight_check(args.project, runtime=args.runtime)

    if args.auto_fix:
        for item in result.retryable_items:
            fixed = auto_fix(item, args.project, runtime=args.runtime)
            idx = result.items.index(item)
            result.items[idx] = fixed
        # Re-run to get updated status
        result = preflight_check(args.project, runtime=args.runtime)

    if args.json:
        import json as _json
        output = {
            "all_pass": result.all_pass,
            "has_hard_blocked": result.has_hard_blocked,
            "has_retryable": result.has_retryable,
            "runtime": args.runtime,
            "items": [
                {
                    "name": i.name,
                    "status": i.status.value,
                    "message": i.message,
                    "fix_command": i.fix_command,
                }
                for i in result.items
            ],
        }
        print(_json.dumps(output, indent=2, ensure_ascii=False))
    else:
        # Human-readable output
        print(f"preflight_check: {'PASS' if result.all_pass else 'FAIL'} [{args.project}] ({args.runtime})")
        for item in result.items:
            icon = {
                PreflightStatus.PASS: "✓",
                PreflightStatus.HARD_BLOCKED: "✗",
                PreflightStatus.RETRYABLE: "⟳",
                PreflightStatus.WARNING: "⚠",
            }.get(item.status, "?")
            print(f"  [{icon}] {item.name}: {item.message}")
            if item.status == PreflightStatus.HARD_BLOCKED and item.fix_command:
                print(f"      → {item.fix_command}")
            elif item.status == PreflightStatus.RETRYABLE and item.fix_command:
                print(f"      → {item.fix_command}")

    if result.has_hard_blocked:
        return 1
    if result.has_retryable:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
