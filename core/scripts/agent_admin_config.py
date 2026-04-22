from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any


_TOOL_BIN_SOURCES: dict[str, str] = {}


# ── Sandbox HOME resolution ───────────────────────────────────────────────────
#
# Claude Code seats run inside a sandbox HOME at
#   ~/.agents/runtime/identities/<tool>/<auth>/<identity>/home/
# so Path.home() inside a seat returns THAT, not the operator's real HOME.
# All agent_admin path resolution must use the effective home to avoid
# pointing at sandbox-local artifacts that don't exist there.
#
# Canonical implementation lives in core/lib/real_home.py; this module
# re-exports the helpers (with their historical underscore-prefix names)
# so existing agent_admin_* callers keep working.

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CORE_LIB = str(_REPO_ROOT / "core" / "lib")
if _CORE_LIB not in sys.path:
    sys.path.insert(0, _CORE_LIB)
from real_home import (  # noqa: E402
    is_sandbox_home as _is_sandbox_home,
    real_user_home as _real_user_home,
)


def _resolve_effective_home() -> Path:
    """Return the effective HOME for agent_admin path resolution.

    Respects CLAWSEAT_SANDBOX_HOME_STRICT=1 (force sandbox, for tests)
    and delegates to _real_user_home() otherwise.
    """
    return _real_user_home()


def _resolve_tool_bin(name: str) -> str:
    """Resolve a backend CLI binary path.

    Probe order: PATH (via shutil.which) → /opt/homebrew/bin → bare name.
    The "bare" fallback means `shell exec` will rely on the caller's PATH
    at runtime; if the CLI is not installed, execution fails with a
    cryptic "command not found" instead of a clear preflight error.
    `unresolved_tool_bins()` exposes that state so startup code
    (preflight, agent_admin main) can surface a visible warning.
    """
    resolved = shutil.which(name)
    if resolved:
        _TOOL_BIN_SOURCES[name] = "path"
        return resolved
    homebrew = f"/opt/homebrew/bin/{name}"
    if os.path.exists(homebrew):
        _TOOL_BIN_SOURCES[name] = "homebrew"
        return homebrew
    _TOOL_BIN_SOURCES[name] = "bare"
    return name


def tool_bin_source(name: str) -> str:
    """Return how TOOL_BINARIES[name] was resolved: path | homebrew | bare.
    Empty string if the name was never probed."""
    return _TOOL_BIN_SOURCES.get(name, "")


def unresolved_tool_bins() -> list[str]:
    """List of tools whose binary fell back to the bare name (i.e. could
    not be located on disk at import time). These will fail at exec time
    unless the user's PATH picks them up."""
    return sorted(name for name, src in _TOOL_BIN_SOURCES.items() if src == "bare")


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
    "ark": {
        "model": "ark-code-latest",
        "base_url": "https://ark.cn-beijing.volces.com/api/coding",
        # ARK exposes an Anthropic-compatible Claude Code endpoint but
        # operators already store the upstream secret as ARK_API_KEY in
        # ~/.agent-runtime/secrets/claude/ark.env. Session startup aliases
        # that name into launcher custom env at runtime.
        "auth_token_var": "ARK_API_KEY",
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

# Gemini has no non-Google API providers today; the matrix exposes
# `api/google-api-key` which is handled via plain env-var injection (no
# config.toml rendering). This dict is kept empty to preserve structural
# symmetry with CLAUDE_/CODEX_API_PROVIDER_CONFIGS and to provide a
# documented place for future providers (e.g. google-vertex). Adding an
# entry here must be paired with an update to SUPPORTED_RUNTIME_MATRIX
# and any renderer that consumes it.
GEMINI_API_PROVIDER_CONFIGS: dict[str, dict[str, object]] = {}


# ── Codex provider schema ───────────────────────────────────────────
#
# `write_codex_api_config` used to render a raw dict into TOML. A typo in
# the dict (e.g. `disable_response_storge`) was silently dropped and the
# codex CLI started without it, which produced confusing runtime
# failures. The dataclass below pins the accepted field set; any unknown
# key raises at load time via `parse_codex_provider_config`. Renderers
# must read from the dataclass, never from a raw dict.

@dataclass(frozen=True)
class CodexProviderConfig:
    model_provider: str
    model: str
    base_url: str
    wire_api: str
    model_reasoning_effort: str | None = None
    disable_response_storage: bool | None = None
    preferred_auth_method: str | None = None
    personality: str | None = None
    name: str | None = None
    env_key: str | None = None
    requires_openai_auth: bool | None = None
    request_max_retries: int | None = None
    stream_max_retries: int | None = None
    stream_idle_timeout_ms: int | None = None
    profile_name: str | None = None


def parse_codex_provider_config(data: dict[str, Any]) -> CodexProviderConfig:
    """Convert a raw dict entry from CODEX_API_PROVIDER_CONFIGS to the
    strongly-typed dataclass. Unknown keys raise ValueError instead of
    being silently dropped — the original reason this function exists
    (audit M1 — see docs/audit-log)."""
    allowed = {field.name for field in fields(CodexProviderConfig)}
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(
            f"unknown codex provider config key(s): {sorted(unknown)}; "
            f"allowed: {sorted(allowed)}"
        )
    return CodexProviderConfig(**data)


SUPPORTED_RUNTIME_MATRIX = {
    "claude": {
        "oauth": ("anthropic",),
        "api": ("xcode-best", "minimax", "ark", "anthropic-console"),
        # C5: long-lived token from `claude setup-token` (valid ~1 year).
        # Skips macOS Keychain entirely — avoids the per-seat popup storm
        # caused by each seat having a different HOME (upstream
        # anthropics/claude-code#43000).
        "oauth_token": ("anthropic",),
        # C5: Claude Code Router (CCR) — local proxy that multiplexes
        # Anthropic-compatible providers (Kimi / MiniMax / GLM / DeepSeek
        # / OpenRouter) behind one ANTHROPIC_BASE_URL. Keeps backend
        # seats off the user's OAuth quota and switchable per-request.
        "ccr": ("ccr-local",),
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


# C5 auth mode families. Used by validators and by build_runtime to decide
# which env-injection branch runs. Keeping this explicit makes it easy to
# answer "does this auth mode need a secret file?" without reading the
# matrix carefully.
AUTH_MODES_REQUIRING_SECRET_FILE = frozenset({"api", "oauth_token"})
AUTH_MODES_WITHOUT_SECRET_FILE = frozenset({"oauth", "ccr"})
ALL_AUTH_MODES = AUTH_MODES_REQUIRING_SECRET_FILE | AUTH_MODES_WITHOUT_SECRET_FILE


# Default endpoint for the local CCR proxy (override with CLAWSEAT_CCR_BASE_URL).
DEFAULT_CCR_BASE_URL = "http://127.0.0.1:3456"


def supported_providers(tool: str, auth_mode: str) -> tuple[str, ...]:
    return SUPPORTED_RUNTIME_MATRIX.get(tool, {}).get(auth_mode, ())


def is_supported_runtime_combo(tool: str, auth_mode: str, provider: str) -> bool:
    return provider in supported_providers(tool, auth_mode)


def supported_runtime_summary_lines() -> list[str]:
    lines: list[str] = []
    for tool in ("claude", "codex", "gemini"):
        tool_map = SUPPORTED_RUNTIME_MATRIX.get(tool, {})
        for auth_mode in ("oauth", "api", "oauth_token", "ccr"):
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
