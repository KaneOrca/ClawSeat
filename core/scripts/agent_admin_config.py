from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HOME = Path.home()
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
DEFAULT_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
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
    "codex": "/opt/homebrew/bin/codex",
    "claude": "/opt/homebrew/bin/claude",
    "gemini": "/opt/homebrew/bin/gemini",
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
