"""Install wizard — produces a v2 project profile TOML by walking the
operator through each required decision from docs/schemas/v0.4-layered-model.md §4.

Status: mockup. Works today against a fake engine adapter so UX can be
validated before Phase 1 lands. Once profile_validator + machine_config
are real, the ENGINE object switches to the real modules and every field
is enum-gated by the validator (no free-form text for role / auth /
provider — see test_tui_validator_seam.py gate B).

Invocation:

    python3 -m core.tui.install_wizard               # interactive
    python3 -m core.tui.install_wizard --dry-run     # print TOML to stdout, don't write
    python3 -m core.tui.install_wizard --project NAME --accept-defaults   # CI-friendly

The wizard is curses-free on purpose for this mockup — terminal I/O via
input() makes the flow diffable in tests and reviewable in transcripts.
When we promote this out of mockup, wrap each screen in the
core/scripts/agent_admin_tui.py curses helpers.
"""
from __future__ import annotations

import argparse
import dataclasses
import io
import json
import sys
import textwrap
from pathlib import Path
from typing import Any, Callable, Sequence


# ─────────────────────────────────────────────────────────────────────
# Engine adapter — either real Phase 1 modules or a mock that encodes
# the §4 canonical sample. The wizard ONLY reads from here; never writes
# TOML directly. When Phase 1 lands, flip USE_REAL_ENGINE to True and
# delete MOCK_* constants.
# ─────────────────────────────────────────────────────────────────────

try:
    # Phase 1 live API — architect-delivered, see docs/schemas/v0.4-layered-model.md §7.
    from profile_validator import (  # type: ignore[import-not-found]
        LEGAL_SEATS,
        ProfileValidationError,
        ValidationResult,
        validate_profile_v2,
        write_validated,
    )
    # Canonical display order (role index). profile_validator exports
    # LEGAL_SEATS as a frozenset; the wizard needs a stable order for UI.
    _CANONICAL_SEAT_ORDER = ("ancestor", "planner", "builder", "reviewer", "qa", "designer")
    LEGAL_SEAT_ROLES = tuple(
        s for s in _CANONICAL_SEAT_ORDER if s in LEGAL_SEATS
    )
    # auth modes aren't exported as an enum yet; keep a local mirror that
    # profile_validator._check_profile accepts — architect will wire a
    # LEGAL_AUTH_MODES export in a follow-up; until then the wizard uses
    # this list and write_validated remains authoritative.
    LEGAL_AUTH_MODES: tuple[str, ...] = ("oauth", "oauth_token", "api")
    from machine_config import (  # type: ignore[import-not-found]
        list_openclaw_tenants,
    )
    USE_REAL_ENGINE = True
except ImportError:
    USE_REAL_ENGINE = False

    # Fallback enums used when Phase 1 modules aren't on sys.path (rare now).
    LEGAL_SEAT_ROLES: tuple[str, ...] = (  # type: ignore[no-redef]
        "ancestor", "planner", "builder", "reviewer", "qa", "designer",
    )
    LEGAL_AUTH_MODES: tuple[str, ...] = ("oauth", "oauth_token", "api")  # type: ignore[no-redef]

    class ProfileValidationError(ValueError):  # type: ignore[no-redef]
        def __init__(self, errors: list[str]):
            self.errors = errors
            super().__init__("; ".join(errors))

    @dataclasses.dataclass
    class ValidationResult:  # type: ignore[no-redef]
        ok: bool
        errors: list[str]
        warnings: list[str]
        normalized: dict | None

    def validate_profile_v2(path: Path, machine_home: Path | None = None) -> ValidationResult:  # type: ignore[no-redef]
        """Mockup: treat any non-empty file as valid."""
        return ValidationResult(
            ok=path.exists() and path.read_text().strip() != "",
            errors=[] if path.exists() else ["file does not exist"],
            warnings=["mock validator — Phase 1 not landed"],
            normalized=None,
        )

    def write_validated(payload: dict, path: Path) -> Path:  # type: ignore[no-redef]
        """Mockup: just write the TOML as-is."""
        path.write_text(_render_v2_toml(payload))
        return path

    @dataclasses.dataclass
    class _MockTenant:
        name: str
        workspace: str
        description: str = ""

    def list_openclaw_tenants() -> list[_MockTenant]:  # type: ignore[no-redef]
        return [
            _MockTenant(
                name="yu",
                workspace="~/.openclaw/workspace-yu",
                description="operator ywf's primary install-side tenant",
            ),
            _MockTenant(
                name="koder",
                workspace="~/.openclaw/workspace-koder",
                description="original koder tenant, currently bound to cartooner",
            ),
        ]


