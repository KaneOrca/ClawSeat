from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


# ── Sandbox HOME resolution ───────────────────────────────────────────────────
#
# Claude Code seats run inside a sandbox HOME at
#   ~/.agents/runtime/identities/<tool>/<auth>/<identity>/home/
# so Path.home() inside a seat returns THAT, not the operator's real HOME.
# All agent_admin path resolution must use the effective home to avoid
# pointing at sandbox-local artifacts that don't exist there.


def _is_sandbox_home(path: Path) -> bool:
    """Return True if *path* looks like a ClawSeat seat runtime sandbox HOME."""
    return "/.agents/runtime/identities/" in str(path)


def _real_user_home() -> Path:
    """Return the operator's real HOME, bypassing seat sandbox isolation.

    Resolution priority (most-authoritative first):
    1. CLAWSEAT_REAL_HOME env override — set explicitly by the harness.
    2. AGENT_HOME env differing from Path.home() — harness injected real path.
    3. pwd.getpwuid — the OS's authoritative answer, immune to HOME env override.
    4. Path.home() as last-resort fallback.
    """
    if os.environ.get("CLAWSEAT_SANDBOX_HOME_STRICT") == "1":
        return Path.home()
    override = os.environ.get("CLAWSEAT_REAL_HOME")
    if override:
        return Path(override).expanduser()
    agent_home = os.environ.get("AGENT_HOME", "")
    if agent_home and agent_home != str(Path.home()):
        return Path(agent_home).expanduser()
    try:
        import pwd
        pw = pwd.getpwuid(os.getuid())
        if pw and pw.pw_dir:
            return Path(pw.pw_dir)
    except (ImportError, KeyError):
        pass
    return Path.home()


def _resolve_effective_home() -> Path:
    """Return the effective HOME for agent_admin path resolution.

    Respects CLAWSEAT_SANDBOX_HOME_STRICT=1 (force sandbox, for tests)
    and delegates to _real_user_home() otherwise.
    """
    return _real_user_home()


def _resolve_tool_bin(name: str) -> str:
    resolved = shutil.which(name)
    if resolved:
        return resolved
    homebrew = f"/opt/homebrew/bin/{name}"
    if os.path.exists(homebrew):
        return homebrew
    return name


def _default_path() -> str:
    override = os.environ.get("CLAWSEAT_DEFAULT_PATH")
    if override:
        return override
    base = "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    if sys.platform == "darwin":
        return "/opt/homebrew/bin:" + base
    return base


REPO_ROOT = Path(__file__).resolve().parents[2]
HOME = _resolve_effective_home()
AGENTS_ROOT = HOME / ".agents"
PROJECTS_ROOT = AGENTS_ROOT / "projects"
ENGINEERS_ROOT = AGENTS_ROOT / "engineers"
SESSIONS_ROOT = AGENTS_ROOT / "sessions"
WORKSPACES_ROOT = AGENTS_ROOT / "workspaces"
RUNTIME_ROOT = AGENTS_ROOT / "runtime" / "identities"
SECRETS_ROOT = AGENTS_ROOT / "secrets"
LEGACY_ROOT = AGENTS_ROOT / "legacy"
STATE_ROOT = AGENTS_ROOT / "state"
CURRENT_PROJECT_PATH = STATE_ROOT / "current_project"
TEMPLATES_ROOT = REPO_ROOT / "core" / "templates"
DEFAULT_PATH = _default_path()
AGENTCTL_SH = REPO_ROOT / "core" / "shell-scripts" / "agentctl.sh"
AGENT_ADMIN_SH = REPO_ROOT / "core" / "shell-scripts" / "agent-admin.sh"
SEND_AND_VERIFY_SH = REPO_ROOT / "core" / "shell-scripts" / "send-and-verify.sh"
HARNESS_PROFILE_ROOT = REPO_ROOT / "core" / "skills" / "gstack-harness" / "assets" / "profiles"

LEGACY_IDENTITIES_ROOT = HOME / ".agent-runtime" / "identities"
LEGACY_SECRETS_ROOT = HOME / ".agent-runtime" / "secrets"
LEGACY_GEMINI_SANDBOXES = [
    REPO_ROOT / ".gemini-E-sandbox",
    REPO_ROOT / ".gemini-F-sandbox",
    REPO_ROOT / ".gemini-image-sandbox",
]

LEGACY_CONFIG_ROOT = REPO_ROOT / ".agent" / "config"
LEGACY_ASSIGNMENTS_PATH = LEGACY_CONFIG_ROOT / "engineer-assignments.toml"
LEGACY_IDENTITIES_PATH = LEGACY_CONFIG_ROOT / "auth-identities.toml"

