"""ClawSeat skill registry — load, query, and validate the skill SSOT.

The registry lives in ``core/skill_registry.toml``.  Every skill referenced
by any template or install script must have an entry there.

This module is a pure library — the CLI lives in ``core/scripts/skill_manager.py``.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── Path constants ──────────────────────────────────────────────────

REPO_ROOT = Path(
    os.environ.get("CLAWSEAT_ROOT", str(Path(__file__).resolve().parents[1]))
)

DEFAULT_REGISTRY_PATH = REPO_ROOT / "core" / "skill_registry.toml"

# Source-specific install hints shown when a skill is missing.
SOURCE_INSTALL_HINTS: dict[str, str] = {
    "bundled": "Ensure the ClawSeat repo is intact: git status / git checkout",
    "gstack": "Install gstack: see https://github.com/gstack-cli/gstack",
    "agent": "Install lark-cli skills: see lark-cli skill install docs or copy from a peer machine",
}


# ── Data model ──────────────────────────────────────────────────────

@dataclass(slots=True)
class SkillEntry:
    """One skill in the registry."""

    name: str
    source: str  # "bundled" | "gstack" | "agent"
    path: str  # raw path with {CLAWSEAT_ROOT} / ~ placeholders
    required: bool
    roles: list[str] = field(default_factory=list)
    description: str = ""
    templates: list[str] = field(default_factory=list)  # empty = all templates
    entry_skill: bool = False


@dataclass(slots=True)
class SkillCheckItem:
    """Result of checking a single skill."""

    name: str
    source: str
    expanded_path: str
    exists: bool
    required: bool
    message: str
    fix_hint: str = ""


@dataclass(slots=True)
class SkillCheckResult:
    """Aggregated result of validating the full registry or a subset."""

    items: list[SkillCheckItem]

    @property
    def all_present(self) -> bool:
        return all(item.exists for item in self.items)

    @property
    def required_missing(self) -> list[SkillCheckItem]:
        return [i for i in self.items if not i.exists and i.required]

    @property
    def optional_missing(self) -> list[SkillCheckItem]:
        return [i for i in self.items if not i.exists and not i.required]

    @property
    def present(self) -> list[SkillCheckItem]:
        return [i for i in self.items if i.exists]

    def summary_lines(self) -> list[str]:
        lines: list[str] = []
        for item in self.items:
            if item.exists:
                lines.append(f"  [ok] {item.name}: {item.expanded_path}")
            else:
                tag = "BLOCKED" if item.required else "MISSING"
                lines.append(f"  [{tag}] {item.name}: {item.expanded_path}")
                if item.fix_hint:
                    lines.append(f"    -> {item.fix_hint}")
        req_missing = self.required_missing
        opt_missing = self.optional_missing
        if req_missing:
            lines.insert(0, f"skill_check: BLOCKED ({len(req_missing)} required skill(s) missing)")
        elif opt_missing:
            lines.insert(0, f"skill_check: WARNING ({len(opt_missing)} optional skill(s) missing)")
        else:
            lines.insert(0, f"skill_check: PASS ({len(self.items)} skills verified)")
        return lines


# ── Loaders ─────────────────────────────────────────────────────────

def _parse_entry(raw: dict[str, Any]) -> SkillEntry:
    return SkillEntry(
        name=str(raw.get("name", "")).strip(),
        source=str(raw.get("source", "bundled")).strip(),
        path=str(raw.get("path", "")).strip(),
        required=bool(raw.get("required", False)),
        roles=list(raw.get("roles", [])),
        description=str(raw.get("description", "")).strip(),
        templates=list(raw.get("templates", [])),
        entry_skill=bool(raw.get("entry_skill", False)),
    )


def load_registry(registry_path: Path | None = None) -> list[SkillEntry]:
    """Parse the skill registry TOML and return a list of SkillEntry."""
    path = registry_path or DEFAULT_REGISTRY_PATH
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return [_parse_entry(raw) for raw in data.get("skills", [])]


# ── Path helpers ────────────────────────────────────────────────────

def expand_skill_path(raw: str) -> Path:
    """Expand ``{CLAWSEAT_ROOT}`` and ``~`` in a skill path."""
    expanded = raw.replace("{CLAWSEAT_ROOT}", str(REPO_ROOT))
    return Path(os.path.expanduser(expanded))


def resolve_skill(entry: SkillEntry) -> tuple[Path, bool]:
    """Return (expanded_path, exists_on_disk)."""
    p = expand_skill_path(entry.path)
    return p, p.exists()


# ── Filters ─────────────────────────────────────────────────────────

def skills_for_source(entries: list[SkillEntry], source: str) -> list[SkillEntry]:
    """Filter entries by source type (bundled / gstack / agent)."""
    return [e for e in entries if e.source == source]


def skills_for_role(entries: list[SkillEntry], role: str) -> list[SkillEntry]:
    """Filter entries by role name."""
    return [e for e in entries if role in e.roles]


def skills_for_template(entries: list[SkillEntry], template_name: str) -> list[SkillEntry]:
    """Filter entries relevant to a template (empty templates list = all templates)."""
    return [e for e in entries if not e.templates or template_name in e.templates]


def external_skills(entries: list[SkillEntry]) -> list[SkillEntry]:
    """Return all non-bundled skills (gstack + agent)."""
    return [e for e in entries if e.source != "bundled"]


# ── Validation ──────────────────────────────────────────────────────

def _check_one(entry: SkillEntry) -> SkillCheckItem:
    expanded, exists = resolve_skill(entry)
    if exists:
        return SkillCheckItem(
            name=entry.name,
            source=entry.source,
            expanded_path=str(expanded),
            exists=True,
            required=entry.required,
            message=f"{entry.name} ({entry.source}): ok",
        )
    return SkillCheckItem(
        name=entry.name,
        source=entry.source,
        expanded_path=str(expanded),
        exists=False,
        required=entry.required,
        message=f"{entry.name} ({entry.source}): not found at {expanded}",
        fix_hint=SOURCE_INSTALL_HINTS.get(entry.source, ""),
    )


def validate_all(
    entries: list[SkillEntry] | None = None,
    *,
    registry_path: Path | None = None,
    role: str | None = None,
    source: str | None = None,
) -> SkillCheckResult:
    """Validate skill paths.  Returns a SkillCheckResult.

    Accepts optional filters:
    - *role*: check only skills for a specific role
    - *source*: check only skills from a specific source layer
    """
    if entries is None:
        entries = load_registry(registry_path)
    if role:
        entries = skills_for_role(entries, role)
    if source:
        entries = skills_for_source(entries, source)
    items = [_check_one(e) for e in entries]
    return SkillCheckResult(items=items)


# ── Template diff ───────────────────────────────────────────────────

def diff_template(template_name: str, entries: list[SkillEntry] | None = None) -> dict[str, list[str]]:
    """Compare a template's skill assignments against the registry.

    Returns ``{"unregistered": [...], "uncovered": [...]}``:
    - *unregistered*: skill paths in the template but not in the registry
    - *uncovered*: registry skills for the template's roles that the template doesn't assign
    """
    if entries is None:
        entries = load_registry()

    # Load the template
    tpl_path = REPO_ROOT / "core" / "templates" / template_name / "template.toml"
    if not tpl_path.exists():
        return {"error": [f"template not found: {tpl_path}"]}

    with open(tpl_path, "rb") as f:
        tpl = tomllib.load(f)

    # Collect all skill paths used in the template
    tpl_skill_paths: set[str] = set()
    tpl_roles: set[str] = set()
    for eng in tpl.get("engineers", []):
        role = str(eng.get("role", "")).strip()
        if role:
            tpl_roles.add(role)
        for skill in eng.get("skills", []):
            tpl_skill_paths.add(str(skill).strip())

    # Registry skill paths (expanded for comparison)
    registry_by_path: dict[str, SkillEntry] = {}
    for e in entries:
        registry_by_path[e.path] = e

    # 1. Skills in template but not in registry
    unregistered = [p for p in sorted(tpl_skill_paths) if p not in registry_by_path]

    # 2. Registry skills for these roles that template doesn't use
    relevant = [e for e in entries if any(r in tpl_roles for r in e.roles)]
    uncovered = [e.name for e in relevant if e.path not in tpl_skill_paths and not e.entry_skill]

    return {"unregistered": unregistered, "uncovered": uncovered}
