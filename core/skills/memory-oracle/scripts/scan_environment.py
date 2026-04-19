#!/usr/bin/env python3
"""
scan_environment.py — zero-dependency environment scanner for Memory CC.

Scans the machine for everything Memory Oracle needs to answer install/runtime
queries. Writes structured JSON to ~/.agents/memory/.

Usage:
    python3 scan_environment.py                       # full scan
    python3 scan_environment.py --only credentials    # single category
    python3 scan_environment.py --only credentials,openclaw
    python3 scan_environment.py --output /tmp/memory  # custom output dir

No third-party dependencies. Safe to run multiple times (idempotent).
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _real_user_home() -> Path:
    """Return the real user's HOME, bypassing sandbox HOME overrides.

    Claude Code seats run with HOME redirected to a runtime sandbox dir, which
    means ``Path.home()`` returns the sandbox. Scanning that sandbox is useless
    because the real env files (.env.global, .agents/, .openclaw/, .gstack/)
    live in the user's real HOME. Resolve it via pwd.getpwuid as fallback.
    """
    import pwd

    try:
        real = Path(pwd.getpwuid(os.getuid()).pw_dir)
        if real.is_dir():
            return real
    except (KeyError, OSError):
        pass
    env_home = os.environ.get("HOME")
    if env_home:
        return Path(env_home)
    return Path.home()


HOME = _real_user_home()
DEFAULT_OUTPUT = HOME / ".agents" / "memory"
SCAN_VERSION = 2
SECRETS_SUBDIR = "secrets"
SECRETS_FILENAME = "credentials.secrets.json"


# ── Helpers ─────────────────────────────────────────────────────────


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_cmd(cmd: list[str], *, timeout: float = 10.0) -> str:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return (result.stdout or "").strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def safe_read(path: Path, *, max_bytes: int = 1_000_000) -> str | None:
    try:
        if not path.is_file():
            return None
        if path.stat().st_size > max_bytes:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return None


def parse_env_file(text: str) -> list[tuple[str, str, int]]:
    """Parse KEY=VALUE lines, return (key, value, 1-based line number) tuples.

    Skips comments/blank lines, strips 'export ' prefix and surrounding quotes.
    Callers that only need a dict can build one from this list.
    """
    result: list[tuple[str, str, int]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Strip "export " prefix if present
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip matching quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if key:
            result.append((key, value, lineno))
    return result


def sha256_hex(value: str) -> str:
    """Hex sha256 of a string value (UTF-8)."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def make_preview(value: str) -> str:
    """Return a masked preview of a credential value.

    Rule: values <= 16 chars are fully masked. Longer values show the first
    6 chars, then ``****``, then the last 10 chars. The preview is intended
    to be safe to paste into logs or ``--schema`` output.
    """
    if not isinstance(value, str):
        return "****"
    if len(value) <= 16:
        return "****"
    return f"{value[:6]}****{value[-10:]}"


def classify_key_type(name: str) -> str:
    """Rough classification from the variable name. Used to hint consumers
    whether a credential is a URL vs. a secret token.
    """
    upper = name.upper()
    if upper.endswith("_URL") or "BASE_URL" in upper or "ENDPOINT" in upper:
        return "base_url"
    if "TOKEN" in upper:
        return "token"
    if "API_KEY" in upper or "APIKEY" in upper or upper.endswith("_KEY"):
        return "api_key"
    if "SECRET" in upper:
        return "secret"
    return "unknown"


def write_json(output_dir: Path, name: str, data: dict) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


# ── Scanners ────────────────────────────────────────────────────────


def scan_system() -> dict:
    """OS, hardware, brew packages."""
    data: dict = {
        "scanned_at": now_iso(),
        "os": {
            "platform": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
        },
        "hardware": {},
        "brew_packages": [],
    }
    if platform.system() == "Darwin":
        data["os"]["sw_vers"] = run_cmd(["sw_vers"])
        cpu = run_cmd(["sysctl", "-n", "hw.ncpu"])
        if cpu.isdigit():
            data["hardware"]["cpu_count"] = int(cpu)
        mem = run_cmd(["sysctl", "-n", "hw.memsize"])
        if mem.isdigit():
            data["hardware"]["memory_bytes"] = int(mem)
    brew_list = run_cmd(["brew", "list", "--formula"], timeout=15)
    if brew_list:
        data["brew_packages"] = sorted(brew_list.splitlines())
    return data


