from __future__ import annotations

import re


PATROL_ALIASES: frozenset[str] = frozenset({"qa"})
PATROL_ALIAS_UNTIL = "2026-10-28"
_QA_NUMBERED_RE = re.compile(r"^qa-(?P<index>\d+)$")
_PATROL_NUMBERED_RE = re.compile(r"^patrol-(?P<index>\d+)$")


def normalize_seat_role(role: str) -> str:
    """Normalize the 6-month qa alias to canonical patrol role ids."""
    value = str(role).strip().lower()
    if value in PATROL_ALIASES:
        return "patrol"
    match = _QA_NUMBERED_RE.match(value)
    if match:
        return f"patrol-{match.group('index')}"
    return value


def patrol_legacy_aliases(role: str) -> list[str]:
    """Return legacy qa ids that can address a canonical patrol id."""
    value = str(role).strip().lower()
    if value == "patrol":
        return ["qa"]
    match = _PATROL_NUMBERED_RE.match(value)
    if match:
        return [f"qa-{match.group('index')}"]
    return []


def patrol_alias_candidates(role: str) -> list[str]:
    """Return role plus qa/patrol compatibility candidates, preserving order."""
    value = str(role).strip().lower()
    candidates = [value]
    normalized = normalize_seat_role(value)
    if normalized not in candidates:
        candidates.append(normalized)
    for alias in patrol_legacy_aliases(value):
        if alias not in candidates:
            candidates.append(alias)
    for alias in patrol_legacy_aliases(normalized):
        if alias not in candidates:
            candidates.append(alias)
    return candidates
