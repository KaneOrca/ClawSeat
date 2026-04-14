from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Any


HOME = Path.home()
REPO_ROOT = Path(os.environ.get("CODE_REPO_ROOT", str(HOME / "coding"))).expanduser()
DEFAULT_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
RUNTIME_ROOT = HOME / ".agents" / "runtime" / "identities"
SECRETS_ROOT = HOME / ".agents" / "secrets"


def q(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def ensure_secret_permissions(path: Path) -> None:
    if path.exists():
        path.chmod(0o600)


def detect_macos_system_proxies() -> dict[str, str]:
    try:
        proc = subprocess.run(
            ["scutil", "--proxy"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return {}

    values: dict[str, str] = {}
    for raw_line in proc.stdout.splitlines():
        line = raw_line.strip()
        if " : " not in line:
            continue
        key, value = line.split(" : ", 1)
        values[key.strip()] = value.strip()

    http_proxy = ""
    https_proxy = ""
    all_proxy = ""

    if values.get("HTTPEnable") == "1" and values.get("HTTPProxy") and values.get("HTTPPort"):
        http_proxy = f"http://{values['HTTPProxy']}:{values['HTTPPort']}"
    if values.get("HTTPSEnable") == "1" and values.get("HTTPSProxy") and values.get("HTTPSPort"):
        https_proxy = f"http://{values['HTTPSProxy']}:{values['HTTPSPort']}"
    if values.get("SOCKSEnable") == "1" and values.get("SOCKSProxy") and values.get("SOCKSPort"):
        all_proxy = f"socks5://{values['SOCKSProxy']}:{values['SOCKSPort']}"
    if not any((http_proxy, https_proxy, all_proxy)):
        return {}
    return {
        "http_proxy": http_proxy,
        "https_proxy": https_proxy,
        "HTTP_PROXY": http_proxy,
        "HTTPS_PROXY": https_proxy,
        "ALL_PROXY": all_proxy,
        "NO_PROXY": "localhost,127.0.0.1,::1,.local",
    }


def parse_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        env[key.strip()] = shlex.split(value.strip(), posix=True)[0] if value.strip() else ""
    return env


def write_env_file(path: Path, values: dict[str, str], ensure_dir_fn: Any, write_text_fn: Any) -> None:
    ensure_dir_fn(path.parent)
    lines = [f"{key}={shlex.quote(value)}" for key, value in sorted(values.items())]
    write_text_fn(path, "\n".join(lines) + ("\n" if lines else ""), mode=0o600)


def ensure_empty_env_file(path: Path, ensure_dir_fn: Any, write_text_fn: Any) -> None:
    if path.exists():
        return
    write_env_file(path, {}, ensure_dir_fn, write_text_fn)


def write_codex_api_config(
    session: Any,
    codex_home: Path,
    project_repo: Path,
    provider_configs: dict[str, dict[str, Any]],
    write_text_fn: Any,
) -> None:
    provider = provider_configs.get(session.provider)
    if not provider:
        raise ValueError(f"Unsupported Codex API provider: {session.provider}")

    trust_paths = [str(HOME), str(REPO_ROOT)]
    for path in (project_repo, project_repo / "cartooner", project_repo / "openclaw"):
        if path.exists():
            trust_paths.append(str(path))

    lines = [
        f'model_provider = {q(provider["model_provider"])}',
        f'model = {q(provider["model"])}',
    ]
    if provider.get("model_reasoning_effort"):
        lines.append(f'model_reasoning_effort = {q(provider["model_reasoning_effort"])}')
    if "disable_response_storage" in provider:
        lines.append(
            f'disable_response_storage = {"true" if provider["disable_response_storage"] else "false"}'
        )
    if provider.get("preferred_auth_method"):
        lines.append(f'preferred_auth_method = {q(provider["preferred_auth_method"])}')
    if provider.get("personality"):
        lines.append(f'personality = {q(provider["personality"])}')
    lines.extend(
        [
            "",
            f'[model_providers.{provider["model_provider"]}]',
            f'name = {q(provider.get("name", provider["model_provider"]))}',
            f'base_url = {q(provider["base_url"])}',
            f'wire_api = {q(provider["wire_api"])}',
        ]
    )
    if provider.get("env_key"):
        lines.append(f'env_key = {q(provider["env_key"])}')
    if "requires_openai_auth" in provider:
        lines.append(
            f'requires_openai_auth = {"true" if provider["requires_openai_auth"] else "false"}'
        )
    for numeric_key in ("request_max_retries", "stream_max_retries", "stream_idle_timeout_ms"):
        if numeric_key in provider:
            lines.append(f"{numeric_key} = {int(provider[numeric_key])}")
    lines.append("")
    if provider.get("profile_name"):
        lines.extend(
            [
                f'[profiles.{provider["profile_name"]}]',
                f'model_provider = {q(provider["model_provider"])}',
                f'model = {q(provider["model"])}',
                "",
            ]
        )
    for path in trust_paths:
        lines.extend(
            [
                f'[projects.{q(path)}]',
                'trust_level = "trusted"',
                "",
            ]
        )
    lines.extend(
        [
            "[notice]",
            'hide_full_access_warning = true',
            "",
        ]
    )
    write_text_fn(codex_home / "config.toml", "\n".join(lines))


def common_env() -> dict[str, str]:
    host = os.environ
    term = host.get("TERM", "")
    if not term or term == "dumb":
        term = "xterm-256color"
    env = {
        "PATH": host.get("PATH", DEFAULT_PATH),
        "USER": host.get("USER", os.popen("id -un").read().strip() or "ywf"),
        "SHELL": host.get("SHELL", "/bin/zsh"),
        "TERM": term,
        "LANG": host.get("LANG", "en_US.UTF-8"),
        "LC_ALL": host.get("LC_ALL", "en_US.UTF-8"),
        "TMPDIR": host.get("TMPDIR", "/tmp"),
        "SSH_AUTH_SOCK": host.get("SSH_AUTH_SOCK", ""),
        "http_proxy": host.get("http_proxy", ""),
        "https_proxy": host.get("https_proxy", ""),
        "HTTP_PROXY": host.get("HTTP_PROXY", ""),
        "HTTPS_PROXY": host.get("HTTPS_PROXY", ""),
        "ALL_PROXY": host.get("ALL_PROXY", ""),
        "NO_PROXY": host.get("NO_PROXY", ""),
    }
    if not any(env[key] for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")):
        env.update(detect_macos_system_proxies())
    return env


def identity_name(
    tool: str,
    mode: str,
    provider: str,
    engineer_id: str,
    project_name: str | None = None,
) -> str:
    parts = [tool, mode, provider]
    if project_name:
        parts.append(project_name)
    parts.append(engineer_id)
    return ".".join(parts)


def runtime_dir_for_identity(tool: str, mode: str, identity: str) -> Path:
    return RUNTIME_ROOT / tool / mode / identity


def secret_file_for(tool: str, provider: str, engineer_id: str) -> Path:
    return SECRETS_ROOT / tool / provider / f"{engineer_id}.env"


def session_name_for(project: str, engineer_id: str, tool: str) -> str:
    return f"{project}-{engineer_id}-{tool}"