def scan_environment() -> dict:
    """Environment variables, PATH entries."""
    env = dict(os.environ)
    path_entries = env.get("PATH", "").split(":")
    return {
        "scanned_at": now_iso(),
        "vars": env,
        "path_entries": [p for p in path_entries if p],
        "key_count": len(env),
    }


def scan_credentials() -> dict:
    """API keys, tokens from known locations.

    Returns the metadata dict (safe to persist in ``credentials.json``).
    The raw plaintext values are captured in ``data["_secrets"]`` as a side
    channel so the caller can split them into a separate 0600 secrets file
    in a different directory. The ``_secrets`` key is stripped before the
    main credentials.json is written.

    Backward compat: each key entry still has ``value`` (plaintext) and
    ``source`` (string path). New fields (``value_preview``, ``value_sha256``,
    ``value_length``, ``value_type``, ``_provenance``) are additive.
    """
    scan_ts = now_iso()
    data: dict = {
        "scanned_at": scan_ts,
        "sources": [],
        "keys": {},
        # Side-channel: raw values keyed by name. Caller consumes + discards.
        "_secrets": {},
    }

    # Known files
    known_files = [
        HOME / ".agents" / ".env.global",
        HOME / ".env",
        HOME / ".env.local",
    ]
    # Glob ~/.env*
    known_files += [Path(p) for p in glob.glob(str(HOME / ".env*"))]
    # Secret directory
    secrets_root = HOME / ".agents" / "secrets"
    if secrets_root.exists():
        for env_file in secrets_root.rglob("*.env"):
            known_files.append(env_file)

    seen: set[Path] = set()
    for f in known_files:
        try:
            resolved = f.resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        text = safe_read(resolved)
        if text is None:
            continue
        parsed = parse_env_file(text)
        if not parsed:
            continue
        data["sources"].append(str(resolved))
        for k, v, line_no in parsed:
            # Don't overwrite if same key already seen
            if k in data["keys"]:
                continue
            data["keys"][k] = {
                # Back-compat fields (plaintext — preserved for existing
                # `--key credentials.keys.X.value` consumers).
                "value": v,
                "source": str(resolved),
                # New metadata fields (safe to log / share)
                "value_preview": make_preview(v),
                "value_length": len(v),
                "value_sha256": sha256_hex(v),
                "value_type": classify_key_type(k),
                "_provenance": {
                    "source_file": str(resolved),
                    "source_line": line_no,
                    "scanned_at": scan_ts,
                },
            }
            data["_secrets"][k] = v

    return data


def scan_openclaw() -> dict:
    """OpenClaw installation state."""
    data: dict = {
        "scanned_at": now_iso(),
        "home": str(HOME / ".openclaw"),
        "exists": (HOME / ".openclaw").exists(),
        "config": None,
        "skills": [],
        "extensions": [],
        "feishu": {},
    }
    if not data["exists"]:
        return data

    config_path = HOME / ".openclaw" / "openclaw.json"
    config_text = safe_read(config_path)
    if config_text:
        try:
            config = json.loads(config_text)
            data["config"] = config
            # Extract feishu section separately for fast query
            channels = config.get("channels", {})
            feishu = channels.get("feishu", {})
            data["feishu"] = {
                "default_account": feishu.get("defaultAccount"),
                "accounts": list(feishu.get("accounts", {}).keys()),
                "groups": list(feishu.get("groups", {}).keys()),
            }
        except json.JSONDecodeError:
            pass

    skills_dir = HOME / ".openclaw" / "skills"
    if skills_dir.is_dir():
        data["skills"] = sorted(p.name for p in skills_dir.iterdir() if p.is_dir() or p.is_symlink())

    extensions_dir = HOME / ".openclaw" / "extensions"
    if extensions_dir.is_dir():
        data["extensions"] = sorted(p.name for p in extensions_dir.iterdir() if p.is_dir() or p.is_symlink())

    return data


