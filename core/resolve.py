"""
resolve.py — Single source of truth for CLAWSEAT_ROOT resolution
and dynamic profile path construction.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Marker files that confirm a directory is the ClawSeat repo root
_REPO_MARKERS = (
    Path("core/scripts/agent_admin.py"),
    Path("core/skills/gstack-harness/scripts/_common.py"),
)


def resolve_clawseat_root(agents_root: Path | None = None) -> Path:
    """
    Resolve CLAWSEAT_ROOT. Tries in order:
    1. $CLAWSEAT_ROOT env var
    2. Parent traversal from this file with dual marker validation
    3. agents_root inference (if provided): agents_root/../coding/ClawSeat
    4. ~/coding/ClawSeat as validated fallback

    Raises RuntimeError if no valid root found.
    """
    # 1. env var
    configured = os.environ.get("CLAWSEAT_ROOT", "").strip()
    if configured:
        p = Path(configured).expanduser()
        if p.exists():
            return p
        # Trust env even without existence check for remote/future setups
        return p

    # 2. parent traversal
    candidates: list[Path] = []
    module_path = Path(__file__).resolve()
    for parent in module_path.parents:
        candidates.append(parent)
        candidates.append(parent / "ClawSeat")

    # 3. agents_root inference
    if agents_root is not None:
        candidates.append(agents_root.parent / "coding" / "ClawSeat")

    # 4. home fallback
    candidates.append(Path.home() / "coding" / "ClawSeat")

    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if all((resolved / marker).exists() for marker in _REPO_MARKERS):
            return resolved

    raise RuntimeError(
        "CLAWSEAT_ROOT is not set and no ClawSeat checkout was found. "
        "Set CLAWSEAT_ROOT env var or run from within the ClawSeat directory."
    )


def try_resolve_clawseat_root() -> Path | None:
    """
    Like resolve_clawseat_root() but returns None instead of raising.
    Use in diagnostics / preflight where a missing root is an expected finding.
    """
    try:
        return resolve_clawseat_root()
    except RuntimeError:
        return None


def dynamic_profile_path(project: str) -> Path:
    """
    Return the canonical path for a project's dynamic profile TOML.
    Currently /tmp/{project}-profile-dynamic.toml.
    """
    return Path("/tmp") / f"{project}-profile-dynamic.toml"
