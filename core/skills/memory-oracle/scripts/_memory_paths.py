#!/usr/bin/env python3
"""
_memory_paths.py — directory layout constants and ID generation for memory-oracle.

Layout (target state, SPEC §3):
  ~/.agents/memory/
  ├── machine/                           ← scanner outputs
  │   └── current_context.json           ← current project pointer + last_refresh_ts
  ├── projects/<project-name>/
  │   ├── decisions/<id>.json
  │   ├── deliveries/<id>.json
  │   ├── issues/<id>.json
  │   ├── findings/<id>.json
  │   └── reflections.jsonl
  ├── shared/
  │   ├── library_knowledge/<topic>.json
  │   ├── patterns/<pattern-id>.json
  │   └── examples/<lib>-<pattern>.json
  ├── research/<topic>/
  ├── events.log
  └── responses/<query-id>.json
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path


def _real_user_home() -> Path:
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
MEMORY_ROOT = HOME / ".agents" / "memory"

MACHINE_DIR = MEMORY_ROOT / "machine"
PROJECTS_DIR = MEMORY_ROOT / "projects"
SHARED_DIR = MEMORY_ROOT / "shared"
RESEARCH_DIR = MEMORY_ROOT / "research"
EVENTS_LOG = MEMORY_ROOT / "events.log"
RESPONSES_DIR = MEMORY_ROOT / "responses"

# Filename for per-project reflection JSONL (SPEC §3)
REFLECTIONS_FILE = "reflections.jsonl"

# Subdirectories under projects/<name>/ for each fact kind
KIND_SUBDIRS: dict[str, str] = {
    "decision": "decisions",
    "delivery": "deliveries",
    "issue": "issues",
    "finding": "findings",
}

# Subdirectories under shared/ for each fact kind
SHARED_KIND_SUBDIRS: dict[str, str] = {
    "library_knowledge": "library_knowledge",
    "pattern": "patterns",
    "example": "examples",
}


def project_dir(project: str) -> Path:
    """Return the directory for a named project."""
    return PROJECTS_DIR / project


def reflections_path(project: str, *, memory_root: Path | None = None) -> Path:
    """Return the reflections JSONL path for a project (SPEC §3).

    Write hooks are M5's responsibility; this constant is registered here so
    M3/M5 can import it without re-deriving the layout.
    """
    root = memory_root if memory_root is not None else MEMORY_ROOT
    return root / "projects" / project / REFLECTIONS_FILE


def events_log_path(*, memory_root: Path | None = None) -> Path:
    """Return the global events.log JSONL path (SPEC §3).

    Write hooks are M5's responsibility; registered here for importability.
    """
    root = memory_root if memory_root is not None else MEMORY_ROOT
    return root / "events.log"


def generate_id(kind: str, project: str, content: str) -> str:
    """Generate a stable fact ID: <kind>-<project|shared>-<8-char hash>.

    Includes time.time_ns() so two writes of the same title don't collide.
    """
    ns = "shared" if project == "_shared" else project
    payload = f"{kind}:{ns}:{content}:{time.time_ns()}"
    digest = hashlib.sha256(payload.encode()).hexdigest()[:8]
    return f"{kind}-{ns}-{digest}"


def fact_path(kind: str, project: str, fact_id: str, *, memory_root: Path | None = None) -> Path:
    """Resolve where a fact JSON file should be stored on disk.

    Args:
        kind: Fact kind (decision, delivery, ...).
        project: Project name or '_shared'.
        fact_id: The generated fact ID.
        memory_root: Override for ~/.agents/memory (used in tests).
    """
    root = memory_root if memory_root is not None else MEMORY_ROOT

    if project == "_shared":
        subdir_name = SHARED_KIND_SUBDIRS.get(kind, f"{kind}s")
        return root / "shared" / subdir_name / f"{fact_id}.json"

    # reflection → per-project JSONL (SPEC §3; write appended by M5)
    if kind == "reflection":
        return reflections_path(project, memory_root=memory_root)

    subdir_name = KIND_SUBDIRS.get(kind)
    if subdir_name:
        return root / "projects" / project / subdir_name / f"{fact_id}.json"

    # Other kinds without a dedicated subdir go at project root
    return root / "projects" / project / f"{fact_id}.json"
