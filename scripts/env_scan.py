#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


def real_home() -> Path:
    try:
        import pwd

        home = Path(pwd.getpwuid(os.getuid()).pw_dir)
        if home.is_dir():
            return home
    except Exception:
        pass
    return Path(os.environ.get("HOME", str(Path.home()))).expanduser()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def scan() -> dict:
    home = real_home()
    claude_dir = home / ".claude"
    claude_files = sorted(p.name for p in claude_dir.glob("*")) if claude_dir.is_dir() else []
    env = os.environ
    auth_methods: list[dict[str, object]] = []

    if (claude_dir / ".credentials.json").is_file() or any("cred" in name or "token" in name for name in claude_files):
        auth_methods.append({
            "tool": "claude",
            "auth_mode": "oauth",
            "provider": "anthropic",
            "source": str(claude_dir),
        })
    if env.get("ANTHROPIC_API_KEY"):
        auth_methods.append({
            "tool": "claude",
            "auth_mode": "api",
            "provider": "anthropic",
            "source": "ANTHROPIC_API_KEY",
        })
    if env.get("MINIMAX_API_KEY"):
        auth_methods.append({
            "tool": "claude",
            "auth_mode": "api",
            "provider": "minimax",
            "source": "MINIMAX_API_KEY",
        })
    if env.get("ANTHROPIC_AUTH_TOKEN"):
        auth_methods.append({
            "tool": "claude",
            "auth_mode": "oauth",
            "provider": "anthropic",
            "source": "ANTHROPIC_AUTH_TOKEN",
        })

    base_url = env.get("ANTHROPIC_BASE_URL", "").strip()
    local_model = any(
        str(env.get(name, "")).startswith(("http://localhost", "http://127.0.0.1"))
        for name in ("ANTHROPIC_BASE_URL", "OPENAI_BASE_URL", "OLLAMA_HOST")
    )
    return {
        "scanned_at": now_iso(),
        "home": str(home),
        "claude": {
            "dir": str(claude_dir),
            "files": claude_files,
            "has_credentials_json": (claude_dir / ".credentials.json").is_file(),
        },
        "env": {
            "ANTHROPIC_API_KEY": bool(env.get("ANTHROPIC_API_KEY")),
            "ANTHROPIC_AUTH_TOKEN": bool(env.get("ANTHROPIC_AUTH_TOKEN")),
            "ANTHROPIC_BASE_URL": base_url or None,
            "MINIMAX_API_KEY": bool(env.get("MINIMAX_API_KEY")),
        },
        "providers": {
            "minimax": bool(env.get("MINIMAX_API_KEY")),
            "anthropic_proxy": bool(base_url and "api.anthropic.com" not in base_url),
            "local_model": local_model,
        },
        "runtimes": {name: shutil.which(name) for name in ("claude", "codex", "gemini")},
        "auth_methods": auth_methods,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Scan local auth evidence and runtime binaries.")
    ap.add_argument("--output", type=Path, default=None, help="write JSON to this path instead of stdout")
    args = ap.parse_args()
    data = scan()
    blob = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(blob, encoding="utf-8")
        print(args.output)
        return 0
    print(blob, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
