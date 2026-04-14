from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any


def resolve_clawseat_root() -> Path:
    configured = os.environ.get("CLAWSEAT_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()

    module_path = Path(__file__).resolve()
    for parent in module_path.parents:
        candidate = parent / "core" / "harness_adapter.py"
        if candidate.exists():
            return parent
    raise RuntimeError("CLAWSEAT_ROOT is not set and no local ClawSeat checkout was discovered")


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_harness_adapter_types() -> Any:
    root = resolve_clawseat_root()
    return _load_module("clawseat_core_harness_adapter", root / "core" / "harness_adapter.py")


def load_tmux_cli_adapter_module() -> Any:
    root = resolve_clawseat_root()
    return _load_module(
        "clawseat_tmux_cli_adapter",
        root / "adapters" / "harness" / "tmux-cli" / "adapter.py",
    )


def create_adapter(
    *,
    agents_root: str | Path | None = None,
    sessions_root: str | Path | None = None,
    workspaces_root: str | Path | None = None,
) -> Any:
    module = load_tmux_cli_adapter_module()
    return module.TmuxCliAdapter(
        agents_root=agents_root,
        sessions_root=sessions_root,
        workspaces_root=workspaces_root,
    )


def shell_metadata() -> dict[str, str]:
    root = resolve_clawseat_root()
    return {
        "shell": "claude-bundle",
        "clawseat_root": str(root),
        "adapter": str(root / "adapters" / "harness" / "tmux-cli" / "adapter.py"),
        "contract": str(root / "core" / "harness_adapter.py"),
        "core_skill": str(root / "core" / "skills" / "gstack-harness" / "SKILL.md"),
    }
