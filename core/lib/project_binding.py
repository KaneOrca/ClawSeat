"""Per-project binding SSOT (C2).

`~/.agents/tasks/<project>/PROJECT_BINDING.toml` is the single source of
truth for a project's external bindings — currently its Feishu group,
bot account, and mention-gate policy. The file is written by
``agent_admin project bind`` (and anything else that understands this
schema) and is read by every Feishu closeout path via
``_feishu.resolve_feishu_group_strict(project)``.

Why this file (and not WORKSPACE_CONTRACT.toml):

1. WORKSPACE_CONTRACT.toml is **regenerated** by the framework during
   bootstrap/reconfigure. Fields not in the generator's payload get
   silently erased on regeneration. Binding data is out-of-band and
   must survive those rewrites.
2. Bindings are per-project, not per-seat. A project contract lives
   under ``<workspace>/<seat>/`` and is naturally per-seat; binding
   belongs one level up.
3. Having a clear, standalone file makes it obvious to an operator
   what is bound where, and makes drift (bindings without a project,
   stale bindings after project delete) trivially detectable.

Schema (v1):

    version = 1
    project = "install"
    feishu_group_id = "oc_b0386423ec11582696a3079ab2ab89ba"
    feishu_bot_account = "koder"
    require_mention = false
    bound_at = "2026-04-21T16:45:16+00:00"
    bound_by = "koder"         # optional — seat that wrote the binding

Unknown fields are preserved on rewrite so future schema extensions
don't silently drop operator-authored metadata.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from real_home import real_user_home

try:  # Python 3.11+ has tomllib in stdlib; fall back to `tomli` for older.
    import tomllib  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

BINDING_SCHEMA_VERSION = 1
BINDING_FILE_NAME = "PROJECT_BINDING.toml"

# Canonical Feishu group id: `oc_` + alphanumerics/underscore/hyphen. Same
# regex as _feishu._FEISHU_GROUP_ID_RE — duplicated here to avoid a cycle
# (this module is imported by agent_admin, which lives outside the
# gstack-harness scripts namespace where _feishu sits).
_FEISHU_GROUP_ID_RE = re.compile(r"^oc_[A-Za-z0-9_-]+$")


class ProjectBindingError(ValueError):
    """Raised on malformed, missing, or mismatched project bindings."""


@dataclass
class ProjectBinding:
    project: str
    feishu_group_id: str
    feishu_bot_account: str = "koder"
    require_mention: bool = False
    bound_at: str = ""
    bound_by: str = ""
    version: int = BINDING_SCHEMA_VERSION
    extras: dict[str, Any] = field(default_factory=dict)

    def as_toml(self) -> str:
        """Serialize to TOML. Deterministic field order for diff readability."""
        lines = [
            f"version = {self.version}",
            f'project = "{_escape(self.project)}"',
            f'feishu_group_id = "{_escape(self.feishu_group_id)}"',
            f'feishu_bot_account = "{_escape(self.feishu_bot_account)}"',
            f"require_mention = {'true' if self.require_mention else 'false'}",
            f'bound_at = "{_escape(self.bound_at)}"',
        ]
        if self.bound_by:
            lines.append(f'bound_by = "{_escape(self.bound_by)}"')
        for key in sorted(self.extras):
            lines.append(_format_extra(key, self.extras[key]))
        return "\n".join(lines) + "\n"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _format_extra(key: str, value: Any) -> str:
    if isinstance(value, bool):
        return f"{key} = {'true' if value else 'false'}"
    if isinstance(value, (int, float)):
        return f"{key} = {value}"
    if isinstance(value, str):
        return f'{key} = "{_escape(value)}"'
    raise ProjectBindingError(
        f"cannot serialize extra key {key!r} of type {type(value).__name__} "
        "back to TOML; bindings only support scalar string/int/bool extras"
    )


def validate_feishu_group_id(group_id: str) -> str:
    """Return the stripped id if valid, else raise ProjectBindingError."""
    value = (group_id or "").strip()
    if not _FEISHU_GROUP_ID_RE.match(value):
        raise ProjectBindingError(
            f"invalid Feishu group id {group_id!r}: must match 'oc_<alphanum>' "
            "(e.g. oc_b0386423ec11582696a3079ab2ab89ba)"
        )
    return value


def validate_project_name(project: str) -> str:
    value = (project or "").strip()
    if not value:
        raise ProjectBindingError("project name cannot be empty")
    # Project name lands in filesystem paths, keep it conservative.
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", value):
        raise ProjectBindingError(
            f"invalid project name {project!r}: must start with alphanumeric "
            "and contain only alphanumerics, dot, hyphen, or underscore"
        )
    return value


# ── Path helpers ──────────────────────────────────────────────────────


def bindings_root(home: Path | None = None) -> Path:
    """Parent directory that contains each project's binding file."""
    return (home or real_user_home()) / ".agents" / "tasks"


