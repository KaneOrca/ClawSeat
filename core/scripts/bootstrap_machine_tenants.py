#!/usr/bin/env python3
"""Bootstrap ~/.clawseat/machine.toml tenants from memory scan output.

Called after memory has produced machine/openclaw.json. Idempotent: existing
tenants are preserved, and only new tenants with existing workspaces are added.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_REPO_ROOT), str(_REPO_ROOT / "core" / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.lib.machine_config import OpenClawTenant, load_machine, write_machine


def bootstrap_machine_tenants(memory_root: Path) -> int:
    oc_json = memory_root / "machine" / "openclaw.json"
    if not oc_json.exists():
        print(f"ERR_NO_SCAN: {oc_json} not found", file=sys.stderr)
        return 2

    try:
        data = json.loads(oc_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERR_BAD_SCAN_JSON: {exc}", file=sys.stderr)
        return 2

    agents = data.get("agents", [])
    if not isinstance(agents, list):
        print("ERR_BAD_SCAN_JSON: agents must be a list", file=sys.stderr)
        return 2

    cfg = load_machine()
    added = 0
    for agent in agents:
        if not isinstance(agent, dict):
            continue
        name = str(agent.get("name", "")).strip()
        workspace_text = str(agent.get("workspace", "")).strip()
        if not name or not workspace_text:
            continue
        workspace = Path(workspace_text).expanduser()
        if not workspace.exists():
            continue
        if name in cfg.tenants:
            continue
        cfg.tenants[name] = OpenClawTenant(
            name=name,
            workspace=workspace,
            description="auto-registered by scan",
        )
        added += 1

    write_machine(cfg)
    print(f"OK: {added} tenant(s) added; {len(cfg.tenants)} total")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    memory_root = Path(args[0] if args else "~/.agents/memory").expanduser()
    return bootstrap_machine_tenants(memory_root)


if __name__ == "__main__":
    raise SystemExit(main())