# ─────────────────────────────────────────────────────────────────────
# Wizard state & recommended defaults per seat (§4 canonical example).
# These defaults match the install profile in the spec verbatim.
# ─────────────────────────────────────────────────────────────────────

# Seats for which parallel_instances > 1 is legal (§7 rule 10).
PARALLEL_OK = {"builder", "reviewer", "qa"}

# Recommended (tool, auth_mode, provider) per role — aligns with §4 example.
RECOMMENDED_OVERRIDES: dict[str, dict[str, str]] = {
    "ancestor": {"tool": "claude", "auth_mode": "oauth_token", "provider": "anthropic"},
    "planner":  {"tool": "claude", "auth_mode": "oauth_token", "provider": "anthropic"},
    "builder":  {"tool": "claude", "auth_mode": "oauth_token", "provider": "anthropic"},
    "reviewer": {"tool": "codex",  "auth_mode": "api",         "provider": "xcode-best"},
    "qa":       {"tool": "claude", "auth_mode": "api",         "provider": "minimax"},
    "designer": {"tool": "gemini", "auth_mode": "oauth",       "provider": "google"},
}

# Canonical role mapping for seat_roles.X (§4).
CANONICAL_ROLE_NAMES: dict[str, str] = {
    "ancestor": "ancestor",
    "planner": "planner-dispatcher",
    "builder": "builder",
    "reviewer": "reviewer",
    "qa": "qa",
    "designer": "designer",
}


@dataclasses.dataclass
class SeatChoice:
    name: str                                # one of LEGAL_SEAT_ROLES
    tool: str
    auth_mode: str
    provider: str
    parallel_instances: int = 1


@dataclasses.dataclass
class WizardState:
    project_name: str = ""
    repo_root: str = "{CLAWSEAT_ROOT}"
    openclaw_frontstage_agent: str = ""      # a tenant name from machine.toml
    machine_services: list[str] = dataclasses.field(default_factory=lambda: ["memory"])
    seats: list[SeatChoice] = dataclasses.field(default_factory=list)
    patrol_cadence_minutes: int = 30


# ─────────────────────────────────────────────────────────────────────
# UI primitives — simple stdin/stdout prompts for the mockup. A later
# pass wraps these in curses (agent_admin_tui.py has helpers).
# ─────────────────────────────────────────────────────────────────────

def _prompt(msg: str, default: str | None = None, accept_defaults: bool = False) -> str:
    if accept_defaults and default is not None:
        print(f"{msg} [{default}] → {default}")
        return default
    suffix = f" [{default}]" if default is not None else ""
    try:
        raw = input(f"{msg}{suffix}: ").strip()
    except EOFError:
        return default or ""
    return raw or (default or "")


def _prompt_choice(
    msg: str,
    choices: Sequence[str],
    default: str | None = None,
    accept_defaults: bool = False,
) -> str:
    if accept_defaults and default is not None and default in choices:
        print(f"{msg} → {default}")
        return default
    print(msg)
    for i, c in enumerate(choices, 1):
        marker = " *" if c == default else ""
        print(f"  {i}) {c}{marker}")
    while True:
        raw = _prompt("select (number or name)", default=default or "")
        if raw in choices:
            return raw
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        print(f"  → pick one of {', '.join(choices)}")


def _prompt_int(msg: str, default: int, lo: int, hi: int, accept_defaults: bool = False) -> int:
    if accept_defaults:
        print(f"{msg} [{default}] → {default}")
        return default
    while True:
        raw = _prompt(msg, default=str(default))
        try:
            n = int(raw)
        except ValueError:
            print(f"  → must be an integer in [{lo}, {hi}]")
            continue
        if lo <= n <= hi:
            return n
        print(f"  → must be in [{lo}, {hi}]")