# Legacy compatibility defaults for the historical "coding" roster.
# These are not the canonical role-first runtime model for new ClawSeat projects;
# new projects should come from templates/profiles such as gstack-harness and use
# `koder / planner / builder-1 / reviewer-1 / qa-1 / designer-1`.
PROJECT_DEFAULTS = {
    "coding": {
        "repo_root": str(REPO_ROOT),
        "monitor_session": "project-coding-monitor",
        "engineers": [
            "engineer-a",
            "engineer-b",
            "engineer-c",
            "engineer-d",
            "engineer-e",
            "engineer-f",
            "engineer-g",
            "engineer-h",
            "engineer-pm",
        ],
        "monitor_engineers": [
            "engineer-a",
            "engineer-b",
            "engineer-c",
            "engineer-d",
            "engineer-g",
            "engineer-h",
            "engineer-e",
            "engineer-f",
        ],
    }
}

# Historical engineer definitions kept only for migration, recovery, and old
# project compatibility. Do not copy these ids into new profiles unless you are
# explicitly operating a legacy engineer-* project.
LEGACY_ENGINEERS = {
    "engineer-a": {
        "project": "coding",
        "tool": "codex",
        "auth_mode": "oauth",
        "provider": "openai",
        "legacy_workspace": "",
        "legacy_session": "codex-A",
        "launch_args": ["--full-auto"],
        "monitor": True,
        "seed_runtime": str(LEGACY_IDENTITIES_ROOT / "codex" / "oauth" / "main"),
        "seed_secret": "",
    },
    "engineer-b": {
        "project": "coding",
        "tool": "claude",
        "auth_mode": "oauth",
        "provider": "anthropic",
        "legacy_workspace": str(HOME / ".b-workspace"),
        "legacy_session": "claude-B",
        "launch_args": [],
        "monitor": True,
        "seed_runtime": str(LEGACY_IDENTITIES_ROOT / "claude" / "oauth" / "main"),
        "seed_secret": "",
    },
    "engineer-c": {
        "project": "coding",
        "tool": "claude",
        "auth_mode": "api",
        "provider": "xcode-best",
        "legacy_workspace": str(REPO_ROOT / ".c-workspace"),
        "legacy_session": "claude-C",
        "launch_args": [],
        "monitor": True,
        "seed_runtime": str(LEGACY_IDENTITIES_ROOT / "claude" / "api" / "xcode"),
        "seed_secret": str(LEGACY_SECRETS_ROOT / "claude" / "xcode.env"),
    },
    "engineer-d": {
        "project": "coding",
        "tool": "claude",
        "auth_mode": "api",
        "provider": "xcode-best",
        "legacy_workspace": str(REPO_ROOT / ".d-workspace"),
        "legacy_session": "claude-D",
        "launch_args": [],
        "monitor": True,
        "seed_runtime": str(LEGACY_IDENTITIES_ROOT / "claude" / "api" / "xcode"),
        "seed_secret": str(LEGACY_SECRETS_ROOT / "claude" / "xcode.env"),
    },
    "engineer-e": {
        "project": "coding",
        "tool": "gemini",
        "auth_mode": "api",
        "provider": "google-api-key",
        "legacy_workspace": "",
        "legacy_session": "gemini-E",
        "launch_args": [],
        "monitor": True,
        "seed_runtime": str(LEGACY_IDENTITIES_ROOT / "gemini" / "api" / "primary"),
        "seed_secret": str(LEGACY_SECRETS_ROOT / "gemini" / "primary.env"),
    },
    "engineer-f": {
        "project": "coding",
        "tool": "gemini",
        "auth_mode": "oauth",
        "provider": "google",
        "legacy_workspace": "",
        "legacy_session": "gemini-F",
        "launch_args": [],
        "monitor": True,
        "seed_runtime": str(LEGACY_IDENTITIES_ROOT / "gemini" / "oauth" / "main"),
        "seed_secret": "",
    },
    "engineer-g": {
        "project": "coding",
        "tool": "claude",
        "auth_mode": "api",
        "provider": "minimax",
        "legacy_workspace": str(REPO_ROOT / ".g-workspace"),
        "legacy_session": "claude-G",
        "launch_args": [],
        "monitor": True,
        "seed_runtime": str(LEGACY_IDENTITIES_ROOT / "claude" / "api" / "minimax"),
        "seed_secret": str(LEGACY_SECRETS_ROOT / "claude" / "minimax.env"),
    },
    "engineer-h": {
        "project": "coding",
        "tool": "claude",
        "auth_mode": "api",
        "provider": "minimax",
        "legacy_workspace": str(REPO_ROOT / ".h-workspace"),
        "legacy_session": "claude-H",
        "launch_args": [],
        "monitor": True,
        "seed_runtime": str(LEGACY_IDENTITIES_ROOT / "claude" / "api" / "minimax"),
        "seed_secret": str(LEGACY_SECRETS_ROOT / "claude" / "minimax.env"),
    },
    "engineer-pm": {
        "project": "coding",
        "tool": "codex",
        "auth_mode": "oauth",
        "provider": "openai",
        "legacy_workspace": str(REPO_ROOT / ".pm-workspace"),
        "legacy_session": "codex-PM",
        "launch_args": [],
        "monitor": False,
        "seed_runtime": str(LEGACY_IDENTITIES_ROOT / "codex" / "oauth" / "main"),
        "seed_secret": "",
    },
}