def binding_path(project: str, home: Path | None = None) -> Path:
    """Return ``~/.agents/tasks/<project>/PROJECT_BINDING.toml``."""
    return bindings_root(home) / validate_project_name(project) / BINDING_FILE_NAME


# ── Read ──────────────────────────────────────────────────────────────


def load_binding(project: str, *, home: Path | None = None) -> ProjectBinding | None:
    """Return the binding for ``project`` or ``None`` if the file is missing."""
    path = binding_path(project, home=home)
    if not path.exists():
        return None
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # parse errors should not be silent
        raise ProjectBindingError(f"cannot parse {path}: {exc}") from exc

    declared_project = str(raw.get("project", "")).strip()
    if declared_project and declared_project != validate_project_name(project):
        raise ProjectBindingError(
            f"{path} declares project={declared_project!r} but was loaded for "
            f"project={project!r}; the file is in the wrong directory"
        )
    group_id = str(raw.get("feishu_group_id", "")).strip()
    if group_id:
        validate_feishu_group_id(group_id)

    known = {
        "version", "project", "feishu_group_id", "feishu_bot_account",
        "require_mention", "bound_at", "bound_by",
    }
    extras = {k: v for k, v in raw.items() if k not in known}
    return ProjectBinding(
        project=validate_project_name(project),
        feishu_group_id=group_id,
        feishu_bot_account=str(raw.get("feishu_bot_account", "koder")).strip() or "koder",
        require_mention=bool(raw.get("require_mention", False)),
        bound_at=str(raw.get("bound_at", "")).strip(),
        bound_by=str(raw.get("bound_by", "")).strip(),
        version=int(raw.get("version", BINDING_SCHEMA_VERSION)),
        extras=extras,
    )


# ── Write ─────────────────────────────────────────────────────────────


def write_binding(
    binding: ProjectBinding,
    *,
    home: Path | None = None,
    bound_at: str | None = None,
) -> Path:
    """Persist ``binding`` to disk, creating parent dirs. Returns the path."""
    validate_project_name(binding.project)
    validate_feishu_group_id(binding.feishu_group_id)
    if not binding.bound_at:
        binding.bound_at = bound_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    path = binding_path(binding.project, home=home)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic-ish write: write tmp + rename. Permissions 0o644 (non-secret).
    tmp = path.with_suffix(".toml.tmp")
    tmp.write_text(binding.as_toml(), encoding="utf-8")
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o644)
    except OSError:
        pass
    return path


def bind_project(
    *,
    project: str,
    feishu_group_id: str,
    feishu_bot_account: str = "koder",
    require_mention: bool = False,
    bound_by: str = "",
    home: Path | None = None,
) -> Path:
    """Convenience constructor → write. Returns the written path."""
    binding = ProjectBinding(
        project=validate_project_name(project),
        feishu_group_id=validate_feishu_group_id(feishu_group_id),
        feishu_bot_account=feishu_bot_account.strip() or "koder",
        require_mention=require_mention,
        bound_by=bound_by.strip(),
    )
    return write_binding(binding, home=home)


def list_bindings(*, home: Path | None = None) -> list[ProjectBinding]:
    """Return every parseable binding under ``~/.agents/tasks/*/``."""
    root = bindings_root(home)
    if not root.exists():
        return []
    results: list[ProjectBinding] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        try:
            binding = load_binding(child.name, home=home)
        except ProjectBindingError:
            continue
        if binding is not None:
            results.append(binding)
    return results