def _prompt_multiselect(
    msg: str,
    choices: Sequence[str],
    default: Sequence[str],
    required: Sequence[str] = (),
    accept_defaults: bool = False,
) -> list[str]:
    if accept_defaults:
        picked = list(default)
        print(f"{msg} → {', '.join(picked)}")
        return picked
    print(msg)
    for c in choices:
        tag = ""
        if c in required:
            tag = " (required)"
        elif c in default:
            tag = " (default on)"
        print(f"  - {c}{tag}")
    print(
        "Type comma-separated names to select, blank = defaults. "
        f"Required always included: {', '.join(required) or 'none'}"
    )
    raw = _prompt("select", default=",".join(default))
    picked = [p.strip() for p in raw.split(",") if p.strip()]
    # Enforce required
    for r in required:
        if r not in picked:
            picked.insert(0, r)
    # Enforce choices ⊆ legal set
    picked = [p for p in picked if p in choices]
    return picked


# ─────────────────────────────────────────────────────────────────────
# Screens
# ─────────────────────────────────────────────────────────────────────

def screen_welcome() -> None:
    print(textwrap.dedent("""
        ╔══════════════════════════════════════════════════════════════╗
        ║  ClawSeat v0.4 install wizard (layered model)                ║
        ║  Spec: docs/schemas/v0.4-layered-model.md                    ║
        ║                                                              ║
        ║  This wizard produces one v2 project profile TOML.           ║
        ║  It does NOT touch machine.toml (that's a separate surface). ║
        ║  It does NOT start any tmux seats (that's `agent-admin       ║
        ║  session start-project` afterward).                          ║
        ║                                                              ║
        ║  At the end we call profile_validator.write_validated — no   ║
        ║  operator hand-edit required if this wizard succeeds.        ║
        ╚══════════════════════════════════════════════════════════════╝
    """).strip())
    if not USE_REAL_ENGINE:
        print("  [mockup mode: profile_validator stub active — see test_tui_validator_seam.py]")
    print()


def screen_project_basics(state: WizardState, project_override: str | None, accept_defaults: bool) -> None:
    print("--- Project basics ---")
    state.project_name = project_override or _prompt(
        "project name (alphanumeric + dash)", default="install", accept_defaults=accept_defaults,
    )
    state.repo_root = _prompt(
        "repo_root (use {CLAWSEAT_ROOT} for the harness itself)",
        default="{CLAWSEAT_ROOT}",
        accept_defaults=accept_defaults,
    )
    print()


def screen_openclaw_frontstage(state: WizardState, accept_defaults: bool) -> None:
    print("--- OpenClaw frontstage tenant (koder) ---")
    print("Every v2 project names exactly one OpenClaw tenant as its koder.")
    print("Tenants come from machine.toml; this wizard only picks, never creates.")
    print()
    tenants = list_openclaw_tenants()
    if not tenants:
        print("[!] machine.toml has no openclaw_tenants entries.")
        print("    Run `agent-admin machine tenant add` (Phase 1) first, then retry.")
        raise SystemExit(2)
    names = [t.name for t in tenants]
    for t in tenants:
        print(f"  {t.name:<8} {t.workspace}  — {t.description}")
    print()
    default = "yu" if "yu" in names else names[0]
    state.openclaw_frontstage_agent = _prompt_choice(
        "pick the tenant that will host THIS project's koder",
        names,
        default=default,
        accept_defaults=accept_defaults,
    )
    print()


def screen_machine_services(state: WizardState, accept_defaults: bool) -> None:
    print("--- Machine-level services consumed by this project ---")
    print("Machine services are singletons — multiple projects can reference")
    print("the same service without duplicating its tmux seat.")
    available = ["memory"]  # v0.4 has only memory
    state.machine_services = _prompt_multiselect(
        "which machine services does this project consume?",
        choices=available,
        default=["memory"],
        required=["memory"],
        accept_defaults=accept_defaults,
    )
    print()


