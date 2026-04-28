from __future__ import annotations

from typing import Final


DEFAULT_ROLE_SKILL: Final[str] = "clawseat"
SHARED_SKILLS: Final[tuple[str, ...]] = (
    "clawseat",
    "gstack-harness",
    "tmux-basics",
)
SEAT_SKILL_MAP: Final[dict[str, str]] = {
    "ancestor": "clawseat-ancestor",
    "planner": "planner",
    "memory": "memory-oracle",
    "builder": "builder",
    "reviewer": "reviewer",
    "patrol": "patrol",
    "qa": "patrol",
    "designer": "designer",
}


def seat_skill_key(seat_id: str) -> str:
    normalized = str(seat_id).strip().lower()
    if not normalized:
        return ""
    if normalized in SEAT_SKILL_MAP:
        return normalized
    return normalized.split("-", 1)[0]


def role_skill_for_seat(seat_id: str) -> str:
    return SEAT_SKILL_MAP.get(seat_skill_key(seat_id), DEFAULT_ROLE_SKILL)


def skill_names_for_seat(seat_id: str) -> list[str]:
    ordered = [role_skill_for_seat(seat_id), *SHARED_SKILLS]
    seen: set[str] = set()
    result: list[str] = []
    for item in ordered:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
