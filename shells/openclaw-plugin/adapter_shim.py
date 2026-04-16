"""
Bootstrap wiring for ClawSeat OpenClaw shell.

Minimal wiring that:
- Resolves CLAWSEAT_ROOT
- Loads core harness_adapter interface via importlib
- Attempts to load openclaw harness adapter (currently stub)
- Falls back to tmux-cli adapter

No business protocol logic (planner/koder/handoff semantics are in core).
Uses importlib to load modules from file paths directly, consistent with
claude-bundle and codex-bundle patterns.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any


def resolve_clawseat_root() -> Path:
    """Resolve CLAWSEAT_ROOT via shared core/resolve.py."""
    _script_dir = Path(__file__).resolve().parent
    _repo_root = _script_dir.parents[1]  # shells/openclaw-plugin/ -> shells/ -> ClawSeat root
    _core_path = str(_repo_root / "core")
    if _core_path not in sys.path:
        sys.path.insert(0, _core_path)
    from resolve import resolve_clawseat_root as _shared
    return _shared()


def _load_module(name: str, path: Path) -> Any:
    """Load a Python module directly from a file path."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_harness_adapter_types() -> Any:
    """Load the core HarnessAdapter interface module."""
    root = resolve_clawseat_root()
    return _load_module("clawseat_core_harness_adapter", root / "core" / "harness_adapter.py")


def load_tmux_cli_adapter_module() -> Any:
    """Load the tmux-cli harness adapter module."""
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
    """Create a tmux-cli adapter instance (fallback when openclaw adapter is stub)."""
    module = load_tmux_cli_adapter_module()
    return module.TmuxCliAdapter(
        agents_root=agents_root,
        sessions_root=sessions_root,
        workspaces_root=workspaces_root,
    )


def get_current_adapter_name() -> str:
    """Return the name of the currently active adapter."""
    return "tmux-cli"  # openclaw adapter is stub, always falls back


def shell_metadata() -> dict[str, str]:
    """Return shell metadata with paths."""
    root = resolve_clawseat_root()
    return {
        "shell": "openclaw-plugin",
        "clawseat_root": str(root),
        "adapter": str(root / "adapters" / "harness" / "tmux-cli" / "adapter.py"),
        "contract": str(root / "core" / "harness_adapter.py"),
    }
