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

    Primary: ~/.agents/profiles/{project}-profile-dynamic.toml (persistent)
    Fallback: /tmp/{project}-profile-dynamic.toml (legacy, lost on reboot)

    If only the /tmp/ copy exists, it is migrated to the persistent
    location on first access. Migration is **concurrency-safe**:

    - all candidate writers go through the same `.lock` file under
      `~/.agents/profiles/.migrating-{project}.lock` using `fcntl.flock`
    - the copy lands in a sibling `.tmp` file and is then renamed, so
      readers never observe a half-written target

    Previously this used plain `shutil.copy2` with no lock, so two
    concurrent startup paths (e.g. planner + heartbeat seat importing
    at the same moment) could interleave writes and produce a truncated
    or mixed TOML (audit H11).
    """
    persistent = Path.home() / ".agents" / "profiles" / f"{project}-profile-dynamic.toml"
    if persistent.exists():
        return persistent
    legacy = Path("/tmp") / f"{project}-profile-dynamic.toml"
    if legacy.exists():
        _atomic_migrate_profile(legacy, persistent)
        return persistent
    # Neither exists yet — return persistent location for new installs
    return persistent


def _atomic_migrate_profile(source: Path, destination: Path) -> None:
    """Copy *source* to *destination* atomically and concurrency-safely.

    Holds an exclusive flock on a sibling `.lock` file while performing
    `copy2 -> rename`. Multiple callers serialize; only one writes, the
    others observe the completed destination and return.
    """
    import fcntl
    import shutil

    destination.parent.mkdir(parents=True, exist_ok=True)
    lock_path = destination.parent / f".migrating-{destination.name}.lock"
    tmp_path = destination.with_suffix(destination.suffix + ".tmp")

    # Open lock file read/write so flock can take an exclusive hold; keep
    # it open for the whole critical section.
    with open(lock_path, "a+") as lock_fh:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        try:
            # Double-check after acquiring the lock — another process may
            # have finished the migration while we were waiting.
            if destination.exists():
                return
            shutil.copy2(source, tmp_path)
            # os.replace is atomic on the same filesystem.
            os.replace(tmp_path, destination)
        finally:
            # Clean up the tmp file if copy2 succeeded but replace failed.
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)
