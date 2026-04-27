#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def registry_path() -> Path:
    return Path.home() / ".clawseat" / "projects.json"


def _empty_registry() -> dict[str, Any]:
    return {"version": 1, "projects": []}


def load_registry() -> dict[str, Any]:
    path = registry_path()
    if not path.exists():
        return _empty_registry()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty_registry()
    if not isinstance(data, dict):
        return _empty_registry()
    projects = data.get("projects")
    if not isinstance(projects, list):
        return _empty_registry()
    return {"version": data.get("version", 1), "projects": projects}


def _project_name(entry: Any) -> str | None:
    if not isinstance(entry, dict):
        return None
    name = entry.get("name")
    if isinstance(name, str) and name:
        return name
    return None


def _normalized_entry(entry: Any) -> dict[str, str] | None:
    name = _project_name(entry)
    if name is None or not isinstance(entry, dict):
        return None
    primary_seat = entry.get("primary_seat")
    if not isinstance(primary_seat, str) or not primary_seat:
        primary_seat = "memory"
    tmux_name = entry.get("tmux_name")
    if not isinstance(tmux_name, str) or not tmux_name:
        tmux_name = f"{name}-{primary_seat}"
    registered_at = entry.get("registered_at")
    if not isinstance(registered_at, str):
        registered_at = ""
    return {
        "name": name,
        "primary_seat": primary_seat,
        "tmux_name": tmux_name,
        "registered_at": registered_at,
    }


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def register_project(name: str, primary_seat: str, *, tmux_name: str | None = None) -> bool:
    data = load_registry()
    projects = data["projects"]
    existing = {_project_name(entry) for entry in projects}
    if name in existing:
        return False

    entry = {
        "name": name,
        "primary_seat": primary_seat,
        "tmux_name": tmux_name or f"{name}-{primary_seat}",
        "registered_at": _utc_timestamp(),
    }
    projects.append(entry)
    _atomic_write(data)
    return True


def unregister_project(name: str) -> bool:
    data = load_registry()
    projects = data["projects"]
    filtered = [entry for entry in projects if _project_name(entry) != name]
    if len(filtered) == len(projects):
        return False
    data["projects"] = filtered
    _atomic_write(data)
    return True


def enumerate_projects() -> list[dict[str, str]]:
    return [
        normalized
        for entry in load_registry()["projects"]
        if (normalized := _normalized_entry(entry)) is not None
    ]


def _atomic_write(data: dict[str, Any]) -> None:
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()

    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    opener = lambda file, flags: os.open(file, flags, 0o600)
    with open(tmp, "w", encoding="utf-8", opener=opener) as handle:
        handle.write(payload)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage ClawSeat active-project registry.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    register = subparsers.add_parser("register")
    register.add_argument("name")
    register.add_argument("primary_seat")
    register.add_argument("tmux_name", nargs="?")

    unregister = subparsers.add_parser("unregister")
    unregister.add_argument("name")

    subparsers.add_parser("list")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "register":
        created = register_project(args.name, args.primary_seat, tmux_name=args.tmux_name)
        print(("registered" if created else "exists") + f" {args.name}")
        return 0
    if args.command == "unregister":
        removed = unregister_project(args.name)
        print(("unregistered" if removed else "missing") + f" {args.name}")
        return 0
    if args.command == "list":
        print(json.dumps(enumerate_projects(), ensure_ascii=False))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