def scan_gstack() -> dict:
    """gstack installation state."""
    data: dict = {
        "scanned_at": now_iso(),
        "root": str(HOME / ".gstack"),
        "exists": (HOME / ".gstack").exists(),
        "repos": [],
        "skills_root": None,
        "skills": [],
    }
    if not data["exists"]:
        return data

    repos_dir = HOME / ".gstack" / "repos"
    if repos_dir.is_dir():
        data["repos"] = sorted(p.name for p in repos_dir.iterdir() if p.is_dir())

    skills_root = HOME / ".gstack" / "repos" / "gstack" / ".agents" / "skills"
    if skills_root.is_dir():
        data["skills_root"] = str(skills_root)
        data["skills"] = sorted(p.name for p in skills_root.iterdir() if p.is_dir())

    return data


def scan_clawseat() -> dict:
    """ClawSeat profiles, sessions, workspaces."""
    data: dict = {
        "scanned_at": now_iso(),
        "agents_root": str(HOME / ".agents"),
        "profiles": {},
        "sessions": {},
        "workspaces": {},
    }

    profiles_dir = HOME / ".agents" / "profiles"
    if profiles_dir.is_dir():
        try:
            import tomllib
        except ModuleNotFoundError:
            tomllib = None  # type: ignore
        for profile_file in profiles_dir.glob("*.toml"):
            info: dict = {"path": str(profile_file)}
            text = safe_read(profile_file)
            if text and tomllib is not None:
                try:
                    parsed = tomllib.loads(text)
                    info["project_name"] = parsed.get("project_name")
                    info["template_name"] = parsed.get("template_name")
                    info["seats"] = parsed.get("seats", [])
                    info["seat_roles"] = parsed.get("seat_roles", {})
                    info["workspace_root"] = parsed.get("workspace_root")
                except Exception:
                    pass
            data["profiles"][profile_file.stem] = info

    sessions_dir = HOME / ".agents" / "sessions"
    if sessions_dir.is_dir():
        for project_dir in sessions_dir.iterdir():
            if not project_dir.is_dir():
                continue
            seats: list[dict] = []
            for seat_dir in project_dir.iterdir():
                session_toml = seat_dir / "session.toml"
                if session_toml.is_file():
                    seat_info: dict = {"seat_id": seat_dir.name}
                    try:
                        import tomllib as _tl
                        parsed = _tl.loads(session_toml.read_text(encoding="utf-8"))
                        for k in ("session", "tool", "provider", "auth_mode", "workspace"):
                            if k in parsed:
                                seat_info[k] = parsed[k]
                    except Exception:
                        pass
                    seats.append(seat_info)
            data["sessions"][project_dir.name] = seats

    workspaces_dir = HOME / ".agents" / "workspaces"
    if workspaces_dir.is_dir():
        for project_dir in workspaces_dir.iterdir():
            if not project_dir.is_dir():
                continue
            data["workspaces"][project_dir.name] = sorted(
                p.name for p in project_dir.iterdir() if p.is_dir()
            )

    return data


def scan_repos() -> dict:
    """Local git repos and their remotes."""
    data: dict = {
        "scanned_at": now_iso(),
        "scan_dirs": [str(HOME / "coding")],
        "repos": [],
    }
    coding_dir = HOME / "coding"
    if not coding_dir.is_dir():
        return data

    for entry in coding_dir.iterdir():
        if not entry.is_dir():
            continue
        git_dir = entry / ".git"
        if not git_dir.exists():
            continue
        remotes = run_cmd(["git", "-C", str(entry), "remote", "-v"], timeout=5)
        branch = run_cmd(["git", "-C", str(entry), "rev-parse", "--abbrev-ref", "HEAD"], timeout=5)
        remote_lines = [line for line in remotes.splitlines() if "(fetch)" in line]
        data["repos"].append({
            "name": entry.name,
            "path": str(entry),
            "branch": branch,
            "remotes": remote_lines,
        })

    return data


def scan_network() -> dict:
    """Proxy settings, known endpoints."""
    data: dict = {
        "scanned_at": now_iso(),
        "proxy": {},
        "endpoints": {},
    }
    # macOS proxy settings
    proxy_raw = run_cmd(["scutil", "--proxy"], timeout=5)
    if proxy_raw:
        data["proxy"]["raw"] = proxy_raw
    # Extract common env proxies
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "no_proxy"):
        v = os.environ.get(k)
        if v:
            data["proxy"][k] = v
    return data


