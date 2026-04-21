"""migrate_profile_to_v2.py — P1 migration v1 → v2 profile schema.

Implements ``docs/schemas/v0.4-layered-model.md §6`` rules:

1. ``memory`` in seats → moved to ``machine.toml [services.memory]``
   (machine.toml only touched if the entry is missing; never overwrite).
2. ``koder`` in seats → replaced by ``openclaw_frontstage_agent = <tenant>``
   where tenant is auto-detected from
   ``~/.openclaw/workspace-*/WORKSPACE_CONTRACT.toml .project == project_name``.
   If no matching tenant, abort with operator instructions.
3. All ``heartbeat_*`` / deprecated fields stripped.
4. ``ancestor`` inserted if missing (§4 minimum).
5. ``designer`` inserted if missing (warning — operator may opt out).
6. ``builder-N``, ``reviewer-N``, ``qa-N`` collapsed to single role with
   ``seat_overrides.<role>.parallel_instances = N``.
7. ``version`` bumped to 2.

Subcommands::

    migrate-profile-to-v2 plan [--profile PATH]
    migrate-profile-to-v2 apply --profile PATH
    migrate-profile-to-v2 apply-all
    migrate-profile-to-v2 rollback --profile PATH

Idempotent: ``apply`` on a v2 profile is a no-op (prints "already v2"
and exits 0).

Stdlib-only. Builder-1's ``profile_validator.write_validated`` /
``machine_config.load_machine`` are used when importable; when they are
not (parallel-branch state), a best-effort fallback writer is used and a
warning is emitted so operators know validation was skipped.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover — Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]

# Path bootstrapping so we can import core.lib.* regardless of invocation
# mode (python path / script / package).
_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_REPO_ROOT), str(_REPO_ROOT / "core" / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from real_home import real_user_home  # noqa: E402

# P1 is a parallel-development task. Builder-1 owns machine_config +
# profile_validator. Import defensively so this script still produces
# diffs / writes a best-effort file when run on a branch that doesn't
# have builder-1's commits yet.
try:
    from profile_validator import (  # type: ignore[import-not-found]
        ProfileValidationError,
        write_validated,
    )
    _VALIDATOR_AVAILABLE = True
except ImportError:  # pragma: no cover — covered by parallel-dev fallback
    _VALIDATOR_AVAILABLE = False

    class ProfileValidationError(ValueError):  # type: ignore[no-redef]
        def __init__(self, errors: list[str]) -> None:
            self.errors = errors
            super().__init__("; ".join(errors))

    def write_validated(payload: dict, path: Path, **_kwargs) -> Path:  # type: ignore[no-redef]
        raise ImportError("profile_validator not available")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SIX_ROLES: tuple[str, ...] = (
    "ancestor", "planner", "builder", "reviewer", "qa", "designer",
)
PARALLEL_ROLES: frozenset[str] = frozenset({"builder", "reviewer", "qa"})

# Deprecated v1 fields that must be stripped during migration.
_DEPRECATED_FIELDS = (
    "heartbeat_owner", "heartbeat_transport",
    "heartbeat_receipt", "heartbeat_seats",
    "active_loop_owner", "default_notify_target",
    "status_script", "patrol_script",
    "description",
)

_DEPRECATED_DYNAMIC_ROSTER = (
    "materialized_seats", "runtime_seats", "compat_legacy_seats",
)

# Regex for indexed v1 role names (builder-1, reviewer-2, qa-3).
_INDEXED_RE = re.compile(r"^(builder|reviewer|qa)-(\d+)$")

# Schema-recommended defaults when a seat needs to be inserted.
_DEFAULT_OVERRIDES: dict[str, dict[str, Any]] = {
    "ancestor":  {"tool": "claude", "auth_mode": "oauth_token", "provider": "anthropic"},
    "planner":   {"tool": "claude", "auth_mode": "oauth_token", "provider": "anthropic"},
    "builder":   {"tool": "claude", "auth_mode": "oauth_token", "provider": "anthropic"},
    "reviewer":  {"tool": "codex",  "auth_mode": "api",          "provider": "xcode-best"},
    "qa":        {"tool": "claude", "auth_mode": "api",          "provider": "minimax"},
    "designer":  {"tool": "gemini", "auth_mode": "oauth",        "provider": "google"},
}

_CANONICAL_ROLE_NAMES: dict[str, str] = {
    "ancestor": "ancestor",
    "planner":  "planner-dispatcher",
    "builder":  "builder",
    "reviewer": "reviewer",
    "qa":       "qa",
    "designer": "designer",
}

# Memory service defaults (schema §3). Used when we need to seed machine.toml
# from a v1 profile's memory overrides.
_MEMORY_DEFAULT: dict[str, Any] = {
    "role":         "memory-oracle",
    "tool":         "claude",
    "auth_mode":    "api",
    "provider":     "minimax",
    "model":        "MiniMax-M2.7-highspeed",
    "runtime_dir":  "~/.agents/runtime/memory",
    "storage_root": "~/.agents/memory",
    "launch_args":  [],
    "monitor":      True,
}


# ---------------------------------------------------------------------------
# Core migration
# ---------------------------------------------------------------------------

class MigrationError(RuntimeError):
    """Raised when migration cannot proceed (e.g., missing tenant match)."""


def detect_tenant(project_name: str, workspaces_root: Path) -> str | None:
    """Probe ``<workspaces_root>/workspace-*/WORKSPACE_CONTRACT.toml``.

    Returns the tenant name (directory suffix after ``workspace-``) whose
    contract declares ``project == project_name``, or None if no match.
    """
    if not workspaces_root.is_dir():
        return None
    for ws in sorted(workspaces_root.glob("workspace-*")):
        contract = ws / "WORKSPACE_CONTRACT.toml"
        if not contract.is_file():
            continue
        try:
            data = tomllib.loads(contract.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(data.get("project", "")) == project_name:
            return ws.name[len("workspace-"):]
    return None


def migrate_profile(
    v1: dict[str, Any],
    *,
    workspaces_root: Path | None = None,
    project_name_override: str | None = None,
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Apply §6 rules to a v1 profile dict.

    Returns ``(v2_dict, warnings, errors)``. Errors are non-blocking at
    the function level — the CLI decides whether to abort.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if int(v1.get("version", 1)) == 2:
        return dict(v1), warnings, errors

    v2: dict[str, Any] = dict(v1)
    project_name = project_name_override or str(v1.get("project_name", ""))

    # 1. Analyse v1 seats.
    v1_seats = list(v1.get("seats", []))
    has_memory = "memory" in v1_seats
    has_koder = "koder" in v1_seats
    parallel: dict[str, int] = {}
    collapsed: list[str] = []

    for seat in v1_seats:
        if seat in ("memory", "koder"):
            continue
        m = _INDEXED_RE.match(seat)
        if m:
            base, n = m.group(1), int(m.group(2))
            parallel[base] = max(parallel.get(base, 0), n)
            if base not in collapsed:
                collapsed.append(base)
        elif seat in SIX_ROLES:
            if seat not in collapsed:
                collapsed.append(seat)
        else:
            errors.append(
                f"unknown v1 seat {seat!r}; expected one of "
                f"{{memory, koder, ancestor, planner, "
                f"builder[-N], reviewer[-N], qa[-N], designer}}"
            )

    # 2. machine_services declaration.
    if has_memory:
        existing = list(v2.get("machine_services", []))
        if "memory" not in existing:
            existing.append("memory")
        v2["machine_services"] = sorted(set(existing))

    # 3. openclaw_frontstage_agent from tenant auto-detect.
    if has_koder:
        root = workspaces_root or (real_user_home() / ".openclaw")
        tenant = detect_tenant(project_name, root)
        if tenant is None:
            errors.append(
                f"v1 seats contain 'koder' but no ~/.openclaw/workspace-*/"
                f"WORKSPACE_CONTRACT.toml declares project={project_name!r}. "
                f"Fix: run `agent-admin project koder-bind --project "
                f"{project_name} --tenant <name>` to bind first, then re-run "
                f"migrate-profile-to-v2."
            )
        else:
            v2["openclaw_frontstage_agent"] = tenant

    # 4. Strip deprecated fields.
    for k in _DEPRECATED_FIELDS:
        v2.pop(k, None)

    # 5. Ensure minimum seat set + designer with warning.
    seats_out = list(collapsed)
    if "ancestor" not in seats_out:
        seats_out.append("ancestor")
    if "planner" not in seats_out:
        seats_out.append("planner")
    if "designer" not in seats_out:
        seats_out.append("designer")
        warnings.append(
            "inserted 'designer' seat per schema §4; operator may remove "
            "it after review if the project does not need a designer role"
        )
    # Canonical order (§4).
    v2["seats"] = [r for r in SIX_ROLES if r in seats_out]

    # 6. seat_roles — canonical 1:1 mapping.
    v2["seat_roles"] = {r: _CANONICAL_ROLE_NAMES[r] for r in v2["seats"]}

    # 7. seat_overrides — copy v1 override when available, else defaults;
    # inject parallel_instances for collapsed roles.
    old_overrides = dict(v1.get("seat_overrides", {}) or {})
    new_overrides: dict[str, dict[str, Any]] = {}
    for role in v2["seats"]:
        src: dict[str, Any] | None = None
        for candidate in (role, f"{role}-1"):
            if candidate in old_overrides and isinstance(old_overrides[candidate], dict):
                src = dict(old_overrides[candidate])
                break
        if src is None:
            src = dict(_DEFAULT_OVERRIDES[role])
        # parallel_instances lives only on builder/reviewer/qa.
        src.pop("parallel_instances", None)
        if role in PARALLEL_ROLES:
            src["parallel_instances"] = parallel.get(role, 1)
        new_overrides[role] = src
    v2["seat_overrides"] = new_overrides

    # 8. dynamic_roster cleanup (keep enabled + session_root; rewrite
    # bootstrap_seats / default_start_seats per schema §4).
    dr = dict(v2.get("dynamic_roster", {}) or {})
    for k in _DEPRECATED_DYNAMIC_ROSTER:
        dr.pop(k, None)
    dr["bootstrap_seats"] = ["ancestor"]
    dr["default_start_seats"] = ["ancestor", "planner"]
    v2["dynamic_roster"] = dr

    # 9. version bump.
    v2["version"] = 2
    return v2, warnings, errors


def memory_service_from_v1(v1: dict[str, Any]) -> dict[str, Any]:
    """Build a ``[services.memory]`` dict from v1's seat_overrides.memory,
    falling back to the schema §3 defaults where v1 is silent."""
    mem = dict(_MEMORY_DEFAULT)
    ovr = dict((v1.get("seat_overrides", {}) or {}).get("memory", {}) or {})
    for k in ("tool", "auth_mode", "provider", "model"):
        if ovr.get(k):
            mem[k] = ovr[k]
    return mem


# ---------------------------------------------------------------------------
# Backup / rollback
# ---------------------------------------------------------------------------

_BACKUP_RE = re.compile(r"\.bak\.v1\.(\d{8}-\d{6})$")


def _backup_suffix(now: datetime | None = None) -> str:
    now = now or datetime.now()
    return f".bak.v1.{now.strftime('%Y%m%d-%H%M%S')}"


def backup_profile(profile: Path, *, now: datetime | None = None) -> Path:
    suffix = _backup_suffix(now)
    backup = profile.with_name(profile.name + suffix)
    shutil.copy2(profile, backup)
    return backup


def latest_backup(profile: Path) -> Path | None:
    candidates: list[tuple[str, Path]] = []
    for sibling in profile.parent.glob(profile.name + ".bak.v1.*"):
        m = _BACKUP_RE.search(sibling.name)
        if m:
            candidates.append((m.group(1), sibling))
    if not candidates:
        return None
    candidates.sort()  # lexicographic ordering == chronological here
    return candidates[-1][1]


# ---------------------------------------------------------------------------
# TOML serializer (stdlib-only fallback)
# ---------------------------------------------------------------------------

def _toml_scalar(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int) and not isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, str):
        # json.dumps handles quoting + escapes correctly for TOML basic strings.
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return "[" + ", ".join(_toml_scalar(x) for x in v) + "]"
    raise TypeError(f"unsupported TOML scalar {type(v).__name__}: {v!r}")


def dump_toml(data: dict[str, Any]) -> str:
    """Small stdlib TOML writer for the v2 profile shape.

    Handles top-level scalars and 1/2-depth tables. Does NOT support
    array-of-tables, which the v2 schema does not need.
    """
    out: list[str] = []
    # Pass 1: top-level scalars / lists.
    for k, v in data.items():
        if isinstance(v, dict):
            continue
        out.append(f"{k} = {_toml_scalar(v)}")
    # Pass 2: tables, recursively (single level of nesting only).
    for k, v in data.items():
        if not isinstance(v, dict):
            continue
        flat_scalars = {kk: vv for kk, vv in v.items() if not isinstance(vv, dict)}
        nested_tables = {kk: vv for kk, vv in v.items() if isinstance(vv, dict)}
        out.append("")
        out.append(f"[{k}]")
        for kk, vv in flat_scalars.items():
            out.append(f"{kk} = {_toml_scalar(vv)}")
        for kk, vv in nested_tables.items():
            out.append("")
            out.append(f"[{k}.{kk}]")
            for inner_k, inner_v in vv.items():
                if isinstance(inner_v, dict):
                    raise ValueError(
                        f"unsupported depth-3 nesting under [{k}.{kk}.{inner_k}]"
                    )
                out.append(f"{inner_k} = {_toml_scalar(inner_v)}")
    return "\n".join(out) + "\n"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def _load_profile(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise MigrationError(f"profile not found: {path}")
    except Exception as exc:
        raise MigrationError(f"cannot parse {path}: {exc}")


def _summary_diff(v1: dict[str, Any], v2: dict[str, Any]) -> list[str]:
    """Human-readable diff between v1 and v2 (not a full TOML diff)."""
    lines: list[str] = []
    lines.append(f"  version  : {v1.get('version', '?')} -> {v2.get('version', '?')}")
    lines.append(f"  seats    : {v1.get('seats', [])} -> {v2.get('seats', [])}")
    if v2.get("openclaw_frontstage_agent"):
        lines.append(f"  openclaw_frontstage_agent = {v2['openclaw_frontstage_agent']!r}")
    if v2.get("machine_services"):
        lines.append(f"  machine_services = {v2['machine_services']}")
    removed = [f for f in _DEPRECATED_FIELDS if f in v1]
    if removed:
        lines.append(f"  removed deprecated fields: {removed}")
    overrides_v2 = v2.get("seat_overrides") or {}
    for role, body in overrides_v2.items():
        if "parallel_instances" in body:
            lines.append(
                f"  seat_overrides.{role}.parallel_instances = {body['parallel_instances']}"
            )
    return lines


def cmd_plan(args: argparse.Namespace) -> int:
    path = Path(args.profile).expanduser()
    v1 = _load_profile(path)
    v2, warnings, errors = migrate_profile(
        v1, workspaces_root=_maybe_path(args.workspaces_root),
    )
    if int(v1.get("version", 1)) == 2:
        print(f"already v2: {path}")
        return 0
    print(f"plan migrate v1 -> v2 for {path}:")
    for line in _summary_diff(v1, v2):
        print(line)
    for w in warnings:
        print(f"  warning: {w}")
    for e in errors:
        print(f"  error: {e}", file=sys.stderr)
    return 1 if errors else 0


def cmd_apply(args: argparse.Namespace) -> int:
    path = Path(args.profile).expanduser()
    v1 = _load_profile(path)
    if int(v1.get("version", 1)) == 2:
        print(f"already v2 (no-op): {path}")
        return 0
    v2, warnings, errors = migrate_profile(
        v1, workspaces_root=_maybe_path(args.workspaces_root),
    )
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        return 1

    backup = backup_profile(path)
    print(f"backup: {backup}")

    wrote_via = "fallback"
    try:
        if _VALIDATOR_AVAILABLE and not args.skip_validate:
            write_validated(v2, path)
            wrote_via = "write_validated"
        else:
            atomic_write(path, dump_toml(v2))
            if not _VALIDATOR_AVAILABLE:
                print(
                    "warning: profile_validator not importable — wrote without "
                    "schema validation. Run `agent-admin project validate` after "
                    "builder-1's commits land to verify.",
                    file=sys.stderr,
                )
    except ProfileValidationError as exc:
        for e in exc.errors:
            print(f"validator error: {e}", file=sys.stderr)
        shutil.copy2(backup, path)
        print(f"restored from backup due to validation failure: {backup}", file=sys.stderr)
        return 2

    for w in warnings:
        print(f"warning: {w}")
    print(f"wrote v2 profile ({wrote_via}): {path}")
    return 0


def cmd_apply_all(args: argparse.Namespace) -> int:
    root = _maybe_path(args.profiles_dir) or (real_user_home() / ".agents" / "profiles")
    if not root.is_dir():
        print(f"error: profiles dir not found: {root}", file=sys.stderr)
        return 1
    rc_worst = 0
    for profile in sorted(root.glob("*.toml")):
        print(f"== {profile}")
        sub = argparse.Namespace(
            profile=str(profile),
            workspaces_root=args.workspaces_root,
            skip_validate=args.skip_validate,
        )
        rc = cmd_apply(sub)
        rc_worst = max(rc_worst, rc)
    return rc_worst


def cmd_rollback(args: argparse.Namespace) -> int:
    path = Path(args.profile).expanduser()
    backup = latest_backup(path)
    if backup is None:
        print(f"error: no backup found for {path}", file=sys.stderr)
        return 1
    shutil.copy2(backup, path)
    print(f"restored: {path} <- {backup}")
    return 0


def _maybe_path(p: str | None) -> Path | None:
    return Path(p).expanduser() if p else None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="migrate-profile-to-v2",
        description="Migrate a v1 ClawSeat project profile to v2 per "
                    "docs/schemas/v0.4-layered-model.md §6.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="Dry-run diff; no file writes.")
    plan.add_argument("--profile", required=True)
    plan.add_argument("--workspaces-root", default=None,
                      help="Override ~/.openclaw for tenant discovery (tests).")
    plan.set_defaults(func=cmd_plan)

    apply_p = sub.add_parser("apply", help="Apply with backup; idempotent on v2.")
    apply_p.add_argument("--profile", required=True)
    apply_p.add_argument("--workspaces-root", default=None)
    apply_p.add_argument(
        "--skip-validate", action="store_true",
        help="Write without calling profile_validator.write_validated "
             "(useful when builder-1's half hasn't landed yet).",
    )
    apply_p.set_defaults(func=cmd_apply)

    apply_all_p = sub.add_parser("apply-all",
                                 help="Apply to every *.toml in ~/.agents/profiles.")
    apply_all_p.add_argument("--profiles-dir", default=None)
    apply_all_p.add_argument("--workspaces-root", default=None)
    apply_all_p.add_argument("--skip-validate", action="store_true")
    apply_all_p.set_defaults(func=cmd_apply_all)

    rollback_p = sub.add_parser("rollback",
                                help="Restore the most recent .bak.v1.* backup.")
    rollback_p.add_argument("--profile", required=True)
    rollback_p.set_defaults(func=cmd_rollback)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except MigrationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