def screen_seats(state: WizardState, accept_defaults: bool) -> None:
    print("--- Project seats (the six-role enum) ---")
    print("ancestor + planner are required (§7 rule 3).")
    print("builder/reviewer/qa are the subagent-fanout seats (§8).")
    print("designer is singleton but declared (v2 requirement).")
    print()
    picked = _prompt_multiselect(
        "which seats should this project have?",
        choices=list(LEGAL_SEAT_ROLES),
        default=list(LEGAL_SEAT_ROLES),         # all 6
        required=["ancestor", "planner"],
        accept_defaults=accept_defaults,
    )
    seats: list[SeatChoice] = []
    for name in picked:
        rec = RECOMMENDED_OVERRIDES[name]
        print(f"\n-- {name} configuration --")
        tool = _prompt_choice(
            f"{name} tool",
            choices=["claude", "codex", "gemini"],
            default=rec["tool"],
            accept_defaults=accept_defaults,
        )
        auth = _prompt_choice(
            f"{name} auth_mode",
            choices=list(LEGAL_AUTH_MODES),
            default=rec["auth_mode"],
            accept_defaults=accept_defaults,
        )
        provider = _prompt(
            f"{name} provider",
            default=rec["provider"],
            accept_defaults=accept_defaults,
        )
        parallel = 1
        if name in PARALLEL_OK:
            parallel = _prompt_int(
                f"{name} parallel_instances (1..10)",
                default=1, lo=1, hi=10,
                accept_defaults=accept_defaults,
            )
        seats.append(SeatChoice(
            name=name, tool=tool, auth_mode=auth, provider=provider, parallel_instances=parallel,
        ))
    state.seats = seats
    print()


def screen_review(state: WizardState) -> None:
    print("--- Review ---")
    print(f"project_name                = {state.project_name}")
    print(f"repo_root                   = {state.repo_root}")
    print(f"openclaw_frontstage_agent   = {state.openclaw_frontstage_agent}")
    print(f"machine_services            = {state.machine_services}")
    print(f"seats ({len(state.seats)})")
    for s in state.seats:
        suffix = f"  parallel={s.parallel_instances}" if s.name in PARALLEL_OK else ""
        print(f"   - {s.name:<9} {s.tool:<7} {s.auth_mode:<11} {s.provider}{suffix}")
    print()


# ─────────────────────────────────────────────────────────────────────
# Payload construction (§4 canonical shape)
# ─────────────────────────────────────────────────────────────────────

def build_payload(state: WizardState) -> dict[str, Any]:
    """Return the v2 profile as a plain dict, ready for write_validated()."""
    tasks_root = f"~/.agents/tasks/{state.project_name}"
    seat_overrides: dict[str, dict[str, Any]] = {}
    for s in state.seats:
        entry: dict[str, Any] = {
            "tool": s.tool,
            "auth_mode": s.auth_mode,
            "provider": s.provider,
        }
        if s.name in PARALLEL_OK:
            entry["parallel_instances"] = s.parallel_instances
        seat_overrides[s.name] = entry

    payload: dict[str, Any] = {
        "version": 2,
        "profile_name": state.project_name,
        "template_name": "gstack-harness",
        "project_name": state.project_name,
        "repo_root": state.repo_root,
        "tasks_root": tasks_root,
        "project_doc": f"{tasks_root}/PROJECT.md",
        "tasks_doc": f"{tasks_root}/TASKS.md",
        "status_doc": f"{tasks_root}/STATUS.md",
        "send_script": "{CLAWSEAT_ROOT}/core/shell-scripts/send-and-verify.sh",
        "agent_admin": "{CLAWSEAT_ROOT}/core/scripts/agent_admin.py",
        "workspace_root": f"~/.agents/workspaces/{state.project_name}",
        "handoff_dir": f"{tasks_root}/patrol/handoffs",
        "machine_services": list(state.machine_services),
        "openclaw_frontstage_agent": state.openclaw_frontstage_agent,
        "seats": [s.name for s in state.seats],
        "seat_roles": {s.name: CANONICAL_ROLE_NAMES[s.name] for s in state.seats},
        "seat_overrides": seat_overrides,
        "dynamic_roster": {
            "enabled": True,
            "session_root": "~/.agents/sessions",
            "bootstrap_seats": ["ancestor"],
            "default_start_seats": ["ancestor", "planner"],
        },
        "patrol": {
            "planner_brief_path": f"{tasks_root}/planner/PLANNER_BRIEF.md",
            "cadence_minutes": state.patrol_cadence_minutes,
        },
        "observability": {
            "announce_planner_events": True,
            "announce_event_types": [
                "task.completed",
                "chain.closeout",
                "seat.blocked_on_modal",
                "seat.context_near_limit",
            ],
        },
    }
    return payload


# ─────────────────────────────────────────────────────────────────────
# Minimal TOML renderer — the REAL writer is profile_validator.write_validated.
# This fallback keeps the mockup self-contained so the wizard can still
# produce correct output for review before Phase 1 lands.
# ─────────────────────────────────────────────────────────────────────

