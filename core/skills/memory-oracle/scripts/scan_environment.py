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
SCAN_VERSION = 1

# Scanner outputs go into machine/ subdirectory (SPEC §3 target layout)
MACHINE_SUBDIR = "machine"


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


def parse_env_file(text: str) -> dict[str, str]:
    """Parse KEY=VALUE lines, skipping comments. Strips surrounding quotes."""
    result: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
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
            result[key] = value
    return result


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
    """API keys, tokens from known locations. Plaintext, local-only."""
    data: dict = {
        "scanned_at": now_iso(),
        "sources": [],
        "keys": {},
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
        for k, v in parsed.items():
            # Don't overwrite if same key already seen
            if k not in data["keys"]:
                data["keys"][k] = {"value": v, "source": str(resolved)}

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
    """
    data: dict = {
        "scanned_at": now_iso(),
        "gitconfig": {},
        "git_credential_helpers": {},
        "gh_cli": {},
        "ssh_keys": [],
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
        if user_email:
            data["gitconfig"]["user_email"] = user_email
        if signing_key:
            data["gitconfig"]["signing_key"] = signing_key
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


def scan_current_context() -> dict:
    """Write the current project pointer and last refresh timestamp.

    Reads CLAWSEAT_PROJECT / AGENTS_PROJECT / CLAWSEAT_WORKSPACE_ROOT from the
    environment so the memory seat knows which project is active right now.
    Written to machine/current_context.json on every full scan.
    """
    last_refresh_ts = now_iso()
    data: dict = {
        "scanned_at": last_refresh_ts,
        "last_refresh_ts": last_refresh_ts,
        "current_project": None,
        "current_project_dir": None,
    }

    # Prefer the explicit project env var set by ClawSeat launch scripts
    project = os.environ.get("CLAWSEAT_PROJECT") or os.environ.get("AGENTS_PROJECT")
    if project:
        data["current_project"] = project

    workspace_root = os.environ.get("CLAWSEAT_WORKSPACE_ROOT")
    if workspace_root:
        data["current_project_dir"] = workspace_root

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
    "current_context": scan_current_context,
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


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output).expanduser().resolve()
    # Scanner outputs go into machine/ subdirectory (SPEC §3 target layout)
    machine_dir = output_dir / MACHINE_SUBDIR
    machine_dir.mkdir(parents=True, exist_ok=True)

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
    for name in targets:
        scanner = SCANNERS[name]
        if not args.quiet:
            print(f"scanning {name}…", end=" ", flush=True)
        try:
            data = scanner()
            path = write_json(machine_dir, name, data)
            results[name] = {"path": str(path), "ok": True}
            if not args.quiet:
                print("✓")
        except Exception as exc:
            errors.append({"scanner": name, "error": str(exc), "type": exc.__class__.__name__})
            results[name] = {"path": None, "ok": False, "error": str(exc)}
            if not args.quiet:
                print(f"✗ ({exc.__class__.__name__}: {exc})")

    # Write index at output_dir root (not inside machine/)
    index = {
        "version": SCAN_VERSION,
        "scanned_at": now_iso(),
        "output_dir": str(output_dir),
        "machine_dir": str(machine_dir),
        "scanners": list(results.keys()),
        "results": results,
        "errors": errors,
    }
    index_path = write_json(output_dir, "index", index)
    if not args.quiet:
        total = len(results)
        ok = sum(1 for r in results.values() if r.get("ok"))
        print(f"\nscan complete: {ok}/{total} scanners succeeded")
        print(f"index: {index_path}")
        machine_files = sorted(p.name for p in machine_dir.iterdir() if p.is_file())
        print(f"machine/ files: {machine_files}")

    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