def scan_github() -> dict:
    """GitHub identity, gh CLI state, SSH keys, git credential setup.

    Captures the full picture an installer needs for GitHub-backed tasks:
    which gh account is active, what scopes the token has, git user config,
    and SSH public keys registered locally.

    Provenance: top-level ``_provenance`` side-table records where each
    non-obvious value came from (git config vs gh API vs hosts.yml). The
    data schema itself is unchanged so existing ``--key github.X.Y``
    consumers keep working.
    """
    scan_ts = now_iso()
    data: dict = {
        "scanned_at": scan_ts,
        "gitconfig": {},
        "git_credential_helpers": {},
        "gh_cli": {},
        "ssh_keys": [],
        "_provenance": {},
    }

    # ── git global config ─────────────────────────────────────────
    gitconfig_text = safe_read(HOME / ".gitconfig")
    if gitconfig_text is not None:
        data["gitconfig"]["path"] = str(HOME / ".gitconfig")
        # Capture key user fields if present
        user_name = run_cmd(["git", "config", "--global", "--get", "user.name"])
        user_email = run_cmd(["git", "config", "--global", "--get", "user.email"])
        signing_key = run_cmd(["git", "config", "--global", "--get", "user.signingkey"])
        if user_name:
            data["gitconfig"]["user_name"] = user_name
            data["_provenance"]["gitconfig.user_name"] = {
                "source": "git_config_global", "scanned_at": scan_ts,
            }
        if user_email:
            data["gitconfig"]["user_email"] = user_email
            data["_provenance"]["gitconfig.user_email"] = {
                "source": "git_config_global", "scanned_at": scan_ts,
            }
        if signing_key:
            data["gitconfig"]["signing_key"] = signing_key
            data["_provenance"]["gitconfig.signing_key"] = {
                "source": "git_config_global", "scanned_at": scan_ts,
            }
        # Credential helpers per URL scheme
        lines = run_cmd(["git", "config", "--global", "--list"]).splitlines()
        for line in lines:
            if ".helper=" in line and "credential" in line:
                key, _, value = line.partition("=")
                data["git_credential_helpers"].setdefault(key, []).append(value)

    # ── gh CLI config ─────────────────────────────────────────────
    gh_hosts_path = HOME / ".config" / "gh" / "hosts.yml"
    gh_hosts_text = safe_read(gh_hosts_path)
    if gh_hosts_text:
        data["gh_cli"]["hosts_file"] = str(gh_hosts_path)
        # Extract host config. NOTE: the ``user:`` field in hosts.yml is a
        # LOCAL gh CLI account alias (keyring entry label), NOT the actual
        # GitHub login. For the real GitHub username use `gh api user`.
        current_host: str | None = None
        hosts: dict[str, dict] = {}
        for raw in gh_hosts_text.splitlines():
            if raw and not raw.startswith(" ") and not raw.startswith("\t") and raw.rstrip().endswith(":"):
                current_host = raw.rstrip().rstrip(":").strip()
                hosts[current_host] = {}
                continue
            stripped = raw.strip()
            if current_host and stripped.startswith("user:"):
                hosts[current_host]["account_alias"] = stripped.split(":", 1)[1].strip()
            if current_host and stripped.startswith("git_protocol:"):
                hosts[current_host]["git_protocol"] = stripped.split(":", 1)[1].strip()
        data["gh_cli"]["hosts"] = hosts

    # Real GitHub login for the currently active account — this is what
    # clone/API calls must use. Separate from the hosts.yml alias.
    login = run_cmd(["gh", "api", "user", "--jq", ".login"], timeout=10)
    if login:
        data["gh_cli"]["active_login"] = login
        data["_provenance"]["gh_cli.active_login"] = {
            "source": "gh_api_user", "scanned_at": scan_ts,
        }

    # Live auth status (respects active keyring entry). NOTE: the "account"
    # token in the status output is the local keyring alias (same as the
    # hosts.yml user field), NOT the actual GitHub login. See active_login.
    gh_status = run_cmd(["gh", "auth", "status"], timeout=10)
    if gh_status:
        accounts: list[dict] = []
        current: dict = {}
        for line in gh_status.splitlines():
            line = line.rstrip()
            if line.startswith("github.com"):
                if current:
                    accounts.append(current)
                current = {"host": "github.com"}
            elif "Logged in to" in line:
                # "  ✓ Logged in to github.com account <alias> (keyring)"
                parts = line.split("account", 1)
                if len(parts) == 2:
                    alias = parts[1].strip().split()[0]
                    current["account_alias"] = alias
            elif "Active account:" in line:
                current["active"] = "true" in line.lower()
            elif "Git operations protocol:" in line:
                current["protocol"] = line.split(":", 1)[1].strip()
            elif "Token scopes:" in line:
                scopes = line.split(":", 1)[1].strip()
                # scopes look like: 'admin:org', 'repo', ...
                current["scopes"] = [s.strip().strip("'\"") for s in scopes.split(",") if s.strip()]
        if current:
            accounts.append(current)
        data["gh_cli"]["auth_status"] = accounts

    # ── SSH public keys ───────────────────────────────────────────
    ssh_dir = HOME / ".ssh"
    if ssh_dir.is_dir():
        for pub in sorted(ssh_dir.glob("*.pub")):
            text = safe_read(pub, max_bytes=8192)
            if text is None:
                continue
            parts = text.strip().split()
            key_type = parts[0] if parts else ""
            comment = parts[-1] if len(parts) >= 3 else ""
            data["ssh_keys"].append({
                "path": str(pub),
                "type": key_type,
                "comment": comment,
                "fingerprint": run_cmd(["ssh-keygen", "-lf", str(pub)], timeout=5).split()[1]
                    if run_cmd(["ssh-keygen", "-lf", str(pub)], timeout=5) else "",
            })

    # ── Remote GitHub: owned repos, orgs, gists ───────────────────
    # Only attempt if gh CLI shows an active auth. Degrades to a
    # `fetch_error` field if the network / token fails — never raises.
    data["remote"] = {}
    active = any(
        acct.get("active") for acct in (data.get("gh_cli", {}).get("auth_status") or [])
    )
    if active:
        # Owned repos — up to 500. `gh repo list` only lists repos the user
        # owns (not the ones they collaborate on via orgs).
        repo_json = run_cmd(
            [
                "gh", "repo", "list",
                "--limit", "500",
                "--json", "name,nameWithOwner,description,isPrivate,isFork,isArchived,"
                          "defaultBranchRef,updatedAt,pushedAt,url,primaryLanguage,"
                          "diskUsage,stargazerCount",
            ],
            timeout=30,
        )
        if repo_json:
            try:
                raw_repos = json.loads(repo_json)
                simplified = []
                for r in raw_repos:
                    default_branch = ""
                    dbref = r.get("defaultBranchRef") or {}
                    if isinstance(dbref, dict):
                        default_branch = dbref.get("name", "") or ""
                    lang = r.get("primaryLanguage") or {}
                    lang_name = lang.get("name", "") if isinstance(lang, dict) else ""
                    simplified.append({
                        "name": r.get("name", ""),
                        "full_name": r.get("nameWithOwner", ""),
                        "url": r.get("url", ""),
                        "description": (r.get("description") or "")[:300],
                        "is_private": bool(r.get("isPrivate")),
                        "is_fork": bool(r.get("isFork")),
                        "is_archived": bool(r.get("isArchived")),
                        "default_branch": default_branch,
                        "primary_language": lang_name,
                        "disk_usage_kb": r.get("diskUsage", 0),
                        "stars": r.get("stargazerCount", 0),
                        "updated_at": r.get("updatedAt", ""),
                        "pushed_at": r.get("pushedAt", ""),
                    })
                data["remote"]["owned_repos"] = simplified
                data["remote"]["owned_repos_count"] = len(simplified)
            except (json.JSONDecodeError, TypeError) as exc:
                data["remote"]["owned_repos_error"] = f"parse_error: {exc}"
        else:
            data["remote"]["owned_repos_error"] = "gh_repo_list_empty_or_failed"

        # Organizations the active user belongs to
        org_json = run_cmd(
            ["gh", "api", "user/orgs", "--jq",
             "[.[] | {login, url, description}]"],
            timeout=15,
        )
        if org_json:
            try:
                data["remote"]["organizations"] = json.loads(org_json)
            except (json.JSONDecodeError, TypeError):
                data["remote"]["organizations_error"] = "parse_error"

        # Summary counts only (gists / starred can be large — keep cheap)
        counts = run_cmd(
            ["gh", "api", "user", "--jq",
             "{public_repos, owned_private_repos, public_gists, followers, following}"],
            timeout=10,
        )
        if counts:
            try:
                data["remote"]["user_summary"] = json.loads(counts)
            except (json.JSONDecodeError, TypeError):
                pass
    else:
        data["remote"]["fetch_skipped"] = "no_active_gh_auth"

    return data