TOOL_BINARIES = {
    "codex": _resolve_tool_bin("codex"),
    "claude": _resolve_tool_bin("claude"),
    "gemini": _resolve_tool_bin("gemini"),
}

DEFAULT_TOOL_ARGS = {
    "codex": ["--dangerously-bypass-approvals-and-sandbox"],
    "claude": ["--dangerously-skip-permissions"],
    "gemini": ["--approval-mode=yolo"],
}

XCODE_PROVIDER_ENDPOINT_RULES = {
    "claude": {
        "xcode-best": {
            "env_var": "ANTHROPIC_BASE_URL",
            "base_url": "https://xcode.best",
        }
    },
    "codex": {
        "xcode-best": {
            "base_url": "https://api.xcode.best/v1",
        }
    },
}

CLAUDE_API_PROVIDER_CONFIGS = {
    "minimax": {
        "model": "MiniMax-M2.7-highspeed",
        "base_url": "https://api.minimaxi.com/anthropic",
        # MiniMax Anthropic-compatible endpoint requires ANTHROPIC_AUTH_TOKEN
        # instead of ANTHROPIC_API_KEY, plus extended timeout and traffic control.
        "auth_token_var": "ANTHROPIC_AUTH_TOKEN",
        "extra_env": {
            "API_TIMEOUT_MS": "3000000",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        },
    },
}

CODEX_API_PROVIDER_CONFIGS = {
    "xcode-best": {
        "model_provider": "api111",
        "model": "gpt-5.4",
        "model_reasoning_effort": "high",
        "disable_response_storage": True,
        "preferred_auth_method": "apikey",
        "personality": "pragmatic",
        "base_url": "https://api.xcode.best/v1",
        "wire_api": "responses",
    },
}


SUPPORTED_RUNTIME_MATRIX = {
    "claude": {
        "oauth": ("anthropic",),
        "api": ("xcode-best", "minimax"),
    },
    "codex": {
        "oauth": ("openai",),
        "api": ("xcode-best",),
    },
    "gemini": {
        "oauth": ("google",),
        "api": ("google-api-key",),
    },
}


def supported_providers(tool: str, auth_mode: str) -> tuple[str, ...]:
    return SUPPORTED_RUNTIME_MATRIX.get(tool, {}).get(auth_mode, ())


def is_supported_runtime_combo(tool: str, auth_mode: str, provider: str) -> bool:
    return provider in supported_providers(tool, auth_mode)


def supported_runtime_summary_lines() -> list[str]:
    lines: list[str] = []
    for tool in ("claude", "codex", "gemini"):
        tool_map = SUPPORTED_RUNTIME_MATRIX.get(tool, {})
        for auth_mode in ("oauth", "api"):
            providers = tool_map.get(auth_mode)
            if not providers:
                continue
            provider_text = ", ".join(providers)
            lines.append(f"- `{tool}` + `{auth_mode}`: {provider_text}")
    return lines


def validate_runtime_combo(
    tool: str,
    auth_mode: str,
    provider: str,
    *,
    error_cls: type[Exception] = ValueError,
    context: str | None = None,
) -> None:
    if is_supported_runtime_combo(tool, auth_mode, provider):
        return
    provider_text = ", ".join(supported_providers(tool, auth_mode)) or "none"
    prefix = f"{context}: " if context else ""
    raise error_cls(
        f"{prefix}unsupported runtime combination `{tool}/{auth_mode}/{provider}`. "
        f"Supported providers for `{tool}/{auth_mode}`: {provider_text}."
    )