def _toml_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return '"' + v.replace('\\', '\\\\').replace('"', '\\"') + '"'
    if isinstance(v, list):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    raise TypeError(f"unsupported toml value type: {type(v).__name__}")


def _render_v2_toml(payload: dict[str, Any]) -> str:
    out = io.StringIO()
    # Top-level scalars + arrays first, then tables.
    TABLES = {"seat_roles", "seat_overrides", "dynamic_roster", "patrol", "observability"}
    out.write("# Generated by core/tui/install_wizard.py (v0.4 layered model)\n")
    out.write("# Spec: docs/schemas/v0.4-layered-model.md §4\n\n")
    for k, v in payload.items():
        if k in TABLES:
            continue
        out.write(f"{k} = {_toml_value(v)}\n")
    out.write("\n")
    for table_name in ("seat_roles",):
        if table_name in payload:
            out.write(f"[{table_name}]\n")
            for k, v in payload[table_name].items():
                out.write(f"{k} = {_toml_value(v)}\n")
            out.write("\n")
    if "seat_overrides" in payload:
        for seat, overrides in payload["seat_overrides"].items():
            out.write(f"[seat_overrides.{seat}]\n")
            for k, v in overrides.items():
                out.write(f"{k} = {_toml_value(v)}\n")
            out.write("\n")
    for table_name in ("dynamic_roster", "patrol", "observability"):
        if table_name in payload:
            out.write(f"[{table_name}]\n")
            for k, v in payload[table_name].items():
                out.write(f"{k} = {_toml_value(v)}\n")
            out.write("\n")
    return out.getvalue().rstrip() + "\n"


# ─────────────────────────────────────────────────────────────────────
# Main flow
# ─────────────────────────────────────────────────────────────────────

_FEISHU_GROUP_RE = __import__("re").compile(r"^oc_[A-Za-z0-9_-]+$")


def screen_feishu_group(
    state: WizardState,
    *,
    accept_defaults: bool,
    distinct_from: str | None = None,
) -> str:
    """Collect the Feishu group chat_id for this project.

    Written to `~/.agents/tasks/<project>/PROJECT_BINDING.toml` at wizard
    end — ancestor's B5 will verify it at boot. v0.4 A-track requires a
    distinct group per project; if `distinct_from` is set (clone-from
    path), reject equal values.
    """
    print("--- Feishu group binding ---")
    print("Each project is bound to exactly one Feishu group chat_id (oc_xxx).")
    if distinct_from:
        print(f"This must differ from the source project's group ({distinct_from}).")
    print("To find chat_id: lark-cli im +chats-list --as user | grep <group-name>")
    print()
    while True:
        raw = _prompt("feishu chat_id (oc_...)", default="", accept_defaults=False)
        raw = raw.strip()
        if not raw:
            print("  → chat_id is required; ancestor's B5 will halt without it")
            continue
        if not _FEISHU_GROUP_RE.match(raw):
            print("  → invalid shape; must match 'oc_<alphanumerics/dash/underscore>'")
            continue
        if distinct_from and raw == distinct_from:
            print(f"  → must differ from source project's group ({distinct_from}); v0.4 A-track enforces distinct groups")
            continue
        return raw