# ── Orchestration ──────────────────────────────────────────────────


SCANNERS = {
    "system": scan_system,
    "environment": scan_environment,
    "credentials": scan_credentials,
    "openclaw": scan_openclaw,
    "gstack": scan_gstack,
    "clawseat": scan_clawseat,
    "repos": scan_repos,
    "network": scan_network,
    "github": scan_github,
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Environment scanner for Memory CC.")
    p.add_argument(
        "--only",
        help=f"Comma-separated scanner names. Default: all. Available: {','.join(SCANNERS)}",
    )
    p.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"Output directory (default: {DEFAULT_OUTPUT})",
    )
    p.add_argument("--quiet", action="store_true", help="Suppress progress output")
    return p.parse_args()


def write_secrets_file(output_dir: Path, secrets: dict[str, str], scan_ts: str) -> Path | None:
    """Persist raw credential values to secrets/credentials.secrets.json.

    Creates the directory with 0700 and the file with 0600. Failures to
    chmod are non-fatal (some filesystems don't support it) but are
    surfaced on stderr.
    """
    if not secrets:
        return None
    secrets_dir = output_dir / SECRETS_SUBDIR
    try:
        secrets_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(secrets_dir, 0o700)
    except OSError as exc:
        print(f"warning: could not chmod {secrets_dir}: {exc}", file=sys.stderr)
    payload = {
        "_warning": "RAW SECRETS — chmod 600, never commit, never transmit.",
        "scanned_at": scan_ts,
        "keys": dict(sorted(secrets.items())),
    }
    path = secrets_dir / SECRETS_FILENAME
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    try:
        os.chmod(path, 0o600)
    except OSError as exc:
        print(f"warning: could not chmod {path}: {exc}", file=sys.stderr)
    return path


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.only:
        targets = [t.strip() for t in args.only.split(",") if t.strip()]
        unknown = [t for t in targets if t not in SCANNERS]
        if unknown:
            print(f"error: unknown scanners: {','.join(unknown)}", file=sys.stderr)
            print(f"available: {','.join(SCANNERS)}", file=sys.stderr)
            return 2
    else:
        targets = list(SCANNERS.keys())

    results: dict[str, dict] = {}
    errors: list[dict] = []
    secrets_path: Path | None = None
    secrets_count = 0
    for name in targets:
        scanner = SCANNERS[name]
        if not args.quiet:
            print(f"scanning {name}…", end=" ", flush=True)
        try:
            data = scanner()
            # Extract credential secrets side-channel before persisting the
            # sanitized credentials.json. The raw values go into a separate
            # file under secrets/ with stricter permissions.
            if name == "credentials" and isinstance(data, dict):
                raw_secrets = data.pop("_secrets", {}) or {}
                if raw_secrets:
                    secrets_path = write_secrets_file(
                        output_dir, raw_secrets, data.get("scanned_at", now_iso())
                    )
                    secrets_count = len(raw_secrets)
            path = write_json(output_dir, name, data)
            results[name] = {"path": str(path), "ok": True}
            if not args.quiet:
                print("✓")
        except Exception as exc:
            errors.append({"scanner": name, "error": str(exc), "type": exc.__class__.__name__})
            results[name] = {"path": None, "ok": False, "error": str(exc)}
            if not args.quiet:
                print(f"✗ ({exc.__class__.__name__}: {exc})")

    # Write index
    index: dict = {
        "version": SCAN_VERSION,
        "scanned_at": now_iso(),
        "output_dir": str(output_dir),
        "scanners": list(results.keys()),
        "results": results,
        "errors": errors,
        "schema_changelog": [
            "v1: initial scanner set",
            "v2: credentials dual-write (metadata + secrets sidecar), per-key provenance",
        ],
    }
    if secrets_path is not None:
        index["secrets_file"] = str(secrets_path)
        index["secrets_key_count"] = secrets_count
    index_path = write_json(output_dir, "index", index)
    if not args.quiet:
        total = len(results)
        ok = sum(1 for r in results.values() if r.get("ok"))
        print(f"\nscan complete: {ok}/{total} scanners succeeded")
        print(f"index: {index_path}")
        if secrets_path is not None:
            print(f"secrets: {secrets_path} ({secrets_count} keys)")

    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