def load_source_profile(source_project: str) -> dict[str, Any]:
    """Load an existing v2 profile from the standard path. Raises on missing/invalid."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]
    path = Path(f"~/.agents/profiles/{source_project}-profile-dynamic.toml").expanduser()
    if not path.is_file():
        raise SystemExit(
            f"error: source profile not found at {path}; cannot clone"
        )
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    if raw.get("version") != 2:
        raise SystemExit(
            f"error: source profile {path} is not v2 (got {raw.get('version')!r}); "
            "run `migrate-profile-to-v2 apply` on it first"
        )
    return raw


def clone_state_from_source(raw: dict[str, Any], new_project: str) -> WizardState:
    """Build WizardState from a source v2 profile, substituting project name."""
    state = WizardState(project_name=new_project)
    state.repo_root = raw.get("repo_root", "{CLAWSEAT_ROOT}")
    state.openclaw_frontstage_agent = raw.get("openclaw_frontstage_agent", "")
    state.machine_services = list(raw.get("machine_services", ["memory"]))
    state.patrol_cadence_minutes = int(raw.get("patrol", {}).get("cadence_minutes", 30))
    overrides = raw.get("seat_overrides", {}) or {}
    for role in raw.get("seats", []):
        ov = overrides.get(role, {}) or {}
        state.seats.append(SeatChoice(
            name=role,
            tool=ov.get("tool", "claude"),
            auth_mode=ov.get("auth_mode", "oauth_token"),
            provider=ov.get("provider", "anthropic"),
            parallel_instances=int(ov.get("parallel_instances", 1) or 1),
        ))
    return state


def _write_project_binding(project: str, feishu_group_id: str, bound_by: str) -> Path:
    """Write PROJECT_BINDING.toml via the canonical helper when available,
    else fall back to a minimal writer. Returns the file path."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
        from project_binding import bind_project
        return bind_project(
            project=project,
            feishu_group_id=feishu_group_id,
            bound_by=bound_by,
        )
    except Exception:
        # Stub writer (tests or environments without project_binding.py)
        path = Path(f"~/.agents/tasks/{project}/PROJECT_BINDING.toml").expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "version = 1\n"
            f'project = "{project}"\n'
            f'feishu_group_id = "{feishu_group_id}"\n'
            'feishu_bot_account = "koder"\n'
            "require_mention = false\n"
            f'bound_by = "{bound_by}"\n',
            encoding="utf-8",
        )
        return path


def run_wizard(
    *,
    project_override: str | None = None,
    accept_defaults: bool = False,
    dry_run: bool = False,
    out_path: Path | None = None,
    clone_from: str | None = None,
) -> dict[str, Any]:
    screen_welcome()
    state = WizardState()
    source_group: str | None = None

    if clone_from:
        if not project_override:
            print("error: --clone-from requires --project <new_name>", file=sys.stderr)
            raise SystemExit(2)
        print(f"--- Clone mode: copying from '{clone_from}' → '{project_override}' ---")
        source_raw = load_source_profile(clone_from)
        state = clone_state_from_source(source_raw, project_override)
        # Source's Feishu group id (if any) — we forbid reusing it per A-track.
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
            from project_binding import load_binding
            src_binding = load_binding(clone_from)
            source_group = src_binding.feishu_group_id if src_binding else None
        except Exception:
            source_group = None
        screen_review(state)
    else:
        screen_project_basics(state, project_override, accept_defaults)
        screen_openclaw_frontstage(state, accept_defaults)
        screen_machine_services(state, accept_defaults)
        screen_seats(state, accept_defaults)
        screen_review(state)

    feishu_group_id = screen_feishu_group(
        state,
        accept_defaults=accept_defaults,
        distinct_from=source_group,
    )

    payload = build_payload(state)
    if dry_run:
        print("--- Rendered v2 profile TOML (dry-run) ---")
        print(_render_v2_toml(payload))
        print(f"\n--- PROJECT_BINDING.toml would be written with feishu_group_id={feishu_group_id} ---")
        return payload

    if out_path is None:
        out_path = Path(
            f"~/.agents/profiles/{state.project_name}-profile-dynamic.toml"
        ).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final = write_validated(payload, out_path)
    print(f"wrote {final}")

    bound_by = f"install_wizard (clone-from={clone_from})" if clone_from else "install_wizard"
    binding_path = _write_project_binding(state.project_name, feishu_group_id, bound_by)
    print(f"wrote {binding_path}")

    if USE_REAL_ENGINE:
        # Round-trip: re-validate the file we just wrote.
        result = validate_profile_v2(final)
        if not result.ok:
            print(f"[!] validator rejected our output: {result.errors}", file=sys.stderr)
            raise SystemExit(3)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ClawSeat v0.4 install wizard")
    parser.add_argument("--project", help="project name (skip the prompt)")
    parser.add_argument("--accept-defaults", action="store_true",
                        help="non-interactive — accept all recommended defaults")
    parser.add_argument("--dry-run", action="store_true",
                        help="print TOML to stdout, don't write to disk")
    parser.add_argument("--out", type=Path, help="explicit output path")
    parser.add_argument("--clone-from",
                        help="clone from an existing v2 project (only asks for the new Feishu group)")
    args = parser.parse_args(argv)
    try:
        run_wizard(
            project_override=args.project,
            accept_defaults=args.accept_defaults,
            dry_run=args.dry_run,
            out_path=args.out,
            clone_from=args.clone_from,
        )
    except (KeyboardInterrupt, EOFError):
        print("\n[cancelled]", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
